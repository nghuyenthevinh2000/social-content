import unittest

from tools.facebook_agent.dm_crawl.crawler import canonicalize_reel_url, extract_reels_from_text


class DmCrawlTests(unittest.TestCase):
    def test_canonicalize_facebook_reel(self):
        url = 'https://www.facebook.com/reel/1234567890?s=yWDuG2&fs=e'
        res = canonicalize_reel_url(url)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'https://www.facebook.com/reel/1234567890')
        self.assertEqual(res[1], 'facebook')

    def test_canonicalize_facebook_share_video(self):
        url = 'https://www.facebook.com/share/v/1GzxfoVanT/?mibextid=wwXIfr'
        res = canonicalize_reel_url(url)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'https://www.facebook.com/share/v/1GzxfoVanT')
        self.assertEqual(res[1], 'facebook')

    def test_canonicalize_instagram_reel(self):
        url = 'https://www.instagram.com/reel/C-xyz123/?igsh=MWQ='
        res = canonicalize_reel_url(url)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'https://www.instagram.com/reel/C-xyz123')
        self.assertEqual(res[1], 'instagram')

    def test_canonicalize_tiktok(self):
        url = 'https://www.tiktok.com/@creator/video/9876543210?is_from_webapp=1'
        res = canonicalize_reel_url(url)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'https://www.tiktok.com/@creator/video/9876543210')
        self.assertEqual(res[1], 'tiktok')

    def test_extract_reels_from_text(self):
        text = "Check this: https://www.facebook.com/share/v/1GzxfoVanT/?mibextid=wwXIfr and https://www.instagram.com/reel/AA99BB!"
        extracted = extract_reels_from_text(text)
        self.assertEqual(len(extracted), 2)
        urls = [item['url'] for item in extracted]
        self.assertIn('https://www.facebook.com/share/v/1GzxfoVanT', urls)
        self.assertIn('https://www.instagram.com/reel/AA99BB', urls)


if __name__ == '__main__':
    unittest.main()
