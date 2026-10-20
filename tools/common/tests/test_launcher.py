"""Unit tests for tools.common.launcher."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from tools.common.config import (
    AgentError,
    read_recorded_port,
    write_recorded_port,
)
from tools.common.launcher import (
    is_browser_responsive,
    launch_browser_process,
    live_profile_endpoint,
    start_browser,
)


class LauncherTests(unittest.TestCase):
    def test_is_browser_responsive_true(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response

        with patch('urllib.request.urlopen', return_value=mock_cm):
            self.assertTrue(is_browser_responsive(9222, '127.0.0.1'))

    def test_is_browser_responsive_false(self):
        with patch('urllib.request.urlopen', side_effect=Exception('Connection refused')):
            self.assertFalse(is_browser_responsive(9222, '127.0.0.1'))

    def test_start_browser_reuses_existing_browser(self):
        checker = MagicMock(return_value=True)
        launcher = MagicMock()

        result = start_browser(
            port=9222,
            host='127.0.0.1',
            data_dir='/tmp/test-profile',
            responsive_checker=checker,
            process_launcher=launcher,
        )

        self.assertEqual(result['action'], 'reused')
        self.assertEqual(result['endpoint'], 'http://127.0.0.1:9222')
        self.assertEqual(result['port'], 9222)
        self.assertEqual(result['user_data_dir'], str(Path('/tmp/test-profile').resolve()))
        # Launcher must NEVER be called if browser is responsive
        self.assertEqual(launcher.call_count, 0)

    def test_start_browser_starts_and_waits_until_ready(self):
        # Simulate: first check False (not running), second check False (waiting), third check True (ready)
        check_results = [False, False, True]
        checker = MagicMock(side_effect=lambda p, h: check_results.pop(0) if check_results else True)
        launcher = MagicMock()

        with patch('tools.common.config.find_browser_binary', return_value='/usr/bin/google-chrome'):
            result = start_browser(
                port=9222,
                host='127.0.0.1',
                data_dir='/tmp/test-profile',
                chrome_bin='/usr/bin/google-chrome',
                timeout=5.0,
                check_interval=0.01,
                responsive_checker=checker,
                process_launcher=launcher,
            )

        self.assertEqual(result['action'], 'started')
        self.assertEqual(result['endpoint'], 'http://127.0.0.1:9222')
        self.assertEqual(result['port'], 9222)
        self.assertEqual(result['browser_bin'], '/usr/bin/google-chrome')
        launcher.assert_called_once_with(
            '/usr/bin/google-chrome',
            9222,
            Path('/tmp/test-profile').resolve(),
            '127.0.0.1',
        )

    def test_start_browser_binary_not_found(self):
        checker = MagicMock(return_value=False)
        launcher = MagicMock()

        with patch('tools.common.config.find_browser_binary', return_value=None):
            with self.assertRaises(AgentError) as ctx:
                start_browser(
                    port=9222,
                    host='127.0.0.1',
                    responsive_checker=checker,
                    process_launcher=launcher,
                )

            self.assertEqual(ctx.exception.code, 'browser_binary_not_found')
            self.assertEqual(launcher.call_count, 0)

    def test_start_browser_readiness_timeout(self):
        checker = MagicMock(return_value=False)
        launcher = MagicMock()

        with patch('tools.common.config.find_browser_binary', return_value='/usr/bin/google-chrome'):
            with self.assertRaises(AgentError) as ctx:
                start_browser(
                    port=9222,
                    host='127.0.0.1',
                    chrome_bin='/usr/bin/google-chrome',
                    timeout=0.05,
                    check_interval=0.01,
                    responsive_checker=checker,
                    process_launcher=launcher,
                )

            self.assertEqual(ctx.exception.code, 'browser_readiness_timeout')
            launcher.assert_called_once()

    def test_launch_browser_process_darwin_app(self):
        target_dir = Path('/tmp/darwin-test-profile')
        with patch('sys.platform', 'darwin'), \
             patch('subprocess.Popen') as mock_popen, \
             patch.object(Path, 'mkdir') as mock_mkdir:
            launch_browser_process(
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                9222,
                target_dir,
                '127.0.0.1',
            )

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_popen.assert_called_once_with(
                [
                    'open',
                    '-na',
                    '/Applications/Google Chrome.app',
                    '--args',
                    '--remote-debugging-port=9222',
                    '--remote-debugging-address=127.0.0.1',
                    f'--user-data-dir={target_dir}',
                    'about:blank',
                ],
                stdout=mock_popen.call_args.kwargs['stdout'],
                stderr=mock_popen.call_args.kwargs['stderr'],
            )

    def test_launch_browser_process_linux(self):
        target_dir = Path('/tmp/linux-test-profile')
        with patch('sys.platform', 'linux'), \
             patch('subprocess.Popen') as mock_popen, \
             patch.object(Path, 'mkdir') as mock_mkdir:
            launch_browser_process(
                '/usr/bin/google-chrome',
                9222,
                target_dir,
                '127.0.0.1',
            )

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_popen.assert_called_once_with(
                [
                    '/usr/bin/google-chrome',
                    '--remote-debugging-port=9222',
                    '--remote-debugging-address=127.0.0.1',
                    f'--user-data-dir={target_dir}',
                    'about:blank',
                ],
                start_new_session=True,
                stdout=mock_popen.call_args.kwargs['stdout'],
                stderr=mock_popen.call_args.kwargs['stderr'],
            )

    def test_start_browser_invisible(self):
        with patch.object(Path, 'mkdir') as mock_mkdir:
            result = start_browser(
                backend='invisible',
                data_dir='/tmp/test-stealth-profile',
                seed=123,
                headless=True,
            )
            self.assertEqual(result['action'], 'ready')
            self.assertEqual(result['backend'], 'invisible')
            self.assertEqual(result['seed'], 123)
            self.assertTrue(result['headless'])
            self.assertEqual(result['user_data_dir'], str(Path('/tmp/test-stealth-profile').resolve()))
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_start_browser_auto_port_assigns_and_records_free_port(self):
        checker = MagicMock(side_effect=[False, True])
        launcher = MagicMock()

        with tempfile.TemporaryDirectory() as profile_dir, \
             patch('tools.common.config.find_browser_binary', return_value='/usr/bin/google-chrome'):
            result = start_browser(
                data_dir=profile_dir,
                chrome_bin='/usr/bin/google-chrome',
                auto_port=True,
                timeout=5.0,
                check_interval=0.01,
                responsive_checker=checker,
                process_launcher=launcher,
            )

            self.assertEqual(result['action'], 'started')
            self.assertGreater(result['port'], 0)
            self.assertEqual(result['endpoint'], f'http://127.0.0.1:{result["port"]}')
            self.assertEqual(read_recorded_port(profile_dir), result['port'])
            launcher.assert_called_once_with(
                '/usr/bin/google-chrome',
                result['port'],
                Path(profile_dir).resolve(),
                '127.0.0.1',
            )

    def test_start_browser_auto_port_reuses_recorded_port(self):
        checker = MagicMock(return_value=True)
        launcher = MagicMock()

        with tempfile.TemporaryDirectory() as profile_dir:
            write_recorded_port(profile_dir, 9411)
            result = start_browser(
                data_dir=profile_dir,
                auto_port=True,
                responsive_checker=checker,
                process_launcher=launcher,
            )

        self.assertEqual(result['action'], 'reused')
        self.assertEqual(result['port'], 9411)
        self.assertEqual(result['endpoint'], 'http://127.0.0.1:9411')
        self.assertEqual(launcher.call_count, 0)

    def test_start_browser_auto_port_is_isolated_per_profile(self):
        launcher = MagicMock()

        with tempfile.TemporaryDirectory() as root:
            page_a = Path(root) / 'page-a'
            page_b = Path(root) / 'page-b'
            with patch('tools.common.config.find_browser_binary', return_value='/usr/bin/google-chrome'):
                for profile in (page_a, page_b):
                    start_browser(
                        data_dir=profile,
                        chrome_bin='/usr/bin/google-chrome',
                        auto_port=True,
                        timeout=5.0,
                        check_interval=0.01,
                        responsive_checker=MagicMock(side_effect=[False, True]),
                        process_launcher=launcher,
                    )

            port_a = read_recorded_port(page_a)
            port_b = read_recorded_port(page_b)

        self.assertIsNotNone(port_a)
        self.assertIsNotNone(port_b)
        self.assertNotEqual(port_a, port_b)

    def test_live_profile_endpoint_returns_none_without_recorded_port(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            self.assertIsNone(
                live_profile_endpoint(data_dir=profile_dir, responsive_checker=MagicMock(return_value=True))
            )

    def test_live_profile_endpoint_requires_responsive_browser(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            write_recorded_port(profile_dir, 9412)
            self.assertIsNone(
                live_profile_endpoint(data_dir=profile_dir, responsive_checker=MagicMock(return_value=False))
            )
            self.assertEqual(
                live_profile_endpoint(data_dir=profile_dir, responsive_checker=MagicMock(return_value=True)),
                'http://127.0.0.1:9412',
            )


if __name__ == '__main__':
    unittest.main()
