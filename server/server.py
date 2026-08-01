"""WebSocket server for streaming Computer Use state to mobile clients.

Streams screenshots + accessibility tree to connected Android app.
Supports tunnels for remote access from anywhere.
Includes AI agent chat via Google Gemini (free, with vision).

Usage:
    python server.py                        # local only
    python server.py --tunnel ngrok         # via ngrok
    python server.py --gemini-key YOUR_KEY  # enable AI chat
"""

import asyncio
import base64
import json
import os
import shutil
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

try:
    import urllib.request
    import urllib.parse
except ImportError:
    pass

MCP_SERVER = os.path.join(os.path.dirname(__file__), "..", "serve.py")
SCREENSHOT_INTERVAL = 2.0
HOST = "0.0.0.0"
PORT = 8765
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Groq (free, fast, no vision but good text)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class TunnelManager:
    """Manages tunnel for remote access."""

    def __init__(self, tunnel_type: str, port: int):
        self.tunnel_type = tunnel_type
        self.port = port
        self.proc: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None

    async def start(self) -> str:
        if self.tunnel_type == "ngrok":
            return await self._start_ngrok()
        elif self.tunnel_type == "cloudflare":
            return await self._start_cloudflare()
        elif self.tunnel_type == "localtunnel":
            return await self._start_localtunnel()
        else:
            raise ValueError(f"Unknown tunnel type: {self.tunnel_type}")

    async def _start_ngrok(self) -> str:
        if not shutil.which("ngrok"):
            print("Installing ngrok...")
            subprocess.run(["brew", "install", "ngrok"], check=True)

        self.proc = subprocess.Popen(
            ["ngrok", "http", str(self.port), "--log=stdout"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # Wait for tunnel URL
        for _ in range(30):
            await asyncio.sleep(1)
            try:
                import urllib.request
                resp = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels")
                data = json.loads(resp.read())
                for tunnel in data.get("tunnels", []):
                    if tunnel.get("proto") == "https":
                        self.public_url = tunnel["public_url"]
                        return self.public_url
            except Exception:
                pass

        raise RuntimeError("Failed to start ngrok tunnel")

    async def _start_cloudflare(self) -> str:
        if not shutil.which("cloudflared"):
            print("Installing cloudflared...")
            subprocess.run(["brew", "install", "cloudflared"], check=True)

        self.proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{self.port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # Wait for tunnel URL from output
        for _ in range(30):
            if self.proc.stdout:
                line = self.proc.stdout.readline().decode()
                if "trycloudflare.com" in line:
                    # Extract URL
                    for word in line.split():
                        if "trycloudflare.com" in word:
                            self.public_url = word.strip()
                            return self.public_url
            await asyncio.sleep(1)

        raise RuntimeError("Failed to start cloudflare tunnel")

    async def _start_localtunnel(self) -> str:
        if not shutil.which("lt"):
            print("Installing localtunnel...")
            subprocess.run(["npm", "install", "-g", "localtunnel"], check=True)

        self.proc = subprocess.Popen(
            ["lt", "--port", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        for _ in range(30):
            if self.proc.stdout:
                line = self.proc.stdout.readline().decode().strip()
                if "your url is" in line.lower() or "loca.lt" in line:
                    # Extract URL
                    for word in line.split():
                        if "loca.lt" in word:
                            self.public_url = word.strip()
                            return self.public_url
            await asyncio.sleep(1)

        raise RuntimeError("Failed to start localtunnel")

    def stop(self):
        if self.proc:
            self.proc.terminate()


class AgentBridge:
    """Bridges MCP server to WebSocket clients."""

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._lock = asyncio.Lock()
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
        asyncio.create_task(self._read_loop())

        resp = await self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                              "clientInfo": {"name": "mobile-viewer", "version": "1.0"}}})
        print("MCP initialized:", resp.get("result", {}).get("serverInfo", {}).get("name"))

    async def _read_loop(self):
        if not self.proc or not self.proc.stdout:
            return
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, self.proc.stdout.readline)
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


class GeminiChat:
    """Free AI chat with vision via Google Gemini or Groq fallback."""

    def __init__(self, api_key: str, groq_key: Optional[str] = None):
        self.api_key = api_key
        self.groq_key = groq_key
        self.history: List[dict] = []

    async def chat(self, message: str, screenshot_b64: Optional[str] = None) -> str:
        # Try Gemini first
        try:
            return await self._gemini_chat(message, screenshot_b64)
        except Exception as e:
            # Try Groq fallback
            if self.groq_key:
                try:
                    return await self._groq_chat(message)
                except Exception as e2:
                    return f"AI error (Groq): {e2}"
            return f"AI error: {e}"

    async def _gemini_chat(self, message: str, screenshot_b64: Optional[str] = None) -> str:
        contents = list(self.history[-10:])
        parts = [{"text": message}]
        if screenshot_b64:
            parts.append({"inlineData": {"mimeType": "image/png", "data": screenshot_b64}})
        contents.append({"role": "user", "parts": parts})

        system_prompt = """You are a Computer Use agent. You can see the user's screen and control their Mac.

To perform actions, use these EXACT commands (one per line):
ACTION:CLICK:<element_index>
ACTION:TYPE:<text>
ACTION:KEY:<key>
ACTION:SCROLL:<element_index>:<direction>
ACTION:SET_VALUE:<element_index>:<value>

Examples:
- To click element 5: ACTION:CLICK:5
- To type "hello": ACTION:TYPE:hello
- To press Enter: ACTION:KEY:Return
- To scroll down on element 3: ACTION:SCROLL:3:down

After describing what you see, include the action command on a separate line.
Always respond in the same language the user writes in."""

        payload = json.dumps({
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]}
        }).encode()

        url = f"{GEMINI_API_URL}?key={self.api_key}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        self.history.append({"role": "user", "parts": [{"text": message}]})
        self.history.append({"role": "model", "parts": [{"text": text}]})
        return text

    async def _groq_chat(self, message: str) -> str:
        system_prompt = """You are a Computer Use agent. You can see the user's screen and control their Mac.

To perform actions, use these EXACT commands (one per line):
ACTION:CLICK:<element_index>
ACTION:TYPE:<text>
ACTION:KEY:<key>
ACTION:SCROLL:<element_index>:<direction>

Examples:
- To click element 5: ACTION:CLICK:5
- To type "hello": ACTION:TYPE:hello
- To press Enter: ACTION:KEY:Return
- To scroll down on element 3: ACTION:SCROLL:3:down

After describing what you see, include the action command on a separate line.
Always respond in the same language the user writes in."""

        messages = [{"role": "system", "content": system_prompt}]
        for h in self.history[-10:]:
            messages.append({"role": h["role"], "content": h["parts"][0]["text"]})
        messages.append({"role": "user", "content": message})

        payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": 1024
        }).encode()

        req = urllib.request.Request(GROQ_API_URL, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.groq_key}",
            "User-Agent": "SkyCUA/1.0"
        })
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"]
        self.history.append({"role": "user", "parts": [{"text": message}]})
        self.history.append({"role": "model", "parts": [{"text": text}]})
        return text

    def clear(self):
        self.history = []


class StateBroadcaster:
    """Periodically captures state and broadcasts to all clients."""

    CHAT_FILE = "/tmp/skycua-chat.json"

    def __init__(self, bridge: AgentBridge, gemini: Optional[GeminiChat] = None):
        self.bridge = bridge
        self.gemini = gemini
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.current_app = "Safari"
        self._running = False
        self._log: List[dict] = []
        self._last_screenshot: Optional[str] = None
        self._chat_queue: List[dict] = []
        self._chat_responses: Dict[str, str] = {}
        # Init chat file
        if not os.path.exists(self.CHAT_FILE):
            self._write_chat_file()

    @staticmethod
    def parse_actions(text: str) -> List[dict]:
        import re
        actions = []
        pattern = r'ACTION:(CLICK|TYPE|KEY|SCROLL|SET_VALUE):([^\n]+)'
        for match in re.finditer(pattern, text):
            action_type = match.group(1)
            payload = match.group(2).strip()
            if action_type == "CLICK":
                if "," in payload:
                    x, y = payload.split(",", 1)
                    actions.append({"tool": "click", "args": {"x": int(x.strip()), "y": int(y.strip())}})
                else:
                    actions.append({"tool": "click", "args": {"element_index": payload}})
            elif action_type == "TYPE":
                actions.append({"tool": "type_text", "args": {"text": payload}})
            elif action_type == "KEY":
                actions.append({"tool": "press_key", "args": {"key": payload}})
            elif action_type == "SCROLL":
                parts = payload.split(":")
                if len(parts) == 2:
                    actions.append({"tool": "scroll", "args": {"element_index": parts[0], "direction": parts[1]}})
            elif action_type == "SET_VALUE":
                parts = payload.split(":", 1)
                if len(parts) == 2:
                    actions.append({"tool": "set_value", "args": {"element_index": parts[0], "value": parts[1]}})
        return actions

    async def register(self, ws):
        self.clients.add(ws)
        print(f"Client connected. Total: {len(self.clients)}")
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

    def _write_chat_file(self):
        data = {
            "queue": self._chat_queue,
            "responses": self._chat_responses,
            "app": self.current_app,
            "screenshot": self._last_screenshot,
        }
        try:
            with open(self.CHAT_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _read_chat_file(self):
        try:
            with open(self.CHAT_FILE, "r") as f:
                data = json.load(f)
            # Check for responses from OpenCode
            for msg_id, response in data.get("responses", {}).items():
                if msg_id not in self._chat_responses:
                    self._chat_responses[msg_id] = response
            # Check for new commands from OpenCode
            for cmd in data.get("commands", []):
                self._chat_queue.append(cmd)
            # Clear processed commands
            data["commands"] = []
            data["responses"] = {}
            self._write_chat_file()
        except Exception:
            pass

    async def capture_loop(self):
        self._running = True
        while self._running:
            try:
                state = await self.bridge.get_state(self.current_app)
                self._last_screenshot = state.get("screenshot")
                await self.broadcast({
                    "type": "screenshot",
                    "app": self.current_app,
                    "screenshot": self._last_screenshot,
                    "text": state.get("text", "")[:2000],
                })
                self.log_add({"action": "screenshot", "app": self.current_app})
                # Read chat file for OpenCode responses
                self._read_chat_file()
                # Check for pending responses
                for msg_id, response in list(self._chat_responses.items()):
                    await self.broadcast({"type": "chat_response", "id": msg_id, "text": response})
                    del self._chat_responses[msg_id]
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
            self._last_screenshot = state.get("screenshot")
            await ws.send(json.dumps({
                "type": "screenshot",
                "app": self.current_app,
                "screenshot": self._last_screenshot,
                "text": state.get("text", "")[:2000],
            }))

        elif msg_type == "chat":
            text = msg.get("text", "")
            if not text:
                return

            msg_id = f"msg_{int(time.time()*1000)}"

            # Add user message to chat file
            self._chat_queue.append({
                "id": msg_id,
                "role": "user",
                "text": text,
                "app": self.current_app,
                "screenshot": self._last_screenshot,
                "tree": (await self.bridge.get_state(self.current_app)).get("text", "")[:3000],
            })
            self._write_chat_file()

            self.log_add({"action": "chat", "query": text[:100], "id": msg_id})
            await ws.send(json.dumps({"type": "chat_thinking", "id": msg_id}))

        elif msg_type == "chat_clear":
            self._chat_queue = []
            self._chat_responses = {}
            self._write_chat_file()
            await ws.send(json.dumps({"type": "chat_cleared"}))


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tunnel", choices=["ngrok", "cloudflare", "localtunnel"],
                        help="Enable tunnel for remote access")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--gemini-key", help="Google Gemini API key for AI chat (free tier)")
    parser.add_argument("--groq-key", help="Groq API key (free fallback, no vision)")
    args = parser.parse_args()

    bridge = AgentBridge()
    gemini = GeminiChat(args.gemini_key, args.groq_key) if args.gemini_key else None
    broadcaster = StateBroadcaster(bridge, gemini)
    tunnel = None

    await bridge.start()

    # Start tunnel if requested
    if args.tunnel:
        tunnel = TunnelManager(args.tunnel, args.port)
        try:
            url = await tunnel.start()
            print(f"\n{'='*50}")
            print(f"TUNNEL ACTIVE: {url}")
            print(f"Enter this URL in Android app")
            print(f"{'='*50}\n")
        except Exception as e:
            print(f"Tunnel failed: {e}")
            print("Falling back to local mode")

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

    async with serve(handler, HOST, args.port):
        print(f"WebSocket server on ws://0.0.0.0:{args.port}")
        if not tunnel:
            local_ip = _get_local_ip()
            print(f"Local: ws://localhost:{args.port}")
            print(f"LAN:   ws://{local_ip}:{args.port}")
        print("Press Ctrl+C to stop")
        await asyncio.Future()


def _get_local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down")
