#!/usr/bin/env python3
"""
Skill Selection, backed by TypeSafe.

Given a user's request, decides which skill(s) under .agents/skills/ should
be used, by asking TypeSafe one Noul ("should this skill apply?") per
discovered skill plus one Choice for the single best-fit "primary" skill.

Why Noul-per-skill instead of one Choice over all skills: several skills can
legitimately apply to the same request at once (e.g. "write a LinkedIn post
about our rebrand and make it sound human" -> story-engine + branding +
humanizer together). A Choice only ever returns one winner; a Noul per label
lets each skill be judged independently. The Choice question is layered on
top only to break ties / pick a lead skill for ordering.

Skills are discovered dynamically from each skill's YAML frontmatter
(`name` + `description` in SKILL.md), so adding, removing, or editing a
skill under .agents/skills/ requires no change here.

Usage:
    echo "make a pitch deck about our new pricing" | uv run --project . scripts/skill_selector.py
    uv run --project . scripts/skill_selector.py "make a pitch deck about our new pricing"

Stage 2: a skill is more than its SKILL.md — branding has 15+ reference docs
and a naming/ sub-tree, beautiful-html-templates has 34 templates described in
index.json, one-pager-html has bare template folders with no metadata at all.
Once a primary skill is chosen, `discover_skill_resources()` finds whatever
templates/references/etc. live inside that skill directory (trying a
structured index.json first, then frontmattered markdown, then scraping
index.html <title>/<h1> as a last resort), and `select_resources()` runs the
same Noul-per-option + Choice pattern over those to recommend which specific
template/reference to actually use.

Output (stdout, JSON):
    {
      "primary": "beautiful-html-templates",
      "primary_confidence": 0.93,
      "recommended": [
        {"skill": "beautiful-html-templates", "probability": 0.96},
        {"skill": "branding", "probability": 0.61}
      ],
      "all_scores": {"beautiful-html-templates": 0.96, "branding": 0.61, ...},
      "resources": {
        "primary": "coral",
        "primary_confidence": 0.88,
        "recommended": [{"resource": "coral", "probability": 0.91}, ...],
        "all_scores": {"coral": 0.91, "8-bit-orbit": 0.02, ...}
      }
    }

Setup:
    uv add typesafe-sdk python-dotenv pyyaml
    # TYPESAFE_API_KEY must be set, e.g. in .env at repo root
"""

import json
import re
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"

RECOMMEND_THRESHOLD = 0.5

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def discover_skills(skills_dir: Path = SKILLS_DIR) -> dict:
    """Parse name + description out of every SKILL.md's YAML frontmatter."""
    skills = {}
    if not skills_dir.exists():
        return skills

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
        match = FRONTMATTER_RE.match(text)
        if not match:
            continue
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            continue

        name = meta.get("name") or skill_md.parent.name
        description = meta.get("description") or ""
        if isinstance(description, str):
            description = " ".join(description.split())  # collapse whitespace
        skills[name] = description

    return skills


def _typesafe_select(request_text: str, options: dict) -> dict:
    """Generic Jev-backed selector: one Noul per option ("does this apply?")
    plus one Choice to pick the single best lead option. Used for both the
    skill-level pass (name -> description) and the resource-level pass
    within a chosen skill (template/reference id -> description)."""
    if not options:
        return {
            "primary": None,
            "primary_confidence": 0.0,
            "recommended": [],
            "all_scores": {},
        }

    from typesafe_sdk import Choice, Noul, TypeSafeClient

    questions = {}
    for key, description in options.items():
        questions[f"use::{key}"] = Noul(
            instructions=(
                f"Should '{key}' be selected to handle this request? "
                f"It is described as: {description}"
            )
        )

    choice_criteria = dict(options)
    choice_criteria["none"] = "No listed option is the right fit for this request."
    questions["primary_choice"] = Choice(
        instructions=(
            "Of the available options, which one is the single best, most "
            "specific fit to lead on this request? Pick 'none' if nothing "
            "listed truly applies."
        ),
        criteria=choice_criteria,
    )

    with TypeSafeClient() as client:
        response = client.system_one(
            state={"user_request": request_text},
            questions=questions,
        )

    all_scores = {}
    for key in options:
        answer = response.answers[f"use::{key}"]
        all_scores[key] = round(answer.noul, 4)

    recommended = sorted(
        (
            {"option": key, "probability": prob}
            for key, prob in all_scores.items()
            if prob >= RECOMMEND_THRESHOLD
        ),
        key=lambda item: -item["probability"],
    )

    primary_answer = response.answers["primary_choice"]

    return {
        "primary": primary_answer.choice if primary_answer.choice != "none" else None,
        "primary_confidence": round(primary_answer.confidence, 4),
        "recommended": recommended,
        "all_scores": all_scores,
    }


def select_skills(request_text: str, skills: dict) -> dict:
    result = _typesafe_select(request_text, skills)
    return {
        "primary": result["primary"],
        "primary_confidence": result["primary_confidence"],
        "recommended": [
            {"skill": r["option"], "probability": r["probability"]}
            for r in result["recommended"]
        ],
        "all_scores": result["all_scores"],
    }


# ---------------------------------------------------------------------------
# Stage 2: within a chosen skill, discover its templates/references/other
# sub-resources and let Jev pick which ones actually apply. Skills vary a lot
# in shape (a JSON template index, frontmattered markdown references, bare
# template folders with only an index.html, ...), so discovery tries a few
# patterns and takes whichever produces results, cheapest/most-structured
# first.
# ---------------------------------------------------------------------------

MAX_DESCRIPTION_CHARS = 400
_HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HTML_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _first_paragraph(markdown_text: str) -> str:
    """Best-effort short description from a markdown file's body: strip
    frontmatter and headings, return the first non-empty paragraph."""
    match = FRONTMATTER_RE.match(markdown_text)
    body = markdown_text[match.end():] if match else markdown_text

    paragraph_lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph_lines:
                break
            continue
        if stripped.startswith("#"):
            continue
        paragraph_lines.append(stripped)

    paragraph = _clean_text(" ".join(paragraph_lines))
    return paragraph[:MAX_DESCRIPTION_CHARS]


def _extract_html_description(html_path: Path) -> str:
    """Best-effort short description from a raw template HTML file: prefer
    <title>, fall back to the first <h1> text."""
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    for pattern in (_HTML_TITLE_RE, _HTML_H1_RE):
        m = pattern.search(text)
        if m:
            cleaned = _HTML_TAG_RE.sub(" ", m.group(1))
            cleaned = _clean_text(cleaned)
            if cleaned:
                return cleaned[:MAX_DESCRIPTION_CHARS]
    return ""


def discover_skill_resources(skill_dir: Path) -> dict:
    """Discover the sub-resources (templates, references, etc.) inside a
    single skill directory and return {resource_id: short_description}.

    Tries, in order, and returns on first non-empty match:
      1. A root `index.json` with a `templates` array (structured metadata:
         slug/name/tagline/best_for/avoid_for) — e.g. beautiful-html-templates.
      2. Frontmattered markdown files anywhere under the skill (excluding its
         own SKILL.md) — e.g. branding's references/*.md, templates/*/design.md.
         Falls back to the first paragraph when there's no `description` key.
      3. Bare template folders that only contain an index.html with no
         markdown/JSON metadata — e.g. one-pager-html's inforgraphic-templates.
         Description is scraped from <title>/<h1>.
    """
    resources = {}

    index_json = skill_dir / "index.json"
    if index_json.exists():
        try:
            data = json.loads(index_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        templates = data.get("templates") if isinstance(data, dict) else data
        for t in templates or []:
            if not isinstance(t, dict):
                continue
            slug = t.get("slug") or t.get("name")
            if not slug:
                continue
            parts = [t.get("name", ""), t.get("tagline", "")]
            if t.get("best_for"):
                parts.append(f"Best for: {t['best_for']}")
            if t.get("avoid_for"):
                parts.append(f"Avoid for: {t['avoid_for']}")
            resources[str(slug)] = _clean_text(" ".join(p for p in parts if p))
        if resources:
            return resources

    skip_dirs = {"evals", "scripts", "runtime", ".git"}
    for md_path in sorted(skill_dir.rglob("*.md")):
        if md_path == skill_dir / "SKILL.md":
            continue
        if skip_dirs & set(md_path.relative_to(skill_dir).parts[:-1]):
            continue
        rel = md_path.relative_to(skill_dir).as_posix()
        try:
            text = md_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        description = None
        match = FRONTMATTER_RE.match(text)
        if match:
            try:
                meta = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                meta = {}
            description = meta.get("description")
            if isinstance(description, str):
                description = _clean_text(description)

        if not description:
            description = _first_paragraph(text)

        if description:
            resources[rel] = description
    if resources:
        return resources

    for html_path in sorted(skill_dir.rglob("index.html")):
        rel_dir = html_path.parent.relative_to(skill_dir)
        if skip_dirs & set(rel_dir.parts):
            continue
        key = rel_dir.as_posix()
        resources[key] = _extract_html_description(html_path) or key.replace("-", " ")

    return resources


def select_resources(request_text: str, resources: dict) -> dict:
    """Stage-2 selection: given a skill's discovered sub-resources, pick
    which one(s) actually apply to this request."""
    result = _typesafe_select(request_text, resources)
    return {
        "primary": result["primary"],
        "primary_confidence": result["primary_confidence"],
        "recommended": [
            {"resource": r["option"], "probability": r["probability"]}
            for r in result["recommended"]
        ],
        "all_scores": result["all_scores"],
    }


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")

    if len(sys.argv) > 1:
        request_text = " ".join(sys.argv[1:])
    else:
        request_text = sys.stdin.read().strip()

    if not request_text:
        print(json.dumps({"error": "No request text provided."}))
        sys.exit(1)

    skills = discover_skills()
    if not skills:
        print(json.dumps({"error": f"No skills found under {SKILLS_DIR}"}))
        sys.exit(1)

    result = select_skills(request_text, skills)

    if result.get("primary"):
        resources = discover_skill_resources(SKILLS_DIR / result["primary"])
        if resources:
            result["resources"] = select_resources(request_text, resources)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
