"""Pure Python client for SkyComputerUse daemon (com.openai.sky.CUAService).

Protocol: JSON-RPC 2.0 over Unix socket with 4-byte LE length prefix.

NOTE: The daemon verifies code signature of connecting processes.
Unsigned Python clients are rejected. Use SkyComputerUseClient binary
as a bridge instead (see mcp_server.py).
"""

import json
import os
import socket
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_SOCK = os.path.expanduser(
    "~/Library/Group Containers/2DC432GLL2.com.openai.sky.CUAService/IPC/computeruse.sock"
)
API_VERSION = "CodexComputerUseIPC-2"
DEFAULT_TIMEOUT = 120

SOCKET_PATHS = [
    os.environ.get("SKY_CUA_NATIVE_PIPE_PATH", ""),
    DEFAULT_SOCK,
]


class SkyError(Exception):
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class SkyClient:
    """Direct socket client for SkyComputerUse daemon.

    WARNING: The daemon rejects unsigned clients. This class is provided
    for reference and testing. For production use, prefer the MCP binary
    bridge (mcp_server.py).
    """

    def __init__(
        self,
        sock_path: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.sock_path = sock_path or self._find_socket()
        self.timeout = timeout
        self._sock = None  # type: Optional[socket.socket]
        self._id = 0

    def _find_socket(self) -> str:
        for p in SOCKET_PATHS:
            if p and os.path.exists(p):
                return p
        raise SkyError(
            f"SkyComputerUse daemon socket not found. "
            f"Ensure ChatGPT.app is installed and the CUA service is running.\n"
            f"Expected: {DEFAULT_SOCK}"
        )

    def _connect(self) -> socket.socket:
        if self._sock is None:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.sock_path)
            s.settimeout(self.timeout)
            self._sock = s
        return self._sock

    def _close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, payload: dict) -> None:
        sock = self._connect()
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sock.sendall(struct.pack("<I", len(data)) + data)

    def _recv(self) -> dict:
        sock = self._connect()
        hdr = b""
        while len(hdr) < 4:
            chunk = sock.recv(4 - len(hdr))
            if not chunk:
                self._close()
                raise SkyError("Connection closed while reading header")
            hdr += chunk
        (length,) = struct.unpack("<I", hdr)
        if length > 8 * 1024 * 1024:
            self._close()
            raise SkyError(f"Frame too large: {length}")
        body = b""
        while len(body) < length:
            chunk = sock.recv(length - len(body))
            if not chunk:
                self._close()
                raise SkyError("Connection closed while reading body")
            body += chunk
        return json.loads(body)

    def _rpc(self, method: str, params: dict, timeout: Optional[int] = None) -> dict:
        msg_id = self._next_id()
        deadline = time.time() + (timeout or self.timeout)
        payload = {
            "id": msg_id,
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self._send(payload)
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise SkyError(f"RPC timeout waiting for response to {method}")
            resp = self._recv()
            if resp.get("id") == msg_id:
                if "error" in resp:
                    err = resp["error"]
                    msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    raise SkyError(msg, code=err.get("code") if isinstance(err, dict) else None)
                return resp.get("result", {})

    def ping(self) -> str:
        result = self._rpc("ping", {"clientApiVersion": API_VERSION}, timeout=5)
        return result.get("serverApiVersion", "unknown")

    def list_apps(self) -> List[Dict[str, Any]]:
        result = self._rpc(
            "request",
            {
                "clientApiVersion": API_VERSION,
                "requestType": "ComputerUseIPCListAppsRequest",
                "request": {},
                "deadlineUnixMilliseconds": int((time.time() + self.timeout) * 1000),
            },
        )
        return result.get("apps", result) if isinstance(result, dict) else result

    def get_app_state(self, app: str, *, disable_diff: bool = False) -> dict:
        req = self._resolve_app(app)
        if disable_diff:
            req["disableDiff"] = True
        return self._rpc(
            "request",
            {
                "clientApiVersion": API_VERSION,
                "requestType": "ComputerUseIPCAppGetSkyshotRequest",
                "request": req,
                "deadlineUnixMilliseconds": int((time.time() + self.timeout) * 1000),
            },
        )

    def click(
        self,
        app: str,
        *,
        element_index: Optional[int] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        click_count: int = 1,
        mouse_button: str = "left",
    ) -> None:
        at = {}
        if element_index is not None:
            at["elementIndex"] = element_index
        if x is not None:
            at["x"] = x
        if y is not None:
            at["y"] = y
        self._perform_action(app, {
            "click": {"at": at, "clickCount": click_count, "mouseButton": mouse_button}
        })

    def press_key(self, app: str, key: str) -> None:
        self._perform_action(app, {"pressKey": {"_0": key}})

    def type_text(self, app: str, text: str) -> None:
        self._perform_action(app, {"typeText": {"text": text}})

    def scroll(self, app: str, element_index: int, direction: str, pages: float = 1) -> None:
        self._perform_action(app, {
            "scroll": {"at": {"elementIndex": element_index}, "direction": direction, "pages": pages}
        })

    def set_value(self, app: str, element_index: int, value: str) -> None:
        self._perform_action(app, {"setValue": {"elementID": element_index, "value": value}})

    def drag(self, app: str, from_x: float, from_y: float, to_x: float, to_y: float) -> None:
        self._perform_action(app, {
            "drag": {"from": {"x": from_x, "y": from_y}, "to": {"x": to_x, "y": to_y}}
        })

    def perform_secondary_action(self, app: str, element_index: int, action: str) -> None:
        self._perform_action(app, {
            "performSecondaryAction": {"action": action, "elementID": element_index}
        })

    def select_text(
        self, app: str, element_index: int, text: str,
        *, prefix: Optional[str] = None, suffix: Optional[str] = None,
        selection_type: str = "text",
    ) -> None:
        params = {"elementID": element_index, "text": text, "selectionType": selection_type}
        if prefix:
            params["prefix"] = prefix
        if suffix:
            params["suffix"] = suffix
        self._perform_action(app, {"selectText": params})

    def _perform_action(self, app: str, action: dict) -> None:
        req = self._resolve_app(app)
        req["action"] = action
        self._rpc(
            "request",
            {
                "clientApiVersion": API_VERSION,
                "requestType": "ComputerUseIPCAppPerformActionRequest",
                "request": req,
                "deadlineUnixMilliseconds": int((time.time() + self.timeout) * 1000),
            },
        )

    @staticmethod
    def _resolve_app(app: str) -> dict:
        if "/" in app or app.endswith(".app"):
            return {"applicationPath": app}
        return {"bundleIdentifier": app}
