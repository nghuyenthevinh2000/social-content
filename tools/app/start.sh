#!/usr/bin/env bash
# Turn-key startup: starts Docker services and the host `agy` TCP bridge.
# Note: this tweak is needed for macOS (host `agy` is Mach-O + uses macOS Keychain,
# so Linux containers cannot execute it or read its credentials directly).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/backend/docker-compose.yml"
BRIDGE_PORT="${AGY_BRIDGE_PORT:-8766}"

docker compose -f "$COMPOSE_FILE" up -d "$@"

if lsof -iTCP:"$BRIDGE_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "agy host bridge already listening on 127.0.0.1:$BRIDGE_PORT"
  exit 0
fi

exec python3 "$SCRIPT_DIR/agy_host_bridge.py" --port "$BRIDGE_PORT"
