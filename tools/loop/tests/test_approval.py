"""Tests for stage 8 human approval."""

import json

from support import LoopTestCase
from tools.loop import approval, storage


class ApprovalTest(LoopTestCase):
    def setUp(self):
        super().setUp()
        self.run_id = 'run-approval-test'
        self.run_dir = self.root / 'loop/runs' / self.run_id
        self.run_dir.mkdir(parents=True)
        storage.save(self.run_dir / 'manifest.json', {
            'run_id': self.run_id, 'status': 'review_proposed', 'page_id': self.page_id,
        })

    def test_approval_requires_recorded_review(self):
        with self.assertRaises(ValueError):
            approval.approve_run_review(self.root, self.run_id)

    def test_approval_records_only_selected_proposals(self):
        storage.save(self.run_dir / 'review.json', {
            'run_id': self.run_id, 'status': 'proposed',
            'observation': 'o', 'limitation': 'l',
            'suggestions': [{'id': 'sug-1'}, {'id': 'sug-2'}],
        })
        result = approval.approve_run_review(self.root, self.run_id, ['sug-1'])
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['approved_proposals'], ['sug-1'])
        manifest = json.loads((self.run_dir / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'review_approved')
        # Approval never publishes or changes placement state.
        self.assertEqual(json.loads(self.state_path.read_text())['placements'], [])

    def test_approval_defaults_to_all_proposals(self):
        storage.save(self.run_dir / 'review.json', {
            'run_id': self.run_id, 'status': 'proposed',
            'suggestions': [{'id': 'sug-1'}, {'id': 'sug-2'}],
        })
        result = approval.approve_run_review(self.root, self.run_id)
        self.assertEqual(result['approved_proposals'], ['sug-1', 'sug-2'])
