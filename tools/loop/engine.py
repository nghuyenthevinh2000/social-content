"""Persistent publication → 24h metrics → agent review queue (stdlib only)."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import parse_qs, urlparse
import uuid

from tools.loop import comparison


REPO_ROOT = Path(__file__).resolve().parents[2]
ENDPOINT = '/v1/facebook/post'


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _add_gap(manifest, gap):
    """Append a gap without duplicating the same kind/identity/detail."""
    gaps = manifest.setdefault('gaps', [])
    if comparison.gap_key(gap) not in {comparison.gap_key(item) for item in gaps}:
        gaps.append(gap)


def _evidence_entry(manifest, relative):
    """Latest recorded entry for a path; the newest verified capture wins on reuse."""
    matches = [item for item in manifest.get('evidence_files', [])
               if item.get('path') == relative]
    return matches[-1] if matches else None


def _note_hash_conflicts(manifest, relative):
    """Document contradictory historical hashes without discarding either one."""
    hashes = {item.get('sha256') for item in manifest.get('evidence_files', [])
              if item.get('path') == relative}
    if len(hashes) > 1:
        _add_gap(manifest, {
            'kind': 'evidence_hash_conflict',
            'path': relative,
            'detail': (f"{relative} has {len(hashes)} recorded hashes "
                       f"({', '.join(sorted(h or '' for h in hashes))}); "
                       "the latest matching file is used and no historical file is overwritten."),
        })


def _check_reusable_evidence(root, manifest, relative, ev_type=None):
    """Verify recorded path + hash + type before any collector is reused."""
    entry = _evidence_entry(manifest, relative)
    if entry is None:
        return False, 'not_recorded'
    path = Path(root) / relative
    if not path.is_file():
        return False, 'missing'
    if entry.get('sha256') != _sha256(path):
        return False, 'hash_mismatch'
    if ev_type and entry.get('type') != ev_type:
        return False, 'type_mismatch'
    return True, 'ok'


def _repair_path(captures_dir, relative_name, manifest):
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


def _record_repair(manifest, original_relative, repair_relative, reason):
    _add_gap(manifest, {
        'kind': 'evidence_repair',
        'path': original_relative,
        'repair_path': repair_relative,
        'detail': f"Prior evidence {original_relative} was {reason}; it is preserved. Re-collection targets {repair_relative}.",
    })


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
    config = json.loads((root / 'loop/config.json').read_text())
    validate_page_id(config.get('page_id'))
    if config.get('hypotheses_file') is not None:
        project_file(root, config['hypotheses_file'])
    return config


def initialize(root, page_id, hypotheses_file=None, *, dry_run=False):
    from tools.loop import project_init
    return project_init.bootstrap_project(
        root, page_id, hypotheses_file=hypotheses_file or 'posts/hypothesis.json', dry_run=dry_run
    )


def migrate(root, *, dry_run=False):
    """Migrate schema v1 publications.json to schema v2 with placement checkpoints."""
    root = Path(root).resolve()
    state_path = root / 'loop/publications.json'
    if not state_path.is_file():
        raise ValueError(f"State file {state_path} does not exist; cannot migrate.")

    config = load_project(root)
    page_id = config['page_id']

    raw_bytes = state_path.read_bytes()
    state = json.loads(raw_bytes.decode('utf-8'))

    version = state.get('schema_version', 1)
    if version == 2:
        return {
            'status': 'already_migrated',
            'schema_version': 2,
            'publications': len(state.get('publications', [])),
            'placements': len(state.get('placements', [])),
        }
    if version != 1:
        raise ValueError(f"Unsupported schema version: {version}")

    backup_path = root / 'loop/publications.json.v1.bak'
    publications = state.get('publications', [])
    placements = []

    for pub in publications:
        pub_id = pub['id']
        placement_id = f"{pub_id}-orig"
        permalink = pub.get('url')
        published_at = pub.get('published_at')
        is_visible = bool(permalink and published_at)
        pub_time = timestamp(published_at) if published_at else None

        due_24h = (pub_time + timedelta(hours=24)).isoformat() if pub_time else None
        due_7d = (pub_time + timedelta(days=7)).isoformat() if pub_time else None

        if pub.get('metrics_status') == 'collected':
            status_24h = 'collected'
            review_24h = pub.get('review_status', 'pending')
            selected_ref_24h = pub.get('receipt_file')
            attempts_24h = 1 if selected_ref_24h else 0
        elif pub.get('metrics_status') == 'needs_attention':
            status_24h = 'needs_attention'
            review_24h = pub.get('review_status', 'waiting_for_metrics')
            selected_ref_24h = pub.get('receipt_file')
            attempts_24h = 1 if selected_ref_24h else 0
        elif pub_time:
            status_24h = pub.get('metrics_status', 'pending')
            review_24h = pub.get('review_status', 'waiting_for_metrics')
            selected_ref_24h = None
            attempts_24h = 0
        else:
            status_24h = 'blocked'
            review_24h = 'waiting_for_metrics'
            selected_ref_24h = None
            attempts_24h = 0

        # Note: 7d checkpoint is never completed from a late 24h snapshot
        status_7d = 'pending' if pub_time else 'blocked'
        review_7d = 'waiting_for_metrics'
        selected_ref_7d = None
        attempts_7d = 0

        placements.append({
            'id': placement_id,
            'publication_id': pub_id,
            'kind': 'original_page',
            'page_id': page_id,
            'group_id': None,
            'copy_post_id': pub.get('post_id'),
            'permalink': permalink,
            'insights_url': pub.get('insights_url'),
            'visibility': 'visible' if is_visible else 'unknown',
            'submitted_at': published_at,
            'visible_at': published_at,
            'first_seen_at': published_at,
            'timestamp_confidence': 'exact' if published_at else 'unknown',
            'checkpoints': {
                '24h': {
                    'due_at': due_24h,
                    'status': status_24h,
                    'attempts': attempts_24h,
                    'selected_observation_ref': selected_ref_24h,
                    'review_status': review_24h,
                },
                '7d': {
                    'due_at': due_7d,
                    'status': status_7d,
                    'attempts': attempts_7d,
                    'selected_observation_ref': selected_ref_7d,
                    'review_status': review_7d,
                },
            },
        })
        pub.setdefault('creative_version', None)

    new_state = {
        'schema_version': 2,
        'publications': publications,
        'placements': placements,
    }

    if dry_run:
        return {
            'dry_run': True,
            'backup_path': str(backup_path),
            'target_path': str(state_path),
            'publications_count': len(publications),
            'placements_count': len(placements),
        }

    if not backup_path.exists():
        backup_path.write_bytes(raw_bytes)
    save(state_path, new_state)

    return {
        'status': 'migrated',
        'schema_version': 2,
        'backup': str(backup_path),
        'publications': len(publications),
        'placements': len(placements),
    }


def glasser(*args):
    result = subprocess.run(['glasser', *args, '-j'], capture_output=True,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def register(state, post, url, published_at=None):
    url = url.rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('facebook.com', 'www.facebook.com'):
        raise ValueError('Use an HTTPS facebook.com permalink.')

    published = timestamp(published_at) if published_at is not None else None
    if published is not None and published > now():
        raise ValueError('A future timestamp is not a confirmed publication.')

    for entry in state.get('publications', []):
        if entry.get('url') and entry['url'].rstrip('/') == url:
            if entry['post'] != post:
                raise ValueError('Existing publication has different details; inspect registry first.')
            if entry.get('published_at') is None:
                if published is not None:
                    entry.update(published_at=published.isoformat(),
                                 due_at=(published + timedelta(hours=24)).isoformat(),
                                 metrics_status='pending', review_status='waiting_for_metrics')
            elif published is not None and timestamp(entry['published_at']) != published:
                raise ValueError('Existing publication has different details; inspect registry first.')
            return entry

    entry = {
        'id': uuid.uuid4().hex,
        'post': post,
        'url': url,
        'published_at': published.isoformat() if published else None,
        'due_at': (published + timedelta(hours=24)).isoformat() if published else None,
        'metrics_status': 'pending' if published else 'missing_publication_details',
        'review_status': 'waiting_for_metrics',
    }
    unresolved = next((item for item in state.get('publications', [])
                       if item['post'] == post
                       and item['metrics_status'] == 'missing_publication_details'), None)
    if unresolved is not None:
        entry['id'] = unresolved.get('id', entry['id'])
        unresolved.update(entry)
        unresolved.pop('note', None)
        return unresolved
    state.setdefault('publications', []).append(entry)
    return entry


def due(entry, at=None):
    at = at or now()
    return (entry.get('metrics_status') in ('pending', 'fetching')
            and entry.get('due_at') is not None
            and timestamp(entry['due_at']) is not None
            and timestamp(entry['due_at']) <= at)


def due_checkpoints(state, at=None):
    """Find all due checkpoints across placements and legacy publications.

    Prefer v2 checkpoints. Include legacy due work only for publications
    not represented by a placement. Deduplicate the same placement/checkpoint;
    freeze the resulting worklist.
    """
    at = at or now()
    due_items = []
    seen_placements = set()
    represented_pubs = set()

    # 1. Check v2 placements
    for pl in state.get('placements', []):
        represented_pubs.add(pl.get('publication_id'))
        for cp_name, cp in pl.get('checkpoints', {}).items():
            key = (pl['id'], cp_name)
            if key in seen_placements:
                continue
            if cp.get('status') in ('pending', 'fetching') and cp.get('due_at'):
                due_time = timestamp(cp['due_at'])
                if due_time and due_time <= at:
                    seen_placements.add(key)
                    due_items.append({
                        'kind': 'placement_checkpoint',
                        'placement_id': pl['id'],
                        'publication_id': pl.get('publication_id'),
                        'placement_kind': pl.get('kind', 'original_page'),
                        'checkpoint': cp_name,
                        'due_at': cp['due_at'],
                        'permalink': pl.get('permalink'),
                        'insights_url': pl.get('insights_url'),
                        'post_id': pl.get('copy_post_id'),
                    })

    # 2. Check legacy publications only if not already represented by a placement
    for pub in state.get('publications', []):
        if pub['id'] in represented_pubs:
            continue
        if due(pub, at):
            due_items.append({
                'kind': 'publication',
                'id': pub['id'],
                'publication_id': pub['id'],
                'placement_kind': 'original_page',
                'checkpoint': '24h',
                'due_at': pub.get('due_at'),
                'url': pub.get('url'),
                'permalink': pub.get('url'),
                'insights_url': pub.get('insights_url'),
                'post_id': pub.get('post_id'),
            })
    return due_items


def collect(state, state_path, budget, *, project_root, page_id, call=glasser, at=None):
    """One attempt per due publication; persist keys before any paid dispatch."""
    validate_page_id(page_id)
    at = at or now()
    remaining = Decimal(budget)
    if not remaining.is_finite() or remaining < 0:
        raise ValueError('Budget must be a finite nonnegative USD amount.')
    entries = [entry for entry in state['publications'] if due(entry, at)]
    if not entries:
        return []
    search_args = ['search', 'facebook post details', '--use-case',
                   f'Fetch 24-hour public metrics for registered Facebook Page {page_id} posts']
    existing_task = next((entry['task_id'] for entry in entries if entry.get('task_id')), None)
    if existing_task:
        search_args.extend(['--task', existing_task])
    search = call(*search_args)
    task = search['task_id']
    contract = call('inspect', '-p', 'scrapecreators', '-e', ENDPOINT,
                    '--endpoint-version', '2', '--task', task)
    rule = contract['price']['rule']
    if rule['type'] != 'flat':
        raise ValueError('Only a flat per-call contract is supported; review pricing.')
    prices = [Decimal(rule['amount_usd'])]
    prices.extend(Decimal(value) for value in contract['price']['charges'].values())
    if any(not value.is_finite() or value < 0 for value in prices):
        raise ValueError('Invalid price contract.')
    price = max(prices)
    results = []
    for entry in entries:
        if price > remaining:
            break
        remaining -= price
        entry.setdefault('idempotency_key', str(uuid.uuid4()))
        entry.setdefault('task_id', task)
        entry['metrics_status'] = 'fetching'
        save(state_path, state)
        receipt_path = project_root / 'sources/post-metrics' / (entry['id'] + '-24h.run.json')
        try:
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
            else:
                receipt = call('run', '-p', 'scrapecreators', '-e', ENDPOINT,
                               '--endpoint-version', '2', '--task', entry['task_id'],
                               '--idempotency-key', entry['idempotency_key'], '--wait',
                               '-i', json.dumps({'url': entry['url']}))
                save(receipt_path, receipt)
            if receipt['status'] in ('QUEUED', 'RUNNING'):
                receipt = call('runs', 'get', '-r', receipt['id'], '--wait')
                save(receipt_path, receipt)
            entry['receipt_file'] = str(receipt_path.relative_to(project_root))
            entry['run_url'] = receipt.get('run_url')
            entry['charge_usd'] = receipt.get('charge_usd')
            payload = receipt.get('output') or {}
            if (receipt['status'] != 'COMPLETED'
                    or receipt.get('provider_response', {}).get('http_status') != 200
                    or payload.get('success') is not True):
                entry['metrics_status'] = 'needs_attention'
                entry['error'] = 'Provider did not return usable metrics; inspect receipt, no automatic new paid attempt.'
            else:
                if (payload.get('url', '').rstrip('/') != entry['url'].rstrip('/')
                        or (payload.get('author') or {}).get('id') != page_id):
                    entry['metrics_status'] = 'needs_attention'
                    entry['error'] = 'Post URL or Page identity mismatch; inspect receipt.'
                    save(state_path, state)
                    results.append(entry)
                    continue
                fetched = timestamp(receipt['completed_at'])
                if fetched < timestamp(entry['due_at']):
                    raise ValueError('Receipt predates the 24-hour checkpoint.')
                entry['snapshot'] = {
                    'fetched_at': fetched.isoformat(),
                    'age_hours': round((fetched - timestamp(entry['published_at'])).total_seconds() / 3600, 2),
                    'views': payload.get('view_count'), 'likes': payload.get('like_count'),
                    'shares': payload.get('share_count'), 'comments': payload.get('comment_count'),
                    'duration_seconds': (payload.get('video') or {}).get('length_in_second'),
                    'qualified_inquiries': None,
                }
                entry['metrics_status'] = 'collected'
                entry['review_status'] = 'pending'
                entry.pop('error', None)
        except (RuntimeError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
            entry['error'] = str(exc)
            save(state_path, state)
            raise
        save(state_path, state)
        results.append(entry)
    return results


def review(entry, finding):
    """Legacy review function on a single publication entry."""
    if entry.get('metrics_status') != 'collected':
        raise ValueError('Collect the due snapshot before reviewing.')
    for key in ('observation', 'limitation', 'next_test'):
        if not isinstance(finding.get(key), str) or not finding[key].strip():
            raise ValueError(f'Review needs a nonempty {key}.')
    entry.setdefault('reviews', []).append({
        **finding, 'reviewed_at': now().isoformat(), 'run_url': entry.get('run_url'),
    })
    entry['review_status'] = 'reviewed'


def collect_insights(state, state_path, *, project_root, page_id, at=None):
    """Free dashboard collection via the repository's authenticated browser CLI."""
    validate_page_id(page_id)
    results = []
    for entry in state['publications']:
        if not due(entry, at or now()):
            continue
        if not entry.get('insights_url'):
            entry['error'] = 'Discover this post’s Insights URL in the Content Library first.'
            save(state_path, state)
            continue
        evidence = project_root / 'sources/post-metrics' / (entry['id'] + '-24h.insights.json')
        try:
            if not evidence.exists():
                subprocess.run([
                    sys.executable, '-m', 'tools.facebook_agent', 'insights',
                    '--page-id', page_id, '--url', entry['insights_url'],
                    '--output', str(evidence), '--scrolls', '2',
                ], cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=120)
            captured = json.loads(evidence.read_text())
            if not captured.get('capture_complete'):
                raise ValueError('Incomplete dashboard evidence; inspect before retrying.')
            from urllib.parse import parse_qs
            if parse_qs(urlparse(captured.get('profile', {}).get('url', '')).query).get('id') != [page_id]:
                raise ValueError('Dashboard evidence belongs to a different Page.')
            record = captured['records'][0]
            metrics = record.get('post_metrics')
            if not metrics or metrics.get('views') is None:
                raise ValueError('Expected labeled Post insights metrics were not available.')
            fetched = timestamp(record['observed_at'])
            if fetched < timestamp(entry['due_at']):
                raise ValueError('Dashboard evidence predates the 24-hour checkpoint.')
            entry['snapshot'] = {**metrics, 'fetched_at': fetched.isoformat(),
                                 'age_hours': round((fetched - timestamp(entry['published_at'])).total_seconds() / 3600, 2)}
            entry['receipt_file'] = str(evidence.relative_to(project_root))
            entry['run_url'] = record['url']
            entry['metrics_source'] = 'facebook_insights_dashboard'
            entry['charge_usd'] = '0.00'
            entry['metrics_status'] = 'collected'
            entry['review_status'] = 'pending'
            entry.pop('error', None)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
            entry['metrics_status'] = 'needs_attention'
            entry['error'] = str(exc)
        save(state_path, state)
        results.append(entry)
    return results


def record_action(root, event):
    """Validate and append a buyer action event to loop/actions.jsonl."""
    root = Path(root).resolve()
    for field in ('contact_key', 'intent', 'status'):
        if not event.get(field):
            raise ValueError(f"Action event must include nonempty '{field}'.")

    if event['status'] not in ('qualified', 'unqualified', 'lead', 'inquiry'):
        raise ValueError(f"Unsupported action status '{event['status']}'.")

    event_id = event.get('event_id') or uuid.uuid4().hex
    record = {
        'event_id': event_id,
        'event_at': event.get('event_at') or now().isoformat(),
        'contact_key': event['contact_key'],
        'intent': event['intent'],
        'status': event['status'],
        'agreed_next_step': event.get('agreed_next_step'),
        'order_outcome': event.get('order_outcome'),
        'attribution_certainty': event.get('attribution_certainty', 'uncertain'),
        'placement_id': event.get('placement_id'),
        'publication_id': event.get('publication_id'),
    }

    actions_path = root / 'loop/actions.jsonl'
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    with actions_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    return record


def _record_evidence_file(manifest, path_str, sha256_hash, ev_type, *, parent_path=None):
    for entry in manifest.setdefault('evidence_files', []):
        if entry.get('path') == path_str:
            if entry.get('sha256') != sha256_hash:
                _add_gap(manifest, {
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


def _validate_run_id(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r'[\w\-\.]+', run_id) or '..' in run_id:
        raise ValueError(f"Invalid run ID '{run_id}': path traversal or invalid characters.")
    return run_id


def load_run(root, run_id):
    root = Path(root).resolve()
    _validate_run_id(run_id)
    run_dir = root / 'loop/runs' / run_id
    manifest_path = run_dir / 'manifest.json'
    if not manifest_path.is_file():
        raise ValueError(f"Run '{run_id}' does not exist; cannot operate on it.")
    return run_dir, json.loads(manifest_path.read_text())


def _load_actions(root):
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


def _load_hypotheses(root, config):
    if not config.get('hypotheses_file'):
        return {}
    try:
        return json.loads(project_file(root, config['hypotheses_file']).read_text())
    except (OSError, ValueError):
        return {}


def _open_runs(root):
    """Describe runs that still need a decision, without changing them."""
    root = Path(root).resolve()
    result = []
    for run_dir in sorted((root / 'loop/runs').glob('*/')):
        manifest_path = run_dir / 'manifest.json'
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            continue
        status = manifest.get('status')
        review_path = run_dir / 'review.json'
        review_status = None
        if review_path.is_file():
            try:
                review_status = json.loads(review_path.read_text()).get('status')
            except (OSError, ValueError):
                review_status = 'unreadable'
        failed = [key for key, value in manifest.get('collector_status', {}).items() if value == 'failed']
        actionable = (
            status in ('in_progress', 'collection_incomplete', 'partial_collection_pending_review', 'pending_agent_review')
            or failed
            or review_status == 'proposed'
        )
        if actionable:
            result.append({
                'run_id': run_dir.name,
                'status': status,
                'review_status': review_status,
                'failed_collectors': failed,
                'gap_count': len(manifest.get('gaps', [])),
            })
    return result


def pending_work(root, state):
    """Surface reviews and failed runs even when no checkpoint is due."""
    root = Path(root).resolve()
    pending_reviews = []
    represented = {str(item.get('publication_id')) for item in state.get('placements', [])}
    for placement in state.get('placements', []):
        for name, checkpoint in placement.get('checkpoints', {}).items():
            if checkpoint.get('review_status') == 'pending':
                pending_reviews.append({
                    'kind': 'placement_checkpoint',
                    'placement_id': placement.get('id'),
                    'publication_id': placement.get('publication_id'),
                    'checkpoint': name,
                    'checkpoint_status': checkpoint.get('status'),
                    'observation_ref': checkpoint.get('selected_observation_ref'),
                })
    for publication in state.get('publications', []):
        if str(publication.get('id')) in represented:
            continue
        if publication.get('review_status') == 'pending':
            pending_reviews.append({
                'kind': 'publication',
                'publication_id': publication.get('id'),
                'checkpoint': '24h',
                'checkpoint_status': publication.get('metrics_status'),
                'observation_ref': publication.get('receipt_file'),
            })
    open_runs = _open_runs(root)
    return {
        'pending_reviews': pending_reviews,
        'open_runs': open_runs,
        'pending_review_count': len(pending_reviews),
        'open_run_count': len(open_runs),
    }


def compare_run(root, run_id):
    """Recompute deterministic comparisons for a run; never collects."""
    root = Path(root).resolve()
    run_dir, manifest = load_run(root, run_id)
    normalized_path = root / 'sources/post-metrics/normalized' / f"{run_id}.json"
    if not normalized_path.is_file():
        raise ValueError(f"Run '{run_id}' has no normalized observations; run cycle before compare.")
    normalized = json.loads(normalized_path.read_text())
    state = json.loads((root / 'loop/publications.json').read_text())
    actions = _load_actions(root)

    selected = comparison.select_comparable(normalized.get('observations', []), state.get('placements', []))
    content = comparison.compare_content(selected, actions=actions)
    groups = comparison.compare_groups(selected, actions=actions)
    gaps = comparison.dedupe_gaps(
        list(manifest.get('gaps', [])) + list(normalized.get('gaps', [])) + list(selected.get('gaps', []))
    )
    artifact = {
        'run_id': run_id,
        'content_comparison': content,
        'group_comparison': groups,
        'gaps': gaps,
    }
    save(run_dir / 'comparison.json', artifact)
    return {
        'run_id': run_id,
        'status': 'compared',
        'comparison_file': str((run_dir / 'comparison.json').relative_to(root)),
        'eligible_content_items': len(content.get('creative_matrix', [])),
        'eligible_group_items': len(groups.get('group_matrix', [])),
        'gap_count': len(gaps),
        'exit_code': 0,
    }


def prepare_review(root, run_id):
    """Rebuild the review bundle for a run from its comparison artifact."""
    root = Path(root).resolve()
    run_dir, manifest = load_run(root, run_id)
    comparison_path = run_dir / 'comparison.json'
    if not comparison_path.is_file():
        raise ValueError(f"Run '{run_id}' has no comparison; run compare first.")
    artifact = json.loads(comparison_path.read_text())
    config = load_project(root)
    bundle = comparison.build_review_bundle(artifact, hypotheses=_load_hypotheses(root, config))
    save(run_dir / 'review-bundle.json', bundle)
    manifest['review_bundle'] = str((run_dir / 'review-bundle.json').relative_to(root))
    save(run_dir / 'manifest.json', manifest)
    return {
        'run_id': run_id,
        'status': 'review_prepared',
        'review_bundle': str((run_dir / 'review-bundle.json').relative_to(root)),
        'summary': bundle.get('summary', {}),
        'exit_code': 0,
    }


def _validate_library(manifest, data, page_id):
    """Reject empty, mismatched or unidentified library captures as usable coverage."""
    captured_page = data.get('page_id')
    placements = data.get('placements')
    if captured_page is not None and str(captured_page) != str(page_id):
        manifest['collector_status']['content_library'] = 'failed'
        _add_gap(manifest, {
            'kind': 'content_library_page_mismatch',
            'detail': f"Content Library evidence belongs to Page {captured_page}, not {page_id}.",
        })
        return False
    if data.get('traversal_complete') is False:
        manifest['collector_status']['content_library'] = 'failed'
        _add_gap(manifest, {
            'kind': 'content_library_traversal_incomplete',
            'detail': 'Content Library reported incomplete scroll-container traversal; rows are not complete coverage.',
        })
        return False
    if captured_page is not None and not isinstance(placements, list):
        manifest['collector_status']['content_library'] = 'failed'
        _add_gap(manifest, {
            'kind': 'content_library_empty',
            'detail': 'Content Library evidence contains no placement rows.',
        })
        return False
    if captured_page is not None and isinstance(placements, list):
        usable = any(
            str(row.get('post_id') or '').isdigit() or row.get('group_id')
            for row in placements
        )
        if not usable:
            manifest['collector_status']['content_library'] = 'failed'
            _add_gap(manifest, {
                'kind': 'content_library_unidentified',
                'detail': 'No Content Library row has a verified post or group identity; coverage is not usable.',
            })
            return False
    if captured_page is None:
        _add_gap(manifest, {
            'kind': 'content_library_unverified',
            'detail': 'Content Library evidence has no Page identity; completeness cannot be verified.',
        })
    return True


def cycle(root, *, dry_run=False, resume=None, runner=None):
    """Execute end-to-end collection, normalization, comparison and review bundle."""
    root = Path(root).resolve()
    config = load_project(root)
    page_id = config['page_id']
    state_path = root / 'loop/publications.json'
    state = json.loads(state_path.read_text())

    at = now()
    runner = runner or subprocess.run

    # 1. Resume validation or new run ID
    if resume:
        run_id = _validate_run_id(resume)
        run_dir = root / 'loop/runs' / run_id
        manifest_path = run_dir / 'manifest.json'
        if not manifest_path.exists():
            raise ValueError(f"Run '{resume}' does not exist; cannot resume.")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('page_id') != page_id:
            raise ValueError(f"Run '{resume}' was recorded for Page {manifest.get('page_id')}, not {page_id}.")
        due_work = manifest.get('due_work', [])
        manifest['status'] = 'in_progress'
        manifest.setdefault('collector_status', {})
        manifest.setdefault('evidence_files', [])
        manifest.setdefault('gaps', [])
        manifest.setdefault('warnings', [])
    else:
        run_id = at.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        run_dir = root / 'loop/runs' / run_id
        manifest_path = run_dir / 'manifest.json'
        due_work = due_checkpoints(state, at)
        manifest = {
            'run_id': run_id,
            'started_at': at.isoformat(),
            'status': 'in_progress',
            'page_id': page_id,
            'due_work': due_work,
            'evidence_files': [],
            'collector_status': {},
            'warnings': [],
            'gaps': [],
        }

    # 2. Check for legitimately empty worklist
    if not due_work:
        pending = pending_work(root, state)
        if dry_run:
            return {
                'status': 'no_work',
                'dry_run': True,
                'page_id': page_id,
                'due_work_count': 0,
                'due_work': [],
                **pending,
                'exit_code': 0,
            }
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest['status'] = 'no_work'
        manifest['completed_at'] = now().isoformat()
        manifest['pending_work'] = pending
        manifest['warnings'].append(
            'No placement checkpoints or publications are currently due. '
            f"Pending reviews: {pending['pending_review_count']}; open runs: {pending['open_run_count']}."
        )
        save(manifest_path, manifest)
        return {
            'status': 'no_work',
            'run_id': run_id,
            'due_work_count': 0,
            'message': 'No due checkpoints.',
            **pending,
            'exit_code': 0,
        }

    # 3. Dry-run preview
    if dry_run:
        return {
            'status': 'planned',
            'dry_run': True,
            'page_id': page_id,
            'due_work_count': len(due_work),
            'due_work': due_work,
            'planned_steps': [
                'discover_content_library',
                'export_summary_csv',
                'capture_insights',
                'normalize',
                'compare',
                'prepare_review',
            ],
            'exit_code': 0,
        }

    run_dir.mkdir(parents=True, exist_ok=True)
    save(manifest_path, manifest)

    captures_dir = root / 'sources/post-metrics/captures' / run_id
    captures_dir.mkdir(parents=True, exist_ok=True)
    exports_dir = root / 'sources/post-metrics/exports'
    exports_dir.mkdir(parents=True, exist_ok=True)

    raw_inputs = {
        'insights_captures': [],
        'content_library_rows': [],
        'csv_posts': [],
        'csv_evidence_hash': None,
        'csv_source_file': None,
    }
    collection_changed = False

    # 4. Sequential Collector Execution
    # Collector 1: Content Library
    lib_relative = f"sources/post-metrics/captures/{run_id}/content-library.json"
    lib_output = root / lib_relative
    lib_data = None
    lib_hash = None
    lib_relative_used = lib_relative
    lib_completed = manifest.get('collector_status', {}).get('content_library') == 'completed'
    _note_hash_conflicts(manifest, lib_relative)
    # Verified evidence beats a later failed collector run: reuse it and do not re-collect.
    reusable, reuse_reason = _check_reusable_evidence(root, manifest, lib_relative, 'content_library')
    if reusable:
        lib_data = json.loads(lib_output.read_text())
        lib_hash = _sha256(lib_output)
        if _validate_library(manifest, lib_data, page_id):
            manifest['collector_status']['content_library'] = 'completed'
            # The selected evidence is usable; drop coverage gaps that described a discarded repair.
            manifest['gaps'] = [g for g in manifest.get('gaps', [])
                                if g.get('kind') not in ('content_library_empty',
                                                         'content_library_unidentified',
                                                         'content_library_traversal_incomplete',
                                                         'content_library_unverified')]
        save(manifest_path, manifest)
    else:
        # Missing or changed completed evidence is repaired at a new path.
        lib_recorded = _evidence_entry(manifest, lib_relative) is not None
        has_history = lib_completed or lib_recorded or lib_output.exists()
        lib_target = (_repair_path(captures_dir, lib_relative, manifest)
                      if has_history else lib_output)
        if lib_target != lib_output:
            _record_repair(manifest, lib_relative, str(lib_target.relative_to(root)),
                           reuse_reason if (lib_completed or lib_recorded) else 'unrecorded')
        collection_changed = True
        manifest.setdefault('collector_status', {})['content_library'] = 'in_progress'
        save(manifest_path, manifest)
        lib_target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, '-m', 'tools.facebook_agent', 'content-library',
            '--page-id', page_id, '--output', str(lib_target), '--scrolls', '3'
        ]
        try:
            res = runner(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
            if lib_target.exists():
                lib_data = json.loads(lib_target.read_text())
                lib_hash = _sha256(lib_target)
                lib_relative_used = str(lib_target.relative_to(root))
                parent = lib_relative if lib_target != lib_output else None
                _record_evidence_file(manifest, lib_relative_used, lib_hash, 'content_library',
                                      parent_path=parent)
                manifest['collector_status']['content_library'] = 'completed'
                manifest['gaps'] = [g for g in manifest.get('gaps', [])
                                    if g.get('kind') not in ('content_library_failed', 'content_library_error')]
                _validate_library(manifest, lib_data, page_id)
            else:
                lib_data = None
                manifest['collector_status']['content_library'] = 'failed'
                _add_gap(manifest, {
                    'kind': 'content_library_failed',
                    'detail': res.stderr or res.stdout or 'content-library did not create output file'
                })
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            lib_data = None
            manifest['collector_status']['content_library'] = 'failed'
            _add_gap(manifest, {'kind': 'content_library_error', 'detail': str(exc)})
        save(manifest_path, manifest)

    if lib_data and isinstance(lib_data.get('placements'), list):
        for row in lib_data['placements']:
            raw_inputs['content_library_rows'].append({
                **row,
                'evidence_file': lib_relative_used,
                'evidence_hash': lib_hash,
            })

    # Collector 2: Summary CSV Export & Import (if original Page due)
    needs_csv = any(item.get('placement_kind') == 'original_page' or item.get('kind') == 'publication' for item in due_work)
    imported_data = None
    csv_hash = None
    actual_csv = None
    if needs_csv:
        csv_output = exports_dir / f"content-summary-{page_id}-{run_id}.csv"
        joined_output = exports_dir / f"content-summary-{page_id}-{run_id}.imported.json"
        csv_relative = str(csv_output.relative_to(root))
        joined_relative = str(joined_output.relative_to(root))
        actual_csv = csv_output

        csv_completed = manifest.get('collector_status', {}).get('csv_export') == 'completed'
        evidence_files = manifest.get('evidence_files', [])
        csv_ev = next((e for e in reversed(evidence_files) if e.get('type') == 'summary_csv'), None)
        joined_ev = next((e for e in reversed(evidence_files)
                          if e.get('type') == 'imported_csv_summary'), None)
        csv_ok = False
        joined_ok = False
        joined_used = joined_output
        if csv_ev:
            csv_ok, _ = _check_reusable_evidence(root, manifest, csv_ev['path'], 'summary_csv')
            if csv_ok:
                actual_csv = root / csv_ev['path']
        if joined_ev:
            joined_ok, _ = _check_reusable_evidence(root, manifest, joined_ev['path'],
                                                    'imported_csv_summary')
            if joined_ok:
                joined_used = root / joined_ev['path']

        def clear_csv_gaps(include_import=True):
            blocked = {'csv_export_failed', 'csv_export_error', 'csv_evidence_unusable'}
            if include_import:
                blocked.add('csv_import_failed')
            manifest['gaps'] = [g for g in manifest.get('gaps', [])
                                if g.get('kind') not in blocked]

        if csv_ok and joined_ok:
            imported_data = json.loads(joined_used.read_text())
            csv_hash = _sha256(actual_csv)
        elif csv_ok:
            # A verified CSV is never re-exported; only its joined import is rebuilt.
            collection_changed = True
            csv_hash = _sha256(actual_csv)
            if joined_ev or joined_output.exists():
                joined_target = _repair_path(exports_dir, joined_relative, manifest)
                _record_repair(manifest, joined_relative, str(joined_target.relative_to(root)),
                               'missing or changed')
            else:
                joined_target = joined_output
            clear_csv_gaps(include_import=False)
            manifest['collector_status']['csv_export'] = 'in_progress'
            save(manifest_path, manifest)
            joined_target.parent.mkdir(parents=True, exist_ok=True)
            try:
                res_imp = runner([
                    sys.executable, '-m', 'tools.facebook_agent', 'insights-import',
                    '--page-id', page_id, '--csv', str(actual_csv),
                    '--output', str(joined_target), '--breakdown', 'summary'
                ], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                if joined_target.exists():
                    imported_data = json.loads(joined_target.read_text())
                    j_hash = _sha256(joined_target)
                    _record_evidence_file(manifest, str(joined_target.resolve().relative_to(root)),
                                          j_hash, 'imported_csv_summary',
                                          parent_path=joined_relative if joined_target != joined_output else None)
                    manifest['collector_status']['csv_export'] = 'completed'
                    clear_csv_gaps()
                else:
                    imported_data = None
                    manifest['collector_status']['csv_export'] = 'failed'
                    _add_gap(manifest, {
                        'kind': 'csv_import_failed',
                        'detail': res_imp.stderr or res_imp.stdout or 'insights-import failed'
                    })
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                imported_data = None
                manifest['collector_status']['csv_export'] = 'failed'
                _add_gap(manifest, {'kind': 'csv_import_failed', 'detail': str(exc)})
            save(manifest_path, manifest)
        else:
            if csv_completed or csv_ev:
                _add_gap(manifest, {
                    'kind': 'csv_evidence_unusable',
                    'detail': 'Recorded CSV evidence is missing or its hash changed; export will be re-attempted through reconciliation.',
                })
            collection_changed = True
            csv_recorded = csv_ev is not None
            csv_audit = csv_output.with_suffix('.export.json')
            has_history = (csv_completed or csv_recorded or csv_output.exists()
                           or joined_output.exists() or csv_audit.exists())
            if has_history:
                csv_target = _repair_path(exports_dir, csv_relative, manifest)
                joined_target = _repair_path(exports_dir, joined_relative, manifest)
                _record_repair(manifest, csv_relative, str(csv_target.relative_to(root)),
                               'missing or changed')
            else:
                csv_target, joined_target = csv_output, joined_output
            actual_csv = csv_target
            manifest['collector_status']['csv_export'] = 'in_progress'
            save(manifest_path, manifest)
            csv_target.parent.mkdir(parents=True, exist_ok=True)
            # A known report ID turns a retry into a download, never a second report.
            prior_report_id = None
            prior_csv_audit = csv_output.with_suffix('.export.json')
            if prior_csv_audit.is_file():
                try:
                    prior_report_id = json.loads(prior_csv_audit.read_text()).get('report_id')
                except (OSError, ValueError):
                    prior_report_id = None
            export_cmd = [
                sys.executable, '-m', 'tools.facebook_agent', 'insights-export',
                '--page-id', page_id, '--output', str(csv_target), '--breakdown', 'summary'
            ]
            if prior_report_id:
                export_cmd += ['--report-id', str(prior_report_id)]
            try:
                res = runner(export_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                # Parse stdout envelope: {"ok": true, "data": {"output": "..."}} or top-level output
                if res.stdout:
                    try:
                        exp_json = json.loads(res.stdout)
                        if isinstance(exp_json, dict):
                            out_val = ((exp_json.get('data') or {}).get('output')
                                       if isinstance(exp_json.get('data'), dict) else None)
                            out_val = out_val or exp_json.get('output')
                            if isinstance(out_val, str) and Path(out_val).exists():
                                actual_csv = Path(out_val).resolve()
                    except (ValueError, OSError):
                        pass

                if actual_csv.exists():
                    csv_hash = _sha256(actual_csv)
                    _record_evidence_file(manifest, str(actual_csv.resolve().relative_to(root)),
                                          csv_hash, 'summary_csv')
                    clear_csv_gaps(include_import=False)
                    import_cmd = [
                        sys.executable, '-m', 'tools.facebook_agent', 'insights-import',
                        '--page-id', page_id, '--csv', str(actual_csv),
                        '--output', str(joined_target), '--breakdown', 'summary'
                    ]
                    res_imp = runner(import_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                    if joined_target.exists():
                        imported_data = json.loads(joined_target.read_text())
                        j_hash = _sha256(joined_target)
                        _record_evidence_file(manifest, str(joined_target.resolve().relative_to(root)),
                                              j_hash, 'imported_csv_summary',
                                              parent_path=joined_relative if joined_target != joined_output else None)
                        manifest['collector_status']['csv_export'] = 'completed'
                        clear_csv_gaps()
                    else:
                        imported_data = None
                        manifest['collector_status']['csv_export'] = 'failed'
                        _add_gap(manifest, {
                            'kind': 'csv_import_failed',
                            'detail': res_imp.stderr or res_imp.stdout or 'insights-import failed'
                        })
                else:
                    imported_data = None
                    manifest['collector_status']['csv_export'] = 'failed'
                    _add_gap(manifest, {
                        'kind': 'csv_export_failed',
                        'detail': res.stderr or res.stdout or 'insights-export did not create CSV'
                    })
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                imported_data = None
                manifest['collector_status']['csv_export'] = 'failed'
                _add_gap(manifest, {'kind': 'csv_export_error', 'detail': str(exc)})
            save(manifest_path, manifest)

        if imported_data and isinstance(imported_data.get('posts'), list):
            raw_inputs['csv_evidence_hash'] = csv_hash
            raw_inputs['csv_source_file'] = str(actual_csv.resolve().relative_to(root)) if actual_csv and actual_csv.exists() else None
            raw_inputs['csv_posts'] = imported_data['posts']

    # Collector 3: Post Dashboard Insights
    for item in due_work:
        insights_url = item.get('insights_url')
        if not insights_url:
            manifest['gaps'].append({
                'kind': 'missing_insights_url',
                'placement_id': item.get('placement_id') or item.get('id'),
                'detail': 'No Insights URL found for due placement/publication.'
            })
            continue

        target_id = item.get('placement_id') or item.get('id')
        cp_name = item.get('checkpoint', '24h')
        cap_relative = f"sources/post-metrics/captures/{run_id}/{target_id}-{cp_name}.insights.json"
        cap_output = root / cap_relative
        cap_data = None
        cap_hash = None
        cap_relative_used = cap_relative
        reused = False

        _note_hash_conflicts(manifest, cap_relative)
        cap_ev = _evidence_entry(manifest, cap_relative)
        if cap_ev and cap_output.exists():
            cap_ok, cap_reason = _check_reusable_evidence(root, manifest, cap_relative, 'post_insights')
            if cap_ok:
                cap_data = json.loads(cap_output.read_text())
                cap_hash = _sha256(cap_output)
                reused = True
            else:
                cap_target = _repair_path(captures_dir, cap_relative, manifest)
                _record_repair(manifest, cap_relative, str(cap_target.relative_to(root)), cap_reason)
        elif cap_ev or cap_output.exists():
            cap_target = _repair_path(captures_dir, cap_relative, manifest)
            _record_repair(manifest, cap_relative, str(cap_target.relative_to(root)),
                           'missing' if cap_ev else 'unrecorded')
        else:
            cap_target = cap_output

        if not reused:
            collection_changed = True
            cap_target.parent.mkdir(parents=True, exist_ok=True)
            cap_cmd = [
                sys.executable, '-m', 'tools.facebook_agent', 'insights',
                '--page-id', page_id, '--url', insights_url, '--open', 'Source',
                '--output', str(cap_target), '--scrolls', '2'
            ]
            try:
                res = runner(cap_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                if cap_target.exists():
                    cap_data = json.loads(cap_target.read_text())
                    cap_hash = _sha256(cap_target)
                    cap_relative_used = str(cap_target.relative_to(root))
                    _record_evidence_file(manifest, cap_relative_used, cap_hash, 'post_insights',
                                          parent_path=cap_relative if cap_target != cap_output else None)
                    manifest['gaps'] = [g for g in manifest.get('gaps', [])
                                        if not (g.get('kind') in ('post_insights_failed', 'post_insights_error')
                                                and g.get('placement_id') == target_id)]
                else:
                    cap_data = None
                    _add_gap(manifest, {
                        'kind': 'post_insights_failed',
                        'placement_id': target_id,
                        'detail': res.stderr or res.stdout or f"insights capture failed for {insights_url}"
                    })
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                cap_data = None
                _add_gap(manifest, {
                    'kind': 'post_insights_error',
                    'placement_id': target_id,
                    'detail': str(exc)
                })
            save(manifest_path, manifest)

        if cap_data and cap_data.get('capture_complete'):
            records = cap_data.get('records') or []
            record = records[0] if records else {}
            metrics = record.get('post_metrics') or {}
            observed_raw = record.get('observed_at')
            usable_metrics = [value for value in metrics.values() if value is not None]
            profile_url = (cap_data.get('profile') or {}).get('url', '')
            profile_id = parse_qs(urlparse(profile_url).query).get('id', [None])[0]
            if (not records or not observed_raw or not usable_metrics
                    or (profile_id is not None and profile_id != page_id)):
                _add_gap(manifest, {
                    'kind': 'post_insights_unusable',
                    'placement_id': target_id,
                    'detail': 'Insights capture lacks Page identity, an observation time, records or any non-null metric; not accepted as required collection.'
                })
            else:
                # Only a verified visible time may define age. Unknown approval time stays unknown.
                pub_dt = None
                placement = next((pl for pl in state.get('placements', [])
                                  if pl.get('id') == target_id), None)
                if placement is not None:
                    if placement.get('kind', 'original_page') == 'original_page':
                        time_str = placement.get('visible_at') or placement.get('submitted_at')
                    else:
                        time_str = placement.get('visible_at')
                    if time_str:
                        pub_dt = timestamp(time_str)
                if pub_dt is None and (placement is None
                                       or placement.get('kind', 'original_page') == 'original_page'):
                    for pub in state.get('publications', []):
                        if pub.get('id') == (item.get('publication_id') or item.get('id')):
                            if pub.get('published_at'):
                                pub_dt = timestamp(pub['published_at'])
                            break

                obs_dt = timestamp(observed_raw)
                if pub_dt:
                    actual_age = round((obs_dt - pub_dt).total_seconds() / 3600, 2)
                else:
                    actual_age = None
                    _add_gap(manifest, {
                        'kind': 'unknown_visible_at',
                        'placement_id': target_id,
                        'detail': 'Placement has no verified approval/visible time; snapshot stays descriptive with unknown age.'
                    })

                raw_inputs['insights_captures'].append({
                    'placement_id': target_id,
                    'publication_id': item.get('publication_id') or item.get('id'),
                    'checkpoint': cp_name,
                    'actual_age_hours': actual_age,
                    'evidence_file': cap_relative_used,
                    'evidence_hash': cap_hash,
                    'reused': reused,
                    **cap_data,
                })

    # 5. Check for Collection Incomplete
    manifest['gaps'] = comparison.dedupe_gaps(manifest.get('gaps', []))
    total_observations = (
        len(raw_inputs['insights_captures']) +
        len(raw_inputs['content_library_rows']) +
        len(raw_inputs['csv_posts'])
    )
    if total_observations == 0:
        manifest['status'] = 'collection_incomplete'
        manifest['completed_at'] = now().isoformat()
        manifest['warnings'].append('Due work existed but no usable evidence files could be collected or parsed.')
        save(manifest_path, manifest)
        return {
            'status': 'collection_incomplete',
            'run_id': run_id,
            'due_work_count': len(due_work),
            'evidence_files_count': len(manifest.get('evidence_files', [])),
            'gaps': manifest.get('gaps', []),
            'exit_code': 1,
        }

    # 6. Normalize observations
    normalized = comparison.normalize_observations(manifest, raw_inputs, state.get('placements', []))
    norm_path = root / 'sources/post-metrics/normalized' / f"{run_id}.json"
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    save(norm_path, normalized)

    # 7. Select comparable & run comparisons
    selected = comparison.select_comparable(normalized['observations'], state.get('placements', []))

    actions = _load_actions(root)
    content_comp = comparison.compare_content(selected, actions=actions)
    group_comp = comparison.compare_groups(selected, actions=actions)

    all_gaps = comparison.dedupe_gaps(
        list(manifest.get('gaps', [])) + list(normalized.get('gaps', [])) + list(selected.get('gaps', []))
    )
    comp_artifact = {
        'run_id': run_id,
        'content_comparison': content_comp,
        'group_comparison': group_comp,
        'gaps': all_gaps,
    }
    save(run_dir / 'comparison.json', comp_artifact)

    # 8. Checkpoint commit in publications.json; reuse never increments attempts.
    for cap in raw_inputs['insights_captures']:
        p_id = cap.get('placement_id')
        cp_name = cap.get('checkpoint', '24h')
        for pl in state.get('placements', []):
            if pl['id'] == p_id and cp_name in pl.get('checkpoints', {}):
                cp = pl['checkpoints'][cp_name]
                cp['status'] = 'collected'
                if not cap.get('reused'):
                    cp['attempts'] = cp.get('attempts', 0) + 1
                cp['selected_observation_ref'] = cap.get('evidence_file')
                if not cap.get('reused') or not cp.get('review_status'):
                    cp['review_status'] = 'pending'
        for pub in state.get('publications', []):
            if pub['id'] == cap.get('publication_id'):
                pub['metrics_status'] = 'collected'
                if not cap.get('reused') or not pub.get('review_status'):
                    pub['review_status'] = 'pending'
                pub['receipt_file'] = cap.get('evidence_file')
    save(state_path, state)

    # 9. Build review bundle
    hypotheses = _load_hypotheses(root, config)
    bundle = comparison.build_review_bundle(comp_artifact, hypotheses=hypotheses)
    save(run_dir / 'review-bundle.json', bundle)

    failed_collectors = [k for k, v in manifest.get('collector_status', {}).items() if v == 'failed']
    any_insights_failed = any(g.get('kind') in ('post_insights_failed', 'post_insights_error',
                                                'post_insights_unusable')
                              for g in manifest.get('gaps', []))
    is_partial = bool(failed_collectors or any_insights_failed)

    if is_partial:
        status_str = 'partial_collection_pending_review'
        exit_code = 1
        manifest['warnings'].append(f"Incomplete collection: collectors {failed_collectors or 'post_insights'} encountered errors; partial review available.")
    elif manifest.get('review_status') in ('proposed', 'approved') and not collection_changed:
        # Re-staging identical evidence must not silently invalidate a recorded review.
        status_str = f"review_{manifest['review_status']}"
        exit_code = 0
    else:
        status_str = 'pending_agent_review'
        exit_code = 0

    manifest['status'] = status_str
    manifest['completed_at'] = now().isoformat()
    manifest['gaps'] = all_gaps
    save(manifest_path, manifest)

    return {
        'run_id': run_id,
        'status': status_str,
        'run_directory': str(run_dir.relative_to(root)),
        'comparison': comp_artifact,
        'review_bundle': str((run_dir / 'review-bundle.json').relative_to(root)),
        'exit_code': exit_code,
    }


def _mark_reviewed(root, review_data):
    """Link a recorded review back to the placement/publication it cites."""
    state_path = Path(root) / 'loop/publications.json'
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text())
    ids = set()
    for key in ('publication_id', 'placement_id'):
        if review_data.get(key):
            ids.add(str(review_data[key]))
    for value in review_data.get('evidence_ids', []) or []:
        ids.add(str(value))
    for value in review_data.get('evidence', []) or []:
        if isinstance(value, str):
            ids.add(value)
    changed = False
    for placement in state.get('placements', []):
        if str(placement.get('id')) in ids or str(placement.get('publication_id')) in ids:
            for checkpoint in placement.get('checkpoints', {}).values():
                if checkpoint.get('status') == 'collected':
                    checkpoint['review_status'] = 'reviewed'
                    changed = True
    for publication in state.get('publications', []):
        if str(publication.get('id')) in ids or str(publication.get('post_id')) in ids:
            publication['review_status'] = 'reviewed'
            changed = True
    if changed:
        save(state_path, state)


def record_run_review(root, run_id, review_data):
    """Save structured proposals and human-readable review table for a run."""
    root = Path(root).resolve()
    run_dir, manifest = load_run(root, run_id)

    for field in ('observation', 'limitation'):
        if not review_data.get(field):
            raise ValueError(f"Review requires nonempty '{field}'.")

    review_path = run_dir / 'review.json'
    review_record = {
        'run_id': run_id,
        'reviewed_at': now().isoformat(),
        'status': 'proposed',
        **review_data,
    }
    save(review_path, review_record)

    # A recorded review changes run state but never implies approval or repairs collection.
    manifest['status'] = 'review_proposed'
    manifest['review_status'] = 'proposed'
    manifest['review_file'] = str(review_path.relative_to(root))
    manifest['reviewed_at'] = review_record['reviewed_at']
    save(run_dir / 'manifest.json', manifest)

    _mark_reviewed(root, review_data)

    # Human-readable markdown
    md_lines = [
        f"# Review for Run `{run_id}`\n\n",
        f"| Field | Value |\n| --- | --- |\n",
        f"| Observation | {review_data.get('observation')} |\n",
        f"| Limitation | {review_data.get('limitation')} |\n",
        f"| Status | Proposed |\n\n",
        "## Suggestions\n\n",
        "| ID | Target | Change | Expected Outcome | Controls |\n| --- | --- | --- | --- | --- |\n",
    ]
    for s in review_data.get('suggestions', []):
        md_lines.append(f"| {s.get('id', '-')} | {s.get('target', '-')} | {s.get('change', '-')} | {s.get('expected_outcome', '-')} | {s.get('controls', '-')} |\n")

    (run_dir / 'review.md').write_text(''.join(md_lines))
    return review_record


def approve_run_review(root, run_id, proposal_ids=None):
    """Record explicit human approval for selected proposals in a run."""
    root = Path(root).resolve()
    run_dir, manifest = load_run(root, run_id)
    review_path = run_dir / 'review.json'
    if not review_path.exists():
        raise ValueError(f"No review found for run {run_id}.")

    review_data = json.loads(review_path.read_text())
    review_data['status'] = 'approved'
    review_data['approved_at'] = now().isoformat()
    review_data['approved_proposals'] = proposal_ids or [s.get('id') for s in review_data.get('suggestions', [])]
    save(review_path, review_data)

    manifest['status'] = 'review_approved'
    manifest['review_status'] = 'approved'
    manifest['approved_at'] = review_data['approved_at']
    save(run_dir / 'manifest.json', manifest)

    return review_data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='Project root containing its own loop/config.json and registry')
    commands = parser.add_subparsers(dest='command', required=True)

    init = commands.add_parser('init', help='Initialize project-owned configuration/state without overwriting existing files')
    init.add_argument('--page-id', required=True)
    init.add_argument('--hypotheses-file', help='Optional project-relative JSON with a hypotheses array')
    init.add_argument('--dry-run', action='store_true', help='Validate inputs without writing to disk')

    mig = commands.add_parser('migrate', help='Migrate publications.json to Schema v2 with byte backup')
    mig.add_argument('--dry-run', action='store_true', help='Preview migration without writing to disk')

    cyc = commands.add_parser('cycle', help='Run end-to-end collection, comparison and review bundle generation')
    cyc.add_argument('--dry-run', action='store_true', help='Preview due checkpoints and planned collectors without network calls')
    cyc.add_argument('--resume', help='Resume an unfinished run ID')

    cmp_cmd = commands.add_parser('compare', help='Recompute deterministic comparisons for a run')
    cmp_cmd.add_argument('--run', required=True, dest='run_id')

    prep = commands.add_parser('prepare-review', help='Prepare review bundle for a run')
    prep.add_argument('--run', required=True, dest='run_id')

    act = commands.add_parser('record-action', help='Append manual qualified inquiry or buyer action event')
    act.add_argument('--file', type=Path, required=True)

    apprv = commands.add_parser('approve-review', help='Record human approval for review proposals')
    apprv.add_argument('--run', required=True, dest='run_id')
    apprv.add_argument('--proposals', help='Comma-separated proposal IDs to approve')

    commands.add_parser('status')
    commands.add_parser('due')
    commands.add_parser('collect-insights', help='Read due post dashboards; no Glasser charges')

    add = commands.add_parser('register')
    add.add_argument('--post', type=int, required=True)
    add.add_argument('--url', required=True)
    add.add_argument('--published-at', default=None)

    fetch = commands.add_parser('collect')
    fetch.add_argument('--max-cost-usd', required=True,
                       help='Explicit total spend ceiling for this invocation, not a recurring approval.')

    learn = commands.add_parser('review')
    learn.add_argument('--id', help='Legacy publication ID')
    learn.add_argument('--run', dest='run_id', help='Run ID to attach review to')
    learn.add_argument('--file', type=Path, required=True)

    args = parser.parse_args(argv)
    root = args.project.expanduser().resolve()
    if args.command != 'init' and not (root / 'loop/config.json').is_file():
        parser.error('Project is not initialized; run --project PATH init --page-id ID first.')

    if args.command == 'init' and getattr(args, 'dry_run', False):
        print(json.dumps(initialize(root, args.page_id, args.hypotheses_file, dry_run=True), indent=2))
        return

    (root / 'loop').mkdir(parents=True, exist_ok=True)
    state_path = root / 'loop/publications.json'

    with (root / 'loop/.engine.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'init':
            print(json.dumps(initialize(root, args.page_id, args.hypotheses_file, dry_run=args.dry_run), indent=2))
            return
        elif args.command == 'migrate':
            print(json.dumps(migrate(root, dry_run=args.dry_run), indent=2))
            return
        elif args.command == 'cycle':
            result = cycle(root, dry_run=args.dry_run, resume=args.resume)
            print(json.dumps(result, indent=2))
            if result.get('exit_code', 0) != 0 or result.get('status') == 'collection_incomplete':
                sys.exit(1)
            return
        elif args.command == 'compare':
            print(json.dumps(compare_run(root, args.run_id), indent=2))
            return
        elif args.command == 'prepare-review':
            print(json.dumps(prepare_review(root, args.run_id), indent=2))
            return
        elif args.command == 'record-action':
            event_data = json.loads(args.file.read_text())
            print(json.dumps(record_action(root, event_data), indent=2))
            return
        elif args.command == 'approve-review':
            proposals = [p.strip() for p in args.proposals.split(',')] if args.proposals else None
            print(json.dumps(approve_run_review(root, args.run_id, proposals), indent=2))
            return

        config = load_project(root)
        state = json.loads(state_path.read_text())

        if args.command == 'register':
            if config.get('hypotheses_file'):
                valid = {item['post'] for item in json.loads(project_file(root, config['hypotheses_file']).read_text())['hypotheses']}
                if args.post not in valid:
                    parser.error('Unknown hypothesis post number.')
            result = register(state, args.post, args.url, args.published_at)
            save(state_path, state)
        elif args.command == 'collect':
            result = collect(state, state_path, args.max_cost_usd, project_root=root, page_id=config['page_id'])
        elif args.command == 'collect-insights':
            result = collect_insights(state, state_path, project_root=root, page_id=config['page_id'])
        elif args.command == 'review':
            review_payload = json.loads(args.file.read_text())
            if args.run_id:
                result = record_run_review(root, args.run_id, review_payload)
            elif args.id:
                entry = next(item for item in state['publications'] if item['id'] == args.id)
                review(entry, review_payload)
                save(state_path, state)
                result = entry
            else:
                parser.error('Provide either --run or --id for review.')
        elif args.command == 'due':
            result = due_checkpoints(state, now())
        elif args.command == 'status':
            result = {**state, 'pending_work': pending_work(root, state)}
        else:
            parser.error(f"Unsupported command '{args.command}'.")

        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
