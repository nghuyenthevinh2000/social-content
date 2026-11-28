"""PostgreSQL-backed video edit template store, sanitizer, and style extractor."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from tools.app.backend.db import ro, tx
from tools.app.backend.profiles import now_iso

WORKSPACE = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = WORKSPACE / ".agents/skills/video-editing/scripts/video_engine/templates"

ALLOWED_TEMPLATE_KEYS = {
    "name",
    "width",
    "height",
    "fps",
    "loudnorm",
    "theme",
    "color_grade",
    "step_anchor_style",
    "hook_card_style",
    "cta_style",
    "subtitle_style",
    "punch_zoom_scale",
    "punch_zoom_duration",
    "step_sfx",
    "cta_sfx",
}
ALLOWED_SFX = {"pop", "ding", "whoosh"}
STRIP_STYLE_KEYS = {
    "lines",
    "title",
    "body",
    "start",
    "end",
    "path",
    "input_video",
    "output_video",
    "sfx_dir",
    "alignment_json",
    "items",
    "windows",
    "events",
    "enabled",
    "type",
    "clause_bounds",
    "badges",
    "hook_banner",
    "hook_card",
}
_STYLE_DICT_KEYS = {"step_anchor_style", "hook_card_style", "cta_style", "subtitle_style"}
_PRIMITIVE_DICT_KEYS = {"theme", "color_grade"}


def _sanitize_style_dict(val: dict) -> dict:
    """Keep declarative style keys and strip content, timing, and path-like fields."""
    cleaned: dict = {}
    for k, v in val.items():
        if k in STRIP_STYLE_KEYS:
            continue
        if k == "font" and isinstance(v, str) and ("/" in v or "\\" in v or ".." in v):
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            cleaned[k] = v
    return cleaned


def sanitize_template_config(raw: Any) -> dict:
    """Return a safe, declarative-only copy of a template config dict."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for k in ALLOWED_TEMPLATE_KEYS:
        if k not in raw:
            continue
        v = raw[k]
        if k in _STYLE_DICT_KEYS:
            if isinstance(v, dict):
                cleaned = _sanitize_style_dict(v)
                if cleaned:
                    out[k] = cleaned
        elif k in _PRIMITIVE_DICT_KEYS:
            if isinstance(v, dict):
                cleaned = {
                    dk: dv
                    for dk, dv in v.items()
                    if isinstance(dv, (str, int, float, bool))
                }
                if cleaned:
                    out[k] = cleaned
        elif k in ("step_sfx", "cta_sfx"):
            if isinstance(v, str) and v in ALLOWED_SFX:
                out[k] = v
        elif k in ("width", "height", "fps"):
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                out[k] = int(v)
        elif k in ("punch_zoom_scale", "punch_zoom_duration"):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = float(v)
        elif k == "loudnorm":
            if isinstance(v, bool):
                out[k] = v
        elif k == "name":
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()[:80]
    return out


def extract_template_from_edit_config(cfg: dict, base_template: Optional[dict] = None) -> dict:
    """Extract a reusable style template from a concrete edit_config.json."""
    out = sanitize_template_config(base_template or {})
    if not isinstance(cfg, dict):
        return out

    for k in ("width", "height", "fps", "loudnorm"):
        if k in cfg:
            out[k] = cfg[k]

    sfx_sounds: list[str] = []
    for eff in cfg.get("effects") or []:
        if not isinstance(eff, dict):
            continue
        eff_type = str(eff.get("type") or "").strip().lower()
        if eff_type == "color_grade":
            grade = {
                dk: dv
                for dk, dv in eff.items()
                if dk not in ("type", "enabled") and isinstance(dv, (str, int, float, bool))
            }
            if grade:
                out["color_grade"] = grade
        elif eff_type == "hook_card" or (eff_type == "text_box" and eff.get("variant") == "hook"):
            style = _sanitize_style_dict(eff)
            if style:
                out["hook_card_style"] = style
        elif eff_type == "text_box" and eff.get("variant") == "info":
            style = _sanitize_style_dict(eff)
            if style:
                out["cta_style"] = style
        elif eff_type in ("text_box", "card"):
            style = _sanitize_style_dict(eff)
            if style:
                out["step_anchor_style"] = style
        elif eff_type in ("subtitles", "captions"):
            raw_sub: dict = {}
            if isinstance(eff.get("style"), dict):
                raw_sub.update(eff["style"])
            raw_sub.update(eff)
            items = eff.get("items")
            if isinstance(items, list) and items and isinstance(items[0], dict):
                for item_key in ("color", "font_size", "margin_v", "outline_color"):
                    if item_key not in raw_sub and item_key in items[0]:
                        raw_sub[item_key] = items[0][item_key]
            style = _sanitize_style_dict(raw_sub)
            if style:
                out["subtitle_style"] = style
        elif eff_type == "punch_zoom":
            if "punch_zoom_scale" not in out:
                win = (eff.get("windows") or [eff])[0] if isinstance(eff.get("windows"), list) and eff.get("windows") else eff
                if isinstance(win, dict):
                    if isinstance(win.get("scale"), (int, float)):
                        out["punch_zoom_scale"] = float(win["scale"])
                    if isinstance(win.get("start"), (int, float)) and isinstance(win.get("end"), (int, float)):
                        out["punch_zoom_duration"] = round(max(0.0, float(win["end"]) - float(win["start"])), 3)
        elif eff_type == "sfx":
            snd = eff.get("sound")
            if isinstance(snd, str) and snd in ALLOWED_SFX:
                sfx_sounds.append(snd)

    if sfx_sounds:
        out.setdefault("step_sfx", sfx_sounds[0])
        if len(sfx_sounds) > 1:
            out.setdefault("cta_sfx", sfx_sounds[-1])

    return sanitize_template_config(out)


def _decode_jsonb(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


class VideoTemplateStore:
    def sync_builtin_templates(self, templates_dir: Path = TEMPLATES_DIR) -> int:
        """Upsert built-in *.template.json files into video_templates (author_id IS NULL)."""
        if not templates_dir.is_dir():
            return 0
        count = 0
        now = now_iso()
        with tx() as conn:
            for p in sorted(templates_dir.glob("*.template.json")):
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                tpl_id = p.stem.removesuffix(".template")
                if not re.fullmatch(r"[a-zA-Z0-9_-]+", tpl_id):
                    continue
                cfg = sanitize_template_config(raw)
                name = str(cfg.get("name") or tpl_id).strip()[:80]
                conn.execute(
                    """
                    INSERT INTO video_templates (id, slug, name, author_id, visibility, config_json, created_at, updated_at)
                    VALUES (%s, %s, %s, NULL, 'public', %s::jsonb, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        config_json = EXCLUDED.config_json,
                        updated_at = EXCLUDED.updated_at
                    WHERE video_templates.author_id IS NULL
                    """,
                    (tpl_id, tpl_id, name, json.dumps(cfg, ensure_ascii=False), now, now),
                )
                count += 1
        return count

    def list_templates(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return public templates plus the caller's private templates."""
        with ro() as conn:
            if user_id:
                cur = conn.execute(
                    """
                    SELECT id, slug, name, author_id, visibility, config_json, created_at, updated_at
                    FROM video_templates
                    WHERE visibility = 'public' OR author_id = %s
                    ORDER BY (author_id IS NOT NULL) ASC, created_at DESC
                    """,
                    (user_id,),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT id, slug, name, author_id, visibility, config_json, created_at, updated_at
                    FROM video_templates
                    WHERE visibility = 'public'
                    ORDER BY (author_id IS NOT NULL) ASC, created_at DESC
                    """
                )
            rows = cur.fetchall()
        return [self._row_to_dict(r, viewer_id=user_id) for r in rows]

    def get_template(self, template_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch a template by id or slug if visible to the caller."""
        tid = (template_id or "").strip()
        if not tid:
            return None
        with ro() as conn:
            cur = conn.execute(
                """
                SELECT id, slug, name, author_id, visibility, config_json, created_at, updated_at
                FROM video_templates
                WHERE id = %s OR slug = %s
                """,
                (tid, tid),
            )
            row = cur.fetchone()
        if not row:
            return None
        item = self._row_to_dict(row, viewer_id=user_id)
        if item["visibility"] != "public" and item["author_id"] != user_id:
            return None
        return item

    def create_template(
        self,
        user_id: str,
        name: str,
        config: dict,
        visibility: str = "public",
    ) -> Dict[str, Any]:
        """Save a user-owned template into video_templates."""
        clean_name = (name or "").strip()
        if not clean_name or len(clean_name) > 80:
            raise ValueError("Template name must be 1–80 characters.")
        vis = (visibility or "public").strip().lower()
        if vis not in ("public", "private"):
            raise ValueError("Visibility must be 'public' or 'private'.")
        clean_cfg = sanitize_template_config(config)
        if not clean_cfg:
            raise ValueError("Template config has no valid style fields.")
        clean_cfg["name"] = clean_name

        tpl_id = f"tpl_{uuid.uuid4().hex[:10]}"
        slug_base = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "template"
        slug = f"{slug_base[:48]}-{uuid.uuid4().hex[:6]}"
        now = now_iso()

        with tx() as conn:
            conn.execute(
                """
                INSERT INTO video_templates (id, slug, name, author_id, visibility, config_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (tpl_id, slug, clean_name, user_id, vis, json.dumps(clean_cfg, ensure_ascii=False), now, now),
            )
        return self.get_template(tpl_id, user_id=user_id)  # type: ignore[return-value]

    def delete_template(self, user_id: str, template_id: str) -> str:
        """Delete a user-owned template. Returns 'deleted', 'forbidden', or 'not_found'."""
        with tx() as conn:
            cur = conn.execute(
                "SELECT author_id FROM video_templates WHERE id = %s FOR UPDATE",
                (template_id,),
            )
            row = cur.fetchone()
            if not row:
                return "not_found"
            author_id = row[0]
            if author_id is None or author_id != user_id:
                return "forbidden"
            conn.execute(
                "DELETE FROM video_templates WHERE id = %s AND author_id = %s",
                (template_id, user_id),
            )
        return "deleted"

    @staticmethod
    def _row_to_dict(row: tuple, viewer_id: Optional[str] = None) -> Dict[str, Any]:
        author_id = row[3]
        return {
            "id": row[0],
            "slug": row[1],
            "name": row[2],
            "source": "builtin" if author_id is None else "user",
            "author_id": author_id,
            "is_owner": bool(viewer_id and author_id == viewer_id),
            "visibility": row[4],
            "config": _decode_jsonb(row[5]),
            "created_at": row[6],
            "updated_at": row[7],
        }


TEMPLATE_STORE = VideoTemplateStore()
