# Developer Documentation - Agent Guide

## Purpose

This directory contains developer-focused documentation for the Home Security Intelligence project. It is part of the hub-and-spoke documentation architecture, with [developer/README.md](README.md) as the central hub.

It is also the home of the contribution and process guides: development setup, coding patterns, testing strategies, git safety, CI/CD, and contribution guidelines. The workflow guides that used to live in `docs/development/` now live here, at the root of this directory; `docs/development/` retains only redirect stubs.

## Target Audience

- Software developers contributing to the project
- Engineers extending the system with new features
- Technical team members debugging or reviewing code

| Audience             | Needs                                  | Primary Documents                           |
| -------------------- | -------------------------------------- | ------------------------------------------- |
| **New Contributors** | Getting started, understanding project | `local-setup.md`, `contributing/README.md`  |
| **Developers**       | Coding patterns, testing               | `patterns-and-conventions.md`, `testing.md` |
| **Reviewers**        | Code review guidelines                 | `contributing/README.md`                    |

## Directory Contents

```
developer/
  AGENTS.md                       # This file
  README.md                       # Developer documentation hub and index
  # --- workflow and process guides (moved from docs/development/) ---
  AGENT_COORDINATION.md           # Parallel agent coordination protocol
  PORT_STANDARDIZATION.md         # Port standardization reference
  api-breaking-change-detection.md # API breaking change detection guide
  buildkit-secrets.md             # BuildKit secrets for Docker builds
  ci-cd.md                        # CI/CD pipeline configuration and workflows
  code-quality.md                 # Code quality tooling and standards
  docs-maintenance.md             # Documentation drift detection system
  fast-confidence-loop-measurements.md # Fast confidence loop measurements record
  flaky-test-detection.md         # Flaky test detection and remediation
  git-workflow.md                 # Git safety protocols and pre-commit rules
  git-worktree-workflow.md        # Git worktree patterns for parallel development
  health-monitoring-di.md         # Health monitoring dependency injection patterns
  hooks.md                        # Git hooks configuration
  linear-integration.md           # Linear MCP tools and workflow states
  llm-inference-optimization.md   # Nemotron LLM inference performance
  metrics-implementation-status.md # Metrics implementation tracking
  migration-rollback.md           # Database migration rollback procedures
  model-testing.md                # AI model testing and validation guide
  moe-offloading.md               # MoE-aware tensor offloading for Nemotron
  multi-gpu.md                    # Multi-GPU support and configuration guide
  nemo-data-designer.md           # NeMo Data Designer integration for synthetic data
  nemotron-buildkit-secrets.md    # Nemotron BuildKit secrets guide
  nemotron-prompting.md           # Nemotron prompting strategies and patterns
  patterns-and-conventions.md                     # Code patterns and conventions
  prompt-evaluation-results.md    # Prompt evaluation results and analysis
  python-3.14-features.md         # Python 3.14 features used in project
  selector-evaluation.md          # Test-selector evaluation (fast_select vs testmon)
  ssl-https.md                    # SSL/HTTPS configuration for development
  synthetic-data-quality.md       # Synthetic data quality metrics
  test-coverage.md                # Coverage reporting and analysis
  testing.md                      # Testing guide
  testing-workflow.md             # TDD workflow and test patterns by layer
  validation-alignment.md         # Frontend/backend validation alignment guide
  # --- reference and implementation spokes ---
  accessibility.md                # WCAG compliance, ARIA patterns, a11y testing
  alerts.md                       # Alert system for developers
  backend-patterns.md             # Repository pattern, Result type, RFC 7807 errors
  batching-logic.md               # Batch aggregation details
  clip-generation.md              # Event video clips, FFmpeg integration, API endpoints
  codebase-tour.md                # Directory structure and key file navigation
  data-model.md                   # Database schema for developers
  detection-service.md            # Detection service details
  entity-tracking.md              # Re-identification, CLIP embeddings, cross-camera matching
  keyboard-patterns.md            # Keyboard shortcuts and command palette
  local-setup.md                  # Development environment setup
  pipeline-overview.md            # AI pipeline for developers
  prompt-management.md            # Prompt template management and versioning
  pwa-implementation.md           # PWA features, push notifications, offline caching
  redis-key-conventions.md        # Redis key naming patterns and best practices
  resilience-patterns.md          # Circuit breakers, retries, prompt injection prevention
  risk-analysis.md                # Risk analysis service details
  ux-patterns.md                  # Toast notifications, page transitions, skeleton loaders
  video.md                        # Video processing details
  visualization-components.md     # Dashboard visualization component patterns
  # --- subdirectories, each with its own AGENTS.md ---
  api/                            # REST/WebSocket API reference
  architecture/                   # Developer-facing architecture guides
  contributing/                   # Contributor workflow (README.md is the guide)
  patterns/                       # Patterns & testing deep dives
```

## Key Files

### Reference and implementation guides

| File                          | Purpose                                           |
| ----------------------------- | ------------------------------------------------- |
| `local-setup.md`              | Development environment setup                     |
| `codebase-tour.md`            | Directory structure and key file navigation       |
| `keyboard-patterns.md`        | Keyboard shortcuts and command palette patterns   |
| `accessibility.md`            | WCAG compliance, ARIA patterns, a11y testing      |
| `backend-patterns.md`         | Repository pattern, Result types, RFC 7807 errors |
| `pwa-implementation.md`       | PWA manifest, push notifications, offline caching |
| `ux-patterns.md`              | Toast notifications, page transitions, skeletons  |
| `resilience-patterns.md`      | Circuit breakers, retry logic, prompt injection   |
| `alerts.md`                   | Alert system implementation for developers        |
| `batching-logic.md`           | Batch aggregation timing and logic                |
| `clip-generation.md`          | Event video clips, FFmpeg integration, API        |
| `data-model.md`               | Database schema documentation                     |
| `detection-service.md`        | Detection service implementation                  |
| `entity-tracking.md`          | Re-ID service, CLIP embeddings, entity APIs       |
| `pipeline-overview.md`        | AI pipeline overview for developers               |
| `risk-analysis.md`            | Risk analysis service implementation              |
| `video.md`                    | Video processing implementation                   |
| `redis-key-conventions.md`    | Redis key naming patterns and best practices      |
| `prompt-management.md`        | Prompt template management and versioning         |
| `visualization-components.md` | Dashboard visualization component patterns        |
| `README.md`                   | Developer documentation hub and index             |

### Workflow and process guides

| File                                   | Purpose                                                       |
| -------------------------------------- | ------------------------------------------------------------- |
| `AGENT_COORDINATION.md`                | Parallel agent coordination protocol                          |
| `api-breaking-change-detection.md`     | Detect and manage API breaking changes                        |
| `buildkit-secrets.md`                  | Docker BuildKit secrets for secure builds                     |
| `ci-cd.md`                             | CI/CD pipeline configuration and workflows                    |
| `code-quality.md`                      | Code quality tooling and standards                            |
| `contributing/README.md`               | Contribution guidelines and PR workflow                       |
| `docs-maintenance.md`                  | Automated documentation drift detection system                |
| `fast-confidence-loop-measurements.md` | Fast confidence loop measurement records                      |
| `flaky-test-detection.md`              | Detecting and fixing flaky tests                              |
| `git-workflow.md`                      | Git safety protocols, pre-commit rules, NEVER DISABLE TESTING |
| `git-worktree-workflow.md`             | Git worktree patterns for parallel development                |
| `health-monitoring-di.md`              | Health monitoring dependency injection patterns               |
| `hooks.md`                             | Git hooks configuration and troubleshooting                   |
| `linear-integration.md`                | Linear MCP tools, workflow state UUIDs, usage examples        |
| `llm-inference-optimization.md`        | Nemotron LLM inference configuration and performance          |
| `metrics-implementation-status.md`     | Metrics implementation status for Grafana dashboards          |
| `migration-rollback.md`                | Database migration rollback procedures                        |
| `model-testing.md`                     | Testing strategies for AI model integrations                  |
| `moe-offloading.md`                    | MoE-aware tensor offloading for Nemotron                      |
| `multi-gpu.md`                         | Multi-GPU support and configuration guide                     |
| `nemo-data-designer.md`                | NeMo Data Designer integration for synthetic test data        |
| `nemotron-buildkit-secrets.md`         | Nemotron-specific BuildKit secrets configuration              |
| `nemotron-prompting.md`                | Nemotron prompting strategies and best practices              |
| `patterns-and-conventions.md`          | Code patterns and conventions used in the project             |
| `PORT_STANDARDIZATION.md`              | Port standardization reference for all services               |
| `prompt-evaluation-results.md`         | Prompt evaluation results and analysis                        |
| `python-3.14-features.md`              | Python 3.14 features used in the project                      |
| `selector-evaluation.md`               | Test-selector evaluation (fast_select vs testmon)             |
| `ssl-https.md`                         | SSL/HTTPS configuration for development and production        |
| `synthetic-data-quality.md`            | Synthetic data quality metrics and validation                 |
| `test-coverage.md`                     | Coverage reporting, analysis, and trend tracking              |
| `testing.md`                           | Comprehensive testing guide                                   |
| `testing-workflow.md`                  | TDD workflow with the RED-GREEN-REFACTOR cycle                |
| `validation-alignment.md`              | Frontend/backend validation alignment guide                   |

### Subdirectories

| Directory       | Contents                                                           |
| --------------- | ------------------------------------------------------------------ |
| `api/`          | REST and WebSocket API reference; see `api/AGENTS.md`              |
| `architecture/` | Developer-facing architecture guides; see `architecture/AGENTS.md` |
| `contributing/` | Contributor workflow and tool setup; see `contributing/AGENTS.md`  |
| `patterns/`     | Patterns and testing deep dives; see `patterns/AGENTS.md`          |

## Workflow Guide Details

Purpose, coverage, and triggers for the workflow guides in this directory.

### AGENT_COORDINATION.md

**Purpose:** Protocol for coordinating parallel Claude Code agents.

**Covers:** Pre-dispatch verification checklist; file scope declaration format; anti-patterns to avoid; when to use sequential vs parallel execution; post-completion verification; common coordination patterns; skills and tools for coordination; lessons from git history.

**When to use:** Before dispatching parallel agents, during multi-agent sessions, after parallel work completes.

### api-breaking-change-detection.md

**Purpose:** Detect and manage API breaking changes.

**Covers:** Breaking change detection workflow; OpenAPI diff tooling; CI integration for API contracts; migration strategies.

**When to use:** Making API changes, reviewing PRs with endpoint changes.

### buildkit-secrets.md

**Purpose:** Docker BuildKit secrets for secure builds.

**Covers:** BuildKit secrets syntax; secret mounting patterns; CI/CD secret injection.

**When to use:** Configuring Docker builds with secrets.

### ci-cd.md

**Purpose:** CI/CD pipeline configuration and workflows.

### code-quality.md

**Purpose:** Code quality tooling and standards.

**Covers:** Linting and formatting (ruff, eslint, prettier); static analysis (mypy, TypeScript); dead code detection (vulture, knip); complexity analysis (radon); security scanning (semgrep, hadolint); API coverage checking.

**When to use:** Understanding code quality tools, running quality checks locally.

### contributing/README.md

**Purpose:** Guide for contributing to the project. (Absorbs the former `docs/development/contributing.md`.)

**Covers:** Code of conduct; how to submit issues; pull request process; code review guidelines; commit message conventions; branch naming conventions; issue tracking in Linear; test commands and validation before PR; git safety; file organization; security guidelines.

**When to use:** Before making your first contribution, understanding project workflow, preparing a PR for review.

### docs-maintenance.md

**Purpose:** Automated documentation drift detection system.

**Covers:** System overview and design principles; detection workflow (analysis, task creation, PR comments); rule configuration in `docs-drift-rules.yml`; rule format and template variables; handling generated Linear tasks; manual usage and local testing; CI/CD integration; troubleshooting common issues.

**When to use:** Understanding how docs drift detection works, adding new detection rules, handling documentation debt tasks.

### fast-confidence-loop-measurements.md

**Purpose:** Measurements record for the fast confidence loop; every row carries its measurement box and rows are never compared across boxes silently.

**When to use:** Reading or extending fast-loop baseline numbers.

### flaky-test-detection.md

**Purpose:** Detecting and fixing flaky tests.

**Covers:** Flaky test identification; root cause analysis; remediation strategies; CI integration.

**When to use:** Debugging intermittent test failures.

### git-workflow.md

**Purpose:** Git safety protocols, pre-commit rules, and the NEVER DISABLE TESTING policy.

**Covers:** Git safety protocol and forbidden commands; test strategy (pre-commit, pre-push, CI); NEVER DISABLE TESTING absolute rule; required hooks that must remain active; pre-commit setup instructions; emergency hook skip procedures.

**When to use:** Understanding git workflow rules, setting up pre-commit hooks, troubleshooting hook issues.

### git-worktree-workflow.md

**Purpose:** Git worktree patterns for parallel development.

**Covers:** Creating and managing git worktrees; parallel development workflows; worktree cleanup and maintenance; integration with claude-squad.

**When to use:** Setting up parallel development environments, working on multiple branches simultaneously.

### health-monitoring-di.md

**Purpose:** Health monitoring dependency injection patterns.

**Covers:** Health check service architecture; dependency injection patterns; service health status tracking; integration with monitoring systems.

**When to use:** Implementing health checks, understanding DI patterns for monitoring.

### hooks.md

**Purpose:** Git hooks configuration and troubleshooting.

**Covers:** Pre-commit hook setup; pre-push hook setup; available hooks and their purposes; troubleshooting hook failures; skipping hooks (when appropriate).

**When to use:** Setting up development environment, troubleshooting pre-commit issues.

### linear-integration.md

**Purpose:** Linear MCP tools, workflow state UUIDs, and usage examples.

**Covers:** Linear MCP tools reference table; workflow state UUIDs for the NEM team; usage examples for listing, getting, creating, and updating issues; querying workflow states via GraphQL API.

**When to use:** Working with Linear issues, updating issue status, creating new issues.

### llm-inference-optimization.md

**Purpose:** Current Nemotron LLM inference configuration, recent performance optimizations, observed characteristics, known limitations, and recommended next steps.

### local-setup.md

**Purpose:** Development environment setup guide. (Absorbs the former `docs/development/setup.md`.)

**Covers:** Prerequisites (Python, Node.js, Podman); repository setup; backend development setup; frontend development setup; AI services setup (optional); IDE configuration (VS Code, PyCharm).

**When to use:** Setting up a new development environment.

### metrics-implementation-status.md

**Purpose:** Tracks the implementation status of metrics referenced in Grafana dashboards.

### migration-rollback.md

**Purpose:** Database migration rollback procedures.

**Covers:** Rollback strategies and best practices; Alembic migration rollback commands; data migration considerations; troubleshooting failed migrations.

**When to use:** Rolling back database migrations, recovering from migration failures.

### model-testing.md

**Purpose:** Testing strategies for AI model integrations in the enrichment service.

**Covers:** Unit testing patterns for model loading, inference, and unloading; VRAM management and eviction testing; integration testing for enrichment endpoints; test fixtures and mocking strategies; benchmarking model performance; GPU testing patterns; troubleshooting common test failures.

**When to use:** Writing tests for AI models, testing model manager behavior, benchmarking inference performance.

### moe-offloading.md

**Purpose:** MoE offloading strategy for Nemotron-3-Nano-30B-A3B — selectively moves expert FFN weights to CPU RAM to free GPU VRAM with minimal performance impact.

### multi-gpu.md

**Purpose:** User guide for configuring multi-GPU support for AI services.

**Covers:** Feature overview and hardware requirements; accessing the GPU Settings page; understanding GPU cards and VRAM utilization; assignment strategies (Manual, VRAM-based, Latency-optimized, Isolation-first, Balanced); manual assignment and VRAM budget overrides; applying changes and restart flow; troubleshooting common issues; API reference for GPU configuration endpoints; FAQ.

**When to use:** Configuring multi-GPU setups, distributing AI workloads, troubleshooting GPU assignment issues.

### nemo-data-designer.md

**Purpose:** NeMo Data Designer integration for synthetic test data.

**Covers:** Synthetic scenario generation; ground truth validation; test fixture creation; prompt evaluation data.

**When to use:** Generating test data for AI pipelines.

### nemotron-buildkit-secrets.md

**Purpose:** Nemotron-specific BuildKit secrets configuration.

**Covers:** NGC API key handling; model download authentication; container build patterns.

**When to use:** Building Nemotron containers with authenticated model access.

### nemotron-prompting.md

**Purpose:** Nemotron prompting strategies and best practices.

**Covers:** Prompt engineering patterns; risk assessment prompts; context enrichment; response parsing.

**When to use:** Developing or tuning Nemotron prompts.

### patterns-and-conventions.md

**Purpose:** Code patterns and conventions used in the project.

**Covers:** Project structure and organization; backend patterns (FastAPI, SQLAlchemy, async patterns); frontend patterns (React, hooks, state management); error handling conventions; logging conventions; testing patterns.

**When to use:** Writing new code, understanding existing code patterns. See `patterns/` for focused deep dives (frontend patterns, form validation, mutation testing, test performance).

### PORT_STANDARDIZATION.md

**Purpose:** Port standardization reference for all services.

**Covers:** Service port assignments; port conflict resolution; development vs production ports.

**When to use:** Configuring service ports, debugging connection issues.

### prompt-evaluation-results.md

**Purpose:** Prompt evaluation results and analysis.

**Covers:** Evaluation metrics; benchmark results; improvement tracking.

**When to use:** Analyzing prompt performance.

### python-3.14-features.md

**Purpose:** Python 3.14 features used in the project.

**Covers:** New language features; type system improvements; performance enhancements; migration notes.

**When to use:** Understanding Python 3.14 usage in codebase.

### selector-evaluation.md

**Purpose:** Completed evaluation of the `fast_select` and `testmon` test selectors (WP2.1), with the decision and its rationale recorded.

### ssl-https.md

**Purpose:** SSL/HTTPS configuration for development and production.

**Covers:** Certificate generation for development; Let's Encrypt for production; nginx SSL configuration; TLS protocol and cipher settings; HSTS configuration.

**When to use:** Enabling HTTPS, configuring SSL certificates.

### synthetic-data-quality.md

**Purpose:** Synthetic data quality metrics and validation.

**Covers:** Quality metrics; validation workflows; data diversity analysis.

**When to use:** Evaluating synthetic test data quality.

### test-coverage.md

**Purpose:** Coverage reporting, analysis, and trend tracking.

**Covers:** Coverage thresholds (80% combined absolute floor; unit 84 / integration 37 CI tier floors; PR diff baseline 85 relative; 90% critical paths); coverage tools (pytest-cov, Codecov, coverage-analysis.py); per-module coverage analysis; trend tracking and regression detection; strategies for improving coverage; CI integration.

**When to use:** Understanding coverage requirements, analyzing coverage gaps, tracking coverage trends.

### testing.md

**Purpose:** Comprehensive testing guide.

**Covers:** Testing philosophy (TDD approach); backend testing with pytest; frontend testing with Vitest; E2E testing; mocking strategies; test coverage requirements (80% combined absolute floor — tier floors and diff baseline in `test-coverage.md`); running tests locally; CI test pipeline.

**When to use:** Writing tests, understanding testing requirements.

### testing-workflow.md

**Purpose:** TDD workflow guide with the RED-GREEN-REFACTOR cycle and test patterns.

**Covers:** TDD cycle: RED-GREEN-REFACTOR; pre-implementation checklist; test patterns by layer (API routes, services, components, E2E); using the TDD skill; integration with Linear TDD-labeled issues; PR checklist for TDD verification.

**When to use:** Following TDD practices, writing tests before implementation, understanding test patterns.

### validation-alignment.md

**Purpose:** Frontend/backend validation alignment guide.

**Covers:** Pydantic schema patterns; Zod schema alignment; validation consistency checks; error message standardization.

**When to use:** Ensuring frontend and backend validation rules are consistent.

## Development Workflow

### Getting Started

1. Read [local-setup.md](local-setup.md) for environment setup
2. Read [contributing/README.md](contributing/README.md) for workflow guidelines
3. Read [patterns-and-conventions.md](patterns-and-conventions.md) for coding conventions
4. Read [testing.md](testing.md) for testing requirements

### Making Changes

1. Create a feature branch from `main`
2. Write tests first (TDD approach) — see [testing-workflow.md](testing-workflow.md)
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

See [hooks.md](hooks.md) for setup and troubleshooting, and [git-workflow.md](git-workflow.md) for the NEVER DISABLE TESTING rule and the hooks that must stay active.

## Related Documentation

Cross-area documentation that this directory links to rather than duplicates:

| Topic          | Existing Location                     | Notes                  |
| -------------- | ------------------------------------- | ---------------------- |
| Architecture   | `docs/architecture/overview.md`       | System design          |
| Data Model     | `docs/architecture/data-model.md`     | Database schemas       |
| AI Pipeline    | `docs/architecture/ai-pipeline.md`    | Detection flow         |
| Real-time      | `docs/architecture/real-time.md`      | WebSocket architecture |
| Frontend Hooks | `docs/architecture/frontend-hooks.md` | React custom hooks     |
| Decisions      | `docs/architecture/decisions.md`      | ADRs                   |

Testing, contributing, code patterns, and coverage now live in this directory (`testing.md`, `contributing/README.md`, `patterns-and-conventions.md`, `test-coverage.md`) rather than in `docs/development/`.

Directory instruction files:

- **docs/AGENTS.md:** Documentation directory overview
- **AGENTS.md:** Root instruction file (single root file; loaded by Claude Code and other agents)
- **backend/AGENTS.md:** Backend architecture overview
- **frontend/AGENTS.md:** Frontend architecture overview

## Navigation

Start at [Developer Hub](README.md) for the complete developer documentation index.

## Document Standards

All spoke documents in this directory should follow the template:

```markdown
# [Topic Title]

> One-sentence summary.

**Time to read:** ~X min
**Prerequisites:** [Link] or "None"

---

[Content]

---

## Next Steps

- [Related Doc](README.md)

---

[Back to Developer Hub](README.md)
```
