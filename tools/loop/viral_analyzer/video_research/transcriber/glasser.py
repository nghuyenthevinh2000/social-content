"""Glasser API Transcriber for Facebook, YouTube, TikTok, and Instagram videos.

Fetches platform-level transcripts directly via Glasser ScrapeCreators
with single-flight deduplication, concurrency cap, and PostgreSQL DB cache persistence.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.loop.viral_analyzer import normalize, platforms, runtime
from tools.loop.viral_analyzer.cache import (
    NO_TRANSCRIPT_SENTINEL,
    get_cached_transcript,
    save_cached_transcript,
)

logger = logging.getLogger(__name__)
_extract_vid_from_url = platforms.extract_video_id
_resolve_transcript_endpoint = platforms.resolve_transcript_endpoint
_clean_webvtt = normalize.clean_webvtt
_extract_transcript_text = normalize.extract_transcript_text


def fetch_reel_transcript(
    reel_url: str,
    video_id: Optional[str] = None,
    timeout: float = 35.0,
    ctx: Optional[runtime.EngineContext] = None,
) -> Optional[str]:
    """Fetch transcript for a supported video URL via Glasser ScrapeCreators with DB cache."""
    if not reel_url:
        return None
    resolved = platforms.resolve_transcript_endpoint(reel_url)
    if not resolved:
        return None
    platform, endpoint, version = resolved

    from tools.app.backend import cost_control

    eng_ctx = ctx or runtime.default_context()
    vid = video_id or platforms.extract_video_id(reel_url)
    url_hash = hashlib.sha256(reel_url.encode("utf-8")).hexdigest()[:16]
    key_id = vid or url_hash

    with eng_ctx.single_flight.acquire(f"transcript:{platform}:{key_id}"):
        if vid:
            cached = get_cached_transcript(vid, include_negative=True, platform=platform)
            if cached:
                cost_control.record_cost_event(
                    provider="scrapecreators",
                    endpoint=endpoint,
                    cost_micro=0,
                    cache_hit=True,
                    sub_action="transcript_cache",
                )
                return None if cached == NO_TRANSCRIPT_SENTINEL else cached

        temp_out = runtime.unique_temp_path(f"glasser_tr_{key_id}", ".json")
        idempotency_key = f"tr-{platform}-{key_id}-{int(time.time() // 86400)}"

        try:
            with eng_ctx.glasser_semaphore:
                res = cost_control.run_glasser_tracked(
                    provider="scrapecreators",
                    endpoint=endpoint,
                    version=version,
                    payload={"url": reel_url},
                    idempotency_key=idempotency_key,
                    out_file=temp_out,
                    timeout=timeout,
                    sub_action="transcript",
                )
            if res.get("not_found"):
                return None

            http_status = res.get("http_status")
            data: Any = None
            if temp_out.exists() and temp_out.stat().st_size > 0:
                with open(temp_out, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    clean_tr = normalize.extract_transcript_text(data, platform)
                    if clean_tr:
                        if vid:
                            save_cached_transcript(vid, clean_tr, url=reel_url, platform=platform)
                        return clean_tr
                    if isinstance(data, dict) and (data.get("error") or data.get("message")):
                        logger.warning(
                            "Glasser transcript error for %s: %s",
                            reel_url,
                            data.get("message") or data.get("error"),
                        )

            if vid and (
                http_status in (400, 404)
                or (http_status == 200 and temp_out.exists() and not (isinstance(data, dict) and data.get("error")))
            ):
                save_cached_transcript(vid, NO_TRANSCRIPT_SENTINEL, url=reel_url, platform=platform)
        except cost_control.CostPolicyError as exc:
            logger.warning("Glasser transcript blocked for %s: %s", reel_url, exc)
        except Exception as exc:
            logger.warning("Glasser transcript failed for %s: %s", reel_url, exc)
        finally:
            if temp_out.exists():
                try:
                    temp_out.unlink()
                except OSError:
                    pass
    return None


def fetch_top_reels_transcripts(
    items: List[Dict[str, Any]],
    max_workers: int = 5,
    progress_cb: Optional[Callable[[str], None]] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> None:
    """Fetch transcripts concurrently for reels/topics and update them in place."""
    eng_ctx = ctx or runtime.default_context()

    def _fetch_one(item: Dict[str, Any]) -> None:
        if item.get("transcript") and str(item["transcript"]).strip():
            return
        reel_url = (
            item.get("reel_url")
            or item.get("url")
            or (item.get("source_urls", [""])[0] if item.get("source_urls") else "")
        )
        vid = item.get("video_id")
        if not vid and reel_url:
            vid = platforms.extract_video_id(reel_url)
            if vid:
                item["video_id"] = vid
        if not reel_url and vid:
            plat = str(item.get("platform") or "facebook").strip().lower()
            reel_url = platforms.fallback_video_url(plat, str(vid), str(item.get("author_handle") or ""))
            item["reel_url"] = reel_url

        if not reel_url:
            return

        tr = fetch_reel_transcript(reel_url=reel_url, video_id=vid, ctx=eng_ctx)
        if tr:
            item["transcript"] = tr
            item.setdefault("segments", [])
            item.setdefault("language", "vi")
            if vid:
                save_cached_transcript(
                    video_id=vid,
                    transcript=tr,
                    url=reel_url,
                    author_handle=item.get("author_handle", ""),
                    title=item.get("title", ""),
                    platform=item.get("platform"),
                )

    needed = [item for item in items if not (item.get("transcript") and str(item["transcript"]).strip())]
    if not needed:
        return

    if progress_cb:
        progress_cb(f"[*] Đang tải transcript từ Glasser cho {len(needed)} video...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {eng_ctx.submit_fn(executor, _fetch_one, it): it for it in needed}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass

    still_missing = [it for it in needed if not (it.get("transcript") and str(it["transcript"]).strip())]
    if not still_missing:
        return

    from tools.loop.viral_analyzer.video_research.collect import _download_reel_video, download_video_stream
    from tools.loop.viral_analyzer.video_research.pipeline import _transcribe_local_fallback

    _log = progress_cb or (lambda msg: logger.info(msg))
    _log(f"[*] Chạy transcript local dự phòng cho {len(still_missing)} video không có phụ đề nền tảng...")
    for item in still_missing:
        reel_url = (
            item.get("reel_url")
            or item.get("url")
            or (item.get("source_urls", [""])[0] if item.get("source_urls") else "")
        )
        vid = item.get("video_id") or (platforms.extract_video_id(reel_url) if reel_url else None)
        video_url = str(item.get("video_url") or "").strip()
        video_path = None
        downloaded_tmp = None
        try:
            if video_url:
                cand = runtime.unique_temp_path(f"tr_{vid or 'vid'}", ".mp4")
                if download_video_stream(video_url, cand):
                    video_path = cand
                    downloaded_tmp = cand
            if video_path is None and reel_url:
                video_path = _download_reel_video(reel_url, vid, _log)
                downloaded_tmp = video_path
            if video_path is not None:
                tr = _transcribe_local_fallback(video_path, vid, reel_url or video_url, _log)
                if tr:
                    item["transcript"] = tr
                    item.setdefault("segments", [])
                    item.setdefault("language", "vi")
        except Exception as exc:
            logger.warning("Local ASR fallback failed for %s: %s", reel_url or video_url, exc)
        finally:
            if downloaded_tmp is not None and downloaded_tmp.exists():
                try:
                    downloaded_tmp.unlink()
                except OSError:
                    pass


transcribe_reels_glasser = fetch_top_reels_transcripts


class GlasserTranscriber:
    """Cloud API Transcriber via Glasser ScrapeCreators."""

    engine = "glasser"

    def __init__(self, max_workers: int = 5, timeout: float = 35.0):
        self.max_workers = max_workers
        self.timeout = timeout

    def transcribe_reel(self, reel_url: str, video_id: Optional[str] = None) -> Optional[str]:
        return fetch_reel_transcript(reel_url=reel_url, video_id=video_id, timeout=self.timeout)

    def transcribe_reels(
        self,
        reels: List[Dict[str, Any]],
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        fetch_top_reels_transcripts(reels, max_workers=self.max_workers, progress_cb=progress_cb)
