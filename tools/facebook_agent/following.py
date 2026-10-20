"""Follow one explicitly approved creator, with identity and post-click checks."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .browser import Browser
from .models import AgentError
from .reels import SNAPSHOT, reel_url
from . import selectors


def validate_profile_url(url):
    parsed = urlparse(url or '')
    path = parsed.path.strip('/')
    if (parsed.scheme != 'https' or parsed.hostname not in ('www.facebook.com', 'facebook.com')
            or parsed.username or parsed.password or parsed.port
            or not re.fullmatch(r'[A-Za-z0-9.]+', path)
            or path.lower() in ('me', 'reel', 'reels', 'watch', 'groups', 'pages', 'login', 'profile.php', 'settings', 'home.php')):
        raise AgentError('invalid_arguments', 'Expected an HTTPS Facebook vanity profile URL.')
    return f'https://www.facebook.com/{path}'


def follow_creator(args):
    direct_url = validate_profile_url(args.profile_url) if args.profile_url else None
    if not args.approved or (not direct_url and (not args.creator or not args.creator.strip() or reel_url(args.reel) is None)):
        raise AgentError('invalid_arguments', 'Provide --approved and a profile URL, or an exact creator name and Reel URL.')
    if not args.page_id.isascii() or not args.page_id.isdecimal():
        raise AgentError('invalid_arguments', 'Expected Page ID must contain ASCII digits only.')
    output = Path(args.output)
    if output.exists():
        raise AgentError('invalid_arguments', 'Choose a new output file; existing follow records are preserved.')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {'creator': args.creator, 'reel': reel_url(args.reel) if args.reel else None, 'expected_page_id': args.page_id,
              'status': 'not_started', 'clicked': False,
              'observed_at': datetime.now(timezone.utc).isoformat()}
    with output.open('x', encoding='utf-8') as stream:
        def save():
            stream.seek(0)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.truncate()
            stream.flush()

        save()
        try:
            with Browser(endpoint=args.cdp, timeout_ms=args.timeout_ms or 30000) as browser:
                result['acting_profile'] = browser.check_authenticated(page_id=args.page_id)
                browser.keep_page = True
                page = browser.page
                if direct_url:
                    href = direct_url
                else:
                    page.goto(result['reel'], wait_until='domcontentloaded')
                    page.wait_for_timeout(3500)
                    result['reel_snapshot'] = page.evaluate(SNAPSHOT)
                    selectors.check_block(page)
                    links = {link['url'] for link in result['reel_snapshot']['links']
                             if link['text'].strip() == args.creator.strip()}
                    if len(links) != 1:
                        raise AgentError('ambiguous_dom', 'Cannot uniquely identify the expected Reel creator profile.', True)
                    href = links.pop()
                parsed = urlparse(href or '')
                if parsed.hostname not in ('www.facebook.com', 'facebook.com'):
                    raise AgentError('unexpected_destination', 'Creator link is not a Facebook profile.', True)
                result['creator_url'] = href
                page.goto(href, wait_until='domcontentloaded')
                page.wait_for_timeout(3500)
                result['profile_snapshot'] = page.evaluate(SNAPSHOT)
                selectors.check_block(page)
                if direct_url and validate_profile_url(page.url).lower() != direct_url.lower():
                    raise AgentError('unexpected_destination', 'Profile URL changed to a different identity; inspect manually.', True)
                lines = result['profile_snapshot']['text'].splitlines()
                if not lines or (args.creator and lines[0].strip() != args.creator.strip()):
                    raise AgentError('ambiguous_dom', 'Creator profile title does not match the expected name.', True)
                result['creator'] = args.creator or lines[0].strip()
                following = page.locator('[role="button"][aria-label="Following"],button[aria-label="Following"]')
                follow = page.locator('[role="button"][aria-label="Follow"],button[aria-label="Follow"]')
                page.wait_for_timeout(1500)
                if selectors.visible(following).count() == 1:
                    result['status'] = 'already_following'
                else:
                    selectors.unique(follow, 'creator profile Follow button')
                    # Mark the click attempt before dispatch; never retry an uncertain mutation.
                    result['status'] = 'uncertain'
                    result['clicked'] = True
                    save()
                    selectors.unique(follow, 'creator profile Follow button').click()
                    try:
                        selectors.visible(following).first.wait_for(state='visible', timeout=10000)
                        selectors.unique(following, 'creator profile Following confirmation')
                        result['status'] = 'confirmed'
                    except PlaywrightTimeout:
                        result['status'] = 'uncertain'
                result['after_snapshot'] = page.evaluate(SNAPSHOT)
                result['confirmation'] = 'Following button visible on creator profile' if result['status'] in ('confirmed', 'already_following') else None
                result['browser_url'] = page.url
        except Exception as exc:
            result['status'] = 'uncertain' if result['clicked'] else 'failed'
            result['error'] = str(exc)
        save()
    return {**{key: value for key, value in result.items() if not key.endswith('_snapshot')},
            'output': str(output)}
