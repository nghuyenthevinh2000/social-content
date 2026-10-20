"""Bootstrap complete project scaffolding: loop, product catalog, hypotheses, and posts.

Standard library only.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


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

DEFAULT_POST_TEMPLATE = """# Nội dung bài đăng Facebook (Bài 1)

[Câu mở đầu / hook trực diện hướng tới người có nhu cầu]

[Tên thương hiệu] giới thiệu các dòng sản phẩm phục vụ nhu cầu của bạn:

1. [Tên sản phẩm 1] — [Ứng dụng chính]
2. [Tên sản phẩm 2] — [Ứng dụng chính]

📦 Quy cách và điều kiện mua:
- Đơn hàng tối thiểu: [Số lượng tối thiểu]
- Giao hàng: Toàn quốc

📞 Liên hệ [Số điện thoại] để nhận báo giá hoặc trao đổi điều kiện thử mẫu!

---

## Ghi chú đăng bài
- Ảnh/video đính kèm trong thư mục này.
- Giữ nguyên số điện thoại và thông tin giao hàng đã xác nhận.
- Đăng xong cần ghi nhận canonical permalink và thời điểm đăng vào loop registry.
"""


def validate_page_id(value: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError("page_id must be a string containing ASCII digits.")
    return value


def bootstrap_project(
    root: Path,
    page_id: str,
    *,
    hypotheses_file: str = "posts/hypothesis.json",
    marketing_goal: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Bootstrap complete project scaffold without overwriting existing files."""
    root = Path(root).resolve()
    validate_page_id(page_id)

    # Directories
    dirs_to_create = [
        root / "loop",
        root / "loop/runs",
        root / "sources/post-metrics/exports",
        root / "sources/post-metrics/captures",
        root / "sources/post-metrics/normalized",
        root / "posts",
        root / "posts/1",
        root / "brand-assets",
        root / "customer",
    ]

    # File targets
    config_path = root / "loop/config.json"
    state_path = root / "loop/publications.json"
    loop_readme = root / "loop/README.md"
    loop_agents = root / "loop/AGENTS.md"
    catalog_path = root / "product-marketing.json"
    hypo_path = root / hypotheses_file
    post_1_path = root / "posts/1/facebook-ad.md"

    # Pre-flight config check
    config = {"page_id": page_id, "hypotheses_file": hypotheses_file}
    if config_path.exists():
        existing_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        if existing_cfg.get("page_id") != page_id:
            raise ValueError(f"Project already configured with Page ID '{existing_cfg.get('page_id')}'; nothing changed.")

    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state.get("publications"), list):
            raise ValueError("Existing loop/publications.json is invalid; nothing changed.")

    files_plan = [
        config_path,
        state_path,
        loop_readme,
        loop_agents,
        catalog_path,
        hypo_path,
        post_1_path,
    ]

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
    if not config_path.exists():
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not state_path.exists():
        state_payload = {"schema_version": 2, "publications": [], "placements": []}
        state_path.write_text(json.dumps(state_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not loop_readme.exists():
        loop_readme.write_text(
            f"# Loop Configuration for Page {page_id}\n\n"
            "## Defined Business Outcomes\n"
            "- Qualified inquiries: [Define qualified inquiry criteria]\n"
            "- Target buyer role: [Define target buyer persona]\n"
            "- Conversion action: [Define expected next step]\n\n"
            "## Orchestrator Commands\n"
            "See `tools/loop/README.md` for orchestrator reference.\n",
            encoding="utf-8",
        )

    if not loop_agents.exists():
        loop_agents.write_text(
            "# Loop Agent Safeguards\n\n"
            "- Do not publish automatically without explicit human approval.\n"
            "- Do not prune groups without at least 3 comparable rounds.\n"
            "- Never treat pending moderation posts as failures.\n",
            encoding="utf-8",
        )

    if not catalog_path.exists():
        cat = dict(DEFAULT_PRODUCT_CATALOG)
        if marketing_goal:
            cat["marketing_goal"] = marketing_goal
        catalog_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not hypo_path.exists():
        hypo_path.parent.mkdir(parents=True, exist_ok=True)
        hypo_path.write_text(json.dumps(DEFAULT_HYPOTHESIS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not post_1_path.exists():
        post_1_path.write_text(DEFAULT_POST_TEMPLATE, encoding="utf-8")

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="New project root directory")
    parser.add_argument("--page-id", required=True, help="Facebook Page ID (digits only)")
    parser.add_argument("--hypotheses-file", default="posts/hypothesis.json", help="Relative path for hypotheses JSON")
    parser.add_argument("--marketing-goal", help="Optional custom marketing goal string")
    parser.add_argument("--dry-run", action="store_true", help="Preview would-create paths without writing to disk")
    args = parser.parse_args(argv)

    result = bootstrap_project(
        args.project,
        args.page_id,
        hypotheses_file=args.hypotheses_file,
        marketing_goal=args.marketing_goal,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
