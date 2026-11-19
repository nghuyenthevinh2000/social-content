"""Video download, frame extraction, and lock-protected 7-day retention management."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
from typing import Callable, Dict, Iterator, List, Optional, Tuple
import urllib.request

from tools.loop.viral_analyzer import runtime
from tools.loop.viral_analyzer.video_research.config import TEMP_DIR

MANIFEST_FILENAME = "retention_manifest.json"


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


def _download_reel_video(
    reel_url: str,
    video_id: Optional[str],
    log: Callable[[str], None],
) -> Optional[Path]:
    """Download a single reel into an isolated temp path so parallel calls never collide."""
    target = runtime.unique_temp_path(f"reel_{video_id or 'saved'}", ".mp4", base_dir=TEMP_DIR)
    log(f"Tải video để phân tích hình ảnh: {target}")
    if download_video_stream(reel_url, target, is_reel_page=True):
        return target
    if target.exists():
        try:
            target.unlink()
        except OSError:
            pass
    log("Không tải được video; bỏ qua phân tích hình ảnh.")
    return None


def _extract_video_frames(video_path: Path, frame_dir: Path, count: int = 4) -> List[Path]:
    """Sample up to `count` frames (one every 3s) from a local video with FFmpeg."""
    from tools.loop.viral_analyzer.video_research.transcriber.local import ffmpeg_bin

    frame_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-i", str(video_path),
        "-vf", "fps=1/3,scale=720:-2",
        "-frames:v", str(count),
        str(frame_dir / "frame_%02d.jpg"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return sorted(frame_dir.glob("frame_*.jpg"))


def get_manifest_path(video_dir: Path) -> Path:
    return video_dir / MANIFEST_FILENAME


@contextmanager
def _manifest_lock(video_dir: Path) -> Iterator[None]:
    video_dir.mkdir(parents=True, exist_ok=True)
    lock_path = video_dir / "retention_manifest.lock"
    # ponytail: local-host flock; switch to DB-tracked media leases if shared object store replaces local disk.
    with lock_path.open("w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def load_manifest(video_dir: Path) -> Dict[str, Dict]:
    manifest_path = get_manifest_path(video_dir)
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_manifest(video_dir: Path, manifest: Dict[str, Dict]) -> None:
    runtime.atomic_write_json(get_manifest_path(video_dir), manifest)


def register_video(
    video_dir: Path,
    video_id: str,
    file_path: Path,
    retention_days: int = 7,
    now: Optional[datetime] = None,
) -> Dict:
    """Register newly downloaded video with expiration timestamp under file lock."""
    now_dt = now or datetime.now(timezone.utc)
    expires_at = now_dt + timedelta(days=retention_days)
    entry = {
        "video_id": video_id,
        "file_name": file_path.name,
        "downloaded_at": now_dt.isoformat(),
        "expires_at": expires_at.isoformat(),
        "retention_days": retention_days,
        "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
    }
    with _manifest_lock(video_dir):
        manifest = load_manifest(video_dir)
        manifest[video_id] = entry
        save_manifest(video_dir, manifest)
    return entry


def purge_expired_videos(
    video_dir: Path,
    retention_days: int = 7,
    now: Optional[datetime] = None,
) -> Tuple[int, int]:
    """Purge video files older than retention_days (1 week) under file lock."""
    if not video_dir.exists():
        return (0, 0)

    now_dt = now or datetime.now(timezone.utc)
    with _manifest_lock(video_dir):
        manifest = load_manifest(video_dir)
        purged_count = 0
        retained_count = 0

        updated_manifest: Dict[str, Dict] = {}
        for vid, entry in manifest.items():
            fname = entry.get("file_name")
            file_path = video_dir / fname if fname else None
            expires_str = entry.get("expires_at")
            is_expired = False
            if expires_str:
                try:
                    exp_dt = datetime.fromisoformat(expires_str)
                    is_expired = now_dt >= exp_dt
                except ValueError:
                    is_expired = True

            if is_expired:
                if file_path and file_path.exists():
                    try:
                        os.remove(file_path)
                        purged_count += 1
                    except Exception:
                        pass
            else:
                if file_path and file_path.exists():
                    retained_count += 1
                    updated_manifest[vid] = entry

        tracked_names = {e.get("file_name") for e in updated_manifest.values()}
        cutoff_ts = (now_dt - timedelta(days=retention_days)).timestamp()
        for f in video_dir.glob("*.mp4"):
            if f.name in tracked_names:
                continue
            try:
                if f.stat().st_mtime < cutoff_ts:
                    os.remove(f)
                    purged_count += 1
                else:
                    retained_count += 1
            except Exception:
                pass

        save_manifest(video_dir, updated_manifest)
        return (purged_count, retained_count)
