---
title: Local Development Setup
source_refs:
  - setup.py:1
  - scripts/setup-hooks.sh:1
  - scripts/validate.sh:1
  - pyproject.toml:1
  - .pre-commit-config.yaml:1
  - uv.lock:1
  - frontend/package.json:1
---

# Local Development Setup

> Get a development environment running: the fast path first, then the details — prerequisites, GPU/CUDA, database and `.env` configuration, service startup, IDE setup, HTTPS, and troubleshooting.

**Time to read:** ~10 min for the fast path, ~25 min end to end
**Prerequisites:** see [Prerequisites](#prerequisites) — Python 3.14+, Node.js 24 LTS (22.12+ accepted), npm 9+, Git 2.x, and Docker 20+ or Podman 4+

---

This is the single setup guide for the Home Security Intelligence project. Start with [Quick Setup](#quick-setup) if you just want a working environment; work down through the numbered sections for step-by-step control, GPU/CUDA setup, environment-variable details, and the validation suite. Troubleshooting is at the end under [Common Issues](#common-issues).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup](#quick-setup)
3. [Manual Setup](#manual-setup)
   1. [1. Clone the Repository](#1-clone-the-repository)
   2. [2. Backend Setup](#2-backend-setup)
   3. [3. Frontend Setup](#3-frontend-setup)
   4. [4. Pre-commit Hooks](#4-pre-commit-hooks)
   5. [5. Environment Configuration](#5-environment-configuration)
   6. [6. Start Infrastructure Services](#6-start-infrastructure-services)
4. [GPU Setup](#gpu-setup)
5. [Verifying the Setup](#verifying-the-setup)
6. [Development Workflow](#development-workflow)
7. [IDE Configuration](#ide-configuration)
8. [Enabling HTTPS](#enabling-https)
9. [Common Issues](#common-issues)
10. [Next Steps](#next-steps)
11. [Related Documentation](#related-documentation)

## Prerequisites

Before starting, ensure you have the following installed.

### Required Software

| Requirement    | Minimum Version         | Check Command                            | Notes                         |
| -------------- | ----------------------- | ---------------------------------------- | ----------------------------- |
| **Python**     | 3.14+                   | `python3 --version`                      | Required for backend          |
| **Node.js**    | 24 LTS, 22.12+ accepted | `node --version`                         | Required for frontend         |
| **npm**        | 9+                      | `npm --version`                          | Comes with Node.js            |
| **Git**        | 2.x                     | `git --version`                          | Version control               |
| **Container**  | Docker 20+ or Podman 4+ | `docker --version` or `podman --version` | Docker or Podman              |
| **PostgreSQL** | 16+                     | `psql --version`                         | Containerized setup in step 6 |
| **Redis**      | 7+                      | `redis-server --version`                 | Containerized setup in step 6 |

### Optional (for GPU features)

| Requirement       | Minimum Version | Check Command    | Notes                  |
| ----------------- | --------------- | ---------------- | ---------------------- |
| **NVIDIA Driver** | 535+            | `nvidia-smi`     | For GPU-accelerated AI |
| **CUDA**          | 12.x            | `nvcc --version` | For YOLO26 inference   |

### Hardware Recommendations

- **RAM:** 16GB minimum, 32GB recommended
- **GPU:** NVIDIA RTX A5500 or equivalent (24GB VRAM) for full AI pipeline
- **Disk:** 50GB free space for models, containers, and data

## Quick Setup

The fastest way to set up your development environment:

```bash
# Clone the repository
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence

# Run the interactive setup script
python setup.py
```

The script ([setup.py](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/setup.py)) automatically:

1. Prompts for camera/model paths, ports, and security credentials (quick mode accepts defaults with Enter; `--guided` walks you through with explanations)
2. Generates `.env` with secure, unique values (JWT secret, database password) and sets its permissions to `600`
3. Optionally installs pre-commit and pre-push hooks (`python setup.py --dev`)

Then sync dependencies (details in [Manual Setup](#manual-setup)):

```bash
uv sync --extra dev
cd frontend && npm install
```

## Manual Setup

If you prefer step-by-step control or the automated script fails.

### 1. Clone the Repository

```bash
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence
```

### 2. Backend Setup

Create and activate a Python virtual environment:

```bash
# Using uv (recommended - 10-100x faster than pip)
# Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --extra dev

# This creates .venv and installs all dependencies from pyproject.toml
# Development tools (pre-commit, ruff, mypy, pytest) are included

# Activate the environment for manual commands
source .venv/bin/activate
```

**Note:** This project uses `uv` for Python dependency management with `pyproject.toml` as the dependency source. The `uv.lock` file ensures reproducible builds.

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

The pre-commit configuration ([.pre-commit-config.yaml](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/.pre-commit-config.yaml)) includes:

| Hook                  | Stage      | Purpose                       |
| --------------------- | ---------- | ----------------------------- |
| `trailing-whitespace` | pre-commit | Remove trailing whitespace    |
| `end-of-file-fixer`   | pre-commit | Ensure files end with newline |
| `ruff`                | pre-commit | Python linting and formatting |
| `mypy`                | pre-commit | Python type checking          |
| `prettier`            | pre-commit | Frontend code formatting      |
| `eslint`              | pre-commit | TypeScript/JavaScript linting |
| `typescript-check`    | pre-commit | TypeScript type checking      |
| `auto-rebase`         | pre-push   | Rebase on origin/main         |
| `parallel-tests`      | pre-push   | Selected fast test tiers      |

See [hooks.md](hooks.md) for the full hook reference.

![Script Dependency Graph](../images/architecture/script-dependency-graph.png)

_Script dependency graph showing relationships between setup scripts, validation tools, and test runners._

### 5. Environment Configuration

Run the setup script to generate `.env` with secure, unique credentials (recommended):

```bash
python setup.py
```

Or create the file from the example and edit it by hand:

```bash
cp .env.example .env
```

Key environment variables to configure:

```bash
# Database (PostgreSQL required)
# IMPORTANT: Run python setup.py to generate .env with a secure password, or set manually:
# Generate password: openssl rand -base64 32
DATABASE_URL=postgresql+asyncpg://security:<your-password>@localhost:5432/security

# Redis
REDIS_URL=redis://localhost:6379/0

# Camera upload directory
FOSCAM_BASE_PATH=/export/foscam

# AI service endpoints (optional for dev)
# Models are served through the AI gateway (port 8090); see .env.example
AI_GATEWAY_URL=http://localhost:8090
YOLO26_URL=http://localhost:8090/yolo26
NEMOTRON_URL=http://localhost:8091
```

`.env` is the sole configuration source for the stack — `docker-compose.prod.yml` reads all of its config from `.env`. Never commit `.env` or `secrets/` to version control. Every variable is documented in [Environment Variable Reference](../reference/config/env-reference.md).

### 6. Start Infrastructure Services

Using Docker or Podman:

```bash
# Docker
docker compose -f docker-compose.prod.yml up -d postgres redis

# OR Podman
podman-compose -f docker-compose.prod.yml up -d postgres redis

# Verify
podman ps
```

Or configure local services manually. See [Database Management](../operator/database.md) for PostgreSQL setup beyond the development container.

## GPU Setup

GPU support is optional (see the [Optional prerequisites](#optional-for-gpu-features) above), but the full AI pipeline assumes an NVIDIA GPU.

1. Install the NVIDIA driver (535+ is the supported floor — check with `nvidia-smi`). Driver-level configuration is covered in [GPU Setup](../operator/gpu-setup.md).
2. Install CUDA 12.x (check with `nvcc --version`); CUDA is required for YOLO26 inference.
3. Confirm the hardware meets the [Hardware Recommendations](#hardware-recommendations) above — 24GB VRAM for the full pipeline.
4. Set the GPU assignment variables in `.env` (the setup script writes them): `GPU_LLM` selects the GPU that hosts the Nemotron LLM (which needs roughly 22GB VRAM), `GPU_AI_SERVICES` the GPU that hosts the remaining models (YOLO26, Florence, CLIP, enrichment), and `BACKEND_MODEL_PRELOAD` to eagerly load backend models into VRAM at startup.

Multi-GPU topology and CUDA architecture details live in [multi-gpu.md](multi-gpu.md).

## Verifying the Setup

Run the verification script:

```bash
./scripts/validate.sh
```

This runs ([scripts/validate.sh](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/scripts/validate.sh)):

1. **Ruff linting** - Python code style
2. **Ruff formatting** - Python code formatting
3. **MyPy** - Python type checking
4. **Pytest** - Backend tests; combined unit+integration coverage gated at 80% by validate.sh
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

## Enabling HTTPS

For secure local development or production deployment, you can enable HTTPS:

```bash
# Generate self-signed certificate for development
./scripts/generate-certs.sh

# Enable HTTPS
echo "SSL_ENABLED=true" >> .env

# Restart frontend
docker compose -f docker-compose.prod.yml restart frontend
```

Access at `https://localhost:8444` (the default `FRONTEND_HTTPS_PORT` host mapping). See [SSL/HTTPS Configuration](ssl-https.md) for complete documentation.

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
# Docker
docker compose -f docker-compose.prod.yml up -d postgres

# OR Podman
podman-compose -f docker-compose.prod.yml up -d postgres
```

Check connection:

```bash
psql postgresql://security:<your-password>@localhost:5432/security
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

- [Codebase Tour](codebase-tour.md) - Understand the directory structure
- [Hooks](hooks.md) - Pre-commit configuration
- [Pipeline Overview](pipeline-overview.md) - AI processing flow
- [Testing Guide](testing.md) - Learn the test strategy and how to write tests
- [Contributing Guide](contributing/README.md) - Understand the PR process
- [Code Patterns](patterns-and-conventions.md) - Learn key patterns used in the codebase
- [SSL/HTTPS Configuration](ssl-https.md) - Enable HTTPS for secure connections

## Related Documentation

- [GPU Setup](../operator/gpu-setup.md) - GPU driver configuration for AI
- [Database Management](../operator/database.md) - PostgreSQL setup
- [Environment Variable Reference](../reference/config/env-reference.md) - Configuration options
- [AGENTS.md](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/AGENTS.md) - Project instructions and rules
- [Backend AGENTS.md](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/backend/AGENTS.md) - Backend architecture overview
- [Frontend AGENTS.md](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/frontend/AGENTS.md) - Frontend architecture overview

---

[Back to Developer Hub](README.md)
