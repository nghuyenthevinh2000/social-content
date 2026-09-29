"""Shared values, stable errors, and exact-content approval binding."""

from dataclasses import dataclass
import hashlib
import json
import math
import re
import unicodedata
from urllib.parse import urlsplit


class AgentError(Exception):
    def __init__(self, code: str, message: str, human_action_required: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.human_action_required = human_action_required


@dataclass(frozen=True)
class Target:
    id: str
    url: str


@dataclass(frozen=True)
class Limits:
    hourly: int = 6
    daily: int = 20
    spacing: float = 120.0
    burst_max: int = 3

    def __post_init__(self):
        if (type(self.hourly) is not int or self.hourly <= 0
                or type(self.daily) is not int or self.daily <= 0
                or type(self.spacing) not in (int, float)
                or not math.isfinite(self.spacing) or self.spacing < 0
                or type(self.burst_max) is not int or self.burst_max <= 0):
            raise AgentError('invalid_limits', 'Limits need positive integer quotas, finite nonnegative spacing, and positive burst_max.')


def normalize_target(value: str) -> Target:
    """Accept a positive ASCII ID or a status URL on an exact supported host."""
    invalid = AgentError('invalid_target', 'Expected a positive post ID or an X/Twitter status URL.')
    if (not isinstance(value, str) or not value
            or any(c.isspace() or c in '\\\"\'' or unicodedata.category(c) in ('Cc', 'Cs') for c in value)):
        raise invalid
    if re.fullmatch(r'[0-9]+', value):
        post_id = value
    else:
        try:
            parsed = urlsplit(value)
            if (parsed.scheme not in ('http', 'https')
                    or parsed.hostname not in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com')
                    or parsed.username is not None or parsed.password is not None
                    or parsed.port not in (None, 443 if parsed.scheme == 'https' else 80)
                    or parsed.netloc.endswith(':')):
                raise invalid
        except ValueError as error:
            raise invalid from error
        match = re.fullmatch(r'/[A-Za-z0-9_]+/status/([0-9]+)', parsed.path)
        if match is None:
            raise invalid
        post_id = match.group(1)
    post_id = post_id.lstrip('0')
    if not post_id:
        raise invalid
    return Target(post_id, f'https://x.com/i/status/{post_id}')


def draft_digest(target_id: str, text: str) -> str:
    payload = json.dumps([target_id, text], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def validate_text(text: str) -> None:
    """Validate without normalizing or stripping the stored reply."""
    if (not isinstance(text, str) or not text.strip()
            or any(unicodedata.category(c) in ('Cc', 'Cs') and c not in '\t\n' for c in text)):
        raise AgentError('invalid_text', 'Reply text must be nonempty, valid Unicode without control characters except tabs/newlines.')
