#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"

TARGET="${1:-}"

# Auto-discover Windows installer if not provided
if [ -z "$TARGET" ]; then
  # Check binaries folder
  TARGET=$(find "${SCRIPT_DIR}/binaries" -maxdepth 1 -type f \( -name "*.msi" -o -name "*.exe" \) 2>/dev/null | head -n 1 || true)
fi

if [ -z "$TARGET" ]; then
  echo "[-] Error: No Windows installer (.msi or .exe) specified or found in 'e2e/binaries/'"
  echo "    Usage: ./test_windows.sh <path_to_msi_or_exe>"
  echo "    Or drop the installer into '${SCRIPT_DIR}/binaries/' and re-run."
  exit 1
fi

ABS_TARGET=$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")
FILENAME=$(basename "$TARGET")

# Ensure binary is in binaries/ for mounting
if [ "$ABS_TARGET" != "${SCRIPT_DIR}/binaries/${FILENAME}" ]; then
  cp "$ABS_TARGET" "${SCRIPT_DIR}/binaries/${FILENAME}"
fi

echo "[*] Testing Windows installer: ${FILENAME}"
echo "[1/3] Launching Wine testing container..."

echo "[2/3] Executing silent installation & checking installed files in Wine..."
if [[ "$FILENAME" == *.msi ]]; then
  docker compose -f "${SCRIPT_DIR}/docker-compose.wine.yml" run --rm wine bash -c "
    wine msiexec /i 'binaries/${FILENAME}' /qn
    echo '[+] Listing installed files:'
    find /root/.wine/drive_c -maxdepth 4 -name '*AIBrand*' -o -name '*aibrand*' -o -name '*.exe'
  "
elif [[ "$FILENAME" == *.exe ]]; then
  docker compose -f "${SCRIPT_DIR}/docker-compose.wine.yml" run --rm wine bash -c "
    wine 'binaries/${FILENAME}' /S
    echo '[+] Listing installed files:'
    find /root/.wine/drive_c -maxdepth 4 -name '*AIBrand*' -o -name '*aibrand*' -o -name '*.exe'
  "
fi

echo ""
echo "============================================================"
echo "[SUCCESS] Windows installer test completed for ${FILENAME}"
echo "============================================================"
