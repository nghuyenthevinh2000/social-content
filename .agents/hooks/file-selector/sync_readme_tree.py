#!/usr/bin/env python3
"""
Redirect wrapper for sync_directory_index.py.
The old README frontmatter system has been migrated to local/index.json and Repomix.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from sync_directory_index import sync_index

if __name__ == "__main__":
    print("ℹ️  Running directory index & Repomix sync (replaced legacy README frontmatter tree)...")
    sync_index()
