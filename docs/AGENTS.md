# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation including design specifications, implementation plans, setup guides, architecture decisions, reference materials, and visual assets. The documentation is organized into 18 subdirectories with AGENTS.md files, plus root-level guides for critical topics.

## Directory Structure

```
docs/
  AGENTS.md                       # This file - guide to documentation
  README.md                       # Documentation navigation hub
  ROADMAP.md                      # Post-MVP roadmap ideas
  TESTING_GUIDE.md                # Comprehensive testing patterns guide

  # Setup and Deployment
  AI_SETUP.md                     # AI services setup guide
  RUNTIME_CONFIG.md               # Authoritative port/env reference
  DOCKER_DEPLOYMENT.md            # Docker deployment guide
  DOCKER_SECRETS.md               # Docker secrets management
  DEPLOYMENT.md                   # Production deployment guide
  DEPLOYMENT_RUNBOOK.md           # Deployment operations runbook
  DEPLOYMENT_SAFETY_CHECKLIST.md  # Pre-deployment safety checklist
  DEPLOYMENT_TROUBLESHOOTING.md   # Deployment troubleshooting guide
  DEPLOYMENT_VERIFICATION_CHECKLIST.md  # Post-deployment verification
  HEALTH_CHECK_STRATEGY.md        # Health check design and patterns
  SERVICE_DEPENDENCIES.md         # Service dependency documentation
  SELF_HOSTED_RUNNER.md           # Self-hosted GPU runner setup guide

  # Development Tools
  CHROME_DEVTOOLS_MCP.md          # Chrome DevTools MCP server guide
  COPILOT_SETUP.md                # GitHub Copilot Free tier setup guide
  GITHUB_MODELS.md                # GitHub Models integration guide
  LINEAR_SETUP_PROMPT.md          # Linear issue tracking setup prompt
  LINEAR-GITHUB-INTEGRATION.md    # Linear-GitHub bi-directional sync
  MUTATION_TESTING.md             # Mutation testing guide (mutmut + Stryker)
  TEST_PERFORMANCE_METRICS.md     # Test suite performance metrics

  # API and Contracts
  API_COVERAGE.md                 # API coverage analysis
  WEBSOCKET_CONTRACTS.md          # WebSocket message contracts

  api/                            # API governance documentation
    AGENTS.md                     # API directory guide
    DEPRECATION_POLICY.md         # API deprecation process and timeline
    migrations/                   # Migration guides for deprecated endpoints
      README.md                   # Migration guide index

  # Security
  METRICS_ENDPOINT_HARDENING.md   # Metrics endpoint security hardening
  PEER_DEPS_CONFLICT.md           # NPM peer dependency conflict resolution
  SECURITY_API_KEYS.md            # API key security documentation
  SECURITY.md                     # Security policies and practices

  # Operations
  slo-definitions.md              # Service Level Objective definitions
  MODEL_LOADER_MIGRATION.md       # Model loader migration guide

  # Documentation Hubs
  developer-hub.md                # Developer documentation hub
  operator-hub.md                 # Operator documentation hub
  user-hub.md                     # User documentation hub

  admin-guide/                    # System administrator documentation
    AGENTS.md                     # Admin guide directory guide
    configuration.md              # System configuration guide
    monitoring.md                 # Monitoring and observability
    security.md                   # Security hardening guide
    storage-retention.md          # Data storage and retention policies
    troubleshooting.md            # Admin troubleshooting guide

  api-reference/                  # API documentation (canonical location)
    AGENTS.md                     # API reference directory guide
    overview.md                   # API overview
    ai-audit.md                   # AI audit API reference (626 lines)
    alerts.md                     # Alerts API reference
    audit.md                      # Audit logging API reference
    cameras.md                    # Cameras API reference
    detections.md                 # Detections API reference
    dlq.md                        # Dead Letter Queue API reference
    enrichment.md                 # Prompt enrichment API reference
    entities.md                   # Entity tracking API reference
    events.md                     # Events API reference (752 lines)
    logs.md                       # Logs API reference
    media.md                      # Media serving API reference
    model-zoo.md                  # Model Zoo API reference (634 lines)
    prompts.md                    # Prompt management API reference
    system.md                     # System API reference
    websocket.md                  # WebSocket API reference
    zones.md                      # Zones API reference

  architecture/                   # Technical architecture documentation
    AGENTS.md                     # Architecture directory guide
    overview.md                   # System architecture overview
    ai-pipeline.md                # AI processing pipeline details
    data-model.md                 # Database schema documentation
    decisions.md                  # Architecture decisions
    frontend-hooks.md             # Frontend React hooks documentation
    real-time.md                  # Real-time communication architecture
    resilience.md                 # Resilience patterns (1248 lines - comprehensive)
    system-page-pipeline-visualization.md  # System page pipeline viz (655 lines)

  benchmarks/                     # Performance benchmark results
    AGENTS.md                     # Benchmarks directory guide
    model-zoo-benchmark.md        # Model Zoo benchmark results

  decisions/                      # Architecture Decision Records (ADRs)
    AGENTS.md                     # Decisions directory guide
    grafana-integration.md        # Grafana integration decision

  developer/                      # Developer-focused documentation
    AGENTS.md                     # Developer directory guide
    alerts.md                     # Alert system for developers
    batching-logic.md             # Batch aggregation details
    codebase-tour.md              # Directory structure navigation
    data-model.md                 # Database schema for developers
    detection-service.md          # Detection service details
    hooks.md                      # Pre-commit hook documentation
    local-setup.md                # Development environment setup
    pipeline-overview.md          # AI pipeline for developers
    risk-analysis.md              # Risk analysis service details
    video.md                      # Video processing details

  development/                    # Development workflow documentation
    AGENTS.md                     # Development directory guide
    AGENT_COORDINATION.md         # Multi-agent coordination patterns
    code-quality.md               # Code quality tools and standards
    contributing.md               # Contribution guidelines
    coverage.md                   # Test coverage requirements
    git-worktree-workflow.md      # Git worktree workflow guide
    hooks.md                      # Git hooks documentation
    patterns.md                   # Code patterns and conventions
    setup.md                      # Development environment setup
    testing.md                    # Testing guide

  getting-started/                # Quick start guides
    AGENTS.md                     # Getting started directory guide
    first-run.md                  # First run guide
    installation.md               # Installation guide
    prerequisites.md              # System prerequisites
    upgrading.md                  # Upgrade guide

  images/                         # Visual assets
    AGENTS.md                     # Images directory guide
    SCREENSHOT_GUIDE.md           # Screenshot capture guidelines
    dashboard-mockup.svg          # Dashboard UI mockup (vector)
    dashboard.png                 # Dashboard screenshot
    dashboard-full.png            # Full dashboard screenshot
    timeline.png                  # Event timeline screenshot
    alerts.png                    # Alerts page screenshot

  testing/                        # Testing guides and patterns
    AGENTS.md                     # Testing directory guide
    TDD_WORKFLOW.md               # Test-Driven Development workflow
    TESTING_PATTERNS.md           # Common testing patterns
    HYPOTHESIS_GUIDE.md           # Property-based testing with Hypothesis

  operator/                       # Operator-focused documentation
    AGENTS.md                     # Operator directory guide
    ai-configuration.md           # AI model configuration
    ai-ghcr-deployment.md         # AI GHCR container deployment
    ai-installation.md            # AI service installation
    ai-overview.md                # AI services overview
    ai-performance.md             # AI performance tuning
    ai-services.md                # AI service management
    ai-tls.md                     # AI service TLS configuration
    ai-troubleshooting.md         # AI troubleshooting quick fixes
    backup.md                     # Backup and recovery
    database.md                   # Database management
    deployment-modes.md           # Deployment mode configurations
    gpu-setup.md                  # GPU and NVIDIA setup
    redis.md                      # Redis configuration and management

  plans/                          # Design and implementation plans
    AGENTS.md                     # Plans directory guide
    2024-12-21-dashboard-mvp-design.md
    2024-12-22-mvp-implementation-plan.md
    2024-12-24-logging-system-design.md
    2024-12-24-logging-implementation-plan.md
    2025-01-01-testing-reliability-design.md
    2025-12-26-github-cicd-design.md
    2025-12-26-github-cicd-implementation.md
    2025-12-26-readme-redesign.md
    2025-12-26-service-health-monitoring-design.md
    2025-12-28-documentation-design.md
    2025-12-30-ai-containerization-design.md
    2025-12-30-documentation-restructure-design.md
    2025-12-30-test-performance-implementation.md
    2025-12-30-test-performance-optimization-design.md
    2025-12-31-documentation-overhaul-design.md
    2025-12-31-system-performance-design.md
    2025-12-31-system-performance-plan.md
    2026-01-01-claude-code-tooling-design.md
    2026-01-01-prompt-enrichment-design.md
    2026-01-01-vision-extraction-design.md
    2026-01-02-ai-performance-audit-implementation.md
    2026-01-02-ai-performance-audit.md
    2026-01-02-interactive-setup-script-design.md
    2026-01-02-interactive-setup-script-implementation.md
    2026-01-03-websocket-deduplication-design.md
    2026-01-04-ai-audit-redesign.md
    2026-01-04-ai-performance-page-redesign.md
    2026-01-04-system-page-redesign.md
    2026-01-05-container-orchestrator-design.md
    2026-01-05-grafana-operations-dashboard-design.md
    2026-01-05-grafana-operations-dashboard-implementation.md
    2026-01-05-prompt-playground-apply-suggestion-design.md
    prompt-enrichment-tasks.md    # Prompt enrichment task list

  reference/                      # Authoritative reference documentation
    AGENTS.md                     # Reference directory guide
    glossary.md                   # Terms and definitions
    stability.md                  # API stability definitions
    api/                          # API endpoint reference
      AGENTS.md                   # API reference guide
      overview.md                 # API conventions
      alerts.md                   # Alert rules API
      cameras.md                  # Cameras API
      detections.md               # Detections API
      events.md                   # Events API
      system.md                   # System API
      websocket.md                # WebSocket API
    config/                       # Configuration reference
      AGENTS.md                   # Config reference guide
      env-reference.md            # Environment variables
      risk-levels.md              # Risk score definitions
    troubleshooting/              # Problem-solving guides
      AGENTS.md                   # Troubleshooting guide
      index.md                    # Symptom quick reference
      ai-issues.md                # AI troubleshooting
      connection-issues.md        # Network troubleshooting
      database-issues.md          # Database troubleshooting
      gpu-issues.md               # GPU troubleshooting

  user/                           # End-user documentation (hub-and-spoke)
    AGENTS.md                     # User directory guide
    ai-audit.md                   # AI audit trail viewer guide
    ai-enrichment.md              # AI enrichment features guide
    ai-performance.md             # AI performance monitoring guide
    dashboard-basics.md           # Dashboard layout and components
    dashboard-settings.md         # Settings configuration
    system-monitoring.md          # System monitoring page guide
    understanding-alerts.md       # Risk levels and responses
    viewing-events.md             # Event viewing and interaction

  user-guide/                     # End-user documentation (original)
    AGENTS.md                     # User guide directory guide
    getting-started.md            # New user onboarding
    understanding-alerts.md       # Risk levels and alerts
    using-the-dashboard.md        # Dashboard usage guide
    alerts-notifications.md       # Alerts and notifications
    dashboard-overview.md         # Dashboard overview
    event-timeline.md             # Event timeline guide
    logs-dashboard.md             # Logs dashboard guide
    search.md                     # Search functionality
    settings.md                   # Settings page guide
```

## Key Files

### Roadmap and Future Vision

**ROADMAP.md**

Post-MVP roadmap ideas organized into 8 themes:

1. **Alerting & escalation** - Notifications, rules, dedupe
2. **Spatial intelligence & zones** - Per-camera polygons, dwell time
3. **Entity continuity (ReID-lite)** - Track actors across detections
4. **Pattern-of-life / anomaly detection** - Learn normal patterns
5. **Search & investigations** - Full-text and semantic search
6. **Better media handling** - Clips, pre/post roll, scrubber UX
7. **Reliability & operations** - Backpressure, retries, observability
8. **Security hardening** - Auth, audit logging, rate limiting

**When to use:** After MVP is fully operational (Phases 1-8 complete)

### Configuration Reference

**RUNTIME_CONFIG.md**

- **Authoritative reference** for all environment variables and port assignments
- Service ports (Frontend, Backend, RT-DETRv2, Nemotron, Redis)
- Container vs host networking for Linux/macOS/Windows
- Database, Redis, and application settings
- AI model configuration

**When to use:** Setting up environment variables or debugging connectivity

### Setup and Deployment Guides

| File                                   | Purpose                                    | Key Sections                                                                |
| -------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------- |
| `AI_SETUP.md`                          | AI inference services setup                | Hardware requirements, model downloads, service management, troubleshooting |
| `DOCKER_DEPLOYMENT.md`                 | Docker Compose deployment                  | Quick start, configuration, health checks, volume management                |
| `DOCKER_SECRETS.md`                    | Docker secrets management                  | Secret creation, rotation, service integration                              |
| `DEPLOYMENT.md`                        | Production deployment guide                | Pre-deployment checks, rollout procedures, post-deployment                  |
| `DEPLOYMENT_RUNBOOK.md`                | Deployment operations runbook              | Step-by-step procedures, rollback, incident response                        |
| `DEPLOYMENT_SAFETY_CHECKLIST.md`       | Pre-deployment safety checklist            | Required verifications before deployment                                    |
| `DEPLOYMENT_TROUBLESHOOTING.md`        | Deployment troubleshooting guide           | Common issues, debugging steps, resolution                                  |
| `DEPLOYMENT_VERIFICATION_CHECKLIST.md` | Post-deployment verification               | Health checks, smoke tests, monitoring setup                                |
| `HEALTH_CHECK_STRATEGY.md`             | Health check design and patterns           | Liveness, readiness, dependency health                                      |
| `SERVICE_DEPENDENCIES.md`              | Service dependency documentation           | Startup order, connectivity requirements                                    |
| `SELF_HOSTED_RUNNER.md`                | Self-hosted GitHub Actions runner with GPU | Installation, security, maintenance                                         |
| `RUNTIME_CONFIG.md`                    | Authoritative port and environment config  | Service ports, environment variables, networking                            |
| `TEST_PERFORMANCE_METRICS.md`          | Test suite performance metrics             | Baselines, thresholds, CI timing, parallelization strategy                  |
| `TESTING_GUIDE.md`                     | Comprehensive testing patterns guide       | Fixtures, factories, test strategies, coverage                              |

### API and Contracts

| File                     | Purpose                     | Key Sections                            |
| ------------------------ | --------------------------- | --------------------------------------- |
| `API_COVERAGE.md`        | API coverage analysis       | Coverage metrics, uncovered endpoints   |
| `WEBSOCKET_CONTRACTS.md` | WebSocket message contracts | Message formats, channel specifications |

### Operations

| File                        | Purpose                             | Key Sections                         |
| --------------------------- | ----------------------------------- | ------------------------------------ |
| `slo-definitions.md`        | Service Level Objective definitions | SLOs, SLIs, error budgets            |
| `MODEL_LOADER_MIGRATION.md` | Model loader migration guide        | Migration steps, compatibility notes |

### Developer Tools

| File                           | Purpose                                   | Key Sections                                              |
| ------------------------------ | ----------------------------------------- | --------------------------------------------------------- |
| `CHROME_DEVTOOLS_MCP.md`       | Chrome DevTools MCP server for debugging  | Setup, available tools, usage examples                    |
| `COPILOT_SETUP.md`             | GitHub Copilot Free tier                  | Enabling, limits (2000 completions/month), best practices |
| `GITHUB_MODELS.md`             | GitHub Models for AI-assisted development | Available models, rate limits, API usage                  |
| `LINEAR-GITHUB-INTEGRATION.md` | Linear-GitHub sync configuration          | Webhook setup, bi-directional sync, troubleshooting       |
| `LINEAR_SETUP_PROMPT.md`       | Prompt for setting up Linear workspace    | Team setup, labels, workflow states                       |
| `MUTATION_TESTING.md`          | Mutation testing setup (mutmut + Stryker) | Installation, usage, interpreting results                 |

### Documentation Hubs

| File               | Purpose                       | Target Audience                   |
| ------------------ | ----------------------------- | --------------------------------- |
| `developer-hub.md` | Developer documentation index | Software developers, contributors |
| `operator-hub.md`  | Operator documentation index  | System admins, DevOps engineers   |
| `user-hub.md`      | User documentation index      | End users, homeowners             |

### Security Documentation

| File                            | Purpose                         | Key Topics                                    |
| ------------------------------- | ------------------------------- | --------------------------------------------- |
| `SECURITY.md`                   | Security policies and practices | Reporting vulnerabilities, security practices |
| `SECURITY_API_KEYS.md`          | API key security documentation  | Key storage, rotation, best practices         |
| `METRICS_ENDPOINT_HARDENING.md` | Metrics endpoint security       | Access control, rate limiting, authentication |
| `PEER_DEPS_CONFLICT.md`         | NPM peer dependency resolution  | Handling version conflicts safely             |

## Subdirectories

### admin-guide/

System administrator documentation for configuring, monitoring, and maintaining the system.

See `admin-guide/AGENTS.md` for detailed information.

### api/

API governance documentation including deprecation policies, migration guides, and versioning standards.

See `api/AGENTS.md` for detailed information.

**Contents:**

- `DEPRECATION_POLICY.md` - Complete API deprecation process with timeline, OpenAPI extensions, and migration templates
- `migrations/` - Migration guides for deprecated endpoints

### api-reference/

REST and WebSocket API documentation (**canonical location**).

See `api-reference/AGENTS.md` for detailed information.

### architecture/

Technical architecture documentation including system design, AI pipeline, data models, and architectural decisions.

See `architecture/AGENTS.md` for detailed information.

### benchmarks/

Performance benchmark results for AI models and system components.

See `benchmarks/AGENTS.md` for detailed information.

### decisions/

Architecture Decision Records (ADRs) documenting significant technical choices.

See `decisions/AGENTS.md` for detailed information.

### developer/

Developer-focused documentation for contributing to and extending the system.

See `developer/AGENTS.md` for detailed information.

### development/

Development workflow documentation including contribution guidelines, patterns, and testing.

See `development/AGENTS.md` for detailed information.

### getting-started/

Quick start guides for installation, first run, and upgrades.

See `getting-started/AGENTS.md` for detailed information.

### images/

Visual assets including mockups, screenshots, and diagrams.

See `images/AGENTS.md` for detailed information.

### operator/

Operator-focused documentation for deployment, configuration, and maintenance.

See `operator/AGENTS.md` for detailed information.

### plans/

Design specifications and implementation plans with date-prefixed filenames.

See `plans/AGENTS.md` for detailed information.

### reference/

Authoritative reference documentation including API, configuration, and troubleshooting.

See `reference/AGENTS.md` for detailed information.

**Subdirectories:**

- `reference/config/` - Configuration reference
- `reference/troubleshooting/` - Problem-solving guides

**Additional files:**

- `reference/glossary.md` - Terms and definitions
- `reference/stability.md` - API stability definitions

### user/

End-user documentation using hub-and-spoke architecture (integrated with user-hub.md).

See `user/AGENTS.md` for detailed information.

### user-guide/

End-user documentation (original structure, standalone documents).

See `user-guide/AGENTS.md` for detailed information.

### testing/

Testing guides and patterns for developers.

See `testing/AGENTS.md` for detailed information.

**Contents:**

- `TDD_WORKFLOW.md` - Test-Driven Development workflow
- `TESTING_PATTERNS.md` - Common testing patterns
- `HYPOTHESIS_GUIDE.md` - Property-based testing with Hypothesis

**Note:** See also the root-level `TESTING_GUIDE.md` for comprehensive testing documentation.

## Documentation Flow

1. **Design Phase:** `plans/2024-12-21-dashboard-mvp-design.md`

   - Architecture, schema, API specs, UI design
   - Defines WHAT to build

2. **Implementation Phase:** `plans/2024-12-22-mvp-implementation-plan.md`

   - Task breakdown with 8 execution phases
   - Defines HOW and WHEN to build

3. **Deployment Phase:** `DOCKER_DEPLOYMENT.md` + `AI_SETUP.md`

   - Comprehensive guides for running the system
   - Defines HOW to deploy and operate

4. **Future Phase:** `ROADMAP.md`
   - Post-MVP enhancement ideas
   - Defines WHAT COMES NEXT

## Source of Truth

**Docs are source of truth for:**

- Architecture decisions (design spec, ADRs)
- API contracts (api-reference/)
- Database schema (architecture/data-model.md)
- Environment configuration (reference/config/env-reference.md)
- Deployment procedures (AI_SETUP.md, DOCKER_DEPLOYMENT.md)
- Risk level definitions (reference/config/risk-levels.md)

**Code is source of truth for:**

- Current implementation state
- Test coverage
- Actual behavior and edge cases

## Entry Points for Agents

### Starting a New Session

1. **Check project status** - Read root `AGENTS.md` or `CLAUDE.md`
2. **Check available work** - Use [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) or MCP tools to find available tasks
3. **Refer to implementation plan** - Find task details and phase breakdown
4. **Refer to design spec** - Understand architecture/API contracts

### Understanding the System

| Goal                | Start Here                           |
| ------------------- | ------------------------------------ |
| System architecture | `architecture/overview.md`           |
| AI pipeline         | `architecture/ai-pipeline.md`        |
| API integration     | `api-reference/overview.md`          |
| Configuration       | `reference/config/env-reference.md`  |
| Stability / WIP     | `reference/stability.md`             |
| Troubleshooting     | `reference/troubleshooting/index.md` |
| User features       | `user/dashboard-basics.md`           |

### Deploying the System

1. **For Docker services** - Read `DOCKER_DEPLOYMENT.md`
2. **For AI services** - Read `AI_SETUP.md`
3. **For environment setup** - Read `RUNTIME_CONFIG.md`
4. **Run deployment tests** - Use `scripts/test-docker.sh`

## Conventions

### File Naming

- Date prefix for time-sensitive docs: `YYYY-MM-DD-description.md`
- ALL_CAPS for root-level guides: `AI_SETUP.md`, `ROADMAP.md`
- Lowercase with hyphens for other docs: `env-reference.md`

### Document Structure

All AGENTS.md files follow this structure:

- Purpose of the directory
- Key files and what they do
- Important patterns and conventions
- Entry points for understanding the code

## Documentation Statistics

This documentation directory contains comprehensive coverage of the project:

| Category                | Count | Description                                          |
| ----------------------- | ----- | ---------------------------------------------------- |
| **AGENTS.md files**     | 20    | Navigation files across 19 subdirectories + root     |
| **Subdirectories**      | 19    | Organized by topic (19 with AGENTS.md files)         |
| **Root-level docs**     | 34    | Guides for deployment, security, testing, operations |
| **API reference files** | 18    | Comprehensive endpoint documentation                 |
| **Design plans**        | 32    | Date-prefixed design and implementation plans        |
| **Architecture docs**   | 9     | System design, resilience, real-time, data model     |

### AGENTS.md File Locations

All 20 AGENTS.md files in the docs directory:

| Path                                       | Purpose                        |
| ------------------------------------------ | ------------------------------ |
| `docs/AGENTS.md`                           | Documentation root navigation  |
| `docs/admin-guide/AGENTS.md`               | Admin guide directory          |
| `docs/api/AGENTS.md`                       | API governance directory       |
| `docs/api-reference/AGENTS.md`             | API reference directory        |
| `docs/architecture/AGENTS.md`              | Architecture directory         |
| `docs/benchmarks/AGENTS.md`                | Benchmarks directory           |
| `docs/decisions/AGENTS.md`                 | ADR directory                  |
| `docs/developer/AGENTS.md`                 | Developer docs directory       |
| `docs/development/AGENTS.md`               | Development workflow directory |
| `docs/getting-started/AGENTS.md`           | Quick start guides directory   |
| `docs/images/AGENTS.md`                    | Visual assets directory        |
| `docs/operator/AGENTS.md`                  | Operator docs directory        |
| `docs/plans/AGENTS.md`                     | Plans directory                |
| `docs/reference/AGENTS.md`                 | Reference root directory       |
| `docs/reference/config/AGENTS.md`          | Configuration reference        |
| `docs/reference/troubleshooting/AGENTS.md` | Troubleshooting guides         |
| `docs/testing/AGENTS.md`                   | Testing guides directory       |
| `docs/user-guide/AGENTS.md`                | User guide (consolidated)      |

## Related Documentation

- **Root AGENTS.md:** Project overview and entry points
- **CLAUDE.md:** Comprehensive Claude Code instructions
- **README.md:** Project overview and quick start guide
- **scripts/AGENTS.md:** Development and deployment scripts
- **backend/AGENTS.md:** Backend architecture overview
- **frontend/AGENTS.md:** Frontend architecture overview
- **ai/AGENTS.md:** AI services implementation details
