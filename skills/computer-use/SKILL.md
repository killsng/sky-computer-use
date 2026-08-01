---
name: computer-use
description: |
  Fast macOS computer use via OpenCode plugin + MCP.
  Control your Mac from Android app or directly from OpenCode.
  200x faster than cu CLI: no screencapture, no cliclick, no file I/O.
  Uses Accessibility tree + element indices for instant actions.
---

# Computer Use — Fast (Plugin + MCP)

**USE PLUGIN TOOLS. NEVER use `cu` CLI or `screencapture`.**

## Architecture

```
Android App ←→ WebSocket (port 8765) ←→ OpenCode Plugin ←→ MCP Binary ←→ Mac
```

## Plugin Tools (computer_use)

| Tool | Description |
|------|-------------|
| `computer_use(action="screenshot")` | Capture screen |
| `computer_use(action="list_apps")` | List running apps |
| `computer_use(action="click", element="N")` | Click element N |
| `computer_use(action="type", text="hello")` | Type text |
| `computer_use(action="key", target="Return")` | Press key |
| `computer_use(action="scroll", element="N", target="down")` | Scroll |
| `computer_use(action="switch_app", target="Safari")` | Switch app |

## MCP Tools (direct)

| Tool | Speed | When |
|------|-------|------|
| `get_app_state` | ~1s | Always call first |
| `list_apps` | instant | Find app names |
| `click` | instant | Click by element_index |
| `press_key` | instant | Keyboard shortcuts |
| `type_text` | instant | Type text |
| `scroll` | instant | Scroll element |
| `set_value` | instant | Set input value |
| `drag` | instant | Drag between coordinates |

## Workflow

```
1. get_app_state("AppName")        → accessibility tree + screenshot
2. click("AppName", element_index="N")  → click element N
3. type_text("AppName", "text")    → type
4. press_key("AppName", "Return")  → press key
5. get_app_state("AppName")        → verify result
```

## Rules

1. **ALWAYS call `get_app_state` first** — gives you the tree with element indices
2. **Use `element_index`** — never use coordinates unless no element exists
3. **One action per turn** — click, then verify with get_app_state
4. **element_index is a string** — "0", "1", "42", not integers
5. **xdotool keys** — `Return`, `Tab`, `Escape`, `super+c`, `cmd+a`

## Key Reference

| Key | xdotool |
|-----|---------|
| Enter | `Return` |
| Escape | `Escape` |
| Tab | `Tab` |
| Delete | `Delete` |
| Arrow keys | `Up`, `Down`, `Left`, `Right` |
| Cmd+C | `super+c` |
| Cmd+V | `super+v` |
| Cmd+A | `super+a` |

## Android App

The Android app connects via WebSocket to `ws://localhost:8765` (or via ngrok tunnel).

Features:
- Real-time screen streaming
- Tappable screenshot (click by coordinates)
- Quick action buttons (keyboard shortcuts)
- Chat with OpenCode agent

## Performance

| Method | get_app_state | click | Total |
|--------|--------------|-------|-------|
| **Plugin (this)** | ~1s | instant | **~1s** |
| cu CLI | ~3s | ~1s | ~4s |
