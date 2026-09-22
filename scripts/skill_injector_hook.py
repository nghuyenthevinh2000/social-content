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


def format_message(result: dict) -> str:
    lines = ["NOTICE: TypeSafe skill router suggests the following for this request:"]

    if result.get("primary"):
        lines.append(
            f"- Lead skill: '{result['primary']}' "
            f"(confidence {result['primary_confidence']:.2f})"
        )

    others = [
        r for r in result.get("recommended", [])
        if r["skill"] != result.get("primary")
    ]
    for r in others:
        lines.append(f"- Also relevant: '{r['skill']}' (p={r['probability']:.2f})")

    lines.append(
        "Review the suggested skill(s) by viewing their SKILL.md via `view_file` if they fit, "
        "or proceed without them if none actually apply."
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

        from skill_selector import discover_skills, select_skills

        skills = discover_skills()
        if not skills:
            print(json.dumps(NO_INJECTION))
            return

        result = select_skills(user_message, skills)
    except Exception:
        # Fail open: TypeSafe unavailable, bad request, etc.
        print(json.dumps(NO_INJECTION))
        return

    if not result.get("primary") and not result.get("recommended"):
        print(json.dumps(NO_INJECTION))
        return

    message = format_message(result)
    print(json.dumps({"injectSteps": [{"ephemeralMessage": message}]}))


if __name__ == "__main__":
    main()
