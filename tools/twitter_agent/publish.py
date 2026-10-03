"""Publish one explicitly approved standalone image post via the existing CDP browser.

Run as ``python -m tools.twitter_agent.publish --help``. Never retries a submit.
No separate supervisor terminal is required.
"""

import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from . import dom, selectors
from .browser import Browser
from .models import AgentError, Limits, validate_text
from .pacing import get_pacer
from .store import Store


def reserve_attempt(store: Store, detail: dict) -> None:
    """Atomically enforce the shared quotas and record approval before clicking."""
    store._require_lock()
    with store._transaction() as db:
        if store._setting(db, 'paused'):
            raise AgentError('paused', 'Submissions are paused.')
        now = store.clock()
        limits = Limits(**store._setting(db, 'limits'))
        attempts = db.execute('''SELECT
            COUNT(CASE WHEN created_at > ? THEN 1 END) AS burst,
            COUNT(CASE WHEN created_at > ? THEN 1 END) AS hourly,
            COUNT(CASE WHEN created_at > ? THEN 1 END) AS daily,
            MAX(created_at) AS latest
            FROM events WHERE kind = 'submission_started' ''',
                              (now - 1800, now - 3600, now - 86400)).fetchone()
        if (attempts['hourly'] >= limits.hourly or attempts['daily'] >= limits.daily
                or attempts['burst'] >= limits.burst_max
                or (attempts['latest'] is not None
                    and now - attempts['latest'] < limits.spacing)):
            raise AgentError('rate_limited', 'Submission quota or minimum spacing reached.')
        store._event(db, 'approval', None, detail, now)
        store._event(db, 'submission_started', None, detail, now)


def verify_response(payload: dict, text: str) -> dict:
    """Verify the returned tweet, allowing only X's appended media shortlink."""
    tweet = payload.get('data', {}).get('create_tweet', {}).get('tweet_results', {}).get('result', {})
    if tweet.get('__typename') == 'TweetWithVisibilityResults':
        tweet = tweet.get('tweet', {})
    post_id = tweet.get('rest_id', '')
    legacy = tweet.get('legacy', {})
    media = legacy.get('extended_entities', {}).get('media', [])
    actual = legacy.get('full_text')
    valid_text = actual == text
    if len(media) == 1 and media[0].get('url'):
        valid_text = valid_text or actual == text + ' ' + media[0]['url']
    if (not isinstance(post_id, str) or not post_id.isascii() or not post_id.isdigit()
            or not valid_text or len(media) != 1 or media[0].get('type') != 'photo'):
        raise AgentError('confirmation_failed', 'Could not verify the published text and photo. Do not retry automatically.')
    return {'state': 'submitted', 'url': f'https://x.com/i/status/{post_id}',
            'text_verified': True, 'image_count': 1}


def publish(text: str, image: Path, store: Store, endpoint: str,
            expected_handle: str, approved: bool = False) -> dict:
    if not approved:
        raise AgentError('approval_required', 'Explicit approval of this exact text and image is required.', True)
    validate_text(text)
    image = image.expanduser().resolve(strict=True)
    image_bytes = image.read_bytes()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    expected_handle = expected_handle.lstrip('@')
    if not expected_handle or not all(c.isascii() and (c.isalnum() or c == '_') for c in expected_handle):
        raise AgentError('invalid_account', 'Expected an X account handle.')

    with store.submission_lock(), Browser(endpoint=endpoint) as browser:
        page = browser.new_page()
        get_pacer().wait('navigation')
        page.goto('https://x.com/compose/post', wait_until='domcontentloaded')
        page.locator(dom.SUBMIT_BUTTON).wait_for(state='visible')
        block = selectors.detect_block(page)
        if block:
            raise block
        profile = page.locator(dom.PROFILE_LINK).get_attribute('href') or ''
        if urlsplit(profile).path.lower() != '/' + expected_handle.lower():
            raise AgentError('account_mismatch', 'The logged-in account does not match --account.', True)
        dialog = page.locator(dom.COMPOSER_DIALOG).filter(
            has=page.locator(dom.SUBMIT_BUTTON)).last
        textarea = dialog.locator(dom.COMPOSER_TEXTAREA).first
        textarea.fill(text)
        # Upload exactly the bytes whose hash is bound to the approval.
        dialog.locator(dom.FILE_INPUT).set_input_files({
            'name': image.name, 'mimeType': mimetypes.guess_type(image.name)[0] or 'application/octet-stream',
            'buffer': image_bytes,
        })
        dialog.locator(dom.ATTACHMENTS).wait_for(state='visible')
        button = dialog.locator(dom.SUBMIT_BUTTON)
        page.wait_for_function('''selector => {
            const b = document.querySelector(selector);
            return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true';
        }''', arg=dom.SUBMIT_BUTTON)
        if (textarea.inner_text() != text
                or dialog.locator(dom.ATTACHED_IMAGES).count() != 1
                or not button.is_enabled()):
            raise AgentError('review_changed', 'Composer text, photo, or submit button changed.')
        block = selectors.detect_block(page)
        if block:
            raise block
        detail = {'type': 'standalone_image_post', 'account': expected_handle, 'text': text,
                  'image': str(image), 'image_sha256': image_hash,
                  'approval': 'Caller explicitly approved exact text and image'}
        reserve_attempt(store, detail)
        try:
            with page.expect_response(
                    lambda r: urlsplit(r.url).hostname == 'x.com'
                    and urlsplit(r.url).path.endswith('/CreateTweet')
                    and r.request.method == 'POST', timeout=20000) as response:
                button.click()  # At most once, even if confirmation fails.
            outcome = verify_response(response.value.json(), text)
        except Exception as exc:
            outcome = {'state': 'uncertain', 'error': str(exc), 'retry': False}
        store.event('standalone_post_' + outcome['state'], None, outcome)
        return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text', required=True, help='Exact approved post text')
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--account', required=True, help='Expected logged-in handle')
    parser.add_argument('--approved', action='store_true', help='Confirm explicit approval of this text and image')
    parser.add_argument('--endpoint', default='http://127.0.0.1:9222')
    parser.add_argument('--state-dir', type=Path, default=Path('.twitter-agent'))
    args = parser.parse_args()
    try:
        # Reject missing approval without creating state or connecting to Chrome.
        if not args.approved:
            raise AgentError('approval_required', 'Use --approved only after explicit approval of the text and image.', True)
        outcome = publish(args.text, args.image, Store(args.state_dir), args.endpoint,
                          args.account, args.approved)
        print(json.dumps({'ok': outcome['state'] == 'submitted', 'data': outcome}, ensure_ascii=False))
        return 0 if outcome['state'] == 'submitted' else 4
    except (AgentError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': {
            'code': getattr(exc, 'code', 'file_error'), 'message': str(exc),
            'human_action_required': getattr(exc, 'human_action_required', False),
        }}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
