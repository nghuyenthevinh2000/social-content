#!/usr/bin/env python3
"""Convert HTML file(s) to high-fidelity vector PDF with custom canvas dimensions, font loading, and background printing.

Usage:
  python3 html-to-pdf.py <input.html> [-o output.pdf] [--width 720px] [--height 1280px] [--wait 1000]
  python3 html-to-pdf.py <folder> [--width 720px] [--height 1280px]

Features:
  - Custom canvas sizing: Supports px, pt, mm, in (e.g. 720px x 1280px for 9:16 portrait, 1920px x 1080px for 16:9).
  - Web font & asset wait: Configurable wait time (default 1000ms) to ensure Google Fonts and external resources render.
  - Zero-margin / Full-bleed: Configurable margins (defaults to 0px for infographics/slides).
  - Engine: Uses Playwright Chromium if available, with headless Google Chrome / Chromium CLI fallback.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time


def find_system_chrome():
    """Find installed Chrome/Chromium executable on macOS, Linux, or Windows."""
    candidates = [
        os.environ.get("CHROME_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def convert_with_playwright(html_file: Path, pdf_file: Path, width: str, height: str, wait_ms: int, margin: str):
    """Render HTML to vector PDF using Playwright Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # Parse viewport dimensions for browser canvas if in px
        vp_width, vp_height = 1280, 800
        if width and width.endswith("px"):
            try:
                vp_width = int(width[:-2])
            except ValueError:
                pass
        if height and height.endswith("px"):
            try:
                vp_height = int(height[:-2])
            except ValueError:
                pass

        page = browser.new_page(viewport={"width": vp_width, "height": vp_height})
        page.goto(html_file.resolve().as_uri())

        if wait_ms > 0:
            page.wait_for_timeout(wait_ms)

        pdf_kwargs = {
            "path": str(pdf_file),
            "print_background": True,
            "margin": {
                "top": margin,
                "right": margin,
                "bottom": margin,
                "left": margin,
            },
        }

        if width:
            pdf_kwargs["width"] = width
        if height:
            pdf_kwargs["height"] = height

        page.pdf(**pdf_kwargs)
        browser.close()


def convert_with_chrome_cli(chrome_path: str, html_file: Path, pdf_file: Path):
    """Fallback rendering using Chrome/Chromium headless CLI."""
    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_file.resolve()}",
        html_file.resolve().as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Chrome CLI print failed: {result.stderr}")


def convert_html_file(html_file: Path, output_file: Path = None, width: str = "720px", height: str = "1280px", wait_ms: int = 1000, margin: str = "0px") -> Path:
    """Convert a single HTML file to PDF."""
    if not html_file.exists():
        raise FileNotFoundError(f"Source file not found: {html_file}")

    if output_file is None:
        output_file = html_file.with_suffix(".pdf")

    # Prefer Playwright for precise dimensioning & font rendering
    try:
        convert_with_playwright(html_file, output_file, width, height, wait_ms, margin)
        engine = "Playwright Chromium"
    except ImportError:
        chrome_bin = find_system_chrome()
        if not chrome_bin:
            raise RuntimeError(
                "Neither python 'playwright' nor a system Chrome/Chromium executable was found. "
                "Install playwright (`pip install playwright && playwright install chromium`) "
                "or install Google Chrome."
            )
        convert_with_chrome_cli(chrome_bin, html_file, output_file)
        engine = f"Chrome CLI ({chrome_bin})"

    size_kb = output_file.stat().st_size / 1024
    print(f"✓ Converted: {html_file.name} ➔ {output_file.name} [{size_kb:.1f} KB] via {engine}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Convert HTML file(s) to vector PDF.")
    parser.add_argument("input", nargs="?", default=".", help="Path to an HTML file or folder containing HTML files (default: current directory).")
    parser.add_argument("-o", "--output", help="Output PDF file path (only valid when converting a single file).")
    parser.add_argument("--width", default="720px", help="Page width with unit (e.g., 720px, 1920px, 210mm). Default: 720px")
    parser.add_argument("--height", default="1280px", help="Page height with unit (e.g., 1280px, 1080px, 297mm). Default: 1280px")
    parser.add_argument("--wait", type=int, default=1000, help="Wait time in milliseconds for fonts and network resources (default: 1000).")
    parser.add_argument("--margin", default="0px", help="Margin for all 4 sides with unit (default: 0px for full-bleed).")

    args = parser.parse_args()
    input_path = Path(args.input).resolve()

    if input_path.is_file():
        if input_path.suffix.lower() not in [".html", ".htm"]:
            sys.exit(f"Error: Input file must be .html or .htm: {input_path}")
        out_path = Path(args.output).resolve() if args.output else None
        convert_html_file(input_path, out_path, args.width, args.height, args.wait, args.margin)
    elif input_path.is_dir():
        if args.output:
            sys.exit("Error: -o/--output cannot be used when converting a directory.")
        html_files = sorted(input_path.glob("*.html")) + sorted(input_path.glob("*.htm"))
        if not html_files:
            sys.exit(f"No .html files found in directory: {input_path}")
        print(f"Found {len(html_files)} HTML file(s) in {input_path}...")
        for f in html_files:
            convert_html_file(f, None, args.width, args.height, args.wait, args.margin)
    else:
        sys.exit(f"Error: Input path does not exist: {input_path}")


if __name__ == "__main__":
    main()
