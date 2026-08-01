"""MCP server for Sky Computer Use.

Two modes:
1. Binary proxy (default): Spawns SkyComputerUseClient mcp as subprocess
2. Direct socket: Connects to daemon directly (requires signed client)

Usage:
    python -m src.mcp_server              # binary proxy mode
    python -m src.mcp_server --direct     # direct socket mode
"""

import json
import os
import struct
import subprocess
import sys
import threading
from typing import Any, Optional

BINARY_SEARCH_PATHS = [
    os.environ.get("SKY_CUA_BINARY_PATH", ""),
    os.path.expanduser(
        "~/Library/Application Support/ChatGPT/Codex Computer Use.app/"
        "Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient"
    ),
    "/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/computer-use/"
    "Codex Computer Use.app/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient",
]

TOOL_DEFINITIONS = [
    {
        "name": "list_apps",
        "description": "List the apps on this computer. Returns the set of apps that are currently running, as well as any that have been used in the last 14 days, including details on usage frequency",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"destructiveHint": False, "idempotentHint": True, "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "get_app_state",
        "description": "Start an app use session if needed, then get the state of the app's key window and return a screenshot and accessibility tree. This must be called once per assistant turn before interacting with the app",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "disableDiff": {"description": "Return full tree instead of diff", "type": "boolean"},
            },
            "required": ["app"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": True, "readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "click",
        "description": "Click an element by index or pixel coordinates from screenshot",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "element_index": {"description": "Element index to click", "type": "string"},
                "x": {"description": "X coordinate in screenshot pixel coordinates", "type": "number"},
                "y": {"description": "Y coordinate in screenshot pixel coordinates", "type": "number"},
                "mouse_button": {"description": "Mouse button to click. Defaults to left.", "enum": ["left", "right", "middle"], "type": "string"},
                "click_count": {"description": "Number of clicks. Defaults to 1", "type": "integer"},
            },
            "required": ["app"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "press_key",
        "description": "Press a key or key-combination on the keyboard, including modifier and navigation keys.\n  - This supports xdotool's `key` syntax.\n  - Examples: \"a\", \"Return\", \"Tab\", \"super+c\", \"Up\", \"KP_0\" (for the numpad 0 key).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "key": {"description": "Key or key combination to press", "type": "string"},
            },
            "required": ["app", "key"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "type_text",
        "description": "Type literal text using keyboard input",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "text": {"description": "Literal text to type", "type": "string"},
            },
            "required": ["app", "text"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "scroll",
        "description": "Scroll an element in a direction by a number of pages",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "element_index": {"description": "Element identifier", "type": "string"},
                "direction": {"description": "Scroll direction: up, down, left, or right", "type": "string"},
                "pages": {"description": "Number of pages to scroll. Fractional values are supported. Defaults to 1", "type": "number"},
            },
            "required": ["app", "element_index", "direction"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "set_value",
        "description": "Set the value of a settable accessibility element",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "element_index": {"description": "Element identifier", "type": "string"},
                "value": {"description": "Value to assign", "type": "string"},
            },
            "required": ["app", "element_index", "value"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "drag",
        "description": "Drag from one point to another using pixel coordinates",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "from_x": {"description": "Start X coordinate", "type": "number"},
                "from_y": {"description": "Start Y coordinate", "type": "number"},
                "to_x": {"description": "End X coordinate", "type": "number"},
                "to_y": {"description": "End Y coordinate", "type": "number"},
            },
            "required": ["app", "from_x", "from_y", "to_x", "to_y"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "perform_secondary_action",
        "description": "Invoke a secondary accessibility action exposed by an element",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "element_index": {"description": "Element identifier", "type": "string"},
                "action": {"description": "Secondary accessibility action name", "type": "string"},
            },
            "required": ["app", "element_index", "action"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
    {
        "name": "select_text",
        "description": "Select text inside a text element, or place the text cursor before or after it. Provide text exactly as it appears in the accessibility tree, including any Markdown formatting. If the text is not unique, provide surrounding prefix or suffix text to disambiguate it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"description": "App name or bundle identifier", "type": "string"},
                "element_index": {"description": "Text element identifier", "type": "string"},
                "text": {"description": "Target text as shown in the accessibility tree", "type": "string"},
                "prefix": {"description": "Optional text immediately before the target, used to disambiguate repeated matches", "type": "string"},
                "suffix": {"description": "Optional text immediately after the target, used to disambiguate repeated matches", "type": "string"},
                "selection": {"description": "Whether to select the text or place the cursor before or after it. Defaults to text.", "enum": ["text", "cursor_before", "cursor_after"], "type": "string"},
            },
            "required": ["app", "element_index", "text"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False, "readOnlyHint": False, "openWorldHint": False},
    },
]


def find_binary() -> Optional[str]:
    for p in BINARY_SEARCH_PATHS:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


class MCPServer:
    """MCP server that proxies to SkyComputerUseClient binary."""

    def __init__(self):
        self.binary_path = find_binary()
        self.proc = None  # type: Optional[subprocess.Popen]
        self._pending = {}  # type: dict[int, dict]
        self._lock = threading.Lock()

    def _ensure_binary(self) -> str:
        if self.binary_path:
            return self.binary_path
        raise RuntimeError(
            "SkyComputerUseClient binary not found.\n"
            "Install ChatGPT.app or set SKY_CUA_BINARY_PATH environment variable.\n"
            "Searched:\n" + "\n".join(f"  - {p}" for p in BINARY_SEARCH_PATHS if p)
        )

    def _start_process(self):
        binary = self._ensure_binary()
        self.proc = subprocess.Popen(
            [binary, "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        # Start reader thread
        t = threading.Thread(target=self._read_loop, daemon=True)
        t.start()

    def _read_loop(self):
        """Read responses from the subprocess and route to pending requests."""
        if not self.proc or not self.proc.stdout:
            return
        reader = self.proc.stdout
        while True:
            hdr = reader.read(4)
            if not hdr or len(hdr) < 4:
                break
            (length,) = struct.unpack("<I", hdr)
            body = reader.read(length)
            if not body or len(body) < length:
                break
            resp = json.loads(body)
            resp_id = resp.get("id")
            if resp_id is not None:
                with self._lock:
                    self._pending[resp_id] = resp

    def _proxy_send(self, request: dict) -> Optional[dict]:
        """Send request to binary subprocess and wait for response."""
        if self.proc is None or self.proc.poll() is not None:
            self._start_process()
        assert self.proc is not None and self.proc.stdin is not None

        msg_id = request.get("id")
        data = json.dumps(request, separators=(",", ":")).encode("utf-8")
        self.proc.stdin.write(struct.pack("<I", len(data)) + data)
        self.proc.stdin.flush()

        if msg_id is None:
            return None

        # Wait for response (simple polling, good enough for MCP)
        import time
        deadline = time.time() + 30
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

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOL_DEFINITIONS},
            }

        if method == "tools/call":
            return self._proxy_send(request)

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        # Proxy unknown methods to the binary
        if msg_id is not None:
            return self._proxy_send(request)
        return None

    def run_stdio(self):
        reader = sys.stdin.buffer
        writer = sys.stdout.buffer

        while True:
            hdr = reader.read(4)
            if not hdr or len(hdr) < 4:
                break
            (length,) = struct.unpack("<I", hdr)
            body = reader.read(length)
            if not body or len(body) < length:
                break
            request = json.loads(body)
            response = self.handle(request)
            if response is not None:
                data = json.dumps(response).encode("utf-8")
                writer.write(struct.pack("<I", len(data)) + data)
                writer.flush()


def main():
    server = MCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
