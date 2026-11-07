"""Local web app for Excel -> viral research -> 3 topic ideas per sheet.

Run:
    python3 tools/app/server.py --port 8765

The frontend is served from tools/app/dist (npm run build). During development
use `npm run dev` in tools/app; Vite proxies /api to this server.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import mimetypes
import multiprocessing
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent
WORKSPACE = BACKEND_DIR.parents[2]
sys.path.insert(0, str(WORKSPACE))

from tools.app.backend.handler import run_worker  # noqa: E402
from tools.app.backend.profiles import PROFILE_STORE  # noqa: E402
from tools.app.backend.research import (  # noqa: E402
    configured_agent,
    create_job,
    parse_workbook,
    resolve_xlsx_bytes,
    STORE,
)

def _default_dist_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", BACKEND_DIR)) / "dist"
    desktop_dist = BACKEND_DIR.parent / "desktop-app" / "dist"
    if desktop_dist.exists():
        return desktop_dist
    browser_dist = BACKEND_DIR.parent / "browser-app" / "dist"
    if browser_dist.exists():
        return browser_dist
    return desktop_dist

DIST_DIR = _default_dist_dir()
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
if os.name == "nt":
    LOG_PATH = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AIBrand" / "logs" / "aibrand.log"
elif sys.platform == "darwin":
    LOG_PATH = Path.home() / "Library" / "Logs" / "AIBrand.log"
else:
    LOG_PATH = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "aibrand" / "aibrand.log"
_LOG_LOCK = threading.Lock()


def _log_line(line: str) -> None:
    formatted = f"{datetime.now().isoformat(timespec='seconds')} {line}\n"
    if not getattr(sys, "frozen", False):
        try:
            sys.stderr.write(formatted)
            sys.stderr.flush()
        except Exception:
            pass
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK, open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(formatted)
    except Exception:
        pass


def _json(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler._cors()
    handler.end_headers()
    handler.wfile.write(body)


def _bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _int(value: Optional[str], default: Optional[int], minimum: int = 0, maximum: int = 10000) -> Optional[int]:
    if value is None or value == "":
        return default
    parsed = int(value)
    return max(minimum, min(maximum, parsed))


class Handler(BaseHTTPRequestHandler):
    server_version = "ViralResearch/0.1"

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, fmt: str, *args: Any) -> None:
        line = f"{self.address_string()} {fmt % args}"
        print(f"[http] {line}")
        _log_line(f"[http] {line}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self) -> None:
        self.do_GET()

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _client_id(self) -> str:
        """Per-browser id from the frontend; falls back to the caller's IP. Not authentication."""
        value = self.headers.get("X-Client-Id") or ""
        if re.fullmatch(r"[A-Za-z0-9-]{8,64}", value):
            return value
        return f"ip-{self.client_address[0]}"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            _json(self, 200, {
                "ok": True,
                "app": "aibrand",
                "desktop": bool(getattr(sys, "frozen", False)),
                "transcription": _transcription_status(),
                "ffmpeg": _ffmpeg_status(),
                "glasser": _glasser_status(),
                "agent": _agent_status(),
            })
            return
        if parsed.path == "/api/logs":
            logs = ""
            if LOG_PATH.exists():
                try:
                    with _LOG_LOCK, open(LOG_PATH, "r", encoding="utf-8", errors="replace") as handle:
                        content = handle.read()
                    logs = content[-65536:] if len(content) > 65536 else content
                except Exception as exc:
                    logs = f"Error reading log file: {exc}"
            _json(self, 200, {
                "path": str(LOG_PATH),
                "logs": logs,
                "os": sys.platform,
                "platform": platform.platform(),
                "python": platform.python_version(),
                "desktop": bool(getattr(sys, "frozen", False)),
            })
            return
        if parsed.path == "/api/sources/topics":
            try:
                query = parse_qs(parsed.query).get("q", [None])[0]
                topics = PROFILE_STORE.list_topics(query)
                _json(self, 200, {"ok": True, "topics": topics})
            except Exception as exc:
                _json(self, 500, {"error": str(exc)})
            return
        match = re.fullmatch(r"/api/jobs/([a-f0-9]+)", parsed.path)
        if match:
            job = STORE.snapshot(match.group(1))
            _json(self, 200 if job else 404, job or {"error": "Không tìm thấy job"})
            return
        match = re.fullmatch(r"/api/jobs/([a-f0-9]+)/export", parsed.path)
        if match:
            job = STORE.snapshot(match.group(1))
            if not job:
                _json(self, 404, {"error": "Không tìm thấy job"})
                return
            body = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="viral-research-{job["id"]}.json"')
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/sources/parse":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    _json(self, 400, {"error": "Thiếu dữ liệu file"})
                    return
                raw = self.rfile.read(length)
                filename = unquote(self.headers.get("X-Filename") or "upload.xlsx")
                topics = PROFILE_STORE.import_from_source(raw, filename)
                _json(self, 200, {
                    "ok": True,
                    "filename": filename,
                    "sheets": topics,
                    "topics": topics,
                })
            except Exception as exc:
                _json(self, 400, {"error": f"Không đọc được file: {exc}"})
            return
        if parsed.path == "/api/sources/topics":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                topic = body.get("topic") or body.get("name")
                url = body.get("url")
                name = body.get("channel_name") or body.get("name")
                if not topic:
                    _json(self, 400, {"error": "Thiếu tên chủ đề"})
                    return
                if url:
                    res = PROFILE_STORE.add_profile(topic, url, name)
                else:
                    res = PROFILE_STORE.upsert_topic(topic, body.get("targets"))
                _json(self, 200, {"ok": True, "topic": res, "topics": PROFILE_STORE.list_topics()})
            except Exception as exc:
                _json(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/sources/topics/delete":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                slug = body.get("slug")
                if not slug:
                    _json(self, 400, {"error": "Thiếu slug chủ đề"})
                    return
                PROFILE_STORE.delete_topic(slug)
                _json(self, 200, {"ok": True, "topics": PROFILE_STORE.list_topics()})
            except Exception as exc:
                _json(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/sources/profiles/delete":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                slug = body.get("slug")
                url = body.get("url")
                if not slug or not url:
                    _json(self, 400, {"error": "Thiếu slug chủ đề hoặc url kênh"})
                    return
                PROFILE_STORE.delete_profile(slug, url)
                _json(self, 200, {"ok": True, "topics": PROFILE_STORE.list_topics()})
            except Exception as exc:
                _json(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/jobs":
            self._create_job(parse_qs(parsed.query))
            return
        match = re.fullmatch(r"/api/jobs/([a-f0-9]+)/cancel", parsed.path)
        if match:
            ok = STORE.cancel(match.group(1))
            _json(self, 200 if ok else 404, {"cancelled": ok})
            return
        if parsed.path == "/api/logs/client":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                msg = body.get("message", "Unknown client error")
                stack = body.get("stack", "")
                source = body.get("source", "client")
                _log_line(f"[CLIENT-ERROR] [{source}] {msg}\n{stack}".strip())
                _json(self, 200, {"ok": True})
            except Exception as exc:
                _json(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/logs/reveal":
            try:
                LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                if not LOG_PATH.exists():
                    LOG_PATH.write_text(f"[{datetime.now().isoformat()}] Log initialized.\n", encoding="utf-8")
                if sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", str(LOG_PATH)])
                elif os.name == "nt":
                    subprocess.Popen(["explorer", f"/select,{LOG_PATH}"])
                else:
                    subprocess.Popen(["xdg-open", str(LOG_PATH.parent)])
                _json(self, 200, {"ok": True})
            except Exception as exc:
                _json(self, 500, {"error": str(exc)})
            return
        if parsed.path == "/api/shutdown":
            _json(self, 200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        _json(self, 404, {"error": "Không tìm thấy endpoint"})

    def _create_job(self, query: Dict[str, list[str]]) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            _json(self, 400, {"error": "Thiếu file Excel"})
            return
        if length > MAX_UPLOAD_BYTES:
            _json(self, 413, {"error": "File quá lớn (giới hạn 25MB)"})
            return
        raw = self.rfile.read(length)
        filename = unquote(self.headers.get("X-Filename") or "upload.xlsx")
        try:
            agent_id = configured_agent()["id"]
        except Exception as exc:
            _json(self, 400, {"error": str(exc)})
            return
        try:
            options = {
                "agent": agent_id,
                "max_videos": _int((query.get("max_videos") or ["5"])[0], 5, minimum=0, maximum=500),
                "media": _bool((query.get("media") or ["1"])[0], True),
                "window_hours": _int((query.get("window_hours") or ["48"])[0], 48, minimum=1, maximum=720),
                "acp_timeout": _int((query.get("acp_timeout") or ["240"])[0], 240, minimum=20, maximum=1800),
            }
        except ValueError as exc:
            _json(self, 400, {"error": f"Tuỳ chọn không hợp lệ: {exc}"})
            return
        try:
            job = create_job(raw, filename, options, self._client_id())
        except Exception as exc:
            _json(self, 400, {"error": f"Không đọc được Excel: {exc}"})
            return
        _json(self, 202, job)

    def _serve_static(self, path: str) -> None:
        if not DIST_DIR.exists():
            body = (
                "<!doctype html><meta charset='utf-8'>"
                "<body style='font-family:system-ui;padding:40px;line-height:1.6'>"
                "<h1>Frontend chưa được build</h1>"
                "<p>Chạy <code>cd tools/app && npm install && npm run build</code> "
                "rồi mở lại trang này.</p></body>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        rel = "index.html" if path in {"", "/"} else path.lstrip("/")
        file_path = (DIST_DIR / rel).resolve()
        if not str(file_path).startswith(str(DIST_DIR.resolve())) or not file_path.is_file():
            fallback = DIST_DIR / "index.html"
            if fallback.is_file() and not rel.startswith("assets/") and not rel.startswith("api/"):
                file_path = fallback
            else:
                _json(self, 404, {"error": "Not found"})
                return
        data = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        self.end_headers()
        self.wfile.write(data)


def _transcription_status() -> Dict[str, bool]:
    return {
        "mlx": importlib.util.find_spec("mlx_qwen3_asr") is not None,
        "transformers": importlib.util.find_spec("transformers") is not None
        and importlib.util.find_spec("torch") is not None,
        "whisper": importlib.util.find_spec("faster_whisper") is not None,
    }


def _ffmpeg_status() -> bool:
    if shutil.which("ffmpeg") or Path("/opt/homebrew/bin/ffmpeg").exists():
        return True
    try:
        import imageio_ffmpeg

        return True
    except Exception:
        return False


def _glasser_status() -> bool:
    return shutil.which("glasser") is not None


def _agent_status() -> Optional[str]:
    try:
        return configured_agent()["label"]
    except Exception:
        return None


def _augment_path() -> None:
    """Finder-launched apps get a minimal PATH; add the user's tool locations."""
    home = Path.home()
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        roaming = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        candidates = [
            str(roaming / "npm"),
            str(local / "Programs" / "opencode"),
            "C:\\Program Files\\nodejs",
            str(home / "scoop" / "shims"),
            str(home / ".local" / "bin"),
            str(home / ".opencode" / "bin"),
            str(home / ".cargo" / "bin"),
            str(home / ".volta" / "bin"),
            str(home / ".bun" / "bin"),
        ]
    else:
        candidates = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            str(home / ".local" / "bin"),
            str(home / ".opencode" / "bin"),
            str(home / ".cargo" / "bin"),
            str(home / ".volta" / "bin"),
            str(home / ".bun" / "bin"),
        ]
        for pattern in (
            ".nvm/versions/node/*/bin",
            ".local/share/fnm/node-versions/*/installation/bin",
        ):
            candidates.extend(str(path) for path in home.glob(pattern))
    parts: list[str] = []
    for item in candidates + os.environ.get("PATH", "").split(os.pathsep):
        if item and item not in parts:
            parts.append(item)
    os.environ["PATH"] = os.pathsep.join(parts)
    workspace_str = str(WORKSPACE)
    existing_ppath = os.environ.get("PYTHONPATH", "")
    if workspace_str not in existing_ppath.split(os.pathsep):
        os.environ["PYTHONPATH"] = f"{workspace_str}{os.pathsep}{existing_ppath}" if existing_ppath else workspace_str


def main() -> None:
    multiprocessing.freeze_support()  # job processes re-launch the PyInstaller binary
    _augment_path()
    parser = argparse.ArgumentParser(description="Viral research web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--parent-pid", type=int, default=0, help="Exit when this process disappears")
    parser.add_argument("--check-asr", action="store_true", help="Load the transcriber and exit")
    parser.add_argument(
        "--role",
        choices=["all", "api", "worker"],
        default="all",
        help="all: API + in-process worker (desktop); api: HTTP only; worker: run queued jobs only",
    )
    parser.add_argument("--dist", type=Path, default=None, help="Custom frontend dist directory to serve")
    args = parser.parse_args()

    global DIST_DIR
    if args.dist:
        DIST_DIR = args.dist.resolve()

    if args.check_asr:
        import traceback

        from tools.loop.viral_analyzer.transcription import UnifiedTranscriber

        try:
            transcriber = UnifiedTranscriber()
            print(f"ASR_OK {transcriber.engine}")
        except Exception:
            traceback.print_exc()
            raise SystemExit(1)
        return

    if args.parent_pid:
        def parent_alive(pid: int) -> bool:
            if os.name == "nt":
                import ctypes

                handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if not handle:
                    return False
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

        def watch_parent() -> None:
            while True:
                time.sleep(1)
                if not parent_alive(args.parent_pid):
                    os._exit(0)

        threading.Thread(target=watch_parent, daemon=True).start()

    if args.role == "worker":
        print("Viral Research worker: waiting for queued jobs")
        try:
            run_worker()
        except KeyboardInterrupt:
            pass
        return
    if args.role == "all":
        threading.Thread(target=run_worker, daemon=True).start()

    ThreadingHTTPServer.allow_reuse_address = True
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        if exc.errno in (48, 98, 10048):
            print(f"Lỗi: Cổng {args.port} đã được sử dụng bởi một tiến trình khác.")
            print(f"Gợi ý: Kiểm tra tiến trình đang chạy (lsof -i :{args.port}) hoặc đổi cổng với --port <khác>.")
            raise SystemExit(1)
        raise
    print(f"Viral Research app: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
