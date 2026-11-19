"""Shared concurrency, atomic I/O, and extensible execution context primitives."""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Callable, Dict, Iterator, Optional
import uuid


def unique_temp_path(
    prefix: str,
    suffix: str = ".json",
    base_dir: Optional[Path] = None,
) -> Path:
    """Return a collision-free temp path scoped by PID, thread ID, and random hex."""
    safe_prefix = "".join(c if c.isalnum() or c in "-_." else "_" for c in (prefix or "tmp"))
    directory = Path(base_dir) if base_dir is not None else Path(tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{safe_prefix}_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}{suffix}"


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write UTF-8 text via a unique sibling temp file and os.replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def atomic_write_json(path: Path, data: Any) -> None:
    """Atomically serialize JSON data to disk via os.replace."""
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


class SingleFlight:
    """In-process per-key mutex deduplicating concurrent cache-miss fetches."""

    # ponytail: in-process single-flight; use pg_advisory_xact_lock(hashtext(key)) if cross-worker stampedes matter.
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: Dict[str, list[Any]] = {}

    @contextmanager
    def acquire(self, key: str) -> Iterator[None]:
        with self._guard:
            entry = self._locks.get(key)
            if entry is None:
                entry = [threading.Lock(), 0]
                self._locks[key] = entry
            entry[1] += 1
            lock: threading.Lock = entry[0]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._guard:
                entry = self._locks.get(key)
                if entry is not None:
                    entry[1] -= 1
                    if entry[1] <= 0:
                        self._locks.pop(key, None)


GLASSER_SEMAPHORE = threading.BoundedSemaphore(
    max(1, int(os.environ.get("VIRAL_GLASSER_MAX_CONCURRENCY", "8")))
)
SINGLE_FLIGHT = SingleFlight()


def submit_with_context(executor: Any, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Submit a callable to an executor preserving ContextVars and backend cost scopes."""
    try:
        from tools.app.backend.cost_control import submit_with_context as cc_submit

        return cc_submit(executor, fn, *args, **kwargs)
    except Exception:
        ctx = contextvars.copy_context()
        return executor.submit(ctx.run, fn, *args, **kwargs)


@dataclass
class EngineContext:
    """Injectable concurrency, transport, cache, and LLM runner configuration."""

    max_workers: int = field(
        default_factory=lambda: max(1, int(os.environ.get("VIRAL_MAX_WORKERS", "8")))
    )
    glasser_semaphore: threading.BoundedSemaphore = field(default_factory=lambda: GLASSER_SEMAPHORE)
    single_flight: SingleFlight = field(default_factory=lambda: SINGLE_FLIGHT)
    submit_fn: Callable[..., Any] = submit_with_context
    agent_runner: Optional[Callable[..., str]] = None
    cache_dir: Optional[Path] = None


def default_context() -> EngineContext:
    """Construct a default EngineContext sharing process-wide single-flight & semaphore."""
    return EngineContext()
