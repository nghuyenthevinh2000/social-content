"""Credit and ledger management for video generation."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from tools.app.backend.profiles import RUNS_ROOT, now_iso

RATE_PER_SEC_MICRO = 23000  # $0.023/s, 10s = 230,000 micro-USD = $0.23


class CreditStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or (RUNS_ROOT / "credits.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            db.execute("""
            CREATE TABLE IF NOT EXISTS user_credits (
                user_id TEXT PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0
            )
            """)
            db.execute("""
            CREATE TABLE IF NOT EXISTS credit_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                job_id TEXT,
                created_at TEXT NOT NULL
            )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_ledger_user ON credit_ledger (user_id, created_at)")
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.close()

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout = 30000")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                try:
                    db.execute("ROLLBACK")
                except Exception:
                    pass
            raise
        finally:
            db.close()

    @contextmanager
    def _ro(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA busy_timeout = 30000")
        try:
            yield db
        finally:
            db.close()

    def get_balance(self, user_id: str) -> int:
        with self._ro() as db:
            row = db.execute("SELECT balance FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
            return int(row[0]) if row else 0

    def get_ledger(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._ro() as db:
            rows = db.execute(
                "SELECT id, user_id, delta, reason, job_id, created_at FROM credit_ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [
            {
                "id": r[0],
                "user_id": r[1],
                "delta": r[2],
                "reason": r[3],
                "job_id": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def grant(self, user_id: str, delta_micro: int, reason: str = "grant", job_id: Optional[str] = None) -> int:
        if delta_micro <= 0:
            raise ValueError("Grant amount must be positive.")
        with self._tx() as db:
            db.execute(
                """
                INSERT INTO user_credits (user_id, balance) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
                """,
                (user_id, delta_micro),
            )
            db.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, job_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, delta_micro, reason, job_id, now_iso()),
            )
            row = db.execute("SELECT balance FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
            return int(row[0])

    def reserve(self, user_id: str, amount_micro: int, job_id: str, reason: str = "reserve") -> bool:
        if amount_micro <= 0:
            raise ValueError("Reserve amount must be positive.")
        with self._tx() as db:
            row = db.execute("SELECT balance FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
            if not row or int(row[0]) < amount_micro:
                return False
            cursor = db.execute(
                "UPDATE user_credits SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                (amount_micro, user_id, amount_micro),
            )
            if cursor.rowcount == 0:
                return False
            db.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, job_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, -amount_micro, reason, job_id, now_iso()),
            )
            return True

    def refund(self, user_id: str, amount_micro: int, job_id: str, reason: str = "refund") -> int:
        if amount_micro <= 0:
            return self.get_balance(user_id)
        with self._tx() as db:
            db.execute(
                """
                INSERT INTO user_credits (user_id, balance) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
                """,
                (user_id, amount_micro),
            )
            db.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, job_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, amount_micro, reason, job_id, now_iso()),
            )
            row = db.execute("SELECT balance FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
            return int(row[0])

    def estimate(self, duration_sec: int = 10, user_id: Optional[str] = None) -> Dict[str, Any]:
        cost_micro = duration_sec * RATE_PER_SEC_MICRO
        balance = self.get_balance(user_id) if user_id else 0
        return {
            "cost_micro": cost_micro,
            "cost_usd": round(cost_micro / 1_000_000, 4),
            "duration_sec": duration_sec,
            "balance": balance,
            "balance_usd": round(balance / 1_000_000, 4),
            "can_afford": balance >= cost_micro,
        }


CREDIT_STORE = CreditStore()


def main() -> None:
    parser = argparse.ArgumentParser(description="Credit ledger CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    grant_p = subparsers.add_parser("grant", help="Grant credits to a user")
    grant_p.add_argument("user_id", help="Target user ID")
    grant_p.add_argument("amount", type=int, help="Amount in micro-USD (e.g. 1000000 = $1.00)")
    grant_p.add_argument("--reason", default="cli_grant", help="Ledger reason")

    bal_p = subparsers.add_parser("balance", help="Check user balance")
    bal_p.add_argument("user_id", help="Target user ID")

    args = parser.parse_args()
    if args.command == "grant":
        bal = CREDIT_STORE.grant(args.user_id, args.amount, reason=args.reason)
        print(f"Granted {args.amount} micro-USD to {args.user_id}. New balance: {bal} ({bal / 1_000_000:.2f} USD)")
    elif args.command == "balance":
        bal = CREDIT_STORE.get_balance(args.user_id)
        print(f"User {args.user_id} balance: {bal} micro-USD ({bal / 1_000_000:.2f} USD)")


if __name__ == "__main__":
    main()
