"""Offline tests: python3 -m unittest discover -s tools/loop/tests"""

import copy
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.loop import engine


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_path = self.root / 'loop/publications.json'
        self.state = {'publications': []}
        self.page_id = '456'
        self.entry = engine.register(self.state, 3, 'https://www.facebook.com/reel/123',
                                     '2026-01-01T00:00:00Z')
        self.at = engine.timestamp('2026-01-02T00:00:00Z')
        self.calls = []
        self.receipt = {
            'id': 'run-1', 'run_url': 'https://app.glasser.ai/runs/run-1',
            'status': 'COMPLETED', 'charge_usd': '0.00188',
            'completed_at': '2026-01-02T00:05:00Z',
            'provider_response': {'http_status': 200},
            'output': {'success': True, 'url': self.entry['url'],
                       'author': {'id': self.page_id},
                       'view_count': 23, 'like_count': 0, 'share_count': 0,
                       'comment_count': None, 'video': {'length_in_second': 10}},
        }

    def fake(self, *args):
        self.calls.append(args)
        if args[0] == 'search':
            return {'task_id': 'tsk_test'}
        if args[0] == 'inspect':
            return {'price': {'rule': {'type': 'flat', 'amount_usd': '0.00188'},
                              'charges': {'NO_RESULT': '0.00188'}}}
        return copy.deepcopy(self.receipt)

    def collect(self, budget='0.00188', at=None, call=None):
        return engine.collect(self.state, self.state_path, budget,
                              project_root=self.root, page_id=self.page_id,
                              call=call or self.fake, at=at or self.at)

    def test_24_hour_boundary(self):
        self.assertFalse(engine.due(self.entry, self.at - timedelta(microseconds=1)))
        self.assertTrue(engine.due(self.entry, self.at))
        self.assertEqual(self.collect(at=self.at - timedelta(seconds=1)), [])
        self.assertEqual(self.calls, [])

    def test_collect_once_nulls_receipt_and_review(self):
        self.collect()
        self.assertEqual(self.entry['snapshot']['views'], 23)
        self.assertIsNone(self.entry['snapshot']['comments'])
        self.assertIsNone(self.entry['snapshot']['qualified_inquiries'])
        self.assertGreater(self.entry['snapshot']['age_hours'], 24)
        self.assertEqual(self.entry['review_status'], 'pending')
        self.assertTrue((self.root / self.entry['receipt_file']).exists())
        count = len(self.calls)
        self.assertEqual(self.collect(), [])
        self.assertEqual(len(self.calls), count)
        engine.review(self.entry, {'observation': '23 views', 'limitation': 'No inquiry data',
                                  'next_test': 'Application-first opening'})
        self.assertEqual(self.entry['review_status'], 'reviewed')
        self.assertEqual(self.entry['reviews'][0]['run_url'], self.receipt['run_url'])

    def test_budget_ceiling(self):
        self.collect('0.00187')
        self.assertFalse(any(args[0] == 'run' for args in self.calls))
        self.assertEqual(self.entry['metrics_status'], 'pending')
        for value in ('NaN', '-1', 'Infinity'):
            with self.assertRaises(ValueError):
                self.collect(value)

    def test_timeout_keeps_saved_key(self):
        def fail(*args):
            if args[0] == 'run':
                saved = json.loads(self.state_path.read_text())['publications'][0]
                self.assertIn('idempotency_key', saved)
                raise RuntimeError('Transport outcome unknown')
            return self.fake(*args)
        with self.assertRaises(RuntimeError):
            self.collect(call=fail)
        key = self.entry['idempotency_key']
        self.collect()
        dispatched = next(args for args in self.calls if args[0] == 'run')
        self.assertEqual(dispatched[dispatched.index('--idempotency-key') + 1], key)

    def test_receipt_recovers_without_new_paid_call(self):
        engine.save(self.root / 'sources/post-metrics' / (self.entry['id'] + '-24h.run.json'),
                    self.receipt)
        self.collect()
        self.assertFalse(any(args[0] == 'run' for args in self.calls))
        self.assertEqual(self.entry['metrics_status'], 'collected')

    def test_no_result_is_not_zero_or_automatic_retry(self):
        self.receipt['output'] = {'success': False}
        self.collect()
        self.assertEqual(self.entry['metrics_status'], 'needs_attention')
        self.assertNotIn('snapshot', self.entry)
        self.assertEqual(self.collect(), [])

    def test_identity_mismatch(self):
        self.receipt['output']['author']['id'] = 'someone-else'
        self.collect()
        self.assertEqual(self.entry['metrics_status'], 'needs_attention')
        self.assertNotIn('snapshot', self.entry)

    def test_registration_idempotent_and_resolves_missing_details(self):
        again = engine.register(self.state, 3, self.entry['url'] + '/', self.entry['published_at'])
        self.assertIs(again, self.entry)
        self.assertEqual(len(self.state['publications']), 1)
        self.state['publications'].append({'post': 1, 'url': None,
                                          'metrics_status': 'missing_publication_details'})
        engine.register(self.state, 1, 'https://www.facebook.com/posts/456', '2026-01-01T00:00:00Z')
        self.assertEqual(len(self.state['publications']), 2)
        for url, time in [('https://evil.example/post', '2026-01-01T00:00:00Z'),
                          (self.entry['url'], '2026-01-01T00:00:00')]:
            with self.assertRaises(ValueError):
                engine.register(self.state, 3, url, time)


    def test_dashboard_checkpoint_collects_once_without_glasser(self):
        self.entry['insights_url'] = 'https://www.facebook.com/content/insights/?content_id=test'
        evidence = self.root / 'sources/post-metrics' / (self.entry['id'] + '-24h.insights.json')

        def fake_cli(*args, **kwargs):
            engine.save(evidence, {'capture_complete': True,
                                  'profile': {'url': f'https://www.facebook.com/profile.php?id={self.page_id}'}, 'records': [{
                'observed_at': '2026-01-02T00:05:00Z', 'url': self.entry['insights_url'],
                'post_metrics': {'views': 23, 'viewers': 1, 'average_percentage_watched': 100,
                                 'qualified_inquiries': None},
            }]})

        with patch.object(engine.subprocess, 'run', side_effect=fake_cli) as cli:
            engine.collect_insights(self.state, self.state_path, project_root=self.root,
                                    page_id=self.page_id, at=self.at)
            self.assertEqual(self.entry['metrics_source'], 'facebook_insights_dashboard')
            self.assertEqual(self.entry['snapshot']['viewers'], 1)
            self.assertEqual(self.entry['review_status'], 'pending')
            self.assertEqual(self.entry['charge_usd'], '0.00')
            self.assertEqual(engine.collect_insights(self.state, self.state_path,
                                                    project_root=self.root, page_id=self.page_id, at=self.at), [])
            self.assertEqual(cli.call_count, 1)
            args = cli.call_args.args[0]
            self.assertEqual(args[args.index('--page-id') + 1], self.page_id)
            self.assertEqual(cli.call_args.kwargs['cwd'], engine.REPO_ROOT)

    def test_resolve_timestamp_on_known_url_preserves_identity(self):
        self.entry['published_at'] = None
        self.entry['metrics_status'] = 'missing_publication_details'
        identity = self.entry['id']
        result = engine.register(self.state, 3, self.entry['url'], '2026-01-01T00:00:00Z')
        self.assertEqual(result['id'], identity)
        self.assertTrue(engine.due(result, self.at))

    def test_project_initialization_and_optional_hypotheses(self):
        engine.initialize(self.root, self.page_id)
        self.assertEqual(engine.load_project(self.root)['page_id'], self.page_id)
        state = json.loads(self.state_path.read_text())
        state['publications'].append(self.entry)
        engine.save(self.state_path, state)
        engine.initialize(self.root, self.page_id)
        self.assertEqual(json.loads(self.state_path.read_text()), state)
        with self.assertRaises(ValueError):
            engine.initialize(self.root, '999')
        with self.assertRaises(ValueError):
            engine.initialize(self.root, 'not-a-page')
        with self.assertRaises(ValueError):
            engine.project_file(self.root, '../other-project.json')

    def test_two_projects_do_not_share_state_or_receipts(self):
        other_root = self.root / 'unrelated-project'
        engine.initialize(self.root, self.page_id)
        engine.initialize(other_root, '789')
        self.collect()
        self.assertEqual(json.loads((other_root / 'loop/publications.json').read_text())['publications'], [])
        self.assertEqual(list((other_root / 'sources/post-metrics').glob('*.json')), [])
        self.assertEqual(engine.load_project(other_root)['page_id'], '789')
        other_state = copy.deepcopy({'publications': [self.entry]})
        other_entry = other_state['publications'][0]
        other_entry['metrics_status'] = 'pending'
        def other_call(*args):
            result = self.fake(*args)
            if args[0] == 'run':
                result['output']['author']['id'] = '789'
            return result
        engine.collect(other_state, other_root / 'loop/publications.json', '0.00188',
                       project_root=other_root, page_id='789', call=other_call, at=self.at)
        self.assertEqual(other_entry['metrics_status'], 'collected')
        self.assertEqual(json.loads((self.root / self.entry['receipt_file']).read_text())['output']['author']['id'], self.page_id)
        self.assertEqual(json.loads((other_root / other_entry['receipt_file']).read_text())['output']['author']['id'], '789')

    def test_dry_run_writes_nothing_to_disk(self):
        new_dir = self.root / 'brand-new-project'
        res = engine.initialize(new_dir, '999111', dry_run=True)
        self.assertTrue(res['dry_run'])
        self.assertFalse(new_dir.exists())

    def test_cli_register_without_product_schema(self):
        import contextlib
        import io
        engine.initialize(self.root, self.page_id)
        with contextlib.redirect_stdout(io.StringIO()):
            engine.main(['--project', str(self.root), 'register', '--post', '1',
                         '--url', 'https://www.facebook.com/reel/999',
                         '--published-at', '2026-01-01T00:00:00Z'])
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['publications'][0]['post'], 1)

    def test_cli_requires_explicit_project(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            engine.main(['status'])

    def test_project_hypothesis_mapping_is_optional_and_scoped(self):
        import contextlib
        import io
        hypothesis_path = self.root / 'custom/hypotheses.json'
        engine.save(hypothesis_path, {'hypotheses': [{'post': 17}]})
        engine.initialize(self.root, self.page_id, 'custom/hypotheses.json')
        command = ['--project', str(self.root), 'register', '--post', '18',
                   '--url', 'https://www.facebook.com/reel/999',
                   '--published-at', '2026-01-01T00:00:00Z']
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            engine.main(command)
        self.assertEqual(json.loads(self.state_path.read_text())['publications'], [])

    def test_register_with_none_published_at_does_not_crash(self):
        # Bugfix check: known permalink without published_at records missing_publication_details
        entry = engine.register(self.state, 4, 'https://www.facebook.com/reel/987654', None)
        self.assertIsNone(entry['published_at'])
        self.assertIsNone(entry['due_at'])
        self.assertEqual(entry['metrics_status'], 'missing_publication_details')
        # Re-registering with published_at resolves it
        resolved = engine.register(self.state, 4, 'https://www.facebook.com/reel/987654', '2026-01-01T00:00:00Z')
        self.assertEqual(resolved['published_at'], '2026-01-01T00:00:00+00:00')
        self.assertEqual(resolved['metrics_status'], 'pending')

    def test_migration_v1_to_v2_with_backup_and_checkpoints(self):
        engine.initialize(self.root, self.page_id)
        # Create legacy state with 1 collected publication
        self.collect()
        legacy_bytes = self.state_path.read_bytes()

        # Migrate
        result = engine.migrate(self.root)
        self.assertEqual(result['status'], 'migrated')
        self.assertEqual(result['schema_version'], 2)

        # Byte-preserving backup check
        backup_path = self.root / 'loop/publications.json.v1.bak'
        self.assertTrue(backup_path.exists())
        self.assertEqual(backup_path.read_bytes(), legacy_bytes)

        # Check v2 state structure
        v2_state = json.loads(self.state_path.read_text())
        self.assertEqual(v2_state['schema_version'], 2)
        self.assertEqual(len(v2_state['publications']), 1)
        self.assertEqual(len(v2_state['placements']), 1)

        placement = v2_state['placements'][0]
        self.assertEqual(placement['kind'], 'original_page')
        self.assertEqual(placement['checkpoints']['24h']['status'], 'collected')
        # Invariant: 7d checkpoint is NEVER marked collected from a legacy 24h snapshot
        self.assertEqual(placement['checkpoints']['7d']['status'], 'pending')

        # Migration idempotency
        rerun = engine.migrate(self.root)
        self.assertEqual(rerun['status'], 'already_migrated')

    def test_record_buyer_action(self):
        engine.initialize(self.root, self.page_id)
        action_data = {
            'contact_key': 'user-hash-abc',
            'intent': 'paper-sample-request',
            'status': 'qualified',
            'agreed_next_step': 'ship_sample_kit',
            'publication_id': self.entry['id'],
        }
        res = engine.record_action(self.root, action_data)
        self.assertEqual(res['status'], 'qualified')
        actions_file = self.root / 'loop/actions.jsonl'
        self.assertTrue(actions_file.exists())
        lines = actions_file.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed['contact_key'], 'user-hash-abc')

    def test_due_checkpoints_deduplication(self):
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        pub_id = pub['id']
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [
                {
                    'id': 'pl-orig-1',
                    'publication_id': pub_id,
                    'kind': 'original_page',
                    'checkpoints': {
                        '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'},
                        '7d': {'due_at': '2026-01-08T00:00:00Z', 'status': 'pending'},
                    }
                }
            ]
        }
        due_at = engine.timestamp('2026-01-03T00:00:00Z')
        due = engine.due_checkpoints(state, at=due_at)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]['placement_id'], 'pl-orig-1')
        self.assertEqual(due[0]['checkpoint'], '24h')

        pub2 = engine.register(self.state, 2, 'https://www.facebook.com/reel/222', '2026-01-01T00:00:00Z')
        state['publications'].append(pub2)
        due_both = engine.due_checkpoints(state, at=due_at)
        self.assertEqual(len(due_both), 2)
        kinds = {d['kind'] for d in due_both}
        self.assertIn('placement_checkpoint', kinds)
        self.assertIn('publication', kinds)

    def test_cycle_no_work(self):
        engine.initialize(self.root, self.page_id)
        dry_res = engine.cycle(self.root, dry_run=True)
        self.assertEqual(dry_res['status'], 'no_work')
        self.assertEqual(dry_res['exit_code'], 0)

        real_res = engine.cycle(self.root)
        self.assertEqual(real_res['status'], 'no_work')
        self.assertEqual(real_res['exit_code'], 0)
        self.assertEqual(real_res['due_work_count'], 0)

    def test_cycle_collection_incomplete_on_collector_failure(self):
        import subprocess
        engine.initialize(self.root, self.page_id)
        state = {
            'schema_version': 2,
            'publications': [],
            'placements': [
                {
                    'id': 'pl-orig-1',
                    'publication_id': 'pub-1',
                    'kind': 'original_page',
                    'insights_url': 'https://www.facebook.com/insights/111',
                    'checkpoints': {
                        '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}
                    }
                }
            ]
        }
        engine.save(self.state_path, state)

        def failing_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout='', stderr='Collector failed')

        res = engine.cycle(self.root, runner=failing_runner)
        self.assertEqual(res['status'], 'collection_incomplete')
        self.assertEqual(res['exit_code'], 1)
        self.assertGreater(len(res['gaps']), 0)

    def test_cycle_offline_and_review_approval(self):
        import hashlib
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        pub['insights_url'] = 'https://www.facebook.com/insights/111'
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [
                {
                    'id': 'pl-orig-1',
                    'publication_id': pub['id'],
                    'kind': 'original_page',
                    'permalink': pub['url'],
                    'insights_url': pub['insights_url'],
                    'checkpoints': {
                        '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}
                    }
                }
            ]
        }
        engine.save(self.state_path, state)

        dry_res = engine.cycle(self.root, dry_run=True)
        self.assertTrue(dry_res['dry_run'])
        self.assertEqual(dry_res['status'], 'planned')
        self.assertEqual(dry_res['due_work_count'], 1)

        commands_run = []
        def mock_runner(cmd, **kwargs):
            commands_run.append(list(cmd))
            if 'content-library' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({
                    'status': 'ok',
                    'placements': [{
                        'id': 'lib-row-1',
                        'post_id': '111',
                        'kind': 'reel',
                        'views': 120,
                        'viewers': 95,
                    }]
                }))
            elif 'insights-export' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text('Date,Reactions,Comments,Shares\n2026-01-01,15,3,2\n')
            elif 'insights-import' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({
                    'posts': [{
                        'post_id': '111',
                        'summary_metrics': {'reactions': 15, 'comments': 3, 'shares': 2}
                    }]
                }))
            elif 'insights' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{
                        'observed_at': '2026-01-02T01:00:00Z',
                        'post_metrics': {'views': 120, 'viewers': 95, 'three_second_views': 80}
                    }]
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        cycle_res = engine.cycle(self.root, runner=mock_runner)
        self.assertEqual(cycle_res['status'], 'pending_agent_review')
        run_id = cycle_res['run_id']
        run_dir = self.root / 'loop/runs' / run_id

        self.assertEqual(len(commands_run), 4)
        self.assertTrue((run_dir / 'manifest.json').exists())
        self.assertTrue((run_dir / 'comparison.json').exists())
        self.assertTrue((run_dir / 'review-bundle.json').exists())

        manifest = json.loads((run_dir / 'manifest.json').read_text())
        for ev in manifest['evidence_files']:
            ev_file = self.root / ev['path']
            self.assertTrue(ev_file.exists())
            self.assertEqual(ev['sha256'], hashlib.sha256(ev_file.read_bytes()).hexdigest())

        # Checkpoint committed
        updated_state = json.loads(self.state_path.read_text())
        self.assertEqual(updated_state['placements'][0]['checkpoints']['24h']['status'], 'collected')

        review_data = {
            'observation': 'Creative hook retained 65% viewers at 3 seconds',
            'limitation': 'Inquiry data is not yet attributed to group copies',
            'suggestions': [
                {
                    'id': 'sug-1',
                    'target': 'reel-opening',
                    'change': 'Test buyer-first problem hook',
                    'expected_outcome': 'Increase 3s retention from 65% to 80%',
                    'controls': 'Keep body, CTA, and placement constant'
                }
            ]
        }
        rec = engine.record_run_review(self.root, run_id, review_data)
        self.assertEqual(rec['status'], 'proposed')
        self.assertTrue((run_dir / 'review.json').exists())
        self.assertTrue((run_dir / 'review.md').exists())

        appr = engine.approve_run_review(self.root, run_id, ['sug-1'])
        self.assertEqual(appr['status'], 'approved')
        self.assertEqual(appr['approved_proposals'], ['sug-1'])
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'review_approved')

    def test_cycle_resume_preserves_completed_and_prevents_reexecution(self):
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        pub['insights_url'] = 'https://www.facebook.com/insights/111'
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [
                {
                    'id': 'pl-orig-1',
                    'publication_id': pub['id'],
                    'kind': 'original_page',
                    'permalink': pub['url'],
                    'insights_url': pub['insights_url'],
                    'checkpoints': {
                        '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}
                    }
                }
            ]
        }
        engine.save(self.state_path, state)

        # Content library succeeds, but insights fails
        def partial_runner(cmd, **kwargs):
            if 'content-library' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({'placements': []}))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout='', stderr='insights error')

        res1 = engine.cycle(self.root, runner=partial_runner)
        self.assertEqual(res1['status'], 'collection_incomplete')
        run_id = res1['run_id']

        # Path traversal guard
        with self.assertRaises(ValueError):
            engine.cycle(self.root, resume='../evil')
        with self.assertRaises(ValueError):
            engine.cycle(self.root, resume='nonexistent-run')

        # Resuming with working runner skips content-library
        resumed_cmds = []
        def working_runner(cmd, **kwargs):
            resumed_cmds.append(list(cmd))
            if 'content-library' in cmd:
                self.fail('content-library was completed and should not run again on resume!')
            elif 'insights-export' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text('Date,Reactions\n2026-01-01,10\n')
            elif 'insights-import' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({'posts': [{'post_id': '111', 'summary_metrics': {'reactions': 10}}]}))
            elif 'insights' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{
                        'observed_at': '2026-01-02T01:00:00Z',
                        'post_metrics': {'views': 100}
                    }]
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res2 = engine.cycle(self.root, resume=run_id, runner=working_runner)
        self.assertEqual(res2['status'], 'pending_agent_review')
        self.assertEqual(res2['run_id'], run_id)

    def test_cycle_reused_csv_export_envelope_adapter(self):
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        pub['insights_url'] = 'https://www.facebook.com/insights/111'
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1',
                'publication_id': pub['id'],
                'kind': 'original_page',
                'permalink': pub['url'],
                'insights_url': pub['insights_url'],
                'checkpoints': {
                    '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}
                }
            }]
        }
        engine.save(self.state_path, state)

        # Pre-create an already downloaded/reconciled CSV with different filename
        reused_csv = (self.root / 'sources/post-metrics/exports/reused-report-999.csv').resolve()
        reused_csv.parent.mkdir(parents=True, exist_ok=True)
        reused_csv.write_text('Date,Reactions\n2026-01-01,42\n')

        commands_dispatched = []
        def mock_reused_runner(cmd, **kwargs):
            commands_dispatched.append(list(cmd))
            if 'content-library' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({'placements': []}))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')
            elif 'insights-export' in cmd:
                # Meta CLI envelope returns data.output pointing to the reused report
                stdout_env = json.dumps({
                    'ok': True,
                    'data': {
                        'status': 'reused',
                        'output': str(reused_csv)
                    }
                })
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout_env, stderr='')
            elif 'insights-import' in cmd:
                # Assert insights-import was invoked with the reused CSV path, not original requested path
                csv_idx = cmd.index('--csv') + 1
                self.assertEqual(cmd[csv_idx], str(reused_csv))
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({'posts': [{'post_id': '111', 'summary_metrics': {'reactions': 42}}]}))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')
            elif 'insights' in cmd:
                out_idx = cmd.index('--output') + 1
                Path(cmd[out_idx]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z', 'post_metrics': {'views': 100}}]
                }))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res = engine.cycle(self.root, runner=mock_reused_runner)
        self.assertEqual(res['status'], 'pending_agent_review')
        run_dir = self.root / 'loop/runs' / res['run_id']
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        # Reused CSV path is recorded in manifest evidence files
        self.assertTrue(any(e['path'] == str(reused_csv.relative_to(self.root.resolve())) for e in manifest['evidence_files']))


    def test_cli_due_reports_placement_checkpoints(self):
        import contextlib
        import io
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        pub['metrics_status'] = 'collected'
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': 'original_page',
                'checkpoints': {
                    '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'collected'},
                    '7d': {'due_at': '2026-01-08T00:00:00Z', 'status': 'pending'},
                },
            }],
        }
        engine.save(self.state_path, state)
        with patch.object(engine, 'now', return_value=engine.timestamp('2026-01-09T00:00:00Z')):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                engine.main(['--project', str(self.root), 'due'])
        due = json.loads(stream.getvalue())
        self.assertEqual([(item['placement_id'], item['checkpoint']) for item in due],
                         [('pl-orig-1', '7d')])

    def test_compare_and_prepare_review_dispatch_without_collection(self):
        import contextlib
        import io
        cycle_res = self._run_single_placement_cycle()
        run_id = cycle_res['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        (run_dir / 'review-bundle.json').unlink()

        with patch.object(engine.subprocess, 'run',
                          side_effect=AssertionError('compare must not collect')):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                engine.main(['--project', str(self.root), 'compare', '--run', run_id])
            compared = json.loads(stream.getvalue())
            self.assertEqual(compared['status'], 'compared')
            self.assertEqual(compared['comparison_file'], f'loop/runs/{run_id}/comparison.json')
            self.assertFalse((run_dir / 'review-bundle.json').exists())

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                engine.main(['--project', str(self.root), 'prepare-review', '--run', run_id])
            prepared = json.loads(stream.getvalue())
            self.assertEqual(prepared['status'], 'review_prepared')
            self.assertTrue((run_dir / 'review-bundle.json').exists())
            self.assertTrue(prepared['summary'])

        with self.assertRaises(ValueError):
            engine.main(['--project', str(self.root), 'compare', '--run', 'missing-run'])

    def test_resume_repairs_changed_evidence_without_overwriting(self):
        import subprocess
        res1 = self._run_single_placement_cycle(insights_fails=True)
        self.assertEqual(res1['status'], 'collection_incomplete')
        run_id = res1['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        lib_path = self.root / 'sources/post-metrics/captures' / run_id / 'content-library.json'
        original_hash = engine._sha256(lib_path)

        lib_path.write_text(json.dumps({'placements': [], 'tampered': True}))

        commands = []
        def working(cmd, **kwargs):
            commands.append(list(cmd))
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'posts': []}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        engine.cycle(self.root, resume=run_id, runner=working)
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        self.assertTrue(any(g.get('kind') == 'evidence_repair' for g in manifest['gaps']))
        lib_entries = [e for e in manifest['evidence_files']
                       if e['path'].startswith(f'sources/post-metrics/captures/{run_id}/')]
        self.assertEqual(len({e['path'] for e in lib_entries}), len(lib_entries))
        by_path = {e['path']: e['sha256'] for e in lib_entries}
        repaired = [path for path in by_path if 'repairs/' in path]
        self.assertEqual(len(repaired), 1)
        self.assertIn('repair1', repaired[0])
        self.assertEqual(by_path[f'sources/post-metrics/captures/{run_id}/content-library.json'],
                         original_hash)
        self.assertTrue((self.root / repaired[0]).exists())
        self.assertTrue(json.loads(lib_path.read_text())['tampered'])

    def test_empty_insights_records_is_a_gap_not_a_crash(self):
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': 'original_page',
                'permalink': pub['url'], 'insights_url': 'https://www.facebook.com/insights/111',
                'visibility': 'visible', 'visible_at': '2026-01-01T00:00:00Z',
                'checkpoints': {'24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}},
            }],
        }
        engine.save(self.state_path, state)

        def runner(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'posts': [{'post_id': '111'}]}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res = engine.cycle(self.root, runner=runner)
        self.assertEqual(res['status'], 'partial_collection_pending_review')
        manifest = json.loads((self.root / 'loop/runs' / res['run_id'] / 'manifest.json').read_text())
        self.assertTrue(any(g.get('kind') == 'post_insights_unusable' for g in manifest['gaps']))
        state = json.loads(self.state_path.read_text())
        self.assertNotEqual(state['placements'][0]['checkpoints']['24h']['status'], 'collected')

    def test_untracked_existing_library_is_repaired_not_overwritten(self):
        import subprocess
        res1 = self._run_single_placement_cycle(insights_fails=True)
        run_id = res1['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        lib_relative = f'sources/post-metrics/captures/{run_id}/content-library.json'
        lib_path = self.root / lib_relative
        original = lib_path.read_text()
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        manifest['collector_status']['content_library'] = 'failed'
        manifest['evidence_files'] = [e for e in manifest['evidence_files'] if e['path'] != lib_relative]
        engine.save(run_dir / 'manifest.json', manifest)

        def runner(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        engine.cycle(self.root, resume=run_id, runner=runner)
        self.assertEqual(lib_path.read_text(), original)
        repairs = list((lib_path.parent / 'repairs').glob('content-library-repair*.json'))
        self.assertTrue(repairs)
        updated = json.loads((run_dir / 'manifest.json').read_text())
        self.assertTrue(any(g.get('kind') == 'evidence_repair'
                            and g.get('repair_path', '').endswith(repairs[0].name)
                            for g in updated['gaps']))

    def test_csv_audit_without_csv_is_repaired_to_new_path(self):
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': 'original_page',
                'permalink': pub['url'], 'insights_url': 'https://www.facebook.com/insights/111',
                'visibility': 'visible', 'visible_at': '2026-01-01T00:00:00Z',
                'checkpoints': {'24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}},
            }],
        }
        engine.save(self.state_path, state)

        def failing(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                output = Path(cmd[cmd.index('--output') + 1])
                output.with_suffix('.export.json').write_text(json.dumps({
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'status': 'creation_requested', 'report_id': '42',
                    'existing_report_ids': ['42'],
                }))
                return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                   stdout='', stderr='Expected one visible Export data; found 0')
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res1 = engine.cycle(self.root, runner=failing)
        self.assertEqual(res1['status'], 'partial_collection_pending_review')
        run_id = res1['run_id']
        original_csv = (self.root / 'sources/post-metrics/exports'
                        / f'content-summary-{self.page_id}-{run_id}.csv')
        self.assertFalse(original_csv.exists())
        self.assertTrue(original_csv.with_suffix('.export.json').exists())

        def working(cmd, **kwargs):
            if 'insights-export' in cmd:
                output = Path(cmd[cmd.index('--output') + 1])
                self.assertIn('/exports/repairs/', str(output))
                self.assertNotEqual(output, original_csv)
                self.assertEqual(cmd[cmd.index('--report-id') + 1], '42')
                output.write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(
                    json.dumps({'posts': [{'post_id': '111'}]}))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        engine.cycle(self.root, resume=run_id, runner=working)
        manifest = json.loads((self.root / 'loop/runs' / run_id / 'manifest.json').read_text())
        self.assertTrue(any(e.get('type') == 'summary_csv' and '/exports/repairs/' in e['path']
                            for e in manifest['evidence_files']))

    def test_valid_csv_is_reimported_without_another_export(self):
        import hashlib
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': 'original_page',
                'permalink': pub['url'], 'insights_url': 'https://www.facebook.com/insights/111',
                'visibility': 'visible', 'visible_at': '2026-01-01T00:00:00Z',
                'checkpoints': {'24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}},
            }],
        }
        engine.save(self.state_path, state)
        exports = []

        def import_fails(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                exports.append(list(cmd))
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).unlink(missing_ok=True)
                return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                   stdout='', stderr='import failed')
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res1 = engine.cycle(self.root, runner=import_fails)
        self.assertEqual(res1['status'], 'partial_collection_pending_review')
        run_id = res1['run_id']
        csv_path = (self.root / 'sources/post-metrics/exports'
                    / f'content-summary-{self.page_id}-{run_id}.csv')
        original_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        export_count = len(exports)

        imports = []
        def working(cmd, **kwargs):
            if 'insights-export' in cmd:
                exports.append(list(cmd))
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                imports.append(list(cmd))
                self.assertEqual(cmd[cmd.index('--csv') + 1], str(csv_path.resolve()))
                Path(cmd[cmd.index('--output') + 1]).write_text(
                    json.dumps({'posts': [{'post_id': '111'}]}))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        engine.cycle(self.root, resume=run_id, runner=working)
        self.assertEqual(len(exports), export_count)
        self.assertTrue(imports)
        self.assertEqual(hashlib.sha256(csv_path.read_bytes()).hexdigest(), original_hash)
        manifest = json.loads((self.root / 'loop/runs' / run_id / 'manifest.json').read_text())
        self.assertEqual(manifest['collector_status']['csv_export'], 'completed')
        self.assertFalse(any('/exports/repairs/' in e['path']
                             for e in manifest['evidence_files']
                             if e.get('type') == 'summary_csv'))

    def test_verified_library_is_reused_after_a_failed_repair(self):
        res1 = self._run_single_placement_cycle()
        run_id = res1['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        manifest['collector_status']['content_library'] = 'failed'
        engine.save(run_dir / 'manifest.json', manifest)

        commands = []
        def forbidden(cmd, **kwargs):
            commands.append(list(cmd))
            raise AssertionError(f'unexpected collector call: {cmd}')

        engine.cycle(self.root, resume=run_id, runner=forbidden)
        self.assertEqual(commands, [])
        updated = json.loads((run_dir / 'manifest.json').read_text())
        self.assertEqual(updated['collector_status']['content_library'], 'completed')
        self.assertTrue(any(e['type'] == 'content_library' for e in updated['evidence_files']))

    def test_intact_resume_has_no_side_effects_or_attempt_increment(self):
        import subprocess
        res1 = self._run_single_placement_cycle(insights_fails=True)
        run_id = res1['run_id']

        def working(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'posts': []}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        engine.cycle(self.root, resume=run_id, runner=working)
        attempts = json.loads(self.state_path.read_text())['placements'][0]['checkpoints']['24h']['attempts']
        self.assertEqual(attempts, 1)

        engine.record_run_review(self.root, run_id, {
            'observation': 'One snapshot',
            'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })

        commands = []
        def forbidden(cmd, **kwargs):
            commands.append(list(cmd))
            raise AssertionError(f'unexpected collector call: {cmd}')

        res = engine.cycle(self.root, resume=run_id, runner=forbidden)
        self.assertEqual(commands, [])
        self.assertEqual(res['status'], 'review_proposed')
        attempts_again = json.loads(self.state_path.read_text())['placements'][0]['checkpoints']['24h']['attempts']
        self.assertEqual(attempts_again, 1)
        checkpoint = json.loads(self.state_path.read_text())['placements'][0]['checkpoints']['24h']
        self.assertEqual(checkpoint['review_status'], 'reviewed')

    def test_no_work_surfaces_pending_reviews_and_open_runs(self):
        cycle_res = self._run_single_placement_cycle()
        res = engine.cycle(self.root)
        self.assertEqual(res['status'], 'no_work')
        self.assertEqual(res['pending_review_count'], 1)
        self.assertIn(cycle_res['run_id'], {run['run_id'] for run in res['open_runs']})

        review = engine.record_run_review(self.root, cycle_res['run_id'], {
            'observation': 'One late snapshot',
            'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        self.assertEqual(review['status'], 'proposed')
        manifest = json.loads((self.root / 'loop/runs' / cycle_res['run_id'] / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'review_proposed')
        self.assertEqual(manifest['review_status'], 'proposed')
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['placements'][0]['checkpoints']['24h']['review_status'], 'reviewed')
        self.assertEqual(engine.pending_work(self.root, state)['pending_review_count'], 0)

    def test_gap_deduplication(self):
        from tools.loop import comparison as comparison_module
        gaps = [
            {'kind': 'csv_export_failed', 'detail': 'same'},
            {'kind': 'csv_export_failed', 'detail': 'same'},
            {'kind': 'unresolved_group_identity', 'placement_id': 'row-a', 'detail': 'same'},
            {'kind': 'unresolved_group_identity', 'placement_id': 'row-b', 'detail': 'same'},
        ]
        self.assertEqual(len(comparison_module.dedupe_gaps(gaps)), 3)

    def test_page_post_id_maps_library_row_to_placement(self):
        from tools.loop import comparison as comparison_module
        normalized = comparison_module.normalize_observations(
            {'run_id': 'run-x', 'gaps': []},
            {'content_library_rows': [
                {'id': 'row-known', 'post_id': '111', 'kind': 'original_page', 'views': 10},
                {'id': 'row-group', 'post_id': None, 'kind': 'group_copy',
                 'group_name': 'Group A', 'views': 5},
            ],
            'csv_posts': [{'post_id': '111', 'export_period_totals': {'reactions': 3}},
                          {'post_id': '999', 'export_period_totals': {'reactions': 0}}],
            'csv_evidence_hash': 'hash'},
            placements=[{'id': 'pl-1', 'publication_id': 'pub-1', 'copy_post_id': '111'}],
        )
        known = next(item for item in normalized['observations'] if item['id'] == 'obs-lib-row-known')
        self.assertEqual(known['placement_id'], 'pl-1')
        self.assertEqual(known['publication_id'], 'pub-1')
        self.assertEqual(known['identity_source'], 'page_post_id')
        group = next(item for item in normalized['observations'] if item['id'] == 'obs-lib-row-group')
        self.assertIsNone(group['placement_id'])
        csv_known = next(item for item in normalized['observations'] if item['id'] == 'obs-csv-111')
        self.assertEqual(csv_known['placement_id'], 'pl-1')
        self.assertEqual(csv_known['identity_source'], 'page_post_id')
        csv_other = next(item for item in normalized['observations'] if item['id'] == 'obs-csv-999')
        self.assertIsNone(csv_other['placement_id'])
        self.assertEqual(csv_other['identity_source'], 'unresolved')
        self.assertEqual([gap['kind'] for gap in normalized['gaps']], ['unresolved_group_identity'])

    def test_group_copy_without_visible_time_stays_descriptive(self):
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-group-1', 'publication_id': pub['id'], 'kind': 'group_copy',
                'permalink': pub['url'], 'insights_url': 'https://www.facebook.com/insights/111',
                'visibility': 'visible', 'visible_at': None,
                'checkpoints': {'24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}},
            }],
        }
        engine.save(self.state_path, state)

        def runner(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'posts': []}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res = engine.cycle(self.root, runner=runner)
        run_dir = self.root / 'loop/runs' / res['run_id']
        comparison_data = json.loads((run_dir / 'comparison.json').read_text())
        self.assertEqual(comparison_data['content_comparison']['creative_matrix'], [])
        reasons = {item.get('exclusion_reason')
                   for item in comparison_data['content_comparison']['descriptive_observations']}
        self.assertIn('unknown_age', reasons)
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        self.assertTrue(any(g.get('kind') == 'unknown_visible_at' for g in manifest['gaps']))

    def _run_single_placement_cycle(self, insights_fails=False):
        import subprocess
        engine.initialize(self.root, self.page_id)
        pub = engine.register(self.state, 1, 'https://www.facebook.com/reel/111', '2026-01-01T00:00:00Z')
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': pub['id'], 'kind': 'original_page',
                'permalink': pub['url'], 'insights_url': 'https://www.facebook.com/insights/111',
                'visibility': 'visible', 'visible_at': '2026-01-01T00:00:00Z',
                'checkpoints': {'24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}},
            }],
        }
        engine.save(self.state_path, state)

        def runner(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'posts': []}))
            elif 'insights' in cmd:
                if insights_fails:
                    return subprocess.CompletedProcess(args=cmd, returncode=1,
                                                       stdout='', stderr='insights error')
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-02-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        return engine.cycle(self.root, runner=runner)


if __name__ == '__main__':
    unittest.main()
