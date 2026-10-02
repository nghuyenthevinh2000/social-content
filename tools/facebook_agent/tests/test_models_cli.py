"""Validation and CLI contracts; no live browser or Facebook calls."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.facebook_agent.models import AgentError, validate_content
from tools.facebook_agent.cli import main


class ContentTests(unittest.TestCase):
    def test_preserves_text(self):
        text, image = validate_content('  Hello 👋\nWorld  ', None)
        self.assertEqual(text, '  Hello 👋\nWorld  ')
        self.assertIsNone(image)

    def test_rejects_empty_or_oversized_text(self):
        for text in ('', ' \n ', 'a' * 63207, 'hello\x00world'):
            with self.subTest(text=text[:20]), self.assertRaises(AgentError):
                validate_content(text, None)

    def test_checks_image_bytes_not_only_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'photo.png'
            path.write_bytes(b'not an image')
            with self.assertRaises(AgentError):
                validate_content('hello', str(path))
            path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 20)
            self.assertEqual(validate_content('hello', str(path))[1], path.resolve())

    def test_missing_image(self):
        with self.assertRaises(AgentError):
            validate_content('hello', '/missing/photo.jpg')


class CliTests(unittest.TestCase):
    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def test_no_supervisor_command(self):
        code, result = self.invoke(['supervise'])
        self.assertEqual(code, 2)
        self.assertFalse(result['ok'])

    def test_invalid_content_does_not_connect(self):
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, result = self.invoke(['post', '--text', ' '])
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_content')
        browser.assert_not_called()

    def test_invalid_timeout(self):
        code, result = self.invoke(['--timeout-ms', '0', 'doctor'])
        self.assertEqual(code, 2)
        self.assertFalse(result['ok'])

    def test_browser_error_is_json(self):
        with patch('tools.facebook_agent.cli.Browser', side_effect=AgentError(
                'browser_connection_failed', 'No CDP', human_action_required=True)):
            code, result = self.invoke(['doctor'])
        self.assertEqual(code, 3)
        self.assertTrue(result['error']['human_action_required'])

    def test_uncertain_is_nonzero(self):
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'uncertain'}):
            code, result = self.invoke(['post', '--text', 'hello'])
        self.assertEqual(code, 4)
        self.assertFalse(result['ok'])
        self.assertEqual(result['data']['status'], 'uncertain')
