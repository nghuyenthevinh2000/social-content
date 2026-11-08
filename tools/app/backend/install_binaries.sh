#!/usr/bin/env bash
# Install all required runtime binaries and CLI tools for tools/app/backend.
# Works in user space (no root/sudo required).
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
OPENCODE_BIN_DIR="${HOME}/.opencode/bin"
mkdir -p "${BIN_DIR}"
export PATH="${OPENCODE_BIN_DIR}:${BIN_DIR}:${PATH}"

echo "=== 1. Checking / Installing uv (Python package manager) ==="
if ! command -v uv >/dev/null 2>&1; then
    echo "[*] Downloading uv to ${BIN_DIR}..."
    curl -LsSf https://astral.sh/uv/install.sh | env CARGO_HOME="${HOME}/.local" BINDIR="${BIN_DIR}" sh
fi
echo "[+] uv: $(uv --version)"

echo "=== 2. Syncing Python virtual environment ==="
cd "${WORKSPACE}"
uv sync
echo "[+] Python venv ready: ${WORKSPACE}/.venv/bin/python"

echo "=== 3. Checking / Installing glasser CLI ==="
if ! command -v glasser >/dev/null 2>&1; then
    if command -v npm >/dev/null 2>&1; then
        echo "[*] Installing @glasser-ai/cli..."
        npm install -g @glasser-ai/cli@latest
    else
        echo "[!] Warning: npm not found in PATH. Please install Node.js / npm to install glasser."
    fi
fi
echo "[+] glasser: $(command -v glasser || echo 'missing')"

echo "=== 4. Checking / Installing opencode CLI ==="
if ! command -v opencode >/dev/null 2>&1; then
    echo "[*] Installing opencode via official install script..."
    curl -fsSL https://opencode.ai/v2/install | bash
fi
if [ -x "${OPENCODE_BIN_DIR}/opencode" ] && ! command -v opencode >/dev/null 2>&1; then
    ln -sf "${OPENCODE_BIN_DIR}/opencode" "${BIN_DIR}/opencode"
fi
echo "[+] opencode: $(command -v opencode || echo 'missing')"

echo "=== 5. Checking / Installing Antigravity CLI ==="
if ! command -v agy >/dev/null 2>&1 && ! command -v antigravity >/dev/null 2>&1; then
    echo "[*] Installing Antigravity CLI via official install script..."
    curl -fsSL https://antigravity.google/cli/install.sh | bash
fi
if command -v agy >/dev/null 2>&1 && ! command -v antigravity >/dev/null 2>&1; then
    ln -sf "$(command -v agy)" "${BIN_DIR}/antigravity"
fi
echo "[+] agy / antigravity: $(command -v agy || command -v antigravity || echo 'missing')"

echo "=== 6. Checking / Installing cloudflared (Tunnel client) ==="
if ! command -v cloudflared >/dev/null 2>&1; then
    ARCH="$(uname -m)"
    OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
    case "${ARCH}" in
        x86_64) CF_ARCH="amd64" ;;
        aarch64|arm64) CF_ARCH="arm64" ;;
        *) CF_ARCH="" ;;
    esac

    if [ -n "${CF_ARCH}" ] && [ "${OS}" = "linux" ]; then
        echo "[*] Downloading cloudflared for linux-${CF_ARCH}..."
        curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" -o "${BIN_DIR}/cloudflared"
        chmod +x "${BIN_DIR}/cloudflared"
        echo "[+] cloudflared installed to ${BIN_DIR}/cloudflared"
    else
        echo "[!] Cannot auto-download cloudflared for ${OS}-${ARCH}. Please install manually."
    fi
else
    echo "[+] cloudflared: $(cloudflared --version)"
fi

echo "=== 7. Checking ffmpeg ==="
if command -v ffmpeg >/dev/null 2>&1; then
    echo "[+] ffmpeg: $(command -v ffmpeg)"
else
    echo "[!] ffmpeg not found in PATH. imageio-ffmpeg fallback is in venv, but system ffmpeg is recommended."
    echo "    (Install via: sudo apt-get install -y ffmpeg)"
fi

echo "=== 8. Verification Summary ==="
"${WORKSPACE}/.venv/bin/python" -c "
import shutil, sys
tools = ['uv', 'glasser', 'opencode', 'agy', 'antigravity', 'cloudflared', 'ffmpeg']
print(f'%-15s %-10s %s' % ('Tool', 'Status', 'Path / Note'))
print('-' * 45)
for t in tools:
    p = shutil.which(t)
    status = 'OK' if p else 'MISSING'
    print(f'%-15s %-10s %s' % (t, status, p or 'Not found'))
"
echo "=== All installations completed successfully ==="
