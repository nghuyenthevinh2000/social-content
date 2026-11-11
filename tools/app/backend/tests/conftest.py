"""Pytest fixtures for Postgres and RustFS test isolation."""

from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import psycopg
import pytest

from tools.app.backend import blobs
from tools.app.backend.db import close_pools, init_schema

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/aibrand_test",
)


@pytest.fixture(autouse=True, scope="session")
def setup_test_env():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["BLOB_ENDPOINT"] = os.environ.get("BLOB_ENDPOINT", "http://localhost:9000")
    os.environ["BLOB_BUCKET"] = "test-aibrand"
    os.environ["BLOB_ACCESS_KEY"] = os.environ.get("BLOB_ACCESS_KEY", "rustfsadmin")
    os.environ["BLOB_SECRET_KEY"] = os.environ.get("BLOB_SECRET_KEY", "rustfsadmin")
    os.environ["BLOB_REGION"] = "us-east-1"
    blobs.reset_client()
    close_pools()
    init_schema(TEST_DATABASE_URL)


@pytest.fixture(autouse=True)
def clean_test_db():
    dsn = os.environ.get("DATABASE_URL", TEST_DATABASE_URL)
    db_name = dsn.split("/")[-1].split("?")[0]
    assert db_name.endswith("_test"), f"Refusing to truncate non-test DB '{db_name}'!"
    close_pools()
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("""
            TRUNCATE TABLE
                job_logs,
                jobs,
                credit_ledger,
                user_credits,
                user_media,
                video_jobs,
                profiles,
                topics,
                profile_cache,
                videos,
                metric_snapshots
            CASCADE;
        """)
    blobs.delete_prefix("test/")
    blobs.delete_prefix("media/")
    blobs.delete_prefix("videos/")
    blobs.delete_prefix("runs/")
    yield
    close_pools()
