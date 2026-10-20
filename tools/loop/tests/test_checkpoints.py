"""Tests for stage 2 checkpoints."""

from datetime import timedelta

from support import LoopTestCase
from tools.loop import checkpoints, register


class CheckpointsTest(LoopTestCase):
    def test_24_hour_boundary(self):
        self.assertFalse(checkpoints.due(self.entry, self.at - timedelta(microseconds=1)))
        self.assertTrue(checkpoints.due(self.entry, self.at))
        self.assertEqual(self.collect(at=self.at - timedelta(seconds=1)), [])
        self.assertEqual(self.calls, [])

    def test_due_checkpoints_deduplication(self):
        pub = register.register(self.state, 1, 'https://www.facebook.com/reel/111',
                                '2026-01-01T00:00:00Z')
        pub_id = pub['id']
        state = {
            'schema_version': 2,
            'publications': [pub],
            'placements': [
                {
                    'id': 'pl-orig-1',
                    'publication_id': pub_id,
                    'kind': 'original_page',
                    'checkpoints': {
                        '24h': {'due_at': '2026-01-02T00:00:00Z', 'status': 'pending'},
                        '7d': {'due_at': '2026-01-08T00:00:00Z', 'status': 'pending'},
                    }
                }
            ]
        }
        due_at = self.at
        due = checkpoints.due_checkpoints(state, at=due_at)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]['placement_id'], 'pl-orig-1')
        self.assertEqual(due[0]['checkpoint'], '24h')

        pub2 = register.register(self.state, 2, 'https://www.facebook.com/reel/222',
                                 '2026-01-01T00:00:00Z')
        state['publications'].append(pub2)
        due_both = checkpoints.due_checkpoints(state, at=due_at)
        self.assertEqual(len(due_both), 2)
        kinds = {d['kind'] for d in due_both}
        self.assertIn('placement_checkpoint', kinds)
        self.assertIn('publication', kinds)

    def test_planned_post_is_not_published(self):
        planned = {'id': 'p1', 'post': 1, 'url': None, 'published_at': None,
                   'due_at': None, 'metrics_status': 'missing_publication_details'}
        self.assertEqual(checkpoints.due_checkpoints({'publications': [planned],
                                                      'placements': []}, at=self.at), [])
