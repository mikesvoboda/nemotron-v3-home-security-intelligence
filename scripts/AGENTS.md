# Scripts Directory - Agent Guide

## Purpose

This directory contains development, testing, and deployment automation scripts for the Home Security Intelligence project.

## Key Files

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

## Script Comparison

| Feature               | setup.sh             | test-runner.sh        | validate.sh           |
| --------------------- | -------------------- | --------------------- | --------------------- |
| Purpose               | Environment setup    | Comprehensive testing | Quick validation      |
| Run frequency         | Once per environment | Before commits        | Before commits/push   |
| Prerequisite checks   | Yes (Python, Node)   | No                    | No                    |
| Backend tests         | Optional             | Yes (pytest)          | Yes (pytest)          |
| Frontend tests        | Optional             | Yes (Vitest)          | Yes (Vitest)          |
| Coverage reports      | No                   | Yes (HTML + JSON)     | No (terminal only)    |
| Coverage threshold    | N/A                  | 95%                   | 90%                   |
| Linting               | No                   | No                    | Yes (ruff + eslint)   |
| Type checking         | No                   | No                    | Yes (mypy + tsc)      |
| Formatting check      | No                   | No                    | Yes (ruff + prettier) |
| Pre-commit hooks      | Installs             | No                    | No                    |
| Colored output        | Yes                  | Yes                   | Yes                   |
| Creates .env file     | Yes                  | No                    | No                    |
| Installs dependencies | Yes                  | No                    | No                    |
| Command-line options  | Yes (4 options)      | No                    | No                    |
| Windows support       | setup.ps1            | No                    | No                    |

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

### Running Tests

1. Quick validation: `./scripts/validate.sh`
2. Full test suite: `./scripts/test-runner.sh`
3. Specific tests: `pytest backend/tests/unit/test_file.py -v`

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
