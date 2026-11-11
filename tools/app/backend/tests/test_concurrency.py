"""Concurrency tests: verify no double-claim and no negative balance under load."""

from __future__ import annotations

import concurrent.futures
from tools.app.backend.credits import CREDIT_STORE
from tools.app.backend.store import JobStore
from tools.app.backend.video_jobs import VIDEO_STORE


def test_concurrent_job_claims_no_double_claim():
    store = JobStore()
    job_id = "test_race_job"
    job = {
        "id": job_id,
        "client_id": "client_a",
        "user_id": "user_a",
        "status": "queued",
        "created_at": "2026-11-11T00:00:00Z",
        "filename": "test.xlsx",
        "sheets": [],
    }
    store.put(job)

    def attempt_claim(worker_idx: int):
        return store.claim(max_per_client=1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_claim, i) for i in range(20)]
        results = [f.result() for f in futures]

    claimed = [r for r in results if r is not None]
    assert len(claimed) == 1, f"Expected exactly 1 claim, got {len(claimed)}"
    assert claimed[0]["id"] == job_id


def test_concurrent_video_job_claims_no_double_claim():
    CREDIT_STORE.grant("user_v_race", 500000)
    job = VIDEO_STORE.create_job("user_v_race", "prompt", "prof_m1")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(VIDEO_STORE.claim_next_pending, 2, 1) for _ in range(20)]
        results = [f.result() for f in futures]

    claimed = [r for r in results if r is not None]
    assert len(claimed) == 1, f"Expected exactly 1 video claim, got {len(claimed)}"
    assert claimed[0]["id"] == job["id"]


def test_concurrent_credit_reserves_no_negative_balance():
    # Grant balance for exactly 3 operations (3 * 230,000 = 690,000)
    user_id = "user_concurrent_race"
    CREDIT_STORE.grant(user_id, 690000)

    def attempt_reserve(op_idx: int):
        return CREDIT_STORE.reserve(user_id, 230000, job_id=f"job_{op_idx}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_reserve, i) for i in range(20)]
        results = [f.result() for f in futures]

    successes = results.count(True)
    failures = results.count(False)
    assert successes == 3, f"Expected 3 successes, got {successes}"
    assert failures == 17, f"Expected 17 failures, got {failures}"
    assert CREDIT_STORE.get_balance(user_id) == 0
