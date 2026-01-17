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
  coverage.md            # Coverage reporting and analysis
  git-workflow.md        # Git safety protocols and pre-commit rules
  git-worktree-workflow.md # Git worktree patterns for parallel development
  health-monitoring-di.md # Health monitoring dependency injection patterns
  hooks.md               # Git hooks configuration
  linear-integration.md  # Linear MCP tools and workflow states
  migration-rollback.md  # Database migration rollback procedures
  patterns.md            # Code patterns and conventions
  setup.md               # Development environment setup
  ssl-https.md           # SSL/HTTPS configuration for development
  testing.md             # Testing guide
  testing-workflow.md    # TDD workflow and test patterns by layer
  validation-alignment.md # Frontend/backend validation alignment guide
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

### coverage.md

**Purpose:** Coverage reporting, analysis, and trend tracking.

**Topics Covered:**

- Coverage thresholds (85% unit, 95% combined, 90% critical)
- Coverage tools (pytest-cov, Codecov, coverage-analysis.py)
- Per-module coverage analysis
- Trend tracking and regression detection
- Strategies for improving coverage
- CI integration

**When to use:** Understanding coverage requirements, analyzing coverage gaps, tracking coverage trends.

### git-workflow.md

**Purpose:** Git safety protocols, pre-commit rules, and the NEVER DISABLE TESTING policy.

**Topics Covered:**

- Git safety protocol and forbidden commands
- Test strategy (pre-commit, pre-push, CI)
- NEVER DISABLE TESTING absolute rule
- Required hooks that must remain active
- Pre-commit setup instructions
- Emergency hook skip procedures

**When to use:** Understanding git workflow rules, setting up pre-commit hooks, troubleshooting hook issues.

### linear-integration.md

**Purpose:** Linear MCP tools, workflow state UUIDs, and usage examples.

**Topics Covered:**

- Linear MCP tools reference table
- Workflow state UUIDs for the NEM team
- Usage examples for listing, getting, creating, and updating issues
- Querying workflow states via GraphQL API

**When to use:** Working with Linear issues, updating issue status, creating new issues.

### testing-workflow.md

**Purpose:** TDD workflow guide with the RED-GREEN-REFACTOR cycle and test patterns.

**Topics Covered:**

- TDD cycle: RED-GREEN-REFACTOR
- Pre-implementation checklist
- Test patterns by layer (API routes, services, components, E2E)
- Using the TDD skill
- Integration with Linear TDD-labeled issues
- PR checklist for TDD verification

**When to use:** Following TDD practices, writing tests before implementation, understanding test patterns.

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
