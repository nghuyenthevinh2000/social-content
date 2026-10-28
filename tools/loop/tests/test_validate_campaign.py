"""Unit tests for hook alignment validation between database and campaign hypotheses."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.loop import validate


SAMPLE_DB = """# Master Marketing Content Hooks Database

## 2. Master Hook Formula Database

| Hook ID & Canonical Slug | Core Psychological Driver | Plug-and-Play Template Formula | Cross-Niche Application Examples | Optimal Platform & Asset Format |
|---|---|---|---|---|
| **HK-01** (`contrarian-truth`)<br>Contrarian Truth | Challenging orthodoxy | "Unpopular opinion:..." | Examples | Formats |
| **HK-02** (`question-first`)<br>Question-First | Risk agitation | "If your team is..." | Examples | Formats |
| **HK-05** (`direct-consulting-teardown`)<br>Direct Consulting Teardown | Technical diagnosis | "We audited..." | Examples | Formats |
| **HK-06** (`lessons-from-models`)<br>Lessons From Models | Benchmark extraction | "What Hong Kong taught us..." | Examples | Formats |
"""


class ValidateHooksTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

        self.db_path = self.root / "content-hooks.md"
        self.db_path.write_text(SAMPLE_DB, encoding="utf-8")

        self.valid_ids, self.slug_to_id, self.id_to_name = (
            validate.load_canonical_hooks(self.db_path)
        )

    def test_load_canonical_hooks(self):
        self.assertIn("HK-01", self.valid_ids)
        self.assertIn("contrarian-truth", self.slug_to_id)
        self.assertIn("question-first", self.slug_to_id)
        self.assertIn("direct-consulting-teardown", self.slug_to_id)
        self.assertIn("lessons-from-models", self.slug_to_id)
        self.assertEqual(
            self.slug_to_id["direct-consulting-teardown"], "HK-05"
        )
        self.assertEqual(self.id_to_name["HK-05"], "Direct Consulting Teardown")

    def test_check_single_hook_exact_match(self):
        ok, err = validate.check_single_hook(
            "question-first", self.valid_ids, self.slug_to_id
        )
        self.assertTrue(ok)
        self.assertIsNone(err)

        ok_id, err_id = validate.check_single_hook(
            "HK-02", self.valid_ids, self.slug_to_id
        )
        self.assertTrue(ok_id)
        self.assertIsNone(err_id)

    def test_check_single_hook_rejects_aliases_and_unknown(self):
        for invalid in ["direct-teardown", "model-lessons", "unknown-type"]:
            ok, err = validate.check_single_hook(
                invalid, self.valid_ids, self.slug_to_id
            )
            self.assertFalse(ok)
            self.assertIn(f"Unrecognized hook.type '{invalid}'", err)

    def test_validate_hypotheses_file(self):
        hypo_file = self.root / "hypothesis.json"
        hypo_file.write_text(
            json.dumps(
                {
                    "hypotheses": [
                        {"post": 1, "hook": {"type": "question-first"}},
                        {
                            "post": 2,
                            "hook": {"type": "direct-consulting-teardown"},
                        },
                        {"post": 3, "hook": {"type": "direct-teardown"}},
                    ]
                }
            ),
            encoding="utf-8",
        )

        ok, report = validate.validate_hooks(
            hypo_file, self.valid_ids, self.slug_to_id, self.id_to_name
        )
        self.assertFalse(ok)
        self.assertEqual(report["total_posts"], 3)
        self.assertEqual(report["valid_count"], 2)
        self.assertEqual(report["error_count"], 1)
        self.assertFalse(report["posts"][2]["valid"])

    def test_validate_campaign_structure(self):
        # Create minimal valid project layout
        (self.root / "loop").mkdir(parents=True, exist_ok=True)
        (self.root / "brand").mkdir(parents=True, exist_ok=True)
        (self.root / "posts").mkdir(parents=True, exist_ok=True)

        (self.root / "AGENTS.md").write_text("# Project Policy", encoding="utf-8")
        (self.root / "loop/config.json").write_text(json.dumps({
            "page_id": "123",
            "allowed_channels": ["facebook_page"],
            "hypotheses_file": "posts/hypothesis.json",
            "content_policy": {
                "tokens_file": "brand/tokens.json",
                "guidelines_file": "brand/guidelines.md"
            }
        }), encoding="utf-8")
        (self.root / "product-marketing.json").write_text(json.dumps({
            "marketing_goal": "Goal",
            "product": {"catalog": [{"id": "1", "name": "Item"}]}
        }), encoding="utf-8")
        (self.root / "brand/tokens.json").write_text(json.dumps({
            "colors": {"canvas": "#FFF", "ink": "#000", "accent": "#F00"},
            "fonts": ["Inter"]
        }), encoding="utf-8")
        (self.root / "brand/guidelines.md").write_text("# Guidelines", encoding="utf-8")
        (self.root / "posts/hypothesis.json").write_text(json.dumps({
            "goal": "Goal",
            "hypotheses": [{"post": 1, "angle": "A", "hook": {"type": "question-first"}, "cta": "123"}]
        }), encoding="utf-8")

        ok, report = validate.validate_campaign(self.root, db_path=self.db_path)
        self.assertTrue(ok)
        self.assertEqual(report["summary"]["total_errors"], 0)


if __name__ == "__main__":
    unittest.main()
