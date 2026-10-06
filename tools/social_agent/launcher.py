"""Browser process detection, startup, and readiness check with CDP reuse."""

from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, Optional, Union
import urllib.request

from .config import AgentError, Config, find_browser_binary, get_config


def is_browser_responsive(port: int, host: str = '127.0.0.1', timeout: float = 1.0) -> bool:
    """Check if Chrome CDP HTTP endpoint is responsive."""
    url = f'http://{host}:{port}/json/version'
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def launch_browser_process(
    chrome_bin: str,
    port: int,
    user_data_dir: Path,
    host: str = '127.0.0.1',
) -> None:
    """Launch the Chromium process configured for loopback remote debugging."""
    # Ensure profile directory exists
    user_data_dir.mkdir(parents=True, exist_ok=True)

    if sys.platform == 'darwin' and '.app' in chrome_bin:
        app_bundle = chrome_bin[:chrome_bin.index('.app') + 4]
        subprocess.Popen(
            [
                'open',
                '-na',
                app_bundle,
                '--args',
                f'--remote-debugging-port={port}',
                f'--remote-debugging-address={host}',
                f'--user-data-dir={user_data_dir}',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            [
                chrome_bin,
                f'--remote-debugging-port={port}',
                f'--remote-debugging-address={host}',
                f'--user-data-dir={user_data_dir}',
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def start_browser(
    port: Optional[int] = None,
    host: Optional[str] = None,
    data_dir: Optional[Union[str, Path]] = None,
    timeout: Optional[float] = None,
    chrome_bin: Optional[str] = None,
    backend: Optional[str] = None,
    seed: Optional[int] = None,
    headless: Optional[bool] = None,
    binary_path: Optional[str] = None,
    check_interval: float = 0.5,
    responsive_checker: Optional[Callable[[int, str], bool]] = None,
    process_launcher: Optional[Callable[[str, int, Path, str], None]] = None,
) -> Dict[str, Any]:
    """Detect or initialize invisible browser or CDP browser.

    Returns:
        Dict reporting action ('ready', 'reused', or 'started'), backend,
        user_data_dir, and relevant connection or engine details.
    """
    resolved_backend = backend
    if resolved_backend is None and (port is not None or chrome_bin is not None):
        resolved_backend = 'cdp'

    config = get_config(
        port=port,
        host=host,
        data_dir=data_dir,
        readiness_timeout_seconds=timeout,
        chrome_bin=chrome_bin,
        backend=resolved_backend,
        seed=seed,
        headless=headless,
        binary_path=binary_path,
    )

    if config.backend == 'invisible':
        config.user_data_dir.mkdir(parents=True, exist_ok=True)
        engine_desc = 'invisible engine ready'
        try:
            from invisible_playwright_mcp.engine import Engine
            eng = Engine(binary_path=config.binary_path)
            if not eng.ready():
                eng.start()
                eng.settle(timeout=config.readiness_timeout_seconds)
            engine_desc = eng.describe()
        except Exception:
            pass

        return {
            'action': 'ready',
            'backend': 'invisible',
            'user_data_dir': str(config.user_data_dir),
            'seed': config.seed,
            'headless': config.headless,
            'binary_path': config.binary_path,
            'engine_status': engine_desc,
        }
    checker = responsive_checker or (lambda p, h: is_browser_responsive(p, h, timeout=1.0))
    launcher = process_launcher or launch_browser_process

    # 1. Reuse existing responsive browser without restarting or killing it
    if checker(config.port, config.host):
        return {
            'action': 'reused',
            'endpoint': config.endpoint,
            'port': config.port,
            'user_data_dir': str(config.user_data_dir),
        }

    # 2. Locate browser executable
    binary_path = config.chrome_bin
    if not binary_path:
        raise AgentError(
            'browser_binary_not_found',
            f'Could not locate a compatible Chromium/Chrome binary. '
            f'Please launch Chrome manually with: '
            f'--remote-debugging-port={config.port} --user-data-dir="{config.user_data_dir}"',
            human_action_required=True,
        )

    # 3. Launch the browser process bound to loopback
    launcher(binary_path, config.port, config.user_data_dir, config.host)

    # 4. Wait for readiness using bounded timeout
    deadline = time.monotonic() + config.readiness_timeout_seconds
    while time.monotonic() < deadline:
        if checker(config.port, config.host):
            return {
                'action': 'started',
                'endpoint': config.endpoint,
                'port': config.port,
                'user_data_dir': str(config.user_data_dir),
                'browser_bin': binary_path,
            }
        time.sleep(check_interval)

    # Final check at boundary
    if checker(config.port, config.host):
        return {
            'action': 'started',
            'endpoint': config.endpoint,
            'port': config.port,
            'user_data_dir': str(config.user_data_dir),
            'browser_bin': binary_path,
        }

    raise AgentError(
        'browser_readiness_timeout',
        f'Browser process launched, but CDP did not become ready within '
        f'{config.readiness_timeout_seconds} seconds at {config.endpoint}.',
        human_action_required=True,
    )
