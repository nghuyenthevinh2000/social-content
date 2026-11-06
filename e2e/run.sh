#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-help}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

case "$MODE" in
  test-mac)
    "${SCRIPT_DIR}/test_macos_tart.sh" "${2:-}"
    ;;
  test-win)
    "${SCRIPT_DIR}/test_windows.sh" "${2:-}"
    ;;
  test-all)
    echo "=== [1/2] Fresh macOS Installer Test (Tart VM) ==="
    "${SCRIPT_DIR}/test_macos_tart.sh" "${2:-}"
    echo ""
    echo "=== [2/2] Fresh Windows Installer Test (Docker) ==="
    "${SCRIPT_DIR}/test_windows.sh" "${3:-}"
    ;;
  help|*)
    echo "Fresh Installer Test Harness for tools/app (AIBrand)"
    echo ""
    echo "Usage: ./run.sh <command>"
    echo ""
    echo "Single Fresh Options:"
    echo "  test-mac [dmg_file]       Run clean-room macOS test in fresh Tart VM"
    echo "  test-win [msi_or_exe]     Run clean-room Windows install test in isolated container"
    echo "  test-all                  Run both clean-room macOS and Windows tests sequentially"
    ;;
esac
