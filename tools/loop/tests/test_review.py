"""Tests for stage 7 review preparation and recording."""

import json
from pathlib import Path

from support import LoopTestCase
from tools.loop import review, storage


class ReviewTest(LoopTestCase):
    def setUp(self):
        super().setUp()
        self.run_id = 'run-review-test'
        self.run_dir = self.root / 'loop/runs' / self.run_id
        self.run_dir.mkdir(parents=True)
        self.manifest = {
            'run_id': self.run_id, 'status': 'pending_agent_review',
            'page_id': self.page_id, 'gaps': [], 'evidence_files': [],
        }
        storage.save(self.run_dir / 'manifest.json', self.manifest)
        storage.save(self.run_dir / 'comparison.json', {
            'run_id': self.run_id,
            'content_comparison': {'creative_matrix': [{'publication_id': 'pub-1'}],
                                   'descriptive_observations': []},
            'group_comparison': {'group_matrix': [], 'exclusions': []},
            'gaps': [{'kind': 'missing_outcome', 'detail': 'unknown'}],
        })

    def test_build_review_bundle_counts_gaps_and_limits(self):
        bundle = review.build_review_bundle({
            'run_id': 'r1',
            'content_comparison': {'creative_matrix': [{'id': 1}], 'descriptive_observations': [{'id': 2}]},
            'group_comparison': {'group_matrix': [{'id': 3}], 'exclusions': []},
            'gaps': [{'kind': 'g'}],
        }, hypotheses={'hypotheses': [{'post': 1}]})
        self.assertEqual(bundle['summary']['eligible_content_items'], 1)
        self.assertEqual(bundle['summary']['descriptive_content_items'], 1)
        self.assertEqual(bundle['summary']['eligible_group_items'], 1)
        self.assertEqual(bundle['summary']['open_gap_count'], 1)
        self.assertEqual(bundle['hypotheses_reference']['hypotheses'][0]['post'], 1)
        self.assertTrue(bundle['pending_agent_review'])

    def test_prepare_review_requires_comparison(self):
        (self.run_dir / 'comparison.json').unlink()
        with self.assertRaises(ValueError):
            review.prepare_review(self.root, self.run_id)

    def test_prepare_review_writes_bundle_and_links_manifest(self):
        result = review.prepare_review(self.root, self.run_id)
        self.assertEqual(result['status'], 'review_prepared')
        self.assertTrue((self.run_dir / 'review-bundle.json').exists())
        manifest = json.loads((self.run_dir / 'manifest.json').read_text())
        self.assertEqual(manifest['review_bundle'],
                         f'loop/runs/{self.run_id}/review-bundle.json')

    def test_record_review_writes_proposal_and_marks_checkpoints(self):
        state = {
            'schema_version': 2, 'publications': [self.entry],
            'placements': [{
                'id': 'pl-orig-1', 'publication_id': self.entry['id'],
                'checkpoints': {'24h': {'status': 'collected', 'review_status': 'pending'}},
            }],
        }
        storage.save(self.state_path, state)
        record = review.record_run_review(self.root, self.run_id, {
            'observation': 'One snapshot',
            'limitation': 'No inquiry data',
            'evidence_ids': ['pl-orig-1'],
            'suggestions': [{'id': 'sug-1', 'target': 'opening', 'change': 'hook'}],
        })
        self.assertEqual(record['status'], 'proposed')
        self.assertTrue((self.run_dir / 'review.md').exists())
        self.assertIn('sug-1', (self.run_dir / 'review.md').read_text())
        manifest = json.loads((self.run_dir / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'review_proposed')
        self.assertEqual(manifest['review_status'], 'proposed')
        updated = json.loads(self.state_path.read_text())
        self.assertEqual(updated['placements'][0]['checkpoints']['24h']['review_status'], 'reviewed')

    def test_record_review_requires_observation_and_limitation(self):
        with self.assertRaises(ValueError):
            review.record_run_review(self.root, self.run_id, {'observation': 'only'})

    def test_legacy_review_requires_collected_snapshot(self):
        with self.assertRaises(ValueError):
            review.review(self.entry, {'observation': 'o', 'limitation': 'l', 'next_test': 'n'})
        self.entry['metrics_status'] = 'collected'
        review.review(self.entry, {'observation': 'o', 'limitation': 'l', 'next_test': 'n'})
        self.assertEqual(self.entry['review_status'], 'reviewed')
