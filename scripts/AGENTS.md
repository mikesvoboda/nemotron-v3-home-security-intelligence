# Scripts Directory - Agent Guide

## Purpose

This directory contains development, testing, deployment, and maintenance scripts for the Home Security Intelligence project.

## Directory Contents

```
scripts/
  AGENTS.md                          # This file
  README.md                          # Quick reference for all scripts
  AI_STARTUP_README.md               # Quick reference for AI services

  # Setup Scripts
  setup.sh                           # Main setup script (Linux/macOS)
  setup.ps1                          # Main setup script (Windows)
  setup-hooks.sh                     # Pre-commit and pre-push hook setup
  setup-systemd.sh                   # Systemd service setup (Linux)
  setup-launchd.sh                   # launchd service setup (macOS)
  setup-windows.ps1                  # Windows Task Scheduler setup
  setup-gpu-runner.sh                # GitHub Actions GPU runner setup

  # Service Management
  dev.sh                             # Development server management
  restart-all.sh                     # Full stack restart (all containers)
  redeploy.sh                        # Stop, destroy volumes, redeploy fresh

  # Validation & Testing
  validate.sh                        # Full validation (lint, type, test)
  test-runner.sh                     # Test suite runner with coverage
  test-fast.sh                       # Fast parallel test runner
  test-docker.sh                     # Docker Compose deployment testing
  test-prod-connectivity.sh          # Production connectivity tests
  test-in-container.sh               # Container-first integration testing
  smoke-test.sh                      # End-to-end pipeline smoke test
  find-slow-tests.sh                 # Test performance debugging
  audit-test-durations.py            # CI test duration auditing
  audit-summary.sh                   # Local weekly audit runner

  # Database & Seeding
  seed-cameras.py                    # Database seeding script
  seed-mock-events.py                # Mock events seeding script
  db-migrate.sh                      # Database migration script
  migrate-sqlite-to-postgres.py      # SQLite to PostgreSQL migration
  migrate-file-types.py              # File type migration utility
  cleanup_orphaned_test_cameras.py   # Remove orphaned test data

  # Code Generation & Certs
  generate-types.sh                  # TypeScript API type generation
  generate_certs.py                  # SSL certificate generation

  # AI Pipeline Scripts
  benchmark_model_zoo.py             # Model Zoo performance benchmarks
  download-model-zoo.py              # Download AI model zoo models
  test_ai_pipeline_e2e.py            # AI pipeline end-to-end test
  test_context_window.py             # 32K context window test
  test_model_outputs.py              # Quick AI model output test
  test_model_outputs_comprehensive.py # Full AI model output test
  trigger-filewatcher.sh             # Trigger file watcher with images

  # Pre-commit Hooks
  check-test-mocks.py                # Pre-commit: mock validation
  check-test-timeouts.py             # Pre-commit: timeout validation
  check-api-coverage.sh              # API endpoint coverage check
  check-api-compatibility.sh         # API backward compatibility check
  check-branch-name.sh               # Git branch naming convention check
  pre-push-rebase.sh                 # Auto-rebase before push

  # Security Scripts
  check-trivyignore-expiry.sh        # Check for expired CVE review dates

  # CI/CD and Analysis Scripts
  analyze-ci-dependencies.py         # Analyze CI workflow dependencies
  analyze-flaky-tests.py             # Analyze and report flaky test patterns
  audit-linear-github-sync.py        # Audit Linear-GitHub synchronization
  ci-metrics-collector.py            # Collect and report CI metrics
  ci-smoke-test.sh                   # Quick CI smoke test
  coverage-analysis.py               # Advanced coverage analysis
  linear-label-issues.sh             # Bulk label Linear issues

  # Development Tools
  create-worktree.sh                 # Create git worktree for isolated work
  git-bisect-helper.sh               # Helper for git bisect debugging
  generate-docs.sh                   # Generate documentation
  load-test.sh                       # Load testing script
  mutation-test.sh                   # Mutation testing runner

  # Utilities
  github-models-examples.py          # GitHub Models API examples
  migrate_beads_to_linear.py         # Migrate beads to Linear (one-time)
```

## Key Scripts

### Development Setup

#### setup.sh

**Purpose:** Primary development environment setup script for Linux/macOS.

**What it does:**

1. Checks prerequisites (Python 3.14+, Node.js 20.19+/22.12+, Docker, NVIDIA drivers)
2. Checks for uv package manager (mandatory)
3. Creates Python virtual environment (`.venv`) using uv
4. Installs backend dependencies from `pyproject.toml` using `uv sync --extra dev`
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

#### restart-all.sh

**Purpose:** Full stack restart for all containerized services.

**Commands:**

| Command   | Description          |
| --------- | -------------------- |
| `start`   | Start all services   |
| `stop`    | Stop all services    |
| `restart` | Restart all services |
| `status`  | Show service status  |

**Services Managed:**

- Core: postgres, redis, backend, frontend
- AI: ai-detector, ai-llm, ai-florence, ai-clip, ai-enrichment
- Monitoring: prometheus, grafana, redis-exporter, json-exporter

#### redeploy.sh

**Purpose:** Stop all containers, destroy volumes, and redeploy fresh.

**Options:**

| Option            | Description                              |
| ----------------- | ---------------------------------------- |
| `--help`          | Show help message                        |
| `--dry-run`       | Show what would be done                  |
| `--keep-volumes`  | Preserve volumes (default destroys them) |
| `--ghcr`          | Use pre-built GHCR images                |
| `--tag TAG`       | Image tag for GHCR mode                  |
| `--skip-ci-check` | Skip CI build status check               |
| `--no-seed`       | Skip database seeding                    |

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

#### test-in-container.sh

**Purpose:** Container-first integration testing with postgres-test and redis-test.

**Usage:**

```bash
./scripts/test-in-container.sh                     # Run integration tests
./scripts/test-in-container.sh backend/tests/unit/ # Run specific tests
```

**What it does:**

1. Starts postgres-test and redis-test containers from `docker-compose.test.yml`
2. Waits for services to be healthy
3. Runs pytest with containerized database URLs
4. Uses port 5433 for postgres-test, 6380 for redis-test

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

### Security Scripts

#### check-trivyignore-expiry.sh

**Purpose:** Check for expired CVE review dates in `.trivyignore`.

**What it does:**

1. Parses `.trivyignore` for CVE entries with `REVIEW BY` dates
2. Reports expired CVEs that need immediate review
3. Warns about CVEs expiring within a configurable window
4. Reports CVEs missing review dates

**Usage:**

```bash
./scripts/check-trivyignore-expiry.sh                 # Check with defaults
./scripts/check-trivyignore-expiry.sh --warn-days 30  # Warn 30 days before expiry
./scripts/check-trivyignore-expiry.sh --file path     # Custom trivyignore path
./scripts/check-trivyignore-expiry.sh --help          # Show help
```

**Exit codes:**

| Code | Meaning                                |
| ---- | -------------------------------------- |
| 0    | All CVEs have valid, non-expired dates |
| 1    | Expired CVEs found or missing dates    |
| 2    | CVEs expiring soon (warning only)      |

**CI Integration:**

This script runs in the Trivy workflow (`.github/workflows/trivy.yml`):

- Weekly on Monday at 9am UTC
- On push to main when `.trivyignore` changes
- Creates Linear issues when CVEs expire

### Infrastructure

#### setup-gpu-runner.sh

**Purpose:** Setup self-hosted GitHub Actions runner with GPU support.

**Requirements:**

- NVIDIA RTX A5500 or compatible GPU
- CUDA drivers installed
- sudo access for service installation

### AI Pipeline Scripts

#### benchmark_model_zoo.py

**Purpose:** Benchmark Model Zoo performance - loading time, VRAM, inference latency.

**Usage:**

```bash
python scripts/benchmark_model_zoo.py                        # Benchmark all
python scripts/benchmark_model_zoo.py --models yolo11,clip   # Specific models
python scripts/benchmark_model_zoo.py --output results.md    # Custom output
```

#### download-model-zoo.py

**Purpose:** Download AI models for on-demand enrichment pipeline.

**Usage:**

```bash
./scripts/download-model-zoo.py                  # Download Phase 1 models
./scripts/download-model-zoo.py --phase 2        # Download Phase 2
./scripts/download-model-zoo.py --all            # Download all phases
./scripts/download-model-zoo.py --list           # List available models
```

#### test_ai_pipeline_e2e.py

**Purpose:** End-to-end test for all AI services in sequence.

**Services Tested:**

1. RT-DETRv2 (port 8090) - object detection
2. Florence-2 (port 8092) - dense captioning
3. CLIP (port 8093) - entity embeddings
4. Enrichment (port 8094) - vehicle/pet/clothing
5. Nemotron (port 8091) - risk analysis

#### trigger-filewatcher.sh

**Purpose:** Touch real image files to trigger file watcher processing.

**Usage:**

```bash
./scripts/trigger-filewatcher.sh                   # Touch 100 images
./scripts/trigger-filewatcher.sh --count 50        # Touch 50 images
./scripts/trigger-filewatcher.sh --camera kitchen  # Specific camera
./scripts/trigger-filewatcher.sh --dry-run         # Preview only
```

### Maintenance Scripts

#### cleanup_orphaned_test_cameras.py

**Purpose:** One-time cleanup of orphaned 'Test Camera' entries from database.

**Usage:**

```bash
python scripts/cleanup_orphaned_test_cameras.py --dry-run  # Preview
python scripts/cleanup_orphaned_test_cameras.py            # Delete
```

#### audit-summary.sh

**Purpose:** Run weekly-audit.yml checks locally to preview findings.

**What it runs:**

- Semgrep security scan
- pip-audit dependency check
- Vulture dead code detection
- Radon complexity analysis
- Knip frontend dead code

### CI/CD and Analysis Scripts

#### analyze-ci-dependencies.py

**Purpose:** Analyze GitHub Actions workflow dependencies and execution paths.

**Usage:**

```bash
python scripts/analyze-ci-dependencies.py
```

**What it analyzes:**

- Workflow job dependencies
- Critical path analysis
- Parallelization opportunities
- Bottleneck identification

#### analyze-flaky-tests.py

**Purpose:** Analyze test results to identify flaky tests (intermittent failures).

**Usage:**

```bash
python scripts/analyze-flaky-tests.py <results-dir>
```

**Outputs:**

- List of tests with inconsistent pass/fail patterns
- Failure rate statistics
- Recommendations for `flaky_tests.txt`

#### ci-metrics-collector.py

**Purpose:** Collect and report CI pipeline metrics for performance tracking.

**Usage:**

```bash
python scripts/ci-metrics-collector.py --workflow ci.yml --days 7
```

**Metrics Collected:**

- Workflow duration trends
- Job execution times
- Success/failure rates
- Resource usage

#### ci-smoke-test.sh

**Purpose:** Quick smoke test for CI environment validation.

**Usage:**

```bash
./scripts/ci-smoke-test.sh
```

**Tests:**

- Environment variables set
- Dependencies installed
- Services healthy
- Basic API connectivity

#### coverage-analysis.py

**Purpose:** Advanced code coverage analysis beyond basic percentage.

**Usage:**

```bash
python scripts/coverage-analysis.py --format html
```

**Analysis:**

- Uncovered critical paths
- Coverage by module
- Historical trends
- Coverage gaps

#### audit-linear-github-sync.py

**Purpose:** Audit Linear-GitHub bidirectional synchronization for consistency.

**Usage:**

```bash
python scripts/audit-linear-github-sync.py
```

**Checks:**

- Linear issues with corresponding GitHub issues
- Status synchronization
- Label mapping accuracy
- Missing bidirectional links

#### linear-label-issues.sh

**Purpose:** Bulk apply labels to Linear issues matching criteria.

**Usage:**

```bash
./scripts/linear-label-issues.sh --label backend --filter "NEM-1*"
```

### Development Tool Scripts

#### create-worktree.sh

**Purpose:** Create git worktree for isolated feature development.

**Usage:**

```bash
./scripts/create-worktree.sh feature-name
```

**What it does:**

- Creates worktree in `../<repo>-<feature-name>/`
- Checks out new branch
- Sets up working directory

#### git-bisect-helper.sh

**Purpose:** Helper script for git bisect to find regression commits.

**Usage:**

```bash
./scripts/git-bisect-helper.sh <test-command>
```

**Example:**

```bash
git bisect start HEAD v1.0.0
git bisect run ./scripts/git-bisect-helper.sh "pytest backend/tests/unit/test_camera.py"
```

#### generate-docs.sh

**Purpose:** Generate documentation from code comments and schemas.

**Usage:**

```bash
./scripts/generate-docs.sh
```

**Generates:**

- API documentation from OpenAPI schema
- Database schema diagrams
- Component documentation

#### load-test.sh

**Purpose:** Load testing script for API performance validation.

**Usage:**

```bash
./scripts/load-test.sh --concurrent 100 --duration 60s
```

**Metrics:**

- Requests per second
- Response time percentiles
- Error rates
- Resource utilization

#### mutation-test.sh

**Purpose:** Run mutation testing to validate test suite quality.

**Usage:**

```bash
./scripts/mutation-test.sh
```

**Runs:**

- `mutmut` for Python backend
- `stryker` for TypeScript frontend
- Generates mutation score reports

### Additional Pre-commit Scripts

#### check-api-compatibility.sh

**Purpose:** Verify API backward compatibility before merging.

**Usage:**

```bash
./scripts/check-api-compatibility.sh
```

**Checks:**

- Breaking changes in API schemas
- Removed endpoints
- Changed response structures

#### check-branch-name.sh

**Purpose:** Enforce git branch naming conventions.

**Usage:**

```bash
./scripts/check-branch-name.sh
```

**Valid Patterns:**

- `feature/description`
- `fix/description`
- `hotfix/description`
- `chore/description`

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
