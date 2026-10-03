"""Unit tests for tools.social_agent.cli."""

import io
import json
import sys
import unittest
from unittest.mock import patch

from tools.social_agent.cli import main
from tools.social_agent.config import AgentError


class CliTests(unittest.TestCase):
    def test_doctor_success_json(self):
        mock_data = {
            'connected': True,
            'endpoint': 'http://127.0.0.1:9222',
            'browser_version': 'Chrome/133.0.0.0',
            'context_count': 1,
        }
        stdout = io.StringIO()
        with patch('tools.social_agent.cli.run_doctor', return_value=mock_data), \
             patch('sys.stdout', stdout):
            code = main(['doctor'])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output['ok'])
        self.assertEqual(output['data'], mock_data)

    def test_doctor_failure_json(self):
        stdout = io.StringIO()
        with patch('tools.social_agent.cli.run_doctor', side_effect=AgentError('browser_connection_failed', 'Cannot reach Chrome', human_action_required=True)), \
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
        with patch('tools.social_agent.cli.start_browser', return_value=mock_data), \
             patch('sys.stdout', stdout):
            code = main(['start-browser', '--port', '9222', '--data-dir', '/tmp/test-profile'])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output['ok'])
        self.assertEqual(output['data'], mock_data)

    def test_start_browser_failure_json(self):
        stdout = io.StringIO()
        with patch('tools.social_agent.cli.start_browser', side_effect=AgentError('browser_readiness_timeout', 'Timed out waiting for CDP', human_action_required=True)), \
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
        with patch('tools.social_agent.cli.run_doctor', side_effect=RuntimeError('Unexpected crash')), \
             patch('sys.stdout', stdout):
            code = main(['doctor'])

        self.assertEqual(code, 1)
        output = json.loads(stdout.getvalue())
        self.assertFalse(output['ok'])
        self.assertEqual(output['error']['code'], 'internal_error')
        self.assertIn('Unexpected crash', output['error']['message'])


if __name__ == '__main__':
    unittest.main()
