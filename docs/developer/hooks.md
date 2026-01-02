# Pre-commit Hooks

> Automated code quality enforcement - never commit broken code.

**Time to read:** ~5 min
**Prerequisites:** [Local Setup](local-setup.md)

---

## Overview

Pre-commit hooks run automatically on every `git commit` and `git push`. They catch issues before they enter the codebase.

**CRITICAL:** Never bypass hooks with `--no-verify`. Fix the issues instead.

## Installation

```bash
# pre-commit is included in dev dependencies
# Install with: uv sync --extra dev
source .venv/bin/activate

# Install hooks (run once per clone)
pre-commit install                     # For commit hooks
pre-commit install --hook-type pre-push  # For push hooks
```

## Hook Summary

| Hook                  | Stage      | Purpose                | Fix Command                       |
| --------------------- | ---------- | ---------------------- | --------------------------------- |
| `trailing-whitespace` | pre-commit | Remove trailing spaces | Automatic                         |
| `end-of-file-fixer`   | pre-commit | Ensure newline at EOF  | Automatic                         |
| `ruff`                | pre-commit | Python lint + format   | `ruff check --fix backend/`       |
| `mypy`                | pre-commit | Python type checking   | Fix type annotations              |
| `prettier`            | pre-commit | JS/TS formatting       | `cd frontend && npm run format`   |
| `eslint`              | pre-commit | JS/TS linting          | `cd frontend && npm run lint:fix` |
| `typescript-check`    | pre-commit | TypeScript compilation | Fix type errors                   |
| `fast-test`           | pre-push   | Run unit tests         | Fix failing tests                 |

## Pre-commit Hooks (on `git commit`)

### Ruff (Python Linting + Formatting)

```bash
# Manual check
ruff check backend/

# Auto-fix most issues
ruff check --fix backend/

# Format code
ruff format backend/
```

**Common issues:**

- Unused imports
- Line too long (>100 chars)
- Unsorted imports
- Missing whitespace

### MyPy (Python Type Checking)

```bash
# Manual check
mypy backend/
```

**Common issues:**

- Missing type annotations
- Incompatible types
- Missing return types

### ESLint (TypeScript Linting)

```bash
cd frontend

# Check
npm run lint

# Auto-fix
npm run lint:fix
```

### Prettier (Code Formatting)

```bash
cd frontend

# Check
npm run format:check

# Fix
npm run format
```

### TypeScript Compilation

```bash
cd frontend

# Check types
npx tsc --noEmit
```

## Pre-push Hooks (on `git push`)

### Fast Test (Unit Tests)

Runs unit tests before allowing push:

```bash
# What runs automatically
pytest backend/tests/unit/ -m "not slow" -q --tb=no -x

# Manual equivalent
pytest backend/tests/unit/ -v
```

**If tests fail:** Fix the failing tests before pushing. Do not skip with `--no-verify`.

## Running Hooks Manually

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff
pre-commit run mypy
pre-commit run eslint
```

## When Hooks Fail

1. **Read the error message** - It tells you what's wrong
2. **Run the fix command** - Most issues have auto-fixes
3. **Re-stage fixed files** - `git add .`
4. **Try commit again** - `git commit -m "..."`

### Example: Ruff Failure

```
ruff......................FAILED
- hook id: ruff
- exit code: 1

backend/api/routes/cameras.py:15:1: F401 [*] `os` imported but unused
```

**Fix:**

```bash
ruff check --fix backend/api/routes/cameras.py
git add backend/api/routes/cameras.py
git commit -m "fix: remove unused import"
```

### Example: TypeScript Failure

```
eslint.....................FAILED
- hook id: eslint

/frontend/src/hooks/useWebSocket.ts
  15:7  error  'data' is assigned a value but never used  @typescript-eslint/no-unused-vars
```

**Fix:**

```bash
cd frontend
npm run lint:fix
# Or manually fix if auto-fix doesn't work
git add src/hooks/useWebSocket.ts
git commit -m "fix: remove unused variable"
```

## Configuration Files

| File                      | Purpose                |
| ------------------------- | ---------------------- |
| `.pre-commit-config.yaml` | Hook definitions       |
| `pyproject.toml`          | Ruff and MyPy settings |
| `frontend/.eslintrc.cjs`  | ESLint rules           |
| `frontend/.prettierrc`    | Prettier settings      |

## Updating Hooks

```bash
# Update hook versions
pre-commit autoupdate

# Reinstall after changes
pre-commit install
pre-commit install --hook-type pre-push
```

---

## Never Bypass Hooks

The following commands are **forbidden**:

```bash
# DO NOT USE
git commit --no-verify
git push --no-verify
SKIP=hook-name git commit
```

If hooks fail, **fix the code**. The hooks exist to maintain code quality across the team.

---

## Next Steps

- [Local Setup](local-setup.md) - Development environment setup
- [Codebase Tour](codebase-tour.md) - Navigate the codebase

---

## See Also

- [CLAUDE.md](../../CLAUDE.md) - Project rules including hook enforcement
- [Glossary](../reference/glossary.md) - Terms and abbreviations

---

[Back to Developer Hub](../developer-hub.md)
