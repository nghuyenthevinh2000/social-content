"""Tests for stage 1 registration."""

from support import LoopTestCase
from tools.loop import register


class RegisterTest(LoopTestCase):
    def test_registration_idempotent_and_resolves_missing_details(self):
        again = register.register(self.state, 3, self.entry['url'] + '/', self.entry['published_at'])
        self.assertIs(again, self.entry)
        self.assertEqual(len(self.state['publications']), 1)
        self.state['publications'].append({'post': 1, 'url': None,
                                          'metrics_status': 'missing_publication_details'})
        register.register(self.state, 1, 'https://www.facebook.com/posts/456', '2026-01-01T00:00:00Z')
        self.assertEqual(len(self.state['publications']), 2)
        for url, time in [('https://evil.example/post', '2026-01-01T00:00:00Z'),
                          (self.entry['url'], '2026-01-01T00:00:00')]:
            with self.assertRaises(ValueError):
                register.register(self.state, 3, url, time)

    def test_resolve_timestamp_on_known_url_preserves_identity(self):
        from tools.loop import checkpoints
        self.entry['published_at'] = None
        self.entry['metrics_status'] = 'missing_publication_details'
        identity = self.entry['id']
        result = register.register(self.state, 3, self.entry['url'], '2026-01-01T00:00:00Z')
        self.assertEqual(result['id'], identity)
        self.assertTrue(checkpoints.due(result, self.at))

    def test_register_with_none_published_at_does_not_crash(self):
        entry = register.register(self.state, 4, 'https://www.facebook.com/reel/987654', None)
        self.assertIsNone(entry['published_at'])
        self.assertIsNone(entry['due_at'])
        self.assertEqual(entry['metrics_status'], 'missing_publication_details')
        resolved = register.register(self.state, 4, 'https://www.facebook.com/reel/987654',
                                     '2026-01-01T00:00:00Z')
        self.assertEqual(resolved['published_at'], '2026-01-01T00:00:00+00:00')
        self.assertEqual(resolved['metrics_status'], 'pending')

    def test_future_timestamp_is_not_confirmed_publication(self):
        with self.assertRaises(ValueError):
            register.register(self.state, 5, 'https://www.facebook.com/reel/555',
                              '2999-01-01T00:00:00Z')
