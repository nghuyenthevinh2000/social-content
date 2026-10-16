#!/usr/bin/env python3
"""Live development server for hook-validation-loop screens.

Serves the screens/ directory with zero-dependency, SSE-based live browser reloading.
Any changes to HTML, CSS, JS, or assets in screens/ immediately reload the page.

Usage:
    python serve.py
    python serve.py --port 8080
    python serve.py --no-browser
"""

import argparse
from functools import partial
import http.server
import mimetypes
import os
from pathlib import Path
import queue
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
import webbrowser

ROOT_DIR = Path(__file__).resolve().parent
SCREENS_DIR = ROOT_DIR / "screens"
DEFAULT_PAGE = "first-onboarding-screen-redesigned.html"

# Connected browser clients for live reloading
clients = set()
clients_lock = threading.Lock()

LIVERELOAD_SCRIPT = """
<!-- Injected by serve.py Live Reload Server -->
<script>
(() => {
  let retryCount = 0;
  function connect() {
    const es = new EventSource('/__livereload__');
    es.onopen = () => {
      retryCount = 0;
    };
    es.onmessage = (e) => {
      if (e.data === 'reload') {
        console.log('[LiveReload] Change detected, reloading page...');
        location.reload();
      }
    };
    es.onerror = () => {
      es.close();
      retryCount++;
      const delay = Math.min(800 * retryCount, 3000);
      setTimeout(connect, delay);
    };
  }
  connect();
})();
</script>
"""


def notify_clients():
    with clients_lock:
        if not clients:
            return
        count = len(clients)
        print(f"\n[\033[32mLiveReload\033[0m] Change detected -> reloading {count} connected browser tab(s)...")
        for q in list(clients):
            q.put("reload")


def get_latest_mtime(directory: Path) -> float:
    latest = 0.0
    for root, _, files in os.walk(directory):
        for f in files:
            if f.startswith(".") or f.endswith("~") or f.endswith(".tmp"):
                continue
            try:
                mtime = (Path(root) / f).stat().st_mtime
                if mtime > latest:
                    latest = mtime
            except OSError:
                pass
    return latest


def watch_files(directory: Path, interval: float = 0.35):
    last_mtime = get_latest_mtime(directory)
    while True:
        time.sleep(interval)
        try:
            current_mtime = get_latest_mtime(directory)
            if current_mtime > last_mtime:
                last_mtime = current_mtime
                time.sleep(0.05)  # debounce rapid writes
                notify_clients()
        except Exception:
            pass


class LiveReloadHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, format, *args):
        # Clean terminal logging: suppress noisy favicon & livereload polling logs
        path = getattr(self, "path", "")
        if path == "/__livereload__" or path == "/favicon.ico":
            return
        sys.stdout.write(f"[\033[34m{self.log_date_time_string()}\033[0m] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        # 1. SSE Live reload endpoint
        if self.path == "/__livereload__":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()

            q = queue.Queue()
            with clients_lock:
                clients.add(q)
            try:
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Heartbeat comment to keep SSE connection alive
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with clients_lock:
                    clients.discard(q)
            return

        # 2. Root redirects to main onboarding screen
        clean_path = urllib.parse.urlparse(self.path).path
        if clean_path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", f"/{DEFAULT_PAGE}")
            self.end_headers()
            return

        # 3. Resolve target file
        rel_path = clean_path.lstrip("/")
        target_file = (SCREENS_DIR / rel_path).resolve()

        # Prevent directory traversal outside SCREENS_DIR
        try:
            target_file.relative_to(SCREENS_DIR.resolve())
        except ValueError:
            self.send_error(403, "Access denied")
            return

        if target_file.is_dir():
            target_file = target_file / "index.html"

        if not target_file.is_file():
            super().do_GET()
            return

        # 4. Inject live reload script into HTML files
        if target_file.suffix.lower() in (".html", ".htm"):
            try:
                content = target_file.read_text(encoding="utf-8", errors="replace")
                if "</body>" in content:
                    content = content.replace("</body>", f"{LIVERELOAD_SCRIPT}</body>", 1)
                else:
                    content += LIVERELOAD_SCRIPT
                encoded = content.encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(encoded)
                return
            except Exception as err:
                self.send_error(500, f"Error reading file: {err}")
                return

        # 5. Disable caching for CSS and JS in development
        mime_type, _ = mimetypes.guess_type(str(target_file))
        if target_file.suffix.lower() in (".css", ".js", ".json"):
            try:
                data = target_file.read_bytes()
                self.send_response(200)
                if mime_type:
                    self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as err:
                self.send_error(500, f"Error reading file: {err}")
                return

        # Fallback to standard handler for media / other assets
        super().do_GET()


class ThreadedTCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def find_available_port(start_port: int = 8000, max_tries: int = 50) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    parser = argparse.ArgumentParser(description="Live Python server for hook-validation-loop screens")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-browser", "-n", action="store_true", help="Do not automatically open the browser")
    args = parser.parse_args()

    if not SCREENS_DIR.exists():
        print(f"\033[31mError:\033[0m Directory not found: {SCREENS_DIR}", file=sys.stderr)
        sys.exit(1)

    port = find_available_port(args.port)
    handler = partial(LiveReloadHTTPHandler, directory=SCREENS_DIR)

    # Start background file watcher
    watcher_thread = threading.Thread(target=watch_files, args=(SCREENS_DIR,), daemon=True)
    watcher_thread.start()

    server = ThreadedTCPServer(("127.0.0.1", port), handler)
    base_url = f"http://localhost:{port}"

    print("\n\033[1;32m╭──────────────────────────────────────────────────────────────╮\033[0m")
    print("\033[1;32m│       Hook Validation Loop — Live Development Server         │\033[0m")
    print("\033[1;32m╰──────────────────────────────────────────────────────────────╯\033[0m\n")
    print(f"  \033[1mServing directory:\033[0m  {SCREENS_DIR}")
    print(f"  \033[1mLive Reload:\033[0m        \033[32mActive\033[0m (auto-reloads on HTML/CSS/JS file edits)")
    print(f"  \033[1mServer URL:\033[0m         \033[4;36m{base_url}\033[0m\n")
    print("  \033[1mAvailable Screens:\033[0m")
    print(f"  ➜  Onboarding:      \033[36m{base_url}/first-onboarding-screen-redesigned.html\033[0m")
    print(f"  ➜  Dashboard:       \033[36m{base_url}/four-stage-loop-dashboard-redesigned.html\033[0m")
    print(f"  ➜  Wireframe:       \033[36m{base_url}/wireframe_preview.html\033[0m\n")
    print("  \033[2mPress Ctrl+C to stop the server.\033[0m\n")

    if not args.no_browser:
        target_url = f"{base_url}/{DEFAULT_PAGE}"
        threading.Timer(0.4, lambda: webbrowser.open(target_url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[\033[33mServer\033[0m] Shutting down...")
        server.shutdown()
        server.server_close()
        print("[\033[32mServer\033[0m] Stopped.")


if __name__ == "__main__":
    main()
