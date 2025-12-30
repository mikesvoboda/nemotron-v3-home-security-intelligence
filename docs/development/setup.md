---
title: Development Environment Setup
source_refs:
  - scripts/setup.sh:1
  - scripts/setup-hooks.sh:1
  - scripts/validate.sh:1
  - pyproject.toml:1
  - .pre-commit-config.yaml:1
  - backend/requirements.txt:1
  - frontend/package.json:1
---

# Development Environment Setup

This guide walks you through setting up a complete development environment for the Home Security Intelligence project.

## Prerequisites

Before starting, ensure you have the following installed:

### Required Software

| Requirement    | Minimum Version | Check Command            | Notes                          |
| -------------- | --------------- | ------------------------ | ------------------------------ |
| **Python**     | 3.14+           | `python3 --version`      | Required for backend           |
| **Node.js**    | 18+             | `node --version`         | Required for frontend          |
| **npm**        | 9+              | `npm --version`          | Comes with Node.js             |
| **Git**        | 2.x             | `git --version`          | Version control                |
| **Podman**     | 4.x             | `podman --version`       | Container runtime (not Docker) |
| **PostgreSQL** | 16+             | `psql --version`         | Or use testcontainers          |
| **Redis**      | 7+              | `redis-server --version` | Or use testcontainers          |

### Optional (for GPU features)

| Requirement       | Minimum Version | Check Command    | Notes                   |
| ----------------- | --------------- | ---------------- | ----------------------- |
| **NVIDIA Driver** | 535+            | `nvidia-smi`     | For GPU-accelerated AI  |
| **CUDA**          | 12.x            | `nvcc --version` | For RT-DETRv2 inference |

### Hardware Recommendations

- **RAM:** 16GB minimum, 32GB recommended
- **GPU:** NVIDIA RTX A5500 or equivalent (24GB VRAM) for full AI pipeline
- **Disk:** 50GB free space for models, containers, and data

## Quick Setup

The fastest way to set up your development environment:

```bash
# Clone the repository
git clone https://github.com/mikesvoboda/home_security_intelligence.git
cd home_security_intelligence

# Run the automated setup script
./scripts/setup.sh
```

This script ([scripts/setup.sh](../../scripts/setup.sh:1)) automatically:

1. Checks all prerequisites
2. Creates a Python virtual environment (`.venv`)
3. Installs backend dependencies
4. Installs frontend dependencies
5. Sets up pre-commit hooks
6. Verifies the installation

## Manual Setup

If you prefer step-by-step control or the automated script fails:

### 1. Clone the Repository

```bash
git clone https://github.com/mikesvoboda/home_security_intelligence.git
cd home_security_intelligence
```

### 2. Backend Setup

Create and activate a Python virtual environment:

```bash
# Using uv (faster, recommended)
uv venv .venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt

# Or using standard venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Install development tools:

```bash
pip install pre-commit ruff mypy pytest
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cd ..
```

### 4. Pre-commit Hooks

Install pre-commit hooks to enforce code quality on every commit:

```bash
# Install standard pre-commit hooks
pre-commit install

# Install pre-push hooks for tests (CRITICAL - do not skip)
pre-commit install --hook-type pre-push
```

The pre-commit configuration ([.pre-commit-config.yaml](../../.pre-commit-config.yaml:1)) includes:

| Hook                  | Stage      | Purpose                       |
| --------------------- | ---------- | ----------------------------- |
| `trailing-whitespace` | pre-commit | Remove trailing whitespace    |
| `end-of-file-fixer`   | pre-commit | Ensure files end with newline |
| `ruff`                | pre-commit | Python linting and formatting |
| `mypy`                | pre-commit | Python type checking          |
| `prettier`            | pre-commit | Frontend code formatting      |
| `eslint`              | pre-commit | TypeScript/JavaScript linting |
| `typescript-check`    | pre-commit | TypeScript type checking      |
| `fast-test`           | pre-push   | Run unit tests before push    |

### 5. Environment Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Key environment variables to configure:

```bash
# Database (PostgreSQL required)
DATABASE_URL=postgresql+asyncpg://security:security_dev_password@localhost:5432/security

# Redis
REDIS_URL=redis://localhost:6379/0

# Camera upload directory
FOSCAM_BASE_PATH=/export/foscam

# AI service endpoints (optional for dev)
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091
```

### 6. Start Infrastructure Services

Using Podman:

```bash
# Start PostgreSQL and Redis
podman-compose -f docker-compose.prod.yml up -d postgres redis
```

Or configure local services manually.

## Verifying the Setup

Run the verification script:

```bash
./scripts/validate.sh
```

This runs ([scripts/validate.sh](../../scripts/validate.sh:1)):

1. **Ruff linting** - Python code style
2. **Ruff formatting** - Python code formatting
3. **MyPy** - Python type checking
4. **Pytest** - Backend tests with 95%+ coverage
5. **ESLint** - Frontend linting
6. **TypeScript** - Frontend type checking
7. **Prettier** - Frontend formatting
8. **Vitest** - Frontend tests

All checks must pass before committing code.

## Development Workflow

### Starting the Development Servers

**Backend:**

```bash
source .venv/bin/activate
python -m backend.main

# Or with hot reload
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**

```bash
cd frontend
npm run dev
```

**Full stack with AI services:**

```bash
./scripts/dev.sh
```

### Running Tests

```bash
# Backend tests
pytest backend/tests/ -v

# Frontend tests
cd frontend && npm test

# Full test suite with coverage
./scripts/test-runner.sh
```

See [testing.md](testing.md) for comprehensive test documentation.

## IDE Configuration

### VS Code (Recommended)

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    }
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "eslint.workingDirectories": ["frontend"],
  "typescript.tsdk": "frontend/node_modules/typescript/lib"
}
```

Recommended extensions:

- **Python:** `ms-python.python`, `charliermarsh.ruff`
- **Frontend:** `esbenp.prettier-vscode`, `dbaeumer.vscode-eslint`
- **General:** `bradlc.vscode-tailwindcss`, `eamodio.gitlens`

### PyCharm / WebStorm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Ruff as external tool for linting
3. Configure ESLint in frontend directory
4. Enable Prettier for TypeScript files

## Common Issues

### Pre-commit Fails on First Run

Pre-commit may need to download hooks on first run:

```bash
pre-commit run --all-files
```

If hooks fail, fix the issues before committing. **Never use `--no-verify`**.

### Database Connection Errors

Ensure PostgreSQL is running:

```bash
podman-compose -f docker-compose.prod.yml up -d postgres
```

Check connection:

```bash
psql postgresql://security:security_dev_password@localhost:5432/security
```

### Import Errors in Tests

Activate the virtual environment:

```bash
source .venv/bin/activate
```

The test configuration automatically adds backend to the Python path.

### Node Modules Issues

Clear and reinstall:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Next Steps

- [Testing Guide](testing.md) - Learn the test strategy and how to write tests
- [Contributing Guide](contributing.md) - Understand the PR process
- [Code Patterns](patterns.md) - Learn key patterns used in the codebase

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Project instructions and rules
- [Backend AGENTS.md](../../backend/AGENTS.md) - Backend architecture overview
- [Frontend AGENTS.md](../../frontend/AGENTS.md) - Frontend architecture overview
