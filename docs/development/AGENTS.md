# Development Directory - Agent Guide

## Purpose

This directory contains developer documentation for contributing to the Home Security Intelligence system. These guides cover development setup, coding patterns, testing strategies, and contribution guidelines.

## Directory Contents

```
development/
  AGENTS.md                       # This file
  AGENT_COORDINATION.md           # Parallel agent coordination protocol
  api-breaking-change-detection.md # API breaking change detection guide
  buildkit-secrets.md             # BuildKit secrets for Docker builds
  code-quality.md                 # Code quality tooling and standards
  contributing.md                 # Contribution guidelines
  coverage.md                     # Coverage reporting and analysis
  docs-maintenance.md             # Documentation drift detection system
  end-to-end-development-metrics.md # Development metrics tracking
  flaky-test-detection.md         # Flaky test detection and remediation
  git-workflow.md                 # Git safety protocols and pre-commit rules
  git-worktree-workflow.md        # Git worktree patterns for parallel development
  health-monitoring-di.md         # Health monitoring dependency injection patterns
  hooks.md                        # Git hooks configuration
  linear-integration.md           # Linear MCP tools and workflow states
  migration-rollback.md           # Database migration rollback procedures
  model-testing.md                # AI model testing and validation guide
  multi-gpu.md                    # Multi-GPU support and configuration guide
  nemo-data-designer.md           # NeMo Data Designer integration for synthetic data
  nemotron-buildkit-secrets.md    # Nemotron BuildKit secrets guide
  nemotron-prompting.md           # Nemotron prompting strategies and patterns
  patterns.md                     # Code patterns and conventions
  PORT_STANDARDIZATION.md         # Port standardization reference
  prompt-evaluation-results.md    # Prompt evaluation results and analysis
  python-3.14-features.md         # Python 3.14 features used in project
  setup.md                        # Development environment setup
  ssl-https.md                    # SSL/HTTPS configuration for development
  synthetic-data-quality.md       # Synthetic data quality metrics
  testing.md                      # Testing guide
  testing-workflow.md             # TDD workflow and test patterns by layer
  validation-alignment.md         # Frontend/backend validation alignment guide
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

### docs-maintenance.md

**Purpose:** Automated documentation drift detection system.

**Topics Covered:**

- System overview and design principles
- Detection workflow (analysis, task creation, PR comments)
- Rule configuration in `docs-drift-rules.yml`
- Rule format and template variables
- Handling generated Linear tasks
- Manual usage and local testing
- CI/CD integration
- Troubleshooting common issues

**When to use:** Understanding how docs drift detection works, adding new detection rules, handling documentation debt tasks.

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

### git-worktree-workflow.md

**Purpose:** Git worktree patterns for parallel development.

**Topics Covered:**

- Creating and managing git worktrees
- Parallel development workflows
- Worktree cleanup and maintenance
- Integration with claude-squad

**When to use:** Setting up parallel development environments, working on multiple branches simultaneously.

### health-monitoring-di.md

**Purpose:** Health monitoring dependency injection patterns.

**Topics Covered:**

- Health check service architecture
- Dependency injection patterns
- Service health status tracking
- Integration with monitoring systems

**When to use:** Implementing health checks, understanding DI patterns for monitoring.

### linear-integration.md

**Purpose:** Linear MCP tools, workflow state UUIDs, and usage examples.

**Topics Covered:**

- Linear MCP tools reference table
- Workflow state UUIDs for the NEM team
- Usage examples for listing, getting, creating, and updating issues
- Querying workflow states via GraphQL API

**When to use:** Working with Linear issues, updating issue status, creating new issues.

### migration-rollback.md

**Purpose:** Database migration rollback procedures.

**Topics Covered:**

- Rollback strategies and best practices
- Alembic migration rollback commands
- Data migration considerations
- Troubleshooting failed migrations

**When to use:** Rolling back database migrations, recovering from migration failures.

### model-testing.md

**Purpose:** Testing strategies for AI model integrations in the enrichment service.

**Topics Covered:**

- Unit testing patterns for model loading, inference, and unloading
- VRAM management and eviction testing
- Integration testing for enrichment endpoints
- Test fixtures and mocking strategies
- Benchmarking model performance
- GPU testing patterns
- Troubleshooting common test failures

**When to use:** Writing tests for AI models, testing model manager behavior, benchmarking inference performance.

### multi-gpu.md

**Purpose:** User guide for configuring multi-GPU support for AI services.

**Topics Covered:**

- Feature overview and hardware requirements
- Accessing the GPU Settings page
- Understanding GPU cards and VRAM utilization
- Assignment strategies (Manual, VRAM-based, Latency-optimized, Isolation-first, Balanced)
- Manual assignment and VRAM budget overrides
- Applying changes and restart flow
- Troubleshooting common issues
- API reference for GPU configuration endpoints
- FAQ

**When to use:** Configuring multi-GPU setups, distributing AI workloads, troubleshooting GPU assignment issues.

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

### ssl-https.md

**Purpose:** SSL/HTTPS configuration for development and production.

**Topics Covered:**

- Certificate generation for development
- Let's Encrypt for production
- nginx SSL configuration
- TLS protocol and cipher settings
- HSTS configuration

**When to use:** Enabling HTTPS, configuring SSL certificates.

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

### api-breaking-change-detection.md

**Purpose:** Detect and manage API breaking changes.

**Topics Covered:**

- Breaking change detection workflow
- OpenAPI diff tooling
- CI integration for API contracts
- Migration strategies

**When to use:** Making API changes, reviewing PRs with endpoint changes.

### buildkit-secrets.md

**Purpose:** Docker BuildKit secrets for secure builds.

**Topics Covered:**

- BuildKit secrets syntax
- Secret mounting patterns
- CI/CD secret injection

**When to use:** Configuring Docker builds with secrets.

### end-to-end-development-metrics.md

**Purpose:** Development metrics tracking and analysis.

**Topics Covered:**

- Metrics collection
- Performance tracking
- Development cycle analysis

**When to use:** Analyzing development workflow efficiency.

### flaky-test-detection.md

**Purpose:** Detecting and fixing flaky tests.

**Topics Covered:**

- Flaky test identification
- Root cause analysis
- Remediation strategies
- CI integration

**When to use:** Debugging intermittent test failures.

### nemo-data-designer.md

**Purpose:** NeMo Data Designer integration for synthetic test data.

**Topics Covered:**

- Synthetic scenario generation
- Ground truth validation
- Test fixture creation
- Prompt evaluation data

**When to use:** Generating test data for AI pipelines.

### nemotron-buildkit-secrets.md

**Purpose:** Nemotron-specific BuildKit secrets configuration.

**Topics Covered:**

- NGC API key handling
- Model download authentication
- Container build patterns

**When to use:** Building Nemotron containers with authenticated model access.

### nemotron-prompting.md

**Purpose:** Nemotron prompting strategies and best practices.

**Topics Covered:**

- Prompt engineering patterns
- Risk assessment prompts
- Context enrichment
- Response parsing

**When to use:** Developing or tuning Nemotron prompts.

### PORT_STANDARDIZATION.md

**Purpose:** Port standardization reference for all services.

**Topics Covered:**

- Service port assignments
- Port conflict resolution
- Development vs production ports

**When to use:** Configuring service ports, debugging connection issues.

### prompt-evaluation-results.md

**Purpose:** Prompt evaluation results and analysis.

**Topics Covered:**

- Evaluation metrics
- Benchmark results
- Improvement tracking

**When to use:** Analyzing prompt performance.

### python-3.14-features.md

**Purpose:** Python 3.14 features used in the project.

**Topics Covered:**

- New language features
- Type system improvements
- Performance enhancements
- Migration notes

**When to use:** Understanding Python 3.14 usage in codebase.

### synthetic-data-quality.md

**Purpose:** Synthetic data quality metrics and validation.

**Topics Covered:**

- Quality metrics
- Validation workflows
- Data diversity analysis

**When to use:** Evaluating synthetic test data quality.

### validation-alignment.md

**Purpose:** Frontend/backend validation alignment guide.

**Topics Covered:**

- Pydantic schema patterns
- Zod schema alignment
- Validation consistency checks
- Error message standardization

**When to use:** Ensuring frontend and backend validation rules are consistent.

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
