# UV Package Manager Guide

**Comprehensive guide to using uv for Python dependency management in this project.**

uv is Astral's next-generation Python package manager, offering 10-100x faster dependency resolution and installation compared to pip. This project uses uv exclusively for Python dependency management.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Reference](#quick-reference)
3. [Project Configuration](#project-configuration)
4. [Dependency Groups](#dependency-groups)
5. [Common Commands](#common-commands)
6. [CI/CD Integration](#cicd-integration)
7. [Docker Integration](#docker-integration)
8. [Troubleshooting](#troubleshooting)
9. [Migration from pip](#migration-from-pip)

---

## Installation

### Local Development

```bash
# Install uv (recommended method)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew (macOS/Linux)
brew install uv

# Or with pip (not recommended for production)
pip install uv

# Verify installation
uv --version
```

### Version Management

This project pins uv version `0.9.18` for CI/CD reproducibility. Check the current pinned version in `.github/workflows/ci.yml`:

```yaml
env:
  UV_VERSION: '0.9.18'
```

To update your local uv to match CI:

```bash
# Install specific version
uv self update --to 0.9.18

# Or reinstall
curl -LsSf https://astral.sh/uv/install.sh | UV_VERSION=0.9.18 sh
```

---

## Quick Reference

```bash
# Install all dependencies (creates .venv if needed)
uv sync

# Install with dev dependencies
uv sync --extra dev

# Install specific dependency groups (PEP 735)
uv sync --group lint
uv sync --group test
uv sync --group lint --group test  # Multiple groups

# Add a new dependency
uv add <package>           # Production dependency
uv add --dev <package>     # Dev dependency

# Remove a dependency
uv remove <package>

# Update lock file after editing pyproject.toml
uv lock

# Run a command in the virtual environment
uv run pytest              # Run pytest
uv run ruff check backend  # Run linter
uv run mypy backend        # Run type checker

# Run a tool without installing it
uv tool run black .        # One-off tool execution
```

---

## Project Configuration

### Key Files

| File              | Purpose                                         |
| ----------------- | ----------------------------------------------- |
| `pyproject.toml`  | Project metadata, dependencies, and tool config |
| `uv.lock`         | Locked dependency versions (commit this file)   |
| `.python-version` | Python version (3.14)                           |
| `.venv/`          | Virtual environment (auto-created, gitignored)  |

### pyproject.toml Structure

```toml
[project]
name = "home-security-intelligence"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    # Production dependencies
    "fastapi>=0.115.0",
    "sqlalchemy>=2.0.36",
    # ...
]

[project.optional-dependencies]
# Legacy format (still works with uv sync --extra dev)
dev = [
    "pytest>=8.0.0",
    "ruff>=0.8.0",
    # ...
]

[dependency-groups]
# Modern PEP 735 format (recommended)
lint = ["ruff>=0.8.0", "mypy>=1.13.0"]
test = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", ...]
dev = [{include-group = "lint"}, {include-group = "test"}, ...]
```

---

## Dependency Groups

This project uses PEP 735 dependency groups for granular control:

| Group       | Purpose                               | Command                     |
| ----------- | ------------------------------------- | --------------------------- |
| `lint`      | Linting and formatting (ruff, mypy)   | `uv sync --group lint`      |
| `test`      | Core testing framework and utilities  | `uv sync --group test`      |
| `benchmark` | Performance benchmarking tools        | `uv sync --group benchmark` |
| `security`  | Security scanning (bandit)            | `uv sync --group security`  |
| `mutation`  | Mutation testing (mutmut)             | `uv sync --group mutation`  |
| `quality`   | Code quality analysis (wily, vulture) | `uv sync --group quality`   |
| `dev`       | All development dependencies          | `uv sync --group dev`       |

### Group Combinations

```bash
# Install only what you need
uv sync --group lint              # Just linting tools
uv sync --group lint --group test # Lint + test

# Install everything for development
uv sync --extra dev               # Legacy format (optional-dependencies)
uv sync --group dev               # Modern format (dependency-groups)

# CI-optimized: minimal dependencies per job
# Lint job:
uv sync --group lint --frozen
# Test job:
uv sync --group test --frozen
```

### Backwards Compatibility

Both methods work:

```bash
# Legacy (optional-dependencies)
uv sync --extra dev

# Modern (dependency-groups)
uv sync --group dev
```

---

## Common Commands

### Dependency Management

```bash
# Sync dependencies (install/update to match lock file)
uv sync                    # Production only
uv sync --extra dev        # Include dev dependencies
uv sync --frozen           # Don't update lock file (CI)

# Add dependencies
uv add httpx               # Add production dependency
uv add --dev pytest-sugar  # Add dev dependency
uv add "numpy>=2.0"        # With version constraint

# Remove dependencies
uv remove httpx

# Update lock file
uv lock                    # Regenerate uv.lock
uv lock --upgrade          # Upgrade all packages
uv lock --upgrade-package httpx  # Upgrade specific package

# Export for compatibility
uv export > requirements.txt            # Standard export
uv export --no-hashes > requirements.txt  # Without hashes
```

### Running Commands

```bash
# Run in virtual environment
uv run pytest backend/tests/unit/
uv run python -m backend.main
uv run ruff check backend/

# Run tools without installing
uv tool run black .
uv tool run isort .

# Python interpreter
uv python install 3.14     # Install Python version
uv python list             # List available versions
```

### Environment Management

```bash
# Virtual environment (auto-created in .venv/)
uv venv                    # Create if not exists
uv venv --python 3.14      # Specific Python version

# Clean rebuild
rm -rf .venv && uv sync --extra dev
```

---

## CI/CD Integration

### Version Pinning

All CI workflows pin the uv version for reproducibility:

```yaml
# .github/workflows/ci.yml
env:
  UV_VERSION: '0.9.18' # Centralized version

jobs:
  lint:
    steps:
      - uses: astral-sh/setup-uv@v4
        with:
          version: ${{ env.UV_VERSION }}
          enable-cache: true
```

### Updating UV Version Across CI

When updating the uv version:

1. Test locally with the new version:

   ```bash
   uv self update --to <new-version>
   uv sync --extra dev
   uv run pytest backend/tests/unit/
   ```

2. Update all workflow files:

   ```bash
   # Find and replace in all workflows
   find .github/workflows -name "*.yml" -exec sed -i "s/UV_VERSION: '0.9.18'/UV_VERSION: '0.10.0'/g" {} \;
   ```

3. Create a PR and verify CI passes.

### Workflow Examples

**Lint Job:**

```yaml
- name: Set up uv
  uses: astral-sh/setup-uv@v4
  with:
    version: ${{ env.UV_VERSION }}
    enable-cache: true

- name: Install dependencies
  run: uv sync --group lint --frozen

- name: Run linter
  run: uv run ruff check backend/
```

**Test Job:**

```yaml
- name: Install dependencies
  run: uv sync --extra dev --frozen

- name: Run tests
  run: uv run pytest backend/tests/unit/ -n auto
```

---

## Docker Integration

### AI Service Dockerfiles

All AI service Dockerfiles use uv for dependency management:

```dockerfile
# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies with BuildKit cache
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements.txt
```

### Backend Dockerfile

For the main backend service:

```dockerfile
# Multi-stage build
FROM python:3.14-slim as builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Production stage
FROM python:3.14-slim
COPY --from=builder /app/.venv /app/.venv
```

### BuildKit Cache

Enable BuildKit for faster builds:

```bash
# Enable BuildKit
export DOCKER_BUILDKIT=1

# Build with cache
docker build -t backend:latest .
```

---

## Troubleshooting

### Common Issues

#### "No Python interpreter found"

```bash
# Install Python with uv
uv python install 3.14

# Or specify Python path
uv sync --python /usr/bin/python3.14
```

#### Lock file out of sync

```bash
# Regenerate lock file
uv lock

# Force sync from lock file
uv sync --frozen
```

#### Cache issues

```bash
# Clear uv cache
uv cache clean

# Or specify no-cache
uv sync --no-cache
```

#### Virtual environment issues

```bash
# Remove and recreate
rm -rf .venv
uv sync --extra dev
```

#### Version conflicts

```bash
# Show dependency tree
uv pip tree

# Check why a package is installed
uv pip show <package>
```

### CI-Specific Issues

#### "uv command not found"

Ensure setup-uv runs before any uv commands:

```yaml
- uses: astral-sh/setup-uv@v4
  with:
    version: ${{ env.UV_VERSION }}
```

#### Cache not working

Check cache configuration:

```yaml
- uses: astral-sh/setup-uv@v4
  with:
    version: ${{ env.UV_VERSION }}
    enable-cache: true # Must be explicitly enabled
```

---

## Migration from pip

### Converting requirements.txt

```bash
# Generate pyproject.toml from requirements.txt
uv init --from requirements.txt

# Or manually add dependencies
cat requirements.txt | xargs uv add
```

### Key Differences from pip

| pip                      | uv                           |
| ------------------------ | ---------------------------- |
| `pip install -r req.txt` | `uv sync`                    |
| `pip install package`    | `uv add package`             |
| `pip freeze`             | `uv export`                  |
| `pip list`               | `uv pip list`                |
| `python -m pytest`       | `uv run pytest`              |
| `requirements.txt`       | `pyproject.toml` + `uv.lock` |

### Performance Comparison

| Operation       | pip   | uv  | Speedup |
| --------------- | ----- | --- | ------- |
| Clean install   | ~120s | ~3s | 40x     |
| Cached install  | ~30s  | ~1s | 30x     |
| Lock resolution | ~60s  | ~2s | 30x     |
| Add dependency  | ~20s  | ~1s | 20x     |

---

## Related Documentation

- [Astral uv Documentation](https://docs.astral.sh/uv/)
- [PEP 735 - Dependency Groups](https://peps.python.org/pep-0735/)
- [Project pyproject.toml](/pyproject.toml)
- [CI Workflow](/github/workflows/ci.yml)
- [Testing Guide](/docs/TESTING_GUIDE.md)

---

## Summary

1. **Install uv** once: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Sync dependencies**: `uv sync --extra dev` (or `--group <name>`)
3. **Run commands**: `uv run pytest`, `uv run ruff check`
4. **Add packages**: `uv add <package>` or `uv add --dev <package>`
5. **Update lock**: `uv lock` after editing pyproject.toml
6. **CI uses pinned version**: Check `UV_VERSION` in workflows

For questions or issues, see the [Troubleshooting](#troubleshooting) section or check the [Astral documentation](https://docs.astral.sh/uv/).
