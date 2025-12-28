# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation including design specifications, implementation plans, setup guides, architecture decisions, and visual assets.

## Directory Structure

```
docs/
├── AGENTS.md                       # This file - guide to documentation
├── ROADMAP.md                      # Post-MVP roadmap ideas
├── AI_SETUP.md                     # AI services setup guide
├── RUNTIME_CONFIG.md               # Authoritative port/env reference
├── DOCKER_DEPLOYMENT.md            # Docker deployment guide
├── DOCKER_VERIFICATION_SUMMARY.md  # Docker deployment verification summary
├── CHROME_DEVTOOLS_MCP.md          # Chrome DevTools MCP server guide
├── COPILOT_SETUP.md                # GitHub Copilot Free tier setup guide
├── GITHUB_MODELS.md                # GitHub Models integration guide
├── SELF_HOSTED_RUNNER.md           # Self-hosted GPU runner setup guide
├── plans/                          # Design and implementation plans
│   ├── AGENTS.md                   # Plans directory guide
│   └── *.md                        # Date-prefixed plan documents
├── decisions/                      # Architecture Decision Records (ADRs)
│   └── grafana-integration.md      # Grafana integration decision
└── images/                         # Visual assets
    └── dashboard-mockup.svg        # Dashboard UI mockup
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

**plans/** - Design specifications and implementation plans

- Date-prefixed files (`YYYY-MM-DD-description.md`)
- MVP design, implementation plan, logging system, CI/CD, health monitoring
- See `plans/AGENTS.md` for detailed documentation

**decisions/** - Architecture Decision Records (ADRs)

- Documents significant technical decisions
- Currently contains: Grafana integration strategy
- See `decisions/AGENTS.md` for more details

**images/** - Visual assets

- `dashboard-mockup.svg` - Main dashboard UI mockup showing risk gauge, camera grid, activity feed

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
