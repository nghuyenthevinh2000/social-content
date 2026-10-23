"""Campaign policy failures stop before browser connection / submission."""

import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from tools.facebook_agent.cli import main
from tools.facebook_agent.models import AgentError
from tools.facebook_agent.posting import publish
from tools.loop import preflight
from tools.loop.tests.test_preflight import ContentFixture


class CampaignPublishTest(ContentFixture, unittest.TestCase):
    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(list(args))
        return code, json.loads(output.getvalue())

    def arguments(self):
        return ['post', '--project', str(self.root), '--post', '2', '--page-id', '123',
                '--text', self.text, '--image', str(self.directory / 'visual.png')]

    def test_missing_approval_never_opens_browser(self):
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, data = self.invoke(*self.arguments())
        self.assertEqual(code, 2)
        self.assertEqual(data['error']['code'], 'content_policy')
        browser.assert_not_called()

    def test_text_file_uses_the_same_approval_guard(self):
        args = self.arguments()
        index = args.index('--text')
        args[index:index + 2] = ['--text-file', str(self.directory / 'facebook-ad.md')]
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, _ = self.invoke(*args)
        self.assertEqual(code, 2)
        browser.assert_not_called()
        self.approve()
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
            code, _ = self.invoke(*args)
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.args[1], self.text)

    def test_changed_approved_assets_never_open_browser(self):
        self.approve()
        self.write('posts/2/facebook-ad.md', self.text + 'Changed')
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, _ = self.invoke(*self.arguments())
        self.assertEqual(code, 2)
        browser.assert_not_called()

    def test_wrong_page_id_never_opens_browser(self):
        self.approve()
        args = self.arguments()
        args[args.index('--page-id') + 1] = '456'
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, _ = self.invoke(*args)
        self.assertEqual(code, 2)
        browser.assert_not_called()

    def test_valid_approval_forwards_scope_and_expected_page(self):
        self.approve()
        args = self.arguments()
        del args[args.index('--page-id'):args.index('--page-id') + 2]
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
            code, _ = self.invoke(*args)
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.kwargs['page_id'], '123')
        self.assertEqual(post.call_args.kwargs['project'], self.root)
        self.assertEqual(post.call_args.kwargs['post'], 2)

    def test_unscoped_managed_page_never_opens_browser(self):
        with patch.object(preflight, 'managed_projects', return_value=[self.root]), patch(
                'tools.facebook_agent.cli.Browser') as browser:
            code, _ = self.invoke('post', '--text', 'Unscoped', '--page-id', '123')
        self.assertEqual(code, 2)
        browser.assert_not_called()

    def test_direct_python_call_cannot_bypass_guard(self):
        page = MagicMock()
        with self.assertRaises(AgentError) as error:
            publish(page, self.text, image=self.directory / 'visual.png', project=self.root, post=2, page_id='123')
        self.assertEqual(error.exception.code, 'content_policy')
        page.goto.assert_not_called()

    def test_name_only_managed_page_stops_before_composer(self):
        page = MagicMock()
        with patch.object(preflight, 'managed_projects', side_effect=lambda page_id: [self.root] if page_id == '123' else []), patch(
                'tools.facebook_agent.posting.inspect_profile', return_value={
                    'name': 'Fixture page', 'type': 'page', 'url': 'https://www.facebook.com/profile.php?id=123'}):
            with self.assertRaises(AgentError) as error:
                publish(page, 'Unscoped', page_name='Fixture page')
        self.assertEqual(error.exception.code, 'content_policy')
        page.get_by_role.assert_not_called()
