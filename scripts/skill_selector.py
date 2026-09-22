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

Output (stdout, JSON):
    {
      "primary": "beautiful-html-templates",
      "primary_confidence": 0.93,
      "recommended": [
        {"skill": "beautiful-html-templates", "probability": 0.96},
        {"skill": "branding", "probability": 0.61}
      ],
      "all_scores": {"beautiful-html-templates": 0.96, "branding": 0.61, ...}
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


def select_skills(request_text: str, skills: dict) -> dict:
    from typesafe_sdk import Choice, Noul, TypeSafeClient

    questions = {}
    for name, description in skills.items():
        questions[f"use::{name}"] = Noul(
            instructions=(
                f"Should the '{name}' skill be used to handle this request? "
                f"It is described as: {description}"
            )
        )

    choice_criteria = {name: description for name, description in skills.items()}
    choice_criteria["none"] = "No listed skill is the right fit for this request."
    questions["primary_skill"] = Choice(
        instructions=(
            "Of the available skills, which one is the single best, most "
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
    for name in skills:
        answer = response.answers[f"use::{name}"]
        all_scores[name] = round(answer.noul, 4)

    recommended = sorted(
        (
            {"skill": name, "probability": prob}
            for name, prob in all_scores.items()
            if prob >= RECOMMEND_THRESHOLD
        ),
        key=lambda item: -item["probability"],
    )

    primary_answer = response.answers["primary_skill"]

    return {
        "primary": primary_answer.choice if primary_answer.choice != "none" else None,
        "primary_confidence": round(primary_answer.confidence, 4),
        "recommended": recommended,
        "all_scores": all_scores,
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
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
