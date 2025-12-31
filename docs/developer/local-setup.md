# Local Development Setup

> Get your development environment running in under 10 minutes.

**Time to read:** ~5 min
**Prerequisites:** Python 3.14+, Node.js 18+, Docker/Podman

---

This document provides a streamlined guide for setting up local development. For comprehensive setup details, see [Development Setup](../development/setup.md).

## Quick Setup

```bash
# Clone repository
git clone https://github.com/mikesvoboda/home_security_intelligence.git
cd home_security_intelligence

# Run automated setup
./scripts/setup.sh
```

The setup script:

1. Creates Python virtual environment (`.venv`)
2. Installs backend dependencies
3. Installs frontend dependencies
4. Configures pre-commit hooks

## Manual Setup

### 1. Backend

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Install dev tools
pip install pre-commit ruff mypy pytest
```

### 2. Frontend

```bash
cd frontend
npm install
cd ..
```

### 3. Pre-commit Hooks

```bash
# Install hooks (CRITICAL - never bypass)
pre-commit install
pre-commit install --hook-type pre-push
```

### 4. Infrastructure

```bash
# Start PostgreSQL and Redis
podman-compose -f docker-compose.prod.yml up -d postgres redis

# Verify
podman ps
```

### 5. Environment

```bash
# Copy example environment
cp .env.example .env

# Edit as needed
# DATABASE_URL=postgresql+asyncpg://security:security_dev_password@localhost:5432/security
# REDIS_URL=redis://localhost:6379/0
```

## Running the Stack

**Backend:**

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**

```bash
cd frontend
npm run dev
```

**Full stack with AI (optional):**

```bash
./scripts/dev.sh
```

## Verification

```bash
# Run validation suite
./scripts/validate.sh

# Backend tests
pytest backend/tests/ -v

# Frontend tests
cd frontend && npm test
```

---

## Next Steps

- [Codebase Tour](codebase-tour.md) - Understand the directory structure
- [Hooks](hooks.md) - Pre-commit configuration
- [Pipeline Overview](pipeline-overview.md) - AI processing flow

---

## See Also

- [GPU Setup](../operator/gpu-setup.md) - GPU driver configuration for AI
- [Database Management](../operator/database.md) - PostgreSQL setup
- [Environment Variable Reference](../reference/config/env-reference.md) - Configuration options

---

[Back to Developer Hub](../developer-hub.md)
