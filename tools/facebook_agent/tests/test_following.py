import contextlib
import io
import json
import unittest
from unittest.mock import patch

from tools.facebook_agent.cli import main
from tools.facebook_agent.following import validate_profile_url
from tools.facebook_agent.models import AgentError


class FollowingTests(unittest.TestCase):
    def test_direct_profile_url_validation(self):
        self.assertEqual(validate_profile_url('https://www.facebook.com/nam.anh.marketing.finance/'),
                         'https://www.facebook.com/nam.anh.marketing.finance')
        for url in ['https://example.com/nam', 'http://www.facebook.com/nam',
                    'https://www.facebook.com/me', 'https://www.facebook.com/groups/123']:
            with self.subTest(url=url), self.assertRaises(AgentError):
                validate_profile_url(url)

    def test_unapproved_follow_never_connects(self):
        output = io.StringIO()
        with patch('tools.facebook_agent.following.Browser') as browser, contextlib.redirect_stdout(output):
            code = main(['follow', '--page-id', '123', '--creator', 'Creator',
                         '--reel', 'https://www.facebook.com/reel/456', '--output', 'must-not-exist.json'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'invalid_arguments')
        browser.assert_not_called()

    def test_uncertain_click_returns_no_retry_exit_code(self):
        output = io.StringIO()
        with patch('tools.facebook_agent.following.follow_creator', return_value={'status': 'uncertain'}), contextlib.redirect_stdout(output):
            code = main(['follow', '--page-id', '123', '--creator', 'Creator',
                         '--reel', 'https://www.facebook.com/reel/456', '--output', 'audit.json', '--approved'])
        self.assertEqual(code, 4)


if __name__ == '__main__':
    unittest.main()
