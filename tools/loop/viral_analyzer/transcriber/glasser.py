"""Glasser API Transcriber for Facebook Reels.

Fetches platform-level transcripts directly via Glasser ScrapeCreators
(/v1/facebook/post/transcript) with PostgreSQL DB cache persistence.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional

from tools.loop.viral_analyzer.cache import (
    get_cached_transcript,
    save_cached_transcript,
)


def fetch_reel_transcript(
    reel_url: str,
    video_id: Optional[str] = None,
    timeout: float = 35.0,
) -> Optional[str]:
    """Fetch transcript for a Facebook Reel via Glasser ScrapeCreators /v1/facebook/post/transcript.

    Checks centralized DB cache first. If missing, runs Glasser endpoint and saves to DB.
    """
    if not reel_url:
        return None
    vid = video_id
    if not vid:
        m = re.search(r"/(?:reel|videos)/(\d+)", reel_url)
        if m:
            vid = m.group(1)
    if vid:
        cached = get_cached_transcript(vid)
        if cached:
            return cached

    glasser_bin = shutil.which("glasser")
    if not glasser_bin:
        return None

    temp_out = Path(tempfile.gettempdir()) / f"glasser_tr_{vid or int(time.time() * 1000)}.json"
    idempotency_key = f"tr-{vid or int(time.time() * 1000)}-{int(time.time() // 86400)}"

    cmd = [
        glasser_bin,
        "run",
        "-p", "scrapecreators",
        "-e", "/v1/facebook/post/transcript",
        "-i", json.dumps({"url": reel_url}),
        "--endpoint-version", "4",
        "--idempotency-key", idempotency_key,
        "-o", str(temp_out),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if temp_out.exists() and temp_out.stat().st_size > 0:
            with open(temp_out, "r", encoding="utf-8") as f:
                data = json.load(f)
                tr = data.get("transcript")
                if isinstance(tr, str) and tr.strip():
                    clean_tr = tr.strip()
                    if vid:
                        save_cached_transcript(vid, clean_tr, url=reel_url)
                    return clean_tr
    except Exception:
        pass
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
        futures = {executor.submit(_fetch_one, it): it for it in needed}
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
