#!/usr/bin/env python3
"""
Skill Selection Injector (PreInvocation), backed by TypeSafe.

Fires before the model reasons on a turn. Reads the PreInvocation payload
from stdin, pulls the latest user message, runs it through
scripts/skill_selector.py's TypeSafe-backed skill router, and — if any
skill scores above threshold — injects an ephemeralMessage naming the
recommended skill(s) so the model considers loading them via the `skill`
tool before picking a path on its own.

Fails open: any error (missing key, bad payload, no skills matched) results
in no injection (empty injectSteps), never a hard failure of the turn.

Expected stdin payload (per Antigravity PreInvocation contract):
    {
      "conversationId": "...",
      "workspacePaths": [...],
      "modelName": "...",
      "transcriptPath": "...",
      "userMessage": "..."   # or read from transcriptPath if absent
    }

Expected stdout:
    {"injectSteps": [{"ephemeralMessage": "..."}]}   # or {"injectSteps": []}
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

NO_INJECTION = {"injectSteps": []}

# How many top-scoring skills to drill into for resource-level (template /
# reference) selection. Keeps the extra TypeSafe calls bounded even when
# several skills score above threshold.
MAX_RESOURCE_DRILLDOWNS = 2


def extract_user_message(payload: dict) -> str:
    """Get the latest user message from the payload, falling back to the
    transcript file if the engine doesn't pass it inline."""
    if payload.get("userMessage"):
        return payload["userMessage"]

    transcript_path = payload.get("transcriptPath")
    if not transcript_path or not Path(transcript_path).exists():
        return ""

    last_user_text = ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    entry.get("type") == "USER_INPUT"
                    or entry.get("role") == "user"
                    or entry.get("source") == "USER_EXPLICIT"
                ):
                    content = entry.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            part.get("text", "") for part in content
                            if isinstance(part, dict)
                        )
                    if isinstance(content, str) and content:
                        m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
                        if m:
                            content = m.group(1).strip()
                        last_user_text = content
    except Exception:
        return ""

    return last_user_text


def format_message(result: dict, resource_results: dict) -> str:
    from skill_selector import display_primary

    lines = ["NOTICE: TypeSafe skill router suggests the following for this request:"]

    lines.append(
        f"- Lead skill: '{display_primary(result.get('primary'))}' "
        f"(confidence {result['primary_confidence']:.2f})"
    )

    others = [
        r for r in result.get("recommended", [])
        if r["skill"] != result.get("primary")
    ]
    for r in others:
        lines.append(f"- Also relevant: '{r['skill']}' (p={r['probability']:.2f})")

    for skill_name, groups in resource_results.items():
        # A group is worth showing whenever it was actually evaluated (has
        # scores), even if nothing cleared the recommend threshold — that's
        # exactly the "no strong candidate" case we want to surface, not
        # silently drop.
        has_any = any(g.get("all_scores") for g in groups.values())
        if not has_any:
            continue
        lines.append(f"  Within '{skill_name}':")

        for group_label, resource_result in groups.items():
            if not resource_result.get("all_scores"):
                continue
            # Named groups mean this skill needs multiple *independent*
            # picks at once (e.g. a layout AND a design style) — label each
            # so they don't read as mutually-exclusive alternatives.
            prefix = f"  [{group_label}] " if group_label else "  "
            lines.append(
                f"{prefix}- Lead resource: '{display_primary(resource_result.get('primary'))}' "
                f"(confidence {resource_result['primary_confidence']:.2f})"
            )
            resource_others = [
                r for r in resource_result.get("recommended", [])
                if r["resource"] != resource_result.get("primary")
            ]
            for r in resource_others:
                lines.append(f"{prefix}- Also relevant: '{r['resource']}' (p={r['probability']:.2f})")

    lines.append(
        "Review the suggested skill(s) by viewing their SKILL.md via `view_file` if they fit, "
        "or proceed without them if none actually apply. If lead resources (template/reference/design) "
        "were named above, open those specific files too before deciding what to load — when a skill "
        "lists multiple bracketed groups, each is an independent pick to combine, not alternatives."
    )
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps(NO_INJECTION))
        return

    user_message = extract_user_message(payload)
    if not user_message:
        print(json.dumps(NO_INJECTION))
        return

    try:
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
            print(json.dumps(NO_INJECTION))
            return

        result = select_skills(user_message, skills)

        # Stage 2: for the skill(s) worth surfacing, drill into their
        # templates/references and let Jev pick which specific one(s) apply.
        # Capped to the top MAX_RESOURCE_DRILLDOWNS skills by probability so
        # a broad match across many skills doesn't fan out into a pile of
        # extra TypeSafe calls.
        candidate_names = []
        if result.get("primary"):
            candidate_names.append(result["primary"])
        for r in result.get("recommended", []):
            if r["skill"] not in candidate_names:
                candidate_names.append(r["skill"])
        candidate_names = candidate_names[:MAX_RESOURCE_DRILLDOWNS]

        resource_results = {}
        for skill_name in candidate_names:
            resources_by_group = discover_skill_resources(SKILLS_DIR / skill_name)
            if not resources_by_group:
                continue
            resource_results[skill_name] = select_resources(user_message, resources_by_group)
    except Exception:
        # Fail open: TypeSafe unavailable, bad request, etc.
        print(json.dumps(NO_INJECTION))
        return

    if not result.get("primary") and not result.get("recommended"):
        print(json.dumps(NO_INJECTION))
        return

    message = format_message(result, resource_results)
    print(json.dumps({"injectSteps": [{"ephemeralMessage": message}]}))


if __name__ == "__main__":
    main()
