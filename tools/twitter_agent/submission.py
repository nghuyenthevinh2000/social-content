"""One-shot reply submission from the caller's terminal, without a review daemon."""

from .models import AgentError
from .replies import inspect_reply, prepare_reply, submit_reply


def submit_draft(store, browser, draft_id: str) -> dict:
    """Submit one selected draft; uncertain attempts are never retried."""
    with store.submission_lock():
        store.recover()
        draft = store.claim(draft_id)
        page = browser.new_page()
        try:
            prepare_reply(page, draft, store.artifact_dir)
            digest = inspect_reply(page, draft)
            if digest != draft['digest']:
                raise AgentError('review_changed', 'Target or composer text changed.')
            store.begin_submission(draft_id, digest)
        except Exception as exc:
            store.finish(draft_id, 'failed', {'error': str(exc)})
            raise
        try:
            outcome = submit_reply(page, draft, store.artifact_dir)
        except Exception as exc:
            outcome = {'state': 'uncertain', 'error': str(exc), 'retry': False}
        store.finish(draft_id, outcome['state'], outcome)
        return store.get(draft_id)
