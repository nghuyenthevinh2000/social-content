#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VM_NAME="clean-mac-test"
BASE_IMAGE="${TART_IMAGE:-ghcr.io/cirruslabs/macos-sonoma-base:latest}"
DMG_NAME="AIBrand_0.1.0_aarch64.dmg"

CUSTOM_DMG="${1:-}"
if [ -n "$CUSTOM_DMG" ] && [ -f "$CUSTOM_DMG" ]; then
  DMG_NAME=$(basename "$CUSTOM_DMG")
  ABS_CUSTOM=$(cd "$(dirname "$CUSTOM_DMG")" && pwd)/"${DMG_NAME}"
  if [ "$ABS_CUSTOM" != "${SCRIPT_DIR}/binaries/${DMG_NAME}" ]; then
    cp "$ABS_CUSTOM" "${SCRIPT_DIR}/binaries/${DMG_NAME}"
  fi
fi

if [ ! -f "${SCRIPT_DIR}/binaries/${DMG_NAME}" ]; then
  # Fallback to locally built DMG if release asset isn't present
  FALLBACK_DMG=$(find "${SCRIPT_DIR}/../tools/app/src-tauri/target/release/bundle/dmg" -name "*.dmg" 2>/dev/null | head -n 1 || true)
  if [ -n "$FALLBACK_DMG" ]; then
    cp "$FALLBACK_DMG" "${SCRIPT_DIR}/binaries/${DMG_NAME}"
  else
    echo "[-] Error: No DMG found in e2e/binaries/ or tools/app bundle"
    exit 1
  fi
fi

if ! command -v tart >/dev/null 2>&1; then
  echo "[-] Tart CLI not found. Please install Tart or check PATH."
  exit 1
fi

cleanup() {
  echo "[*] Stopping Tart VM if running..."
  tart stop "${VM_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Step 1: Ensure clean VM exists
if ! tart list | grep -q "${VM_NAME}"; then
  echo "[1/4] Cloning fresh disposable macOS VM from ${BASE_IMAGE}..."
  tart clone "${BASE_IMAGE}" "${VM_NAME}"
else
  echo "[1/4] Reusing existing Tart VM: ${VM_NAME}"
fi

# Step 2: Start VM in background with shared binaries directory
echo "[2/4] Booting clean-room macOS VM..."
tart run --no-graphics --dir="binaries:${SCRIPT_DIR}/binaries:ro" "${VM_NAME}" &
VM_PID=$!

echo "[*] Waiting for Tart VM and Guest Agent to be ready..."
for i in {1..60}; do
  if tart exec "${VM_NAME}" /bin/bash -c "true" >/dev/null 2>&1; then
    VM_IP=$(tart ip "${VM_NAME}" 2>/dev/null || echo "unknown")
    echo "[+] Tart VM is online at IP: ${VM_IP}"
    break
  fi
  sleep 2
done

# Step 3: Run installer validation inside pristine guest OS
echo "[3/4] Running installation tests in clean guest macOS..."
tart exec -i "${VM_NAME}" /bin/bash <<EOF
  set -euo pipefail
  echo '    [Guest] Attaching DMG from shared folder...'
  DMG_PATH=""
  for i in {1..30}; do
    if [ -f "/Volumes/My Shared Files/binaries/${DMG_NAME}" ]; then
      DMG_PATH="/Volumes/My Shared Files/binaries/${DMG_NAME}"
      break
    elif [ -f "/Volumes/My Shared Files/${DMG_NAME}" ]; then
      DMG_PATH="/Volumes/My Shared Files/${DMG_NAME}"
      break
    fi
    sleep 1
  done

  if [ -z "\$DMG_PATH" ]; then
    echo "    [-] Error: ${DMG_NAME} not found under '/Volumes/My Shared Files'"
    ls -la "/Volumes/My Shared Files" 2>/dev/null || ls -la "/Volumes"
    exit 1
  fi

  hdiutil detach /tmp/dmg-mnt >/dev/null 2>&1 || true
  mkdir -p /tmp/dmg-mnt
  hdiutil attach "\$DMG_PATH" -mountpoint /tmp/dmg-mnt -nobrowse -readonly

  APP_PATH=\$(find /tmp/dmg-mnt -maxdepth 1 -name '*.app' | head -n 1)
  APP_NAME=\$(basename "\$APP_PATH")
  echo "    [Guest] Installing \$APP_NAME to /Applications..."
  cp -R "\$APP_PATH" /Applications/

  hdiutil detach /tmp/dmg-mnt >/dev/null

  echo '    [Guest] Verifying installed bundle...'
  ls -la "/Applications/\$APP_NAME/Contents/MacOS"

  echo '    [Guest] Testing sidecar execution without Homebrew/developer tools...'
  "/Applications/\$APP_NAME/Contents/MacOS/viral-server" --help >/dev/null
  echo '    [+] Sidecar --help succeeded in clean macOS guest!'

  echo '    [Guest] Simulating launch...'
  open -a "/Applications/\$APP_NAME"
  sleep 3
EOF

echo "[4/4] Installation validation completed successfully in Tart VM!"
