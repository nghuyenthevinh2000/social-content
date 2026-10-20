"""Offline tests for Content Library parser and row deduplication:

python3 -m unittest discover -s tools/facebook_agent/tests
"""

import unittest
from tools.facebook_agent.content_library import (
    extract_group_id_from_url,
    extract_post_id_from_url,
    parse_row,
    deduplicate_rows
)


class ContentLibraryTest(unittest.TestCase):
    def test_group_id_extraction_never_fabricates_from_name(self):
        self.assertEqual(extract_group_id_from_url('https://www.facebook.com/groups/987654321/'), '987654321')
        self.assertEqual(extract_group_id_from_url('https://www.facebook.com/groups/987654321/posts/111'), '987654321')
        self.assertIsNone(extract_group_id_from_url('https://www.facebook.com/groups/handmade-community/'))
        self.assertIsNone(extract_group_id_from_url(None))

    def test_post_id_extraction(self):
        self.assertEqual(extract_post_id_from_url('https://www.facebook.com/reel/122104901223509642'), '122104901223509642')
        self.assertEqual(extract_post_id_from_url('https://www.facebook.com/posts/122104901223509642'), '122104901223509642')
        self.assertIsNone(extract_post_id_from_url('https://www.facebook.com/profile.php?id=61595289277974'))

    def test_column_reordering_and_pending_status(self):
        # Column headers in custom order: Reactions, Title, Views
        headers = ['Reactions', 'Title', 'Views']
        raw_row = {
            'cells': ['15', 'Test Video Post', '120'],
            'row_text': 'Test Video Post\nPending approval in Group',
            'links': [
                {'text': 'View Reel', 'href': 'https://www.facebook.com/reel/123456789'},
                {'text': 'Target Group', 'href': 'https://www.facebook.com/groups/999888777/'}
            ]
        }
        parsed = parse_row(raw_row, headers, '61595289277974')
        self.assertEqual(parsed['kind'], 'group_copy')
        self.assertEqual(parsed['visibility'], 'pending')
        self.assertEqual(parsed['post_id'], '123456789')
        self.assertEqual(parsed['group_id'], '999888777')
        self.assertEqual(parsed['reactions'], 15)
        self.assertEqual(parsed['views'], 120)

    def test_same_title_never_merges_different_placements(self):
        # Two rows with identical title but one original page and one group copy
        headers = ['Title', 'Views']
        row1 = {
            'cells': ['Same Title', '100'],
            'row_text': 'Same Title',
            'links': [{'text': 'Post', 'href': 'https://www.facebook.com/posts/11111'}]
        }
        row2 = {
            'cells': ['Same Title', '50'],
            'row_text': 'Same Title',
            'links': [
                {'text': 'Post', 'href': 'https://www.facebook.com/posts/22222'},
                {'text': 'Group Name', 'href': 'https://www.facebook.com/groups/88888/'}
            ]
        }
        parsed1 = parse_row(row1, headers, 'page-1')
        parsed2 = parse_row(row2, headers, 'page-1')

        deduped = deduplicate_rows([parsed1, parsed2])
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]['kind'], 'original_page')
        self.assertEqual(deduped[1]['kind'], 'group_copy')
        self.assertEqual(deduped[1]['group_id'], '88888')

    def test_virtualized_duplicates_are_deduplicated(self):
        headers = ['Title', 'Views']
        row = {
            'cells': ['Title 1', '100'],
            'row_text': 'Title 1',
            'links': [{'text': 'Post', 'href': 'https://www.facebook.com/posts/11111'}]
        }
        parsed1 = parse_row(row, headers, 'page-1')
        parsed2 = parse_row(row, headers, 'page-1')

        deduped = deduplicate_rows([parsed1, parsed2])
        self.assertEqual(len(deduped), 1)

    def test_line_based_fallback_parsing_with_bullet_groups_and_metrics(self):
        headers = [
            'Preview', 'Views', 'Viewers', 'Engagement', 'Follows',
            'Impressions', 'Comments', 'Distribution', 'Watch time',
            'Average watch time', '3-second views', '1-minute views'
        ]
        # Real-world Meta Professional Dashboard row without role="gridcell"
        raw_row = {
            'cells': [],
            'links': [],
            'row_text': (
                "Chưa Tết... sao thấy nhớ nhà rồi? Giấy Nhung đỏ 120.\n"
                "HỘI IN THIỆP CƯỚI - Wedding invitation •\n"
                "Yesterday at 11:41\n"
                "23\n"
                "19\n"
                "0\n"
                "0\n"
                "24\n"
                "0\n"
                "-2.7x\n"
                "24s\n"
                "1s\n"
                "2\n"
                "0"
            )
        }
        parsed = parse_row(raw_row, headers, '61595289277974')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['kind'], 'group_copy')
        self.assertEqual(parsed['group_name'], 'HỘI IN THIỆP CƯỚI - Wedding invitation')
        self.assertIsNone(parsed['group_id'])
        self.assertTrue(parsed['unresolved_group_identity'])
        self.assertEqual(parsed['visibility'], 'visible')
        self.assertEqual(parsed['views'], 23)
        self.assertEqual(parsed['viewers'], 19)
        self.assertEqual(parsed['three_second_views'], 2)
        self.assertEqual(parsed['comments'], 0)
        self.assertTrue(parsed['id'].startswith('row-'))

    def test_empty_rows_are_discarded(self):
        headers = ['Preview', 'Views']
        empty_row = {'cells': [], 'links': [], 'row_text': '   \n\xa0\n  '}
        parsed = parse_row(empty_row, headers, 'page-1')
        self.assertIsNone(parsed)
        deduped = deduplicate_rows([parsed])
        self.assertEqual(len(deduped), 0)


if __name__ == '__main__':
    unittest.main()
