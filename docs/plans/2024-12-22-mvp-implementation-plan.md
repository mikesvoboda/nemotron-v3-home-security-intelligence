# Home Security Intelligence MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered home security monitoring dashboard that processes camera uploads through RT-DETRv2 for object detection and Nemotron for contextual risk assessment.

**Architecture:** File watcher monitors FTP uploads, RT-DETRv2 detects objects, batches aggregate in Redis, Nemotron analyzes risk, results display in React dashboard via WebSocket.

**Tech Stack:** React/TypeScript + Tailwind/Tremor (frontend), FastAPI + SQLite + Redis (backend), RT-DETRv2 + Nemotron/llama.cpp (AI), Docker Compose (deployment)

---

## Issue Tracking

All tasks are tracked in `bd` (beads). Use these commands:

```bash
bd ready                    # Find available work
bd show <id>               # View task details
bd update <id> --status in_progress  # Claim work
bd close <id>              # Complete work
bd epic status             # View epic progress
bd sync                    # Sync with git
```

---

## Epic Overview

| Epic ID | Name | Tasks |
|---------|------|-------|
| home_security_intelligence-337 | Project Setup & Infrastructure | 8 |
| home_security_intelligence-7z7 | Backend Core - FastAPI & Database | 18 |
| home_security_intelligence-61l | AI Pipeline - RT-DETRv2 & Nemotron | 13 |
| home_security_intelligence-m9u | Frontend Dashboard - React UI | 20 |
| home_security_intelligence-fax | Integration & E2E Testing | 8 |

**Total: 67 tasks** (includes 14 TDD test tasks)

---

## Execution Phases

Tasks are organized into **8 execution phases** using labels. Complete phases in order.

### Phase 1: Project Setup (P0) - 7 tasks
```bash
bd list --label phase-1
```
- Create backend directory structure
- Create frontend directory structure
- Create Docker Compose configuration
- Create environment configuration
- Create AI model startup scripts
- Create backend requirements.txt
- Create frontend package.json

### Phase 2: Database & Layout Foundation (P1) - 6 tasks
```bash
bd list --label phase-2
```
- Implement SQLite database models
- Implement database connection and migrations
- Implement Redis connection
- Configure Tailwind with NVIDIA theme
- Implement app layout with sidebar navigation
- **TDD:** Write tests for database models

### Phase 3: Core APIs & Components (P2) - 11 tasks
```bash
bd list --label phase-3
```
- Implement cameras API endpoints
- Implement system API endpoints
- Implement media serving endpoint
- Implement API client service
- Implement WebSocket hooks
- Implement BoundingBoxOverlay component
- Implement RiskBadge component
- **TDD:** Write tests for cameras API
- **TDD:** Write tests for system API
- **TDD:** Write tests for API client
- **TDD:** Write tests for RiskBadge component

### Phase 4: AI Pipeline (P3/P4) - 13 tasks
```bash
bd list --label phase-4
```
- Implement file watcher service (with debounce & integrity checks)
- Implement RT-DETRv2 inference wrapper
- Implement detector client service
- Implement batch aggregator service
- Implement Nemotron analyzer service
- Implement Nemotron prompt template
- Configure llama.cpp server for Nemotron
- Implement thumbnail generation with bounding boxes
- Create model download script
- **TDD:** Write tests for file watcher service
- **TDD:** Write tests for detector client
- **TDD:** Write tests for batch aggregator
- **TDD:** Write tests for Nemotron analyzer

### Phase 5: Events & Real-time (P4) - 9 tasks
```bash
bd list --label phase-5
```
- Implement events API endpoints
- Implement detections API endpoints
- Implement WebSocket event channel
- Implement WebSocket system channel
- Implement GPU monitor service
- Implement data cleanup service
- Implement 'Fast Path' high-confidence alerts
- **TDD:** Write tests for events API
- **TDD:** Write tests for Fast Path alerts
- **TDD:** Write tests for detections API
- **TDD:** Write tests for WebSocket channels

### Phase 6: Dashboard Components (P3) - 7 tasks
```bash
bd list --label phase-6
```
- Implement circular Risk Gauge component
- Implement Live Activity Feed component
- Implement Camera Grid component
- Implement GPU Stats component
- Implement EventCard component
- **TDD:** Write tests for Dashboard components
- **TDD:** Write tests for EventCard component

### Phase 7: Pages & Modals (P4) - 6 tasks
```bash
bd list --label phase-7
```
- Implement main Dashboard page
- Implement Event Timeline page
- Implement Event Detail Modal
- Implement Settings page - Cameras tab
- Implement Settings page - Processing tab
- Implement Settings page - AI Models tab

### Phase 8: Integration & E2E (P4) - 8 tasks
```bash
bd list --label phase-8
```
- Create backend unit tests
- Create frontend component tests
- Create E2E pipeline integration test
- Test Docker Compose deployment
- Test native AI model startup
- Create seed cameras script
- Create project README
- Create setup script
- Implement basic API Key authentication middleware
- **TDD:** Write tests for API Key middleware

---

## TDD Workflow

Tasks labeled `tdd` are test-first tasks. For each feature:

1. **Write failing test first** (tdd task)
2. **Implement feature** (feature task)
3. **Verify tests pass**
4. **Commit both together**

Find all TDD tasks:
```bash
bd list --label tdd
```

---

## NVIDIA Persona Perspectives & Future Roadmap

This project leverages the NVIDIA AI stack (RT-DETRv2 + Nemotron). Below are strategic perspectives from various NVIDIA personas on how this platform can evolve.

### 1. The Edge AI Developer (GTC/Developer Relations)
*   **Perspective:** Showcase the transition from "Object Detection" to "Intent Recognition".
*   **Strategic Idea:** **Spatial Context Injection**. Enhance the prompt to Nemotron by including spatial relationships (e.g., "Person is 2ft from Window, crouched"). This demonstrates Nemotron's superior reasoning capabilities in interpreting intent (e.g., "potential reconnaissance" vs. "routine maintenance") beyond simple bounding boxes.

### 2. The NIM Product Manager (Inference Microservices)
*   **Perspective:** Standardize deployment and maximize GPU utilization.
*   **Strategic Idea:** **NVIDIA NIM Migration**. Replace the local `llama.cpp` server with an **NVIDIA NIM** container. This shift allows the system to scale from a single RTX A5500 to multi-GPU clusters, providing enterprise-grade throughput and unified API management for industrial-scale monitoring (e.g., 50+ high-res streams).

### 3. The Digital Twin Architect (Omniverse)
*   **Perspective:** Bridge the gap between 2D monitoring and 3D spatial awareness.
*   **Strategic Idea:** **USD Event Reconstruction**. Have Nemotron generate **Universal Scene Description (USD)** snippets describing detections. These snippets can be fed into an Omniverse Digital Twin of the building to reconstruct and "replay" security events in a 3D simulated environment for forensic analysis from any camera angle.

### 4. The Cybersecurity Engineer (Trustworthy AI)
*   **Perspective:** Move from reactive alerts to proactive threat intelligence.
*   **Strategic Idea:** **Baseline Anomaly Scoring**. Implement a "Baseline of Normalcy" where Nemotron learns routine house patterns (e.g., "Deliveries occur between 10am-4pm"). If a detection occurs at an anomalous time or location, Nemotron reasons about the *contextual anomaly* to escalate risk, even if the detected object (e.g., a person) is partially obscured.

### 5. The RTX Marketing Lead (AI at Home)
*   **Perspective:** Democratize "Personal AI" for the GeForce ecosystem.
*   **Strategic Idea:** **"Chat with your Security"**. Implement a RAG (Retrieval-Augmented Generation) layer allowing users to query their security history: "Hey Nemotron, did any vehicles I don't recognize park in the driveway while I was at work today?" This transforms the dashboard from a passive feed into a proactive security consultant.