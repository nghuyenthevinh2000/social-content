"""Offline module entry-point and mocked CLI dispatch contract tests."""

from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.linkedin_agent.models import AgentError


ROOT = Path(__file__).resolve().parents[3]


class ModuleTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, '-m', 'tools.linkedin_agent', *args],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )

    def assert_error(self, result, code):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, '')
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {'ok', 'error'})
        self.assertFalse(payload['ok'])
        self.assertEqual(set(payload['error']), {'code', 'message', 'human_action_required'})
        self.assertEqual(payload['error']['code'], code)
        self.assertTrue(payload['error']['message'])
        self.assertFalse(payload['error']['human_action_required'])

    def test_module_and_command_help(self):
        for args in (('--help',), ('doctor', '--help'), ('post', '--help')):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertIn('usage:', result.stdout)
                self.assertNotIn('supervise', result.stdout)

    def test_missing_required_arguments_and_unknown_commands_are_json(self):
        for args in ((), ('post',), ('post', '--text', 'Approved'),
                     ('post', '--image', 'missing.png'), ('unknown',), ('supervise',)):
            with self.subTest(args=args):
                self.assert_error(self.run_cli(*args), 'invalid_arguments')

    def test_invalid_timeout_is_json(self):
        for value, code in (('0', 'invalid_timeout'), ('-1', 'invalid_timeout'),
                            ('not-a-number', 'invalid_arguments')):
            with self.subTest(value=value):
                self.assert_error(self.run_cli('--timeout-ms', value, 'doctor'), code)

    def test_blank_and_oversized_text_are_json(self):
        for text in (' \n', 'sensitive-approved-text-' * 150):
            with self.subTest(length=len(text)):
                result = self.run_cli('post', '--text', text, '--image', 'missing.png')
                self.assert_error(result, 'invalid_text')
                self.assertNotIn('sensitive-approved-text', result.stdout)

    def test_missing_and_non_image_files_are_json(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / 'invalid.png'
            invalid.write_bytes(b'sensitive-image-buffer')
            for path in (root / 'missing.png', root, invalid):
                with self.subTest(path=path):
                    result = self.run_cli('post', '--text', 'Approved', '--image', str(path))
                    self.assert_error(result, 'invalid_images')
                    self.assertNotIn('sensitive-image-buffer', result.stdout)

    def test_parser_errors_do_not_echo_sensitive_arguments(self):
        for args in (('private-post-text',), ('post', '--text', 'Approved',
                     '--image', 'missing.png', '--private-image-buffer')):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assert_error(result, 'invalid_arguments')
                self.assertNotIn('private-post-text', result.stdout)
                self.assertNotIn('private-image-buffer', result.stdout)

    def test_unreadable_file_is_json_in_subprocess(self):
        with TemporaryDirectory() as directory:
            image = Path(directory) / 'unreadable.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\nprivate-image-buffer')
            image.chmod(0)
            try:
                # Privileged runners can read mode-000 files; use a resolution
                # loop there to exercise an unreadable path without live CDP.
                try:
                    image.read_bytes()
                except PermissionError:
                    pass
                else:
                    image.chmod(0o600)
                    image.unlink()
                    image.symlink_to(image.name)
                result = self.run_cli('post', '--text', 'Approved', '--image', str(image))
                self.assert_error(result, 'invalid_images')
                self.assertNotIn('private-image-buffer', result.stdout)
            finally:
                if not image.is_symlink():
                    image.chmod(0o600)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.cli = importlib.import_module('tools.linkedin_agent.cli')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.png = Path(self.temp.name) / 'first.png'
        self.png.write_bytes(b'\x89PNG\r\n\x1a\nfirst-buffer')
        self.jpg = Path(self.temp.name) / 'second.jpg'
        self.jpg.write_bytes(b'\xff\xd8\xffsecond-buffer')
        self.args = ['post', '--text', '  Approved\r\n\ntext  ',
                     '--image', str(self.png), '--image', str(self.jpg)]

    def call_main(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            status = self.cli.main(args)
        return status, json.loads(output.getvalue())

    def test_invalid_inputs_never_construct_browser(self):
        cases = [(['post', '--text', ' ', '--image', 'missing.png'], 'invalid_text'),
                 (['post', '--text', 'Approved', '--image', 'missing.png'], 'invalid_images'),
                 (['--timeout-ms', '0', 'doctor'], 'invalid_timeout'),
                 (['post', '--text', 'Approved'], 'invalid_arguments')]
        with patch('tools.linkedin_agent.cli.Browser') as browser:
            for args, code in cases:
                with self.subTest(code=code):
                    status, payload = self.call_main(args)
                    self.assertEqual(status, 2)
                    self.assertEqual(payload['error']['code'], code)
            browser.assert_not_called()

    def test_unreadable_file_is_validated_before_browser(self):
        with patch.object(Path, 'open', side_effect=PermissionError('private-path')), \
                patch('tools.linkedin_agent.cli.Browser') as browser:
            status, payload = self.call_main(self.args)
        self.assertEqual(status, 2)
        self.assertEqual(payload['error']['code'], 'invalid_images')
        browser.assert_not_called()

    def test_doctor_dispatches_without_posting(self):
        with patch('tools.linkedin_agent.cli.Browser') as browser, \
                patch('tools.linkedin_agent.cli.publish_post') as publish:
            session = browser.return_value.__enter__.return_value
            session.doctor.return_value = {
                'connected': True, 'authenticated': True,
            }
            status, payload = self.call_main([
                '--cdp', 'http://localhost:9223', '--timeout-ms', '1234', 'doctor',
            ])
        self.assertEqual(status, 0)
        self.assertEqual(payload, {'ok': True, 'data': {
            'connected': True, 'authenticated': True,
        }})
        browser.assert_called_once_with(endpoint='http://localhost:9223', timeout_ms=1234)
        session.new_page.assert_not_called()
        publish.assert_not_called()
        browser.return_value.__exit__.assert_called_once()

    def test_post_dispatches_exact_text_and_ordered_snapshots_once(self):
        with patch('tools.linkedin_agent.cli.Browser') as browser, \
                patch('tools.linkedin_agent.cli.publish_post') as publish:
            session = browser.return_value.__enter__.return_value
            publish.return_value = {'status': 'posted', 'url': None}
            status, payload = self.call_main(self.args)
        self.assertEqual(status, 0)
        self.assertEqual(payload, {'ok': True, 'data': {'status': 'posted', 'url': None}})
        publish.assert_called_once()
        args, kwargs = publish.call_args
        self.assertIs(args[0], session.new_page.return_value)
        self.assertEqual(args[1], '  Approved\r\n\ntext  ')
        self.assertEqual([(image.name, image.mime_type, image.buffer) for image in args[2]], [
            ('first.png', 'image/png', b'\x89PNG\r\n\x1a\nfirst-buffer'),
            ('second.jpg', 'image/jpeg', b'\xff\xd8\xffsecond-buffer'),
        ])
        self.assertEqual(kwargs, {'timeout_ms': 15000})
        session.preserve_page.assert_not_called()
        browser.return_value.__exit__.assert_called_once()

    def test_uncertainty_preserves_page_before_disconnect_without_retry(self):
        events = []
        with patch('tools.linkedin_agent.cli.Browser') as browser, \
                patch('tools.linkedin_agent.cli.publish_post') as publish:
            session = browser.return_value.__enter__.return_value
            session.preserve_page.side_effect = lambda page: events.append(('preserve', page))
            browser.return_value.__exit__.side_effect = lambda *args: events.append(('disconnect',))
            publish.side_effect = AgentError('submission_uncertain', 'Inspect manually.', True)
            status, payload = self.call_main(self.args)
        self.assertEqual(status, 4)
        self.assertEqual(payload['error']['code'], 'submission_uncertain')
        self.assertTrue(payload['error']['human_action_required'])
        self.assertEqual(events, [('preserve', session.new_page.return_value), ('disconnect',)])
        publish.assert_called_once()

    def test_known_pre_submit_errors_exit_three_and_do_not_preserve(self):
        for code in ('not_authenticated', 'browser_challenge', 'dom_timeout',
                     'ambiguous_selector', 'unsupported_identity', 'upload_failed',
                     'text_mismatch', 'submission_disabled', 'composer_failed'):
            with self.subTest(code=code), patch('tools.linkedin_agent.cli.Browser') as browser, \
                    patch('tools.linkedin_agent.cli.publish_post',
                          side_effect=AgentError(code, 'Inspect manually.')) as publish:
                status, payload = self.call_main(self.args)
                self.assertEqual(status, 3)
                self.assertEqual(payload['error']['code'], code)
                browser.return_value.__enter__.return_value.preserve_page.assert_not_called()
                browser.return_value.__exit__.assert_called_once()
                publish.assert_called_once()

    def test_connection_error_is_json_exit_three(self):
        with patch('tools.linkedin_agent.cli.Browser') as browser:
            browser.return_value.__enter__.side_effect = AgentError(
                'browser_connection_failed', 'Launch Chrome.', True,
            )
            status, payload = self.call_main(['doctor'])
        self.assertEqual(status, 3)
        self.assertEqual(payload['error'], {
            'code': 'browser_connection_failed', 'message': 'Launch Chrome.',
            'human_action_required': True,
        })

    def test_unexpected_error_is_sanitized_and_disconnects(self):
        with patch('tools.linkedin_agent.cli.Browser') as browser, \
                patch('tools.linkedin_agent.cli.publish_post',
                      side_effect=RuntimeError('private-post-text private-image-buffer')):
            status, payload = self.call_main(self.args)
        self.assertEqual(status, 1)
        self.assertEqual(payload['error']['code'], 'unexpected_error')
        self.assertNotIn('private', json.dumps(payload))
        self.assertNotIn('Traceback', json.dumps(payload))
        browser.return_value.__exit__.assert_called_once()


if __name__ == '__main__':
    unittest.main()
