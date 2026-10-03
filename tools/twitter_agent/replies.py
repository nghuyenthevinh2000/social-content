"""Prepare, inspect, and submit browser interactions for replies."""

from pathlib import Path
import re
import time
from typing import Optional, Set

from .models import AgentError, draft_digest
from .pacing import get_pacer
from . import dom, selectors


def _find_target_article(page, target_id: str):
    """Find the specific top-level article matching target_id, excluding quotes."""
    articles = page.locator(dom.ARTICLE).all()
    target_id_str = str(target_id).lstrip('0')
    for article in articles:
        # Check status links inside article
        links = article.locator(dom.TIMESTAMP_LINK).all()
        for link in links:
            # Check if this link is inside a quoted tweet
            is_quoted = link.evaluate("""
                (el, quoteTweet) => {
                    let parent = el.parentElement;
                    while (parent && parent.tagName.toLowerCase() !== 'article') {
                        if (parent.getAttribute('role') === 'link' || parent.matches(quoteTweet)) {
                            return true;
                        }
                        parent = parent.parentElement;
                    }
                    return false;
                }
            """, dom.QUOTE_TWEET)
            if is_quoted:
                continue
            href = link.get_attribute('href') or ''
            match = re.search(r'/status/([0-9]+)', href)
            if match and match.group(1).lstrip('0') == target_id_str:
                return article
    return None


def _get_signed_in_handle(page) -> Optional[str]:
    """Extract signed-in user's handle from the current page."""
    try:
        switcher = page.locator(dom.ACCOUNT_SWITCHER).first
        if switcher.count() > 0:
            text = switcher.inner_text()
            match = re.search(r'@[A-Za-z0-9_]+', text)
            if match:
                return match.group(0).lower()
    except Exception:
        pass
    return None


def _get_page_status_ids(page) -> Set[str]:
    """Get all status IDs currently visible on the page."""
    ids = set()
    try:
        links = page.locator(dom.TIMESTAMP_LINK).all()
        for link in links:
            href = link.get_attribute('href') or ''
            match = re.search(r'/status/([0-9]+)', href)
            if match:
                ids.add(match.group(1).lstrip('0'))
    except Exception:
        pass
    return ids


def prepare_reply(page, draft: dict, artifact_dir: Path) -> dict:
    """Navigate to target, locate exact post, open reply dialog, fill text, and capture screenshot."""
    current_url = getattr(page, 'url', '') or ''
    has_fixture = False
    if current_url == 'about:blank' or current_url.startswith('data:'):
        try:
            has_fixture = page.locator(dom.ARTICLE).count() > 0
        except Exception:
            pass

    if not has_fixture:
        block = selectors.detect_block(page)
        if block:
            raise block
        get_pacer().wait('navigation')
        page.goto(draft['target_url'], wait_until='domcontentloaded')
        page.wait_for_timeout(1000)

    # Locate target article
    target_article = _find_target_article(page, draft['target_id'])
    if target_article is None:
        raise AgentError('target_not_found', f"Target post {draft['target_id']} not found on page.")

    # Extract target text
    target_text = ''
    text_el = target_article.locator(dom.TWEET_TEXT).first
    if text_el.count() > 0:
        target_text = text_el.inner_text()

    target_author = ''
    author_el = target_article.locator(dom.AUTHOR).first
    if author_el.count() > 0:
        target_author = author_el.inner_text()

    # Click reply button on target article
    reply_btn = target_article.locator(dom.REPLY_BUTTON).first
    if reply_btn.count() == 0:
        raise AgentError('reply_button_not_found', 'Reply button not found for target post.')
    reply_btn.click()

    # Wait for composer dialog
    dialog = page.locator(dom.COMPOSER_DIALOG).first
    try:
        dialog.wait_for(state='visible', timeout=10000)
    except Exception as exc:
        raise AgentError('composer_dialog_missing', 'Composer dialog did not appear.') from exc

    # Locate contenteditable textarea
    textarea = dialog.locator(dom.COMPOSER_TEXTAREA).first
    try:
        textarea.wait_for(state='visible', timeout=5000)
    except Exception as exc:
        raise AgentError('composer_textarea_missing', 'Composer textarea not found in dialog.') from exc

    # Fill contenteditable
    textarea.click()
    textarea.fill(draft['text'])
    page.wait_for_timeout(300)

    actual_text = textarea.inner_text().strip('\r\n')

    # Capture before screenshot
    screenshot_path = artifact_dir / f"{draft['id']}_before.png"
    warning = None
    try:
        page.screenshot(path=str(screenshot_path))
    except Exception as exc:
        screenshot_path = None
        warning = f"Screenshot capture failed: {exc}"

    return {
        'target_id': draft['target_id'],
        'target_url': draft['target_url'],
        'target_author': target_author,
        'target_text': target_text,
        'reply_text': actual_text,
        'screenshot': str(screenshot_path) if screenshot_path else None,
        'warning': warning,
    }


def inspect_reply(page, draft: dict) -> str:
    """Verify target and composer identity, read composer text, check submit button, return digest."""
    # Check dialog
    dialog = page.locator(dom.COMPOSER_DIALOG).first
    if dialog.count() == 0 or not dialog.is_visible():
        raise AgentError('review_changed', 'Target or composer dialog is no longer available.')

    # Check submit button
    submit_btn = dialog.locator(dom.SUBMIT_BUTTON).first
    if submit_btn.count() == 0:
        submit_btn = dialog.locator(dom.SUBMIT_BUTTON_INLINE).first
    if submit_btn.count() == 0:
        raise AgentError('review_changed', 'Submit button not found in composer dialog.')

    if submit_btn.is_disabled() or submit_btn.get_attribute('aria-disabled') == 'true':
        raise AgentError('submit_disabled', 'Submit button is disabled.')

    # Check textarea text
    textarea = dialog.locator(dom.COMPOSER_TEXTAREA).first
    if textarea.count() == 0:
        raise AgentError('review_changed', 'Composer textarea missing.')

    current_text = textarea.inner_text().strip('\r\n')
    return draft_digest(draft['target_id'], current_text)


def submit_reply(page, draft: dict, artifact_dir: Path) -> dict:
    """Submit reply with exactly one click and verify DOM confirmation."""
    # Pre-submission observations
    existing_ids = _get_page_status_ids(page)
    user_handle = _get_signed_in_handle(page)

    # Final check of composer
    digest = inspect_reply(page, draft)
    if digest != draft['digest']:
        raise AgentError('review_changed', 'DOM state changed immediately before click.')

    dialog = page.locator(dom.COMPOSER_DIALOG).first
    submit_btn = dialog.locator(dom.SUBMIT_BUTTON).first
    if submit_btn.count() == 0:
        submit_btn = dialog.locator(dom.SUBMIT_BUTTON_INLINE).first

    # CLICK AT MOST ONCE
    submit_btn.click()

    # Capture after screenshot
    after_path = artifact_dir / f"{draft['id']}_after.png"
    try:
        page.screenshot(path=str(after_path))
    except Exception:
        after_path = None

    # Bounded confirmation poll (up to 8 seconds)
    start = time.time()
    confirmed_id = None
    confirmed_url = None

    while time.time() - start < 8.0:
        page.wait_for_timeout(500)
        articles = page.locator(dom.ARTICLE).all()
        for article in articles:
            # Check text
            text_el = article.locator(dom.TWEET_TEXT).first
            if text_el.count() == 0:
                continue
            text = text_el.inner_text().strip()
            if text != draft['text'].strip():
                continue

            # Check status link
            links = article.locator(dom.TIMESTAMP_LINK).all()
            for link in links:
                href = link.get_attribute('href') or ''
                match = re.search(r'/status/([0-9]+)', href)
                if match:
                    post_id = match.group(1).lstrip('0')
                    if post_id not in existing_ids:
                        # If signed in handle is known, verify author handle
                        if user_handle:
                            author_el = article.locator(dom.AUTHOR).first
                            if author_el.count() > 0:
                                author_text = author_el.inner_text().lower()
                                if user_handle not in author_text:
                                    continue
                        confirmed_id = post_id
                        confirmed_url = f"https://x.com/i/status/{post_id}"
                        break
            if confirmed_id:
                break
        if confirmed_id:
            break

    if confirmed_id:
        return {
            'state': 'submitted',
            'reply_id': confirmed_id,
            'reply_url': confirmed_url,
            'after_screenshot': str(after_path) if after_path else None,
        }

    return {
        'state': 'uncertain',
        'reason': 'confirmation_timeout',
        'after_screenshot': str(after_path) if after_path else None,
    }
