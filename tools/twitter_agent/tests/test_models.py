"""Input and exact-content approval contracts."""

import hashlib
import unittest

from tools.twitter_agent.models import AgentError, Limits, draft_digest, normalize_target


class ModelTests(unittest.TestCase):
    def test_supported_ids_and_urls_are_canonical(self):
        for value in ('123', '00123', 'https://x.com/alice/status/123?x=1#reply',
                      'http://www.twitter.com/i/status/123',
                      'https://twitter.com/A_1/status/123',
                      'https://www.x.com:443/i/status/123',
                      'http://x.com:80/i/status/123'):
            with self.subTest(value=value):
                target = normalize_target(value)
                self.assertEqual(target.id, '123')
                self.assertEqual(target.url, 'https://x.com/i/status/123')

    def test_rejects_url_tricks_and_nonpositive_ids(self):
        for value in ('', '0', '-1', '+1', '１２３', '1.2', ' 123 ',
                      'https://x.com.evil.test/a/status/123',
                      'https://evil.test/x.com/a/status/123',
                      'https://x.com@evil.test/a/status/123',
                      'https://evil.test@x.com/a/status/123',
                      'https://x.com:444/a/status/123',
                      'https://x.com:bad/a/status/123',
                      'https://x.com./a/status/123',
                      'ftp://x.com/a/status/123', '//x.com/a/status/123',
                      '"https://x.com/a/status/123"',
                      'https://x.com/a/status/123/quote',
                      'https://x.com/a/status/0',
                      'https://x.com/a/status/%31',
                      'https://x.com/a/status/1\n23',
                      'https://x.com/a/status/123?url="https://evil.test"'):
            with self.subTest(value=value):
                with self.assertRaises(AgentError) as caught:
                    normalize_target(value)
                self.assertEqual(caught.exception.code, 'invalid_target')

    def test_digest_binds_exact_unicode_text_and_target(self):
        self.assertEqual(draft_digest('123', 'é\n🙂'), hashlib.sha256(
            '["123","é\\n🙂"]'.encode('utf-8')).hexdigest())
        base = draft_digest('123', 'é')
        for target, text in [('124', 'é'), ('123', 'e\u0301'), ('123', ' é'),
                             ('123', 'é\n')]:
            self.assertNotEqual(base, draft_digest(target, text))

    def test_limits_reject_invalid_values(self):
        for kwargs in ({'hourly': 0}, {'daily': -1}, {'hourly': True},
                       {'daily': 1.5}, {'spacing': -1}, {'spacing': float('nan')},
                       {'spacing': float('inf')}, {'spacing': '60'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AgentError):
                Limits(**kwargs)

    def test_limits_defaults_and_burst_validation(self):
        limits = Limits()
        self.assertEqual(limits.hourly, 6)
        self.assertEqual(limits.daily, 20)
        self.assertEqual(limits.spacing, 120.0)
        self.assertEqual(limits.burst_max, 3)

        with self.assertRaises(AgentError) as ctx:
            Limits(burst_max=0)
        self.assertEqual(ctx.exception.code, 'invalid_limits')


if __name__ == '__main__':
    unittest.main()

