---
title: Architecture Overview
description: High-level system design, technology stack, data flow, and component responsibilities
last_updated: 2025-12-30
source_refs:
  - backend/main.py
  - backend/api/routes/cameras.py
  - backend/api/routes/events.py
  - backend/api/routes/detections.py
  - backend/api/routes/system.py
  - backend/services/file_watcher.py:FileWatcher
  - backend/services/detector_client.py:DetectorClient
  - backend/services/batch_aggregator.py:BatchAggregator
  - backend/services/nemotron_analyzer.py:NemotronAnalyzer
  - backend/services/event_broadcaster.py:EventBroadcaster
  - backend/services/gpu_monitor.py:GPUMonitor
  - backend/services/health_monitor.py:ServiceHealthMonitor
  - backend/models/camera.py:Camera
  - backend/models/detection.py:Detection
  - backend/models/event.py:Event
  - frontend/src/hooks/useWebSocket.ts
  - frontend/src/hooks/useEventStream.ts
  - ai/rtdetr/model.py
  - ai/nemotron/AGENTS.md
---

# Architecture Overview

> **Last Updated:** 2025-12-30
> **Target Audience:** Future maintainers, technical contributors

---

## System Purpose

Home Security Intelligence transforms commodity IP cameras into an intelligent threat detection system. Rather than simply alerting when motion is detected, the system uses AI to understand _what_ is happening and _why_ it might be concerning.

**Problem solved:** Traditional security cameras generate endless motion alerts with no context. A person walking their dog and a stranger approaching at 2 AM both trigger the same notification. This system provides contextual risk assessment using AI, turning raw camera feeds into actionable security intelligence.

**Key value proposition:**

- **Contextual alerts:** Not just "person detected" but "unfamiliar person approaching back entrance at 2 AM, risk: high"
- **Batch reasoning:** Groups multiple detections into coherent events for better context
- **Fast path:** High-confidence critical detections bypass batching for immediate alerts
- **Local processing:** All AI inference runs locally on your hardware, no cloud dependencies

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Cameras["Camera Layer"]
        CAM1[Foscam Camera 1]
        CAM2[Foscam Camera 2]
        CAM3[Foscam Camera N]
    end

    subgraph FTP["FTP Upload"]
        FTPS["/export/foscam/{camera}/"]
    end

    subgraph Docker["Docker Services"]
        direction TB
        FE["Frontend<br/>React + Vite<br/>:5173"]
        BE["Backend<br/>FastAPI<br/>:8000"]
        RD["Redis<br/>:6379"]
    end

    subgraph GPU["Containerized GPU Services"]
        DET["RT-DETRv2<br/>Object Detection<br/>:8090"]
        LLM["Nemotron LLM<br/>Risk Analysis<br/>:8091"]
    end

    subgraph Storage["Persistent Storage"]
        DB[(PostgreSQL<br/>security)]
        FS[("Filesystem<br/>thumbnails/")]
    end

    CAM1 & CAM2 & CAM3 -->|FTP Upload| FTPS
    FTPS -->|FileWatcher| BE
    BE <-->|Queues & Pub/Sub| RD
    BE -->|HTTP /detect| DET
    BE -->|HTTP /completion| LLM
    BE <-->|SQLAlchemy| DB
    BE -->|PIL/Pillow| FS
    FE <-->|REST API| BE
    FE <-->|WebSocket| BE
```

---

## Technology Stack

| Layer                | Technology       | Version | Why This Choice                                                                |
| -------------------- | ---------------- | ------- | ------------------------------------------------------------------------------ |
| **Frontend**         | React            | 18.2    | Industry standard, excellent ecosystem, component model fits dashboard UI      |
|                      | TypeScript       | 5.3     | Type safety catches bugs early, better IDE support, self-documenting code      |
|                      | Tailwind CSS     | 3.4     | Utility-first approach, dark theme customization, responsive design            |
|                      | Tremor           | 3.17    | Pre-built data visualization components (charts, gauges) for dashboards        |
|                      | Vite             | 5.0     | Fast dev server with HMR, modern bundling, excellent DX                        |
| **Backend**          | Python           | 3.11+   | AI/ML ecosystem (PyTorch, transformers), async support, rapid development      |
|                      | FastAPI          | 0.104+  | Modern async framework, automatic OpenAPI docs, type hints, WebSocket support  |
|                      | SQLAlchemy       | 2.0     | Async ORM, excellent PostgreSQL support, type-safe queries with `Mapped` hints |
|                      | Pydantic         | 2.0     | Request validation, settings management, schema generation                     |
| **Database**         | PostgreSQL       | 15+     | Concurrent writes, JSONB, full-text search, proper transaction isolation       |
|                      | Redis            | 7.x     | Fast pub/sub for WebSocket, reliable queues for pipeline, ephemeral cache      |
| **AI - Detection**   | RT-DETRv2        | -       | Real-time transformer detector, 30-50ms inference, COCO-trained                |
|                      | PyTorch          | 2.x     | GPU acceleration, HuggingFace Transformers integration                         |
| **AI - Reasoning**   | Nemotron Mini 4B | Q4_K_M  | Small but capable LLM, runs on consumer GPUs, instruction-tuned                |
|                      | llama.cpp        | -       | Efficient inference, GGUF format, GPU offloading, HTTP API                     |
| **Containerization** | Docker Compose   | 2.x     | Multi-service orchestration, health checks, networking                         |
| **Monitoring**       | Prometheus       | 2.48    | Time-series metrics, optional monitoring stack                                 |
|                      | Grafana          | 10.2    | Dashboards for system monitoring                                               |

---

## Component Responsibilities

### Backend Components

| Component               | Location                  | Responsibility                                                      |
| ----------------------- | ------------------------- | ------------------------------------------------------------------- |
| **FastAPI App**         | `backend/main.py`         | HTTP/WebSocket server, middleware, lifespan management              |
| **API Routes**          | `backend/api/routes/`     | REST endpoints for cameras, events, detections, system, media, logs |
| **Pydantic Schemas**    | `backend/api/schemas/`    | Request/response validation, OpenAPI documentation                  |
| **Middleware**          | `backend/api/middleware/` | Authentication (optional), request ID propagation                   |
| **ORM Models**          | `backend/models/`         | SQLAlchemy models: Camera, Detection, Event, GPUStats, Log, APIKey  |
| **Core Infrastructure** | `backend/core/`           | Config, database, Redis, logging, metrics                           |

### Service Layer (AI Pipeline)

| Service                   | Location                                  | Responsibility                                         |
| ------------------------- | ----------------------------------------- | ------------------------------------------------------ |
| **FileWatcher**           | `backend/services/file_watcher.py`        | Monitor camera directories, debounce, queue new images |
| **DedupeService**         | `backend/services/dedupe.py`              | Prevent duplicate processing via content hashes        |
| **DetectorClient**        | `backend/services/detector_client.py`     | HTTP client for RT-DETRv2, store detections            |
| **BatchAggregator**       | `backend/services/batch_aggregator.py`    | Group detections into time-windowed batches            |
| **NemotronAnalyzer**      | `backend/services/nemotron_analyzer.py`   | LLM risk analysis, event creation                      |
| **ThumbnailGenerator**    | `backend/services/thumbnail_generator.py` | Bounding box overlays, preview images                  |
| **EventBroadcaster**      | `backend/services/event_broadcaster.py`   | WebSocket event distribution via Redis pub/sub         |
| **SystemBroadcaster**     | `backend/services/system_broadcaster.py`  | Periodic system status broadcasts                      |
| **GPUMonitor**            | `backend/services/gpu_monitor.py`         | NVIDIA GPU metrics via pynvml                          |
| **CleanupService**        | `backend/services/cleanup_service.py`     | Data retention enforcement                             |
| **HealthMonitor**         | `backend/services/health_monitor.py`      | Service health checks, auto-recovery                   |
| **RetryHandler**          | `backend/services/retry_handler.py`       | Exponential backoff, dead-letter queues                |
| **PipelineWorkerManager** | `backend/services/pipeline_workers.py`    | Background worker lifecycle management                 |

### Frontend Components

| Component            | Location                             | Responsibility                                        |
| -------------------- | ------------------------------------ | ----------------------------------------------------- |
| **DashboardPage**    | `frontend/src/components/dashboard/` | Main view with risk gauge, camera grid, activity feed |
| **EventTimeline**    | `frontend/src/components/events/`    | Chronological event list with filtering               |
| **EventDetailModal** | `frontend/src/components/events/`    | Full event details, detections, reasoning             |
| **SettingsPage**     | `frontend/src/components/settings/`  | Camera management, AI status, processing config       |
| **LogsDashboard**    | `frontend/src/components/logs/`      | System logs with filtering and statistics             |
| **Layout**           | `frontend/src/components/layout/`    | Header, sidebar, navigation                           |
| **API Client**       | `frontend/src/services/api.ts`       | Type-safe REST API wrapper                            |
| **WebSocket Hooks**  | `frontend/src/hooks/`                | useWebSocket, useEventStream, useSystemStatus         |

### AI Services

| Service              | Location             | Responsibility                                       |
| -------------------- | -------------------- | ---------------------------------------------------- |
| **RT-DETRv2 Server** | `ai/rtdetr/model.py` | Object detection inference, security-class filtering |
| **Nemotron LLM**     | `ai/nemotron/`       | Risk reasoning via llama.cpp server                  |

---

## Communication Patterns

### REST API

Used for: CRUD operations, data queries, configuration

| Endpoint Pattern               | Methods            | Purpose                          |
| ------------------------------ | ------------------ | -------------------------------- |
| `/api/cameras`                 | GET, POST          | List/create cameras              |
| `/api/cameras/{id}`            | GET, PATCH, DELETE | Single camera operations         |
| `/api/events`                  | GET                | List events with filtering       |
| `/api/events/{id}`             | GET, PATCH         | Get/update event (mark reviewed) |
| `/api/detections`              | GET                | List detections with filtering   |
| `/api/system/health`           | GET                | Comprehensive health check       |
| `/api/system/gpu`              | GET                | GPU statistics                   |
| `/api/media/thumbnails/{file}` | GET                | Serve detection thumbnails       |
| `/api/logs`                    | GET                | List system logs                 |
| `/api/dlq/*`                   | GET, POST, DELETE  | Dead-letter queue management     |
| `/api/metrics`                 | GET                | Prometheus metrics               |

### WebSocket

Used for: Real-time updates without polling

| Channel    | Endpoint     | Message Type                         | Frequency         |
| ---------- | ------------ | ------------------------------------ | ----------------- |
| **Events** | `/ws/events` | Security events                      | On event creation |
| **System** | `/ws/system` | System status (GPU, cameras, health) | Every 5 seconds   |

**Message Format:**

```json
{
  "type": "event",
  "data": {
    "id": 123,
    "camera_id": "front_door",
    "risk_score": 75,
    "risk_level": "high",
    "summary": "Person detected..."
  }
}
```

### Redis Pub/Sub

Used for: Multi-instance WebSocket broadcasting

| Channel           | Publisher        | Subscribers         | Purpose                                    |
| ----------------- | ---------------- | ------------------- | ------------------------------------------ |
| `security_events` | NemotronAnalyzer | EventBroadcaster(s) | Distribute events to all backend instances |

### Redis Queues (Lists)

Used for: Reliable async job processing

| Queue                 | Producer        | Consumer             | Data                                   |
| --------------------- | --------------- | -------------------- | -------------------------------------- |
| `detection_queue`     | FileWatcher     | DetectionQueueWorker | `{camera_id, file_path, timestamp}`    |
| `analysis_queue`      | BatchAggregator | AnalysisQueueWorker  | `{batch_id, camera_id, detection_ids}` |
| `dlq:detection_queue` | RetryHandler    | Manual/API           | Failed detection jobs                  |
| `dlq:analysis_queue`  | RetryHandler    | Manual/API           | Failed analysis jobs                   |

### HTTP (Internal Services)

Used for: AI inference requests

| Service   | Endpoint      | Method | Request                             | Response                                    |
| --------- | ------------- | ------ | ----------------------------------- | ------------------------------------------- |
| RT-DETRv2 | `/detect`     | POST   | Multipart image                     | `{detections: [{class, confidence, bbox}]}` |
| RT-DETRv2 | `/health`     | GET    | -                                   | `{status, model_loaded, cuda_available}`    |
| Nemotron  | `/completion` | POST   | `{prompt, temperature, max_tokens}` | `{content: "..."}`                          |
| Nemotron  | `/health`     | GET    | -                                   | `{status: "ok"}`                            |

---

## Deployment Topology

```mermaid
flowchart TB
    subgraph Host["Host Machine (with GPU)"]
        subgraph Docker["Docker Compose Network"]
            FE["Frontend Container<br/>Node 20 Alpine<br/>Port 5173 (dev) / 80 (prod)"]
            BE["Backend Container<br/>Python 3.11<br/>Port 8000"]
            RD["Redis Container<br/>Redis 7 Alpine<br/>Port 6379"]
        end

        subgraph GPUContainers["Containerized GPU Services (CDI)"]
            DET["RT-DETRv2 Container<br/>PyTorch + CUDA<br/>Port 8090<br/>~650 MiB VRAM"]
            LLM["Nemotron Container<br/>llama.cpp<br/>Port 8091<br/>~14.7 GB VRAM"]
        end

        subgraph Storage["Persistent Storage"]
            VOL1["PostgreSQL<br/>database volume"]
            VOL2["/export/foscam/<br/>Camera uploads (RO)"]
            VOL3["redis_data<br/>Redis persistence"]
        end

        GPU["NVIDIA GPU<br/>RTX A5500 (24GB)<br/>CUDA 12.0+"]
    end

    FE <--> BE
    BE <--> RD
    BE -->|localhost:8090| DET
    BE -->|localhost:8091| LLM
    DET --> GPU
    LLM --> GPU
    BE --> VOL1
    BE --> VOL2
    RD --> VOL3
```

### What Runs Where

| Component      | Deployment                      | Why                                      |
| -------------- | ------------------------------- | ---------------------------------------- |
| **Frontend**   | Podman (dev: Vite, prod: Nginx) | No GPU needed, isolated environment      |
| **Backend**    | Podman                          | No GPU needed, isolated environment      |
| **Redis**      | Podman                          | No GPU needed, ephemeral data acceptable |
| **PostgreSQL** | Podman                          | Database isolation, volume persistence   |
| **RT-DETRv2**  | Podman (GPU via CDI)            | GPU access via NVIDIA Container Toolkit  |
| **Nemotron**   | Podman (GPU via CDI)            | GPU access via NVIDIA Container Toolkit  |

### Port Summary

| Port | Service         | Protocol | Exposed To                   |
| ---- | --------------- | -------- | ---------------------------- |
| 5173 | Frontend (dev)  | HTTP     | Browser                      |
| 80   | Frontend (prod) | HTTP     | Browser                      |
| 8000 | Backend API     | HTTP/WS  | Browser, Frontend container  |
| 6379 | Redis           | TCP      | Backend container only       |
| 8090 | RT-DETRv2       | HTTP     | Backend container, localhost |
| 8091 | Nemotron        | HTTP     | Backend container, localhost |

---

## Data Flow

### Complete Pipeline: Camera to Dashboard

```mermaid
sequenceDiagram
    participant CAM as Foscam Camera
    participant FTP as /export/foscam/
    participant FW as FileWatcher
    participant DQ as detection_queue
    participant DW as DetectionWorker
    participant DET as RT-DETRv2
    participant DB as PostgreSQL
    participant BA as BatchAggregator
    participant AQ as analysis_queue
    participant AW as AnalysisWorker
    participant LLM as Nemotron
    participant EB as EventBroadcaster
    participant WS as WebSocket
    participant UI as Dashboard

    CAM->>FTP: FTP upload image
    FTP->>FW: watchdog event (file created)
    FW->>FW: debounce (0.5s)
    FW->>FW: validate image (PIL)
    FW->>DQ: queue {camera_id, file_path}

    DQ->>DW: BLPOP (blocking pop)
    DW->>DW: dedupe check (Redis/DB)
    DW->>DET: POST /detect (image)
    DET->>DET: inference (30-50ms)
    DET-->>DW: {detections: [...]}
    DW->>DB: INSERT detections

    alt Fast Path (person > 90% confidence)
        DW->>LLM: immediate analysis
        LLM-->>DW: risk assessment
        DW->>DB: INSERT event (is_fast_path=true)
        DW->>EB: broadcast_event()
    else Normal Path
        DW->>BA: add_detection(camera_id, detection_id)
        BA->>BA: check batch timeout (90s window / 30s idle)
        BA->>AQ: queue {batch_id, detection_ids}
    end

    AQ->>AW: BLPOP
    AW->>DB: SELECT detections WHERE id IN (...)
    AW->>LLM: POST /completion (prompt)
    LLM->>LLM: inference (2-5s)
    LLM-->>AW: {risk_score, risk_level, summary, reasoning}
    AW->>DB: INSERT event
    AW->>EB: broadcast_event()

    EB->>WS: send to connected clients
    WS->>UI: {"type": "event", "data": {...}}
    UI->>UI: update activity feed
```

### Batching Logic

Why batch detections instead of analyzing each frame?

A single "person walks to door" scenario might generate 15 images over 30 seconds. Batching provides:

1. **Better context:** LLM sees the full sequence, not isolated frames
2. **Reduced API calls:** One LLM call per event, not per frame
3. **Coherent events:** User sees "Person approached door" not 15 separate alerts

**Batch timing:**

- **Window:** 90 seconds maximum per batch
- **Idle timeout:** 30 seconds of no activity closes batch early
- **Fast path:** High-confidence person detections (>90%) skip batching

### Fast Path Flow

Critical detections can bypass batching for immediate alerts:

```mermaid
flowchart TB
    D[Detection]
    D --> C{Confidence > 90%<br/>AND<br/>type = person?}
    C -->|Yes| FP[Fast Path<br/>Immediate LLM analysis]
    C -->|No| NP[Normal Path<br/>Add to batch]
    FP --> E1[Event created<br/>is_fast_path=true]
    NP --> B[Batch accumulates]
    B --> T{Timeout?}
    T -->|Yes| E2[Event created<br/>is_fast_path=false]
```

---

## Database Schema

```mermaid
erDiagram
    cameras ||--o{ detections : "has"
    cameras ||--o{ events : "has"

    cameras {
        string id PK "UUID"
        string name "Human-readable name"
        string folder_path "FTP upload path"
        string status "online/offline/error"
        datetime created_at
        datetime last_seen_at
    }

    detections {
        int id PK "Auto-increment"
        string camera_id FK
        string file_path "Original image"
        datetime detected_at
        string object_type "person/car/dog/etc"
        float confidence "0.0-1.0"
        int bbox_x "Bounding box"
        int bbox_y
        int bbox_width
        int bbox_height
        string thumbnail_path "With boxes drawn"
    }

    events {
        int id PK "Auto-increment"
        string batch_id "Groups detections"
        string camera_id FK
        datetime started_at
        datetime ended_at
        int risk_score "0-100 from LLM"
        string risk_level "low/medium/high/critical"
        text summary "LLM summary"
        text reasoning "LLM explanation"
        text detection_ids "JSON array"
        bool reviewed "User marked"
        text notes "User notes"
        bool is_fast_path "Bypassed batching"
    }

    gpu_stats {
        int id PK
        datetime recorded_at
        float gpu_utilization "0-100%"
        int memory_used "MB"
        int memory_total "MB"
        float temperature "Celsius"
        float inference_fps
    }

    logs {
        int id PK
        datetime timestamp
        string level "DEBUG/INFO/WARNING/ERROR/CRITICAL"
        string component "Logger name"
        text message
        string camera_id "Nullable"
        int event_id "Nullable"
        string request_id "Correlation ID"
        int detection_id "Nullable"
        int duration_ms "Nullable"
        json extra "Additional context"
        string source "backend/frontend"
    }

    api_keys {
        int id PK
        string key_hash "SHA-256"
        string name
        datetime created_at
        bool is_active
    }
```

### Key Indexes

| Table      | Index                       | Purpose                      |
| ---------- | --------------------------- | ---------------------------- |
| detections | (camera_id, detected_at)    | Camera-specific time queries |
| events     | started_at                  | Timeline queries             |
| events     | risk_score                  | High-risk filtering          |
| events     | reviewed                    | Workflow queries             |
| gpu_stats  | recorded_at                 | Time-series queries          |
| logs       | timestamp, level, component | Dashboard filters            |

---

## Component Interaction Diagram

```mermaid
flowchart TB
    subgraph Frontend["Frontend (React)"]
        DASH[DashboardPage]
        TL[EventTimeline]
        SET[SettingsPage]

        subgraph Hooks["Custom Hooks"]
            HWS[useWebSocket]
            HES[useEventStream]
            HSS[useSystemStatus]
        end

        subgraph Services["Services"]
            API[api.ts]
            LOG[logger.ts]
        end
    end

    subgraph Backend["Backend (FastAPI)"]
        subgraph Routes["API Routes"]
            RC[/cameras]
            RE[/events]
            RD[/detections]
            RS[/system]
            RM[/media]
            RW[/ws/*]
        end

        subgraph Pipeline["AI Pipeline"]
            FW[FileWatcher]
            DC[DetectorClient]
            BA[BatchAggregator]
            NA[NemotronAnalyzer]
            TG[ThumbnailGenerator]
        end

        subgraph Workers["Background Workers"]
            DW[DetectionWorker]
            AW[AnalysisWorker]
            BW[BatchTimeoutWorker]
            QW[QueueMetricsWorker]
        end

        subgraph Background["Background Services"]
            GPU[GPUMonitor]
            CL[CleanupService]
            HM[HealthMonitor]
            EB[EventBroadcaster]
            SB[SystemBroadcaster]
        end
    end

    subgraph External["External Services"]
        REDIS[(Redis)]
        POSTGRES[(PostgreSQL)]
        RTDETR[RT-DETRv2]
        NEMOTRON[Nemotron LLM]
    end

    %% Frontend connections
    DASH --> HES
    DASH --> HSS
    TL --> API
    SET --> API
    HES --> HWS
    HSS --> HWS
    HWS --> RW
    API --> RC & RE & RD & RS & RM

    %% Backend internal
    FW --> REDIS
    DW --> DC
    DC --> RTDETR
    DC --> POSTGRES
    DW --> BA
    BA --> REDIS
    AW --> NA
    NA --> NEMOTRON
    NA --> POSTGRES
    NA --> EB
    TG --> POSTGRES
    GPU --> POSTGRES
    GPU --> SB
    CL --> POSTGRES
    EB --> REDIS
    SB --> RW
    EB --> RW

    %% Routes to DB
    RC & RE & RD & RS --> POSTGRES
    RM --> POSTGRES
```

---

## Error Handling and Resilience

### Graceful Degradation

| Component | Failure Mode  | Fallback Behavior                                                 |
| --------- | ------------- | ----------------------------------------------------------------- |
| RT-DETRv2 | Unreachable   | DetectorClient returns empty list, skips detection                |
| Nemotron  | Unreachable   | NemotronAnalyzer returns default risk (50, medium)                |
| Redis     | Unreachable   | Deduplication fails open (allows processing), pub/sub unavailable |
| GPU       | Not available | GPUMonitor returns mock data                                      |

### Retry and Dead-Letter Queues

```mermaid
flowchart TB
    JOB[Job]
    JOB --> W[Worker]
    W --> P{Processing}
    P -->|Success| DONE[Complete]
    P -->|Fail| R{Retries < 3?}
    R -->|Yes| BACK[Exponential Backoff]
    BACK --> W
    R -->|No| DLQ[Dead Letter Queue]
    DLQ --> API["/api/dlq/*"]
    API --> REQUEUE[Manual Requeue]
    REQUEUE --> W
```

### Health Monitoring

The `HealthMonitor` service:

1. Periodically checks service health (RT-DETRv2, Nemotron, Redis)
2. On failure, attempts restart with exponential backoff
3. Broadcasts status changes via WebSocket
4. Gives up after max retries (prevents infinite restart loops)

---

## Security Model

### Current State (MVP)

| Aspect         | Implementation            | Rationale                            |
| -------------- | ------------------------- | ------------------------------------ |
| Authentication | Optional API key          | Single-user local deployment         |
| Authorization  | None                      | Single-user, no roles needed         |
| Media security | Path traversal prevention | Prevent escaping allowed directories |
| Network        | Local/trusted only        | Not designed for internet exposure   |

### Production Hardening (Recommended)

- Enable `API_KEY_ENABLED=true` with strong keys
- Use HTTPS for AI service endpoints
- Restrict CORS origins
- Add rate limiting
- Run behind reverse proxy with TLS
- Review `docs/ROADMAP.md` security hardening section

---

## Performance Characteristics

| Operation                 | Typical Latency | Notes                               |
| ------------------------- | --------------- | ----------------------------------- |
| RT-DETRv2 inference       | 30-50ms         | Per image, on RTX A5500             |
| Nemotron analysis         | 2-5s            | Per batch, depends on prompt length |
| WebSocket broadcast       | <10ms           | Redis pub/sub to clients            |
| Database query            | <5ms            | PostgreSQL with proper indexes      |
| Full pipeline (fast path) | ~3-6s           | Camera to dashboard notification    |
| Full pipeline (batched)   | 30-120s         | Depends on batch timeout settings   |

### Resource Usage

| Resource       | Typical Usage          |
| -------------- | ---------------------- |
| RT-DETRv2 VRAM | ~4GB                   |
| Nemotron VRAM  | ~3GB                   |
| Total GPU VRAM | ~7GB (fits 8GB+ cards) |
| Backend RAM    | ~500MB                 |
| Frontend RAM   | ~100MB                 |
| Redis RAM      | ~50MB                  |

---

## Configuration Summary

See `docs/RUNTIME_CONFIG.md` for complete reference.

**Key environment variables:**

```bash
# Database and Redis (PostgreSQL required)
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security
REDIS_URL=redis://localhost:6379/0

# AI Services
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091

# Detection
DETECTION_CONFIDENCE_THRESHOLD=0.5
FAST_PATH_CONFIDENCE_THRESHOLD=0.90
FAST_PATH_OBJECT_TYPES=["person"]

# Batching
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30

# Retention
RETENTION_DAYS=30
```

---

## Related Documentation

| Document                    | Purpose                                 |
| --------------------------- | --------------------------------------- |
| `docs/RUNTIME_CONFIG.md`    | Complete environment variable reference |
| `docs/DOCKER_DEPLOYMENT.md` | Docker deployment guide                 |
| `docs/AI_SETUP.md`          | AI services setup and troubleshooting   |
| `docs/ROADMAP.md`           | Post-MVP enhancement ideas              |
| `backend/AGENTS.md`         | Backend architecture details            |
| `frontend/AGENTS.md`        | Frontend architecture details           |
| `ai/AGENTS.md`              | AI pipeline details                     |

---

## Image Generation Prompts

The following prompts can be used with AI image generators (DALL-E, Midjourney, Stable Diffusion) to create professional diagrams for presentations or documentation.

### Prompt 1: System Architecture Diagram

**Dimensions:** 1600x900 (16:9 widescreen)

**Style:** Professional technical documentation, clean white/light gray background, modern enterprise software aesthetic, subtle shadows and gradients

**Prompt:**

```
Create a professional system architecture diagram for a home security AI system with the following components:

LAYOUT: Left-to-right data flow, clean spacing, professional enterprise style

LEFT SIDE - INPUT:
- Icon cluster of 3-4 security cameras (modern IP camera style)
- Arrow labeled "FTP Upload" pointing to a folder icon
- Folder labeled "/export/foscam/"

CENTER - PROCESSING LAYER (large rounded rectangle):
- Title: "Docker Services"
- Three boxes inside:
  1. "Frontend" box with React logo, port 5173
  2. "Backend" box with Python/FastAPI logo, port 8000
  3. "Redis" box with Redis logo, port 6379
- Show bidirectional arrows between Frontend and Backend
- Show bidirectional arrow between Backend and Redis

BOTTOM CENTER - AI SERVICES (separate rounded rectangle):
- Title: "Native GPU Services"
- GPU chip icon prominently displayed
- Two boxes:
  1. "RT-DETRv2 Object Detection" port 8090
  2. "Nemotron LLM Risk Analysis" port 8091
- Dashed arrow from Backend to these services labeled "host.docker.internal"

RIGHT SIDE - STORAGE:
- Database cylinder icon labeled "PostgreSQL"
- Folder icon labeled "Thumbnails"
- Arrows from Backend to storage

FAR RIGHT - OUTPUT:
- Browser window icon labeled "Dashboard"
- Show WebSocket connection from Frontend

COLOR SCHEME:
- NVIDIA Green (#76B900) for AI components
- Blue (#3B82F6) for containers
- Dark gray (#1A1A1A) for text
- Light backgrounds with subtle gradients
- Thin gray border lines connecting components

Include a small legend in bottom-right corner explaining icons.
```

### Prompt 2: Deployment Topology Visualization

**Dimensions:** 1400x800

**Style:** Infrastructure diagram style, isometric or 2.5D perspective, professional data center aesthetic

**Prompt:**

```
Create an isometric deployment topology diagram showing:

MAIN ELEMENT - Server Machine:
- Large server/workstation icon with visible GPU card
- Label: "Host Machine (GPU Server)"
- NVIDIA GPU prominently visible with green accent lighting

WITHIN THE SERVER (nested containers):

Docker Layer (blue container outline):
- Three stacked containers:
  1. Frontend container (React icon, port 5173/80)
  2. Backend container (Python icon, port 8000)
  3. Redis container (Redis icon, port 6379)
- Shared network shown as connecting lines between containers

Native Processes (green highlight, outside Docker):
- RT-DETRv2 process (port 8090) with arrow to GPU
- Nemotron LLM process (port 8091) with arrow to GPU

EXTERNAL CONNECTIONS:
- Camera icons (3-4) on left side, connected via network lines
- Browser icon on right side, connected to Frontend
- Storage icons (database, folder) at bottom

LABELS:
- Clear port numbers on each component
- "Docker Compose Network" label on container area
- "CUDA/GPU Access" label on native processes
- "host.docker.internal" label on connection between Docker and native

STYLE:
- Professional blues for Docker containers
- NVIDIA green for GPU and AI components
- Clean white/light background
- Subtle shadows for depth
- Modern tech company presentation style
```

### Prompt 3: Data Flow Visualization

**Dimensions:** 1800x600 (panoramic)

**Style:** Process flow diagram, clean infographic style with icons, timeline-based left-to-right flow

**Prompt:**

```
Create a horizontal data flow infographic showing security camera processing pipeline:

FLOW DIRECTION: Left to right, numbered steps

STEP 1 - CAPTURE (far left):
- Security camera icon
- Small image frames showing motion
- Label: "Camera FTP Upload"
- Timestamp indicator

STEP 2 - INGEST:
- Folder icon with incoming arrow
- Small "watching eye" icon
- Label: "FileWatcher"
- "0.5s debounce" indicator

STEP 3 - QUEUE:
- Redis logo with list icon
- Label: "Detection Queue"
- Small queue visualization (stacked items)

STEP 4 - DETECT:
- GPU chip icon glowing green
- Bounding box overlay on sample image
- Label: "RT-DETRv2"
- "30-50ms" timing indicator
- Output: person, car, dog icons with confidence bars

STEP 5 - BATCH (split path):
- Timer/clock icon
- Grouped detection thumbnails
- Label: "BatchAggregator"
- Two paths shown:
  - Normal: "90s window"
  - Fast: "High confidence bypass" (highlighted in orange)

STEP 6 - ANALYZE:
- Brain/AI chip icon (Nemotron)
- Thought bubble with risk assessment
- Label: "LLM Risk Analysis"
- Output: Risk gauge showing score

STEP 7 - NOTIFY (far right):
- WebSocket waves icon
- Dashboard preview
- Label: "Real-time Dashboard"
- Alert notification icon

VISUAL STYLE:
- Clean white background
- Icons in consistent style (outline or filled)
- NVIDIA green for AI processing steps
- Blue for data movement/queues
- Orange/red for high-risk indicators
- Connecting arrows with timing annotations
- Step numbers in circles above each stage
- Subtle timeline bar at bottom

Bottom of image: Key metrics bar showing "End-to-end: 3-6s (fast) / 30-120s (batched)"
```

---

_This document provides a comprehensive overview of the Home Security Intelligence system architecture. For implementation details, refer to the source code and component-specific AGENTS.md files._
