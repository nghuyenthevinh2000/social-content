"""Fail-closed personal composer preparation and one irreversible submission."""

import hashlib
import time
from urllib.parse import urljoin, urlsplit

from . import dom, selectors
from .models import AgentError, ImageInput


def _visible(locator):
    return [locator.nth(index) for index in range(locator.count())
            if locator.nth(index).is_visible()]


def _unique_visible(locator):
    matches = _visible(locator)
    if len(matches) > 1:
        raise AgentError('ambiguous_selector', 'Multiple active LinkedIn controls matched. Inspect manually.')
    return matches[0] if matches else None


def _remaining(deadline):
    remaining = int((deadline - time.monotonic()) * 1000)
    if remaining <= 0:
        raise AgentError('dom_timeout', 'Timed out preparing the LinkedIn composer. Inspect manually.')
    return remaining


def _wait_unique(page, locator, deadline):
    while True:
        selectors.detect_block(page)
        result = _unique_visible(locator)
        if result is not None:
            return result
        page.wait_for_timeout(min(50, _remaining(deadline)))


def _wait_media(page, composer, existing_inputs, deadline):
    while True:
        selectors.detect_block(page)
        # Persistent hidden file inputs do not make the underlying composer
        # an active media dialog. A distinct visible modal takes precedence.
        media = _unique_visible(page.locator(dom.MEDIA_DIALOG))
        if media is not None:
            return media
        # Inline media is supported only when Add media exposes a new input.
        # Otherwise wait for a delayed modal, not the composer's old chooser.
        inputs = composer.locator(dom.FILE_INPUT).element_handles()
        if composer.is_visible() and any(
            not any(node.evaluate('(el, old) => el === old', old) for old in existing_inputs)
            for node in inputs
        ):
            selectors.unique_locator(composer, dom.FILE_INPUT)
            return composer
        page.wait_for_timeout(min(50, _remaining(deadline)))


def _personal_author(composer, page_url):
    links = _visible(composer.locator(dom.AUTHOR))
    identities = []
    for link in links:
        url = urlsplit(urljoin(page_url, link.get_attribute('href') or ''))
        if url.hostname not in ('linkedin.com', 'www.linkedin.com'):
            raise AgentError('unsupported_identity', 'Composer author must be a LinkedIn personal profile.')
        if url.path.startswith('/company/'):
            raise AgentError('unsupported_identity', 'Company posting is unsupported. Select your personal profile manually.')
        if url.path.startswith('/in/') and url.path[len('/in/'):].strip('/'):
            identities.append(url.path.rstrip('/'))
    if len(identities) != 1:
        raise AgentError('unsupported_identity', 'A unique personal author profile could not be verified. Inspect manually.')
    return identities[0]


def _modern_author(page, composer, deadline):
    """Verify the selected member row against the own-feed profile, without switching."""
    feed = selectors.unique_locator(page, dom.OWN_PROFILE)
    profile = urlsplit(urljoin(page.url, feed.get_attribute('href') or ''))
    if (profile.hostname not in ('linkedin.com', 'www.linkedin.com')
            or not profile.path.startswith('/in/') or not profile.path[4:].strip('/')):
        raise AgentError('unsupported_identity', 'Own personal feed profile could not be verified.')
    control = _wait_unique(page, composer.locator(dom.MODERN_AUTHOR), deadline)
    name = selectors.unique_locator(control, dom.AUTHOR_LABEL).get_attribute('aria-label')
    if not name or control.get_attribute('aria-expanded') != 'false':
        raise AgentError('unsupported_identity', 'Author control must be uniquely labeled and closed.')
    named_profiles = [link for link in page.locator(dom.NAMED_PROFILE).element_handles()
                      if link.evaluate('''(link, expected) => {
                          const url=new URL(link.href);
                          return ['linkedin.com','www.linkedin.com'].includes(url.hostname)
                              && url.pathname.replace(/\\/$/,'')===expected.profile
                               && link.querySelector(expected.personalIcon).getAttribute('aria-label')===expected.name;
                       }''', {'profile': profile.path.rstrip('/'), 'name': name,
                              'personalIcon': dom.PERSONAL_FIGURE_ICON})]
    if len(named_profiles) != 1:
        raise AgentError('unsupported_identity', 'Own-feed personal profile name could not be uniquely matched.')
    named_profile = named_profiles[0]
    control.click(timeout=_remaining(deadline))
    picker = _wait_unique(page, page.locator(dom.AUTHOR_PICKER), deadline)
    selected = picker.locator(dom.SELECTED_AUTHOR)
    if selected.count() != 1:
        raise AgentError('unsupported_identity', 'A unique selected author is required.')
    radio = selected.element_handle()
    row = radio.evaluate_handle('''(radio, figure) => {
        let row=radio.parentElement;
        while(row && !row.querySelector(figure)) row=row.parentElement;
        return row;
    }''', dom.FIGURE).as_element()
    if row is None:
        raise AgentError('unsupported_identity', 'Selected personal author row is missing.')
    evidence = row.evaluate('''(row, s) => ({
        personal: row.querySelectorAll(s.personalFigureIcon).length===1
            && !row.querySelector(s.companyIcon),
        names: [...row.querySelectorAll(s.authorNames)].map(p=>p.textContent.trim()),
        image: row.querySelector(s.figureImage)?.getAttribute('src'),
        labeled: [...row.querySelectorAll(s.selectedAuthor)].every(r=>
            r.id && [...row.querySelectorAll(s.radioLabel)].some(l=>l.htmlFor===r.id))
    })''', {'personalFigureIcon': dom.PERSONAL_FIGURE_ICON, 'companyIcon': dom.COMPANY_ICON,
            'authorNames': dom.AUTHOR_NAMES, 'figureImage': dom.FIGURE_IMAGE,
            'selectedAuthor': dom.SELECTED_AUTHOR, 'radioLabel': dom.RADIO_LABEL})
    feed_image = selectors.unique_locator(feed, dom.PERSONAL_AVATAR_IMAGE).get_attribute('src')
    if not evidence['personal'] or evidence['names'] != [name] or not evidence['labeled'] or not feed_image or evidence['image'] != feed_image:
        raise AgentError('unsupported_identity', 'Selected author does not match the own personal feed profile.')
    control.click(timeout=_remaining(deadline))
    while control.get_attribute('aria-expanded') != 'false' or picker.is_visible():
        selectors.detect_block(page)
        page.wait_for_timeout(min(50, _remaining(deadline)))
    avatar = selectors.unique_locator(composer, dom.PERSONAL_AVATAR)
    return {'profile': profile.path.rstrip('/'), 'name': name, 'image': feed_image,
            'control': control.element_handle(), 'feed': feed.element_handle(),
            'row': row, 'radio': radio, 'avatar': avatar.element_handle(), 'namedProfile': named_profile}


def _same_modern_author(old, new):
    return (all(old[key] == new[key] for key in ('profile', 'name', 'image'))
            and old['control'].evaluate('(el, other) => el === other', new['control']))


def _images_ready(scope, count):
    if _visible(scope.locator(dom.UPLOAD_ERROR)):
        raise AgentError('upload_failed', 'LinkedIn reported a media upload error. Inspect the composer manually.')
    previews = _visible(scope.locator(dom.IMAGE_PREVIEW))
    thumbnails = _visible(scope.locator(dom.MODERN_THUMBNAIL))
    if thumbnails and any(image.get_attribute('alt') != f'image {i}' for i, image in enumerate(thumbnails)):
        raise AgentError('upload_failed', 'Media thumbnail order is unexpected.')
    if len(previews) > count:
        raise AgentError('upload_failed', 'Composer contains unexpected images. Inspect manually.')
    return (len(previews) == count and not _visible(scope.locator(dom.UPLOAD_PROGRESS))
            and all(image.evaluate('(img) => img.complete && img.naturalWidth > 0') for image in previews))


def _wait_images(page, scope, count, deadline):
    while True:
        selectors.detect_block(page)
        if _images_ready(scope, count):
            return
        page.wait_for_timeout(min(50, _remaining(deadline)))


def _require_empty_media(scope):
    # Hidden previews/choosers can also hold an old draft. Do not merge it with
    # supplied media or let it count as completion of the new upload.
    if (scope.locator(dom.IMAGE_PREVIEW).count()
            or scope.locator(dom.UPLOAD_PROGRESS).count()
            or scope.locator(dom.UPLOAD_ERROR).count()
            or scope.locator(dom.FILE_INPUT).evaluate_all(
                'inputs => inputs.some(input => input.files.length > 0)')):
        raise AgentError('upload_failed', 'Composer contains pre-existing media. Start an empty personal draft manually.')


def _verify_upload_payload(file_input, images, timeout_ms):
    actual = file_input.evaluate('''async (input, timeout) => {
        let timer;
        try { return await Promise.race([Promise.all([...input.files].map(async file => ({
        name: file.name, mime: file.type, size: file.size,
        digest: [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))]
            .map(byte => byte.toString(16).padStart(2, '0')).join('')
        }))), new Promise((_, reject) => { timer=setTimeout(()=>reject(new Error('Payload verification deadline')), timeout); })]);
        } finally { clearTimeout(timer); }
    }''', timeout_ms)
    expected = [{'name': image.name, 'mime': image.mime_type, 'size': len(image.buffer),
                 'digest': hashlib.sha256(image.buffer).hexdigest()} for image in images]
    if actual != expected:
        raise AgentError('upload_failed', 'Uploaded files differ from the approved image snapshots or order. Inspect manually.')


def _editor_text(editor):
    # Chromium innerText adds an extra newline for an empty <div><br></div>
    # in a contenteditable. Native copy/selection text represents the actual
    # user-visible draft, preserving blank lines and spaces without trimming.
    return editor.evaluate('''el => {
        const selection = window.getSelection();
        const saved = Array.from({length: selection.rangeCount}, (_, i) => selection.getRangeAt(i).cloneRange());
        const range = document.createRange(); range.selectNodeContents(el);
        try {
            selection.removeAllRanges(); selection.addRange(range);
            return selection.toString();
        } finally {
            selection.removeAllRanges(); saved.forEach(r => selection.addRange(r));
        }
    }''')


def _modern_preview_evidence(page, scope, images, deadline):
    """Pin ordered decoded blob previews to the approved byte snapshots.

    LinkedIn changes blob URLs across Next. Compare their bytes, not URL shape
    or dimensions. Unknown/non-blob sources and unavailable bytes fail closed.
    """
    records = []
    previews = _visible(scope.locator(dom.IMAGE_PREVIEW))
    if len(previews) != len(images):
        raise AgentError('upload_failed', 'Ordered media evidence is incomplete.')
    for preview, image in zip(previews, images, strict=True):
        node = preview.element_handle()
        source = node.get_attribute('src')
        try:
            actual = node.evaluate('''async (img, expected) => {
                if (!img.isConnected || !img.complete || img.naturalWidth<=0
                    || img.src!==expected.src || !img.src.startsWith('blob:'+location.origin+'/'))
                    throw new Error('Unverifiable preview source');
                const controller=new AbortController(); let timer;
                try { return await Promise.race([
                    (async () => {
                        const response=await fetch(expected.src,{signal:controller.signal});
                        if(!response.ok) throw new Error('Preview unavailable');
                        const bytes=await response.arrayBuffer();
                        const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
                            .map(byte=>byte.toString(16).padStart(2,'0')).join('');
                        if(!img.isConnected || img.src!==expected.src || !img.complete || img.naturalWidth<=0)
                            throw new Error('Preview changed');
                        return {size:bytes.byteLength,digest};
                    })(),
                    new Promise((_,reject)=>{timer=setTimeout(()=>{
                        controller.abort();reject(new Error('Preview deadline'));
                    },expected.timeout);})
                ]); } finally {clearTimeout(timer);controller.abort();}
            }''', {'src': source, 'timeout': _remaining(deadline)})
        except Exception as exc:
            raise AgentError('upload_failed', 'Cannot prove ordered preview correspondence to approved images.') from exc
        if actual != {'size': len(image.buffer), 'digest': hashlib.sha256(image.buffer).hexdigest()}:
            raise AgentError('upload_failed', 'Ordered previews differ from approved image bytes.')
        records.append({'node': node, 'src': source, 'payload': actual})
    current = _visible(scope.locator(dom.IMAGE_PREVIEW))
    if len(current) != len(records) or any(
        not record['node'].evaluate('(node, current) => node === current', item.element_handle())
        or item.get_attribute('src') != record['src']
        for record, item in zip(records, current, strict=True)
    ):
        raise AgentError('upload_failed', 'Preview nodes or order changed while verifying media.')
    selectors.detect_block(page)
    _remaining(deadline)
    return records


_NOTIFICATION_STATE = '''(el, s) => ({
    visible: !!(el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden'),
    text: el.innerText || '',
    message: el.querySelector(s.notificationMessage)?.innerText || el.innerText || '',
    links: [...el.querySelectorAll(s.notificationLink)].map(a => a.href)
})'''


def _notification_state(handle):
    return handle.evaluate(_NOTIFICATION_STATE, {
        'notificationMessage': dom.NOTIFICATION_MESSAGE, 'notificationLink': dom.NOTIFICATION_LINK,
    })


def _capture_final_dispatch(post_button, composer, approved_text, author, count, timeout_ms, preview_evidence=None):
    # Locator.click() can auto-wait while notifications change. Snapshot in the
    # browser's capture phase of the chosen button's trusted click, before the
    # application handles it, not before starting Playwright's click operation.
    return post_button.evaluate_handle('''(button, expected) => {
        const snapshot = ''' + _NOTIFICATION_STATE + ''';
        const s = expected.selectors, composer = expected.composer;
        const visible = el => !!(el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
        const matches = (scope, selector) => [...scope.querySelectorAll(selector)].filter(visible);
        const previews = expected.previews || matches(composer, s.images).map(node => ({node, src: node.src}));
        const capture = {dispatched: false, error: false, canceled: null, baseline: []};
        function validate() {
            const composers = matches(document, s.composer);
            if (composers.length !== 1 || composers[0] !== composer || !composer.contains(button)) return 'dom_timeout';
            if (!expected.modern) {
            const authors = matches(composer, s.author);
            if (authors.length !== 1) return 'unsupported_identity';
            const url = new URL(authors[0].href);
            if (!['linkedin.com','www.linkedin.com'].includes(url.hostname)
                || url.pathname.replace(/\\/$/, '') !== expected.author) return 'unsupported_identity';
            } else {
                const a=expected.author, controls=matches(composer,s.modernAuthor);
                const labels=a.control.querySelectorAll(s.authorLabel);
                const feeds=document.querySelectorAll(s.ownProfile);
                const url=new URL(a.feed.href);
                if(controls.length!==1 || controls[0]!==a.control || labels.length!==1
                    || labels[0].getAttribute('aria-label')!==a.name || a.control.getAttribute('aria-expanded')!=='false'
                    || feeds.length!==1 || feeds[0]!==a.feed || !['linkedin.com','www.linkedin.com'].includes(url.hostname)
                    || url.pathname.replace(/\\/$/,'')!==a.profile
                    || a.feed.querySelector(s.figureImage)?.getAttribute('src')!==a.image
                    || !a.feed.querySelector(s.personalFigureIcon)
                    || !a.namedProfile.isConnected
                    || new URL(a.namedProfile.href).pathname.replace(/\\/$/,'')!==a.profile
                    || a.namedProfile.querySelector(s.personalFigureIcon)?.getAttribute('aria-label')!==a.name
                    || !composer.contains(a.avatar) || !a.avatar.querySelector(s.personalIcon)
                    || a.row.querySelectorAll(s.personalFigureIcon).length!==1
                    || a.row.querySelector(s.companyIcon) || !a.radio.checked
                    || a.row.querySelectorAll(s.selectedAuthor).length!==1
                    || a.row.querySelector(s.figureImage)?.getAttribute('src')!==a.image
                    || [...a.row.querySelectorAll(s.authorNames)].map(p=>p.textContent.trim()).join('\\n')!==a.name)
                    return 'unsupported_identity';
            }
            const editors = matches(composer, s.editor);
            if (editors.length !== 1) return 'text_mismatch';
            const selection = window.getSelection();
            const saved = [...Array(selection.rangeCount)].map((_, i) => selection.getRangeAt(i).cloneRange());
            const range = document.createRange(); range.selectNodeContents(editors[0]);
            let text;
            try { selection.removeAllRanges(); selection.addRange(range); text = selection.toString(); }
            finally { selection.removeAllRanges(); saved.forEach(r => selection.addRange(r)); }
            const normalized = text.replace(/\\r\\n?/g, '\\n');
            if (normalized !== expected.text && normalized.replace(/\\n\\n/g, '\\n') !== expected.text) return 'text_mismatch';
            const images = matches(composer, s.images);
            if (images.length !== expected.count || images.length !== previews.length
                || images.some((img,i) => img !== previews[i].node || img.src !== previews[i].src
                    || !img.complete || img.naturalWidth <= 0)
                || matches(composer, s.progress).length || matches(composer, s.error).length) return 'upload_failed';
            const posts = matches(composer, s.button).filter(el => (el.innerText || '').trim() === s.postLabel);
            if (posts.length !== 1 || posts[0] !== button || button.disabled
                || button.getAttribute('aria-disabled') === 'true') return 'submission_disabled';
            if (document.querySelector(s.checkpoint) || matches(document,s.challenge).length
                || /^\\/checkpoint(?:\\/|$)/.test(location.pathname)) return 'browser_challenge';
            if (matches(document, s.login).length) return 'not_authenticated';
            return null;
        }
        function onClick(event) {
            const path = event.composedPath();
            // Locator.click may re-resolve to a replacement button during its
            // wait. Such a Post click must be canceled, not bypass this guard.
            const replacementPost = path.some(node => node instanceof Element
                && node.matches(s.button) && (node.innerText || '').trim() === s.postLabel
                && node.closest(s.composer));
            if (!event.isTrusted || (!path.includes(button) && !replacementPost)) return;
            try {
                const failure = capture.dispatched ? 'dom_timeout' : validate();
                if (failure) {
                    event.preventDefault(); event.stopImmediatePropagation(); event.stopPropagation();
                    capture.canceled = event.defaultPrevented ? failure : null;
                    capture.error = !event.defaultPrevented;
                    return;
                }
                capture.baseline = [...document.querySelectorAll(s.notification)].map(node => ({node, state: snapshot(node, s)}));
                capture.dispatched = true;
            } catch (error) {
                event.preventDefault(); event.stopImmediatePropagation(); event.stopPropagation();
                capture.canceled = event.defaultPrevented ? 'composer_failed' : null;
                capture.error = true;
            }
        }
        // Window capture precedes even pre-existing document capture handlers.
        capture.cleanup = () => window.removeEventListener('click', onClick, true);
        window.addEventListener('click', onClick, true);
        return capture;
    }''', {'composer': composer.element_handle(), 'text': approved_text, 'author': author, 'count': count,
           'modern': isinstance(author, dict),
           'previews': preview_evidence,
           'selectors': {'composer': dom.COMPOSER, 'author': dom.AUTHOR,
                         'editor': dom.EDITOR, 'images': dom.IMAGE_PREVIEW,
                         'progress': dom.UPLOAD_PROGRESS, 'error': dom.UPLOAD_ERROR,
                         'notification': dom.NOTIFICATION, 'checkpoint': dom.CHECKPOINT_FORM,
                          'challenge': dom.CHALLENGE_FRAME, 'login': dom.LOGIN_FORM,
                          'modernAuthor': dom.MODERN_AUTHOR, 'ownProfile': dom.OWN_PROFILE,
                          'authorLabel': dom.AUTHOR_LABEL, 'figureImage': dom.FIGURE_IMAGE,
                          'personalFigureIcon': dom.PERSONAL_FIGURE_ICON, 'personalIcon': dom.PERSONAL_ICON,
                          'companyIcon': dom.COMPANY_ICON, 'selectedAuthor': dom.SELECTED_AUTHOR,
                          'authorNames': dom.AUTHOR_NAMES, 'button': dom.BUTTON, 'postLabel': dom.POST_LABEL,
                          'notificationMessage': dom.NOTIFICATION_MESSAGE,
                          'notificationLink': dom.NOTIFICATION_LINK}}, timeout=timeout_ms)


def _remove_dispatch_capture(capture):
    try:
        capture.evaluate('capture => capture.cleanup()')
    finally:
        capture.dispose()


def _post_url(links):
    for link in links:
        url = urlsplit(link)
        if (url.scheme == 'https' and url.hostname in ('linkedin.com', 'www.linkedin.com')
                and not url.username and not url.password and url.port in (None, 443)
                and (url.path.startswith('/posts/') or url.path.startswith('/feed/update/urn:li:activity:'))):
            return link
    return None


def wait_for_new_confirmation(page, baseline, timeout_ms) -> dict:
    """Private polling helper: only evidence after actual click dispatch counts."""
    deadline = time.monotonic() + timeout_ms / 1000
    if not baseline.evaluate('capture => capture.dispatched && !capture.error'):
        raise AgentError('dom_timeout', 'The final Post click dispatch could not be verified.')
    while True:
        if time.monotonic() >= deadline:
            raise AgentError('dom_timeout', 'No fresh explicit post-success notification appeared.')
        for handle in page.locator(dom.NOTIFICATION).element_handles():
            state = _notification_state(handle)
            if not state['visible'] or not dom.SUCCESS.search(state['message'].strip()):
                continue
            old = baseline.evaluate('''(capture, node) =>
                capture.baseline.find(record => record.node === node)?.state || null''', handle)
            if old is not None and old['visible'] and old['message'].strip() == state['message'].strip():
                continue
            if time.monotonic() >= deadline:
                raise AgentError('dom_timeout', 'Post-success evidence was observed after the confirmation deadline.')
            return {'status': 'posted', 'url': _post_url(state['links'])}
        # This runs inside the final-click exception boundary, including login,
        # browser disconnects and challenges appearing after dispatch.
        selectors.detect_block(page)
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise AgentError('dom_timeout', 'No fresh explicit post-success notification appeared.')
        page.wait_for_timeout(min(50, remaining))


def publish_post(page, text: str, images: tuple[ImageInput, ...], timeout_ms: int = 30000) -> dict:
    """Upload ordered snapshots, verify a personal draft, and click Post once.

    Caller supplies locally validated inputs. No browser operation is retried.
    Every exception starting with the final click is submission_uncertain.
    An acknowledged capture-phase cancellation can prove a pre-submit failure.
    """
    if timeout_ms <= 0:
        raise AgentError('invalid_timeout', 'Composer timeout must be positive.')
    try:
        try:
            page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=timeout_ms)
        except Exception as exc:
            selectors.detect_block(page)
            raise AgentError('browser_navigation_failed', 'Cannot load the LinkedIn feed. Check connectivity.') from exc
        deadline = time.monotonic() + timeout_ms / 1000
        _wait_unique(page, page.locator(dom.AUTHENTICATED_HOME), deadline)
        start = _wait_unique(page, page.locator(dom.START_POST), deadline)
        if start.evaluate('el => el.tagName === "DIV" && el.getAttribute("role") === "button"'):
            _wait_unique(page, page.locator(dom.HYDRATED_BODY), deadline)
        start.click(timeout=_remaining(deadline))
        composer = _wait_unique(page, page.locator(dom.COMPOSER), deadline)
        modern = composer.evaluate('(el) => el.tagName === "DIALOG"')
        author = _modern_author(page, composer, deadline) if modern else _personal_author(composer, page.url)
        editor = _wait_unique(page, composer.locator(dom.EDITOR), deadline)
        _require_empty_media(composer)
        if _editor_text(editor):
            raise AgentError('text_mismatch', 'Composer contains a pre-existing draft. Start an empty personal draft manually.')
        approved_text = text.replace('\r\n', '\n').replace('\r', '\n')
        editor.fill(approved_text, timeout=_remaining(deadline))
        add_media = _wait_unique(page, composer.locator(dom.ADD_MEDIA), deadline)
        existing_inputs = composer.locator(dom.FILE_INPUT).element_handles()
        if modern:
            with page.expect_file_chooser(timeout=_remaining(deadline)) as emitted:
                add_media.click(timeout=_remaining(deadline))
            chooser = emitted.value
        else:
            add_media.click(timeout=_remaining(deadline))
        media = _wait_media(page, composer, existing_inputs, deadline)
        inline_media = media.evaluate('(el, composer) => el === composer', composer.element_handle())
        # File inputs are commonly intentionally hidden; uniqueness, not
        # visibility, is required inside the verified active dialog.
        file_input = chooser.element if modern else selectors.unique_locator(media, dom.FILE_INPUT)
        if modern:
            # The emitted chooser owns the body-level input, not a global selector.
            if not chooser.is_multiple() or not file_input.evaluate('el => el.isConnected && el.type === "file" && el.files.length === 0'):
                raise AgentError('upload_failed', 'Media chooser must be fresh, connected, and multiple-file.')
            unexpected_progress = media.locator(dom.UPLOAD_PROGRESS).evaluate_all('''(nodes, loader) => nodes.some(node =>
                !node.closest(loader))''', dom.AWAITING_FILE_LOADER)
            if (media.locator(dom.MEDIA_IMAGE_PREVIEW).count()
                    or media.locator(dom.UPLOAD_ERROR).count() or unexpected_progress
                    or media.locator(dom.FILE_INPUT).evaluate_all(
                        'inputs => inputs.some(input => input.files.length > 0)')):
                raise AgentError('upload_failed', 'Media editor contains pre-existing media.')
        else:
            _require_empty_media(media)
        payload = [
            {'name': image.name, 'mimeType': image.mime_type, 'buffer': image.buffer}
            for image in images
        ]
        if modern:
            chooser.set_files(payload, timeout=_remaining(deadline))
        else:
            file_input.set_input_files(payload, timeout=_remaining(deadline))
        _verify_upload_payload(file_input, images, _remaining(deadline))
        _wait_images(page, media, len(images), deadline)
        if modern:
            media_evidence = _modern_preview_evidence(page, media, images, deadline)
        transitions = []
        for _ in range(3):
            if not media.is_visible() or inline_media:
                break
            advance = _wait_unique(page, dom.media_advance_button(media), deadline)
            # A still-visible unchanged Next/Done is not clicked a second time.
            node = advance.element_handle()
            label = advance.inner_text()
            if any(label == old_label and node.evaluate('(el, old) => el === old', old_node)
                   for old_node, old_label in transitions):
                raise AgentError('dom_timeout', 'Media dialog did not advance. Inspect manually.')
            transitions.append((node, label))
            advance.click(timeout=_remaining(deadline))
            # Wait for this transition to hide the dialog or change its control.
            while media.is_visible():
                current = _unique_visible(dom.media_advance_button(media))
                if current is not None and (current.inner_text() != label
                        or not node.evaluate('(el, other) => el === other', current.element_handle())):
                    _wait_images(page, media, len(images), deadline)
                    break
                page.wait_for_timeout(min(50, _remaining(deadline)))
        if media.is_visible() and not inline_media:
            raise AgentError('dom_timeout', 'Media dialog remains open. Inspect manually.')
        composer = _wait_unique(page, page.locator(dom.COMPOSER), deadline)
        _wait_images(page, composer, len(images), deadline)
        _wait_unique(page, dom.post_button(composer), deadline)
        # Revalidate the author, exact text, uploads and final control at the
        # last reversible point; page-wide editors/buttons are never used.
        selectors.detect_block(page)
        composer = _unique_visible(page.locator(dom.COMPOSER))
        if composer is None:
            raise AgentError('dom_timeout', 'The personal composer is no longer visible.')
        current_author = _modern_author(page, composer, deadline) if modern else _personal_author(composer, page.url)
        if (not _same_modern_author(author, current_author) if modern else current_author != author):
            raise AgentError('unsupported_identity', 'Composer author changed. Inspect manually.')
        author = current_author
        if not _images_ready(composer, len(images)):
            raise AgentError('upload_failed', 'Image previews changed before submission. Inspect manually.')
        preview_evidence = _modern_preview_evidence(page, composer, images, deadline) if modern else None
        if modern and [record['payload'] for record in media_evidence] != [record['payload'] for record in preview_evidence]:
            raise AgentError('upload_failed', 'Attachment order differs from verified media thumbnails.')
        editor = _unique_visible(composer.locator(dom.EDITOR))
        if editor is None:
            raise AgentError('dom_timeout', 'Composer editor is no longer visible.')
        actual_text = _editor_text(editor).replace('\r\n', '\n').replace('\r', '\n')
        if actual_text != approved_text and actual_text.replace('\n\n', '\n') != approved_text:
            raise AgentError('text_mismatch', 'Composer text differs from approved text. Inspect manually.')
        post_button = _unique_visible(dom.post_button(composer))
        if post_button is None:
            raise AgentError('dom_timeout', 'Composer Post button is no longer visible.')
        if not post_button.is_enabled():
            raise AgentError('submission_disabled', 'LinkedIn Post is disabled. Inspect the draft manually.')
        click_timeout = _remaining(deadline)
        baseline = _capture_final_dispatch(post_button, composer, approved_text, author, len(images), click_timeout, preview_evidence)
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError('composer_failed', 'Could not prepare the LinkedIn composer. Inspect manually.') from exc

    try:
        try:
            post_button.click(timeout=click_timeout)
            canceled = baseline.evaluate('capture => !capture.dispatched && !capture.error && capture.canceled')
            if not canceled:
                return wait_for_new_confirmation(page, baseline, timeout_ms)
        finally:
            # Remove on success, missing evidence, and click exceptions alike.
            # A cleanup failure also remains inside the uncertainty boundary.
            _remove_dispatch_capture(baseline)
    except Exception as exc:
        raise AgentError(
            'submission_uncertain',
            'Submission may have completed. Inspect LinkedIn manually before retrying.',
            True,
        ) from exc
    # Only an acknowledged synchronous cancellation AND successful cleanup can
    # establish a pre-submit failure after the click invocation. All exceptions
    # above remain uncertain, including lost cancellation acknowledgements.
    raise AgentError(canceled, 'Draft changed at the final click. Submission was canceled; inspect the draft manually.')
