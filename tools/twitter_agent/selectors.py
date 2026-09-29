"""Centralized DOM selectors and block/challenge detection for X."""

import re
from typing import Optional
from .models import AgentError

ARTICLE = 'article[data-testid="tweet"]'
AUTHOR = '[data-testid="User-Name"]'
TWEET_TEXT = '[data-testid="tweetText"]'
TIMESTAMP_LINK = 'a[href*="/status/"]'
REPLY_BUTTON = '[data-testid="reply"]'
COMPOSER_DIALOG = '[role="dialog"]'
COMPOSER_TEXTAREA = '[data-testid="tweetTextarea_0"]'
SUBMIT_BUTTON = '[data-testid="tweetButton"]'
SUBMIT_BUTTON_INLINE = '[data-testid="tweetButtonInline"]'
LOGIN_BUTTON = '[data-testid="loginButton"]'
LOGIN_LINK = 'a[href="/login"]'
AUTHENTICATED_HOME = '[data-testid="AppTabBar_Home_Link"]'
ACCOUNT_SWITCHER = '[data-testid="SideNav_AccountSwitcher_Button"]'

# Challenge / block selectors
CHALLENGE_CONTAINER = '[data-testid="challenge"]'
ARKOSE_IFRAME = 'iframe[src*="arkoselabs"], iframe[title*="challenge"]'
EMPTY_STATE = '[data-testid="emptyState"]'


def detect_block(page) -> Optional[AgentError]:
    """Check for visible challenges, login walls, rate limits, or account blocks."""
    try:
        # Check login walls
        if page.locator(LOGIN_BUTTON).count() > 0 or page.locator(LOGIN_LINK).count() > 0:
            return AgentError('not_authenticated', 'Not logged in to X.', human_action_required=True)

        # Check challenges / captchas
        if page.locator(CHALLENGE_CONTAINER).count() > 0 or page.locator(ARKOSE_IFRAME).count() > 0:
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
