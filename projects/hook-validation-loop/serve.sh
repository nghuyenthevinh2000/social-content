#!/usr/bin/env bash
# Run live Python dev server for hook-validation-loop screens
cd "$(dirname "$0")" || exit 1
python3 serve.py "$@"
