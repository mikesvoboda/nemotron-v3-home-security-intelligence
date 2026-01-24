# AGENTS.md Validator Design

**Date:** 2026-01-24
**Status:** Approved

## Problem Statement

This project uses the AGENTS.md framework with 204 documentation files across the codebase. These files serve as an index for AI agents to understand the codebase scope and integration points. However, as the codebase evolves, AGENTS.md files can become stale, leading to:

1. **Stale references** - AGENTS.md files reference files/functions that no longer exist
2. **Missing coverage** - New directories are added without corresponding AGENTS.md documentation
3. **Dead links** - Internal markdown links point to non-existent files or anchors

## Solution Overview

A Python-based validation system that:

- Runs in CI on every PR and push to main
- Detects documentation drift without blocking merges
- Creates/updates a rolling Linear task to track documentation debt
- Auto-closes the task when all issues are resolved

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI Pipeline                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ Other CI     │    │ agents-md    │    │ Linear API       │  │
│  │ Jobs         │    │ validator    │    │ (create/update)  │  │
│  │ (parallel)   │    │              │────▶│                  │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│                      ┌──────────────┐                           │
│                      │ CI Artifacts │                           │
│                      │ (report.json)│                           │
│                      └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Components

| Component                          | Purpose                                   |
| ---------------------------------- | ----------------------------------------- |
| `scripts/agents_md_validator.py`   | Core validation logic - finds issues      |
| `scripts/agents_md_linear_sync.py` | Linear integration - creates/updates task |
| `.agents-md-validator.yml`         | Configuration file                        |
| `.github/workflows/agents-md.yml`  | CI workflow                               |

## Validation Checks

### Check 1: File Reference Validation

Scans each AGENTS.md for paths that look like file references and verifies they exist.

**Patterns detected:**

- Backtick-wrapped paths: `` `backend/api/routes/foo.py` ``
- Directory references: `backend/api/routes/`
- Table cells with paths: `| config.py | Purpose |`

**Issue format:**

```json
{
  "type": "stale_reference",
  "agents_md": "backend/api/routes/AGENTS.md",
  "line": 45,
  "reference": "prompt_management.py",
  "resolved_path": "backend/api/routes/prompt_management.py",
  "reason": "file_not_found"
}
```

### Check 2: Directory Coverage

Finds directories with code files but no AGENTS.md.

**Criteria for requiring AGENTS.md:**

- Contains `.py`, `.ts`, `.tsx`, `.js`, `.jsx` files
- Is not an excluded directory (e.g., `__pycache__`, `node_modules`)
- Has 2+ code files

**Issue format:**

```json
{
  "type": "missing_agents_md",
  "directory": "backend/services/new_feature/",
  "code_files": ["handler.py", "models.py", "utils.py"]
}
```

### Check 3: Dead Links

Validates internal markdown links.

**Patterns:**

- Relative links: `[Text](../other/AGENTS.md)`
- Local file links: `[Text](./file.py)`
- Anchor links: `[Text](#anchor)`

**Issue format:**

```json
{
  "type": "dead_link",
  "agents_md": "backend/AGENTS.md",
  "line": 23,
  "link": "../deprecated/AGENTS.md",
  "reason": "target_not_found"
}
```

## Linear Integration

### Rolling Task Strategy

A single Linear task tracks all AGENTS.md issues. The task is:

- **Created** when issues first appear
- **Updated** on each CI run with current issues
- **Auto-closed** when all issues are resolved

### Task Identification

```python
TASK_TITLE = "AGENTS.md Documentation Sync Required"
```

The sync script searches for an existing task with this exact title in non-closed states.

### Task Content Template

```markdown
## Summary

Automated scan found AGENTS.md documentation drift that needs attention.

## Issues Found

### Stale References (3)

| File                         | Line | Reference            | Reason         |
| ---------------------------- | ---- | -------------------- | -------------- |
| backend/api/routes/AGENTS.md | 45   | prompt_management.py | file_not_found |

### Missing AGENTS.md (1)

| Directory                     | Code Files            |
| ----------------------------- | --------------------- |
| backend/services/new_feature/ | handler.py, models.py |

### Dead Links (0)

None found.

---

_Last scanned: 2026-01-24 at commit abc1234_
_CI Run: [View](https://github.com/.../actions/runs/123)_
```

### Task Lifecycle

| Condition                      | Action                  |
| ------------------------------ | ----------------------- |
| Issues found, no existing task | Create task in Backlog  |
| Issues found, task exists      | Update task description |
| No issues, task exists         | Move task to Done       |
| No issues, no task             | No action               |

## CI Workflow

**File:** `.github/workflows/agents-md.yml`

```yaml
name: AGENTS.md Validation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate-agents-md:
    runs-on: ubuntu-latest
    continue-on-error: true

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Run AGENTS.md validator
        run: |
          python scripts/agents_md_validator.py \
            --output report.json \
            --format json

      - name: Upload report artifact
        uses: actions/upload-artifact@v4
        with:
          name: agents-md-report
          path: report.json

      - name: Sync to Linear (main branch only)
        if: github.ref == 'refs/heads/main'
        env:
          LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
        run: |
          python scripts/agents_md_linear_sync.py \
            --report report.json \
            --commit ${{ github.sha }}
```

**Key behaviors:**

- `continue-on-error: true` ensures it never blocks merges
- Linear sync only runs on main branch (avoids duplicate tasks from PRs)
- Report uploaded as artifact for debugging

## Configuration

**File:** `.agents-md-validator.yml`

```yaml
# Directories to skip entirely (no AGENTS.md required)
exclude_directories:
  - __pycache__
  - node_modules
  - .git
  - .venv
  - .pytest_cache
  - coverage
  - dist
  - build
  - .mypy_cache
  - .ruff_cache
  - mutants
  - '*.egg-info'

# Directories that intentionally have no AGENTS.md
no_agents_md_required:
  - certs/
  - data/
  - custom/clips/

# File extensions that count as "code files"
code_extensions:
  - .py
  - .ts
  - .tsx
  - .js
  - .jsx

# Minimum code files before requiring AGENTS.md
min_code_files: 2

# Linear configuration
linear:
  team_id: '998946a2-aa75-491b-a39d-189660131392'
  task_title: 'AGENTS.md Documentation Sync Required'
  labels:
    - 'documentation'
    - 'tech-debt'
```

### Inline Exclusions

AGENTS.md files can exclude specific references from validation:

```markdown
<!-- agents-md-validator: ignore-reference backend/deprecated/old.py -->
```

## Implementation Plan

### Files to Create

| File                                        | Purpose                   | ~Lines |
| ------------------------------------------- | ------------------------- | ------ |
| `scripts/agents_md_validator.py`            | Core validation logic     | ~300   |
| `scripts/agents_md_linear_sync.py`          | Linear task create/update | ~150   |
| `.agents-md-validator.yml`                  | Configuration             | ~40    |
| `.github/workflows/agents-md.yml`           | CI workflow               | ~50    |
| `scripts/tests/test_agents_md_validator.py` | Unit tests                | ~200   |

### Dependencies

No new dependencies required:

- `pyyaml` - config parsing (already in project)
- `requests` - Linear API calls (already available)

### Implementation Order

1. Create configuration file `.agents-md-validator.yml`
2. Implement `scripts/agents_md_validator.py` with all three checks
3. Add unit tests for validator logic
4. Implement `scripts/agents_md_linear_sync.py`
5. Create CI workflow `.github/workflows/agents-md.yml`
6. Add `LINEAR_API_KEY` to GitHub secrets
7. Run initial validation and create baseline task if needed

## Future Enhancements

**Pre-commit hook (optional):**
A local pre-commit hook could run the validator in warning mode, giving developers immediate feedback when editing near AGENTS.md files.

**Stale file list detection:**
A more sophisticated check could compare file lists in tables against actual directory contents. Deferred due to higher false-positive risk (AGENTS.md may intentionally document only key files).

## Decision Log

| Decision                      | Rationale                                                          |
| ----------------------------- | ------------------------------------------------------------------ |
| Soft gate (no merge blocking) | Maintains velocity; documentation debt is tracked, not enforced    |
| Rolling Linear task           | Prevents task spam; single source of truth for documentation debt  |
| Linear sync on main only      | Avoids duplicate tasks from PR branches                            |
| Python implementation         | Fits existing stack; easy to test and maintain                     |
| Skip stale file list check    | High false-positive risk; AGENTS.md may be intentionally selective |
