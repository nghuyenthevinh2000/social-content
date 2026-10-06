"""CLI entry point exposing doctor and start-browser with JSON output and stable exit codes."""

import argparse
import json
import sys
from typing import List, Optional

from .config import (
    DEFAULT_DOCTOR_TIMEOUT_MS,
    DEFAULT_PORT,
    DEFAULT_PROFILE_DIR,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    AgentError,
)
from .doctor import run_doctor
from .launcher import start_browser


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises AgentError on invalid arguments while preserving help output."""
    def error(self, message: str):
        raise AgentError('invalid_arguments', message)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        prog='social_agent',
        description='Shared browser CDP diagnostics and launcher foundation for social content tools.',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    commands = parser.add_subparsers(dest='command', required=True)

    # doctor command
    doctor = commands.add_parser(
        'doctor',
        help='Check browser connectivity and context readiness without platform navigation.',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    doctor.add_argument(
        '-b',
        '--backend',
        dest='backend',
        choices=['invisible', 'cdp'],
        default=None,
        help='Browser backend (default: invisible or env BROWSER_BACKEND)',
    )
    doctor.add_argument(
        '--cdp',
        '--endpoint',
        dest='endpoint',
        default=None,
        help='Chrome CDP endpoint (default: http://127.0.0.1:9222 or env CDP_ENDPOINT)',
    )
    doctor.add_argument(
        '--timeout-ms',
        type=int,
        default=None,
        help=f'Timeout in milliseconds (default: {DEFAULT_DOCTOR_TIMEOUT_MS} or env DEFAULT_DOCTOR_TIMEOUT_MS)',
    )
    doctor.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Deterministic fingerprint seed for invisible browser',
    )
    doctor.add_argument(
        '--binary',
        dest='binary',
        default=None,
        help='Path to browser engine binary (for invisible browser or custom Chrome)',
    )
    doctor.add_argument(
        '--headless',
        dest='headless',
        action='store_true',
        default=None,
        help='Run browser in headless mode',
    )

    # start-browser command
    start = commands.add_parser(
        'start-browser',
        help='Detect or start invisible stealth browser or responsive CDP browser.',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    start.add_argument(
        '-b',
        '--backend',
        dest='backend',
        choices=['invisible', 'cdp'],
        default=None,
        help='Browser backend (default: invisible or env BROWSER_BACKEND)',
    )
    start.add_argument(
        '-p',
        '--port',
        type=int,
        default=None,
        help=f'CDP remote debugging port (default: {DEFAULT_PORT})',
    )
    start.add_argument(
        '-d',
        '--data-dir',
        default=None,
        help=f'Browser profile directory (default: {DEFAULT_PROFILE_DIR})',
    )
    start.add_argument(
        '--timeout',
        type=float,
        default=None,
        help=f'Readiness check timeout in seconds (default: {DEFAULT_READINESS_TIMEOUT_SECONDS})',
    )
    start.add_argument(
        '--chrome-bin',
        default=None,
        help='Path to Chromium/Chrome executable (default: auto-detected or env CHROME_BIN)',
    )
    start.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Deterministic fingerprint seed for invisible browser',
    )
    start.add_argument(
        '--binary',
        dest='binary',
        default=None,
        help='Path to browser engine binary (for invisible browser)',
    )
    start.add_argument(
        '--headless',
        dest='headless',
        action='store_true',
        default=None,
        help='Run browser in headless mode',
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)

        if args.command == 'doctor':
            data = run_doctor(
                endpoint=args.endpoint,
                timeout_ms=args.timeout_ms,
                backend=args.backend,
                seed=args.seed,
                headless=args.headless,
                binary_path=args.binary,
            )
        elif args.command == 'start-browser':
            data = start_browser(
                port=args.port,
                data_dir=args.data_dir,
                timeout=args.timeout,
                chrome_bin=args.chrome_bin,
                backend=args.backend,
                seed=args.seed,
                headless=args.headless,
                binary_path=args.binary,
            )
        else:
            raise AgentError('invalid_arguments', f'Unknown command: {args.command}')

        sys.stdout.write(json.dumps({'ok': True, 'data': data}, ensure_ascii=False, indent=2) + '\n')
        sys.stdout.flush()
        return 0

    except SystemExit as exc:
        return exc.code

    except AgentError as exc:
        sys.stdout.write(json.dumps({
            'ok': False,
            'error': {
                'code': exc.code,
                'message': exc.message,
                'human_action_required': exc.human_action_required,
            }
        }, ensure_ascii=False, indent=2) + '\n')
        sys.stdout.flush()
        return 2 if exc.code == 'invalid_arguments' else 3

    except Exception as exc:
        sys.stdout.write(json.dumps({
            'ok': False,
            'error': {
                'code': 'internal_error',
                'message': str(exc),
                'human_action_required': True,
            }
        }, ensure_ascii=False, indent=2) + '\n')
        sys.stdout.flush()
        return 1
