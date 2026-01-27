# Scripts Directory - Agent Guide

## Purpose

This directory contains development, testing, deployment, and maintenance scripts for the Home Security Intelligence project.

## Directory Contents

```
scripts/
  AGENTS.md                          # This file
  README.md                          # Quick reference for all scripts
  AI_STARTUP_README.md               # Quick reference for AI services
  hooks/                             # Git hooks
    post-checkout                    # Post-checkout hook for worktree protection

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
  quick-rebuild.sh                   # Quick rebuild and restart containers
  setup-container-api.sh             # Setup container API access

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
  seed-events.py                # Mock events and cameras seeding script
  db-migrate.sh                      # Database migration script

  # Code Generation & Certs
  generate-types.sh                  # TypeScript API type generation
  generate-certs.sh                  # SSL certificate generation
  generate-openapi.py                # Generate OpenAPI specification from FastAPI
  generate_zod_schemas.py            # Generate Zod validation schemas for frontend
  generate-ws-types.py               # Generate WebSocket TypeScript types
  extract_pydantic_constraints.py    # Extract Pydantic model constraints

  # AI Pipeline Scripts
  benchmark_model_zoo.py             # Model Zoo performance benchmarks
  benchmark_yolo26_accuracy.py       # YOLO26 accuracy benchmarks
  download-model-zoo.py              # Download AI model zoo models
  download_yolo26.py                 # Download YOLO26 model weights
  export_yolo26.py                   # Export YOLO26 to ONNX/TensorRT
  test_ai_pipeline_e2e.py            # AI pipeline end-to-end test
  test_context_window.py             # 32K context window test
  test_model_outputs.py              # Quick AI model output test
  test_model_outputs_comprehensive.py # Full AI model output test
  trigger-filewatcher.sh             # Trigger file watcher with images

  # Pre-commit Hooks & Test Validation
  check-test-mocks.py                # Pre-commit: mock validation
  check-test-timeouts.py             # Pre-commit: timeout validation
  check-api-coverage.sh              # API endpoint coverage check
  check-api-compatibility.sh         # API backward compatibility check
  check-api-contracts.sh             # API contract validation
  check-branch-name.sh               # Git branch naming convention check
  check-validation-drift.py          # Detect validation rule drift between schemas
  pre-push-rebase.sh                 # Auto-rebase before push
  pre-push-tests.sh                  # Run tests before push

  # Test Automation & Enforcement (NEM-2102)
  check-test-coverage-gate.py        # PR gate: detect files without tests
  generate-test-stubs.py             # Auto-generate test skeleton files
  check-integration-tests.py         # Ensure integration tests for API/services
  generate-api-tests.py              # Generate tests from OpenAPI spec
  weekly-test-report.py              # Weekly coverage and quality report

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
  check-docs-drift.py                # Detect documentation drift from code
  docs-drift-rules.yml               # Rules configuration for docs drift detection

  # Development Tools
  create-worktree.sh                 # Create git worktree for isolated work
  git-bisect-helper.sh               # Helper for git bisect debugging
  generate-docs.sh                   # Generate documentation
  load-test.sh                       # Load testing shell wrapper
  load_test.py                       # Load testing Python implementation
  mutation-test.sh                   # Mutation testing runner
  verify-observability.sh            # Verify observability stack (Prometheus, Grafana, etc)

  # Utilities
  validate-api-types.sh              # Validate API type definitions

  # Accessibility Testing
  a11y-smoke-test.sh                 # Accessibility smoke tests
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
- AI: ai-yolo26, ai-llm, ai-florence, ai-clip, ai-enrichment
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

#### seed-events.py

**Purpose:** Populate database with mock security events and cameras for testing.

### Database Migration

#### db-migrate.sh

**Purpose:** Run database migrations using Alembic.

**Usage:**

```bash
./scripts/db-migrate.sh                    # Run pending migrations
./scripts/db-migrate.sh --generate "msg"   # Generate new migration
./scripts/db-migrate.sh --downgrade        # Rollback last migration
```

### Code Generation

#### generate-types.sh

**Purpose:** Generate TypeScript types from FastAPI OpenAPI schema.

**Usage:**

```bash
./scripts/generate-types.sh          # Generate types
./scripts/generate-types.sh --check  # Check if types are current
```

**Output:** `frontend/src/types/api-endpoints.ts`

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

1. YOLO26 (port 8090) - object detection
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

#### export_yolo26.py

**Purpose:** Export YOLO26 models to various formats (ONNX, TensorRT) and benchmark inference speeds.

**Usage:**

```bash
# Export ONNX only
uv run python scripts/export_yolo26.py --format onnx

# Export all formats (ONNX + TensorRT if CUDA available)
uv run python scripts/export_yolo26.py

# Export specific model
uv run python scripts/export_yolo26.py --model yolo26s.pt

# Benchmark only (skip export)
uv run python scripts/export_yolo26.py --benchmark-only

# Force re-export even if files exist
uv run python scripts/export_yolo26.py --force
```

**Export Formats:**

| Format   | Extension         | GPU Required | Notes                            |
| -------- | ----------------- | ------------ | -------------------------------- |
| ONNX     | .onnx             | No           | Cross-platform, simplify enabled |
| TensorRT | .engine           | Yes          | FP16 optimized for NVIDIA GPUs   |
| OpenVINO | \_openvino_model/ | No           | Intel hardware optimized         |

**Output Locations:**

- Exported models: `/export/ai_models/model-zoo/yolo26/exports/`
- Benchmark report: `docs/benchmarks/yolo26-benchmarks.md`
- Local report: `/export/ai_models/model-zoo/yolo26/exports/EXPORT_REPORT.md`

**Requirements:**

- ultralytics>=8.4.0
- onnx (for ONNX export)
- tensorrt (for TensorRT export, optional)
- CUDA-enabled PyTorch (for TensorRT export)

#### download_yolo26.py

**Purpose:** Download and validate YOLO26 model weights from Ultralytics.

**Usage:**

```bash
uv run python scripts/download_yolo26.py
```

**Models Downloaded:**

- yolo26n.pt (Nano - fastest, ~5 MB)
- yolo26s.pt (Small - balanced, ~20 MB)
- yolo26m.pt (Medium - higher accuracy, ~42 MB)

**Output Location:** `/export/ai_models/model-zoo/yolo26/`

### Maintenance Scripts

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

#### check-api-contracts.sh

**Purpose:** Validate API contract consistency between backend schemas and frontend types.

**Usage:**

```bash
./scripts/check-api-contracts.sh
```

**Checks:**

- OpenAPI schema matches backend implementation
- Frontend types match OpenAPI definitions
- Request/response schemas are synchronized

#### validate-api-types.sh

**Purpose:** Validate TypeScript API types are current and match backend schemas.

**Usage:**

```bash
./scripts/validate-api-types.sh              # Validate types are current
./scripts/validate-api-types.sh --generate   # Regenerate if outdated
```

**What it does:**

- Compares generated types with committed types
- Fails if types are out of sync
- Can auto-regenerate with `--generate` flag

### Accessibility Scripts

#### a11y-smoke-test.sh

**Purpose:** Run accessibility smoke tests on the frontend.

**Usage:**

```bash
./scripts/a11y-smoke-test.sh                  # Run all a11y tests
./scripts/a11y-smoke-test.sh --component Nav  # Test specific component
./scripts/a11y-smoke-test.sh --verbose        # Verbose output
```

**Tests:**

- WCAG 2.1 compliance
- Color contrast ratios
- Keyboard navigation
- Screen reader compatibility
- Focus management

### Test Automation & Enforcement (NEM-2102)

#### check-test-coverage-gate.py

**Purpose:** PR gate for enforcing test coverage requirements on new/modified code.

**Usage:**

```bash
# Check current branch against base branch
./scripts/check-test-coverage-gate.py --base-branch origin/main

# Strict mode - fail on any missing tests
./scripts/check-test-coverage-gate.py --strict

# Check coverage diff
./scripts/check-test-coverage-gate.py --base-branch origin/main --strict
```

**What it does:**

- Detects new backend files without corresponding test files
- Verifies API routes have both unit and integration tests (95% coverage)
- Ensures services have unit and integration tests (90% coverage)
- Checks model files have unit tests (85% coverage)
- Detects coverage regressions between branches

**Requirements by Component:**

| Type               | Required Tests     | Min Coverage | Enforcement        |
| ------------------ | ------------------ | ------------ | ------------------ |
| API Route          | Unit + Integration | 95%          | Strict (blocks PR) |
| Service            | Unit + Integration | 90%          | Strict (blocks PR) |
| ORM Model          | Unit               | 85%          | Warning            |
| Frontend Component | Unit               | 80%          | Warning            |

**Integration:** Used in `.github/workflows/test-coverage-gate.yml` CI job

#### generate-test-stubs.py

**Purpose:** Auto-generate test skeleton files for new source files.

**Usage:**

```bash
# Generate test stub for backend file
./scripts/generate-test-stubs.py backend/api/routes/cameras.py

# Generate test stub for frontend component
./scripts/generate-test-stubs.py frontend/src/components/RiskGauge.tsx

# Frontend files auto-detected by extension
./scripts/generate-test-stubs.py frontend/src/hooks/useWebSocket.ts
```

**Features:**

- Generates appropriate test structure based on file location
- Includes proper imports and fixtures
- Provides TODO comments for implementation
- Follows project test conventions
- Supports both backend (pytest) and frontend (Vitest) patterns

**Generated Test Locations:**

- Backend API routes → `backend/tests/integration/test_<name>.py`
- Backend services → `backend/tests/unit/test_<name>.py`
- Backend models → `backend/tests/unit/test_<name>.py`
- Frontend components → `frontend/src/components/<Name>.test.tsx`
- Frontend hooks → `frontend/src/hooks/<name>.test.ts`

**Next Steps:**

1. Review generated test stub
2. Replace TODO comments with actual test cases
3. Follow patterns from `docs/development/testing.md`
4. Run `./scripts/validate.sh` to verify tests work

#### check-integration-tests.py

**Purpose:** Pre-commit reminder to add integration tests for API/service changes.

**Usage:**

```bash
# Automatically invoked by pre-commit hook
./scripts/check-integration-tests.py file1.py file2.py

# Manual check on changed files
git diff --name-only HEAD~1 | xargs ./scripts/check-integration-tests.py
```

**What it checks:**

- API routes have integration tests (required)
- Services have integration tests (required)
- Core utilities have integration tests (recommended)

**Why integration tests matter:**

- Verify database interactions work correctly
- Test service-to-service communication
- Validate error handling across components
- Ensure external API calls are correct

**Hook stage:** Runs on both commit and push

**Skip (emergency only):**

```bash
SKIP=check-integration-tests git commit
```

#### generate-api-tests.py

**Purpose:** Generate test cases from FastAPI OpenAPI specification.

**Usage:**

```bash
# Generate tests for all endpoints
./scripts/generate-api-tests.py

# Save extracted OpenAPI spec
./scripts/generate-api-tests.py --save-spec

# Custom output directory
./scripts/generate-api-tests.py --output-dir backend/tests/integration
```

**Features:**

- Extracts endpoint definitions from FastAPI app
- Generates test method stubs for each endpoint
- Includes happy path and error case tests
- Creates proper test class structure
- Follows project naming conventions

**Generated Tests Include:**

- Happy path test (successful request)
- Error handling test (404, 400, 500)
- Input validation test
- Authorization test (if applicable)

**Workflow:**

1. Run script to extract OpenAPI spec and generate tests
2. Review generated test files in `backend/tests/integration/`
3. Implement test logic (replace TODO comments)
4. Run `uv run pytest backend/tests/integration/test_*_endpoints.py -v`

#### weekly-test-report.py

**Purpose:** Generate comprehensive weekly test coverage and quality report.

**Usage:**

```bash
# Generate full report
./scripts/weekly-test-report.py

# Save report to JSON
./scripts/weekly-test-report.py --output weekly-report.json

# Skip frontend tests
./scripts/weekly-test-report.py --no-frontend
```

**What it collects:**

- Overall test coverage (backend and frontend)
- Test execution time by suite
- Flaky test detection and patterns
- Coverage trend analysis
- Test gap analysis (untested code paths)
- Performance benchmarks

**Report includes:**

- Summary statistics
- Coverage metrics by component
- Flaky test list with pass rates
- Coverage gaps (files under 80%)
- Execution time trends

**Output Format:**

- Console output with formatted summary
- JSON report (if `--output` specified) for trend analysis
- Test artifacts uploaded to GitHub Actions

**Integration:** Runs weekly via `.github/workflows/weekly-test-report.yml` (Mondays 9 AM UTC)

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
# Seed mock events and cameras
./scripts/seed-events.py

# Reset database
rm -f data/security.db
./scripts/dev.sh restart
./scripts/seed-events.py
```

## Related Documentation

- `/CLAUDE.md` - Git workflow and testing requirements
- `/README.md` - Project overview
- `/docs/operator/ai-installation.md` - AI services detailed setup
- `/.pre-commit-config.yaml` - Pre-commit hook configuration
