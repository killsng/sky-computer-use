# sky-computer-use

Pure Python MCP server for Sky Computer Use daemon on macOS.

Reverse-engineered from Codex Computer Use (`@oai/sky` + `SkyComputerUseClient`).

## What is this?

ChatGPT.app ships with a "Computer Use" feature that lets an LLM control your Mac apps via Accessibility API. The daemon (`com.openai.sky.CUAService`) runs in the background and exposes a Unix socket. This project provides a standalone MCP server that wraps the existing `SkyComputerUseClient` binary, making it usable from opencode and other MCP-compatible tools.

## Requirements

- macOS 14+
- ChatGPT.app installed (provides the daemon + `SkyComputerUseClient` binary)
- Python 3.9+
- Screen Recording + Accessibility permissions granted to ChatGPT.app

## Install

```bash
git clone https://github.com/matvij/sky-computer-use.git
cd sky-computer-use
pip install -e .
```

## Usage

### As opencode MCP server

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "sky-computer-use": {
      "type": "local",
      "command": ["python3", "serve.py"],
      "cwd": "/Users/YOU/sky-computer-use"
    }
  }
}
```

### As Python library

```python
from src.sky_client import SkyClient

client = SkyClient()
apps = client.list_apps()
state = client.get_app_state("Safari")
client.click("Safari", element_index=42)
```

### As CLI

```bash
python3 serve.py  # runs MCP server on stdio
```

## Tools

| Tool | Description |
|------|-------------|
| `list_apps` | List running and recently used apps |
| `get_app_state` | Get screenshot + accessibility tree for an app |
| `click` | Click element by index or coordinates |
| `press_key` | Press key or key combination (xdotool syntax) |
| `type_text` | Type text via keyboard input |
| `scroll` | Scroll element by page count |
| `set_value` | Set value of editable element |
| `drag` | Drag from point to point |
| `perform_secondary_action` | Invoke secondary accessibility action |
| `select_text` | Select text or place cursor in editable element |

## How it works

```
┌─────────────────────────────────────────────────────┐
│  opencode / LLM agent                              │
│    ↓ (MCP protocol over stdio)                     │
│  serve.py (Python MCP server)                      │
│    ↓ (spawns binary subprocess)                    │
│  SkyComputerUseClient mcp                          │
│    ↓ (JSON-RPC 2.0 over unix socket)              │
│  computeruse.sock                                  │
│    ↓                                               │
│  SkyComputerUseService (com.openai.sky.CUAService) │
│    ↓ (Accessibility API + ScreenCapture)           │
│  macOS UI                                          │
└─────────────────────────────────────────────────────┘
```

## Architecture Notes

### Daemon Socket Protocol

- **Transport:** Unix socket
- **Path:** `~/Library/Group Containers/2DC432GLL2.com.openai.sky.CUAService/IPC/computeruse.sock`
- **Protocol:** JSON-RPC 2.0, 4-byte LE length prefix
- **API version:** `CodexComputerUseIPC-2`

The daemon verifies code signature of connecting processes. Unsigned clients (like raw Python sockets) are rejected. The `SkyComputerUseClient` binary is signed and can connect.

### Request Types

| RequestType | Purpose |
|-------------|---------|
| `ComputerUseIPCListAppsRequest` | List available apps |
| `ComputerUseIPCAppStartRequest` | Start/launch an app |
| `ComputerUseIPCAppGetSkyshotRequest` | Get screenshot + accessibility tree |
| `ComputerUseIPCAppPerformActionRequest` | Perform UI action (click, type, scroll, etc.) |
| `ComputerUseIPCAppPolicyRequest` | Get app policy |

### Action Payloads

Actions are nested in `ComputerUseIPCAppPerformActionRequest`:

```json
{
  "action": {
    "click": {
      "at": {"elementIndex": 42},
      "clickCount": 1,
      "mouseButton": "left"
    }
  }
}
```

```json
{
  "action": {
    "pressKey": {"_0": "Return"}
  }
}
```

```json
{
  "action": {
    "scroll": {
      "at": {"elementIndex": 10},
      "direction": "down",
      "pages": 1
    }
  }
}
```

## License

MIT
