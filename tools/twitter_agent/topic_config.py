"""Topic JSON validation and explicit query construction."""

import copy
import json
from pathlib import Path
from typing import Any, List

from .models import AgentError


def _is_control_char(c: str) -> bool:
    """Return True if character is an ASCII or Unicode control character (excluding regular spaces)."""
    return ord(c) < 32 or (127 <= ord(c) <= 159)


def _normalize_keyword(keyword: Any, field_path: str) -> str:
    """Validate and normalize a keyword term. Raise AgentError on any violation."""
    if not isinstance(keyword, str):
        raise AgentError('invalid_topics_file', f"{field_path}: must be a string, got {type(keyword).__name__}.")

    term = keyword.strip()
    if not term:
        raise AgentError('invalid_topics_file', f"{field_path}: cannot be empty or whitespace only.")

    if any(_is_control_char(c) for c in term):
        raise AgentError('invalid_topics_file', f"{field_path}: contains forbidden control characters.")

    if term.startswith('"') and term.endswith('"'):
        if len(term) <= 2:
            raise AgentError('invalid_topics_file', f"{field_path}: empty quoted phrase.")
        inner = term[1:-1]
        if not inner.strip():
            raise AgentError('invalid_topics_file', f"{field_path}: whitespace-only quoted phrase.")
        if '"' in inner:
            raise AgentError('invalid_topics_file', f"{field_path}: embedded quotes inside quoted phrase.")
        if any(_is_control_char(c) for c in inner):
            raise AgentError('invalid_topics_file', f"{field_path}: contains control characters in quoted phrase.")
        return '"' + inner.strip() + '"'
    else:
        if '"' in term:
            raise AgentError('invalid_topics_file', f"{field_path}: unbalanced or unquoted double quote in term: {term!r}.")
        if any(c in term for c in (':', '(', ')')):
            raise AgentError('invalid_topics_file', f"{field_path}: forbidden operator characters (':', '(', ')') in term: {term!r}.")
        upper = term.upper()
        if upper in ('AND', 'OR', 'NOT'):
            raise AgentError('invalid_topics_file', f"{field_path}: standalone operator {term!r} is not allowed as a term.")

        if any(c.isspace() for c in term):
            return '"' + term + '"'
        return term


def load_topics(path: Path) -> List[dict]:
    """Load and validate topics JSON from path. Raise AgentError('invalid_topics_file', ...) on any issue."""
    p = Path(path)
    try:
        content = p.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise AgentError('invalid_topics_file', f"Failed to read topics file '{p}': {exc}") from exc

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AgentError('invalid_topics_file', f"Malformed JSON in topics file '{p}': {exc}") from exc

    if not isinstance(data, dict):
        raise AgentError('invalid_topics_file', f"Root of topics file '{p}' must be a JSON object, got {type(data).__name__}.")

    if 'topics' not in data:
        raise AgentError('invalid_topics_file', f"Topics file '{p}' is missing required 'topics' list.")

    raw_topics = data['topics']
    if not isinstance(raw_topics, list):
        raise AgentError('invalid_topics_file', f"'topics' must be a list in topics file '{p}', got {type(raw_topics).__name__}.")

    if not raw_topics:
        raise AgentError('invalid_topics_file', f"Field 'topics' list cannot be empty in '{p}'.")

    validated_topics = []
    seen_ids = set()

    for idx, item in enumerate(raw_topics):
        field_prefix = f"topics[{idx}]"
        if not isinstance(item, dict):
            raise AgentError('invalid_topics_file', f"{field_prefix}: must be an object, got {type(item).__name__}.")

        if 'id' not in item:
            raise AgentError('invalid_topics_file', f"{field_prefix}: missing required 'id'.")
        tid = item['id']
        if not isinstance(tid, str) or not tid.strip():
            raise AgentError('invalid_topics_file', f"{field_prefix}.id: cannot be empty string.")
        tid = tid.strip()
        if tid in seen_ids:
            raise AgentError('invalid_topics_file', f"{field_prefix}.id: duplicate topic id '{tid}'.")
        seen_ids.add(tid)

        if 'name' not in item:
            raise AgentError('invalid_topics_file', f"{field_prefix}: missing required 'name'.")
        name = item['name']
        if not isinstance(name, str) or not name.strip():
            raise AgentError('invalid_topics_file', f"{field_prefix}.name: cannot be empty string.")

        if 'search_keywords' not in item:
            raise AgentError('invalid_topics_file', f"{field_prefix}: missing required 'search_keywords'.")
        kws = item['search_keywords']
        if not isinstance(kws, list):
            raise AgentError('invalid_topics_file', f"{field_prefix}.search_keywords: must be a list.")
        if not kws:
            raise AgentError('invalid_topics_file', f"{field_prefix}.search_keywords: cannot be empty.")

        # Validate all search keywords
        for k_idx, kw in enumerate(kws):
            kw_path = f"{field_prefix}.search_keywords[{k_idx}]"
            _normalize_keyword(kw, kw_path)

        # Preserve metadata and input order; do not mutate input dict
        validated_topics.append(copy.deepcopy(item))

    return validated_topics


def build_topic_query(topic: dict, *, start: int, end: int) -> str:
    """Build a search query string for the topic within the half-open window [start, end)."""
    if not isinstance(topic, dict):
        raise AgentError('invalid_topics_file', "Topic must be a dictionary.")

    tid = topic.get('id', 'unknown')
    kws = topic.get('search_keywords')
    if not isinstance(kws, list) or not kws:
        raise AgentError('invalid_topics_file', f"Topic '{tid}' has missing or empty 'search_keywords'.")

    normalized_terms = []
    for k_idx, kw in enumerate(kws):
        norm = _normalize_keyword(kw, f"topic '{tid}'.search_keywords[{k_idx}]")
        normalized_terms.append(norm)

    query = '(' + ' OR '.join(normalized_terms) + ')'
    query += f' since_time:{start} until_time:{end}'
    return query
