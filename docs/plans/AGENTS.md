# Plans Directory - Agent Guide

## Purpose

This directory contains design specifications and implementation plans that define the project architecture, requirements, and task breakdown. These documents serve as the source of truth for what to build and how.

## Directory Contents

```
plans/
├── AGENTS.md                                    # This file
├── 2024-12-21-dashboard-mvp-design.md          # MVP design specification
├── 2024-12-22-mvp-implementation-plan.md       # Task breakdown and phases
├── 2024-12-24-logging-system-design.md         # Logging architecture spec
├── 2024-12-24-logging-implementation-plan.md   # Logging implementation tasks
├── 2025-12-26-github-cicd-design.md            # CI/CD pipeline design
├── 2025-12-26-github-cicd-implementation.md    # CI/CD implementation tasks
├── 2025-12-26-service-health-monitoring-design.md  # Health monitoring design
└── 2025-12-26-readme-redesign.md               # README restructuring plan
```

## Key Files

### MVP Design and Implementation

**2024-12-21-dashboard-mvp-design.md**

Complete MVP design specification. This is the primary reference for architecture decisions.

| Section             | Lines   | Description                                        |
| ------------------- | ------- | -------------------------------------------------- |
| Technology Stack    | 10-20   | React, FastAPI, SQLite, Redis, RT-DETRv2, Nemotron |
| System Architecture | 22-57   | ASCII diagram of data flow                         |
| Data Flow           | 59-65   | 5-step processing pipeline                         |
| Database Schema     | 67-122  | cameras, detections, events, gpu_stats tables      |
| API Endpoints       | 124-169 | REST and WebSocket endpoints                       |
| Processing Pipeline | 172-200 | File watcher, detection, batching, analysis        |
| Nemotron Prompt     | 202-239 | LLM prompt template and risk guidelines            |
| UI Design           | 248-263 | Color scheme, layout, components                   |
| UI Mockups          | 426-553 | Dashboard, timeline, event detail, settings        |
| Deferred to v2      | 554-563 | Face recognition, notifications, RTSP, etc.        |

**When to use:** Understanding architecture, API contracts, database schema, UI requirements

**2024-12-22-mvp-implementation-plan.md**

Task breakdown organized into 8 execution phases with bd (beads) issue tracking.

| Phase | Label   | Tasks | Focus Area                                           |
| ----- | ------- | ----- | ---------------------------------------------------- |
| 1     | phase-1 | 7     | Project Setup (directories, Docker, environment)     |
| 2     | phase-2 | 6     | Database & Layout (SQLite, Redis, Tailwind)          |
| 3     | phase-3 | 11    | Core APIs & Components (cameras, system, WebSocket)  |
| 4     | phase-4 | 13    | AI Pipeline (file watcher, RT-DETRv2, Nemotron)      |
| 5     | phase-5 | 9     | Events & Real-time (events API, detections, cleanup) |
| 6     | phase-6 | 7     | Dashboard Components (risk gauge, camera grid, feed) |
| 7     | phase-7 | 6     | Pages & Modals (dashboard, timeline, event detail)   |
| 8     | phase-8 | 8     | Integration & E2E (tests, deployment, docs)          |

**When to use:** Finding task requirements, understanding phase dependencies

### Design Spec Detailed Sections

1. **Technology Stack** (lines 10-20)

   - React, FastAPI, SQLite, Redis, RT-DETRv2, Nemotron

2. **System Architecture** (lines 22-57)

   - ASCII diagram of data flow

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

**Implementation Plan Details**

- **Purpose:** Task breakdown and execution plan for MVP
- **Status:** IN PROGRESS (Phase 5 complete, Phase 6 in progress)
- **Date:** 2024-12-22
- **Last Updated:** 2025-12-27

### Logging System

**2024-12-24-logging-system-design.md**

Logging architecture specification with three output destinations:

- Console (human-readable)
- Rotating files (JSON format)
- SQLite (queryable via admin UI)

**2024-12-24-logging-implementation-plan.md**

Implementation tasks for logging system in 5 phases:

1. Backend Foundation
2. Service Integration
3. Frontend Logging
4. Admin UI
5. Testing and Verification

### GitHub CI/CD

**2025-12-26-github-cicd-design.md**

CI/CD pipeline design with:

- Three-phase rollout (Security, Performance, Claude Code Review)
- Security scanning tools (Dependabot, CodeQL, Trivy, Bandit, Semgrep, Gitleaks)
- Performance benchmarking and complexity analysis
- Self-hosted GPU runner configuration

**2025-12-26-github-cicd-implementation.md**

Implementation tasks for CI/CD workflows:

- Phase 1: Security scanning workflows
- Phase 2: Performance benchmarking
- Phase 3: Self-hosted runner configuration
- Phase 4: Container build and push

### Service Health Monitoring

**2025-12-26-service-health-monitoring-design.md**

Auto-recovery and health monitoring design:

- ServiceManager abstraction (strategy pattern)
- ShellServiceManager vs DockerServiceManager
- Health check loop with exponential backoff
- WebSocket status broadcasts
- Frontend ServiceStatusAlert component

### README Redesign

**2025-12-26-readme-redesign.md**

Plan for README.md restructuring:

- Target audiences (future self, contributors, deployers, showcase)
- 7-section structure outline
- Visual assets needed

## Using These Documents

### When Implementing a Feature

1. **Check implementation plan** - Find which phase and task
2. **Read design spec section** - Get detailed requirements
3. Write tests based on design spec contracts
4. Implement following design patterns
5. Verify against acceptance criteria

### When Clarifying Requirements

1. **Check design spec first** - Most detailed source
2. If not found, check implementation plan
3. If still unclear, check existing code patterns
4. If still unclear, ask for clarification

### Design Spec Reference by Topic

| Topic               | Design Spec Section |
| ------------------- | ------------------- |
| Database schema     | lines 67-122        |
| API endpoints       | lines 124-169       |
| Processing pipeline | lines 172-200       |
| Nemotron prompt     | lines 202-239       |
| UI design           | lines 248-263       |
| UI mockups          | lines 426-553       |
| Docker config       | lines 340-384       |
| Environment vars    | lines 386-412       |

## Key Design Decisions

These decisions are documented in the design spec:

| Decision         | Value                        | Rationale                                 |
| ---------------- | ---------------------------- | ----------------------------------------- |
| Batch processing | 90s window + 30s idle        | Balance between real-time and LLM context |
| Risk scoring     | LLM-determined (0-100)       | Context-aware analysis vs rigid rules     |
| Deployment       | Hybrid (Docker + native GPU) | GPU access complexity in Docker           |
| Database         | SQLite + Redis               | Single-user, local deployment             |
| Auth             | None (MVP)                   | Single-user local deployment              |
| Retention        | 30 days                      | Configurable via environment              |

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

## Related Documentation

- **docs/AGENTS.md:** Documentation directory guide
- **docs/ROADMAP.md:** Post-MVP roadmap ideas
- **docs/decisions/:** Architecture Decision Records
- **CLAUDE.md:** Claude Code instructions
- **Root AGENTS.md:** Project overview
