#!/bin/bash
# ==============================================================================
# All-In-One Markdown to PDF Converter with High-Contrast Mermaid Support
# Portable / Single-File: Copy this script to any project and run!
#
# Usage:
#   ./md-to-pdf.sh filename.md          # Convert a single file
#   ./md-to-pdf.sh /path/to/folder       # Convert all .md files in a folder
#   ./md-to-pdf.sh                       # Convert all .md files in current dir
#
# Prerequisites:
#   - pandoc       (brew install pandoc)
#   - xelatex      (brew install --cask mactex-no-gui or basictex)
#   - mmdc         (npm install -g @mermaid-js/mermaid-cli)
#   - python3      (macOS built-in or brew install python3)
# ==============================================================================

set -eo pipefail

# 1. Environment and PATH auto-detection (macOS Homebrew & TeX paths)
for p in "/opt/homebrew/bin" "/usr/local/bin" "/Library/TeX/texbin" "$HOME/.npm-global/bin"; do
    if [ -d "$p" ] && [[ ":$PATH:" != *":$p:"* ]]; then
        export PATH="$p:$PATH"
    fi
done

# 2. Dependency Checks
check_cmd() {
    local cmd="$1"
    local install_tip="$2"
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: '$cmd' is not installed or not in PATH." >&2
        echo "Tip: $install_tip" >&2
        exit 1
    fi
}

check_cmd "pandoc" "Install via: brew install pandoc"
check_cmd "xelatex" "Install via: brew install --cask basictex (or MacTeX)"
check_cmd "python3" "Install via: brew install python3"

# Note: mmdc is optional if file has no mermaid diagrams, but checked if present
MMDC_PATH=$(command -v mmdc || true)

# 3. Create self-cleaning temporary directory
TEMP_DIR=$(mktemp -d -t md_to_pdf_XXXXXX)
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# 4. Embed High-Contrast Mermaid Stylesheet
cat << 'EOF_CSS' > "$TEMP_DIR/mermaid-style.css"
/* High-Contrast, Clean Professional Styling for Mermaid Diagrams */
.node rect, .node circle, .node ellipse, .node polygon, .node path {
  fill: #FFFFFF !important;
  stroke: #1E40AF !important;
  stroke-width: 2px !important;
}

.node .label, .node text, span.nodeLabel, .label text, .mindmap-node text {
  fill: #000000 !important;
  color: #000000 !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  font-family: Arial, Helvetica, sans-serif !important;
}

.mindmap-node rect, .mindmap-node circle {
  stroke: #1E40AF !important;
  stroke-width: 2px !important;
  fill: #FFFFFF !important;
}

.mindmap-node text {
  fill: #000000 !important;
  color: #000000 !important;
  font-weight: 700 !important;
}

.edgeLabel, .edgeLabel span {
  background-color: #FFFFFF !important;
  color: #000000 !important;
  font-weight: 700 !important;
  font-size: 13px !important;
  padding: 3px 6px !important;
}

.edgePath path, .edge-thickness-normal {
  stroke: #1E293B !important;
  stroke-width: 2px !important;
}

marker path {
  fill: #1E293B !important;
  stroke: #1E293B !important;
}
EOF_CSS

# 5. Embed Python Mermaid Preprocessor
cat << 'EOF_PY' > "$TEMP_DIR/preprocess_mermaid.py"
#!/usr/bin/env python3
import sys
import os
import subprocess
import re

def main():
    if len(sys.argv) < 4:
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    temp_dir = sys.argv[3]
    css_file = os.path.join(temp_dir, "mermaid-style.css")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    content = content.replace('\r\n', '\n')
    pattern = re.compile(r'```\s*mermaid\s*\n(.*?)\n```[ \t]*', re.DOTALL)
    
    mmdc_path = "mmdc"
    for candidate in ["mmdc", "/opt/homebrew/bin/mmdc", "/usr/local/bin/mmdc"]:
        if subprocess.call(["which", candidate], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            mmdc_path = candidate
            break
            
    diagram_counter = 0
    
    def replace_mermaid(match):
        nonlocal diagram_counter
        diagram_counter += 1
        diagram_code = match.group(1)
        
        mmd_file = os.path.join(temp_dir, f"diagram_{diagram_counter}.mmd")
        pdf_file = os.path.join(temp_dir, f"diagram_{diagram_counter}.pdf")
        
        with open(mmd_file, 'w', encoding='utf-8') as df:
            df.write(diagram_code)
            
        print(f"  [Mermaid] Compiling diagram {diagram_counter}...", file=sys.stderr)
        try:
            cmd = [mmdc_path, "-i", mmd_file, "-o", pdf_file, "-f"]
            if os.path.exists(css_file):
                cmd.extend(["-C", css_file])
                
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                print(f"  [Mermaid] Successfully compiled diagram {diagram_counter} to PDF.", file=sys.stderr)
                return f"\n![Mermaid Diagram {diagram_counter}]({pdf_file})\n"
            else:
                print(f"  [Warning] Failed compiling diagram {diagram_counter}: {res.stderr}", file=sys.stderr)
                return match.group(0)
        except Exception as e:
            print(f"  [Warning] Error invoking mmdc: {e}", file=sys.stderr)
            return match.group(0)
            
    processed_content = pattern.sub(replace_mermaid, content)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(processed_content)

if __name__ == '__main__':
    main()
EOF_PY

# 6. Core Conversion Function
convert_file() {
    local file="$1"
    local output_dir="$2"
    local filename=$(basename "$file" .md)
    local output_pdf="$output_dir/$filename.pdf"
    
    echo "=================================================="
    echo "Converting: $(basename "$file") -> ${filename}.pdf"
    
    # Preprocess mermaid diagrams
    local temp_md="$TEMP_DIR/processed_${filename}.md"
    python3 "$TEMP_DIR/preprocess_mermaid.py" "$file" "$temp_md" "$TEMP_DIR"
    
    pandoc "$temp_md" \
        -o "$output_pdf" \
        --pdf-engine=xelatex \
        -V mainfont="Arial" \
        -V geometry:margin=1in \
        -V colorlinks=true \
        -V linkcolor=blue \
        -V header-includes="\usepackage{float} \floatplacement{figure}{H}"
        
    if [ $? -eq 0 ]; then
        echo "✓ Success: $output_pdf"
    else
        echo "✗ Failed to convert: $file" >&2
    fi
}

# 7. Argument Processing
TARGET="${1:-.}"

if [ -f "$TARGET" ]; then
    if [[ "$TARGET" != *.md ]]; then
        echo "Error: '$TARGET' is not a Markdown (.md) file." >&2
        exit 1
    fi
    convert_file "$TARGET" "$(dirname "$TARGET")"
elif [ -d "$TARGET" ]; then
    echo "Scanning directory '$TARGET' for Markdown (.md) files..."
    found=0
    while IFS= read -r -d '' file; do
        found=1
        convert_file "$file" "$(dirname "$file")"
    done < <(find "$TARGET" -maxdepth 1 -name "*.md" -print0)
    
    if [ "$found" -eq 0 ]; then
        echo "No .md files found in '$TARGET'."
    fi
else
    echo "Error: Target '$TARGET' does not exist or is not a valid file/directory." >&2
    exit 1
fi

echo "=================================================="
echo "Done!"
