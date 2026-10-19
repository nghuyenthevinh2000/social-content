"""Compatibility checks for shared agent plumbing; no browser or network needed."""

import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import call, patch

from tools.common import config
from tools.common.cli_support import JsonArgumentParser, emit_error, emit_result, emit_success
from tools.common.errors import AgentError
from tools.common.groups import MAX_SHARE_GROUPS, validate_group_names
from tools.common.post import PostError, _validate_group_names
from tools.facebook_agent import models as facebook
from tools.linkedin_agent import models as linkedin
from tools.linkedin_agent.cli import build_parser as linkedin_parser
from tools.twitter_agent import models as twitter


class SharedSupportTests(unittest.TestCase):
    def test_error_reexports_and_string_compatibility(self):
        for module in (facebook, linkedin, twitter):
            self.assertIs(module.AgentError, AgentError)
            error = module.AgentError('example', 'Inspect manually.', True)
            self.assertEqual(str(error), 'Inspect manually.')
            self.assertTrue(error.human_action_required)
        self.assertEqual(str(PostError('invalid_post', 'Bad post.')), 'Bad post.')
        self.assertEqual(str(config.AgentError('example', 'Bad config.')), '[example] Bad config.')
        self.assertIsInstance(config.AgentError('example', 'Bad config.'), AgentError)

    def test_timeout_fallback_and_reexports(self):
        from tools.facebook_agent.cli import get_default_doctor_timeout_ms as facebook_timeout
        from tools.linkedin_agent.cli import get_default_doctor_timeout_ms as linkedin_timeout
        from tools.twitter_agent.cli import get_default_doctor_timeout_ms as twitter_timeout
        for helper in (facebook_timeout, linkedin_timeout, twitter_timeout):
            self.assertIs(helper, config.get_default_doctor_timeout_ms)
        for value, expected in (('45000', 45000), ('bad', 30000), ('', 30000), ('0', 0)):
            with self.subTest(value=value), patch.dict(os.environ, {'DEFAULT_DOCTOR_TIMEOUT_MS': value}):
                self.assertEqual(config.get_default_doctor_timeout_ms(), expected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.get_default_doctor_timeout_ms(), 30000)

    def test_environment_loading_order_and_optional_repository_defaults(self):
        tools_env = Path(config.__file__).resolve().parents[1] / '.env'
        repo_env = tools_env.parent.parent / '.env'
        with patch('dotenv.load_dotenv') as load, patch.object(Path, 'exists', return_value=True):
            config.load_environment()
            self.assertEqual(load.call_args_list, [call(tools_env)])
            load.reset_mock()
            config.load_environment(include_repository=True)
            self.assertEqual(load.call_args_list, [call(tools_env), call(repo_env)])

    def test_parser_errors_and_help(self):
        parser = JsonArgumentParser()
        parser.add_argument('--required', required=True)
        with self.assertRaises(AgentError) as caught:
            parser.parse_args([])
        self.assertEqual(caught.exception.code, 'invalid_arguments')
        with patch('sys.stdout', new_callable=io.StringIO), self.assertRaises(SystemExit) as caught:
            parser.parse_args(['--help'])
        self.assertEqual(caught.exception.code, 0)

    def test_linkedin_nested_parser_does_not_leak_input(self):
        secret = 'PRIVATE-PAYLOAD'
        with self.assertRaises(AgentError) as caught:
            linkedin_parser().parse_args(['post', '--text', secret, '--image', 'image.png', '--unknown', secret])
        self.assertNotIn(secret, caught.exception.message)

    def test_json_envelopes_and_uncertain_result(self):
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            emit_success({'text': 'Tiếng Việt'}, ok=False, ensure_ascii=False)
            emit_error('browser_challenge', 'Inspect manually.', True)
        decoder = json.JSONDecoder()
        first, end = decoder.raw_decode(output.getvalue())
        second = json.loads(output.getvalue()[end:])
        self.assertEqual(first, {'ok': False, 'data': {'text': 'Tiếng Việt'}})
        self.assertEqual(second['error'], {
            'code': 'browser_challenge', 'message': 'Inspect manually.', 'human_action_required': True,
        })
        self.assertIn('Tiếng Việt', output.getvalue())
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            emit_result(first, indent=None)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(output.getvalue()), first)

    def test_group_reexports_and_boundary_types(self):
        self.assertIs(facebook.validate_group_names, validate_group_names)
        self.assertEqual(facebook.MAX_SHARE_GROUPS, MAX_SHARE_GROUPS)
        self.assertEqual(validate_group_names(iter([' A ', 'B'])), ['A', 'B'])
        self.assertEqual(_validate_group_names([' A ', 'B']), ('A', 'B'))
        self.assertEqual(_validate_group_names([]), ())
        self.assertEqual(len(validate_group_names([str(i) for i in range(MAX_SHARE_GROUPS)])), MAX_SHARE_GROUPS)
        with self.assertRaises(PostError):
            _validate_group_names(('A', 'B'))

    def test_group_failures_keep_public_error_types(self):
        for names in (['A', ' A '], [''], ['bad\x00name'], [None], list(map(str, range(10)))):
            for validator, error_class in ((validate_group_names, AgentError), (_validate_group_names, PostError)):
                with self.subTest(names=names, validator=validator), self.assertRaises(error_class) as caught:
                    validator(names)
                self.assertEqual(caught.exception.code, 'invalid_groups')


if __name__ == '__main__':
    unittest.main()
