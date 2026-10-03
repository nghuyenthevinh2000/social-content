"""Direct approved-input LinkedIn CLI with JSON results and fail-closed exits."""

import argparse
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / '.env'
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

from .browser import Browser
from .models import AgentError, validate_inputs
from .posts import publish_post


def get_default_doctor_timeout_ms() -> int:
    try:
        return int(os.environ.get('DEFAULT_DOCTOR_TIMEOUT_MS', 30000))
    except (ValueError, TypeError):
        return 30000


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's message can contain arbitrary supplied post text or paths.
        raise AgentError(
            'invalid_arguments',
            'Invalid arguments. Use --help; post requires --text and at least one --image, '
            'and global options must precede the command.',
        )


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        prog='linkedin_agent', description='Direct approved-input LinkedIn personal posting',
        allow_abbrev=False,
    )
    parser.add_argument('--cdp', default='http://127.0.0.1:9222',
                        help='Shared Chrome DevTools Protocol endpoint')
    parser.add_argument('--timeout-ms', type=int, default=None,
                        help='Positive browser operation timeout in milliseconds')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Check Chrome and LinkedIn login without posting',
                        allow_abbrev=False)
    post = commands.add_parser('post', help='Publish already-approved text and images directly',
                               allow_abbrev=False)
    post.add_argument('--text', required=True, help='Exact already-approved post text')
    post.add_argument('--image', action='append', required=True, metavar='PATH',
                      help='PNG/JPEG image path; repeat for multiple ordered images')
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        timeout_ms = args.timeout_ms
        if timeout_ms is None:
            timeout_ms = get_default_doctor_timeout_ms() if args.command == 'doctor' else 15000
        if timeout_ms <= 0:
            raise AgentError('invalid_timeout', 'Browser timeout must be positive.')
        # Snapshot and validate all approved inputs before even constructing Browser.
        if args.command == 'post':
            text, images = validate_inputs(args.text, args.image)
        with Browser(endpoint=args.cdp, timeout_ms=timeout_ms) as browser:
            if args.command == 'doctor':
                data = browser.doctor()
            else:
                page = browser.new_page()
                try:
                    data = publish_post(page, text, images, timeout_ms=timeout_ms)
                except AgentError as error:
                    if error.code == 'submission_uncertain':
                        # Must happen inside the context, before owned-tab cleanup.
                        browser.preserve_page(page)
                    raise
        result = {'ok': True, 'data': data}
        status = 0
    except AgentError as error:
        result = {'ok': False, 'error': {
            'code': error.code, 'message': error.message,
            'human_action_required': error.human_action_required,
        }}
        if error.code in ('invalid_arguments', 'invalid_timeout', 'invalid_text', 'invalid_images'):
            status = 2
        elif error.code == 'submission_uncertain':
            status = 4
        elif error.code in (
            'browser_connection_failed', 'no_browser_context', 'browser_not_connected',
            'browser_navigation_failed', 'not_authenticated', 'browser_challenge',
            'dom_timeout', 'ambiguous_selector', 'unsupported_identity', 'upload_failed',
            'text_mismatch', 'submission_disabled', 'composer_failed',
        ):
            status = 3
        else:
            status = 1
    except Exception:
        # Never serialize exception repr/tracebacks: they may contain payloads.
        result = {'ok': False, 'error': {
            'code': 'unexpected_error', 'message': 'Unexpected failure. Inspect Chrome manually before retrying.',
            'human_action_required': True,
        }}
        status = 1
    print(json.dumps(result, indent=2))
    return status
