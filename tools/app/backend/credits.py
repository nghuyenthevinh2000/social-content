"""Credit and ledger management for video generation."""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List, Optional

from tools.app.backend.db import ro, tx
from tools.app.backend.profiles import now_iso
from tools.app.backend.video_engine import _load_env, get_video_duration


def get_rate_per_sec_micro() -> int:
    """Return rate per second in micro-USD enforced by RATE_PER_SEC_MICRO (default 23000)."""
    _load_env()
    try:
        return int(os.environ.get("RATE_PER_SEC_MICRO", 23000))
    except (ValueError, TypeError):
        return 23000


RATE_PER_SEC_MICRO = get_rate_per_sec_micro()


class CreditStore:
    def __init__(self) -> None:
        pass

    def get_balance(self, user_id: str) -> int:
        with ro() as conn:
            cur = conn.execute("SELECT balance FROM user_credits WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_ledger(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with ro() as conn:
            cur = conn.execute(
                "SELECT id, user_id, delta, reason, job_id, created_at FROM credit_ledger WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
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
        with tx() as conn:
            cur = conn.execute(
                """
                INSERT INTO user_credits (user_id, balance) VALUES (%s, %s)
                ON CONFLICT(user_id) DO UPDATE SET balance = user_credits.balance + EXCLUDED.balance
                RETURNING balance
                """,
                (user_id, delta_micro),
            )
            row = cur.fetchone()
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, job_id, created_at) VALUES (%s, %s, %s, %s, %s)",
                (user_id, delta_micro, reason, job_id, now_iso()),
            )
            return int(row[0]) if row else 0

    def reserve(self, user_id: str, amount_micro: int, job_id: str, reason: str = "reserve") -> bool:
        if amount_micro <= 0:
            raise ValueError("Reserve amount must be positive.")
        with tx() as conn:
            cur = conn.execute(
                "UPDATE user_credits SET balance = balance - %s WHERE user_id = %s AND balance >= %s RETURNING balance",
                (amount_micro, user_id, amount_micro),
            )
            row = cur.fetchone()
            if not row:
                return False
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, job_id, created_at) VALUES (%s, %s, %s, %s, %s)",
                (user_id, -amount_micro, reason, job_id, now_iso()),
            )
            return True

    def refund(self, user_id: str, amount_micro: int, job_id: str, reason: str = "refund") -> int:
        if amount_micro <= 0:
            return self.get_balance(user_id)
        with tx() as conn:
            cur = conn.execute(
                """
                INSERT INTO user_credits (user_id, balance) VALUES (%s, %s)
                ON CONFLICT(user_id) DO UPDATE SET balance = user_credits.balance + EXCLUDED.balance
                RETURNING balance
                """,
                (user_id, amount_micro),
            )
            row = cur.fetchone()
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, job_id, created_at) VALUES (%s, %s, %s, %s, %s)",
                (user_id, amount_micro, reason, job_id, now_iso()),
            )
            return int(row[0]) if row else 0

    def claim_email_credits(self, email: str, user_id: str) -> None:
        """Transfer any balance granted to an email address to the user's authenticated UID."""
        if not email or not user_id or email == user_id:
            return
        with tx() as conn:
            cur = conn.execute("SELECT balance FROM user_credits WHERE user_id = %s FOR UPDATE", (email,))
            row = cur.fetchone()
            if not row or row[0] <= 0:
                return
            amount = row[0]
            conn.execute("UPDATE user_credits SET balance = 0 WHERE user_id = %s", (email,))
            conn.execute(
                """
                INSERT INTO user_credits (user_id, balance) VALUES (%s, %s)
                ON CONFLICT(user_id) DO UPDATE SET balance = user_credits.balance + EXCLUDED.balance
                """,
                (user_id, amount),
            )
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, created_at) VALUES (%s, %s, %s, %s)",
                (user_id, amount, f"claim_from_email:{email}", now_iso()),
            )
            conn.execute(
                "INSERT INTO credit_ledger (user_id, delta, reason, created_at) VALUES (%s, %s, %s, %s)",
                (email, -amount, f"transferred_to_uid:{user_id}", now_iso()),
            )

    def estimate(self, user_id: Optional[str] = None, *_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        dur = get_video_duration()
        rate = get_rate_per_sec_micro()
        cost_micro = dur * rate
        balance = self.get_balance(user_id) if user_id else 0
        return {
            "cost_micro": cost_micro,
            "cost_usd": round(cost_micro / 1_000_000, 4),
            "rate_per_sec_micro": rate,
            "duration_sec": dur,
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
