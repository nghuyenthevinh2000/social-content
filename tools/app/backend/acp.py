"""Minimal Agent Client Protocol (ACP) stdio client.

Spawns an ACP-compatible agent harness, creates a session and streams one prompt
turn. Used by the viral research app so the user can pick which agent "thinks"
about the three topic suggestions.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class ACPError(RuntimeError):
    pass


class ACPClient:
    def __init__(
        self,
        command: List[str],
        cwd: Path,
        timeout_sec: float = 240.0,
        log: Optional[Callable[[str], None]] = None,
    ):
        self.command = command
        self.cwd = str(Path(cwd).resolve())
        self.timeout_sec = timeout_sec
        self.log = log or (lambda _msg: None)
        self._next_id = 0
        self._pending: Dict[int, "queue.Queue[Dict[str, Any]]"] = {}
        self._pending_lock = threading.Lock()
        self._stderr_lines: List[str] = []
        self._closed = False
        self._notification_hook: Optional[Callable[[Dict[str, Any]], None]] = None
        self._proc: Optional[subprocess.Popen[str]] = None
        self._sock: Optional[socket.socket] = None
        bridge = os.environ.get("AGY_HOST_BRIDGE", "").strip()
        if bridge and command and Path(command[0]).name == "agy":
            host, _, port_str = bridge.rpartition(":")
            port = int(port_str) if port_str.isdigit() else 8766
            try:
                self._sock = socket.create_connection((host or "host.docker.internal", port), timeout=10)
                self._sock.settimeout(None)
            except OSError as exc:
                raise ACPError(
                    f"Không kết nối được host agy bridge tại {bridge}: {exc}. "
                    "Chạy `python tools/app/agy_host_bridge.py` trên máy host."
                ) from exc
            self._stdin = self._sock.makefile("w", encoding="utf-8", buffering=1)
            self._stdout = self._sock.makefile("r", encoding="utf-8")
            self._stdin.write(json.dumps({"command": command}, ensure_ascii=False) + "\n")
            self._stdin.flush()
            threading.Thread(target=self._read_stdout, daemon=True).start()
        else:
            self._proc = subprocess.Popen(
                command,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**os.environ, "NO_COLOR": "1"},
            )
            self._stdin = self._proc.stdin
            self._stdout = self._proc.stdout
            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()

    # -- transport -----------------------------------------------------------
    def _send(self, payload: Dict[str, Any]) -> None:
        if not self._stdin:
            raise ACPError("Agent stdin is closed")
        self._stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._stdin.flush()

    def _read_stdout(self) -> None:
        assert self._stdout
        for line in self._stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self.log(f"[acp] bỏ qua dòng không phải JSON: {line[:120]}")
                continue
            if "id" in message and ("result" in message or "error" in message):
                with self._pending_lock:
                    waiter = self._pending.get(int(message["id"]))
                if waiter:
                    waiter.put(message)
                continue
            method = message.get("method")
            if method == "session/update":
                if self._notification_hook:
                    self._notification_hook(message)
                continue
            if method == "session/request_permission":
                self._handle_permission(message)
                continue
            if "id" in message:
                self._send({
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": f"Unsupported client method: {method}"},
                })

    def _read_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        for line in self._proc.stderr:
            line = line.strip()
            if line:
                self._stderr_lines.append(line)
                del self._stderr_lines[:-20]

    def _handle_permission(self, message: Dict[str, Any]) -> None:
        options = message.get("params", {}).get("options", [])
        choice = next((o for o in options if o.get("kind") == "allow_once"), None)
        if not choice:
            choice = next((o for o in options if o.get("kind") == "allow_always"), None)
        if not choice:
            choice = next((o for o in options if not str(o.get("kind", "")).startswith("reject")), None)
        result = (
            {"outcome": {"outcome": "selected", "optionId": choice["optionId"]}}
            if choice
            else {"outcome": {"outcome": "cancelled"}}
        )
        self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def request(self, method: str, params: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        if self._closed:
            raise ACPError("ACP connection is closed")
        self._next_id += 1
        request_id = self._next_id
        waiter: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = waiter
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        try:
            message = waiter.get(timeout=timeout or self.timeout_sec)
        except queue.Empty:
            raise ACPError(f"Timeout chờ agent trả lời {method} ({timeout or self.timeout_sec:.0f}s)")
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)
        if "error" in message:
            error = message["error"]
            raise ACPError(f"{method} lỗi {error.get('code')}: {error.get('message')}")
        return message.get("result", {})

    # -- protocol ------------------------------------------------------------
    def initialize(self) -> Dict[str, Any]:
        return self.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {},
                "clientInfo": {"name": "viral-research-app", "title": "Viral Research", "version": "0.1.0"},
            },
        )

    def new_session(self) -> str:
        result = self.request("session/new", {"cwd": self.cwd, "mcpServers": []})
        session_id = result.get("sessionId")
        if not session_id:
            raise ACPError("Agent không trả về sessionId")
        return session_id

    def prompt(
        self,
        session_id: str,
        text: str,
        images: Optional[List[Tuple[bytes, str]]] = None,
    ) -> str:
        """Send a prompt (text plus optional images) and return the agent's text."""
        chunks: List[str] = []
        chunks_lock = threading.Lock()

        def collect(message: Dict[str, Any]) -> None:
            update = message.get("params", {}).get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                content = update.get("content", {})
                if content.get("type") == "text":
                    with chunks_lock:
                        chunks.append(content.get("text", ""))

        blocks: List[Dict[str, Any]] = [{"type": "text", "text": text}]
        for data, mime_type in images or []:
            if data:
                blocks.append({
                    "type": "image",
                    "mimeType": mime_type,
                    "data": base64.b64encode(data).decode("ascii"),
                })

        self._notification_hook = collect
        t0 = time.perf_counter()
        http_status = 200
        try:
            self.request(
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": blocks,
                },
                timeout=self.timeout_sec,
            )
        except Exception:
            http_status = 500
            raise
        finally:
            self._notification_hook = None
            try:
                from tools.app.backend import cost_control

                agent_name = Path(self.command[0]).name if self.command else "agent"
                cost_control.record_cost_event(
                    provider="acp",
                    endpoint=f"session/prompt:{agent_name}",
                    cost_micro=0,
                    http_status=http_status,
                    wasted=http_status >= 400,
                    sub_action="acp_prompt",
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                )
            except Exception:
                pass
        with chunks_lock:
            return "".join(chunks)

    def close(self) -> None:
        self._closed = True
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        if self._stdin is not None:
            try:
                self._stdin.close()
            except OSError:
                pass
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    @property
    def is_alive(self) -> bool:
        if self._closed:
            return False
        if self._proc is not None and self._proc.poll() is not None:
            return False
        return True

    @property
    def stderr_tail(self) -> str:
        return "\n".join(self._stderr_lines[-8:])
