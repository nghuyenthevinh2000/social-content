#!/usr/bin/env python3
"""Business workflow: lessons/*.json -> infographic (template.html) -> LinkedIn post -> linkedin/results.json.

Dry run by default; pass --publish to actually post via tools.linkedin_agent.
"""
import argparse
import datetime
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

BIZ = Path(__file__).resolve().parent
REPO_ROOT = BIZ.parent.parent
LESSONS = BIZ / "lessons"
INFOGRAPHICS = BIZ / "infographics"
TEMPLATE = INFOGRAPHICS / "template.html"
RESULTS = BIZ / "linkedin" / "results.json"
HASHTAGS = "#B2BMarketing #GrowthStrategy #SalesPlaybook"


def render(data: dict, out_png: Path) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        page.add_init_script(f"window.__DATA__ = {json.dumps(data)}")
        page.goto(TEMPLATE.as_uri())
        page.wait_for_selector("body[data-ready]")
        page.evaluate("document.fonts.ready")
        page.locator("#canvas").screenshot(path=str(out_png))
        browser.close()


def linkedin_text(data: dict) -> str:
    lines = [f"❌ {p['trap']['title']}\n✅ {p['solution']['title']}" for p in data["pairs"][:4]]
    return (f"{data['title']}\n\n{data.get('subtitle', '')}\n\n" + "\n\n".join(lines)
            + f"\n\nFull breakdown in the infographic 👇\n\n{HASHTAGS}").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="only this lesson (name or stem)")
    ap.add_argument("--publish", action="store_true", help="post to LinkedIn (default: dry run)")
    args = ap.parse_args()

    files = sorted(LESSONS.glob("*.json"))
    if args.file:
        files = [f for f in files if args.file in (f.name, f.stem)]
    if not files:
        raise SystemExit(f"No lesson JSON found in {LESSONS}")

    items = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        png = INFOGRAPHICS / f.stem / "output.png"
        render(data, png)
        text = linkedin_text(data)
        cmd = ["uv", "run", "python", "-m", "tools.linkedin_agent", "post", "--text", text, "--image", str(png)]
        status, output = "staged_dry_run", None
        if args.publish:
            r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
            status, output = ("published" if r.returncode == 0 else "error"), (r.stdout or r.stderr).strip()
        print(f"{f.name}: {len(data['pairs'])} pairs -> {png.relative_to(REPO_ROOT)} [{status}]")
        items.append({
            "lesson": str(f.relative_to(REPO_ROOT)),
            "title": data["title"],
            "pairs": len(data["pairs"]),
            "image": str(png.relative_to(REPO_ROOT)),
            "linkedin": {"status": status, "text": text, "output": output},
        })

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({
        "updated_at": datetime.datetime.now().isoformat(),
        "dry_run": not args.publish,
        "items": items,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results: {RESULTS.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
