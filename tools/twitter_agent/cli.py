"""CLI parser, JSON output formatting, and command dispatch."""

import argparse
import csv
import json
import os
from pathlib import Path
import sys
import time
from typing import List, Optional

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / '.env'
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

from .browser import Browser
from .models import AgentError, normalize_target, validate_text
from .posts import read_posts
from .report import collect_report, write_report
from .store import Store
from .submission import submit_draft
from .topic_config import load_topics


def get_default_doctor_timeout_ms() -> int:
    try:
        return int(os.environ.get('DEFAULT_DOCTOR_TIMEOUT_MS', 30000))
    except (ValueError, TypeError):
        return 30000


DEFAULT_TOPICS = (
    'AI, LLM, claude, cursor, openai, gemini, engineering, '
    '"just shipped", "just launched", "I built", startup, founder'
)


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises AgentError on invalid arguments while preserving help."""
    def error(self, message):
        raise AgentError('invalid_arguments', message)


def emit_success(data):
    sys.stdout.write(json.dumps({'ok': True, 'data': data}, indent=2) + '\n')
    sys.stdout.flush()


def emit_error(code: str, message: str, human_action_required: bool = False):
    sys.stdout.write(json.dumps({
        'ok': False,
        'error': {
            'code': code,
            'message': message,
            'human_action_required': human_action_required,
        }
    }, indent=2) + '\n')
    sys.stdout.flush()


def error_exit_code(code: str) -> int:
    if code in (
        'invalid_target', 'invalid_text', 'invalid_limits', 'invalid_limit',
        'invalid_jsonl', 'invalid_arguments', 'invalid_mode', 'invalid_search_query',
        'invalid_handle', 'invalid_window_minutes', 'invalid_min_score',
        'invalid_topics_file', 'invalid_search_mode'
    ):
        return 2
    if code in (
        'browser_connection_failed', 'no_browser_context', 'not_authenticated',
        'browser_challenge', 'account_blocked', 'dom_timeout', 'browser_navigation_failed',
        'browser_not_connected', 'composer_dialog_missing', 'composer_textarea_missing',
        'reply_button_not_found', 'target_not_found'
    ):
        return 3
    if code in (
        'submission_running', 'submission_lock_required', 'draft_not_found',
        'paused', 'rate_limited', 'digest_mismatch', 'interactive_required',
        'review_changed', 'submit_disabled', 'duplicate_draft', 'invalid_state'
    ):
        return 4
    return 1


def build_parser() -> JsonArgumentParser:
    doctor_timeout = get_default_doctor_timeout_ms()
    parser = JsonArgumentParser(prog='twitter_agent', description='Terminal-operated X DOM CLI')
    parser.add_argument('--state-dir', default='.twitter-agent', help='Directory for database and artifacts')
    parser.add_argument('--cdp', default='http://127.0.0.1:9222', help='Chrome DevTools Protocol endpoint')
    parser.add_argument('--timeout-ms', type=int, default=None, help=f'Browser operations timeout in ms (default: {doctor_timeout} for doctor, 15000 for others)')

    subparsers = parser.add_subparsers(dest='subcommand', required=True)

    # doctor
    doc = subparsers.add_parser('doctor', help='Check CDP connectivity and X authentication')
    doc.add_argument('--timeout-ms', type=int, default=argparse.SUPPRESS, help=f'Browser operations timeout in ms (default: {doctor_timeout})')

    # timeline
    tl = subparsers.add_parser('timeline', help='Read home timeline posts')
    tl.add_argument('--limit', type=int, default=10, help='Max posts to read (1-100)')

    # search
    sr = subparsers.add_parser('search', help='Search recent posts')
    sr.add_argument('query', help='Search query string')
    sr.add_argument('--limit', type=int, default=10, help='Max posts to read (1-100)')
    sr.add_argument('--window-minutes', type=int, default=60, help='Restrict search to posts within the last N minutes')
    sr.add_argument('--min-score', type=float, default=None, help='Minimum opportunity score (0-100) to return')

    # thread
    th = subparsers.add_parser('thread', help='Read thread for post ID or URL')
    th.add_argument('target', help='Post ID or URL')
    th.add_argument('--limit', type=int, default=10, help='Max posts to read (1-100)')

    # reply
    rp = subparsers.add_parser('reply', help='Draft operations')
    rp_sub = rp.add_subparsers(dest='reply_cmd', required=True)
    prep = rp_sub.add_parser('prepare', help='Persist pending draft without submitting')
    prep.add_argument('target', help='Target post ID or URL')
    prep.add_argument('--text', required=True, help='Exact reply text')
    submit = rp_sub.add_parser('submit', help='Submit one selected draft immediately (no supervisor)')
    submit.add_argument('draft_id', help='Prepared draft ID to submit')

    # queue
    qu = subparsers.add_parser('queue', help='Import drafts from JSONL file')
    qu.add_argument('file', help='Path to UTF-8 JSONL file')

    # status
    subparsers.add_parser('status', help='Report submission activity, drafts, limits')

    # pause
    subparsers.add_parser('pause', help='Pause submissions')

    # resume
    subparsers.add_parser('resume', help='Resume submissions')

    # cancel
    cn = subparsers.add_parser('cancel', help='Cancel a pending draft')
    cn.add_argument('draft_id', help='ID of draft to cancel')

    # watchlist
    wl = subparsers.add_parser('watchlist', help='Watchlist operations')
    wl_sub = wl.add_subparsers(dest='watchlist_cmd', required=True)
    wl_add = wl_sub.add_parser('add', help='Add or update handle in watchlist')
    wl_add.add_argument('handle', help='Twitter handle to watch')
    wl_add.add_argument('--notes', default='', help='Optional notes on the account')
    wl_rem = wl_sub.add_parser('remove', help='Remove handle from watchlist')
    wl_rem.add_argument('handle', help='Twitter handle to remove')
    wl_sub.add_parser('list', help='List all watched accounts')

    # watch
    wc = subparsers.add_parser('watch', help='Discover reply opportunities from watched accounts')
    wc.add_argument('--limit', type=int, default=10, help='Max opportunities to return')
    wc.add_argument('--poll', type=int, default=None, help='Poll interval in seconds')
    wc.add_argument('--topics', nargs='?', const=DEFAULT_TOPICS, default=None,
                    help='Comma-separated topics for discovery (uses curated defaults if passed without value)')
    wc.add_argument('--window-minutes', type=int, default=None,
                    help='Restrict search to posts within the last N minutes')
    wc.add_argument('--min-score', type=float, default=None,
                    help='Minimum opportunity score (0-100) to return')

    # report
    rp = subparsers.add_parser('report', help='Report high-engagement posts across configured topics')
    rp.add_argument('--topics-file', type=Path, default=Path(__file__).parent / 'topics' / 'topics.json',
                    help='Path to topics JSON file (default: bundled topics/topics.json)')
    rp.add_argument('--window-hours', type=int, default=24, help='Lookback window in hours (default: 24)')
    rp.add_argument('--per-topic', type=int, default=5, help='Target number of selected posts per topic (default: 5)')
    rp.add_argument('--candidate-limit', type=int, default=100, help='Total candidate budget per topic split between Top and Latest (default: 100)')
    rp.add_argument('--output-dir', type=Path, default=None, help='Output directory for run artifacts (default: <state-dir>/reports)')

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except AgentError as err:
        emit_error(err.code, err.message, err.human_action_required)
        return error_exit_code(err.code)
    except SystemExit as exc:
        return exc.code

    store = Store(Path(args.state_dir))

    timeout_ms = args.timeout_ms
    if timeout_ms is None:
        timeout_ms = get_default_doctor_timeout_ms() if args.subcommand == 'doctor' else 15000
    if timeout_ms <= 0:
        emit_error('invalid_arguments', 'timeout-ms must be positive.')
        return 2

    try:
        if args.subcommand == 'doctor':
            with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                data = browser.doctor()
                emit_success(data)
                return 0

        elif args.subcommand == 'timeline':
            with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                page = browser.new_page()
                data = read_posts(page, 'timeline', None, limit=args.limit)
                emit_success(data)
                return 0

        elif args.subcommand == 'search':
            query = args.query
            if args.window_minutes is not None:
                if args.window_minutes <= 0:
                    raise AgentError('invalid_window_minutes', 'window-minutes must be positive.')
                since_time = int(time.time() - (args.window_minutes * 60))
                query = f"{query} since_time:{since_time}"

            if args.min_score is not None and (args.min_score < 0.0 or args.min_score > 100.0):
                raise AgentError('invalid_min_score', 'min-score must be between 0 and 100.')

            with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                page = browser.new_page()
                data = read_posts(page, 'search', query, limit=args.limit)
                if args.min_score is not None:
                    data['posts'] = [p for p in data.get('posts', []) if p.get('score', 0.0) >= args.min_score]
                emit_success(data)
                return 0

        elif args.subcommand == 'thread':
            with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                page = browser.new_page()
                data = read_posts(page, 'thread', args.target, limit=args.limit)
                emit_success(data)
                return 0

        elif args.subcommand == 'reply':
            if args.reply_cmd == 'prepare':
                target = normalize_target(args.target)
                validate_text(args.text)
                draft = store.enqueue(target, args.text)
                emit_success({
                    'draft': draft,
                    'browser_prepared': False,
                })
                return 0

            elif args.reply_cmd == 'submit':
                # Fail locally before opening Chrome for nonexistent or terminal drafts.
                draft = store.get(args.draft_id)
                if draft['state'] != 'pending':
                    raise AgentError('invalid_state', 'Only pending drafts can be submitted.')
                with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                    draft = submit_draft(store, browser, args.draft_id)
                emit_success({'draft': draft})
                return 0 if draft['state'] == 'submitted' else 4

        elif args.subcommand == 'queue':
            path = Path(args.file)
            if not path.is_file():
                raise AgentError('invalid_jsonl', f'Queue file not found: {args.file}')
            content = path.read_text(encoding='utf-8')
            lines = content.splitlines()
            if not lines:
                raise AgentError('invalid_jsonl', 'JSONL file is empty.')

            items = []
            for line_no, line in enumerate(lines, 1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception as exc:
                    raise AgentError('invalid_jsonl', f'Line {line_no}: invalid JSON: {exc}') from exc
                if not isinstance(obj, dict):
                    raise AgentError('invalid_jsonl', f'Line {line_no}: expected a JSON object.')
                if 'target' not in obj or 'text' not in obj:
                    raise AgentError('invalid_jsonl', f'Line {line_no}: missing required fields target or text.')
                if not isinstance(obj['target'], str) or not isinstance(obj['text'], str):
                    raise AgentError('invalid_jsonl', f'Line {line_no}: target and text must be strings.')
                try:
                    target = normalize_target(obj['target'])
                    validate_text(obj['text'])
                except AgentError as exc:
                    raise AgentError('invalid_jsonl', f'Line {line_no}: {exc.message}') from exc
                items.append((target, obj['text']))

            if not items:
                raise AgentError('invalid_jsonl', 'No valid entries found in JSONL file.')
            drafts = store.enqueue_many(items)
            emit_success({'drafts': drafts})
            return 0

        elif args.subcommand == 'status':
            data = store.status()
            emit_success(data)
            return 0

        elif args.subcommand == 'pause':
            store.set_paused(True)
            emit_success({'paused': True})
            return 0

        elif args.subcommand == 'resume':
            store.set_paused(False)
            emit_success({'paused': False})
            return 0

        elif args.subcommand == 'cancel':
            draft = store.cancel(args.draft_id)
            emit_success({'draft': draft})
            return 0

        elif args.subcommand == 'watchlist':
            if args.watchlist_cmd == 'add':
                item = store.add_watchlist(args.handle, notes=args.notes)
                emit_success({'item': item})
                return 0
            elif args.watchlist_cmd == 'remove':
                removed = store.remove_watchlist(args.handle)
                emit_success({'removed': removed})
                return 0
            elif args.watchlist_cmd == 'list':
                items = store.get_watchlist()
                emit_success({'watchlist': items})
                return 0

        elif args.subcommand == 'watch':
            if args.limit < 1 or args.limit > 100:
                raise AgentError('invalid_limit', 'Limit must be between 1 and 100.')
            if args.poll is not None and args.poll <= 0:
                raise AgentError('invalid_arguments', 'Poll interval must be greater than 0.')
            if args.window_minutes is not None and args.window_minutes <= 0:
                raise AgentError('invalid_window_minutes', 'window-minutes must be positive.')
            if args.min_score is not None and (args.min_score < 0.0 or args.min_score > 100.0):
                raise AgentError('invalid_min_score', 'min-score must be between 0 and 100.')

            def process_posts(posts_list):
                if args.min_score is not None:
                    posts_list = [p for p in posts_list if (p.get('score') if p.get('score') is not None else 0.0) >= args.min_score]
                posts_list.sort(key=lambda x: x.get('score', 0.0) if x.get('score') is not None else 0.0, reverse=True)
                seen = set()
                deduped = []
                for p in posts_list:
                    pid = p.get('id')
                    if pid:
                        if pid in seen:
                            continue
                        seen.add(pid)
                    deduped.append(p)
                return deduped[:args.limit]

            if args.topics is not None:
                topics = [t.strip() for row in csv.reader([args.topics], skipinitialspace=True) for t in row if t.strip()]

                def run_watch_cycle():
                    all_posts = []
                    with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                        for t in topics:
                            query_topic = f'"{t}"' if ' ' in t and not (t.startswith('"') and t.endswith('"')) else t
                            suffix = 'min_faves:5 lang:en -filter:links'
                            if args.window_minutes is not None:
                                since_time = int(time.time() - (args.window_minutes * 60))
                                suffix = f"{suffix} since_time:{since_time}"
                            query = f"{query_topic} {suffix}"
                            res = read_posts(browser.page, 'search', query, limit=args.limit)
                            posts = res.get('posts', [])
                            for p in posts:
                                annotated = dict(p)
                                annotated['topic'] = t
                                all_posts.append(annotated)
                    return process_posts(all_posts)

            else:
                watchlist = store.get_watchlist()
                if not watchlist:
                    emit_success({
                        'opportunities': [],
                        'message': 'Watchlist is empty. Add accounts with watchlist add <handle>.',
                    })
                    return 0

                def run_watch_cycle():
                    all_posts = []
                    with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                        for item in watchlist:
                            res = read_posts(browser.page, 'search', f"from:{item['handle']}", limit=args.limit)
                            posts = res.get('posts', [])
                            for p in posts:
                                annotated = dict(p)
                                annotated['watchlist_handle'] = item['handle']
                                annotated['watchlist_notes'] = item.get('notes', '')
                                all_posts.append(annotated)
                    return process_posts(all_posts)

            if args.poll is None:
                opps = run_watch_cycle()
                emit_success({'opportunities': opps})
                return 0
            else:
                try:
                    while True:
                        opps = run_watch_cycle()
                        emit_success({'opportunities': opps})
                        time.sleep(args.poll)
                except (KeyboardInterrupt, SystemExit):
                    return 0

        elif args.subcommand == 'report':
            if args.window_hours <= 0:
                raise AgentError('invalid_arguments', 'window-hours must be positive.')
            if not 2 <= args.candidate_limit <= 100:
                raise AgentError('invalid_arguments', 'candidate-limit must be between 2 and 100.')
            if not 1 <= args.per_topic <= args.candidate_limit:
                raise AgentError('invalid_arguments', 'per-topic must be between 1 and candidate-limit.')

            topics = load_topics(args.topics_file)
            end = int(time.time())
            start = end - args.window_hours * 3600

            with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
                report = collect_report(
                    browser.page,
                    topics,
                    topics_file=str(args.topics_file.resolve()),
                    start=start,
                    end=end,
                    per_topic=args.per_topic,
                    candidate_limit=args.candidate_limit,
                )

            paths = write_report(report, args.output_dir or Path(args.state_dir) / 'reports')
            emit_success({
                'artifacts': paths,
                'summary': report['summary'],
                'partial': report['partial'],
                'coverage': report['coverage'],
                'window': report['window'],
            })
            return 4 if report['partial'] else 0

    except AgentError as err:
        emit_error(err.code, err.message, err.human_action_required)
        return error_exit_code(err.code)
    except Exception as exc:
        emit_error('unexpected_error', str(exc))
        return 1

    return 0
