# API Reference Directory - Agent Guide

## Purpose

This directory contains comprehensive API documentation for the Home Security Intelligence system. These references are for developers integrating with or extending the system's APIs.

> **Canonical location:** `docs/api-reference/`
>
> A second copy exists at `docs/reference/api/` (historical). To avoid drift, treat `docs/api-reference/` as the source of truth.

## Directory Contents

```
api-reference/
  AGENTS.md        # This file
  overview.md      # API overview and conventions
  ai-audit.md      # AI Audit API reference (pipeline performance auditing)
  alerts.md        # Alerts API reference
  audit.md         # Audit API reference (system audit logs)
  cameras.md       # Cameras API reference
  detections.md    # Detections API reference
  dlq.md           # Dead Letter Queue API reference
  enrichment.md    # Enrichment API reference (vision model results)
  entities.md      # Entities API reference (re-identification tracking)
  events.md        # Events API reference
  logs.md          # Logs API reference
  media.md         # Media API reference (file serving)
  model-zoo.md     # Model Zoo API reference (AI model management)
  prompts.md       # Prompt Management API reference (AI model prompts)
  system.md        # System API reference
  websocket.md     # WebSocket API reference
  zones.md         # Zones API reference
```

## Key Files

### overview.md

**Purpose:** API overview and common conventions.

**Topics Covered:**

- Base URL and versioning
- Authentication (if applicable)
- Request/response format (JSON)
- Error handling and status codes
- Pagination conventions
- Rate limiting

**When to use:** Starting to use any API, understanding common patterns.

### ai-audit.md

**Purpose:** AI Audit API reference - AI pipeline performance auditing.

**Endpoints:**

- `GET /api/ai-audit/events/{event_id}` - Get audit for a specific event
- `POST /api/ai-audit/events/{event_id}/evaluate` - Trigger full evaluation for an event
- `GET /api/ai-audit/stats` - Get aggregate audit statistics
- `GET /api/ai-audit/leaderboard` - Get model leaderboard by contribution
- `GET /api/ai-audit/recommendations` - Get aggregated prompt recommendations
- `POST /api/ai-audit/batch` - Trigger batch audit processing

**Topics Covered:**

- Model contribution tracking (RT-DETR, Florence, CLIP, etc.)
- Self-evaluation quality scores (1-5 scale)
- Prompt improvement recommendations
- Consistency checking
- Batch processing for historical events

**When to use:** Monitoring AI pipeline performance, improving prompt templates, analyzing model contributions.

### alerts.md

**Purpose:** Alerts API reference.

**Endpoints:**

- `GET /api/alerts/rules` - List alert rules
- `POST /api/alerts/rules` - Create alert rule
- `GET /api/alerts/rules/{rule_id}` - Get alert rule
- `PUT /api/alerts/rules/{rule_id}` - Update alert rule
- `DELETE /api/alerts/rules/{rule_id}` - Delete alert rule
- `POST /api/alerts/rules/{rule_id}/test` - Test rule against historical events
- `GET /api/notification/config` - Get notification configuration
- `POST /api/notification/test` - Test notification delivery

**When to use:** Working with alert management features.

### cameras.md

**Purpose:** Cameras API reference.

**Endpoints:**

- `GET /api/cameras` - List cameras
- `GET /api/cameras/{camera_id}` - Get camera by ID
- `POST /api/cameras` - Create camera
- `PATCH /api/cameras/{camera_id}` - Update camera
- `DELETE /api/cameras/{camera_id}` - Delete camera
- `GET /api/cameras/{camera_id}/snapshot` - Get latest snapshot image

**When to use:** Managing camera configurations.

### detections.md

**Purpose:** Detections API reference.

**Endpoints:**

- `GET /api/detections` - List detections
- `GET /api/detections/{detection_id}` - Get detection by ID
- `GET /api/detections/{detection_id}/image` - Get detection thumbnail
- `GET /api/detections/{detection_id}/enrichment` - Get enrichment data for detection
- `GET /api/detections/{detection_id}/video` - Stream detection video
- `GET /api/detections/{detection_id}/video/thumbnail` - Get video thumbnail frame

**When to use:** Querying object detection results.

### dlq.md

**Purpose:** Dead Letter Queue API reference - managing failed AI pipeline jobs.

**Endpoints:**

- `GET /api/dlq/stats` - Get DLQ statistics (counts per queue)
- `GET /api/dlq/jobs/{queue_name}` - List jobs in a specific DLQ
- `POST /api/dlq/requeue/{queue_name}` - Requeue oldest job (requires auth)
- `POST /api/dlq/requeue-all/{queue_name}` - Requeue all jobs (requires auth)
- `DELETE /api/dlq/{queue_name}` - Clear all jobs from DLQ (requires auth)

**Topics Covered:**

- DLQ architecture (detection vs analysis queues)
- Retry behavior (exponential backoff configuration)
- Job failure format (original_job, error, timestamps)
- Circuit breaker protection for DLQ overflow
- Common failure reasons and resolutions
- Operational workflows for recovery

**When to use:** Investigating failed jobs, recovering from service outages, clearing stale data.

### enrichment.md

**Purpose:** Enrichment API reference - structured results from vision model analysis.

**Endpoints:**

- `GET /api/detections/{detection_id}/enrichment` - Get enrichment data for a detection
- `GET /api/events/{event_id}/enrichments` - Get enrichment data for all detections in an event

**Data Categories:**

- License plate detection and OCR
- Face detection
- Vehicle classification and damage detection
- Clothing analysis (FashionCLIP, SegFormer)
- Violence detection
- Image quality assessment
- Pet classification

**When to use:** Accessing detailed vision model results beyond basic detection data.

### entities.md

**Purpose:** Entities API reference - entity re-identification tracking across cameras.

**Endpoints:**

- `GET /api/entities` - List tracked entities with filtering
- `GET /api/entities/{entity_id}` - Get detailed entity information
- `GET /api/entities/{entity_id}/history` - Get entity appearance timeline

**Topics Covered:**

- Entity types (person, vehicle) and attributes
- Re-identification using CLIP embeddings
- Appearance history and cross-camera tracking
- Similarity matching (cosine similarity, threshold 0.85)
- Redis storage pattern (24-hour TTL)
- Rate limiting configuration

**When to use:** Tracking persons and vehicles across cameras, understanding entity movement patterns, re-identification workflows.

### events.md

**Purpose:** Events API reference.

**Endpoints:**

- `GET /api/events` - List events with filtering
- `GET /api/events/stats` - Get event statistics
- `GET /api/events/search` - Full-text search
- `GET /api/events/export` - CSV export
- `GET /api/events/{event_id}` - Get event by ID
- `PATCH /api/events/{event_id}` - Update event (review/notes)
- `GET /api/events/{event_id}/detections` - Get detections for event
- `GET /api/events/{event_id}/enrichments` - Get enrichment data for all detections

**When to use:** Querying security events and their associated data.

### media.md

**Purpose:** Media API reference - secure file serving for images, videos, and thumbnails.

**Endpoints:**

- `GET /api/media/cameras/{camera_id}/{filename}` - Serve camera image or video
- `GET /api/media/thumbnails/{filename}` - Serve detection thumbnail
- `GET /api/media/detections/{detection_id}` - Serve image for a detection
- `GET /api/media/clips/{filename}` - Serve event video clip
- `GET /api/media/{path}` - Compatibility route (legacy support)

**Topics Covered:**

- Path traversal protection
- File type allowlist (jpg, png, gif, mp4, avi, webm)
- Rate limiting (MEDIA tier)
- Directory containment validation

**When to use:** Serving media files to the frontend, accessing camera images, detection thumbnails, or video clips.

### model-zoo.md

**Purpose:** Model Zoo API reference - AI model status and latency monitoring.

**Endpoints:**

- `GET /api/system/models` - Get Model Zoo registry with all models
- `GET /api/system/models/{model_name}` - Get status of a specific model
- `GET /api/system/model-zoo/status` - Get compact status for UI display
- `GET /api/system/model-zoo/latency/history` - Get latency history for a model

**Topics Covered:**

- Model status (loaded, unloaded, disabled)
- VRAM budget and usage monitoring
- Model categories and capabilities
- Latency time-series data for performance monitoring
- Available models (18+ vision models)

**When to use:** Monitoring AI model performance, VRAM management, building AI dashboards.

### prompts.md

**Purpose:** Prompt Management API reference - AI model prompt configuration management.

**Endpoints:**

- `GET /api/ai-audit/prompts` - Get all model prompt configurations
- `GET /api/ai-audit/prompts/{model}` - Get prompt configuration for a specific model
- `PUT /api/ai-audit/prompts/{model}` - Update prompt configuration for a model
- `GET /api/ai-audit/prompts/export` - Export all prompt configurations
- `GET /api/ai-audit/prompts/history` - Get version history for prompts
- `POST /api/ai-audit/prompts/history/{version_id}` - Restore a specific prompt version
- `POST /api/ai-audit/prompts/test` - Test a prompt configuration
- `POST /api/ai-audit/prompts/import` - Import prompt configurations
- `POST /api/ai-audit/prompts/import/preview` - Preview import changes

**Topics Covered:**

- Supported AI models (Nemotron, Florence-2, YOLO-World, X-CLIP, Fashion-CLIP)
- Model-specific configuration schemas
- Version history and rollback
- Prompt testing against events
- Import/export for backup and sharing
- Default configurations

**When to use:** Managing AI model prompts, testing prompt changes, backing up configurations, version control for prompts.

### system.md

**Purpose:** System API reference.

**Endpoints:**

- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe (root-level)
- `GET /api/system/health` - Detailed health check
- `GET /api/system/health/ready` - Detailed readiness
- `GET /api/system/gpu` - GPU statistics
- `GET /api/system/gpu/history` - GPU history
- `GET /api/system/stats` - System counters/uptime
- `GET /api/system/config` - Public config
- `PATCH /api/system/config` - Update config (requires API key when enabled)
- `GET /api/system/telemetry` - Pipeline telemetry
- `GET /api/system/pipeline-latency` - Pipeline latency percentiles
- `GET /api/system/pipeline-latency/history` - Pipeline latency time series
- `GET /api/system/pipeline` - Pipeline status (FileWatcher, BatchAggregator, Degradation)
- `POST /api/system/cleanup` - Trigger cleanup (requires API key when enabled)
- `GET /api/system/cleanup/status` - Cleanup job status
- `GET /api/system/severity` - Severity definitions
- `GET /api/system/storage` - Storage stats
- `GET /api/system/circuit-breakers` - Circuit breaker status

**When to use:** Monitoring system health, managing configuration.

### websocket.md

**Purpose:** WebSocket API reference.

**Channels:**

- `/ws/events` - Real-time event and detection updates
- `/ws/system` - System status and GPU stats updates

**Topics Covered:**

- Connection establishment
- Message formats
- Subscription patterns
- Reconnection handling

**When to use:** Implementing real-time features, building custom dashboards.

## API Conventions

### Request Format

All requests use JSON:

```http
Content-Type: application/json
```

### Response Format

This API intentionally uses **resource-shaped responses** (e.g. `{ "events": [...] }`) rather than a single global `{data, meta}` wrapper. See `overview.md` for common pagination conventions.

### Error Format

Errors follow FastAPI’s standard shape:

```json
{ "detail": "Error message" }
```

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/architecture/:** Technical architecture details
- **backend/api/routes/AGENTS.md:** Route implementation details
- **backend/api/schemas/AGENTS.md:** Pydantic schema definitions
