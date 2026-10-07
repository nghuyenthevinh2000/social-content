"""Render reviewed notes and dated source evidence into private research artifacts."""

from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parent / "local"


def source_field(text, label):
    match = re.search(rf"^- {re.escape(label)}: (.+)$", text, re.M)
    return match.group(1).strip() if match else "Unknown / not disclosed"


def record_anonymous_limits():
    """Preserve identities withheld by owners instead of trying to research aliases."""
    rows = json.loads((OUT / "selection.json").read_text())["data"]
    path = OUT / "reviewed-notes.json"
    notes = json.loads(path.read_text())
    for row in rows:
        if not row.get("stealthMode") or row["slug"] in notes:
            continue
        description = row.get("description")
        notes[row["slug"]] = {
            "segment": "Anonymous / limited evidence",
            "product": "Founder-disclosed description only (not verified): " + description if description else "Unknown; the owner has withheld the product identity and public description.",
            "user": "Only the broad audience, if any, stated in the disclosed description is available. Specific user/customer identities are unknown.",
            "payer": "Unknown. Aggregate subscription/MRR data does not disclose who buys, who funds access, or whether several offers share the payment account.",
            "trigger": "Unknown; no independently researchable public product workflow.",
            "renewal": "Unknown; an aggregate recurring-revenue snapshot does not establish retention mechanisms or contractual terms.",
            "pricing": "Not disclosed. MRR divided by active subscriptions is not a published plan price or a reliable customer-count estimate.",
            "customer_evidence": "No named paying-customer evidence established. Do not infer hidden identities from founder handles, slugs or similar products.",
            "risk": "Limited-research entry retained at its original MRR rank. Founder-described outcomes, revenue, margins and growth claims are not independently validated. Product/pricing/customer diligence requires owner-authorized disclosure.",
            "sources": [],
        }
    path.write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n")
    print(f"Recorded explicit evidence limits for {sum(row.get('stealthMode', False) for row in rows)} anonymous entries")


def build():
    selection = json.loads((OUT / "selection.json").read_text())
    notes = json.loads((OUT / "reviewed-notes.json").read_text())
    rows = selection["data"]
    assert len(rows) == 100 and len({row["slug"] for row in rows}) == 100
    assert set(notes) == {row["slug"] for row in rows}, "Every selected entry needs a reviewed note"
    amounts = [Decimal(str(row["revenue"]["mrr"])) for row in rows]
    assert amounts == sorted(amounts, reverse=True)
    asof = datetime.fromisoformat(selection["captured_at"])
    enriched = []
    dossiers = []
    for row in rows:
        note = notes[row["slug"]]
        for field in ("product", "user", "payer", "trigger", "renewal", "pricing", "customer_evidence", "risk", "segment", "sources"):
            assert field in note, f"Missing {field}: {row['slug']}"
        directory = OUT / "sources" / row["slug"]
        profile = json.loads((directory / "profile.json").read_text())
        text = profile.get("text", "")
        sync = source_field(text, "Revenue last synced")
        credential = source_field(text, "Primary payment provider API credential")
        freshness = "unknown"
        try:
            age = (asof - datetime.fromisoformat(sync.replace("Z", "+00:00"))).total_seconds() / 86400
            freshness = "recent (<=7 days)" if age <= 7 else "stale (>7 days)"
        except ValueError:
            pass
        if "expired" in credential.lower():
            freshness = "stale / expired credential"
        source_urls = list(dict.fromkeys([profile["url"], *note["sources"]]))
        assert all(url.startswith(("https://", "http://")) for url in source_urls)
        status = json.loads((directory / "status.json").read_text())
        official_pages = [json.loads(path.read_text()) for path in directory.glob("*.json")
                          if path.name not in ("profile.json", "robots.json", "status.json")]
        # Count distinct extracts; repeated homepages and app-store recommendations
        # are not additional product evidence. This still measures fetches, not proof.
        successful = len({page["text"].strip() for page in official_pages
                          if page.get("text", "").strip() and not page.get("error")
                          and "see-all=customers-also-bought-apps" not in page["url"]
                          and not page["url"].rstrip("/").endswith("affiliates")})
        failures = [f"{page['url']}: {page['error']}" for page in official_pages if page.get("error")]
        exported = {
            "mrr_rank": row["mrr_rank"], "name": row["name"], "slug": row["slug"],
            "mrr_usd": str(Decimal(str(row["revenue"]["mrr"])).quantize(Decimal("0.01"))),
            "revenue_30d_usd": str(Decimal(str(row["revenue"]["last30Days"])).quantize(Decimal("0.01"))),
            "active_subscriptions": row.get("activeSubscriptions"),
            "payment_provider": row.get("paymentProvider"), "revenue_last_synced": sync,
            "freshness": freshness, "anonymous": bool(row.get("stealthMode")),
            "website": "" if row.get("stealthMode") else row.get("website", ""),
            "segment": note["segment"], "product": note["product"], "user": note["user"],
            "payer_hypothesis": note["payer"], "purchase_trigger_hypothesis": note["trigger"],
            "renewal_hypothesis": note["renewal"], "pricing_evidence": note["pricing"],
            "named_customer_evidence": note["customer_evidence"], "risk_and_gaps": note["risk"],
            "official_pages_fetched": successful, "collection_status": status["status"],
            "sources": " | ".join(source_urls),
        }
        enriched.append(exported)
        heading = f"## {row['mrr_rank']:03d}. {row['name']} (`{row['slug']}`)"
        lines = [heading, "", f"**Displayed MRR:** ${exported['mrr_usd']} | **Active subscriptions:** {exported['active_subscriptions']} | **Provider:** {exported['payment_provider']}",
                 f"**Revenue last synced:** {sync} | **Freshness:** {freshness}", "",
                 f"- **Product / workflow:** {note['product']}",
                 f"- **User / beneficiary:** {note['user']}",
                 f"- **Who pays / budget (hypothesis unless explicitly documented):** {note['payer']}",
                 f"- **Purchase trigger (hypothesis):** {note['trigger']}",
                 f"- **Renewal reason (hypothesis):** {note['renewal']}",
                 f"- **Pricing evidence:** {note['pricing']}",
                 f"- **Named customer / payment evidence:** {note['customer_evidence']}",
                 f"- **Risks / unknowns:** {note['risk']}",
                 f"- **Research coverage:** {successful} distinct official extracts fetched; {status['status']}. Fetch count is not evidence quality."]
        if failures:
            lines.append("- **Fetch failures:** " + "; ".join(failures))
        lines += ["", "**Sources:** " + " · ".join(f"[S{i}]({url})" for i, url in enumerate(source_urls, 1)), ""]
        dossiers.append("\n".join(lines))
    counts = Counter(row["freshness"] for row in enriched)
    segments = Counter(row["segment"] for row in enriched)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_captured_at": selection["captured_at"],
        "entries_reviewed": len(enriched), "anonymous_entries": sum(row["anonymous"] for row in enriched),
        "freshness_counts": dict(counts), "segment_counts": dict(segments),
        "entries_with_official_page_text": sum(row["official_pages_fetched"] > 0 for row in enriched),
        "official_pages_fetched": sum(row["official_pages_fetched"] for row in enriched),
        "ranking_floor_usd": selection["selection_floor_usd"],
        "eligible_records_scanned": selection["eligible_records_scanned"],
        "rank_100_mrr_usd": enriched[-1]["mrr_usd"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "research.json").write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n")
    with (OUT / "top-100.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(enriched[0]))
        writer.writeheader()
        writer.writerows(enriched)
    preamble = f"""# Top 100 displayed-MRR startups — private product and payer research

Selection capture: {selection['captured_at']}. Research: October 7, 2026.

## Scope and method

All **100 selected entries** have been reviewed, including **{summary['anonymous_entries']} anonymous entries**.
The API was paginated across **{summary['eligible_records_scanned']} records** with MRR >= **${selection['selection_floor_usd']:,.0f}**, then sorted by MRR locally; rank 100 displayed **${enriched[-1]['mrr_usd']}**.
This proves coverage above the chosen threshold for this capture, not an atomic or independently audited live ranking. Monetary units were checked against public profiles: the live API uses USD despite documentation stating cents. The API `rank` and last-30-day revenue sort were not used as MRR ranks.

This is bounded desk research, not customer interviews, transaction auditing, hands-on product testing, or exhaustive review-platform analysis. **{summary['entries_with_official_page_text']} entries** have fetched official-site text (**{summary['official_pages_fetched']} distinct extracts** across entries, excluding duplicate text, App Store related-app pages and affiliate pages); others are anonymous, unreachable, blocked, or lack a public website. Fetch success is not substantive evidence quality: empty/JavaScript-only extracts, navigation and logos do not prove product or customer facts. Some entries therefore rely on founder-edited profile descriptions only. Captured sources and failures are preserved under `sources/`. Remaining gaps are explicit, not fabricated.

Freshness counts: {dict(counts)}. Revenue sync is a freshness indicator, not a separately confirmed timestamp for every MRR field. Stale/expired feeds remain in the displayed-MRR ranking; they do not establish current October performance. Zero or absent customer counts are not interpreted as no paying customers.

## Evidence labels

- Provider-backed aggregate: TrustMRR's payment-derived metric, subject to feed freshness.
- Vendor-stated offer/target: positioning or pricing from a profile or official website, not independently verified outcomes.
- Customer relationship claimed: named logo, testimonial, or story without proof of payment.
- Paid-tier association, vendor-reported: an explicit named commercial plan, not a verified transaction.
- Analyst hypothesis: likely purchaser, budget, trigger, or renewal mechanism. Not an observed customer fact.
- Unknown: no reliable public evidence found within the bounded research.

No named customer is labeled transaction-verified. Service users, institution-sponsored beneficiaries, marketplace shoppers, affiliates, free users, and subscribers are kept distinct. No attempt was made to identify anonymous companies. A known brand in another product's customer list is not automatically a paying software buyer.

**Private-use restriction:** No publication, SEO directory, redistributed dataset, outreach, or cloning is authorized. Review [TrustMRR's acceptable-use policy](https://trustmrr.com/terms#api-acceptable-use) before any downstream sharing.

## Dossiers

"""
    (OUT / "top-100-dossiers.md").write_text(preamble + "\n".join(dossiers))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    assert source_field("- Revenue last synced: 2026-10-07", "Revenue last synced") == "2026-10-07"
    assert source_field("", "Revenue last synced") == "Unknown / not disclosed"
    if "--anonymous-limits" in sys.argv:
        record_anonymous_limits()
    else:
        build()
