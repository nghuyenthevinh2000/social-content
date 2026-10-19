"""Direct publishing CLI with structured JSON output and stable exit codes."""

import argparse
import json
from pathlib import Path

from tools.common.cli_support import JsonArgumentParser, emit_error, emit_success
from tools.common.config import get_default_doctor_timeout_ms, load_environment

load_environment(include_repository=True)

from .browser import Browser
from .messaging import run_plan
from .models import (
    AgentError, load_group_names, load_message_plan, validate_content, validate_group_names, validate_video)
from .pacing import MessagePacer
from .posting import inspect_profile, publish


def build_parser():
    doctor_timeout = get_default_doctor_timeout_ms()
    parser = JsonArgumentParser(prog='facebook_agent', description='Publish approved content to your Facebook profile or explicitly named active Page.')
    parser.add_argument('--cdp', default='http://127.0.0.1:9222', help='Existing Chrome CDP endpoint')
    parser.add_argument('--timeout-ms', type=int, default=None, help=f'Timeout per DOM stage (default: {doctor_timeout} for doctor, 15000 for post and message)')
    commands = parser.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Check connection, login, and personal-profile identity without posting')
    doctor.add_argument('--timeout-ms', type=int, default=argparse.SUPPRESS, help=f'Timeout per DOM stage (default: {doctor_timeout})')
    doctor.add_argument('--page-name', help='Exact name of the already-active Fanpage (default: personal profile only)')
    doctor.add_argument('--page-id', help='Expected active Page ID from its profile.php?id= URL')
    reels = commands.add_parser('reels', help='Read visible Reels recommendations for an explicitly identified active Page')
    reels.add_argument('--page-id', required=True, help='Expected already-active Page ID')
    reels.add_argument('--limit', type=int, default=15, help='Number of feed observations (1-50)')
    reels.add_argument('--output', required=True, help='Save raw observations as JSON')
    judge = commands.add_parser('judge-reels', help='Use Jev to classify saved observations; does not open Facebook')
    judge.add_argument('--input', required=True, help='Saved Reels observations JSON')
    judge.add_argument('--product-dir', required=True, help='Directory containing product-marketing.json')
    judge.add_argument('--output', required=True, help='New judgments JSON; raw input is preserved')
    judge.add_argument('--limit', type=int, default=10, help='Maximum paid requests (1-100), one per Reel')
    judge.add_argument('--threshold', type=float, default=0.9, help='Provisional exclusion threshold; uncertainty allows')
    judge.add_argument('--model', default='jev-latest', help='TypeSafe model; resolved model is recorded')
    judge.add_argument('--dry-run', action='store_true', help='Validate inputs and save run manifest without API calls')
    judge.add_argument('--approve-api', action='store_true', help='Authorize sending observed text and product context to TypeSafe for paid judgments')
    judge.add_argument('--vietnamese-audience', action='store_true', help='Also judge Vietnamese-speaking audience fit independently of promotion')
    judge.add_argument('--target-count', type=int, help='Stop after this many allowed audience-matching Reels')
    benchmark = commands.add_parser('benchmark-reels', help='Time collection-only versus collection plus Jev on the same feed sample')
    benchmark.add_argument('--page-id', required=True)
    benchmark.add_argument('--product-dir', required=True)
    benchmark.add_argument('--output-dir', required=True, help='New directory for raw data, Jev judgments, shortlist, and timing')
    benchmark.add_argument('--target-count', type=int, default=10)
    benchmark.add_argument('--max-observations', type=int, default=50)
    benchmark.add_argument('--approve-api', action='store_true')
    post = commands.add_parser('post', help='Publish supplied approved content directly, without prompting')
    post.add_argument('--text', required=True, help='Exact approved post text')
    post.add_argument('--image', help='Optional local PNG, JPEG, GIF, or WebP image')
    post.add_argument('--video', help='Optional local MP4/MOV/WebM/etc. video (mutually exclusive with --image)')
    post.add_argument('--page-name', help='Exact name of the already-active Fanpage (default: personal profile only)')
    post.add_argument('--page-id', help='Expected active Page ID from its profile.php?id= URL')
    post.add_argument('--group', action='append', dest='groups', default=None,
                      help='Exact group name to also share the post to (repeatable, max 9)')
    post.add_argument('--groups-file', help="Path to a JSON array of group names to also share to (max 9)")
    post.add_argument('--timeout-ms', type=int, default=argparse.SUPPRESS, help='Timeout per DOM stage (default: 15000)')
    message = commands.add_parser('message', help='Send one custom direct message per recipient from a JSON plan')
    message.add_argument('--plan', required=True, help='Path to a JSON plan: an array of {url, message} entries')
    message.add_argument('--max-messages', type=int, default=50, help='Maximum recipients to attempt in this run (default: 50)')
    message.add_argument('--min-delay-ms', type=int, default=3200, help='Minimum pause between recipients in ms (default: 3200)')
    message.add_argument('--max-delay-ms', type=int, default=4500, help='Maximum pause between recipients in ms (default: 4500)')
    message.add_argument('--cooldown-every', type=int, default=50, help='Take a long cooldown every N recipients (0 disables, default: 50)')
    message.add_argument('--cooldown-ms', type=int, default=240000, help='Base cooldown in ms at each interval (default: 240000)')
    message.add_argument('--timeout-ms', type=int, default=argparse.SUPPRESS, help='Timeout per DOM stage (default: 15000)')
    return parser


def _exit_code(command: str, data: dict) -> int:
    if command == 'message':
        if data.get('uncertain'):
            return 4
        if data.get('failed') or (data.get('stopped_reason') and data['stopped_reason'] != 'max_messages_reached'):
            return 3
        return 0
    return 4 if data.get('status') == 'uncertain' else 0


def _build_pacer(args) -> MessagePacer:
    if args.max_messages <= 0:
        raise AgentError('invalid_arguments', 'max-messages must be positive.')
    for name, value in (('min-delay-ms', args.min_delay_ms), ('max-delay-ms', args.max_delay_ms),
                        ('cooldown-ms', args.cooldown_ms), ('cooldown-every', args.cooldown_every)):
        if value < 0:
            raise AgentError('invalid_arguments', f'{name} must not be negative.')
    if args.max_delay_ms < args.min_delay_ms:
        raise AgentError('invalid_arguments', 'max-delay-ms must be at least min-delay-ms.')
    return MessagePacer(min_delay_s=args.min_delay_ms / 1000, max_delay_s=args.max_delay_ms / 1000,
                        cooldown_every=args.cooldown_every, cooldown_s=args.cooldown_ms / 1000)


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == 'benchmark-reels':
            from .reel_benchmark import run_benchmark
            data = run_benchmark(args)
            emit_success(data, ensure_ascii=False)
            return 0
        if args.command == 'judge-reels':
            from .reel_decisions import judge_file
            data = judge_file(args)
            emit_success(data, ensure_ascii=False)
            return 0
        page_name = getattr(args, 'page_name', None)
        page_id = getattr(args, 'page_id', None)
        timeout_ms = args.timeout_ms
        if timeout_ms is None:
            timeout_ms = get_default_doctor_timeout_ms() if args.command == 'doctor' else 15000
        if timeout_ms <= 0:
            raise AgentError('invalid_arguments', 'timeout-ms must be positive.')
        if page_name is not None and not page_name.strip():
            raise AgentError('invalid_arguments', 'page-name must not be blank.')
        if page_id is not None and (not page_id.isascii() or not page_id.isdecimal()):
            raise AgentError('invalid_arguments', 'page-id must contain ASCII digits only.')
        text = image = video = recipients = pacer = groups = None
        if args.command == 'reels' and not 1 <= args.limit <= 50:
            raise AgentError('invalid_arguments', 'Reels limit must be between 1 and 50.')
        if args.command == 'post':
            if args.image and args.video:
                raise AgentError('invalid_arguments', 'Provide either --image or --video, not both.')
            text, image = validate_content(args.text, args.image)
            video = validate_video(args.video)
            from_file = load_group_names(args.groups_file) if args.groups_file else []
            combined = (args.groups or []) + from_file
            groups = validate_group_names(combined) if combined else None
        elif args.command == 'message':
            recipients = load_message_plan(args.plan)
            pacer = _build_pacer(args)
        with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
            if args.command == 'doctor':
                data = browser.doctor(page_name=page_name, page_id=page_id)
            elif args.command == 'reels':
                from .reels import collect_reels
                output = Path(args.output)
                if output.exists():
                    raise AgentError('invalid_arguments', 'Output file already exists; choose a new path.')
                output.parent.mkdir(parents=True, exist_ok=True)
                data = collect_reels(browser, page_id, args.limit)
                with output.open('x') as stream:
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                data = {'profile': data['profile'], 'observations': len(data['records']), 'output': str(output)}
            elif args.command == 'post':
                # Keep the visible tab for both successful posts and manual recovery.
                browser.keep_page = True
                data = publish(browser.page, text, image=image, video=video, timeout_ms=timeout_ms,
                               page_name=page_name, page_id=page_id, groups=groups)
            else:
                # Keep the visible tab so any uncertain send can be inspected.
                browser.keep_page = True
                data = run_plan(browser.page, recipients, timeout_ms=timeout_ms, pacer=pacer,
                                max_messages=args.max_messages)
        code = _exit_code(args.command, data)
        emit_success(data, ok=code == 0, ensure_ascii=False)
        return code
    except SystemExit as exc:
        return exc.code
    except AgentError as exc:
        emit_error(exc.code, exc.message, exc.human_action_required)
        return 2 if exc.code in ('invalid_arguments', 'invalid_content', 'invalid_image', 'invalid_video', 'invalid_plan', 'invalid_groups') else 3
    except Exception as exc:
        emit_error('internal_error', str(exc), True)
        return 1
