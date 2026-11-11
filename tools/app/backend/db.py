"""Centralized PostgreSQL connection pooling and transaction management."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import threading
from typing import Dict, Iterator, Optional

import psycopg
from psycopg_pool import ConnectionPool

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/aibrand"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_POOLS: Dict[int, ConnectionPool] = {}
_POOLS_LOCK = threading.Lock()
_SCHEMA_INITIALIZED = False


def get_dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


def get_pool(dsn: Optional[str] = None) -> ConnectionPool:
    global _POOLS
    pid = os.getpid()
    target_dsn = dsn or get_dsn()
    max_size = int(os.environ.get("DB_POOL_MAX", "10"))

    with _POOLS_LOCK:
        pool = _POOLS.get(pid)
        if pool is None or getattr(pool, "closed", False):
            pool = ConnectionPool(
                conninfo=target_dsn,
                min_size=1,
                max_size=max_size,
                timeout=30.0,
                open=True,
                kwargs={"autocommit": False},
            )
            _POOLS[pid] = pool
        return pool


def close_pools() -> None:
    global _POOLS
    with _POOLS_LOCK:
        for pool in _POOLS.values():
            try:
                pool.close()
            except Exception:
                pass
        _POOLS.clear()


@contextmanager
def tx() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.transaction():
            yield conn


@contextmanager
def ro() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def init_schema(dsn: Optional[str] = None) -> None:
    global _SCHEMA_INITIALIZED
    target_dsn = dsn or get_dsn()
    if not SCHEMA_PATH.exists():
        return
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(target_dsn, autocommit=True) as conn:
        conn.execute(sql)
    _SCHEMA_INITIALIZED = True


# Run init_schema once at import if database is reachable
try:
    init_schema()
except Exception:
    # Will initialize when connection is ready or in tests
    pass
