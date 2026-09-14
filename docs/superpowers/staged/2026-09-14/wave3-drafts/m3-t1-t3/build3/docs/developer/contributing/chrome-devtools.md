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
- Node.js v20.19+ or v22.12+ with npx (Vite 7 requirement)
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

**CRITICAL:** In headless/SSH environments, you must configure the `CHROME_WS_ENDPOINT` environment variable so the MCP server connects to your existing headless Chrome instance instead of trying to launch its own browser.

```bash
# For headless environments (SSH, servers, no X11):
claude mcp add chrome-devtools -e CHROME_WS_ENDPOINT=ws://127.0.0.1:9222 -- npx chrome-devtools-mcp@latest

# For desktop environments with display:
claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest
```

Without `CHROME_WS_ENDPOINT`, the MCP server attempts to launch a new browser instance, which fails in headless environments with:

```
Missing X server to start the headful browser.
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

Once connected, the following MCP tools become available (prefixed with `mcp__chrome-devtools__`):

| Tool                          | Description                                     |
| ----------------------------- | ----------------------------------------------- |
| `navigate_page`               | Navigate to a URL, back/forward, or reload      |
| `new_page`                    | Create a new browser tab                        |
| `list_pages`                  | List all open pages in the browser              |
| `select_page`                 | Select a page as context for future operations  |
| `close_page`                  | Close a page by index                           |
| `take_snapshot`               | Get page content/DOM via accessibility tree     |
| `take_screenshot`             | Capture a screenshot of page or element         |
| `click`                       | Click an element by uid from snapshot           |
| `fill`                        | Type text into input/textarea/select            |
| `fill_form`                   | Fill multiple form elements at once             |
| `hover`                       | Hover over an element                           |
| `press_key`                   | Press a key or key combination                  |
| `drag`                        | Drag an element onto another                    |
| `evaluate_script`             | Execute JavaScript in the page context          |
| `list_console_messages`       | Retrieve console output (log, warn, error)      |
| `get_console_message`         | Get details of a specific console message       |
| `list_network_requests`       | View network requests since last navigation     |
| `get_network_request`         | Get details of a specific network request       |
| `wait_for`                    | Wait for text to appear on the page             |
| `handle_dialog`               | Accept or dismiss browser dialogs (alert, etc.) |
| `upload_file`                 | Upload a file through a file input element      |
| `resize_page`                 | Resize the page window dimensions               |
| `emulate`                     | Emulate CPU throttling, network, geolocation    |
| `performance_start_trace`     | Start a performance trace recording             |
| `performance_stop_trace`      | Stop the performance trace                      |
| `performance_analyze_insight` | Analyze a specific performance insight          |

## Usage Examples

### Inspect a Page for Console Errors

```
Navigate to http://localhost:5173 and check the console for any errors or warnings.
```

### Debug a Form Submission

```
Go to http://localhost:5173/login, fill in the username field with "test@example.com",
submit the form, and report any console errors or network failures.
```

### Capture Visual State

```
Take a screenshot of http://localhost:5173 after it finishes loading.
```

### Analyze JavaScript Errors

```
Navigate to http://localhost:5173, wait for the page to load, then check for any
uncaught exceptions or JavaScript errors in the console. Also check the network
tab for any failed requests.
```

### DOM Inspection

```
Go to http://localhost:5173 and find all elements with the class "error-message".
Report their text content and visibility state.
```

## Troubleshooting

### "Missing X server to start the headful browser"

This error occurs when the MCP server tries to launch its own Chrome browser in a headless environment (SSH, servers, containers).

**Solution:** Configure the MCP server to connect to your existing headless Chrome instance:

```bash
# Remove existing configuration
claude mcp remove chrome-devtools

# Re-add with CHROME_WS_ENDPOINT
claude mcp add chrome-devtools -e CHROME_WS_ENDPOINT=ws://127.0.0.1:9222 -- npx chrome-devtools-mcp@latest

# Restart Claude Code (MCP tools load at session start)
```

**Verify Chrome is running first:**

```bash
curl -s http://127.0.0.1:9222/json/version
```

### MCP Server Shows "Failed to connect"

1. Ensure Chrome is running with remote debugging enabled:

   ```bash
   curl -s http://127.0.0.1:9222/json/version
   ```

2. If Chrome crashed, restart it:

   ```bash
   pkill -9 chrome
   rm -f /tmp/chrome-debug-profile/SingletonLock
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

### Chrome Won't Start - "SingletonLock: File exists"

This occurs when Chrome crashed or was killed without cleanup:

```bash
# Error message:
# Failed to create /tmp/chrome-debug-profile/SingletonLock: File exists

# Solution:
pkill -9 -f "chrome.*remote-debugging"
rm -f /tmp/chrome-debug-profile/SingletonLock
google-chrome --headless=new --remote-debugging-port=9222 --disable-gpu --no-sandbox --disable-dev-shm-usage --user-data-dir=/tmp/chrome-debug-profile &
```

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
- Environment: `CHROME_WS_ENDPOINT=ws://127.0.0.1:9222`

**Quick Status Check:**

```bash
# Verify Chrome is running
curl -s http://127.0.0.1:9222/json/version

# Verify MCP is connected
claude mcp list
```

## Security Considerations

- The `--no-sandbox` flag reduces Chrome's security isolation. Use only in trusted environments.
- The DevTools port (9222) should not be exposed to untrusted networks.
- The user-data-dir may contain sensitive data from browsed pages.

## Related Documentation

- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [chrome-devtools-mcp npm package](https://www.npmjs.com/package/chrome-devtools-mcp)
