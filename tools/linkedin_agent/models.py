"""Structured errors and immutable, locally validated LinkedIn post inputs."""

from dataclasses import dataclass
from pathlib import Path


class AgentError(Exception):
    def __init__(self, code: str, message: str, human_action_required: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.human_action_required = human_action_required


@dataclass(frozen=True)
class ImageInput:
    name: str
    mime_type: str
    buffer: bytes


def validate_inputs(text: str, paths: list[str]) -> tuple[str, tuple[ImageInput, ...]]:
    """Snapshot image bytes in order without normalizing approved post text."""
    if not isinstance(text, str) or not text.strip() or len(text) > 3000:
        raise AgentError('invalid_text', 'Provide nonblank post text of at most 3,000 characters.')
    if not 1 <= len(paths) <= 20:
        raise AgentError('invalid_images', 'Provide between 1 and 20 PNG/JPEG image paths.')

    images = []
    seen = set()
    max_bytes = 10 * 1024 * 1024
    for index, value in enumerate(paths, start=1):
        try:
            path = Path(value)
            resolved = path.resolve(strict=True)
            if resolved in seen:
                raise AgentError('invalid_images', f'Image {index} repeats a resolved path. Provide distinct image paths.')
            if not resolved.is_file():
                raise AgentError('invalid_images', f'Image {index} must be a readable regular PNG/JPEG file.')
            with resolved.open('rb') as source:
                buffer = source.read(max_bytes + 1)
        except (OSError, ValueError, RuntimeError) as error:
            raise AgentError(
                'invalid_images',
                f'Cannot read image {index}. Check that its path exists and the file is readable.',
            ) from error

        if len(buffer) > max_bytes:
            raise AgentError('invalid_images', f'Image {index} exceeds 10 MiB. Choose a smaller file.')
        if buffer.startswith(b'\x89PNG\r\n\x1a\n'):
            mime_type = 'image/png'
        elif buffer.startswith(b'\xff\xd8\xff'):
            mime_type = 'image/jpeg'
        else:
            raise AgentError('invalid_images', f'Image {index} has no PNG/JPEG signature. Provide a PNG or JPEG file.')
        seen.add(resolved)
        images.append(ImageInput(path.name, mime_type, buffer))

    return text, tuple(images)
