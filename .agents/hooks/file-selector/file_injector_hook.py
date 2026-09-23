#!/usr/bin/env python3
"""
Folder and File Relevance Injector Hook (PreInvocation), backed by TypeSafe Jev.

Fires before the model begins reasoning on a turn. Reads the PreInvocation
payload from stdin, extracts the latest user message, determines which
directory AND specific files are relevant via `file_selector.py` (hierarchical
selection), and injects an ephemeral directive to drive the agent directly
to the right file without reading around the bush.

Fails open: any error results in an empty injectSteps, never blocking the turn.

Expected stdin (Antigravity PreInvocation contract):
    {
      "conversationId": "...",
      "workspacePaths": [...],
      "modelName": "...",
      "transcriptPath": "...",
      "userMessage": "..."   # optional inline
    }

Expected stdout:
    {"injectSteps": [{"ephemeralMessage": "..."}]}  or {"injectSteps": []}
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent

sys.path.insert(0, str(SCRIPT_DIR))

NO_INJECTION = {"injectSteps": []}


def extract_user_message(payload: dict) -> str:
    """Extract latest user message from payload or transcript file."""
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
                            part.get("text", "")
                            for part in content
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


def display_folder_name(folder: str) -> str:
    """Human-friendly label for the synthetic repo-root key ('.') from file_selector."""
    return "(repository root)" if folder == "." else folder


def format_scope_directive(result: dict) -> str:
    """Format the folder and file scoping instructions for the agent."""
    folder_res = result.get("folder", {})
    files_res = result.get("files", {})

    primary_folder = folder_res.get("primary")
    folder_conf = folder_res.get("primary_confidence", 0.0)

    lead_file = files_res.get("lead_file")
    lead_conf = files_res.get("lead_confidence", 0.0)
    rec_files = files_res.get("recommended", [])

    lines = [
        "[PINPOINT FILE & DIRECTORY DIRECTIVE - TypeSafe Jev System One]",
        "Semantic evaluation identified the exact directory and file(s) relevant to your request:"
    ]

    if primary_folder:
        lines.append(f"- Target Directory: `{display_folder_name(primary_folder)}` (confidence: {folder_conf:.2f})")

    if lead_file:
        lines.append(f"- Target Lead File: `{lead_file}` (confidence: {lead_conf:.2f})")

    additional_files = [r for r in rec_files if r.get("file") != lead_file]
    if additional_files:
        lines.append("Additional relevant file(s):")
        for r in additional_files[:4]:
            lines.append(f"  • `{r.get('file')}` (relevance: {r.get('probability', 0.0):.2f})")

    lines.append("")
    lines.append("Instructions for Agent:")
    if lead_file:
        lines.append(f"1. Start by inspecting `{lead_file}` directly using `view_file`.")
        lines.append("2. DO NOT wander across the repository or read around the bush in unrelated folders.")
        lines.append("3. Keep all tool calls focused strictly on the file(s) and directory identified above.")
    else:
        lines.append("1. Confine your file reading (`view_file`) and searches to the target directory above.")
        lines.append("2. DO NOT wander into unrelated folders or perform broad directory traversals.")

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

        from file_selector import select_hierarchical

        workspace_paths = payload.get("workspacePaths") or []
        workspace = Path(workspace_paths[0]) if workspace_paths else REPO_ROOT

        result = select_hierarchical(user_message, root_dir=workspace)
    except Exception:
        # Fail open
        print(json.dumps(NO_INJECTION))
        return

    folder_res = result.get("folder", {})
    files_res = result.get("files", {})

    has_folder = folder_res.get("primary") or folder_res.get("recommended")
    has_file = files_res.get("lead_file") or files_res.get("recommended")

    if not has_folder and not has_file:
        print(json.dumps(NO_INJECTION))
        return

    directive = format_scope_directive(result)
    print(json.dumps({"injectSteps": [{"ephemeralMessage": directive}]}))


if __name__ == "__main__":
    main()
