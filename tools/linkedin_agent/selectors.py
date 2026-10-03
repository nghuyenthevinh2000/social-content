"""Fail-closed readiness and block checks; identifiers live in dom.py."""

from urllib.parse import urlsplit

from . import dom
from .models import AgentError


def detect_block(page):
    """Raise structured errors for login and checkpoints; never bypass either."""
    path = urlsplit(page.url).path.lower()
    if (path.startswith('/checkpoint/') or path == '/checkpoint'
            or page.locator(dom.CHECKPOINT_FORM).count() > 0
            or any(frame.is_visible() for frame in page.locator(dom.CHALLENGE_FRAME).all())):
        raise AgentError(
            'browser_challenge', 'LinkedIn checkpoint detected. Complete it manually in Chrome.',
            human_action_required=True,
        )
    login = page.locator(dom.LOGIN_FORM)
    if (path in ('/login', '/uas/login', '/authwall')
            or any(login.nth(index).is_visible() for index in range(login.count()))):
        raise AgentError(
            'not_authenticated', 'Log into LinkedIn manually in the shared Chrome profile.',
            human_action_required=True,
        )


def unique_locator(page, selector: str):
    """Return exactly one match; never silently select the first ambiguous control."""
    locator = page.locator(selector)
    count = locator.count()
    if count > 1:
        raise AgentError('ambiguous_selector', 'Multiple LinkedIn controls matched; inspect the page manually.')
    if count == 0:
        raise AgentError('dom_timeout', 'Expected LinkedIn control was not found.')
    return locator


def wait_for_selector_or_block(page, selector: str, timeout_ms: int = 15000):
    """Wait for one visible control, checking blocks before and after the wait."""
    detect_block(page)
    if page.locator(selector).count() > 1:
        return unique_locator(page, selector)
    try:
        page.locator(selector).wait_for(state='visible', timeout=timeout_ms)
    except Exception as exc:
        detect_block(page)
        if page.locator(selector).count() > 1:
            return unique_locator(page, selector)
        raise AgentError('dom_timeout', 'Timed out waiting for LinkedIn feed controls.') from exc
    detect_block(page)
    return unique_locator(page, selector)
