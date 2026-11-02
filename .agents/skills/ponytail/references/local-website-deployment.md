# Local Website Deployment & Remote Tunneling (The Ponytail Way)

The laziest way to preview and deploy a local web front-end is the standard library: zero `npm install`, zero Vite/Express/Nginx/Docker scaffolding, zero configuration drift. But "lazy" means **understanding the real flow first** so a minimal solution doesn't collapse under real browser behavior.

When deploying a local site and exposing it remotely (via VS Code Dev Tunnels, Cloudflare Tunnel, ngrok, or local LAN), a naive `python3 -m http.server` fails on three common traps: concurrency deadlocks (SSE / live-reload), macOS port collisions, and video byte-range streaming.

---

## The 4 Traps & Lazy Senior Fixes

### 1. Concurrency Trap: Single-Threaded Deadlock
- **The Mistake:** Using `http.server.HTTPServer` with long-lived connections (Server-Sent Events `/live-reload`, WebSockets, or streaming media).
- **Why it breaks:** `HTTPServer` is strictly single-threaded synchronous. An SSE loop (`while True: time.sleep(15)`) or a slow video stream holds the server thread permanently. When the browser requests `style.css`, `app.js`, or video chunks in parallel, they hang in the socket queue and time out with 504 / connection dropped.
- **The Lazy Fix:** `from http.server import ThreadingHTTPServer`. One line swap. Zero dependencies. Every request gets its own background daemon thread.

### 2. The macOS Port 5000 Trap: AirPlay Receiver (`AirTunes`)
- **The Mistake:** Binding a local development server to port `5000` on macOS Monterey, Ventura, Sonoma, or Sequoia.
- **Why it breaks:** macOS `ControlCenter` listens on port 5000 (`*:5000`) for AirPlay Receiver on both IPv4 and IPv6.
  - Reverse proxies (like VS Code Dev Tunnels) forward to `localhost:5000`.
  - macOS resolves `localhost` to IPv6 `::1` first.
  - If Python only binds to IPv4 `127.0.0.1`, IPv6 traffic hits ControlCenter, returning `HTTP/1.1 403 Forbidden` (`Server: AirTunes/935.7.1` and `x-apple-processingtime: 0`). CSS breaks, assets fail.
- **The Lazy Fixes:**
  1. *Easiest:* Pick any other port (`5050`, `8080`, `5173`).
  2. *System toggle:* **System Settings ➔ General ➔ AirDrop & Handoff ➔ AirPlay Receiver (Toggle OFF)**.
  3. *If port 5000 is required (e.g. pinned devtunnel URL):* Bind **both** `127.0.0.1` and `::1` using `SO_REUSEPORT`. In BSD/macOS routing tables, an explicit IP bind (`::1` or `127.0.0.1`) takes precedence over wildcard `*:5000`.

### 3. Remote Tunnel & CORS Trap
- **The Mistake:** Relying on same-origin assumptions when exposing local ports to external tunnel domains (`https://*.devtunnels.ms`, `https://*.trycloudflare.com`).
- **Why it breaks:** Browsers, web workers, and mobile webviews enforce strict CORS and preflight checks on external domains.
- **The Lazy Fix:** Add universal CORS headers in `end_headers()`:
  ```python
  def end_headers(self):
      self.send_header("Access-Control-Allow-Origin", "*")
      self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
      self.send_header("Access-Control-Allow-Headers", "*")
      super().end_headers()

  def do_OPTIONS(self):
      self.send_response(204)
      self.end_headers()
  ```

### 4. Video Streaming & Byte-Range Requests
- **The Mistake:** Serving MP4 files with standard `200 OK` whole-file reads.
- **Why it breaks:** Safari (iOS and macOS) and Chrome require HTTP Byte Ranges (`206 Partial Content`) for video seeking, metadata extraction (`moov` atom), and audio/video sync. Without range support, videos fail to play or scrub, or hang mobile connections.
- **The Lazy Fix:** Parse the `Range: bytes=START-END` header, return `206 Partial Content`, and stream in 64KB chunks (`remaining -= len(chunk)`). Never read the entire 50MB file into memory at once.

### 5. The LiveReload Reconnect Loop
- **The Mistake:** Adding `es.onerror = () => location.reload()` in client scripts.
- **Why it breaks:** Reverse proxies and tunnels close idle SSE streams every 30–60s. Forcing `location.reload()` on disconnect causes an infinite refresh loop that ruins remote testing.
- **The Lazy Fix:** Remove `location.reload()` on error. The browser's native `EventSource` automatically reconnects with exponential backoff.

---

## Minimal Reference Server Template

A complete, zero-dependency, production-grade local development server (~120 lines of pure Python stdlib):

```python
#!/usr/bin/env python3
"""
Zero-dependency, multi-threaded static file server with:
- Multi-threaded request handling (ThreadingHTTPServer)
- Dual-stack IPv4/IPv6 loopback binding (overrides macOS port 5000 AirPlay)
- HTTP 206 Byte-Range streaming for playable videos
- Universal CORS headers for remote devtunnels
- SSE live reload with thread-safe queues
"""
import os
import sys
import time
import queue
import socket
import mimetypes
import threading
from urllib.parse import unquote, urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5000))
DOC_ROOT = os.path.dirname(os.path.abspath(__file__))

subscribers = []
subscribers_lock = threading.Lock()

class LiveReloadHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_HEAD(self):
        self._serve_file(send_body=False)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # 1. SSE Live Reload endpoint
        if path == "/live-reload":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            q = queue.Queue(maxsize=10)
            with subscribers_lock:
                subscribers.append(q)
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with subscribers_lock:
                    if q in subscribers:
                        subscribers.remove(q)
            return

        self._serve_file(send_body=True)

    def _serve_file(self, send_body=True):
        parsed = urlparse(self.path)
        path = unquote(parsed.path).lstrip("/")
        if not path or path == "":
            path = "index.html"

        full_path = os.path.join(DOC_ROOT, os.path.normpath(path))
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            self.send_error(404, "File Not Found")
            return

        ctype, _ = mimetypes.guess_type(full_path)
        file_size = os.path.getsize(full_path)
        range_header = self.headers.get("Range")

        try:
            if range_header and range_header.startswith("bytes="):
                ranges = range_header.replace("bytes=", "").split("-")
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1

                if start >= file_size or end >= file_size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers()
                    return

                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                if send_body:
                    with open(full_path, "rb") as f:
                        f.seek(start)
                        rem = length
                        while rem > 0:
                            chunk = f.read(min(65536, rem))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            rem -= len(chunk)
            else:
                self.send_response(200)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                if send_body:
                    with open(full_path, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

class ReusableServerV4(ThreadingHTTPServer):
    address_family = socket.AF_INET
    daemon_threads = True
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()

class ReusableServerV6(ThreadingHTTPServer):
    address_family = socket.AF_INET6
    daemon_threads = True
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()

def run():
    s4 = ReusableServerV4(("127.0.0.1", PORT), LiveReloadHandler)
    t4 = threading.Thread(target=s4.serve_forever, daemon=True)
    t4.start()

    try:
        s6 = ReusableServerV6(("::1", PORT), LiveReloadHandler)
        t6 = threading.Thread(target=s6.serve_forever, daemon=True)
        t6.start()
    except Exception:
        pass

    print(f"Serving {DOC_ROOT} on port {PORT} (IPv4 + IPv6)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()
```

---

## When to reach for this reference

- You need to preview or review HTML/JS/CSS without installing npm dependencies.
- You need to share a local web build to mobile devices or remote teammates via tunnels (VS Code Dev Tunnels, ngrok, Cloudflare).
- The front-end plays video/audio files or streams data.
- You see `403 Forbidden` (`Server: AirTunes`) or timeout hangs on port 5000 on macOS.
