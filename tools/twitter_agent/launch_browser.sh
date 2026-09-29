#!/usr/bin/env bash
#
# launch-browser.sh
# Detects whether Chrome is running with remote debugging (CDP) enabled.
# If not detected, launches Chrome with a dedicated user profile and CDP port.
#

set -euo pipefail

PORT="${CDP_PORT:-9222}"
USER_DATA_DIR="${CHROME_USER_DATA_DIR:-$HOME/chrome-twitter-profile}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -p, --port PORT          CDP remote debugging port (default: 9222)
  -d, --data-dir DIR       Chrome user data directory (default: \$HOME/chrome-twitter-profile)
  -h, --help               Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --port=*)
            PORT="${1#*=}"
            shift
            ;;
        -d|--data-dir)
            USER_DATA_DIR="$2"
            shift 2
            ;;
        --data-dir=*)
            USER_DATA_DIR="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            ;;
    esac
done

is_browser_running() {
    curl -s --connect-timeout 1 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1
}

if is_browser_running; then
    echo "Browser is already running with CDP on http://127.0.0.1:${PORT}"
    exit 0
fi

echo "No active browser detected on port ${PORT}. Searching for Chrome binary..."

CHROME_BIN=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    CANDIDATES=(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        "/Applications/Chromium.app/Contents/MacOS/Chromium"
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    for bin in "${CANDIDATES[@]}"; do
        if [[ -x "$bin" ]]; then
            CHROME_BIN="$bin"
            break
        fi
    done
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CANDIDATES=(
        "google-chrome"
        "google-chrome-stable"
        "chromium-browser"
        "chromium"
        "brave-browser"
    )
    for bin in "${CANDIDATES[@]}"; do
        if command -v "$bin" >/dev/null 2>&1; then
            CHROME_BIN="$(command -v "$bin")"
            break
        fi
    done
fi

if [[ -z "$CHROME_BIN" ]]; then
    echo "Error: Could not locate a compatible Chromium/Chrome binary." >&2
    echo "Please launch Chrome manually with:" >&2
    echo "  --remote-debugging-port=${PORT} --user-data-dir=\"${USER_DATA_DIR}\"" >&2
    exit 1
fi

echo "Launching: $CHROME_BIN"
echo "  Port:      $PORT"
echo "  Profile:   $USER_DATA_DIR"

mkdir -p "$USER_DATA_DIR"

if [[ "$OSTYPE" == "darwin"* && "$CHROME_BIN" == *".app"* ]]; then
    APP_BUNDLE="${CHROME_BIN%%.app/*}.app"
    open -na "$APP_BUNDLE" --args --remote-debugging-port="$PORT" --user-data-dir="$USER_DATA_DIR"
else
    nohup "$CHROME_BIN" \
        --remote-debugging-port="$PORT" \
        --user-data-dir="$USER_DATA_DIR" \
        >/dev/null 2>&1 &
    disown || true
fi

echo "Process started. Waiting for CDP to respond..."

for i in {1..15}; do
    if is_browser_running; then
        echo "Browser ready! CDP is listening on http://127.0.0.1:${PORT}"
        exit 0
    fi
    sleep 1
done

echo "Error: Browser process launched, but CDP did not become ready within 15 seconds." >&2
exit 1
