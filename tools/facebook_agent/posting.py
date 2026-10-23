"""Profile/Page navigation, composer validation, and one-click publishing."""

import time
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urljoin, urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .models import AgentError, validate_content, validate_video
from . import dom, selectors


def inspect_profile(page, timeout_ms: int = 30000, page_name: str | None = None,
                    page_id: str | None = None) -> dict:
    """Inspect /me; Page mode requires the exact expected, already-active Page."""
    if page_name is not None and not page_name.strip():
        raise AgentError('invalid_arguments', 'page-name must not be blank.')
    if page_id is not None and (not page_id.isascii() or not page_id.isdecimal()):
        raise AgentError('invalid_arguments', 'page-id must contain ASCII digits only.')
    page_mode = page_name is not None or page_id is not None
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
            if page_mode:
                raise AgentError('not_active_page', 'Editable Page controls were not found. Switch into the intended Page manually.', True)
            raise AgentError('not_personal_profile', 'Own-profile Edit profile control was not found. Pages and Groups are unsupported.', True)
        management = dom.page_management_control(page)
        if page_mode:
            if (not selectors.visible(management).count()
                    or selectors.visible(dom.switch_into_page_control(page)).count()):
                raise AgentError('not_active_page', 'Switch into the intended Page manually before continuing.', True)
        elif selectors.visible(management).count():
            raise AgentError('not_personal_profile', 'Page management controls detected; only personal profiles are supported.', True)
        parsed = urlparse(page.url)
        path = parsed.path.strip('/')
        if page_id is not None and (path != 'profile.php' or parse_qs(parsed.query).get('id') != [page_id]):
            raise AgentError('page_identity_mismatch', f'Active /me URL does not match Page ID {page_id}: {page.url}. Switch into the intended Page manually.', True)
        if not path or '/' in path or path in ('me', 'home.php', 'groups', 'pages') or (
                path == 'profile.php' and not parse_qs(parsed.query).get('id')):
            raise AgentError('not_personal_profile', 'Could not identify a canonical personal-profile URL.', True)
        if page_name is not None:
            headings = selectors.visible(page.get_by_role('heading', name=page_name, exact=True))
            # Repeated display labels are not distinct identities. Accept them
            # only after the active /me URL matched the explicitly supplied ID.
            if page_id is not None and {name.strip() for name in headings.all_inner_texts()} == {page_name}:
                return {'name': page_name, 'url': page.url, 'type': 'page'}
            heading = selectors.unique(headings, 'expected Page heading')
            return {'name': heading.inner_text().strip(), 'url': page.url, 'type': 'page'}
        if page_id is not None:
            candidates = dom.profile_primary_heading(page).filter(has_not_text=dom.PAGE_MANAGEMENT)
            if selectors.visible(candidates).count() != 1:
                headings = selectors.visible(page.locator(dom.PROFILE_HEADINGS)).all_text_contents()
                raise AgentError('ambiguous_dom', f'Cannot determine Page author safely. Visible headings: {headings}. Supply --page-name with the exact Page name.', True)
            heading = selectors.unique(candidates, 'Page heading')
            name = heading.inner_text().strip()
            if not name:
                raise AgentError('ambiguous_dom', 'Page name is empty.', True)
            return {'name': name, 'url': page.url, 'type': 'page'}
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


def _check_attachments(dialog, media=None, kind: str = 'image'):
    """Reject restored or added media not explicitly supplied by this request."""
    controls = selectors.visible(dom.remove_attachment_button(dialog))
    files = dom.attachment_inputs(dialog).evaluate_all(
        '(inputs) => inputs.flatMap(el => Array.from(el.files, f => ({name:f.name, size:f.size})))')
    if media is None:
        if controls.count() or files:
            raise AgentError('unexpected_attachment', 'Composer contains an attachment not supplied by this request. Clear it manually.', True)
        return
    matching_files = (files == [{'name': media.name, 'size': media.stat().st_size}])
    if kind == 'video':
        # Facebook reads then clears the file input, so verify via the preview.
        if controls.count() != 1 or dom.uploaded_video(dialog).count() < 1:
            raise AgentError('unexpected_attachment', 'Final composer attachments differ from the supplied video. Nothing submitted.', True)
        return
    photos = selectors.visible(dom.remove_photo_button(dialog))
    matching_alt = (dom.uploaded_image(dialog, media.name).count() >= 1)
    if controls.count() != 1 or photos.count() != 1 or not (matching_files or matching_alt):
        raise AgentError('unexpected_attachment', 'Final composer attachments differ from the supplied image. Nothing submitted.', True)


def _confirmation(page):
    return selectors.visible(dom.post_confirmation(page))


def _confirmation_permalink(page, old_count, profile_url):
    """Read only new success toasts, never guess from the feed's newest post."""
    urls = set()
    confirmations = _confirmation(page)
    owner = urlparse(profile_url)
    owner_id = parse_qs(owner.query).get('id', [None])[0]
    for index in range(old_count, confirmations.count()):
        links = selectors.visible(dom.confirmation_links(confirmations.nth(index)))
        for link in links.all():
            parsed = urlparse(urljoin(page.url, link.get_attribute('href') or ''))
            if (parsed.scheme != 'https' or parsed.hostname not in ('www.facebook.com', 'facebook.com')
                    or parsed.username or parsed.password or parsed.port not in (None, 443)):
                continue
            path = parsed.path.rstrip('/')
            match = re.fullmatch(r'/([^/]+)/(posts|videos)/([A-Za-z0-9]+)', path)
            query = parse_qs(parsed.query)
            if match:
                actor = match[1]
                if owner_id and actor.isdecimal() and actor != owner_id:
                    continue
                if not owner_id and actor != owner.path.strip('/'):
                    continue
                canonical = 'https://www.facebook.com' + path
            elif re.fullmatch(r'/(reel|videos)/\d+', path):
                canonical = 'https://www.facebook.com' + path
            elif (path in ('/permalink.php', '/story.php')
                  and len(query.get('story_fbid', [])) == len(query.get('id', [])) == 1
                  and re.fullmatch(r'[A-Za-z0-9]+', query['story_fbid'][0])
                  and query['id'][0].isascii() and query['id'][0].isdecimal()
                  and (not owner_id or query['id'][0] == owner_id)):
                canonical = 'https://www.facebook.com' + path + '?' + urlencode(
                    {'story_fbid': query['story_fbid'][0], 'id': query['id'][0]})
            else:
                continue
            urls.add(canonical)
    return (next(iter(urls)), 'observed') if len(urls) == 1 else (None, 'ambiguous' if urls else 'not_exposed')


def _groups_limit(picker) -> int:
    match = dom.GROUPS_PICKER_TEXT.search(picker.inner_text() or '')
    if not match:
        raise AgentError('ambiguous_dom', 'Could not read the group-sharing limit.', True)
    return int(match.group(1))


# Facebook re-renders the picker while it loads, so a single atomic pass over
# the rows avoids per-element waits on rows that vanish between calls.
_GROUP_ROWS_JS = """(picker) => {
  const rows = Array.from(picker.querySelectorAll('div[role="button"]'))
    .filter((row) => row.querySelector('input[aria-checked]'));
  return rows.map((row) => (((row.innerText || '').trim().split('\\n')[0]) || '').trim());
}"""

_READ_GROUP_JS = """(picker, name) => {
  const row = Array.from(picker.querySelectorAll('div[role="button"]'))
    .filter((r) => r.querySelector('input[aria-checked]'))
    .find((r) => ((((r.innerText || '').trim().split('\\n')[0]) || '').trim()) === name);
  return row ? row.querySelector('input[aria-checked]').getAttribute('aria-checked') : null;
}"""

_CLICK_GROUP_JS = """(picker, name) => {
  const row = Array.from(picker.querySelectorAll('div[role="button"]'))
    .filter((r) => r.querySelector('input[aria-checked]'))
    .find((r) => ((((r.innerText || '').trim().split('\\n')[0]) || '').trim()) === name);
  if (!row) return null;
  const box = row.querySelector('input[aria-checked]');
  if (box.getAttribute('aria-checked') !== 'true') {
    const fire = (type, pointer) => row.dispatchEvent(
      pointer ? new PointerEvent(type, {bubbles: true, cancelable: true, view: window, pointerId: 1})
              : new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
    fire('pointerdown', true); fire('mousedown', false);
    fire('pointerup', true); fire('mouseup', false); fire('click', false);
  }
  return box.getAttribute('aria-checked');
}"""


def _share_to_groups(page, groups, timeout_ms: int = 15000):
    """Select the named groups on the composer's final step, then confirm.

    Group rows are matched by their exact first line, so a duplicated display
    name stops the post rather than selecting the wrong group.
    """
    settings = selectors.visible(dom.post_settings_dialog(page))
    try:
        settings.first.wait_for(state='visible', timeout=timeout_ms)
    except PlaywrightTimeout:
        raise AgentError('groups_unsupported',
                         'This composer exposed no group-sharing step. Nothing submitted.', True)
    dialog = selectors.unique(settings, 'Post settings dialog')
    share = selectors.unique(selectors.visible(dom.share_to_groups_button(dialog)), 'Share to groups button')
    share.click(timeout=timeout_ms)
    picker = selectors.unique(selectors.visible(dom.groups_picker_dialog(page)), 'Share to groups picker')
    limit = _groups_limit(picker)
    if len(groups) > limit:
        raise AgentError('too_many_groups',
                         f'Facebook allows up to {limit} groups for this post; {len(groups)} requested. Nothing submitted.', True)
    available = picker.evaluate(_GROUP_ROWS_JS)
    for name in groups:
        matches = sum(1 for line in available if line == name)
        if matches == 0:
            raise AgentError('group_not_found', f'Group not found in the picker: {name}. Nothing submitted.', True)
        if matches > 1:
            raise AgentError('ambiguous_dom', f'Multiple groups are named "{name}"; pick a unique group. Nothing submitted.', True)
        picker.evaluate(_CLICK_GROUP_JS, name)
        deadline = time.monotonic() + timeout_ms / 1000
        while picker.evaluate(_READ_GROUP_JS, name) != 'true':
            if time.monotonic() > deadline:
                raise AgentError('group_not_selected', f'Could not select group: {name}. Nothing submitted.', True)
            page.wait_for_timeout(150)
    done = selectors.unique(selectors.visible(dom.groups_done_button(picker)), 'Done button')
    done.click(timeout=timeout_ms)


def check_campaign(**kwargs):
    """Translate shared policy failures into the publisher's stable error contract."""
    from tools.loop import preflight
    try:
        return preflight.require_publication(**kwargs)
    except (ValueError, OSError) as exc:
        raise AgentError('content_policy', str(exc), True) from exc


def publish(page, text: str, image: Path | None = None, video: Path | None = None,
            timeout_ms: int = 15000, page_name: str | None = None,
            page_id: str | None = None, groups: list[str] | None = None,
            project: Path | None = None, post: int | None = None) -> dict:
    """Publish approved content directly. Never retry a dispatched click.

    At most one of `image` or `video` may be supplied. When `groups` is given,
    the final composer step (Post settings or Reel settings) is used to also
    share the post to those exact groups before the single Post click.
    """
    if image is not None and video is not None:
        raise AgentError('invalid_arguments', 'Provide either an image or a video, not both.')
    text, image = validate_content(text, image)
    video = validate_video(video)
    campaign = dict(project=project, post=post, text=text, image=image, video=video, groups=groups)
    page_id = check_campaign(page_id=page_id, **campaign)
    media = video or image
    kind = 'video' if video else 'image'
    profile = inspect_profile(page, timeout_ms, page_name=page_name, page_id=page_id)
    # Name-only callers must not bypass managed-Page policy. Verify observed ID
    # before opening the composer, even when no project/Page ID was supplied.
    observed_id = parse_qs(urlparse(profile['url']).query).get('id', [page_id])[0]
    check_campaign(page_id=observed_id, **campaign)
    try:
        triggers = dom.composer_trigger(page)
        selectors.visible(triggers).first.wait_for(state='visible', timeout=timeout_ms)
        trigger = selectors.unique(triggers, 'profile composer trigger')
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
        if video:
            upload = dom.video_upload_input(dialog)
            if upload.count() == 0:
                photo = selectors.unique(dom.photo_video_button(dialog), 'Photo/video button')
                photo.click(timeout=timeout_ms)
                upload = dom.video_upload_input(dialog)
            if upload.count() != 1:
                raise AgentError('ambiguous_dom', 'Expected one video upload input in the composer.', True)
            upload.set_input_files(str(video), timeout=timeout_ms)
            # Facebook uploads and processes the video asynchronously, and it
            # clears the file input after reading it, so verify via the preview.
            try:
                selectors.visible(dom.uploaded_video(dialog)).first.wait_for(state='visible', timeout=timeout_ms)
            except PlaywrightTimeout:
                pass
            selectors.unique(selectors.visible(dom.remove_attachment_button(dialog)), 'video attachment preview')
        elif image:
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
        _check_attachments(dialog, media, kind)
        # Facebook may insert extra wizard steps (e.g. Create post -> Edit reel
        # -> Reel settings). Click any visible Next until the Post button shows.
        step_deadline = time.monotonic() + timeout_ms / 1000
        while True:
            posts = selectors.visible(dom.post_button(page))
            if posts.count():
                submit = selectors.unique(posts, 'Post button')
                break
            nxt = selectors.visible(dom.next_button(page))
            if nxt.count() == 1:
                nxt.first.click(timeout=timeout_ms)
                page.wait_for_timeout(300)
                continue
            if time.monotonic() > step_deadline:
                raise AgentError('dom_error', 'Post button did not appear after the composer steps.', True)
            page.wait_for_timeout(300)
        # Group sharing lives on the final step (Post settings or Reel settings).
        if groups:
            _share_to_groups(page, groups, timeout_ms=timeout_ms)
        active_dialog = selectors.visible(dom.submission_dialog(page, submit)).first
        deadline = time.monotonic() + timeout_ms / 1000
        # Playwright 1.50 misroutes Locator.is_enabled to is_editable.
        while submit.is_disabled():
            selectors.check_block(page)
            if time.monotonic() >= deadline:
                raise AgentError('submit_disabled', 'Post button remained disabled; nothing submitted.', True)
            page.wait_for_timeout(100)
        selectors.check_block(page)
        old_confirmations = _confirmation(page).count()
        # Re-read hashes immediately before the irreversible click, outside the
        # uncertain-submission handler: changed files mean nothing was submitted.
        check_campaign(page_id=observed_id, **campaign)
    except AgentError:
        raise
    except Exception as exc:
        selectors.check_block(page)
        raise AgentError('dom_error', f'Composer preparation failed before submission: {exc}', True) from exc

    result = {'status': 'uncertain', 'profile': profile, 'audience': audience,
              'permalink': None, 'permalink_status': 'not_confirmed',
              'image': str(image) if image else None,
              'video': str(video) if video else None,
              'groups': list(groups) if groups else [],
              'human_action_required': True, 'message': 'Check the open Facebook tab before attempting this post again.'}
    # From this point forward every failure is uncertain, including click timeouts.
    try:
        submit.click(timeout=timeout_ms, no_wait_after=True)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            selectors.check_block(page)
            if _confirmation(page).count() > old_confirmations and not active_dialog.is_visible():
                result.update(status='confirmed', human_action_required=False, message='Facebook displayed a post-sharing confirmation.')
                # Publication success and URL discovery are separate outcomes.
                # Extraction failure must never invite a duplicate publish.
                try:
                    result['permalink'], result['permalink_status'] = _confirmation_permalink(
                        page, old_confirmations, profile['url'])
                except Exception:
                    result['permalink_status'] = 'unavailable'
                result['registration_status'] = 'ready' if result['permalink'] else 'needs_permalink'
                if not result['permalink']:
                    result['next_action'] = (
                        'Do not repost. Use the read-only content-library command with --page-id and a new --output '
                        'to inspect candidates, or inspect manually. Verify the exact original post before loop register; '
                        'never infer its URL from recency or use ad-hoc browser scripts.')
                return result
            page.wait_for_timeout(100)
    except Exception as exc:
        result['detail'] = str(exc)
    return result
