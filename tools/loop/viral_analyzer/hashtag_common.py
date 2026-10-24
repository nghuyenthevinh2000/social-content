"""Shared primitives for hashtag generation and platform verification.

Stdlib only. No network, no ranking decisions, no provider-specific parsing.
"""

import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from tools.loop import storage


PROMPT_VERSION = 'hashtag-prompt-v2'
HISTORY_SCHEMA = '1.0.0'
HISTORY_RELATIVE = 'sources/viral/hashtag-performance.json'

REQUIRED_CONTEXT = ('product-marketing.json',)

# Viewer age is never collected, targeted or embedded in model context.
AGE_KEYS = {'age', 'age_band', 'age_range', 'viewer_age', 'audience_age',
            'age_target', 'min_age', 'max_age'}

# Private contact details, credentials and lead lists never leave the campaign.
SENSITIVE_KEYS = {'phone', 'email', 'password', 'token', 'api_key', 'apikey',
                  'secret', 'authorization', 'cookie', 'access_token',
                  'refresh_token', 'client_secret', 'leads', 'lead_list'}

LABELS = ('direct_application', 'adjacent_process', 'creative_only',
          'irrelevant', 'insufficient_evidence')

MAX_CONTEXT_FILE_BYTES = 200_000
MAX_CONTEXT_TOTAL_BYTES = 1_000_000
MAX_SEED_EXCERPT_CHARS = 2_000
MAX_SEEDS = 10
MAX_CANDIDATES = 20
DEFAULT_CANDIDATES = 8
MAX_HISTORY_EVALUATIONS = 20
MAX_PRIOR_ANALYSES = 5
MAX_PRIOR_ANALYSIS_BYTES = 20_000

EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)')


class Problems:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)

    @property
    def ok(self):
        return not self.errors


class HistoryConflict(ValueError):
    """An evaluation ID already exists with different content."""


def canonical_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def campaign_root(project):
    root = Path(project).resolve()
    if not root.is_dir():
        raise ValueError(f'campaign directory does not exist: {project}')
    if not root.name:
        raise ValueError('campaign directory must have a name')
    return root


def run_directory(root, run_id):
    storage.validate_run_id(run_id)
    return storage.project_file(root, f'sources/viral/{run_id}')


def artifact_directory(root, run_id):
    """New runs are tidy; resume flat legacy runs without moving evidence."""
    run = run_directory(root, run_id)
    legacy = any((run / name).exists() for name in (
        'context.json', 'candidates.json', 'plan.json', 'manifest.json',
        'relevance.json', 'calls', 'expansion'))
    if legacy and (run / 'artifacts').exists():
        raise ValueError('ambiguous run layout: both flat and artifacts/ data exist')
    if legacy:
        return run
    return storage.project_file(root, f'sources/viral/{run_id}/artifacts')


def write_run_report(root, run_id, context, *, state='pending', rows=(), detail=None):
    """Keep an honest collection handoff even when no samples can be reviewed."""
    run = run_directory(root, run_id)
    run.mkdir(parents=True, exist_ok=True)
    def cell(value):
        return str(value if value is not None else 'unknown').replace('|', '\\|').replace('\n', ' ')

    brief = storage.project_file(root, f'sources/viral/{run_id}/brief.md')
    if not brief.exists():
        brief.write_text(
            f'# Viral research brief: {run_id}\n\n'
            '| Field | Value |\n|---|---|\n'
            f'| Campaign | {cell(root.name)} |\n'
            f'| Platform | {cell(context.get("platform"))} |\n'
            f'| Market language | {cell(context.get("market_language"))} |\n'
            f'| Application | {cell(context.get("application"))} |\n'
            f'| Goal | {cell((context.get("context") or {}).get("goal"))} |\n'
            '| Scope | Product goal/catalog; optional past analyses. No spend authorization. |\n')
    report = storage.project_file(root, f'sources/viral/{run_id}/report.md')
    marker = '<!-- viral-analyzer: automatic collection report -->'
    if report.exists() and not report.read_text().startswith(marker):
        return report  # Never overwrite an agent/human-authored analysis.
    lines = [marker, f'# Viral research report: {run_id}', '',
             '```text', 'Brief → Collection → Evidence review → Final shortlist', '```', '',
             '| Field | Observation |', '|---|---|',
             f'| Outcome | {cell(state)} |',
             f'| Platform / market language | {cell(context.get("platform"))} / {cell(context.get("market_language"))} |',
             f'| Application | {cell(context.get("application"))} |',
             f'| Updated | {utc_now()} |',
             f'| Finding | {cell(detail or "Collection/review pending; no verified-video result claimed.")} |',
             '| Qualification | Not assessed by this collection report. Complete the linked-video report after evidence review. |', '',
             '| Query | Provider / endpoint | Outcome | Receipt charge | Evidence |',
             '|---|---|---|---|---|']
    lines.extend('| ' + ' | '.join(cell(value) for value in row) + ' |' for row in rows)
    next_action = ('Deprioritize this tested provider/query route for this campaign pending new evidence; do not repeat paid probes without approval.'
                   if state in ('no_results', 'failed') else
                   'Complete the current stage and review evidence before claiming a qualified shortlist.')
    lines.extend(['', '| Decision | Scope / next action |', '|---|---|',
                  f'| Recommendation | {next_action} |',
                  '| Limits | Empty/error responses do not prove the platform has no Vietnam audience or cannot support marketing. No buyer/sales effectiveness was measured. |',
                  '| Handoff | Agent must finalize this report, even for zero results, with query coverage, costs, failures, market-specific recommendation and uncertainty. |', ''])
    report.write_text('\n'.join(lines))
    return report


def load_json(path, label):
    if not path.is_file():
        raise ValueError(f'{label} is missing: {path}')
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f'{label} is not valid JSON: {exc}') from exc


def load_optional_json(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def normalize_term(text):
    if not isinstance(text, str):
        return ''
    return text.strip().lstrip('#').strip().casefold()


def history_key(kind, text):
    normalized = normalize_term(text)
    return normalized if kind == 'hashtag' else f'keyword:{normalized}'


def infer_query_kind(entry):
    kind = entry.get('query_kind')
    if kind in ('hashtag', 'keyword'):
        return kind
    endpoint = entry.get('source_endpoint') or ''
    if not endpoint:
        evaluations = entry.get('evaluations') or []
        latest = evaluations[-1] if evaluations and isinstance(evaluations[-1], dict) else {}
        endpoint = latest.get('source_endpoint') or ''
    return 'hashtag' if '/hashtag' in endpoint else 'keyword'


def empty_history(campaign):
    return {
        'schema_version': HISTORY_SCHEMA,
        'campaign': campaign,
        'updated_at': storage.now().isoformat().replace('+00:00', 'Z'),
        'description': ('Campaign-local, cross-run hit/miss history tracking hashtag '
                        'and vocabulary probe evaluations.'),
        'platforms': {},
    }


def load_history(root):
    """Read history with an explicit version reader; never coerce legacy versions."""
    path = Path(root) / HISTORY_RELATIVE
    if not path.is_file():
        return empty_history(Path(root).name)
    data = load_json(path, 'hashtag history')
    if not isinstance(data, dict):
        raise ValueError('hashtag history must be a JSON object')
    version = data.get('schema_version')
    if isinstance(version, int) or version != HISTORY_SCHEMA:
        raise ValueError(f'unsupported hashtag history schema_version: {version!r}')
    if not isinstance(data.get('platforms'), dict):
        raise ValueError('hashtag history requires a platforms object')
    if data.get('campaign') not in (None, Path(root).name):
        raise ValueError('hashtag history belongs to another campaign')
    return data


def history_entries(data):
    """Yield (platform, entry, evaluations) with an inferred query kind."""
    for platform, entries in (data.get('platforms') or {}).items():
        if not isinstance(entries, dict):
            continue
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            yield platform, entry, list(entry.get('evaluations') or [])


def history_feedback(data, platform, market_language=None, limit=MAX_HISTORY_EVALUATIONS):
    """Bounded, platform-matched prior evaluations; never proof of current quality."""
    rows = []
    for item_platform, entry, evaluations in history_entries(data):
        if item_platform != platform:
            continue
        for evaluation in evaluations:
            if market_language and evaluation.get('market_language') not in (None, market_language):
                continue
            rows.append({
                'key': entry.get('normalized_tag') or entry.get('original_tag'),
                'query_kind': infer_query_kind(entry),
                'checked_at': evaluation.get('checked_at'),
                'application': evaluation.get('application'),
                'market_language': evaluation.get('market_language'),
                'hits': evaluation.get('hits'),
                'misses': evaluation.get('misses'),
                'unknowns': evaluation.get('unknowns'),
                'unique_reviewed': evaluation.get('unique_reviewed'),
                'decision': evaluation.get('decision'),
                'reason': evaluation.get('reason'),
                'collection_status': evaluation.get('collection_status', 'unknown'),
            })
    rows.sort(key=lambda row: (row.get('checked_at') or '', row.get('key') or ''))
    return rows[-limit:]


def _redact_string(value):
    value = EMAIL_RE.sub('[redacted]', value)
    return PHONE_RE.sub('[redacted]', value)


def scrub(value, *, key=None):
    """Drop private/credential/age fields and redact contact details in text."""
    if isinstance(value, dict):
        clean = {}
        for child_key, child in value.items():
            lowered = str(child_key).lower()
            if lowered in SENSITIVE_KEYS or lowered in AGE_KEYS:
                continue
            clean[child_key] = scrub(child, key=lowered)
        return clean
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def resolve_context_files(root, problems):
    """Read only the product brief beneath the campaign; record missing inputs."""
    files = {}
    gaps = []
    total = 0
    for relative in REQUIRED_CONTEXT:
        try:
            path = storage.project_file(root, relative)
        except ValueError as exc:
            problems.error(str(exc))
            gaps.append({'kind': 'invalid_context_path', 'path': relative,
                         'detail': str(exc)})
            continue
        if not path.is_file():
            gaps.append({'kind': 'missing_context', 'path': relative,
                         'detail': 'required context file is missing'})
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            gaps.append({'kind': 'unreadable_context', 'path': relative,
                         'detail': str(exc)})
            continue
        if len(raw) > MAX_CONTEXT_FILE_BYTES:
            problems.error(f'{relative} exceeds the {MAX_CONTEXT_FILE_BYTES}-byte context limit')
            continue
        total += len(raw)
        if total > MAX_CONTEXT_TOTAL_BYTES:
            problems.error(f'campaign context exceeds the {MAX_CONTEXT_TOTAL_BYTES}-byte total limit')
            break
        text = raw.decode('utf-8', errors='replace')
        files[relative] = {'text': text, 'sha256': hashlib.sha256(raw).hexdigest(),
                           'bytes': len(raw)}
    return files, gaps


def parse_json_constant(files, relative, label, problems, gaps):
    item = files.get(relative)
    if item is None:
        return None
    try:
        return json.loads(item['text'])
    except ValueError as exc:
        gaps.append({'kind': 'unreadable_context', 'path': relative,
                     'detail': f'{label} is not valid JSON: {exc}'})
        return None


def prior_analyses(root, run_id, problems):
    """Bounded campaign-local derived analysis, never raw receipts or this run."""
    base = storage.project_file(root, 'sources/viral')
    current = run_directory(root, run_id)
    candidates = []
    for path in base.rglob('*'):
        relative = path.relative_to(base)
        if (path.suffix not in ('.md', '.json')
                or {'raw', 'calls', 'expansion'} & set(relative.parts)
                or not any(term in path.stem.lower() for term in
                           ('analysis', 'report', 'review', 'relevance', 'evaluation', 'creator-style'))
                or 'prompt' in path.stem.lower()):
            continue
        try:
            safe = storage.project_file(root, str(path.relative_to(root)))
            if safe.is_relative_to(current) or not safe.is_file():
                continue
            candidates.append((safe.stat().st_mtime_ns, str(path.relative_to(root)), safe))
        except (OSError, ValueError) as exc:
            problems.warn(f'prior analysis skipped: {path}: {exc}')
    analyses, sources = [], []
    for _, relative, path in sorted(candidates, reverse=True):
        if len(analyses) == MAX_PRIOR_ANALYSES:
            problems.warn(f'prior analysis context limited to {MAX_PRIOR_ANALYSES} newest readable files')
            break
        try:
            if path.stat().st_size > MAX_PRIOR_ANALYSIS_BYTES:
                problems.warn(f'prior analysis skipped: {relative} exceeds {MAX_PRIOR_ANALYSIS_BYTES} bytes')
                continue
            raw = path.read_bytes()
            text = raw.decode('utf-8')
            content = json.loads(text) if path.suffix == '.json' else text
        except (OSError, ValueError) as exc:
            problems.warn(f'prior analysis skipped: {relative}: {exc}')
            continue
        analyses.append({'path': relative, 'content': scrub(content)})
        sources.append({'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(),
                        'bytes': len(raw)})
    return analyses, sources


def bounded_seeds(items, problems):
    if items is None:
        return []
    if isinstance(items, dict):
        items = items.get('items') or items.get('seeds') or []
    if not isinstance(items, list):
        problems.error('seed evidence must be a list or an object with items')
        return []
    seeds = []
    for index, item in enumerate(items[:MAX_SEEDS]):
        if not isinstance(item, dict):
            problems.error(f'seed evidence [{index}] must be an object')
            continue
        excerpt = item.get('excerpt')
        if not isinstance(excerpt, str) or not excerpt.strip():
            problems.error(f'seed evidence [{index}].excerpt must be a nonempty string')
            continue
        url = item.get('url')
        if url is not None:
            if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
                problems.error(f'seed evidence [{index}].url must be an http(s) URL')
                continue
            parts = urlsplit(url)
            keys = {key.lower() for key in parse_qs(parts.query)}
            if parts.username or parts.password or keys & {
                    'token', 'access_token', 'api_key', 'apikey', 'secret', 'key'}:
                problems.error(f'seed evidence [{index}].url must not embed credentials')
                continue
        seeds.append({
            'id': str(item.get('id') or f'seed-{index + 1}'),
            'url': url,
            'platform': item.get('platform'),
            'excerpt': excerpt[:MAX_SEED_EXCERPT_CHARS],
        })
    if len(items) > MAX_SEEDS:
        problems.warn(f'seed evidence truncated to {MAX_SEEDS} items')
    return seeds


def write_json(path, data):
    storage.save(path, data)


def read_json_file(path, label):
    return load_json(Path(path), label)


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def decimal_string(value):
    try:
        from decimal import Decimal
        result = Decimal(str(value))
    except Exception:
        return None
    return result if result.is_finite() and result >= 0 else None


def append_evaluation(root, platform, key, record, *, original_term=None,
                      normalized_term=None, correction=False):
    """Single-evaluation wrapper around the batch merge."""
    return append_evaluations(root, [{
        'platform': platform, 'key': key, 'record': record,
        'original_term': original_term, 'normalized_term': normalized_term,
        'correction': correction,
    }])[0]


def append_evaluations(root, items):
    """Locked read-merge-write for all items; no partial write on conflict."""
    path = Path(root) / HISTORY_RELATIVE
    lock_path = path.with_suffix('.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = load_history(root)
            results = []
            changed = False
            for item in items:
                result = _merge_evaluation(data, item)
                results.append(result)
                changed = changed or result['status'] == 'appended'
            if changed:
                data['updated_at'] = utc_now()
                storage.save(path, data)
            return results
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _merge_evaluation(data, item):
    platform, key = item['platform'], item['key']
    record = copy.deepcopy(item['record'])
    bucket = data['platforms'].setdefault(platform, {})
    if not isinstance(bucket, dict):
        raise ValueError(f'hashtag history platform is not an object: {platform}')
    entry = bucket.get(key)
    if entry is None:
        entry = bucket[key] = {
            'original_tag': item.get('original_term') or key,
            'normalized_tag': item.get('normalized_term') or normalize_term(key),
            'query_kind': record.get('query_kind', 'hashtag'),
            'evaluations': [],
        }
    if not isinstance(entry, dict):
        raise ValueError(f'hashtag history entry is not an object: {platform}/{key}')
    evaluations = entry.setdefault('evaluations', [])
    if not isinstance(evaluations, list) or not all(
            isinstance(existing, dict) for existing in evaluations):
        raise ValueError(f'hashtag history evaluations are malformed: {platform}/{key}')
    same_probe = [existing for existing in evaluations
                  if existing.get('probe_id') == record.get('probe_id')
                  and existing.get('phase') == record.get('phase')]
    if same_probe:
        latest = same_probe[-1]
        if _same_evaluation(latest, record):
            return {'status': 'noop', 'evaluation_id': latest.get('evaluation_id')}
        if not item.get('correction'):
            raise HistoryConflict(
                f"evaluation for probe {record.get('probe_id')} already exists "
                f"({latest.get('evaluation_id')}); pass --correction to supersede")
        record['evaluation_id'] = f"{record['evaluation_id']}-r{len(same_probe) + 1}"
        record['supersedes'] = latest.get('evaluation_id')
    elif any(existing.get('evaluation_id') == record.get('evaluation_id')
             for existing in evaluations):
        raise HistoryConflict(
            f"evaluation_id already exists with different content: {record.get('evaluation_id')}")
    evaluations.append(record)
    return {'status': 'appended', 'evaluation_id': record['evaluation_id']}


def _same_evaluation(left, right):
    ignore = {'checked_at', 'evaluation_id', 'supersedes'}
    return ({k: v for k, v in left.items() if k not in ignore}
            == {k: v for k, v in right.items() if k not in ignore})
