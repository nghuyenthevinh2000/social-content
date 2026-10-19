#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["huggingface_hub>=0.34"]
# ///
"""Download the nvidia/Nemotron-Personas-Vietnam dataset into ./local.

Usage:
    uv run --no-project download_dataset.py                  # everything (~2.25 GB)
    uv run --no-project download_dataset.py --only "data/*"  # just the parquet shards
    uv run --no-project download_dataset.py --only "data/train-00000*"

Files are fetched with huggingface_hub's snapshot_download, so re-running resumes
and skips files that are already complete in ./local.
"""

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "nvidia/Nemotron-Personas-Vietnam"
LOCAL_DIR = Path(__file__).resolve().parent / "local"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        action="append",
        metavar="GLOB",
        help="Only download files matching this glob (repeatable). Default: all files.",
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="Parallel download workers (default: 8)."
    )
    args = parser.parse_args()

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    path = snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=LOCAL_DIR,
        allow_patterns=args.only,
        max_workers=args.workers,
    )
    print(f"Done. Files in: {path}")


if __name__ == "__main__":
    main()
