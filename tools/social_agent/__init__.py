"""Shared social agent foundation for browser CDP diagnostics and launcher."""

from .browser import Browser, CDPBrowser, InvisibleBrowser
from .config import AgentError, Config, get_config
from .doctor import run_doctor
from .launcher import start_browser

__all__ = [
    'AgentError',
    'Browser',
    'CDPBrowser',
    'InvisibleBrowser',
    'Config',
    'get_config',
    'run_doctor',
    'start_browser',
]
