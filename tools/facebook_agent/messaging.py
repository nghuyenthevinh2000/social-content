"""Direct-message navigation, humanized typing, and one-click sending.

Adapted from the reference messaging tool's flow (open a profile, open its
message composer, type, send) while keeping this project's guarantees: explicit
recipients, exact-text checks before sending, humanized keystrokes, a single
dispatched click, and no automatic retry of an uncertain send.
"""

import random
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .models import AgentError
from .pacing import MessagePacer
from . import dom, selectors

TYPING_DELAY_RANGE = (0.02, 0.08)
SAFETY_CODES = (
    'not_authenticated', 'browser_challenge', 'account_restricted', 'unexpected_destination')


def _type_humanized(page, editor, text, rng):
    """Type text character by character with jittered pauses.

    Enter sends a message, so a literal newline is typed as Shift+Enter, which
    inserts a line break in the composer instead of dispatching the message.
    """
    editor.click()
    for char in text:
        if char == '\n':
            page.keyboard.press('Shift+Enter')
        else:
            page.keyboard.type(char)
        page.wait_for_timeout(int(rng.uniform(*TYPING_DELAY_RANGE) * 1000))


def send_message(page, url, text, timeout_ms=15000, rng=None) -> dict:
    """Send one custom direct message and verify it appears in the conversation.

    Never retries a dispatched send: a missing confirmation is reported as
    'uncertain' and the caller keeps the tab open for manual inspection.
    """
    rng = rng if rng is not None else random.Random()
    if not isinstance(text, str) or not text.strip() or '\x00' in text:
        raise AgentError('invalid_content', 'Provide nonempty message text without NUL bytes.')
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
        selectors.check_block(page)
        if selectors.visible(dom.cannot_message_notice(page)).count():
            raise AgentError('cannot_message', 'Facebook reports this recipient cannot be messaged.', True)
        triggers = dom.message_button(page)
        try:
            selectors.visible(triggers).first.wait_for(state='visible', timeout=timeout_ms)
        except PlaywrightTimeout:
            selectors.check_block(page)
            if selectors.visible(dom.cannot_message_notice(page)).count():
                raise AgentError('cannot_message', 'Facebook reports this recipient cannot be messaged.', True)
            raise AgentError('message_button_missing', 'No Message control found on this profile.', True)
        trigger = selectors.unique(triggers, 'Message button')
        trigger.click(timeout=timeout_ms)
        dialogs = dom.message_dialog(page)
        selectors.visible(dialogs).first.wait_for(state='visible', timeout=timeout_ms)
        dialog = selectors.unique(dialogs, 'message dialog')
        editor = selectors.unique(dom.message_textbox(dialog), 'message input')
        # Never append to a draft Facebook restored into the composer.
        if editor.inner_text().strip():
            raise AgentError('unexpected_content', 'The message composer already contains text. Clear it manually.', True)
        _type_humanized(page, editor, text, rng)
        # innerText uses LF regardless of the input's line-ending convention.
        if editor.inner_text().replace('\r\n', '\n') != text.replace('\r\n', '\n'):
            raise AgentError('content_changed', 'Message input differs from the supplied text. Nothing sent.', True)
        submit = selectors.unique(dom.send_button(dialog), 'Send button')
        deadline = time.monotonic() + timeout_ms / 1000
        # Playwright 1.50 misroutes Locator.is_enabled to is_editable.
        while submit.is_disabled():
            selectors.check_block(page)
            if time.monotonic() >= deadline:
                raise AgentError('submit_disabled', 'Send button remained disabled; nothing sent.', True)
            page.wait_for_timeout(100)
        selectors.check_block(page)
        old_bubbles = selectors.visible(dom.sent_bubble(dialog, text)).count()
    except AgentError:
        raise
    except Exception as exc:
        selectors.check_block(page)
        raise AgentError('dom_error', f'Message preparation failed before sending: {exc}', True) from exc

    result = {
        'status': 'uncertain', 'url': url, 'text': text, 'human_action_required': True,
        'message': 'Check the open Facebook tab before sending this message again.',
    }
    # From this point forward every failure is uncertain, including click timeouts.
    try:
        submit.click(timeout=timeout_ms, no_wait_after=True)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            selectors.check_block(page)
            fresh = selectors.visible(dom.sent_bubble(dialog, text)).count() > old_bubbles
            if fresh and not editor.inner_text().strip():
                result.update(status='confirmed', human_action_required=False,
                              message='The message appears in the conversation and the composer cleared.')
                return result
            page.wait_for_timeout(100)
    except Exception as exc:
        result['detail'] = str(exc)
    return result


def run_plan(page, recipients: list[dict], timeout_ms: int = 15000, pacer: MessagePacer | None = None,
             max_messages: int = 50) -> dict:
    """Send one custom message per recipient, pacing between attempts.

    A safety block (login, challenge, restriction) stops the run immediately.
    Send failures are recorded per recipient without aborting the rest. The run
    stops early once max_messages recipients have been attempted.
    """
    pacer = pacer if pacer is not None else MessagePacer()
    results = []
    confirmed = uncertain = failed = 0
    stopped_reason = None
    for index, entry in enumerate(recipients):
        if max_messages > 0 and index >= max_messages:
            stopped_reason = 'max_messages_reached'
            break
        try:
            outcome = send_message(page, entry['url'], entry['message'], timeout_ms=timeout_ms)
        except AgentError as exc:
            record = {'url': entry['url'], 'label': entry.get('label'), 'status': 'failed',
                      'error': {'code': exc.code, 'message': exc.message}}
            if exc.code in SAFETY_CODES:
                record['status'] = 'aborted'
                results.append(record)
                stopped_reason = exc.code
                break
            results.append(record)
            failed += 1
        else:
            results.append({**outcome, 'label': entry.get('label')})
            if outcome['status'] == 'confirmed':
                confirmed += 1
            else:
                uncertain += 1
        pacer.after_attempt()
    return {
        'requested': len(recipients),
        'attempted': confirmed + uncertain + failed,
        'confirmed': confirmed,
        'uncertain': uncertain,
        'failed': failed,
        'stopped_reason': stopped_reason,
        'results': results,
    }
