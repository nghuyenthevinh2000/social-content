"""Platform-independent CDP connection and safe client disconnection.

Guarantees:
- Safe disconnection: detaches the client without calling browser.close() or context.close().
- User tab preservation: user tabs, contexts, and Chrome processes are never closed.
- Automatic cleanup: Playwright client is safely stopped on both success and failure.
- Tab management: supports tracking, closing, and preserving tool-created tabs.
"""

import sys
from typing import List, Optional

from .config import AgentError as DefaultAgentError, get_config


class CDPBrowser:
    """Platform-independent browser connection over Chrome DevTools Protocol (CDP)."""

    def __init__(self, endpoint: Optional[str] = None, timeout_ms: Optional[int] = None):
        cfg = get_config(endpoint=endpoint, timeout_ms=timeout_ms)
        self.endpoint = cfg.endpoint
        self.timeout_ms = cfg.doctor_timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._created_pages: List = []

    @property
    def _agent_error_class(self):
        mod = sys.modules.get(self.__class__.__module__)
        return getattr(mod, 'AgentError', DefaultAgentError)

    @property
    def _playwright_factory(self):
        mod = sys.modules.get(self.__class__.__module__)
        mod_factory = getattr(mod, 'sync_playwright', None)
        import playwright.sync_api
        ps_factory = playwright.sync_api.sync_playwright
        if mod_factory is not None and mod_factory is not ps_factory:
            return mod_factory
        return ps_factory

    def __enter__(self):
        return self.connect()

    def connect(self) -> 'CDPBrowser':
        """Connect to an existing Chromium instance via CDP.

        Raises:
            AgentError('browser_connection_failed'): If Chrome cannot be reached.
            AgentError('no_browser_context'): If Chrome has no open browser context/tab.
        """
        factory = self._playwright_factory
        err_cls = self._agent_error_class

        try:
            self._playwright = factory().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.endpoint, timeout=self.timeout_ms
            )
        except Exception as exc:
            self.disconnect()
            raise err_cls(
                'browser_connection_failed',
                'Cannot connect to Chrome. Check the configured CDP endpoint and launch the shared profile.',
                human_action_required=True,
            ) from exc

        if not self._browser.contexts:
            self.disconnect()
            raise err_cls(
                'no_browser_context',
                'Chrome has no open browser contexts. Open at least one tab.',
                human_action_required=True,
            )

        self._context = self._browser.contexts[0]
        return self

    @property
    def browser(self):
        """The connected Playwright browser object."""
        return self._browser

    @property
    def contexts(self) -> list:
        """List of active browser contexts in user Chrome."""
        if self._browser is None:
            return []
        return list(self._browser.contexts)

    @property
    def context(self):
        """The primary browser context if connected."""
        return self._context

    @property
    def version(self) -> str:
        """Reported Chromium browser version."""
        if self._browser is None:
            return ''
        return getattr(self._browser, 'version', '')

    def new_page(self):
        """Create a new temporary page owned by this connection."""
        if self._context is None:
            raise self._agent_error_class('browser_not_connected', 'Browser is not connected.')
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

    @property
    def page(self):
        """Current temporary page or create a new page if none exists."""
        if not self._created_pages:
            return self.new_page()
        return self._created_pages[-1]

    def disconnect(self):
        """Safely detach client without closing user Chrome, contexts, or unmanaged tabs."""
        if self._playwright is not None:
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
        self.disconnect()


Browser = CDPBrowser
