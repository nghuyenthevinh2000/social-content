"""Unified campaign validator combining file structure, channel isolation, and hook alignment.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from .hooks import find_database, load_canonical_hooks, resolve_hypothesis_file, validate_hypotheses
from .structure import check_project_structure


def validate_campaign(root: Path | str, db_path: Path | str | None = None) -> tuple[bool, dict]:
    """Execute complete campaign health check for a project."""
    root_path = Path(root).expanduser().resolve()

    # 1. Check file structure, brand, marketing, and channel isolation
    struct_ok, struct_report = check_project_structure(root_path)

    # 2. Check hook alignment
    database_file = Path(db_path) if db_path else find_database(root_path)
    hooks_ok = True
    hooks_report = {}

    if not database_file or not database_file.is_file():
        struct_report["warnings"].append("content-hooks.md database not found; skipping hook alignment checks.")
        hooks_ok = True
    else:
        try:
            valid_ids, slug_to_id, id_to_name = load_canonical_hooks(database_file)
            hypo_path = resolve_hypothesis_file(None, root_path)
            hooks_ok, hooks_report = validate_hypotheses(hypo_path, valid_ids, slug_to_id, id_to_name)
            if not hooks_ok:
                for p in hooks_report.get("posts", []):
                    if not p.get("valid"):
                        struct_report["errors"].append(f"posts/hypothesis.json post {p.get('post')}: {p.get('error')}")
        except Exception as exc:
            hooks_ok = False
            struct_report["errors"].append(f"Hook validation error: {exc}")

    overall_ok = struct_ok and hooks_ok

    combined_report = {
        "ok": overall_ok,
        "project": str(root_path),
        "summary": {
            "structure_ok": struct_ok,
            "hooks_ok": hooks_ok,
            "total_errors": len(struct_report["errors"]),
            "total_warnings": len(struct_report["warnings"]),
        },
        "structure": struct_report["checks"],
        "hooks": hooks_report,
        "errors": struct_report["errors"],
        "warnings": struct_report["warnings"],
    }
    return overall_ok, combined_report


def print_campaign_summary(report: dict):
    """Pretty-print human-friendly terminal report."""
    status = "PASSED" if report["ok"] else "FAILED"
    print("=" * 60)
    print(f"CAMPAIGN VALIDATION: {status}")
    print(f"Project: {report['project']}")
    print(f"Errors: {report['summary']['total_errors']} | Warnings: {report['summary']['total_warnings']}")
    print("-" * 60)

    # Print section statuses
    print("Component Health Checks:")
    struct = report.get("structure", {})
    for section, data in struct.items():
        sec_status = "PASS" if data.get("ok") else "FAIL"
        print(f"  • {section.replace('_', ' ').title():<20}: [{sec_status}]")

    hooks = report.get("hooks", {})
    if hooks:
        h_status = "PASS" if hooks.get("ok") else "FAIL"
        print(f"  • {'Hook Alignment':<20}: [{h_status}] ({hooks.get('valid_count', 0)}/{hooks.get('total_posts', 0)} posts valid)")

    if report.get("warnings"):
        print("\nWarnings:")
        for w in report["warnings"]:
            print(f"  [!] {w}")

    if not report["ok"]:
        print("\nErrors Detected:")
        for err in report["errors"]:
            print(f"  [X] {err}")
    print("=" * 60)
