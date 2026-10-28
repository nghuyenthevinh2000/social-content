"""Validate hook alignment between content-hooks database and campaign hypotheses.

Strict exact matching against canonical database slugs only; zero aliases.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


def find_database(search_start: Path | None = None) -> Path | None:
    """Find the canonical content-hooks.md reference file."""
    candidates = []
    if search_start:
        p = Path(search_start).expanduser().resolve()
        candidates.extend([
            p / ".agents" / "skills" / "social-campaign" / "references" / "content-hooks.md",
            p.parent / ".agents" / "skills" / "social-campaign" / "references" / "content-hooks.md",
            p.parent.parent / ".agents" / "skills" / "social-campaign" / "references" / "content-hooks.md",
        ])

    here = Path(__file__).resolve()
    # tools/loop/validate/hooks.py -> repo_root = here.parents[3]
    repo_root = here.parents[3]
    candidates.append(repo_root / ".agents" / "skills" / "social-campaign" / "references" / "content-hooks.md")

    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def load_canonical_hooks(db_path: Path) -> tuple[set[str], dict[str, str], dict[str, str]]:
    """Parse content-hooks.md to extract valid Hook IDs, canonical slugs, and names."""
    if not db_path or not db_path.exists():
        raise FileNotFoundError(f"Hook database not found: {db_path}")

    text = db_path.read_text(encoding="utf-8")
    valid_ids: set[str] = set()
    slug_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}

    pattern = re.compile(r"\|\s*\*\*(HK-\d+)\*\*\s*\(`([a-z0-9-]+)`\)(?:<br>|\s+)([^|]+?)\s*\|")
    for match in pattern.finditer(text):
        hk_id = match.group(1).strip()
        slug = match.group(2).strip()
        name = match.group(3).strip()
        valid_ids.add(hk_id)
        slug_to_id[slug] = hk_id
        id_to_name[hk_id] = name

    if not slug_to_id:
        raise ValueError(f"No canonical hooks extracted from {db_path}")

    return valid_ids, slug_to_id, id_to_name


def check_single_hook(raw_type: str | None, valid_ids: set[str], slug_to_id: dict[str, str]) -> tuple[bool, str | None]:
    """Check a single hook.type for exact match against canonical database slugs or IDs."""
    if not raw_type:
        return False, "Missing hook.type."
    raw = str(raw_type).strip()
    if raw in slug_to_id or raw in valid_ids:
        return True, None
    valid_slugs = sorted(slug_to_id.keys())
    return False, f"Unrecognized hook.type '{raw}'. Valid canonical slugs: {valid_slugs}"


def resolve_hypothesis_file(target: str | None, project_dir: Path | str | None) -> Path | str:
    """Resolve hypothesis.json path from project slug or direct file path."""
    if target == "-":
        return "-"
    if target:
        path = Path(target)
        if path.is_file():
            return path
        if path.is_dir():
            cand = path / "posts" / "hypothesis.json"
            if cand.is_file():
                return cand

    if project_dir:
        p = Path(project_dir).expanduser().resolve()
        cfg_file = p / "loop" / "config.json"
        if cfg_file.is_file():
            try:
                cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                rel = cfg.get("hypotheses_file", "posts/hypothesis.json")
                cand = p / rel
                if cand.is_file():
                    return cand
            except Exception:
                pass
        cand = p / "posts" / "hypothesis.json"
        if cand.is_file():
            return cand

    default_path = Path("local/block-lc/posts/hypothesis.json")
    if default_path.is_file():
        return default_path

    raise FileNotFoundError("Could not resolve hypothesis.json. Specify --project or file path.")


def validate_hypotheses(
    hypo_path: Path | str,
    valid_ids: set[str],
    slug_to_id: dict[str, str],
    id_to_name: dict[str, str],
) -> tuple[bool, dict]:
    """Validate each post in hypothesis.json strictly against database without aliases."""
    if hypo_path == "-":
        content = json.loads(sys.stdin.read())
        source_name = "stdin"
    else:
        content = json.loads(Path(hypo_path).read_text(encoding="utf-8"))
        source_name = str(hypo_path)

    items = content.get("hypotheses", [])
    results = []
    has_errors = False
    distribution: dict[str, int] = {}

    for item in items:
        post_id = item.get("post")
        hook_obj = item.get("hook")

        if not isinstance(hook_obj, dict):
            results.append({"post": post_id, "valid": False, "error": "Missing 'hook' dictionary object"})
            has_errors = True
            continue

        raw_type = hook_obj.get("type")
        ok, err = check_single_hook(raw_type, valid_ids, slug_to_id)
        if not ok:
            results.append({"post": post_id, "valid": False, "type": raw_type, "error": err})
            has_errors = True
            continue

        raw_str = str(raw_type).strip()
        canonical_slug = raw_str if raw_str in slug_to_id else next(s for s, i in slug_to_id.items() if i == raw_str)
        hk_id = slug_to_id[canonical_slug]
        distribution[canonical_slug] = distribution.get(canonical_slug, 0) + 1
        results.append({
            "post": post_id,
            "valid": True,
            "type": canonical_slug,
            "id": hk_id,
            "category": id_to_name.get(hk_id, ""),
        })

    report = {
        "ok": not has_errors,
        "file": source_name,
        "total_posts": len(items),
        "valid_count": sum(1 for r in results if r.get("valid")),
        "error_count": sum(1 for r in results if not r.get("valid")),
        "distribution": distribution,
        "posts": results,
    }
    return not has_errors, report


def print_summary(report: dict, slug_to_id: dict[str, str], id_to_name: dict[str, str]):
    """Pretty print text validation summary."""
    status = "PASSED" if report["ok"] else "FAILED"
    print(f"Validation: {status}")
    print(f"File: {report['file']}")
    print(f"Posts: {report['total_posts']} total | {report['valid_count']} valid | {report['error_count']} errors")
    if report["distribution"]:
        print("Distribution by canonical hook type:")
        for slug, count in sorted(report["distribution"].items()):
            hk_id = slug_to_id.get(slug, "Unknown")
            name = id_to_name.get(hk_id, "")
            print(f"  • {slug} ({hk_id} - {name}): {count} posts")
    if not report["ok"]:
        print("\nErrors detected:")
        for r in report["posts"]:
            if not r.get("valid"):
                print(f"  - Post {r.get('post')}: {r.get('error')}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="Direct path to hypothesis.json or '-' for stdin")
    parser.add_argument("--project", "-p", help="Campaign directory (e.g., local/block-lc)")
    parser.add_argument("--database", "-d", help="Path to content-hooks.md")
    parser.add_argument("--json", action="store_true", help="Output raw JSON report")
    args = parser.parse_args(argv)

    db_path = Path(args.database) if args.database else find_database(Path(args.project) if args.project else None)
    if not db_path or not db_path.exists():
        print("Error: Could not locate content-hooks.md database.", file=sys.stderr)
        return 1

    try:
        valid_ids, slug_to_id, id_to_name = load_canonical_hooks(db_path)
    except Exception as exc:
        print(f"Error loading hook database: {exc}", file=sys.stderr)
        return 1

    try:
        hypo_path = resolve_hypothesis_file(args.target, args.project)
    except Exception as exc:
        print(f"Error resolving hypothesis file: {exc}", file=sys.stderr)
        return 1

    ok, report = validate_hypotheses(hypo_path, valid_ids, slug_to_id, id_to_name)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_summary(report, slug_to_id, id_to_name)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
