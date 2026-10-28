---
name: file-conversion
description: "Convert documents and files between formats, supporting bidirectional conversions including PDF to Markdown, Markdown to PDF, and HTML to vector PDF with custom canvas dimensions. The agent must confirm first which file conversion the user wants before proceeding."
metadata:
  tags: file-conversion, pdf-to-markdown, md-to-pdf, html-to-pdf, markitdown, pandoc, chromium, playwright, mermaid, document-parsing, ocr, markdown
---

# File Conversion Skill: PDF to Markdown, Markdown to PDF & HTML to PDF

This skill provides an end-to-end operational playbook for converting documents across formats. It features three primary pipelines:
1. **PDF to Markdown** (using Microsoft MarkItDown with layout reflow and artifact cleaning)
2. **Markdown to PDF** (using the bundled `scripts/md-to-pdf.py` with Pandoc, Chrome/Chromium, and high-contrast Mermaid diagram compilation)
3. **HTML to PDF** (using the bundled `scripts/html-to-pdf.py` with Playwright Chromium or Chrome CLI, supporting custom canvas dimensions, web font rendering, and full-bleed zero margins)

---

## ⚠️ Critical Rule: Always Confirm Conversion Intent First

Before executing any conversion command or writing output files, **the agent must confirm first which file conversion the user wants**.

1. **Clarify the Conversion Direction:**
   - PDF $\rightarrow$ Markdown (`.pdf` to `.md`)
   - Markdown $\rightarrow$ PDF (`.md` to `.pdf`)
   - Other format pairs (e.g., DOCX $\rightarrow$ MD, HTML $\rightarrow$ MD)
2. **Confirm Target File(s) & Scope:**
   - Single file vs. batch folder conversion.
   - Target output location (default: same directory as input).
3. **Verify Special Requirements (if applicable):**
   - For Markdown $\rightarrow$ PDF: Are there Mermaid diagrams to compile?
   - For PDF $\rightarrow$ Markdown: Does it need OCR for scanned pages?

*Note: If the user has already explicitly specified the exact source file, target format, and destination in their prompt, verify the details and proceed.*

---

## When to Use

Use this skill whenever asked to:
- Convert a PDF to Markdown (extract clean text, structure, headings, and tables).
- Convert Markdown files to high-quality PDFs with professional typography and rendered diagrams.
- Clean up extraction artifacts (hard line breaks, page headers/footers, form-feed `\x0c` characters).
- Batch-process documentation files in a repository.

---

## Pipeline 1: Markdown to PDF (via `md-to-pdf.py`)

For converting Markdown files into publication-ready PDFs, use the dedicated script included in this skill:

- **Script Path:** `.agents/skills/file-conversion/scripts/md-to-pdf.py`

### Features
- **High-Contrast Mermaid Preprocessing:** Automatically extracts embedded ```mermaid``` blocks, renders them to PNG via `@mermaid-js/mermaid-cli` (`mmdc`) with a custom stylesheet (`#1E40AF` border, white fill, dark text), and injects the compiled figures.
- **Engine:** Python standard library orchestrates `pandoc` HTML and Chrome/Chromium PDF printing (Arial font, 18mm margins, colored hyperlinks, Unicode and emoji font fallback).
- **Wide Tables:** Documents with tables of seven or more columns use A3 landscape pages; other documents use A4 portrait.
- **Batch or Single-File:** Converts a single `.md` file or an entire directory of `.md` files.

### Prerequisites Check
Before running, verify that the required tools exist on the system:
```bash
which pandoc
python3 --version
# Chrome on macOS is detected automatically; otherwise set CHROME_PATH.
test -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" || which chromium || which google-chrome
which mmdc || which /opt/homebrew/bin/mmdc || which /usr/local/bin/mmdc
```
*(Tip: On macOS, install missing tools via `brew install pandoc`, `brew install --cask google-chrome`, `npm install -g @mermaid-js/mermaid-cli`. `mmdc` is required only for Mermaid diagrams. No Python packages are needed.)*

### Usage Commands

Resolve the repository root and invoke the script:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
SCRIPT="$REPO_ROOT/.agents/skills/file-conversion/scripts/md-to-pdf.py"

# 1. Convert a single Markdown file (generates filename.pdf in the same folder)
python3 "$SCRIPT" "/path/to/document.md"

# 2. Convert all Markdown files in a directory
python3 "$SCRIPT" "/path/to/folder"

# 3. Convert all Markdown files in the current working directory
python3 "$SCRIPT"
```

---

## Pipeline 2: PDF to Markdown (via MarkItDown & Refinement)

```
[ PDF File ]
     │
     ▼
[ 1. Inspect & Classify ] ── Scanned? ──► [ OCR / Doc Intelligence ]
     │ (Digital Text)
     ▼
[ 2. Extract with markitdown / CLI ]
     │
     ▼
[ 3. Refine & Post-Process ]
     ├─ Restore paragraph flow (remove artificial line breaks)
     ├─ Preserve headings & typography hierarchy
     ├─ Format tables, lists, quotes
     └─ Strip page numbers & header/footer noise
     │
     ▼
[ 4. Verify & Deliver Output (.md) ]
```

### Step 1 — Inspection & Assessment
```bash
# 1. Check metadata and page count
pdfinfo "path/to/document.pdf"

# 2. Check if digital text exists or if file is scanned images
pdftotext "path/to/document.pdf" - | head -n 30
```
- **Digital text found:** Proceed to Step 2.
- **Empty or scanned:** Requires OCR (`markitdown -d` with Document Intelligence, or `ocrmypdf`).

### Step 2 — Extraction Tools

#### Method A: Microsoft MarkItDown (CLI Standard)
```bash
markitdown "input.pdf" -o "output.md"
```

Python API:
```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("path/to/input.pdf")
with open("output.md", "w", encoding="utf-8") as f:
    f.write(result.text_content)
```

#### Method B: Layout-Aware Structural Extraction
When raw extraction flattens section headers or splits words:
- `pdftohtml -c -s -noframes "input.pdf" scratch/doc.html` (inspect font sizes, weights, and header elements).
- `pdftotext -layout "input.pdf" scratch/doc_layout.txt` (verify tabular data and visual columns).

### Step 3 — Post-Processing Rules

1. **Reflow Artificial Line Breaks:** PDFs insert hard `\n` or `\n\n` at margins. Reflow sentences within the same paragraph into a single continuous block.
2. **Stitch Page Boundaries:** When text breaks across page margins (marked by `\x0c`), stitch words and sentences seamlessly.
3. **Establish Heading Levels:**
   - Document Title $\rightarrow$ `# Title` (H1)
   - Major Sections $\rightarrow$ `## Section Name` (H2)
   - Subsections $\rightarrow$ `### Subsection Name` (H3)
4. **Strip Header/Footer Clutter:** Remove recurring page numbers, timestamps, and running headers. Keep legitimate footnotes using `[^1]: Footnote text`.
5. **Format Tables & Lists:** Align tables with GitHub Flavored Markdown (GFM) pipe syntax and standardize bullet points to `- Item`.

### Step 4 — Verification & Delivery
1. Place output in the **same folder** as the input file unless specified otherwise.
2. Confirm UTF-8 character encoding (especially Vietnamese and non-Latin diacritics).
3. Return clickable file links: `[document.md](file:///absolute/path/to/document.md)`.

---

## Pipeline 3: HTML to Vector PDF (via `html-to-pdf.py`)

For converting HTML files (single pages, infographics, presentation slides, or reports) into vector PDFs with exact canvas dimensions and high-fidelity web font loading:

- **Script Path:** `.agents/skills/file-conversion/scripts/html-to-pdf.py`

### Features
- **Custom Canvas Sizing:** Supports exact width and height units (e.g., `--width 720px --height 1280px` for 9:16 portrait mobile infographics, or `1920px x 1080px` for 16:9 widescreen presentation decks).
- **Web Font & Asset Preloading:** Configurable wait period (`--wait <ms>`, default: 1000ms) to ensure Google Fonts (Instrument Serif, Plus Jakarta Sans, Inter, etc.) and CDN assets finish loading before vector generation.
- **Zero-Margin / Full-Bleed Layouts:** Defaults to `0px` margins to avoid page overflow and accidental blank pages.
- **Engine Support:** Uses Playwright Chromium if available in the virtual environment, with automatic fallback to headless system Chrome/Chromium CLI.

### Usage Commands

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
SCRIPT="$REPO_ROOT/.agents/skills/file-conversion/scripts/html-to-pdf.py"

# 1. Convert an infographic HTML to single-page 9:16 portrait PDF
python3 "$SCRIPT" "path/to/index.html" -o "path/to/output.pdf" --width 720px --height 1280px --wait 1000

# 2. Convert a presentation deck HTML to 16:9 widescreen PDF
python3 "$SCRIPT" "slides.html" --width 1920px --height 1080px

# 3. Convert all HTML files in a directory
python3 "$SCRIPT" "path/to/html-folder" --width 720px --height 1280px
```

---

## Supported Conversions Matrix

| Conversion | Primary Tool / Script | Fallback / Alternative | Notes |
| :--- | :--- | :--- | :--- |
| **HTML $\rightarrow$ PDF** | `scripts/html-to-pdf.py` | Headless Chrome CLI | Supports custom dimensions (e.g. 720x1280 9:16), zero margins, web fonts. |
| **Markdown $\rightarrow$ PDF** | `scripts/md-to-pdf.py` | `pandoc input.md -o output.pdf` | Supports high-contrast Mermaid diagrams, emoji, wide tables, Chrome/Chromium. |
| **PDF $\rightarrow$ Markdown** | `markitdown input.pdf -o output.md` | `pdftotext` / `pandoc` | Reflow wrapped lines and fix page boundaries. |
| **Word (`.docx`) $\rightarrow$ MD** | `markitdown input.docx -o output.md` | `pandoc -f docx -t markdown` | Preserves headings, bold, tables cleanly. |
| **HTML $\rightarrow$ MD** | `markitdown input.html -o output.md` | `markdownify` / `readability` | Strip navigation bars and scripts. |
| **PowerPoint (`.pptx`) $\rightarrow$ MD** | `markitdown input.pptx -o output.md` | `python-pptx` | Extracts slide titles and bullets. |
| **Excel (`.xlsx`, `.csv`) $\rightarrow$ MD** | `markitdown input.xlsx -o output.md` | `pandas.to_markdown()` | Formats tables cleanly. |

---

## Quick Reference Commands

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)

# Convert HTML to Vector PDF (Infographics / Slides)
python3 "$REPO_ROOT/.agents/skills/file-conversion/scripts/html-to-pdf.py" "index.html" -o "output.pdf" --width 720px --height 1280px

# Convert Markdown to PDF
python3 "$REPO_ROOT/.agents/skills/file-conversion/scripts/md-to-pdf.py" "document.md"

# Convert PDF to Markdown
markitdown "document.pdf" -o "document.md"
```
