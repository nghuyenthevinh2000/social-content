"""Stable errors and validation before any browser interaction."""

import json
from pathlib import Path
from urllib.parse import urlparse

from tools.common.errors import AgentError
from tools.common.groups import MAX_SHARE_GROUPS, validate_group_names

MAX_MESSAGE_CHARS = 20000
FACEBOOK_HOSTS = {'www.facebook.com', 'facebook.com', 'm.facebook.com', 'web.facebook.com'}
PROFILE_PLAN_KEYS = {'url', 'recipient', 'message', 'text', 'label'}
NON_PROFILE_PATHS = {
    '', 'home.php', 'me', 'groups', 'pages', 'messages', 'watch',
    'marketplace', 'friends', 'notifications', 'bookmarks', 'events',
}


def load_post_text(path: str | Path) -> str:
    """Read UTF-8 copy without shell interpolation; match preflight newline rules."""
    try:
        return Path(path).expanduser().read_text(encoding='utf-8').rstrip('\n')
    except (OSError, UnicodeError) as exc:
        raise AgentError('invalid_content', f'Cannot read UTF-8 copy file: {path}') from exc


def validate_content(text: str, image: str | Path | None = None) -> tuple[str, Path | None]:
    if not isinstance(text, str) or not text.strip() or len(text) > 63206 or '\x00' in text:
        raise AgentError('invalid_content', 'Provide nonempty text up to 63,206 characters without NUL bytes.')
    if image is None:
        return text, None
    path = Path(image).expanduser().resolve()
    try:
        with path.open('rb') as file:
            header = file.read(16)
    except OSError as exc:
        raise AgentError('invalid_image', f'Cannot read image: {path}') from exc
    is_image = (
        header.startswith(b'\x89PNG\r\n\x1a\n')
        or header.startswith(b'\xff\xd8\xff')
        or header.startswith((b'GIF87a', b'GIF89a'))
        or (header.startswith(b'RIFF') and header[8:12] == b'WEBP')
    )
    if not is_image:
        raise AgentError('invalid_image', 'Image must have a PNG, JPEG, GIF, or WebP signature.')
    return text, path


def _is_video(header: bytes) -> bool:
    return (
        header[4:8] == b'ftyp'                              # MP4, MOV, M4V, 3GP
        or header.startswith(b'\x1aE\xdf\xa3')              # Matroska, WebM
        or (header.startswith(b'RIFF') and header[8:12] == b'AVI ')
        or header.startswith(b'FLV\x01')                    # FLV
        or header.startswith(b'\x30\x26\xb2\x75\x8e\x66\xcf\x11')  # ASF, WMV
        or header.startswith(b'OggS')                       # Ogg, Ogv
    )


def validate_video(video: str | Path | None = None) -> Path | None:
    """Return the resolved video path or raise AgentError('invalid_video')."""
    if video is None:
        return None
    path = Path(video).expanduser().resolve()
    try:
        with path.open('rb') as file:
            header = file.read(16)
    except OSError as exc:
        raise AgentError('invalid_video', f'Cannot read video: {path}') from exc
    if not _is_video(header):
        raise AgentError('invalid_video', 'Video must have an MP4/MOV, WebM/MKV, AVI, WMV, FLV, or Ogg signature.')
    return path


def validate_recipient_url(url: str) -> str:
    """Return a normalized Facebook profile URL or raise AgentError('invalid_plan')."""
    if not isinstance(url, str) or not url.strip():
        raise AgentError('invalid_plan', 'Recipient URL must be a nonempty string.')
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in FACEBOOK_HOSTS:
        raise AgentError('invalid_plan', f'Recipient must be a Facebook profile URL: {value}')
    segments = [part for part in parsed.path.split('/') if part]
    if not segments or segments[0] in NON_PROFILE_PATHS:
        raise AgentError('invalid_plan', f'Recipient URL is not a profile path: {value}')
    if segments[0] == 'profile.php' and not parsed.query:
        raise AgentError('invalid_plan', f'Recipient profile.php URL needs an id parameter: {value}')
    return value


def _validate_recipient(entry, index: int) -> dict:
    """Validate one plan entry and normalize it to {url, message, label}."""
    prefix = f'Plan entry {index}'
    if not isinstance(entry, dict):
        raise AgentError('invalid_plan', f'{prefix} must be an object.')
    unknown = sorted(set(entry) - PROFILE_PLAN_KEYS)
    if unknown:
        raise AgentError('invalid_plan', f'{prefix} has unknown keys: {unknown}.')
    url_keys = [key for key in ('url', 'recipient') if key in entry]
    if len(url_keys) != 1:
        raise AgentError('invalid_plan', f"{prefix} needs exactly one of 'url' or 'recipient'.")
    message_keys = [key for key in ('message', 'text') if key in entry]
    if len(message_keys) != 1:
        raise AgentError('invalid_plan', f"{prefix} needs exactly one of 'message' or 'text'.")
    url = validate_recipient_url(entry[url_keys[0]])
    message = entry[message_keys[0]]
    if not isinstance(message, str) or not message.strip() or '\x00' in message:
        raise AgentError('invalid_plan', f'{prefix} message must be nonempty text without NUL bytes.')
    if len(message) > MAX_MESSAGE_CHARS:
        raise AgentError('invalid_plan', f'{prefix} message exceeds {MAX_MESSAGE_CHARS} characters.')
    label = entry.get('label')
    if label is not None and not isinstance(label, str):
        raise AgentError('invalid_plan', f'{prefix} label must be a string.')
    return {'url': url, 'message': message, 'label': (label or url).strip()}


def load_message_plan(path: str | Path) -> list[dict]:
    """Load and validate a JSON direct-message plan before any browser interaction.

    Accepts a top-level array of entries, or an object with a 'recipients'
    (or 'messages') array. Each entry needs a profile URL and a message.
    Returns a list of {url, message, label} dictionaries.
    """
    resolved = Path(path).expanduser().resolve()
    try:
        raw = resolved.read_text(encoding='utf-8')
    except OSError as exc:
        raise AgentError('invalid_plan', f'Cannot read plan file: {resolved}') from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError('invalid_plan', f'Plan is not valid JSON: {exc}') from exc
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = next((data[key] for key in ('recipients', 'messages', 'plan') if key in data), None)
        if entries is None:
            raise AgentError('invalid_plan', "Plan object must contain a 'recipients' array.")
    else:
        raise AgentError('invalid_plan', 'Plan must be a JSON array or an object with a recipients array.')
    if not isinstance(entries, list) or not entries:
        raise AgentError('invalid_plan', 'Plan must contain at least one recipient.')
    return [_validate_recipient(entry, index) for index, entry in enumerate(entries, start=1)]


def load_group_names(path: str | Path) -> list[str]:
    """Load group names from a JSON array or an object with a 'groups' array."""
    resolved = Path(path).expanduser().resolve()
    try:
        raw = resolved.read_text(encoding='utf-8')
    except OSError as exc:
        raise AgentError('invalid_groups', f'Cannot read groups file: {resolved}') from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError('invalid_groups', f'Groups file is not valid JSON: {exc}') from exc
    if isinstance(data, dict):
        data = data.get('groups')
    if not isinstance(data, list) or not data:
        raise AgentError('invalid_groups', "Groups file must be a JSON array of group names or an object with a 'groups' array.")
    return validate_group_names(data)
