#!/usr/bin/env python3
"""Run with python3; requires converter dependencies and Poppler tools."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

script = Path(__file__).with_name("md-to-pdf.py").resolve()

with tempfile.TemporaryDirectory(prefix="md-to-pdf-test-") as directory:
    root = Path(directory)
    # No blank line before lists: this must still produce separate list items.
    (root / "portrait.md").write_text(
        "# Unicode regression\n\n"
        "Emoji: 🚀 ✅ 🔥 👩🏽‍💻 🇻🇳 :smile:\n\n"
        "Tiếng Việt: kiểm tra chuyển đổi.\n\n"
        "Stages:\n1. First stage\n2. Second stage\n\n"
        "```\n[ Model ] ──> [ Creation ] ──> [ Loop ]\n```\n\n"
        "```mermaid\ngraph TD\n"
        '  A["HOOK VALIDATION LOOP"] --> B["Full diagram label"]\n```\n',
        encoding="utf-8",
    )
    (root / "wide.md").write_text(
        "# Wide table\n\n"
        "| " + " | ".join(f"Column {n}" for n in range(9)) + " |\n"
        "| " + " | ".join("---" for _ in range(9)) + " |\n"
        "| " + " | ".join(f"Readable platform {n}" for n in range(9)) + " |\n",
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(script), str(root)], check=True)
    text = subprocess.check_output(
        ["pdftotext", "-layout", str(root / "portrait.pdf"), "-"], text=True
    )
    for expected in ("🚀", "✅", "🔥", "Tiếng Việt", "kiểm tra chuyển đổi", "──>"):
        assert expected in text, (expected, text)
    assert ":smile:" not in text, text
    assert re.search(r"1\. First stage\s*\n\s*2\. Second stage", text), text
    for name, expected_size in (("portrait", "A4"), ("wide", "A3")):
        info = subprocess.check_output(["pdfinfo", str(root / f"{name}.pdf")], text=True)
        assert f"({expected_size})" in info, info
    wide_text = subprocess.check_output(
        ["pdftotext", "-layout", str(root / "wide.pdf"), "-"], text=True
    )
    assert "Readable platform 8" in wide_text, wide_text

    # A dependency failure must not replace a previously generated report.
    original = (root / "wide.pdf").read_bytes()
    failed = subprocess.run(
        [sys.executable, str(script), str(root / "wide.md")], capture_output=True, text=True,
        env={**os.environ, "CHROME_PATH": str(root / "missing-chrome")},
    )
    assert failed.returncode != 0 and "CHROME_PATH" in failed.stderr, failed
    assert (root / "wide.pdf").read_bytes() == original
    empty = root / "empty"
    empty.mkdir()
    result = subprocess.run([sys.executable, str(script)], cwd=empty, capture_output=True, text=True)
    assert result.returncode == 0 and "No .md files" in result.stdout, result

print("PASS: Unicode/emoji, lists, Mermaid, page sizes, default target, and failure safety")
