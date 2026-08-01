---
name: sky-computer-use
description: |
  Pure Python client for SkyComputerUse daemon (macOS Computer Use).
  Provides: list_apps, get_app_state, click, press_key, type_text,
  scroll, set_value, drag, perform_secondary_action, select_text.
---

# Sky Computer Use — macOS

**RULE: NEVER write scripts. ONLY use `sky-cua` CLI or MCP tools to automate GUIs.**

## Prerequisites

1. ChatGPT.app must be installed (provides the daemon)
2. The daemon must be running (auto-starts when ChatGPT opens)
3. Grant permissions: System Settings → Privacy & Security → Screen Recording + Accessibility → ChatGPT

## Architecture

```
LLM agent → MCP server (mcp_server.py) → unix socket → SkyComputerUseService daemon → macOS UI
```

## MCP Server

Start the MCP server for use with opencode:

```bash
cd /path/to/sky-computer-use
python -m src.mcp_server
```

Register in `opencode.json`:

```json
{
  "mcp": {
    "sky-computer-use": {
      "type": "local",
      "command": ["python3", "-m", "src.mcp_server"],
      "cwd": "/path/to/sky-computer-use"
    }
  }
}
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

## Agent Workflow

```
1. get_app_state("Safari")          → get UI tree + screenshot
2. click("Safari", element_index=5) → click a link
3. type_text("Safari", "hello")     → type text
4. press_key("Safari", "Return")    → press Enter
5. get_app_state("Safari")          → verify result
```

## Protocol (for reference)

- **Transport:** Unix socket (`computeruse.sock`)
- **Protocol:** JSON-RPC 2.0, 4-byte LE length prefix
- **API version:** `CodexComputerUseIPC-2`
- **Socket path:** `~/Library/Group Containers/2DC432GLL2.com.openai.sky.CUAService/IPC/computeruse.sock`

## Python API

```python
from src.sky_client import SkyClient

client = SkyClient()
apps = client.list_apps()
state = client.get_app_state("Safari")
client.click("Safari", element_index=42)
```
