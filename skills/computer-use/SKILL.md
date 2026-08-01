---
name: computer-use
description: |
  Fast macOS computer use via MCP (open-computer-use).
  200x faster than cu CLI: no screencapture, no cliclick, no file I/O.
  Uses Accessibility tree + element indices for instant actions.
---

# Computer Use — Fast (MCP)

**USE MCP TOOLS ONLY. NEVER use `cu` CLI or `screencapture`.**

## Available Tools

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
| `perform_secondary_action` | instant | Context menus, expand |
| `select_text` | instant | Select text in field |

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

## App Resolution

App can be:
- Display name: `"Safari"`, `"Finder"`, `"Visual Studio Code"`
- Bundle ID: `"com.apple.Safari"`, `"com.apple.finder"`
- Path: `"/Applications/Safari.app"`

## Performance

| Method | get_app_state | click | Total |
|--------|--------------|-------|-------|
| **MCP (this)** | ~1s | instant | **~1s** |
| cu CLI | ~3s | ~1s | ~4s |

## Example

```
# Open Safari and navigate
get_app_state("Safari")
→ tree shows element 42 is address bar

click("Safari", element_index="42")
type_text("Safari", "github.com")
press_key("Safari", "Return")
get_app_state("Safari")
→ verify page loaded
```
