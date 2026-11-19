"""CLI entrypoint for single-reel/video research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional

from tools.loop.viral_analyzer.video_research.pipeline import research_single_reel


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze an individual video/Reel URL")
    parser.add_argument("--url", required=True, help="Reel or short video URL")
    parser.add_argument("--sheet-name", default="Reel đã lưu", help="Topic group label")
    parser.add_argument("--agent", default=None, help="Optional ACP harness ID (agy, opencode, claude, codex)")
    parser.add_argument("--model", default=None, help="Optional model override for ACP harness")
    parser.add_argument("--timeout", type=float, default=120.0, help="ACP timeout in seconds")
    args = parser.parse_args(argv)

    result = research_single_reel(
        reel_url=args.url,
        sheet_name=args.sheet_name,
        agent_id=args.agent,
        model=args.model,
        cwd=Path.cwd() if args.agent else None,
        timeout_sec=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
