"""Media storage and management for user profile and context images."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid

from tools.app.backend import blobs
from tools.app.backend.db import ro, tx
from tools.app.backend.profiles import now_iso

ALLOWED_MIMES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_MEDIA_BYTES = 10 * 1024 * 1024  # 10MB


class MediaStore:
    def __init__(self) -> None:
        pass

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
        media_id = uuid.uuid4().hex[:12]
        blob_key = f"media/{user_id}/{media_id}{ext}"

        # If uploading a new profile image, delete old profile images for this user
        if kind == "profile":
            with tx() as conn:
                cur = conn.execute("SELECT id, blob_key FROM user_media WHERE user_id = %s AND kind = 'profile'", (user_id,))
                rows = cur.fetchall()
                for old_id, old_path in rows:
                    try:
                        blobs.delete(old_path)
                    except Exception:
                        pass
                conn.execute("DELETE FROM user_media WHERE user_id = %s AND kind = 'profile'", (user_id,))

        blobs.put(blob_key, raw_bytes, content_type=mime)

        record = {
            "id": media_id,
            "user_id": user_id,
            "kind": kind,
            "path": blob_key,
            "blob_key": blob_key,
            "mime": mime,
            "bytes": len(raw_bytes),
            "created_at": now_iso(),
        }

        with tx() as conn:
            conn.execute(
                "INSERT INTO user_media (id, user_id, kind, blob_key, mime, bytes, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (record["id"], record["user_id"], record["kind"], record["blob_key"], record["mime"], record["bytes"], record["created_at"]),
            )

        return record

    def list_media(self, user_id: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with ro() as conn:
            if kind:
                cur = conn.execute(
                    "SELECT id, user_id, kind, blob_key, mime, bytes, created_at FROM user_media WHERE user_id = %s AND kind = %s ORDER BY created_at DESC",
                    (user_id, kind),
                )
            else:
                cur = conn.execute(
                    "SELECT id, user_id, kind, blob_key, mime, bytes, created_at FROM user_media WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,),
                )
            rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "user_id": r[1],
                "kind": r[2],
                "path": r[3],
                "blob_key": r[3],
                "mime": r[4],
                "bytes": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    def get_media(self, user_id: str, media_id: str) -> Optional[Dict[str, Any]]:
        with ro() as conn:
            cur = conn.execute(
                "SELECT id, user_id, kind, blob_key, mime, bytes, created_at FROM user_media WHERE id = %s AND user_id = %s",
                (media_id, user_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "kind": row[2],
            "path": row[3],
            "blob_key": row[3],
            "mime": row[4],
            "bytes": row[5],
            "created_at": row[6],
        }

    def delete_media(self, user_id: str, media_id: str) -> bool:
        with tx() as conn:
            cur = conn.execute("SELECT blob_key FROM user_media WHERE id = %s AND user_id = %s", (media_id, user_id))
            row = cur.fetchone()
            if not row:
                return False
            blob_key = row[0]
            conn.execute("DELETE FROM user_media WHERE id = %s AND user_id = %s", (media_id, user_id))
        try:
            blobs.delete(blob_key)
        except Exception:
            pass
        return True


MEDIA_STORE = MediaStore()
