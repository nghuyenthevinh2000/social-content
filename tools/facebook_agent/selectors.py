"""English accessibility selectors; fail closed when Facebook changes its DOM."""

import re
from urllib.parse import urlparse

from .models import AgentError


COMPOSER_TRIGGER = re.compile(r"^(What's on your mind|Write something)", re.I)
AUDIENCE = re.compile(r'^(Edit privacy|Public|Friends(?: except.*)?|Only me|Custom|Specific friends)(?:\b|$)', re.I)
SUCCESS = re.compile(r'^(?:Your post (?:has been shared|was shared|has been published)|Post (?:shared|published))[.!]?$', re.I)


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
    if '/login' in parsed.path.lower() or visible(page.locator('input[name="pass"]')).count():
        raise AgentError('not_authenticated', 'Log into Facebook manually in chrome-twitter-profile.', True)
    restricted = page.get_by_role('dialog').filter(has_text=re.compile(
        r"temporarily blocked|account (?:has been )?(?:restricted|disabled)|confirm (?:your )?identity", re.I))
    if visible(restricted).count():
        raise AgentError('account_restricted', 'Facebook requires manual account attention.', True)
