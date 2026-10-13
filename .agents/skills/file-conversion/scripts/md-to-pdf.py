#!/usr/bin/env python3
"""Convert a Markdown file or folder to PDF (defaults to the current folder).

Usage: python3 md-to-pdf.py [file.md | folder]
Requires Pandoc and Chrome/Chromium; Mermaid diagrams also require mmdc.
Set CHROME_PATH to override the browser executable. No Python packages needed.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser


MERMAID_CSS = """
.node rect, .node circle, .node ellipse, .node polygon, .node path,
.mindmap-node rect, .mindmap-node circle {
  fill: #FFFFFF !important; stroke: #1E40AF !important; stroke-width: 2px !important;
}
.node .label, .node text, span.nodeLabel, .label text, .mindmap-node text {
  fill: #000000 !important; color: #000000 !important;
}
.edgeLabel, .edgeLabel span {
  background-color: #FFFFFF !important; color: #000000 !important; padding: 3px 6px !important;
}
.edgePath path, .edge-thickness-normal { stroke: #1E293B !important; stroke-width: 2px !important; }
marker path { fill: #1E293B !important; stroke: #1E293B !important; }
"""

# Set fonts before Mermaid measures nodes; CSS font overrides clip labels.
MERMAID_CONFIG = """{"theme":"base","fontFamily":"Arial","themeVariables":{"fontFamily":"Arial","fontSize":"15px"},"flowchart":{"htmlLabels":false}}"""

PRINT_CSS = """
@page { size: A4; margin: 18mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
  font-size: 11pt; line-height: 1.5; color: #172033;
}
h1 { font-size: 25pt; line-height: 1.2; }
h2 { font-size: 18pt; }
h3 { font-size: 13pt; }
h1, h2, h3, h4 { break-after: avoid; }
p, li { orphans: 3; widows: 3; }
li, pre { break-inside: avoid; }
a { color: #1e40af; overflow-wrap: anywhere; }
table { width: 100%; border-collapse: collapse; font-size: 10pt; line-height: 1.4; margin: 1em 0; }
/* Ignore Pandoc's source-width colgroup percentages; let content size columns. */
col { width: auto !important; }
th, td { padding: 7pt; border: 1px solid #cbd5e1; vertical-align: top; hyphens: none; word-break: normal; }
th { background: #edf2f7; text-align: left; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
pre, code { font-family: "DejaVu Sans Mono", Menlo, Consolas, monospace; }
pre { font-size: 9pt; white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f6f8; padding: 10pt; }
img { max-width: 100%; height: auto; }
figure { margin: 1em 0; break-inside: avoid; }
figure img { max-height: 170mm; object-fit: contain; }
figcaption { font-size: 9pt; color: #526075; }
hr { border: 0; border-top: 1px solid #cbd5e1; margin: 1.5em 0; }
"""


class TableWidth(HTMLParser):
    def __init__(self):
        super().__init__()
        self.columns = 0
        self.widest = 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.columns = 0
        elif tag in ("th", "td"):
            self.columns += int(dict(attrs).get("colspan", 1))
            self.widest = max(self.widest, self.columns)


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} failed:\n{result.stderr or result.stdout}")
    return result


def preprocess_mermaid(content, temp):
    counter = 0

    def replace(match):
        nonlocal counter
        counter += 1
        mmdc = shutil.which("mmdc")
        if not mmdc:
            raise RuntimeError("Mermaid diagrams require mmdc (npm install -g @mermaid-js/mermaid-cli)")
        source = temp / f"diagram_{counter}.mmd"
        image = temp / f"diagram_{counter}.png"
        source.write_text(match.group(1), encoding="utf-8")
        print(f"  [Mermaid] Compiling diagram {counter}...", flush=True)
        run([mmdc, "-i", str(source), "-o", str(image), "-s", "2", "-b", "white",
             "-c", str(temp / "mermaid-config.json"), "-C", str(temp / "mermaid-style.css")])
        return f"\n![Mermaid Diagram {counter}]({image.as_uri()})\n"

    return re.sub(r"```\s*mermaid\s*\n(.*?)\n```[ \t]*", replace, content, flags=re.DOTALL)


def convert_file(source, pandoc, chrome):
    output = source.with_suffix(".pdf")
    print(f"Converting: {source.name} -> {output.name}", flush=True)
    with tempfile.TemporaryDirectory(prefix="md-to-pdf-") as directory:
        temp = Path(directory).resolve()
        for name, content in (("print.css", PRINT_CSS), ("mermaid-style.css", MERMAID_CSS),
                              ("mermaid-config.json", MERMAID_CONFIG)):
            (temp / name).write_text(content, encoding="utf-8")
        markdown = temp / "processed.md"
        markdown.write_text(preprocess_mermaid(source.read_text(encoding="utf-8"), temp), encoding="utf-8")
        html_path = temp / "report.html"
        run([pandoc, str(markdown), "--from=markdown+lists_without_preceding_blankline+emoji",
             "--to=html5", "--standalone", "--embed-resources",
             f"--resource-path={source.parent}{os.pathsep}{temp}",
             "--metadata", f"pagetitle={source.stem}", f"--css={temp / 'print.css'}",
             "-o", str(html_path)])

        html = html_path.read_text(encoding="utf-8")
        parser = TableWidth()
        parser.feed(html)
        # Wide matrices need real page width, not tiny fonts or split words.
        if parser.widest >= 7:
            html = html.replace("</head>", "<style>@page { size: A3 landscape; margin: 18mm; } "
                                "body > :not(table) { max-width: 1100px; }</style></head>")
            html_path.write_text(html, encoding="utf-8")

        pdf = temp / "output.pdf"
        result = run([chrome, "--headless", "--disable-gpu", f"--user-data-dir={temp / 'chrome-profile'}",
                      "--no-pdf-header-footer", f"--print-to-pdf={pdf}", "--timeout=30000",
                      "--virtual-time-budget=2000", html_path.as_uri()])
        if not pdf.is_file() or not pdf.stat().st_size:
            raise RuntimeError(f"Chrome did not generate a PDF.\n{result.stderr}")
        # Leave an existing report untouched if preprocessing or rendering fails.
        shutil.move(str(pdf), str(output))
    print(f"✓ Success: {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=".", type=Path)
    target = parser.parse_args().target.expanduser().resolve()
    if target.is_file():
        if target.suffix != ".md":
            raise RuntimeError(f"'{target}' is not a Markdown (.md) file.")
        files = [target]
    elif target.is_dir():
        files = sorted(path for path in target.glob("*.md") if path.is_file())
    else:
        raise RuntimeError(f"Target '{target}' does not exist or is not a file/directory.")
    if not files:
        print(f"No .md files found in '{target}'.")
        return

    for directory in ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".npm-global/bin")):
        if Path(directory).is_dir() and directory not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("Pandoc is required (brew install pandoc).")
    candidates = [os.environ["CHROME_PATH"]] if os.environ.get("CHROME_PATH") else [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "chromium", "chromium-browser", "google-chrome",
    ]
    chrome = next((path for candidate in candidates if (path := shutil.which(candidate))), None)
    if not chrome:
        raise RuntimeError("Install Chrome/Chromium or set CHROME_PATH to its executable.")
    for source in files:
        convert_file(source, pandoc, chrome)
    print("Done!")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
