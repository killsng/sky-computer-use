"""MCP server for Sky Computer Use.

Proxies MCP protocol through OpenComputerUse binary (from open-computer-use npm package).
The binary talks to the SkyComputerUseService daemon over unix socket.

MCP stdio transport uses newline-delimited JSON (NOT length-prefixed frames).

Usage:
    python3 serve.py
    python3 -m src.mcp_server
"""

import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

BINARY_SEARCH_PATHS = [
    os.environ.get("SKY_CUA_BINARY_PATH", ""),
    "/usr/local/lib/node_modules/open-computer-use/dist/Open Computer Use.app/Contents/MacOS/OpenComputerUse",
    "/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/computer-use/"
    "Codex Computer Use.app/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient",
]


def find_binary() -> Optional[str]:
    for p in BINARY_SEARCH_PATHS:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


class MCPServer:
    """MCP server that proxies all requests to the OpenComputerUse binary."""

    def __init__(self):
        self.binary_path = find_binary()
        self.proc = None  # type: Optional[subprocess.Popen]
        self._pending = {}  # type: Dict[int, dict]
        self._lock = threading.Lock()
        self._started = False

    def _ensure_binary(self) -> str:
        if self.binary_path:
            return self.binary_path
        raise RuntimeError(
            "OpenComputerUse binary not found.\n"
            "Install: npm install -g open-computer-use\n"
            "Or set SKY_CUA_BINARY_PATH environment variable.\n"
            "Searched:\n" + "\n".join(f"  - {p}" for p in BINARY_SEARCH_PATHS if p)
        )

    def _start_process(self):
        if self._started and self.proc and self.proc.poll() is None:
            return
        binary = self._ensure_binary()
        self.proc = subprocess.Popen(
            [binary, "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._started = True
        t = threading.Thread(target=self._read_loop, daemon=True)
        t.start()

    def _read_loop(self):
        """Read newline-delimited JSON responses from the subprocess."""
        if not self.proc or not self.proc.stdout:
            return
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                resp_id = resp.get("id")
                if resp_id is not None:
                    with self._lock:
                        self._pending[resp_id] = resp
            except json.JSONDecodeError:
                pass

    def _proxy_send(self, request: dict, timeout: float = 30) -> Optional[dict]:
        """Send request to binary subprocess and wait for response."""
        self._start_process()
        assert self.proc is not None and self.proc.stdin is not None

        msg_id = request.get("id")
        line = json.dumps(request, separators=(",", ":")) + "\n"
        try:
            self.proc.stdin.write(line.encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._start_process()
            assert self.proc is not None and self.proc.stdin is not None
            self.proc.stdin.write(line.encode())
            self.proc.stdin.flush()

        if msg_id is None:
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if msg_id in self._pending:
                    return self._pending.pop(msg_id)
            time.sleep(0.01)
        return None

    def handle(self, request: dict) -> Optional[dict]:
        method = request.get("method", "")
        msg_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "sky-computer-use", "version": "1.0.0"},
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        return self._proxy_send(request)

    def run_stdio(self):
        reader = sys.stdin.buffer
        writer = sys.stdout.buffer

        while True:
            line = reader.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle(request)
            if response is not None:
                writer.write((json.dumps(response) + "\n").encode())
                writer.flush()


def main():
    server = MCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
