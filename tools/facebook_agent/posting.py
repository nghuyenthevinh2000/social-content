"""Personal-profile navigation, composer validation, and one-click publishing."""

import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .models import AgentError, validate_content
from . import dom, selectors


def inspect_profile(page, timeout_ms: int = 30000) -> dict:
    """Navigate through /me, verifying an editable personal profile."""
    try:
        page.goto('https://www.facebook.com/me', wait_until='domcontentloaded', timeout=timeout_ms)
        selectors.check_block(page)
        profile_heading = dom.profile_heading(page)
        selectors.visible(profile_heading).first.wait_for(state='visible', timeout=timeout_ms)
        edit = dom.profile_edit_control(page)
        try:
            selectors.visible(edit).first.wait_for(state='visible', timeout=timeout_ms)
        except PlaywrightTimeout:
            selectors.check_block(page)
            raise AgentError('not_personal_profile', 'Own-profile Edit profile control was not found. Pages and Groups are unsupported.', True)
        management = dom.page_management_control(page)
        if selectors.visible(management).count():
            raise AgentError('not_personal_profile', 'Page management controls detected; only personal profiles are supported.', True)
        parsed = urlparse(page.url)
        path = parsed.path.strip('/')
        if not path or '/' in path or path in ('me', 'home.php', 'groups', 'pages') or (
                path == 'profile.php' and not parse_qs(parsed.query).get('id')):
            raise AgentError('not_personal_profile', 'Could not identify a canonical personal-profile URL.', True)
        named_heading = selectors.visible(dom.profile_name(page, path)).first
        if not named_heading.count():
            h1s = selectors.visible(dom.profile_primary_heading(page))
            named_heading = selectors.unique(h1s, 'profile heading') if h1s.count() == 1 else h1s.first
        name = named_heading.inner_text().strip() if named_heading.count() else ''
        if not name:
            raise AgentError('not_personal_profile', 'Profile name is empty.', True)
        return {'name': name, 'url': page.url}
    except AgentError:
        raise
    except Exception as exc:
        selectors.check_block(page)
        raise AgentError('dom_error', f'Could not inspect Facebook profile: {exc}', True) from exc


def _audience(dialog) -> str:
    button = selectors.unique(dom.audience_button(dialog), 'audience control')
    value = button.inner_text().strip()
    # Facebook may expose the value only in its accessible label.
    if not value:
        value = button.get_attribute('aria-label') or ''
    if value.lower() == 'edit privacy' or not value:
        raise AgentError('ambiguous_dom', 'Could not read the current post audience.', True)
    return value


def _check_identity(dialog, profile, timeout_ms: int = 15000):
    # Approved post text can itself contain the actor name. Never interpret
    # editable text or its descendants as the author identity.
    author = dom.posting_identity(dialog, profile['name'])
    try:
        selectors.visible(author).first.wait_for(state='visible', timeout=timeout_ms)
    except PlaywrightTimeout:
        pass
    selectors.unique(author, 'posting identity')


def _check_composer(dialog, profile, text, audience):
    _check_identity(dialog, profile)
    editor = selectors.unique(dom.post_textbox(dialog), 'post textbox')
    # innerText uses LF regardless of the CLI input's line-ending convention.
    if editor.inner_text().replace('\r\n', '\n') != text.replace('\r\n', '\n'):
        raise AgentError('content_changed', 'Composer text differs from the supplied text. Nothing submitted.', True)
    if _audience(dialog) != audience:
        raise AgentError('audience_changed', 'Audience changed while preparing the post. Nothing submitted.', True)


def _check_attachments(dialog, image=None):
    """Reject restored or added media not explicitly supplied by this request."""
    media = selectors.visible(dom.remove_attachment_button(dialog))
    files = dom.attachment_inputs(dialog).evaluate_all(
        '(inputs) => inputs.flatMap(el => Array.from(el.files, f => ({name:f.name, size:f.size})))')
    if image is None:
        if media.count() or files:
            raise AgentError('unexpected_attachment', 'Composer contains an attachment not supplied by this request. Clear it manually.', True)
        return
    photos = selectors.visible(dom.remove_photo_button(dialog))
    matching_files = (files == [{'name': image.name, 'size': image.stat().st_size}])
    matching_alt = (dom.uploaded_image(dialog, image.name).count() >= 1)
    if media.count() != 1 or photos.count() != 1 or not (matching_files or matching_alt):
        raise AgentError('unexpected_attachment', 'Final composer attachments differ from the supplied image. Nothing submitted.', True)


def _confirmation(page):
    return selectors.visible(dom.post_confirmation(page))


def publish(page, text: str, image: Path | None = None, timeout_ms: int = 15000) -> dict:
    """Publish approved content directly. Never retry a dispatched click."""
    text, image = validate_content(text, image)
    profile = inspect_profile(page, timeout_ms)
    try:
        trigger = selectors.unique(dom.composer_trigger(page), 'profile composer trigger')
        trigger.click(timeout=timeout_ms)
        dialogs = dom.composer_dialog(page)
        if dialogs.count() > 1:
            tb_dialogs = dom.composer_dialog_with_textbox(dialogs)
            if tb_dialogs.count() == 1:
                dialogs = tb_dialogs
        selectors.visible(dialogs).first.wait_for(state='visible', timeout=timeout_ms)
        dialog = selectors.unique(dialogs, 'Create post dialog')
        _check_identity(dialog, profile, timeout_ms=timeout_ms)
        # Never merge this request with a Facebook-restored media draft.
        _check_attachments(dialog)
        audience = _audience(dialog)
        editor = selectors.unique(dom.post_textbox(dialog), 'post textbox')
        editor.fill(text, timeout=timeout_ms)
        if image:
            upload = dom.image_upload_input(dialog)
            # File inputs are commonly hidden; uniqueness still matters.
            if upload.count() == 0:
                photo = selectors.unique(dom.photo_video_button(dialog), 'Photo/video button')
                photo.click(timeout=timeout_ms)
                upload = dom.image_upload_input(dialog)
            if upload.count() != 1:
                raise AgentError('ambiguous_dom', 'Expected one image upload input in the composer.', True)
            upload.set_input_files(str(image), timeout=timeout_ms)
            preview = dom.remove_photo_button(dialog)
            selectors.visible(preview).first.wait_for(state='visible', timeout=timeout_ms)
            selectors.unique(preview, 'uploaded photo preview')
            files = upload.evaluate('(el) => Array.from(el.files, f => ({name:f.name, size:f.size}))')
            matching_files = (files == [{'name': image.name, 'size': image.stat().st_size}])
            if not matching_files:
                img_locator = dom.uploaded_image(dialog, image.name)
                try:
                    selectors.visible(img_locator).first.wait_for(state='visible', timeout=timeout_ms)
                except PlaywrightTimeout:
                    pass
            matching_alt = (dom.uploaded_image(dialog, image.name).count() >= 1)
            if not (matching_files or matching_alt):
                raise AgentError('content_changed', 'Image selection differs from the supplied file.', True)
        _check_composer(dialog, profile, text, audience)
        _check_attachments(dialog, image)
        next_btn = selectors.visible(dom.next_button(dialog))
        post_btn = selectors.visible(dom.post_button(dialog))
        if next_btn.count() == 1 and post_btn.count() == 0:
            next_btn.first.click(timeout=timeout_ms)
            post_button_locator = dom.post_button(page)
            selectors.visible(post_button_locator).first.wait_for(state='visible', timeout=timeout_ms)
            submit = selectors.unique(post_button_locator, 'Post button')
            active_dialog = selectors.visible(dom.submission_dialog(page, submit)).first
        else:
            submit = selectors.unique(dom.post_button(dialog), 'Post button')
            active_dialog = dialog
        deadline = time.monotonic() + timeout_ms / 1000
        # Playwright 1.50 misroutes Locator.is_enabled to is_editable.
        while submit.is_disabled():
            selectors.check_block(page)
            if time.monotonic() >= deadline:
                raise AgentError('submit_disabled', 'Post button remained disabled; nothing submitted.', True)
            page.wait_for_timeout(100)
        selectors.check_block(page)
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
            if _confirmation(page).count() > old_confirmations and not active_dialog.is_visible():
                result.update(status='confirmed', human_action_required=False, message='Facebook displayed a post-sharing confirmation.')
                return result
            page.wait_for_timeout(100)
    except Exception as exc:
        result['detail'] = str(exc)
    return result
