"""Unit tests for tools.common.cli."""

import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.common.cli import main
from tools.common.config import AgentError
from tools.common.post import PostError


class CliTests(unittest.TestCase):
    def test_doctor_success_json(self):
        mock_data = {
            'connected': True,
            'endpoint': 'http://127.0.0.1:9222',
            'browser_version': 'Chrome/133.0.0.0',
            'context_count': 1,
        }
        stdout = io.StringIO()
        with patch('tools.common.cli.run_doctor', return_value=mock_data), \
             patch('sys.stdout', stdout):
            code = main(['doctor'])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output['ok'])
        self.assertEqual(output['data'], mock_data)

    def test_doctor_failure_json(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.run_doctor', side_effect=AgentError('browser_connection_failed', 'Cannot reach Chrome', human_action_required=True)), \
             patch('sys.stdout', stdout):
            code = main(['doctor'])

        self.assertEqual(code, 3)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'browser_connection_failed')
        self.assertTrue(output['error']['human_action_required'])

    def test_start_browser_success_json(self):
        mock_data = {
            'action': 'reused',
            'endpoint': 'http://127.0.0.1:9222',
            'port': 9222,
            'user_data_dir': '/tmp/test-profile',
        }
        stdout = io.StringIO()
        with patch('tools.common.cli.start_browser', return_value=mock_data), \
             patch('tools.common.cli.record_profile') as mock_record, \
             patch('sys.stdout', stdout):
            code = main(['start-browser', '--port', '9222', '--data-dir', '/tmp/test-profile'])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output['ok'])
        self.assertEqual(output['data'], mock_data)
        mock_record.assert_called_once_with(data_dir='/tmp/test-profile', port=9222, backend=None)

    def test_start_browser_failure_json(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.start_browser', side_effect=AgentError('browser_readiness_timeout', 'Timed out waiting for CDP', human_action_required=True)), \
             patch('sys.stdout', stdout):
            code = main(['start-browser'])

        self.assertEqual(code, 3)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'browser_readiness_timeout')

    def test_invalid_arguments_json(self):
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            code = main(['start-browser', '--port', 'not-a-number'])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'invalid_arguments')

    def test_missing_command_json(self):
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            code = main([])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'invalid_arguments')

    def test_start_browser_help_contains_profile_and_port(self):
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            code = main(['start-browser', '--help'])

        self.assertEqual(code, 0)
        help_text = stdout.getvalue()
        self.assertIn('chrome-twitter-profile', help_text)
        self.assertIn('9222', help_text)

    def test_internal_error_json(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.run_doctor', side_effect=RuntimeError('Unexpected crash')), \
             patch('sys.stdout', stdout):
            code = main(['doctor'])

        self.assertEqual(code, 1)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'internal_error')
    def test_cli_doctor_invisible_flags(self):
        stdout = io.StringIO()
        mock_data = {'connected': True, 'backend': 'invisible', 'seed': 42}
        with patch('tools.common.cli.run_doctor', return_value=mock_data) as mock_doc, \
             patch('sys.stdout', stdout):
            code = main(['doctor', '--backend', 'invisible', '--seed', '42', '--binary', '/bin/engine', '--headless'])

        self.assertEqual(code, 0)
        mock_doc.assert_called_once_with(
            endpoint=None,
            timeout_ms=None,
            backend='invisible',
            data_dir=None,
            seed=42,
            headless=True,
            binary_path='/bin/engine',
        )

    def test_cli_start_browser_invisible_flags(self):
        stdout = io.StringIO()
        mock_data = {'action': 'ready', 'backend': 'invisible'}
        with patch('tools.common.cli.start_browser', return_value=mock_data) as mock_sb, \
             patch('tools.common.cli.record_profile'), \
             patch('sys.stdout', stdout):
            code = main(['start-browser', '--backend', 'invisible', '--seed', '42', '--binary', '/bin/engine', '--headless'])

        self.assertEqual(code, 0)
        mock_sb.assert_called_once_with(
            port=None,
            data_dir=None,
            timeout=None,
            chrome_bin=None,
            backend='invisible',
            seed=42,
            headless=True,
            binary_path='/bin/engine',
            auto_port=False,
        )

    def test_cli_start_browser_auto_port_flag(self):
        stdout = io.StringIO()
        mock_data = {'action': 'started', 'backend': 'cdp', 'port': 54123}
        with patch('tools.common.cli.start_browser', return_value=mock_data) as mock_sb, \
             patch('tools.common.cli.record_profile') as mock_record, \
             patch('sys.stdout', stdout):
            code = main(['start-browser', '--port', 'auto', '--data-dir', '/tmp/page-a'])

        self.assertEqual(code, 0)
        self.assertEqual(mock_sb.call_args.kwargs['port'], None)
        self.assertTrue(mock_sb.call_args.kwargs['auto_port'])
        self.assertEqual(mock_sb.call_args.kwargs['data_dir'], '/tmp/page-a')
        mock_record.assert_called_once_with(data_dir='/tmp/page-a', port=54123, backend='cdp')

    def test_cli_profiles_lists_recorded_profiles(self):
        stdout = io.StringIO()
        registry = {'profiles': {'chrome-page-a': {'port': 54123, 'data_dir': '/tmp/page-a'}}}
        with patch('tools.common.cli.load_registry', return_value=registry), \
             patch('sys.stdout', stdout):
            code = main(['profiles', '--base-dir', '/tmp/registry'])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output['ok'])
        self.assertEqual(output['data']['profiles'], registry['profiles'])
        self.assertEqual(output['data']['registry_path'], '/tmp/registry/profiles.json')

    def test_cli_profiles_records_named_profile_dir(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.record_profile') as mock_record, \
             patch('tools.common.cli.load_registry', return_value={'profiles': {}}), \
             patch('sys.stdout', stdout):
            code = main(['profiles', '--data-dir', '/tmp/page-b'])

        self.assertEqual(code, 0)
        mock_record.assert_called_once_with(data_dir='/tmp/page-b', backend=None,
                                            identities={}, base_dir=None)

    def test_cli_profiles_records_backend_choice(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.record_profile') as mock_record, \
             patch('tools.common.cli.load_registry', return_value={'profiles': {}}), \
             patch('sys.stdout', stdout):
            code = main(['profiles', '--data-dir', '/tmp/chrome-block-lc', '--backend', 'cdp'])

        self.assertEqual(code, 0)
        self.assertEqual(mock_record.call_args.kwargs['backend'], 'cdp')

    def test_cli_profiles_rejects_unknown_backend(self):
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            code = main(['profiles', '--data-dir', '/tmp/p', '--backend', 'firefox'])

        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())['error']['code'], 'invalid_arguments')

    def test_cli_profiles_links_platform_identities(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.record_profile') as mock_record, \
             patch('tools.common.cli.load_registry', return_value={'profiles': {}}), \
             patch('sys.stdout', stdout):
            code = main([
                'profiles', '--data-dir', '/tmp/chrome-twitter-profile',
                '--facebook-page-id', '61595289277974',
                '--linkedin-account', 'Vinh Nguyen',
                '--twitter-account', 'TheVinhNguyen4',
            ])

        self.assertEqual(code, 0)
        self.assertEqual(mock_record.call_args.kwargs['identities'], {
            'facebook': {'page_id': '61595289277974'},
            'linkedin': {'account': 'Vinh Nguyen'},
            'twitter': {'account': 'TheVinhNguyen4'},
        })

    def test_cli_profiles_identity_flag_without_data_dir_is_invalid(self):
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            code = main(['profiles', '--facebook-page-id', '61595289277974'])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'invalid_arguments')

    def test_cli_profiles_rejects_non_numeric_facebook_page_id(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as base_dir, patch('sys.stdout', stdout):
            code = main(['profiles', '--data-dir', '/tmp/p', '--base-dir', base_dir,
                         '--facebook-page-id', 'not-a-page'])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output['error']['code'], 'invalid_identity')

    def test_cli_profiles_reports_invalid_registry(self):
        stdout = io.StringIO()
        registry = {'profiles': {'p': {'identities': {'mastodon': {'account': 'x'}}}}}
        with patch('tools.common.cli.load_registry', return_value=registry), \
             patch('sys.stdout', stdout):
            code = main(['profiles'])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output['error']['code'], 'invalid_registry')

    def test_cli_doctor_profile_dir_flag(self):
        stdout = io.StringIO()
        mock_data = {'connected': True}
        with patch('tools.common.cli.run_doctor', return_value=mock_data) as mock_doc, \
             patch('sys.stdout', stdout):
            code = main(['doctor', '--data-dir', '/tmp/page-b'])

        self.assertEqual(code, 0)
        self.assertEqual(mock_doc.call_args.kwargs['data_dir'], '/tmp/page-b')

    def test_post_command_prints_plans(self):
        stdout = io.StringIO()
        mock_data = {'id': 'p1', 'title': 'Launch', 'posting_groups': ['Alpha'], 'plans': []}
        with patch('tools.common.cli.plan_post', return_value=mock_data), \
             patch('sys.stdout', stdout):
            code = main(['post', 'tools/common/samples/post.json', '--platform', 'facebook'])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output['ok'])
        self.assertEqual(output['data'], mock_data)

    def test_post_command_invalid_post_json(self):
        stdout = io.StringIO()
        with patch('tools.common.cli.plan_post', side_effect=PostError('invalid_post', 'bad post')), \
             patch('sys.stdout', stdout):
            code = main(['post', 'bad.json'])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'invalid_post')

    def test_post_command_rejects_unknown_platform(self):
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            code = main(['post', 'tools/common/samples/post.json', '--platform', 'mastodon'])

        self.assertEqual(code, 2)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output['error']['code'], 'invalid_arguments')


if __name__ == '__main__':
    unittest.main()
