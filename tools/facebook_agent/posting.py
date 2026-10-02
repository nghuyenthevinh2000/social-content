"""Personal-profile navigation, composer validation, and one-click publishing."""

import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .models import AgentError, validate_content
from . import selectors


def inspect_profile(page, timeout_ms: int = 15000) -> dict:
    """Navigate through /me, verifying an editable personal profile."""
    try:
        page.goto('https://www.facebook.com/me', wait_until='domcontentloaded', timeout=timeout_ms)
        selectors.check_block(page)
        page.get_by_role('heading', level=1).first.wait_for(state='visible', timeout=timeout_ms)
        edit = page.get_by_role('button', name='Edit profile', exact=True).or_(
            page.get_by_role('link', name='Edit profile', exact=True))
        try:
            selectors.visible(edit).first.wait_for(state='visible', timeout=timeout_ms)
        except PlaywrightTimeout:
            selectors.check_block(page)
            raise AgentError('not_personal_profile', 'Own-profile Edit profile control was not found. Pages and Groups are unsupported.', True)
        management = page.get_by_role('button', name=re.compile(r'^(Manage Page|Switch into Page|Meta Business Suite)$', re.I)).or_(
            page.get_by_role('link', name=re.compile(r'^(Manage Page|Switch into Page|Meta Business Suite)$', re.I)))
        if selectors.visible(management).count():
            raise AgentError('not_personal_profile', 'Page management controls detected; only personal profiles are supported.', True)
        parsed = urlparse(page.url)
        path = parsed.path.strip('/')
        if not path or '/' in path or path in ('me', 'home.php', 'groups', 'pages') or (
                path == 'profile.php' and not parse_qs(parsed.query).get('id')):
            raise AgentError('not_personal_profile', 'Could not identify a canonical personal-profile URL.', True)
        name = selectors.unique(page.get_by_role('heading', level=1), 'profile heading').inner_text().strip()
        if not name:
            raise AgentError('not_personal_profile', 'Profile name is empty.', True)
        return {'name': name, 'url': page.url}
    except AgentError:
        raise
    except Exception as exc:
        selectors.check_block(page)
        raise AgentError('dom_error', f'Could not inspect Facebook profile: {exc}', True) from exc


def _audience(dialog) -> str:
    button = selectors.unique(dialog.get_by_role('button', name=selectors.AUDIENCE), 'audience control')
    value = button.inner_text().strip()
    # Facebook may expose the value only in its accessible label.
    if not value:
        value = button.get_attribute('aria-label') or ''
    if value.lower() == 'edit privacy' or not value:
        raise AgentError('ambiguous_dom', 'Could not read the current post audience.', True)
    return value


def _check_identity(dialog, profile):
    # Approved post text can itself contain the actor name. Never interpret
    # editable text or its descendants as the author identity.
    author = dialog.get_by_text(profile['name'], exact=True).and_(dialog.locator(
        ':not([contenteditable="true"]):not([contenteditable="true"] *)'))
    selectors.unique(author, 'posting identity')


def _check_composer(dialog, profile, text, audience):
    _check_identity(dialog, profile)
    editor = selectors.unique(dialog.locator('[role="textbox"][contenteditable="true"]'), 'post textbox')
    # innerText uses LF regardless of the CLI input's line-ending convention.
    if editor.inner_text().replace('\r\n', '\n') != text.replace('\r\n', '\n'):
        raise AgentError('content_changed', 'Composer text differs from the supplied text. Nothing submitted.', True)
    if _audience(dialog) != audience:
        raise AgentError('audience_changed', 'Audience changed while preparing the post. Nothing submitted.', True)


def _check_attachments(dialog, image=None):
    """Reject restored or added media not explicitly supplied by this request."""
    media = selectors.visible(dialog.get_by_role('button', name=re.compile(
        r'^Remove (?:photo|image|video|attachment|gif)(?:\b|$)', re.I)))
    files = dialog.locator('input[type="file"]').evaluate_all(
        '(inputs) => inputs.flatMap(el => Array.from(el.files, f => ({name:f.name, size:f.size})))')
    if image is None:
        if media.count() or files:
            raise AgentError('unexpected_attachment', 'Composer contains an attachment not supplied by this request. Clear it manually.', True)
        return
    photos = selectors.visible(dialog.get_by_role('button', name=re.compile(
        r'^Remove (?:photo|image)(?:\b|$)', re.I)))
    if media.count() != 1 or photos.count() != 1 or files != [{'name': image.name, 'size': image.stat().st_size}]:
        raise AgentError('unexpected_attachment', 'Final composer attachments differ from the supplied image. Nothing submitted.', True)


def _confirmation(page):
    return selectors.visible(page.get_by_role('status').or_(page.get_by_role('alert')).filter(has_text=selectors.SUCCESS))


def publish(page, text: str, image: Path | None = None, timeout_ms: int = 15000) -> dict:
    """Publish approved content directly. Never retry a dispatched click."""
    text, image = validate_content(text, image)
    profile = inspect_profile(page, timeout_ms)
    try:
        trigger = selectors.unique(page.get_by_role('button', name=selectors.COMPOSER_TRIGGER), 'profile composer trigger')
        trigger.click(timeout=timeout_ms)
        dialogs = page.get_by_role('dialog').filter(has=page.get_by_role('heading', name='Create post', exact=True))
        selectors.visible(dialogs).first.wait_for(state='visible', timeout=timeout_ms)
        dialog = selectors.unique(dialogs, 'Create post dialog')
        _check_identity(dialog, profile)
        # Never merge this request with a Facebook-restored media draft.
        _check_attachments(dialog)
        audience = _audience(dialog)
        editor = selectors.unique(dialog.locator('[role="textbox"][contenteditable="true"]'), 'post textbox')
        editor.fill(text, timeout=timeout_ms)
        if image:
            upload = dialog.locator('input[type="file"][accept*="image"]')
            # File inputs are commonly hidden; uniqueness still matters.
            if upload.count() == 0:
                photo = selectors.unique(dialog.get_by_role('button', name=re.compile(r'^Photo/video$', re.I)), 'Photo/video button')
                photo.click(timeout=timeout_ms)
                upload = dialog.locator('input[type="file"][accept*="image"]')
            if upload.count() != 1:
                raise AgentError('ambiguous_dom', 'Expected one image upload input in the composer.', True)
            upload.set_input_files(str(image), timeout=timeout_ms)
            preview = dialog.get_by_role('button', name=re.compile(r'^Remove (?:photo|image)(?:\b|$)', re.I))
            selectors.visible(preview).first.wait_for(state='visible', timeout=timeout_ms)
            selectors.unique(preview, 'uploaded photo preview')
            files = upload.evaluate('(el) => Array.from(el.files, f => ({name:f.name, size:f.size}))')
            if files != [{'name': image.name, 'size': image.stat().st_size}]:
                raise AgentError('content_changed', 'Image selection differs from the supplied file.', True)
        submit = selectors.unique(dialog.get_by_role('button', name='Post', exact=True), 'Post button')
        deadline = time.monotonic() + timeout_ms / 1000
        # Playwright 1.50 misroutes Locator.is_enabled to is_editable.
        while submit.is_disabled():
            selectors.check_block(page)
            if time.monotonic() >= deadline:
                raise AgentError('submit_disabled', 'Post button remained disabled; nothing submitted.', True)
            page.wait_for_timeout(100)
        selectors.check_block(page)
        _check_composer(dialog, profile, text, audience)
        _check_attachments(dialog, image)
        old_confirmations = _confirmation(page).count()
    except AgentError:
        raise
    except Exception as exc:
        selectors.check_block(page)
        raise AgentError('dom_error', f'Composer preparation failed before submission: {exc}', True) from exc

    result = {'status': 'uncertain', 'profile': profile, 'audience': audience, 'image': str(image) if image else None,
              'human_action_required': True, 'message': 'Check the open Facebook tab before attempting this post again.'}
    # From this point forward every failure is uncertain, including click timeouts.
    try:
        submit.click(timeout=timeout_ms, no_wait_after=True)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            selectors.check_block(page)
            if _confirmation(page).count() > old_confirmations and not dialog.is_visible():
                result.update(status='confirmed', human_action_required=False, message='Facebook displayed a post-sharing confirmation.')
                return result
            page.wait_for_timeout(100)
    except Exception as exc:
        result['detail'] = str(exc)
    return result
