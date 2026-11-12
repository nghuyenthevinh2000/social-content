import unittest
from unittest.mock import patch, MagicMock

from tools.app.backend.services.dm_service import (
    canonicalize_reel_url,
    extract_reels_from_text,
    create_link_code,
    check_and_apply_link_code,
    find_user_by_psid,
    link_psid_to_user,
    DmPollerService,
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

    def test_extract_reels_from_text(self):
        msg = "Hey save this: https://www.facebook.com/share/v/1GzxfoVanT/?mibextid=wwXIfr thanks!"
        found = extract_reels_from_text(msg)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["url"], "https://www.facebook.com/share/v/1GzxfoVanT")
        self.assertEqual(found[0]["platform"], "facebook")

    @patch("tools.app.backend.services.dm_service.tx")
    @patch("tools.app.backend.services.dm_service.ro")
    def test_link_code_flow(self, mock_ro, mock_tx):
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__.return_value = mock_conn
        mock_ro.return_value.__enter__.return_value = mock_conn

        # Test link code generation
        code = create_link_code("test_user_123")
        self.assertTrue(code.startswith("LINK-"))

        # Test code validation
        mock_conn.execute.return_value.fetchone.return_value = ("test_user_123",)
        user = check_and_apply_link_code(code, "psid_999", "Test User")
        self.assertEqual(user, "test_user_123")


if __name__ == "__main__":
    unittest.main()
