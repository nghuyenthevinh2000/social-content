"""Shared Glasser CLI client, error classification, and concurrency-safe runner."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple

from tools.loop.viral_analyzer import runtime

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


# -- Execution & Failure Classification -------------------------------------

_IGNORED_PREFIXES = (
    "Idempotency-Key:",
    "Update available:",
    "upgrade:",
    "skill:",
    "Run ID:",
    "Run URL:",
)


def _classify_glasser_failure(
    res: Dict[str, Any],
    handle: str,
    has_key: bool,
    endpoint_label: Optional[str] = None,
) -> GlasserError:
    """Map non-zero/empty Glasser CLI execution output to a typed GlasserError."""
    stdout_text = str(res.get("stdout") or "").strip()
    stderr_text = str(res.get("stderr") or "").strip()
    output_text = f"{stdout_text}\n{stderr_text}".strip()
    err_lines = [
        line.strip()
        for line in output_text.splitlines()
        if line.strip() and not any(line.strip().startswith(p) for p in _IGNORED_PREFIXES)
    ]
    err_first_line = err_lines[0] if err_lines else "Lỗi không xác định"
    rc = res.get("returncode")

    if rc == 2 or ("No Key configured" in output_text) or (not has_key and "key" in output_text.lower()):
        return GlasserMissingKeyError(
            message=f"Glasser thiếu API Key: {err_first_line}",
            handle=handle,
            returncode=rc,
            raw_output=output_text,
            suggestion="Thêm 'GLASSER_API_KEY=gl_...' vào file local/deployment-service/.env rồi khởi động lại backend.",
        )

    target_desc = endpoint_label or "query"
    return GlasserExecutionError(
        message=f"Glasser {target_desc} thất bại (code {rc}): {err_first_line}",
        handle=handle,
        returncode=rc,
        raw_output=output_text,
    )


def execute_glasser_query(
    profile_url: str,
    provider: str,
    endpoint: str,
    endpoint_version: int,
    idempotency_key: str,
    temp_out: Path,
    handle: str = "unknown",
    timeout: float = 45.0,
    payload: Optional[Dict[str, Any]] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> Tuple[bool, Optional[str], Optional[GlasserError]]:
    """Execute glasser run command under shared concurrency limit and classify failures."""
    from tools.app.backend import cost_control

    eng_ctx = ctx or runtime.default_context()
    has_key, _ = check_glasser_key()

    try:
        with eng_ctx.glasser_semaphore:
            res = cost_control.run_glasser_tracked(
                provider=provider,
                endpoint=endpoint,
                version=endpoint_version,
                payload=payload if payload is not None else {"url": profile_url},
                idempotency_key=idempotency_key,
                out_file=temp_out,
                timeout=timeout,
                sub_action="profile_scrape",
            )
        if res.get("not_found"):
            err = GlasserNotFoundError(handle=handle)
            return False, err.message, err
        if res["ok"] and temp_out.exists() and temp_out.stat().st_size > 0:
            return True, None, None

        output_text = f"{str(res.get('stdout') or '').strip()}\n{str(res.get('stderr') or '').strip()}".strip()
        is_not_found = res["returncode"] == 0 and (
            "HTTP 404" in output_text
            or '"errorStatus": 404' in output_text
            or '"error": "not_found"' in output_text
            or "doesn't exist or is private" in output_text
            or "don't have a reels tab" in output_text
            or "NO_RESULT" in output_text
            or "Response: HTTP 404" in output_text
            or '"http_status": 404' in output_text
            or (
                "only a COMPLETED Run with output is saved" in output_text
                and ("Status:   COMPLETED" in output_text or '"status": "COMPLETED"' in output_text)
            )
        )
        if is_not_found:
            try:
                runtime.atomic_write_json(temp_out, {"reels": [], "status": "not_found", "handle": handle})
                return True, None, None
            except Exception:
                pass

        err = _classify_glasser_failure(res, handle=handle, has_key=has_key)
        return False, err.message, err
    except cost_control.CostPolicyError as exc:
        err = GlasserExecutionError(message=str(exc), handle=handle)
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


def run_glasser_json(
    provider: str,
    endpoint: str,
    version: int,
    payload: Dict[str, Any],
    cache_dir: Optional[Path],
    task_id: Optional[str] = None,
    timeout: float = 45.0,
    sub_action: str = "keyword_search",
    cache_sub_action: str = "keyword_cache",
    ctx: Optional[runtime.EngineContext] = None,
) -> Tuple[Optional[Any], Optional[str], Optional[Exception]]:
    """Run a single Glasser endpoint with single-flight dedup, semaphore, and atomic disk cache."""
    from tools.app.backend import cost_control

    eng_ctx = ctx or runtime.default_context()
    cache_key = hashlib.sha256(
        json.dumps({"p": provider, "e": endpoint, "v": version, "i": payload}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    cache_file = (cache_dir / f"{cache_key}.json") if cache_dir else None
    handle = f"{provider}:{endpoint}"

    with eng_ctx.single_flight.acquire(f"glasser:{cache_key}"):
        if cache_file and cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                cost_control.record_cost_event(
                    provider=provider,
                    endpoint=endpoint,
                    cost_micro=0,
                    cache_hit=True,
                    sub_action=cache_sub_action,
                )
                return cached_data, "cache", None
            except Exception:
                pass

        ensure_glasser_env()
        has_key, _ = check_glasser_key()
        tmp_out = runtime.unique_temp_path(f"glasser_{cache_key}", ".json")
        idem = f"vvs-{cache_key}"

        try:
            with eng_ctx.glasser_semaphore:
                res = cost_control.run_glasser_tracked(
                    provider=provider,
                    endpoint=endpoint,
                    version=version,
                    payload=payload,
                    idempotency_key=idem,
                    out_file=tmp_out,
                    task_id=task_id,
                    timeout=timeout,
                    sub_action=sub_action,
                )
            if res.get("not_found"):
                return None, None, GlasserNotFoundError(handle=handle)
            if res["ok"] and tmp_out.exists() and tmp_out.stat().st_size > 0:
                data = json.loads(tmp_out.read_text(encoding="utf-8"))
                if cache_file is not None:
                    runtime.atomic_write_json(cache_file, data)
                return data, "glasser_api", None
            return None, None, _classify_glasser_failure(
                res,
                handle=handle,
                has_key=has_key,
                endpoint_label=f"{provider}{endpoint}",
            )
        except cost_control.CostPolicyError as exc:
            return None, None, GlasserExecutionError(message=str(exc), handle=handle)
        except subprocess.TimeoutExpired:
            return None, None, GlasserExecutionError(
                message=f"Glasser {provider}{endpoint} timeout sau {timeout:.0f}s",
                handle=handle,
            )
        except Exception as exc:
            return None, None, GlasserExecutionError(message=str(exc), handle=handle)
        finally:
            if tmp_out.exists():
                try:
                    tmp_out.unlink()
                except OSError:
                    pass
