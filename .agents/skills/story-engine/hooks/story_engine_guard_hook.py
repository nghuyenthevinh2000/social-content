#!/usr/bin/env python3
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = SKILL_DIR / 'state'
STATE_FILE = STATE_DIR / 'story_pipeline.json'
REPO_ROOT = Path(__file__).resolve().parents[4]

EXEMPT_NAMES = {
    'readme.md',
    'frontmatter.md',
    'agents.md',
    'gemini.md',
    'skill.md',
    'contributing.md',
}

def normalize_rel_path(path_str: str) -> str:
    p = Path(path_str)
    if p.is_absolute():
        try:
            return str(p.relative_to(REPO_ROOT))
        except ValueError:
            return path_str
    return str(p)

def is_story_engine_active_in_transcript(transcript_path_str: str | None) -> bool:
    if not transcript_path_str:
        return False
    p = Path(transcript_path_str)
    if not p.exists():
        return False
    try:
        content = p.read_text(encoding='utf-8')
        return 'skills/story-engine' in content or 'story-engine' in content
    except Exception:
        return False

def is_exempt_file(target_file_str: str) -> bool:
    if not target_file_str:
        return True
    path = Path(target_file_str).resolve()
    if path.suffix.lower() != '.md':
        return True
    if path.name.lower() in EXEMPT_NAMES:
        return True
    rel = normalize_rel_path(str(path))
    if rel.startswith('.agents/') or rel.startswith('scripts/') or '/scratch/' in str(path):
        return True
    return False

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps({'decision': 'allow'}))
        return

    tool_call = payload.get('toolCall') or {}
    tool_name = tool_call.get('name') or ''
    tool_args = tool_call.get('args') or {}

    if tool_name not in {'write_to_file', 'replace_file_content'}:
        print(json.dumps({'decision': 'allow'}))
        return

    target_file = tool_args.get('TargetFile') or ''
    if is_exempt_file(target_file):
        print(json.dumps({'decision': 'allow'}))
        return

    rel_target_path = normalize_rel_path(target_file)

    registry = {}
    if STATE_FILE.exists():
        try:
            state_data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            registry = state_data.get('registry', {})
        except Exception:
            registry = {}

    is_tracked = rel_target_path in registry
    transcript_path = payload.get('transcriptPath')
    story_engine_active = is_story_engine_active_in_transcript(transcript_path)

    if not is_tracked and not story_engine_active:
        print(json.dumps({'decision': 'allow'}))
        return

    if not is_tracked:
        reason = f'PRE-DRAFT GATE BLOCKED: Tep {rel_target_path} chua dang ky trong Story Pipeline! User can khoi tao va phe duyet brief.'
        print(json.dumps({'decision': 'deny', 'reason': reason}))
        return

    file_info = registry[rel_target_path]
    if not file_info.get('brief_approved', False):
        status = file_info.get('status', 'UNKNOWN')
        reason = f'PRE-DRAFT GATE BLOCKED: Bai viet {rel_target_path} o trang thai {status} (brief_approved: false)! User can chay approve-brief trong terminal.'
        print(json.dumps({'decision': 'deny', 'reason': reason}))
        return

    print(json.dumps({'decision': 'allow'}))

if __name__ == '__main__':
    main()
