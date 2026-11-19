"""Glasser API Transcriber for Facebook, YouTube, TikTok, and Instagram videos.

Fetches platform-level transcripts directly via Glasser ScrapeCreators
with PostgreSQL DB cache persistence.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.app.backend import cost_control
from tools.facebook_agent.dm_crawl.crawler import REEL_PATTERNS
from tools.loop.viral_analyzer.cache import (
    NO_TRANSCRIPT_SENTINEL,
    get_cached_transcript,
    save_cached_transcript,
)

logger = logging.getLogger(__name__)


def _resolve_transcript_endpoint(reel_url: str) -> Optional[Tuple[str, str, int]]:
    if cost_control.is_valid_facebook_transcript_url(reel_url):
        return ("facebook", "/v1/facebook/post/transcript", 4)
    if cost_control.is_valid_youtube_transcript_url(reel_url):
        return ("youtube", "/v1/youtube/video/transcript", 4)
    if cost_control.is_valid_tiktok_transcript_url(reel_url):
        return ("tiktok", "/v1/tiktok/video/transcript", 4)
    if cost_control.is_valid_instagram_transcript_url(reel_url):
        return ("instagram", "/v2/instagram/media/transcript", 6)
    return None


def _clean_webvtt(raw: str) -> str:
    lines: List[str] = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped == "WEBVTT" or stripped.isdigit() or "-->" in stripped:
            continue
        if stripped.startswith(("NOTE", "Kind:", "Language:")):
            continue
        lines.append(stripped)
    return " ".join(lines).strip()


def _extract_transcript_text(data: Any, platform: str) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    if platform == "youtube":
        txt = data.get("transcript_only_text")
        if isinstance(txt, str) and txt.strip():
            return txt.strip()
        tr = data.get("transcript")
        if isinstance(tr, list):
            parts = [str(seg.get("text") or "").strip() for seg in tr if isinstance(seg, dict) and str(seg.get("text") or "").strip()]
            return " ".join(parts) if parts else None
        return tr.strip() if isinstance(tr, str) and tr.strip() else None
    if platform == "tiktok":
        tr = data.get("transcript")
        if isinstance(tr, str) and tr.strip():
            cleaned = _clean_webvtt(tr)
            if cleaned:
                return cleaned
        twt = data.get("transcript_with_timestamp")
        if isinstance(twt, list):
            parts = [str(seg.get("text") or "").strip() for seg in twt if isinstance(seg, dict) and str(seg.get("text") or "").strip()]
            return " ".join(parts) if parts else None
        return None
    if platform == "instagram":
        trs = data.get("transcripts")
        if isinstance(trs, list):
            parts = [
                str(t.get("text") or "").strip()
                for t in trs
                if isinstance(t, dict) and isinstance(t.get("text"), str) and t.get("text").strip()
            ]
            return " ".join(parts) if parts else None
        tr = data.get("transcript")
        return tr.strip() if isinstance(tr, str) and tr.strip() else None
    tr = data.get("transcript")
    return tr.strip() if isinstance(tr, str) and tr.strip() else None


def _extract_vid_from_url(reel_url: str) -> Optional[str]:
    if not reel_url:
        return None
    for pattern in REEL_PATTERNS:
        m = pattern.search(reel_url)
        if m and m.groups():
            return m.group(1)
    return None


def fetch_reel_transcript(
    reel_url: str,
    video_id: Optional[str] = None,
    timeout: float = 35.0,
) -> Optional[str]:
    """Fetch transcript for a Facebook, YouTube, TikTok, or Instagram video via Glasser ScrapeCreators.

    Checks centralized DB cache first. If missing, runs Glasser endpoint via cost_control and saves to DB.
    """
    if not reel_url:
        return None
    resolved = _resolve_transcript_endpoint(reel_url)
    if not resolved:
        return None
    platform, endpoint, version = resolved

    vid = video_id or _extract_vid_from_url(reel_url)
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

    url_hash = hashlib.sha256(reel_url.encode("utf-8")).hexdigest()[:16]
    key_id = vid or url_hash
    temp_out = Path(tempfile.gettempdir()) / f"glasser_tr_{key_id}.json"
    idempotency_key = f"tr-{platform}-{key_id}-{int(time.time() // 86400)}"

    try:
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
                clean_tr = _extract_transcript_text(data, platform)
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
                os.remove(temp_out)
            except Exception:
                pass
    return None


def fetch_top_reels_transcripts(
    items: List[Dict[str, Any]],
    max_workers: int = 5,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Fetch transcripts concurrently for reels/topics and update them in place."""
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
            vid = _extract_vid_from_url(reel_url)
            if vid:
                item["video_id"] = vid
        if not reel_url and vid:
            plat = str(item.get("platform") or "facebook").strip().lower()
            if plat == "youtube":
                reel_url = f"https://www.youtube.com/watch?v={vid}"
            elif plat == "tiktok":
                h = str(item.get("author_handle") or "").strip().lstrip("@")
                reel_url = f"https://www.tiktok.com/@{h}/video/{vid}" if h else f"https://www.tiktok.com/video/{vid}"
            elif plat == "instagram":
                reel_url = f"https://www.instagram.com/reel/{vid}/"
            else:
                reel_url = f"https://www.facebook.com/reel/{vid}"
            item["reel_url"] = reel_url

        if not reel_url:
            return

        tr = fetch_reel_transcript(reel_url=reel_url, video_id=vid)
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
        futures = {cost_control.submit_with_context(executor, _fetch_one, it): it for it in needed}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
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
