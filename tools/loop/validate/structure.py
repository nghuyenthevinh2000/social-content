"""Check project file structure, configuration, brand tokens, and channel artifact alignment.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

SUPPORTED_CHANNELS = {
    "facebook_page": ("facebook*.md",),
    "facebook_profile": ("facebook*.md",),
    "linkedin": ("linkedin*.md",),
    "twitter": ("twitter*.md", "x-post*.md"),
}


def read_json_safe(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, f"File does not exist: {path.name}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"Invalid JSON in {path.name}: {exc}"


def check_project_structure(root: Path) -> tuple[bool, dict]:
    """Inspect complete project structure and return structured result."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, dict] = {}

    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        return False, {
            "ok": False,
            "error": f"Project directory does not exist: {root}",
            "errors": [f"Directory not found: {root}"],
            "warnings": [],
            "checks": {},
        }

    # 1. Config Check
    cfg_path = root / "loop" / "config.json"
    cfg, cfg_err = read_json_safe(cfg_path)
    if cfg_err:
        errors.append(f"loop/config.json: {cfg_err}")
        checks["config"] = {"ok": False, "error": cfg_err}
        cfg = {}
    else:
        cfg_checks = []
        page_id = cfg.get("page_id")
        if not page_id or not str(page_id).strip():
            errors.append("loop/config.json missing valid 'page_id'")
            cfg_checks.append("missing page_id")

        allowed_channels = cfg.get("allowed_channels")
        if not isinstance(allowed_channels, list) or not allowed_channels:
            errors.append("loop/config.json: 'allowed_channels' must be a non-empty list")
            cfg_checks.append("invalid allowed_channels")
        else:
            unsupported = [c for c in allowed_channels if c not in SUPPORTED_CHANNELS]
            if unsupported:
                errors.append(f"loop/config.json: unsupported channels in allowed_channels: {unsupported}")
                cfg_checks.append(f"unsupported channels: {unsupported}")

        policy = cfg.get("content_policy", {})
        if not isinstance(policy, dict):
            errors.append("loop/config.json: 'content_policy' must be an object")
            cfg_checks.append("invalid content_policy")

        checks["config"] = {
            "ok": not bool(cfg_checks),
            "page_id": page_id,
            "allowed_channels": allowed_channels,
            "details": cfg_checks or ["valid"],
        }

    # 2. Project Instruction Check (AGENTS.md)
    agents_path = root / "AGENTS.md"
    if not agents_path.is_file() or not agents_path.read_text(encoding="utf-8").strip():
        errors.append("Missing or empty root AGENTS.md instructions")
        checks["instructions"] = {"ok": False, "file": "AGENTS.md"}
    else:
        checks["instructions"] = {"ok": True, "file": "AGENTS.md"}

    # 3. Product Marketing Facts
    mktg_path = root / "product-marketing.json"
    mktg, mktg_err = read_json_safe(mktg_path)
    if mktg_err:
        errors.append(f"product-marketing.json: {mktg_err}")
        checks["marketing"] = {"ok": False, "error": mktg_err}
    else:
        mktg_errors = []
        if not mktg.get("marketing_goal") or not str(mktg["marketing_goal"]).strip():
            mktg_errors.append("missing non-empty 'marketing_goal'")
        catalog = mktg.get("product", {}).get("catalog") if isinstance(mktg.get("product"), dict) else None
        if not isinstance(catalog, list) or not catalog:
            mktg_errors.append("missing or empty 'product.catalog' list")
        if mktg_errors:
            errors.extend([f"product-marketing.json: {e}" for e in mktg_errors])
        checks["marketing"] = {
            "ok": not bool(mktg_errors),
            "catalog_count": len(catalog) if isinstance(catalog, list) else 0,
            "details": mktg_errors or ["valid"],
        }

    # 4. Brand System
    policy = cfg.get("content_policy", {}) if isinstance(cfg, dict) else {}
    tokens_rel = policy.get("tokens_file", "brand/tokens.json")
    tokens_path = root / tokens_rel
    tokens, tokens_err = read_json_safe(tokens_path)
    brand_checks = []
    if tokens_err:
        errors.append(f"{tokens_rel}: {tokens_err}")
        brand_checks.append(f"tokens error: {tokens_err}")
    else:
        colors = tokens.get("colors", {}) if isinstance(tokens, dict) else {}
        for req_color in ("canvas", "ink", "accent"):
            if not colors.get(req_color):
                errors.append(f"{tokens_rel}: missing required color token '{req_color}'")
                brand_checks.append(f"missing color: {req_color}")

    guide_rel = policy.get("guidelines_file", "brand/guidelines.md")
    guide_path = root / guide_rel
    if not guide_path.is_file() or not guide_path.read_text(encoding="utf-8").strip():
        errors.append(f"Missing or empty brand guidelines: {guide_rel}")
        brand_checks.append("missing guidelines")

    checks["brand"] = {"ok": not bool(brand_checks), "details": brand_checks or ["valid"]}

    # 5. Hypotheses & Post Matrix
    hypo_rel = cfg.get("hypotheses_file", "posts/hypothesis.json") if isinstance(cfg, dict) else "posts/hypothesis.json"
    hypo_path = root / hypo_rel
    hypo, hypo_err = read_json_safe(hypo_path)
    hypo_items = []
    post_map: dict[int, dict] = {}
    if hypo_err:
        errors.append(f"{hypo_rel}: {hypo_err}")
        checks["hypotheses"] = {"ok": False, "error": hypo_err}
    else:
        hypo_items = hypo.get("hypotheses", [])
        if not isinstance(hypo_items, list) or not hypo_items:
            errors.append(f"{hypo_rel}: missing or empty 'hypotheses' array")
            checks["hypotheses"] = {"ok": False, "error": "empty hypotheses"}
        else:
            required_cta = policy.get("required_cta", [])
            hypo_errors = []
            for item in hypo_items:
                pid = item.get("post")
                if pid is None:
                    hypo_errors.append("hypothesis entry missing 'post' number")
                    continue
                post_map[pid] = item
                if not item.get("angle"):
                    hypo_errors.append(f"post {pid}: missing 'angle'")
                if not item.get("hook"):
                    hypo_errors.append(f"post {pid}: missing 'hook'")
                cta_text = str(item.get("cta", ""))
                for req in required_cta:
                    if req not in cta_text:
                        warnings.append(f"post {pid}: CTA does not contain required contact '{req}'")

            if hypo_errors:
                errors.extend(hypo_errors)
            checks["hypotheses"] = {
                "ok": not bool(hypo_errors),
                "total_hypotheses": len(hypo_items),
                "details": hypo_errors or ["valid"],
            }

    # 6. Post Folders Alignment
    posts_dir = root / "posts"
    post_checks = []
    allowed_channels = cfg.get("allowed_channels", []) if isinstance(cfg, dict) else []
    forbidden_patterns = policy.get("forbidden_artifacts", []) if isinstance(policy, dict) else []

    if posts_dir.is_dir():
        for entry in sorted(posts_dir.iterdir()):
            if entry.is_dir() and entry.name.isdigit():
                pid = int(entry.name)
                if pid not in post_map:
                    warnings.append(f"Found orphaned post folder 'posts/{entry.name}' not in {hypo_rel}")

                # Check artifacts inside post directory
                for path in entry.rglob("*"):
                    if not path.is_file():
                        continue
                    # Check forbidden patterns
                    if any(fnmatch.fnmatch(path.name, pat) for pat in forbidden_patterns):
                        errors.append(f"posts/{pid}/{path.name}: forbidden artifact per policy")
                        post_checks.append(f"forbidden: posts/{pid}/{path.name}")
                    # Check channel isolation
                    for ch, patterns in SUPPORTED_CHANNELS.items():
                        if ch not in allowed_channels and any(fnmatch.fnmatch(path.name, pat) for pat in patterns):
                            # Ensure not shared pattern
                            shared = False
                            for ac in allowed_channels:
                                if any(fnmatch.fnmatch(path.name, p2) for p2 in SUPPORTED_CHANNELS.get(ac, ())):
                                    shared = True
                                    break
                            if not shared:
                                errors.append(f"posts/{pid}/{path.name}: unauthorized channel artifact for {ch}")
                                post_checks.append(f"unauthorized channel: posts/{pid}/{path.name}")

    checks["posts_directory"] = {
        "ok": not bool(post_checks),
        "post_folders_count": sum(1 for d in posts_dir.iterdir() if d.is_dir() and d.name.isdigit()) if posts_dir.is_dir() else 0,
        "details": post_checks or ["aligned"],
    }

    ok = len(errors) == 0
    return ok, {
        "ok": ok,
        "project": str(root),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
