# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation including design specifications, implementation plans, setup guides, architecture decisions, and visual assets.

## Directory Structure

```
docs/
  AGENTS.md                       # This file - guide to documentation
  README.md                       # Documentation navigation hub
  ROADMAP.md                      # Post-MVP roadmap ideas
  AI_SETUP.md                     # AI services setup guide
  RUNTIME_CONFIG.md               # Authoritative port/env reference
  DOCKER_DEPLOYMENT.md            # Docker deployment guide
  DOCKER_VERIFICATION_SUMMARY.md  # Docker deployment verification summary
  CHROME_DEVTOOLS_MCP.md          # Chrome DevTools MCP server guide
  COPILOT_SETUP.md                # GitHub Copilot Free tier setup guide
  GITHUB_MODELS.md                # GitHub Models integration guide
  SELF_HOSTED_RUNNER.md           # Self-hosted GPU runner setup guide
  architecture/                   # Technical architecture documentation
    AGENTS.md                     # Architecture directory guide
    overview.md                   # System architecture overview
    ai-pipeline.md                # AI processing pipeline details
    data-model.md                 # Database schema documentation
    decisions.md                  # Architecture decisions
  user-guide/                     # End-user documentation
    AGENTS.md                     # User guide directory guide
    getting-started.md            # New user onboarding
    understanding-alerts.md       # Risk levels and alerts
    using-the-dashboard.md        # Dashboard usage guide
  plans/                          # Design and implementation plans
    AGENTS.md                     # Plans directory guide
    *.md                          # Date-prefixed plan documents
  decisions/                      # Architecture Decision Records (ADRs)
    AGENTS.md                     # Decisions directory guide
    grafana-integration.md        # Grafana integration decision
  images/                         # Visual assets
    AGENTS.md                     # Images directory guide
    dashboard-mockup.svg          # Dashboard UI mockup
    *.png                         # Screenshots
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

| File                             | Purpose                                    | Key Sections                                                                |
| -------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------- |
| `AI_SETUP.md`                    | AI inference services setup                | Hardware requirements, model downloads, service management, troubleshooting |
| `DOCKER_DEPLOYMENT.md`           | Docker Compose deployment                  | Quick start, configuration, health checks, volume management                |
| `DOCKER_VERIFICATION_SUMMARY.md` | Phase 8 Docker task completion             | Verification checklist, files modified                                      |
| `SELF_HOSTED_RUNNER.md`          | Self-hosted GitHub Actions runner with GPU | Installation, security, maintenance                                         |

### Developer Tools

| File                     | Purpose                                   | Key Sections                                              |
| ------------------------ | ----------------------------------------- | --------------------------------------------------------- |
| `CHROME_DEVTOOLS_MCP.md` | Chrome DevTools MCP server for debugging  | Setup, available tools, usage examples                    |
| `COPILOT_SETUP.md`       | GitHub Copilot Free tier                  | Enabling, limits (2000 completions/month), best practices |
| `GITHUB_MODELS.md`       | GitHub Models for AI-assisted development | Available models, rate limits, API usage                  |

### Subdirectories

**architecture/** - Technical architecture documentation

- System overview with Mermaid diagrams
- AI pipeline details and data flow
- Database schema and relationships
- Architecture decisions and rationale
- See `architecture/AGENTS.md` for detailed documentation

**user-guide/** - End-user documentation

- Written for non-technical users
- Getting started guide
- Understanding alerts and risk levels
- Dashboard usage guide
- See `user-guide/AGENTS.md` for detailed documentation

**plans/** - Design specifications and implementation plans

- Date-prefixed files (`YYYY-MM-DD-description.md`)
- MVP design, implementation plan, logging system, CI/CD, health monitoring
- See `plans/AGENTS.md` for detailed documentation

**decisions/** - Architecture Decision Records (ADRs)

- Documents significant technical decisions
- Currently contains: Grafana integration strategy
- See `decisions/AGENTS.md` for more details

**images/** - Visual assets

- `dashboard-mockup.svg` - Main dashboard UI mockup (vector)
- `dashboard.png`, `dashboard-full.png` - Dashboard screenshots
- `timeline.png` - Event timeline screenshot
- `alerts.png` - Alerts page screenshot
- See `images/AGENTS.md` for detailed documentation

## Relationship to Project

### Documentation Flow

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

### Source of Truth

**Docs are source of truth for:**

- Architecture decisions (design spec, ADRs)
- API contracts (design spec)
- Database schema (design spec)
- Environment configuration (RUNTIME_CONFIG.md)
- Deployment procedures (AI_SETUP.md, DOCKER_DEPLOYMENT.md)

**Code is source of truth for:**

- Current implementation state
- Test coverage
- Actual behavior and edge cases

## Important Patterns

### When to Update Documentation

**ROADMAP.md** should be updated:

- When adding new post-MVP enhancement ideas
- When completing roadmap items (mark as done)
- When changing prioritization strategy
- After MVP is operational and roadmap work begins

**Implementation Plan** should be updated:

- RARELY (tasks are tracked in bd, not this file)
- Only if phase definitions change
- Only if new epics are added

**Design Specification** should be updated:

- When architecture changes
- When API contracts change
- When database schema changes
- NOT for implementation details or refinements

**Setup/Deployment Guides** should be updated:

- When adding new services or dependencies
- When changing deployment procedures
- When updating recommended configurations
- When adding new troubleshooting solutions
- NOT for code-level changes (those go in code comments)

### Design Decisions Documented

The design specification and architecture documents these critical decisions:

1. **Database:** PostgreSQL (chosen for concurrent pipeline worker access)
2. **Batch Processing:** 90s window + 30s idle timeout (vs real-time per-frame analysis)
3. **Risk Scoring:** LLM-determined via Nemotron (0-100 scale)
4. **Deployment:** Hybrid (Docker for services, native for GPU models)
5. **Authentication:** None for MVP (single-user local deployment)
6. **Retention:** 30 days (configurable)
7. **UI Theme:** NVIDIA green (#76B900) with dark background

## Entry Points for Agents

### Starting a New Session

1. **Check project status** - Read root `AGENTS.md` or `CLAUDE.md`
2. **Check available work** - Run `bd ready` or `bd list --label phase-N`
3. **Refer to implementation plan** - Find task details and phase breakdown
4. **Refer to design spec** - Understand architecture/API contracts

### Understanding AI Pipeline

1. **Read design spec** - Processing Pipeline section
2. **Read AI_SETUP.md** - How to set up and run AI services
3. **Read RUNTIME_CONFIG.md** - Port assignments and configuration
4. Check `backend/services/` for implementation

### Deploying the System

1. **For Docker services** - Read `DOCKER_DEPLOYMENT.md`
2. **For AI services** - Read `AI_SETUP.md`
3. **For environment setup** - Read `RUNTIME_CONFIG.md`
4. **Run deployment tests** - Use `scripts/test-docker.sh`

## Conventions

### File Naming

- Date prefix for time-sensitive docs: `YYYY-MM-DD-description.md`
- ALL_CAPS for root-level guides: `AI_SETUP.md`, `ROADMAP.md`
- Lowercase with hyphens for ADRs: `grafana-integration.md`

### Document Structure

All AGENTS.md files follow this structure:

- Purpose of the directory
- Key files and what they do
- Important patterns and conventions
- Entry points for understanding the code

All guide files follow this structure:

- Overview and quick start
- Detailed sections with examples
- Troubleshooting guide
- Quick reference at the end

## Related Documentation

- **Root AGENTS.md:** Project overview and entry points
- **CLAUDE.md:** Comprehensive Claude Code instructions
- **README.md:** Project overview and quick start guide
- **scripts/AGENTS.md:** Development and deployment scripts
- **backend/AGENTS.md:** Backend architecture overview
- **frontend/AGENTS.md:** Frontend architecture overview
