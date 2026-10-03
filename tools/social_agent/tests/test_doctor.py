"""Unit tests for tools.social_agent.doctor."""

import unittest
from unittest.mock import MagicMock, patch

from tools.social_agent.config import AgentError
from tools.social_agent.doctor import run_doctor


class DoctorTests(unittest.TestCase):
    def test_doctor_success(self):
        mock_playwright_inst = MagicMock()
        mock_browser = MagicMock()
        mock_context1 = MagicMock()
        mock_context2 = MagicMock()
        mock_page = MagicMock()

        mock_context1.pages = [mock_page]
        mock_browser.contexts = [mock_context1, mock_context2]
        mock_browser.version = 'Chrome/133.0.0.0'
        mock_playwright_inst.chromium.connect_over_cdp.return_value = mock_browser

        with patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright_inst

            result = run_doctor(endpoint='http://127.0.0.1:9222', timeout_ms=5000)

            self.assertEqual(result, {
                'connected': True,
                'endpoint': 'http://127.0.0.1:9222',
                'browser_version': 'Chrome/133.0.0.0',
                'context_count': 2,
            })

            # Assert no navigation occurred
            self.assertEqual(mock_page.goto.call_count, 0)
            self.assertEqual(mock_context1.new_page.call_count, 0)

            # Assert user browser, context, and page were not closed
            self.assertEqual(mock_browser.close.call_count, 0)
            self.assertEqual(mock_context1.close.call_count, 0)
            self.assertEqual(mock_page.close.call_count, 0)

            # Assert Playwright client was stopped
            mock_playwright_inst.stop.assert_called_once()

    def test_doctor_connection_failure(self):
        mock_playwright_inst = MagicMock()
        mock_playwright_inst.chromium.connect_over_cdp.side_effect = Exception('Cannot connect')

        with patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright_inst

            with self.assertRaises(AgentError) as ctx:
                run_doctor(endpoint='http://127.0.0.1:9999')

            self.assertEqual(ctx.exception.code, 'browser_connection_failed')
            mock_playwright_inst.stop.assert_called_once()

    def test_doctor_no_browser_context(self):
        mock_playwright_inst = MagicMock()
        mock_browser = MagicMock()
        mock_browser.contexts = []
        mock_playwright_inst.chromium.connect_over_cdp.return_value = mock_browser

        with patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright_inst

            with self.assertRaises(AgentError) as ctx:
                run_doctor(endpoint='http://127.0.0.1:9222')

            self.assertEqual(ctx.exception.code, 'no_browser_context')
            mock_playwright_inst.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
