# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation including design specifications, implementation plans, setup guides, and session handoff documents.

## Key Files

### Roadmap and Future Vision

**ROADMAP.md**

- **Purpose:** Post-MVP roadmap ideas to pursue after Phases 1-8 are operational
- **Contents:**
  - 8 roadmap themes with implementation notes
  - Prioritization rubric for selecting next features
  - Bigger bets (longer-term/researchy ideas)
  - Context about what MVP establishes
  - Guiding principles to keep scope sane
- **When to use:** After MVP is fully operational (Phases 1-8 complete, deployment verified, tests passing)
- **Key sections:**
  - Alerting & escalation (turn insights into action)
  - Spatial intelligence & zones (reduce false positives)
  - Entity continuity (ReID-lite and "same actor" reasoning)
  - Pattern-of-life / anomaly detection
  - Search & investigations
  - Better media handling (clips, pre/post roll)
  - Reliability & operations
  - Security hardening
- **Last updated:** 2025-12-24

### Setup and Deployment Guides

**AI_SETUP.md**

- **Purpose:** Comprehensive guide for setting up and running AI inference services
- **Contents:**
  - Hardware requirements (GPU, VRAM, CUDA)
  - Software prerequisites (NVIDIA drivers, Python, llama.cpp)
  - Model downloads (Nemotron, RT-DETRv2)
  - Starting services (unified startup script)
  - Service management (status, stop, restart, health check)
  - Verification and testing procedures
  - Troubleshooting guide
  - Performance tuning recommendations
  - Monitoring and production deployment
- **When to use:**
  - Setting up AI services for the first time
  - Troubleshooting AI service issues
  - Understanding GPU resource usage
  - Production deployment planning
- **Key sections:**
  - Quick reference (lines 844-897)
  - Troubleshooting (lines 443-623)
  - Performance tuning (lines 625-682)

**DOCKER_DEPLOYMENT.md**

- **Purpose:** Complete guide for Docker Compose deployment
- **Contents:**
  - Quick start (development and production modes)
  - Configuration files (docker-compose.yml vs docker-compose.prod.yml)
  - Service details (Backend, Frontend, Redis)
  - Environment variables reference
  - Health checks documentation
  - Volume management and data persistence
  - Troubleshooting common issues
  - Security considerations
  - Performance tuning
  - Backup and recovery procedures
  - CI/CD integration example
- **When to use:**
  - Deploying services with Docker
  - Understanding service architecture
  - Configuring production deployment
  - Troubleshooting deployment issues
- **Key sections:**
  - Quick start (lines 16-41)
  - Troubleshooting (lines 249-307)
  - Security hardening (lines 363-381)

**DOCKER_VERIFICATION_SUMMARY.md**

- **Purpose:** Summary of Docker deployment verification and enhancements (Phase 8 task completion)
- **Contents:**
  - Files verified and enhanced
  - Health checks configuration
  - Production configuration details
  - Test script features
  - Verification checklist
  - Usage instructions
  - Files created/modified list
- **When to use:**
  - Understanding what was done for Phase 8 Docker task
  - Reference for deployment enhancements
  - Understanding test script capabilities
- **Last updated:** 2025-12-24

**CHROME_DEVTOOLS_MCP.md**

- **Purpose:** Guide for using Chrome DevTools MCP server for web page inspection
- **Contents:**
  - Overview and architecture diagram
  - Prerequisites (Chrome, Node.js, Claude Code)
  - Setup instructions for headless Chrome
  - MCP server configuration
  - Available tools and commands
  - Usage examples for debugging
  - Troubleshooting common issues
- **When to use:**
  - Debugging frontend UI issues from Claude Code
  - Capturing console errors and warnings
  - Inspecting DOM structure and network requests
  - Taking screenshots of rendered pages
  - Performance analysis and JavaScript debugging
- **Key capabilities:**
  - Navigate to URLs and inspect rendered pages
  - Read console logs, errors, and warnings
  - Execute JavaScript in page context
  - Monitor network requests
  - Capture screenshots
- **Last updated:** 2025-12-25

**COPILOT_SETUP.md**

- **Purpose:** Guide for setting up GitHub Copilot Free tier for this project
- **Contents:**
  - How to enable Copilot Free tier (link to GitHub settings)
  - Free tier limits (2,000 completions/month, 50 chat messages/month)
  - VS Code extension recommendations
  - Best practices for using Copilot with this codebase
  - Tips to maximize value within free tier limits
- **When to use:**
  - Setting up Copilot for development
  - Understanding Copilot usage limits
  - Optimizing Copilot suggestions
- **Related file:** `.github/copilot-instructions.md` - Project-specific Copilot context
- **Last updated:** 2025-12-26

**GITHUB_MODELS.md**

- **Purpose:** Guide for using GitHub Models for AI-assisted development
- **Contents:**
  - Available models (GPT-4o, Llama, Phi, Mistral, etc.)
  - Rate limits (free tier: 10 req/min, 50 req/day for high-tier models)
  - Authentication (GH_TOKEN, GitHub Actions integration)
  - gh CLI usage examples
  - REST API usage with Python
  - Current project usage (AI code review workflow)
  - Use cases for this project (code review, test generation, security analysis)
  - Best practices and troubleshooting
- **When to use:**
  - Setting up GitHub Models integration
  - Understanding rate limits and quotas
  - Using AI for code review, test generation, or security analysis
  - Adding new GitHub Actions workflows using AI
- **Related files:**
  - `.github/workflows/ai-code-review.yml` - AI code review workflow
  - `scripts/github-models-examples.py` - Working Python examples
- **Marketplace:** [https://github.com/marketplace/models](https://github.com/marketplace/models)
- **Last updated:** 2025-12-26

**SELF_HOSTED_RUNNER.md**

- **Purpose:** Guide for setting up self-hosted GitHub Actions runner with GPU
- **Contents:**
  - Prerequisites (hardware, software, GitHub requirements)
  - Installation steps (driver verification, NVIDIA container toolkit, runner setup)
  - Configuration (registration, labels, systemd service)
  - Security considerations (fork protection, resource limits, secrets)
  - Verification and troubleshooting
  - Maintenance (updates, monitoring, cleanup)
- **When to use:**
  - Setting up GPU-accelerated CI/CD
  - Troubleshooting self-hosted runner issues
  - Understanding security implications
- **Related files:**
  - `.github/workflows/gpu-tests.yml` - GPU test workflow
  - `.github/workflows/nightly.yml` - Nightly workflow
  - `scripts/setup-gpu-runner.sh` - Runner setup script
- **Last updated:** 2025-12-26

### Implementation Plans

**plans/** directory contains design specifications and implementation plans:

- **2024-12-21-dashboard-mvp-design.md** - Complete MVP design specification (architecture, schema, APIs, UI)
- **2024-12-22-mvp-implementation-plan.md** - Task breakdown with 8 execution phases
- **2024-12-24-logging-system-design.md** - Logging system architecture spec
- **2024-12-24-logging-implementation-plan.md** - Logging implementation tasks
- **2025-12-26-github-cicd-design.md** - GitHub CI/CD pipeline design with security scanning
- **2025-12-26-github-cicd-implementation.md** - CI/CD implementation tasks
- **2025-12-26-service-health-monitoring-design.md** - Auto-recovery and health monitoring design
- **2025-12-26-readme-redesign.md** - README structure redesign plan

See `plans/AGENTS.md` for detailed documentation of plan files.

## Directory Structure

```
docs/
├── AGENTS.md                             # This file - guide to documentation
├── ROADMAP.md                            # Post-MVP roadmap ideas
├── AI_SETUP.md                           # AI services setup guide
├── COPILOT_SETUP.md                      # GitHub Copilot Free tier setup guide
├── DOCKER_DEPLOYMENT.md                  # Docker deployment guide
├── DOCKER_VERIFICATION_SUMMARY.md        # Docker deployment verification summary
├── CHROME_DEVTOOLS_MCP.md                # Chrome DevTools MCP server guide
├── GITHUB_MODELS.md                      # GitHub Models integration guide
├── SELF_HOSTED_RUNNER.md                 # Self-hosted GPU runner setup guide
├── plans/                                # Design and implementation plans
│   ├── AGENTS.md                         # Plans directory guide
│   ├── 2024-12-21-dashboard-mvp-design.md
│   ├── 2024-12-22-mvp-implementation-plan.md
│   ├── 2024-12-24-logging-system-design.md
│   ├── 2024-12-24-logging-implementation-plan.md
│   ├── 2025-12-26-github-cicd-design.md
│   ├── 2025-12-26-github-cicd-implementation.md
│   ├── 2025-12-26-service-health-monitoring-design.md
│   └── 2025-12-26-readme-redesign.md
└── images/                               # Visual assets (placeholder)
    └── .gitkeep
```

## Relationship to Project

### Design -> Implementation -> Deployment Flow

1. **Design Phase:** `plans/2024-12-21-dashboard-mvp-design.md`

   - Created first with architecture, schema, API specs, UI design
   - Approved by stakeholder
   - Defines WHAT to build

2. **Implementation Phase:** `plans/2024-12-22-mvp-implementation-plan.md`

   - Created second with task breakdown
   - References design document
   - Defines HOW and WHEN to build

3. **Deployment Phase:** `DOCKER_DEPLOYMENT.md` + `AI_SETUP.md`

   - Created during Phase 8 (Integration & E2E)
   - Comprehensive guides for running the system
   - Defines HOW to deploy and operate

4. **Future Phase:** `ROADMAP.md`
   - Post-MVP enhancement ideas
   - Prioritization guidance
   - Defines WHAT COMES NEXT after MVP is operational

### Documentation vs Code

- **Docs are source of truth for:**

  - Architecture decisions (design spec)
  - API contracts (design spec)
  - Database schema (design spec)
  - UI specifications (design spec)
  - Risk scoring logic / Nemotron prompts (design spec)
  - Deployment procedures (AI_SETUP.md, DOCKER_DEPLOYMENT.md)
  - Future roadmap (ROADMAP.md)

- **Code is source of truth for:**
  - Current implementation state
  - Test coverage
  - Bug fixes and refinements
  - Performance optimizations
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

The design specification documents these critical decisions:

1. **Batch Processing:** 90s window + 30s idle timeout (vs real-time per-frame analysis)
2. **Risk Scoring:** LLM-determined via Nemotron
3. **Deployment:** Hybrid (Docker for services, native for GPU models)
4. **Database:** PostgreSQL for concurrent access and reliability
5. **Authentication:** None for MVP (single-user local deployment)
6. **Retention:** 30 days (configurable)
7. **UI Theme:** NVIDIA green (#76B900) with dark background

## Entry Points for Agents

### Starting a New Session

1. **Check project status** - Read root AGENTS.md or CLAUDE.md
2. **Check available work** - Run `bd ready` or `bd list --label phase-N`
3. **Refer to implementation plan** - Find task details and phase breakdown
4. **Refer to design spec** - Understand architecture/API contracts
5. **After MVP complete** - Review ROADMAP.md for post-MVP work

### Implementing a New Feature

1. **Check design spec** - Understand requirements
2. **Check implementation plan** - Find related tasks
3. Write tests (TDD approach for tasks labeled `tdd`)
4. Implement feature
5. Run tests and validation
6. Commit changes (pre-commit hooks will run automatically)

### Understanding Architecture

1. **Read design spec** - System architecture section
2. Look at data flow diagram
3. Review database schema
4. Check API endpoint specifications

### Understanding AI Pipeline

1. **Read design spec** - Processing Pipeline section (lines 172-200)
2. **Read design spec** - Nemotron Prompt section (lines 202-239)
3. **Read AI_SETUP.md** - How to set up and run AI services
4. Check implementation plan for task breakdown
5. Look at `backend/services/` code for actual implementation

### Deploying the System

1. **For Docker services** - Read DOCKER_DEPLOYMENT.md
2. **For AI services** - Read AI_SETUP.md
3. **Run deployment tests** - Use `scripts/test-docker.sh`
4. **Monitor services** - Use health check endpoints and logs

## Conventions

### Markdown Structure

- Use `#` for top-level headings
- Use code blocks with language hints (`bash`, `python`, `sql`)
- Use tables for structured data
- Use bullet points for lists
- Use bold for emphasis on critical information

### File Naming

- Date prefix for time-sensitive docs: `YYYY-MM-DD-description.md`
- ALL_CAPS for root-level agent docs: `AGENTS.md`, `AGENT_HANDOFF.md`
- Lowercase with hyphens for plans: `dashboard-mvp-design.md`

### Common Documentation Patterns

1. **All AGENTS.md files** follow this structure:

   - Purpose of the directory
   - Key files and what they do
   - Important patterns and conventions
   - Entry points for understanding the code

2. **All guide files** (AI_SETUP.md, DOCKER_DEPLOYMENT.md) follow this structure:

   - Overview and quick start
   - Detailed sections with examples
   - Troubleshooting guide
   - Quick reference at the end

3. **All plan files** (design spec, implementation plan) have:
   - Date and status header
   - Table of contents or clear sections
   - Code blocks for technical content
   - Tables for structured data

## Related Documentation

- **Root AGENTS.md:** Overview of entire project
- **CLAUDE.md:** Comprehensive Claude Code instructions
- **README.md:** Project overview and quick start guide
- **DOCKER_QUICKSTART.md:** Quick reference for Docker commands
- **scripts/AGENTS.md:** Development and deployment scripts documentation
- **backend/AGENTS.md:** Backend architecture overview
- **frontend/AGENTS.md:** Frontend architecture overview
- **ai/AGENTS.md:** AI pipeline overview

## Future Roadmap

The ROADMAP.md file contains post-MVP enhancement ideas organized into themes:

1. **Alerting & escalation** - Turn insights into action (notifications, rules, dedupe)
2. **Spatial intelligence & zones** - Reduce false positives (polygons, line crossing)
3. **Entity continuity (ReID-lite)** - Track "same actor" across detections
4. **Pattern-of-life / anomaly detection** - Learn normal patterns, flag unusual activity
5. **Search & investigations** - Full-text and semantic search, case workflows
6. **Better media handling** - Clips, pre/post roll, scrubber UX
7. **Reliability & operations** - Backpressure, retries, observability, storage tooling
8. **Security hardening** - Auth, audit logging, rate limiting

**Bigger bets (researchy/longer-term):**

- Natural language "chat with your security history" (RAG)
- NIM / standardized inference deployment
- Digital twin reconstruction (USD / Omniverse)
- Face recognition / license plates (privacy-sensitive, explicit opt-in)

**IMPORTANT:** Only pursue roadmap items **after MVP is fully operational** (Phases 1-8 complete, deployment verified, tests passing).
