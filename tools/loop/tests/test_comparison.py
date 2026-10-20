"""Offline tests for comparison pure functions:

python3 -m unittest discover -s tools/loop/tests
"""

import unittest
from tools.loop import comparison


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.manifest = {'run_id': 'run-20261020-test'}
        self.placements = [
            {
                'id': 'pl-orig-1',
                'publication_id': 'pub-1',
                'kind': 'original_page',
                'page_id': '123',
                'visibility': 'visible',
            },
            {
                'id': 'pl-group-pending',
                'publication_id': 'pub-1',
                'kind': 'group_copy',
                'group_id': 'grp-1',
                'visibility': 'pending',
            },
            {
                'id': 'pl-group-visible-1',
                'publication_id': 'pub-1',
                'kind': 'group_copy',
                'group_id': 'grp-2',
                'visibility': 'visible',
            },
            {
                'id': 'pl-group-visible-2',
                'publication_id': 'pub-1',
                'kind': 'group_copy',
                'group_id': 'grp-3',
                'visibility': 'visible',
            },
        ]

    def test_pending_groups_are_excluded_and_generate_gaps(self):
        raw_inputs = {
            'content_library_rows': [
                {
                    'id': 'row-1',
                    'placement_id': 'pl-group-pending',
                    'publication_id': 'pub-1',
                    'group_id': 'grp-1',
                    'views': 50,
                    'viewers': 40,
                    'age_hours': 24.5,
                }
            ]
        }
        normalized = comparison.normalize_observations(self.manifest, raw_inputs)
        selected = comparison.select_comparable(normalized['observations'], self.placements)

        self.assertEqual(len(selected['eligible']), 0)
        self.assertEqual(len(selected['descriptive']), 1)
        self.assertEqual(selected['descriptive'][0]['exclusion_reason'], 'placement_pending')
        # Proves pending post is NOT ranked as a failure, but creates a gap
        self.assertTrue(any(g['kind'] == 'pending_approval' for g in selected['gaps']))

    def test_unresolved_group_identity_generates_unique_obs_id_and_gap(self):
        raw_inputs = {
            'content_library_rows': [
                {
                    'id': 'row-abc',
                    'post_id': None,
                    'kind': 'group_copy',
                    'unresolved_group_identity': True,
                    'group_name': 'Hội In Thiệp',
                    'raw_text': 'Line 1\nLine 2',
                    'views': 23,
                    'viewers': 19,
                },
                {
                    'id': 'row-def',
                    'post_id': None,
                    'kind': 'group_copy',
                    'unresolved_group_identity': True,
                    'group_name': 'Hội In Ấn',
                    'raw_text': 'Line 3\nLine 4',
                    'views': 6,
                    'viewers': 6,
                }
            ]
        }
        normalized = comparison.normalize_observations(self.manifest, raw_inputs)
        obs = normalized['observations']
        self.assertEqual(len(obs), 2)
        # Unique observation IDs, never obs-lib-None
        self.assertNotEqual(obs[0]['id'], obs[1]['id'])
        self.assertNotIn('None', obs[0]['id'])
        self.assertNotIn('None', obs[1]['id'])
        # Generates explicit unresolved_group_identity gap
        gaps = normalized['gaps']
        self.assertTrue(any(g['kind'] == 'unresolved_group_identity' and g['group_name'] == 'Hội In Thiệp' for g in gaps))
        self.assertTrue(any(g['kind'] == 'unresolved_group_identity' and g['group_name'] == 'Hội In Ấn' for g in gaps))

    def test_mismatched_ages_stay_descriptive(self):
        raw_inputs = {
            'insights_captures': [
                {
                    'placement_id': 'pl-orig-1',
                    'publication_id': 'pub-1',
                    'checkpoint': '24h',
                    'actual_age_hours': 28.5,  # 24h + 4.5h > 2.0h tolerance
                    'records': [{
                        'stage': 'initial',
                        'post_metrics': {'views': 100, 'viewers': 80, 'average_percentage_watched': 45.0}
                    }]
                }
            ]
        }
        normalized = comparison.normalize_observations(self.manifest, raw_inputs)
        selected = comparison.select_comparable(normalized['observations'], self.placements)

        self.assertEqual(len(selected['eligible']), 0)
        self.assertEqual(len(selected['descriptive']), 1)
        self.assertEqual(selected['descriptive'][0]['exclusion_reason'], 'mismatched_age')

    def test_unknown_inquiries_remain_null_not_zero(self):
        raw_inputs = {
            'insights_captures': [
                {
                    'placement_id': 'pl-orig-1',
                    'publication_id': 'pub-1',
                    'checkpoint': '24h',
                    'actual_age_hours': 24.5,
                    'records': [{
                        'stage': 'initial',
                        'post_metrics': {'views': 100, 'viewers': 80}
                    }]
                }
            ]
        }
        normalized = comparison.normalize_observations(self.manifest, raw_inputs)
        selected = comparison.select_comparable(normalized['observations'], self.placements)
        result = comparison.compare_content(selected, actions=[])

        self.assertEqual(len(result['creative_matrix']), 1)
        # Unknown inquiries must stay None, not 0
        self.assertIsNone(result['creative_matrix'][0]['qualified_inquiries'])
        self.assertFalse(result['creative_matrix'][0]['action_coverage'])
        self.assertTrue(any(f['type'] == 'missing_outcome' for f in result['flags']))

    def test_average_percentage_watched_has_guardrail(self):
        raw_inputs = {
            'insights_captures': [
                {
                    'placement_id': 'pl-orig-1',
                    'publication_id': 'pub-1',
                    'checkpoint': '24h',
                    'actual_age_hours': 24.5,
                    'records': [{
                        'stage': 'initial',
                        'post_metrics': {'views': 100, 'viewers': 80, 'average_percentage_watched': 100.0}
                    }]
                }
            ]
        }
        normalized = comparison.normalize_observations(self.manifest, raw_inputs)
        selected = comparison.select_comparable(normalized['observations'], self.placements)
        result = comparison.compare_content(selected)

        self.assertTrue(any('Average percentage watched is not completion rate' in f['message'] for f in result['flags']))

    def test_group_matrix_ranking_and_no_reach_pooling(self):
        raw_inputs = {
            'content_library_rows': [
                {
                    'id': 'row-1',
                    'placement_id': 'pl-group-visible-1',
                    'publication_id': 'pub-1',
                    'group_id': 'grp-2',
                    'views': 20,
                    'viewers': 15,
                    'age_hours': 24.0,
                },
                {
                    'id': 'row-2',
                    'placement_id': 'pl-group-visible-2',
                    'publication_id': 'pub-1',
                    'group_id': 'grp-3',
                    'views': 50,
                    'viewers': 35,
                    'age_hours': 24.0,
                }
            ]
        }
        # In this synthetic test, override policy for observation checkpoint to eligible
        obs = [
            {
                'id': 'obs-1',
                'placement_id': 'pl-group-visible-1',
                'publication_id': 'pub-1',
                'checkpoint': '24h',
                'actual_age_hours': 24.2,
                'source': 'content_library',
                'metrics': {'views': 20, 'viewers': 15},
            },
            {
                'id': 'obs-2',
                'placement_id': 'pl-group-visible-2',
                'publication_id': 'pub-1',
                'checkpoint': '24h',
                'actual_age_hours': 24.5,
                'source': 'content_library',
                'metrics': {'views': 50, 'viewers': 35},
            }
        ]
        selected = comparison.select_comparable(obs, self.placements)
        res = comparison.compare_groups(selected)

        # Higher viewers ranks higher in distribution_only mode
        matrix = res['group_matrix']
        self.assertEqual(len(matrix), 2)
        self.assertEqual(matrix[0]['placement_id'], 'pl-group-visible-2')
        self.assertEqual(matrix[0]['rank'], 1)
        self.assertEqual(matrix[1]['placement_id'], 'pl-group-visible-1')
        self.assertEqual(matrix[1]['rank'], 2)
        self.assertEqual(matrix[0]['rank_basis'], 'distribution_only')

        # Assert no pooling reach flag exists
        self.assertTrue(any('must never be pooled' in flag['message'] for flag in res['diagnostic_flags']))


if __name__ == '__main__':
    unittest.main()
