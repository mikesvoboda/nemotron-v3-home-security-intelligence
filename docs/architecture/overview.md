---
title: Architecture Overview
description: High-level system design, technology stack, data flow, and component responsibilities
last_updated: 2026-10-02
source_refs:
  - backend/main.py
  - backend/api/routes/cameras.py
  - backend/api/routes/events.py
  - backend/api/routes/detections.py
  - backend/api/routes/system.py
  - backend/services/file_watcher.py:FileWatcher
  - backend/services/detector_client.py:DetectorClient
  - backend/services/batch_aggregator.py:BatchAggregator
  - backend/services/pipeline_factory.py:build_pipeline_analyzer
  - backend/services/vlm_analyzer.py:VlmAnalyzer
  - backend/services/key_frame_selector.py:select_key_frames
  - backend/services/vlm_specialists.py:collect_specialist_outputs
  - backend/services/osnet_loader.py:get_reid_handle
  - backend/services/face_recognizer_loader.py:get_face_leg_handles
  - backend/services/fast_alpr_loader.py:load_fast_alpr
  - backend/services/event_broadcaster.py:EventBroadcaster
  - backend/services/gpu_monitor.py:GPUMonitor
  - backend/services/health_monitor.py:ServiceHealthMonitor
  - backend/services/performance_collector.py:PerformanceCollector
  - backend/services/prompt_service.py:PromptService
  - backend/services/audit_logger.py:AuditService
  - backend/services/notification.py:NotificationService
  - backend/services/scene_change_detector.py:SceneChangeDetector
  - backend/services/video_processor.py:VideoProcessor
  - backend/models/camera.py:Camera
  - backend/models/detection.py:Detection
  - backend/models/event.py:Event
  - backend/models/event_verification.py:EventVerification
  - frontend/src/hooks/useWebSocket.ts
  - frontend/src/hooks/useEventStream.ts
  - frontend/src/hooks/useAIMetrics.ts
  - frontend/src/hooks/usePerformanceMetrics.ts
  - frontend/src/hooks/useHealthStatus.ts
  - frontend/src/hooks/useServiceStatus.ts
  - frontend/src/hooks/useConnectionStatus.ts
  - frontend/src/hooks/useModelZooStatus.ts
  - ai/gateway/main.py
  - ai/vlm/Dockerfile
---

# Architecture Overview

> **Target Audience:** Future maintainers, technical contributors

The hop-by-hop description of the live path, with file:line pins, lives in
[AI pipeline: current state](./ai-pipeline-current-state.md). This page is the map around it:
layers, stack, components, ports, and schema.

---

## System Purpose

Home Security Intelligence transforms commodity IP cameras into an intelligent threat detection system. Rather than simply alerting when motion is detected, the system uses AI to understand _what_ is happening and _why_ it might be concerning.

**Problem solved:** Traditional security cameras generate endless motion alerts with no context. A person walking their dog and a stranger approaching at 2 AM both trigger the same notification. This system provides contextual risk assessment using AI, turning raw camera feeds into actionable security intelligence.

**Key value proposition:**

- **Contextual verdicts:** Not just "person detected" — the VLM attaches a scene description, a verdict, and a risk score to each event
- **Batch reasoning:** Groups multiple detections into coherent events for better context
- **Specialist lookups:** Face, license-plate, and person re-identification results are gathered in-process and fed to the VLM as text
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
        FE["Frontend<br/>React + Vite<br/>:8444 HTTPS"]
        BE["Backend :8000<br/>FastAPI<br/>+ in-process specialist lookups<br/>faces · plates · person re-ID"]
        RD["Redis<br/>:6379"]
    end

    subgraph GPU["AI Services (GPU via CDI)"]
        GW["ai-gateway :8090<br/>Triton serving YOLO26<br/>(reid, threat resident)"]
        VLM["ai-vlm :8098<br/>llama.cpp llama-server<br/>Qwen3VL-8B-Instruct<br/>+ mmproj projector"]
    end

    subgraph Storage["Persistent Storage"]
        DB[(PostgreSQL<br/>security)]
        FS[("Filesystem<br/>thumbnails/")]
    end

    CAM1 & CAM2 & CAM3 -->|FTP Upload| FTPS

    FTPS -->|FileWatcher inotify| BE
    BE <-->|Streams & Pub/Sub| RD
    BE -->|POST /yolo26/detect| GW
    BE -->|POST /v1/chat/completions| VLM
    BE <-->|SQLAlchemy| DB
    BE -->|PIL/Pillow| FS
    FE <-->|REST API| BE
    FE <-->|WebSocket| BE
```

The system is organized into four layers:

- **Camera Layer:** Foscam IP cameras upload images via FTP
- **Application Layer:** React frontend + FastAPI backend. The backend also runs the three specialist lookup legs (faces, plates, person re-identification) in-process
- **AI Services:** 2 containers — `ai-gateway` (Triton serving YOLO26, port 8090) and `ai-vlm` (llama.cpp serving the Qwen3VL vision-language model, port 8098, in the default compose set)
- **Data Layer:** PostgreSQL, Redis, and filesystem storage

### The two AI services

| Service      | Port | Engine                   | Serves                                                             |
| ------------ | ---- | ------------------------ | ------------------------------------------------------------------ |
| `ai-gateway` | 8090 | Triton Inference Server  | `/yolo26` detection; `/enrich-lt` readiness + resident specialists |
| `ai-vlm`     | 8098 | llama.cpp `llama-server` | `/v1/chat/completions` on Qwen3VL-8B-Instruct-Q4_K_M + mmproj      |

`ai-vlm` is the only LLM service in the shipped stack.

---

## Technology Stack

| Layer                | Technology            | Version | Why This Choice                                                                |
| -------------------- | --------------------- | ------- | ------------------------------------------------------------------------------ |
| **Frontend**         | React                 | 19.2    | Industry standard, excellent ecosystem, component model fits dashboard UI      |
|                      | TypeScript            | 6.0     | Type safety catches bugs early, better IDE support, self-documenting code      |
|                      | Tailwind CSS          | 3       | Utility-first approach, dark theme customization, responsive design            |
|                      | Tremor                | 3.17    | Pre-built data visualization components (charts, gauges) for dashboards        |
|                      | Vite                  | 7.3     | Fast dev server with HMR, modern bundling, excellent DX                        |
| **Backend**          | Python                | 3.14    | AI/ML ecosystem (PyTorch, transformers), async support, rapid development      |
|                      | FastAPI               | ≥0.115  | Modern async framework, automatic OpenAPI docs, type hints, WebSocket support  |
|                      | SQLAlchemy            | 2.0     | Async ORM, excellent PostgreSQL support, type-safe queries with `Mapped` hints |
|                      | Pydantic              | 2.0     | Request validation, settings management, schema generation                     |
| **Database**         | PostgreSQL            | 16      | Concurrent writes, JSONB, full-text search, proper transaction isolation       |
|                      | Redis                 | 7.4     | Fast pub/sub for WebSocket, Streams for the pipeline, ephemeral cache          |
| **AI - Detection**   | YOLO26                | -       | Transformer detector served by ai-gateway via Triton (TensorRT engine)         |
|                      | Triton                | -       | Inference server hosting the shipped `{yolo26, reid, threat}` model set        |
|                      | PyTorch               | 2.x     | GPU acceleration for in-process specialist loaders                             |
| **AI - Reasoning**   | Qwen3VL-8B-Instruct   | Q4_K_M  | Vision-language model; scene description + verdict + risk score per batch      |
|                      | llama.cpp             | -       | GGUF inference with mmproj multimodal projector, HTTP API                      |
| **Containerization** | Docker/Podman Compose | -       | Multi-service orchestration, health checks, networking                         |
| **Monitoring**       | Prometheus            | 3.1     | Time-series metrics, monitoring stack (`docker.io/prom/prometheus:v3.1.0`)     |
|                      | Grafana               | custom  | Dashboards for system monitoring (built from `monitoring/grafana/Dockerfile`)  |

---

## Component Responsibilities

### Backend Components

| Component               | Location                  | Responsibility                                                                        |
| ----------------------- | ------------------------- | ------------------------------------------------------------------------------------- |
| **FastAPI App**         | `backend/main.py`         | HTTP/WebSocket server, middleware, lifespan management                                |
| **API Routes**          | `backend/api/routes/`     | REST endpoints for cameras, events, detections, system, media, logs                   |
| **Pydantic Schemas**    | `backend/api/schemas/`    | Request/response validation, OpenAPI documentation                                    |
| **Middleware**          | `backend/api/middleware/` | Authentication (optional), request ID propagation                                     |
| **ORM Models**          | `backend/models/`         | SQLAlchemy models: Camera, Detection, Event, EventVerification, GPUStats, Log, APIKey |
| **Core Infrastructure** | `backend/core/`           | Config, database, Redis, logging, metrics                                             |

### Service Layer (AI Pipeline)

| Service                    | Location                                     | Responsibility                                                                  |
| -------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------- |
| **FileWatcher**            | `backend/services/file_watcher.py`           | Monitor camera directories, debounce, queue new images                          |
| **DedupeService**          | `backend/services/dedupe.py`                 | Prevent duplicate processing via content hashes                                 |
| **DetectorClient**         | `backend/services/detector_client.py`        | HTTP client for YOLO26 via ai-gateway, store detections                         |
| **BatchAggregator**        | `backend/services/batch_aggregator.py`       | Group detections into time-windowed batches                                     |
| **pipeline_factory**       | `backend/services/pipeline_factory.py`       | Build the pipeline analyzer (one mode: VLM)                                     |
| **VlmAnalyzer**            | `backend/services/vlm_analyzer.py`           | Key-frame selection, specialist gather, VLM call, event write                   |
| **key_frame_selector**     | `backend/services/key_frame_selector.py`     | Pick 1-4 stills per batch for the VLM                                           |
| **vlm_specialists**        | `backend/services/vlm_specialists.py`        | Gather the three in-process specialist lookup legs                              |
| **osnet_loader**           | `backend/services/osnet_loader.py`           | OSNet person re-ID handle (residency-gated)                                     |
| **face_recognizer_loader** | `backend/services/face_recognizer_loader.py` | SCRFD + w600k face leg handles (residency-gated)                                |
| **fast_alpr_loader**       | `backend/services/fast_alpr_loader.py`       | FastALPR plate leg (loads on demand)                                            |
| **vlm_client**             | `backend/services/vlm_client.py`             | POST `/v1/chat/completions` to ai-vlm                                           |
| **ThumbnailGenerator**     | `backend/services/thumbnail_generator.py`    | Bounding box overlays, preview images                                           |
| **EventBroadcaster**       | `backend/services/event_broadcaster.py`      | WebSocket event distribution via Redis pub/sub                                  |
| **SystemBroadcaster**      | `backend/services/system_broadcaster.py`     | Periodic system status broadcasts                                               |
| **GPUMonitor**             | `backend/services/gpu_monitor.py`            | NVIDIA GPU metrics via pynvml                                                   |
| **CleanupService**         | `backend/services/cleanup_service.py`        | Data retention enforcement                                                      |
| **HealthMonitor**          | `backend/services/health_monitor.py`         | Service health checks, auto-recovery                                            |
| **RetryHandler**           | `backend/services/retry_handler.py`          | Exponential backoff, dead-letter queues                                         |
| **PipelineWorkerManager**  | `backend/services/pipeline_workers.py`       | Background worker lifecycle management                                          |
| **AlertEngine**            | `backend/services/alert_engine.py`           | Alert rule evaluation (rule-test endpoint only; no event auto-creates an Alert) |
| **ZoneService**            | `backend/services/zone_service.py`           | Geographic zone management for detections                                       |
| **BaselineService**        | `backend/services/baseline.py`               | Anomaly detection via activity baselines                                        |
| **ReidService**            | `backend/services/reid_service.py`           | Person re-identification gallery matching                                       |
| **ContextEnricher**        | `backend/services/context_enricher.py`       | Add contextual metadata (zones, baselines) to detection batches                 |
| **SceneChangeDetector**    | `backend/services/scene_change_detector.py`  | SSIM-based scene change detection between frames                                |
| **VideoProcessor**         | `backend/services/video_processor.py`        | Extract metadata and thumbnails from video files                                |
| **ModelZoo**               | `backend/services/model_zoo.py`              | On-demand loading of lookup models (plates, faces, OCR)                         |
| **PerformanceCollector**   | `backend/services/performance_collector.py`  | AI pipeline performance metrics collection                                      |
| **PromptService**          | `backend/services/prompt_service.py`         | Dynamic prompt template management                                              |
| **PromptVersionService**   | `backend/services/prompt_version_service.py` | Prompt versioning and history support                                           |
| **AuditService**           | `backend/services/audit_logger.py`           | Security audit logging and compliance tracking                                  |
| **NotificationService**    | `backend/services/notification.py`           | Alert delivery via multiple channels                                            |
| **CircuitBreaker**         | `backend/services/circuit_breaker.py`        | Protect services from cascading failures                                        |
| **DegradationManager**     | `backend/services/degradation_manager.py`    | Graceful degradation during service failures                                    |
| **CacheService**           | `backend/services/cache_service.py`          | Redis-based caching for frequently accessed data                                |
| **AlertDedupService**      | `backend/services/alert_dedup.py`            | Deduplicate repeated alerts                                                     |
| **SearchService**          | `backend/services/search.py`                 | Full-text search across events and detections                                   |
| **SeverityService**        | `backend/services/severity.py`               | Calculate and normalize severity scores                                         |
| **BBoxValidation**         | `backend/services/bbox_validation.py`        | Validate and normalize bounding box coordinates                                 |

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

### Frontend Hooks

| Hook                      | Location                                      | Responsibility                                       |
| ------------------------- | --------------------------------------------- | ---------------------------------------------------- |
| **useWebSocket**          | `frontend/src/hooks/useWebSocket.ts`          | Core WebSocket connection management                 |
| **WebSocketManager**      | `frontend/src/hooks/webSocketManager.ts`      | Singleton WebSocket instance with reconnection logic |
| **useEventStream**        | `frontend/src/hooks/useEventStream.ts`        | Subscribe to real-time security events               |
| **useSystemStatus**       | `frontend/src/hooks/useSystemStatus.ts`       | Subscribe to system health broadcasts                |
| **useWebSocketStatus**    | `frontend/src/hooks/useWebSocketStatus.ts`    | Track WebSocket connection state                     |
| **useConnectionStatus**   | `frontend/src/hooks/useConnectionStatus.ts`   | Combined API and WebSocket connection status         |
| **useHealthStatus**       | `frontend/src/hooks/useHealthStatus.ts`       | Monitor backend service health                       |
| **useServiceStatus**      | `frontend/src/hooks/useServiceStatus.ts`      | Track individual AI service availability             |
| **useAIMetrics**          | `frontend/src/hooks/useAIMetrics.ts`          | AI pipeline performance metrics (latency, accuracy)  |
| **usePerformanceMetrics** | `frontend/src/hooks/usePerformanceMetrics.ts` | System performance metrics (CPU, memory, GPU)        |
| **useGpuHistory**         | `frontend/src/hooks/useGpuHistory.ts`         | Historical GPU utilization data                      |
| **useStorageStats**       | `frontend/src/hooks/useStorageStats.ts`       | Storage usage and retention statistics               |
| **useModelZooStatus**     | `frontend/src/hooks/useModelZooStatus.ts`     | Optional model zoo loading status                    |
| **useSavedSearches**      | `frontend/src/hooks/useSavedSearches.ts`      | Manage user-saved search filters                     |
| **useSidebarContext**     | `frontend/src/hooks/useSidebarContext.ts`     | Sidebar state management context                     |

### AI Services

| Service         | Location             | Responsibility                                                    |
| --------------- | -------------------- | ----------------------------------------------------------------- |
| **ai-gateway**  | `ai/gateway/`        | FastAPI + Triton front: `/yolo26` detection, `/enrich-lt` lane    |
| **YOLO26 leaf** | `ai/yolo26/model.py` | Pure-leaf detection contract + TensorRT build used by the gateway |
| **ai-vlm**      | `ai/vlm/Dockerfile`  | llama.cpp `llama-server` image for the Qwen3VL GGUF pair          |

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

<!-- prettier-ignore-start -->
--8<-- "docs/_includes/websocket-channels.md"
<!-- prettier-ignore-end -->

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

| Channel              | Publisher         | Subscribers          | Purpose                                    |
| -------------------- | ----------------- | -------------------- | ------------------------------------------ |
| `security_events`    | VlmAnalyzer       | EventBroadcaster(s)  | Distribute events to all backend instances |
| `system_status`      | SystemBroadcaster | SystemBroadcaster(s) | Sync status broadcasts across instances    |
| `performance_update` | SystemBroadcaster | SystemBroadcaster(s) | Sync detailed performance broadcasts       |

### Redis Queues (Streams)

Used for: Reliable async job processing with consumer groups and acknowledgment
(`USE_REDIS_STREAMS=true` ships as the default).

| Stream              | Producer        | Consumer             | Data                                   |
| ------------------- | --------------- | -------------------- | -------------------------------------- |
| `detections:stream` | FileWatcher     | DetectionQueueWorker | `{camera_id, file_path, timestamp}`    |
| `analysis:stream`   | BatchAggregator | AnalysisQueueWorker  | `{batch_id, camera_id, detection_ids}` |

### HTTP (Internal Services)

Used for: AI inference requests

| Service    | Endpoint               | Method | Request                          | Response                                          |
| ---------- | ---------------------- | ------ | -------------------------------- | ------------------------------------------------- |
| ai-gateway | `/yolo26/detect`       | POST   | Multipart image                  | `{detections: [{class, confidence, bbox}]}`       |
| ai-gateway | `/yolo26/health`       | GET    | -                                | health + Triton model readiness                   |
| ai-vlm     | `/v1/chat/completions` | POST   | `{messages, images, max_tokens}` | OpenAI-style completion with the VLM verdict JSON |
| ai-vlm     | `/health`              | GET    | -                                | `{status: "ok"}`                                  |

---

## Deployment Topology

```mermaid
flowchart TB
    subgraph Host["Host Machine (with GPU)"]
        subgraph Docker["Docker Compose Network"]
            FE["Frontend Container<br/>Port 8444 HTTPS / 8080 HTTP (prod)"]
            BE["Backend Container<br/>Python 3.14<br/>Port 8000"]
            RD["Redis Container<br/>Redis 7 Alpine<br/>Port 6379"]
        end

        subgraph GPUContainers["AI Services (GPU via CDI)"]
            GW["ai-gateway<br/>Triton: yolo26, reid, threat<br/>Port 8090 (metrics 8002)"]
            VLM["ai-vlm (default compose set)<br/>llama.cpp + Qwen3VL GGUF pair<br/>Port 8098"]
        end

        subgraph Storage["Persistent Storage"]
            VOL1["PostgreSQL<br/>database volume"]
            VOL2["/export/foscam/<br/>Camera uploads (RO)"]
            VOL3["redis_data<br/>Redis persistence"]
        end

        GPU["NVIDIA GPU<br/>CUDA 12.0+"]
    end

    FE <--> BE

    BE <--> RD
    BE -->|ai-gateway:8090| GW
    BE -->|ai-vlm:8098| VLM
    GW --> GPU
    VLM --> GPU
    BE --> VOL1
    BE --> VOL2
    RD --> VOL3
```

### What Runs Where

| Component      | Deployment                      | Why                                                       |
| -------------- | ------------------------------- | --------------------------------------------------------- |
| **Frontend**   | Podman (dev: Vite, prod: Nginx) | No GPU needed, isolated environment                       |
| **Backend**    | Podman                          | No GPU needed, isolated environment                       |
| **Redis**      | Podman                          | No GPU needed, ephemeral data acceptable                  |
| **PostgreSQL** | Podman                          | Database isolation, volume persistence                    |
| **ai-gateway** | Podman (GPU via CDI)            | Triton models; GPU access via NVIDIA Container Toolkit    |
| **ai-vlm**     | Podman (GPU via CDI)            | The verdict engine; in the default set, `up -d` starts it |

### Port Summary

Host ports are `.env.example` defaults; everything binds `127.0.0.1`, the frontend nginx included, unless `EXPOSE_LAN=true` — the single switch (`O1.6`) that publishes the frontend on `0.0.0.0` and arms the backend's auth gate at the same time.

| Port        | Service                              | Protocol | Exposed To                   |
| ----------- | ------------------------------------ | -------- | ---------------------------- |
| 8444 / 8080 | Frontend (HTTPS / HTTP)              | HTTP     | Browser                      |
| 8000        | Backend API                          | HTTP/WS  | Browser, Frontend container  |
| 6379        | Redis                                | TCP      | Backend container only       |
| 8090        | ai-gateway (`/yolo26`, `/enrich-lt`) | HTTP     | Backend container, localhost |
| 8002        | ai-gateway metrics                   | HTTP     | Prometheus, localhost        |
| 8098        | ai-vlm (llama.cpp)                   | HTTP     | Backend container, localhost |

---

## Data Flow

### Complete Pipeline: Camera to Dashboard

```mermaid
sequenceDiagram
    participant CAM as Foscam Camera
    participant FTP as /export/foscam/
    participant FW as FileWatcher
    participant DS as detections:stream
    participant DW as DetectionQueueWorker
    participant GW as ai-gateway /yolo26
    participant DB as PostgreSQL
    participant BA as BatchAggregator
    participant AS as analysis:stream
    participant AW as AnalysisQueueWorker
    participant SP as specialist lookups
    participant VLM as ai-vlm
    participant EB as EventBroadcaster
    participant WS as WebSocket
    participant UI as Dashboard

    CAM->>FTP: FTP upload image
    FTP->>FW: watchdog inotify event
    FW->>FW: debounce 0.5s + size-stability wait
    FW->>FW: validate media, content-hash dedupe
    FW->>DS: XADD {camera_id, file_path}

    DS->>DW: XREADGROUP
    DW->>GW: POST /yolo26/detect (image)
    GW-->>DW: {detections: [...]}
    DW->>DB: INSERT detections
    DW->>BA: add_detection(camera_id, detection_id)
    BA->>BA: close batch on 90s window / 30s idle / 500 detections
    BA->>AS: XADD {batch_id, detection_ids}

    AS->>AW: XREADGROUP
    AW->>DB: SELECT detections WHERE id IN (...)
    AW->>AW: select_key_frames (1-4 stills)
    AW->>SP: collect faces / plates / person_reid (in-process)
    SP-->>AW: specialist output text lines
    AW->>VLM: POST /v1/chat/completions (stills + prompt)
    VLM-->>AW: verdict + scene description + risk score
    AW->>AW: apply_verdict_invariants (SeverityService)
    AW->>DB: INSERT events + event_verifications + event_detections
    AW->>EB: broadcast_event()

    EB->>WS: send to connected clients
    WS->>UI: {"type": "event", "data": {...}}
    UI->>UI: update activity feed
```

### Batching Logic

Why batch detections instead of analyzing each frame?

A single "person walks to door" scenario might generate 15 images over 30 seconds. Batching provides:

1. **Better context:** the VLM sees the full sequence, not isolated frames
2. **Reduced calls:** One VLM call per event, not per frame
3. **Coherent events:** User sees "Person approached door" not 15 separate alerts

**Batch timing:**

<!-- prettier-ignore-start -->
--8<-- "docs/_includes/batching-config.md"
<!-- prettier-ignore-end -->

---

## Database Schema

```mermaid
erDiagram
    cameras ||--o{ detections : "has"
    cameras ||--o{ events : "has"
    events ||--o| event_verifications : "verified by"
    events ||--o{ event_detections : "groups"
    detections ||--o{ event_detections : "member of"

    cameras {
        string id PK "camera id"
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
        string batch_id "Groups detections (unique)"
        string camera_id FK
        datetime started_at
        datetime ended_at
        int risk_score "0-100 from the VLM"
        string risk_level "low/medium/high/critical"
        text summary "VLM summary"
        text reasoning "VLM explanation"
        bool reviewed "User marked"
        text notes "User notes"
        bool is_fast_path "Bypassed batching"
    }

    event_verifications {
        int id PK
        int event_id FK
        string verdict "confirmed/rejected/uncertain/verification_failed"
        text scene_description
        jsonb criteria
        jsonb key_frame_detection_ids
        string engine
        string model_id
        int latency_ms
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
        string id PK
        string key_hash "hashed key"
        string name
        datetime created_at
        datetime expires_at
    }
```

### Key Indexes

| Table      | Index                       | Purpose                      |
| ---------- | --------------------------- | ---------------------------- |
| detections | (camera_id, detected_at)    | Camera-specific time queries |
| events     | started_at                  | Timeline queries             |
| events     | risk_score                  | High-risk filtering          |
| events     | reviewed                    | Workflow queries             |
| events     | batch_id                    | Idempotent batch writes      |
| gpu_stats  | recorded_at                 | Time-series queries          |
| logs       | timestamp, level, component | Dashboard filters            |

---

## Error Handling and Resilience

### Graceful Degradation

| Component           | Failure Mode                   | Fallback Behavior                                                    |
| ------------------- | ------------------------------ | -------------------------------------------------------------------- |
| ai-gateway (YOLO26) | Unreachable                    | DetectorClient returns empty list, skips detection                   |
| ai-vlm              | Unreachable                    | Event still written; verdict `verification_failed`, score/level NULL |
| Specialist legs     | Weights absent or not resident | That leg's line reads `unavailable: specialist did not run`          |
| Redis               | Unreachable                    | Deduplication fails open (allows processing), pub/sub unavailable    |
| GPU                 | Not available                  | GPUMonitor returns mock data                                         |

### Circuit Breaker Pattern

The `CircuitBreaker` service (`backend/services/circuit_breaker.py`) protects against cascading failures:

| State      | Behavior                                                             |
| ---------- | -------------------------------------------------------------------- |
| **Closed** | Normal operation, requests pass through                              |
| **Open**   | All requests immediately fail, prevents overwhelming failing service |
| **Half**   | Limited requests allowed to test if service recovered                |

### Degradation Manager

The `DegradationManager` service (`backend/services/degradation_manager.py`) coordinates graceful degradation:

- Monitors service health across components
- Automatically disables non-critical features when resources are constrained
- Prioritizes core detection and risk analysis over optional enhancements
- Broadcasts degradation status changes via WebSocket

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

1. Periodically checks service health (ai-gateway, ai-vlm, Redis)
2. On failure, attempts restart with exponential backoff
3. Broadcasts status changes via WebSocket
4. Gives up after max retries (prevents infinite restart loops)

---

## Security Model

<!-- prettier-ignore-start -->
--8<-- "docs/_includes/auth-model.md"
<!-- prettier-ignore-end -->

The http/TLS/cookie trade-off behind item 4, including the startup warning, is in [The login cookie over http and TLS](../reference/config/env-reference.md#the-login-cookie-over-http-and-tls).

### Production Hardening (Recommended)

- Set `EXPOSE_LAN=true` whenever anything beyond this machine reaches the UI (login session or API key required)
- Use HTTPS for AI service endpoints
- Restrict CORS origins
- Add rate limiting
- Run behind reverse proxy with TLS
- Review `docs/ROADMAP.md` security hardening section

---

## Performance Characteristics

Latency is dominated by two steps: the ai-gateway detection call per image, and one ai-vlm
chat-completion call per closed batch (up to four stills ride along in the prompt). Event-to-
dashboard delivery is a Redis pub/sub fan-out. End-to-end cadence for a batched event is the
batch close time (90s window / 30s idle / 500 detections, whichever fires first) plus the
analysis call. Publish the `hsi_specialist_unavailable_total` counter and the
`event_verifications.verdict` distribution to see what the pipeline is actually doing — see
[AI pipeline: current state](./ai-pipeline-current-state.md) §8.

### Resource Usage

<!-- prettier-ignore-start -->
--8<-- "docs/_includes/vram-requirements.md"
<!-- prettier-ignore-end -->

---

## Configuration Summary

See `docs/reference/config/env-reference.md` for complete reference.

**Key environment variables:**

```bash
# Database and Redis (PostgreSQL required)
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret
REDIS_URL=redis://localhost:6379/0

# AI services
AI_GATEWAY_URL=http://ai-gateway:8090
USE_AI_GATEWAY=true
YOLO26_URL=http://localhost:8090/yolo26
ENRICHMENT_LIGHT_URL=http://localhost:8090/enrich-lt   # readiness lane

# Pipeline selection — both accept only "vlm" (anything else hard-raises)
PIPELINE_MODE=vlm
GATEWAY_MODEL_SET=vlm
GATEWAY_ENABLE_THREAT=false

# Specialist leg residency (face + re-ID handle preload; >=24GB hosts opt in)
BACKEND_MODEL_PRELOAD=false

# Detection
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Batching
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30

# Retention
RETENTION_DAYS=30
```

---

## Related Documentation

| Document                                         | Purpose                                       |
| ------------------------------------------------ | --------------------------------------------- |
| `docs/architecture/ai-pipeline-current-state.md` | Measured, pinned description of the live path |
| `docs/reference/config/env-reference.md`         | Complete environment variable reference       |
| `docs/operator/deployment/`                      | Docker deployment guide                       |
| `docs/operator/ai-installation.md`               | AI services setup and troubleshooting         |
| `docs/ROADMAP.md`                                | Post-MVP enhancement ideas                    |
| `backend/AGENTS.md`                              | Backend architecture details                  |
| `frontend/AGENTS.md`                             | Frontend architecture details                 |
| `ai/AGENTS.md`                                   | AI pipeline details                           |

---

_This document provides a comprehensive overview of the Home Security Intelligence system architecture. For implementation details, refer to the source code and component-specific AGENTS.md files._
