"""WebSocket server for streaming Computer Use state to mobile clients.

Streams screenshots + accessibility tree to connected Android app.
Usage:
    python server.py
    # Then connect from Android app to ws://YOUR_IP:8765
"""

import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("pip install websockets")
    sys.exit(1)

# MCP server path
MCP_SERVER = os.path.join(os.path.dirname(__file__), "..", "serve.py")

SCREENSHOT_INTERVAL = 2.0  # seconds between auto-screenshots
HOST = "0.0.0.0"
PORT = 8765


class AgentBridge:
    """Bridges MCP server to WebSocket clients."""

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._read_task: Optional[asyncio.Task] = None
        self._started = False

    async def start(self):
        if self._started and self.proc and self.proc.poll() is None:
            return
        self.proc = subprocess.Popen(
            [sys.executable, MCP_SERVER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._started = True
        self._read_task = asyncio.create_task(self._read_loop())

        # Initialize
        resp = await self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                              "clientInfo": {"name": "mobile-viewer", "version": "1.0"}}})
        print("MCP initialized:", resp.get("result", {}).get("serverInfo", {}).get("name"))

    async def _read_loop(self):
        if not self.proc or not self.proc.stdout:
            return
        loop = asyncio.get_event_loop()
        reader = self.proc.stdout
        while True:
            line = await loop.run_in_executor(None, reader.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                resp_id = resp.get("id")
                if resp_id is not None and resp_id in self._pending:
                    self._pending[resp_id].set_result(resp)
            except json.JSONDecodeError:
                pass

    async def _send(self, request: dict, timeout: float = 30) -> dict:
        if not self.proc or self.proc.poll() is not None:
            await self.start()
        assert self.proc and self.proc.stdin

        msg_id = request.get("id")
        line = json.dumps(request, separators=(",", ":")) + "\n"
        self.proc.stdin.write(line.encode())
        self.proc.stdin.flush()

        if msg_id is None:
            return {}

        future = asyncio.get_event_loop().create_future()
        async with self._lock:
            self._pending[msg_id] = future

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return {"error": "timeout"}
        finally:
            async with self._lock:
                self._pending.pop(msg_id, None)

    async def list_apps(self) -> str:
        resp = await self._send({"jsonrpc": "2.0", "id": 100, "method": "tools/call",
                                  "params": {"name": "list_apps", "arguments": {}}})
        return resp.get("result", {}).get("content", [{}])[0].get("text", "[]")

    async def get_state(self, app: str) -> dict:
        resp = await self._send({"jsonrpc": "2.0", "id": 101, "method": "tools/call",
                                  "params": {"name": "get_app_state", "arguments": {"app": app}}})
        content = resp.get("result", {}).get("content", [])
        result = {"text": "", "screenshot": None}
        for item in content:
            if item.get("type") == "text":
                result["text"] = item.get("text", "")
            elif item.get("type") == "image":
                result["screenshot"] = item.get("data", "")
        return result

    async def call_tool(self, name: str, args: dict) -> str:
        resp = await self._send({"jsonrpc": "2.0", "id": 102, "method": "tools/call",
                                  "params": {"name": name, "arguments": args}})
        return resp.get("result", {}).get("content", [{}])[0].get("text", "")

    def stop(self):
        if self.proc:
            self.proc.terminate()


class StateBroadcaster:
    """Periodically captures state and broadcasts to all clients."""

    def __init__(self, bridge: AgentBridge):
        self.bridge = bridge
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.current_app = "Safari"
        self._running = False
        self._log: List[dict] = []

    async def register(self, ws):
        self.clients.add(ws)
        print(f"Client connected. Total: {len(self.clients)}")
        # Send current state
        try:
            await ws.send(json.dumps({
                "type": "state",
                "app": self.current_app,
                "apps": await self.bridge.list_apps(),
                "log": self.log_recent(20),
            }))
        except Exception:
            pass

    async def unregister(self, ws):
        self.clients.discard(ws)
        print(f"Client disconnected. Total: {len(self.clients)}")

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self.clients:
            try:
                await ws.send(json.dumps(message))
            except Exception:
                dead.add(ws)
        self.clients -= dead

    def log_add(self, entry: dict):
        entry["time"] = time.time()
        self._log.append(entry)
        if len(self._log) > 100:
            self._log = self._log[-100:]

    def log_recent(self, n: int = 20) -> list:
        return self._log[-n:]

    async def capture_loop(self):
        """Periodically capture screenshot and broadcast."""
        self._running = True
        while self._running:
            try:
                state = await self.bridge.get_state(self.current_app)
                await self.broadcast({
                    "type": "screenshot",
                    "app": self.current_app,
                    "screenshot": state.get("screenshot"),
                    "text": state.get("text", "")[:2000],
                })
                self.log_add({"action": "screenshot", "app": self.current_app})
            except Exception as e:
                self.log_add({"action": "error", "message": str(e)})
            await asyncio.sleep(SCREENSHOT_INTERVAL)

    async def handle_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "set_app":
            self.current_app = msg.get("app", self.current_app)
            state = await self.bridge.get_state(self.current_app)
            await ws.send(json.dumps({
                "type": "state",
                "app": self.current_app,
                "text": state.get("text", ""),
                "screenshot": state.get("screenshot"),
            }))
            self.log_add({"action": "switch_app", "app": self.current_app})

        elif msg_type == "action":
            tool = msg.get("tool", "")
            args = msg.get("args", {})
            args["app"] = self.current_app
            result = await self.bridge.call_tool(tool, args)
            self.log_add({"action": tool, "args": args, "result": result[:200]})

            # Capture state after action
            state = await self.bridge.get_state(self.current_app)
            await self.broadcast({
                "type": "screenshot",
                "app": self.current_app,
                "screenshot": state.get("screenshot"),
                "text": state.get("text", "")[:2000],
            })

        elif msg_type == "list_apps":
            apps = await self.bridge.list_apps()
            await ws.send(json.dumps({"type": "apps", "apps": apps}))

        elif msg_type == "screenshot":
            state = await self.bridge.get_state(self.current_app)
            await ws.send(json.dumps({
                "type": "screenshot",
                "app": self.current_app,
                "screenshot": state.get("screenshot"),
                "text": state.get("text", "")[:2000],
            }))


async def main():
    bridge = AgentBridge()
    broadcaster = StateBroadcaster(bridge)

    await bridge.start()
    print(f"MCP bridge started")

    # Start capture loop
    asyncio.create_task(broadcaster.capture_loop())

    async def handler(ws):
        await broadcaster.register(ws)
        try:
            async for message in ws:
                await broadcaster.handle_message(ws, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            await broadcaster.unregister(ws)

    async with serve(handler, HOST, PORT):
        print(f"WebSocket server running on ws://{HOST}:{PORT}")
        print(f"Connect from Android app to ws://YOUR_COMPUTER_IP:{PORT}")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down")
