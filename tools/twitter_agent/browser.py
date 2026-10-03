"""Playwright CDP browser lifecycle management and doctor connectivity checks."""

import re
from typing import List, Optional
from playwright.sync_api import sync_playwright

from tools.social_agent.browser import CDPBrowser
from .models import AgentError
from .pacing import get_pacer
from . import dom, selectors


class Browser(CDPBrowser):
    """Twitter/X browser session backed by shared CDP foundation."""

    def __init__(self, endpoint: str = 'http://127.0.0.1:9222', timeout_ms: int = 15000):
        super().__init__(endpoint=endpoint, timeout_ms=timeout_ms)

    def doctor(self) -> dict:
        """Check CDP connectivity, browser context, and X authentication."""
        if not self._context:
            raise AgentError('browser_not_connected', 'Browser is not connected.')

        page = self.new_page()
        try:
            try:
                get_pacer().wait('navigation')
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

            if page.locator(dom.AUTHENTICATED_HOME).count() > 0 or page.locator(dom.ACCOUNT_SWITCHER).count() > 0:
                auth_found = True
                switcher = page.locator(dom.ACCOUNT_SWITCHER).first
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
