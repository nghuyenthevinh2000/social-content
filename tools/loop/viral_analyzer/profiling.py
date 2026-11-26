"""Stdlib-only profiling spans and isolated subsystem benchmarks for tools.loop.viral_analyzer.

Usage:
    python3 -m tools.loop.viral_analyzer.profiling --context core,profile,video,keyword,concurrency
    .venv/bin/python -m tools.loop.viral_analyzer.profiling --context all --iterations 5 --cprofile
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import cProfile
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import pstats
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple
from unittest.mock import patch

WORKSPACE = Path(__file__).resolve().parents[3]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from tools.loop.viral_analyzer import normalize, platforms, runtime

ALL_CONTEXTS = ("core", "profile", "video", "keyword", "concurrency", "cache")


def _parse_bool(val: Optional[str]) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_contexts(val: Optional[str]) -> set[str]:
    raw = (val or "").strip().lower()
    if not raw or raw == "all":
        return set(ALL_CONTEXTS)
    return {c.strip() for c in raw.split(",") if c.strip() in ALL_CONTEXTS}


ENABLED = _parse_bool(os.environ.get("PROFILE_VIRAL_ANALYZER"))
ACTIVE_CONTEXTS: set[str] = _parse_contexts(os.environ.get("PROFILE_VIRAL_CONTEXTS"))


def configure(enabled: Optional[bool] = None, contexts: Optional[str] = None) -> None:
    """Update runtime profiling flags (useful for benchmarks and tests)."""
    global ENABLED, ACTIVE_CONTEXTS
    if enabled is not None:
        ENABLED = enabled
    if contexts is not None:
        ACTIVE_CONTEXTS = _parse_contexts(contexts)


def is_enabled(context: Optional[str] = None) -> bool:
    if not ENABLED:
        return False
    if context is None:
        return True
    return context in ACTIVE_CONTEXTS


def rss_kb() -> int:
    """Return process max RSS in kilobytes (normalizing macOS bytes vs Linux KB)."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage // 1024) if sys.platform == "darwin" else int(usage)


@contextmanager
def span(context: str, name: str) -> Iterator[None]:
    """Time a named operation when viral-analyzer profiling is enabled for `context`."""
    if not is_enabled(context):
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        sys.stderr.write(f"[viral-profile:{context}] {name} {ms:.2f}ms\n")


def profile_callable(
    fn: Callable[..., Any],
    *args: Any,
    top_n: int = 15,
    **kwargs: Any,
) -> Tuple[Any, str, float]:
    """Run `fn` under cProfile and tracemalloc, returning (result, pstats_text, peak_kb)."""
    prof = cProfile.Profile()
    started_trace = not tracemalloc.is_tracing()
    if started_trace:
        tracemalloc.start()
    try:
        prof.enable()
        result = fn(*args, **kwargs)
        prof.disable()
        _cur, peak = tracemalloc.get_traced_memory()
    finally:
        if started_trace and tracemalloc.is_tracing():
            tracemalloc.stop()
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("cumtime").print_stats(top_n)
    return result, buf.getvalue(), peak / 1024.0


class BenchCollector:
    """Thread-safe percentile and throughput collector across benchmark contexts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.samples: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self.notes: List[str] = []

    def record(
        self,
        context: str,
        operation: str,
        elapsed_ms: float,
        items: int = 1,
        rss_delta_kb: int = 0,
        note: str = "",
    ) -> None:
        entry = {
            "ms": float(elapsed_ms),
            "items": max(1, int(items)),
            "rss_delta_kb": max(0, int(rss_delta_kb)),
            "note": note,
        }
        with self._lock:
            self.samples.setdefault((context, operation), []).append(entry)

    def add_note(self, text: str) -> None:
        with self._lock:
            self.notes.append(text)

    def update_note(self, context: str, operation: str, suffix: str) -> None:
        with self._lock:
            rows = self.samples.get((context, operation)) or []
            if rows:
                prev = rows[-1].get("note", "")
                rows[-1]["note"] = f"{prev}; {suffix}" if prev else suffix

    def summary(self) -> List[Dict[str, Any]]:
        with self._lock:
            ordered = list(self.samples.items())
        out: List[Dict[str, Any]] = []
        for (ctx, op), rows in ordered:
            times = sorted(r["ms"] for r in rows)
            n = len(times)
            p50 = statistics.median(times)
            p95 = times[min(n - 1, max(0, int(0.95 * n) - 1))] if n > 1 else times[0]
            mx = times[-1]
            avg_items = sum(r["items"] for r in rows) / n
            throughput = (avg_items / (p50 / 1000.0)) if p50 > 0 else 0.0
            max_rss = max(r["rss_delta_kb"] for r in rows)
            note = next((r["note"] for r in reversed(rows) if r.get("note")), "")
            out.append({
                "context": ctx,
                "operation": op,
                "n": n,
                "p50_ms": round(p50, 3),
                "p95_ms": round(p95, 3),
                "max_ms": round(mx, 3),
                "throughput_per_s": round(throughput, 1),
                "rss_delta_kb": max_rss,
                "note": note,
            })
        return out

    def format_markdown(self) -> str:
        lines = [
            "| Context | Operation | N | p50 (ms) | p95 (ms) | max (ms) | Throughput | RSS Δ (KB) | Notes |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for row in self.summary():
            tput = row["throughput_per_s"]
            tput_str = f"{int(round(tput)):,} /s" if tput >= 100 else f"{tput:.1f} /s"
            note = str(row["note"]).replace("|", "\\|")
            lines.append(
                f"| `{row['context']}` | `{row['operation']}` | {row['n']} | "
                f"{row['p50_ms']:.2f} | {row['p95_ms']:.2f} | {row['max_ms']:.2f} | "
                f"{tput_str} | {row['rss_delta_kb']} | {note} |"
            )
        return "\n".join(lines)


def _measure(
    collector: BenchCollector,
    context: str,
    operation: str,
    iterations: int,
    fn: Callable[[], Any],
    items: int = 1,
    note_fn: Optional[Callable[[Any], str]] = None,
) -> float:
    """Measure `fn` over `iterations` runs and return median elapsed ms."""
    medians: List[float] = []
    for _ in range(max(1, iterations)):
        rss0 = rss_kb()
        t0 = time.perf_counter()
        res = fn()
        elapsed = (time.perf_counter() - t0) * 1000.0
        delta_kb = max(0, rss_kb() - rss0)
        note = note_fn(res) if note_fn else ""
        collector.record(context, operation, elapsed, items=items, rss_delta_kb=delta_kb, note=note)
        medians.append(elapsed)
    return statistics.median(medians)


# -- Context Benchmarks ------------------------------------------------------

def run_core_context(iterations: int, collector: BenchCollector) -> None:
    """Benchmark pure-stdlib URL detection, payload normalization, and atomic JSON writes."""
    urls = [
        f"https://www.facebook.com/reel/{100000 + i}?ref=share"
        if i % 4 == 0
        else f"https://www.youtube.com/shorts/abc_{i:04d}?feature=share"
        if i % 4 == 1
        else f"https://www.tiktok.com/@creator_{i % 7}/video/{700000000 + i}"
        if i % 4 == 2
        else f"https://www.instagram.com/reel/CODE_{i:04d}/?igsh=xyz"
        for i in range(100)
    ]

    def _bench_urls() -> None:
        for u in urls:
            platforms.detect_platform(u)
            platforms.canonicalize_reel_url(u, resolve_redirects=False)

    _measure(collector, "core", "platforms.detect_and_canonicalize", iterations, _bench_urls, items=100, note_fn=lambda _: "100 mixed URLs")

    yt_prof = {"videos": [{"id": f"yt{i}", "title": f"YT {i}", "viewCountInt": 1000 + i, "likeCountInt": 50} for i in range(25)]}
    tt_prof = {"aweme_list": [{"aweme_info": {"aweme_id": f"{700 + i}", "desc": f"TT {i}", "author": {"unique_id": "tt"}, "statistics": {"play_count": 2000 + i, "digg_count": 80}}} for i in range(25)]}
    ig_prof = {"items": [{"media": {"code": f"IG{i}", "pk": f"{900 + i}", "play_count": 3000 + i, "like_count": 90, "caption": {"text": f"IG {i}"}}} for i in range(25)]}
    fb_prof = {"reels": [{"video_id": f"{500 + i}", "url": f"https://www.facebook.com/reel/{500 + i}", "view_count": 4000 + i} for i in range(25)]}

    def _bench_profile_norm() -> None:
        normalize.normalize_profile_youtube(yt_prof, "ytdoc")
        normalize.normalize_profile_tiktok(tt_prof, "ttdoc")
        normalize.normalize_profile_instagram(ig_prof, "igdoc")
        normalize.normalize_profile_facebook(fb_prof, "fbdoc")

    _measure(collector, "core", "normalize.profile_payloads", iterations, _bench_profile_norm, items=100, note_fn=lambda _: "100 items (4 plats)")

    s_yt = {"videos": [{"id": f"sy{i}", "title": f"YT {i}", "viewCountInt": 5000 + i, "channel": {"title": "Ch", "handle": "@ch"}} for i in range(20)]}
    s_serper = {"videos": [{"link": f"https://www.tiktok.com/@c{i}/video/{800 + i}", "title": f"S {i}", "views": "1200"} for i in range(20)]}
    s_fb = {"results": [{"ad_archive_id": f"ad{i}", "page_name": f"Page {i}", "snapshot": {"title": f"Ad {i}", "videos": [{"video_hd_url": "https://cdn/v.mp4"}]}} for i in range(20)]}
    s_tt = {"search_item_list": [{"aweme_info": {"aweme_id": f"st{i}", "desc": f"TT {i}", "author": {"unique_id": f"u{i}"}, "statistics": {"play_count": 9000}}} for i in range(20)]}
    s_ig = {"reels": [{"code": f"C{i}", "id": f"si{i}", "play_count": 7000, "user": {"username": f"ig{i}"}, "caption": {"text": f"Cap {i}"}} for i in range(20)]}
    no_oembed = lambda _u, _p, fallback: (fallback or "creator", "https://www.tiktok.com/@creator")

    def _bench_search_norm() -> None:
        normalize.normalize_search_youtube(s_yt, "acne")
        normalize.normalize_search_serper(s_serper, "acne", "google", infer_author_fn=no_oembed)
        normalize.normalize_search_fb_ads(s_fb, "acne")
        normalize.normalize_search_tiktok(s_tt, "acne")
        normalize.normalize_search_instagram(s_ig, "acne")

    _measure(collector, "core", "normalize.search_payloads", iterations, _bench_search_norm, items=100, note_fn=lambda _: "100 items (5 plats)")

    vtt_payload = {
        "transcript": "WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nXin chào các bạn\n\n2\n00:00:02.000 --> 00:00:04.500\nĐây là benchmark transcript\n"
    }

    def _bench_vtt() -> None:
        for _ in range(100):
            normalize.extract_transcript_text(vtt_payload, "tiktok")

    _measure(collector, "core", "normalize.transcript_webvtt", iterations, _bench_vtt, items=100, note_fn=lambda _: "100 WebVTT payloads")

    sample_json = {
        "reels": [
            {"video_id": f"id_{i}", "views": 1000 * i, "title": f"Benchmark Reel #{i}", "tags": ["a", "b"]}
            for i in range(50)
        ]
    }
    with tempfile.TemporaryDirectory(prefix="va-prof-core-") as tmp:
        out_path = Path(tmp) / "summary.json"
        _measure(
            collector,
            "core",
            "runtime.atomic_write_json",
            iterations,
            lambda: runtime.atomic_write_json(out_path, sample_json),
            items=50,
            note_fn=lambda _: "50-reel atomic JSON replace",
        )


def run_profile_context(iterations: int, collector: BenchCollector, workers: int = 5) -> None:
    """Benchmark profile_research serial vs parallel fan-out and SingleFlight stampede collapse."""
    from tools.loop.viral_analyzer.profile_research import collect as prof_collect, pipeline as prof_pipeline
    from tools.loop.viral_analyzer.profile_research.config import StorageConfig, ViralAnalyzerConfig

    fresh_iso = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    targets = [
        {"handle": f"chan_{i}", "url": f"https://www.facebook.com/chan_{i}", "platform": "facebook"}
        for i in range(10)
    ]

    def _fake_fetch(target: Dict[str, Any], *_args: Any, **_kwargs: Any) -> List[Dict[str, Any]]:
        time.sleep(0.015)
        h = target["handle"]
        return [
            {
                "video_id": f"{h}_{j}",
                "url": f"https://www.facebook.com/reel/{h}_{j}",
                "view_count": 500 + j * 2500,
                "likes": 40,
                "comments": 5,
                "shares": 2,
                "description": f"Benchmark {h} #{j}",
                "creation_time": fresh_iso,
                "_source": "glasser",
            }
            for j in range(25)
        ]

    with tempfile.TemporaryDirectory(prefix="va-prof-profile-") as tmp:
        tmp_path = Path(tmp)
        cfg = ViralAnalyzerConfig(
            storage=StorageConfig(video_dir=tmp_path / "videos", output_file=tmp_path / "out.json"),
            targets=targets,
        )

        def _run_with_workers(w: int) -> Dict[str, Any]:
            ctx = runtime.EngineContext(max_workers=w, submit_fn=runtime.submit_with_context)
            with (
                patch.object(prof_pipeline, "fetch_target_reels", side_effect=_fake_fetch),
                patch.object(prof_pipeline, "persist_to_database"),
                redirect_stdout(io.StringIO()),
            ):
                return prof_pipeline.run_analyzer_pipeline(cfg, transcribe=False, max_workers=w, ctx=ctx)

        serial_ms = _measure(
            collector,
            "profile",
            "profile.pipeline_serial_1w",
            iterations,
            lambda: _run_with_workers(1),
            items=250,
            note_fn=lambda r: f"10 targets, {len(r['all_reels'])} reels @15ms IO",
        )
        par_op = f"profile.pipeline_parallel_{workers}w"
        par_ms = _measure(
            collector,
            "profile",
            par_op,
            iterations,
            lambda: _run_with_workers(workers),
            items=250,
            note_fn=lambda r: f"10 targets, {len(r['all_reels'])} reels",
        )
        if par_ms > 0:
            collector.update_note("profile", par_op, f"{serial_ms / par_ms:.2f}x vs 1w")

    def _stampede() -> Tuple[int, int]:
        sf = runtime.SingleFlight()
        ctx = runtime.EngineContext(single_flight=sf)
        mem_cache: Dict[str, Tuple[List[Dict[str, Any]], str, str]] = {}
        upstream_calls = 0
        guard = threading.Lock()
        stampede_targets = [{"handle": f"dup_{i % 2}", "url": f"https://www.facebook.com/dup_{i % 2}", "platform": "facebook"} for i in range(12)]

        def _fake_read(handle: str, **_kwargs: Any):
            return mem_cache.get(handle)

        def _fake_write(handle: str, reels: List[Dict[str, Any]], status: str = "ok", **_kwargs: Any):
            mem_cache[handle] = (reels, status, "postgres")

        def _fake_exec(*_args: Any, **kwargs: Any):
            nonlocal upstream_calls
            time.sleep(0.020)
            with guard:
                upstream_calls += 1
            temp_out: Path = kwargs["temp_out"]
            runtime.atomic_write_json(temp_out, {"reels": [{"video_id": "v1", "view_count": 1000}]})
            return True, None, None

        fake_cc = SimpleNamespace(record_cost_event=lambda **_k: None)
        with (
            patch.object(prof_collect, "read_cached_reels", side_effect=_fake_read),
            patch.object(prof_collect, "write_cached_reels", side_effect=_fake_write),
            patch.object(prof_collect, "execute_glasser_query", side_effect=_fake_exec),
            patch.dict(sys.modules, {"tools.app.backend.telemetry.cost_control": fake_cc}),
            redirect_stdout(io.StringIO()),
        ):
            with ThreadPoolExecutor(max_workers=12) as pool:
                list(pool.map(lambda t: prof_collect.fetch_target_reels(t, SimpleNamespace(), legacy_cache=False, ctx=ctx), stampede_targets))
        return len(stampede_targets), upstream_calls

    _measure(
        collector,
        "profile",
        "profile.single_flight_stampede",
        iterations,
        _stampede,
        items=12,
        note_fn=lambda res: f"upstream={res[1]}/{res[0]} collapsed",
    )


def run_video_context(iterations: int, collector: BenchCollector) -> None:
    """Benchmark video_research topic/prompt generation, single-reel pipeline, FFmpeg, and locked retention."""
    from tools.loop.viral_analyzer.video_research import collect as vid_collect, pipeline as vid_pipeline

    sample_reels = [
        {
            "video_id": f"v{i}",
            "url": f"https://www.facebook.com/reel/{2000 + i}",
            "platform": "facebook",
            "views": 1000 + i * 3000,
            "velocity_per_hour": 120.0 + i * 25,
            "current_pool": min(5, 1 + i // 4),
            "pool_name": "niche",
            "author_handle": f"creator_{i % 4}",
            "title": f"Viral clinical explainer #{i}",
            "transcript": f"Transcript text explaining issue #{i} with practical steps.",
        }
        for i in range(20)
    ]

    agent_json = json.dumps([
        {
            "title": f"Topic {i}",
            "hook": f"Hook {i}",
            "angle": "Storytelling",
            "why_viral": "High retention",
            "outline": ["Open", "Explain", "CTA"],
            "format": "Reels 15s UGC",
            "source_urls": [sample_reels[i]["url"]],
        }
        for i in range(3)
    ])

    def _bench_topics() -> List[Dict[str, Any]]:
        heur = vid_pipeline.heuristic_video_analyses("Bench", sample_reels, limit=20)
        prompt = vid_pipeline.build_video_structure_prompt("Bench", [{"name": "c", "url": "https://fb.com/c"}], sample_reels)
        parsed = vid_pipeline.parse_video_analyses(agent_json, heur, reels=sample_reels, sheet_name="Bench")
        for topic in parsed:
            vid_pipeline.format_director_prompt(topic, sheet_name="Bench")
        return parsed if prompt else []

    _measure(collector, "video", "video.topics_and_prompts_20", iterations, _bench_topics, items=20, note_fn=lambda r: f"20 reels -> {len(r)} parsed+formatted")

    with tempfile.TemporaryDirectory(prefix="va-prof-video-") as tmp:
        tmp_path = Path(tmp)
        single_ctx = runtime.EngineContext(agent_runner=lambda _prompt, **_kwargs: agent_json)

        def _fake_dl(_url: str, vid: Optional[str], _log: Any) -> Path:
            p = tmp_path / f"tmp_{vid or 'r'}.mp4"
            p.write_bytes(b"mp4bytes")
            return p

        def _bench_single_reel() -> Dict[str, Any]:
            with (
                patch.object(vid_pipeline, "fetch_reel_transcript", return_value="Mock transcript for single reel benchmark"),
                patch.object(vid_pipeline, "_download_reel_video", side_effect=_fake_dl),
                patch.object(vid_pipeline, "_extract_video_frames", return_value=[]),
            ):
                return vid_pipeline.research_single_reel(
                    "https://www.facebook.com/reel/123456789",
                    sheet_name="Bench Sheet",
                    cwd=tmp_path,
                    ctx=single_ctx,
                )

        _measure(
            collector,
            "video",
            "video.research_single_reel_mock",
            iterations,
            _bench_single_reel,
            items=1,
            note_fn=lambda r: f"topics={len(r.get('topics', []))}, injected agent_runner",
        )

        # Real FFmpeg frame extraction benchmark (1s synthetic 360x640 clip)
        from tools.loop.viral_analyzer.video_research.transcriber.local import ffmpeg_bin

        ffmpeg_path = ffmpeg_bin() if shutil.which("ffmpeg") else ""
        sample_mp4 = tmp_path / "sample.mp4"
        if ffmpeg_path:
            gen = subprocess.run(
                [ffmpeg_path, "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=6", str(sample_mp4)],
                capture_output=True,
            )
            if gen.returncode == 0 and sample_mp4.exists():
                def _bench_ffmpeg() -> int:
                    fdir = tmp_path / "frames"
                    frames = vid_collect._extract_video_frames(sample_mp4, fdir, count=4)
                    for f in frames:
                        f.unlink(missing_ok=True)
                    return len(frames)

                _measure(
                    collector,
                    "video",
                    "video.ffmpeg_extract_frames",
                    iterations,
                    _bench_ffmpeg,
                    items=1,
                    note_fn=lambda cnt: f"{cnt} JPEG frames (real ffmpeg)",
                )
        else:
            collector.add_note("video.ffmpeg_extract_frames skipped: ffmpeg not found in PATH")

        # 8-thread flock-protected retention registration + purge
        ret_dir = tmp_path / "retention"
        ret_dir.mkdir(parents=True, exist_ok=True)
        now_dt = datetime.now(timezone.utc)

        def _bench_retention() -> int:
            def _reg(i: int) -> None:
                p = ret_dir / f"v_{i}.mp4"
                p.write_bytes(b"mp4")
                vid_collect.register_video(ret_dir, f"v_{i}", p, retention_days=7, now=now_dt)

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(_reg, range(8)))
            _purged, retained = vid_collect.purge_expired_videos(ret_dir, retention_days=7, now=now_dt)
            return retained

        _measure(
            collector,
            "video",
            "video.retention_flock_8t",
            iterations,
            _bench_retention,
            items=8,
            note_fn=lambda cnt: f"{cnt} locked manifest entries + purge",
        )


def run_keyword_context(iterations: int, collector: BenchCollector, workers: int = 5) -> None:
    """Benchmark 5-platform keyword search serial vs parallel fan-out and offline campaign pipeline."""
    from tools.loop.viral_analyzer.keyword_research import config as hc, pipeline as kw_pipeline
    from tools.loop.viral_analyzer.keyword_research.campaign import generate as hg, scrape as vs, verify as hv

    def _fake_glasser(provider: str, endpoint: str, version: int, payload: Dict[str, Any], *_a: Any, **_k: Any):
        time.sleep(0.012)
        q = payload.get("query") or payload.get("q") or "q"
        if provider == "serper":
            return {"videos": [{"link": f"https://www.tiktok.com/@auth/video/{abs(hash((endpoint, q))) % 999999}", "title": q, "views": "15000"}]}, "glasser_api", None
        if "youtube" in endpoint:
            return {"videos": [{"id": f"yt_{abs(hash(q)) % 9999}", "title": q, "viewCountInt": 12000, "channel": {"title": "Ch", "handle": "@ch"}}]}, "glasser_api", None
        if "tiktok" in endpoint:
            return {"search_item_list": [{"aweme_info": {"aweme_id": f"tt_{abs(hash(q)) % 9999}", "desc": q, "author": {"unique_id": "tt"}, "statistics": {"play_count": 22000}}}]}, "glasser_api", None
        return {"reels": [{"code": f"ig_{abs(hash(q)) % 9999}", "id": "ig1", "play_count": 18000, "user": {"username": "ig"}, "caption": {"text": q}}]}, "glasser_api", None

    with tempfile.TemporaryDirectory(prefix="va-prof-kw-") as tmp:
        run_dir = Path(tmp) / "search_run"

        def _search(w: int) -> Dict[str, Any]:
            ctx = runtime.EngineContext(max_workers=w, submit_fn=runtime.submit_with_context)
            with (
                patch.object(kw_pipeline, "_glasser_run_json", side_effect=_fake_glasser),
                patch.object(kw_pipeline, "_enrich_creator_followers"),
            ):
                return kw_pipeline.run_viral_video_search("gyno conditions", run_dir, options={}, ctx=ctx)

        serial_ms = _measure(
            collector,
            "keyword",
            "keyword.search_5plat_serial_1w",
            iterations,
            lambda: _search(1),
            items=15,
            note_fn=lambda r: f"3x5=15 calls @12ms IO, reels={len(r['reels'])}",
        )
        par_op = f"keyword.search_5plat_parallel_{workers}w"
        par_ms = _measure(
            collector,
            "keyword",
            par_op,
            iterations,
            lambda: _search(workers),
            items=15,
            note_fn=lambda r: f"3x5=15 calls, reels={len(r['reels'])}",
        )
        if par_ms > 0:
            collector.update_note("keyword", par_op, f"{serial_ms / par_ms:.2f}x vs 1w")

        def _bench_campaign_flow(idx_holder: List[int]) -> bool:
            idx_holder[0] += 1
            root = Path(tmp) / f"camp_{idx_holder[0]}"
            root.mkdir(parents=True, exist_ok=True)
            (root / "product-marketing.json").write_text(json.dumps({
                "marketing_goal": "Find packaging buyers",
                "product": {"catalog": [{"name": "Wedding Cards"}]},
            }))
            schema = root / "schema.json"
            schema.write_text(json.dumps({
                "provider": "scrapecreators",
                "currency": "USD",
                "endpoints": [{
                    "platform": "instagram", "kind": "hashtag",
                    "endpoint": "/v1/instagram/search/hashtag", "method_field": "hashtag",
                    "price_usd": "0.0019", "fixed": {"limit": 3}, "max_results": 3, "ranking_filter": "reels",
                }],
            }))
            b_res, _ = hg.build_prompt(SimpleNamespace(
                project=str(root), run="run-1", platform="instagram", market_language="vi",
                application="wedding", hypothesis=None, new_test=None, seed_evidence=None, max_candidates=4,
            ))
            ctx_doc = json.loads((root / b_res["context_path"]).read_text())
            resp_path = root / "resp.json"
            resp_path.write_text(json.dumps({
                "schema_version": 1, "campaign": ctx_doc["campaign"], "run_id": "run-1",
                "context_sha256": ctx_doc["context_sha256"], "platform": "instagram",
                "candidates": [{
                    "id": "c1", "kind": "hashtag", "text": "#thiepcuoi", "language": "vi",
                    "application": "wedding", "connection": "buyer", "context_sources": ["product-marketing.json"],
                    "rationale": "fit", "alternative_meanings": [], "priority": 1,
                    "origin": "generated_unverified", "evidence_ref": None,
                }],
            }))
            hg.import_response(SimpleNamespace(project=str(root), run="run-1", response=str(resp_path)))
            hv.plan_probes(SimpleNamespace(project=str(root), run="run-1", schema=str(schema), max_calls=5, ceiling=None))
            fake_payload = {"run_id": "r1", "run_url": "https://app.glasser.ai/r1", "charge_usd": "0.0019", "data": [
                {"id": f"v{k}", "url": f"https://www.instagram.com/reel/v{k}/", "caption": "thiep cuoi", "owner": {"username": f"u{k}"}}
                for k in range(3)
            ]}
            hv.collect_probes(SimpleNamespace(
                project=str(root), run="run-1", plan=None, execute=True, ceiling="1.00", resume=False,
                run_func=lambda _c, _k: {"returncode": 0, "stdout": json.dumps(fake_payload), "stderr": ""},
            ))
            hv.build_review_prompt(SimpleNamespace(project=str(root), run="run-1", plan=None))
            plan_doc = json.loads((hc.artifact_directory(root, "run-1") / "plan.json").read_text())
            call_id = plan_doc["calls"][0]["call_id"]
            samples = json.loads((hc.artifact_directory(root, "run-1") / "calls" / f"{call_id}.samples.json").read_text())
            rev_path = root / "review.json"
            rev_path.write_text(json.dumps({
                "schema_version": 1, "campaign": ctx_doc["campaign"], "run_id": "run-1",
                "phase": "probe", "reviewer": "bench", "reviewer_type": "agent",
                "checked_at": "2026-11-19T08:00:00Z", "prompt_version": hc.PROMPT_VERSION, "model": "bench",
                "evaluations": [{
                    "call_id": call_id, "reason": "bench",
                    "samples": [{
                        "sample_id": s["sample_id"], "label": "direct_application", "reason": "fit",
                        "evidence": [s["url"]], "observed": {"application": "wedding", "language": "vi", "tag_present": True},
                    } for s in samples["reviewed"]],
                }],
            }))
            hv.record_review(SimpleNamespace(project=str(root), run="run-1", review=str(rev_path), plan=None, correction=False, human_corrected=False))
            sc_res, _ = vs.scrape(SimpleNamespace(project=str(root), run="run-1", schema=str(schema), platform=None, limit=None, ceiling=None, execute=False, resume=False))
            return bool(sc_res["ok"])

        counter = [0]
        _measure(
            collector,
            "keyword",
            "keyword.campaign_flow_offline",
            iterations,
            lambda: _bench_campaign_flow(counter),
            items=7,
            note_fn=lambda ok: f"7-stage CLI flow ok={ok}",
        )


def run_concurrency_context(iterations: int, collector: BenchCollector) -> None:
    """Benchmark BoundedSemaphore throughput, SingleFlight key contention, and temp path allocation."""
    def _bench_sem() -> None:
        sem = threading.BoundedSemaphore(8)

        def _work(_i: int) -> None:
            with sem:
                time.sleep(0.010)

        with ThreadPoolExecutor(max_workers=24) as pool:
            list(pool.map(_work, range(24)))

    _measure(collector, "concurrency", "runtime.glasser_semaphore_8", iterations, _bench_sem, items=24, note_fn=lambda _: "24 tasks @10ms, cap=8")

    def _bench_sf() -> int:
        sf = runtime.SingleFlight()
        store: Dict[str, int] = {}
        misses = 0
        guard = threading.Lock()

        def _work(i: int) -> int:
            k = f"k_{i % 4}"
            with sf.acquire(k):
                nonlocal misses
                if k not in store:
                    time.sleep(0.010)
                    with guard:
                        misses += 1
                    store[k] = i
                return store[k]

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(_work, range(16)))
        return misses

    _measure(collector, "concurrency", "runtime.single_flight_16t_4k", iterations, _bench_sf, items=16, note_fn=lambda m: f"16t on 4 keys -> misses={m}")

    with tempfile.TemporaryDirectory(prefix="va-prof-tmp-") as tmp:
        base = Path(tmp)
        _measure(
            collector,
            "concurrency",
            "runtime.unique_temp_path_1k",
            iterations,
            lambda: [runtime.unique_temp_path("bench", ".json", base_dir=base) for _ in range(1000)],
            items=1000,
            note_fn=lambda _: "1,000 temp path allocs",
        )


def run_cache_context(iterations: int, collector: BenchCollector, dsn: Optional[str] = None) -> None:
    """Benchmark batched PostgreSQL cache reads/writes against *_test database."""
    target_dsn = dsn or os.environ.get("TEST_DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/aibrand_test"
    db_name = target_dsn.split("/")[-1].split("?")[0]
    if not db_name.endswith("_test"):
        collector.add_note(f"cache skipped: refusing non-test DB {db_name!r}")
        return

    os.environ["DATABASE_URL"] = target_dsn
    try:
        import psycopg  # noqa: F401
        from tools.app.backend.db import close_pools, init_schema, tx
        from tools.loop.viral_analyzer import cache
    except Exception as exc:
        collector.add_note(f"cache skipped: DB dependency unavailable ({exc})")
        return

    try:
        close_pools()
        init_schema(target_dsn)
    except Exception as exc:
        collector.add_note(f"cache skipped: Postgres unreachable ({exc})")
        return

    reels = [
        {
            "video_id": f"bench_v_{i}",
            "platform": "facebook",
            "url": f"https://www.facebook.com/reel/99000{i}",
            "author_handle": f"bench_creator_{i % 5}",
            "title": f"Bench Video {i}",
            "current_pool": (i % 5) + 1,
            "published_at": "2026-11-19T00:00:00+00:00",
            "views": 1000 * (i + 1),
            "likes": 50 * (i + 1),
            "comments": 5 * (i + 1),
            "shares": 2 * (i + 1),
            "velocity_per_hour": 250.0,
            "comment_ratio": 0.1,
        }
        for i in range(50)
    ]
    sample_cache_reels = reels[:20]
    follower_entries = [(f"https://www.facebook.com/bench_creator_{i}", 10_000 + i * 100) for i in range(25)]
    follower_urls = [u for u, _ in follower_entries]

    try:
        def _bench_persist() -> int:
            cache.persist_to_database(reels)
            return len(reels)

        _measure(
            collector,
            "cache",
            "cache.persist_batch_50_reels",
            iterations,
            _bench_persist,
            items=50,
            note_fn=lambda cnt: f"{cnt} videos + snapshots batched",
        )

        def _bench_prof_cache() -> int:
            cache.write_cached_reels("bench_prof_handle", sample_cache_reels, status="ok", profile_url="https://www.facebook.com/bench_prof_handle")
            hit = cache.read_cached_reels("bench_prof_handle", legacy_cache=False)
            return len(hit[0]) if hit else 0

        _measure(collector, "cache", "cache.profile_cache_rw_20", iterations, _bench_prof_cache, items=20, note_fn=lambda cnt: f"20 reels upsert+read ({cnt})")

        def _bench_followers() -> int:
            cache.write_cached_followers(follower_entries)
            hits = cache.read_cached_followers(follower_urls)
            return len(hits)

        _measure(collector, "cache", "cache.followers_batch_rw_25", iterations, _bench_followers, items=25, note_fn=lambda cnt: f"25 URLs upsert+read ({cnt})")
    finally:
        try:
            with tx() as conn:
                conn.execute("DELETE FROM metric_snapshots WHERE video_id LIKE 'facebook:bench_v_%'")
                conn.execute("DELETE FROM videos WHERE id LIKE 'facebook:bench_v_%'")
                conn.execute("DELETE FROM profile_cache WHERE handle = 'bench_prof_handle' OR handle LIKE 'followers:https://www.facebook.com/bench_creator_%'")
            close_pools()
        except Exception:
            pass


def run_benchmarks(
    contexts: Sequence[str],
    iterations: int = 5,
    workers: int = 5,
    use_cprofile: bool = False,
    dsn: Optional[str] = None,
) -> Dict[str, Any]:
    """Run selected isolated benchmark contexts and return Markdown table + structured rows."""
    global ENABLED, ACTIVE_CONTEXTS
    prev_enabled, prev_contexts = ENABLED, set(ACTIVE_CONTEXTS)
    configure(enabled=False)
    collector = BenchCollector()
    cprofile_text = ""
    peak_kb = 0.0

    def _exec() -> None:
        if "core" in contexts:
            run_core_context(iterations, collector)
        if "profile" in contexts:
            run_profile_context(iterations, collector, workers=workers)
        if "video" in contexts:
            run_video_context(iterations, collector)
        if "keyword" in contexts:
            run_keyword_context(iterations, collector, workers=workers)
        if "concurrency" in contexts:
            run_concurrency_context(iterations, collector)
        if "cache" in contexts:
            run_cache_context(iterations, collector, dsn=dsn)

    try:
        if use_cprofile:
            _, cprofile_text, peak_kb = profile_callable(_exec)
        else:
            _exec()
    finally:
        ENABLED, ACTIVE_CONTEXTS = prev_enabled, prev_contexts

    return {
        "contexts": list(contexts),
        "iterations": iterations,
        "workers": workers,
        "table": collector.format_markdown(),
        "summary": collector.summary(),
        "notes": collector.notes,
        "cprofile": cprofile_text,
        "peak_kb": round(peak_kb, 1),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark & profile tools.loop.viral_analyzer subsystems")
    parser.add_argument("--context", default="core,profile,video,keyword,concurrency", help=f"Comma-separated: {','.join(ALL_CONTEXTS)},all")
    parser.add_argument("--iterations", type=int, default=5, help="Iterations per operation (default: 5)")
    parser.add_argument("--workers", type=int, default=5, help="Parallel worker pool size for fan-out benchmarks (default: 5)")
    parser.add_argument("--cprofile", action="store_true", help="Attach cProfile cumulative-time table + tracemalloc peak")
    parser.add_argument("--dsn", default=None, help="Override Postgres DSN (must end with _test)")
    parser.add_argument("--json-out", default=None, help="Optional file path to write structured JSON results")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    raw = args.context.strip().lower()
    selected = list(ALL_CONTEXTS) if raw == "all" else [c.strip() for c in raw.split(",") if c.strip() in ALL_CONTEXTS]
    if not selected:
        raise SystemExit(f"No valid contexts in {args.context!r}. Choose from {', '.join(ALL_CONTEXTS)}, all.")

    t0 = time.perf_counter()
    res = run_benchmarks(
        selected,
        iterations=max(1, args.iterations),
        workers=max(1, args.workers),
        use_cprofile=args.cprofile,
        dsn=args.dsn,
    )
    elapsed = time.perf_counter() - t0
    res["elapsed_s"] = round(elapsed, 3)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"# Viral Analyzer Profile ({', '.join(selected)}) — {elapsed:.2f}s (N={args.iterations}, workers={args.workers})\n")
    print(res["table"])
    if res["notes"]:
        print("\n## Notes\n" + "\n".join(f"- {n}" for n in res["notes"]))
    if res["cprofile"]:
        print(f"\n## cProfile (tracemalloc peak: {res['peak_kb']:.1f} KB)\n```text\n{res['cprofile']}```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
