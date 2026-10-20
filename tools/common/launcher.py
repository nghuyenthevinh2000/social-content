"""Browser process detection, startup, and readiness check with CDP reuse."""

from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, Optional, Union
import urllib.request

from .config import (
    AgentError,
    Config,
    DEFAULT_START_URL,
    find_browser_binary,
    find_free_port,
    get_config,
    read_recorded_port,
    resolve_host,
    resolve_profile_dir,
    write_recorded_port,
)


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
    start_url: str = DEFAULT_START_URL,
) -> None:
    """Launch the Chromium process configured for loopback remote debugging.

    `start_url` guarantees the fresh profile keeps at least one tab, because
    Chrome drops to zero browser contexts once its first-run tab closes and CDP
    clients then refuse to attach.
    """
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
                start_url,
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
                start_url,
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def live_profile_endpoint(
    data_dir: Optional[Union[str, Path]] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    responsive_checker: Optional[Callable[[int, str], bool]] = None,
) -> Optional[str]:
    """Return the CDP endpoint of a running profile, or None when it is not up.

    Reads the port recorded for the profile directory by `start_browser`, so a
    caller can target one identity without hardcoding a port.
    """
    resolved_host = resolve_host(host)
    resolved_port = port if port is not None else read_recorded_port(resolve_profile_dir(data_dir))
    if resolved_port is None:
        return None
    checker = responsive_checker or (lambda p, h: is_browser_responsive(p, h, timeout=1.0))
    if not checker(resolved_port, resolved_host):
        return None
    return f'http://{resolved_host}:{resolved_port}'


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
    auto_port: bool = False,
    check_interval: float = 0.5,
    responsive_checker: Optional[Callable[[int, str], bool]] = None,
    process_launcher: Optional[Callable[[str, int, Path, str], None]] = None,
) -> Dict[str, Any]:
    """Detect or initialize invisible browser or CDP browser for one profile.

    Each call targets one profile directory (`data_dir`), so different social
    identities keep separate logins. With `auto_port=True` the profile is given
    an unused CDP port the first time and that port is recorded inside the
    profile directory for later runs.

    Returns:
        Dict reporting action ('ready', 'reused', or 'started'), backend,
        user_data_dir, and relevant connection or engine details.
    """
    resolved_backend = backend
    if resolved_backend is None and (port is not None or chrome_bin is not None or auto_port):
        resolved_backend = 'cdp'

    if auto_port and port is None and resolved_backend != 'invisible':
        profile_dir = resolve_profile_dir(data_dir)
        resolved_host = resolve_host(host)
        checker = responsive_checker or (lambda p, h: is_browser_responsive(p, h, timeout=1.0))
        recorded_port = read_recorded_port(profile_dir)
        if recorded_port is not None and checker(recorded_port, resolved_host):
            return {
                'action': 'reused',
                'endpoint': f'http://{resolved_host}:{recorded_port}',
                'port': recorded_port,
                'user_data_dir': str(profile_dir),
            }
        port = recorded_port if recorded_port is not None else find_free_port(resolved_host)

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
    ready = False
    while time.monotonic() < deadline:
        if checker(config.port, config.host):
            ready = True
            break
        time.sleep(check_interval)

    # Final check at boundary
    if not ready:
        ready = checker(config.port, config.host)

    if not ready:
        raise AgentError(
            'browser_readiness_timeout',
            f'Browser process launched, but CDP did not become ready within '
            f'{config.readiness_timeout_seconds} seconds at {config.endpoint}.',
            human_action_required=True,
        )

    if auto_port:
        write_recorded_port(config.user_data_dir, config.port)

    return {
        'action': 'started',
        'endpoint': config.endpoint,
        'port': config.port,
        'user_data_dir': str(config.user_data_dir),
        'browser_bin': binary_path,
    }
