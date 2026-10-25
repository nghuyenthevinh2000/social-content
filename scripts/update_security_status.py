#!/usr/bin/env python3
"""Updates README.md with unified security, supply chain, and prompt injection scan results."""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

START_MARKER = "<!-- SECURITY_STATUS_START -->"
END_MARKER = "<!-- SECURITY_STATUS_END -->"
LEGACY_MARKERS = [
    ("<!-- MALWARE_SCAN_START -->", "<!-- MALWARE_SCAN_END -->"),
]

TARGET_CONFIG = {
    "malware": {
        "title": "Repo Malware",
        "scanner": "ClamAV",
        "default_details": "Filesystem virus & trojan scan",
    },
    "supply-chain": {
        "title": "Supply Chain",
        "scanner": "GuardDog + uv & npm audit",
        "default_details": "PyPI & npm backdoors, scripts blocked, OSV",
    },
    "prompt-injection": {
        "title": "Prompt Injection",
        "scanner": "LLM Safety Guard",
        "default_details": "Instruction overrides, jailbreaks & token smuggling",
    },
}


def parse_clamscan_log(log_text: str) -> tuple[str, str]:
    """Extract status and details from ClamAV log text."""
    infected: int | None = None
    scanned_files: int | None = None
    engine_version: str = "ClamAV"

    for line in log_text.splitlines():
        if "Infected files:" in line:
            parts = line.split(":", 1)
            try:
                infected = int(parts[1].strip())
            except ValueError:
                pass
        elif "Scanned files:" in line:
            parts = line.split(":", 1)
            try:
                scanned_files = int(parts[1].strip())
            except ValueError:
                pass
        elif "Engine version:" in line:
            parts = line.split(":", 1)
            engine_version = parts[1].strip().split("/")[0].strip()

    if infected is None:
        status = "⚠️ Incomplete"
        details = "Log summary missing"
    elif infected == 0:
        status = "✅ Clean"
        details = f"{scanned_files or 0} files scanned, 0 threats (v{engine_version})"
    else:
        status = f"❌ {infected} threat(s)"
        details = f"{infected} infected file(s) detected!"

    return status, details


def format_status(val: str) -> str:
    """Format status string with emoji indicator."""
    v = val.strip()
    if v.lower() in ("passed", "clean", "ok"):
        return "✅ Clean"
    if "threat" in v.lower() or "fail" in v.lower() or "error" in v.lower():
        return f"❌ {v}"
    if "pending" in v.lower():
        return f"⏳ {v}"
    return v


def parse_existing_table(content: str) -> dict[str, dict[str, str]]:
    """Parse rows from existing markdown table between markers."""
    rows: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        f"{re.escape(START_MARKER)}(.*?){re.escape(END_MARKER)}", re.DOTALL
    )
    match = pattern.search(content)
    if not match:
        return rows

    block = match.group(1).strip()
    for line in block.splitlines():
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 5 and parts[0] != "Target" and not parts[0].startswith(":---"):
            target_raw = parts[0].replace("*", "").strip()
            # Match to canonical target key
            for key, conf in TARGET_CONFIG.items():
                if conf["title"].lower() in target_raw.lower() or key in target_raw.lower():
                    rows[key] = {
                        "title": conf["title"],
                        "scanner": parts[1],
                        "status": parts[2],
                        "last_scanned": parts[3],
                        "details": parts[4],
                    }
                    break
    return rows


def generate_security_table(rows: dict[str, dict[str, str]]) -> str:
    """Generate Markdown report table from row dictionary."""
    header = (
        f"{START_MARKER}\n"
        f"| Target | Scanner | Status | Last Scanned | Details |\n"
        f"| :--- | :--- | :--- | :--- | :--- |\n"
    )
    body_lines = []
    for key, conf in TARGET_CONFIG.items():
        row = rows.get(
            key,
            {
                "title": conf["title"],
                "scanner": conf["scanner"],
                "status": "⏳ Pending first CI run",
                "last_scanned": "-",
                "details": conf["default_details"],
            },
        )
        body_lines.append(
            f"| **{row['title']}** | {row['scanner']} | {row['status']} | {row['last_scanned']} | {row['details']} |"
        )
    return header + "\n".join(body_lines) + f"\n{END_MARKER}"


def update_readme_text(readme_content: str, new_table: str) -> str:
    """Replace content between markers in README text."""
    pattern = re.compile(
        f"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}", re.DOTALL
    )
    if pattern.search(readme_content):
        return pattern.sub(new_table, readme_content)

    for start_m, end_m in LEGACY_MARKERS:
        legacy_pat = re.compile(f"{re.escape(start_m)}.*?{re.escape(end_m)}", re.DOTALL)
        if legacy_pat.search(readme_content):
            return legacy_pat.sub(new_table, readme_content)

    raise ValueError(f"Markers {START_MARKER} and {END_MARKER} not found in README content.")


def run_self_tests() -> None:
    """Minimal assert checks."""
    sample_readme = f"""
    Title
    {START_MARKER}
    | Target | Scanner | Status | Last Scanned | Details |
    | :--- | :--- | :--- | :--- | :--- |
    | **Repo Malware** | ClamAV | ✅ Clean | 2026-10-25 09:00 UTC | 150 files |
    | **Supply Chain** | GuardDog + uv & npm audit | ⏳ Pending first CI run | - | Scan pending |
    | **Prompt Injection** | LLM Safety Guard | ⏳ Pending first CI run | - | Scan pending |
    {END_MARKER}
    Footer
    """
    rows = parse_existing_table(sample_readme)
    assert "malware" in rows
    assert rows["malware"]["status"] == "✅ Clean"

    # Update prompt-injection row
    rows["prompt-injection"] = {
        "title": "Prompt Injection",
        "scanner": "LLM Safety Guard",
        "status": format_status("Passed"),
        "last_scanned": "2026-10-25 10:30 UTC",
        "details": "771 files clean",
    }
    table = generate_security_table(rows)
    assert "771 files clean" in table
    assert "150 files" in table  # Preserved malware row!

    updated = update_readme_text(sample_readme, table)
    assert "771 files clean" in updated
    assert "Title" in updated
    assert "Footer" in updated
    print("All update_security_status self-tests passed!")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    parser.add_argument(
        "--target",
        choices=["malware", "supply-chain", "prompt-injection", "all"],
        help="Specific target to update",
    )
    parser.add_argument("--status", default="Passed", help="Status value")
    parser.add_argument("--details", help="Details text")
    parser.add_argument("--clamav-log", help="Path to ClamAV log file (for malware target)")
    parser.add_argument("--readme", default="README.md", help="Path to README.md")
    args = parser.parse_args()

    if args.test:
        run_self_tests()
        return 0

    readme_path = Path(args.readme)
    if not readme_path.exists():
        sys.stderr.write(f"Error: README file not found at {readme_path}\n")
        return 1

    readme_content = readme_path.read_text(encoding="utf-8")
    rows = parse_existing_table(readme_content)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if args.target == "malware":
        if args.clamav_log and Path(args.clamav_log).exists():
            status, details = parse_clamscan_log(Path(args.clamav_log).read_text(encoding="utf-8", errors="replace"))
        else:
            status = format_status(args.status)
            details = args.details or TARGET_CONFIG["malware"]["default_details"]
        rows["malware"] = {
            "title": TARGET_CONFIG["malware"]["title"],
            "scanner": TARGET_CONFIG["malware"]["scanner"],
            "status": status,
            "last_scanned": timestamp,
            "details": details,
        }
    elif args.target == "supply-chain":
        rows["supply-chain"] = {
            "title": TARGET_CONFIG["supply-chain"]["title"],
            "scanner": TARGET_CONFIG["supply-chain"]["scanner"],
            "status": format_status(args.status),
            "last_scanned": timestamp,
            "details": args.details or TARGET_CONFIG["supply-chain"]["default_details"],
        }
    elif args.target == "prompt-injection":
        rows["prompt-injection"] = {
            "title": TARGET_CONFIG["prompt-injection"]["title"],
            "scanner": TARGET_CONFIG["prompt-injection"]["scanner"],
            "status": format_status(args.status),
            "last_scanned": timestamp,
            "details": args.details or TARGET_CONFIG["prompt-injection"]["default_details"],
        }
    elif args.target == "all" or not args.target:
        for key, conf in TARGET_CONFIG.items():
            if key not in rows:
                rows[key] = {
                    "title": conf["title"],
                    "scanner": conf["scanner"],
                    "status": "⏳ Pending first CI run",
                    "last_scanned": "-",
                    "details": conf["default_details"],
                }

    new_table = generate_security_table(rows)
    try:
        updated = update_readme_text(readme_content, new_table)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    if updated != readme_content:
        readme_path.write_text(updated, encoding="utf-8")
        print(f"Updated {readme_path} with {args.target or 'all'} status.")
    else:
        print(f"No changes needed for {readme_path}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
