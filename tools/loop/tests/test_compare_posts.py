"""Tests for stage 6a content comparison."""

import unittest

from tools.loop import compare_posts, eligibility, normalize


class ComparePostsTest(unittest.TestCase):
    placements = [
        {'id': 'pl-orig-1', 'publication_id': 'pub-1', 'kind': 'original_page',
         'page_id': '123', 'visibility': 'visible'},
    ]

    def _selected(self, metrics):
        normalized = normalize.normalize_observations({'run_id': 'run'}, {
            'insights_captures': [{
                'placement_id': 'pl-orig-1', 'publication_id': 'pub-1',
                'checkpoint': '24h', 'actual_age_hours': 24.5,
                'records': [{'stage': 'initial', 'post_metrics': metrics}],
            }]
        })
        return eligibility.select_comparable(normalized['observations'], self.placements)

    def test_unknown_inquiries_remain_null_not_zero(self):
        selected = self._selected({'views': 100, 'viewers': 80})
        result = compare_posts.compare_content(selected, actions=[])
        self.assertEqual(len(result['creative_matrix']), 1)
        self.assertIsNone(result['creative_matrix'][0]['qualified_inquiries'])
        self.assertFalse(result['creative_matrix'][0]['action_coverage'])
        self.assertTrue(any(f['type'] == 'missing_outcome' for f in result['flags']))

    def test_average_percentage_watched_has_guardrail(self):
        selected = self._selected({'views': 100, 'viewers': 80,
                                   'average_percentage_watched': 100.0})
        result = compare_posts.compare_content(selected)
        self.assertTrue(any('Average percentage watched is not completion rate' in f['message']
                            for f in result['flags']))

    def test_known_actions_rank_counts(self):
        selected = self._selected({'views': 100, 'viewers': 80})
        result = compare_posts.compare_content(selected, actions=[
            {'publication_id': 'pub-1', 'status': 'qualified'},
            {'publication_id': 'pub-1', 'status': 'inquiry'},
        ])
        self.assertEqual(result['creative_matrix'][0]['qualified_inquiries'], 1)
        self.assertTrue(result['creative_matrix'][0]['action_coverage'])
