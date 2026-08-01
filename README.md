# Sky Computer Use

Control your Mac from Android phone with AI.

## Architecture

```
Android App ←→ WebSocket (8765) ←→ OpenCode Plugin ←→ MCP Binary ←→ Mac
```

## Components

### Android App
- Real-time screen streaming
- Tappable screenshot (click by coordinates)
- Quick action buttons (keyboard shortcuts)
- Chat with OpenCode agent

### OpenCode Plugin
- WebSocket server on port 8765
- `computer_use` tool for AI agents
- Auto-refresh screenshots

### MCP Binary
- `open-computer-use` npm package
- Accessibility tree access
- Element-based interactions

## Quick Start

1. Install OpenCode: `curl -fsSL https://opencode.ai/install | bash`
2. Install MCP: `npm i -g open-computer-use`
3. Start plugin (runs automatically with OpenCode)
4. Start ngrok: `ngrok http 8765`
5. Connect Android app to ngrok URL

## Android App

Download: [Releases](https://github.com/killsng/sky-computer-use/releases)

## Usage

```
# In OpenCode, use computer_use tool:
computer_use(action="screenshot")
computer_use(action="click", element="42")
computer_use(action="type", text="hello")
computer_use(action="key", target="Return")
```

## Links

- GitHub: https://github.com/killsng/sky-computer-use
- OpenCode: https://opencode.ai
- MCP: https://opencode.ai/docs/mcp-servers/
