# Scripts Directory - Agent Guide

## Purpose

This directory contains development, testing, deployment, and maintenance scripts for the Home Security Intelligence project.

## Directory Contents

```
scripts/
  AGENTS.md                          # This file
  README.md                          # Quick reference for all scripts
  hooks/                             # Git hooks
    post-checkout                    # Post-checkout hook for worktree protection

  # Setup Scripts
  # (cross-platform env setup moved to root `setup.py`; setup.ps1 is Windows-only extras)
  setup.ps1                          # Windows PowerShell dev environment setup
  setup-hooks.sh                     # Pre-commit and pre-push hook setup
  setup-systemd.sh                   # Systemd service setup (Linux)
  setup-launchd.sh                   # launchd service setup (macOS)
  setup-windows.ps1                  # Windows Task Scheduler setup
  setup-gpu-runner.sh                # GitHub Actions GPU runner setup

  # Service Management
  dev.sh                             # Development server management
  restart-all.sh                     # Full stack restart (all containers)
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
  feature-check.sh                   # Golden paths against an isolated test deployment (O2.2)
  feature_check.py                   # feature-check.sh's logic: preflight, in-run check, postflight
  find-slow-tests.sh                 # Test performance debugging
  audit-test-durations.py            # CI test duration auditing
  audit-summary.sh                   # Local weekly audit runner

  # Database & Seeding
  seed-events.py                # Mock events and cameras seeding script

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
  trigger-filewatcher.sh             # Trigger file watcher with images

  # Pre-commit Hooks & Test Validation
  check-test-mocks.py                # Pre-commit: mock validation
  check-test-timeouts.py             # Pre-commit: timeout validation
  check-api-coverage.sh              # API endpoint coverage check
  check-api-compatibility.sh         # API backward compatibility check
  check-api-contracts.sh             # API contract validation
  check-branch-name.sh               # Git branch naming convention check
  check-version-consistency.sh       # All runtime versions must agree with .nvmrc/.python-version
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
  check-npm-audit-exemptions.py      # CI gate: frontend npm-audit exemption registry

  # CI/CD and Analysis Scripts
  analyze-ci-dependencies.py         # Analyze CI workflow dependencies
  analyze-flaky-tests.py             # Analyze and report flaky test patterns
  audit-linear-github-sync.py        # Audit Linear-GitHub synchronization
  ci-metrics-collector.py            # Collect and report CI metrics
  ci-smoke-test.sh                   # Quick CI smoke test
  close-rollback-issues.sh           # Close the open "Automated Rollback" incidents (O1.9)
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

#### setup.ps1

**Purpose:** Development environment setup for Windows (PowerShell). Cross-platform setup (including Linux/macOS) is the root-level `python setup.py` — the former scripts/setup.sh was removed in the setup consolidation (commit 84188795); `setup.py` checks prerequisites, creates `.venv` via uv, syncs deps, generates `.env` from `.env.example`, installs frontend deps and pre-commit hooks.

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

- PID files: .pids/backend.pid, .pids/frontend.pid (created at runtime by dev.sh; dir gitignored)
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
- AI: ai-gateway, ai-llm (matches `AI_SERVICES` in `scripts/restart-all.sh`)
- Monitoring: prometheus, grafana, redis-exporter, json-exporter

### Testing Scripts

<!-- RESOLVED (owner ruling A7.1, 2026-09-19): the "95% coverage" claim
below corrected to the executed number — validate.sh combines unit +
integration data and gates at --fail-under=80. Per the same ruling,
pyproject.toml fail_under=85 is the PR diff gate's RELATIVE baseline, not
an absolute floor, and test-runner.sh is an optional local runner no CI
job invokes. Docs text only, no behavior. -->

#### validate.sh

**Purpose:** Full project validation (linting, type checking, tests).

**What it runs:**

1. **Backend:** Ruff linting, Ruff format check, MyPy type checking, pytest; combined unit+integration coverage must reach 80%
2. **Frontend:** ESLint, TypeScript check, Prettier check, Vitest

**Usage:**

```bash
./scripts/validate.sh              # Full validation
./scripts/validate.sh --backend    # Backend only
./scripts/validate.sh --frontend   # Frontend only
./scripts/validate.sh --fast       # Change-scoped advisory tier (<=10 min, no coverage)
./scripts/validate.sh --help       # Show help
```

#### test-runner.sh

**Purpose:** Optional local full-suite runner. No CI job invokes it (A7.1 census); its `COVERAGE_THRESHOLD=93` is a stricter local choice, not a CI number — the CI-mirrored floor is validate.sh's 80% combined.

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

#### check-version-consistency.sh

**Purpose:** Fail the build when any runtime-version declaration drifts from the source-of-truth files.

**Source of truth:** `.nvmrc` (Node major), `.python-version` (Python X.Y), `pyproject.toml` `requires-python` (must equal `.python-version`).

**What it does:**

1. Reads `.nvmrc` and `.python-version` (missing truth file = hard fail)
2. Checks ci.yml `python-version` matrix labels + `PYTHON_VERSION` env against `.python-version` (the 3.11-label-vs-3.14-reality bug class)
3. Checks every workflow's `setup-python`/`NODE_VERSION`/`node-version` literals against truth — deliberate off-runtime tooling pins must be in the script's `PYTHON_ALLOWLIST`
4. Checks both Dockerfiles' `FROM python:`/`FROM node:` bases, `frontend/package.json` engines, and any hardcoded `REQUIRED_NODE_MAJOR` in validate.sh

**Usage:**

```bash
./scripts/check-version-consistency.sh              # check repo root (default)
./scripts/check-version-consistency.sh /path/to/repo  # check a tree copy (tests use this)
```

**Exit codes:**

| Code | Meaning                                                            |
| ---- | ------------------------------------------------------------------ |
| 0    | All declarations agree with the truth files                        |
| 1    | Drift found (one FAIL line per finding) or a truth file is missing |

Wired as a pre-commit hook (`always_run`) and the `Version Consistency` CI job, which the CI Gate requires. Tests: `backend/tests/unit/scripts/test_check_version_consistency.py`.

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

#### check-npm-audit-exemptions.py

**Purpose:** The frontend `npm audit` CI gate — `npm audit --json` cross-checked against the tracked registry `frontend/.npm-audit-exemptions.json` (mirrors `.trivyignore` doctrine: every entry carries a REVIEW BY date).

**Why it exists:** A bare `npm audit --audit-level=high` fails open the day an advisory lands whose only fix path is a semver-major migration (the braces DoS chain — every published version affected; npm's sole resolution is tailwindcss 3 → 4). This checker fails CLOSED: without the registry file, any finding at all is red, and a green run proves every finding is covered by an active, unexpired exemption.

**What it does:**

1. Runs `npm audit --json` in the frontend tree and extracts every advisory (GHSA id from `via[].url`)
2. Fails if the registry file is missing (fails closed), or an entry has a missing/malformed/passed REVIEW BY date
3. Fails if an audit finding is UNEXEMPTED, if an exemption matches nothing in the current audit (stale), or if its registered package differs from the audit's attribution
4. Fails if npm starts reporting an IN-RANGE (non-major) fix path for an exempted advisory — the exemption premise ("the only fix is a major migration") is broken, take the fix and drop the entry
5. Warns (exit 2) about exemptions expiring within `--warn-days`

**Usage:**

```bash
uv run python scripts/check-npm-audit-exemptions.py                        # defaults: --frontend frontend
uv run python scripts/check-npm-audit-exemptions.py --warn-days 30         # wider expiry warning window
uv run python scripts/check-npm-audit-exemptions.py --registry path.json   # custom registry (tests)
```

**Exit codes:**

| Code | Meaning                                                        |
| ---- | -------------------------------------------------------------- |
| 0    | Audit findings all covered by active exemptions, none expiring |
| 1    | Violations (unexempted / expired / stale / premise broken)     |
| 2    | Warning only — an exemption expires within `--warn-days`       |

**CI Integration:**

Runs right after `npm ci` (fresh lockfile-faithful tree) in both the `npm Audit (Frontend)` job of `.github/workflows/ci.yml` and the `NPM Dependency Audit` job of `.github/workflows/dependency-audit.yml` — invoked with preinstalled `python3` (the checker is stdlib-only; neither job sets up uv). Tests: `scripts/test_check_npm_audit_exemptions.py` (fake-`npm` shim on PATH; no network), also wired into the scripts anti-rot pytest list.

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

**Purpose:** Run the CI audit checks locally to preview findings (semgrep as in sast.yml, pip-audit as in dependency-audit.yml, vulture as in ci.yml's dead-code job).

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

**Purpose:** Analyze test results to identify flaky tests (intermittent failures). The WP1.5 consumer of the per-shard `flaky-test-tracking-*.jsonl` artifacts — invoked on main by ci.yml's `flake-report` job against a harvested corpus (see `fetch-ci-artifacts.py`).

**Usage:**

```bash
python scripts/analyze-flaky-tests.py <results-dir> [--owner-summary]
```

**Outputs:**

- List of tests with inconsistent pass/fail patterns
- Failure rate statistics
- Recommendations toward the governed quarantine: a `.github/flake-allowlist.yml` entry (tracking ref + expiry) — the legacy flaky_tests.txt manifest was retired with WP0.8
- `--owner-summary` (WP1.5): a RANKED table with an explicit Owner column to the GHA job summary — registered flakes show their tracking ref, unregistered ones read "no owner", and the corpus size is printed even at zero flakes ("no flakes" vs "read nothing" stay distinguishable)

#### fetch-ci-artifacts.py

**Purpose:** Download a previous CI run's artifacts into a local directory — the ONE tested implementation of "the newest completed main runs of this workflow, never the current run" (the rule was transcribed in curl/jq twice in one day and bitten by both traps: the generic runs endpoint mixes sibling workflows, and self-selection launders every violation). Used by TPA's baseline fetch (WP1.3) and the flake-report consumer (WP1.5).

**Usage:**

```bash
echo "$GH_TOKEN" | python scripts/fetch-ci-artifacts.py --repo OWNER/REPO \
  --current-run-id N --out DIR [--harvest-runs K]
```

**Notes:** token via stdin (never argv); cross-host redirects shed the Authorization header (the artifact URL is a pre-signed blob — carrying the token there 401s, measured); any fetch failure exits non-zero — empty output can never be read as "no history".

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
./scripts/ci-smoke-test.sh --backend-url http://localhost:8000 --frontend-url http://localhost:3000
./scripts/ci-smoke-test.sh --check-contract payload.json   # offline contract check, no server
```

**Tests:**

- Backend `/api/system/health/ready` answers 200 (`ready=false` warns but passes)
- Backend `/api/system/health` reports `healthy` or `degraded`
- Frontend serves HTML
- `/api/system/stats` and `/api/cameras` respond (warnings, non-blocking)
- WebSocket connectivity (skipped when `websocat` is absent)

`--check-contract FILE` runs only the O1.9 health check against one recorded
`/api/system/health/full` body, so the contract's behaviour is unit-testable
outside a deploy (`backend/tests/unit/scripts/data/` holds the bodies captured
from the incident's own job log). The expected set lives in
`scripts/ci-smoke-contract.json`, not in shell: the CI stack starts no AI
service, so a 503 naming only `yolo26` is the PASSING answer there, and the file
says why. Delete it when O2.1's fake AI stack runs here instead.

#### feature-check.sh

**Purpose:** O2.2's harness. It runs the golden paths against a **test
deployment**: the CI stack with the fake AI (`docker-compose.fake-ai.yml`)
under a compose project of its own, which touches nothing else on the machine.

**Usage:**

```bash
./scripts/feature-check.sh --fake --image-tag <sha7>
./scripts/feature-check.sh --real --image-tag <sha7>   # operator sandbox: agent-gpu
./scripts/feature-check.sh drop <image> <camera>   # inside a golden spec
```

The logic is `feature_check.py`, standard library only:

- the preflight refuses a run that could write outside its run directory,
  reach an engine socket or the host, or overlap anything on the machine;
- the in-run check and the postflight prove the isolation held;
- the harness smoke check drops one scenario image and expects one event with
  the scenario's verdict;
- `--real` (owner ruling 66) serves the real VLM through `agent-gpu` in place
  of the fake one (`AgentGpu`): the weights' pin first, the runner's port as
  the only host address the run may reach, and the VLM removed after the run.

The tests are in `backend/tests/unit/scripts/test_feature_check.py`. The
`Feature Check` workflow runs `--fake` on every PR that changes more than
Markdown, and on `main`. Usage and the golden-path
contract are in `docs/developer/testing.md`, "Feature Check".

#### close-rollback-issues.sh

**Purpose:** O1.9 box 5 as a tool: comment-and-close every open
"Automated Rollback" incident (owner ruling 2026-10-08 — a red `Deploy` run is
the signal; the daily batch reports it), then re-run the query to VERIFY the
Done-when instead of trusting the loop.

**Usage:**

```bash
./scripts/close-rollback-issues.sh --plan          # list only; touches nothing
./scripts/close-rollback-issues.sh --link '#6875'  # comment + close each (post-merge)
```

Run it ONCE, after #6875 merges and Deploy reads green on the merge commit —
closing earlier closes issues whose mechanism is still filing them. The unit
guard stubs `gh` offline; the recorded open-issue numbers live in
`backend/tests/unit/scripts/data/rollback-issues-open.json`.

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
git bisect run ./scripts/git-bisect-helper.sh "pytest backend/tests/unit/models/test_camera.py"
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
- Verifies API routes have both unit and integration tests (strict: blocks PR even without `--strict`)
- Ensures services have unit and integration tests; models and frontend files need unit tests
- Detects coverage regressions between branches (diff against `coverage-baseline.json`)

**Requirements by Component (mirrors `REQUIREMENTS` in the script — corrected 2026-09-19 per owner ruling A7.1; the previous rows advertised 95/90 which the script never contained):**

| Type                      | Required Tests     | Advisory Coverage | Enforcement                            |
| ------------------------- | ------------------ | ----------------- | -------------------------------------- |
| API Route                 | Unit + Integration | 85%               | Strict — blocks PR                     |
| Service                   | Unit + Integration | 85%               | Strict under `--strict` (CI passes it) |
| ORM Model                 | Unit               | 85%               | Strict under `--strict` (CI passes it) |
| Frontend Component / Hook | Unit               | 80%               | Strict under `--strict` (CI passes it) |

The coverage column is the number the script PRINTS in its missing-test
report; the gate's blocking checks are test presence and the branch-diff
coverage drop — no per-file coverage threshold is computed. The executed
absolute backend floor remains validate.sh's 80% combined.

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
3. Follow patterns from `docs/developer/testing.md`
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

#### agents_md_validator.py - the AGENTS.md ratchet (W1.1, zero tolerance since W1.3)

**Purpose:** the anti-rot gate over every `AGENTS.md`: dead file references, dead
markdown links, and retired-product-name mentions. Ratchet, not report: dead
references carry ZERO tolerance - W1.1 shipped a `dead_reference_allowlist` as a
starting set, W1.3 drained it to zero and REMOVED the mechanism, so any dead
reference fails directly. The only committed baseline left is the per-name
`retired_name_baseline` in `.agents-md-validator.yml`, and it admits no new
mentions. The loader REJECTS the presence of a `dead_reference_allowlist` key
(exit 2): re-adding an excuse list is treated as a gate-disable attempt, not a
config edit. `missing_agents_md` stays reporting-only until W3.1 wires the
boundary rule. W2.1 added the other two required keys: `boundary_list` (the
directories that keep an `AGENTS.md` when W3.1 prunes the rest, one `reason`
per entry - 42 today) and `line_caps` (per-tier ceilings - `root`,
`lane_root`, `package`). Both are loader-mandatory on the baseline doctrine:
deleting either key exits 2 rather than meaning "none". Line caps are
**reporting-only until W3.2** - an over-cap boundary file lands in
`ratchet.line_caps.over` and the console summary and does not fail the run,
because most boundary files are over cap today and that set is W3.2's rewrite
work list. The standard itself has its single home at
`docs/developer/agents-md-standard.md`.

**Exit codes:** `0` clean under the baselines; `1` a content violation (any dead
reference, any dead link, a retired-name count above its ceiling, an unbalanced
code fence, or an inline suppression comment without a tracking ref); `2` the
gate could not run (config absent, unparseable, missing any baseline key, or
carrying the removed allowlist key - the report is then NOT written, so a broken
gate can never feed `scripts/agents_md_linear_sync.py` a DEFAULTS table).

**Usage:**

```bash
uv run python scripts/agents_md_validator.py --output report.json   # the gate
uv run python scripts/agents_md_validator.py --root tmp/fixture     # a fixture tree
```

**Resolution is anchored:** an existing path proves a reference only when it
resolves inside the scan root with no excluded component - that is what makes the
dead-reference count identical on CI and dev machines. (History: the codeql
custom-queries citation to a gitignored virtualenv dir was dead on EVERY tree -
absent in CI, excluded-but-present at home - so a local "fix" could never green
CI; W1.1 admitted it as the thirteenth pair, W1.3 drained it by re-pointing the
citation at the real mechanism, the codeql config's paths-ignore list. That
sentence still dodges backticks around the path because this file is scanned by
the gate it describes.) **No minting:** counts hand-fall in the PR that removes
the mentions - there is deliberately no `--update`; a flag that rewrites the
baseline is an opt-out with no diff.

**CI:** `.github/workflows/agents-md.yml` runs the validator and uploads the
report; the teeth are in `collection-sanity`'s anti-rot pytest list, which CI Gate
requires - `scripts/test_agents_md_validator.py` asserts the real tree is green
there, and since W1.3 that it reports ZERO dead references. Baselines and the
zero census re-measured 2026-10-08 at the W1.3 PR head; the pattern to follow
for any future ratchet is `scripts/ratchet-check.py`.

#### audit/ - committed measurement censuses (O1.7)

Five scanners print the **[C]** baselines `docs/uplevel/00-audit.md` carries,
one per count a later package measures against; tests and CI conventions live
in `scripts/audit/AGENTS.md`, which is written to avoid the retired component
names the first census counts. This file is not: the model-download section
below already names one live pipeline feature with a retired name, so
`retired_names.py` counts this file in its agents bucket - W1.1's cleanup
includes it.

## Usage Patterns

### Initial Setup

```bash
# Linux/macOS (cross-platform, from repo root)
python setup.py

# Windows (PowerShell)
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

- `/AGENTS.md` - Git workflow and testing requirements
- `/README.md` - Project overview
- `/docs/operator/ai-installation.md` - AI services detailed setup
- `/.pre-commit-config.yaml` - Pre-commit hook configuration
