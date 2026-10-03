"""Shared configuration, defaults, override precedence, and error definitions."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from typing import List, Optional

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / '.env'
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass


DEFAULT_PORT: int = 9222
DEFAULT_HOST: str = '127.0.0.1'
DEFAULT_ENDPOINT: str = f'http://{DEFAULT_HOST}:{DEFAULT_PORT}'
DEFAULT_PROFILE_DIR: str = '$HOME/chrome-twitter-profile'
DEFAULT_DOCTOR_TIMEOUT_MS: int = 30000
DEFAULT_READINESS_TIMEOUT_SECONDS: float = 15.0
DEFAULT_CHECK_INTERVAL_SECONDS: float = 0.5

DARWIN_CHROME_CANDIDATES: List[str] = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
]

LINUX_CHROME_CANDIDATES: List[str] = [
    'google-chrome',
    'google-chrome-stable',
    'chromium-browser',
    'chromium',
    'brave-browser',
]


class AgentError(Exception):
    """Structured operational error for social agent tools."""
    def __init__(self, code: str, message: str, human_action_required: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.human_action_required = human_action_required

    def __str__(self) -> str:
        return f'[{self.code}] {self.message}'


def find_browser_binary(custom_bin: Optional[str] = None) -> Optional[str]:
    """Locate a supported Chromium executable.

    Precedence:
    1. Explicit custom_bin argument.
    2. CHROME_BIN environment variable.
    3. Platform-specific default candidate search paths.
    """
    candidate = custom_bin or os.environ.get('CHROME_BIN')
    if candidate:
        expanded = os.path.expandvars(os.path.expanduser(candidate))
        if os.path.isabs(expanded) and os.path.isfile(expanded) and os.access(expanded, os.X_OK):
            return expanded
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        return None

    if sys.platform == 'darwin':
        for path in DARWIN_CHROME_CANDIDATES:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    elif sys.platform.startswith('linux'):
        for bin_name in LINUX_CHROME_CANDIDATES:
            resolved = shutil.which(bin_name)
            if resolved:
                return resolved

    return None


@dataclass(frozen=True)
class Config:
    """Immutable resolved configuration for social agent browser interactions."""
    port: int
    host: str
    endpoint: str
    user_data_dir: Path
    doctor_timeout_ms: int
    readiness_timeout_seconds: float
    chrome_bin: Optional[str] = None


def get_config(
    port: Optional[int] = None,
    host: Optional[str] = None,
    endpoint: Optional[str] = None,
    data_dir: Optional[str | Path] = None,
    timeout_ms: Optional[int] = None,
    readiness_timeout_seconds: Optional[float] = None,
    chrome_bin: Optional[str] = None,
) -> Config:
    """Resolve configuration with documented override precedence:
    Explicit function/CLI arguments > Environment variables > Default fallbacks.
    """
    # 1. Resolve host and port
    resolved_host = host or os.environ.get('CDP_HOST') or DEFAULT_HOST

    resolved_port: int
    if port is not None:
        try:
            resolved_port = int(port)
        except (ValueError, TypeError) as exc:
            raise AgentError('invalid_arguments', f'Invalid port: {port}') from exc
    else:
        env_port = os.environ.get('CDP_PORT') or os.environ.get('PORT')
        if env_port:
            try:
                resolved_port = int(env_port)
            except (ValueError, TypeError) as exc:
                raise AgentError('invalid_arguments', f'Invalid port in environment: {env_port}') from exc
        else:
            resolved_port = DEFAULT_PORT

    if resolved_port <= 0 or resolved_port > 65535:
        raise AgentError('invalid_arguments', f'Port out of valid range (1-65535): {resolved_port}')

    # 2. Resolve endpoint
    if endpoint:
        resolved_endpoint = endpoint
    else:
        env_endpoint = os.environ.get('CDP_ENDPOINT')
        if env_endpoint:
            resolved_endpoint = env_endpoint
        else:
            resolved_endpoint = f'http://{resolved_host}:{resolved_port}'

    # 3. Resolve user data directory
    if data_dir is not None:
        raw_dir = str(data_dir)
    else:
        raw_dir = os.environ.get('CHROME_USER_DATA_DIR') or os.environ.get('USER_DATA_DIR') or DEFAULT_PROFILE_DIR
    resolved_user_data_dir = Path(os.path.expandvars(os.path.expanduser(raw_dir))).resolve()

    # 4. Resolve doctor timeout
    resolved_timeout_ms: int
    if timeout_ms is not None:
        try:
            resolved_timeout_ms = int(timeout_ms)
        except (ValueError, TypeError) as exc:
            raise AgentError('invalid_arguments', f'Invalid timeout: {timeout_ms}') from exc
    else:
        env_timeout = os.environ.get('DEFAULT_DOCTOR_TIMEOUT_MS')
        if env_timeout:
            try:
                resolved_timeout_ms = int(env_timeout)
            except (ValueError, TypeError) as exc:
                raise AgentError('invalid_arguments', f'Invalid timeout in environment: {env_timeout}') from exc
        else:
            resolved_timeout_ms = DEFAULT_DOCTOR_TIMEOUT_MS

    if resolved_timeout_ms <= 0:
        raise AgentError('invalid_arguments', 'Browser timeout must be positive.')

    # 5. Resolve readiness timeout
    resolved_readiness_timeout: float
    if readiness_timeout_seconds is not None:
        try:
            resolved_readiness_timeout = float(readiness_timeout_seconds)
        except (ValueError, TypeError) as exc:
            raise AgentError('invalid_arguments', f'Invalid readiness timeout: {readiness_timeout_seconds}') from exc
    else:
        env_readiness = os.environ.get('CDP_READINESS_TIMEOUT_SECONDS')
        if env_readiness:
            try:
                resolved_readiness_timeout = float(env_readiness)
            except (ValueError, TypeError) as exc:
                raise AgentError('invalid_arguments', f'Invalid readiness timeout in environment: {env_readiness}') from exc
        else:
            resolved_readiness_timeout = DEFAULT_READINESS_TIMEOUT_SECONDS

    if resolved_readiness_timeout <= 0:
        raise AgentError('invalid_arguments', 'Readiness timeout must be positive.')

    # 6. Resolve chrome binary
    resolved_bin = find_browser_binary(chrome_bin)

    return Config(
        port=resolved_port,
        host=resolved_host,
        endpoint=resolved_endpoint,
        user_data_dir=resolved_user_data_dir,
        doctor_timeout_ms=resolved_timeout_ms,
        readiness_timeout_seconds=resolved_readiness_timeout,
        chrome_bin=resolved_bin,
    )
