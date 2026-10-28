"""Validation package for campaign file structure, policy, and hook alignment.
"""

from .campaign import print_campaign_summary, validate_campaign
from .hooks import (
    check_single_hook,
    find_database,
    load_canonical_hooks,
    print_summary as print_hooks_summary,
    resolve_hypothesis_file,
    validate_hypotheses as validate_hooks,
)
from .structure import check_project_structure

__all__ = [
    "validate_campaign",
    "print_campaign_summary",
    "validate_hooks",
    "print_hooks_summary",
    "check_single_hook",
    "find_database",
    "load_canonical_hooks",
    "resolve_hypothesis_file",
    "check_project_structure",
]
