#!/usr/bin/env bash
# Reuse the X launcher and its default $HOME/chrome-twitter-profile.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/../twitter_agent/launch_browser.sh" "$@"
