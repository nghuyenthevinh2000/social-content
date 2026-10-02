"""Stable errors and validation before any browser interaction."""

from pathlib import Path


class AgentError(Exception):
    def __init__(self, code: str, message: str, human_action_required: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.human_action_required = human_action_required


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
