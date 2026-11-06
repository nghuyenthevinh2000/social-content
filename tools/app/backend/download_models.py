#!/usr/bin/env python3
"""Pre-download ASR model weights for the viral research backend."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

DEFAULT_MODEL = "Qwen/Qwen3-ASR-0.6B-hf"


def download_model(model_id: str = DEFAULT_MODEL, cache_dir: Path | None = None) -> Path:
    """Download model weights into Hugging Face cache so the container runs offline."""
    print(f"[*] Downloading {model_id}...")
    try:
        from huggingface_hub import snapshot_download

        path = snapshot_download(
            repo_id=model_id,
            cache_dir=str(cache_dir) if cache_dir else None,
        )
        print(f"[+] Download complete: {path}")
        return Path(path)
    except ImportError:
        pass

    try:
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        print("[*] huggingface_hub not found directly; using transformers...")
        AutoProcessor.from_pretrained(model_id, cache_dir=cache_dir)
        AutoModelForMultimodalLM.from_pretrained(model_id, cache_dir=cache_dir)
        print(f"[+] Download complete for {model_id} via transformers.")
        return cache_dir or (Path.home() / ".cache" / "huggingface")
    except ImportError:
        print(
            "[!] Error: Neither 'huggingface_hub' nor 'transformers' is installed.\n"
            "    Install with: pip install huggingface_hub\n"
            "    Or run via Docker: docker compose -f tools/app/backend/docker-compose.yml run --rm download-models",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download model weights for ASR transcription")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Hugging Face model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--cache-dir", type=Path, default=None, help="Hugging Face cache dir (default: standard HF cache)")
    args = parser.parse_args()

    download_model(args.model, cache_dir=args.cache_dir)


if __name__ == "__main__":
    main()
