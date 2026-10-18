"""Platform-independent browser connection, invisible stealth engine, and safe client disconnection.

Guarantees:
- Stealth browsing: supports invisible_playwright anti-detect browser with humanized pointer motion and fingerprint seeds.
- Safe disconnection: detaches the client without calling browser.close() or context.close().
- User tab preservation: user tabs, contexts, and Chrome processes are never closed.
- Automatic cleanup: Playwright client is safely stopped on both success and failure.
- Tab management: supports tracking, closing, and preserving tool-created tabs.
"""

import os
from pathlib import Path
import sys
from typing import List, Optional, Union

from .config import AgentError as DefaultAgentError, get_config


class BaseBrowser:
    """Base browser session managing pages, contexts, and clean detachment."""

    def __init__(self):
        self._browser = None
        self._context = None
        self._created_pages: List = []

    @property
    def _agent_error_class(self):
        mod = sys.modules.get(self.__class__.__module__)
        return getattr(mod, 'AgentError', DefaultAgentError)

    def __enter__(self):
        return self.connect()

    def connect(self):
        raise NotImplementedError

    @property
    def browser(self):
        """The connected Playwright browser object."""
        return self._browser

    @property
    def contexts(self) -> list:
        """List of active browser contexts."""
        if self._browser is not None:
            return list(self._browser.contexts)
        if self._context is not None:
            return [self._context]
        return []

    @property
    def context(self):
        """The primary browser context if connected."""
        return self._context

    @property
    def version(self) -> str:
        """Reported browser version."""
        if self._browser is not None:
            return getattr(self._browser, 'version', '')
        if self._context is not None:
            b = getattr(self._context, 'browser', None)
            if b is not None:
                return getattr(b, 'version', '')
        return ''

    def new_page(self):
        """Create a new temporary page owned by this connection."""
        if self._context is None:
            raise self._agent_error_class('browser_not_connected', 'Browser is not connected.')
        page = self._context.new_page()
        self._created_pages.append(page)
        timeout_ms = getattr(self, 'timeout_ms', None)
        if timeout_ms is not None:
            page.set_default_timeout(timeout_ms)
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
        raise NotImplementedError

    def __exit__(self, exc_type, exc_val, exc_tb):
        for page in list(self._created_pages):
            self.close_page(page)
        self.disconnect()


class InvisibleBrowser(BaseBrowser):
    """Anti-detect stealth browser session powered by invisible_playwright_mcp."""

    def __init__(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        seed: Optional[int] = None,
        headless: Optional[bool] = None,
        proxy: Optional[Union[str, dict]] = None,
        binary_path: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        endpoint: Optional[str] = None,
        fallback_to_cdp: bool = True,
        **kwargs,
    ):
        super().__init__()
        cfg = get_config(
            data_dir=data_dir,
            seed=seed,
            headless=headless,
            proxy=proxy if isinstance(proxy, str) else None,
            binary_path=binary_path,
            timeout_ms=timeout_ms,
            endpoint=endpoint,
            backend='invisible',
        )
        self.backend = 'invisible'
        self.user_data_dir = cfg.user_data_dir
        self.seed = cfg.seed
        self.headless = cfg.headless
        self.proxy = proxy if isinstance(proxy, dict) else cfg.proxy
        self.binary_path = cfg.binary_path
        self.timeout_ms = cfg.doctor_timeout_ms
        self.endpoint = cfg.endpoint
        self.fallback_to_cdp = fallback_to_cdp
        self._ipw = None
        self._cdp_fallback = None

    @property
    def _ipw_factory(self):
        mod = sys.modules.get(self.__class__.__module__)
        factory = getattr(mod, 'InvisiblePlaywright', None)
        if factory is not None:
            return factory
        try:
            from invisible_playwright import InvisiblePlaywright
            return InvisiblePlaywright
        except ImportError:
            try:
                from invisible_playwright_mcp.mcp.session import InvisiblePlaywright
                return InvisiblePlaywright
            except ImportError:
                return None

    @property
    def version(self) -> str:
        ver = super().version
        if ver:
            return ver
        try:
            import invisible_playwright
            return f'invisible-firefox/{invisible_playwright.__version__}'
        except Exception:
            return 'invisible-firefox'

    def connect(self) -> 'InvisibleBrowser':
        err_cls = self._agent_error_class
        factory = self._ipw_factory
        if factory is None:
            raise err_cls(
                'invisible_browser_not_installed',
                "Package 'invisible-playwright' is not installed. Install via uv pip.",
                human_action_required=True,
            )

        kwargs = {
            'headless': self.headless,
        }
        if self.seed is not None:
            kwargs['seed'] = self.seed
        if self.user_data_dir:
            kwargs['profile_dir'] = Path(self.user_data_dir)
        if self.binary_path:
            kwargs['binary_path'] = self.binary_path
        if self.proxy:
            if isinstance(self.proxy, str):
                try:
                    from invisible_playwright_mcp.mcp.proxy import proxy_from_url
                    kwargs['proxy'] = proxy_from_url(self.proxy)
                except Exception:
                    kwargs['proxy'] = {'server': self.proxy}
            else:
                kwargs['proxy'] = self.proxy

        try:
            self._ipw = factory(**kwargs)
            result = self._ipw.__enter__()
            if hasattr(result, 'new_context'):
                self._browser = result
                self._context = result.new_context()
            else:
                self._context = result
                self._browser = getattr(result, 'browser', None)
            return self
        except NotImplementedError as exc:
            if self.fallback_to_cdp:
                return self._activate_cdp_fallback()
            raise err_cls(
                'invisible_browser_unsupported',
                f'Invisible browser engine is not supported on this platform: {exc}. '
                f'Pass binary_path or use backend="cdp".',
                human_action_required=True,
            ) from exc
        except Exception as exc:
            self.disconnect()
            raise err_cls(
                'invisible_browser_start_failed',
                f'Failed to start invisible browser: {exc}',
                human_action_required=True,
            ) from exc

    def _activate_cdp_fallback(self) -> 'InvisibleBrowser':
        self._cdp_fallback = CDPBrowser(endpoint=self.endpoint, timeout_ms=self.timeout_ms)
        self._cdp_fallback.connect()
        self._browser = self._cdp_fallback.browser
        self._context = self._cdp_fallback.context
        self.backend = 'cdp'
        return self

    def disconnect(self):
        if self._cdp_fallback is not None:
            self._cdp_fallback.disconnect()
            self._cdp_fallback = None
        if self._ipw is not None:
            try:
                self._ipw.__exit__(None, None, None)
            except Exception:
                pass
            self._ipw = None
        self._browser = None
        self._context = None


class CDPBrowser(BaseBrowser):
    """Platform-independent browser connection over Chrome DevTools Protocol (CDP) or invisible engine."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        backend: Optional[str] = None,
        data_dir: Optional[Union[str, Path]] = None,
        seed: Optional[int] = None,
        headless: Optional[bool] = None,
        proxy: Optional[Union[str, dict]] = None,
        binary_path: Optional[str] = None,
    ):
        super().__init__()
        cfg = get_config(
            endpoint=endpoint,
            timeout_ms=timeout_ms,
            backend=backend,
            data_dir=data_dir,
            seed=seed,
            headless=headless,
            proxy=proxy if isinstance(proxy, str) else None,
            binary_path=binary_path,
        )
        self.endpoint = cfg.endpoint
        self.timeout_ms = cfg.doctor_timeout_ms
        if backend is not None or os.environ.get('BROWSER_BACKEND') or os.environ.get('BROWSER_TYPE'):
            self.backend = cfg.backend
        else:
            self.backend = 'cdp'
        self.cfg = cfg
        self._playwright = None
        self._invisible_delegate = None

    @property
    def _playwright_factory(self):
        mod = sys.modules.get(self.__class__.__module__)
        mod_factory = getattr(mod, 'sync_playwright', None)
        import playwright.sync_api
        ps_factory = playwright.sync_api.sync_playwright
        if mod_factory is not None and mod_factory is not ps_factory:
            return mod_factory
        return ps_factory

    def connect(self) -> 'CDPBrowser':
        """Connect to invisible browser or Chromium over CDP."""
        if self.backend == 'invisible':
            self._invisible_delegate = InvisibleBrowser(
                data_dir=self.cfg.user_data_dir,
                seed=self.cfg.seed,
                headless=self.cfg.headless,
                proxy=self.cfg.proxy,
                binary_path=self.cfg.binary_path,
                timeout_ms=self.timeout_ms,
                endpoint=self.endpoint,
            )
            self._invisible_delegate.connect()
            self._browser = self._invisible_delegate.browser
            self._context = self._invisible_delegate.context
            return self

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

    def disconnect(self):
        """Safely detach client without closing user Chrome, contexts, or unmanaged tabs."""
        if self._invisible_delegate is not None:
            self._invisible_delegate.disconnect()
            self._invisible_delegate = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._browser = None
        self._context = None


Browser = InvisibleBrowser
