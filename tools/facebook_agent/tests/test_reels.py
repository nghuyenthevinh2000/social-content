import unittest

from tools.facebook_agent.cli import build_parser
from tools.facebook_agent.reels import reel_url


class ReelsTests(unittest.TestCase):
    def test_canonical_url(self):
        self.assertEqual(reel_url('https://www.facebook.com/reel/123/?s=1'),
                         'https://www.facebook.com/reel/123')
        self.assertIsNone(reel_url('https://example.com/reel/123'))
        self.assertIsNone(reel_url('https://www.facebook.com/reel/'))

    def test_read_only_command(self):
        args = build_parser().parse_args(['reels', '--page-id', '123', '--output', 'reels.json'])
        self.assertEqual(args.command, 'reels')
        self.assertEqual(args.limit, 15)


if __name__ == '__main__':
    unittest.main()
