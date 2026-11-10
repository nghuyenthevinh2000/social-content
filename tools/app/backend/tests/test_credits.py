import concurrent.futures
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from tools.app.backend.credits import CreditStore, RATE_PER_SEC_MICRO

def test_credit_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CreditStore(db_path=Path(tmpdir) / "credits.db")
        
        # New user has 0 balance
        assert store.get_balance("user_a") == 0
        est = store.estimate(duration_sec=10, user_id="user_a")
        assert est["cost_micro"] == 230000
        assert est["cost_usd"] == 0.23
        assert est["can_afford"] is False
        
        # Cannot reserve with 0 balance
        assert store.reserve("user_a", 230000, job_id="job1") is False
        assert store.get_balance("user_a") == 0
        
        # Grant credits
        new_bal = store.grant("user_a", 500000, reason="test_grant")
        assert new_bal == 500000
        assert store.get_balance("user_a") == 500000
        
        # Estimate now shows can_afford = True
        est2 = store.estimate(duration_sec=10, user_id="user_a")
        assert est2["can_afford"] is True

        est15 = store.estimate(duration_sec=15, user_id="user_a")
        assert est15["cost_micro"] == 345000
        assert est15["cost_usd"] == 0.345
        assert est15["can_afford"] is True
        
        # Reserve credits
        ok = store.reserve("user_a", 230000, job_id="job1")
        assert ok is True
        assert store.get_balance("user_a") == 270000
        
        # Reserve again
        ok2 = store.reserve("user_a", 230000, job_id="job2")
        assert ok2 is True
        assert store.get_balance("user_a") == 40000
        
        # Third reserve fails due to insufficient balance
        ok3 = store.reserve("user_a", 230000, job_id="job3")
        assert ok3 is False
        assert store.get_balance("user_a") == 40000
        
        # Refund job2
        ref = store.refund("user_a", 230000, job_id="job2", reason="failure_refund")
        assert ref == 270000
        assert store.get_balance("user_a") == 270000
        
        # Check ledger
        ledger = store.get_ledger("user_a")
        # Entries: grant(+500k), reserve(-230k), reserve(-230k), refund(+230k)
        assert len(ledger) == 4
        assert ledger[0]["delta"] == 230000
        assert ledger[0]["reason"] == "failure_refund"

def test_concurrent_reserves_never_go_negative():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CreditStore(db_path=Path(tmpdir) / "credits.db")
        # Exactly enough for 3 videos (3 * 230,000 = 690,000)
        store.grant("user_concurrent", 690000)
        
        def attempt_reserve(i):
            return store.reserve("user_concurrent", 230000, job_id=f"job_{i}")
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(attempt_reserve, i) for i in range(10)]
            results = [f.result() for f in futures]
            
        # Exactly 3 should succeed, 7 should fail
        assert results.count(True) == 3
        assert results.count(False) == 7
        assert store.get_balance("user_concurrent") == 0


