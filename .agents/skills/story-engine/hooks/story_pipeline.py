#!/usr/bin/env python3
"""
Story Pipeline State Manager (Multi-Topic Registry).
Scoped specifically to story-engine skill.

State is kept in .agents/skills/story-engine/state/story_pipeline.json
(ignored by git via .agents/skills/story-engine/.gitignore).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Paths
SKILL_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = SKILL_DIR / "state"
STATE_FILE = STATE_DIR / "story_pipeline.json"
REPO_ROOT = Path(__file__).resolve().parents[4]


def normalize_rel_path(path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        try:
            return str(p.relative_to(REPO_ROOT))
        except ValueError:
            return path_str
    return str(p)


def load_registry() -> dict:
    if not STATE_FILE.exists():
        return {"active_topic": None, "registry": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if "registry" not in data:
            return {"active_topic": data.get("target_file"), "registry": {}}
        return data
    except Exception as e:
        print(f"Warning: Failed to parse {STATE_FILE}: {e}", file=sys.stderr)
        return {"active_topic": None, "registry": {}}


def save_registry(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_status() -> None:
    data = load_registry()
    registry = data.get("registry", {})
    active = data.get("active_topic")
    print(f"=== Story Engine Registry (Total: {len(registry)}) ===")
    print(f"Skill Dir:    {SKILL_DIR}")
    print(f"Active Topic: {active or 'None'}\n")

    if not registry:
        print("No story files registered yet.")
        return

    for path, info in registry.items():
        prefix = "👉 [ACTIVE] " if path == active else "   "
        print(f"{prefix}{path}")
        print(f"      Slug:                    {info.get('topic_slug')}")
        print(f"      Status:                  {info.get('status')}")
        print(f"      Root Conflict Confirmed: {info.get('root_conflict_confirmed')}")
        print(f"      Brief Approved:          {info.get('brief_approved')}")
        print(f"      Updated At:              {info.get('updated_at')}\n")


def cmd_init(target_file: str, topic_slug: str | None = None) -> None:
    data = load_registry()
    rel_path = normalize_rel_path(target_file)
    slug = topic_slug or Path(rel_path).stem

    data["active_topic"] = rel_path
    data["registry"][rel_path] = {
        "topic_slug": slug,
        "status": "RESEARCH_AND_ASSESSMENT",
        "root_conflict_confirmed": False,
        "brief_approved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_registry(data)
    print(f"✅ Registered story file in story-engine: '{slug}'")
    print(f"   Target File: {rel_path}")
    print("   Phase: RESEARCH_AND_ASSESSMENT. Drafting is strictly locked for this file.")


def ensure_human_caller() -> None:
    import os
    if os.environ.get("ANTIGRAVITY_AGENT") == "1":
        print(
            "❌ BỊ CHẶN (Self-Approval Forbidden):\n"
            "Lệnh này CHỈ ĐƯỢC PHÉP thực thi bởi CON NGƯỜI (User) từ Terminal cá nhân!\n"
            "Agent (AI) không có quyền tự phê duyệt Story Brief để vượt rào Story Engine.",
            file=sys.stderr
        )
        sys.exit(1)


def cmd_confirm_conflict(target_file: str | None = None) -> None:
    ensure_human_caller()
    data = load_registry()
    rel_path = normalize_rel_path(target_file) if target_file else data.get("active_topic")
    if not rel_path or rel_path not in data["registry"]:
        print(f"❌ Error: Story file '{rel_path}' not found in registry.", file=sys.stderr)
        sys.exit(1)

    topic = data["registry"][rel_path]
    topic["root_conflict_confirmed"] = True
    topic["status"] = "BRIEF_SUBMITTED"
    topic["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(data)
    print(f"✅ Root conflict confirmed for: {rel_path}. Phase: BRIEF_SUBMITTED.")


def cmd_approve_brief(target_file: str | None = None) -> None:
    ensure_human_caller()
    data = load_registry()
    rel_path = normalize_rel_path(target_file) if target_file else data.get("active_topic")
    if not rel_path or rel_path not in data["registry"]:
        print(f"❌ Error: Story file '{rel_path}' not found in registry.", file=sys.stderr)
        sys.exit(1)

    topic = data["registry"][rel_path]
    topic["status"] = "APPROVED"
    topic["brief_approved"] = True
    topic["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(data)
    print(f"🎉 Story Brief APPROVED for: {rel_path}!")
    print(f"   PreToolUse gate is now UNLOCKED exclusively for this target file.")


def cmd_complete(target_file: str | None = None) -> None:
    data = load_registry()
    rel_path = normalize_rel_path(target_file) if target_file else data.get("active_topic")
    if not rel_path or rel_path not in data["registry"]:
        print(f"❌ Error: Story file '{rel_path}' not found in registry.", file=sys.stderr)
        sys.exit(1)

    topic = data["registry"][rel_path]
    topic["status"] = "COMPLETED"
    topic["brief_approved"] = False  # Re-lock drafting to prevent accidental overwrite
    topic["updated_at"] = datetime.now(timezone.utc).isoformat()
    if data.get("active_topic") == rel_path:
        data["active_topic"] = None
    save_registry(data)
    print(f"🏁 Marked story file '{rel_path}' as COMPLETED and re-locked.")


def cmd_reset(target_file: str | None = None) -> None:
    data = load_registry()
    if target_file:
        rel_path = normalize_rel_path(target_file)
        if rel_path in data["registry"]:
            del data["registry"][rel_path]
            if data.get("active_topic") == rel_path:
                data["active_topic"] = None
            save_registry(data)
            print(f"🔄 Removed '{rel_path}' from story-engine registry.")
    else:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        print("🔄 Cleared entire story-engine registry.")


def main():
    parser = argparse.ArgumentParser(description="story-engine Pipeline State Manager")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show current story pipeline registry")

    init_parser = subparsers.add_parser("init", help="Register a new story file")
    init_parser.add_argument("--target-file", required=True, help="Target markdown file path (in any folder)")
    init_parser.add_argument("--topic", required=False, help="Topic slug / identifier")

    confirm_parser = subparsers.add_parser("confirm-conflict", help="Mark root conflict as confirmed")
    confirm_parser.add_argument("--target-file", required=False, help="Target file path (defaults to active)")

    approve_parser = subparsers.add_parser("approve-brief", help="Approve Story Brief to unlock drafting")
    approve_parser.add_argument("--target-file", required=False, help="Target file path (defaults to active)")

    complete_parser = subparsers.add_parser("complete", help="Mark topic as completed and re-lock")
    complete_parser.add_argument("--target-file", required=False, help="Target file path (defaults to active)")

    reset_parser = subparsers.add_parser("reset", help="Reset a topic or entire registry")
    reset_parser.add_argument("--target-file", required=False, help="Specific target file to remove")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "init":
        cmd_init(args.target_file, args.topic)
    elif args.command == "confirm-conflict":
        cmd_confirm_conflict(args.target_file)
    elif args.command == "approve-brief":
        cmd_approve_brief(args.target_file)
    elif args.command == "complete":
        cmd_complete(args.target_file)
    elif args.command == "reset":
        cmd_reset(args.target_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
