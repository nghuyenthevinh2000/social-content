#!/usr/bin/env python3
"""Host-side TCP-to-stdio bridge so Docker containers can invoke host `agy`."""

from __future__ import annotations

import argparse
import json
import os
import socketserver
import subprocess
import threading
from typing import List


def _validate_agy_command(cmd: object) -> List[str]:
    if not isinstance(cmd, list) or len(cmd) < 2 or cmd[0] != "agy" or cmd[-1] != "acp":
        raise ValueError("Only ['agy', ..., 'acp'] commands are allowed")
    args = [str(x) for x in cmd[1:-1]]
    if args and not (len(args) == 2 and args[0] == "--model" and args[1]):
        raise ValueError("Only optional '--model <name>' flag is allowed")
    return ["agy", *args, "acp"]


class _AgyBridgeHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        header = self.rfile.readline().decode("utf-8", errors="replace").strip()
        if not header:
            return
        try:
            cmd = _validate_agy_command(json.loads(header).get("command"))
        except Exception as exc:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": str(exc)}}
            self.wfile.write((json.dumps(err) + "\n").encode("utf-8"))
            self.wfile.flush()
            return

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "NO_COLOR": "1"},
        )

        def _pump_stdout() -> None:
            assert proc.stdout
            try:
                for line in proc.stdout:
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()
            except OSError:
                pass

        t = threading.Thread(target=_pump_stdout, daemon=True)
        t.start()
        try:
            assert proc.stdin
            for raw in self.rfile:
                line = raw.decode("utf-8", errors="replace")
                try:
                    msg = json.loads(line)
                    if msg.get("method") == "session/new":
                        cwd = msg.get("params", {}).get("cwd")
                        if cwd and not os.path.isdir(cwd):
                            msg["params"]["cwd"] = os.getcwd()
                            line = json.dumps(msg, ensure_ascii=False) + "\n"
                except Exception:
                    pass
                proc.stdin.write(line)
                proc.stdin.flush()
        except OSError:
            pass
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()


class _BridgeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Expose host `agy acp` to Docker over TCP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    with _BridgeServer((args.host, args.port), _AgyBridgeHandler) as srv:
        print(f"agy host bridge listening on {args.host}:{args.port}", flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
