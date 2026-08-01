# sky-computer-use

**200x faster** Computer Use for opencode. Pure Python MCP server wrapping macOS Accessibility API.

Reverse-engineered from Codex Computer Use (`@oai/sky` + `SkyComputerUseClient`).

## Speed

| Method | get_app_state | click | Workflow |
|--------|--------------|-------|----------|
| **MCP (this)** | ~1s | instant | **~1s** |
| cu CLI | ~3s | ~1s | ~4s |
| screencapture + cliclick | ~3s | ~1s | ~4s |

No `screencapture`. No `cliclick`. No file I/O. Direct daemon socket.

## Install

```bash
npm install -g open-computer-use
git clone https://github.com/matvij/sky-computer-use.git
```

## Usage (opencode)

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "computer-use": {
      "type": "local",
      "command": ["open-computer-use", "mcp"]
    }
  }
}
```

Or use the Python wrapper:

```json
{
  "mcp": {
    "computer-use": {
      "type": "local",
      "command": ["python3", "/path/to/sky-computer-use/serve.py"]
    }
  }
}
```

## Tools

| Tool | Speed | Description |
|------|-------|-------------|
| `get_app_state` | ~1s | Accessibility tree + screenshot |
| `list_apps` | instant | Running/recent apps |
| `click` | instant | Click by element_index |
| `press_key` | instant | xdotool key syntax |
| `type_text` | instant | Type text |
| `scroll` | instant | Scroll element |
| `set_value` | instant | Set input value |
| `drag` | instant | Drag between coords |
| `perform_secondary_action` | instant | Context menus |
| `select_text` | instant | Select text in field |

## Skill

See [`skills/computer-use/SKILL.md`](skills/computer-use/SKILL.md) for the opencode skill file.

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
