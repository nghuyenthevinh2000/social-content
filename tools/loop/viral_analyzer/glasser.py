"""Glasser CLI client, error detection, and response caching for Facebook Reels.

Handles authentication checks, ScrapeCreators reel harvesting, TTL-based caching,
and detailed error classification (e.g. missing API key, missing binary, execution failure).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).parent.resolve()


# -- Error definitions -------------------------------------------------------

class GlasserError(RuntimeError):
    """Base exception for Glasser scraping errors."""

    def __init__(
        self,
        message: str,
        handle: Optional[str] = None,
        returncode: Optional[int] = None,
        raw_output: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.handle = handle
        self.returncode = returncode
        self.raw_output = raw_output
        self.suggestion = suggestion or "Kiểm tra kết nối mạng hoặc đường dẫn Facebook."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "handle": self.handle,
            "returncode": self.returncode,
            "suggestion": self.suggestion,
        }


class GlasserMissingKeyError(GlasserError):
    """Raised when GLASSER_API_KEY is missing or unauthenticated."""

    def __init__(
        self,
        message: str = "Chưa cấu hình GLASSER_API_KEY cho Glasser CLI.",
        handle: Optional[str] = None,
        returncode: Optional[int] = None,
        raw_output: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        sugg = suggestion or (
            "Thêm 'GLASSER_API_KEY=<key>' vào file .env (hoặc local/deployment-service/.env) "
            "rồi khởi động lại backend."
        )
        super().__init__(
            message=message,
            handle=handle,
            returncode=returncode,
            raw_output=raw_output,
            suggestion=sugg,
        )


class GlasserNotFoundError(GlasserError):
    """Raised when the glasser executable is not found in PATH."""

    def __init__(
        self,
        message: str = "Không tìm thấy lệnh 'glasser' trong hệ thống.",
        handle: Optional[str] = None,
    ):
        suggestion = "Chạy 'npm install -g @glasser-ai/cli' hoặc script install_binaries.sh."
        super().__init__(message=message, handle=handle, suggestion=suggestion)


class GlasserExecutionError(GlasserError):
    """Raised when glasser run returns a non-zero exit code or invalid response."""
    pass


# -- Health & Auth Checks ---------------------------------------------------

def ensure_glasser_env() -> Optional[str]:
    """Ensure GLASSER_API_KEY is available in os.environ by reading known .env files."""
    key = os.environ.get("GLASSER_API_KEY", "").strip()
    if key:
        return key

    repo_root = CURRENT_DIR.resolve().parents[2]
    candidate_files = [
        repo_root / "local" / "deployment-service" / ".env",
        repo_root / "tools" / "app" / "backend" / ".env",
        repo_root / ".env",
        Path(".env"),
    ]
    for env_path in candidate_files:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GLASSER_API_KEY=") or line.startswith("export GLASSER_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"\'')
                        if val:
                            os.environ["GLASSER_API_KEY"] = val
                            return val
            except Exception:
                pass
    return None


def check_glasser_key() -> Tuple[bool, Optional[str]]:
    """Check if GLASSER_API_KEY is set in environment or configured in Glasser CLI."""
    key = ensure_glasser_env() or os.environ.get("GLASSER_API_KEY", "").strip()
    if key:
        if len(key) < 10:
            return False, "GLASSER_API_KEY quá ngắn hoặc không hợp lệ."
        return True, None

    # Fallback: check if Glasser CLI has a locally stored key (glasser keys list)
    glasser_bin = shutil.which("glasser")
    if glasser_bin:
        try:
            res = subprocess.run([glasser_bin, "keys", "list"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0 and "*" in res.stdout:
                return True, None
        except Exception:
            pass

    return False, "Thiếu biến môi trường GLASSER_API_KEY hoặc chưa cấu hình Glasser CLI."


def check_glasser_status() -> Dict[str, Any]:
    """Comprehensive status check for Glasser CLI and credentials."""
    glasser_bin = shutil.which("glasser")
    has_key, key_err = check_glasser_key()

    installed = glasser_bin is not None
    ok = installed and has_key
    error = None
    if not installed:
        error = "Chưa cài đặt CLI glasser (@glasser-ai/cli)."
    elif not has_key:
        error = key_err

    return {
        "ok": ok,
        "installed": installed,
        "has_key": has_key,
        "bin_path": glasser_bin,
        "error": error,
    }


# -- Execution --------------------------------------------------------------

def execute_glasser_query(
    profile_url: str,
    provider: str,
    endpoint: str,
    endpoint_version: int,
    idempotency_key: str,
    temp_out: Path,
    handle: str = "unknown",
    timeout: float = 45.0,
) -> Tuple[bool, Optional[str], Optional[GlasserError]]:
    """Execute glasser run command and classify any failure."""
    glasser_bin = shutil.which("glasser")
    if not glasser_bin:
        err = GlasserNotFoundError(handle=handle)
        return False, err.message, err

    has_key, _ = check_glasser_key()

    cmd = [
        glasser_bin,
        "run",
        "-p", provider,
        "-e", endpoint,
        "-i", json.dumps({"url": profile_url}),
        "--endpoint-version", str(endpoint_version),
        "--idempotency-key", idempotency_key,
        "-o", str(temp_out),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 0:
            return True, None, None

        # Analyze failure or 404 output
        output_text = (proc.stderr or proc.stdout or "").strip()

        # Handle Facebook 404 / no reels tab (COMPLETED run with HTTP 404 or empty output)
        if proc.returncode == 0 and (
            "HTTP 404" in output_text
            or '"errorStatus": 404' in output_text
            or '"error": "not_found"' in output_text
            or "doesn't exist or is private" in output_text
            or "don't have a reels tab" in output_text
        ):
            try:
                temp_out.write_text(json.dumps({"reels": [], "status": "not_found", "handle": handle}), encoding="utf-8")
                return True, None, None
            except Exception:
                pass

        # Parse specific failure cause, skipping idempotency banner
        err_lines = [
            line.strip() for line in output_text.splitlines()
            if line.strip() and not line.startswith("Idempotency-Key:")
        ]
        err_first_line = err_lines[0] if err_lines else "Lỗi không xác định"

        if proc.returncode == 2 or ("No Key configured" in output_text) or (not has_key and "key" in output_text.lower()):
            err = GlasserMissingKeyError(
                message=f"Glasser thiếu API Key: {err_first_line}",
                handle=handle,
                returncode=proc.returncode,
                raw_output=output_text,
                suggestion="Thêm 'GLASSER_API_KEY=gl_...' vào file local/deployment-service/.env rồi khởi động lại backend.",
            )
        else:
            err = GlasserExecutionError(
                message=f"Glasser query thất bại (code {proc.returncode}): {err_first_line}",
                handle=handle,
                returncode=proc.returncode,
                raw_output=output_text,
            )
        return False, err.message, err
    except subprocess.TimeoutExpired:
        err = GlasserExecutionError(
            message=f"Glasser query bị timeout sau {timeout:.0f}s",
            handle=handle,
            suggestion="Kiểm tra kết nối internet hoặc thử lại sau.",
        )
        return False, err.message, err
    except Exception as exc:
        err = GlasserExecutionError(
            message=f"Lỗi khi thực thi Glasser: {exc}",
            handle=handle,
        )
        return False, err.message, err


# -- Fetching with Cache & Error Tracking ------------------------------------

def fetch_target_reels(
    target: Dict[str, Any],
    config: Any,
    cache_dir: Optional[Path] = None,
    legacy_cache: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
    error_collector: Optional[List[GlasserError]] = None,
) -> List[Dict[str, Any]]:
    """Fetch profile reels via Glasser ScrapeCreators or cached responses.

    Appends encountered GlasserErrors to error_collector if provided.
    """
    profile_url = target.get("url") or f"https://www.facebook.com/{target.get('handle')}"
    handle = target.get("handle")
    if not handle or handle == "unknown":
        try:
            from tools.app.backend.profiles import facebook_handle
            h, _ = facebook_handle(profile_url)
            handle = h or "unknown"
        except Exception:
            handle = "unknown"
    slug = handle.replace(".", "_")

    # Search paths in priority order: explicitly provided cache_dir, app shared cache, output dir
    search_dirs: List[Path] = []
    if cache_dir:
        search_dirs.append(Path(cache_dir))
    env_cache = os.environ.get("VIRAL_APP_CACHE_DIR")
    if env_cache:
        search_dirs.append(Path(env_cache))
    else:
        shared_default = CURRENT_DIR.resolve().parents[2] / "local" / "app-runs" / "cache"
        if shared_default not in search_dirs:
            search_dirs.append(shared_default)
    if getattr(config, "storage", None) and config.storage.output_file and config.storage.output_file.parent not in search_dirs:
        search_dirs.append(config.storage.output_file.parent)
    if legacy_cache:
        search_dirs += [Path("local/social-listening-test"), CURRENT_DIR]

    ttl_hours = int(os.environ.get("VIRAL_APP_CACHE_TTL_HOURS", "24"))
    ttl_seconds = ttl_hours * 3600
    now_ts = time.time()

    # 1. Check local valid cache first
    for d in search_dirs:
        if not d or not d.exists():
            continue
        for fname in (f"glasser_{slug}.json", f"temp_{slug}.json"):
            c_path = d / fname
            if c_path.exists() and c_path.stat().st_size > 10:
                if ttl_seconds > 0 and (now_ts - c_path.stat().st_mtime) > ttl_seconds:
                    continue  # Expired
                try:
                    with open(c_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        reels = data.get("reels", [])
                        if reels:
                            msg = f"    [cache] Dùng cache ({len(reels)} reel) cho {handle} ({fname})."
                            print(msg)
                            if progress_cb:
                                progress_cb(msg)
                            return reels
                except Exception:
                    pass

    # 2. Glasser CLI Fetch
    msg = f"    [api] Gọi Glasser cho {handle}..."
    print(msg)
    if progress_cb:
        progress_cb(msg)

    temp_out = Path(tempfile.gettempdir()) / f"glasser_{slug}.json"
    idempotency_key = f"viral-loop-{slug}-{int(time.time() // 86400)}"

    provider = getattr(config, "glasser_provider", "scrapecreators")
    endpoint = getattr(config, "glasser_endpoint", "/v1/facebook/profile/reels")
    endpoint_version = getattr(config, "glasser_endpoint_version", 2)

    ok, err_msg, glasser_err = execute_glasser_query(
        profile_url=profile_url,
        provider=provider,
        endpoint=endpoint,
        endpoint_version=endpoint_version,
        idempotency_key=idempotency_key,
        temp_out=temp_out,
        handle=handle,
        timeout=45.0,
    )

    if ok and temp_out.exists():
        try:
            with open(temp_out, "r", encoding="utf-8") as f:
                data = json.load(f)
                reels = data.get("reels", [])
                for d in search_dirs:
                    if d:
                        try:
                            d.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(temp_out, d / f"glasser_{slug}.json")
                        except Exception:
                            pass
                return reels
        except Exception as read_err:
            glasser_err = GlasserExecutionError(
                message=f"Không đọc được file kết quả JSON từ Glasser: {read_err}",
                handle=handle,
            )
        finally:
            if temp_out.exists():
                try:
                    os.remove(temp_out)
                except Exception:
                    pass

    # Record error if Glasser query failed
    if glasser_err:
        if error_collector is not None:
            error_collector.append(glasser_err)
        log_msg = f"    [!] Glasser lỗi cho {handle}: {glasser_err.message}"
        print(log_msg)
        if progress_cb:
            progress_cb(log_msg)

    # 3. Fallback to expired cache if Glasser query failed or was unavailable
    for d in search_dirs:
        if not d or not d.exists():
            continue
        for fname in (f"glasser_{slug}.json", f"temp_{slug}.json"):
            c_path = d / fname
            if c_path.exists() and c_path.stat().st_size > 10:
                try:
                    with open(c_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        reels = data.get("reels", [])
                        if reels:
                            fallback_msg = f"    [!] Glasser lỗi; dùng lại cache cũ ({len(reels)} reel) cho {handle}."
                            print(fallback_msg)
                            if progress_cb:
                                progress_cb(fallback_msg)
                            return reels
                except Exception:
                    pass

    return []
