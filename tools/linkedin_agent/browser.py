"""Independent LinkedIn CDP lifecycle; disconnect without closing user Chrome."""

from .models import AgentError
from . import selectors


class Browser:
    def __init__(self, endpoint: str = 'http://127.0.0.1:9222', timeout_ms: int = 15000):
        if timeout_ms <= 0:
            raise AgentError('invalid_timeout', 'Browser timeout must be positive.')
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._created_pages = []

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.endpoint, timeout=self.timeout_ms
            )
        except Exception as exc:
            self._disconnect()
            raise AgentError(
                'browser_connection_failed',
                'Cannot connect to Chrome. Check the configured CDP endpoint and launch the shared profile.',
                human_action_required=True,
            ) from exc
        if not self._browser.contexts:
            self._disconnect()
            raise AgentError(
                'no_browser_context', 'Chrome has no browser context. Open at least one tab.',
                human_action_required=True,
            )
        self._context = self._browser.contexts[0]
        return self

    def _disconnect(self):
        # Playwright stop detaches this client; browser.close() would close user Chrome.
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._playwright = None
        self._browser = None
        self._context = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        for page in list(self._created_pages):
            self.close_page(page)
        self._disconnect()

    def new_page(self):
        if self._context is None:
            raise AgentError('browser_not_connected', 'Browser is not connected.')
        page = self._context.new_page()
        self._created_pages.append(page)
        page.set_default_timeout(self.timeout_ms)
        return page

    def preserve_page(self, page):
        """Leave this tool-created tab open when detaching, for human inspection."""
        self._created_pages = [owned for owned in self._created_pages if owned is not page]

    def close_page(self, page):
        """Close only a temporary tab owned by this connection."""
        if not any(owned is page for owned in self._created_pages):
            return
        try:
            page.close()
        except Exception:
            pass
        self.preserve_page(page)

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
