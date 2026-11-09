"""Centralized error handling, aggregation, and logging for AIBrand backend.

Aggregates structured errors across all components:
- Glasser scraping & API key authentication
- ACP (Agent Client Protocol) harnesses (agy, opencode, claude, codex)
- SQLite database transactions and locks
- Audio transcription and video processing
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("aibrand.backend.errors")


class ErrorCategory(str, Enum):
    GLASSER = "glasser"
    ACP = "acp"
    DATABASE = "database"
    TRANSCRIPTION = "transcription"
    VALIDATION = "validation"
    SYSTEM = "system"


class ErrorSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AppError:
    """Standardized error object for UI reporting, job logs, and monitoring."""
    category: str
    code: str
    message: str
    severity: str = ErrorSeverity.ERROR.value
    source: Optional[str] = None
    suggestion: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def format_notice(self) -> str:
        """User-friendly single line notification suitable for UI alerts."""
        prefix = f"[{self.category.upper()}]"
        src = f" ({self.source})" if self.source else ""
        sugg = f" Gợi ý: {self.suggestion}" if self.suggestion else ""
        return f"{prefix}{src} {self.message}.{sugg}".strip()


# -- Aggregator -------------------------------------------------------------

class ErrorAggregator:
    """Thread-safe collector and summarizer for errors during job lifecycle."""

    def __init__(self, job_id: Optional[str] = None):
        self.job_id = job_id
        self._errors: List[AppError] = []
        self._lock = threading.Lock()

    def add(self, error: AppError) -> AppError:
        with self._lock:
            self._errors.append(error)
        return error

    def record(
        self,
        category: Union[ErrorCategory, str],
        code: str,
        message: str,
        severity: Union[ErrorSeverity, str] = ErrorSeverity.ERROR,
        source: Optional[str] = None,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AppError:
        cat_str = category.value if isinstance(category, ErrorCategory) else str(category)
        sev_str = severity.value if isinstance(severity, ErrorSeverity) else str(severity)
        err = AppError(
            category=cat_str,
            code=code,
            message=message,
            severity=sev_str,
            source=source,
            suggestion=suggestion,
            details=details,
        )
        return self.add(err)

    def record_exception(
        self,
        category: Union[ErrorCategory, str],
        exc: Exception,
        source: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> AppError:
        code = exc.__class__.__name__
        msg = str(exc)
        return self.record(
            category=category,
            code=code,
            message=msg,
            source=source,
            suggestion=suggestion,
        )

    def has_errors(self) -> bool:
        with self._lock:
            return any(e.severity in {ErrorSeverity.ERROR.value, ErrorSeverity.CRITICAL.value} for e in self._errors)

    def has_category(self, category: Union[ErrorCategory, str]) -> bool:
        cat_str = category.value if isinstance(category, ErrorCategory) else str(category)
        with self._lock:
            return any(e.category == cat_str for e in self._errors)

    def all_errors(self) -> List[AppError]:
        with self._lock:
            return list(self._errors)

    def filter(
        self,
        category: Optional[Union[ErrorCategory, str]] = None,
        severity: Optional[Union[ErrorSeverity, str]] = None,
    ) -> List[AppError]:
        cat_str = category.value if isinstance(category, ErrorCategory) else (str(category) if category else None)
        sev_str = severity.value if isinstance(severity, ErrorSeverity) else (str(severity) if severity else None)
        with self._lock:
            return [
                e for e in self._errors
                if (cat_str is None or e.category == cat_str)
                and (sev_str is None or e.severity == sev_str)
            ]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            counts_by_cat: Dict[str, int] = {}
            counts_by_sev: Dict[str, int] = {}
            for e in self._errors:
                counts_by_cat[e.category] = counts_by_cat.get(e.category, 0) + 1
                counts_by_sev[e.severity] = counts_by_sev.get(e.severity, 0) + 1
            return {
                "total": len(self._errors),
                "by_category": counts_by_cat,
                "by_severity": counts_by_sev,
                "errors": [e.to_dict() for e in self._errors],
            }

    def notices(self) -> List[str]:
        with self._lock:
            return [e.format_notice() for e in self._errors]


# -- Specialized Component Handlers -----------------------------------------

def handle_glasser_error(
    error_or_exc: Any,
    handle: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> AppError:
    """Normalize and classify errors coming from Glasser scraper execution."""
    raw_text = str(error_or_exc)
    err_type = ""
    err_code = ""
    returncode = None
    if isinstance(error_or_exc, Exception):
        err_type = error_or_exc.__class__.__name__
        returncode = getattr(error_or_exc, "returncode", None)
    elif isinstance(error_or_exc, dict):
        err_type = str(error_or_exc.get("error_type") or "")
        err_code = str(error_or_exc.get("code") or "")
        returncode = error_or_exc.get("returncode")

    # 1. Missing or unconfigured API Key
    is_missing_key = (
        "GlasserMissingKeyError" in err_type
        or err_code == "GLASSER_MISSING_API_KEY"
        or "No Key configured" in raw_text
        or "Chưa cấu hình GLASSER_API_KEY" in raw_text
        or "Thiếu biến môi trường GLASSER_API_KEY" in raw_text
        or (returncode == 2 and "key" in raw_text.lower())
    )

    if is_missing_key:
        app_err = AppError(
            category=ErrorCategory.GLASSER.value,
            code="GLASSER_MISSING_API_KEY",
            message=f"Chưa cấu hình hoặc thiếu GLASSER_API_KEY khi truy vấn kênh {handle or ''}".strip(),
            severity=ErrorSeverity.CRITICAL.value,
            source=handle,
            suggestion="Thêm 'GLASSER_API_KEY=gl_...' vào file local/deployment-service/.env rồi khởi động lại backend.",
            details={"raw": raw_text},
        )
    # 2. Missing binary in PATH
    elif "GlasserNotFoundError" in err_type or "Không tìm thấy lệnh 'glasser'" in raw_text:
        app_err = AppError(
            category=ErrorCategory.GLASSER.value,
            code="GLASSER_BINARY_NOT_FOUND",
            message=f"Không tìm thấy binary 'glasser' khi cào dữ liệu kênh {handle or ''}".strip(),
            severity=ErrorSeverity.CRITICAL.value,
            source=handle,
            suggestion="Chạy 'npm install -g @glasser-ai/cli' hoặc chạy tools/app/backend/install_binaries.sh.",
            details={"raw": raw_text},
        )
    # 3. Timeout or rate limits
    elif "timeout" in raw_text.lower():
        app_err = AppError(
            category=ErrorCategory.GLASSER.value,
            code="GLASSER_TIMEOUT",
            message=f"Quá thời gian chờ phản hồi từ Glasser cho kênh {handle or ''}".strip(),
            severity=ErrorSeverity.WARNING.value,
            source=handle,
            suggestion="Kiểm tra kết nối mạng hoặc thử lại sau.",
            details={"raw": raw_text},
        )
    # 4. General execution failure
    else:
        clean_msg = error_or_exc.get("message") if isinstance(error_or_exc, dict) and error_or_exc.get("message") else raw_text
        custom_suggestion = error_or_exc.get("suggestion") if isinstance(error_or_exc, dict) and error_or_exc.get("suggestion") else None
        app_err = AppError(
            category=ErrorCategory.GLASSER.value,
            code="GLASSER_EXECUTION_ERROR",
            message=f"Lỗi khi cào dữ liệu Glasser cho {handle or 'kênh'}: {clean_msg}".strip(),
            severity=ErrorSeverity.ERROR.value,
            source=handle,
            suggestion=custom_suggestion or "Kiểm tra lại đường dẫn Facebook hoặc quota Glasser.",
            details={"raw": raw_text},
        )

    if log:
        log(f"[!] {app_err.format_notice()}")
    return app_err


def handle_acp_error(
    error_or_exc: Any,
    agent_id: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> AppError:
    """Normalize and classify errors from ACP agent invocations."""
    raw_text = str(error_or_exc)
    lower = raw_text.lower()

    if "auth" in lower or "login" in lower:
        app_err = AppError(
            category=ErrorCategory.ACP.value,
            code="ACP_AUTH_REQUIRED",
            message=f"Harness '{agent_id or 'agent'}' yêu cầu đăng nhập",
            severity=ErrorSeverity.ERROR.value,
            source=agent_id,
            suggestion=f"Đăng nhập CLI cho harness '{agent_id}' rồi thử lại.",
            details={"raw": raw_text},
        )
    elif "không tìm thấy harness" in lower or "not found" in lower:
        app_err = AppError(
            category=ErrorCategory.ACP.value,
            code="ACP_HARNESS_NOT_FOUND",
            message=f"Không tìm thấy binary harness '{agent_id}'",
            severity=ErrorSeverity.ERROR.value,
            source=agent_id,
            suggestion="Cài đặt harness tương ứng trên máy.",
            details={"raw": raw_text},
        )
    elif "timeout" in lower:
        app_err = AppError(
            category=ErrorCategory.ACP.value,
            code="ACP_TIMEOUT",
            message=f"Harness '{agent_id or 'agent'}' quá thời gian phản hồi (timeout)",
            severity=ErrorSeverity.WARNING.value,
            source=agent_id,
            suggestion="Tăng acp_timeout trong cấu hình hoặc kiểm tra tải máy.",
            details={"raw": raw_text},
        )
    else:
        app_err = AppError(
            category=ErrorCategory.ACP.value,
            code="ACP_EXECUTION_ERROR",
            message=f"Lỗi harness '{agent_id or 'agent'}': {raw_text}",
            severity=ErrorSeverity.ERROR.value,
            source=agent_id,
            suggestion="Kiểm tra stderr của harness hoặc thử lại với harness khác.",
            details={"raw": raw_text},
        )

    if log:
        log(f"[!] {app_err.format_notice()}")
    return app_err


def handle_database_error(
    exc: Exception,
    operation: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> AppError:
    """Classify SQLite database errors (busy, locking, disk I/O)."""
    raw_text = str(exc)
    lower = raw_text.lower()

    if "busy" in lower or "locked" in lower:
        app_err = AppError(
            category=ErrorCategory.DATABASE.value,
            code="DATABASE_BUSY",
            message=f"Database đang bị khoá trong thao tác {operation or ''}".strip(),
            severity=ErrorSeverity.WARNING.value,
            source=operation,
            suggestion="Hệ thống sẽ tự động retry với backoff.",
            details={"raw": raw_text},
        )
    else:
        app_err = AppError(
            category=ErrorCategory.DATABASE.value,
            code="DATABASE_ERROR",
            message=f"Lỗi cơ sở dữ liệu ({operation or 'db'}): {raw_text}",
            severity=ErrorSeverity.ERROR.value,
            source=operation,
            details={"raw": raw_text},
        )

    if log:
        log(f"[!] {app_err.format_notice()}")
    return app_err
