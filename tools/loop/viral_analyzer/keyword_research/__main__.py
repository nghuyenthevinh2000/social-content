"""Unified CLI entrypoint for keyword discovery, hashtag verification, and gated scraping."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from tools.loop.viral_analyzer.keyword_research import config, pipeline
from tools.loop.viral_analyzer.keyword_research.campaign import generate, scrape, verify


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.loop.viral_analyzer.keyword_research",
        description="Unified CLI for cross-platform keyword search and campaign hashtag verification.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pipeline.register_search_subparser(commands)
    generate.register_subparsers(commands)
    verify.register_subparsers(commands)
    scrape.register_subparsers(commands)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build-prompt" and not 1 <= args.max_candidates <= config.MAX_CANDIDATES:
        print(
            json.dumps(
                {"ok": False, "errors": [f"--max-candidates must be 1..{config.MAX_CANDIDATES}"]},
                ensure_ascii=False,
            )
        )
        return 2
    try:
        result, _ = args.command_func(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "command": args.command, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "command": args.command, "errors": [f"unexpected failure: {exc}"]},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
