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
                     └── PerformanceCollector (metrics aggregation)
```

### Service Categories

1. **Core AI Pipeline** - File watching, detection, batching, analysis
2. **AI Clients** - HTTP clients for external AI services (Florence, CLIP)
3. **Context Enrichment** - Zone detection, baseline tracking, re-identification
4. **Model Zoo** - On-demand model loading for attribute extraction
5. **Model Loaders** - Individual model loading functions for Model Zoo
6. **Pipeline Workers** - Background queue consumers and managers
7. **Background Services** - GPU monitoring, cleanup, health checks
8. **Container Orchestrator** - Container discovery, lifecycle management
9. **Infrastructure** - Circuit breakers, retry handlers, degradation
10. **Alerting** - Alert rules, deduplication, notifications
11. **Utility** - Search, severity mapping, prompt templates

## Service Files Overview

### Core AI Pipeline Services

| Service                  | Purpose                                      | Exported via `__init__.py` |
| ------------------------ | -------------------------------------------- | -------------------------- |
| `file_watcher.py`        | Monitor camera directories for media uploads | Yes                        |
| `dedupe.py`              | Prevent duplicate file processing            | Yes                        |
| `detector_client.py`     | Send images to RT-DETRv2 for detection       | Yes                        |
| `batch_aggregator.py`    | Group detections into time-based batches     | Yes                        |
| `nemotron_analyzer.py`   | LLM-based risk analysis via llama.cpp        | Yes                        |
| `thumbnail_generator.py` | Generate preview images with bounding boxes  | Yes                        |
| `video_processor.py`     | Extract video metadata and thumbnails        | No (import directly)       |
| `event_broadcaster.py`   | Distribute events via WebSocket              | Yes                        |

### AI Client Services

| Service              | Purpose                                    | Exported via `__init__.py` |
| -------------------- | ------------------------------------------ | -------------------------- |
| `florence_client.py` | HTTP client for Florence-2 vision-language | No (import directly)       |
| `clip_client.py`     | HTTP client for CLIP embedding generation  | No (import directly)       |

### Context Enrichment Services

| Service                    | Purpose                                          | Exported via `__init__.py` |
| -------------------------- | ------------------------------------------------ | -------------------------- |
| `context_enricher.py`      | Aggregate context from zones, baselines, reid    | No (import directly)       |
| `enrichment_pipeline.py`   | Orchestrate Model Zoo enrichment for batches     | No (import directly)       |
| `enrichment_client.py`     | HTTP client for enrichment service               | No (import directly)       |
| `vision_extractor.py`      | Florence-2 attribute extraction orchestration    | No (import directly)       |
| `florence_extractor.py`    | Florence-2 specific extraction logic             | No (import directly)       |
| `zone_service.py`          | Zone detection and context generation            | Yes                        |
| `baseline.py`              | Activity baseline tracking for anomaly detection | Yes                        |
| `scene_baseline.py`        | Scene-level baseline tracking                    | No (import directly)       |
| `scene_change_detector.py` | SSIM-based scene change detection                | No (import directly)       |
| `reid_service.py`          | Entity re-identification across cameras          | No (import directly)       |
| `bbox_validation.py`       | Bounding box validation utilities                | No (import directly)       |

### Model Zoo Services

| Service        | Purpose                                      | Exported via `__init__.py` |
| -------------- | -------------------------------------------- | -------------------------- |
| `model_zoo.py` | Registry and manager for on-demand AI models | No (import directly)       |

### Model Loader Services

| Service                        | Purpose                                          | Exported via `__init__.py` |
| ------------------------------ | ------------------------------------------------ | -------------------------- |
| `clip_loader.py`               | Load CLIP ViT-L for embeddings                   | No (import directly)       |
| `florence_loader.py`           | Load Florence-2 for vision-language              | No (import directly)       |
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

### Specialized Detection Services

| Service             | Purpose                                     | Exported via `__init__.py` |
| ------------------- | ------------------------------------------- | -------------------------- |
| `plate_detector.py` | License plate detection and OCR             | No (import directly)       |
| `face_detector.py`  | Face detection for person re-identification | No (import directly)       |
| `ocr_service.py`    | OCR text extraction from detected regions   | No (import directly)       |

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
| `system_broadcaster.py`          | Broadcast system health status                | No (import directly)       |
| `performance_collector.py`       | Collect system performance metrics            | No (import directly)       |

### Container Orchestrator Services

| Service                  | Purpose                                             | Exported via `__init__.py` |
| ------------------------ | --------------------------------------------------- | -------------------------- |
| `container_discovery.py` | Discover Docker containers by name pattern          | No (import directly)       |
| `lifecycle_manager.py`   | Self-healing restart logic with exponential backoff | No (import directly)       |

### Infrastructure Services

| Service                  | Purpose                                 | Exported via `__init__.py` |
| ------------------------ | --------------------------------------- | -------------------------- |
| `retry_handler.py`       | Exponential backoff and DLQ support     | Yes                        |
| `service_managers.py`    | Strategy pattern for service management | No (import directly)       |
| `circuit_breaker.py`     | Circuit breaker for service resilience  | Yes                        |
| `degradation_manager.py` | Graceful degradation management         | Yes                        |
| `cache_service.py`       | Redis caching utilities                 | No (import directly)       |
| `service_registry.py`    | Service registry with Redis persistence | No (import directly)       |

### Alerting Services

| Service           | Purpose                             | Exported via `__init__.py` |
| ----------------- | ----------------------------------- | -------------------------- |
| `alert_engine.py` | Evaluate alert rules against events | Yes                        |
| `alert_dedup.py`  | Alert deduplication logic           | Yes                        |
| `notification.py` | Multi-channel notification delivery | Yes                        |

### Audit Services

| Service            | Purpose                                      | Exported via `__init__.py` |
| ------------------ | -------------------------------------------- | -------------------------- |
| `audit.py`         | Audit logging for security-sensitive actions | Yes                        |
| `audit_service.py` | AI pipeline audit and self-evaluation        | No (import directly)       |

### Prompt Management Services

| Service                     | Purpose                                               | Exported via `__init__.py` |
| --------------------------- | ----------------------------------------------------- | -------------------------- |
| `prompts.py`                | LLM prompt templates                                  | No (import directly)       |
| `prompt_sanitizer.py`       | Prompt injection prevention for LLM inputs (NEM-1722) | No (import directly)       |
| `prompt_service.py`         | CRUD operations for AI prompt configs                 | No (import directly)       |
| `prompt_storage.py`         | File-based prompt storage with versioning             | No (import directly)       |
| `prompt_version_service.py` | Prompt version history and restoration                | No (import directly)       |

### Utility Services

| Service             | Purpose                                                 | Exported via `__init__.py` |
| ------------------- | ------------------------------------------------------- | -------------------------- |
| `search.py`         | Full-text search for events                             | Yes                        |
| `severity.py`       | Severity level mapping and configuration                | Yes                        |
| `clip_generator.py` | Video clip generation for events                        | Yes                        |
| `token_counter.py`  | LLM prompt token counting and context window validation | No (import directly)       |

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

**Purpose:** HTTP client for RT-DETRv2 object detection service.

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
- RT-DETRv2: 650 MB (always loaded)
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
rtdetr, florence, clip, violence, clothing, vehicle, pet, weather, image_quality, zones, baseline, cross_camera

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
3. AI container health endpoints (RT-DETRv2 reports VRAM)
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
- HTTP health endpoint checks for AI services (RT-DETRv2, Nemotron, Florence, CLIP)
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
    image="ghcr.io/.../rtdetr:latest",
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

**Purpose:** Circuit breaker pattern for external service protection.

**States:**

- CLOSED: Normal operation, calls pass through
- OPEN: Circuit tripped, calls rejected immediately
- HALF_OPEN: Recovery testing, limited calls allowed

**Key Features:**

- Configurable failure thresholds and recovery timeouts
- Half-open state for gradual recovery testing
- Excluded exceptions that don't count as failures
- Thread-safe async implementation
- Registry for managing multiple circuit breakers

**Public API:**

- `CircuitBreaker(name, config)`
- `async call(operation, *args, **kwargs)` - Execute through circuit breaker
- `get_circuit_breaker(name, config)` - Get from global registry
- Supports async context manager: `async with breaker: ...`

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
- `display_name` - Human-readable name (e.g., "PostgreSQL", "RT-DETRv2")
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
| RT-DETRv2  | HTTP `/health` endpoint        | Status, VRAM, model name, device      |
| Nemotron   | HTTP `/slots` endpoint         | Status, active/total slots, context   |
| PostgreSQL | SQL queries (pg_stat_activity) | Connections, cache hit ratio, txns    |
| Redis      | redis-py INFO command          | Clients, memory, hit ratio, blocked   |
| Host       | psutil                         | CPU%, RAM GB, disk GB                 |
| Containers | HTTP health endpoints          | Status, health for each container     |
| Inference  | PipelineLatencyTracker         | RT-DETR/Nemotron/pipeline latencies   |

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
| AI             | RT-DETRv2, Nemotron, Florence-2, CLIP, Enrichment  | Standard backoff      |
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
   | Publishes: Redis pub/sub channel "security_events"

7. [AlertRuleEngine] (After Event Creation)
   | Evaluates: Each rule's conditions against event
   | Creates: Alert records for triggered rules
   | Calls: NotificationService.send_alert()
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

ServiceHealthMonitor (Periodic Health Checks)
   | Every check_interval seconds (default: 15s)
   | Checks: HTTP health endpoints for RT-DETRv2, Nemotron, Florence, CLIP
   | Checks: Redis via redis-cli ping
   | Restarts: Failed services with exponential backoff
   | Broadcasts: Service status changes via WebSocket
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
)

# For context enrichment (import directly)
from backend.services.context_enricher import ContextEnricher, get_context_enricher
from backend.services.enrichment_pipeline import EnrichmentPipeline, get_enrichment_pipeline
from backend.services.reid_service import ReIdentificationService, get_reid_service
from backend.services.scene_change_detector import SceneChangeDetector, get_scene_change_detector
from backend.services.vision_extractor import VisionExtractor

# For Model Zoo (import directly)
from backend.services.model_zoo import ModelManager, get_model_manager, get_model_config

# For AI clients (import directly)
from backend.services.florence_client import FlorenceClient, get_florence_client
from backend.services.clip_client import CLIPClient, get_clip_client

# For workers and background services (import directly)
from backend.services.pipeline_workers import PipelineWorkerManager
from backend.services.health_monitor import ServiceHealthMonitor
from backend.services.performance_collector import PerformanceCollector
from backend.services.audit_service import AuditService, get_audit_service
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

- **RT-DETRv2 HTTP server** (port 8090) - Object detection
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

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/api/routes/AGENTS.md` - API endpoint documentation
- `/backend/api/schemas/AGENTS.md` - Pydantic schema documentation
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/ai/AGENTS.md` - AI pipeline overview
- `/ai/rtdetr/AGENTS.md` - RT-DETRv2 detection server
- `/ai/nemotron/AGENTS.md` - Nemotron LLM configuration
