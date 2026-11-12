"""24/7 Facebook Page DM Ingestion & User Library Sync Service.

Periodically polls Facebook Page messages via Meta Graph API v27.0,
determines the sender (Page-Scoped ID / PSID), resolves their user identity,
and saves the captured Reel directly into their app Library.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import string
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

# Ensure project root is in sys.path
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.common.config import load_environment
from tools.common.errors import AgentError
from tools.facebook_agent.dm_crawl.crawler import (
    canonicalize_reel_url,
    extract_reels_from_text,
    _resolve_page_token,
)
from tools.app.backend.db import tx, ro
from tools.app.backend.profiles import SocialProfileStore

logger = logging.getLogger("dm_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LINK_CODE_RE = re.compile(r'^(?:#?LINK[-_]?([a-zA-Z0-9]{4,8}))', re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_credentials() -> tuple[str, str]:
    """Retrieve Page ID and Page Access Token from environment or dm_crawl/.env."""
    load_environment(include_repository=True)
    env_file = Path(_project_root) / "tools" / "facebook_agent" / "dm_crawl" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ or not os.environ[k]:
                    os.environ[k] = v

    page_id = os.environ.get("PAGE_ID", "1216806404853891")
    token = os.environ.get("PAGE_ACCESS_TOKEN", "")

    # Resolve Page Access Token if it is a user token
    resolved = _resolve_page_token(page_id, token, "v27.0")
    if resolved:
        page_id, _, token = resolved

    return page_id, token


def send_messenger_reply(page_id: str, access_token: str, recipient_psid: str, text: str) -> bool:
    """Send an automated confirmation or notification reply back to the user via Messenger."""
    if not access_token or not recipient_psid:
        return False
    url = f"https://graph.facebook.com/v27.0/{page_id}/messages"
    payload = json.dumps({
        "recipient": {"id": recipient_psid},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "SocialContentBot/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.warning("Failed to send Messenger reply to %s: %s", recipient_psid, exc)
        return False


def create_link_code(user_id: str, valid_minutes: int = 60) -> str:
    """Generate a unique 6-character link code for a web user to connect their Facebook Messenger."""
    chars = string.ascii_uppercase + string.digits
    code = f"LINK-{''.join(random.choices(chars, k=6))}"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=valid_minutes)).isoformat()

    with tx() as conn:
        conn.execute(
            "INSERT INTO account_link_codes (code, user_id, expires_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (code) DO UPDATE SET user_id = EXCLUDED.user_id, expires_at = EXCLUDED.expires_at",
            (code, user_id, expires),
        )
    return code


def find_user_by_psid(psid: str) -> Optional[str]:
    """Look up which app user_id is mapped to a Facebook Page-Scoped ID."""
    with ro() as conn:
        cur = conn.execute("SELECT user_id FROM facebook_user_mappings WHERE psid = %s", (psid,))
        row = cur.fetchone()
        return row[0] if row else None


def link_psid_to_user(psid: str, user_id: str, fb_name: Optional[str] = None) -> None:
    """Permanently bind a Facebook PSID to an app user_id."""
    now = now_iso()
    with tx() as conn:
        conn.execute(
            "INSERT INTO facebook_user_mappings (psid, user_id, fb_name, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (psid) DO UPDATE SET user_id = EXCLUDED.user_id, fb_name = COALESCE(EXCLUDED.fb_name, facebook_user_mappings.fb_name), updated_at = EXCLUDED.updated_at",
            (psid, user_id, fb_name, now, now),
        )


def check_and_apply_link_code(code: str, psid: str, fb_name: Optional[str] = None) -> Optional[str]:
    """Validate a link code, map the user, and delete the one-time code."""
    clean_code = code.strip().upper()
    now = now_iso()
    with tx() as conn:
        cur = conn.execute(
            "SELECT user_id FROM account_link_codes WHERE code = %s AND expires_at > %s",
            (clean_code, now),
        )
        row = cur.fetchone()
        if not row:
            return None
        user_id = row[0]
        conn.execute("DELETE FROM account_link_codes WHERE code = %s", (clean_code,))

    link_psid_to_user(psid, user_id, fb_name)
    return user_id


class DmPollerService:
    """Background polling service checking Facebook Page DMs 24/7."""

    def __init__(
        self,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None,
        poll_interval_sec: int = 30,
        reply_user: bool = True,
    ):
        self.page_id, self.access_token = page_id or "", access_token or ""
        self.poll_interval_sec = poll_interval_sec
        self.reply_user = reply_user
        self._profile_store: Optional[SocialProfileStore] = None
        self.seen_message_ids: set[str] = set()
        self._running = False

    @property
    def profile_store(self) -> SocialProfileStore:
        if self._profile_store is None:
            self._profile_store = SocialProfileStore()
        return self._profile_store

    def init_credentials(self):
        if not self.page_id or not self.access_token:
            self.page_id, self.access_token = get_credentials()

    def process_message(self, msg: Dict[str, Any], page_id: str, token: str) -> None:
        """Process a single incoming message: handle account linking or reel ingestion."""
        msg_id = msg.get("id")
        if not msg_id or msg_id in self.seen_message_ids:
            return
        self.seen_message_ids.add(msg_id)

        sender = msg.get("from", {})
        sender_id = str(sender.get("id", ""))
        sender_name = sender.get("name", "Người dùng Facebook")
        msg_text = msg.get("message", "").strip()

        if not sender_id or sender_id == str(page_id):
            return

        # 1. Check for Account Linking Command (e.g. LINK-ABC123)
        code_match = LINK_CODE_RE.match(msg_text)
        if code_match:
            full_code = f"LINK-{code_match.group(1).upper()}"
            matched_user = check_and_apply_link_code(full_code, sender_id, sender_name)
            if matched_user:
                logger.info("Successfully linked PSID %s to user_id %s", sender_id, matched_user)
                if self.reply_user:
                    send_messenger_reply(
                        page_id,
                        token,
                        sender_id,
                        f"✅ Đã liên kết tài khoản thành công! Bây giờ bạn chỉ cần gửi/chia sẻ bất kỳ Reel nào vào đây để lưu vào thư viện.",
                    )
            else:
                if self.reply_user:
                    send_messenger_reply(
                        page_id,
                        token,
                        sender_id,
                        f"⚠️ Mã liên kết không hợp lệ hoặc đã hết hạn. Vui lòng lấy mã mới từ trang web của bạn.",
                    )
            return

        # 2. Extract Reel URLs (Native Shares + Text Links)
        reels_to_save: List[Dict[str, Any]] = []

        # Native share sheet
        for share_item in msg.get("shares", {}).get("data", []):
            canonical = canonicalize_reel_url(share_item.get("link"))
            if canonical:
                reels_to_save.append({
                    "reel_url": canonical[0],
                    "original_url": canonical[0],
                    "platform": canonical[1],
                    "share_type": "native_share",
                })

        # Text links
        text_links = extract_reels_from_text(msg_text)
        for t in text_links:
            # If native share already matched a canonical /reel/, don't duplicate
            if not any(r["reel_url"] == t["url"] for r in reels_to_save):
                reels_to_save.append({
                    "reel_url": t["url"],
                    "original_url": t["url"],
                    "platform": t["platform"],
                    "share_type": "link_share",
                })

        if not reels_to_save:
            return

        # 3. Determine the target user
        user_id = find_user_by_psid(sender_id)
        if not user_id:
            logger.info("Received Reel from unlinked PSID %s (%s)", sender_id, sender_name)
            if self.reply_user:
                send_messenger_reply(
                    page_id,
                    token,
                    sender_id,
                    "👋 Bạn chưa liên kết tài khoản! Để lưu Reel vào thư viện của mình, vui lòng đăng nhập trên website và gửi mã liên kết (VD: LINK-ABC123) vào đây.",
                )
            return

        # 4. Save into User Library
        for item in reels_to_save:
            self._save_to_user_library(
                user_id=user_id,
                reel_url=item["reel_url"],
                original_url=item["original_url"],
                platform=item["platform"],
                share_type=item["share_type"],
                sender_psid=sender_id,
                sender_name=sender_name,
                message_text=msg_text,
            )

        if self.reply_user:
            count = len(reels_to_save)
            msg_ack = f"🎬 Đã lưu thành công {count} Reel vào Thư viện của bạn trên website!"
            send_messenger_reply(page_id, token, sender_id, msg_ack)

    def _save_to_user_library(
        self,
        user_id: str,
        reel_url: str,
        original_url: str,
        platform: str,
        share_type: str,
        sender_psid: str,
        sender_name: str,
        message_text: str,
    ) -> None:
        """Persist Reel into database: saved_reels table and profiles Library topic."""
        reel_id = f"reel_{hashlib.md5(f'{user_id}:{reel_url}'.encode('utf-8')).hexdigest()[:16]}"
        now = now_iso()

        # Insert into saved_reels table
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO saved_reels (
                    id, user_id, reel_url, original_url, platform, share_type,
                    sender_psid, sender_name, message_text, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, reel_url) DO NOTHING
                """,
                (
                    reel_id, user_id, reel_url, original_url, platform, share_type,
                    sender_psid, sender_name, message_text, now,
                ),
            )

        # Also register into ProfileStore under default topic "saved-reels" so it renders in the UI
        try:
            topic_slug = "saved-reels"
            topic_name = "Thư viện Reel đã lưu"
            self.profile_store.upsert_topic(topic_slug, topic_name, user_id=user_id)
            self.profile_store.add_profile(
                topic_slug=topic_slug,
                name=sender_name or "Reel đã lưu từ Messenger",
                url=reel_url,
                user_id=user_id,
            )
            logger.info("Saved reel %s to user library for user_id %s", reel_url, user_id)
        except Exception as exc:
            logger.warning("Could not add reel to ProfileStore: %s", exc)

    def poll_once(self) -> int:
        """Perform a single poll against Graph API v27.0. Returns number of messages processed."""
        self.init_credentials()
        fields = (
            "id,snippet,updated_time,participants,"
            "messages.limit(25){id,message,created_time,from,shares{id,description,link,name},attachments{id,mime_type,name,file_url,video_data,type,payload}}"
        )
        query = urllib.parse.urlencode({"fields": fields, "limit": "20", "access_token": self.access_token})
        url = f"https://graph.facebook.com/v27.0/{self.page_id}/conversations?{query}"

        req = urllib.request.Request(url, headers={"User-Agent": "SocialContentBot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.error("Polling error: %s", exc)
            return 0

        processed = 0
        for conv in data.get("data", []):
            for msg in reversed(conv.get("messages", {}).get("data", [])):
                self.process_message(msg, self.page_id, self.access_token)
                processed += 1
        return processed

    def run_forever(self) -> None:
        """Main service loop running 24/7."""
        self._running = True
        self.init_credentials()
        logger.info(
            "Starting 24/7 DM Poller Service for Page ID: %s (Interval: %ds)",
            self.page_id, self.poll_interval_sec,
        )

        while self._running:
            try:
                self.poll_once()
            except Exception as exc:
                logger.error("Unhandled exception in poll loop: %s", exc)
            time.sleep(self.poll_interval_sec)

    def stop(self) -> None:
        self._running = False


_SERVICE_INSTANCE: Optional[DmPollerService] = None


def start_dm_service(daemon: bool = True) -> DmPollerService:
    """Start the DM poller as a background thread."""
    global _SERVICE_INSTANCE
    if _SERVICE_INSTANCE is None:
        import threading
        _SERVICE_INSTANCE = DmPollerService()
        thread = threading.Thread(target=_SERVICE_INSTANCE.run_forever, daemon=daemon)
        thread.start()
    return _SERVICE_INSTANCE


def main():
    parser = argparse.ArgumentParser(description="24/7 Facebook Page DM Ingestion Daemon")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds (default: 30)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron/testing)")
    parser.add_argument("--link", help="Generate a link code for a user_id: --link <USER_ID>")
    parser.add_argument("--bind", nargs=2, metavar=("PSID", "USER_ID"), help="Directly bind a PSID to USER_ID")

    args = parser.parse_args()

    if args.link:
        code = create_link_code(args.link)
        print(f"Generated Link Code for user '{args.link}': {code}")
        return 0

    if args.bind:
        psid, uid = args.bind
        link_psid_to_user(psid, uid)
        print(f"Successfully bound PSID {psid} -> user_id {uid}")
        return 0

    svc = DmPollerService(poll_interval_sec=args.interval)
    if args.once:
        count = svc.poll_once()
        print(f"Polled once successfully. Processed {count} messages.")
        return 0

    svc.run_forever()


if __name__ == "__main__":
    main()
