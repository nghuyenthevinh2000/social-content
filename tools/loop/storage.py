"""Shared storage primitives: paths, config, atomic writes and evidence records.

No ranking or workflow decisions belong here.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]


def timestamp(value):
    if value is None:
        return None
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp must include a timezone.')
    return result.astimezone(timezone.utc)


def now():
    return datetime.now(timezone.utc)


def save(path, data):
    """Write JSON atomically inside the project."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence_revision(manifest):
    """Stable fingerprint of the recorded evidence set for review invalidation."""
    entries = sorted((item.get('path'), item.get('sha256'))
                     for item in manifest.get('evidence_files', []))
    payload = json.dumps(entries, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def validate_page_id(value):
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError('page_id must be a string containing ASCII digits.')
    return value


def project_file(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative:
        raise ValueError('Project file must be a nonempty relative path.')
    if Path(relative).is_absolute():
        raise ValueError('Project file must be relative to --project.')
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Project file must stay inside --project.')
    return path


def load_project(root):
    config = json.loads((Path(root) / 'loop/config.json').read_text())
    validate_page_id(config.get('page_id'))
    if config.get('hypotheses_file') is not None:
        project_file(root, config['hypotheses_file'])
    return config


def load_hypotheses(root, config):
    if not config.get('hypotheses_file'):
        return {}
    try:
        return json.loads(project_file(root, config['hypotheses_file']).read_text())
    except (OSError, ValueError):
        return {}


def gap_key(gap):
    """Stable identity for duplicate clean-up; keeps distinct placements separate."""
    return (gap.get('kind'), gap.get('placement_id'), gap.get('detail'))


def dedupe_gaps(gaps):
    seen = set()
    unique = []
    for gap in gaps:
        key = gap_key(gap)
        if key in seen:
            continue
        seen.add(key)
        unique.append(gap)
    return unique


def add_gap(manifest, gap):
    """Append a gap without duplicating the same kind/identity/detail."""
    gaps = manifest.setdefault('gaps', [])
    if gap_key(gap) not in {gap_key(item) for item in gaps}:
        gaps.append(gap)


def evidence_entry(manifest, relative):
    """Latest recorded entry for a path; the newest verified capture wins on reuse."""
    matches = [item for item in manifest.get('evidence_files', [])
               if item.get('path') == relative]
    return matches[-1] if matches else None


def note_hash_conflicts(manifest, relative):
    """Document contradictory historical hashes without discarding either one."""
    hashes = {item.get('sha256') for item in manifest.get('evidence_files', [])
              if item.get('path') == relative}
    if len(hashes) > 1:
        add_gap(manifest, {
            'kind': 'evidence_hash_conflict',
            'path': relative,
            'detail': (f"{relative} has {len(hashes)} recorded hashes "
                       f"({', '.join(sorted(h or '' for h in hashes))}); "
                       "the latest matching file is used and no historical file is overwritten."),
        })


def check_reusable_evidence(root, manifest, relative, ev_type=None):
    """Verify recorded path + hash + type before any collector is reused."""
    entry = evidence_entry(manifest, relative)
    if entry is None:
        return False, 'not_recorded'
    path = Path(root) / relative
    if not path.is_file():
        return False, 'missing'
    if entry.get('sha256') != sha256_file(path):
        return False, 'hash_mismatch'
    if ev_type and entry.get('type') != ev_type:
        return False, 'type_mismatch'
    return True, 'ok'


def repair_path(captures_dir, relative_name, manifest):
    """Never overwrite historical evidence; allocate a sibling repair path."""
    original = Path(relative_name)
    counter = manifest.setdefault('repair_attempts', {})
    attempt = int(counter.get(relative_name, 0)) + 1
    while True:
        candidate = captures_dir / 'repairs' / f"{original.stem}-repair{attempt}{original.suffix}"
        if not candidate.exists():
            break
        attempt += 1
    counter[relative_name] = attempt
    return candidate


def record_repair(manifest, original_relative, repair_relative, reason):
    add_gap(manifest, {
        'kind': 'evidence_repair',
        'path': original_relative,
        'repair_path': repair_relative,
        'detail': f"Prior evidence {original_relative} was {reason}; it is preserved. Re-collection targets {repair_relative}.",
    })


def record_evidence_file(manifest, path_str, sha256_hash, ev_type, *, parent_path=None):
    for entry in manifest.setdefault('evidence_files', []):
        if entry.get('path') == path_str:
            if entry.get('sha256') != sha256_hash:
                add_gap(manifest, {
                    'kind': 'evidence_hash_conflict',
                    'path': path_str,
                    'detail': f"{path_str} was recorded as {entry.get('sha256')} but now hashes to {sha256_hash}; the historical hash is preserved and this write is not accepted.",
                })
                return False
            if ev_type and entry.get('type') != ev_type:
                entry['type'] = ev_type
            return True
    entry = {'path': path_str, 'sha256': sha256_hash, 'type': ev_type}
    if parent_path:
        entry['parent_path'] = parent_path
    manifest['evidence_files'].append(entry)
    return True


def validate_run_id(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r'[\w\-\.]+', run_id) or '..' in run_id:
        raise ValueError(f"Invalid run ID '{run_id}': path traversal or invalid characters.")
    return run_id


def run_directory(root, run_id):
    root = Path(root).resolve()
    validate_run_id(run_id)
    return root / 'loop/runs' / run_id


def load_run(root, run_id):
    root = Path(root).resolve()
    run_dir = run_directory(root, run_id)
    manifest_path = run_dir / 'manifest.json'
    if not manifest_path.is_file():
        raise ValueError(f"Run '{run_id}' does not exist; cannot operate on it.")
    return run_dir, json.loads(manifest_path.read_text())


def load_actions(root):
    path = Path(root) / 'loop/actions.jsonl'
    if not path.exists():
        return []
    actions = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            actions.append(json.loads(line))
        except ValueError:
            continue
    return actions
