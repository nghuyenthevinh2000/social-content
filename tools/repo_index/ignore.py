"""Gitignore-style ignore rules shared by the repository index and hooks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

DEFAULT_IGNORE_FILE = ".repo-indexignore"

# Always-on safety net. Kept small on purpose; project-specific policy belongs
# in .repo-indexignore so it can be reviewed and changed in one place.
DEFAULT_PATTERNS: Sequence[str] = (
    ".git/",
    ".hg/",
    ".svn/",
    ".venv/",
    "venv/",
    "env/",
    "node_modules/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".DS_Store",
    ".env",
    ".env.*",
    "*.sqlite3",
    "*.db",
    "*.lock",
    "package-lock.json",
    "uv.lock",
)


@dataclass(frozen=True)
class Rule:
    """A single compiled ignore pattern."""

    source: str
    negated: bool
    dir_only: bool
    anchored: bool
    has_slash: bool
    regex: re.Pattern[str]

    def matches(self, rel_path: str, is_dir: bool) -> bool:
        if self.dir_only and not is_dir and not self._matches_ancestor(rel_path):
            return False
        return bool(self.regex.match(rel_path)) or self._matches_ancestor(rel_path)

    def _matches_ancestor(self, rel_path: str) -> bool:
        if not self.dir_only:
            return False
        parts = rel_path.split("/")
        for i in range(1, len(parts)):
            if self.regex.match("/".join(parts[:i])):
                return True
        return False


def _translate(pattern: str) -> str:
    """Translate a gitignore glob to a regular expression body."""
    out: List[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                i += 2
                if i < len(pattern) and pattern[i] == "/":
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        elif char == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(r"\[")
                i += 1
            else:
                body = pattern[i + 1 : end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                i = end + 1
        else:
            out.append(re.escape(char))
            i += 1
    return "".join(out)


def _compile(pattern: str, source: str = "") -> Optional[Rule]:
    raw = pattern.strip()
    if not raw or raw.startswith("#"):
        return None

    negated = raw.startswith("!")
    if negated:
        raw = raw[1:].strip()
        if not raw:
            return None

    dir_only = raw.endswith("/")
    if dir_only:
        raw = raw[:-1]
    if not raw:
        return None

    anchored = raw.startswith("/")
    if anchored:
        raw = raw[1:]
    if not raw:
        return None

    has_slash = "/" in raw
    body = _translate(raw)

    if anchored or has_slash:
        regex_body = "^" + body
    else:
        # A pattern without a slash matches at any depth.
        regex_body = "^(?:.*/)?" + body

    # A directory rule also matches everything below it.
    if dir_only:
        regex_body += "(?:/.*)?"
    regex_body += "$"

    try:
        return Rule(
            source=source or pattern,
            negated=negated,
            dir_only=dir_only,
            anchored=anchored,
            has_slash=has_slash,
            regex=re.compile(regex_body),
        )
    except re.error:
        return None


class IgnoreRules:
    """Ordered ignore rules; the last matching rule wins."""

    def __init__(self, rules: Iterable[Rule]):
        self.rules = list(rules)

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        rel = rel_path.replace("\\", "/").strip("/")
        if rel in {"", "."}:
            return False
        ignored = False
        for rule in self.rules:
            if rule.matches(rel, is_dir):
                ignored = not rule.negated
        return ignored

    def add(self, patterns: Sequence[str], source: str = "<runtime>") -> "IgnoreRules":
        rules = list(self.rules)
        for pattern in patterns:
            rule = _compile(pattern, source)
            if rule is not None:
                rules.append(rule)
        return IgnoreRules(rules)


def load_rules(
    root: Path,
    extra_patterns: Optional[Sequence[str]] = None,
    ignore_file: Optional[Path] = None,
) -> IgnoreRules:
    """Load defaults, then .repo-indexignore, then runtime patterns."""
    root = Path(root).resolve()
    rules: List[Rule] = []
    for pattern in DEFAULT_PATTERNS:
        rule = _compile(pattern, "<defaults>")
        if rule is not None:
            rules.append(rule)

    path = ignore_file or (root / DEFAULT_IGNORE_FILE)
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                rule = _compile(line, str(path))
                if rule is not None:
                    rules.append(rule)
        except OSError:
            pass

    for pattern in extra_patterns or ():
        rule = _compile(pattern, "<runtime>")
        if rule is not None:
            rules.append(rule)

    return IgnoreRules(rules)


def is_ignored(
    root: Path,
    rel_path: str,
    is_dir: bool = False,
    extra_patterns: Optional[Sequence[str]] = None,
) -> bool:
    """Convenience wrapper for one-off checks."""
    return load_rules(root, extra_patterns=extra_patterns).is_ignored(rel_path, is_dir=is_dir)
