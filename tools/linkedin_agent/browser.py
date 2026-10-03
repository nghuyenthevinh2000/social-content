"""Independent LinkedIn CDP lifecycle; disconnect without closing user Chrome."""

from tools.social_agent.browser import CDPBrowser
from .models import AgentError
from . import selectors


class Browser(CDPBrowser):
    """LinkedIn browser session backed by shared CDP foundation."""

    def __init__(self, endpoint: str = 'http://127.0.0.1:9222', timeout_ms: int = 15000):
        if timeout_ms <= 0:
            raise AgentError('invalid_timeout', 'Browser timeout must be positive.')
        super().__init__(endpoint=endpoint, timeout_ms=timeout_ms)

    def doctor(self) -> dict:
        """Check feed readiness without opening a composer or posting anything."""
        page = self.new_page()
        try:
            try:
                page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded',
                          timeout=self.timeout_ms)
            except Exception as exc:
                selectors.detect_block(page)
                raise AgentError(
                    'browser_navigation_failed', 'Cannot load the LinkedIn feed. Check connectivity.'
                ) from exc
            selectors.wait_for_selector_or_block(page, selectors.AUTHENTICATED_HOME, self.timeout_ms)
            selectors.wait_for_selector_or_block(page, selectors.START_POST, self.timeout_ms)
            selectors.detect_block(page)
            # Earlier readiness can become stale while waiting for the other control.
            for selector in (selectors.AUTHENTICATED_HOME, selectors.START_POST):
                if not selectors.unique_locator(page, selector).is_visible():
                    raise AgentError('dom_timeout', 'LinkedIn feed controls are no longer visible.')
            return {'connected': True, 'authenticated': True}
        finally:
            self.close_page(page)
