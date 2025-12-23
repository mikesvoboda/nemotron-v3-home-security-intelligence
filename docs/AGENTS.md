# Documentation Directory - Agent Guide

## Purpose

This directory contains all project documentation including design specifications, implementation plans, and session handoff documents.

## Key Files

### Session Continuity

**AGENT_HANDOFF.md**

- **Purpose:** Primary session handoff document for maintaining context between agent sessions
- **Contents:**
  - Current project status (Phase 1-4 complete, 5-8 remaining)
  - Test coverage statistics (Backend: 98.54%, Frontend: 98.95%)
  - How to continue workflow (bd commands, testing, commits)
  - Phase 5 task breakdown (Events & Real-time APIs)
  - Key file reference for implemented services
  - Environment setup instructions
- **When to use:** Read this FIRST when starting a new session
- **Last updated:** 2025-12-23 after Phase 4 completion

### Implementation Plans

**plans/2024-12-22-mvp-implementation-plan.md**

- **Purpose:** Master implementation plan with task breakdown
- **Contents:**
  - Epic overview (5 epics, 67 tasks total)
  - 8-phase execution plan with task IDs
  - TDD workflow guidance
  - Issue tracking commands (bd)
  - NVIDIA persona perspectives for future roadmap
- **When to use:**
  - Understanding overall project scope
  - Finding specific task requirements
  - Planning work across phases
- **Key sections:**
  - Phase definitions (1: Setup, 2: Database, 3: Core APIs, 4: AI Pipeline, 5: Events, 6: Dashboard, 7: Pages, 8: E2E)
  - TDD task identification
  - Future enhancement ideas

**plans/2024-12-21-dashboard-mvp-design.md**

- **Purpose:** Comprehensive design specification and architecture
- **Contents:**
  - System architecture diagram
  - Data flow explanation
  - Database schema (cameras, detections, events, gpu_stats)
  - API endpoint specifications (REST + WebSocket)
  - Processing pipeline details
  - Nemotron prompt template
  - UI design (color scheme, layout, mockups)
  - Component library choices
  - Configuration specifications
- **When to use:**
  - Understanding system architecture
  - Implementing new API endpoints
  - Understanding data model relationships
  - Designing UI components
  - Understanding AI pipeline flow
- **Key sections:**
  - Database Schema (lines 67-122)
  - API Endpoints (lines 124-169)
  - Processing Pipeline (lines 172-200)
  - Nemotron Prompt (lines 202-239)
  - UI Mockups (lines 434-553)

## Directory Structure

```
docs/
├── AGENTS.md             # This file - guide to documentation
├── AGENT_HANDOFF.md      # Session continuity document
└── plans/
    ├── 2024-12-21-dashboard-mvp-design.md        # Design specification
    └── 2024-12-22-mvp-implementation-plan.md     # Implementation plan
```

## Relationship to Project

### Design → Implementation Flow

1. **Design Phase:** `plans/2024-12-21-dashboard-mvp-design.md`

   - Created first with architecture, schema, API specs, UI design
   - Approved by stakeholder
   - Defines WHAT to build

2. **Implementation Phase:** `plans/2024-12-22-mvp-implementation-plan.md`

   - Created second with task breakdown
   - References design document
   - Defines HOW and WHEN to build

3. **Session Continuity:** `AGENT_HANDOFF.md`
   - Updated after each major milestone
   - Tracks current state and next steps
   - Defines WHERE YOU ARE NOW

### Documentation vs Code

- **Docs are source of truth for:**

  - Architecture decisions
  - API contracts
  - Database schema
  - UI specifications
  - Risk scoring logic (Nemotron prompts)

- **Code is source of truth for:**
  - Current implementation state
  - Test coverage
  - Bug fixes and refinements
  - Performance optimizations

## Important Patterns

### When to Update Documentation

**AGENT_HANDOFF.md** should be updated:

- After completing a phase
- After major feature implementation
- At end of each agent session
- When test coverage changes significantly
- When starting new work that others need context on

**Implementation Plan** should be updated:

- RARELY (tasks are tracked in bd, not this file)
- Only if phase definitions change
- Only if new epics are added

**Design Specification** should be updated:

- When architecture changes
- When API contracts change
- When database schema changes
- NOT for implementation details or refinements

### Design Decisions Documented

The design specification documents these critical decisions:

1. **Batch Processing:** 90s window + 30s idle timeout (vs real-time per-frame analysis)
2. **Risk Scoring:** LLM-determined (Nemotron) vs rule-based
3. **Deployment:** Hybrid (Docker for services, native for GPU models)
4. **Database:** SQLite (single-user) vs PostgreSQL
5. **Authentication:** None for MVP (single-user local deployment)
6. **Retention:** 30 days (configurable)
7. **UI Theme:** NVIDIA green (#76B900) with dark background

## Entry Points for Agents

### Starting a New Session

1. **Read AGENT_HANDOFF.md** - Get current status
2. Check which phase you're in
3. Refer to implementation plan for task details
4. Refer to design spec for architecture/API contracts

### Implementing a New Feature

1. **Check design spec** - Understand requirements
2. **Check implementation plan** - Find related tasks
3. Write tests (TDD approach)
4. Implement feature
5. Update AGENT_HANDOFF.md if major milestone

### Understanding Architecture

1. **Read design spec** - System architecture section
2. Look at data flow diagram
3. Review database schema
4. Check API endpoint specifications

### Understanding AI Pipeline

1. **Read design spec** - Processing Pipeline section (lines 172-200)
2. **Read design spec** - Nemotron Prompt section (lines 202-239)
3. Check implementation plan for task breakdown
4. Look at `backend/services/` code for actual implementation

## Conventions

### Markdown Structure

- Use `#` for top-level headings
- Use code blocks with language hints (`bash, `python, ```sql)
- Use tables for structured data
- Use bullet points for lists
- Use bold for emphasis on critical information

### File Naming

- Date prefix for time-sensitive docs: `YYYY-MM-DD-description.md`
- ALL_CAPS for root-level agent docs: `AGENTS.md`, `AGENT_HANDOFF.md`
- Lowercase with hyphens for plans: `dashboard-mvp-design.md`

### Sections in AGENT_HANDOFF.md

1. Header with date and last commit
2. Project Overview
3. Current Status (completed + remaining phases)
4. Test Coverage
5. How to Continue (commands)
6. Critical Rules
7. Next Phase Details
8. Key Files Reference
9. Environment Setup

## Related Documentation

- **Root AGENTS.md:** Overview of entire project
- **CLAUDE.md:** Comprehensive Claude Code instructions
- **backend/README.md files:** Module-specific documentation
- **frontend/TESTING.md:** Frontend testing guide
- **backend/tests/README.md:** Backend testing guide

## Future Roadmap (from Implementation Plan)

The implementation plan includes strategic perspectives from NVIDIA personas:

1. **Edge AI:** Spatial Context Injection (enhance prompts with spatial relationships)
2. **NIM PM:** NVIDIA NIM Migration (replace llama.cpp with NIM containers)
3. **Digital Twin:** USD Event Reconstruction (Omniverse integration)
4. **Cybersecurity:** Baseline Anomaly Scoring (learn normal patterns)
5. **RTX Marketing:** RAG-based Security Chat (query history with natural language)

These are v2+ features, not part of current MVP.
