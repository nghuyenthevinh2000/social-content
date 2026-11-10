"""Media storage and management for user profile and context images."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from tools.app.backend.profiles import RUNS_ROOT, now_iso

ALLOWED_MIMES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_MEDIA_BYTES = 10 * 1024 * 1024  # 10MB


class MediaStore:
    def __init__(self, db_path: Optional[Path] = None, media_dir: Optional[Path] = None) -> None:
        self.db_path = db_path or (RUNS_ROOT / "media.db")
        self.media_dir = media_dir or (RUNS_ROOT / "media")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            db.execute("""
            CREATE TABLE IF NOT EXISTS user_media (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                mime TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_media_user ON user_media (user_id, kind)")
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.close()

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout = 30000")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                try:
                    db.execute("ROLLBACK")
                except Exception:
                    pass
            raise
        finally:
            db.close()

    @contextmanager
    def _ro(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA busy_timeout = 30000")
        try:
            yield db
        finally:
            db.close()

    def save_media(self, user_id: str, kind: str, raw_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        if kind not in ("profile", "context"):
            raise ValueError(f"Invalid kind: '{kind}'. Must be 'profile' or 'context'.")
        mime = mime_type.split(";")[0].strip().lower()
        if mime not in ALLOWED_MIMES:
            raise ValueError(f"Unsupported media type: '{mime}'. Allowed: JPEG, PNG, WEBP.")
        if len(raw_bytes) > MAX_MEDIA_BYTES:
            raise ValueError(f"File too large: {len(raw_bytes)} bytes. Max allowed: {MAX_MEDIA_BYTES} bytes.")
        if len(raw_bytes) == 0:
            raise ValueError("Empty file.")

        ext = ALLOWED_MIMES[mime]
        user_dir = self.media_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # If uploading a new profile image, delete old profile images for this user
        if kind == "profile":
            with self._tx() as db:
                rows = db.execute("SELECT id, path FROM user_media WHERE user_id = ? AND kind = 'profile'", (user_id,)).fetchall()
                for old_id, old_path in rows:
                    try:
                        p = Path(old_path)
                        if p.exists():
                            p.unlink()
                    except OSError:
                        pass
                db.execute("DELETE FROM user_media WHERE user_id = ? AND kind = 'profile'", (user_id,))

        media_id = uuid.uuid4().hex[:12]
        file_path = user_dir / f"{media_id}{ext}"
        file_path.write_bytes(raw_bytes)

        record = {
            "id": media_id,
            "user_id": user_id,
            "kind": kind,
            "path": str(file_path),
            "mime": mime,
            "bytes": len(raw_bytes),
            "created_at": now_iso(),
        }

        with self._tx() as db:
            db.execute(
                "INSERT INTO user_media (id, user_id, kind, path, mime, bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record["id"], record["user_id"], record["kind"], record["path"], record["mime"], record["bytes"], record["created_at"]),
            )

        return record

    def list_media(self, user_id: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._ro() as db:
            if kind:
                rows = db.execute(
                    "SELECT id, user_id, kind, path, mime, bytes, created_at FROM user_media WHERE user_id = ? AND kind = ? ORDER BY created_at DESC",
                    (user_id, kind),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, user_id, kind, path, mime, bytes, created_at FROM user_media WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()

        return [
            {
                "id": r[0],
                "user_id": r[1],
                "kind": r[2],
                "path": r[3],
                "mime": r[4],
                "bytes": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    def get_media(self, user_id: str, media_id: str) -> Optional[Dict[str, Any]]:
        with self._ro() as db:
            row = db.execute(
                "SELECT id, user_id, kind, path, mime, bytes, created_at FROM user_media WHERE id = ? AND user_id = ?",
                (media_id, user_id),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "kind": row[2],
            "path": row[3],
            "mime": row[4],
            "bytes": row[5],
            "created_at": row[6],
        }

    def delete_media(self, user_id: str, media_id: str) -> bool:
        with self._tx() as db:
            row = db.execute("SELECT path FROM user_media WHERE id = ? AND user_id = ?", (media_id, user_id)).fetchone()
            if not row:
                return False
            path = Path(row[0])
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
            db.execute("DELETE FROM user_media WHERE id = ? AND user_id = ?", (media_id, user_id))
            return True


MEDIA_STORE = MediaStore()
