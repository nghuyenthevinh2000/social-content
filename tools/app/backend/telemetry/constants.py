"""Shared constants for backend telemetry (cost control and profiling)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Optional, Tuple

# -- Cost Control Constants --------------------------------------------------

MICRO_PER_USD = 1_000_000

DEFAULT_USER_ID = "default"
DEFAULT_ACTION = "unknown"
DEFAULT_USER_GENDER = "male"
DEFAULT_USER_AGE = 28

DEFAULT_GLASSER_TIMEOUT_SEC = 45.0
DEFAULT_SUMMARY_DAYS = 30
DEFAULT_REPORT_DAYS = 7
RECENT_RUNS_LIMIT = 50
WASTED_CALLS_LIMIT = 25
MAX_CHARGE_CLAUSE_LEN = 200

@dataclass(frozen=True)
class ActionPolicy:
    allowed_endpoints: frozenset[Tuple[str, str]]
    max_calls: Optional[int] = None
    max_transcript_calls: Optional[int] = None
    max_cost_micro: Optional[int] = None


TRANSCRIPT_ENDPOINT_PLATFORMS: Dict[str, Tuple[str, str]] = {
    "/v1/facebook/post/transcript": ("facebook", "Facebook"),
    "/v1/youtube/video/transcript": ("youtube", "YouTube"),
    "/v1/tiktok/video/transcript": ("tiktok", "TikTok"),
    "/v2/instagram/media/transcript": ("instagram", "Instagram"),
}

TRANSCRIPT_ENDPOINTS = frozenset(TRANSCRIPT_ENDPOINT_PLATFORMS)

ACTION_POLICIES: Dict[str, ActionPolicy] = {
    "keyword_search": ActionPolicy(
        allowed_endpoints=frozenset({
            ("scrapecreators", "/v1/youtube/search"),
            ("serper", "/videos"),
            ("scrapecreators", "/v1/facebook/adLibrary/search/ads"),
            ("scrapecreators", "/v1/tiktok/search/keyword"),
            ("scrapecreators", "/v2/instagram/reels/search"),
        }),
        max_calls=28,
        max_cost_micro=45_000,
    ),
    "profile_research": ActionPolicy(
        allowed_endpoints=frozenset({
            ("scrapecreators", "/v1/facebook/profile/reels"),
            ("scrapecreators", "/v1/youtube/channel-videos"),
            ("scrapecreators", "/v1/youtube/channel/shorts"),
            ("scrapecreators", "/v3/tiktok/profile/videos"),
            ("scrapecreators", "/v1/instagram/user/reels"),
        }),
        max_transcript_calls=0,
        max_cost_micro=100_000,
    ),
    "reel_research": ActionPolicy(
        allowed_endpoints=frozenset(("scrapecreators", ep) for ep in TRANSCRIPT_ENDPOINTS),
        max_transcript_calls=3,
        max_cost_micro=10_000,
    ),
    "hashtag_search": ActionPolicy(
        allowed_endpoints=frozenset({
            ("tikhub", "/api/v1/tiktok/app/v3/fetch_hashtag_search_result"),
            ("tikhub", "/api/v1/instagram/v2/search_hashtags"),
        }),
        max_calls=12,
        max_cost_micro=25_000,
    ),
    "video_generation": ActionPolicy(
        allowed_endpoints=frozenset({("google_genai", "veo-video-generation")}),
        max_calls=2,
    ),
}

RUN_ID_RE = re.compile(r"Run\s+ID:\s*(\S+)", re.IGNORECASE)
RUN_URL_RE = re.compile(r"Run\s+URL:\s*(\S+)", re.IGNORECASE)
HTTP_STATUS_RE = re.compile(r"Response:\s*HTTP\s*(\d+)", re.IGNORECASE)
CHARGE_RE = re.compile(r"Charge:\s*\$([0-9]+(?:\.[0-9]+)?)\s*(?:\(([^)]+)\))?", re.IGNORECASE)

# -- Profiling Constants -----------------------------------------------------

ALL_CONTEXTS = ("db", "http", "supervisor", "worker", "video")
SLOW_SQL_MS = 20.0
TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})
BYTES_PER_KB = 1024
SQL_SNIPPET_MAX_LEN = 100
DEFAULT_PROFILE_TOP_N = 15
DEFAULT_BENCH_ITERATIONS = 10
SUPERVISOR_STALE_SEC = 30
HTTP_BENCH_MAX_WORKERS = 8
HTTP_BENCH_TIMEOUT_SEC = 10

DEFAULT_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/aibrand_test"
DEFAULT_TEST_BLOB_ENDPOINT = "http://localhost:9000"
DEFAULT_TEST_BLOB_BUCKET = "test-aibrand"
DEFAULT_TEST_BLOB_ACCESS_KEY = "rustfsadmin"
DEFAULT_TEST_BLOB_SECRET_KEY = "rustfsadmin"
DEFAULT_TEST_BLOB_REGION = "us-east-1"

DEFAULT_PROF_USER_ID = "prof_user"
DEFAULT_PROF_JOB_ID = "deadbeef0001"
DEFAULT_PROF_CLIENT_ID = "prof-client"

HTTP_BENCH_ROUTES = (
    ("GET", "/api/health"),
    ("GET", "/api/jobs"),
    ("GET", "/api/jobs/{job_id}"),
    ("GET", "/api/sources/topics"),
    ("GET", "/api/credits"),
    ("GET", "/api/logs"),
)
