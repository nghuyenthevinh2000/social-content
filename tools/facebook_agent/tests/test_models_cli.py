"""Validation and CLI contracts; no live browser or Facebook calls."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.facebook_agent.models import (
    AgentError, load_group_names, load_message_plan, validate_content, validate_group_names)
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


class PlanTests(unittest.TestCase):
    def write(self, payload):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'plan.json'
        path.write_text(payload, encoding='utf-8')
        return str(path)

    def test_loads_array_and_object_plans(self):
        for payload in ('[{"url": "https://www.facebook.com/a", "message": "Hi A"}]',
                        '{"recipients": [{"url": "https://www.facebook.com/a", "message": "Hi A"}]}'):
            with self.subTest(payload=payload):
                plan = load_message_plan(self.write(payload))
                self.assertEqual(plan, [{'url': 'https://www.facebook.com/a', 'message': 'Hi A',
                                         'label': 'https://www.facebook.com/a'}])

    def test_accepts_aliases_and_label(self):
        plan = load_message_plan(self.write(
            '[{"recipient": "https://www.facebook.com/a", "text": "Hi", "label": "Alice"}]'))
        self.assertEqual(plan, [{'url': 'https://www.facebook.com/a', 'message': 'Hi', 'label': 'Alice'}])

    def test_rejects_bad_plans(self):
        cases = {
            'not json': 'nonsense',
            'empty': '[]',
            'unknown key': '[{"url": "https://www.facebook.com/a", "message": "Hi", "extra": 1}]',
            'no url': '[{"message": "Hi"}]',
            'both url and recipient': '[{"url": "https://www.facebook.com/a", '
                                      '"recipient": "https://www.facebook.com/b", "message": "Hi"}]',
            'no message': '[{"url": "https://www.facebook.com/a"}]',
            'blank message': '[{"url": "https://www.facebook.com/a", "message": "  "}]',
            'non-facebook': '[{"url": "https://example.com/a", "message": "Hi"}]',
            'reserved path': '[{"url": "https://www.facebook.com/messages", "message": "Hi"}]',
            'oversized': '[{"url": "https://www.facebook.com/a", "message": "' + 'a' * 20001 + '"}]',
        }
        for name, payload in cases.items():
            with self.subTest(case=name), self.assertRaises(AgentError) as error:
                load_message_plan(self.write(payload))
            self.assertEqual(error.exception.code, 'invalid_plan')

    def test_missing_file(self):
        with self.assertRaises(AgentError) as error:
            load_message_plan('/missing/plan.json')
        self.assertEqual(error.exception.code, 'invalid_plan')


class GroupNameTests(unittest.TestCase):
    def write(self, payload):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'groups.json'
        path.write_text(payload, encoding='utf-8')
        return str(path)

    def test_loads_array_and_object(self):
        for payload in ('["Group A", "Group B"]', '{"groups": ["Group A", "Group B"]}'):
            with self.subTest(payload=payload):
                self.assertEqual(load_group_names(self.write(payload)), ['Group A', 'Group B'])

    def test_validate_strips_and_keeps_order(self):
        self.assertEqual(validate_group_names(['  A ', 'B']), ['A', 'B'])

    def test_rejects_bad_groups(self):
        cases = {
            'not json': 'nope',
            'empty': '[]',
            'non string': '[1]',
            'blank': '["  "]',
            'duplicate': '["A", "A"]',
            'too many': json.dumps([f'G{n}' for n in range(10)]),
        }
        for name, payload in cases.items():
            with self.subTest(case=name), self.assertRaises(AgentError) as error:
                load_group_names(self.write(payload))
            self.assertEqual(error.exception.code, 'invalid_groups')

    def test_missing_file(self):
        with self.assertRaises(AgentError) as error:
            load_group_names('/missing/groups.json')
        self.assertEqual(error.exception.code, 'invalid_groups')


class GroupCliTests(unittest.TestCase):
    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def test_group_flags_forwarded(self):
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
            code, _ = self.invoke(['post', '--text', 'Hi', '--group', 'Group A', '--group', 'Group B'])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.kwargs['groups'], ['Group A', 'Group B'])

    def test_groups_file_forwarded_and_combined(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'groups.json'
        path.write_text('["From File"]', encoding='utf-8')
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
            code, _ = self.invoke(['post', '--text', 'Hi', '--group', 'Flag', '--groups-file', str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.kwargs['groups'], ['Flag', 'From File'])

    def test_no_groups_passes_none(self):
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
            self.invoke(['post', '--text', 'Hi'])
        self.assertIsNone(post.call_args.kwargs['groups'])

    def test_invalid_groups_do_not_connect(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'groups.json'
        path.write_text('["A", "A"]', encoding='utf-8')
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, result = self.invoke(['post', '--text', 'Hi', '--groups-file', str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_groups')
        browser.assert_not_called()

    def test_duplicate_across_flag_and_file_rejected(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'groups.json'
        path.write_text('["A"]', encoding='utf-8')
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, _ = self.invoke(['post', '--text', 'Hi', '--group', 'A', '--groups-file', str(path)])
        self.assertEqual(code, 2)
        browser.assert_not_called()


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

    def test_text_file_preserves_unicode_quotes_and_literal_shell_text(self):
        text = '  Tư vấn "RWA" — dòng 1\nDòng 2: \'trích dẫn\' $(touch NEVER_RUN) `literal` $HOME  '
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'approved copy.md'
            path.write_bytes((text + '\n\n').replace('\n', '\r\n').encode('utf-8'))
            with patch('tools.facebook_agent.cli.Browser'), patch(
                    'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
                code, _ = self.invoke(['post', '--text-file', str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.args[1], text)

    def test_text_input_is_required_and_mutually_exclusive(self):
        for argv in (['post'], ['post', '--text', 'Hi', '--text-file', 'copy.md']):
            with self.subTest(argv=argv), patch('tools.facebook_agent.cli.Browser') as browser:
                code, _ = self.invoke(argv)
            self.assertEqual(code, 2)
            browser.assert_not_called()

    def test_invalid_text_file_never_opens_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'copy.md'
            for value in (None, b'\xff\xfe', b'\n\n', b'\0invalid', b'a' * 63207):
                with self.subTest(value=str(value)[:20]):
                    if value is not None:
                        path.write_bytes(value)
                    with patch('tools.facebook_agent.cli.Browser') as browser:
                        code, data = self.invoke(['post', '--text-file', str(path)])
                    self.assertEqual(code, 2)
                    self.assertEqual(data['error']['code'], 'invalid_content')
                    browser.assert_not_called()

    def test_invalid_timeout(self):
        code, result = self.invoke(['--timeout-ms', '0', 'doctor'])
        self.assertEqual(code, 2)
        self.assertFalse(result['ok'])

    def test_blank_page_name_does_not_connect(self):
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, _ = self.invoke(['doctor', '--page-name', ' '])
        self.assertEqual(code, 2)
        browser.assert_not_called()

    def test_page_name_forwarded_to_doctor_and_publish(self):
        with patch('tools.facebook_agent.cli.Browser') as browser:
            browser.return_value.__enter__.return_value.doctor.return_value = {'authenticated': True}
            code, _ = self.invoke(['doctor', '--page-name', 'Test Page'])
            self.assertEqual(code, 0)
            browser.return_value.__enter__.return_value.doctor.assert_called_once_with(page_name='Test Page', page_id=None)
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
            code, _ = self.invoke(['post', '--page-name', 'Test Page', '--text', 'Hello'])
            self.assertEqual(code, 0)
            self.assertEqual(post.call_args.kwargs['page_name'], 'Test Page')

    def test_video_forwarded_to_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / 'clip.mp4'
            clip.write_bytes(b'\x00\x00\x00\x20ftypisom' + b'0' * 64)
            with patch('tools.facebook_agent.cli.Browser'), patch(
                    'tools.facebook_agent.cli.publish', return_value={'status': 'confirmed'}) as post:
                code, _ = self.invoke(['post', '--text', 'Hello', '--video', str(clip)])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.kwargs['video'], clip.resolve())

    def test_invalid_video_does_not_connect(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / 'clip.mp4'
            clip.write_bytes(b'not a video')
            with patch('tools.facebook_agent.cli.Browser') as browser:
                code, result = self.invoke(['post', '--text', 'Hello', '--video', str(clip)])
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_video')
        browser.assert_not_called()

    def test_image_and_video_together_do_not_connect(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / 'clip.mp4'
            clip.write_bytes(b'\x00\x00\x00\x20ftypisom' + b'0' * 64)
            with patch('tools.facebook_agent.cli.Browser') as browser:
                code, result = self.invoke(
                    ['post', '--text', 'Hello', '--image', str(clip), '--video', str(clip)])
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_arguments')
        browser.assert_not_called()

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


class MessageCliTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.plan = Path(directory.name) / 'plan.json'
        self.plan.write_text('[{"url": "https://www.facebook.com/a", "message": "Hi A"}]', encoding='utf-8')

    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def test_invalid_plan_does_not_connect(self):
        with patch('tools.facebook_agent.cli.Browser') as browser:
            code, result = self.invoke(['message', '--plan', '/missing/plan.json'])
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_plan')
        browser.assert_not_called()

    def test_invalid_pacing_does_not_connect(self):
        for argv in (['message', '--plan', str(self.plan), '--max-messages', '0'],
                     ['message', '--plan', str(self.plan), '--min-delay-ms', '5000',
                      '--max-delay-ms', '1000'],
                     ['message', '--plan', str(self.plan), '--cooldown-every', '-1']):
            with self.subTest(argv=argv), patch('tools.facebook_agent.cli.Browser') as browser:
                code, _ = self.invoke(argv)
                self.assertEqual(code, 2)
                browser.assert_not_called()

    def test_message_forwards_plan_and_confirms(self):
        data = {'requested': 1, 'attempted': 1, 'confirmed': 1, 'uncertain': 0,
                'failed': 0, 'stopped_reason': None, 'results': []}
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.run_plan', return_value=data) as run:
            code, result = self.invoke(['message', '--plan', str(self.plan)])
        self.assertEqual(code, 0)
        self.assertTrue(result['ok'])
        recipients = run.call_args.args[1]
        self.assertEqual(recipients, [{'url': 'https://www.facebook.com/a', 'message': 'Hi A',
                                       'label': 'https://www.facebook.com/a'}])

    def test_message_uncertain_exits_four(self):
        data = {'requested': 1, 'attempted': 1, 'confirmed': 0, 'uncertain': 1,
                'failed': 0, 'stopped_reason': None, 'results': []}
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.run_plan', return_value=data):
            code, result = self.invoke(['message', '--plan', str(self.plan)])
        self.assertEqual(code, 4)
        self.assertFalse(result['ok'])

    def test_message_failed_or_aborted_exits_three(self):
        for data in ({'requested': 1, 'attempted': 1, 'confirmed': 0, 'uncertain': 0,
                      'failed': 1, 'stopped_reason': None, 'results': []},
                     {'requested': 2, 'attempted': 1, 'confirmed': 0, 'uncertain': 0,
                      'failed': 0, 'stopped_reason': 'not_authenticated', 'results': []}):
            with self.subTest(stopped=data['stopped_reason']), patch(
                    'tools.facebook_agent.cli.Browser'), patch(
                    'tools.facebook_agent.cli.run_plan', return_value=data):
                code, _ = self.invoke(['message', '--plan', str(self.plan)])
            self.assertEqual(code, 3)

    def test_max_messages_stop_is_not_an_error(self):
        data = {'requested': 5, 'attempted': 2, 'confirmed': 2, 'uncertain': 0,
                'failed': 0, 'stopped_reason': 'max_messages_reached', 'results': []}
        with patch('tools.facebook_agent.cli.Browser'), patch(
                'tools.facebook_agent.cli.run_plan', return_value=data):
            code, result = self.invoke(['message', '--plan', str(self.plan)])
        self.assertEqual(code, 0)
        self.assertTrue(result['ok'])

    def test_plan_is_required(self):
        code, result = self.invoke(['message'])
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_arguments')
