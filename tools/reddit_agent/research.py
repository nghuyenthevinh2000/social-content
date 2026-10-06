#!/usr/bin/env python3
"""
research.py

A lightweight, zero-credential scraper that fetches posts and nested comments/replies
from any subreddit using Reddit's public Atom/RSS feeds.

Features:
- Does NOT require Reddit developer API keys or Descope authentication.
- Automatically handles Reddit HTTP 429 rate limits using exact x-ratelimit-reset headers.
- Supports paginated crawling (new, top, hot).
- Supports time filtering (e.g. last N months).
- Cleans HTML markup from selftext and comment bodies.
- Exports structured JSON containing post metadata, URLs, authors, and replies.

Usage:
    python3 research.py --subreddit https://www.reddit.com/r/Marketresearch/ --months 6 --output local/market-research
"""

import argparse
from datetime import datetime, timezone, timedelta
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

NS = {"atom": "http://www.w3.org/2005/Atom"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def clean_subreddit_name(sub_input: str) -> str:
    """Extracts clean subreddit name from full URL or r/ prefix."""
    s = sub_input.strip().rstrip("/")
    if "reddit.com/r/" in s:
        s = s.split("reddit.com/r/")[1].split("/")[0]
    s = s.replace("r/", "").strip("/")
    return s


def clean_html(raw_html: str) -> str:
    """Removes HTML tags and unescapes entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^<]+?>", "", html.unescape(raw_html))
    return "\n".join([line.strip() for line in text.splitlines() if line.strip()])


def fetch_xml(url: str, max_retries: int = 6) -> ET.Element:
    """Fetches an RSS/Atom XML feed with exponential/header backoff on HTTP 429."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(max_retries):
        try:
            with opener.open(req, timeout=20) as resp:
                return ET.fromstring(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                reset_header = e.headers.get("x-ratelimit-reset")
                if reset_header:
                    try:
                        wait_time = float(reset_header) + 1.5
                    except ValueError:
                        wait_time = 15.0 * (attempt + 1)
                else:
                    wait_time = 15.0 * (attempt + 1)
                print(f"      [Rate limited 429] Reddit reset window: waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts.")


def parse_published_date(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def fetch_subreddit_posts(
    subreddit: str = "AskMarketing",
    sort: str = "new",
    timeframe: str = "month",
    limit: Optional[int] = None,
    months: Optional[float] = None,
    crawl_replies: bool = False,
    request_delay: float = 6.0,
    output_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches posts from a given subreddit with pagination and optional time cutoff.
    """
    clean_sub = clean_subreddit_name(subreddit)
    cutoff_dt = None
    if months is not None:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=months * 30.5)
        print(f"Filtering posts newer than: {cutoff_dt.isoformat()} (last {months} months)")

    posts_data: List[Dict[str, Any]] = []
    seen_ids = set()
    after_id = None
    page = 1
    reached_cutoff = False

    while True:
        # Build URL
        if sort == "top":
            base_url = f"https://www.reddit.com/r/{clean_sub}/top.rss?t={timeframe}"
        elif sort == "hot":
            base_url = f"https://www.reddit.com/r/{clean_sub}/hot.rss"
        else:
            base_url = f"https://www.reddit.com/r/{clean_sub}/new.rss"

        feed_url = f"{base_url}&after={after_id}" if "?" in base_url else (f"{base_url}?after={after_id}" if after_id else base_url)
        print(f"\n[Page {page}] Fetching feed from r/{clean_sub} ({feed_url})...")

        try:
            feed = fetch_xml(feed_url)
        except Exception as err:
            print(f"Error fetching page {page}: {err}")
            break

        entries = feed.findall("atom:entry", NS)
        if not entries:
            print("No entries returned in feed. Reached end of listing.")
            break

        new_entries_in_page = 0
        for entry in entries:
            post_id = entry.find("atom:id", NS).text or ""
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)
            new_entries_in_page += 1

            published_el = entry.find("atom:published", NS)
            published = published_el.text if published_el is not None else ""
            pub_dt = parse_published_date(published)

            # Check cutoff
            if cutoff_dt and pub_dt and pub_dt < cutoff_dt:
                print(f"Reached post dated {published} which is older than cutoff {cutoff_dt.isoformat()}. Stopping.")
                reached_cutoff = True
                break

            title_el = entry.find("atom:title", NS)
            title = title_el.text if (title_el is not None and title_el.text) else ""
            author_el = entry.find("atom:author/atom:name", NS)
            author = author_el.text if (author_el is not None and author_el.text) else ""
            post_link = entry.find("atom:link", NS).attrib.get("href", "") if entry.find("atom:link", NS) is not None else ""
            content_el = entry.find("atom:content", NS)
            raw_content = content_el.text if (content_el is not None and content_el.text) else ""
            body = clean_html(raw_content)

            replies: List[Dict[str, Any]] = []
            if crawl_replies:
                comments_url = f"{post_link.rstrip('/')}.rss"
                time.sleep(request_delay)
                try:
                    comments_feed = fetch_xml(comments_url)
                    for c in comments_feed.findall("atom:entry", NS):
                        c_id_el = c.find("atom:id", NS)
                        c_id = c_id_el.text if c_id_el is not None else ""
                        if c_id.startswith("t1_"):
                            c_auth_el = c.find("atom:author/atom:name", NS)
                            c_auth = c_auth_el.text if (c_auth_el is not None and c_auth_el.text) else ""
                            c_link = c.find("atom:link", NS).attrib.get("href", "") if c.find("atom:link", NS) is not None else ""
                            c_cnt_el = c.find("atom:content", NS)
                            c_cnt = clean_html(c_cnt_el.text or "") if (c_cnt_el is not None and c_cnt_el.text) else ""
                            c_up_el = c.find("atom:updated", NS)
                            c_up = c_up_el.text if (c_up_el is not None and c_up_el.text) else ""
                            replies.append({
                                "id": c_id,
                                "author": c_auth,
                                "body": c_cnt,
                                "url": c_link,
                                "published_at": c_up,
                            })
                except Exception as c_err:
                    print(f"       --> Error fetching comments: {c_err}")

            posts_data.append({
                "id": post_id,
                "title": title,
                "author": author,
                "url": post_link,
                "published_at": published,
                "body": body,
                "reply_count": len(replies),
                "replies": replies,
            })

            print(f"  + [{len(posts_data)}] ({published[:10]}) {title[:60]}")

            if limit and len(posts_data) >= limit:
                break

        # Save checkpoint after each page
        if output_file:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(posts_data, f, indent=2, ensure_ascii=False)
            except Exception as save_err:
                print(f"Warning: could not save checkpoint: {save_err}")

        if reached_cutoff or (limit and len(posts_data) >= limit):
            break

        if new_entries_in_page == 0:
            print("No new unique posts found on this page. Stopping.")
            break

        after_id = entries[-1].find("atom:id", NS).text
        page += 1
        time.sleep(request_delay)

    return posts_data


def main():
    parser = argparse.ArgumentParser(
        description="Fetch posts and replies from any subreddit without API keys."
    )
    parser.add_argument("--subreddit", default="AskMarketing", help="Target subreddit or Reddit URL")
    parser.add_argument("--sort", default="new", choices=["new", "top", "hot"], help="Listing sort order (default: new)")
    parser.add_argument("--timeframe", default="month", choices=["day", "week", "month", "year", "all"], help="Timeframe if sort=top (default: month)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of posts to fetch")
    parser.add_argument("--months", type=float, default=None, help="Fetch posts from the last N months (e.g. 6)")
    parser.add_argument("--crawl-replies", action="store_true", help="Crawl nested comment replies for each post")
    parser.add_argument("--output", default="askmarketing_posts.json", help="Path to output JSON file or destination directory")
    parser.add_argument("--delay", type=float, default=3.0, help="Polite delay between requests in seconds")

    args = parser.parse_args()

    clean_sub = clean_subreddit_name(args.subreddit)

    # Determine destination file path
    output_path = Path(args.output)
    if output_path.is_dir() or (not output_path.suffix and not output_path.exists()):
        output_path.mkdir(parents=True, exist_ok=True)
        target_file = output_path / f"{clean_sub.lower()}_posts.json"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_file = output_path

    results = fetch_subreddit_posts(
        subreddit=clean_sub,
        sort=args.sort,
        timeframe=args.timeframe,
        limit=args.limit,
        months=args.months,
        crawl_replies=args.crawl_replies,
        request_delay=args.delay,
        output_file=target_file,
    )

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Saved {len(results)} posts into {target_file}")


if __name__ == "__main__":
    main()
