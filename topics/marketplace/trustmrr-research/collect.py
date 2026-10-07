"""Private TrustMRR snapshot and bounded official-site research; no paid services."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "local"
AGENT = "ProductResearch/1.0"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def api_snapshot():
    key = os.environ.get("TRUSTMRR_API_KEY") or dotenv_values(ROOT / ".env").get("TRUSTMRR_API_KEY")
    if not key:
        raise SystemExit("Configure TRUSTMRR_API_KEY in .env")
    # Live API uses USD, unlike the cents described in the October 7 docs.
    # Exhaust every record above a threshold; lower it if fewer than 100 qualify.
    for floor in (20000, 10000, 0):
        rows = {}
        page = 1
        while True:
            path = OUT / "api" / f"floor-{floor}-page-{page}.json"
            if path.exists():
                payload = json.loads(path.read_text())["response"]
            else:
                query = urlencode({"minMrr": floor, "limit": 10, "page": page, "sort": "revenue-desc"})
                req = Request(f"https://trustmrr.com/api/v1/startups?{query}",
                              headers={"Authorization": f"Bearer {key}", "User-Agent": AGENT})
                for attempt in range(3):
                    try:
                        with urlopen(req, timeout=60) as response:
                            payload = json.load(response)
                            headers = dict(response.headers)
                        break
                    except HTTPError as error:
                        if error.code != 429 or attempt == 2:
                            raise SystemExit(f"TrustMRR API returned HTTP {error.code}; stopped")
                        reset = float(error.headers.get("X-RateLimit-Reset", 0))
                        if reset > 1e12:
                            reset /= 1000
                        time.sleep(max(7, reset - time.time() + 1))
                save(path, {"captured_at": stamp(), "response": payload})
                # Conservative standard-key pacing, including rolling windows.
                time.sleep(6.2)
            for row in payload["data"]:
                rows[row["slug"]] = row
            print(f"floor=${floor:,} page={page} collected={len(rows)} total={payload['meta']['total']}", flush=True)
            if not payload["meta"]["hasMore"]:
                break
            page += 1
        ranked = sorted(rows.values(), key=lambda row: (-Decimal(str(row["revenue"]["mrr"])), row["slug"]))
        if len(rows) != payload["meta"]["total"]:
            raise SystemExit("Pagination count changed or duplicates occurred; recapture before claiming complete ranking")
        if any(not Decimal(str(row["revenue"]["mrr"])).is_finite()
               or Decimal(str(row["revenue"]["mrr"])) < floor for row in ranked):
            raise SystemExit("Unexpected MRR units or values; inspect contract before continuing")
        if len(ranked) >= 100:
            save(OUT / "selection.json", {"captured_at": stamp(), "observed_currency_unit": "USD",
                 "selection_floor_usd": floor, "eligible_records_scanned": len(ranked),
                 "ranking_method": "All matching records paginated; local descending revenue.mrr, slug tie-break",
                 "snapshot_caveat": "Paginated live capture, not an atomic database snapshot",
                 "data": [dict(row, mrr_rank=i + 1) for i, row in enumerate(ranked[:100])]})
            print(f"Selected 100; cutoff MRR ${ranked[99]['revenue']['mrr']:,.2f}", flush=True)
            return
    raise SystemExit("Fewer than 100 eligible startups; no complete selection written")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
        self.links = []
        self.href = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "tr", "section"):
            self.parts.append("\n")
        if tag == "a":
            self.href = attrs.get("href")
            self.label = []
        if tag == "meta" and attrs.get("name") == "description":
            self.parts.append(attrs.get("content", "") + "\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        if tag == "a" and self.href:
            self.links.append({"href": self.href, "label": " ".join(self.label)})
            self.href = None

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.href:
                self.label.append(data.strip())

    def text(self):
        return "\n".join(line for raw in "".join(self.parts).splitlines()
                         if (line := re.sub(r"\s+", " ", raw).strip()))


def get(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return {"url": url, "error": "Invalid public URL", "captured_at": stamp()}
    # Do not follow profile links to private/local networks or send credentials to websites.
    import ipaddress
    import socket
    try:
        for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
            if not ipaddress.ip_address(info[4][0]).is_global:
                return {"url": url, "error": "Non-public network address", "captured_at": stamp()}
        req = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,text/plain,application/json"})
        with urlopen(req, timeout=35) as response:
            final = response.url
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            return {"url": url, "error": "Page exceeds bounded download size", "captured_at": stamp()}
        body = raw.decode("utf-8", errors="replace")
        if "html" in content_type or body.lstrip().lower().startswith(("<!doctype", "<html")):
            parser = Page()
            parser.feed(body)
            text, links = parser.text(), parser.links
        else:
            text, links = body, []
        return {"url": url, "final_url": final, "captured_at": stamp(), "text": text, "links": links}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        # Error strings contain no request authorization headers.
        return {"url": url, "captured_at": stamp(), "error": str(error)}


def research_one(row):
    directory = OUT / "sources" / row["slug"]
    profile_path = directory / "profile.json"
    if not profile_path.exists():
        save(profile_path, get(row.get("markdownUrl") or f"https://trustmrr.com/startup/{row['slug']}.md"))
    if row.get("stealthMode") or not row.get("website"):
        save(directory / "status.json", {"status": "anonymous_or_no_public_website", "captured_at": stamp()})
        return f"{row['mrr_rank']}: {row['name']} — identity unavailable"
    website = row["website"]
    if not website.startswith(("https://", "http://")):
        website = "https://" + website
    if website.startswith("http://"):
        website = "https://" + website[len("http://"):]
    robots_url = urljoin(website, "/robots.txt")
    robots = get(robots_url)
    save(directory / "robots.json", robots)
    rules = RobotFileParser()
    rules.parse(robots.get("text", "").splitlines())
    # Missing robots allows crawling; other HTTP failures do not imply permission.
    if "error" in robots and "404" not in robots["error"]:
        save(directory / "status.json", {"status": "robots_unavailable", "error": robots["error"]})
        return f"{row['mrr_rank']}: {row['name']} — robots unavailable"
    if not rules.can_fetch(AGENT, website):
        save(directory / "status.json", {"status": "robots_disallowed"})
        return f"{row['mrr_rank']}: {row['name']} — robots disallowed"
    homepage_path = directory / "homepage.json"
    if homepage_path.exists():
        home = json.loads(homepage_path.read_text())
    else:
        time.sleep(1)
        home = get(website)
        save(homepage_path, home)
    if "error" in home:
        save(directory / "status.json", {"status": "homepage_failed", "error": home["error"]})
        return f"{row['mrr_rank']}: {row['name']} — homepage unavailable"
    base = home.get("final_url", website)
    # ponytail: at most four linked product/pricing/customer pages; expand manually when evidence is weak.
    candidates = []
    for link in home.get("links", []):
        href = urljoin(base, link["href"]).split("#")[0]
        label = link["label"] + " " + href
        if urlparse(href).netloc != urlparse(base).netloc or href == base:
            continue
        if re.search(r"pricing|plans|customers|case.stud|success.stor|features|how.it.works|enterprise", label, re.I):
            score = 0 if re.search(r"pricing|plans", label, re.I) else 1 if re.search(r"customers|case.stud|success.stor", label, re.I) else 2
            candidates.append((score, href))
    urls = []
    for score, cap in ((0, 1), (1, 2), (2, 1)):
        group = list(dict.fromkeys(href for kind, href in candidates if kind == score))
        urls.extend(url for url in group[:cap] if url not in urls)
    for index, url in enumerate(urls):
        path = directory / f"page-{index + 1}.json"
        if path.exists():
            continue
        if rules.can_fetch(AGENT, url):
            time.sleep(1)
            save(path, get(url))
    save(directory / "status.json", {"status": "bounded_official_research_collected", "linked_pages": len(urls)})
    return f"{row['mrr_rank']}: {row['name']} — {len(urls) + 1} official pages collected"


def self_check():
    parser = Page()
    parser.feed('<h1>Hello</h1><script>SECRET</script><a href="/pricing">Plans</a>')
    assert "SECRET" not in parser.text()
    assert parser.links == [{"href": "/pricing", "label": "Plans"}]
    assert Decimal("3569654.22") > Decimal("863632.00")
    print("Self-check passed")


def digest(start, end):
    rows = json.loads((OUT / "selection.json").read_text())["data"]
    for row in rows[start - 1:end]:
        directory = OUT / "sources" / row["slug"]
        print(f"\n## {row['mrr_rank']} {row['name']} [{row['slug']}] MRR=${row['revenue']['mrr']:,.2f} stealth={row.get('stealthMode')}")
        print("API description:", row.get("description"))
        for path in sorted(directory.glob("*.json")):
            if path.name in ("robots.json", "status.json"):
                continue
            source = json.loads(path.read_text())
            print(f"SOURCE {path.name}: {source['url']}")
            if source.get("error"):
                print("ERROR", source["error"])
                continue
            text = source.get("text", "")
            if path.name == "profile.json":
                for line in text.splitlines():
                    if re.match(r"- (Description|Revenue last synced|Primary payment provider API credential|Pricing model|Target persona|Audience type|Value proposition|Problem solved|Current MRR):", line):
                        print(line)
            else:
                # Human-reviewed extracts, not automatic product/customer judgments.
                print(text[:2300])
                money = [line for line in text.splitlines() if re.search(r"\$\s*\d|€\s*\d|£\s*\d", line)]
                print("PRICE LINES:", " / ".join(money[:30])[:1800])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("mode", choices=("snapshot", "research", "check", "digest"))
    cli.add_argument("--start", type=int, default=1)
    cli.add_argument("--end", type=int, default=100)
    args = cli.parse_args()
    if args.mode == "snapshot":
        api_snapshot()
    elif args.mode == "research":
        rows = json.loads((OUT / "selection.json").read_text())["data"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for message in pool.map(research_one, rows):
                print(message, flush=True)
    elif args.mode == "digest":
        digest(args.start, args.end)
    else:
        self_check()
