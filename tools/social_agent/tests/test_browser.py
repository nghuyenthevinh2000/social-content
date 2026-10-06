"""Unit tests for tools.social_agent.browser."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from tools.social_agent.browser import CDPBrowser
from tools.social_agent.config import AgentError


class BrowserTests(unittest.TestCase):
    def test_connect_success(self):
        mock_playwright_inst = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_context.pages = [mock_page]
        mock_browser.contexts = [mock_context]
        mock_browser.version = 'Chrome/133.0.6943.98'
        mock_playwright_inst.chromium.connect_over_cdp.return_value = mock_browser

        with patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright_inst

            with CDPBrowser(endpoint='http://127.0.0.1:9222', timeout_ms=5000) as cdp:
                self.assertEqual(cdp.endpoint, 'http://127.0.0.1:9222')
                self.assertEqual(cdp.version, 'Chrome/133.0.6943.98')
                self.assertEqual(len(cdp.contexts), 1)
                self.assertEqual(cdp.context, mock_context)
                self.assertEqual(cdp.browser, mock_browser)

            # Verification of safety:
            # 1. Playwright client was stopped
            mock_playwright_inst.stop.assert_called_once()
            # 2. User browser was NEVER closed
            self.assertEqual(mock_browser.close.call_count, 0)
            # 3. User context was NEVER closed
            self.assertEqual(mock_context.close.call_count, 0)
            # 4. User page/tab was NEVER closed
            self.assertEqual(mock_page.close.call_count, 0)

    def test_connection_failure_cleans_up(self):
        mock_playwright_inst = MagicMock()
        mock_playwright_inst.chromium.connect_over_cdp.side_effect = Exception('Connection refused')

        with patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright_inst

            cdp = CDPBrowser(endpoint='http://127.0.0.1:9222')
            with self.assertRaises(AgentError) as ctx:
                cdp.connect()

            self.assertEqual(ctx.exception.code, 'browser_connection_failed')
            self.assertTrue(ctx.exception.human_action_required)
            # Playwright client must be stopped on failure
            mock_playwright_inst.stop.assert_called_once()
            self.assertIsNone(cdp.browser)

    def test_missing_contexts_cleans_up(self):
        mock_playwright_inst = MagicMock()
        mock_browser = MagicMock()
        mock_browser.contexts = []  # No open tabs/contexts
        mock_playwright_inst.chromium.connect_over_cdp.return_value = mock_browser

        with patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright_inst

            cdp = CDPBrowser(endpoint='http://127.0.0.1:9222')
            with self.assertRaises(AgentError) as ctx:
                cdp.connect()

            self.assertEqual(ctx.exception.code, 'no_browser_context')
            self.assertTrue(ctx.exception.human_action_required)
            # Playwright client must be stopped on failure
            mock_playwright_inst.stop.assert_called_once()
            # User browser must NOT be closed
            self.assertEqual(mock_browser.close.call_count, 0)
            self.assertIsNone(cdp.browser)

    def test_version_and_context_empty_when_not_connected(self):
        cdp = CDPBrowser()
        self.assertEqual(cdp.version, '')
        self.assertIsNone(cdp.context)
        self.assertEqual(cdp.contexts, [])

    def test_cdp_browser_delegates_to_invisible(self):
        mock_context = MagicMock(spec=['new_page', 'pages', 'close', 'browser'])
        mock_ipw_instance = MagicMock()
        mock_ipw_instance.__enter__.return_value = mock_context

        with patch('invisible_playwright.InvisiblePlaywright', return_value=mock_ipw_instance):
            browser = CDPBrowser(backend='invisible')
            browser.connect()
            self.assertEqual(browser.backend, 'invisible')
            self.assertEqual(browser.context, mock_context)
            browser.disconnect()


class InvisibleBrowserTests(unittest.TestCase):
    def test_invisible_connect_success(self):
        from tools.social_agent.browser import InvisibleBrowser
        mock_context = MagicMock(spec=['new_page', 'pages', 'close', 'browser'])
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_ipw_instance = MagicMock()
        mock_ipw_instance.__enter__.return_value = mock_context

        with patch('invisible_playwright.InvisiblePlaywright', return_value=mock_ipw_instance):
            with InvisibleBrowser(seed=42, headless=True) as browser:
                self.assertEqual(browser.backend, 'invisible')
                self.assertEqual(browser.seed, 42)
                self.assertTrue(browser.headless)
                self.assertEqual(browser.context, mock_context)

                # Page creation
                page = browser.new_page()
                self.assertEqual(page, mock_page)
                self.assertEqual(browser.page, mock_page)

            # Cleanup
            mock_ipw_instance.__exit__.assert_called_once()
            self.assertIsNone(browser.context)

    def test_invisible_unsupported_raises_error(self):
        from tools.social_agent.browser import InvisibleBrowser

        with patch('invisible_playwright.InvisiblePlaywright', side_effect=NotImplementedError('macOS not supported')):
            browser = InvisibleBrowser(fallback_to_cdp=False)
            with self.assertRaises(AgentError) as ctx:
                browser.connect()
            self.assertEqual(ctx.exception.code, 'invisible_browser_unsupported')

    def test_invisible_unsupported_fallback_to_cdp(self):
        from tools.social_agent.browser import InvisibleBrowser
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_browser.contexts = [mock_context]
        mock_playwright = MagicMock()
        mock_playwright.chromium.connect_over_cdp.return_value = mock_browser

        with patch('invisible_playwright.InvisiblePlaywright', side_effect=NotImplementedError('macOS not supported')), \
             patch('playwright.sync_api.sync_playwright') as mock_sp:
            mock_sp.return_value.start.return_value = mock_playwright
            browser = InvisibleBrowser(fallback_to_cdp=True, endpoint='http://127.0.0.1:9222')
            browser.connect()
            self.assertEqual(browser.backend, 'cdp')
            self.assertEqual(browser.context, mock_context)
            browser.disconnect()


if __name__ == '__main__':
    unittest.main()
