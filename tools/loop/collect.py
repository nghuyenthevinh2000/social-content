"""Stage 3: capture evidence from the existing Facebook collectors.

Sequential collection: Content Library, summary CSV export/import, post Insights.
Browser implementation stays in ``tools/facebook_agent/``.
"""

from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlparse
import uuid

from tools.loop import checkpoints, storage


ENDPOINT = '/v1/facebook/post'


def glasser(*args):
    result = subprocess.run(['glasser', *args, '-j'], capture_output=True,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def collect(state, state_path, budget, *, project_root, page_id, call=glasser, at=None):
    """Legacy publication-level Glasser collection; one attempt per due publication."""
    storage.validate_page_id(page_id)
    at = at or storage.now()
    remaining = Decimal(budget)
    if not remaining.is_finite() or remaining < 0:
        raise ValueError('Budget must be a finite nonnegative USD amount.')
    entries = [entry for entry in state['publications'] if checkpoints.due(entry, at)]
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
        storage.save(state_path, state)
        receipt_path = project_root / 'sources/post-metrics' / (entry['id'] + '-24h.run.json')
        try:
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
            else:
                receipt = call('run', '-p', 'scrapecreators', '-e', ENDPOINT,
                               '--endpoint-version', '2', '--task', entry['task_id'],
                               '--idempotency-key', entry['idempotency_key'], '--wait',
                               '-i', json.dumps({'url': entry['url']}))
                storage.save(receipt_path, receipt)
            if receipt['status'] in ('QUEUED', 'RUNNING'):
                receipt = call('runs', 'get', '-r', receipt['id'], '--wait')
                storage.save(receipt_path, receipt)
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
                    storage.save(state_path, state)
                    results.append(entry)
                    continue
                fetched = storage.timestamp(receipt['completed_at'])
                if fetched < storage.timestamp(entry['due_at']):
                    raise ValueError('Receipt predates the 24-hour checkpoint.')
                entry['snapshot'] = {
                    'fetched_at': fetched.isoformat(),
                    'age_hours': round((fetched - storage.timestamp(entry['published_at'])).total_seconds() / 3600, 2),
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
            storage.save(state_path, state)
            raise
        storage.save(state_path, state)
        results.append(entry)
    return results


def collect_insights(state, state_path, *, project_root, page_id, at=None):
    """Legacy free dashboard collection for due publications."""
    storage.validate_page_id(page_id)
    results = []
    for entry in state['publications']:
        if not checkpoints.due(entry, at or storage.now()):
            continue
        if not entry.get('insights_url'):
            entry['error'] = 'Discover this post’s Insights URL in the Content Library first.'
            storage.save(state_path, state)
            continue
        evidence = project_root / 'sources/post-metrics' / (entry['id'] + '-24h.insights.json')
        try:
            if not evidence.exists():
                subprocess.run([
                    sys.executable, '-m', 'tools.facebook_agent', 'insights',
                    '--page-id', page_id, '--url', entry['insights_url'],
                    '--output', str(evidence), '--scrolls', '2',
                ], cwd=storage.REPO_ROOT, check=True, capture_output=True, text=True, timeout=120)
            captured = json.loads(evidence.read_text())
            if not captured.get('capture_complete'):
                raise ValueError('Incomplete dashboard evidence; inspect before retrying.')
            if parse_qs(urlparse(captured.get('profile', {}).get('url', '')).query).get('id') != [page_id]:
                raise ValueError('Dashboard evidence belongs to a different Page.')
            record = captured['records'][0]
            metrics = record.get('post_metrics')
            if not metrics or metrics.get('views') is None:
                raise ValueError('Expected labeled Post insights metrics were not available.')
            fetched = storage.timestamp(record['observed_at'])
            if fetched < storage.timestamp(entry['due_at']):
                raise ValueError('Dashboard evidence predates the 24-hour checkpoint.')
            entry['snapshot'] = {**metrics, 'fetched_at': fetched.isoformat(),
                                 'age_hours': round((fetched - storage.timestamp(entry['published_at'])).total_seconds() / 3600, 2)}
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
        storage.save(state_path, state)
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

    record = {
        'event_id': event.get('event_id') or uuid.uuid4().hex,
        'event_at': event.get('event_at') or storage.now().isoformat(),
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


def validate_library(manifest, data, page_id):
    """Reject empty, mismatched or unidentified library captures as usable coverage."""
    captured_page = data.get('page_id')
    placements = data.get('placements')
    if captured_page is not None and str(captured_page) != str(page_id):
        manifest['collector_status']['content_library'] = 'failed'
        storage.add_gap(manifest, {
            'kind': 'content_library_page_mismatch',
            'detail': f"Content Library evidence belongs to Page {captured_page}, not {page_id}.",
        })
        return False
    if data.get('traversal_complete') is False:
        manifest['collector_status']['content_library'] = 'failed'
        storage.add_gap(manifest, {
            'kind': 'content_library_traversal_incomplete',
            'detail': 'Content Library reported incomplete scroll-container traversal; rows are not complete coverage.',
        })
        return False
    if captured_page is not None and not isinstance(placements, list):
        manifest['collector_status']['content_library'] = 'failed'
        storage.add_gap(manifest, {
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
            storage.add_gap(manifest, {
                'kind': 'content_library_unidentified',
                'detail': 'No Content Library row has a verified post or group identity; coverage is not usable.',
            })
            return False
    if captured_page is None:
        storage.add_gap(manifest, {
            'kind': 'content_library_unverified',
            'detail': 'Content Library evidence has no Page identity; completeness cannot be verified.',
        })
    return True


class Collector:
    """Sequential collectors for one frozen run, persisting evidence manifests."""

    def __init__(self, root, run_id, page_id, state, manifest, manifest_path, runner):
        self.root = Path(root).resolve()
        self.run_id = run_id
        self.page_id = page_id
        self.state = state
        self.manifest = manifest
        self.manifest_path = manifest_path
        self.runner = runner
        self.captures_dir = self.root / 'sources/post-metrics/captures' / run_id
        self.exports_dir = self.root / 'sources/post-metrics/exports'
        self.raw_inputs = {
            'insights_captures': [],
            'content_library_rows': [],
            'csv_posts': [],
            'csv_evidence_hash': None,
            'csv_source_file': None,
        }
        self.changed = False
        self.failures = []

    def _save(self):
        storage.save(self.manifest_path, self.manifest)

    def fail(self, step, detail):
        if not any(item['step'] == step for item in self.failures):
            self.failures.append({'step': step, 'detail': detail})

    # Collector 1: Content Library -------------------------------------------------
    def content_library(self):
        lib_relative = f"sources/post-metrics/captures/{self.run_id}/content-library.json"
        lib_output = self.root / lib_relative
        lib_data = None
        lib_hash = None
        lib_relative_used = lib_relative
        lib_completed = self.manifest.get('collector_status', {}).get('content_library') == 'completed'
        storage.note_hash_conflicts(self.manifest, lib_relative)
        # Verified evidence beats a later failed collector run: reuse it and do not re-collect.
        reusable, reuse_reason = storage.check_reusable_evidence(
            self.root, self.manifest, lib_relative, 'content_library')
        if reusable:
            lib_data = json.loads(lib_output.read_text())
            lib_hash = storage.sha256_file(lib_output)
            if validate_library(self.manifest, lib_data, self.page_id):
                self.manifest['collector_status']['content_library'] = 'completed'
                # The selected evidence is usable; drop coverage gaps that described a discarded repair.
                self.manifest['gaps'] = [g for g in self.manifest.get('gaps', [])
                                         if g.get('kind') not in ('content_library_empty',
                                                                  'content_library_unidentified',
                                                                  'content_library_traversal_incomplete',
                                                                  'content_library_unverified')]
            else:
                self.fail('content_library', 'Reused Content Library evidence is not usable coverage.')
            self._save()
        else:
            # Missing or changed completed evidence is repaired at a new path.
            lib_recorded = storage.evidence_entry(self.manifest, lib_relative) is not None
            has_history = lib_completed or lib_recorded or lib_output.exists()
            lib_target = (storage.repair_path(self.captures_dir, lib_relative, self.manifest)
                          if has_history else lib_output)
            if lib_target != lib_output:
                storage.record_repair(
                    self.manifest, lib_relative, str(lib_target.relative_to(self.root)),
                    reuse_reason if (lib_completed or lib_recorded) else 'unrecorded')
            self.changed = True
            self.manifest.setdefault('collector_status', {})['content_library'] = 'in_progress'
            self._save()
            lib_target.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable, '-m', 'tools.facebook_agent', 'content-library',
                '--page-id', self.page_id, '--output', str(lib_target), '--scrolls', '3'
            ]
            try:
                res = self.runner(cmd, cwd=storage.REPO_ROOT, capture_output=True, text=True, timeout=120)
                if lib_target.exists():
                    lib_data = json.loads(lib_target.read_text())
                    lib_hash = storage.sha256_file(lib_target)
                    lib_relative_used = str(lib_target.relative_to(self.root))
                    parent = lib_relative if lib_target != lib_output else None
                    storage.record_evidence_file(
                        self.manifest, lib_relative_used, lib_hash, 'content_library',
                        parent_path=parent)
                    self.manifest['collector_status']['content_library'] = 'completed'
                    self.manifest['gaps'] = [g for g in self.manifest.get('gaps', [])
                                             if g.get('kind') not in ('content_library_failed', 'content_library_error')]
                    if not validate_library(self.manifest, lib_data, self.page_id):
                        self.fail('content_library', 'Content Library evidence is not usable coverage.')
                else:
                    lib_data = None
                    self.manifest['collector_status']['content_library'] = 'failed'
                    detail = res.stderr or res.stdout or 'content-library did not create output file'
                    storage.add_gap(self.manifest, {'kind': 'content_library_failed', 'detail': detail})
                    self.fail('content_library', detail)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                lib_data = None
                self.manifest['collector_status']['content_library'] = 'failed'
                storage.add_gap(self.manifest, {'kind': 'content_library_error', 'detail': str(exc)})
                self.fail('content_library', str(exc))
            self._save()

        if lib_data and isinstance(lib_data.get('placements'), list):
            for row in lib_data['placements']:
                self.raw_inputs['content_library_rows'].append({
                    **row,
                    'evidence_file': lib_relative_used,
                    'evidence_hash': lib_hash,
                })
        return lib_data

    # Collector 2: Summary CSV export and import -----------------------------------
    def summary_csv(self, due_work):
        needs_csv = any(item.get('placement_kind') == 'original_page'
                        or item.get('kind') == 'publication' for item in due_work)
        if not needs_csv:
            return None

        page_id = self.page_id
        csv_output = self.exports_dir / f"content-summary-{page_id}-{self.run_id}.csv"
        joined_output = self.exports_dir / f"content-summary-{page_id}-{self.run_id}.imported.json"
        csv_relative = str(csv_output.relative_to(self.root))
        joined_relative = str(joined_output.relative_to(self.root))
        actual_csv = csv_output

        csv_completed = self.manifest.get('collector_status', {}).get('csv_export') == 'completed'
        evidence_files = self.manifest.get('evidence_files', [])
        csv_ev = next((e for e in reversed(evidence_files) if e.get('type') == 'summary_csv'), None)
        joined_ev = next((e for e in reversed(evidence_files)
                          if e.get('type') == 'imported_csv_summary'), None)
        csv_ok = False
        joined_ok = False
        joined_used = joined_output
        if csv_ev:
            csv_ok, _ = storage.check_reusable_evidence(self.root, self.manifest, csv_ev['path'], 'summary_csv')
            if csv_ok:
                actual_csv = self.root / csv_ev['path']
        if joined_ev:
            joined_ok, _ = storage.check_reusable_evidence(self.root, self.manifest, joined_ev['path'],
                                                           'imported_csv_summary')
            if joined_ok:
                joined_used = self.root / joined_ev['path']

        def clear_csv_gaps(include_import=True):
            blocked = {'csv_export_failed', 'csv_export_error', 'csv_evidence_unusable'}
            if include_import:
                blocked.add('csv_import_failed')
            self.manifest['gaps'] = [g for g in self.manifest.get('gaps', [])
                                     if g.get('kind') not in blocked]

        imported_data = None
        csv_hash = None
        if csv_ok and joined_ok:
            imported_data = json.loads(joined_used.read_text())
            csv_hash = storage.sha256_file(actual_csv)
        elif csv_ok:
            # A verified CSV is never re-exported; only its joined import is rebuilt.
            self.changed = True
            csv_hash = storage.sha256_file(actual_csv)
            if joined_ev or joined_output.exists():
                joined_target = storage.repair_path(self.exports_dir, joined_relative, self.manifest)
                storage.record_repair(self.manifest, joined_relative,
                                      str(joined_target.relative_to(self.root)),
                                      'missing or changed')
            else:
                joined_target = joined_output
            clear_csv_gaps(include_import=False)
            self.manifest['collector_status']['csv_export'] = 'in_progress'
            self._save()
            joined_target.parent.mkdir(parents=True, exist_ok=True)
            try:
                res_imp = self.runner([
                    sys.executable, '-m', 'tools.facebook_agent', 'insights-import',
                    '--page-id', page_id, '--csv', str(actual_csv),
                    '--output', str(joined_target), '--breakdown', 'summary'
                ], cwd=storage.REPO_ROOT, capture_output=True, text=True, timeout=120)
                if joined_target.exists():
                    imported_data = json.loads(joined_target.read_text())
                    j_hash = storage.sha256_file(joined_target)
                    storage.record_evidence_file(
                        self.manifest, str(joined_target.resolve().relative_to(self.root)),
                        j_hash, 'imported_csv_summary',
                        parent_path=joined_relative if joined_target != joined_output else None)
                    self.manifest['collector_status']['csv_export'] = 'completed'
                    clear_csv_gaps()
                else:
                    imported_data = None
                    self.manifest['collector_status']['csv_export'] = 'failed'
                    detail = res_imp.stderr or res_imp.stdout or 'insights-import failed'
                    storage.add_gap(self.manifest, {'kind': 'csv_import_failed', 'detail': detail})
                    self.fail('csv_import', detail)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                imported_data = None
                self.manifest['collector_status']['csv_export'] = 'failed'
                storage.add_gap(self.manifest, {'kind': 'csv_import_failed', 'detail': str(exc)})
                self.fail('csv_import', str(exc))
            self._save()
        else:
            if csv_completed or csv_ev:
                storage.add_gap(self.manifest, {
                    'kind': 'csv_evidence_unusable',
                    'detail': 'Recorded CSV evidence is missing or its hash changed; export will be re-attempted through reconciliation.',
                })
            self.changed = True
            csv_recorded = csv_ev is not None
            csv_audit = csv_output.with_suffix('.export.json')
            has_history = (csv_completed or csv_recorded or csv_output.exists()
                           or joined_output.exists() or csv_audit.exists())
            if has_history:
                csv_target = storage.repair_path(self.exports_dir, csv_relative, self.manifest)
                joined_target = storage.repair_path(self.exports_dir, joined_relative, self.manifest)
                storage.record_repair(self.manifest, csv_relative,
                                      str(csv_target.relative_to(self.root)), 'missing or changed')
            else:
                csv_target, joined_target = csv_output, joined_output
            actual_csv = csv_target
            self.manifest['collector_status']['csv_export'] = 'in_progress'
            self._save()
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
                res = self.runner(export_cmd, cwd=storage.REPO_ROOT, capture_output=True,
                                  text=True, timeout=120)
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
                    csv_hash = storage.sha256_file(actual_csv)
                    storage.record_evidence_file(
                        self.manifest, str(actual_csv.resolve().relative_to(self.root)),
                        csv_hash, 'summary_csv')
                    clear_csv_gaps(include_import=False)
                    import_cmd = [
                        sys.executable, '-m', 'tools.facebook_agent', 'insights-import',
                        '--page-id', page_id, '--csv', str(actual_csv),
                        '--output', str(joined_target), '--breakdown', 'summary'
                    ]
                    res_imp = self.runner(import_cmd, cwd=storage.REPO_ROOT, capture_output=True,
                                          text=True, timeout=120)
                    if joined_target.exists():
                        imported_data = json.loads(joined_target.read_text())
                        j_hash = storage.sha256_file(joined_target)
                        storage.record_evidence_file(
                            self.manifest, str(joined_target.resolve().relative_to(self.root)),
                            j_hash, 'imported_csv_summary',
                            parent_path=joined_relative if joined_target != joined_output else None)
                        self.manifest['collector_status']['csv_export'] = 'completed'
                        clear_csv_gaps()
                    else:
                        imported_data = None
                        self.manifest['collector_status']['csv_export'] = 'failed'
                        detail = res_imp.stderr or res_imp.stdout or 'insights-import failed'
                        storage.add_gap(self.manifest, {'kind': 'csv_import_failed', 'detail': detail})
                        self.fail('csv_import', detail)
                else:
                    imported_data = None
                    self.manifest['collector_status']['csv_export'] = 'failed'
                    detail = res.stderr or res.stdout or 'insights-export did not create CSV'
                    storage.add_gap(self.manifest, {'kind': 'csv_export_failed', 'detail': detail})
                    self.fail('csv_export', detail)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                imported_data = None
                self.manifest['collector_status']['csv_export'] = 'failed'
                storage.add_gap(self.manifest, {'kind': 'csv_export_error', 'detail': str(exc)})
                self.fail('csv_export', str(exc))
            self._save()

        if imported_data and isinstance(imported_data.get('posts'), list):
            self.raw_inputs['csv_evidence_hash'] = csv_hash
            self.raw_inputs['csv_source_file'] = (
                str(actual_csv.resolve().relative_to(self.root))
                if actual_csv and actual_csv.exists() else None)
            self.raw_inputs['csv_posts'] = imported_data['posts']
        return imported_data

    # Collector 3: Post Dashboard Insights -----------------------------------------
    def post_insights(self, due_work):
        for item in due_work:
            insights_url = item.get('insights_url')
            if not insights_url:
                self.manifest['gaps'].append({
                    'kind': 'missing_insights_url',
                    'placement_id': item.get('placement_id') or item.get('id'),
                    'detail': 'No Insights URL found for due placement/publication.'
                })
                continue

            target_id = item.get('placement_id') or item.get('id')
            cp_name = item.get('checkpoint', '24h')
            cap_relative = f"sources/post-metrics/captures/{self.run_id}/{target_id}-{cp_name}.insights.json"
            cap_output = self.root / cap_relative
            cap_data = None
            cap_hash = None
            cap_relative_used = cap_relative
            reused = False

            storage.note_hash_conflicts(self.manifest, cap_relative)
            cap_ev = storage.evidence_entry(self.manifest, cap_relative)
            if cap_ev and cap_output.exists():
                cap_ok, cap_reason = storage.check_reusable_evidence(
                    self.root, self.manifest, cap_relative, 'post_insights')
                if cap_ok:
                    cap_data = json.loads(cap_output.read_text())
                    cap_hash = storage.sha256_file(cap_output)
                    reused = True
                else:
                    cap_target = storage.repair_path(self.captures_dir, cap_relative, self.manifest)
                    storage.record_repair(self.manifest, cap_relative,
                                          str(cap_target.relative_to(self.root)), cap_reason)
            elif cap_ev or cap_output.exists():
                cap_target = storage.repair_path(self.captures_dir, cap_relative, self.manifest)
                storage.record_repair(self.manifest, cap_relative,
                                      str(cap_target.relative_to(self.root)),
                                      'missing' if cap_ev else 'unrecorded')
            else:
                cap_target = cap_output

            if not reused:
                self.changed = True
                cap_target.parent.mkdir(parents=True, exist_ok=True)
                cap_cmd = [
                    sys.executable, '-m', 'tools.facebook_agent', 'insights',
                    '--page-id', self.page_id, '--url', insights_url, '--open', 'Source',
                    '--output', str(cap_target), '--scrolls', '2'
                ]
                try:
                    res = self.runner(cap_cmd, cwd=storage.REPO_ROOT, capture_output=True,
                                      text=True, timeout=120)
                    if cap_target.exists():
                        cap_data = json.loads(cap_target.read_text())
                        cap_hash = storage.sha256_file(cap_target)
                        cap_relative_used = str(cap_target.relative_to(self.root))
                        storage.record_evidence_file(
                            self.manifest, cap_relative_used, cap_hash, 'post_insights',
                            parent_path=cap_relative if cap_target != cap_output else None)
                        self.manifest['gaps'] = [g for g in self.manifest.get('gaps', [])
                                                 if not (g.get('kind') in ('post_insights_failed', 'post_insights_error')
                                                         and g.get('placement_id') == target_id)]
                    else:
                        cap_data = None
                        detail = res.stderr or res.stdout or f"insights capture failed for {insights_url}"
                        storage.add_gap(self.manifest, {
                            'kind': 'post_insights_failed',
                            'placement_id': target_id,
                            'detail': detail
                        })
                        self.fail('post_insights', detail)
                except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                    cap_data = None
                    storage.add_gap(self.manifest, {
                        'kind': 'post_insights_error',
                        'placement_id': target_id,
                        'detail': str(exc)
                    })
                    self.fail('post_insights', str(exc))
                self._save()

            if cap_data and cap_data.get('capture_complete'):
                records = cap_data.get('records') or []
                record = records[0] if records else {}
                metrics = record.get('post_metrics') or {}
                observed_raw = record.get('observed_at')
                usable_metrics = [value for value in metrics.values() if value is not None]
                profile_url = (cap_data.get('profile') or {}).get('url', '')
                profile_id = parse_qs(urlparse(profile_url).query).get('id', [None])[0]
                if (not records or not observed_raw or not usable_metrics
                        or (profile_id is not None and profile_id != self.page_id)):
                    detail = ('Insights capture lacks Page identity, an observation time, records '
                              'or any non-null metric; not accepted as required collection.')
                    storage.add_gap(self.manifest, {
                        'kind': 'post_insights_unusable',
                        'placement_id': target_id,
                        'detail': detail
                    })
                    self.fail('post_insights', detail)
                else:
                    # Only a verified visible time may define age. Unknown approval time stays unknown.
                    pub_dt = None
                    placement = next((pl for pl in self.state.get('placements', [])
                                      if pl.get('id') == target_id), None)
                    if placement is not None:
                        if placement.get('kind', 'original_page') == 'original_page':
                            time_str = placement.get('visible_at') or placement.get('submitted_at')
                        else:
                            time_str = placement.get('visible_at')
                        if time_str:
                            pub_dt = storage.timestamp(time_str)
                    if pub_dt is None and (placement is None
                                           or placement.get('kind', 'original_page') == 'original_page'):
                        for pub in self.state.get('publications', []):
                            if pub.get('id') == (item.get('publication_id') or item.get('id')):
                                if pub.get('published_at'):
                                    pub_dt = storage.timestamp(pub['published_at'])
                                break

                    obs_dt = storage.timestamp(observed_raw)
                    if pub_dt:
                        actual_age = round((obs_dt - pub_dt).total_seconds() / 3600, 2)
                    else:
                        actual_age = None
                        storage.add_gap(self.manifest, {
                            'kind': 'unknown_visible_at',
                            'placement_id': target_id,
                            'detail': 'Placement has no verified approval/visible time; snapshot stays descriptive with unknown age.'
                        })

                    self.raw_inputs['insights_captures'].append({
                        'placement_id': target_id,
                        'publication_id': item.get('publication_id') or item.get('id'),
                        'checkpoint': cp_name,
                        'actual_age_hours': actual_age,
                        'evidence_file': cap_relative_used,
                        'evidence_hash': cap_hash,
                        'reused': reused,
                        **cap_data,
                    })
        return self.raw_inputs['insights_captures']
