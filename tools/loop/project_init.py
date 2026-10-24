"""Bootstrap complete project scaffolding: loop, product catalog, hypotheses, and posts.

Standard library only.
"""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure repository root is in sys.path when script is executed directly
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.loop import storage

DEFAULT_SAMPLE_PATH = Path(__file__).parent / "samples" / "folder_structure.json"


def load_sample_structure(sample_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load folder structure sample JSON from file or default sample location."""
    target = Path(sample_path) if sample_path else DEFAULT_SAMPLE_PATH
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    return {}


DEFAULT_PRODUCT_CATALOG = {
    "marketing_goal": "Tìm kiếm đối tác phân phối và khách hàng thử nghiệm sản phẩm",
    "product": {
        "catalog": [
            {
                "id": "sample-item-1",
                "name": "Sản phẩm mẫu 1",
                "specification": "Quy cách / định lượng chuẩn",
                "applications": ["Ứng dụng 1", "Ứng dụng 2"],
                "image": "./sample_product.jpg"
            }
        ],
        "unique": {
            "origin": "Nguồn gốc xuất xứ rõ ràng",
            "feature": "Đặc tính kỹ thuật nổi bật",
            "positioning": "Định vị giải pháp cho xưởng sản xuất và đại lý",
            "claims_note": "Chỉ đưa ra cam kết chất lượng đã được kiểm chứng thực tế"
        }
    },
    "customer_profile": [
        {
            "persona": "Chủ xưởng / cơ sở sản xuất mục tiêu",
            "industry": "Gia công / sản xuất thành phẩm",
            "region": "Toàn quốc",
            "leads": []
        }
    ],
    "sales_information": {
        "phone": "0900000000",
        "minimum_order": "Đơn hàng tối thiểu",
        "bulk_orders_available": True
    }
}

DEFAULT_HYPOTHESIS = {
    "goal": "Tìm đối tác phân phối và khách hàng thử nghiệm, đo bằng cuộc hỏi phù hợp",
    "research": {
        "workflow": "Nguồn tham khảo → Giả thuyết sản phẩm → Thử mở đầu → Đo cuộc hỏi phù hợp"
    },
    "hypotheses": [
        {
            "post": 1,
            "status": "planned",
            "angle": "Giới thiệu danh mục sản phẩm theo nhu cầu sử dụng",
            "hook": {
                "opening": "Câu mở đầu nêu thẳng vấn đề hoặc nhu cầu của khách hàng mục tiêu?",
                "rationale": "Mở đầu trực tiếp để lọc đúng tệp khách có nhu cầu thực tế"
            },
            "hypothesis": "Nêu rõ chủng loại, ứng dụng và quy cách mua giúp khách nhận diện sản phẩm phù hợp và chủ động liên hệ.",
            "audience": "Khách hàng doanh nghiệp, xưởng sản xuất hoặc đại lý mục tiêu",
            "format": "Bài viết Facebook kèm hình ảnh/video sản phẩm",
            "cta": "Liên hệ số điện thoại để nhận báo giá hoặc đăng ký thử mẫu.",
            "primary_metric": "Số khách hàng phù hợp liên hệ hỏi giá hoặc đăng ký thử mẫu",
            "metrics": []
        }
    ]
}

DEFAULT_POST_TEMPLATE = """# Facebook post copy

TODO: Replace this scaffold with confirmed project copy before approval.

[Opening hook aimed at readers with the target need]

[Brand name] offers product lines that fit your needs:

1. [Product name 1] — [Primary use case]
2. [Product name 2] — [Primary use case]

📦 Purchase terms:
- Minimum order: [Minimum quantity]
- Delivery: Nationwide

📞 Contact [Phone number] for pricing or to discuss sample terms.

---

## Publishing notes
- Attach the image/video from this folder.
- Keep the confirmed phone number and delivery details unchanged.
- After publishing, record the canonical permalink and publish time in the loop registry.
"""

DEFAULT_POST_CONTENT = {
    "schema_version": 1,
    "channel": "facebook_page",
    "copy": "facebook-ad.md",
    "visual": {"source": "visual.svg", "image": "visual.png"},
    "groups": [],
}

DEFAULT_POST_RESEARCH_MD = """# Research & Evidence Dossier

## 1. Objective and Hypothesis
- **Objective**: Establish the verified evidence and source basis for the campaign message.
- **Hypothesis**: Concrete evidence increases trust and drives inquiry actions.

## 2. Primary References
- [Source 1 name]: Technical basis / applicable standard.
- [Source 2 name]: Empirical study / representative precedent.
"""

DEFAULT_POST_RESEARCH = {
    "schema_version": 1,
    "sources": [
        {
            "id": "source-1",
            "type": "primary_statute",
            "title": "TODO: verified official title",
            "url": "https://example.com/source-1",
            "jurisdiction": "VN",
            "checked_at": "2026-01-01",
            "effective_date": "2026-01-01",
            "provisions": ["TODO: exact article and clause"],
            "analysis": "TODO: applicability and interpretation",
        },
        {
            "id": "case-1",
            "type": "case_study",
            "title": "TODO: documented empirical case",
            "url": "https://example.com/case-1",
            "jurisdiction": "VN",
            "checked_at": "2026-01-01",
            "analysis": "TODO: observed facts, outcomes and limits",
        },
    ],
    "claims": [
        {
            "claim": "TODO: precise claim used in copy",
            "source_ids": ["source-1", "case-1"],
            "limitations": "TODO: jurisdiction, timing and applicability boundaries",
        }
    ],
}

DEFAULT_POST_VISUAL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" width="1200" height="675">
  <rect x="0" y="0" width="1200" height="675" fill="#FBFBF9"/>
  <line x1="60" y1="36" x2="1140" y2="36" stroke="#E7E5DE" stroke-width="1"/>
  <text x="60" y="70" font-family="JetBrains Mono" font-size="13" font-weight="600" fill="#C25E2E">CAMPAIGN TITLE — BRAND INTELLIGENCE</text>
  <text x="60" y="112" font-family="Instrument Serif" font-size="36" fill="#0F172A">Main Post Headline</text>
  <text x="60" y="140" font-family="Plus Jakarta Sans" font-size="14" fill="#64748B">Positioning message and verified evidence</text>

  <rect x="60" y="175" width="340" height="270" rx="8" fill="#FFFFFF" stroke="#E7E5DE" stroke-width="1"/>
  <rect x="80" y="195" width="210" height="26" rx="4" fill="#F4F3EE"/>
  <text x="90" y="213" font-family="JetBrains Mono" font-size="11" fill="#334155" font-weight="600">FEATURE / VALUE 1</text>
  <text x="80" y="270" font-family="Plus Jakarta Sans" font-size="34" font-weight="700" fill="#0F172A">01</text>
  <text x="135" y="266" font-family="Plus Jakarta Sans" font-size="13" fill="#64748B">Quality standard</text>
  <line x1="80" y1="290" x2="380" y2="290" stroke="#E7E5DE" stroke-width="1"/>
  <text x="80" y="320" font-family="Plus Jakarta Sans" font-size="13" fill="#334155" font-weight="600">↳ Primary use case:</text>
  <text x="80" y="340" font-family="Plus Jakarta Sans" font-size="12" fill="#64748B">Fits the customer's real needs</text>

  <rect x="430" y="175" width="340" height="270" rx="8" fill="#FDF3ED" stroke="#C25E2E" stroke-width="1"/>
  <rect x="450" y="195" width="220" height="26" rx="4" fill="#C25E2E"/>
  <text x="460" y="213" font-family="JetBrains Mono" font-size="11" fill="#FFFFFF" font-weight="600">COMPETITIVE EDGE</text>
  <text x="450" y="270" font-family="Plus Jakarta Sans" font-size="34" font-weight="700" fill="#C25E2E">02</text>
  <text x="545" y="266" font-family="Plus Jakarta Sans" font-size="13" fill="#334155">Clear differentiation</text>
  <line x1="450" y1="290" x2="750" y2="290" stroke="#E7E5DE" stroke-width="1"/>
  <text x="450" y="320" font-family="Plus Jakarta Sans" font-size="13" fill="#334155" font-weight="600">↳ Transparent sourcing:</text>
  <text x="450" y="340" font-family="Plus Jakarta Sans" font-size="12" fill="#64748B">Verifiable commitments</text>

  <rect x="800" y="175" width="340" height="270" rx="8" fill="#FFFFFF" stroke="#E7E5DE" stroke-width="1"/>
  <rect x="820" y="195" width="220" height="26" rx="4" fill="#F4F3EE"/>
  <text x="830" y="213" font-family="JetBrains Mono" font-size="11" fill="#334155" font-weight="600">SUPPLY TERMS</text>
  <text x="820" y="270" font-family="Plus Jakarta Sans" font-size="34" font-weight="700" fill="#0F172A">03</text>
  <text x="900" y="266" font-family="Plus Jakarta Sans" font-size="13" fill="#64748B">Nationwide</text>
  <line x1="820" y1="290" x2="1120" y2="290" stroke="#E7E5DE" stroke-width="1"/>
  <text x="820" y="320" font-family="Plus Jakarta Sans" font-size="13" fill="#334155" font-weight="600">↳ Customer support:</text>
  <text x="820" y="340" font-family="Plus Jakarta Sans" font-size="12" fill="#64748B">Advisory and delivery on schedule</text>

  <line x1="60" y1="605" x2="1140" y2="605" stroke="#E7E5DE" stroke-width="1"/>
  <text x="60" y="635" font-family="JetBrains Mono" font-size="12" fill="#64748B">CONTACT: [Phone / Hotline] | [Email]</text>
</svg>"""

# Post package files: the scaffold always creates these, independent of any sample.
DEFAULT_POST_FILES = {
    "facebook-ad.md": ("text", DEFAULT_POST_TEMPLATE),
    "content.json": ("json", DEFAULT_POST_CONTENT),
    "research.md": ("text", DEFAULT_POST_RESEARCH_MD),
    "research.json": ("json", DEFAULT_POST_RESEARCH),
    "visual.svg": ("text", DEFAULT_POST_VISUAL),
}


def validate_page_id(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError("page_id must be a string containing ASCII digits.")
    return value


def _render_sample_file(
    rel_path: str,
    spec: Dict[str, Any],
    root: Path,
    page_id: str,
    hypotheses_file: str,
    marketing_goal: Optional[str] = None,
) -> str:
    file_type = spec.get("type", "text")
    if file_type == "json":
        data = spec.get("content", {})
        if rel_path == "loop/config.json":
            cfg = dict(data)
            cfg["page_id"] = page_id
            cfg["hypotheses_file"] = hypotheses_file
            return json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
        if rel_path == "product-marketing.json":
            cat = dict(data)
            if marketing_goal:
                cat["marketing_goal"] = marketing_goal
            return json.dumps(cat, indent=2, ensure_ascii=False) + "\n"
        if rel_path == "loop/publications.json":
            return json.dumps({"schema_version": 2, "publications": [], "placements": []}, indent=2, ensure_ascii=False) + "\n"
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    # Text content
    text = spec.get("content", "")
    text = text.replace("{{PAGE_ID}}", page_id)
    text = text.replace("{{HYPOTHESES_FILE}}", hypotheses_file)
    text = text.replace("{{PROJECT_SLUG}}", root.name)
    project_name = root.name.replace("-", " ").title()
    text = text.replace("{{PROJECT_NAME}}", project_name)
    text = text.replace("{{CURRENT_DATE}}", date.today().isoformat())
    return text


def bootstrap_project(
    root: Path,
    page_id: str,
    *,
    hypotheses_file: str = "posts/hypothesis.json",
    marketing_goal: Optional[str] = None,
    sample_file: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Bootstrap complete project scaffold without overwriting existing files."""
    root = Path(root).resolve()
    validate_page_id(page_id)

    sample = load_sample_structure(sample_file)
    sample_dirs = sample.get("directories", [])
    if sample_dirs:
        dirs_to_create = [root / d for d in sample_dirs]
    else:
        dirs_to_create = [
            root / "loop",
            root / "loop/runs",
            root / "sources/post-metrics/exports",
            root / "sources/post-metrics/captures",
            root / "sources/post-metrics/normalized",
            root / "sources/viral",
            root / "posts",
            root / "posts/1",
            root / "brand",
            root / "brand/assets",
            root / "brand/preview",
            root / "brand-assets",
            root / "customer",
            root / "customer/leads",
            root / "customer/research",
        ]

    config_path = root / "loop/config.json"
    state_path = root / "loop/publications.json"
    catalog_path = root / "product-marketing.json"
    hypo_path = root / hypotheses_file
    post_1_path = root / "posts/1/facebook-ad.md"

    # Pre-flight config check
    if config_path.exists():
        existing_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        if existing_cfg.get("page_id") != page_id:
            raise ValueError(f"Project already configured with Page ID '{existing_cfg.get('page_id')}'; nothing changed.")

    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state.get("publications"), list):
            raise ValueError("Existing loop/publications.json is invalid; nothing changed.")

    sample_files = sample.get("files", {})
    files_plan = []
    file_renderers = {}

    if sample_files:
        for rel_str, spec in sample_files.items():
            actual_rel = hypotheses_file if rel_str == "posts/hypothesis.json" else rel_str
            target_path = root / actual_rel
            files_plan.append(target_path)
            file_renderers[target_path] = (lambda s=spec, r=rel_str: _render_sample_file(
                r, s, root, page_id, hypotheses_file, marketing_goal
            ))
    else:
        loop_readme = root / "loop/README.md"
        loop_agents = root / "loop/AGENTS.md"
        project_agents = root / "AGENTS.md"
        content_path = root / "posts/1/content.json"
        config = {
            "page_id": page_id,
            "hypotheses_file": hypotheses_file,
            "allowed_channels": ["facebook_page"],
            "content_policy": {"schema_version": 1},
        }
        files_plan = [
            config_path,
            state_path,
            loop_readme,
            loop_agents,
            project_agents,
            catalog_path,
            hypo_path,
            post_1_path,
            content_path,
        ]
        file_renderers = {
            config_path: lambda: json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            state_path: lambda: json.dumps({"schema_version": 2, "publications": [], "placements": []}, indent=2, ensure_ascii=False) + "\n",
            loop_readme: lambda: f"# Loop Configuration for Page {page_id}\n\n## Defined Business Outcomes\n- Qualified inquiries: [Define qualified inquiry criteria]\n- Target buyer role: [Define target buyer persona]\n- Conversion action: [Define expected next step]\n\n## Orchestrator Commands\nSee `tools/loop/README.md` for orchestrator reference.\n",
            loop_agents: lambda: "# Loop Agent Safeguards\n\n- Do not publish automatically without explicit human approval.\n- Do not prune groups without at least 3 comparable rounds.\n- Never treat pending moderation posts as failures.\n",
            project_agents: lambda: "# Campaign instructions\n\n```text\nPolicy → research → draft → visual → approval → publish → register\n```\n\n| Scope | Rule |\n|---|---|\n| Routing | Load social-campaign; read loop/config.json and existing project/brand facts before drafting. |\n| Channels | Use only allowed_channels in loop/config.json; cross-platform work is opt-in. |\n| Content | Select exact copy/media in posts/<id>/content.json; use .agents/skills/social-campaign/references/content-gates.md from repository root. |\n| Approval | Run preflight; record approve-content only after explicit human approval of the current assets. |\n| Publication | Pass --project and --post to facebook_agent; verify configured Page identity. Never retry uncertain submission. |\n| Measurement | Read loop/AGENTS.md; register the confirmed URL after publication. |\n",
            catalog_path: lambda: json.dumps({**DEFAULT_PRODUCT_CATALOG, **({"marketing_goal": marketing_goal} if marketing_goal else {})}, indent=2, ensure_ascii=False) + "\n",
            hypo_path: lambda: json.dumps(DEFAULT_HYPOTHESIS, indent=2, ensure_ascii=False) + "\n",
            post_1_path: lambda: DEFAULT_POST_TEMPLATE,
            content_path: lambda: json.dumps(DEFAULT_POST_CONTENT, indent=2, ensure_ascii=False) + "\n",
        }

    # Post package files are built-in defaults: samples describe posts/1, not its contents.
    for name, (kind, content) in DEFAULT_POST_FILES.items():
        default_path = root / "posts/1" / name
        if default_path in file_renderers:
            continue
        files_plan.append(default_path)
        if kind == "json":
            file_renderers[default_path] = lambda c=content: json.dumps(c, indent=2, ensure_ascii=False) + "\n"
        else:
            file_renderers[default_path] = lambda c=content: c

    if dry_run:
        return {
            "dry_run": True,
            "project_root": str(root),
            "page_id": page_id,
            "would_create_directories": [str(d.relative_to(root)) for d in dirs_to_create if not d.exists()],
            "would_create_files": [str(f.relative_to(root)) for f in files_plan if not f.exists()],
            "schema_version": 2,
        }

    # Execute directory creation
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)

    # Write files atomically if missing
    for target_path, renderer in file_renderers.items():
        if not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(renderer(), encoding="utf-8")

    return {
        "status": "initialized",
        "schema_version": 2,
        "page_id": page_id,
        "directories_created": len([d for d in dirs_to_create if d.exists()]),
        "config": str(config_path.relative_to(root)),
        "registry": str(state_path.relative_to(root)),
        "product_catalog": str(catalog_path.relative_to(root)),
        "hypotheses": str(hypo_path.relative_to(root)),
        "first_post": str(post_1_path.relative_to(root)),
    }


def migrate(root, *, dry_run=False):
    """Migrate schema v1 publications.json to schema v2 with placement checkpoints."""
    root = Path(root).resolve()
    state_path = root / 'loop/publications.json'
    if not state_path.is_file():
        raise ValueError(f"State file {state_path} does not exist; cannot migrate.")

    config = storage.load_project(root)
    page_id = config['page_id']

    raw_bytes = state_path.read_bytes()
    state = json.loads(raw_bytes.decode('utf-8'))

    version = state.get('schema_version', 1)
    if version == 2:
        return {
            'status': 'already_migrated',
            'schema_version': 2,
            'publications': len(state.get('publications', [])),
            'placements': len(state.get('placements', [])),
        }
    if version != 1:
        raise ValueError(f"Unsupported schema version: {version}")

    backup_path = root / 'loop/publications.json.v1.bak'
    publications = state.get('publications', [])
    placements = []

    for pub in publications:
        pub_id = pub['id']
        placement_id = f"{pub_id}-orig"
        permalink = pub.get('url')
        published_at = pub.get('published_at')
        is_visible = bool(permalink and published_at)
        pub_time = storage.timestamp(published_at) if published_at else None

        due_24h = (pub_time + timedelta(hours=24)).isoformat() if pub_time else None
        due_7d = (pub_time + timedelta(days=7)).isoformat() if pub_time else None

        if pub.get('metrics_status') == 'collected':
            status_24h = 'collected'
            review_24h = pub.get('review_status', 'pending')
            selected_ref_24h = pub.get('receipt_file')
            attempts_24h = 1 if selected_ref_24h else 0
        elif pub.get('metrics_status') == 'needs_attention':
            status_24h = 'needs_attention'
            review_24h = pub.get('review_status', 'waiting_for_metrics')
            selected_ref_24h = pub.get('receipt_file')
            attempts_24h = 1 if selected_ref_24h else 0
        elif pub_time:
            status_24h = pub.get('metrics_status', 'pending')
            review_24h = pub.get('review_status', 'waiting_for_metrics')
            selected_ref_24h = None
            attempts_24h = 0
        else:
            status_24h = 'blocked'
            review_24h = 'waiting_for_metrics'
            selected_ref_24h = None
            attempts_24h = 0

        # Note: 7d checkpoint is never completed from a late 24h snapshot
        status_7d = 'pending' if pub_time else 'blocked'
        review_7d = 'waiting_for_metrics'
        selected_ref_7d = None
        attempts_7d = 0

        placements.append({
            'id': placement_id,
            'publication_id': pub_id,
            'kind': 'original_page',
            'page_id': page_id,
            'group_id': None,
            'copy_post_id': pub.get('post_id'),
            'permalink': permalink,
            'insights_url': pub.get('insights_url'),
            'visibility': 'visible' if is_visible else 'unknown',
            'submitted_at': published_at,
            'visible_at': published_at,
            'first_seen_at': published_at,
            'timestamp_confidence': 'exact' if published_at else 'unknown',
            'checkpoints': {
                '24h': {
                    'due_at': due_24h,
                    'status': status_24h,
                    'attempts': attempts_24h,
                    'selected_observation_ref': selected_ref_24h,
                    'review_status': review_24h,
                },
                '7d': {
                    'due_at': due_7d,
                    'status': status_7d,
                    'attempts': attempts_7d,
                    'selected_observation_ref': selected_ref_7d,
                    'review_status': review_7d,
                },
            },
        })
        pub.setdefault('creative_version', None)

    new_state = {
        'schema_version': 2,
        'publications': publications,
        'placements': placements,
    }

    if dry_run:
        return {
            'dry_run': True,
            'backup_path': str(backup_path),
            'target_path': str(state_path),
            'publications_count': len(publications),
            'placements_count': len(placements),
        }

    if not backup_path.exists():
        backup_path.write_bytes(raw_bytes)
    storage.save(state_path, new_state)

    return {
        'status': 'migrated',
        'schema_version': 2,
        'backup': str(backup_path),
        'publications': len(publications),
        'placements': len(placements),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="New project root directory")
    parser.add_argument("--page-id", required=True, help="Facebook Page ID (digits only)")
    parser.add_argument("--hypotheses-file", default="posts/hypothesis.json", help="Relative path for hypotheses JSON")
    parser.add_argument("--marketing-goal", help="Optional custom marketing goal string")
    parser.add_argument("--sample-file", type=Path, help="Optional path to custom folder structure sample JSON")
    parser.add_argument("--dry-run", action="store_true", help="Preview would-create paths without writing to disk")
    args = parser.parse_args(argv)

    result = bootstrap_project(
        args.project,
        args.page_id,
        hypotheses_file=args.hypotheses_file,
        marketing_goal=args.marketing_goal,
        sample_file=args.sample_file,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if __package__ is None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    main()
