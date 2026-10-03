"""Browser and CDP connectivity diagnostics without platform navigation."""

from typing import Any, Dict, Optional

from .browser import CDPBrowser
from .config import get_config


def run_doctor(endpoint: Optional[str] = None, timeout_ms: Optional[int] = None) -> Dict[str, Any]:
    """Diagnose Chrome CDP availability and context readiness.

    Verifies that Chrome is reachable over CDP and has at least one active context,
    reporting the endpoint, version, and context count. Does not navigate to any
    social websites, alter tabs, or launch processes.
    """
    config = get_config(endpoint=endpoint, timeout_ms=timeout_ms)
    with CDPBrowser(endpoint=config.endpoint, timeout_ms=config.doctor_timeout_ms) as cdp:
        return {
            'connected': True,
            'endpoint': config.endpoint,
            'browser_version': cdp.version,
            'context_count': len(cdp.contexts),
        }
