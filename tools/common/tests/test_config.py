"""Unit tests for tools.common.config."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.common.config import (
    DEFAULT_DOCTOR_TIMEOUT_MS,
    DEFAULT_ENDPOINT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    AgentError,
    find_browser_binary,
    find_free_port,
    get_config,
    read_recorded_port,
    resolve_profile_dir,
    write_recorded_port,
)


class ConfigTests(unittest.TestCase):
    def test_default_config(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.port, DEFAULT_PORT)
            self.assertEqual(cfg.host, DEFAULT_HOST)
            self.assertEqual(cfg.endpoint, DEFAULT_ENDPOINT)
            self.assertEqual(cfg.doctor_timeout_ms, DEFAULT_DOCTOR_TIMEOUT_MS)
            self.assertEqual(cfg.readiness_timeout_seconds, DEFAULT_READINESS_TIMEOUT_SECONDS)
            self.assertTrue(str(cfg.user_data_dir).endswith('chrome-twitter-profile'))

    def test_env_overrides(self):
        env = {
            'CDP_PORT': '9333',
            'CDP_HOST': '127.0.0.2',
            'CHROME_USER_DATA_DIR': '/tmp/custom-profile',
            'DEFAULT_DOCTOR_TIMEOUT_MS': '45000',
            'CDP_READINESS_TIMEOUT_SECONDS': '25.0',
            'CHROME_BIN': '/usr/bin/custom-chrome',
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.port, 9333)
            self.assertEqual(cfg.host, '127.0.0.2')
            self.assertEqual(cfg.endpoint, 'http://127.0.0.2:9333')
            self.assertEqual(cfg.user_data_dir, Path('/tmp/custom-profile').resolve())
            self.assertEqual(cfg.doctor_timeout_ms, 45000)
            self.assertEqual(cfg.readiness_timeout_seconds, 25.0)

    def test_port_env_fallback(self):
        env = {'PORT': '9444'}
        with patch.dict(os.environ, env, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.port, 9444)

    def test_user_data_dir_env_fallback(self):
        env = {'USER_DATA_DIR': '/tmp/fallback-profile'}
        with patch.dict(os.environ, env, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.user_data_dir, Path('/tmp/fallback-profile').resolve())

    def test_explicit_argument_precedence(self):
        env = {
            'CDP_PORT': '9333',
            'CHROME_USER_DATA_DIR': '/tmp/env-profile',
            'DEFAULT_DOCTOR_TIMEOUT_MS': '45000',
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = get_config(
                port=9555,
                data_dir='/tmp/arg-profile',
                timeout_ms=10000,
            )
            self.assertEqual(cfg.port, 9555)
            self.assertEqual(cfg.user_data_dir, Path('/tmp/arg-profile').resolve())
            self.assertEqual(cfg.doctor_timeout_ms, 10000)

    def test_invalid_port(self):
        with self.assertRaises(AgentError) as ctx:
            get_config(port='not-a-number')
        self.assertEqual(ctx.exception.code, 'invalid_arguments')

        with self.assertRaises(AgentError) as ctx:
            get_config(port=0)
        self.assertEqual(ctx.exception.code, 'invalid_arguments')

        with self.assertRaises(AgentError) as ctx:
            get_config(port=70000)
        self.assertEqual(ctx.exception.code, 'invalid_arguments')

    def test_invalid_timeouts(self):
        with self.assertRaises(AgentError) as ctx:
            get_config(timeout_ms=0)
        self.assertEqual(ctx.exception.code, 'invalid_arguments')

        with self.assertRaises(AgentError) as ctx:
            get_config(readiness_timeout_seconds=-1)
        self.assertEqual(ctx.exception.code, 'invalid_arguments')

    def test_find_browser_binary_custom(self):
        with patch('os.path.isfile', return_value=True), \
             patch('os.access', return_value=True):
            found = find_browser_binary('/mock/path/to/chrome')
            self.assertEqual(found, '/mock/path/to/chrome')

    def test_find_browser_binary_env(self):
        with patch.dict(os.environ, {'CHROME_BIN': '/mock/env/chrome'}), \
             patch('os.path.isfile', return_value=True), \
             patch('os.access', return_value=True):
            found = find_browser_binary()
            self.assertEqual(found, '/mock/env/chrome')

    def test_find_browser_binary_not_found(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch('os.path.isfile', return_value=False), \
             patch('shutil.which', return_value=None):
            found = find_browser_binary()
            self.assertIsNone(found)

    def test_resolve_profile_dir_prefers_explicit_argument(self):
        with patch.dict(os.environ, {'CHROME_USER_DATA_DIR': '/tmp/env-profile'}, clear=True):
            self.assertEqual(
                resolve_profile_dir('/tmp/arg-profile'),
                Path('/tmp/arg-profile').resolve(),
            )

    def test_find_free_port_is_bindable_and_avoids_the_default(self):
        port = find_free_port()
        self.assertGreater(port, 0)
        self.assertLessEqual(port, 65535)

    def test_recorded_port_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            self.assertIsNone(read_recorded_port(profile_dir))
            write_recorded_port(profile_dir, 9411)
            self.assertEqual(read_recorded_port(profile_dir), 9411)

    def test_recorded_port_rejects_garbage(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            (Path(profile_dir) / '.cdp-port').write_text('not-a-port', encoding='utf-8')
            self.assertIsNone(read_recorded_port(profile_dir))
            (Path(profile_dir) / '.cdp-port').write_text('70000', encoding='utf-8')
            self.assertIsNone(read_recorded_port(profile_dir))


if __name__ == '__main__':
    unittest.main()
