#!/usr/bin/env python3
"""Minimal stdlib-only Agent Client Protocol (ACP) stdio client."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class ACPError(RuntimeError):
    """Raised when an ACP harness request fails or times out."""


class ACPClient:
    """Minimal JSON-RPC stdio client for ACP-compatible agent harnesses."""

    def __init__(self, command: Sequence[str], cwd: Path, timeout_sec: float = 60.0) -> None:
        self.command = list(command)
        self.cwd = str(Path(cwd).resolve())
        self.timeout_sec = timeout_sec
        self._next_id = 0
        self._pending: Dict[int, "queue.Queue[Dict[str, Any]]"] = {}
        self._lock = threading.Lock()
        self._chunks: Optional[List[str]] = None
        self._closed = False
        self._proc = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env={**os.environ, "NO_COLOR": "1"},
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()

    def __enter__(self) -> "ACPClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _send(self, payload: Dict[str, Any]) -> None:
        if not self._proc.stdin:
            raise ACPError("Agent stdin is closed")
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_stdout(self) -> None:
        assert self._proc.stdout
        for raw in self._proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                with self._lock:
                    waiter = self._pending.get(int(msg["id"]))
                if waiter:
                    waiter.put(msg)
                continue
            method = msg.get("method")
            if method == "session/update" and self._chunks is not None:
                update = msg.get("params", {}).get("update", {})
                if update.get("sessionUpdate") == "agent_message_chunk":
                    content = update.get("content", {})
                    if content.get("type") == "text":
                        self._chunks.append(content.get("text", ""))
            elif method == "session/request_permission":
                opts = msg.get("params", {}).get("options", [])
                pick = next((o for o in opts if o.get("kind") in ("allow_once", "allow_always")), None)
                res = {"outcome": {"outcome": "selected", "optionId": pick["optionId"]}} if pick else {"outcome": {"outcome": "cancelled"}}
                self._send({"jsonrpc": "2.0", "id": msg["id"], "result": res})
            elif "id" in msg:
                self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"Unsupported: {method}"}})

    def request(self, method: str, params: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        if self._closed:
            raise ACPError("ACP connection is closed")
        self._next_id += 1
        req_id = self._next_id
        waiter: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[req_id] = waiter
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        try:
            msg = waiter.get(timeout=timeout or self.timeout_sec)
        except queue.Empty:
            raise ACPError(f"Timeout waiting for {method}")
        finally:
            with self._lock:
                self._pending.pop(req_id, None)
        if "error" in msg:
            err = msg["error"]
            raise ACPError(f"{method} error {err.get('code')}: {err.get('message')}")
        return msg.get("result", {})

    def initialize(self) -> Dict[str, Any]:
        return self.request(
            "initialize",
            {"protocolVersion": 1, "clientCapabilities": {}, "clientInfo": {"name": "acp-client", "version": "0.1.0"}},
        )

    def new_session(self) -> str:
        sid = self.request("session/new", {"cwd": self.cwd, "mcpServers": []}).get("sessionId")
        if not sid:
            raise ACPError("Missing sessionId")
        return sid

    def prompt(self, session_id: str, text: str) -> str:
        self._chunks = []
        try:
            self.request("session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": text}]})
            return "".join(self._chunks)
        finally:
            self._chunks = None

    def close(self) -> None:
        self._closed = True
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()


def ask(
    prompt_text: str,
    command: Optional[Sequence[str]] = None,
    cwd: Optional[Path] = None,
    timeout_sec: float = 30.0,
) -> str:
    """Run a single ACP prompt turn and return the response text."""
    cmd = list(command) if command else ["agy", "acp"]
    if not shutil.which(cmd[0]):
        raise ACPError(f"ACP harness not found: {cmd[0]}")
    with ACPClient(cmd, cwd or Path.cwd(), timeout_sec=timeout_sec) as client:
        client.initialize()
        return client.prompt(client.new_session(), prompt_text)
