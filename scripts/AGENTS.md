# Scripts Directory - Agent Guide

## Purpose

This directory contains development, testing, and deployment automation scripts for the Home Security Intelligence project.

## Quick Reference Documentation

### README.md

- **Purpose:** Quick reference guide for all scripts in this directory
- **Contents:**
  - Quick start instructions
  - Available scripts table
  - Common workflows
  - Troubleshooting tips
- **When to use:** Quick overview of script purposes and usage

### AI_STARTUP_README.md

- **Purpose:** Quick reference for AI services startup
- **Contents:**
  - Prerequisites checklist
  - Quick start commands for AI services
  - Service endpoints and ports
  - Common commands (start, stop, status, health)
  - Troubleshooting common AI service issues
- **When to use:** Quick reference for managing RT-DETRv2 and Nemotron services

## Key Scripts

### Development Setup

**setup.sh** (530 lines, executable) - PRIMARY SETUP SCRIPT

- **Purpose:** Comprehensive development environment setup script for Linux/macOS
- **What it does:**
  1. Checks prerequisites (Python 3.11+, Node.js 18+, Docker, NVIDIA drivers, git)
  2. Creates Python virtual environment (`.venv`) if needed
  3. Installs backend dependencies from `backend/requirements.txt`
  4. Installs dev tools (pre-commit, ruff, mypy)
  5. Creates `.env` file from `.env.example`
  6. Creates data directory and prepares database
  7. Installs frontend dependencies (`npm install`)
  8. Installs pre-commit hooks (git hooks)
  9. Verifies all tools are working
  10. Optionally runs verification tests
- **When to use:**
  - First time setting up project (recommended)
  - After cloning repository
  - When recreating environment from scratch
  - When setting up on a new machine
- **Usage:**

  ```bash
  # Full setup with all checks
  ./scripts/setup.sh

  # Show help and options
  ./scripts/setup.sh --help

  # Setup without GPU checks (for machines without NVIDIA GPUs)
  ./scripts/setup.sh --skip-gpu

  # Skip verification tests (faster setup)
  ./scripts/setup.sh --skip-tests

  # Clean existing setup and reinstall
  ./scripts/setup.sh --clean
  ```

- **Command-line options:**
  - `--help` - Show help message
  - `--skip-gpu` - Skip GPU/NVIDIA driver checks
  - `--skip-tests` - Skip verification tests
  - `--clean` - Remove existing .venv, node_modules, database before setup
- **Output:**
  - Colored progress messages (blue headers, green success, yellow warnings)
  - Prerequisite check results with versions
  - Tool version verification
  - GPU information if available
  - Available commands summary with next steps
- **Features:**
  - Idempotent (safe to run multiple times)
  - Detects and uses `uv` for faster Python package installation
  - Validates Python 3.11+ and Node.js 18+ versions
  - Optional GPU support detection
  - Creates .env from template if missing
  - Comprehensive verification of all tools
- **Dependencies:**
  - Python 3.11+ (required)
  - Node.js 18+ (required)
  - git (required)
  - Docker (optional)
  - NVIDIA drivers (optional, for GPU features)

**setup.ps1** (485 lines, PowerShell) - WINDOWS SETUP SCRIPT

- **Purpose:** Development environment setup script for Windows (PowerShell)
- **What it does:** Same as setup.sh but for Windows environments
- **When to use:**
  - First time setting up project on Windows
  - After cloning repository on Windows machine
- **Usage:**

  ```powershell
  # Full setup
  .\scripts\setup.ps1

  # Show help
  .\scripts\setup.ps1 -Help

  # Setup without GPU checks
  .\scripts\setup.ps1 -SkipGpu

  # Clean and reinstall
  .\scripts\setup.ps1 -Clean
  ```

- **Command-line options:**
  - `-Help` - Show help message
  - `-SkipGpu` - Skip GPU/NVIDIA driver checks
  - `-SkipTests` - Skip verification tests
  - `-Clean` - Remove existing setup before reinstalling
- **Features:**
  - Windows-native PowerShell implementation
  - Same functionality as Linux/macOS version
  - Colored output using PowerShell Write-Host
  - Uses Windows paths (backslashes)
  - Activates .venv using PowerShell activation script
- **Dependencies:**
  - PowerShell 5.1+ or PowerShell Core 7+
  - Python 3.11+ for Windows
  - Node.js 18+ for Windows
  - git for Windows
  - Optional: Docker Desktop for Windows
  - Optional: NVIDIA drivers for Windows

**setup-hooks.sh** (128 lines, executable) - LEGACY

- **Purpose:** Legacy development environment setup script (superseded by setup.sh)
- **Note:** Use `setup.sh` instead for new setups. This script is kept for backward compatibility.
- **What it does:**
  1. Creates Python virtual environment (`.venv`)
  2. Installs backend dependencies from `backend/requirements.txt`
  3. Installs dev tools (pre-commit, ruff, mypy)
  4. Installs frontend dependencies (`npm install`)
  5. Installs pre-commit hooks (git hooks)
  6. Verifies all tools are working
- **When to use:**
  - Only if you've been using it previously
  - Prefer `setup.sh` for new setups
- **Usage:**
  ```bash
  ./scripts/setup-hooks.sh
  ```
- **Output:**
  - Colored progress messages (blue headers, green success, yellow info)
  - Tool version verification
  - Available commands summary
- **Dependencies:**
  - Python 3.11+
  - Node.js (for npm)
  - Optional: uv (faster Python package manager)

### Development Services

**dev.sh** (263 lines, executable)

- **Purpose:** Manage development servers (Redis, backend, frontend) for local testing
- **What it does:**
  1. Starts/stops Redis container (Docker) or system Redis
  2. Starts/stops FastAPI backend server (uvicorn)
  3. Starts/stops React frontend dev server (Vite)
  4. Tracks process PIDs in `.pids/` directory
  5. Logs output to `logs/` directory
  6. Provides service status and health monitoring
- **When to use:**
  - Starting development environment
  - Testing full-stack integration
  - Running all services at once
  - Debugging service interactions
- **Usage:**

  ```bash
  # Start all services (Redis, backend, frontend)
  ./scripts/dev.sh start

  # Stop all services
  ./scripts/dev.sh stop

  # Restart all services
  ./scripts/dev.sh restart

  # Check service status
  ./scripts/dev.sh status

  # View recent logs
  ./scripts/dev.sh logs

  # Manage individual services
  ./scripts/dev.sh redis start
  ./scripts/dev.sh backend start
  ./scripts/dev.sh frontend start
  ```

- **Commands:**
  - `start` - Start Redis, backend, and frontend
  - `stop` - Stop all services
  - `restart` - Restart all services
  - `status` - Show service status and PIDs
  - `logs` - Show recent log output
  - `redis [start|stop]` - Manage Redis only
  - `backend [start|stop]` - Manage backend only
  - `frontend [start|stop]` - Manage frontend only
- **Service ports:**
  - Redis: localhost:6379
  - Backend: http://localhost:8000
  - Frontend: http://localhost:5173
- **PID files:** `.pids/backend.pid`, `.pids/frontend.pid`
- **Log files:** `logs/backend.log`, `logs/frontend.log`
- **Docker support:**
  - Automatically detects Docker availability
  - Uses `sudo docker` if user not in docker group
  - Creates/starts Redis container (`home-security-redis`)
  - Falls back to system Redis if Docker unavailable
- **Features:**
  - Graceful shutdown with cleanup
  - Orphaned process cleanup
  - Colored status output (green=running, red=stopped)
  - Idempotent (safe to run multiple times)
- **Dependencies:**
  - Python virtual environment (`.venv`)
  - Node.js and npm
  - Docker (optional, for Redis container)

**start-ai.sh** (437 lines, executable)

- **Purpose:** Manage AI inference services (RT-DETRv2 and Nemotron LLM) for GPU-accelerated detection and reasoning
- **What it does:**
  1. Checks prerequisites (NVIDIA GPU, CUDA, llama-server, model files)
  2. Starts RT-DETRv2 object detection server (port 8001)
  3. Starts Nemotron LLM server (port 8002)
  4. Waits for services to become healthy (60s timeout each)
  5. Monitors GPU usage and VRAM consumption
  6. Provides health checks and status reporting
- **When to use:**
  - Starting AI pipeline for development
  - Testing object detection and risk analysis
  - GPU performance testing
  - Production deployment of AI services
- **Usage:**

  ```bash
  # Start both AI services
  ./scripts/start-ai.sh start

  # Stop both AI services
  ./scripts/start-ai.sh stop

  # Restart both AI services
  ./scripts/start-ai.sh restart

  # Show service status and GPU usage
  ./scripts/start-ai.sh status

  # Test service health endpoints
  ./scripts/start-ai.sh health
  ```

- **Commands:**
  - `start` - Start both AI services (checks prerequisites first)
  - `stop` - Stop both AI services gracefully
  - `restart` - Restart both AI services
  - `status` - Show service status, PIDs, and GPU usage
  - `health` - Test health endpoints and show detailed info
- **Service configuration:**
  - RT-DETRv2 Detection Server: http://localhost:8001 (~4GB VRAM)
  - Nemotron LLM Server: http://localhost:8002 (~3GB VRAM)
  - Total VRAM usage: ~7GB
- **Model files:**
  - RT-DETRv2: `ai/rtdetr/rtdetrv2_r50vd.onnx`
  - Nemotron: `ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf`
- **PID files:**
  - RT-DETRv2: `/tmp/rtdetr-detector.pid`
  - Nemotron: `/tmp/nemotron-llm.pid`
- **Log files:**
  - RT-DETRv2: `/tmp/rtdetr-detector.log`
  - Nemotron: `/tmp/nemotron-llm.log`
- **Prerequisites:**
  - NVIDIA GPU with CUDA support (RTX A5500 or similar)
  - llama-server (from llama.cpp) in PATH
  - Python environment with RT-DETRv2 dependencies
  - Model files downloaded (run `ai/download_models.sh` first)
- **Features:**
  - Prerequisite validation before startup
  - Health endpoint monitoring with retry logic
  - GPU status reporting (VRAM, utilization)
  - Graceful shutdown (10s timeout, force kill if needed)
  - Colored status output
  - Idempotent service management
- **Startup time:**
  - First run: 2-3 minutes (model loading + GPU warmup)
  - Subsequent runs: 30-60 seconds
- **Dependencies:**
  - nvidia-smi (NVIDIA drivers)
  - llama-server (llama.cpp)
  - Python 3.10+ with RT-DETRv2 packages
  - curl (for health checks)

### Testing

**test-runner.sh** (188 lines, executable)

- **Purpose:** Unified test runner for both backend and frontend with coverage enforcement
- **What it does:**
  1. Activates Python virtual environment
  2. Runs backend tests with pytest
  3. Generates backend coverage report (HTML + JSON)
  4. Runs frontend tests with Vitest
  5. Generates frontend coverage report
  6. Displays summary with pass/fail status
  7. Exits with error code if any tests fail or coverage below threshold
- **Coverage threshold:** 95% (configurable via `COVERAGE_THRESHOLD` variable)
- **When to use:**
  - Before committing code
  - After implementing new features
  - Before creating pull requests
  - During CI/CD pipeline (future)
- **Usage:**
  ```bash
  ./scripts/test-runner.sh
  ```
- **Output:**
  - Test results for both backend and frontend
  - Coverage percentages
  - Paths to HTML coverage reports
  - Exit code 0 (success) or 1 (failure)
- **Generated reports:**
  - `coverage/backend/index.html` - Backend coverage
  - `frontend/coverage/index.html` - Frontend coverage
  - `coverage/backend/coverage.json` - Backend coverage data

**validate.sh** (47 lines, executable)

- **Purpose:** Quick validation script for linting, type checking, and tests
- **What it does:**
  1. Backend linting (ruff check)
  2. Backend formatting check (ruff format --check)
  3. Backend type checking (mypy)
  4. Frontend linting (eslint)
  5. Frontend type checking (tsc --noEmit)
  6. Frontend formatting check (prettier --check)
  7. Backend tests with 90% coverage threshold
  8. Frontend tests
- **When to use:**
  - Quick pre-commit validation
  - CI/CD pipeline
  - Before pushing to remote
  - After making changes across backend and frontend
- **Usage:**
  ```bash
  ./scripts/validate.sh
  ```
- **Output:**
  - Colored section headers (green)
  - Tool output for each check
  - Final success message
  - Exit code 0 (success) or 1 (failure)
- **Differences from test-runner.sh:**
  - No coverage HTML reports generated
  - 90% threshold vs 95%
  - Includes linting and type checking
  - Faster execution (no HTML generation)

**test-docker.sh** (279 lines, executable)

- **Purpose:** Docker Compose deployment testing - validates containerized deployment
- **What it does:**
  1. Checks Docker availability and daemon status
  2. Validates docker-compose.yml syntax
  3. Stops and removes existing containers
  4. Builds Docker images (optional)
  5. Starts all services with docker compose up -d
  6. Waits for services to become healthy (120s timeout)
  7. Tests service endpoints (Redis, backend, frontend)
  8. Tests inter-service communication
  9. Shows container resource usage
  10. Optionally cleans up on exit
- **When to use:**
  - Testing Docker Compose deployment
  - Validating containerization setup
  - Pre-deployment verification
  - CI/CD pipeline testing
  - Ensuring all services communicate correctly
- **Usage:**

  ```bash
  # Full test with cleanup on exit
  ./scripts/test-docker.sh

  # Leave containers running after test
  ./scripts/test-docker.sh --no-cleanup

  # Skip build step (use existing images)
  ./scripts/test-docker.sh --skip-build

  # Show help
  ./scripts/test-docker.sh --help
  ```

- **Command-line options:**
  - `--no-cleanup` - Leave containers running after test
  - `--skip-build` - Skip docker compose build step
  - `--help` - Show help message
- **Services tested:**
  - Redis: localhost:6379 (health check via redis-cli)
  - Backend: http://localhost:8000 (health endpoint + root endpoint)
  - Frontend: http://localhost:5173 (HTTP response check)
- **Test stages:**
  1. Prerequisites (Docker, docker-compose.yml)
  2. Syntax validation
  3. Cleanup existing containers
  4. Build images (optional)
  5. Start services
  6. Health monitoring (with state checking)
  7. Endpoint testing
  8. Inter-service communication
  9. Resource usage reporting
- **Timeout configuration:**
  - Service health timeout: 120 seconds
  - Health check interval: 5 seconds
  - Max wait for healthy: 24 checks
- **Output:**
  - Colored status messages (blue=info, green=success, yellow=warning, red=error)
  - Service health status (state + health for each service)
  - Container logs on failure
  - Resource usage statistics (CPU, memory, network)
  - Service URLs and endpoints
- **Exit behavior:**
  - Default: Stops and removes containers on exit
  - `--no-cleanup`: Leaves containers running for inspection
  - Non-zero exit code on any failure
- **Health checks:**
  - Redis: `docker compose exec redis redis-cli ping`
  - Backend: `curl http://localhost:8000/health`
  - Backend root: `curl http://localhost:8000/`
  - Backend->Redis: Checks Redis connection status in health endpoint
- **Dependencies:**
  - Docker (docker CLI)
  - Docker daemon (running)
  - docker-compose.yml in project root
  - jq (for JSON parsing of container status)
  - curl (for HTTP endpoint testing)

**smoke-test.sh** (~650 lines, executable)

- **Purpose:** End-to-end smoke test for validating the complete MVP pipeline
- **What it does:**
  1. Checks prerequisites (curl, jq, backend API, Redis, database)
  2. Creates a test camera in the database
  3. Generates a test image fixture (using PIL or fallback minimal JPEG)
  4. Drops the test image into the camera folder
  5. Waits for detection to be created (polls /api/detections)
  6. Waits for event to be created (batch processing)
  7. Verifies API endpoints return expected data
  8. Cleans up test artifacts (camera, images)
- **When to use:**
  - After deployment to verify pipeline is operational
  - After configuration changes
  - Before releasing new versions
  - During incident investigation
  - As part of production health checks
- **Usage:**

  ```bash
  # Basic smoke test
  ./scripts/smoke-test.sh

  # Verbose output for debugging
  ./scripts/smoke-test.sh --verbose

  # Keep test artifacts for inspection
  ./scripts/smoke-test.sh --skip-cleanup

  # Custom API URL and timeout
  ./scripts/smoke-test.sh --api-url http://192.168.1.100:8000 --timeout 180
  ```

- **Command-line options:**
  - `--help, -h` - Show help message with full usage documentation
  - `--verbose, -v` - Enable verbose output (API responses, debug info)
  - `--skip-cleanup` - Don't remove test artifacts after completion
  - `--timeout N` - Timeout in seconds for pipeline completion (default: 90)
  - `--api-url URL` - Backend API URL (default: http://localhost:8000)
- **Exit codes:**
  - `0` - All tests passed
  - `1` - Test failure (see output for details)
  - `2` - Prerequisite check failed
- **Pipeline validation:**
  - Creates test camera: `smoke-test-camera`
  - Creates test image in: `data/smoke_test_camera/`
  - Validates detection created within timeout
  - Validates event created after batch processing
  - Verifies all API endpoints return valid responses
- **Output:**
  - Colored status messages (PASS/FAIL/WARN)
  - Diagnostic information on failures
  - Troubleshooting suggestions
  - Summary with test duration
- **Error handling:**
  - Graceful handling of missing services
  - Automatic cleanup on exit (via trap)
  - Helpful troubleshooting messages for each failure mode
- **Dependencies:**
  - curl (HTTP requests)
  - jq (JSON parsing)
  - Backend API running
  - Redis running
  - (Optional) AI services for full pipeline validation

## Script Comparison

### Development & Testing Scripts

| Feature                 | setup.sh             | dev.sh               | start-ai.sh           | test-runner.sh        | validate.sh         | test-docker.sh       | smoke-test.sh       |
| ----------------------- | -------------------- | -------------------- | --------------------- | --------------------- | ------------------- | -------------------- | ------------------- |
| **Purpose**             | Environment setup    | Dev servers          | AI services           | Comprehensive testing | Quick validation    | Docker deployment    | E2E pipeline test   |
| **Run frequency**       | Once per environment | Daily dev use        | When testing AI       | Before commits        | Before commits/push | Before deployment    | After deployment    |
| **Prerequisite checks** | Yes (Python, Node)   | No                   | Yes (GPU, llama)      | No                    | No                  | Yes (Docker)         | Yes (API, Redis)    |
| **Starts services**     | No                   | Yes (3 services)     | Yes (2 AI services)   | No                    | No                  | Yes (Docker Compose) | No                  |
| **Backend tests**       | Optional             | No                   | No                    | Yes (pytest)          | Yes (pytest)        | No                   | No (E2E only)       |
| **Frontend tests**      | Optional             | No                   | No                    | Yes (Vitest)          | Yes (Vitest)        | No                   | No                  |
| **Coverage reports**    | No                   | No                   | No                    | Yes (HTML + JSON)     | No (terminal only)  | No                   | No                  |
| **Coverage threshold**  | N/A                  | N/A                  | N/A                   | 95%                   | 90%                 | N/A                  | N/A                 |
| **Linting**             | No                   | No                   | No                    | No                    | Yes (ruff + eslint) | No                   | No                  |
| **Type checking**       | No                   | No                   | No                    | No                    | Yes (mypy + tsc)    | No                   | No                  |
| **Health checks**       | No                   | Yes (service status) | Yes (GPU + endpoints) | No                    | No                  | Yes (containers)     | Yes (API endpoints) |
| **GPU monitoring**      | Check only           | No                   | Yes (nvidia-smi)      | No                    | No                  | No                   | No                  |
| **Pre-commit hooks**    | Installs             | No                   | No                    | No                    | No                  | No                   | No                  |
| **Colored output**      | Yes                  | Yes                  | Yes                   | Yes                   | Yes                 | Yes                  | Yes                 |
| **Creates .env**        | Yes                  | No                   | No                    | No                    | No                  | No                   | No                  |
| **Installs deps**       | Yes                  | No                   | No                    | Yes (if missing)      | No                  | No                   | No                  |
| **Command options**     | 4 flags              | 9 commands           | 5 commands            | None                  | None                | 3 flags              | 4 flags             |
| **Windows support**     | setup.ps1            | No                   | No                    | No                    | No                  | No                   | No                  |
| **Cleanup on exit**     | No                   | No                   | No                    | No                    | No                  | Yes (optional)       | Yes (optional)      |

## Usage Patterns

### Initial Project Setup (Linux/macOS)

```bash
# 1. Clone repository
git clone <repo>
cd nemotron-v3-home-security-intelligence

# 2. Run setup script (automatically handles everything)
./scripts/setup.sh

# 3. Environment is ready! Activate virtualenv and start coding
source .venv/bin/activate
```

### Initial Project Setup (Windows)

```powershell
# 1. Clone repository
git clone <repo>
cd nemotron-v3-home-security-intelligence

# 2. Run setup script (automatically handles everything)
.\scripts\setup.ps1

# 3. Environment is ready! Activate virtualenv and start coding
.\.venv\Scripts\Activate.ps1
```

### Setup Options

```bash
# Full setup with all checks (recommended)
./scripts/setup.sh

# Setup without GPU checks (for non-GPU machines)
./scripts/setup.sh --skip-gpu

# Skip verification tests (faster)
./scripts/setup.sh --skip-tests

# Clean and reinstall everything
./scripts/setup.sh --clean

# Get help
./scripts/setup.sh --help
```

### Development Workflow

```bash
# Start development services
./scripts/dev.sh start

# (Optional) Start AI services if testing AI features
./scripts/start-ai.sh start

# Make changes to code

# Quick check before commit
./scripts/validate.sh

# If validation passes, commit
git add -A
git commit -m "feat: description"
# Pre-commit hooks run automatically

# Full test suite before push
./scripts/test-runner.sh

# Push to remote
git push origin main

# Stop services when done
./scripts/dev.sh stop
./scripts/start-ai.sh stop  # if AI services were started
```

### Full-Stack Development Session

```bash
# 1. Start all development services
./scripts/dev.sh start
# This starts: Redis (6379), Backend (8000), Frontend (5173)

# 2. Check service status
./scripts/dev.sh status

# 3. View logs if needed
./scripts/dev.sh logs

# 4. Make changes to code...

# 5. Stop services when done
./scripts/dev.sh stop
```

### AI Pipeline Development

```bash
# 1. Download models (first time only)
./ai/download_models.sh

# 2. Start AI services
./scripts/start-ai.sh start
# This starts: RT-DETRv2 (8001), Nemotron LLM (8002)

# 3. Check GPU usage and service status
./scripts/start-ai.sh status

# 4. Test AI service health
./scripts/start-ai.sh health

# 5. View AI service logs
tail -f /tmp/rtdetr-detector.log
tail -f /tmp/nemotron-llm.log

# 6. Stop AI services when done
./scripts/start-ai.sh stop
```

### Docker Deployment Testing

```bash
# Test Docker Compose deployment
./scripts/test-docker.sh

# Leave containers running for inspection
./scripts/test-docker.sh --no-cleanup

# Skip build step (faster, use existing images)
./scripts/test-docker.sh --skip-build

# Stop containers manually
docker compose down -v
```

### Test-Driven Development (TDD)

```bash
# 1. Write failing test
# Edit backend/tests/unit/test_feature.py

# 2. Run tests (should fail)
pytest backend/tests/unit/test_feature.py -v

# 3. Implement feature
# Edit backend/services/feature.py

# 4. Run tests (should pass)
pytest backend/tests/unit/test_feature.py -v

# 5. Run full suite with coverage
./scripts/test-runner.sh

# 6. Commit
git commit -m "feat: implement feature with tests"
```

### CI/CD Integration (Future)

```bash
# In CI/CD pipeline, run validate.sh
./scripts/validate.sh
# Exit code 0 = success, 1 = failure
```

## Important Patterns

### Error Handling

- All scripts use `set -e` (exit on error)
- Scripts check for dependencies before running
- Clear error messages with colored output

### Environment Management

- Scripts activate `.venv` when needed
- Check for virtual environment existence
- Create virtual environment if missing
- Use `uv` package manager if available (faster)

### Coverage Enforcement

- **test-runner.sh:** 95% threshold (strict)
- **validate.sh:** 90% threshold (pre-commit)
- **pytest.ini:** 95% threshold (in pyproject.toml)
- Fail fast if coverage below threshold

### Output Formatting

```bash
# Color codes used
RED='\033[0;31m'      # Errors, failures
GREEN='\033[0;32m'    # Success, completion
YELLOW='\033[1;33m'   # Warnings, info
BLUE='\033[0;34m'     # Headers, sections
NC='\033[0m'          # No Color (reset)
```

### Directory Navigation

- Scripts use `PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`
- Always cd to project root before running commands
- Change to specific directories (frontend/) when needed
- Return to project root after completion

## Relationship to Project

### Pre-commit Hooks

- **setup-hooks.sh** installs hooks from `.pre-commit-config.yaml`
- Hooks run automatically on `git commit`
- Hooks include:
  - ruff (linting + formatting)
  - mypy (type checking)
  - eslint (JS/TS linting)
  - prettier (formatting)
  - typescript (type checking)
  - fast-test (quick pytest run)

### Testing Infrastructure

- **test-runner.sh** implements same checks as pre-commit hooks
- Additional coverage HTML reports for review
- Used in development and CI/CD

### Quality Gates

1. **Pre-commit:** `validate.sh` equivalent (fast checks)
2. **Pre-push:** `test-runner.sh` (full suite with coverage)
3. **CI/CD:** `validate.sh` (fast checks for automation)

## Entry Points for Agents

### Setting Up New Environment

1. Run `./scripts/setup.sh` (or `.\scripts\setup.ps1` on Windows)
   - This automatically handles prerequisites, dependencies, and configuration
   - Use `--skip-gpu` if no NVIDIA GPU is available
   - Use `--skip-tests` for faster setup
2. Activate virtual environment:
   - Linux/macOS: `source .venv/bin/activate`
   - Windows: `.\.venv\Scripts\Activate.ps1`
3. Optional: Seed test data: `./scripts/seed-cameras.py --no-folders`
4. Optional: Verify with `./scripts/validate.sh`

### Starting Development Services

1. **Core services (required):**

   ```bash
   ./scripts/dev.sh start  # Redis, Backend, Frontend
   ```

2. **AI services (optional, for AI features):**

   ```bash
   # First time only: download models
   ./ai/download_models.sh

   # Start AI services
   ./scripts/start-ai.sh start  # RT-DETRv2, Nemotron LLM
   ```

3. **Check status:**

   ```bash
   ./scripts/dev.sh status        # Core services
   ./scripts/start-ai.sh status   # AI services
   ```

4. **Stop services:**
   ```bash
   ./scripts/dev.sh stop
   ./scripts/start-ai.sh stop
   ```

### Running Tests

1. Quick validation: `./scripts/validate.sh`
2. Full test suite: `./scripts/test-runner.sh`
3. Docker deployment: `./scripts/test-docker.sh`
4. Specific tests: `pytest backend/tests/unit/test_file.py -v`

### Database Management

1. Seed cameras: `./scripts/seed-cameras.py`
2. List cameras: `./scripts/seed-cameras.py --list`
3. Reset cameras: `./scripts/seed-cameras.py --clear --count 6`
4. Check database state before E2E tests

### Before Committing

1. Run `./scripts/validate.sh` (optional, pre-commit hooks will run anyway)
2. Stage changes: `git add -A`
3. Commit: `git commit -m "message"` (hooks run automatically)

### Before Pushing

1. Run `./scripts/test-runner.sh` (mandatory)
2. Check coverage reports if needed
3. Push: `git push origin main`

### Debugging Services

1. **View logs:**

   ```bash
   # Core services
   ./scripts/dev.sh logs
   tail -f logs/backend.log
   tail -f logs/frontend.log

   # AI services
   tail -f /tmp/rtdetr-detector.log
   tail -f /tmp/nemotron-llm.log
   ```

2. **Check health:**

   ```bash
   # Core services
   curl http://localhost:8000/health  # Backend
   curl http://localhost:6379         # Redis (or redis-cli ping)

   # AI services
   ./scripts/start-ai.sh health
   curl http://localhost:8001/health  # RT-DETRv2
   curl http://localhost:8002/health  # Nemotron
   ```

3. **GPU monitoring:**
   ```bash
   nvidia-smi                          # Current GPU status
   watch -n 1 nvidia-smi              # Live GPU monitoring
   ./scripts/start-ai.sh status       # AI service GPU usage
   ```

### Database Seeding

**seed-cameras.py** (223 lines, executable)

- **Purpose:** Populate database with test cameras for development and testing
- **What it does:**
  1. Initializes database connection
  2. Creates sample camera records with realistic names
  3. Optionally creates corresponding folders in `/export/foscam/`
  4. Prevents duplicates (idempotent)
  5. Lists cameras with folder status
- **When to use:**
  - Setting up development environment
  - Resetting database for testing
  - E2E test setup
  - After clearing database
- **Usage:**

  ```bash
  # Seed all 6 default cameras (creates folders)
  ./scripts/seed-cameras.py

  # Seed specific number of cameras without creating folders
  python scripts/seed-cameras.py --count 4 --no-folders

  # Clear existing cameras and re-seed
  ./scripts/seed-cameras.py --clear --count 3

  # List current cameras
  ./scripts/seed-cameras.py --list

  # Show help
  ./scripts/seed-cameras.py --help
  ```

- **Command-line options:**
  - `--clear` - Remove all cameras before seeding
  - `--count N` - Number of cameras to create (1-6, default: 6)
  - `--no-folders` - Don't create camera folders on filesystem
  - `--list` - List all cameras and exit
- **Sample cameras:**
  1. Front Door (front-door) - active
  2. Backyard (backyard) - active
  3. Garage (garage) - inactive
  4. Driveway (driveway) - active
  5. Side Gate (side-gate) - active
  6. Living Room (living-room) - inactive
- **Output:**
  - Progress messages for each camera
  - Warning if folder creation fails (permission issues)
  - Table showing cameras with folder status (✓/✗)
  - Clear status of operations
- **Idempotency:**
  - Running multiple times won't create duplicates
  - Skips cameras that already exist
  - Safe to run repeatedly
- **Dependencies:**
  - Backend database models (Camera)
  - SQLAlchemy async session
  - Requires database initialization

## Future Scripts (Not Yet Implemented)

These may be added in later phases:

- **start-services.sh** - Start all services (backend, redis, AI models)
- **stop-services.sh** - Stop all services
- **reset-database.sh** - Clear database and reset to initial state
- **download-models.sh** - Download AI model weights (exists in `ai/` directory)
- **deploy.sh** - Production deployment automation

## Conventions

### Script Naming

- Use kebab-case: `setup-hooks.sh`, `test-runner.sh`
- Suffix with `.sh` for shell scripts
- Suffix with `.py` for Python scripts
- Make executable: `chmod +x scripts/*.sh`

### Script Structure

```bash
#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
# ... other colors

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Script logic
echo -e "${GREEN}Starting...${NC}"

# ... do work

echo -e "${GREEN}Complete!${NC}"
```

### Error Messages

- Use colored output for visibility
- Print clear error messages before exit
- Exit with non-zero code on failure
- Print success messages on completion

## Related Documentation

- **Root .pre-commit-config.yaml:** Hook configuration
- **pyproject.toml:** Python tool configuration
- **pytest.ini:** Pytest configuration
- **frontend/package.json:** Frontend test scripts
- **CLAUDE.md:** Git and testing workflow rules
