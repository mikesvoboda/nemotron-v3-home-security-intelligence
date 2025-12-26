# Development Scripts

This directory contains scripts to help you set up, test, and run the Nemotron v3 Home Security Intelligence project.

## Quick Start

### First Time Setup

**Linux/macOS:**

```bash
./scripts/setup.sh
```

**Windows:**

```powershell
.\scripts\setup.ps1
```

This will:

- Check prerequisites (Python 3.11+, Node.js 18+, git, etc.)
- Install all backend and frontend dependencies
- Set up pre-commit hooks
- Create `.env` configuration file
- Verify installation

### Setup Options

```bash
# Show all options
./scripts/setup.sh --help

# Skip GPU checks (for machines without NVIDIA GPUs)
./scripts/setup.sh --skip-gpu

# Skip verification tests (faster)
./scripts/setup.sh --skip-tests

# Clean and reinstall everything
./scripts/setup.sh --clean
```

## Available Scripts

### Development Setup

| Script           | Platform    | Purpose                                      |
| ---------------- | ----------- | -------------------------------------------- |
| `setup.sh`       | Linux/macOS | Full development environment setup           |
| `setup.ps1`      | Windows     | Full development environment setup           |
| `setup-hooks.sh` | Linux/macOS | Legacy setup script (use `setup.sh` instead) |

### Testing

| Script           | Purpose                                           |
| ---------------- | ------------------------------------------------- |
| `test-runner.sh` | Run full test suite with 95% coverage enforcement |
| `validate.sh`    | Quick validation (linting, type checking, tests)  |
| `smoke-test.sh`  | E2E smoke test for MVP pipeline validation        |

### Development Tools

| Script            | Purpose                             |
| ----------------- | ----------------------------------- |
| `dev.sh`          | Start all development services      |
| `seed-cameras.py` | Populate database with test cameras |

## Usage Examples

### Setting Up a New Development Environment

```bash
# 1. Clone the repository
git clone <repo-url>
cd nemotron-v3-home-security-intelligence

# 2. Run setup script
./scripts/setup.sh

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Start development
cd backend && uvicorn main:app --reload
```

### Running Tests

```bash
# Full test suite with coverage reports
./scripts/test-runner.sh

# Quick validation (faster)
./scripts/validate.sh

# Specific test file
pytest backend/tests/unit/test_feature.py -v
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
./scripts/seed-cameras.py

# Seed without creating folders
./scripts/seed-cameras.py --no-folders

# Seed specific number of cameras
./scripts/seed-cameras.py --count 3

# Clear and re-seed
./scripts/seed-cameras.py --clear --count 6

# List current cameras
./scripts/seed-cameras.py --list
```

## Prerequisites

### Required

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **git** - [Download](https://git-scm.com/)

### Optional

- **Docker** - For containerized services (optional)
- **NVIDIA GPU drivers** - For GPU-accelerated AI inference (optional)
  - Use `--skip-gpu` flag if you don't have an NVIDIA GPU

### Windows-Specific

- **PowerShell 5.1+** or **PowerShell Core 7+**
- **Visual Studio Build Tools** (for some Python packages)

## Troubleshooting

### "Command not found" errors

**Linux/macOS:**

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
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
python3 --version  # Should be 3.11 or higher

# If you have multiple Python versions, use specific version
python3.11 -m venv .venv
```

### Node.js version issues

```bash
# Check Node version
node --version  # Should be 18 or higher

# Use nvm (Node Version Manager) to install correct version
nvm install 18
nvm use 18
```

### Permission denied errors

**Linux/macOS:**

```bash
# Make scripts executable
chmod +x scripts/*.sh

# If you get permission errors for folders
sudo chown -R $USER:$USER .
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

# Run hooks manually to test
pre-commit run --all-files
```

### Database issues

```bash
# Delete and recreate database
rm -f data/security.db

# Start backend (will recreate database)
cd backend
uvicorn main:app --reload

# Seed test data
./scripts/seed-cameras.py
```

## Environment Variables

The setup script creates a `.env` file from `.env.example`. Review and update these variables:

```bash
# Camera Configuration
CAMERA_ROOT=/export/foscam

# Database
DATABASE_URL=sqlite+aiosqlite:///data/security.db

# Redis
REDIS_URL=redis://localhost:6379

# AI Services
DETECTOR_URL=http://localhost:8001
LLM_URL=http://localhost:8002

# Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Retention
RETENTION_DAYS=30

# GPU Monitoring
GPU_POLL_INTERVAL_SECONDS=2

# Frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

## Next Steps After Setup

1. **Review configuration:**

   ```bash
   nano .env  # or your preferred editor
   ```

2. **Start backend server:**

   ```bash
   source .venv/bin/activate
   cd backend
   uvicorn main:app --reload
   ```

3. **Start frontend (in another terminal):**

   ```bash
   cd frontend
   npm run dev
   ```

4. **Seed test data:**

   ```bash
   ./scripts/seed-cameras.py
   ```

5. **Run tests:**
   ```bash
   ./scripts/test-runner.sh
   ```

## Getting Help

- **Script help:** `./scripts/setup.sh --help`
- **Project documentation:** See `AGENTS.md` files in each directory
- **Roadmap:** See `docs/ROADMAP.md`
- **Git workflow:** See `CLAUDE.md` in project root

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
./scripts/setup.sh --help

# Dry run (check without installing)
# Add this to your script: --dry-run flag

# Test on clean environment
./scripts/setup.sh --clean
./scripts/setup.sh
```

## Related Documentation

- **scripts/AGENTS.md** - Detailed technical documentation for AI agents
- **CLAUDE.md** - Git and development workflow rules
- **README.md** - Project overview and architecture
- **docs/ROADMAP.md** - Future enhancements and features
