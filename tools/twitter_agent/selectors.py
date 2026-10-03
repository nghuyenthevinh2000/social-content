"""Block/challenge detection and waiting for X; identifiers live in dom.py."""

from typing import Optional
from . import dom
from .models import AgentError


def detect_block(page) -> Optional[AgentError]:
    """Check for visible challenges, login walls, rate limits, or account blocks."""
    try:
        # Check login walls
        if page.locator(dom.LOGIN_BUTTON).count() > 0 or page.locator(dom.LOGIN_LINK).count() > 0:
            return AgentError('not_authenticated', 'Not logged in to X.', human_action_required=True)

        # Check challenges / captchas
        if page.locator(dom.CHALLENGE_CONTAINER).count() > 0 or page.locator(dom.ARKOSE_IFRAME).count() > 0:
            return AgentError('browser_challenge', 'X challenge detected: manual intervention required.', human_action_required=True)

        # Check text-based blocks
        content = page.content().lower()
        if 'account suspended' in content:
            return AgentError('account_blocked', 'Account suspended on X.', human_action_required=True)
        if 'your account has been locked' in content:
            return AgentError('account_blocked', 'Account locked on X.', human_action_required=True)
        if 'rate limit exceeded' in content or 'try again later' in content:
            return AgentError('rate_limited', 'X rate limit detected.', human_action_required=False)
    except Exception:
        pass
    return None


def wait_for_selector_or_block(page, selector: str, timeout_ms: int = 10000):
    """Wait for selector; detect known blocks first and classify unknown timeout as dom_timeout."""
    block = detect_block(page)
    if block:
        raise block

    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
    except Exception as exc:
        block = detect_block(page)
        if block:
            raise block
        raise AgentError('dom_timeout', f'Timed out waiting for {selector}.') from exc
