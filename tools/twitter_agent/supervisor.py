"""Interactive supervisor review orchestration, approval binding, and submission loop."""

from pathlib import Path
import select
import sys
import time
from typing import Callable, Optional

from .browser import Browser
from .models import AgentError
from .replies import inspect_reply, prepare_reply, submit_reply
from .store import Store


def review_once(store: Store, page, decide: Callable[[dict], str]) -> bool:
    """Process a single pending draft: prepare, inspect, get decision, and submit."""
    draft = store.claim_next()
    if draft is None:
        return False

    # Prepare browser tab
    try:
        review_info = prepare_reply(page, draft, store.artifact_dir)
    except Exception as exc:
        store.finish(draft['id'], 'failed', {'error': str(exc)})
        return True

    review_info['draft_id'] = draft['id']
    review_info['text'] = draft['text']

    try:
        decision = decide(review_info)
    except Exception as exc:
        store.defer(draft['id'], f'Decision callback error: {exc}')
        return True

    decision_str = str(decision).strip().lower()
    if decision_str.startswith('reject'):
        store.reject(draft['id'])
        return True
    elif decision_str.startswith('defer'):
        store.defer(draft['id'], 'Deferred by supervisor.')
        return True
    elif not decision_str.startswith('approve'):
        store.defer(draft['id'], f'Unrecognized decision: {decision}')
        return True

    # Approve path
    try:
        current_digest = inspect_reply(page, draft)
    except Exception as exc:
        store.defer(draft['id'], f'DOM inspection failed: {exc}')
        return True

    if current_digest != draft['digest']:
        store.defer(draft['id'], 'Reviewed target or text changed before submission.')
        return True

    try:
        store.begin_submission(draft['id'], draft['digest'])
    except Exception as exc:
        try:
            store.defer(draft['id'], str(exc))
        except Exception:
            pass
        return True

    # Once begin_submission has committed, submit click occurs.
    # Any subsequent error MUST result in uncertain state, never re-queued.
    try:
        outcome = submit_reply(page, draft, store.artifact_dir)
    except Exception as exc:
        store.finish(draft['id'], 'uncertain', {'error': str(exc)})
    else:
        store.finish(draft['id'], outcome['state'], outcome)

    return True


def _render_strategy_hud(store: Store, info: dict) -> str:
    """Render strategy HUD lines for watchlist status and burst rate warnings."""
    lines = []
    author = info.get('target_author')
    if author:
        clean_author = str(author).strip().lstrip('@').lower()
        watchlist = store.get_watchlist()
        watched_handles = {item['handle'].lower() for item in watchlist}
        if clean_author in watched_handles:
            lines.append('[★ WATCHLIST TARGET]')

    now = store.clock()
    with store._connection() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'submission_started' AND created_at > ?",
            (now - 1800,)
        ).fetchone()
        burst_count = row[0] if row else 0

    if burst_count >= 2:
        lines.append('[⚠️ DEBOOST WARNING: High burst frequency]')

    return '\n'.join(lines)


def supervise(store: Store, browser: Browser, prompt_fn: Optional[Callable[[dict], str]] = None) -> None:
    """Run interactive supervisor loop with visible tab and exclusive lock."""
    with store.supervisor_lock():
        store.recover()
        page = browser.new_page()

        def default_prompt(info: dict) -> str:
            draft_id = info['draft_id']
            sys.stderr.write('\n' + '=' * 60 + '\n')
            sys.stderr.write(f"Draft ID:        {draft_id}\n")
            sys.stderr.write(f"Target URL:      {info['target_url']}\n")
            sys.stderr.write(f"Target Author:   {info.get('target_author', '')}\n")
            sys.stderr.write(f"Target Text:     {info.get('target_text', '')}\n")
            sys.stderr.write(f"Proposed Reply:  {info['text']}\n")
            if info.get('screenshot'):
                sys.stderr.write(f"Screenshot:      {info['screenshot']}\n")
            if info.get('warning'):
                sys.stderr.write(f"Warning:         {info['warning']}\n")
            hud = _render_strategy_hud(store, info)
            if hud:
                sys.stderr.write(f"{hud}\n")
            sys.stderr.write('=' * 60 + '\n')
            sys.stderr.write(f"Enter 'approve {draft_id}', 'reject {draft_id}', or 'defer':\n")
            sys.stderr.flush()

            while True:
                # Read input with timeout to allow heartbeat updates
                store.heartbeat()
                rlist, _, _ = select.select([sys.stdin], [], [], 1.0)
                if rlist:
                    line = sys.stdin.readline()
                    if not line:
                        raise KeyboardInterrupt('EOF received')
                    cmd = line.strip()
                    parts = cmd.split()
                    if not parts:
                        continue
                    action = parts[0].lower()
                    if action == 'defer':
                        return 'defer'
                    if len(parts) >= 2 and parts[1] == draft_id:
                        if action in ('approve', 'reject'):
                            return action
                    sys.stderr.write(f"Invalid command. Use 'approve {draft_id}', 'reject {draft_id}', or 'defer'.\n")
                    sys.stderr.flush()

        decide = prompt_fn or default_prompt

        try:
            while True:
                store.heartbeat()
                processed = review_once(store, page, decide)
                if not processed:
                    time.sleep(1.0)
        except (KeyboardInterrupt, SystemExit):
            sys.stderr.write('\nSupervisor exiting. Recovering reviewing drafts...\n')
            sys.stderr.flush()
            store.recover()
