"""Tests for centralized profiling.py and isolated context modes."""

from __future__ import annotations

from tools.app.backend.telemetry import profiling
from tools.app.backend.db import ro


def test_profiling_disabled_by_default():
    profiling.configure(enabled=False, contexts="all")
    assert not profiling.is_enabled()
    assert not profiling.is_enabled("db")
    with profiling.request_scope("GET", "/api/health") as scope:
        assert scope is None


def test_profiling_context_filtering_and_sql_count():
    profiling.configure(enabled=True, contexts="db")
    try:
        assert profiling.is_enabled("db")
        assert not profiling.is_enabled("http")
        with profiling.request_scope("DB", "test_query", context="db") as scope:
            assert scope is not None
            with ro() as conn:
                conn.execute("SELECT 1").fetchone()
            assert scope.sql_count == 1
            assert scope.sql_ms >= 0.0
    finally:
        profiling.configure(enabled=False, contexts="all")


def test_isolated_db_context_runner():
    res = profiling.run_contexts(["db"], iterations=2)
    assert "| `db` |" in res["table"]
    assert "ProfileStore.list_topics" in res["table"]
    assert len(res["explain"]) >= 1
