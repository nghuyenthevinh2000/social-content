"""Shared social agent foundation: browser diagnostics, launcher, and post format."""

from .browser import Browser, CDPBrowser, InvisibleBrowser
from .config import (
    AgentError,
    Config,
    find_free_port,
    get_config,
    read_recorded_port,
    resolve_profile_dir,
    write_recorded_port,
)
from .doctor import run_doctor
from .launcher import live_profile_endpoint, start_browser
from .post import (
    PLATFORMS,
    Content,
    PlatformPost,
    Post,
    PostError,
    load_post,
    parse_post,
    plan_post,
)
from .profiles import (
    IDENTITY_FIELDS,
    load_registry,
    normalize_identity,
    record_profile,
    registry_path,
    validate_registry,
)

__all__ = [
    'AgentError',
    'Browser',
    'CDPBrowser',
    'Config',
    'Content',
    'IDENTITY_FIELDS',
    'InvisibleBrowser',
    'PLATFORMS',
    'PlatformPost',
    'Post',
    'PostError',
    'find_free_port',
    'get_config',
    'live_profile_endpoint',
    'load_post',
    'load_registry',
    'normalize_identity',
    'parse_post',
    'plan_post',
    'read_recorded_port',
    'record_profile',
    'registry_path',
    'resolve_profile_dir',
    'run_doctor',
    'start_browser',
    'validate_registry',
    'write_recorded_port',
]
