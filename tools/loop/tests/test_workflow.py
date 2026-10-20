"""End-to-end workflow, resume and pending-work regressions."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from support import LoopTestCase
from tools.loop import approval, compare_posts, review, storage, workflow


class WorkflowTest(LoopTestCase):
    def test_cycle_no_work(self):
        self.save_state({'schema_version': 2, 'publications': [], 'placements': []})
        dry_res = self.run_cycle(dry_run=True)
        self.assertEqual(dry_res['status'], 'no_work')
        self.assertEqual(dry_res['exit_code'], 0)

        real_res = self.run_cycle()
        self.assertEqual(real_res['status'], 'no_work')
        self.assertEqual(real_res['exit_code'], 0)
        self.assertEqual(real_res['due_work_count'], 0)
        self.assertFalse((self.root / 'loop/status.json').exists() and
                         self.status()['state'] == 'running')

    def test_cycle_collection_incomplete_on_collector_failure(self):
        storage.save(self.state_path, {
            'schema_version': 2,
            'publications': [],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': 'pub-1', 'kind': 'original_page',
                'insights_url': 'https://www.facebook.com/insights/111',
                'checkpoints': {'24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'}},
            }],
        })

        def failing_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=1,
                                               stdout='', stderr='Collector failed')

        res = self.run_cycle(runner=failing_runner)
        self.assertEqual(res['status'], 'collection_incomplete')
        self.assertEqual(res['exit_code'], 1)
        self.assertGreater(len(res['gaps']), 0)
        status = self.status()
        self.assertEqual(status['current_stage'], 'collect')
        self.assertEqual(status['state'], 'failed')

    def test_cycle_offline_and_review_approval(self):
        self.make_cycle_state()
        cycle_res = self.run_cycle()
        self.assertEqual(cycle_res['status'], 'pending_agent_review')
        run_id = cycle_res['run_id']
        run_dir = self.root / 'loop/runs' / run_id

        self.assertEqual(len(self.calls), 4)
        self.assertTrue((run_dir / 'manifest.json').exists())
        self.assertTrue((run_dir / 'comparison.json').exists())
        self.assertTrue((run_dir / 'review-bundle.json').exists())

        manifest = self.run_manifest(run_id)
        import hashlib
        for ev in manifest['evidence_files']:
            ev_file = self.root / ev['path']
            self.assertTrue(ev_file.exists())
            self.assertEqual(ev['sha256'], hashlib.sha256(ev_file.read_bytes()).hexdigest())

        updated_state = json.loads(self.state_path.read_text())
        self.assertEqual(updated_state['placements'][0]['checkpoints']['24h']['status'], 'collected')

        self.assertEqual(self.status()['current_stage'], 'review')
        self.assertEqual(self.status()['state'], 'waiting')

        review_data = {
            'observation': 'Creative hook retained 65% viewers at 3 seconds',
            'limitation': 'Inquiry data is not yet attributed to group copies',
            'suggestions': [{
                'id': 'sug-1', 'target': 'reel-opening',
                'change': 'Test buyer-first problem hook',
                'expected_outcome': 'Increase 3s retention from 65% to 80%',
                'controls': 'Keep body, CTA, and placement constant',
            }],
        }
        rec = workflow.record_review_run(self.root, run_id, review_data)
        self.assertEqual(rec['status'], 'proposed')
        self.assertTrue((run_dir / 'review.json').exists())
        self.assertTrue((run_dir / 'review.md').exists())
        self.assertEqual(self.status()['current_stage'], 'approval')
        self.assertEqual(self.status()['state'], 'waiting')

        appr = workflow.approve_review_run(self.root, run_id, ['sug-1'])
        self.assertEqual(appr['status'], 'approved')
        self.assertEqual(appr['approved_proposals'], ['sug-1'])
        self.assertEqual(self.run_manifest(run_id)['status'], 'review_approved')
        self.assertEqual(self.status()['state'], 'completed')

    def test_cycle_resume_preserves_completed_and_prevents_reexecution(self):
        self.make_cycle_state()

        def partial_runner(cmd, **kwargs):
            self.calls.append(list(cmd))
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')
            return subprocess.CompletedProcess(args=cmd, returncode=1,
                                               stdout='', stderr='insights error')

        res1 = self.run_cycle(runner=partial_runner)
        self.assertEqual(res1['status'], 'collection_incomplete')
        run_id = res1['run_id']
        self.assertEqual(self.status()['state'], 'failed')

        with self.assertRaises(ValueError):
            workflow.cycle(self.root, resume='../evil')
        with self.assertRaises(ValueError):
            workflow.cycle(self.root, resume='nonexistent-run')

        resumed_cmds = []

        def working_runner(cmd, **kwargs):
            resumed_cmds.append(list(cmd))
            if 'content-library' in cmd:
                self.fail('content-library was completed and should not run again on resume!')
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,10\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(
                    json.dumps({'posts': [{'post_id': '111', 'summary_metrics': {'reactions': 10}}]}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res2 = self.run_cycle(runner=working_runner, resume=run_id)
        self.assertEqual(res2['status'], 'pending_agent_review')
        self.assertEqual(res2['run_id'], run_id)
        self.assertEqual(self.status()['current_stage'], 'review')

    def test_cycle_reused_csv_export_envelope_adapter(self):
        self.make_cycle_state()
        reused_csv = (self.root / 'sources/post-metrics/exports/reused-report-999.csv').resolve()
        reused_csv.parent.mkdir(parents=True, exist_ok=True)
        reused_csv.write_text('Date,Reactions\n2026-01-01,42\n')

        def mock_reused_runner(cmd, **kwargs):
            self.calls.append(list(cmd))
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')
            if 'insights-export' in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stderr='', stdout=json.dumps({
                    'ok': True, 'data': {'status': 'reused', 'output': str(reused_csv)}}))
            if 'insights-import' in cmd:
                self.assertEqual(cmd[cmd.index('--csv') + 1], str(reused_csv))
                Path(cmd[cmd.index('--output') + 1]).write_text(
                    json.dumps({'posts': [{'post_id': '111', 'summary_metrics': {'reactions': 42}}]}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [{'observed_at': '2026-01-02T01:00:00Z',
                                 'post_metrics': {'views': 100}}],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res = self.run_cycle(runner=mock_reused_runner)
        self.assertEqual(res['status'], 'pending_agent_review')
        manifest = self.run_manifest(res['run_id'])
        self.assertTrue(any(e['path'] == str(reused_csv.relative_to(self.root.resolve()))
                            for e in manifest['evidence_files']))

    def test_resume_repairs_changed_evidence_without_overwriting(self):
        self.make_cycle_state()
        res1 = self.run_cycle(runner=self.default_runner(insights_fails=True))
        self.assertEqual(res1['status'], 'collection_incomplete')
        run_id = res1['run_id']
        lib_path = self.root / 'sources/post-metrics/captures' / run_id / 'content-library.json'
        original_hash = storage.sha256_file(lib_path)
        lib_path.write_text(json.dumps({'placements': [], 'tampered': True}))

        self.run_cycle(runner=self.default_runner(), resume=run_id)
        run_dir = self.root / 'loop/runs' / run_id
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
        self.make_cycle_state()

        def runner(cmd, **kwargs):
            if 'content-library' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({'placements': []}))
            elif 'insights-export' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text('Date,Reactions\n2026-01-01,0\n')
            elif 'insights-import' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(
                    json.dumps({'posts': [{'post_id': '111'}]}))
            elif 'insights' in cmd:
                Path(cmd[cmd.index('--output') + 1]).write_text(json.dumps({
                    'capture_complete': True,
                    'profile': {'url': f'https://www.facebook.com/?id={self.page_id}'},
                    'records': [],
                }))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='ok', stderr='')

        res = self.run_cycle(runner=runner)
        self.assertEqual(res['status'], 'partial_collection_pending_review')
        manifest = self.run_manifest(res['run_id'])
        self.assertTrue(any(g.get('kind') == 'post_insights_unusable' for g in manifest['gaps']))
        state = json.loads(self.state_path.read_text())
        self.assertNotEqual(state['placements'][0]['checkpoints']['24h']['status'], 'collected')
        status = self.status()
        self.assertEqual(status['current_stage'], 'collect')
        self.assertEqual(status['current_step'], 'post_insights')
        self.assertEqual(status['state'], 'failed')

    def test_untracked_existing_library_is_repaired_not_overwritten(self):
        self.make_cycle_state()
        res1 = self.run_cycle(runner=self.default_runner(insights_fails=True))
        run_id = res1['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        lib_relative = f'sources/post-metrics/captures/{run_id}/content-library.json'
        lib_path = self.root / lib_relative
        original = lib_path.read_text()
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        manifest['collector_status']['content_library'] = 'failed'
        manifest['evidence_files'] = [e for e in manifest['evidence_files'] if e['path'] != lib_relative]
        storage.save(run_dir / 'manifest.json', manifest)

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

        self.run_cycle(runner=runner, resume=run_id)
        self.assertEqual(lib_path.read_text(), original)
        repairs = list((lib_path.parent / 'repairs').glob('content-library-repair*.json'))
        self.assertTrue(repairs)
        updated = json.loads((run_dir / 'manifest.json').read_text())
        self.assertTrue(any(g.get('kind') == 'evidence_repair'
                            and g.get('repair_path', '').endswith(repairs[0].name)
                            for g in updated['gaps']))

    def test_csv_audit_without_csv_is_repaired_to_new_path(self):
        self.make_cycle_state()

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

        res1 = self.run_cycle(runner=failing)
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

        self.run_cycle(runner=working, resume=run_id)
        manifest = self.run_manifest(run_id)
        self.assertTrue(any(e.get('type') == 'summary_csv' and '/exports/repairs/' in e['path']
                            for e in manifest['evidence_files']))

    def test_valid_csv_is_reimported_without_another_export(self):
        import hashlib
        self.make_cycle_state()
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

        res1 = self.run_cycle(runner=import_fails)
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

        self.run_cycle(runner=working, resume=run_id)
        self.assertEqual(len(exports), export_count)
        self.assertTrue(imports)
        self.assertEqual(hashlib.sha256(csv_path.read_bytes()).hexdigest(), original_hash)
        manifest = self.run_manifest(run_id)
        self.assertEqual(manifest['collector_status']['csv_export'], 'completed')
        self.assertFalse(any('/exports/repairs/' in e['path']
                             for e in manifest['evidence_files']
                             if e.get('type') == 'summary_csv'))

    def test_verified_library_is_reused_after_a_failed_repair(self):
        self.make_cycle_state()
        res1 = self.run_cycle()
        run_id = res1['run_id']
        run_dir = self.root / 'loop/runs' / run_id
        manifest = json.loads((run_dir / 'manifest.json').read_text())
        manifest['collector_status']['content_library'] = 'failed'
        storage.save(run_dir / 'manifest.json', manifest)
        commands = []

        def forbidden(cmd, **kwargs):
            commands.append(list(cmd))
            raise AssertionError(f'unexpected collector call: {cmd}')

        self.run_cycle(runner=forbidden, resume=run_id)
        self.assertEqual(commands, [])
        updated = json.loads((run_dir / 'manifest.json').read_text())
        self.assertEqual(updated['collector_status']['content_library'], 'completed')
        self.assertTrue(any(e['type'] == 'content_library' for e in updated['evidence_files']))

    def test_intact_resume_has_no_side_effects_or_attempt_increment(self):
        self.make_cycle_state()
        res1 = self.run_cycle(runner=self.default_runner(insights_fails=True))
        run_id = res1['run_id']
        self.run_cycle(runner=self.default_runner(), resume=run_id)
        attempts = json.loads(self.state_path.read_text())['placements'][0]['checkpoints']['24h']['attempts']
        self.assertEqual(attempts, 1)

        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot',
            'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })

        commands = []

        def forbidden(cmd, **kwargs):
            commands.append(list(cmd))
            raise AssertionError(f'unexpected collector call: {cmd}')

        res = self.run_cycle(runner=forbidden, resume=run_id)
        self.assertEqual(commands, [])
        self.assertEqual(res['status'], 'review_proposed')
        attempts_again = json.loads(self.state_path.read_text())['placements'][0]['checkpoints']['24h']['attempts']
        self.assertEqual(attempts_again, 1)
        checkpoint = json.loads(self.state_path.read_text())['placements'][0]['checkpoints']['24h']
        self.assertEqual(checkpoint['review_status'], 'reviewed')
        self.assertEqual(self.status()['current_stage'], 'approval')
        self.assertEqual(self.status()['state'], 'waiting')

    def test_no_work_surfaces_pending_reviews_and_open_runs(self):
        self.make_cycle_state()
        cycle_res = self.run_cycle()
        res = self.run_cycle()
        self.assertEqual(res['status'], 'no_work')
        self.assertEqual(res['pending_review_count'], 1)
        self.assertIn(cycle_res['run_id'], {run['run_id'] for run in res['open_runs']})
        status = self.status()
        self.assertEqual(status['state'], 'waiting')
        self.assertIn(cycle_res['run_id'], [status['run_id']] + status['pending_run_ids'])

        review_record = workflow.record_review_run(self.root, cycle_res['run_id'], {
            'observation': 'One late snapshot',
            'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        self.assertEqual(review_record['status'], 'proposed')
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['placements'][0]['checkpoints']['24h']['review_status'], 'reviewed')
        self.assertEqual(workflow.pending_work(self.root, state)['pending_review_count'], 0)

    def test_group_copy_without_visible_time_stays_descriptive(self):
        pub = self.make_cycle_state(kind='group_copy', visible_at=None)[0]
        state = json.loads(self.state_path.read_text())
        state['placements'][0]['kind'] = 'group_copy'
        state['placements'][0]['visible_at'] = None
        self.save_state(state)

        res = self.run_cycle()
        comparison_data = json.loads(
            (self.root / 'loop/runs' / res['run_id'] / 'comparison.json').read_text())
        self.assertEqual(comparison_data['content_comparison']['creative_matrix'], [])
        reasons = {item.get('exclusion_reason')
                   for item in comparison_data['content_comparison']['descriptive_observations']}
        self.assertIn('unknown_age', reasons)
        manifest = self.run_manifest(res['run_id'])
        self.assertTrue(any(g.get('kind') == 'unknown_visible_at' for g in manifest['gaps']))

    def test_empty_comparison_reports_not_comparable_with_counts(self):
        self.make_cycle_state(kind='group_copy', visible_at=None)
        state = json.loads(self.state_path.read_text())
        state['placements'][0]['visible_at'] = None
        self.save_state(state)

        res = self.run_cycle()
        summary = res['comparison']['comparison_summary']
        self.assertEqual(summary['result'], 'not_comparable')
        self.assertEqual(summary['eligible_content_items'], 0)
        self.assertEqual(summary['eligible_group_items'], 0)
        self.assertGreater(summary['descriptive_observations'], 0)
        self.assertIn('unknown_age', summary['exclusion_reasons'])
        self.assertIn('No leaderboard is implied', summary['reason'])

        status = self.status()
        self.assertEqual(status['comparison_result']['result'], 'not_comparable')
        self.assertEqual(status['stages']['compare_groups']['state'], 'waiting')
        self.assertIn('No eligible observations',
                      status['stages']['compare_groups']['reason'])
        bundle = json.loads(
            (self.root / 'loop/runs' / res['run_id'] / 'review-bundle.json').read_text())
        self.assertEqual(bundle['comparison_result'], 'not_comparable')
        self.assertEqual(bundle['comparison_summary']['eligible_observations'], 0)

    def test_compare_failure_reports_the_stage_that_failed(self):
        self.make_cycle_state()
        res = self.run_cycle()
        with patch.object(compare_posts, 'compare_content',
                          side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                workflow.compare_run(self.root, res['run_id'])
        status = self.status()
        self.assertEqual(status['current_stage'], 'compare_posts')
        self.assertEqual(status['state'], 'failed')
        self.assertEqual(status['error']['stage'], 'compare_posts')
        self.assertEqual(status['stages']['eligibility']['state'], 'completed')
        self.assertEqual(status['stages']['compare_posts']['state'], 'failed')
        self.assertNotIn('compare_groups', status['error']['stage'])
