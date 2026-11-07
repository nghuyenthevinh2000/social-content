"""Social profile storage, query, URL normalization, and workbook parsing."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import openpyxl

WORKSPACE = Path(__file__).resolve().parents[3]
if os.environ.get("VIRAL_APP_RUNS"):
    RUNS_ROOT = Path(os.environ["VIRAL_APP_RUNS"])
elif getattr(sys, "frozen", False):
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    RUNS_ROOT = base / "AIBrand" / "runs"
else:
    RUNS_ROOT = WORKSPACE / "local" / "app-runs"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- Social profile URL and handle helpers -----------------------------------
def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower() or "sheet"


def facebook_handle(url: str) -> Tuple[str, str]:
    """Return (handle, canonical_url) from a Facebook profile/reel/page URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "profile.php" in parsed.path and query.get("id"):
        profile_id = query["id"][0]
        return f"profile_{profile_id}", f"https://www.facebook.com/profile.php?id={profile_id}"
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        handle = parts[0]
        return handle, f"https://www.facebook.com/{handle}"
    return parsed.netloc or "unknown", url


def is_facebook_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http") and ("facebook.com" in lowered or "fb.com" in lowered)


def clean_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# -- Workbook and source file resolution -------------------------------------
def parse_workbook(path: Path) -> List[Dict[str, Any]]:
    """Parse Excel sheets into topics with extracted social profile targets."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets: List[Dict[str, Any]] = []
    try:
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            targets: List[Dict[str, Any]] = []
            seen = set()
            for row in worksheet.iter_rows(values_only=True):
                raw_cells = [clean_name(str(cell)) if cell is not None else "" for cell in row]
                url_index = next((i for i, cell in enumerate(raw_cells) if is_facebook_url(cell)), None)
                if url_index is None:
                    continue
                url = raw_cells[url_index]
                handle, canonical = facebook_handle(url)
                if canonical in seen:
                    continue
                seen.add(canonical)
                name = ""
                if url_index + 1 < len(raw_cells):
                    candidate = raw_cells[url_index + 1]
                    if candidate and not is_facebook_url(candidate) and candidate.lower() not in {
                        "tên kênh", "mô tả", "source lưu", "file excel", "chú ý", "chú ys",
                        "link chatbot", "chatbot tạo ảnh", "link page đối chiếu", "tên page",
                    }:
                        name = candidate
                targets.append(
                    {
                        "handle": handle,
                        "url": canonical,
                        "name": name or handle,
                        "category": sheet_name,
                    }
                )
            sheets.append(
                {
                    "name": sheet_name,
                    "slug": slugify(sheet_name),
                    "is_aggregate": slugify(sheet_name) == "tong-hop",
                    "targets": targets,
                }
            )
    finally:
        workbook.close()
    return sheets


def resolve_xlsx_bytes(raw: bytes, filename: str) -> Tuple[bytes, str]:
    """Return valid .xlsx bytes, converting Google Sheets URLs, .gsheet JSON, or custom JSON."""
    if raw.startswith(b"PK\x03\x04"):
        return raw, filename

    try:
        text = raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return raw, filename

    sheet_id: Optional[str] = None
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        sheet_id = match.group(1)
    else:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "sheets" in data and isinstance(data["sheets"], list):
                    wb = openpyxl.Workbook()
                    for idx, s in enumerate(data["sheets"]):
                        ws = wb.active if idx == 0 else wb.create_sheet(title=s.get("name", f"Sheet {idx+1}"))
                        ws.title = s.get("name", f"Sheet {idx+1}")
                        ws.append(["url", "name"])
                        for t in s.get("targets", []):
                            url = t.get("url") if isinstance(t, dict) else str(t)
                            name = t.get("name", "") if isinstance(t, dict) else ""
                            ws.append([url, name])
                    buf = io.BytesIO()
                    wb.save(buf)
                    stem = Path(filename).stem or "custom_sources"
                    clean_filename = f"{stem}.xlsx" if not stem.endswith(".xlsx") else stem
                    return buf.getvalue(), clean_filename
                if "doc_id" in data:
                    sheet_id = str(data["doc_id"])
                elif "url" in data and isinstance(data["url"], str):
                    url_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", data["url"])
                    if url_match:
                        sheet_id = url_match.group(1)
        except Exception:
            pass

    if sheet_id:
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                downloaded = resp.read()
                if downloaded.startswith(b"PK\x03\x04"):
                    stem = Path(filename).stem or f"google_sheet_{sheet_id[:8]}"
                    clean_filename = f"{stem}.xlsx" if not stem.endswith(".xlsx") else stem
                    return downloaded, clean_filename
                err_text = downloaded[:400].decode("utf-8", errors="ignore").lower()
                if "service login" in err_text or "accounts.google.com" in err_text:
                    raise ValueError(
                        "Google Sheet này chưa được cấp quyền công khai. Vui lòng mở file trên Google Drive → "
                        "chọn Chia sẻ (Share) → chọn 'Bất kỳ ai có đường liên kết' (Anyone with link - quyền Xem) rồi thử lại."
                    )
                raise ValueError("Không thể tải Google Sheet về định dạng Excel. Hãy kiểm tra quyền truy cập file.")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ValueError(
                    "Google Sheet bị từ chối truy cập (401/403). Vui lòng vào Chia sẻ (Share) → bật quyền xem công khai."
                ) from exc
            raise ValueError(f"Không thể tải Google Sheet (HTTP {exc.code}): {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"Lỗi kết nối khi tải Google Sheet: {exc.reason}") from exc

    return raw, filename


# -- Social Profile Store and Query ------------------------------------------
DEFAULT_SEEDS = [
    {
        "name": "Mẹ chồng - nàng dâu",
        "targets": [
            {"name": "Mẹ chồng vào bếp", "url": "https://www.facebook.com/100084795256037"},
            {"name": "Nàng dâu kể chuyện", "url": "https://www.facebook.com/Nangdaukechuyen"},
            {"name": "Mẹ dạy mẹo hay", "url": "https://www.facebook.com/Medaymeohay"},
        ],
    },
    {
        "name": "Thực phẩm bẩn",
        "targets": [{"name": "Đơn giản thôi", "url": "https://www.facebook.com/dongianthoi.ok"}],
    },
    {
        "name": "Vợ chồng",
        "targets": [{"name": "Gia trưởng lo cho em", "url": "https://www.facebook.com/Giatruonglochoem"}],
    },
    {
        "name": "Cỏ cây sức khoẻ",
        "targets": [{"name": "Sống khoẻ mỗi ngày", "url": "https://www.facebook.com/100084795256037"}],
    },
]


class SocialProfileStore:
    """SQLite-backed store for competitor social accounts organized by topic."""

    def __init__(self, path: Path) -> None:
        import sqlite3

        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            db.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
            db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_slug TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                handle TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(topic_slug, url)
            )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_profiles_topic ON profiles (topic_slug)")
        db = sqlite3.connect(path)
        db.execute("PRAGMA journal_mode=WAL")
        db.close()
        self._ensure_seeds()

    @contextmanager
    def _tx(self):
        import sqlite3

        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def _ensure_seeds(self) -> None:
        with self._tx() as db:
            count = db.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
            if count == 0:
                now = now_iso()
                for seed in DEFAULT_SEEDS:
                    slug = slugify(seed["name"])
                    db.execute("INSERT OR IGNORE INTO topics (slug, name, created_at) VALUES (?, ?, ?)", (slug, seed["name"], now))
                    for target in seed["targets"]:
                        handle, canonical = facebook_handle(target["url"])
                        db.execute(
                            "INSERT OR IGNORE INTO profiles (topic_slug, name, url, handle, created_at) VALUES (?, ?, ?, ?, ?)",
                            (slug, target["name"], canonical, handle, now),
                        )

    def list_topics(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query topics and attached social profiles, optionally filtered by keyword."""
        with self._tx() as db:
            rows = db.execute("SELECT slug, name FROM topics ORDER BY rowid ASC").fetchall()
            results: List[Dict[str, Any]] = []
            q = (query or "").strip().lower()
            for slug, name in rows:
                p_rows = db.execute(
                    "SELECT name, url, handle FROM profiles WHERE topic_slug = ? ORDER BY id ASC",
                    (slug,),
                ).fetchall()
                targets = [{"name": r[0], "url": r[1], "handle": r[2]} for r in p_rows]
                if q:
                    topic_matches = q in name.lower() or q in slug
                    matched_targets = [
                        t for t in targets
                        if q in t["name"].lower() or q in t["url"].lower() or q in t["handle"].lower()
                    ]
                    if topic_matches:
                        results.append({"name": name, "slug": slug, "targets": targets})
                    elif matched_targets:
                        results.append({"name": name, "slug": slug, "targets": matched_targets})
                else:
                    results.append({"name": name, "slug": slug, "targets": targets})
            return results

    def get_topic(self, slug: str) -> Optional[Dict[str, Any]]:
        with self._tx() as db:
            row = db.execute("SELECT slug, name FROM topics WHERE slug = ?", (slug,)).fetchone()
            if not row:
                return None
            slug, name = row
            p_rows = db.execute(
                "SELECT name, url, handle FROM profiles WHERE topic_slug = ? ORDER BY id ASC",
                (slug,),
            ).fetchall()
            return {
                "name": name,
                "slug": slug,
                "targets": [{"name": r[0], "url": r[1], "handle": r[2]} for r in p_rows],
            }

    def upsert_topic(self, name: str, targets: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        slug = slugify(name)
        now = now_iso()
        with self._tx() as db:
            db.execute(
                "INSERT INTO topics (slug, name, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET name = excluded.name",
                (slug, name.strip(), now),
            )
            if targets:
                for target in targets:
                    url = target.get("url") or ""
                    if not url:
                        continue
                    handle, canonical = facebook_handle(url)
                    t_name = clean_name(target.get("name") or handle)
                    db.execute(
                        "INSERT INTO profiles (topic_slug, name, url, handle, created_at) VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(topic_slug, url) DO UPDATE SET name = excluded.name",
                        (slug, t_name, canonical, handle, now),
                    )
        return self.get_topic(slug) or {"name": name, "slug": slug, "targets": targets or []}

    def add_profile(self, topic_name_or_slug: str, url: str, name: Optional[str] = None) -> Dict[str, Any]:
        slug = slugify(topic_name_or_slug)
        handle, canonical = facebook_handle(url)
        channel_name = clean_name(name or handle)
        now = now_iso()
        with self._tx() as db:
            row = db.execute("SELECT slug, name FROM topics WHERE slug = ?", (slug,)).fetchone()
            if not row:
                db.execute("INSERT INTO topics (slug, name, created_at) VALUES (?, ?, ?)", (slug, topic_name_or_slug.strip(), now))
            db.execute(
                "INSERT INTO profiles (topic_slug, name, url, handle, created_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(topic_slug, url) DO UPDATE SET name = excluded.name",
                (slug, channel_name, canonical, handle, now),
            )
        return self.get_topic(slug) or {"name": topic_name_or_slug, "slug": slug, "targets": []}

    def delete_profile(self, topic_slug: str, url: str) -> bool:
        _, canonical = facebook_handle(url)
        with self._tx() as db:
            res = db.execute(
                "DELETE FROM profiles WHERE topic_slug = ? AND (url = ? OR url = ?)",
                (topic_slug, url, canonical),
            )
            return res.rowcount > 0

    def delete_topic(self, topic_slug: str) -> bool:
        with self._tx() as db:
            db.execute("DELETE FROM profiles WHERE topic_slug = ?", (topic_slug,))
            res = db.execute("DELETE FROM topics WHERE slug = ?", (topic_slug,))
            return res.rowcount > 0

    def import_from_source(self, raw: bytes, filename: str) -> List[Dict[str, Any]]:
        """Parse an Excel or Google Sheet and persist the discovered topics and profiles."""
        import tempfile

        xlsx_bytes, _ = resolve_xlsx_bytes(raw, filename)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(xlsx_bytes)
            tmp_path = Path(tmp.name)
        try:
            sheets = parse_workbook(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        for sheet in sheets:
            self.upsert_topic(sheet["name"], sheet["targets"])
        return self.list_topics()


PROFILE_STORE = SocialProfileStore(RUNS_ROOT / "profiles.db")
