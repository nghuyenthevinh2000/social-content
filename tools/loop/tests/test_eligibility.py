"""Tests for stage 5 eligibility."""

import unittest

from tools.loop import eligibility, normalize


class EligibilityTest(unittest.TestCase):
    def setUp(self):
        self.manifest = {'run_id': 'run-20261020-test'}
        self.placements = [
            {'id': 'pl-orig-1', 'publication_id': 'pub-1', 'kind': 'original_page',
             'page_id': '123', 'visibility': 'visible'},
            {'id': 'pl-group-pending', 'publication_id': 'pub-1', 'kind': 'group_copy',
             'group_id': 'grp-1', 'visibility': 'pending'},
            {'id': 'pl-group-visible-1', 'publication_id': 'pub-1', 'kind': 'group_copy',
             'group_id': 'grp-2', 'visibility': 'visible'},
            {'id': 'pl-group-visible-2', 'publication_id': 'pub-1', 'kind': 'group_copy',
             'group_id': 'grp-3', 'visibility': 'visible'},
        ]

    def test_pending_groups_are_excluded_and_generate_gaps(self):
        raw_inputs = {
            'content_library_rows': [{
                'id': 'row-1', 'placement_id': 'pl-group-pending',
                'publication_id': 'pub-1', 'group_id': 'grp-1',
                'views': 50, 'viewers': 40, 'age_hours': 24.5,
            }]
        }
        normalized = normalize.normalize_observations(self.manifest, raw_inputs)
        selected = eligibility.select_comparable(normalized['observations'], self.placements)
        self.assertEqual(len(selected['eligible']), 0)
        self.assertEqual(len(selected['descriptive']), 1)
        self.assertEqual(selected['descriptive'][0]['exclusion_reason'], 'placement_pending')
        self.assertTrue(any(g['kind'] == 'pending_approval' for g in selected['gaps']))

    def test_mismatched_ages_stay_descriptive(self):
        raw_inputs = {
            'insights_captures': [{
                'placement_id': 'pl-orig-1', 'publication_id': 'pub-1',
                'checkpoint': '24h', 'actual_age_hours': 28.5,
                'records': [{'stage': 'initial',
                             'post_metrics': {'views': 100, 'viewers': 80,
                                              'average_percentage_watched': 45.0}}],
            }]
        }
        normalized = normalize.normalize_observations(self.manifest, raw_inputs)
        selected = eligibility.select_comparable(normalized['observations'], self.placements)
        self.assertEqual(len(selected['eligible']), 0)
        self.assertEqual(selected['descriptive'][0]['exclusion_reason'], 'mismatched_age')

    def test_unknown_age_stays_descriptive(self):
        obs = [{'id': 'o1', 'placement_id': 'pl-orig-1', 'checkpoint': '24h',
                'actual_age_hours': None, 'metrics': {'views': 1}}]
        selected = eligibility.select_comparable(obs, self.placements)
        self.assertEqual(selected['descriptive'][0]['exclusion_reason'], 'unknown_age')
        self.assertEqual(selected['eligible'], [])

    def test_unmatched_placement_is_descriptive_not_dropped(self):
        obs = [{'id': 'o1', 'placement_id': 'missing', 'checkpoint': '24h',
                'actual_age_hours': 24.0, 'metrics': {'views': 1}}]
        selected = eligibility.select_comparable(obs, self.placements)
        self.assertEqual(selected['descriptive'][0]['exclusion_reason'], 'unmatched_placement')
