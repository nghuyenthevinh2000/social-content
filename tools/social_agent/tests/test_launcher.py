"""Unit tests for tools.social_agent.launcher."""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, call, patch

from tools.social_agent.config import AgentError
from tools.social_agent.launcher import (
    is_browser_responsive,
    launch_browser_process,
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

        with patch('tools.social_agent.config.find_browser_binary', return_value='/usr/bin/google-chrome'):
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

        with patch('tools.social_agent.config.find_browser_binary', return_value=None):
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

        with patch('tools.social_agent.config.find_browser_binary', return_value='/usr/bin/google-chrome'):
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
                ],
                start_new_session=True,
                stdout=mock_popen.call_args.kwargs['stdout'],
                stderr=mock_popen.call_args.kwargs['stderr'],
            )


if __name__ == '__main__':
    unittest.main()
