"""Offline unit tests for TikTok + Instagram hashtag research engine."""

from pathlib import Path
import tempfile
import unittest

from tools.loop import viral_analyzer
from tools.loop.viral_analyzer import hashtag_research as hr


class TestHashtagResearch(unittest.TestCase):

    def test_strip_accents_and_normalize_tag(self):
        self.assertEqual(hr.strip_accents("Nhân viên BĐS đắt giá"), "Nhan vien BDS dat gia")
        self.assertEqual(hr.normalize_tag("#Thương_Hiệu Cá Nhân!"), "thuonghieucanhan")
        self.assertEqual(hr.normalize_tag("  #XâyKênh🌿 "), "xaykenh")

    def test_relevance_filters_tiktok_noise(self):
        seeds = ["thương hiệu cá nhân BĐS", "nhân viên BĐS xây kênh", "AI xây thương hiệu cá nhân"]
        for good in ("thuonghieucanhan", "thươnghiệucánhân", "xaykenhtiktok", "nhanvienbds", "xaykenhai"):
            self.assertGreater(hr.score_hashtag_relevance(good, seeds), 0, good)
        for noise in ("aycaaysinturan", "ianthony", "thuongcacbannhieu💗", "aithuongthicamonnhiu"):
            self.assertEqual(hr.score_hashtag_relevance(noise, seeds), 0, noise)

    def test_run_hashtag_research_merges_tiktok_and_instagram(self):
        def fake_glasser(provider, endpoint, version, payload, cache_dir, task_id=None):
            q = payload["keyword"]
            if "tiktok" in endpoint:
                return (
                    {
                        "data": {
                            "challenge_list": [
                                {"challenge_info": {"cha_name": "thuonghieucanhan", "view_count": 597240736, "user_count": 79090}},
                                {"challenge_info": {"cha_name": "xaykenhtiktok", "view_count": 15779721840, "user_count": 5572448}},
                                {"challenge_info": {"cha_name": "aycaaysinturan", "view_count": 1817142557, "user_count": 30947}},
                            ]
                        }
                    },
                    "glasser_api",
                    None,
                )
            return (
                {
                    "data": {
                        "items": [
                            {"name": "thuonghieucanhan", "media_count": 33064},
                            {"name": "xaykenhai", "media_count": 914},
                        ]
                    }
                },
                "cache" if q == "xaykenh" else "glasser_api",
                None,
            )

        with tempfile.TemporaryDirectory() as tmp:
            res = viral_analyzer.run_hashtag_research(
                "thương hiệu cá nhân BĐS, nhân viên BĐS xây kênh, AI xây thương hiệu cá nhân",
                run_dir=Path(tmp),
                extra_stems=["xaykenh"],
                glasser_fn=fake_glasser,
            )

        self.assertIsNone(res["error"])
        self.assertEqual(len(res["keywords"]), 3)
        self.assertNotIn("#aycaaysinturan", res["hashtag_list"])
        self.assertNotIn("#xaykenhai", res["hashtag_list"])
        self.assertIn("#thuonghieucanhan", res["hashtag_list"])
        merged = next(h for h in res["hashtags"] if h["normalized"] == "thuonghieucanhan")
        self.assertEqual(sorted(merged["platforms"]), ["instagram", "tiktok"])
        self.assertEqual(merged["tiktok_views"], 597240736)
        self.assertEqual(merged["instagram_posts"], 33064)
        self.assertEqual(merged["combined_views"], 597240736 + 33064)
        self.assertTrue(res["source_breakdown"]["glasser_api"])
        self.assertTrue(res["source_breakdown"]["cache"])

        with tempfile.TemporaryDirectory() as tmp2:
            unfiltered = viral_analyzer.run_hashtag_research(
                "thương hiệu cá nhân BĐS, nhân viên BĐS xây kênh, AI xây thương hiệu cá nhân",
                run_dir=Path(tmp2),
                extra_stems=["xaykenh"],
                min_views=0,
                glasser_fn=fake_glasser,
            )
        self.assertIn("#xaykenhai", unfiltered["hashtag_list"])

    def test_empty_keywords_and_glasser_error(self):
        empty = hr.run_hashtag_research("   ,  ")
        self.assertEqual(empty["hashtags"], [])
        self.assertTrue(empty["error"])

        def failing_glasser(*_args, **_kwargs):
            return None, None, RuntimeError("network down")

        err_res = hr.run_hashtag_research(["xây kênh"], glasser_fn=failing_glasser)
        self.assertEqual(err_res["hashtags"], [])
        self.assertTrue(err_res["errors"])
        self.assertIn("network down", err_res["error"])


if __name__ == "__main__":
    unittest.main()
