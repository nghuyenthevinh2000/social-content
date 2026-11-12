"""CLI Entrypoint for Facebook Page DM Ingestion via Graph API."""

import sys
from .crawler import main

if __name__ == '__main__':
    sys.exit(main())
