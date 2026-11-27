#!/usr/bin/env python3
"""Benchmark tools/app/backend/video_engine/edit.py concurrency on this machine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any, Callable

from tools.app.backend.video_engine.edit import (
    EFFECT_EDITOR,
    WORKSPACE,
    _prepare_user_source,
    _resolve_editor_python,
    _run_rea_decompose,
    edit_video,
    resolve_rea_video_bin,
)

SOURCE_VIDEO = WORKSPACE / "local/aibrand/rea-video-runs/ref-cache/a0c4f7625700f98c/clip_25s.mp4"
CONFIG_TEMPLATE = WORKSPACE / "local/aibrand/rea-video-runs/edit_9ee2039296/edit_config.json"
TEMP_ROOT = Path("/tmp/video_edit_bench")
RESULTS_PATH = Path(
    "/home/vinh/.gemini/antigravity-cli/brain/07a0395b-5365-4c77-9715-ff033602ea62/scratch/bench_results.json"
)


def read_mem_available_mb() -> float:
    """Read MemAvailable in MiB from /proc/meminfo."""
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                kb = int(line.split()[1])
                return kb / 1024.0
    return 0.0


class ResourceMonitor:
    """Sample MemAvailable delta and 1m loadavg every 0.5s."""

    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self.baseline_mem_mb = read_mem_available_mb()
        self.peak_ram_delta_mb = 0.0
        self.peak_loadavg_1m = os.getloadavg()[0]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            avail = read_mem_available_mb()
            delta = max(0.0, self.baseline_mem_mb - avail)
            if delta > self.peak_ram_delta_mb:
                self.peak_ram_delta_mb = delta
            load1 = os.getloadavg()[0]
            if load1 > self.peak_loadavg_1m:
                self.peak_loadavg_1m = load1
            self._stop.wait(self.interval)

    def __enter__(self) -> "ResourceMonitor":
        self._thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)


def run_batch(
    stage: str,
    n: int,
    worker_fn: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    """Run n concurrent workers and collect latency, throughput, and resource metrics."""
    latencies: list[float] = []
    errors: list[str] = []
    extras: list[dict[str, Any]] = []

    t0 = time.monotonic()
    with ResourceMonitor() as mon:
        with ThreadPoolExecutor(max_workers=n) as pool:
            futs = [pool.submit(worker_fn, idx) for idx in range(n)]
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                    latencies.append(float(res["elapsed_sec"]))
                    if not res.get("ok", False):
                        errors.append(str(res.get("error") or "worker returned ok=False"))
                    extras.append(res)
                except Exception as exc:
                    errors.append(repr(exc))
    makespan = time.monotonic() - t0

    ok_count = n - len(errors)
    throughput_vpm = (ok_count / makespan * 60.0) if makespan > 0 and ok_count > 0 else 0.0
    avg_lat = (sum(latencies) / len(latencies)) if latencies else 0.0
    max_lat = max(latencies) if latencies else 0.0

    summary = {
        "stage": stage,
        "n": n,
        "ok_count": ok_count,
        "error_count": len(errors),
        "errors": errors[:3],
        "makespan_sec": round(makespan, 2),
        "avg_latency_sec": round(avg_lat, 2),
        "max_latency_sec": round(max_lat, 2),
        "throughput_vpm": round(throughput_vpm, 2),
        "peak_ram_delta_mb": round(mon.peak_ram_delta_mb, 1),
        "peak_loadavg_1m": round(mon.peak_loadavg_1m, 2),
        "details": extras,
    }
    print(
        f"[{stage}] N={n}: ok={ok_count}/{n}, makespan={summary['makespan_sec']}s, "
        f"avg={summary['avg_latency_sec']}s, max={summary['max_latency_sec']}s, "
        f"tput={summary['throughput_vpm']} vid/min, ram+={summary['peak_ram_delta_mb']}MB, "
        f"load={summary['peak_loadavg_1m']}",
        flush=True,
    )
    if errors:
        print(f"  errors: {errors[:3]}", flush=True)
    return summary


def main() -> None:
    assert SOURCE_VIDEO.exists(), f"Missing source video: {SOURCE_VIDEO}"
    assert CONFIG_TEMPLATE.exists(), f"Missing config template: {CONFIG_TEMPLATE}"

    rea_bin = resolve_rea_video_bin()
    editor_py = _resolve_editor_python(rea_bin)
    base_cfg = json.loads(CONFIG_TEMPLATE.read_text(encoding="utf-8"))

    print(f"Source: {SOURCE_VIDEO}")
    print(f"rea_bin: {rea_bin}")
    print(f"editor_py: {editor_py}")
    print(f"Baseline MemAvailable: {read_mem_available_mb():.1f} MiB, load1: {os.getloadavg()[0]:.2f}")

    if TEMP_ROOT.exists():
        shutil.rmtree(TEMP_ROOT)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "source_video": str(SOURCE_VIDEO),
        "rea_bin": str(rea_bin) if rea_bin else None,
        "editor_py": editor_py,
        "batches": [],
    }

    try:
        # Stage A: _prepare_user_source()
        for n in (1, 2, 4, 8):
            stage_dir = TEMP_ROOT / f"stage_a_n{n}"
            stage_dir.mkdir(parents=True, exist_ok=True)

            def worker_a(idx: int, root: Path = stage_dir) -> dict[str, Any]:
                wdir = root / f"job_{idx}"
                t_start = time.monotonic()
                out = _prepare_user_source(SOURCE_VIDEO, wdir, editor_py)
                elapsed = time.monotonic() - t_start
                ok = out is not None and (wdir / "user_probe.json").exists()
                return {
                    "elapsed_sec": round(elapsed, 3),
                    "ok": ok,
                    "transcript_none": out.get("transcript_path") is None if out else True,
                }

            batch = run_batch("A:_prepare_user_source", n, worker_a)
            results["batches"].append(batch)
            shutil.rmtree(stage_dir, ignore_errors=True)

        # Stage B: _run_rea_decompose()
        if rea_bin is not None:
            for n in (1, 2, 4):
                stage_dir = TEMP_ROOT / f"stage_b_n{n}"
                stage_dir.mkdir(parents=True, exist_ok=True)

                def worker_b(idx: int, root: Path = stage_dir) -> dict[str, Any]:
                    out_dir = root / f"job_{idx}"
                    t_start = time.monotonic()
                    ok = _run_rea_decompose(SOURCE_VIDEO, out_dir, rea_bin, timeout_sec=240)
                    elapsed = time.monotonic() - t_start
                    return {"elapsed_sec": round(elapsed, 3), "ok": ok}

                batch = run_batch("B:_run_rea_decompose", n, worker_b)
                results["batches"].append(batch)
                shutil.rmtree(stage_dir, ignore_errors=True)
                if batch["error_count"] > 0 or batch["makespan_sec"] > 300:
                    break

        # Stage C: effect_editor.py full render
        for n in (1, 2, 3, 4, 6, 8):
            stage_dir = TEMP_ROOT / f"stage_c_n{n}"
            stage_dir.mkdir(parents=True, exist_ok=True)

            def worker_c(idx: int, root: Path = stage_dir) -> dict[str, Any]:
                jdir = root / f"job_{idx}"
                jdir.mkdir(parents=True, exist_ok=True)
                cfg = dict(base_cfg)
                cfg["input_video"] = str(SOURCE_VIDEO)
                out_mp4 = jdir / "output.mp4"
                cfg["output_video"] = str(out_mp4)
                cfg_path = jdir / "edit_config.json"
                cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

                t_start = time.monotonic()
                proc = subprocess.run(
                    [editor_py, str(EFFECT_EDITOR), str(cfg_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                elapsed = time.monotonic() - t_start
                ok = proc.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 0
                err = None if ok else (proc.stderr[-500:] if proc.stderr else f"rc={proc.returncode}")
                return {
                    "elapsed_sec": round(elapsed, 3),
                    "ok": ok,
                    "size_bytes": out_mp4.stat().st_size if out_mp4.exists() else 0,
                    "error": err,
                }

            batch = run_batch("C:effect_editor", n, worker_c)
            results["batches"].append(batch)
            shutil.rmtree(stage_dir, ignore_errors=True)
            if batch["error_count"] > 0 or batch["makespan_sec"] > 300:
                print(f"Stopping Stage C sweep at N={n} (errors={batch['error_count']}, makespan={batch['makespan_sec']}s)")
                break

        # Stage D: Full end-to-end edit_video()
        prompt = (
            "Apply a subtle color grade and add a 2-second top title card "
            "'BENCH TEST' from 0.5s to 2.5s. Aim for 1-pass completion."
        )
        for n in (1, 2):
            stage_dir = TEMP_ROOT / f"stage_d_n{n}"
            stage_dir.mkdir(parents=True, exist_ok=True)

            def worker_d(idx: int, root: Path = stage_dir) -> dict[str, Any]:
                jdir = root / f"job_{idx}"
                wdir = jdir / "work"
                out_mp4 = jdir / "output.mp4"
                t_start = time.monotonic()
                try:
                    edit_video(
                        source_video_path=SOURCE_VIDEO,
                        prompt=prompt,
                        output_path=out_mp4,
                        reference_video_url=None,
                        work_dir=wdir,
                        timeout_sec=240,
                        pre_decompose=True,
                    )
                    elapsed = time.monotonic() - t_start
                    ok = out_mp4.exists() and out_mp4.stat().st_size > 0
                    return {
                        "elapsed_sec": round(elapsed, 3),
                        "ok": ok,
                        "size_bytes": out_mp4.stat().st_size if out_mp4.exists() else 0,
                    }
                except Exception as exc:
                    elapsed = time.monotonic() - t_start
                    return {"elapsed_sec": round(elapsed, 3), "ok": False, "error": repr(exc)}

            batch = run_batch("D:edit_video_e2e", n, worker_d)
            results["batches"].append(batch)
            shutil.rmtree(stage_dir, ignore_errors=True)
            if batch["error_count"] > 0:
                print(f"Stopping Stage D sweep at N={n} due to error")
                break
    finally:
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Saved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
