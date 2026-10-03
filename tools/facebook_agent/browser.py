"""Connect to existing Chrome, preserving user tabs and the browser process."""

from playwright.sync_api import sync_playwright

from tools.social_agent.browser import CDPBrowser
from .models import AgentError
from .posting import inspect_profile


class Browser(CDPBrowser):
    """Facebook browser session backed by shared CDP foundation."""

    def __init__(self, endpoint: str = 'http://127.0.0.1:9222', timeout_ms: int = 30000):
        super().__init__(endpoint=endpoint, timeout_ms=timeout_ms)
        self.keep_page = False
        self._single_page = None

    def __enter__(self):
        super().connect()
        self._single_page = self.new_page()
        self._single_page.bring_to_front()
        return self

    @property
    def page(self):
        return self._single_page

    def check_authenticated(self) -> dict:
        """Verify that an account is already logged in with a personal profile.

        Navigates through /me, validating that the user is authenticated and has
        an active, editable personal profile (not a Page, Group, or login screen).

        Returns:
            dict with profile 'name' and 'url'.

        Raises:
            AgentError('not_authenticated'): If not logged into Facebook.
            AgentError('browser_challenge'): If Facebook presents a checkpoint/2FA.
            AgentError('account_restricted'): If the account is restricted.
            AgentError('not_personal_profile'): If logged into a Page or Group.
        """
        return inspect_profile(self.page, self.timeout_ms)

    def is_authenticated(self) -> bool:
        """Check if an account is already logged into Facebook without raising on failure."""
        try:
            self.check_authenticated()
            return True
        except AgentError:
            return False

    def doctor(self) -> dict:
        """Check CDP connectivity, authentication, and personal profile readiness."""
        profile = self.check_authenticated()
        return {
            'connected': True,
            'authenticated': True,
            'profile': profile,
            'endpoint': self.endpoint,
        }

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.keep_page and self._single_page:
            self.preserve_page(self._single_page)
        super().__exit__(exc_type, exc_val, exc_tb)
