# .pids Directory - Agent Guide

## Purpose

This directory stores Process ID (PID) files for development services managed by `scripts/dev.sh`. PID files allow the dev script to track and manage running backend and frontend processes.

## Directory Contents

```
.pids/
  AGENTS.md       # This file
  backend.pid     # Backend API server process ID
  frontend.pid    # Frontend dev server process ID
```

## Key Files

### backend.pid

**Purpose:** Stores the process ID of the running FastAPI backend server.

**Created by:** `scripts/dev.sh start` when starting the backend

**Contains:** Single line with the PID number (e.g., `12345`)

**Used for:**

- Checking if backend is running: `scripts/dev.sh status`
- Stopping backend gracefully: `scripts/dev.sh stop`
- Restarting backend: `scripts/dev.sh restart`

### frontend.pid

**Purpose:** Stores the process ID of the running Vite frontend dev server.

**Created by:** `scripts/dev.sh start` when starting the frontend

**Contains:** Single line with the PID number (e.g., `12346`)

**Used for:**

- Checking if frontend is running: `scripts/dev.sh status`
- Stopping frontend gracefully: `scripts/dev.sh stop`
- Restarting frontend: `scripts/dev.sh restart`

## Usage

### How PID Files Work

1. **Start services:**

   ```bash
   ./scripts/dev.sh start
   # Creates .pids/backend.pid and .pids/frontend.pid
   ```

2. **Check status:**

   ```bash
   ./scripts/dev.sh status
   # Reads PID files and checks if processes are running
   ```

3. **Stop services:**
   ```bash
   ./scripts/dev.sh stop
   # Reads PID files, sends SIGTERM to processes
   # Removes PID files after successful stop
   ```

### Process Management

The dev script uses these PID files to:

- **Prevent duplicate starts** - Check if process is already running
- **Graceful shutdown** - Send proper termination signal to process
- **Status reporting** - Show which services are running and their PIDs
- **Cleanup** - Remove stale PID files if process no longer exists

## Git Ignore Rules

PID files are excluded from version control:

```gitignore
.pids/*.pid
```

Only this `AGENTS.md` file is tracked in git. Actual PID files are runtime-only.

## Troubleshooting

### Stale PID Files

If a service crashes or is killed unexpectedly, PID files may remain:

```bash
# Check if process is actually running
ps aux | grep <pid>

# Remove stale PID file
rm .pids/backend.pid

# Or restart to clean up
./scripts/dev.sh restart
```

### Missing PID Files

If services are running but PID files are missing:

```bash
# Stop all manually
pkill -f uvicorn  # Backend
pkill -f vite     # Frontend

# Restart using dev script
./scripts/dev.sh start
```

## Alternative: Container Management

For production deployments, services run in containers without PID files:

```bash
# Container-based management (no PID files)
podman-compose -f docker-compose.prod.yml up -d
podman-compose -f docker-compose.prod.yml ps
podman-compose -f docker-compose.prod.yml stop
```

PID files are only used for local development with `scripts/dev.sh`.

## Related Files

- `/scripts/dev.sh` - Development service manager that creates/uses PID files
- `/backend/main.py` - Backend server entry point
- `/frontend/vite.config.ts` - Frontend dev server configuration

## Notes for AI Agents

- Do NOT commit PID files to version control
- PID files are created and managed automatically by `scripts/dev.sh`
- If you need to check service status, use `./scripts/dev.sh status` instead of reading PID files directly
- PID files are process-specific and become invalid if services are restarted
- This directory is only relevant for local development, not for container deployments
