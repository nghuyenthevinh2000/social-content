"""Direct publishing CLI with structured JSON output and stable exit codes."""

import argparse
import json

from .browser import Browser
from .models import AgentError, validate_content
from .posting import inspect_profile, publish


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise AgentError('invalid_arguments', message)


def build_parser():
    parser = JsonArgumentParser(prog='facebook_agent', description='Publish approved content to your Facebook personal profile through visible Chrome.')
    parser.add_argument('--cdp', default='http://127.0.0.1:9222', help='Existing Chrome CDP endpoint')
    parser.add_argument('--timeout-ms', type=int, default=15000, help='Timeout per DOM stage (default: 15000)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Check connection, login, and personal-profile identity without posting')
    post = commands.add_parser('post', help='Publish supplied approved content directly, without prompting')
    post.add_argument('--text', required=True, help='Exact approved post text')
    post.add_argument('--image', help='Optional local PNG, JPEG, GIF, or WebP image')
    return parser


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.timeout_ms <= 0:
            raise AgentError('invalid_arguments', 'timeout-ms must be positive.')
        if args.command == 'post':
            text, image = validate_content(args.text, args.image)
        with Browser(endpoint=args.cdp, timeout_ms=args.timeout_ms) as browser:
            if args.command == 'doctor':
                data = {'connected': True, 'authenticated': True, 'profile': inspect_profile(browser.page, args.timeout_ms), 'endpoint': args.cdp}
            else:
                # Keep the visible tab for both successful posts and manual recovery.
                browser.keep_page = True
                data = publish(browser.page, text, image=image, timeout_ms=args.timeout_ms)
        uncertain = data.get('status') == 'uncertain'
        print(json.dumps({'ok': not uncertain, 'data': data}, ensure_ascii=False, indent=2))
        return 4 if uncertain else 0
    except SystemExit as exc:
        return exc.code
    except AgentError as exc:
        print(json.dumps({'ok': False, 'error': {'code': exc.code, 'message': exc.message,
                                               'human_action_required': exc.human_action_required}}, indent=2))
        return 2 if exc.code in ('invalid_arguments', 'invalid_content', 'invalid_image') else 3
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': {'code': 'internal_error', 'message': str(exc),
                                               'human_action_required': True}}, indent=2))
        return 1
