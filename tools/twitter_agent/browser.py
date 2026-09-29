"""Playwright CDP browser lifecycle management and doctor connectivity checks."""

import re
from typing import List, Optional
from playwright.sync_api import sync_playwright

from .models import AgentError
from . import selectors


class Browser:
    def __init__(self, endpoint: str = 'http://127.0.0.1:9222', timeout_ms: int = 15000):
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._created_pages: List = []

    def __enter__(self):
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.endpoint, timeout=self.timeout_ms
            )
        except Exception as exc:
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
            raise AgentError(
                'browser_connection_failed',
                f'Failed to connect to browser CDP at {self.endpoint}: {exc}',
                human_action_required=True,
            ) from exc

        if not self._browser.contexts:
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
            raise AgentError(
                'no_browser_context',
                'Chrome has no open browser contexts. Open at least one tab.',
                human_action_required=True,
            )

        self._context = self._browser.contexts[0]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close only tool-created temporary tabs, preserving existing user tabs
        for page in list(self._created_pages):
            try:
                page.close()
            except Exception:
                pass
        self._created_pages.clear()

        # Disconnect client without calling browser.close() on user's browser
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass

    def new_page(self):
        if not self._context:
            raise AgentError('browser_not_connected', 'Browser is not connected.')
        page = self._context.new_page()
        page.set_default_timeout(self.timeout_ms)
        self._created_pages.append(page)
        return page

    @property
    def page(self):
        """Current temporary page or create a new page if none exists."""
        if not self._created_pages:
            return self.new_page()
        return self._created_pages[-1]


    def close_page(self, page):
        """Explicitly close a created temporary page."""
        try:
            page.close()
        except Exception:
            pass
        if page in self._created_pages:
            self._created_pages.remove(page)

    def doctor(self) -> dict:
        """Check CDP connectivity, browser context, and X authentication."""
        if not self._context:
            raise AgentError('browser_not_connected', 'Browser is not connected.')

        page = self.new_page()
        try:
            try:
                page.goto('https://x.com/home', wait_until='domcontentloaded', timeout=self.timeout_ms)
                page.wait_for_timeout(1000)
            except Exception as e:
                block = selectors.detect_block(page)
                if block:
                    raise block
                raise AgentError('browser_navigation_failed', f'Failed to navigate to X home: {e}') from e

            # Check blocks/challenges
            block = selectors.detect_block(page)
            if block:
                raise block

            auth_found = False
            user_handle = None

            if page.locator(selectors.AUTHENTICATED_HOME).count() > 0 or page.locator(selectors.ACCOUNT_SWITCHER).count() > 0:
                auth_found = True
                switcher = page.locator(selectors.ACCOUNT_SWITCHER).first
                if switcher.count() > 0:
                    text = switcher.inner_text()
                    match = re.search(r'@[A-Za-z0-9_]+', text)
                    if match:
                        user_handle = match.group(0)

            if not auth_found:
                raise AgentError(
                    'not_authenticated',
                    'Chrome profile is not logged into X.',
                    human_action_required=True,
                )

            return {
                'connected': True,
                'authenticated': True,
                'user': user_handle,
                'endpoint': self.endpoint,
            }
        finally:
            self.close_page(page)
