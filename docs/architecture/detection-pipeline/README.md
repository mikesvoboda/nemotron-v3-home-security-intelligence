# Detection Pipeline Architecture

This hub documents the complete flow from camera image upload to analyzed security event, including queue architecture, batch aggregation, and worker processes.

## Pipeline Overview

```
Camera FTP --> FileWatcher --> detection_queue --> DetectionQueueWorker -->
YOLO26 (ai-gateway:8090) --> BatchAggregator --> analysis_queue -->
AnalysisQueueWorker --> VlmAnalyzer (specialist lookups --> ai-vlm:8098 assess) -->
Event + EventVerification --> EventBroadcaster --> WebSocket
```

## Directory Contents

| Document                                   | Description                                    |
| ------------------------------------------ | ---------------------------------------------- |
| [file-watcher.md](file-watcher.md)         | FileWatcher service, debouncing, deduplication |
| [detection-queue.md](detection-queue.md)   | Detection queue structure and worker           |
| [batch-aggregator.md](batch-aggregator.md) | Batch timing, fast path, size limits           |
| [analysis-queue.md](analysis-queue.md)     | Analysis queue and VlmAnalyzer integration     |
| [critical-paths.md](critical-paths.md)     | Latency targets and optimization paths         |

## Pipeline Stages

### Stage 1: File Detection (FileWatcher)

Camera uploads arrive via FTP to watched directories. The FileWatcher monitors these directories using watchdog observers and handles:

- **Debouncing:** 0.5s delay to ensure file writes complete (line 404, `debounce_delay`)
- **File stability:** 2.0s stability check for FTP uploads (`stability_time` at line 411, `_wait_for_file_stability` at lines 620-681)
- **Validation:** Image integrity via PIL verification (`_validate_image_sync` at lines 139-164)
- **Deduplication:** content hashing through `DedupeService.is_duplicate_and_mark` (lines 871-872)

**Source:** `backend/services/file_watcher.py`

### Stage 2: Detection Queue Processing

The `DetectionQueueWorker` consumes `detection_queue`. `USE_REDIS_STREAMS` defaults to true, so the loop reads the `detections:stream` consumer group and acknowledges each message; with the setting off it falls back to Redis BLPOP with timeout (`backend/services/pipeline_workers.py:421-427`). For each item:

1. Validates payload using Pydantic schemas (line 477)
2. Routes to image or video processing (lines 513-517)
3. Calls `DetectorClient.detect_objects()` with retry logic
4. Adds detections to `BatchAggregator`

**Source:** `backend/services/pipeline_workers.py` (lines 222-762)

### Stage 3: Object Detection (YOLO26)

The `DetectorClient` sends images to the YOLO26 endpoint on the AI gateway (`YOLO26_URL`, `http://ai-gateway:8090/yolo26` under compose — `docker-compose.prod.yml:592`):

- **Concurrency control:** Class semaphore limits concurrent detector requests (lines 203-223); the shared inference semaphore is acquired per request (lines 1115-1116)
- **Circuit breaker:** Prevents retry storms when the detector is down (lines 336-344)
- **Retry logic:** Exponential backoff for transient failures (`delay = min(2**attempt, 30)` at line 691, slept at line 704)
- **Confidence filtering:** Per-class threshold with a global fallback (lines 1191-1195)

**Source:** `backend/services/detector_client.py`

### Stage 4: Batch Aggregation

The `BatchAggregator` groups detections by camera before analysis:

- **Time window:** 90 seconds from batch start (configurable)
- **Idle timeout:** 30 seconds with no new detections
- **Max size:** 500 detections per batch by default
- **Fast path:** The high-confidence person bypass, which the shipped config keeps disabled (see [Batch Aggregator](batch-aggregator.md#fast-path-processing)); weapon and smoke/fire bypasses do run

**Source:** `backend/services/batch_aggregator.py` (lines 172-1487)

### Stage 5: Analysis Queue Processing

The `AnalysisQueueWorker` processes completed batches:

1. Validates payload using Pydantic schemas (line 993)
2. Builds the analyzer at the one construction seam — `build_pipeline_analyzer` returns `VlmAnalyzer` (line 802; `backend/services/pipeline_factory.py:28-40`)
3. Calls `VlmAnalyzer.analyze_batch()` (lines 1052-1056)
4. Records pipeline latency metrics (lines 1062-1067)

**Source:** `backend/services/pipeline_workers.py` (lines 765-1186)

### Stage 6: VLM Risk Verification

`VlmAnalyzer` turns one closed batch into one event:

1. Resolves the batch's camera and detection ids, refusing loudly when no detector ever closed the batch (`backend/services/vlm_analyzer.py:413-432`)
2. Reads detections, zones, and household context, and collects the three specialist lookup texts — `faces`, `plates`, `person_reid` — over the selected key frames (lines 505-508)
3. Renders the `vlm_assess` prompt and sends it to `ai-vlm` (`backend/services/vlm_client.py:755`)
4. Applies the verdict invariant table, which clamps a `rejected` verdict and NULLs the score of a verification failure (`backend/services/vlm_analyzer.py:255-306`)
5. Writes Event and EventVerification in one transaction (lines 573-633), then broadcasts

**Source:** `backend/services/vlm_analyzer.py` (class starts at line 344)

### Stage 7: Event Broadcasting

Events are broadcast to connected WebSocket clients via the `EventBroadcaster`:

- Redis pub/sub for multi-instance support
- Message sequencing for ordering guarantees
- Retry logic for connection failures

**Source:** `backend/services/event_broadcaster.py`

## Queue Architecture

Both queues run on Redis Streams by default (`USE_REDIS_STREAMS`, `backend/core/config.py:2239-2242`): `XADD` producers, a consumer group per queue, and `XACK` after the item is processed. The Redis LIST names below stay active when the setting is turned off.

```
detection_queue (Redis LIST) / detections:stream (Redis Stream)
    |
    v
DetectionQueueWorker --> YOLO26 --> BatchAggregator
                                            |
                                            v
                          analysis_queue (Redis LIST) / analysis:stream
                                            |
                                            v
                          AnalysisQueueWorker --> VlmAnalyzer --> Event
```

**Queue Names:** Defined in `backend/core/constants.py` (lines 146-150)

- `DETECTION_QUEUE = "detection_queue"`
- `ANALYSIS_QUEUE = "analysis_queue"`

## Key Constants

| Constant                   | Value               | Source                                     |
| -------------------------- | ------------------- | ------------------------------------------ |
| `DETECTION_QUEUE`          | `"detection_queue"` | `backend/core/constants.py:146`            |
| `ANALYSIS_QUEUE`           | `"analysis_queue"`  | `backend/core/constants.py:149`            |
| `BATCH_KEY_TTL_SECONDS`    | 3600 (1 hour)       | `backend/services/batch_aggregator.py:183` |
| `MIN_DETECTION_IMAGE_SIZE` | 10KB                | `backend/services/detector_client.py:105`  |

## Worker Management

The `PipelineWorkerManager` provides unified lifecycle management:

- **Start/stop:** Coordinated worker lifecycle (lines 1814-1950)
- **Signal handling:** SIGTERM/SIGINT graceful shutdown (lines 1966-1988)
- **Status reporting:** Worker stats and health (lines 1780-1812)
- **Queue draining:** Graceful shutdown with timeout (lines 1701-1778)

**Source:** `backend/services/pipeline_workers.py` (lines 1494-1988)

The FastAPI lifespan registers the same workers with the `WorkerSupervisor` through factory callables — `create_analysis_worker` at `backend/services/pipeline_workers.py:2140`, registered as `"analysis"` at `backend/main.py:996-1001`.

## Metrics and Observability

Pipeline stages record metrics via Prometheus:

- `hsi_stage_duration_seconds` - Stage latency histogram (label: `stage`)
- `hsi_detection_queue_depth`, `hsi_analysis_queue_depth` - Queue depth gauges
- `hsi_pipeline_errors_total` - Error counter by type
- `hsi_detections_processed_total` - Detection throughput

## Related Documentation

- **[AI Pipeline Overview](../ai-pipeline-current-state.md):** Broader AI processing context
- **[Real-time Architecture](../real-time.md):** WebSocket and pub/sub details
- **[Resilience Patterns](../resilience-patterns/README.md):** Circuit breakers and retry handlers
