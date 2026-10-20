"""Persistent publication → 24h metrics → agent review queue (stdlib only)."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
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


def _record_evidence_file(manifest, path_str, sha256_hash, ev_type):
    for entry in manifest.setdefault('evidence_files', []):
        if entry.get('path') == path_str:
            entry['sha256'] = sha256_hash
            entry['type'] = ev_type
            return
    manifest['evidence_files'].append({
        'path': path_str,
        'sha256': sha256_hash,
        'type': ev_type,
    })


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
        import re
        if not re.fullmatch(r'[\w\-\.]+', resume) or '..' in resume:
            raise ValueError(f"Invalid resume run ID '{resume}': path traversal or invalid characters.")
        run_id = resume
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
        if dry_run:
            return {
                'status': 'no_work',
                'dry_run': True,
                'page_id': page_id,
                'due_work_count': 0,
                'due_work': [],
                'exit_code': 0,
            }
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest['status'] = 'no_work'
        manifest['completed_at'] = now().isoformat()
        manifest['warnings'].append('No placement checkpoints or publications are currently due.')
        save(manifest_path, manifest)
        return {
            'status': 'no_work',
            'run_id': run_id,
            'due_work_count': 0,
            'message': 'No due checkpoints.',
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

    # 4. Sequential Collector Execution
    # Collector 1: Content Library
    lib_output = captures_dir / 'content-library.json'
    if manifest.get('collector_status', {}).get('content_library') == 'completed' and lib_output.exists():
        lib_data = json.loads(lib_output.read_text())
        lib_hash = hashlib.sha256(lib_output.read_bytes()).hexdigest()
    else:
        manifest.setdefault('collector_status', {})['content_library'] = 'in_progress'
        save(manifest_path, manifest)
        cmd = [
            sys.executable, '-m', 'tools.facebook_agent', 'content-library',
            '--page-id', page_id, '--output', str(lib_output), '--scrolls', '3'
        ]
        try:
            res = runner(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
            if lib_output.exists():
                lib_data = json.loads(lib_output.read_text())
                lib_hash = hashlib.sha256(lib_output.read_bytes()).hexdigest()
                manifest['evidence_files'].append({
                    'path': str(lib_output.relative_to(root)),
                    'sha256': lib_hash,
                    'type': 'content_library'
                })
                manifest['collector_status']['content_library'] = 'completed'
                manifest['gaps'] = [g for g in manifest.get('gaps', []) if g.get('kind') not in ('content_library_failed', 'content_library_error')]
            else:
                lib_data = None
                manifest['collector_status']['content_library'] = 'failed'
                manifest['gaps'].append({
                    'kind': 'content_library_failed',
                    'detail': res.stderr or res.stdout or 'content-library did not create output file'
                })
        except Exception as exc:
            lib_data = None
            manifest['collector_status']['content_library'] = 'failed'
            manifest['gaps'].append({'kind': 'content_library_error', 'detail': str(exc)})
        save(manifest_path, manifest)

    if lib_data and isinstance(lib_data.get('placements'), list):
        for row in lib_data['placements']:
            raw_inputs['content_library_rows'].append({
                **row,
                'evidence_file': str(lib_output.relative_to(root)),
                'evidence_hash': lib_hash,
            })

    # Collector 2: Summary CSV Export & Import (if original Page due)
    needs_csv = any(item.get('placement_kind') == 'original_page' or item.get('kind') == 'publication' for item in due_work)
    if needs_csv:
        csv_output = exports_dir / f"content-summary-{page_id}-{run_id}.csv"
        joined_output = exports_dir / f"content-summary-{page_id}-{run_id}.imported.json"
        actual_csv = csv_output

        if manifest.get('collector_status', {}).get('csv_export') == 'completed' and joined_output.exists():
            imported_data = json.loads(joined_output.read_text())
            csv_ev = next((e for e in manifest.get('evidence_files', []) if e.get('type') == 'summary_csv'), None)
            if csv_ev and (root / csv_ev['path']).exists():
                actual_csv = root / csv_ev['path']
            csv_hash = hashlib.sha256(actual_csv.read_bytes()).hexdigest() if actual_csv.exists() else None
        else:
            manifest['collector_status']['csv_export'] = 'in_progress'
            save(manifest_path, manifest)
            export_cmd = [
                sys.executable, '-m', 'tools.facebook_agent', 'insights-export',
                '--page-id', page_id, '--output', str(csv_output), '--breakdown', 'summary'
            ]
            try:
                res = runner(export_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                # Parse stdout envelope: {"ok": true, "data": {"output": "..."}} or top-level output
                if res.stdout:
                    try:
                        exp_json = json.loads(res.stdout)
                        out_val = (exp_json.get('data') or {}).get('output') or exp_json.get('output')
                        if out_val and Path(out_val).exists():
                            actual_csv = Path(out_val).resolve()
                    except Exception:
                        pass

                if actual_csv.exists():
                    csv_hash = hashlib.sha256(actual_csv.read_bytes()).hexdigest()
                    _record_evidence_file(manifest, str(actual_csv.resolve().relative_to(root)), csv_hash, 'summary_csv')
                    import_cmd = [
                        sys.executable, '-m', 'tools.facebook_agent', 'insights-import',
                        '--page-id', page_id, '--csv', str(actual_csv), '--output', str(joined_output), '--breakdown', 'summary'
                    ]
                    res_imp = runner(import_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                    if joined_output.exists():
                        imported_data = json.loads(joined_output.read_text())
                        j_hash = hashlib.sha256(joined_output.read_bytes()).hexdigest()
                        _record_evidence_file(manifest, str(joined_output.resolve().relative_to(root)), j_hash, 'imported_csv_summary')
                        manifest['collector_status']['csv_export'] = 'completed'
                        manifest['gaps'] = [g for g in manifest.get('gaps', []) if g.get('kind') not in ('csv_export_failed', 'csv_export_error', 'csv_import_failed')]
                    else:
                        imported_data = None
                        manifest['collector_status']['csv_export'] = 'failed'
                        manifest['gaps'].append({
                            'kind': 'csv_import_failed',
                            'detail': res_imp.stderr or res_imp.stdout or 'insights-import failed'
                        })
                else:
                    imported_data = None
                    manifest['collector_status']['csv_export'] = 'failed'
                    manifest['gaps'].append({
                        'kind': 'csv_export_failed',
                        'detail': res.stderr or res.stdout or 'insights-export did not create CSV'
                    })
            except Exception as exc:
                imported_data = None
                manifest['collector_status']['csv_export'] = 'failed'
                manifest['gaps'].append({'kind': 'csv_export_error', 'detail': str(exc)})
            save(manifest_path, manifest)

        if imported_data and isinstance(imported_data.get('posts'), list):
            raw_inputs['csv_evidence_hash'] = csv_hash
            raw_inputs['csv_source_file'] = str(actual_csv.resolve().relative_to(root)) if actual_csv.exists() else None
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
        cap_output = captures_dir / f"{target_id}-{cp_name}.insights.json"

        if cap_output.exists():
            cap_data = json.loads(cap_output.read_text())
            cap_hash = hashlib.sha256(cap_output.read_bytes()).hexdigest()
            _record_evidence_file(manifest, str(cap_output.relative_to(root)), cap_hash, 'post_insights')
        else:
            cap_cmd = [
                sys.executable, '-m', 'tools.facebook_agent', 'insights',
                '--page-id', page_id, '--url', insights_url, '--open', 'Source',
                '--output', str(cap_output), '--scrolls', '2'
            ]
            try:
                res = runner(cap_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
                if cap_output.exists():
                    cap_data = json.loads(cap_output.read_text())
                    cap_hash = hashlib.sha256(cap_output.read_bytes()).hexdigest()
                    _record_evidence_file(manifest, str(cap_output.relative_to(root)), cap_hash, 'post_insights')
                    manifest['gaps'] = [g for g in manifest.get('gaps', []) if not (g.get('kind') in ('post_insights_failed', 'post_insights_error') and g.get('placement_id') == target_id)]
                else:
                    cap_data = None
                    manifest['gaps'].append({
                        'kind': 'post_insights_failed',
                        'placement_id': target_id,
                        'detail': res.stderr or res.stdout or f"insights capture failed for {insights_url}"
                    })
            except Exception as exc:
                cap_data = None
                manifest['gaps'].append({
                    'kind': 'post_insights_error',
                    'placement_id': target_id,
                    'detail': str(exc)
                })
            save(manifest_path, manifest)

        if cap_data and cap_data.get('capture_complete'):
            record = cap_data.get('records', [{}])[0]
            metrics = record.get('post_metrics') or {}

            # Calculate actual age in hours from visible_at / submitted_at / published_at
            pub_dt = None
            for pl in state.get('placements', []):
                if pl.get('id') == target_id:
                    time_str = pl.get('visible_at') or pl.get('submitted_at') or pl.get('published_at') or pl.get('first_seen_at')
                    if time_str:
                        pub_dt = timestamp(time_str)
                    break
            if not pub_dt:
                for pub in state.get('publications', []):
                    if pub.get('id') == (item.get('publication_id') or item.get('id')):
                        time_str = pub.get('published_at')
                        if time_str:
                            pub_dt = timestamp(time_str)
                        break

            obs_dt = timestamp(record.get('observed_at')) or now()
            if pub_dt:
                actual_age = round((obs_dt - pub_dt).total_seconds() / 3600, 2)
            else:
                baseline_hours = 168.0 if cp_name == '7d' else 24.0
                due_dt = timestamp(item.get('due_at')) if item.get('due_at') else obs_dt
                actual_age = round(baseline_hours + ((obs_dt - due_dt).total_seconds() / 3600), 2)

            raw_inputs['insights_captures'].append({
                'placement_id': target_id,
                'publication_id': item.get('publication_id') or item.get('id'),
                'checkpoint': cp_name,
                'actual_age_hours': actual_age,
                'evidence_file': str(cap_output.relative_to(root)),
                'evidence_hash': cap_hash,
                **cap_data,
            })

    # 5. Check for Collection Incomplete
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
    normalized = comparison.normalize_observations(manifest, raw_inputs)
    norm_path = root / 'sources/post-metrics/normalized' / f"{run_id}.json"
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    save(norm_path, normalized)

    # 7. Select comparable & run comparisons
    selected = comparison.select_comparable(normalized['observations'], state.get('placements', []))

    actions = []
    actions_path = root / 'loop/actions.jsonl'
    if actions_path.exists():
        for line in actions_path.read_text().splitlines():
            if line.strip():
                try:
                    actions.append(json.loads(line))
                except ValueError:
                    pass

    content_comp = comparison.compare_content(selected, actions=actions)
    group_comp = comparison.compare_groups(selected, actions=actions)

    all_gaps = list(manifest.get('gaps', [])) + list(normalized.get('gaps', [])) + list(selected.get('gaps', []))
    comp_artifact = {
        'run_id': run_id,
        'content_comparison': content_comp,
        'group_comparison': group_comp,
        'gaps': all_gaps,
    }
    save(run_dir / 'comparison.json', comp_artifact)

    # 8. Checkpoint commit in publications.json
    for cap in raw_inputs['insights_captures']:
        p_id = cap.get('placement_id')
        cp_name = cap.get('checkpoint', '24h')
        for pl in state.get('placements', []):
            if pl['id'] == p_id and cp_name in pl.get('checkpoints', {}):
                cp = pl['checkpoints'][cp_name]
                cp['status'] = 'collected'
                cp['attempts'] = cp.get('attempts', 0) + 1
                cp['selected_observation_ref'] = cap.get('evidence_file')
                cp['review_status'] = 'pending'
        for pub in state.get('publications', []):
            if pub['id'] == cap.get('publication_id'):
                pub['metrics_status'] = 'collected'
                pub['review_status'] = 'pending'
                pub['receipt_file'] = cap.get('evidence_file')
    save(state_path, state)

    # 9. Build review bundle
    hypotheses = {}
    if config.get('hypotheses_file'):
        try:
            hypotheses = json.loads(project_file(root, config['hypotheses_file']).read_text())
        except Exception:
            pass

    bundle = comparison.build_review_bundle(comp_artifact, hypotheses=hypotheses)
    save(run_dir / 'review-bundle.json', bundle)

    failed_collectors = [k for k, v in manifest.get('collector_status', {}).items() if v == 'failed']
    any_insights_failed = any(g.get('kind') in ('post_insights_failed', 'post_insights_error') for g in manifest.get('gaps', []))
    is_partial = bool(failed_collectors or any_insights_failed)

    if is_partial:
        status_str = 'partial_collection_pending_review'
        exit_code = 1
        manifest['warnings'].append(f"Incomplete collection: collectors {failed_collectors or 'post_insights'} encountered errors; partial review available.")
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


def record_run_review(root, run_id, review_data):
    """Save structured proposals and human-readable review table for a run."""
    root = Path(root).resolve()
    run_dir = root / 'loop/runs' / run_id
    if not run_dir.exists():
        raise ValueError(f"Run {run_id} not found.")

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
    run_dir = root / 'loop/runs' / run_id
    review_path = run_dir / 'review.json'
    if not review_path.exists():
        raise ValueError(f"No review found for run {run_id}.")

    review_data = json.loads(review_path.read_text())
    review_data['status'] = 'approved'
    review_data['approved_at'] = now().isoformat()
    review_data['approved_proposals'] = proposal_ids or [s.get('id') for s in review_data.get('suggestions', [])]
    save(review_path, review_data)

    manifest_path = run_dir / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest['status'] = 'review_approved'
        manifest['approved_at'] = review_data['approved_at']
        save(manifest_path, manifest)

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
            result = [item for item in state['publications'] if due(item, now())]
        else:
            result = state

        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
