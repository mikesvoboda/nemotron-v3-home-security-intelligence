# Development Directory - Agent Guide

## Purpose

This directory contains developer documentation for contributing to the Home Security Intelligence system. These guides cover development setup, coding patterns, testing strategies, and contribution guidelines.

## Directory Contents

```
development/
  AGENTS.md              # This file
  AGENT_COORDINATION.md  # Parallel agent coordination protocol
  code-quality.md        # Code quality tooling and standards
  contributing.md        # Contribution guidelines
  hooks.md               # Git hooks configuration
  patterns.md            # Code patterns and conventions
  setup.md               # Development environment setup
  testing.md             # Testing guide
```

## Key Files

### AGENT_COORDINATION.md

**Purpose:** Protocol for coordinating parallel Claude Code agents.

**Topics Covered:**

- Pre-dispatch verification checklist
- File scope declaration format
- Anti-patterns to avoid
- When to use sequential vs parallel execution
- Post-completion verification
- Common coordination patterns
- Skills and tools for coordination
- Lessons from git history

**When to use:** Before dispatching parallel agents, during multi-agent sessions, after parallel work completes.

### code-quality.md

**Purpose:** Code quality tooling and standards.

**Topics Covered:**

- Linting and formatting (ruff, eslint, prettier)
- Static analysis (mypy, TypeScript)
- Dead code detection (vulture, knip)
- Complexity analysis (radon)
- Security scanning (semgrep, hadolint)
- API coverage checking

**When to use:** Understanding code quality tools, running quality checks locally.

### contributing.md

**Purpose:** Guide for contributing to the project.

**Topics Covered:**

- Code of conduct
- How to submit issues
- Pull request process
- Code review guidelines
- Commit message conventions
- Branch naming conventions

**When to use:** Before making your first contribution, understanding project workflow.

### hooks.md

**Purpose:** Git hooks configuration and troubleshooting.

**Topics Covered:**

- Pre-commit hook setup
- Pre-push hook setup
- Available hooks and their purposes
- Troubleshooting hook failures
- Skipping hooks (when appropriate)

**When to use:** Setting up development environment, troubleshooting pre-commit issues.

### patterns.md

**Purpose:** Code patterns and conventions used in the project.

**Topics Covered:**

- Project structure and organization
- Backend patterns (FastAPI, SQLAlchemy, async patterns)
- Frontend patterns (React, hooks, state management)
- Error handling conventions
- Logging conventions
- Testing patterns

**When to use:** Writing new code, understanding existing code patterns.

### setup.md

**Purpose:** Development environment setup guide.

**Topics Covered:**

- Prerequisites (Python, Node.js, Podman)
- Repository setup
- Backend development setup
- Frontend development setup
- AI services setup (optional)
- IDE configuration (VS Code, PyCharm)

**When to use:** Setting up a new development environment.

### testing.md

**Purpose:** Comprehensive testing guide.

**Topics Covered:**

- Testing philosophy (TDD approach)
- Backend testing with pytest
- Frontend testing with Vitest
- E2E testing
- Mocking strategies
- Test coverage requirements (85% unit, 95% combined backend)
- Running tests locally
- CI test pipeline

**When to use:** Writing tests, understanding testing requirements.

## Development Workflow

### Getting Started

1. Read `setup.md` for environment setup
2. Read `contributing.md` for workflow guidelines
3. Read `patterns.md` for coding conventions
4. Read `testing.md` for testing requirements

### Making Changes

1. Create a feature branch from `main`
2. Write tests first (TDD approach)
3. Implement the feature
4. Ensure all tests pass
5. Submit a pull request
6. Address code review feedback

### Pre-commit Hooks

The project uses pre-commit hooks for quality checks:

- `ruff check` - Python linting
- `ruff format` - Python formatting
- `mypy` - Python type checking
- `eslint` - TypeScript/JavaScript linting
- `prettier` - Code formatting

Run manually with:

```bash
pre-commit run --all-files
```

## Target Audience

| Audience             | Needs                                  | Primary Documents         |
| -------------------- | -------------------------------------- | ------------------------- |
| **New Contributors** | Getting started, understanding project | setup.md, contributing.md |
| **Developers**       | Coding patterns, testing               | patterns.md, testing.md   |
| **Reviewers**        | Code review guidelines                 | contributing.md           |

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/architecture/:** Technical architecture details
- **CLAUDE.md:** Claude Code instructions
- **backend/AGENTS.md:** Backend architecture overview
- **frontend/AGENTS.md:** Frontend architecture overview
