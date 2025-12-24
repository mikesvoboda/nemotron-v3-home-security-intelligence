# Chrome DevTools MCP Server Guide

This document explains how to use the Chrome DevTools MCP (Model Context Protocol) server for inspecting rendered web pages, capturing console errors, and debugging UI issues from Claude Code.

## Overview

The Chrome DevTools MCP server connects Claude Code to a running Chrome instance via the Chrome DevTools Protocol. This allows agents to:

- Navigate to URLs and inspect rendered pages
- Read console logs, errors, and warnings
- Inspect the DOM structure
- Execute JavaScript in the page context
- Capture screenshots
- Monitor network requests
- Debug JavaScript and analyze performance

## Prerequisites

- Google Chrome installed (`/usr/bin/google-chrome` on this system)
- Node.js v18+ with npx
- Claude Code with MCP support

## Architecture

```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Claude Code   │────▶│  Chrome DevTools    │────▶│  Headless Chrome │
│                 │     │    MCP Server       │     │   (port 9222)    │
└─────────────────┘     └─────────────────────┘     └──────────────────┘
                              (stdio)                 (WebSocket CDP)
```

## Setup Instructions

### 1. Start Chrome in Headless Mode with Remote Debugging

For headless/SSH environments:

```bash
google-chrome \
  --headless=new \
  --remote-debugging-port=9222 \
  --disable-gpu \
  --no-sandbox \
  --disable-dev-shm-usage \
  --user-data-dir=/tmp/chrome-debug-profile &
```

**Flags explained:**

- `--headless=new`: New headless mode (Chrome 112+)
- `--remote-debugging-port=9222`: Enable DevTools protocol on port 9222
- `--disable-gpu`: Disable GPU acceleration (required for headless)
- `--no-sandbox`: Required for running as root or in containers
- `--disable-dev-shm-usage`: Prevent /dev/shm issues in Docker/limited environments
- `--user-data-dir`: Isolated profile to avoid conflicts

### 2. Verify Chrome is Running

```bash
# Check process
pgrep -a chrome

# Check port is listening
ss -tlnp | grep 9222

# Test DevTools API
curl -s http://127.0.0.1:9222/json/version
```

Expected response:

```json
{
  "Browser": "Chrome/142.0.7444.175",
  "Protocol-Version": "1.3",
  "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/..."
}
```

### 3. Add MCP Server to Claude Code

```bash
claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest
```

### 4. Verify MCP Connection

```bash
claude mcp list
```

Expected output:

```
chrome-devtools: npx chrome-devtools-mcp@latest - ✓ Connected
```

### 5. Restart Claude Code

MCP tools are loaded at session start. Exit and restart Claude Code to access the new tools.

## Available Tools

Once connected, the following MCP tools become available:

| Tool               | Description                                |
| ------------------ | ------------------------------------------ |
| `navigate`         | Navigate to a URL                          |
| `screenshot`       | Capture a screenshot of the current page   |
| `get_console_logs` | Retrieve console output (log, warn, error) |
| `evaluate`         | Execute JavaScript in the page context     |
| `get_page_content` | Get the current page HTML                  |
| `click`            | Click an element by selector               |
| `type`             | Type text into an input field              |
| `get_network_logs` | View network requests and responses        |

## Usage Examples

### Inspect a Page for Console Errors

```
Navigate to http://localhost:3000 and check the console for any errors or warnings.
```

### Debug a Form Submission

```
Go to http://localhost:3000/login, fill in the username field with "test@example.com",
submit the form, and report any console errors or network failures.
```

### Capture Visual State

```
Take a screenshot of http://localhost:8080/dashboard after it finishes loading.
```

### Analyze JavaScript Errors

```
Navigate to http://localhost:3000, wait for the page to load, then check for any
uncaught exceptions or JavaScript errors in the console. Also check the network
tab for any failed requests.
```

### DOM Inspection

```
Go to http://localhost:3000 and find all elements with the class "error-message".
Report their text content and visibility state.
```

## Troubleshooting

### MCP Server Shows "Failed to connect"

1. Ensure Chrome is running with remote debugging enabled:

   ```bash
   curl -s http://127.0.0.1:9222/json/version
   ```

2. If Chrome crashed, restart it:

   ```bash
   pkill -9 chrome
   google-chrome --headless=new --remote-debugging-port=9222 --disable-gpu --no-sandbox --disable-dev-shm-usage --user-data-dir=/tmp/chrome-debug-profile &
   ```

3. Check for port conflicts:
   ```bash
   ss -tlnp | grep 9222
   ```

### Tools Not Available After Adding MCP Server

MCP tools are loaded at session start. You must restart Claude Code after adding the MCP server.

### Chrome Crashes Immediately

Common causes:

- Missing `--no-sandbox` when running as root
- Missing `--disable-dev-shm-usage` in Docker/container environments
- Insufficient memory

### Permission Denied Errors

Ensure the user running Claude Code has permission to execute Chrome and write to the user-data-dir.

## Keeping Chrome Running

For persistent usage, consider:

1. **Systemd service** (recommended for servers):

   ```ini
   # /etc/systemd/user/chrome-devtools.service
   [Unit]
   Description=Headless Chrome for DevTools

   [Service]
   ExecStart=/usr/bin/google-chrome --headless=new --remote-debugging-port=9222 --disable-gpu --no-sandbox --disable-dev-shm-usage --user-data-dir=/tmp/chrome-debug-profile
   Restart=always

   [Install]
   WantedBy=default.target
   ```

2. **Shell profile** (for interactive sessions):
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   if ! pgrep -f "chrome.*remote-debugging-port=9222" > /dev/null; then
     google-chrome --headless=new --remote-debugging-port=9222 --disable-gpu --no-sandbox --disable-dev-shm-usage --user-data-dir=/tmp/chrome-debug-profile &>/dev/null &
   fi
   ```

## Current Configuration

**Chrome Status:**

- Binary: `/usr/bin/google-chrome`
- Version: Chrome 142.0.7444.175
- Debugging Port: 9222
- User Data Dir: `/tmp/chrome-debug-profile`

**MCP Server:**

- Package: `chrome-devtools-mcp@latest`
- Transport: stdio
- Configuration: `~/.claude.json`

## Security Considerations

- The `--no-sandbox` flag reduces Chrome's security isolation. Use only in trusted environments.
- The DevTools port (9222) should not be exposed to untrusted networks.
- The user-data-dir may contain sensitive data from browsed pages.

## Related Documentation

- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [chrome-devtools-mcp npm package](https://www.npmjs.com/package/chrome-devtools-mcp)
