"""Video download helpers shared by transcription and Reel visual research."""

from __future__ import annotations

from pathlib import Path
import subprocess
import urllib.request


def download_video_stream(
    url_or_cdn: str,
    target_path: Path,
    is_reel_page: bool = False,
    max_bytes: int = 80 * 1024 * 1024,
) -> bool:
    """Download video stream with direct CDN streaming and yt-dlp fallback."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not is_reel_page and (url_or_cdn.startswith("http://") or url_or_cdn.startswith("https://")):
        try:
            req = urllib.request.Request(
                url_or_cdn,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            downloaded = 0
            with urllib.request.urlopen(req, timeout=60) as resp, open(target_path, "wb") as out:
                while chunk := resp.read(64 * 1024):
                    out.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= max_bytes:
                        break
            return target_path.exists() and target_path.stat().st_size > 1000
        except Exception:
            pass

    try:
        from yt_dlp import YoutubeDL

        with YoutubeDL({
            "outtmpl": str(target_path),
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "noplaylist": True,
        }) as ydl:
            ydl.download([url_or_cdn])
        if target_path.exists() and target_path.stat().st_size > 1000:
            return True
    except Exception:
        pass

    cmd = [
        "uv", "run", "yt-dlp",
        "--skip-download", "false",
        "-f", "best[ext=mp4]/best",
        "-o", str(target_path),
        "--quiet",
        url_or_cdn,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        return res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 1000
    except Exception:
        return False
