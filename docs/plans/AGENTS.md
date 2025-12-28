# Plans Directory - Agent Guide

## Purpose

This directory contains design specifications and implementation plans that define the project architecture, requirements, and task breakdown.

## Key Files

### MVP Design and Implementation

**2024-12-21-dashboard-mvp-design.md** (572 lines)

- **Purpose:** Complete MVP design specification
- **Status:** APPROVED, serves as source of truth for architecture
- **Date:** 2024-12-21
- **Last Updated:** 2024-12-21 (stable, no changes needed)

#### Contents Overview

1. **Technology Stack** (lines 10-20)

   - Frontend: React + TypeScript + Tailwind + Tremor
   - Backend: FastAPI + SQLite + Redis
   - AI: RT-DETRv2 + Nemotron via llama.cpp
   - Deployment: Docker Compose (hybrid)

2. **System Architecture** (lines 22-57)

   - ASCII diagram showing complete data flow
   - FTP upload -> File Watcher -> RT-DETRv2 -> Redis -> Nemotron -> WebSocket -> Dashboard

3. **Data Flow** (lines 59-65)

   - 5-step processing pipeline
   - Camera upload to dashboard display

4. **Database Schema** (lines 67-122)

   - `cameras` - Camera configuration and status
   - `detections` - Individual RT-DETRv2 detections with bounding boxes
   - `events` - Batched Nemotron analysis with risk scores
   - `gpu_stats` - GPU performance snapshots
   - **Key relationships:**
     - Events reference multiple detections via `detection_ids` (JSON array, e.g., "[1, 2, 3]")
     - Detections reference cameras via `camera_id`
     - All timestamps for temporal queries

5. **API Endpoints** (lines 124-169)

   - **REST APIs:**
     - `/api/events` - CRUD for events with filtering
     - `/api/detections` - Query detections, serve images with bbox overlays
     - `/api/cameras` - CRUD for camera config
     - `/api/system` - GPU stats, health checks, config
     - `/api/media/{path}` - Serve images/videos
   - **WebSocket APIs:**
     - `/ws/events` - Real-time event and detection push
     - `/ws/system` - GPU stats and camera status updates

6. **Processing Pipeline** (lines 172-200)

   - **File Watcher:** watchdog library, monitors FTP directories, 500ms debounce
   - **RT-DETRv2:** ~7ms per frame on RTX A5500, produces object/confidence/bbox
   - **Batch Aggregator:** 90s window + 30s idle timeout, groups by camera
   - **Nemotron Analysis:** 2-5s per batch, produces risk_score/summary/reasoning
   - **Notification:** WebSocket push to dashboard

7. **Nemotron Prompt Template** (lines 202-239)

   - System prompt with JSON response structure
   - Risk guidelines (LOW: 0-33, MEDIUM: 34-66, HIGH: 67-100)
   - Factors: time of day, object type, behavior, count
   - User prompt with camera/time/duration/detections

8. **MVP Dashboard Panels** (lines 241-246)

   - Live Activity Feed
   - Multi-Camera Grid
   - Event Detail Modal
   - Risk Assessment Gauge
   - GPU Performance

9. **UI Design** (lines 248-263)

   - Color scheme (NVIDIA-themed, green #76B900)
   - Layout structure (header, sidebar, main grid)

10. **Project Structure** (lines 265-338)

    - Directory tree for backend, ai, frontend, scripts

11. **Docker Compose** (lines 340-384)

    - Backend container (port 8000)
    - Redis container (port 6379)
    - Frontend container (port 5173)
    - Volume mounts for data and camera uploads

12. **Configuration** (lines 386-412)

    - Environment variables and defaults
    - Camera root path
    - Batch window/timeout settings
    - Retention period

13. **Key Specifications** (lines 414-424)

    - 5-8 Foscam cameras
    - 1-2 minute batch window
    - 30 day retention
    - No auth (MVP)
    - RTX A5500 24GB

14. **UI Mockups** (lines 426-553)

    - Main Dashboard layout
    - Event Timeline with filters
    - Event Detail Modal with bounding boxes
    - Settings Page tabs (Cameras, Processing, AI Models)
    - Navigation structure

15. **Deferred to v2** (lines 554-563)
    - Face recognition
    - License plate recognition
    - Email/push notifications
    - RTSP live streams
    - Natural language search
    - Analytics/heatmaps

**2024-12-22-mvp-implementation-plan.md** (223 lines)

- **Purpose:** Task breakdown and execution plan for MVP
- **Status:** IN PROGRESS (Phase 5 complete, Phase 6 in progress)
- **Date:** 2024-12-22
- **Last Updated:** 2025-12-27

### Logging System Documentation

**2024-12-24-logging-system-design.md**

- **Purpose:** Design specification for comprehensive logging system
- **Status:** APPROVED
- **Date:** 2024-12-24
- **Contents:**
  - Overview of logging architecture
  - Three output destinations: Console, Rotating Files, SQLite
  - Backend logging module design (`backend/core/logging.py`)
  - JSON log format structure
  - Log levels and component classification
  - Frontend error capture and reporting
  - Admin UI requirements
- **When to use:**
  - Understanding logging architecture decisions
  - Implementing new logging features
  - Adding log entries to services
  - Troubleshooting log configuration

**2024-12-24-logging-implementation-plan.md**

- **Purpose:** Detailed task breakdown for logging system implementation
- **Status:** IN PROGRESS
- **Date:** 2024-12-24
- **Contents:**
  - Phase 1: Backend Foundation (config, models, logger module)
  - Phase 2: Service Integration (instrument services with logging)
  - Phase 3: Frontend Logging (error capture, API client)
  - Phase 4: Admin UI (logs page, filtering, export)
  - Phase 5: Testing and Verification
- **When to use:**
  - Implementing logging features step-by-step
  - Understanding logging task dependencies
  - Finding specific implementation instructions
- **Beads Epic:** `home_security_intelligence-cfd`

### GitHub CI/CD Documentation

**2025-12-26-github-cicd-design.md**

- **Purpose:** GitHub CI/CD pipeline design with security scanning and performance analysis
- **Status:** APPROVED
- **Date:** 2025-12-26
- **Contents:**
  - Three-phase rollout (Security, Performance, Claude Code Review)
  - Runner strategy (GitHub-hosted vs self-hosted GPU)
  - Workflow triggers matrix
  - Security scanning tools (Dependabot, CodeQL, Trivy, Bandit, Semgrep, Gitleaks)
  - Performance metrics and thresholds
  - Complexity analysis tools (radon, wily, big-o)
  - Self-hosted runner setup and security
  - Container strategy (GitHub Container Registry)
  - Required PR status checks
- **When to use:**
  - Setting up or modifying CI/CD workflows
  - Understanding security scanning configuration
  - Configuring performance benchmarks
  - Setting up self-hosted runners

**2025-12-26-github-cicd-implementation.md**

- **Purpose:** Detailed implementation tasks for GitHub CI/CD
- **Status:** IN PROGRESS
- **Date:** 2025-12-26
- **Contents:**
  - Phase 1: Security scanning workflows
  - Phase 2: Performance benchmarking workflows
  - Phase 3: Self-hosted runner configuration
  - Phase 4: Container build and push workflows
  - Integration with existing pre-commit hooks
- **When to use:**
  - Implementing CI/CD features step-by-step
  - Understanding workflow file structure
  - Adding new checks to the pipeline

### Service Health Monitoring

**2025-12-26-service-health-monitoring-design.md**

- **Purpose:** Design for automatic health monitoring and recovery
- **Status:** APPROVED
- **Date:** 2025-12-26
- **Epic:** home_security_intelligence-a2v
- **Contents:**
  - ServiceManager abstraction (strategy pattern)
  - ShellServiceManager vs DockerServiceManager
  - ServiceHealthMonitor service
  - Health check loop with exponential backoff
  - WebSocket status broadcasts
  - Frontend ServiceStatusAlert component
  - Configuration settings
  - Task breakdown with priorities
  - Acceptance criteria
- **When to use:**
  - Implementing service health monitoring
  - Adding new monitored services
  - Understanding recovery strategies
  - Debugging service restart issues

### README Redesign

**2025-12-26-readme-redesign.md**

- **Purpose:** Plan for README.md restructuring
- **Status:** APPROVED
- **Date:** 2025-12-26
- **Contents:**
  - Target audiences (future self, contributors, deployers, showcase)
  - Design principles (problem-first, layered, scannable, visual)
  - 7-section structure outline
  - Visual assets needed (hero screenshot, architecture diagram)
  - Implementation notes
- **When to use:**
  - Restructuring the README
  - Understanding documentation philosophy
  - Adding new README sections

## Relationship Between Files

### Design Spec -> Implementation Plan

1. Design spec defines **WHAT** to build (architecture, schema, APIs, UI)
2. Implementation plan defines **HOW** to build it (task breakdown, order, TDD)
3. Design spec is reference during implementation
4. Implementation plan tracks progress

### Using Both Together

**When implementing a feature:**

1. Check implementation plan for task requirements
2. Check design spec for detailed specifications
3. Write tests based on design spec contracts
4. Implement code following design patterns
5. Verify against design spec acceptance criteria

**Example: Implementing Events API**

1. Implementation plan says: "Implement events API endpoints" (Phase 5)
2. Design spec shows: `/api/events` with GET/PATCH endpoints (lines 130-133)
3. Design spec shows: Schema with filters (camera, risk level, date)
4. Write tests for each endpoint
5. Implement endpoints matching spec
6. Verify WebSocket integration from design spec

## Important Sections to Reference

### For Backend Development

**Database Schema** (design spec, lines 67-122)

- SQLAlchemy model definitions
- Foreign key relationships
- Index requirements
- Timestamp fields

**API Endpoints** (design spec, lines 124-169)

- HTTP methods and paths
- Request/response shapes
- Query parameters
- WebSocket channels

**Processing Pipeline** (design spec, lines 172-200)

- Service responsibilities
- Timing/debounce requirements
- Redis queue structure
- Error handling

### For Frontend Development

**UI Design** (design spec, lines 248-263)

- Color palette
- Typography
- Spacing
- Component library (Tremor + Headless UI)

**UI Mockups** (design spec, lines 426-553)

- Layout wireframes
- Component hierarchy
- Navigation structure
- Interaction patterns

**API Client** (design spec, lines 124-169)

- Endpoints to consume
- WebSocket channels
- Data shapes

### For AI Pipeline Development

**Nemotron Prompt** (design spec, lines 202-239)

- Complete prompt template
- Risk scoring guidelines
- Input/output format
- Context factors

**Processing Pipeline** (design spec, lines 172-200)

- File watcher triggers
- Detection flow
- Batch aggregation logic
- Analysis timing

### For CI/CD Development

**GitHub CI/CD Design** (2025-12-26-github-cicd-design.md)

- Workflow structure and triggers
- Security scanning configuration
- Performance benchmark thresholds
- Self-hosted runner setup

## Key Design Decisions Documented

### Batch Processing (Design Spec)

- **Decision:** 90s window + 30s idle timeout
- **Rationale:** Balance between real-time alerts and LLM context
- **Location:** Lines 189, 403

### Risk Scoring (Design Spec)

- **Decision:** LLM-determined via Nemotron
- **Rationale:** Context-aware analysis vs rigid rules
- **Location:** Lines 202-239

### Deployment Model (Design Spec)

- **Decision:** Hybrid (Docker for services, native for GPU models)
- **Rationale:** GPU access complexity in Docker
- **Location:** Lines 19-20, 340-384

### Database Choice (Design Spec)

- **Decision:** SQLite + Redis
- **Rationale:** Single-user, local deployment, no remote access
- **Location:** Lines 15, 67-122

### Service Health Recovery (2025-12-26-service-health-monitoring-design.md)

- **Decision:** Strategy pattern for shell vs Docker restart
- **Rationale:** Support both dev (shell scripts) and prod (Docker) environments
- **Location:** ServiceManager abstraction

### CI/CD Strategy (2025-12-26-github-cicd-design.md)

- **Decision:** Three-phase rollout with GitHub-hosted and self-hosted runners
- **Rationale:** Security scanning on all PRs, GPU tests only on safe contexts
- **Location:** Runner Strategy section

## Conventions

### Document Structure

- Date-prefixed filenames: `YYYY-MM-DD-description.md`
- Headers with metadata (Date, Status)
- Code blocks for all technical content
- Tables for structured data
- ASCII diagrams for architecture

### Design Spec Sections

1. Overview
2. Technology Stack
3. Architecture
4. Data Flow
5. Database Schema
6. API Endpoints
7. Processing Pipeline
8. Prompts/Configuration
9. UI Design
10. Deployment
11. Deferred Features

### Implementation Plan Sections

1. Issue Tracking
2. Epic Overview
3. Phase Breakdown
4. TDD Workflow
5. Future Ideas

## Entry Points for Agents

### Starting Work on a New Phase

1. **Read implementation plan** - Find phase tasks
2. **Read design spec** - Understand requirements
3. Check `bd list --label phase-N` for task details
4. Implement following TDD workflow

### Understanding a Feature

1. **Search implementation plan** - Find which phase
2. **Read design spec section** - Get detailed requirements
3. Look at related code in codebase
4. Check tests for examples

### Clarifying Requirements

1. **Check design spec first** - Most detailed source
2. If not found, check implementation plan
3. If still unclear, check existing code patterns
4. If still unclear, ask user for clarification

## Implementation Progress

### Completed Phases (1-5)

**Phase 1: Project Setup (P0)** - COMPLETE

- Directory structures, Docker, environment, dependencies
- All 7 tasks completed

**Phase 2: Database & Layout Foundation (P1)** - COMPLETE

- SQLAlchemy models, Redis connection, Tailwind theme, app layout
- All 6 tasks completed

**Phase 3: Core APIs & Components (P2)** - COMPLETE

- Cameras API, system API, WebSocket hooks, API client, basic UI components
- All 11 tasks completed

**Phase 4: AI Pipeline (P3/P4)** - COMPLETE

- File watcher, RT-DETRv2 wrapper, detector client, batch aggregator, Nemotron analyzer
- All 13 tasks completed
- Test coverage: Backend 98.54% (335 tests), Frontend 98.95% (233 tests)

**Phase 5: Events & Real-time (P4)** - COMPLETE

- Events API, detections API, WebSocket channels, GPU monitor, cleanup service
- All 9 tasks completed

### Current Phase (6)

**Phase 6: Dashboard Components (P3)** - IN PROGRESS

- Risk gauge, camera grid, live activity feed, GPU stats, EventCard
- 7 tasks remaining

### Remaining Phases (7-8)

**Phase 7: Pages & Modals (P4)** - NOT STARTED

- Main dashboard, event timeline, event detail modal, settings pages
- 6 tasks

**Phase 8: Integration & E2E (P4)** - NOT STARTED

- Unit tests, E2E tests, deployment verification, documentation
- 8 tasks (Docker deployment verification already completed)

### Implementation Notes

- All design decisions followed
- Additional improvements:
  - Enhanced error handling
  - More comprehensive tests (98%+ coverage)
  - Better type hints and validation
  - Production Docker configuration with multi-stage builds
  - Comprehensive deployment testing scripts

## Related Documentation

- **Root AGENTS.md:** Project overview and entry points
- **docs/AGENTS.md:** Documentation directory guide
- **docs/ROADMAP.md:** Post-MVP roadmap ideas (pursue after Phases 1-8 complete)
- **docs/AI_SETUP.md:** AI services setup and troubleshooting guide
- **docs/DOCKER_DEPLOYMENT.md:** Docker Compose deployment guide
- **CLAUDE.md:** Claude Code instructions and workflow
- **README.md:** Project overview and quick start guide
