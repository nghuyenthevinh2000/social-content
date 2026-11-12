from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from tools.app.backend.services.dm_service import (
    canonicalize_reel_url,
    extract_reels_from_text,
    find_user_by_psid,
    link_psid_to_user,
    DmPollerService,
)
from tools.app.backend.services.get_page_token import (
    exchange_long_lived_user_token,
    resolve_env_path,
    save_token_to_env,
)


class DmServiceTests(unittest.TestCase):
    def test_canonicalize_reels(self):
        fb_url = "https://www.facebook.com/reel/1042248898646523?s=yWDuG2"
        res = canonicalize_reel_url(fb_url)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "https://www.facebook.com/reel/1042248898646523")
        self.assertEqual(res[1], "facebook")

        ig_url = "https://www.instagram.com/reel/C-xyz123/?igsh=123"
        res_ig = canonicalize_reel_url(ig_url)
        self.assertIsNotNone(res_ig)
        self.assertEqual(res_ig[0], "https://www.instagram.com/reel/C-xyz123")
        self.assertEqual(res_ig[1], "instagram")

    @patch("tools.facebook_agent.dm_crawl.crawler.resolve_short_url")
    def test_extract_reels_from_text(self, mock_resolve):
        mock_resolve.return_value = "https://www.facebook.com/reel/1963371435020478/?fs=e"
        msg = "Hey save this: https://www.facebook.com/share/v/1GzxfoVanT/?mibextid=wwXIfr thanks!"
        found = extract_reels_from_text(msg)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["url"], "https://www.facebook.com/reel/1963371435020478")
        self.assertEqual(found[0]["platform"], "facebook")

    @patch("tools.app.backend.services.dm_service.tx")
    @patch("tools.app.backend.services.dm_service.ro")
    def test_user_mapping_flow(self, mock_ro, mock_tx):
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__.return_value = mock_conn
        mock_ro.return_value.__enter__.return_value = mock_conn

        # Test link user
        link_psid_to_user("psid_999", "test_user_123", "Test User")
        self.assertTrue(mock_conn.execute.called)

        # Test find user
        mock_conn.execute.return_value.fetchone.return_value = ("test_user_123",)
        user = find_user_by_psid("psid_999")
        self.assertEqual(user, "test_user_123")

    def test_save_token_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Test resolving directory to .env
            env_file = resolve_env_path(tmpdir)
            self.assertEqual(env_file, (Path(tmpdir) / ".env").resolve())

            # 2. Test saving token to custom directory
            saved = save_token_to_env("test_token_123", "987654", env_path=env_file)
            self.assertTrue(saved.exists())
            content = saved.read_text()
            self.assertIn("PAGE_ID=987654", content)
            self.assertIn("FACEBOOK_ACCESS_TOKEN=test_token_123", content)

            # 3. Test update in place
            save_token_to_env("updated_token_456", "987654", env_path=saved)
            updated_content = saved.read_text()
            self.assertIn("FACEBOOK_ACCESS_TOKEN=updated_token_456", updated_content)
            self.assertNotIn("test_token_123", updated_content)

    @patch("tools.app.backend.services.get_page_token.get_page_access_token")
    @patch("tools.app.backend.services.get_page_token.debug_token_expiry")
    def test_check_and_renew_token(self, mock_debug, mock_get_token):
        mock_debug.return_value = {"expires_at": 0}
        mock_get_token.return_value = {
            "page_access_token": "renewed_token_789",
            "expires_at": "1899999999",
        }

        service = DmPollerService(page_id="123", access_token="old_token", renew_interval_sec=50 * 86400)

        # 1. Immediate call should not renew
        self.assertFalse(service.check_and_renew_token())
        self.assertEqual(service.access_token, "old_token")

        # 2. Advance time beyond 50 days
        service.last_renewed_at = service.last_renewed_at - (51 * 86400)
        renewed = service.check_and_renew_token()
        self.assertTrue(renewed)
        self.assertEqual(service.access_token, "renewed_token_789")

    @patch("tools.app.backend.services.get_page_token.graph_get")
    def test_exchange_token_dynamic_expires_in(self, mock_graph):
        # 1. Test when Meta returns dynamic expires_in
        mock_graph.return_value = {"access_token": "token_abc", "expires_in": 5139463}
        token, expires_in = exchange_long_lived_user_token("user_tok", "app_1", "sec_1")
        self.assertEqual(token, "token_abc")
        self.assertEqual(expires_in, 5139463)

        # 2. Test when Meta omits expires_in (never-expiring token)
        mock_graph.return_value = {"access_token": "token_xyz"}
        token2, expires_in2 = exchange_long_lived_user_token("user_tok", "app_1", "sec_1")
        self.assertEqual(token2, "token_xyz")
        self.assertIsNone(expires_in2)


if __name__ == "__main__":
    unittest.main()
