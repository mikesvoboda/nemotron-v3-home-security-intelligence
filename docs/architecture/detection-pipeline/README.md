# Detection Pipeline Architecture

This hub documents the complete flow from camera image upload to analyzed security event, including queue architecture, batch aggregation, and worker processes.

## Pipeline Overview

```
Camera FTP --> FileWatcher --> detection_queue --> DetectionQueueWorker -->
YOLO26 --> BatchAggregator --> analysis_queue --> AnalysisQueueWorker -->
Enrichment --> Nemotron --> Event --> EventBroadcaster --> WebSocket
```

## Directory Contents

| Document                                   | Description                                    |
| ------------------------------------------ | ---------------------------------------------- |
| [file-watcher.md](file-watcher.md)         | FileWatcher service, debouncing, deduplication |
| [detection-queue.md](detection-queue.md)   | Detection queue structure and worker           |
| [batch-aggregator.md](batch-aggregator.md) | Batch timing, fast path, size limits           |
| [analysis-queue.md](analysis-queue.md)     | Analysis queue and Nemotron integration        |
| [critical-paths.md](critical-paths.md)     | Latency targets and optimization paths         |

## Pipeline Stages

### Stage 1: File Detection (FileWatcher)

Camera uploads arrive via FTP to watched directories. The FileWatcher monitors these directories using watchdog observers and handles:

- **Debouncing:** 0.5s delay to ensure file writes complete (line 355, `debounce_delay`)
- **File stability:** 2.0s stability check for FTP uploads (lines 560-621)
- **Validation:** Image integrity via PIL verification (lines 159-205, 207-254)
- **Deduplication:** SHA256 content hashing with Redis TTL (lines 809-818)

**Source:** `backend/services/file_watcher.py`

### Stage 2: Detection Queue Processing

The `DetectionQueueWorker` continuously polls `detection_queue` using Redis BLPOP with timeout. For each item:

1. Validates payload using Pydantic schemas (line 407)
2. Routes to image or video processing (lines 443-450)
3. Calls `DetectorClient.detect_objects()` with retry logic
4. Adds detections to `BatchAggregator`

**Source:** `backend/services/pipeline_workers.py` (lines 209-692)

### Stage 3: Object Detection (YOLO26)

The `DetectorClient` sends images to the YOLO26 service:

- **Concurrency control:** Semaphore limits concurrent GPU requests (lines 649-652)
- **Circuit breaker:** Prevents retry storms when detector is down (lines 319-334)
- **Retry logic:** Exponential backoff for transient failures (lines 585-908)
- **Confidence filtering:** Configurable threshold (lines 1299-1308)

**Source:** `backend/services/detector_client.py`

### Stage 4: Batch Aggregation

The `BatchAggregator` groups detections by camera before analysis:

- **Time window:** 90 seconds from batch start (configurable)
- **Idle timeout:** 30 seconds with no new detections
- **Max size:** Configurable detection limit per batch
- **Fast path:** High-confidence person detections bypass batching

**Source:** `backend/services/batch_aggregator.py` (lines 122-1119)

### Stage 5: Analysis Queue Processing

The `AnalysisQueueWorker` processes completed batches:

1. Validates payload using Pydantic schemas (line 863)
2. Calls `NemotronAnalyzer.analyze_batch()`
3. Records pipeline latency metrics

**Source:** `backend/services/pipeline_workers.py` (lines 695-1056)

### Stage 6: LLM Risk Analysis (Nemotron)

The `NemotronAnalyzer` performs risk assessment:

1. Fetches batch detections from database
2. Enriches context with zones and baselines
3. Runs optional enrichment pipeline (license plates, faces, OCR)
4. Formats prompt and calls llama.cpp endpoint
5. Parses JSON response and creates Event

**Source:** `backend/services/nemotron_analyzer.py` (class starts at line 220)

### Stage 7: Event Broadcasting

Events are broadcast to connected WebSocket clients via the `EventBroadcaster`:

- Redis pub/sub for multi-instance support
- Message sequencing for ordering guarantees
- Retry logic for connection failures

**Source:** `backend/services/event_broadcaster.py`

## Queue Architecture

Both queues use Redis LIST data structures with LPUSH/BRPOP pattern for FIFO ordering.

```
detection_queue (Redis LIST)
    |
    v
DetectionQueueWorker --> YOLO26 --> BatchAggregator
                                            |
                                            v
                                      analysis_queue (Redis LIST)
                                            |
                                            v
                                      AnalysisQueueWorker --> Nemotron --> Event
```

**Queue Names:** Defined in `backend/core/constants.py` (lines 146-150)

- `DETECTION_QUEUE = "detection_queue"`
- `ANALYSIS_QUEUE = "analysis_queue"`

## Key Constants

| Constant                   | Value               | Source                                     |
| -------------------------- | ------------------- | ------------------------------------------ |
| `DETECTION_QUEUE`          | `"detection_queue"` | `backend/core/constants.py:146`            |
| `ANALYSIS_QUEUE`           | `"analysis_queue"`  | `backend/core/constants.py:149`            |
| `BATCH_KEY_TTL_SECONDS`    | 3600 (1 hour)       | `backend/services/batch_aggregator.py:133` |
| `MIN_DETECTION_IMAGE_SIZE` | 10KB                | `backend/services/detector_client.py:103`  |

## Worker Management

The `PipelineWorkerManager` provides unified lifecycle management:

- **Start/stop:** Coordinated worker lifecycle (lines 1607-1745)
- **Signal handling:** SIGTERM/SIGINT graceful shutdown (lines 1747-1769)
- **Status reporting:** Worker stats and health (lines 1581-1605)
- **Queue draining:** Graceful shutdown with timeout (lines 1502-1579)

**Source:** `backend/services/pipeline_workers.py` (lines 1325-1769)

## Metrics and Observability

Pipeline stages record metrics via Prometheus:

- `hsi_pipeline_stage_duration_seconds` - Stage latency histogram
- `hsi_queue_depth` - Queue depth gauge
- `hsi_pipeline_errors_total` - Error counter by type
- `hsi_detection_processed_total` - Detection throughput

## Related Documentation

- **[AI Pipeline Overview](../ai-pipeline.md):** Broader AI processing context
- **[Real-time Architecture](../real-time.md):** WebSocket and pub/sub details
- **[Resilience Patterns](../resilience-patterns/README.md):** Circuit breakers and retry handlers
