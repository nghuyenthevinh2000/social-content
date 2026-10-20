"""Machine-local registry of browser profiles used for social publishing.

One profile directory holds one login session, so this registry is the
machine-local list of identities this checkout has launched and the CDP port
each one uses. It is written under `tools/common/local`, which is gitignored,
because ports and profile paths are specific to one machine.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .config import AgentError, get_config, read_recorded_port, resolve_profile_dir
from .post import PLATFORMS

REGISTRY_DIRNAME: str = 'local'
REGISTRY_FILENAME: str = 'profiles.json'

# Identity fields each platform accepts, mirroring the unified post schema so a
# registry entry maps straight onto an agent's arguments.
IDENTITY_FIELDS: Dict[str, tuple] = {
    'facebook': ('page_id',),
    'linkedin': ('account',),
    'twitter': ('account',),
}


def _configured_backend() -> str:
    """Backend this checkout would use, for profiles recorded without one."""
    try:
        return get_config().backend
    except Exception:
        return 'cdp'


def default_registry_dir() -> Path:
    """Directory holding the machine-local registry, next to this package."""
    return Path(__file__).resolve().parent / REGISTRY_DIRNAME


def registry_path(base_dir: Optional[Union[str, Path]] = None) -> Path:
    """Path of the registry file, optionally overridden for tests."""
    base = Path(base_dir) if base_dir is not None else default_registry_dir()
    return base / REGISTRY_FILENAME


def profile_name(data_dir: Union[str, Path]) -> str:
    """Short handle for a profile: its directory name."""
    return Path(data_dir).name


def normalize_identity(platform: str, values: Dict[str, Any]) -> Dict[str, str]:
    """Validate and trim one platform's identity fields for a profile."""
    if platform not in IDENTITY_FIELDS:
        raise AgentError(
            'invalid_identity',
            f'Unknown platform {platform!r}. Expected one of {list(IDENTITY_FIELDS)}.',
        )
    unknown = sorted(set(values) - set(IDENTITY_FIELDS[platform]))
    if unknown:
        raise AgentError(
            'invalid_identity',
            f'{platform} does not accept {unknown}; expected {list(IDENTITY_FIELDS[platform])}.',
        )

    cleaned: Dict[str, str] = {}
    for field, value in values.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            raise AgentError('invalid_identity', f'{platform}.{field} must not be empty.')
        if field == 'page_id':
            if not text.isascii() or not text.isdecimal():
                raise AgentError(
                    'invalid_identity', f'{platform}.page_id must contain ASCII digits only.'
                )
        elif field == 'account' and platform == 'twitter':
            text = text.lstrip('@')
            if not text or not all(c.isascii() and (c.isalnum() or c == '_') for c in text):
                raise AgentError('invalid_identity', f'{platform}.account must be an X handle.')
        cleaned[field] = text
    return cleaned


def load_registry(base_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load the registry, returning an empty one when missing or unreadable."""
    try:
        raw = json.loads(registry_path(base_dir).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'profiles': {}}
    profiles = raw.get('profiles') if isinstance(raw, dict) else None
    return {'profiles': profiles if isinstance(profiles, dict) else {}}


def record_profile(
    data_dir: Optional[Union[str, Path]] = None,
    *,
    port: Optional[int] = None,
    backend: Optional[str] = None,
    identities: Optional[Dict[str, Dict[str, Any]]] = None,
    base_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Add or update one used profile and return the updated registry.

    The profile is keyed by its directory name. A port is taken from the caller,
    or from the profile's recorded `.cdp-port` marker when the caller has none.
    `identities` links platforms to the account this profile is logged into,
    merged field by field so a later call can add one platform without clearing
    the others.
    """
    profile_dir = resolve_profile_dir(data_dir)
    registry = load_registry(base_dir)
    entry = registry['profiles'].get(profile_name(profile_dir), {})

    entry['data_dir'] = str(profile_dir)
    entry['backend'] = backend or entry.get('backend') or _configured_backend()
    resolved_port = port if port is not None else read_recorded_port(profile_dir)
    if resolved_port is not None:
        entry['port'] = resolved_port
    entry['last_used'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    if identities:
        linked = {platform: dict(fields) for platform, fields in entry.get('identities', {}).items()}
        for platform, values in identities.items():
            linked.setdefault(platform, {}).update(normalize_identity(platform, values))
        entry['identities'] = linked

    registry['profiles'][profile_name(profile_dir)] = entry
    target = registry_path(base_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    return registry


def validate_registry(registry: Dict[str, Any]) -> None:
    """Reject a registry whose platform keys or identity fields are unknown."""
    profiles = registry.get('profiles')
    if not isinstance(profiles, dict):
        raise AgentError('invalid_registry', 'Registry must hold a "profiles" object.')
    for name, entry in profiles.items():
        if not isinstance(entry, dict):
            raise AgentError('invalid_registry', f'Profile {name!r} must be an object.')
        identities = entry.get('identities', {})
        if not isinstance(identities, dict):
            raise AgentError('invalid_registry', f'Profile {name!r} identities must be an object.')
        for platform, values in identities.items():
            if platform not in PLATFORMS:
                raise AgentError(
                    'invalid_registry',
                    f'Profile {name!r} lists unknown platform {platform!r}.',
                )
            try:
                normalize_identity(platform, values or {})
            except AgentError as exc:
                raise AgentError('invalid_registry', f'Profile {name!r}: {exc.message}') from exc
