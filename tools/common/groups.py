"""Canonical Facebook sharing-group names and limit."""

from .errors import AgentError

MAX_SHARE_GROUPS = 9


def validate_group_names(names) -> list[str]:
    """Validate an iterable of names, trimming whitespace and preserving order."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(names, start=1):
        if not isinstance(item, str) or not item.strip() or '\x00' in item:
            raise AgentError('invalid_groups', f'Group {index} must be a nonempty name.')
        name = item.strip()
        if name in seen:
            raise AgentError('invalid_groups', f'Group name repeated: {name}')
        seen.add(name)
        cleaned.append(name)
    if len(cleaned) > MAX_SHARE_GROUPS:
        raise AgentError('invalid_groups', f'At most {MAX_SHARE_GROUPS} groups can be shared to in one post.')
    return cleaned
