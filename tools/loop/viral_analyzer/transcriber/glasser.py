"""Glasser API Transcriber for Facebook Reels.

Fetches platform-level transcripts directly via Glasser ScrapeCreators
(/v1/facebook/post/transcript) with PostgreSQL DB cache persistence.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional

from tools.app.backend import cost_control
from tools.loop.viral_analyzer.cache import (
    NO_TRANSCRIPT_SENTINEL,
    get_cached_transcript,
    save_cached_transcript,
)

logger = logging.getLogger(__name__)


def fetch_reel_transcript(
    reel_url: str,
    video_id: Optional[str] = None,
    timeout: float = 35.0,
) -> Optional[str]:
    """Fetch transcript for a Facebook Reel via Glasser ScrapeCreators /v1/facebook/post/transcript.

    Checks centralized DB cache first. If missing, runs Glasser endpoint via cost_control and saves to DB.
    """
    if not reel_url:
        return None
    vid = video_id
    if not vid:
        m = re.search(r"/(?:reel|videos)/(\d+)", reel_url)
        if m:
            vid = m.group(1)
    if vid:
        cached = get_cached_transcript(vid, include_negative=True)
        if cached:
            cost_control.record_cost_event(
                provider="scrapecreators",
                endpoint="/v1/facebook/post/transcript",
                cost_micro=0,
                cache_hit=True,
                sub_action="transcript_cache",
            )
            return None if cached == NO_TRANSCRIPT_SENTINEL else cached

    url_hash = hashlib.sha256(reel_url.encode("utf-8")).hexdigest()[:16]
    key_id = vid or url_hash
    temp_out = Path(tempfile.gettempdir()) / f"glasser_tr_{key_id}.json"
    idempotency_key = f"tr-{key_id}-{int(time.time() // 86400)}"

    try:
        res = cost_control.run_glasser_tracked(
            provider="scrapecreators",
            endpoint="/v1/facebook/post/transcript",
            version=4,
            payload={"url": reel_url},
            idempotency_key=idempotency_key,
            out_file=temp_out,
            timeout=timeout,
            sub_action="transcript",
        )
        if res.get("not_found"):
            return None

        http_status = res.get("http_status")
        if temp_out.exists() and temp_out.stat().st_size > 0:
            with open(temp_out, "r", encoding="utf-8") as f:
                data = json.load(f)
                tr = data.get("transcript")
                if isinstance(tr, str) and tr.strip():
                    clean_tr = tr.strip()
                    if vid:
                        save_cached_transcript(vid, clean_tr, url=reel_url)
                    return clean_tr
                if data.get("error") or data.get("message"):
                    logger.warning(
                        "Glasser transcript error for %s: %s",
                        reel_url,
                        data.get("message") or data.get("error"),
                    )

        if vid and http_status in (400, 404):
            save_cached_transcript(vid, NO_TRANSCRIPT_SENTINEL, url=reel_url)
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
            m = re.search(r"/(?:reel|videos)/(\d+)", reel_url)
            if m:
                vid = m.group(1)
                item["video_id"] = vid
        if not reel_url and vid:
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
