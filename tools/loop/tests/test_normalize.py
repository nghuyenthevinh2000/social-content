"""Tests for stage 4 normalization."""

from support import LoopTestCase
from tools.loop import normalize


class NormalizeTest(LoopTestCase):
    def test_page_post_id_maps_library_row_to_placement(self):
        normalized = normalize.normalize_observations(
            {'run_id': 'run-x', 'gaps': []},
            {
                'content_library_rows': [
                    {'id': 'row-known', 'post_id': '111', 'kind': 'original_page', 'views': 10},
                    {'id': 'row-group', 'post_id': None, 'kind': 'group_copy',
                     'group_name': 'Group A', 'views': 5},
                ],
                'csv_posts': [{'post_id': '111', 'export_period_totals': {'reactions': 3}},
                              {'post_id': '999', 'export_period_totals': {'reactions': 0}}],
                'csv_evidence_hash': 'hash',
            },
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

    def test_unresolved_group_identity_generates_unique_obs_id_and_gap(self):
        raw_inputs = {
            'content_library_rows': [
                {'id': 'row-abc', 'post_id': None, 'kind': 'group_copy',
                 'unresolved_group_identity': True, 'group_name': 'Hội In Thiệp',
                 'raw_text': 'Line 1\nLine 2', 'views': 23, 'viewers': 19},
                {'id': 'row-def', 'post_id': None, 'kind': 'group_copy',
                 'unresolved_group_identity': True, 'group_name': 'Hội In Ấn',
                 'raw_text': 'Line 3\nLine 4', 'views': 6, 'viewers': 6},
            ]
        }
        normalized = normalize.normalize_observations({'run_id': 'run'}, raw_inputs)
        obs = normalized['observations']
        self.assertEqual(len(obs), 2)
        self.assertNotEqual(obs[0]['id'], obs[1]['id'])
        self.assertNotIn('None', obs[0]['id'])
        gaps = normalized['gaps']
        self.assertTrue(any(g['kind'] == 'unresolved_group_identity'
                            and g['group_name'] == 'Hội In Thiệp' for g in gaps))
        self.assertTrue(any(g['kind'] == 'unresolved_group_identity'
                            and g['group_name'] == 'Hội In Ấn' for g in gaps))

    def test_null_metrics_stay_null(self):
        normalized = normalize.normalize_observations({'run_id': 'run'}, {
            'insights_captures': [{
                'placement_id': 'pl-1', 'publication_id': 'pub-1', 'checkpoint': '24h',
                'actual_age_hours': 24.5,
                'records': [{'stage': 'initial', 'post_metrics': {'views': 100, 'comments': None}}],
            }]
        })
        metrics = normalized['observations'][0]['metrics']
        self.assertEqual(metrics['views'], 100)
        self.assertIsNone(metrics['comments'])
        self.assertIsNone(metrics['qualified_inquiries'])
