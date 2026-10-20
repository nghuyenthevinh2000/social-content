"""Tests for stage 6b group distribution comparison."""

import unittest

from tools.loop import compare_groups, eligibility


class CompareGroupsTest(unittest.TestCase):
    placements = [
        {'id': 'pl-group-visible-1', 'publication_id': 'pub-1', 'kind': 'group_copy',
         'group_id': 'grp-2', 'visibility': 'visible'},
        {'id': 'pl-group-visible-2', 'publication_id': 'pub-1', 'kind': 'group_copy',
         'group_id': 'grp-3', 'visibility': 'visible'},
    ]

    def test_group_matrix_ranking_and_no_reach_pooling(self):
        obs = [
            {'id': 'obs-1', 'placement_id': 'pl-group-visible-1', 'publication_id': 'pub-1',
             'checkpoint': '24h', 'actual_age_hours': 24.2, 'source': 'content_library',
             'metrics': {'views': 20, 'viewers': 15}},
            {'id': 'obs-2', 'placement_id': 'pl-group-visible-2', 'publication_id': 'pub-1',
             'checkpoint': '24h', 'actual_age_hours': 24.5, 'source': 'content_library',
             'metrics': {'views': 50, 'viewers': 35}},
        ]
        selected = eligibility.select_comparable(obs, self.placements)
        res = compare_groups.compare_groups(selected)
        matrix = res['group_matrix']
        self.assertEqual(len(matrix), 2)
        self.assertEqual(matrix[0]['placement_id'], 'pl-group-visible-2')
        self.assertEqual(matrix[0]['rank'], 1)
        self.assertEqual(matrix[1]['placement_id'], 'pl-group-visible-1')
        self.assertEqual(matrix[1]['rank'], 2)
        self.assertEqual(matrix[0]['rank_basis'], 'distribution_only')
        self.assertTrue(any('must never be pooled' in flag['message']
                            for flag in res['diagnostic_flags']))

    def test_inquiry_ranking_is_separate(self):
        obs = [
            {'id': 'obs-1', 'placement_id': 'pl-group-visible-1', 'publication_id': 'pub-1',
             'checkpoint': '24h', 'actual_age_hours': 24.2, 'source': 'content_library',
             'metrics': {'views': 20, 'viewers': 15}},
            {'id': 'obs-2', 'placement_id': 'pl-group-visible-2', 'publication_id': 'pub-1',
             'checkpoint': '24h', 'actual_age_hours': 24.5, 'source': 'content_library',
             'metrics': {'views': 50, 'viewers': 35}},
        ]
        selected = eligibility.select_comparable(obs, self.placements)
        res = compare_groups.compare_groups(selected, actions=[
            {'placement_id': 'pl-group-visible-1', 'status': 'qualified'},
        ])
        self.assertEqual(res['group_matrix'][0]['placement_id'], 'pl-group-visible-1')
        self.assertEqual(res['group_matrix'][0]['rank_basis'], 'qualified_inquiries')
        self.assertIsNone(res['group_matrix'][1]['qualified_inquiries'])
