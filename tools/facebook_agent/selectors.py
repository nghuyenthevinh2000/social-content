"""Visibility, uniqueness, and account safety checks; identifiers live in dom.py."""

from urllib.parse import urlparse

from . import dom
from .models import AgentError


def visible(locator):
    """Retain visibility without accepting the first ambiguous DOM match."""
    # Locator.and_ predates 1.50; filter(visible=...) requires 1.51.
    return locator.and_(locator.page.locator(':visible'))


def unique(locator, description: str):
    locator = visible(locator)
    if locator.count() != 1:
        raise AgentError('ambiguous_dom', f'Expected one visible {description}; found {locator.count()}.', True)
    return locator


def check_block(page):
    parsed = urlparse(page.url)
    if parsed.hostname not in ('www.facebook.com', 'facebook.com'):
        raise AgentError('unexpected_destination', 'Browser left Facebook.', True)
    if any(part in parsed.path.lower() for part in ('checkpoint', 'challenge', 'two_step_verification')):
        raise AgentError('browser_challenge', 'Complete the Facebook challenge manually.', True)
    if '/login' in parsed.path.lower() or visible(dom.login_password_input(page)).count():
        raise AgentError('not_authenticated', 'Log into Facebook manually in chrome-twitter-profile.', True)
    restricted = dom.account_restriction_dialog(page)
    if visible(restricted).count():
        raise AgentError('account_restricted', 'Facebook requires manual account attention.', True)
