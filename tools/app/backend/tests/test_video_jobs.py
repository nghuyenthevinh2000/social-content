from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from tools.app.backend.credits import CreditStore, CREDIT_STORE
from tools.app.backend.media import MediaStore
from tools.app.backend.video_jobs import VideoJobStore, VideoRunner, VIDEO_COST_MICRO


def test_video_job_lifecycle_and_cancel():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        c_store = CreditStore(db_path=tmp / "credits.db")
        # monkeypatch global CREDIT_STORE
        import tools.app.backend.video_jobs as vj
        orig_credit_store = vj.CREDIT_STORE
        vj.CREDIT_STORE = c_store

        try:
            store = VideoJobStore(db_path=tmp / "jobs.db", runs_dir=tmp / "runs")
            
            # User has 0 balance -> create fails
            with pytest.raises(ValueError, match="INSUFFICIENT_CREDITS"):
                store.create_job(user_id="u1", prompt="test prompt", profile_media_id="m1")

            # Grant credits
            c_store.grant("u1", 500000)
            assert c_store.get_balance("u1") == 500000

            # Create job reserves 345,000 (15s @ 23,000/s)
            job = store.create_job(user_id="u1", prompt="test prompt", profile_media_id="m1")
            assert job["status"] == "pending"
            assert job["cost"] == 345000
            assert c_store.get_balance("u1") == 155000

            # List jobs
            jobs = store.list_jobs("u1")
            assert len(jobs) == 1
            assert jobs[0]["id"] == job["id"]

            # User 2 cannot see or cancel User 1's job
            assert store.get_job("u2", job["id"]) is None
            assert store.cancel_job("u2", job["id"]) is False

            # Cancel while pending refunds credits
            assert store.cancel_job("u1", job["id"]) is True
            job_cancelled = store.get_job("u1", job["id"])
            assert job_cancelled["status"] == "cancelled"
            assert c_store.get_balance("u1") == 500000

            # Delete job
            assert store.delete_job("u1", job["id"]) is True
            assert store.get_job("u1", job["id"]) is None
        finally:
            vj.CREDIT_STORE = orig_credit_store


def test_crash_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        c_store = CreditStore(db_path=tmp / "credits.db")
        import tools.app.backend.video_jobs as vj
        orig_credit_store = vj.CREDIT_STORE
        vj.CREDIT_STORE = c_store

        try:
            store = VideoJobStore(db_path=tmp / "jobs.db", runs_dir=tmp / "runs")
            c_store.grant("u1", 500000)
            job = store.create_job(user_id="u1", prompt="p", profile_media_id="m1")
            
            # Simulate job running when server crashes
            claimed = store.claim_next_pending()
            assert claimed is not None
            assert store.get_job("u1", job["id"])["status"] == "running"
            assert c_store.get_balance("u1") == 155000

            # Run crash recovery
            recovered = store.recover_stale_jobs()
            assert recovered == 1
            stale_job = store.get_job("u1", job["id"])
            assert stale_job["status"] == "failed"
            assert "Server restarted" in stale_job["error"]
            # Credits refunded
            assert c_store.get_balance("u1") == 500000
        finally:
            vj.CREDIT_STORE = orig_credit_store


def test_concurrency_and_per_user_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        c_store = CreditStore(db_path=tmp / "credits.db")
        m_store = MediaStore(db_path=tmp / "media.db", media_dir=tmp / "media")
        import tools.app.backend.video_jobs as vj
        orig_credit_store = vj.CREDIT_STORE
        vj.CREDIT_STORE = c_store

        try:
            store = VideoJobStore(db_path=tmp / "jobs.db", runs_dir=tmp / "runs")
            
            # Save dummy profile media for u1 and u2
            m1 = m_store.save_media("u1", "profile", b"fakejpg1", "image/jpeg")
            m2 = m_store.save_media("u2", "profile", b"fakejpg2", "image/jpeg")

            c_store.grant("u1", 1000000)
            c_store.grant("u2", 1000000)

            # u1 enqueues two jobs, u2 enqueues one job
            j1_u1 = store.create_job("u1", "prompt 1", m1["id"])
            j2_u1 = store.create_job("u1", "prompt 2", m1["id"])
            j1_u2 = store.create_job("u2", "prompt 3", m2["id"])

            def mock_gen(prompt, profile_image_bytes, context_images_bytes, output_path):
                time.sleep(0.1)
                output_path.write_bytes(b"dummy_mp4")

            runner = VideoRunner(
                store=store,
                media_store=m_store,
                max_workers=2,
                max_per_user=1,
                generator=mock_gen,
            )

            runner.trigger()
            # Give background threads time to claim
            time.sleep(0.05)
            # Max 1 running for u1, max 1 running for u2
            assert store.count_running("u1") == 1
            assert store.count_running("u2") == 1
            assert store.count_running() == 2

            # Wait for completion
            time.sleep(0.3)
            # After j1_u1 completes, j2_u1 should run and complete
            time.sleep(0.2)
            assert store.get_job("u1", j1_u1["id"])["status"] == "completed"
            assert store.get_job("u1", j2_u1["id"])["status"] == "completed"
            assert store.get_job("u2", j1_u2["id"])["status"] == "completed"
            runner.shutdown()
        finally:
            vj.CREDIT_STORE = orig_credit_store
