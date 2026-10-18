"""Unified, platform-agnostic post documents and per-platform adapters.

One JSON post records approved content once and resolves it into the exact
arguments each posting agent expects, so a single post can be reused across
Facebook, LinkedIn, and X/Twitter instead of maintaining three separate inputs.

Media paths are resolved relative to the post file's own directory, so a post
document and its assets can be moved together. Nothing here connects to a
browser or publishes; it only validates and translates.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

FACEBOOK_MAX_TEXT = 63206
LINKEDIN_MAX_TEXT = 3000
TWITTER_MAX_TEXT = 280
LINKEDIN_MAX_IMAGES = 20
MAX_SHARE_GROUPS = 9

PLATFORMS = ('facebook', 'linkedin', 'twitter')
FACEBOOK_PROFILES = ('personal', 'page')

_TOP_KEYS = frozenset({'id', 'title', 'content', 'posting_groups', 'platforms'})
_CONTENT_KEYS = frozenset({'text', 'images', 'video'})
_OVERRIDE_KEYS = frozenset({'text', 'images', 'video'})
_PLATFORM_KEYS = {
    'facebook': _OVERRIDE_KEYS | {'enabled', 'profile', 'page_name', 'page_id', 'posting_groups'},
    'linkedin': _OVERRIDE_KEYS | {'enabled'},
    'twitter': _OVERRIDE_KEYS | {'enabled', 'account', 'approved'},
}


class PostError(Exception):
    """Stable error raised for any invalid or unsupported post document."""

    def __init__(self, code: str, message: str, human_action_required: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.human_action_required = human_action_required


def _invalid(message: str) -> PostError:
    return PostError('invalid_post', message)


def _require_text(value: Any, where: str) -> str:
    """Return nonblank text unchanged (exact match matters for captions)."""
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f'{where} must be nonempty text.')
    if '\x00' in value:
        raise _invalid(f'{where} must not contain NUL bytes.')
    return value


def _require_text_within(value: Any, limit: int, where: str) -> str:
    text = _require_text(value, where)
    if len(text) > limit:
        raise _invalid(f'{where} exceeds {limit} characters for this platform ({len(text)} given).')
    return text


def _require_identifier(value: Any, where: str) -> str:
    text = _require_text(value, where).strip()
    return text


def _resolve_media(value: Any, base_dir: Path | None, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f'{where} must be a nonempty path string.')
    path = Path(value).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return str(path)


def _resolve_images(value: Any, base_dir: Path | None, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _invalid(f'{where} must be an array of image paths.')
    return tuple(
        _resolve_media(item, base_dir, f'{where}[{index}]')
        for index, item in enumerate(value)
    )


def _validate_group_names(names: Any) -> tuple[str, ...]:
    if not isinstance(names, list):
        raise PostError('invalid_groups', 'posting_groups must be an array of group names.')
    cleaned: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(names, start=1):
        if not isinstance(item, str) or not item.strip() or '\x00' in item:
            raise PostError('invalid_groups', f'posting_groups[{index}] must be a nonempty group name.')
        name = item.strip()
        if name in seen:
            raise PostError('invalid_groups', f'posting_groups repeats the name: {name}')
        seen.add(name)
        cleaned.append(name)
    if len(cleaned) > MAX_SHARE_GROUPS:
        raise PostError('invalid_groups', f'At most {MAX_SHARE_GROUPS} posting_groups are allowed per post.')
    return tuple(cleaned)


@dataclass(frozen=True)
class Content:
    """Shared default caption and media, inherited by every platform."""

    text: str
    images: tuple[str, ...] = ()
    video: str | None = None


@dataclass(frozen=True)
class PlatformPost:
    """Resolved, validated content for one platform plus its posting options."""

    platform: str
    text: str
    images: tuple[str, ...] = ()
    video: str | None = None
    posting_groups: tuple[str, ...] = ()
    profile: str | None = None
    page_name: str | None = None
    page_id: str | None = None
    account: str | None = None
    approved: bool = False

    @property
    def image(self) -> str | None:
        """Single media path for the one-image platforms (Facebook and X)."""
        return self.images[0] if self.images else None

    def arguments(self) -> dict[str, Any]:
        """Keyword arguments matching the target agent's ``publish`` function."""
        if self.platform == 'facebook':
            return {'text': self.text, 'image': self.image, 'video': self.video,
                    'groups': list(self.posting_groups) or None,
                    'page_name': self.page_name, 'page_id': self.page_id}
        if self.platform == 'linkedin':
            return {'text': self.text, 'images': list(self.images)}
        return {'text': self.text, 'image': self.image, 'account': self.account,
                'approved': self.approved}

    def command(self, runner: tuple[str, ...] = ('uv', 'run', 'python', '-m')) -> list[str]:
        """Return the equivalent CLI invocation without executing anything."""
        base = list(runner)
        if self.platform == 'facebook':
            argv = base + ['tools.facebook_agent', 'post', '--text', self.text]
            if self.image:
                argv += ['--image', self.image]
            if self.video:
                argv += ['--video', self.video]
            if self.page_name:
                argv += ['--page-name', self.page_name]
            if self.page_id:
                argv += ['--page-id', self.page_id]
            for group in self.posting_groups:
                argv += ['--group', group]
            return argv
        if self.platform == 'linkedin':
            argv = base + ['tools.linkedin_agent', 'post', '--text', self.text]
            for image in self.images:
                argv += ['--image', image]
            return argv
        argv = base + ['tools.twitter_agent.publish', '--text', self.text,
                       '--image', self.image or '', '--account', self.account or '']
        if self.approved:
            argv += ['--approved']
        return argv


@dataclass(frozen=True)
class Post:
    """A validated post plus the concrete plan for each enabled platform."""

    content: Content
    posting_groups: tuple[str, ...]
    platforms: Mapping[str, PlatformPost]
    id: str | None = None
    title: str | None = None

    @property
    def platform_names(self) -> tuple[str, ...]:
        return tuple(self.platforms)

    def for_platform(self, name: str) -> PlatformPost:
        try:
            return self.platforms[name]
        except KeyError as exc:
            raise PostError('platform_not_enabled', f'Post does not target {name}.') from exc


def _parse_platform(name: str, block: Any, content: Content,
                    default_groups: tuple[str, ...], base_dir: Path | None) -> PlatformPost | None:
    if not isinstance(block, dict):
        raise _invalid(f'platforms.{name} must be an object.')
    unknown = sorted(set(block) - _PLATFORM_KEYS[name])
    if unknown:
        raise _invalid(f'Unknown keys for platforms.{name}: {unknown}.')
    enabled = block.get('enabled', True)
    if not isinstance(enabled, bool):
        raise _invalid(f'platforms.{name}.enabled must be true or false.')
    if not enabled:
        return None

    text = content.text if 'text' not in block else _require_text(block['text'], f'platforms.{name}.text')
    images = content.images if 'images' not in block else _resolve_images(
        block['images'], base_dir, f'platforms.{name}.images')
    if 'video' not in block:
        video = content.video
    else:
        video = (None if block['video'] is None
                 else _resolve_media(block['video'], base_dir, f'platforms.{name}.video'))
    groups = default_groups
    if name == 'facebook' and 'posting_groups' in block:
        groups = _validate_group_names(block['posting_groups'])

    if name == 'facebook':
        if len(images) > 1:
            raise _invalid('Facebook accepts at most one image; override platforms.facebook.images.')
        if video is not None and images:
            raise _invalid('Facebook accepts either images or a video, not both.')
        _require_text_within(text, FACEBOOK_MAX_TEXT, 'platforms.facebook.text')
        profile = block.get('profile', 'personal')
        if profile not in FACEBOOK_PROFILES:
            raise _invalid(f'platforms.facebook.profile must be one of {list(FACEBOOK_PROFILES)}.')
        page_name = block.get('page_name')
        if page_name is not None:
            page_name = _require_identifier(page_name, 'platforms.facebook.page_name')
        page_id = block.get('page_id')
        if page_id is not None:
            page_id = _require_identifier(page_id, 'platforms.facebook.page_id')
            if not page_id.isascii() or not page_id.isdecimal():
                raise _invalid('platforms.facebook.page_id must contain ASCII digits only.')
        if profile == 'page' and not (page_name or page_id):
            raise _invalid("platforms.facebook.profile 'page' needs page_name or page_id.")
        if profile == 'personal' and (page_name or page_id):
            raise _invalid("platforms.facebook.profile 'personal' must not set page_name or page_id.")
        return PlatformPost(name, text, images, video, groups,
                            profile=profile, page_name=page_name, page_id=page_id)

    if name == 'linkedin':
        if video is not None:
            raise _invalid('LinkedIn posting does not support video in this tool.')
        _require_text_within(text, LINKEDIN_MAX_TEXT, 'platforms.linkedin.text')
        if not 1 <= len(images) <= LINKEDIN_MAX_IMAGES:
            raise _invalid(f'LinkedIn requires between 1 and {LINKEDIN_MAX_IMAGES} images.')
        return PlatformPost(name, text, images, None)

    # name == 'twitter'
    if video is not None:
        raise _invalid('X/Twitter posting does not support video in this tool.')
    _require_text_within(text, TWITTER_MAX_TEXT, 'platforms.twitter.text')
    if len(images) != 1:
        raise _invalid('X/Twitter posting requires exactly one image; override platforms.twitter.images.')
    account = _require_text(block.get('account'), 'platforms.twitter.account').lstrip('@')
    if not account or not all(c.isascii() and (c.isalnum() or c == '_') for c in account):
        raise _invalid('platforms.twitter.account must be an X handle.')
    approved = block.get('approved', False)
    if not isinstance(approved, bool):
        raise _invalid('platforms.twitter.approved must be true or false.')
    return PlatformPost(name, text, images, None, account=account, approved=approved)


def parse_post(data: Any, base_dir: Path | None = None) -> Post:
    """Validate an already-decoded post document. Media paths resolve against ``base_dir``."""
    if not isinstance(data, dict):
        raise _invalid('Post must be a JSON object.')
    unknown = sorted(set(data) - _TOP_KEYS)
    if unknown:
        raise _invalid(f'Unknown top-level keys: {unknown}.')

    content_block = data.get('content')
    if not isinstance(content_block, dict):
        raise _invalid("Post needs a 'content' object.")
    unknown = sorted(set(content_block) - _CONTENT_KEYS)
    if unknown:
        raise _invalid(f'Unknown content keys: {unknown}.')
    content = Content(
        text=_require_text(content_block.get('text'), 'content.text'),
        images=_resolve_images(content_block.get('images', []), base_dir, 'content.images'),
        video=(None if content_block.get('video') is None
               else _resolve_media(content_block['video'], base_dir, 'content.video')),
    )

    groups = _validate_group_names(data.get('posting_groups', []))

    platforms_block = data.get('platforms')
    if not isinstance(platforms_block, dict) or not platforms_block:
        raise _invalid("Post needs a nonempty 'platforms' object.")
    unknown = sorted(set(platforms_block) - set(PLATFORMS))
    if unknown:
        raise _invalid(f'Unknown platforms: {unknown}. Supported: {list(PLATFORMS)}.')

    plans: dict[str, PlatformPost] = {}
    for name, block in platforms_block.items():
        plan = _parse_platform(name, block, content, groups, base_dir)
        if plan is not None:
            plans[name] = plan
    if not plans:
        raise _invalid('At least one platform must be enabled.')

    post_id = data.get('id')
    title = data.get('title')
    return Post(
        content=content,
        posting_groups=groups,
        platforms=MappingProxyType(plans),
        id=None if post_id is None else _require_identifier(post_id, 'id'),
        title=None if title is None else _require_identifier(title, 'title'),
    )


def load_post(path: str | Path) -> Post:
    """Load and validate a unified post, resolving media relative to its file."""
    resolved = Path(path).expanduser().resolve()
    try:
        raw = resolved.read_text(encoding='utf-8')
    except OSError as exc:
        raise PostError('invalid_post', f'Cannot read post file: {resolved}') from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PostError('invalid_post', f'Post is not valid JSON: {exc}') from exc
    return parse_post(data, base_dir=resolved.parent)


def plan_post(path: str | Path, platforms: Sequence[str] | None = None) -> dict[str, Any]:
    """Resolve a post into JSON-serializable per-platform plans. Never posts."""
    loaded = load_post(path)
    names = tuple(platforms) if platforms else loaded.platform_names
    plans = []
    for name in names:
        plan = loaded.for_platform(name)
        plans.append({'platform': name, 'arguments': plan.arguments(), 'command': plan.command()})
    return {
        'id': loaded.id,
        'title': loaded.title,
        'posting_groups': list(loaded.posting_groups),
        'plans': plans,
    }


__all__ = [
    'Content', 'FACEBOOK_MAX_TEXT', 'FACEBOOK_PROFILES', 'LINKEDIN_MAX_IMAGES',
    'LINKEDIN_MAX_TEXT', 'MAX_SHARE_GROUPS', 'PLATFORMS', 'PlatformPost', 'Post',
    'PostError', 'TWITTER_MAX_TEXT', 'load_post', 'parse_post', 'plan_post',
]
