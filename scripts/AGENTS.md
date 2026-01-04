# Scripts Directory - Agent Guide

## Purpose

This directory contains development, testing, deployment, and maintenance scripts for the Home Security Intelligence project.

## Directory Contents

```
scripts/
  AGENTS.md                    # This file
  README.md                    # Quick reference for all scripts
  AI_STARTUP_README.md         # Quick reference for AI services
  setup.sh                     # Main setup script (Linux/macOS)
  setup.ps1                    # Main setup script (Windows)
  setup-hooks.sh               # Legacy setup script
  setup-systemd.sh             # Systemd service setup (Linux)
  setup-launchd.sh             # launchd service setup (macOS)
  setup-windows.ps1            # Windows Task Scheduler setup
  dev.sh                       # Development server management
  start-ai.sh                  # AI services management
  start_redis.sh               # Redis startup script
  validate.sh                  # Full validation (lint, type, test)
  test-runner.sh               # Test suite runner with coverage
  test-fast.sh                 # Fast parallel test runner
  test-docker.sh               # Docker Compose deployment testing
  test-prod-connectivity.sh    # Production connectivity tests
  smoke-test.sh                # End-to-end pipeline smoke test
  seed-cameras.py              # Database seeding script
  seed-mock-events.py          # Mock events seeding script
  db-migrate.sh                # Database migration script
  migrate-sqlite-to-postgres.py # SQLite to PostgreSQL migration
  migrate-file-types.py        # File type migration utility
  generate-types.sh            # TypeScript API type generation
  generate_certs.py            # SSL certificate generation
  setup-gpu-runner.sh          # GitHub Actions GPU runner setup
  find-slow-tests.sh           # Test performance debugging
  audit-test-durations.py      # CI test duration auditing
  check-test-mocks.py          # Pre-commit: mock validation
  check-test-timeouts.py       # Pre-commit: timeout validation
  github-models-examples.py    # GitHub Models API examples
```

## Key Scripts

### Development Setup

#### setup.sh

**Purpose:** Primary development environment setup script for Linux/macOS.

**What it does:**

1. Checks prerequisites (Python 3.14+, Node.js 20.19+/22.12+, Docker, NVIDIA drivers)
2. Creates Python virtual environment (`.venv`)
3. Installs backend dependencies from `backend/requirements.txt`
4. Installs dev tools (pre-commit, ruff, mypy)
5. Creates `.env` file from `.env.example`
6. Creates data directory and prepares database
7. Installs frontend dependencies (`npm install`)
8. Installs pre-commit hooks
9. Verifies all tools are working

**Usage:**

```bash
./scripts/setup.sh              # Full setup
./scripts/setup.sh --help       # Show options
./scripts/setup.sh --skip-gpu   # Skip NVIDIA GPU checks
./scripts/setup.sh --skip-tests # Skip verification tests
./scripts/setup.sh --clean      # Clean and reinstall
```

#### setup.ps1

**Purpose:** Development environment setup for Windows (PowerShell equivalent of setup.sh).

**Usage:**

```powershell
.\scripts\setup.ps1             # Full setup
.\scripts\setup.ps1 -Help       # Show options
.\scripts\setup.ps1 -SkipGpu    # Skip NVIDIA GPU checks
.\scripts\setup.ps1 -Clean      # Clean and reinstall
```

### Service Auto-Start Setup

#### setup-systemd.sh

**Purpose:** Configure systemd user services for container auto-start on Linux boot.

**What it does:**

1. Generates systemd unit files for Podman containers
2. Enables user-level lingering (allows services without login)
3. Configures auto-restart policies

**Usage:**

```bash
./scripts/setup-systemd.sh              # Setup auto-start
./scripts/setup-systemd.sh --uninstall  # Remove services
```

**Requirements:**

- Linux with systemd
- Podman containers already running
- User session (not root)

#### setup-launchd.sh

**Purpose:** Configure launchd user agents for container auto-start on macOS boot.

**What it does:**

1. Creates plist files for Podman containers
2. Loads agents into launchd
3. Enables auto-start on user login

**Usage:**

```bash
./scripts/setup-launchd.sh              # Setup auto-start
./scripts/setup-launchd.sh --uninstall  # Remove agents
```

**Requirements:**

- macOS with launchd
- Podman containers already running

#### setup-windows.ps1

**Purpose:** Configure Windows Task Scheduler for container auto-start on boot.

**What it does:**

1. Creates scheduled tasks for Podman containers
2. Configures startup triggers
3. Sets up appropriate user permissions

**Usage:**

```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
.\scripts\setup-windows.ps1 -Uninstall  # Remove tasks
.\scripts\setup-windows.ps1 -Help       # Show help
```

**Requirements:**

- Windows 10/11 with Podman Desktop or WSL2 + Podman
- Administrator privileges
- Containers already running

### Development Services

#### dev.sh

**Purpose:** Manage development servers (Redis, backend, frontend).

**Commands:**

| Command                  | Description                        |
| ------------------------ | ---------------------------------- |
| `start`                  | Start Redis, backend, and frontend |
| `stop`                   | Stop all services                  |
| `restart`                | Restart all services               |
| `status`                 | Show service status and PIDs       |
| `logs`                   | Show recent log output             |
| `redis [start\|stop]`    | Manage Redis only                  |
| `backend [start\|stop]`  | Manage backend only                |
| `frontend [start\|stop]` | Manage frontend only               |

**Service Ports:**

- Redis: localhost:6379
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

**Files Created:**

- PID files: `.pids/backend.pid`, `.pids/frontend.pid`
- Log files: `logs/backend.log`, `logs/frontend.log`

#### start-ai.sh

**Purpose:** Manage AI inference services (RT-DETRv2 and Nemotron LLM).

**Commands:**

| Command   | Description                  |
| --------- | ---------------------------- |
| `start`   | Start both AI services       |
| `stop`    | Stop both AI services        |
| `restart` | Restart both AI services     |
| `status`  | Show status, PIDs, GPU usage |
| `health`  | Test health endpoints        |

**Service Configuration:**

| Service   | Port | VRAM | Description              |
| --------- | ---- | ---- | ------------------------ |
| RT-DETRv2 | 8090 | ~4GB | Object detection server  |
| Nemotron  | 8091 | ~3GB | LLM risk analysis server |

**Log Files:**

- RT-DETRv2: `/tmp/rtdetr-detector.log`
- Nemotron: `/tmp/nemotron-llm.log`

#### start_redis.sh

**Purpose:** Redis server startup with auto-recovery support.

**Features:**

- Checks if Redis is already running
- Attempts systemd start if available
- Falls back to direct `redis-server` start
- Configurable via `REDIS_PORT` and `REDIS_HOST` environment variables

### Testing Scripts

#### validate.sh

**Purpose:** Full project validation (linting, type checking, tests).

**What it runs:**

1. **Backend:** Ruff linting, Ruff format check, MyPy type checking, pytest with 95% coverage
2. **Frontend:** ESLint, TypeScript check, Prettier check, Vitest

**Usage:**

```bash
./scripts/validate.sh              # Full validation
./scripts/validate.sh --backend    # Backend only
./scripts/validate.sh --frontend   # Frontend only
./scripts/validate.sh --help       # Show help
```

#### test-runner.sh

**Purpose:** Run full test suite with 95% coverage enforcement.

**Features:**

- Generates HTML and JSON coverage reports
- Backend: `coverage/backend/index.html`
- Frontend: `frontend/coverage/index.html`

#### test-fast.sh

**Purpose:** Fast parallel test runner with timing report.

**What it does:**

1. Runs pytest with parallel workers (auto-detected or specified)
2. Reports timing for each test
3. Supports running unit, integration, or all tests

**Usage:**

```bash
./scripts/test-fast.sh                    # Run all unit tests
./scripts/test-fast.sh backend/tests/     # Run specific path
./scripts/test-fast.sh unit 8             # Run unit tests with 8 workers
./scripts/test-fast.sh integration        # Run integration tests
./scripts/test-fast.sh all                # Run all tests
```

#### test-docker.sh

**Purpose:** Test Docker Compose deployment.

**Usage:**

```bash
./scripts/test-docker.sh              # Full test with cleanup
./scripts/test-docker.sh --no-cleanup # Leave containers running
./scripts/test-docker.sh --skip-build # Use existing images
```

#### test-prod-connectivity.sh

**Purpose:** Test production service connectivity and health.

**Usage:**

```bash
./scripts/test-prod-connectivity.sh              # Test all services
./scripts/test-prod-connectivity.sh --backend    # Test backend only
./scripts/test-prod-connectivity.sh --ai         # Test AI services only
```

#### smoke-test.sh

**Purpose:** End-to-end smoke test for MVP pipeline validation.

**What it validates:**

1. Prerequisites (curl, jq, backend API, Redis)
2. Creates test camera in database
3. Generates and drops test image
4. Waits for detection to be created
5. Waits for event to be created (batch processing)
6. Verifies API endpoints return expected data
7. Cleans up test artifacts

**Usage:**

```bash
./scripts/smoke-test.sh                  # Basic smoke test
./scripts/smoke-test.sh --verbose        # Verbose output
./scripts/smoke-test.sh --skip-cleanup   # Keep test artifacts
./scripts/smoke-test.sh --api-url URL    # Custom API URL
./scripts/smoke-test.sh --timeout 180    # Custom timeout
```

#### find-slow-tests.sh

**Purpose:** Find tests that hang or take too long.

**What it does:**

- Runs each test file individually with timeout
- Unit tests: 15-second timeout
- Integration tests: 30-second timeout
- Reports TIMEOUT, FAILED, or OK for each file

#### audit-test-durations.py

**Purpose:** Analyze CI JUnit XML test results and flag slow tests.

**What it does:**

1. Parses JUnit XML files from CI test runs
2. Identifies tests exceeding their category threshold
3. Warns about tests approaching the threshold (>80%)
4. Exits non-zero if any test exceeds its limit

**Usage:**

```bash
python scripts/audit-test-durations.py <results-dir>
```

**Environment Variables:**

| Variable                   | Default | Description                       |
| -------------------------- | ------- | --------------------------------- |
| UNIT_TEST_THRESHOLD        | 1.0     | Max seconds for unit tests        |
| INTEGRATION_TEST_THRESHOLD | 5.0     | Max seconds for integration tests |
| SLOW_TEST_THRESHOLD        | 60.0    | Max seconds for @pytest.mark.slow |
| WARN_THRESHOLD_PERCENT     | 80      | Warn at this percentage of limit  |

### Database Seeding

#### seed-cameras.py

**Purpose:** Populate database with test cameras.

**Usage:**

```bash
./scripts/seed-cameras.py              # Seed 6 cameras (creates folders)
./scripts/seed-cameras.py --no-folders # Skip folder creation
./scripts/seed-cameras.py --count 3    # Seed specific number
./scripts/seed-cameras.py --clear      # Clear before seeding
./scripts/seed-cameras.py --list       # List current cameras
```

**Sample Cameras:**

1. Front Door (front-door) - active
2. Backyard (backyard) - active
3. Garage (garage) - inactive
4. Driveway (driveway) - active
5. Side Gate (side-gate) - active
6. Living Room (living-room) - inactive

#### seed-mock-events.py

**Purpose:** Populate database with mock security events for testing.

### Database Migration

#### db-migrate.sh

**Purpose:** Run database migrations using Alembic.

**Usage:**

```bash
./scripts/db-migrate.sh                    # Run pending migrations
./scripts/db-migrate.sh --generate "msg"   # Generate new migration
./scripts/db-migrate.sh --downgrade        # Rollback last migration
```

#### migrate-sqlite-to-postgres.py

**Purpose:** Migrate data from SQLite to PostgreSQL database.

**Usage:**

```bash
python scripts/migrate-sqlite-to-postgres.py --source data/security.db --target postgresql://...
```

#### migrate-file-types.py

**Purpose:** Utility for migrating file type configurations.

### Code Generation

#### generate-types.sh

**Purpose:** Generate TypeScript types from FastAPI OpenAPI schema.

**Usage:**

```bash
./scripts/generate-types.sh          # Generate types
./scripts/generate-types.sh --check  # Check if types are current
```

**Output:** `frontend/src/types/api.ts`

#### generate_certs.py

**Purpose:** Generate self-signed SSL certificates for HTTPS development.

**Usage:**

```bash
python scripts/generate_certs.py                    # Generate certs in ./certs/
python scripts/generate_certs.py --output /path/    # Custom output directory
python scripts/generate_certs.py --days 365         # Custom validity period
```

**Output:** Creates `server.crt` and `server.key` files.

### Pre-commit Hooks

#### check-test-mocks.py

**Purpose:** Detect integration tests missing required mocks.

**Checks for:**

- Tests using `TestClient(app)` must mock: SystemBroadcaster, GPUMonitor, CleanupService

#### check-test-timeouts.py

**Purpose:** Detect potentially slow sleeps in test files.

**Flags:** Sleep calls >= 1 second that are not properly handled.

**Safe patterns recognized:**

- Sleep inside `mock_*`, `slow_*`, `fake_*` functions
- Sleep wrapped in `asyncio.wait_for()`
- Comments: `# cancelled`, `# timeout`, `# mocked`, `# patched`

### Infrastructure

#### setup-gpu-runner.sh

**Purpose:** Setup self-hosted GitHub Actions runner with GPU support.

**Requirements:**

- NVIDIA RTX A5500 or compatible GPU
- CUDA drivers installed
- sudo access for service installation

## Usage Patterns

### Initial Setup

```bash
# Linux/macOS
./scripts/setup.sh

# Windows
.\scripts\setup.ps1

# Activate environment and start
source .venv/bin/activate
./scripts/dev.sh start
```

### Development Workflow

```bash
# Start services
./scripts/dev.sh start

# Optional: Start AI services
./scripts/start-ai.sh start

# Make changes...

# Validate before commit
./scripts/validate.sh

# Commit (pre-commit hooks run automatically)
git add -A && git commit -m "message"

# Stop services when done
./scripts/dev.sh stop
```

### Testing Workflow

```bash
# Quick validation
./scripts/validate.sh

# Full test suite with coverage
./scripts/test-runner.sh

# Docker deployment test
./scripts/test-docker.sh

# E2E smoke test
./scripts/smoke-test.sh
```

### Database Management

```bash
# Seed cameras
./scripts/seed-cameras.py

# Reset database
rm -f data/security.db
./scripts/dev.sh restart
./scripts/seed-cameras.py
```

## Related Documentation

- `/CLAUDE.md` - Git workflow and testing requirements
- `/README.md` - Project overview
- `/docs/AI_SETUP.md` - AI services detailed setup
- `/.pre-commit-config.yaml` - Pre-commit hook configuration
