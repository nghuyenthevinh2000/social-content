"""Repository index: one deterministic, edit-oriented catalog for AI agents."""

from .indexer import SCHEMA_VERSION, build_index, check_index, ensure_fresh

__all__ = ["SCHEMA_VERSION", "build_index", "check_index", "ensure_fresh"]
