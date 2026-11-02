"""Video cache retention manager.

Enforces a configurable retention window (default 7 days / 1 week) for downloaded
video media. Tracks download timestamps in a manifest and purges video files
whose retention period has expired.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MANIFEST_FILENAME = "retention_manifest.json"


def get_manifest_path(video_dir: Path) -> Path:
    return video_dir / MANIFEST_FILENAME


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
    manifest_path = get_manifest_path(video_dir)
    tmp_path = manifest_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    tmp_path.replace(manifest_path)


def register_video(
    video_dir: Path,
    video_id: str,
    file_path: Path,
    retention_days: int = 7,
    now: Optional[datetime] = None,
) -> Dict:
    """Register newly downloaded video with expiration timestamp."""
    now_dt = now or datetime.now(timezone.utc)
    expires_at = now_dt + timedelta(days=retention_days)
    manifest = load_manifest(video_dir)
    entry = {
        "video_id": video_id,
        "file_name": file_path.name,
        "downloaded_at": now_dt.isoformat(),
        "expires_at": expires_at.isoformat(),
        "retention_days": retention_days,
        "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
    }
    manifest[video_id] = entry
    save_manifest(video_dir, manifest)
    return entry


def purge_expired_videos(
    video_dir: Path,
    retention_days: int = 7,
    now: Optional[datetime] = None,
) -> Tuple[int, int]:
    """Purge video files older than retention_days (1 week).
    
    Returns:
        (purged_count, retained_count)
    """
    if not video_dir.exists():
        return (0, 0)

    now_dt = now or datetime.now(timezone.utc)
    manifest = load_manifest(video_dir)
    purged_count = 0
    retained_count = 0

    # 1. Sweep manifest entries
    updated_manifest = {}
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

    # 2. Sweep unmanifested video files by file mtime
    cutoff_ts = (now_dt - timedelta(days=retention_days)).timestamp()
    for f in video_dir.glob("*.mp4"):
        if f.name in [e.get("file_name") for e in updated_manifest.values()]:
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
