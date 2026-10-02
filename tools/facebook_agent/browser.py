"""Connect to existing Chrome, preserving user tabs and the browser process."""

from playwright.sync_api import sync_playwright

from .models import AgentError


class Browser:
    def __init__(self, endpoint: str = 'http://127.0.0.1:9222', timeout_ms: int = 15000):
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._page = None
        self.keep_page = False

    def __enter__(self):
        try:
            self._playwright = sync_playwright().start()
            browser = self._playwright.chromium.connect_over_cdp(self.endpoint, timeout=self.timeout_ms)
            if not browser.contexts:
                raise AgentError('browser_connection_failed', 'Chrome has no existing browser context.', True)
            self._page = browser.contexts[0].new_page()
            self._page.set_default_timeout(self.timeout_ms)
            self._page.bring_to_front()
            return self
        except Exception as exc:
            self.__exit__(None, None, None)
            if isinstance(exc, AgentError):
                raise
            raise AgentError('browser_connection_failed', f'Cannot connect to Chrome CDP at {self.endpoint}: {exc}', True) from exc

    @property
    def page(self):
        return self._page

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if self._page is not None and not self.keep_page:
                self._page.close()
        finally:
            if self._playwright is not None:
                # Do not close the CDP browser or context: both belong to the user.
                self._playwright.stop()
