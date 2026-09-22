# Development Scripts

This directory contains scripts to help you set up, test, and run the Nemotron v3 Home Security Intelligence project.

## Quick Start

### First Time Setup

**Linux/macOS (and any platform with Python):**

```bash
python setup.py          # repo root - cross-platform setup
```

`setup.py` lives at the repository root. It checks prerequisites, creates
`.venv` via [uv](https://docs.astral.sh/uv/), syncs Python dependencies,
generates `.env` from `.env.example`, and installs pre-commit hooks when you
pass `--dev`. The former `scripts/setup.sh` was removed in the setup
consolidation (commit 84188795).

**Windows extras:**

```powershell
.\scripts\setup.ps1      # npm prerequisites + frontend deps on Windows
```

Useful `setup.py` flags (`python setup.py --help` for the full list):

```bash
python setup.py --defaults   # non-interactive, all defaults
python setup.py --dev        # install pre-commit hooks
python setup.py --yes        # auto-accept prompts (quick mode)
```

### Install frontend dependencies

```bash
cd frontend
npm ci                     # CI uses npm; bun.lock is also kept in sync
```

## Available Scripts

### Development Setup

| Script             | Platform    | Purpose                                                                                              |
| ------------------ | ----------- | ---------------------------------------------------------------------------------------------------- |
| (root) `setup.py`  | All         | Cross-platform dev environment setup (the entry point this README used to attribute to a `setup.sh`) |
| `setup.ps1`        | Windows     | Windows dev environment extras (npm/prereq checks, frontend deps)                                    |
| `setup-hooks.sh`   | Linux/macOS | Pre-commit / commit-msg / pre-push git hook setup                                                    |
| `setup-systemd.sh` | Linux       | Install backend as a systemd service                                                                 |
| `setup-launchd.sh` | macOS       | Install backend as a launchd service                                                                 |

### Testing

| Script           | Purpose                                                                     |
| ---------------- | --------------------------------------------------------------------------- |
| `test-runner.sh` | Optional local full-suite runner (no CI gate; see its header)               |
| `validate.sh`    | Validation the CI mirrors (lint, types, tests, 80% combined coverage floor) |
| `smoke-test.sh`  | E2E smoke test for MVP pipeline validation                                  |

### Development Tools

| Script           | Purpose                                        |
| ---------------- | ---------------------------------------------- |
| `dev.sh`         | Start all development services                 |
| `seed-events.py` | Populate database with mock events and cameras |

## Usage Examples

### Setting Up a New Development Environment

```bash
# 1. Clone the repository
git clone <repo-url>
cd nemotron-v3-home-security-intelligence

# 2. Run setup (creates .venv + .env)
python setup.py --dev

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Start development (repo root)
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running Tests

```bash
# Full test suite with coverage reports
./scripts/test-runner.sh

# Quick validation (faster)
./scripts/validate.sh

# Specific test file
uv run pytest backend/tests/unit/test_feature.py -v
```

### Running E2E Smoke Test

```bash
# Basic smoke test (after starting services)
./scripts/smoke-test.sh

# With verbose output for debugging
./scripts/smoke-test.sh --verbose

# Keep test artifacts for inspection
./scripts/smoke-test.sh --skip-cleanup

# Custom API URL and timeout
./scripts/smoke-test.sh --api-url http://192.168.1.100:8000 --timeout 180

# Show help
./scripts/smoke-test.sh --help
```

### Seeding Test Data

```bash
# Seed all cameras (creates folders)
./scripts/seed-events.py

# Seed without creating folders
./scripts/seed-events.py --no-folders

# Seed specific number of cameras
./scripts/seed-events.py --count 3

# Clear and re-seed
./scripts/seed-events.py --clear --count 6

# List current cameras
./scripts/seed-events.py --list
```

## Prerequisites

### Required

- **Python 3.14+** (`requires-python = ">=3.14"` in `pyproject.toml`) - [Download](https://www.python.org/downloads/)
- **uv** - creates `.venv` and syncs dependencies (`uv sync --extra dev`)
- **Node.js 24 LTS, 22.12+ accepted** (`engines` in `frontend/package.json`; Vite 7 requirement) - [Download](https://nodejs.org/)
- **git** - [Download](https://git-scm.com/)

### Optional

- **Podman or Docker** - for containerized services (this project standardizes on Podman; see `AGENTS.md`)
- **NVIDIA GPU drivers** - for GPU-accelerated AI inference

### Windows-Specific

- **PowerShell 5.1+** or **PowerShell Core 7+**
- **Visual Studio Build Tools** (for some Python packages)

## Troubleshooting

### "Command not found" errors

**Linux/macOS:**

```bash
chmod +x scripts/*.sh
python setup.py
```

**Windows:**

```powershell
# Run PowerShell as Administrator if needed
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\setup.ps1
```

### Python version issues

```bash
# Check Python version
python3 --version  # Should be 3.14 or higher

# uv can install and pin the right version
uv python install 3.14
```

### Node.js version issues

```bash
# Check Node version
node --version  # Should be 24.x, or 22.12+

# Use nvm (Node Version Manager) to install correct version
nvm install 24
nvm use 24
```

### Permission denied errors

**Linux/macOS:**

```bash
# Make scripts executable
chmod +x scripts/*.sh
```

**Windows:**

```powershell
# Run PowerShell as Administrator
# Then run setup script
.\scripts\setup.ps1
```

### Pre-commit hook issues

```bash
# Reinstall pre-commit hooks
pre-commit uninstall
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push

# Run hooks manually to test
pre-commit run --all-files
```

### Database issues

The database is PostgreSQL (no SQLite fallback). To reset it, tear the stack
down and remove the compose-managed `postgres_data` volume (find its
project-prefixed name first):

```bash
podman compose -f docker-compose.prod.yml down
podman volume ls | grep postgres_data        # e.g. workspace_postgres_data
podman volume rm <that-name>
podman compose -f docker-compose.prod.yml up -d postgres
```

## Environment Variables

`setup.py` creates a `.env` file from `.env.example`. Review and update these
variables (values below are the current `.env.example` defaults - grep it
before copying; secrets like the database password are generated by setup):

```bash
# Camera Configuration
FOSCAM_BASE_PATH=/export/foscam

# Database (PostgreSQL; password generated by setup)
# DATABASE_URL=postgresql+asyncpg://security:<GENERATED_BY_SETUP>@localhost:5432/security

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Services (defaults point at the ai-gateway facade; see USE_AI_GATEWAY)
YOLO26_URL=http://localhost:8090/yolo26
NEMOTRON_URL=http://localhost:8091

# Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Retention
RETENTION_DAYS=30

# GPU Monitoring
GPU_POLL_INTERVAL_SECONDS=5.0

# Frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

## Next Steps After Setup

1. **Review configuration:**

   ```bash
   nano .env  # or your preferred editor
   ```

2. **Start backend server (repo root):**

   ```bash
   uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Start frontend (in another terminal):**

   ```bash
   cd frontend
   npm run dev
   ```

4. **Seed test data:**

   ```bash
   ./scripts/seed-events.py
   ```

5. **Run tests:**
   ```bash
   ./scripts/test-runner.sh
   ```

## Getting Help

- **Setup help:** `python setup.py --help`
- **Project documentation:** See `AGENTS.md` files in each directory
- **Roadmap:** See `docs/ROADMAP.md`
- **Git workflow:** See `AGENTS.md` in project root

## For Developers

### Script Conventions

- All scripts use colored output for better readability
- Scripts are idempotent (safe to run multiple times)
- Scripts check for prerequisites before running
- Scripts provide clear error messages and exit codes

### Adding New Scripts

1. Create script in `scripts/` directory
2. Make executable: `chmod +x scripts/your-script.sh`
3. Add shebang: `#!/bin/bash`
4. Use color codes from existing scripts
5. Document in `scripts/AGENTS.md`
6. Add to this README

### Testing Scripts

```bash
# Test help message
python setup.py --help
```

## Related Documentation

- **scripts/AGENTS.md** - Detailed technical documentation for AI agents
- **AGENTS.md** - Git and development workflow rules
- **README.md** - Project overview and architecture
- **docs/ROADMAP.md** - Future enhancements and features
