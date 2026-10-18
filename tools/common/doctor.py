"""Browser and CDP connectivity diagnostics without platform navigation."""

from typing import Any, Dict, Optional

from .browser import CDPBrowser, InvisibleBrowser
from .config import get_config


def run_doctor(
    endpoint: Optional[str] = None,
    timeout_ms: Optional[int] = None,
    backend: Optional[str] = None,
    data_dir: Optional[str] = None,
    seed: Optional[int] = None,
    headless: Optional[bool] = None,
    binary_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Diagnose browser availability and context readiness.

    Supports both invisible stealth browser and Chrome CDP without navigating
    to any social websites, altering tabs, or launching unmanaged processes.
    """
    resolved_backend = backend
    if resolved_backend is None and endpoint is not None:
        resolved_backend = 'cdp'

    config = get_config(
        endpoint=endpoint,
        timeout_ms=timeout_ms,
        backend=resolved_backend,
        data_dir=data_dir,
        seed=seed,
        headless=headless,
        binary_path=binary_path,
    )

    if config.backend == 'invisible':
        with InvisibleBrowser(
            data_dir=config.user_data_dir,
            seed=config.seed,
            headless=config.headless,
            proxy=config.proxy,
            binary_path=config.binary_path,
            timeout_ms=config.doctor_timeout_ms,
            endpoint=config.endpoint,
        ) as browser:
            return {
                'connected': True,
                'backend': 'invisible',
                'browser_version': browser.version,
                'user_data_dir': str(config.user_data_dir),
                'seed': browser.seed,
                'context_count': len(browser.contexts),
            }

    with CDPBrowser(endpoint=config.endpoint, timeout_ms=config.doctor_timeout_ms) as cdp:
        return {
            'connected': True,
            'endpoint': config.endpoint,
            'browser_version': cdp.version,
            'context_count': len(cdp.contexts),
        }
