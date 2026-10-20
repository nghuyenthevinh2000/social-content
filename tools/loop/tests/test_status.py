"""Acceptance tests for the project-level status projection."""

import json
from pathlib import Path
from unittest.mock import patch

from support import LoopTestCase
from tools.loop import storage, workflow


class StatusProjectionTest(LoopTestCase):
    def test_csv_failure_reports_stage_step_and_recovery(self):
        self.make_cycle_state()
        res = self.run_cycle(runner=self.default_runner(export_fails=True))
        self.assertEqual(res['status'], 'partial_collection_pending_review')
        status = self.status()
        self.assertEqual(status['current_stage'], 'collect')
        self.assertEqual(status['current_step'], 'csv_export')
        self.assertEqual(status['state'], 'failed')
        self.assertIn('csv_export', status['next_action'])
        self.assertEqual(status['stages']['checkpoints']['state'], 'completed')
        self.assertEqual(status['stages']['collect']['state'], 'failed')
        self.assertEqual(status['stages']['review']['state'], 'waiting')
        self.assertIn('review_bundle', status['artifacts'])
        self.assertEqual(status['artifacts']['review_bundle'],
                         f"loop/runs/{res['run_id']}/review-bundle.json")

    def test_review_bundle_waits_for_agent(self):
        self.make_cycle_state()
        res = self.run_cycle()
        status = self.status()
        self.assertEqual(status['current_stage'], 'review')
        self.assertEqual(status['state'], 'waiting')
        self.assertEqual(status['run_id'], res['run_id'])
        self.assertIn('review --run', status['next_action'])
        self.assertIn('review_bundle', status['artifacts'])

    def test_recorded_proposal_waits_for_human(self):
        self.make_cycle_state()
        res = self.run_cycle()
        workflow.record_review_run(self.root, res['run_id'], {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        status = self.status()
        self.assertEqual(status['current_stage'], 'approval')
        self.assertEqual(status['state'], 'waiting')
        self.assertIn('review.json', status['artifacts']['review'])
        self.assertIn('approve-review', status['next_action'])
        self.assertNotEqual(status['next_action'], None)

    def test_intact_resume_keeps_projection_manifest_and_checkpoint_agree(self):
        self.make_cycle_state()
        res1 = self.run_cycle(runner=self.default_runner(insights_fails=True))
        run_id = res1['run_id']
        self.run_cycle(resume=run_id)
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        final = self.run_cycle(resume=run_id)
        self.assertEqual(final['status'], 'review_proposed')
        status = self.status()
        manifest = self.run_manifest(run_id)
        state = json.loads(self.state_path.read_text())
        self.assertEqual(status['current_stage'], 'approval')
        self.assertEqual(status['state'], 'waiting')
        self.assertEqual(manifest['review_status'], 'proposed')
        self.assertEqual(state['placements'][0]['checkpoints']['24h']['review_status'], 'reviewed')

    def test_crash_becomes_interrupted_not_completed(self):
        writer = workflow.StatusWriter(self.root)
        writer.begin('collect', run_id='run-crashed', step='post_insights')
        recovered = workflow.StatusWriter(self.root).recover_interrupted()
        self.assertEqual(recovered['state'], 'interrupted')
        self.assertEqual(recovered['stages']['collect']['state'], 'failed')
        self.assertIn('--resume run-crashed', recovered['next_action'])
        self.assertNotEqual(recovered['state'], 'completed')

    def test_no_due_work_lists_other_waiting_runs(self):
        self.make_cycle_state()
        first = self.run_cycle()
        second_run = self.root / 'loop/runs/zzz-waiting'
        second_run.mkdir(parents=True)
        storage.save(second_run / 'manifest.json', {
            'run_id': 'zzz-waiting', 'status': 'pending_agent_review',
            'page_id': self.page_id, 'collector_status': {}, 'gaps': [],
        })
        result = self.run_cycle()
        self.assertEqual(result['status'], 'no_work')
        status = self.status()
        self.assertEqual(status['state'], 'waiting')
        open_ids = {run['run_id'] for run in result['open_runs']}
        self.assertEqual(open_ids, {first['run_id'], 'zzz-waiting'})
        selected_and_pending = {status['run_id'], *status['pending_run_ids']}
        self.assertEqual(selected_and_pending, {first['run_id'], 'zzz-waiting'})

    def test_failed_pre_stage_status_write_prevents_collection(self):
        self.make_cycle_state()
        original_save = storage.save

        def failing_save(path, data):
            if Path(path).name == 'status.json':
                raise OSError('status write failed')
            return original_save(path, data)

        with patch.object(storage, 'save', side_effect=failing_save):
            with self.assertRaises(OSError):
                self.run_cycle()
        self.assertEqual(self.calls, [])

    def test_prepare_review_after_proposal_keeps_approval_handoff(self):
        self.make_cycle_state()
        res = self.run_cycle()
        run_id = res['run_id']
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        prepared = workflow.prepare_review_run(self.root, run_id)
        self.assertFalse(prepared['pending_agent_review'])
        self.assertEqual(prepared['review_status'], 'proposed')
        bundle = json.loads(
            (self.root / 'loop/runs' / run_id / 'review-bundle.json').read_text())
        self.assertFalse(bundle['pending_agent_review'])
        status = self.status()
        self.assertEqual(status['current_stage'], 'approval')
        self.assertEqual(status['state'], 'waiting')
        self.assertEqual(status['stages']['review']['state'], 'completed')
        self.assertEqual(self.run_manifest(run_id)['status'], 'review_proposed')

    def test_prepare_review_backfills_legacy_review_revision(self):
        self.make_cycle_state()
        res = self.run_cycle()
        run_id = res['run_id']
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        review_path = self.root / 'loop/runs' / run_id / 'review.json'
        record = json.loads(review_path.read_text())
        record.pop('evidence_revision')
        storage.save(review_path, record)

        prepared = workflow.prepare_review_run(self.root, run_id)
        self.assertFalse(prepared['pending_agent_review'])
        self.assertEqual(prepared['review_status'], 'proposed')
        record = json.loads(review_path.read_text())
        self.assertTrue(record['evidence_revision'])
        self.assertEqual(self.status()['current_stage'], 'approval')

    def test_prepare_review_invalidates_when_evidence_changes(self):
        self.make_cycle_state()
        res = self.run_cycle()
        run_id = res['run_id']
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        manifest = self.run_manifest(run_id)
        manifest['evidence_files'].append({
            'path': 'sources/post-metrics/later.json',
            'sha256': '0' * 64, 'type': 'post_insights',
        })
        storage.save(self.root / 'loop/runs' / run_id / 'manifest.json', manifest)

        prepared = workflow.prepare_review_run(self.root, run_id)
        self.assertTrue(prepared['pending_agent_review'])
        self.assertTrue(prepared['review_invalidated'])
        manifest = self.run_manifest(run_id)
        self.assertEqual(manifest['status'], 'pending_agent_review')
        self.assertEqual(manifest['review_status'], 'pending')
        review_record = json.loads(
            (self.root / 'loop/runs' / run_id / 'review.json').read_text())
        self.assertEqual(review_record['status'], 'superseded')
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['placements'][0]['checkpoints']['24h']['review_status'],
                         'pending')
        status = self.status()
        self.assertEqual(status['current_stage'], 'review')
        self.assertEqual(status['state'], 'waiting')
        self.assertIn('superseded', status['reason'])

    def test_intact_resume_closes_review_stage_with_recorded_proposal(self):
        self.make_cycle_state()
        res = self.run_cycle()
        run_id = res['run_id']
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        final = self.run_cycle(resume=run_id)
        self.assertEqual(final['status'], 'review_proposed')
        status = self.status()
        self.assertEqual(status['stages']['review']['state'], 'completed')
        self.assertEqual(status['stages']['approval']['state'], 'waiting')
        self.assertIsNone(status['stages']['approval']['ended_at'])
        bundle = json.loads(
            (self.root / 'loop/runs' / run_id / 'review-bundle.json').read_text())
        self.assertFalse(bundle['pending_agent_review'])

    def test_rebuild_uses_recorded_times_and_leaves_unknown_times_null(self):
        self.make_cycle_state()
        res = self.run_cycle()
        run_id = res['run_id']
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        history = self.run_manifest(run_id)['stage_history']
        approval_started = history['approval']['started_at']
        (self.root / 'loop/status.json').unlink()
        rebuilt = workflow.rebuild_if_missing(
            self.root, json.loads(self.state_path.read_text()))
        self.assertEqual(rebuilt['stages']['approval']['started_at'], approval_started)
        self.assertIsNone(rebuilt['stages']['approval']['ended_at'])
        self.assertEqual(rebuilt['stages']['collect']['started_at'],
                         history['collect']['started_at'])

        manifest = self.run_manifest(run_id)
        manifest.pop('stage_history', None)
        storage.save(self.root / 'loop/runs' / run_id / 'manifest.json', manifest)
        (self.root / 'loop/status.json').unlink()
        rebuilt = workflow.rebuild_if_missing(
            self.root, json.loads(self.state_path.read_text()))
        self.assertIsNone(rebuilt['stages']['collect']['started_at'])
        self.assertIsNone(rebuilt['stages']['collect']['ended_at'])
        self.assertEqual(rebuilt['stages']['collect']['state'], 'completed')

    def test_no_work_does_not_rewrite_waiting_run_history(self):
        self.make_cycle_state()
        res = self.run_cycle()
        run_id = res['run_id']
        workflow.record_review_run(self.root, run_id, {
            'observation': 'One snapshot', 'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
        })
        before = self.status()
        self.run_cycle()
        after = self.status()
        self.assertEqual(after['run_id'], run_id)
        self.assertEqual(after['stages']['approval']['started_at'],
                         before['stages']['approval']['started_at'])
        self.assertIsNone(after['stages']['approval']['ended_at'])
        self.assertEqual(after['stages']['collect']['started_at'],
                         before['stages']['collect']['started_at'])

    def test_stale_schema_projection_rebuilds_without_invented_times(self):
        self.make_cycle_state()
        res = self.run_cycle()
        status = self.status()
        status['schema_version'] = 1
        status['stages']['collect']['started_at'] = '2099-01-01T00:00:00+00:00'
        storage.save(self.root / 'loop/status.json', status)
        rebuilt = workflow.rebuild_if_missing(
            self.root, json.loads(self.state_path.read_text()))
        self.assertEqual(rebuilt['schema_version'], 3)
        self.assertNotEqual(rebuilt['stages']['collect']['started_at'],
                            '2099-01-01T00:00:00+00:00')
        self.assertEqual(rebuilt['stages']['collect']['started_at'],
                         self.run_manifest(res['run_id'])['stage_history']['collect']['started_at'])

    def test_missing_projection_rebuilds_from_saved_run(self):
        self.make_cycle_state()
        res = self.run_cycle(runner=self.default_runner(export_fails=True))
        (self.root / 'loop/status.json').unlink()
        state = json.loads(self.state_path.read_text())
        rebuilt = workflow.rebuild_if_missing(self.root, state)
        self.assertEqual(rebuilt['run_id'], res['run_id'])
        self.assertEqual(rebuilt['current_stage'], 'collect')
        self.assertEqual(rebuilt['current_step'], 'csv_export')
        self.assertEqual(rebuilt['state'], 'failed')
        self.assertTrue((self.root / 'loop/status.json').exists())
