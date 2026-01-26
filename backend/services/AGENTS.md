# Backend Services Directory

## Purpose

This directory contains the core business logic and background services for the AI-powered home security monitoring system. Services orchestrate the complete detection pipeline from file monitoring through AI analysis to event creation, along with context enrichment, re-identification, and model zoo management.

## Architecture Overview

The services implement a multi-stage async pipeline with real-time broadcasting and background maintenance:

```
File Upload -> Detection -> Batching -> Enrichment -> Analysis -> Event Creation -> Broadcasting
   (1)          (2)         (3)          (4)          (5)          (6)              (7)

                     Monitoring Services (Parallel)
                     ├── GPUMonitor (polls GPU stats)
                     ├── SystemBroadcaster (system status)
                     ├── HealthMonitor (service recovery)
                     ├── CleanupService (retention policy)
                     ├── PerformanceCollector (metrics aggregation)
                     └── BackgroundEvaluator (AI audit evaluation)
```

### Service Categories

1. **Core AI Pipeline** - File watching, detection, batching, analysis, streaming
2. **AI Clients** - HTTP clients for external AI services (Florence, CLIP)
3. **AI Services** - DI wrappers for face/plate detection services
4. **Context Enrichment** - Zone detection, baseline tracking, re-identification
5. **Entity Re-identification** - Embedding clustering, hybrid storage bridge
6. **Model Zoo** - On-demand model loading for attribute extraction
7. **Model Loaders** - Individual model loading functions for Model Zoo
8. **Model Loader Base** - Abstract base class for model loaders
9. **Pipeline Workers** - Background queue consumers and managers
10. **Background Services** - GPU monitoring, cleanup, health checks, worker supervision
11. **Container Orchestrator** - Container discovery, lifecycle management
12. **Infrastructure** - Circuit breakers, retry handlers, degradation, fallback
13. **Alerting** - Alert rules, deduplication, notifications, filtering, CRUD
14. **Audit** - Security audit logging, AI pipeline auditing
15. **Prompt Management** - LLM prompt templates, storage, versioning, type-safety
16. **Utility** - Search, severity mapping, token counting, batch fetching, cost tracking
17. **Data Management** - Partition management for time-series tables
18. **Camera Services** - Camera status updates with concurrency control
19. **Event Services** - Event CRUD, cascade soft delete, export generation
20. **File Services** - Scheduled deletion, cleanup, orphan scanning
21. **Job Services** - Job lifecycle, status tracking, timeout handling, history
22. **Calibration Services** - Adaptive threshold adjustment from feedback
23. **Queue Status** - Queue depth and health monitoring
24. **Transcoding** - Video transcoding with caching and NVENC support
25. **WebSocket** - Centralized event emission service
26. **Monitoring** - Prometheus/Grafana stack validation

## Service Files Overview

### Core AI Pipeline Services

| Service                  | Purpose                                      | Exported via `__init__.py` |
| ------------------------ | -------------------------------------------- | -------------------------- |
| `file_watcher.py`        | Monitor camera directories for media uploads | Yes                        |
| `dedupe.py`              | Prevent duplicate file processing            | Yes                        |
| `detector_client.py`     | Send images to YOLO26v2 for detection        | Yes                        |
| `batch_aggregator.py`    | Group detections into time-based batches     | Yes                        |
| `nemotron_analyzer.py`   | LLM-based risk analysis via llama.cpp        | Yes                        |
| `nemotron_streaming.py`  | Streaming LLM response extensions            | No (import directly)       |
| `thumbnail_generator.py` | Generate preview images with bounding boxes  | Yes                        |
| `video_processor.py`     | Extract video metadata and thumbnails        | No (import directly)       |
| `event_broadcaster.py`   | Distribute events via WebSocket              | Yes                        |

### AI Client Services

| Service                | Purpose                                    | Exported via `__init__.py` |
| ---------------------- | ------------------------------------------ | -------------------------- |
| `florence_client.py`   | HTTP client for Florence-2 vision-language | No (import directly)       |
| `clip_client.py`       | HTTP client for CLIP embedding generation  | No (import directly)       |
| `enrichment_client.py` | HTTP client for enrichment service         | No (import directly)       |

### Context Enrichment Services

| Service                    | Purpose                                          | Exported via `__init__.py` |
| -------------------------- | ------------------------------------------------ | -------------------------- |
| `context_enricher.py`      | Aggregate context from zones, baselines, reid    | Yes                        |
| `enrichment_pipeline.py`   | Orchestrate Model Zoo enrichment for batches     | Yes                        |
| `vision_extractor.py`      | Florence-2 attribute extraction orchestration    | No (import directly)       |
| `florence_extractor.py`    | Florence-2 specific extraction logic             | Yes                        |
| `zone_service.py`          | Zone detection and context generation            | Yes                        |
| `baseline.py`              | Activity baseline tracking for anomaly detection | Yes                        |
| `scene_baseline.py`        | Scene-level baseline tracking                    | No (import directly)       |
| `scene_change_detector.py` | SSIM-based scene change detection                | Yes                        |
| `reid_service.py`          | Entity re-identification across cameras          | Yes                        |
| `reid_matcher.py`          | Person re-ID matching across detections          | No (import directly)       |
| `bbox_validation.py`       | Bounding box validation utilities                | No (import directly)       |

### Model Zoo Services

| Service        | Purpose                                      | Exported via `__init__.py` |
| -------------- | -------------------------------------------- | -------------------------- |
| `model_zoo.py` | Registry and manager for on-demand AI models | Yes                        |

### Model Loader Services

| Service                        | Purpose                                          | Exported via `__init__.py` |
| ------------------------------ | ------------------------------------------------ | -------------------------- |
| `clip_loader.py`               | Load CLIP ViT-L for embeddings                   | Yes                        |
| `florence_loader.py`           | Load Florence-2 for vision-language              | Yes                        |
| `yolo_world_loader.py`         | Load YOLO-World for open-vocabulary detection    | No (import directly)       |
| `vitpose_loader.py`            | Load ViTPose for human pose estimation           | No (import directly)       |
| `depth_anything_loader.py`     | Load Depth Anything for depth estimation         | No (import directly)       |
| `violence_loader.py`           | Load violence detection model                    | No (import directly)       |
| `weather_loader.py`            | Load weather classification model                | No (import directly)       |
| `segformer_loader.py`          | Load SegFormer for clothing segmentation         | No (import directly)       |
| `xclip_loader.py`              | Load X-CLIP for action recognition               | No (import directly)       |
| `fashion_clip_loader.py`       | Load Fashion-CLIP for clothing classification    | No (import directly)       |
| `image_quality_loader.py`      | Load BRISQUE for image quality assessment        | No (import directly)       |
| `vehicle_classifier_loader.py` | Load vehicle segment classifier                  | No (import directly)       |
| `vehicle_damage_loader.py`     | Load vehicle damage detection model              | No (import directly)       |
| `pet_classifier_loader.py`     | Load pet classifier for false positive reduction | No (import directly)       |

### Model Loader Base

| Service                | Purpose                                       | Exported via `__init__.py` |
| ---------------------- | --------------------------------------------- | -------------------------- |
| `model_loader_base.py` | Abstract base class for all Model Zoo loaders | No (import directly)       |

### Specialized Detection Services

| Service             | Purpose                                     | Exported via `__init__.py` |
| ------------------- | ------------------------------------------- | -------------------------- |
| `plate_detector.py` | License plate detection and OCR             | Yes                        |
| `face_detector.py`  | Face detection for person re-identification | Yes                        |
| `ocr_service.py`    | OCR text extraction from detected regions   | Yes                        |

### Pipeline Workers

| Service               | Purpose                              | Exported via `__init__.py` |
| --------------------- | ------------------------------------ | -------------------------- |
| `pipeline_workers.py` | Background queue workers and manager | No (import directly)       |

### Background Services

| Service                          | Purpose                                       | Exported via `__init__.py` |
| -------------------------------- | --------------------------------------------- | -------------------------- |
| `gpu_monitor.py`                 | Poll NVIDIA GPU metrics                       | Yes                        |
| `cleanup_service.py`             | Enforce data retention policies               | Yes                        |
| `health_monitor.py`              | Monitor service health with auto-recovery     | No (import directly)       |
| `health_monitor_orchestrator.py` | Container orchestrator health monitoring loop | No (import directly)       |
| `health_event_emitter.py`        | WebSocket health status event emission        | No (import directly)       |
| `health_service_registry.py`     | DI registry for health monitoring (NEM-2611)  | No (import directly)       |
| `system_broadcaster.py`          | Broadcast system health status                | No (import directly)       |
| `performance_collector.py`       | Collect system performance metrics            | No (import directly)       |
| `background_evaluator.py`        | Run AI audit evaluations when GPU is idle     | Yes                        |
| `worker_supervisor.py`           | Auto-recovery for crashed worker tasks        | No (import directly)       |

### Container Orchestrator Services

| Service                     | Purpose                                             | Exported via `__init__.py` |
| --------------------------- | --------------------------------------------------- | -------------------------- |
| `container_discovery.py`    | Discover Docker containers by name pattern          | No (import directly)       |
| `lifecycle_manager.py`      | Self-healing restart logic with exponential backoff | No (import directly)       |
| `container_orchestrator.py` | Coordinate discovery, health, lifecycle, broadcast  | No (import directly)       |

### Infrastructure Services

| Service                  | Purpose                                            | Exported via `__init__.py` |
| ------------------------ | -------------------------------------------------- | -------------------------- |
| `retry_handler.py`       | Exponential backoff and DLQ support                | Yes                        |
| `service_managers.py`    | Strategy pattern for service management            | No (import directly)       |
| `circuit_breaker.py`     | Circuit breaker for service resilience             | Yes                        |
| `degradation_manager.py` | Graceful degradation management                    | Yes                        |
| `cache_service.py`       | Redis caching utilities                            | Yes                        |
| `service_registry.py`    | Service registry with Redis persistence            | No (import directly)       |
| `inference_semaphore.py` | Shared semaphore for AI inference                  | No (import directly)       |
| `managed_service.py`     | Canonical ManagedService and ServiceRegistry types | Yes                        |
| `ai_fallback.py`         | AI service fallback strategies for degradation     | No (import directly)       |

### Alerting Services

| Service                  | Purpose                                  | Exported via `__init__.py` |
| ------------------------ | ---------------------------------------- | -------------------------- |
| `alert_engine.py`        | Evaluate alert rules against events      | Yes                        |
| `alert_dedup.py`         | Alert deduplication logic                | Yes                        |
| `alert_service.py`       | Alert CRUD with WebSocket events         | No (import directly)       |
| `notification.py`        | Multi-channel notification delivery      | Yes                        |
| `notification_filter.py` | Filter notifications by user preferences | No (import directly)       |

### Audit Services

| Service                             | Purpose                                      | Exported via `__init__.py` |
| ----------------------------------- | -------------------------------------------- | -------------------------- |
| `audit.py`                          | Audit logging for security-sensitive actions | Yes                        |
| `audit_logger.py`                   | High-level security audit logging interface  | No (import directly)       |
| `pipeline_quality_audit_service.py` | AI pipeline audit and self-evaluation        | Yes                        |

### Prompt Management Services

| Service                     | Purpose                                               | Exported via `__init__.py` |
| --------------------------- | ----------------------------------------------------- | -------------------------- |
| `prompts.py`                | LLM prompt templates                                  | No (import directly)       |
| `prompt_sanitizer.py`       | Prompt injection prevention for LLM inputs (NEM-1722) | No (import directly)       |
| `prompt_service.py`         | CRUD operations for AI prompt configs                 | No (import directly)       |
| `prompt_storage.py`         | File-based prompt storage with versioning             | No (import directly)       |
| `prompt_version_service.py` | Prompt version history and restoration                | No (import directly)       |
| `prompt_parser.py`          | Parse and modify prompts with suggestions             | No (import directly)       |
| `typed_prompt_config.py`    | Type-safe prompt configuration with generics          | No (import directly)       |

### Utility Services

| Service             | Purpose                                                 | Exported via `__init__.py` |
| ------------------- | ------------------------------------------------------- | -------------------------- |
| `search.py`         | Full-text search for events                             | Yes                        |
| `severity.py`       | Severity level mapping and configuration                | Yes                        |
| `clip_generator.py` | Video clip generation for events                        | Yes                        |
| `token_counter.py`  | LLM prompt token counting and context window validation | No (import directly)       |
| `batch_fetch.py`    | Batch fetch detections (avoid N+1)                      | No (import directly)       |
| `cost_tracker.py`   | LLM inference cost tracking and budget controls         | Yes                        |

### Data Management Services

| Service                | Purpose                         | Exported via `__init__.py` |
| ---------------------- | ------------------------------- | -------------------------- |
| `partition_manager.py` | PostgreSQL partition management | Yes                        |

### Evaluation Services

| Service               | Purpose                                 | Exported via `__init__.py` |
| --------------------- | --------------------------------------- | -------------------------- |
| `evaluation_queue.py` | Priority queue for AI audit evaluations | Yes                        |

### Camera Services

| Service                    | Purpose                                              | Exported via `__init__.py` |
| -------------------------- | ---------------------------------------------------- | -------------------------- |
| `camera_service.py`        | Camera status with optimistic concurrency (NEM-2030) | No (import directly)       |
| `camera_status_service.py` | Camera status changes with WebSocket broadcasting    | No (import directly)       |

### Entity Re-identification Services

| Service                        | Purpose                                             | Exported via `__init__.py` |
| ------------------------------ | --------------------------------------------------- | -------------------------- |
| `entity_clustering_service.py` | Embedding similarity for entity matching (NEM-2497) | No (import directly)       |
| `hybrid_entity_storage.py`     | Redis/PostgreSQL hybrid storage bridge (NEM-2498)   | No (import directly)       |

### Event Services

| Service             | Purpose                                        | Exported via `__init__.py` |
| ------------------- | ---------------------------------------------- | -------------------------- |
| `event_service.py`  | Event CRUD with cascade soft delete (NEM-1956) | No (import directly)       |
| `export_service.py` | CSV/Excel/JSON export generation (NEM-1989)    | No (import directly)       |

### File Services

| Service                     | Purpose                                              | Exported via `__init__.py` |
| --------------------------- | ---------------------------------------------------- | -------------------------- |
| `file_service.py`           | Scheduled file deletion with Redis queue (NEM-1988)  | No (import directly)       |
| `file_cleanup_service.py`   | Cascade file deletion for events (NEM-2384)          | No (import directly)       |
| `orphan_cleanup_service.py` | Cleanup orphaned files without DB records (NEM-2260) | No (import directly)       |
| `orphan_scanner_service.py` | Scan for orphaned files on disk (NEM-2387)           | No (import directly)       |

### Job Services

| Service                    | Purpose                                        | Exported via `__init__.py` |
| -------------------------- | ---------------------------------------------- | -------------------------- |
| `job_tracker.py`           | Job lifecycle management with WebSocket events | No (import directly)       |
| `job_service.py`           | Job CRUD service layer (NEM-2389, NEM-2390)    | No (import directly)       |
| `job_status.py`            | Redis-backed job status tracking               | No (import directly)       |
| `job_state_service.py`     | Job state machine transitions                  | No (import directly)       |
| `job_timeout_service.py`   | Job timeout detection and handling             | No (import directly)       |
| `job_history_service.py`   | Job execution history retrieval                | No (import directly)       |
| `job_search_service.py`    | Job search and filtering                       | No (import directly)       |
| `job_progress_reporter.py` | WebSocket job progress emission (NEM-2380)     | No (import directly)       |

### Calibration Services

| Service                  | Purpose                                     | Exported via `__init__.py` |
| ------------------------ | ------------------------------------------- | -------------------------- |
| `calibration_service.py` | Adaptive threshold adjustment from feedback | No (import directly)       |

### Queue Status Services

| Service                   | Purpose                           | Exported via `__init__.py` |
| ------------------------- | --------------------------------- | -------------------------- |
| `queue_status_service.py` | Queue depth and health monitoring | No (import directly)       |

### Transcoding Services

| Service                  | Purpose                                   | Exported via `__init__.py` |
| ------------------------ | ----------------------------------------- | -------------------------- |
| `transcoding.py`         | Video transcoding to H.264/MP4 (NEM-2681) | No (import directly)       |
| `transcoding_service.py` | Transcoding with caching (NEM-2682)       | No (import directly)       |
| `transcode_cache.py`     | Disk cache for transcoded videos with LRU | No (import directly)       |

### WebSocket Services

| Service                | Purpose                              | Exported via `__init__.py` |
| ---------------------- | ------------------------------------ | -------------------------- |
| `websocket_emitter.py` | Centralized WebSocket event emission | No (import directly)       |

### AI Services

| Service          | Purpose                               | Exported via `__init__.py` |
| ---------------- | ------------------------------------- | -------------------------- |
| `ai_services.py` | AI service wrappers for DI (NEM-2030) | No (import directly)       |

### Monitoring Services

| Service                         | Purpose                                    | Exported via `__init__.py` |
| ------------------------------- | ------------------------------------------ | -------------------------- |
| `monitoring_stack_validator.py` | Prometheus/Grafana stack health validation | No (import directly)       |

## Detailed Service Documentation

### file_watcher.py

**Purpose:** Monitors Foscam camera upload directories and queues images and videos for processing.

**Key Features:**

- Watchdog-based filesystem monitoring (recursive)
- Supports both images (.jpg, .jpeg, .png) and videos (.mp4, .mkv, .avi, .mov)
- Debounce logic (0.5s default) to wait for complete file writes
- Image integrity validation using PIL
- Integrates with DedupeService for content-hash based deduplication
- Supports both native filesystem events (inotify/FSEvents) and polling mode

**Observer Selection:**

- Default: Native backend (inotify on Linux, FSEvents on macOS)
- Polling mode: Enabled via `FILE_WATCHER_POLLING` env var or `settings.file_watcher_polling`
- Use polling for Docker Desktop, NFS/SMB mounts where inotify events don't propagate

**Camera ID Contract:**

```
Upload path: /export/foscam/Front Door/image.jpg
-> folder_name: "Front Door"
-> camera_id: "front_door" (normalized)
```

**Public API:**

- `FileWatcher(camera_root, redis_client, debounce_delay, queue_name, dedupe_service)`
- `async start()` - Begin monitoring camera directories
- `async stop()` - Gracefully shutdown
- `is_image_file(path)`, `is_video_file(path)`, `is_supported_media_file(path)`

### detector_client.py

**Purpose:** HTTP client for YOLO26v2 object detection service.

**Key Features:**

- Async HTTP client using httpx
- Confidence threshold filtering
- Direct database persistence (creates Detection records)
- 30-second timeout for detection requests
- Prometheus metrics for AI request duration

**Public API:**

- `DetectorClient()` - Initialize with settings
- `async health_check()` - Check if detector is reachable
- `async detect_objects(image_path, camera_id, session)` - Detect and store

### batch_aggregator.py

**Purpose:** Groups detections into time-based batches for efficient LLM analysis.

**Batching Rules:**

- **Window timeout:** 90 seconds from batch start (configurable)
- **Idle timeout:** 30 seconds since last detection (configurable)
- **One batch per camera:** Each camera has max 1 active batch at a time
- **Fast path:** High-confidence critical detections bypass batching

**Redis Keys (all keys have 1-hour TTL for orphan cleanup):**

```
batch:{camera_id}:current         -> current batch ID
batch:{batch_id}:camera_id        -> camera ID
batch:{batch_id}:detections       -> LIST of detection IDs (RPUSH for atomic append)
batch:{batch_id}:started_at       -> Unix timestamp
batch:{batch_id}:last_activity    -> Unix timestamp
```

**Concurrency:** Uses per-camera locks plus global lock for batch operations. Detection list updates use Redis RPUSH for atomic append in distributed environments.

**Public API:**

- `BatchAggregator(redis_client, analyzer)`
- `async add_detection(camera_id, detection_id, file_path, confidence, object_type)`
- `async check_batch_timeouts()` - Close expired batches
- `async close_batch(batch_id)` - Force close and push to analysis queue

### nemotron_analyzer.py

**Purpose:** LLM-based risk analysis using Nemotron via llama.cpp server.

**Analysis Flow:**

1. Fetch batch detections from Redis/database
2. Enrich context with zones, baselines, and cross-camera activity
3. Run enrichment pipeline for license plates, faces, OCR (optional)
4. Format prompt with enriched detection details
5. POST to llama.cpp completion endpoint
6. Parse JSON response
7. Create Event with risk assessment
8. Store Event in database
9. Broadcast via WebSocket (if available)

**Prompt Templates:**

- `RISK_ANALYSIS_PROMPT` - Basic risk analysis
- `ENRICHED_RISK_ANALYSIS_PROMPT` - With context enrichment
- `VISION_ENHANCED_RISK_ANALYSIS_PROMPT` - With Florence-2 attributes
- `MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT` - Full Model Zoo enrichment

**Public API:**

- `NemotronAnalyzer(redis_client, context_enricher, enrichment_pipeline)`
- `async analyze_batch(batch_id)` - Analyze batch and create Event
- `async analyze_detection_fast_path(camera_id, detection_id)` - Immediate analysis
- `async health_check()` - Check if LLM server is reachable

### event_broadcaster.py

**Purpose:** Distributes security events to frontend clients via WebSocket.

**Channel:** `security_events` (Redis pub/sub)

**Message Format:**

```json
{
  "type": "event",
  "data": {
    "id": "uuid",
    "camera_id": "front_door",
    "risk_score": 75,
    "summary": "Person detected at front door",
    "created_at": "2024-01-15T10:30:00Z",
    "detections": [...]
  }
}
```

**Key Features:**

- WebSocket broadcast to all connected clients
- Redis pub/sub for horizontal scaling
- Automatic reconnection handling
- Message queuing during disconnection

**Public API:**

- `EventBroadcaster(redis_client)`
- `async broadcast_event(event)` - Broadcast event to all clients
- `CHANNEL_NAME` - Canonical channel name ("security_events")

### context_enricher.py

**Purpose:** Aggregates contextual information from multiple sources for LLM prompts.

**Context Sources:**

- Zone information (from zone_service)
- Activity baselines (from baseline)
- Cross-camera activity (recent detections on other cameras)

**Key Classes:**

- `EnrichedContext` - Dataclass holding all enrichment data
- `ContextEnricher` - Service class for context aggregation

**Public API:**

- `ContextEnricher(session)` - Initialize with database session
- `async enrich_detections(camera_id, detections)` - Get context for detections
- `get_context_enricher()` - Get global singleton
- `reset_context_enricher()` - Reset singleton (for testing)

### enrichment_pipeline.py

**Purpose:** Orchestrates Model Zoo enrichment during batch analysis.

**Enrichment Flow:**

1. Load appropriate models based on detection types
2. Extract license plates from vehicles (YOLO + PaddleOCR)
3. Detect faces on persons (YOLO)
4. Generate embeddings for re-identification (CLIP)
5. Run vision-language queries (Florence-2)
6. Extract pose, clothing, vehicle type attributes
7. Assess violence, weather, image quality

**Key Classes:**

- `DetectionInput` - Input detection with bbox and image path
- `BoundingBox` - Validated bounding box coordinates
- `EnrichmentResult` - All extracted attributes and metadata
- `EnrichmentPipeline` - Main orchestration class

**Public API:**

- `EnrichmentPipeline(model_manager, redis_client)`
- `async enrich_batch(image_path, detections)` - Run full enrichment
- `get_enrichment_pipeline()` - Get global singleton
- `reset_enrichment_pipeline()` - Reset singleton (for testing)

### model_zoo.py

**Purpose:** Registry and manager for on-demand AI model loading with VRAM optimization.

**Available Models:**

| Model Name                     | Category           | VRAM (MB) | Purpose                                           |
| ------------------------------ | ------------------ | --------- | ------------------------------------------------- |
| yolo11-license-plate           | detection          | 300       | License plate detection                           |
| yolo11-face                    | detection          | 200       | Face detection                                    |
| paddleocr                      | ocr                | 100       | Text extraction from plates                       |
| clip-vit-l                     | embedding          | 800       | Re-identification embeddings                      |
| florence-2-large               | vision-language    | 1200      | Attribute extraction (disabled - runs as service) |
| yolo-world-s                   | detection          | 1500      | Open-vocabulary detection                         |
| vitpose-small                  | pose               | 1500      | Human pose keypoints (17 COCO)                    |
| depth-anything-v2-small        | depth-estimation   | 150       | Monocular depth estimation                        |
| violence-detection             | classification     | 500       | Violence detection (98.8% acc)                    |
| weather-classification         | classification     | 200       | Weather condition (5 classes)                     |
| segformer-b2-clothes           | segmentation       | 1500      | Clothing segmentation (18 categories)             |
| xclip-base                     | action-recognition | 2000      | Temporal action recognition                       |
| fashion-clip                   | classification     | 500       | Zero-shot clothing classification                 |
| brisque-quality                | quality-assessment | 0         | Image quality (CPU-based, disabled)               |
| vehicle-segment-classification | classification     | 1500      | Detailed vehicle type (11 classes)                |
| vehicle-damage-detection       | detection          | 2000      | Vehicle damage (6 damage types)                   |
| pet-classifier                 | classification     | 200       | Cat/dog classification                            |

**VRAM Budget:**

- Nemotron LLM: 21,700 MB (always loaded)
- YOLO26v2: 650 MB (always loaded)
- Available for Model Zoo: ~1,650 MB
- Models load sequentially, never concurrently

**Key Classes:**

- `ModelConfig` - Configuration for a Model Zoo model
- `ModelManager` - Manager for on-demand model loading with reference counting

**Public API:**

```python
manager = get_model_manager()

async with manager.load("yolo11-face") as model:
    results = model.predict(image)
# Model automatically unloaded and CUDA cache cleared

# Utility functions
get_model_config(name)       # Get config for model
get_enabled_models()         # List enabled models
get_available_models()       # List verified working models
get_total_vram_if_loaded(names)  # Calculate VRAM usage
```

### florence_client.py

**Purpose:** HTTP client for Florence-2 vision-language extraction.

**Service:** Runs at `http://ai-florence:8092` as dedicated container.

**Supported Tasks:**

- `<CAPTION>` - Brief caption
- `<DETAILED_CAPTION>` - Detailed caption
- `<MORE_DETAILED_CAPTION>` - Extensive description
- `<VQA>` - Visual question answering
- `<OCR>` - Text extraction with regions
- `<OD>` - Object detection
- `<DENSE_REGION_CAPTION>` - Regional captions

**Key Classes:**

- `FlorenceClient` - HTTP client for Florence service
- `FlorenceUnavailableError` - Raised when service unavailable
- `OCRRegion`, `Detection`, `CaptionedRegion` - Response types

**Public API:**

- `FlorenceClient(base_url, timeout)`
- `async extract(image, task, text_input)` - Run extraction
- `async caption(image)`, `async detailed_caption(image)`
- `async vqa(image, question)` - Visual Q&A
- `async ocr(image)` - Text extraction
- `async health_check()` - Check service health
- `get_florence_client()` - Get global singleton

### clip_client.py

**Purpose:** HTTP client for CLIP embedding generation.

**Service:** Runs at `http://ai-clip:8093` as dedicated container.

**Features:**

- 768-dimensional embeddings from CLIP ViT-L
- 10s connect timeout, 15s read timeout
- Error handling with CLIPUnavailableError

**Public API:**

- `CLIPClient(base_url, timeout)`
- `async embed(image)` - Generate 768-dim embedding
- `async health_check()` - Check service health
- `get_clip_client()` - Get global singleton

### enrichment_client.py

**Purpose:** HTTP client for the ai-enrichment service providing unified detection enrichment.

**Service:** Runs at `http://ai-enrichment:8094` as dedicated container.

**Endpoints:**

| Endpoint             | Purpose                               |
| -------------------- | ------------------------------------- |
| `/vehicle-classify`  | Vehicle type and color classification |
| `/pet-classify`      | Cat/dog classification                |
| `/clothing-classify` | FashionCLIP clothing attributes       |
| `/depth-estimate`    | Depth Anything V2 depth estimation    |
| `/object-distance`   | Object distance from depth map        |
| `/pose-analyze`      | ViTPose+ human pose keypoints         |
| `/action-classify`   | X-CLIP temporal action recognition    |
| `/enrich`            | Unified enrichment endpoint           |

**Result Dataclasses:**

- `VehicleClassificationResult` - Vehicle type, display name, confidence, is_commercial
- `PetClassificationResult` - Pet type, breed, confidence, is_household_pet
- `ClothingClassificationResult` - Clothing type, color, style, is_suspicious
- `DepthEstimationResult` - Depth map, min/max/mean depth
- `ObjectDistanceResult` - Estimated distance, proximity label
- `PoseAnalysisResult` - Keypoints, posture, alerts
- `ActionClassificationResult` - Action, confidence, is_suspicious

**Features:**

- Circuit breaker integration for resilience
- Automatic retry with exponential backoff
- Timeout configuration (10s connect, 60s read)
- Bbox validation and clamping
- Prometheus metrics for request duration

**Public API:**

```python
from backend.services.enrichment_client import get_enrichment_client

client = get_enrichment_client()

# Health check
health = await client.check_health()

# Individual classifications
vehicle = await client.classify_vehicle(image, bbox=(x1, y1, x2, y2))
pet = await client.classify_pet(image)
clothing = await client.classify_clothing(image)
pose = await client.analyze_pose(image)

# Unified enrichment
enrichment = await client.enrich(
    image=person_image,
    detection_type="person",
    bbox=(x1, y1, x2, y2),
    is_suspicious=True,
)
```

**Error Handling:**

- `EnrichmentUnavailableError` - Service unavailable (connection/timeout/5xx)
- HTTP 4xx errors - Logged and returns None (no retry)
- Invalid JSON - Logged and returns None

### reid_service.py

**Purpose:** Entity re-identification across cameras using CLIP embeddings.

**Features:**

- Generate embeddings from detected entities via ai-clip HTTP service
- Store embeddings in Redis with 24-hour TTL
- Match entities across camera views using cosine similarity
- Rate limiting via asyncio.Semaphore (configurable max concurrent requests)
- Timeout and retry logic with exponential backoff
- Batch similarity computation for performance (NEM-1071)
- Bounding box validation with clamping (NEM-1073)

**Redis Storage:**

```
entity_embeddings:{date} -> {
    "persons": [{entity_type, embedding, camera_id, timestamp, detection_id, attributes}, ...],
    "vehicles": [...]
}
TTL: 24 hours (86400 seconds)
```

**Key Classes:**

- `EntityEmbedding` - Embedding data for detected entity
- `EntityMatch` - Match result with similarity score
- `ReIdentificationService` - Main service class

**Public API:**

- `ReIdentificationService(clip_client, max_concurrent_requests, embedding_timeout, max_retries)`
- `async generate_embedding(image, bbox)` - Generate 768-dim embedding
- `async store_embedding(redis, embedding)` - Store in Redis
- `async find_matching_entities(redis, embedding, entity_type, threshold)` - Find matches
- `get_reid_service()` - Get global singleton

**Prompt Formatting:**

- `format_entity_match(match)` - Format single match for prompt
- `format_reid_context(matches_by_entity, entity_type)` - Format all matches
- `format_full_reid_context(person_matches, vehicle_matches)` - Complete context
- `format_reid_summary(person_matches, vehicle_matches)` - Brief summary

### reid_matcher.py

**Purpose:** Person re-identification matching service for tracking individuals across detections and time.

**Related to:** NEM-3043 - Implement Re-ID Matching Service

**Features:**

- Cosine similarity matching for person embeddings
- Configurable similarity threshold (default: 0.7)
- Time-window based search (default: 24 hours)
- Embedding hash for quick lookup
- Uses embeddings from Detection model's `enrichment_data.reid_embedding`

**Key Classes:**

- `ReIDMatch` - Match result with detection_id, similarity, timestamp, camera_id
- `ReIDMatcher` - Main service class for matching embeddings

**Public API:**

```python
from backend.services.reid_matcher import ReIDMatcher

async with get_session() as session:
    matcher = ReIDMatcher(session, similarity_threshold=0.7)

    # Find matches for an embedding
    matches = await matcher.find_matches(
        embedding=[0.1, 0.2, ...],  # 512-dim from OSNet
        time_window_hours=24,
        max_results=10,
        exclude_detection_id=current_detection_id,
    )

    # Check if this is a known person
    is_known, best_match = await matcher.is_known_person(
        embedding=[0.1, 0.2, ...],
        time_window_hours=24,
    )
```

**Embedding Source:**

Embeddings are stored in the Detection model:

```python
Detection.enrichment_data = {
    "reid_embedding": [0.1, 0.2, ...],  # 512-dim from OSNet-x0.25
    "reid_hash": "abc123...",           # First 16 chars of SHA-256
    ...
}
```

**Integration with Enrichment Service:**

The enrichment service (`ai-enrichment:8094`) generates OSNet embeddings via the `/enrich` endpoint when `detection_type="person"`. These embeddings are stored by the backend and can be queried by ReIDMatcher.

### scene_change_detector.py

**Purpose:** CPU-based scene change detection using Structural Similarity Index (SSIM).

**Features:**

- Compares current frames against stored baselines
- Detects significant visual changes (>10% difference by default)
- Per-camera baseline management
- Configurable similarity threshold and resize dimensions

**Key Classes:**

- `SceneChangeResult` - Detection result with similarity score and is_first_frame flag
- `SceneChangeDetector` - Main detector class

**Public API:**

- `SceneChangeDetector(similarity_threshold=0.90, resize_width=640)`
- `detect_changes(camera_id, frame)` - Compare frame to baseline
- `update_baseline(camera_id, frame)` - Set new baseline
- `reset_baseline(camera_id)` - Remove baseline
- `reset_all_baselines()` - Clear all baselines
- `get_scene_change_detector()` - Get global singleton

### audit_service.py

**Purpose:** AI pipeline auditing with self-evaluation via Nemotron.

**Features:**

- Create audit records with model contribution flags
- Self-evaluation modes:
  1. **Self-critique** - LLM critiques its own response
  2. **Rubric scoring** - Quality dimension scoring (1-5 scale)
  3. **Consistency check** - Re-analyze and compare risk scores
  4. **Prompt improvement** - Suggest prompt enhancements
- Aggregate statistics and model leaderboard

**Tracked Models:**
yolo26, florence, clip, violence, clothing, vehicle, pet, weather, image_quality, zones, baseline, cross_camera

**Quality Dimensions:**

- context_usage - Did analysis reference all relevant enrichment data?
- reasoning_coherence - Is reasoning logical and well-structured?
- risk_justification - Does evidence support the risk score?
- actionability - Is summary useful for homeowner?

**Public API:**

- `AuditService()`
- `create_partial_audit(event_id, llm_prompt, enriched_context, enrichment_result)`
- `async persist_record(audit, session)` - Save to database
- `async run_full_evaluation(audit, event, session)` - Run all 4 evaluation modes
- `async get_stats(session, days, camera_id)` - Aggregate statistics
- `async get_leaderboard(session, days)` - Model contribution ranking
- `async get_recommendations(session, days)` - Prompt improvements
- `get_audit_service()` - Get global singleton

### gpu_monitor.py

**Purpose:** NVIDIA GPU statistics monitoring with multiple fallback strategies.

**Fallback Order:**

1. pynvml (direct NVML bindings - fastest)
2. nvidia-smi subprocess (works when nvidia-smi in PATH)
3. AI container health endpoints (YOLO26v2 reports VRAM)
4. Mock data (for development without GPU)

**Public API:**

- `GPUMonitor(poll_interval, history_minutes, broadcaster, http_timeout)`
- `async start()` - Start polling loop
- `async stop()` - Stop polling
- `async poll_once()` - Single poll
- `get_latest_stats()` - Get most recent stats
- `get_history(minutes)` - Get stats history

### cleanup_service.py

**Purpose:** Automated data retention and disk space management.

**Features:**

- Delete events older than retention period
- Cascade delete associated detections
- Remove GPU stats older than retention period
- Clean up thumbnail files for deleted detections
- Clean up log entries older than log_retention_days
- Optional cleanup of original image files
- Transaction-safe with rollback support

**Key Classes:**

- `CleanupStats` - Statistics for cleanup operation (events, detections, gpu_stats, logs, thumbnails, images, space_reclaimed)
- `CleanupService` - Main cleanup service

**Public API:**

- `CleanupService(session)`
- `async cleanup(dry_run=False)` - Run cleanup
- `async get_stats()` - Get cleanup statistics

### health_monitor_orchestrator.py

**Purpose:** Health monitoring loop for the container orchestrator.

**Features:**

- Periodic health checks for all enabled services (default: every 30 seconds)
- HTTP health endpoint checks for AI services (YOLO26v2, Nemotron, Florence, CLIP)
- Command-based health checks for infrastructure (PostgreSQL, Redis)
- Container running status as fallback health check
- Grace period support for recently started containers
- Failure tracking with automatic status updates
- Callback support for health change notifications

**Note:** This is separate from `health_monitor.py` (ServiceHealthMonitor) which uses ServiceManager/ServiceConfig for AI service restart scripts. This module uses DockerClient for container management through Docker API.

**Key Classes:**

- `ManagedService` - Dataclass holding state and config for a managed container
- `ServiceRegistry` - Registry for managed services with lookup and update methods
- `HealthMonitor` - Main health monitoring loop class

**Health Check Priority:**

1. HTTP health check - If `health_endpoint` is set (e.g., `/health`)
2. Command health check - If `health_cmd` is set (e.g., `pg_isready -U security`)
3. Container running check - Fallback if neither is defined

**Grace Period:**

Services are not health-checked during their startup grace period (default: 60s for AI services, 10s for PostgreSQL). This allows time for the service to initialize.

**Public API:**

```python
from backend.services.health_monitor_orchestrator import (
    HealthMonitor,
    ManagedService,
    ServiceRegistry,
    check_http_health,
    check_cmd_health,
)

# Create registry and register services
registry = ServiceRegistry()
service = ManagedService(
    name="ai-detector",
    container_id="abc123",
    image="ghcr.io/.../yolo26:latest",
    port=8090,
    health_endpoint="/health",
    category=ServiceCategory.AI,
)
registry.register(service)

# Create and start health monitor
async with DockerClient() as docker:
    monitor = HealthMonitor(
        registry=registry,
        docker_client=docker,
        settings=orchestrator_settings,
        on_health_change=my_callback,  # Optional callback
    )
    await monitor.start()
    # ... monitor runs in background
    await monitor.stop()

# Check individual service health
healthy = await check_http_health("localhost", 8090, "/health")
healthy = await check_cmd_health(docker_client, "container_id", "pg_isready")
```

### alert_engine.py

**Purpose:** Core engine for evaluating alert rules against events.

**Features:**

- AND logic within rules (all conditions must match)
- Condition types: risk_threshold, object_types, camera_ids, zone_ids, min_confidence, schedule
- Cooldown periods using dedup_key
- Creates Alert records for triggered rules

**Public API:**

- `AlertRuleEngine(session, redis_client)`
- `async evaluate_event(event, detections, current_time)` - Evaluate all rules
- `async create_alerts_for_event(event, triggered_rules)` - Create Alert records
- `async test_rule_against_events(rule, events)` - Test rule configuration

### circuit_breaker.py

**Purpose:** Circuit breaker pattern for external service protection. This is the canonical implementation - all modules should import from here rather than from `backend.core.circuit_breaker`.

**States:**

| State     | Code | Description      | Behavior                   |
| --------- | ---- | ---------------- | -------------------------- |
| CLOSED    | 0    | Normal operation | Calls pass through         |
| OPEN      | 1    | Circuit tripped  | Calls rejected immediately |
| HALF_OPEN | 2    | Recovery testing | Limited calls allowed      |

**State Transitions:**

```
CLOSED ─(failures >= threshold)──> OPEN
   ↑                                  │
   │                                  │ (recovery_timeout elapsed)
   │                                  ↓
   └──(success_threshold met)── HALF_OPEN ──(any failure)──> OPEN
```

**Key Features:**

- Configurable failure thresholds and recovery timeouts
- Half-open state for gradual recovery testing
- Excluded exceptions that don't count as failures
- Thread-safe async implementation
- Registry for managing multiple circuit breakers
- Prometheus metrics integration (both legacy and hsi\_-prefixed)
- Protected call wrapper and async context manager

**Configuration Options:**

| Parameter           | Default | Description                                  |
| ------------------- | ------- | -------------------------------------------- |
| failure_threshold   | 5       | Failures before opening circuit              |
| recovery_timeout    | 30.0s   | Seconds before transitioning to half-open    |
| half_open_max_calls | 3       | Maximum calls allowed in half-open state     |
| success_threshold   | 2       | Successes needed in half-open to close       |
| excluded_exceptions | ()      | Exception types that don't count as failures |

**Prometheus Metrics:**

| Metric                            | Type    | Labels            | Description                    |
| --------------------------------- | ------- | ----------------- | ------------------------------ |
| `circuit_breaker_state`           | Gauge   | service           | Current state (0/1/2)          |
| `circuit_breaker_failures_total`  | Counter | service           | Total failures recorded        |
| `circuit_breaker_state_changes`   | Counter | service, from, to | State transitions              |
| `circuit_breaker_calls_total`     | Counter | service, result   | Calls by result (success/fail) |
| `circuit_breaker_rejected_total`  | Counter | service           | Calls rejected when open       |
| `hsi_circuit_breaker_state`       | Gauge   | service           | HSI-prefixed state (Grafana)   |
| `hsi_circuit_breaker_trips_total` | Counter | service           | Times circuit has tripped      |

**Public API:**

```python
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitOpenError,
    CircuitState,
    CircuitBreakerRegistry,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)

# Method 1: Create with config
config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3,
    success_threshold=2,
)
breaker = CircuitBreaker(name="ai_service", config=config)

# Method 2: Use global registry
breaker = get_circuit_breaker("ai_service", config)

# Execute through circuit breaker
try:
    result = await breaker.call(async_operation, arg1, arg2)
except CircuitBreakerError as e:
    # Handle service unavailable
    logger.warning(f"Circuit open for {e.service_name}")

# Async context manager
async with breaker:
    result = await async_operation()

# Protected call wrapper
result = await breaker.protected_call(lambda: client.fetch_data())

# Context manager with retry info
try:
    async with breaker.protect():
        result = await risky_operation()
except CircuitOpenError as e:
    # Return 503 with Retry-After header
    raise HTTPException(
        status_code=503,
        headers={"Retry-After": str(int(e.recovery_time_remaining))}
    )

# Manual control
breaker.reset()        # Reset to CLOSED
breaker.force_open()   # Force to OPEN (for maintenance)

# Get status
status = breaker.get_status()
metrics = breaker.get_metrics()
```

**Troubleshooting:**

| Issue                        | Check                                                   |
| ---------------------------- | ------------------------------------------------------- |
| Circuit stuck open           | Check `recovery_timeout` and service health             |
| Too many failures triggering | Increase `failure_threshold` or add excluded exceptions |
| Half-open not recovering     | Verify `success_threshold` and service stability        |
| Metrics not showing          | Ensure Prometheus scraping `/metrics` endpoint          |

### retry_handler.py

**Purpose:** Retry logic with exponential backoff and dead-letter queue support.

**DLQ Queues:**

- `dlq:detection_queue` - Failed detection jobs
- `dlq:analysis_queue` - Failed LLM analysis jobs

**Key Features:**

- Configurable max retries, base delay, max delay
- Exponential backoff with optional jitter
- Moves failed jobs to DLQ after exhausting retries
- DLQ inspection and management

**Public API:**

- `RetryHandler(redis_client, config)`
- `async with_retry(operation, job_data, queue_name)` - Execute with retries
- `async get_dlq_stats()` - Get DLQ statistics
- `async get_dlq_jobs(dlq_name)` - Inspect DLQ contents
- `async requeue_dlq_job(dlq_name)` - Move job back to processing

### service_registry.py

**Purpose:** Service registry with Redis persistence for Container Orchestrator.

**Key Features:**

- In-memory storage for fast access during health checks
- Redis persistence for state recovery across backend restarts
- Thread-safe concurrent access via RLock
- Redis key pattern: `orchestrator:service:{name}:state`

**ManagedService Dataclass:**

- `name` - Service identifier (e.g., "postgres", "ai-detector")
- `display_name` - Human-readable name (e.g., "PostgreSQL", "YOLO26v2")
- `container_id` - Docker container ID or None
- `image` - Container image (e.g., "postgres:16-alpine")
- `port` - Primary service port
- `health_endpoint` - HTTP health check path or None
- `health_cmd` - Docker exec health command or None
- `category` - ServiceCategory (infrastructure, ai, monitoring)
- `status` - ServiceStatus (running, stopped, unhealthy, etc.)
- `enabled` - Whether auto-restart is enabled
- `failure_count` - Consecutive health check failures
- `restart_count` - Total restarts since backend boot
- `max_failures` - Disable service after N consecutive failures (default 5)
- `restart_backoff_base` - Base delay for exponential backoff (default 5.0s)
- `restart_backoff_max` - Maximum backoff delay (default 300.0s)
- `startup_grace_period` - Seconds before counting health failures (default 60)

**Public API:**

```python
from backend.services.service_registry import (
    ServiceRegistry,
    ManagedService,
    get_service_registry,
    reset_service_registry,
)

# Get global singleton
registry = get_service_registry()

# Registration
registry.register(service)
registry.unregister(name)
registry.get(name) -> ManagedService | None
registry.get_all() -> list[ManagedService]
registry.get_by_category(category) -> list[ManagedService]
registry.get_enabled() -> list[ManagedService]

# State updates
registry.update_status(name, status)
registry.increment_failure(name) -> int  # returns new count
registry.reset_failures(name)
registry.record_restart(name)
registry.set_enabled(name, enabled)

# Redis persistence
await registry.persist_state(name)
await registry.load_state(name)
await registry.load_all_state()
await registry.clear_state(name)
```

**Redis State Schema:**

```json
{
  "enabled": true,
  "failure_count": 2,
  "last_failure_at": "2026-01-05T10:30:00+00:00",
  "last_restart_at": "2026-01-05T10:29:00+00:00",
  "restart_count": 5,
  "status": "running"
}
```

### vision_extractor.py

**Purpose:** Florence-2 attribute extraction orchestration for vehicles and persons.

**Extracted Attributes:**

**Vehicles:**

- color (e.g., "white", "red", "black")
- vehicle_type (e.g., "sedan", "SUV", "pickup", "van")
- is_commercial (boolean)
- commercial_text (visible company name/logo)
- caption (full description)

**Persons:**

- clothing (e.g., "blue jacket, dark pants")
- carrying (e.g., "backpack", "package", "nothing")
- is_service_worker (boolean)
- action (e.g., "walking", "standing", "crouching")
- caption (full description)

**Scene Analysis:**

- unusual_objects
- tools_detected
- abandoned_items
- scene_description

**Key Classes:**

- `VehicleAttributes`, `PersonAttributes` - Immutable dataclasses
- `SceneAnalysis`, `EnvironmentContext` - Scene-level data
- `BatchExtractionResult` - Complete extraction results
- `VisionExtractor` - Main service class

### performance_collector.py

**Purpose:** Collects system performance metrics from all components.

**Metrics Sources:**

| Source     | Method                         | Metrics                               |
| ---------- | ------------------------------ | ------------------------------------- |
| GPU        | pynvml or HTTP fallback        | Utilization, VRAM, temperature, power |
| YOLO26v2   | HTTP `/health` endpoint        | Status, VRAM, model name, device      |
| Nemotron   | HTTP `/slots` endpoint         | Status, active/total slots, context   |
| PostgreSQL | SQL queries (pg_stat_activity) | Connections, cache hit ratio, txns    |
| Redis      | redis-py INFO command          | Clients, memory, hit ratio, blocked   |
| Host       | psutil                         | CPU%, RAM GB, disk GB                 |
| Containers | HTTP health endpoints          | Status, health for each container     |
| Inference  | PipelineLatencyTracker         | YOLO26/Nemotron/pipeline latencies    |

**Alert Thresholds:**

- GPU temperature: warning 75C, critical 85C
- GPU utilization: warning 90%, critical 98%
- GPU VRAM: warning 90%, critical 95%
- PostgreSQL connections: warning 80%, critical 95%
- PostgreSQL cache hit: warning <90%, critical <80%
- Redis memory: warning 100MB, critical 500MB
- Host CPU: warning 80%, critical 95%
- Host RAM: warning 85%, critical 95%
- Host disk: warning 80%, critical 90%

**Public API:**

```python
from backend.services.performance_collector import PerformanceCollector

collector = PerformanceCollector()
metrics = await collector.collect_all()  # Returns PerformanceUpdate schema
await collector.close()
```

### container_discovery.py

**Purpose:** Discovers Docker containers by name pattern and creates ManagedService objects with proper configuration for the container orchestrator.

**Key Features:**

- Pattern-based container name matching (e.g., "postgres" matches "security-postgres-1")
- Pre-configured service definitions for infrastructure, AI, and monitoring services
- Category-based discovery filtering (infrastructure, AI, monitoring)
- Automatic configuration assignment from matched patterns
- Supports both HTTP health endpoints and Docker exec health commands

**Pre-configured Service Categories:**

| Category       | Services                                           | Restart Policy        |
| -------------- | -------------------------------------------------- | --------------------- |
| Infrastructure | PostgreSQL (:5432), Redis (:6379)                  | Critical - aggressive |
| AI             | YOLO26v2, Nemotron, Florence-2, CLIP, Enrichment   | Standard backoff      |
| Monitoring     | Prometheus, Grafana, Redis Exporter, JSON Exporter | Lenient               |

**Key Classes:**

- `ServiceConfig` - Configuration dataclass for service patterns (port, health check, limits)
- `ManagedService` - Represents a discovered container with config values
- `ContainerDiscoveryService` - Main service for container discovery

**Public API:**

```python
from backend.services.container_discovery import (
    ContainerDiscoveryService,
    ServiceConfig,
    ManagedService,
    ALL_CONFIGS,
    INFRASTRUCTURE_CONFIGS,
    AI_CONFIGS,
    MONITORING_CONFIGS,
)

# Create discovery service
service = ContainerDiscoveryService(docker_client)

# Discover all containers matching known patterns
all_services = await service.discover_all()

# Discover by category
ai_services = await service.discover_by_category(ServiceCategory.AI)

# Get config for a service name
config = service.get_config("postgres")

# Match container name against patterns (returns config key or None)
config_key = service.match_container_name("security-postgres-1")  # Returns "postgres"
```

### lifecycle_manager.py

**Purpose:** Self-healing restart logic with exponential backoff for the container orchestrator.

**Key Features:**

- Exponential backoff calculation: base \* 2^failure_count, capped at max
- Category-specific defaults for Infrastructure, AI, and Monitoring services
- Automatic disabling of services after max_failures consecutive failures
- Callbacks for restart and disabled events
- State persistence to Redis for durability across backend restarts

**Self-Healing Decision Tree:**

```
Container Missing/Stopped/Unhealthy
            |
            v
    +-------------------+
    | failure_count >=  |--Yes--> Mark DISABLED, alert, skip
    | max_failures?     |
    +-------------------+
            | No
            v
    +-------------------+
    | Backoff elapsed?  |--No---> Skip this cycle
    | (exponential)     |
    +-------------------+
            | Yes
            v
    +-------------------+
    | Restart container |
    | Increment counts  |
    | Record timestamp  |
    +-------------------+
```

**Backoff Calculation:**

```python
# Exponential backoff: 5s, 10s, 20s, 40s, 80s, 160s, 300s (cap)
def calculate_backoff(failure_count, base=5.0, max_backoff=300.0):
    return min(base * (2 ** failure_count), max_backoff)
```

**Category-Specific Defaults:**

| Category       | max_failures | backoff_base | backoff_max |
| -------------- | ------------ | ------------ | ----------- |
| Infrastructure | 10           | 2.0s         | 60s         |
| AI             | 5            | 5.0s         | 300s        |
| Monitoring     | 3            | 10.0s        | 600s        |

**Key Classes:**

- `ManagedService` - Dataclass representing a managed container with lifecycle tracking
- `ServiceRegistry` - Registry for managing ManagedService instances with Redis persistence
- `LifecycleManager` - Main orchestration class for self-healing restart logic

**Public API:**

```python
from backend.services.lifecycle_manager import (
    LifecycleManager,
    ManagedService,
    ServiceRegistry,
    calculate_backoff,
)

# Create lifecycle manager with dependencies
manager = LifecycleManager(
    registry=registry,
    docker_client=docker_client,
    on_restart=my_restart_callback,
    on_disabled=my_disabled_callback,
)

# Backoff calculation
backoff = manager.calculate_backoff(service)
should_restart = manager.should_restart(service)
remaining = manager.backoff_remaining(service)

# Lifecycle actions
await manager.restart_service(service)
await manager.start_service(service)
await manager.stop_service(service)
await manager.enable_service("ai-detector")  # Reset failures and enable
await manager.disable_service("ai-detector")

# Self-healing handlers
await manager.handle_unhealthy(service)
await manager.handle_stopped(service)
await manager.handle_missing(service)
```

**ServiceRegistry API:**

```python
registry = ServiceRegistry(redis_client=redis)

# Register a service
registry.register(service)

# Get service(s)
service = registry.get("ai-detector")
all_services = registry.get_all()
enabled = registry.get_enabled_services()

# Update tracking
registry.record_restart("ai-detector")
new_count = registry.increment_failure("ai-detector")
registry.reset_failures("ai-detector")
registry.update_status("ai-detector", ContainerServiceStatus.RUNNING)
registry.set_enabled("ai-detector", False)

# Persistence
await registry.persist_state("ai-detector")
await registry.load_state()
```

### container_orchestrator.py

**Purpose:** Coordinates container discovery, health monitoring, lifecycle management, and real-time WebSocket broadcasting of service status changes.

**Key Features:**

- Service discovery using container name patterns
- Health monitoring with configurable intervals
- Self-healing restart logic with exponential backoff
- WebSocket broadcast of service status changes
- Integration with HealthMonitor and LifecycleManager components

**Public API:**

```python
from backend.services.container_orchestrator import (
    ContainerOrchestrator,
    create_service_status_event,
)

# Create orchestrator with broadcast function
orchestrator = ContainerOrchestrator(
    docker_client=docker_client,
    redis_client=redis_client,
    settings=settings,
    broadcast_fn=event_broadcaster.broadcast_service_status,
)

# Start orchestrator (discovery + monitoring)
await orchestrator.start()

# Query services
all_services = orchestrator.get_all_services()
service = orchestrator.get_service("ai-detector")

# Manual control
await orchestrator.restart_service("ai-detector")
await orchestrator.enable_service("ai-detector")
await orchestrator.disable_service("ai-detector")
await orchestrator.start_service("ai-detector")

# Stop orchestrator
await orchestrator.stop()
```

**Broadcasts service status events when:**

- Service discovered on startup
- Health check passes after failure (recovery)
- Health check fails
- Container restart initiated
- Container restart succeeded
- Container restart failed
- Service disabled (max failures)
- Service manually enabled
- Service manually disabled
- Service manually restarted

### prompt_parser.py

**Purpose:** Prompt parsing utilities for smart insertion of suggestions.

**Key Features:**

- Parse system prompts to identify optimal insertion points
- Detect variable style patterns (curly/angle/dollar)
- Generate insertion text matching detected style
- Validate prompt syntax (unclosed brackets, duplicate variables)
- Apply suggestions to prompts programmatically

**Public API:**

```python
from backend.services.prompt_parser import (
    find_insertion_point,
    detect_variable_style,
    generate_insertion_text,
    validate_prompt_syntax,
    apply_suggestion_to_prompt,
)

# Find where to insert a suggestion
insert_idx, insert_type = find_insertion_point(
    prompt,
    target_section="Camera & Time Context",
    insertion_point="append"
)

# Detect variable style in prompt
style = detect_variable_style(prompt)  # {'format': 'curly', 'label_style': 'colon', ...}

# Generate insertion text
new_text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

# Validate prompt syntax
warnings = validate_prompt_syntax(prompt)

# Apply suggestion to prompt (convenience function)
modified_prompt = apply_suggestion_to_prompt(
    prompt,
    target_section="Camera & Time Context",
    insertion_point="append",
    proposed_label="Time Since Last Event",
    proposed_variable="time_since_last_event"
)
```

### batch_fetch.py

**Purpose:** Batch fetching service for detections to avoid N+1 query problems.

**Key Features:**

- Deduplicate input IDs
- Split IDs into configurable batch sizes (default 250, max 1000)
- Execute batched queries with IN clauses
- Aggregate results efficiently
- Optional ordering by detected_at timestamp

**Configuration:**

- `MIN_BATCH_SIZE`: 1
- `DEFAULT_BATCH_SIZE`: 250 (balanced between query count and IN clause size)
- `MAX_BATCH_SIZE`: 1000 (PostgreSQL handles IN clauses well up to ~1000 items)

**Public API:**

```python
from backend.services.batch_fetch import (
    batch_fetch_detections,
    batch_fetch_detections_by_ids,
    batch_fetch_file_paths,
)

async with get_session() as session:
    # Fetch as list
    detections = await batch_fetch_detections(session, detection_ids)

    # Fetch as dict for O(1) lookup
    detection_map = await batch_fetch_detections_by_ids(session, detection_ids)
    detection = detection_map.get(123)

    # Fetch only file paths (optimized)
    paths = await batch_fetch_file_paths(session, detection_ids)
```

### inference_semaphore.py

**Purpose:** Shared semaphore for AI inference concurrency control.

**Key Features:**

- Limits concurrent AI inference operations across all services
- Prevents GPU/AI service overload under high traffic
- Configurable via `AI_MAX_CONCURRENT_INFERENCES` env var (default: 4)
- Global singleton pattern for shared resource management

**Benefits:**

- Prevents GPU OOM errors under high load
- Ensures predictable latency by preventing request pileup
- Allows graceful degradation instead of service crashes
- Shared limit ensures total AI load stays bounded

**Public API:**

```python
from backend.services.inference_semaphore import get_inference_semaphore

async def detect_objects(...):
    semaphore = get_inference_semaphore()
    async with semaphore:
        # Perform AI inference (this block limited to N concurrent operations)
        result = await ai_client.detect(...)
    return result
```

### partition_manager.py

**Purpose:** PostgreSQL native partition management for high-volume time-series tables.

**Key Features:**

- Automatic partition creation for current and future months
- Configurable partition intervals (monthly, weekly)
- Automatic cleanup of old partitions beyond retention period
- Partition statistics and monitoring
- Idempotent partition creation (safe to run multiple times)

**Partitioned Tables:**

| Table      | Partition Column | Interval | Retention |
| ---------- | ---------------- | -------- | --------- |
| detections | detected_at      | monthly  | 12 months |
| events     | started_at       | monthly  | 12 months |
| logs       | timestamp        | monthly  | 6 months  |
| gpu_stats  | recorded_at      | weekly   | 3 months  |

**Partition Naming Convention:**

- Monthly: `{table}_y{year}m{month:02d}` (e.g., `detections_y2026m01`)
- Weekly: `{table}_y{year}w{week:02d}` (e.g., `gpu_stats_y2026w01`)

**Public API:**

```python
from backend.services.partition_manager import PartitionManager

manager = PartitionManager()
await manager.ensure_partitions()  # Create missing partitions
await manager.cleanup_old_partitions()  # Remove expired partitions
stats = await manager.get_partition_stats()  # Get partition info
result = await manager.run_maintenance()  # Full maintenance (create + cleanup)
```

### degradation_manager.py

**Purpose:** Graceful degradation management for system resilience during partial outages.

**Key Features:**

- Track service health states (Redis, YOLO26v2, Nemotron)
- Fallback to disk-based queues when Redis is down
- In-memory queue fallback when Redis unavailable
- Automatic recovery detection
- Integration with circuit breakers
- Job queueing for later processing
- Configurable health check timeouts

**Degradation Modes:**

| Mode     | Description               | Available Features        |
| -------- | ------------------------- | ------------------------- |
| NORMAL   | All services healthy      | Full functionality        |
| DEGRADED | Some services unavailable | events, media (read-only) |
| MINIMAL  | Critical services down    | media only                |
| OFFLINE  | All services down         | Queueing only             |

**Fallback Queue Hierarchy:**

1. **Redis queue** - Primary storage for jobs
2. **Disk fallback** - JSON files on disk when Redis is down
3. **Memory queue** - In-memory deque when disk is unavailable (max 1000 items)

**Redis Keys:**

```
degraded:jobs      -> LIST of queued jobs
```

**Disk Fallback Storage:**

```
~/.cache/hsi_fallback/{queue_name}/{timestamp}_{counter}.json
```

**Public API:**

```python
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    DegradationServiceStatus,
    get_degradation_manager,
    reset_degradation_manager,
    FallbackQueue,
)

# Get global singleton
manager = get_degradation_manager(redis_client=redis)

# Register services for monitoring
manager.register_service(
    name="ai_detector",
    health_check=detector.health_check,
    critical=True,
)

# Check service health
if manager.is_service_healthy("yolo26"):
    # Proceed with AI analysis
    pass

# Queue with automatic fallback
await manager.queue_with_fallback("detection_queue", item)

# Determine if job should be queued
if manager.should_queue_job("detection"):
    await manager.queue_job_for_later("detection", job_data)
else:
    await process_job(job_data)

# Drain fallback queue when recovered
drained_count = await manager.drain_fallback_queue("detection_queue")

# Get status
status = manager.get_status()
# Returns: {"mode": "degraded", "redis_healthy": False, "memory_queue_size": 5, ...}

# Start/stop background health checks
await manager.start()
await manager.stop()
```

**Troubleshooting:**

| Issue                    | Check                                                  |
| ------------------------ | ------------------------------------------------------ |
| Stuck in DEGRADED mode   | Verify service health via `manager.get_status()`       |
| Jobs not processing      | Check `await manager.get_pending_job_count()`          |
| Fallback queue growing   | Ensure Redis is healthy, call `drain_fallback_queue()` |
| Health checks timing out | Adjust `health_check_timeout` in settings              |

### health_service_registry.py

**Purpose:** Centralized dependency injection registry for health monitoring services.

**Key Features:**

- Replaces global state pattern with proper dependency injection (NEM-2611)
- Tracks background workers and health monitors
- Circuit breaker for external health checks
- FastAPI dependency support for route handlers
- Worker status aggregation for health endpoints

**Tracked Services:**

| Service                  | Purpose                    | Critical |
| ------------------------ | -------------------------- | -------- |
| `gpu_monitor`            | GPU resource monitoring    | No       |
| `cleanup_service`        | Data cleanup service       | No       |
| `system_broadcaster`     | WebSocket system status    | No       |
| `file_watcher`           | File system monitoring     | Yes      |
| `pipeline_manager`       | Detection/analysis workers | Yes      |
| `batch_aggregator`       | Batch processing           | No       |
| `degradation_manager`    | Service degradation        | No       |
| `service_health_monitor` | Auto-recovery monitoring   | No       |
| `performance_collector`  | Performance metrics        | No       |
| `health_event_emitter`   | WebSocket health events    | No       |

**Circuit Breaker for Health Checks:**

The registry includes a `HealthCircuitBreaker` to prevent health checks from blocking on slow services:

- Failure threshold: 3 consecutive failures before opening
- Reset timeout: 30 seconds before retrying
- States: CLOSED (normal), OPEN (skip checks, return cached error)

**Public API:**

```python
from backend.services.health_service_registry import (
    HealthServiceRegistry,
    WorkerStatus,
    HealthCircuitBreaker,
    get_health_registry,
    get_health_registry_optional,
)

# FastAPI dependency
@app.get("/health")
async def get_health(
    registry: HealthServiceRegistry = Depends(get_health_registry),
):
    statuses = registry.get_worker_statuses()
    return {"workers": [s.__dict__ for s in statuses]}

# Get registry from DI container
container = get_container()
registry = await container.get_async("health_service_registry")

# Check critical workers
if registry.are_critical_pipeline_workers_healthy():
    # Detection and analysis workers are running
    pass

# Get pipeline status
pipeline_status = registry.get_pipeline_status()

# Register services (during startup)
registry.register_gpu_monitor(gpu_monitor)
registry.register_pipeline_manager(pipeline_manager)
registry.register_degradation_manager(degradation_manager)

# Get worker statuses
statuses: list[WorkerStatus] = registry.get_worker_statuses()
for status in statuses:
    print(f"{status.name}: {'running' if status.running else status.message}")

# Circuit breaker usage
cb = registry.circuit_breaker
if not cb.is_open("ai_service"):
    try:
        result = await check_ai_health()
        cb.record_success("ai_service")
    except Exception as e:
        cb.record_failure("ai_service", str(e))
```

### health_event_emitter.py

**Purpose:** WebSocket health event broadcasting with change detection.

**Key Features:**

- Tracks health state for each system component
- Emits WebSocket events only on status changes (prevents spam)
- Aggregates component health into overall system status
- Critical components (database, redis) impact overall health more heavily
- Thread-safe singleton pattern

**Health Components Monitored:**

| Component  | Check Method                | Critical |
| ---------- | --------------------------- | -------- |
| database   | PostgreSQL connection/query | Yes      |
| redis      | Redis connection/memory     | Yes      |
| ai_service | Nemotron + YOLO26v2 health  | No       |
| gpu        | CUDA availability/memory    | No       |
| storage    | Disk space for /export      | No       |

**Health Status Values:**

| Status    | Priority | Description                    |
| --------- | -------- | ------------------------------ |
| UNHEALTHY | 0        | Component is failing           |
| DEGRADED  | 1        | Component is partially working |
| UNKNOWN   | 2        | Status not yet determined      |
| HEALTHY   | 3        | Component is working normally  |

**Event Types Emitted:**

- `system.health_changed` - When health status changes
- `system.error` - When a system-level error occurs

**WebSocket Payload Examples:**

```json
{
  "type": "system.health_changed",
  "data": {
    "health": "degraded",
    "previous_health": "healthy",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "ai_service": "unhealthy",
      "gpu": "healthy"
    },
    "changed_component": "ai_service",
    "component_previous_status": "healthy",
    "component_new_status": "unhealthy",
    "timestamp": "2026-01-18T10:30:00+00:00"
  }
}
```

**Public API:**

```python
from backend.services.health_event_emitter import (
    HealthEventEmitter,
    HealthStatus,
    ErrorSeverity,
    get_health_event_emitter,
    emit_system_error,
    reset_health_event_emitter,
)

# Get singleton emitter
emitter = get_health_event_emitter()

# Set WebSocket emitter (during startup)
emitter.set_emitter(websocket_emitter_service)

# Check and emit health changes (returns True if status changed)
changed = await emitter.check_and_emit(
    component="database",
    new_status="unhealthy",
    details={"error": "Connection refused"},
)

# Update multiple components at once
changed_components = await emitter.update_all_components(
    statuses={"database": "healthy", "redis": "degraded"},
    details={"redis": {"memory_mb": 450}},
)

# Emit system error
await emit_system_error(
    error_code="AI_SERVICE_CRASH",
    message="Nemotron service crashed unexpectedly",
    severity="high",
    details={"exit_code": 137},
    recoverable=True,
)

# Get current status
overall = emitter.get_overall_status()
component_statuses = emitter.get_all_component_statuses()
```

**Overall Status Calculation:**

1. If any critical component (database, redis) is UNHEALTHY -> overall is UNHEALTHY
2. Otherwise, take the worst status across all components

### orphan_cleanup_service.py

**Purpose:** Periodic cleanup of orphaned files (files on disk without database records).

**Key Features:**

- Configurable scan interval (default: 24 hours)
- Configurable age threshold before deletion (default: 24 hours)
- Integration with job tracking system for progress monitoring
- WebSocket notification on cleanup completion
- Safe deletion with file age verification
- Multiple file naming pattern recognition

**File Extensions Scanned:**

- `.mp4`, `.webm`, `.mkv`, `.avi`

**Event ID Extraction Patterns:**

| Pattern           | Example          | Extracted ID |
| ----------------- | ---------------- | ------------ |
| `event_<id>`      | `event_123.mp4`  | 123          |
| `clip_event_<id>` | `clip_event_456` | 456          |
| `<id>_clip`       | `789_clip.webm`  | 789          |
| Numeric filename  | `123.mp4`        | 123          |

**Orphan Detection Logic:**

1. Extract event ID from filename
2. Check if event exists in database
3. If event exists, check if file is referenced in `clip_path`
4. If not referenced, file is an orphan

**Safety Measures:**

- Files must be older than `age_threshold_hours` before deletion
- Files without extractable event IDs are checked against all clip_paths
- On database error, file is NOT deleted (safe default)

**Public API:**

```python
from backend.services.orphan_cleanup_service import (
    OrphanedFileCleanupService,
    OrphanedFileCleanupStats,
    get_orphan_cleanup_service,
    reset_orphan_cleanup_service,
    JOB_TYPE_ORPHAN_CLEANUP,
)

# Get singleton service
service = get_orphan_cleanup_service(
    scan_interval_hours=24,
    age_threshold_hours=24,
    clips_directory="/path/to/clips",
    enabled=True,
    job_tracker=job_tracker,
    broadcast_callback=my_broadcast_fn,
)

# Start background cleanup loop
await service.start()

# Run cleanup manually
stats = await service.run_cleanup()
print(f"Scanned: {stats.files_scanned}")
print(f"Orphans found: {stats.orphans_found}")
print(f"Deleted: {stats.files_deleted}")
print(f"Space reclaimed: {stats.space_reclaimed} bytes")
print(f"Skipped (too young): {stats.files_skipped_young}")

# Get service status
status = service.get_status()
# Returns: {"running": True, "enabled": True, "scan_interval_hours": 24, ...}

# Stop service
await service.stop()

# Use as async context manager
async with service:
    # Service runs in background
    pass  # Automatically stopped on exit
```

**Job Tracker Integration:**

When `job_tracker` is provided:

- Creates job with type `orphan_cleanup`
- Updates progress as files are scanned (0-90%)
- Completes job with cleanup statistics
- Fails job on critical errors

**Troubleshooting:**

| Issue                   | Check                                                   |
| ----------------------- | ------------------------------------------------------- |
| Files not being deleted | Verify files are older than `age_threshold_hours`       |
| Wrong files deleted     | Check event ID extraction patterns in logs              |
| Service not running     | Check `enabled` setting and `service.get_status()`      |
| High disk usage         | Decrease `age_threshold_hours` or `scan_interval_hours` |

### evaluation_queue.py

**Purpose:** Priority queue for AI audit evaluations backed by Redis.

**Key Features:**

- Redis sorted set (ZSET) for priority-based ordering
- Higher priority events (higher risk scores) are evaluated first
- Persists across restarts (Redis-backed)
- Supports queue status and management

**Redis Storage:**

- Key: `evaluation:pending` (sorted set)
- Members: event IDs (as strings)
- Scores: priorities (higher = evaluated first)

**Public API:**

```python
from backend.services.evaluation_queue import get_evaluation_queue

queue = get_evaluation_queue(redis_client)

await queue.enqueue(event_id, priority=risk_score)  # Add to queue
event_id = await queue.dequeue()  # Get highest priority event
size = await queue.get_size()  # Get queue size
pending = await queue.get_pending_events(limit=100)  # List pending events
removed = await queue.remove(event_id)  # Remove specific event
is_queued = await queue.is_queued(event_id)  # Check if event is queued
```

### background_evaluator.py

**Purpose:** Background service that runs AI audit evaluations automatically when GPU is idle.

**Key Features:**

- Monitors GPU utilization and only processes when idle
- Detection and analysis queues take priority over evaluation
- Higher risk events are evaluated first (priority queue)
- Configurable idle threshold (default: 20%) and duration requirements (default: 5s)

**Processing Flow:**

1. Check if detection/analysis queues are empty
2. Check if GPU has been idle for required duration
3. Dequeue highest priority event from evaluation queue
4. Run full AI audit evaluation (4 LLM calls)
5. Repeat or wait based on queue status

**Configuration:**

- `gpu_idle_threshold`: GPU utilization % below which GPU is idle (default: 20%)
- `idle_duration_required`: Seconds GPU must be idle before processing (default: 5s)
- `poll_interval`: How often to check for work (default: 5s)
- `enabled`: Whether background evaluation is enabled (default: True)

**Public API:**

```python
from backend.services.background_evaluator import get_background_evaluator

evaluator = get_background_evaluator(
    redis_client=redis_client,
    gpu_monitor=gpu_monitor,
    evaluation_queue=evaluation_queue,
    audit_service=audit_service,
)

await evaluator.start()  # Start background loop
is_idle = await evaluator.is_gpu_idle()  # Check GPU idle status
can_process = await evaluator.can_process_evaluation()  # Check if can process
processed = await evaluator.process_one()  # Process one evaluation manually
await evaluator.stop()  # Stop background loop
```

### token_counter.py

**Purpose:** Token counting service for LLM context window management.

**Key Features:**

- Tiktoken-based token counting with configurable encoding
- Context utilization tracking with warning thresholds
- Intelligent truncation of enrichment data by priority
- Prometheus metrics for context utilization monitoring

**Configuration:**

- `encoding_name`: Tiktoken encoding (default: from settings, usually "cl100k_base")
- `context_window`: Max context window (default: 32,768 for Nemotron)
- `max_output_tokens`: Tokens reserved for output (default: 1,536)
- `warning_threshold`: Utilization threshold for warnings (default: 0.85 = 85%)

**Truncation Priority (lowest priority truncated first):**

1. `depth_context` - Depth estimation (lowest priority)
2. `pose_analysis` - Human pose estimation
3. `action_recognition` - Action recognition
4. `pet_classification_context` - Pet classification
5. `image_quality_context` - Image quality assessment
6. `weather_context` - Weather classification
7. `vehicle_damage_context` - Vehicle damage detection
8. `vehicle_classification_context` - Vehicle type classification
9. `clothing_analysis_context` - Clothing analysis
10. `violence_context` - Violence detection
11. `reid_context` - Re-identification matches
12. `cross_camera_summary` - Cross-camera activity
13. `baseline_comparison` - Baseline anomaly detection
14. `zone_analysis` - Zone context
15. `detections_with_all_attributes` - Core detection data (high priority)
16. `scene_analysis` - Scene analysis (highest priority)

**Public API:**

```python
from backend.services.token_counter import (
    get_token_counter,
    count_prompt_tokens,
    validate_prompt_tokens,
)

counter = get_token_counter()

# Count tokens
token_count = counter.count_tokens(prompt_text)
token_count = count_prompt_tokens(prompt_text)  # Convenience function

# Validate prompt fits in context window
result = counter.validate_prompt(prompt, max_output_tokens=1536)
result = validate_prompt_tokens(prompt, max_output_tokens=1536)  # Convenience function
if not result.is_valid:
    # Handle truncation
    truncated = counter.truncate_enrichment_data(prompt, max_tokens)

# Truncate to fit
truncated_text = counter.truncate_to_fit(text, max_tokens, suffix="...[truncated]")

# Estimate enrichment token counts
token_counts = counter.estimate_enrichment_tokens({
    "zone_analysis": zone_text,
    "reid_context": reid_text,
})

# Get context budget
budget = counter.get_context_budget()  # Returns dict with context_window, max_output_tokens, available_for_prompt
```

### clip_generator.py

**Purpose:** Event clip generator service for creating video clips around detected events.

**Key Features:**

- Extract clips from existing video files using ffmpeg
- Generate video from image sequences (MP4/GIF)
- Configurable pre/post roll seconds (default: 5s each)
- Store clips in configurable directory
- Associate clips with Event records

**Output Format:**

- File: `{clips_directory}/{event_id}_clip.mp4` or `{event_id}_clip.gif`
- Codec: libx264 (H.264) for MP4
- Audio: copy (if present) or none

**Security:**

- All user inputs are validated before use in subprocess calls
- Uses subprocess with list arguments (never shell=True)
- Paths are validated to prevent command-line option injection

**Public API:**

```python
from backend.services.clip_generator import get_clip_generator

generator = get_clip_generator()

# Generate clip from video
clip_path = await generator.generate_clip_from_video(
    event,
    video_path="/path/to/video.mp4",
    pre_seconds=5,
    post_seconds=5
)

# Generate clip from images
clip_path = await generator.generate_clip_from_images(
    event,
    image_paths=["/path/to/img1.jpg", "/path/to/img2.jpg"],
    fps=2,
    output_format="mp4"  # or "gif"
)

# Generate clip automatically (chooses best method)
clip_path = await generator.generate_clip_for_event(
    event,
    video_path="/path/to/video.mp4",  # Optional
    image_paths=[...],  # Optional
    fps=2
)

# Query clips
clip_path = generator.get_clip_path(event_id)  # Returns Path or None
deleted = generator.delete_clip(event_id)  # Returns bool
```

### clip_loader.py

**Purpose:** CLIP model loader for re-identification embeddings.

**Key Features:**

- Async loading of CLIP ViT-L models from HuggingFace
- Generates 768-dimensional embeddings for entity re-identification
- Automatic GPU detection and device placement
- Thread pool execution to avoid blocking

**Public API:**

```python
from backend.services.clip_loader import load_clip_model

# Load CLIP model
result = await load_clip_model("openai/clip-vit-large-patch14")
model = result["model"]
processor = result["processor"]

# Model is automatically moved to GPU if available
```

### ai_fallback.py

**Purpose:** AI service fallback strategies for graceful degradation when AI services become unavailable.

**Key Features:**

- Per-service fallback strategies for YOLO26v2, Nemotron, Florence-2, and CLIP
- Cached risk score retrieval for fallback values
- Default value generation based on object types
- Health-based routing and degradation level tracking
- WebSocket status broadcasting for status changes
- Integration with circuit breakers

**Degradation Levels:**

- `NORMAL` - All services healthy
- `DEGRADED` - Non-critical services (Florence, CLIP) down
- `MINIMAL` - Critical services (YOLO26v2, Nemotron) partially available
- `OFFLINE` - All AI services down

**Key Classes:**

- `AIService` - Enum of AI service identifiers (yolo26, nemotron, florence, clip)
- `DegradationLevel` - System degradation levels
- `ServiceState` - State information for a single AI service
- `FallbackRiskAnalysis` - Fallback risk analysis result when Nemotron unavailable
- `RiskScoreCache` - Cache for risk score patterns
- `AIFallbackService` - Main service class

**Public API:**

```python
from backend.services.ai_fallback import (
    AIFallbackService,
    AIService,
    DegradationLevel,
    get_ai_fallback_service,
    reset_ai_fallback_service,
)

service = get_ai_fallback_service()
await service.start()

# Check service availability
if service.is_service_available(AIService.NEMOTRON):
    result = await analyzer.analyze(...)
else:
    result = service.get_fallback_risk_analysis(
        camera_name="front_door",
        object_types=["person", "vehicle"]
    )

# Get degradation status
status = service.get_degradation_status()
level = service.get_degradation_level()
features = service.get_available_features()

# Convenience checks
if service.should_skip_detection():
    pass  # YOLO26v2 unavailable
if service.should_use_default_risk():
    pass  # Nemotron unavailable

await service.stop()
```

### nemotron_streaming.py

**Purpose:** Streaming extensions for NemotronAnalyzer to enable progressive LLM response updates during long inference times.

**Key Features:**

- Server-Sent Events (SSE) streaming from llama.cpp
- Progressive content updates during LLM inference
- Error handling with typed error codes
- Full batch analysis with streaming progress events
- Integration with inference semaphore for concurrency control

**Streaming Event Types:**

- `StreamingProgressEvent` - Incremental content chunks
- `StreamingCompleteEvent` - Final analysis result
- `StreamingErrorEvent` - Error with code and recoverability flag

**Error Codes:**

- `BATCH_NOT_FOUND` - Batch ID not found in Redis
- `NO_DETECTIONS` - Batch has no detections
- `LLM_TIMEOUT` - LLM request timed out
- `LLM_CONNECTION_ERROR` - Cannot connect to LLM server
- `LLM_SERVER_ERROR` - LLM inference failed
- `INTERNAL_ERROR` - Unexpected internal error

**Public API:**

```python
from backend.services.nemotron_streaming import (
    call_llm_streaming,
    analyze_batch_streaming,
)

# Stream LLM response chunks
async for chunk in call_llm_streaming(
    analyzer=nemotron_analyzer,
    camera_name="Front Door",
    start_time="2024-01-15T10:30:00",
    end_time="2024-01-15T10:31:30",
    detections_list="- person detected at 10:30:15 (confidence: 0.95)",
    enriched_context=context,
    enrichment_result=enrichment,
):
    print(chunk, end="")  # Progressive output

# Full streaming batch analysis
async for event in analyze_batch_streaming(
    analyzer=nemotron_analyzer,
    batch_id="batch_uuid",
    camera_id="front_door",
    detection_ids=[1, 2, 3],
):
    if event["type"] == "progress":
        print(event["content"], end="")
    elif event["type"] == "complete":
        print(f"Risk score: {event['risk_score']}")
    elif event["type"] == "error":
        print(f"Error: {event['error_message']}")
```

### managed_service.py

**Purpose:** Canonical ManagedService and ServiceRegistry definitions for the Container Orchestrator system.

**Key Features:**

- Single authoritative definitions used throughout container orchestration
- Redis persistence for state recovery across backend restarts
- Thread-safe concurrent access via RLock
- Factory methods for creating services from configs
- Serialization/deserialization for JSON and Redis storage

**Key Classes:**

- `ServiceConfig` - Configuration for service patterns used in discovery
- `ManagedService` - Container service managed by the orchestrator
- `ServiceRegistry` - Registry with optional Redis persistence

**ManagedService Fields:**

- Identity: name, display_name, container_id, image, port
- Health: health_endpoint, health_cmd
- Classification: category (infrastructure, ai, monitoring)
- Runtime: status, enabled
- Tracking: failure_count, last_failure_at, restart_count, last_restart_at
- Limits: max_failures, restart_backoff_base, restart_backoff_max, startup_grace_period

**Public API:**

```python
from backend.services.managed_service import (
    ManagedService,
    ServiceConfig,
    ServiceRegistry,
    get_service_registry,
    reset_service_registry,
)
from backend.api.schemas.services import ServiceCategory, ContainerServiceStatus

# Create a managed service
service = ManagedService(
    name="ai-detector",
    display_name="YOLO26v2",
    container_id="abc123",
    image="ghcr.io/.../yolo26:latest",
    port=8090,
    health_endpoint="/health",
    category=ServiceCategory.AI,
    status=ContainerServiceStatus.RUNNING,
)

# Get global registry
registry = await get_service_registry()

# Register and manage services
registry.register(service)
registry.update_status("ai-detector", ContainerServiceStatus.UNHEALTHY)
registry.increment_failure("ai-detector")
registry.record_restart("ai-detector")

# Persist to Redis
await registry.persist_state("ai-detector")
await registry.load_state("ai-detector")
```

### model_loader_base.py

**Purpose:** Abstract base class for all model loaders in the Model Zoo.

**Key Features:**

- Consistent interface for 14+ model loaders
- Generic type parameter for model instance types
- Required properties: model_name, vram_mb
- Required methods: load(device), unload()
- VRAM budget management integration

**Abstract Interface:**

```python
class ModelLoaderBase(ABC, Generic[T]):
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Unique model identifier (e.g., 'clip-vit-l')."""
        ...

    @property
    @abstractmethod
    def vram_mb(self) -> int:
        """Estimated VRAM usage in megabytes."""
        ...

    @abstractmethod
    async def load(self, device: str = "cuda") -> T:
        """Load model and return instance."""
        ...

    @abstractmethod
    async def unload(self) -> None:
        """Unload model and free GPU memory."""
        ...
```

**Usage Example:**

```python
from backend.services.model_loader_base import ModelLoaderBase

class CLIPLoader(ModelLoaderBase[dict]):
    @property
    def model_name(self) -> str:
        return "clip-vit-l"

    @property
    def vram_mb(self) -> int:
        return 800

    async def load(self, device: str = "cuda") -> dict:
        from transformers import CLIPModel, CLIPProcessor
        model = CLIPModel.from_pretrained(self.model_path)
        processor = CLIPProcessor.from_pretrained(self.model_path)
        if device.startswith("cuda"):
            model = model.cuda()
        return {"model": model, "processor": processor}

    async def unload(self) -> None:
        del self._model
        torch.cuda.empty_cache()
```

### typed_prompt_config.py

**Purpose:** Type-safe prompt configuration with Python generics and Pydantic validation.

**Key Features:**

- Compile-time type checking via mypy
- Runtime validation via Pydantic
- Model-specific parameter types
- Generic template with type constraints
- Factory functions for template creation

**Parameter Types:**

| Type                      | Purpose                        | Required Fields                                  |
| ------------------------- | ------------------------------ | ------------------------------------------------ |
| `NemotronPromptParams`    | Nemotron risk analysis         | camera_name, timestamp, day_of_week, time_of_day |
| `Florence2PromptParams`   | Florence-2 VQA                 | queries                                          |
| `YoloWorldPromptParams`   | YOLO-World detection           | classes, confidence_threshold                    |
| `XClipPromptParams`       | X-CLIP action recognition      | action_classes                                   |
| `FashionClipPromptParams` | Fashion-CLIP clothing analysis | clothing_categories, suspicious_indicators       |

**Public API:**

```python
from backend.services.typed_prompt_config import (
    TypedPromptTemplate,
    NemotronPromptParams,
    create_typed_template,
    get_typed_params,
    get_param_type_for_model,
)

# Create typed template
template = TypedPromptTemplate[NemotronPromptParams](
    model_name="nemotron",
    template_string="Camera: {camera_name}\nTime: {timestamp}",
    param_type=NemotronPromptParams,
)

# Or use factory
template = create_typed_template("nemotron", "Camera: {camera_name}")

# Validate and render
params = NemotronPromptParams(
    camera_name="Front Door",
    timestamp="2024-01-15T10:30:00",
    day_of_week="Monday",
    time_of_day="morning",
)
rendered = template.render(params)

# Parse raw data into typed params
params = get_typed_params("nemotron", raw_dict)
```

### service_managers.py

**Purpose:** Strategy pattern for service management with health checks and restarts.

**Key Features:**

- Abstract ServiceManager base class
- ShellServiceManager for script-based restarts
- DockerServiceManager for container restarts
- HTTP health checks for AI services
- Redis health via redis-cli ping
- Security: Command allowlist and container name validation

**Security Measures:**

- Restart commands validated against `ALLOWED_RESTART_SCRIPTS` allowlist
- Container names validated against Docker naming regex
- Commands executed with `shell=False` to prevent injection
- Maximum container name length of 128 characters

**Key Classes:**

- `ServiceConfig` - Configuration for a managed service
- `ServiceManager` - Abstract base class
- `ShellServiceManager` - Restart via shell scripts
- `DockerServiceManager` - Restart via docker restart

**Public API:**

```python
from backend.services.service_managers import (
    ServiceConfig,
    ShellServiceManager,
    DockerServiceManager,
    validate_restart_command,
    validate_container_name,
)

# Create config
config = ServiceConfig(
    name="yolo26",
    health_url="http://localhost:8090/health",
    restart_cmd="scripts/restart_yolo26.sh",  # Must be in allowlist
    health_timeout=5.0,
    max_retries=3,
    backoff_base=5.0,
)

# Use shell manager
manager = ShellServiceManager(subprocess_timeout=60.0)
healthy = await manager.check_health(config)
if not healthy:
    success = await manager.restart(config)

# Use Docker manager
docker_manager = DockerServiceManager()
healthy = await docker_manager.check_health(config)
if not healthy:
    success = await docker_manager.restart(config)

# Validate commands
is_valid = validate_restart_command("scripts/restart_yolo26.sh")
is_valid = validate_container_name("ai-detector-1")
```

### notification_filter.py

**Purpose:** Filter notifications based on user preferences, camera settings, and quiet hours.

**Key Features:**

- Global notification preference checking
- Per-camera notification settings
- Risk level filtering (critical, high, medium, low)
- Quiet hours periods with day-of-week support
- Handles periods spanning midnight

**Filtering Logic:**

1. Check if global notifications enabled
2. Check if risk level is in enabled filters
3. Check per-camera settings (if provided)
4. Check quiet hours periods (if provided)

**Risk Level Thresholds:**

- CRITICAL: score >= 80
- HIGH: score >= 60
- MEDIUM: score >= 40
- LOW: score < 40

**Public API:**

```python
from backend.services.notification_filter import NotificationFilterService
from backend.models.notification_preferences import (
    NotificationPreferences,
    CameraNotificationSetting,
    QuietHoursPeriod,
)
from datetime import UTC, datetime, time

filter_service = NotificationFilterService()

# Check if notification should be sent
should_send = filter_service.should_notify(
    risk_score=75,
    camera_id="front_door",
    timestamp=datetime.now(UTC),
    global_prefs=NotificationPreferences(
        enabled=True,
        risk_filters=["critical", "high"],
    ),
    camera_setting=CameraNotificationSetting(
        enabled=True,
        risk_threshold=50,
    ),
    quiet_periods=[
        QuietHoursPeriod(
            start_time=time(22, 0),
            end_time=time(6, 0),
            days=["monday", "tuesday", "wednesday", "thursday", "friday"],
        ),
    ],
)

# Check if in quiet period
is_quiet = filter_service.is_quiet_period(
    timestamp=datetime.now(UTC),
    period=quiet_period,
)
```

### cost_tracker.py

**Purpose:** LLM inference cost tracking and budget controls.

**Key Features:**

- Token usage tracking per LLM request (input/output)
- GPU-time tracking per model inference
- Cost estimation based on cloud equivalents
- Daily/monthly budget limits with alerts
- Prometheus metrics for monitoring
- Redis persistence for usage records

**Cloud Pricing Models:**

- AWS GPU instances (p4d, p3, g5)
- GCP GPU instances (a2, n1)
- Azure GPU instances (NC, ND)

**Public API:**

```python
from backend.services.cost_tracker import (
    CostTracker,
    CostModel,
    get_cost_tracker,
    reset_cost_tracker,
)

tracker = get_cost_tracker()

# Track LLM usage
tracker.track_llm_usage(
    input_tokens=1500,
    output_tokens=500,
    model="nemotron",
    duration_seconds=2.5,
    camera_id="front_door",
)

# Track detection model usage
tracker.track_detection_usage(
    model="yolo26",
    duration_seconds=0.15,
    images_processed=1,
)

# Check budget status
status = await tracker.get_budget_status()
if status.daily_exceeded:
    logger.warning("Daily budget exceeded!")

# Get usage summary
daily = await tracker.get_daily_usage()
monthly = await tracker.get_monthly_usage()
```

### audit_logger.py

**Purpose:** High-level security audit logging interface for common security events.

**Key Features:**

- Simplified API for logging security events
- Rate limit violation logging
- Content-Type validation failure logging
- File magic number validation logging
- Configuration change tracking
- Sensitive operation logging

**Logged Events:**

- Rate limit exceeded
- Content-Type validation failure
- File magic validation failure
- Configuration changes
- Export operations
- Cleanup operations

**Public API:**

```python
from backend.services.audit_logger import audit_logger

# Log rate limit exceeded
await audit_logger.log_rate_limit_exceeded(
    db=db,
    request=request,
    tier="default",
    current_count=65,
    limit=60,
)

# Log configuration change
await audit_logger.log_config_change(
    db=db,
    request=request,
    setting_name="batch_window_seconds",
    old_value=90,
    new_value=120,
)

# Log sensitive operation
await audit_logger.log_sensitive_operation(
    db=db,
    request=request,
    operation="export_events",
    details={"format": "csv", "count": 1000},
)
```

## Data Flow Between Services

### Complete Pipeline Flow

```
1. FileWatcher
   | Detects new image or video files
   | Validates media file integrity
   | Checks for duplicates via DedupeService
   | Queues to Redis: detection_queue

2. [DetectionQueueWorker]
   | Consumes from: detection_queue
   | For images: Calls DetectorClient.detect_objects()
   | For videos: Calls VideoProcessor.extract_thumbnail() then DetectorClient
   | Stores: Detection records in PostgreSQL

3. [DetectionQueueWorker]
   | Calls: BatchAggregator.add_detection(confidence, object_type)
   |---> [Fast Path] If high-confidence critical detection:
   |     | Calls: NemotronAnalyzer.analyze_detection_fast_path()
   |     | Creates: Event with is_fast_path=True
   |
   └---> [Normal Path] Otherwise:
         | Updates Redis batch keys

4. [BatchTimeoutWorker]
   | Calls: BatchAggregator.check_batch_timeouts()
   | Queues to Redis: analysis_queue

5. [AnalysisQueueWorker]
   | Consumes from: analysis_queue
   | Calls: ContextEnricher.enrich_detections()
   | Calls: EnrichmentPipeline.enrich_batch()
   | Calls: NemotronAnalyzer.analyze_batch()
   | Stores: Event records in PostgreSQL

6. [NemotronAnalyzer]
   | Calls: AuditService.create_partial_audit()
   | Calls: EventBroadcaster.broadcast_event()
   | Calls: EvaluationQueue.enqueue(event_id, priority=risk_score)
   | Publishes: Redis pub/sub channel "security_events"

7. [AlertRuleEngine] (After Event Creation)
   | Evaluates: Each rule's conditions against event
   | Creates: Alert records for triggered rules
   | Calls: NotificationService.send_alert()

8. [BackgroundEvaluator] (When GPU Idle)
   | Checks: GPU idle and queues empty
   | Dequeues: Highest priority event from evaluation queue
   | Calls: AuditService.run_full_evaluation()
   | Updates: EventAudit record with quality scores
```

### Enrichment Pipeline Flow

```
EnrichmentPipeline.enrich_batch(image_path, detections)
│
├── For each person detection:
│   ├── florence_client.vqa() -> clothing, carrying, action
│   ├── face_detector.detect() -> face locations
│   ├── reid_service.generate_embedding() -> CLIP embedding
│   ├── vitpose_loader -> pose keypoints
│   ├── fashion_clip_loader -> clothing categories
│   └── violence_loader (if 2+ persons) -> violence score
│
├── For each vehicle detection:
│   ├── florence_client.vqa() -> color, type, commercial
│   ├── plate_detector.detect() -> license plate bbox
│   ├── ocr_service.extract() -> plate text
│   ├── reid_service.generate_embedding() -> CLIP embedding
│   ├── vehicle_classifier_loader -> detailed type (11 classes)
│   └── vehicle_damage_loader -> damage detection (6 types)
│
├── For each animal detection:
│   └── pet_classifier_loader -> cat/dog classification
│
└── Scene-level enrichment (once per batch):
    ├── weather_loader -> weather classification
    ├── depth_anything_loader -> depth estimation
    └── image_quality_loader -> quality score (disabled)
```

### Background Services (Parallel)

```
GPUMonitor (Continuous Polling)
   | Every poll_interval seconds
   | Reads: pynvml GPU metrics (or fallback)
   | Stores: GPUStats records in PostgreSQL
   | Broadcasts: WebSocket to SystemBroadcaster (optional)

SystemBroadcaster (Periodic Broadcasting)
   | Every 5 seconds
   | Queries: Latest GPUStats, Camera counts, Redis queue lengths
   | Checks: Database + Redis health
   | Broadcasts: WebSocket system_status to all connected clients

PerformanceCollector (Periodic Collection)
   | Every 5 seconds
   | Collects: GPU, AI models, PostgreSQL, Redis, host, containers
   | Calculates: Alert thresholds (warning/critical)
   | Returns: PerformanceUpdate schema for WebSocket broadcast

CleanupService (Daily Scheduled)
   | Once per day at cleanup_time (default: 03:00)
   | Deletes: Events, Detections, GPUStats older than retention_days
   | Deletes: Logs older than log_retention_days
   | Removes: Thumbnail files (and optionally original images)

PartitionManager (Periodic Maintenance)
   | Once per day (recommended)
   | Creates: Missing partitions for current and future months
   | Removes: Expired partitions beyond retention period
   | Logs: Partition statistics and counts

ServiceHealthMonitor (Periodic Health Checks)
   | Every check_interval seconds (default: 15s)
   | Checks: HTTP health endpoints for YOLO26v2, Nemotron, Florence, CLIP
   | Checks: Redis via redis-cli ping
   | Restarts: Failed services with exponential backoff
   | Broadcasts: Service status changes via WebSocket

BackgroundEvaluator (GPU Idle Processing)
   | Every poll_interval seconds (default: 5s)
   | Checks: GPU idle and detection/analysis queues empty
   | Dequeues: Highest priority event from evaluation queue
   | Runs: Full AI audit evaluation (4 LLM calls)
   | Updates: EventAudit records with quality scores
```

### Redis Queue Structure

**detection_queue:**

```json
{
  "camera_id": "front_door",
  "file_path": "/export/foscam/front_door/image_001.jpg",
  "timestamp": "2024-01-15T10:30:00.000000",
  "media_type": "image",
  "file_hash": "abc123..."
}
```

**analysis_queue:**

```json
{
  "batch_id": "batch_uuid",
  "camera_id": "front_door",
  "detection_ids": [1, 2, 3]
}
```

**evaluation:pending (sorted set):**

```
Member: "123" (event_id as string)
Score: 75 (priority, usually risk_score)
```

## Import Patterns

```python
# For exported services (via __init__.py)
from backend.services import (
    FileWatcher,
    DetectorClient,
    NemotronAnalyzer,
    BatchAggregator,
    ThumbnailGenerator,
    EventBroadcaster,
    GPUMonitor,
    CleanupService,
    CircuitBreaker,
    RetryHandler,
    BackgroundEvaluator,
    EvaluationQueue,
    PartitionManager,
    ManagedService,
    ServiceConfig,
    ServiceRegistry,
    CostTracker,
)

# For context enrichment (import directly)
from backend.services.context_enricher import ContextEnricher, get_context_enricher
from backend.services.enrichment_pipeline import EnrichmentPipeline, get_enrichment_pipeline
from backend.services.reid_service import ReIdentificationService, get_reid_service
from backend.services.scene_change_detector import SceneChangeDetector, get_scene_change_detector
from backend.services.vision_extractor import VisionExtractor

# For Model Zoo (import directly)
from backend.services.model_zoo import ModelManager, get_model_manager, get_model_config
from backend.services.model_loader_base import ModelLoaderBase

# For AI clients (import directly)
from backend.services.florence_client import FlorenceClient, get_florence_client
from backend.services.clip_client import CLIPClient, get_clip_client

# For AI fallback and streaming (import directly)
from backend.services.ai_fallback import AIFallbackService, get_ai_fallback_service
from backend.services.nemotron_streaming import call_llm_streaming, analyze_batch_streaming

# For workers and background services (import directly)
from backend.services.pipeline_workers import PipelineWorkerManager
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.performance_collector import PerformanceCollector
from backend.services.pipeline_quality_audit_service import PipelineQualityAuditService, get_audit_service

# For container orchestrator (import directly)
from backend.services.container_orchestrator import ContainerOrchestrator
from backend.services.container_discovery import ContainerDiscoveryService
from backend.services.lifecycle_manager import LifecycleManager
from backend.services.managed_service import get_service_registry

# For service management (import directly)
from backend.services.service_managers import (
    ServiceManager,
    ShellServiceManager,
    DockerServiceManager,
)

# For notifications (import directly)
from backend.services.notification_filter import NotificationFilterService

# For typed prompts (import directly)
from backend.services.typed_prompt_config import (
    TypedPromptTemplate,
    NemotronPromptParams,
    create_typed_template,
)

# For utilities (import directly)
from backend.services.token_counter import get_token_counter, count_prompt_tokens
from backend.services.batch_fetch import batch_fetch_detections, batch_fetch_detections_by_ids
from backend.services.prompt_parser import apply_suggestion_to_prompt
from backend.services.inference_semaphore import get_inference_semaphore
from backend.services.cost_tracker import get_cost_tracker
from backend.services.audit_logger import audit_logger
```

## Testing Considerations

### Mocking AI Services

```python
# Mock Model Zoo for tests
from backend.services.model_zoo import reset_model_zoo, reset_model_manager
reset_model_zoo()
reset_model_manager()

# Mock HTTP clients
from backend.services.florence_client import reset_florence_client
from backend.services.clip_client import reset_clip_client
reset_florence_client()
reset_clip_client()
```

### Singleton Reset Functions

Most services provide `reset_*()` functions for test isolation:

- `reset_model_zoo()`, `reset_model_manager()`
- `reset_florence_client()`, `reset_clip_client()`
- `reset_reid_service()`, `reset_dedupe_service()`
- `reset_context_enricher()`, `reset_enrichment_pipeline()`
- `reset_scene_change_detector()`, `reset_audit_service()`
- `reset_background_evaluator()`, `reset_evaluation_queue()`
- `reset_token_counter()`, `reset_clip_generator()`
- `reset_inference_semaphore()`
- `reset_ai_fallback_service()`, `reset_service_registry()`
- `reset_cost_tracker()`

### Integration Test Patterns

```python
@pytest.mark.asyncio
async def test_enrichment_pipeline():
    # Reset singletons
    reset_enrichment_pipeline()

    # Create mock dependencies
    mock_model_manager = MagicMock()
    mock_redis = MagicMock()

    # Create pipeline with mocks
    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        redis_client=mock_redis,
    )

    # Test enrichment
    result = await pipeline.enrich_batch(image_path, detections)
    assert result.has_vision_extraction
```

### Bounding Box Testing

```python
from backend.services.bbox_validation import (
    is_valid_bbox,
    clamp_bbox_to_image,
    InvalidBoundingBoxError,
)

# Test invalid bboxes
assert not is_valid_bbox((0, 0, 0, 0))  # Zero dimensions
assert not is_valid_bbox((100, 100, 50, 50))  # Inverted

# Test clamping
clamped = clamp_bbox_to_image((10, 10, 200, 200), 100, 100)
assert clamped == (10, 10, 100, 100)
```

## Dependencies

### External Services

- **YOLO26v2 HTTP server** (port 8090) - Object detection
- **ai-florence HTTP server** (port 8092) - Florence-2 vision-language
- **ai-clip HTTP server** (port 8093) - CLIP embeddings
- **llama.cpp server** (port 8080) - Nemotron LLM inference
- **Redis** - Queue and cache storage
- **PostgreSQL** - Persistent storage
- **ffmpeg/ffprobe** - Video processing

### Python Packages

- `watchdog` - Filesystem monitoring
- `httpx` - Async HTTP client
- `PIL/Pillow` - Image processing
- `sqlalchemy[asyncio]` - Database ORM
- `redis` - Redis client
- `pynvml` - NVIDIA GPU monitoring (optional)
- `numpy` - Numerical operations
- `scikit-image` - SSIM computation
- `transformers` - Model loading (HuggingFace)
- `torch` - PyTorch for model inference
- `tiktoken` - Token counting for LLMs

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/backend/api/schemas/AGENTS.md` - Pydantic schema documentation
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/ai/AGENTS.md` - AI pipeline overview
- `/ai/yolo26/AGENTS.md` - YOLO26v2 detection server
- `/ai/nemotron/AGENTS.md` - Nemotron LLM configuration
