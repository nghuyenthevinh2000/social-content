#!/usr/bin/env python3
"""
Jev Percentage Suggestion — local-only demo server.

Serves the static/ frontend and relays a single POST call (via the
skill router) to TypeSafe's Jev endpoint, keeping TYPESAFE_API_KEY
server-side (the browser can never call TypeSafe directly: its CORS
policy rejects arbitrary origins).

Every request re-runs the two-stage skill router
(.agents/hooks/skill-selector/skill_selector.py) against whatever text the user typed and
returns BOTH stages, always:
  1. `skills`          — every discovered skill, ranked by confidence.
  2. `resource_groups` — a list of the top skill's discoverable resource
     groups (templates/references/design styles/...), each ranked by
     confidence. Most skills have exactly one group; skills that need
     more than one independent pick at once (e.g. `infographic` needs
     both a layout AND a design style) return one entry per group here
     instead of merging them into a single ranking.
Each section also carries `has_strong_primary`: whether Jev actually landed
on a single best-fit winner for that section, vs. every candidate scoring
too low/close to call — the frontend renders that as a distinct "no strong
candidate" state instead of just quietly ranking mediocre options.
The frontend renders these as stacked, animated bar sections — no raw
JSON or digits are shown, only bar length/color per item.

Run:
    uv run --project . python scripts/skill-selector-demo/server.py
    # then open http://127.0.0.1:8765 in a browser
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
STATIC_DIR = SCRIPT_DIR / "static"

sys.path.insert(0, str(REPO_ROOT / ".agents" / "hooks" / "skill-selector"))

HOST = "127.0.0.1"
PORT = 8765

MAX_ITEMS = 8  # cap how many bars we return per section so charts stay readable


def _ranked(scores: dict) -> list:
    items = sorted(
        ({"name": name, "confidence": score} for name, score in (scores or {}).items()),
        key=lambda x: -x["confidence"],
    )
    return items[:MAX_ITEMS]


def _analyze(text: str) -> dict:
    """Run the text through the two-stage Jev skill router and return both
    the skill-level ranking and one resource-level ranking per resource
    group discovered within the top skill."""
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    from skill_selector import (
        SKILLS_DIR,
        discover_skill_resources,
        discover_skills,
        select_resources,
        select_skills,
    )

    skills = discover_skills()
    if not skills:
        return {
            "skills": {"group": "skills", "items": [], "has_strong_primary": False},
            "resource_groups": [],
        }

    result = select_skills(text, skills)
    skills_section = {
        "group": "skills",
        "items": _ranked(result.get("all_scores")),
        "has_strong_primary": bool(result.get("primary")),
    }

    top_skill = result.get("primary")
    resource_groups = []

    if top_skill:
        resources_by_group = discover_skill_resources(SKILLS_DIR / top_skill)
        if resources_by_group:
            selection_by_group = select_resources(text, resources_by_group)
            for group_label, group_result in selection_by_group.items():
                # "" means the skill has just one natural resource domain —
                # label the section with the skill name. A named group means
                # this is one of several independent picks (e.g. "design",
                # "inforgraphic-templates") that combine, not alternatives.
                label = top_skill if not group_label else f"{top_skill} \u2192 {group_label}"
                resource_groups.append(
                    {
                        "group": label,
                        "items": _ranked(group_result.get("all_scores")),
                        "has_strong_primary": bool(group_result.get("primary")),
                    }
                )

    return {"skills": skills_section, "resource_groups": resource_groups}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/analyze":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
            text = (payload.get("text") or "").strip()
        except Exception:
            self._send_json(400, {"error": "bad request"})
            return

        if not text:
            self._send_json(400, {"error": "empty text"})
            return

        try:
            result = _analyze(text)
        except Exception as exc:  # fail loud here; it's a local dev tool
            self._send_json(500, {"error": str(exc)})
            return

        self._send_json(200, result)

    def do_GET(self):
        rel = self.path.lstrip("/") or "index.html"
        rel = rel.split("?", 1)[0]
        file_path = (STATIC_DIR / rel).resolve()

        if STATIC_DIR not in file_path.parents and file_path != STATIC_DIR:
            self._send_json(403, {"error": "forbidden"})
            return
        if not file_path.exists() or not file_path.is_file():
            self._send_json(404, {"error": "not found"})
            return

        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }
        content_type = content_types.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Jev percentage suggestion running at http://{HOST}:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
