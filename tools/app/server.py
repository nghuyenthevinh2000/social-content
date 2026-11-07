"""Backward-compatible entry point for tools.app.backend.server."""
from pathlib import Path
import sys

_WORKSPACE = Path(__file__).resolve().parents[2]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from tools.app.backend.server import *  # noqa: F401, F403
from tools.app.backend.server import main

if __name__ == "__main__":
    main()
