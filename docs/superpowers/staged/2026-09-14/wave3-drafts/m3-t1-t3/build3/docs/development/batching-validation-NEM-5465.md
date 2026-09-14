# Phase 5: Batching and Scheduling Optimization -- Validation Report (NEM-5465)

**Date:** 2026-02-07
**Validator:** Claude Code (NEM-5465 audit)
**Status:** Validated with gaps identified

---

## 1. Architecture Overview

```
Camera Frames
     |
     v
+---------------------+     +---------------------+
| DetectorClient      |---->| YOLO26 HTTP Service  |
| (1 image per call)  |     | ai-yolo26:8095      |
+---------------------+     +---------------------+
     |                            |
     | Detection results          | (also has /detect/batch
     v                            |  endpoint, unused)
+---------------------+
| BatchAggregator     |  <-- Groups detections per-camera
| (Redis state)       |      90s window / 30s idle / 500 max
+---------------------+
     |
     | Batch closed -> analysis_queue (Redis)
     v
+---------------------+
| BatchCoalescer      |  <-- Merges similar batches (optional)
| (Redis sorted sets) |      Same camera + type + confidence
+---------------------+
     |
     v
+---------------------+     +---------------------+
| NemotronAnalyzer    |---->| EnrichmentPipeline   |
|                     |     | (3-phase parallel)   |
+---------------------+     +---------------------+
                                  |
                        +---------+---------+----------+
                        |         |         |          |
                        v         v         v          v
                    Florence-2  CLIP    Enrichment   Local
                    :8092       :8093   :8094/:8096  Models
                    (1 req/det) (1 req) (1 req/det)  (batch)
```

---

## 2. Batch Aggregator Analysis

**File:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/batch_aggregator.py`

### 2.1 How Detections Are Grouped

Detections are grouped per-camera into time-based batches stored in Redis:

- **Key structure:** `batch:{camera_id}:current` points to the active batch ID.
- Each detection is appended atomically via Redis `RPUSH` to `batch:{batch_id}:detections`.
- Metadata (camera_id, started_at, last_activity, pipeline_start_time) stored as separate keys with 1-hour TTL.

### 2.2 Batch Close Triggers

| Trigger                | Threshold                       | Configuration Key                                    |
| ---------------------- | ------------------------------- | ---------------------------------------------------- |
| Window timeout         | 90 seconds from batch start     | `batch_window_seconds` (default: 90)                 |
| Idle timeout           | 30 seconds since last detection | `batch_idle_timeout_seconds` (default: 30)           |
| Max detections         | 500 detections per batch        | `batch_max_detections` (default: 500, range 1-10000) |
| Timeout check interval | Every 5 seconds                 | `batch_check_interval_seconds` (default: 5.0)        |

### 2.3 Fast Path Bypasses

Three fast-path mechanisms bypass normal batching entirely:

1. **General fast path:** High-confidence detections of configured object types skip batching and go directly to `NemotronAnalyzer.analyze_detection_fast_path()`.
2. **Threat fast path (NEM-5279):** Weapons (gun, pistol, rifle, knife, machete, sword) at >=0.7 confidence bypass batching and go to `ThreatMonitorService`.
3. **Smoke/fire fast path (NEM-5298):** Fire at >=0.70 confidence or smoke at >=0.75 confidence bypass batching and go to `SmokeFireConsecutiveService`.

### 2.4 Assessment: Is 90s Window Optimal?

**Verdict: Appropriate for the use case, with caveats.**

- The 90-second window is designed to accumulate multiple detections of the same event (e.g., person walking through camera view) before sending to the LLM for analysis.
- The 30-second idle timeout provides faster response when activity stops.
- Critical threats (weapons, fire) bypass the window entirely via fast paths.
- The enrichment pipeline has a 30-second hard timeout, leaving 60 seconds of the batch window for Nemotron analysis.

**Potential concern:** For low-activity cameras, a single detection waits up to 30 seconds (idle timeout) before processing. This is acceptable for routine monitoring but could be reduced to 15-20 seconds for faster initial response without impacting throughput.

---

## 3. Batch Coalescer Analysis

**File:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/batch_coalescer.py`

### 3.1 Merging Logic

Batches are compatible for merging when all of the following are true:

1. Same `camera_id`
2. Same `primary_object_type` (most frequent type in batch)
3. Confidence difference within tolerance (default: 0.15)
4. Combined size does not exceed max (default: 10 detections)

### 3.2 Priority System

| Priority      | Level | Triggers                                                |
| ------------- | ----- | ------------------------------------------------------- |
| P0 (CRITICAL) | 4     | Weapons, unknown persons at night, fire/smoke, intruder |
| P1 (HIGH)     | 3     | Unknown vehicles                                        |
| P2 (NORMAL)   | 2     | Regular daytime detections                              |
| P3 (LOW)      | 1     | Known faces, household members                          |

### 3.3 Actual Reduction Rate

The coalescer targets 20-40% reduction in inference count. The `CoalesceResult.inference_reduction_pct` property tracks this per-merge. In-memory metrics (`CoalescerMetrics`) track cumulative statistics.

### 3.4 Edge Cases: Can Important Detections Be Dropped?

**No detections are dropped during coalescing.** The coalescer merges _batches_ (combining their detection ID lists), not individual detections. All detection IDs from source batches are preserved in the merged batch. The coalescer only reduces the number of _LLM inference calls_, not the number of detections analyzed.

**One concern:** The `remove_candidates` method uses `zrem("coalesce:candidates:*", ...)` with a wildcard, which is not a valid Redis operation for targeted removal from sorted sets when the camera_id is unknown. The code comments acknowledge this: "we can't easily remove from sorted sets without knowing camera_id." The TTL (10 minutes) handles eventual cleanup, but this could leave stale candidate references during active operation.

### 3.5 Integration Gap

The `BatchCoalescer` is implemented as a standalone service with a singleton accessor (`get_batch_coalescer()`), and the configuration (`batch_coalescing_enabled`, `batch_coalescing_max_size`, `batch_coalescing_time_window`) exists in settings. However, there is no evidence in `batch_aggregator.py` or `pipeline_workers.py` that the coalescer is actually invoked in the hot path between batch close and Nemotron analysis. **The coalescer appears to be implemented but not yet wired into the pipeline.**

---

## 4. Enrichment Pipeline Scheduling Analysis

**File:** `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/services/enrichment_pipeline.py`

### 4.1 Phase Structure

The enrichment pipeline uses a 3-phase parallel architecture (NEM-4234, NEM-5525 optimized):

**Super-Phase (all concurrent via `asyncio.gather`):**

- **Phase 1:** Local models + enrichment HTTP services (face detection, license plate detection, violence detection, pose estimation, action recognition, threat detection, image quality, weather, clothing, depth, vehicle classification, vehicle damage, pet classification, demographics, scene OCR, clothing segmentation, CLIP scene classification, CLIP threat matching)
- **Florence-2 Vision Extraction:** Runs in parallel with Phase 1

**Phase 2 (after Super-Phase completes):**

- OCR (depends on license plate detection from Phase 1)
- Re-identification (CLIP embedding extraction)
- Scene change detection
- Scene OCR crop (depends on frame OCR from Phase 1)

**Phase 3 (after Phase 2 completes):**

- CLIP anomaly detection (depends on Phase 2 re-ID embeddings)
- Household matching (uses Phase 1/2 results)

### 4.2 Parallelism Verification

`asyncio.gather` is used correctly in three places:

1. **Super-Phase:** `super_results = await asyncio.gather(*all_super_tasks, return_exceptions=True)` -- All Phase 1 tasks + Florence-2 run concurrently with `return_exceptions=True` to prevent one failure from canceling others.
2. **Phase 2:** `phase2_results = await asyncio.gather(*phase2_tasks.values(), return_exceptions=True)`
3. **Phase 3:** `phase3_results = await asyncio.gather(*phase3_tasks.values(), return_exceptions=True)`

The `return_exceptions=True` pattern is correct -- it prevents a single model failure from canceling the entire phase and enables partial enrichment results.

### 4.3 Semaphore Values

| Semaphore                         | Default | Range | Purpose                                 |
| --------------------------------- | ------- | ----- | --------------------------------------- |
| `enrichment_florence_concurrency` | 3       | 1-10  | Max concurrent Florence-2 requests      |
| `enrichment_clip_concurrency`     | 3       | 1-10  | Max concurrent CLIP requests            |
| `enrichment_service_concurrency`  | 4       | 1-10  | Max concurrent enrichment HTTP requests |

**Assessment:** The semaphore values are appropriate for a single-GPU deployment. Florence-2 (~1.2GB VRAM) and CLIP (~800MB VRAM) are relatively lightweight, so 3 concurrent requests is reasonable. The enrichment service semaphore is slightly higher (4) because ai-enrichment and ai-enrichment-light are separate containers. These are configurable via settings if GPU capacity changes.

### 4.4 Pipeline Timeout

The hard timeout is **30 seconds** (configurable, range 5-120s). This is enforced via `async with asyncio.timeout(self._pipeline_timeout)`. If exceeded, partial results are returned with an error appended.

**Assessment:** 30 seconds is well-calibrated. It leaves 60 seconds of the 90-second batch window for Nemotron LLM analysis. The adaptive quality system (`enrichment_quality_level`: full/standard/minimal) can further reduce enrichment time under load by skipping non-essential models.

---

## 5. AI Service Batching Support

### 5.1 Florence-2 (`ai/florence/model.py`)

- **BatchProcessor exists:** `Florence2Model.__init__` creates a `BatchProcessor(BatchConfig(max_batch_size=4))`.
- **However, it is not used in any endpoint.** All endpoints (`/extract`, `/ocr`, `/detect`, `/dense-caption`, `/analyze-scene`, `/describe-region`, `/phrase-grounding`) process a single image per request.
- The `analyze-scene` endpoint runs DENSE_REGION_CAPTION and OCR_WITH_REGION in parallel via `asyncio.gather` and `asyncio.to_thread`, but this is intra-request parallelism, not batch inference.
- **HTTP batch endpoint: None.** No `/extract/batch` or `/batch-extract` endpoint exists.

**Gap:** The BatchProcessor infrastructure is in place but unused. Each Florence-2 call from the backend is a separate HTTP request with separate base64 image encoding/decoding overhead.

### 5.2 CLIP (`ai/clip/model.py`)

- **No BatchProcessor.** The CLIP model operates on single images for embedding, anomaly scoring, and classification.
- **Batch-like endpoint exists:** `/batch-similarity` accepts one image + multiple text descriptions and computes similarities in a single forward pass. This is used by the enrichment pipeline for CLIP scene classification and threat matching.
- **No image batch endpoint.** There is no endpoint to extract embeddings for multiple images in one request.
- **Thread lock protection:** A global `_model_lock` prevents race conditions during concurrent access (NEM-4509).

**Gap:** Re-identification requires embedding extraction for each detected person/vehicle crop. These are currently separate HTTP calls. A batch embedding endpoint would significantly reduce overhead for multi-detection frames.

### 5.3 YOLO26 (`ai/yolo26/model.py`)

- **Batch inference implemented:** `YOLO26Model.detect_batch(images)` processes multiple images in a single call, using Ultralytics' built-in batch support.
- **Batch HTTP endpoint exists:** `POST /detect/batch` accepts multiple image files and returns detections for all.
- **However, the backend does not use it.** `DetectorClient.detect_objects()` sends one image at a time via `_send_detection_request()`. Each camera frame is a separate HTTP POST with a single file upload.

**Gap:** The YOLO26 batch detection infrastructure is fully implemented server-side but unused by the backend client. When multiple cameras trigger simultaneously, each frame is sent as an independent HTTP request.

---

## 6. Scheduling and Race Condition Analysis

### 6.1 Concurrency Safety in BatchAggregator

The BatchAggregator uses a multi-layer locking strategy:

1. **Per-camera locks (`_camera_locks`):** `defaultdict(asyncio.Lock)` prevents race conditions when multiple detections arrive for the same camera. Lock creation itself is protected by `_locks_lock`.
2. **Global batch close lock (`_batch_close_lock`):** Prevents concurrent `close_batch()` calls from double-processing the same batch.
3. **Redis atomic operations:** `RPUSH` for detection list append (atomic), `MULTI/EXEC` pipeline for batch metadata creation (transactional).
4. **Closing flag with TTL (NEM-2507):** `batch:{batch_id}:closing` flag with 5-minute TTL prevents orphaned locks if the process crashes mid-close.
5. **Double-check after lock acquisition:** `close_batch()` re-verifies the batch exists after acquiring both locks.

**Assessment:** The locking strategy is thorough and handles the expected race conditions. The use of Redis `RPUSH` for the detection list eliminates the read-modify-write race condition mentioned in the docstring. The `MULTI/EXEC` pipeline for metadata creation ensures atomic batch setup.

### 6.2 Redis State Management

Redis keys use consistent 1-hour TTL for orphan cleanup, which handles:

- Process crashes mid-batch
- Network partitions between backend and Redis
- Zombie batches from stale camera connections

The `check_batch_timeouts()` method uses `SCAN` instead of `KEYS` for production safety (non-blocking iteration) and Redis pipelines for batch metadata fetching (O(2) RTTs instead of O(N\*3)).

### 6.3 Multi-Camera Simultaneous Batches

When multiple cameras trigger simultaneously:

1. Each camera has its own batch (keyed by `batch:{camera_id}:current`), so there is no cross-camera contention at the batch level.
2. Per-camera locks ensure sequential processing within a camera.
3. The analysis queue (`analysis_queue`) is shared across all cameras, with DLQ overflow policy to handle burst scenarios.
4. The inference semaphore (`get_inference_semaphore()`) in the detector client limits concurrent GPU operations globally.

**One concern:** The `_batch_close_lock` is a single global lock, meaning only one batch can close at a time across all cameras. If many batches time out simultaneously (e.g., after a burst of activity across 10 cameras), they will close sequentially. This is likely fine for typical home security (2-8 cameras) but could bottleneck at scale.

### 6.4 GPU Memory Pressure Backpressure (NEM-1727)

The BatchAggregator integrates with the GPU monitor to apply backpressure when GPU memory is at CRITICAL level. The `should_apply_backpressure()` method checks memory pressure before processing. This prevents OOM crashes during sustained high-activity periods.

---

## 7. What Is Working Correctly

1. **Batch lifecycle management:** Creation, detection accumulation, timeout checking, and closing are well-implemented with proper Redis state management and concurrency safety.
2. **Fast path bypasses:** Critical threats (weapons, fire, smoke) correctly bypass the 90-second window for immediate processing.
3. **Enrichment pipeline parallelism:** The 3-phase architecture maximizes throughput with correct dependency ordering and `asyncio.gather` usage.
4. **Graceful degradation:** `return_exceptions=True` on all `asyncio.gather` calls, structured error handling with `EnrichmentError`, and adaptive quality levels ensure partial results are returned when individual models fail.
5. **Pipeline timeout:** 30-second hard timeout with `asyncio.timeout()` prevents enrichment from consuming the entire batch window.
6. **Concurrency control:** Per-service semaphores prevent GPU saturation; inference semaphore limits global concurrent AI operations.
7. **Observability:** Prometheus metrics for batch lifecycle, enrichment stage timing, model call/error counts, and pipeline timeouts.
8. **Backpressure:** GPU memory pressure integration prevents OOM during sustained load.
9. **WebSocket broadcasting:** Real-time `detection.new` and `detection.batch` events for frontend updates.

---

## 8. Gaps Identified

### 8.1 HIGH: HTTP Batch Inference Not Used

**Impact: Significant per-detection HTTP overhead**

The backend makes separate HTTP calls to AI services for each detection in a batch:

- Florence-2: Multiple VQA queries per detection (color, type, commercial, clothing, carrying, action), each a separate HTTP POST with base64 image encoding.
- CLIP: Separate embedding extraction per person/vehicle crop.
- YOLO26: The `/detect/batch` endpoint exists but `DetectorClient` sends one image per call.

**Current flow for a batch of 5 person detections:**

- Florence-2: ~25 HTTP calls (5 detections x ~5 queries each)
- CLIP embeddings: 5 HTTP calls
- Each call includes base64 encode/decode overhead (~33% size increase)

**Recommended fix:** Implement batch HTTP endpoints for Florence-2 and CLIP, and update the backend to use the existing YOLO26 batch endpoint. Estimated 40-60% reduction in HTTP overhead for multi-detection frames.

### 8.2 MEDIUM: BatchCoalescer Not Wired Into Pipeline

**Impact: Missing 20-40% inference reduction**

The `BatchCoalescer` is fully implemented with Redis-backed candidate tracking, compatibility checking, priority system, and merge metrics. Configuration (`batch_coalescing_enabled`, etc.) exists in settings. However, it does not appear to be called anywhere in the batch processing hot path. The coalescer needs to be integrated between `BatchAggregator.close_batch()` and the Nemotron analysis queue consumer.

### 8.3 MEDIUM: Florence-2 BatchProcessor Unused

**Impact: Missed GPU throughput optimization**

`Florence2Model.__init__` creates a `BatchProcessor(BatchConfig(max_batch_size=4))` but no endpoint or method uses it. The shared `ai/torch_optimizations.py` `BatchProcessor` class supports padding images to uniform size and splitting large batches. Enabling true batch inference would allow processing multiple VQA queries in a single GPU forward pass instead of sequential calls.

### 8.4 LOW: Global Batch Close Lock Scalability

**Impact: Potential bottleneck with many cameras**

The `_batch_close_lock` is a single `asyncio.Lock` that serializes all batch close operations globally. For a home deployment with 2-8 cameras this is fine, but if the system scales to 20+ cameras, simultaneous batch closes could queue up. Consider per-camera close locks or a lock-free approach using Redis atomic operations.

### 8.5 LOW: Coalescer `remove_candidates` Uses Invalid Redis Pattern

**Impact: Stale candidate references**

`BatchCoalescer.remove_candidates()` calls `redis.zrem("coalesce:candidates:*", *batch_ids)` but `ZREM` does not support glob patterns -- it operates on a single key. This means candidates are not properly removed from sorted sets after merging, relying solely on the 10-minute TTL for cleanup. This should be fixed to use the camera_id from each candidate to target the correct sorted set.

---

## 9. Recommended Improvements (Prioritized)

### Priority 1: Wire BatchCoalescer into Pipeline

**Effort: Low (1-2 days)**

Insert the coalescer between batch close and analysis queue consumption. When a batch is pulled from the analysis queue, check for compatible candidates and merge before sending to Nemotron.

### Priority 2: Use YOLO26 Batch Detection Endpoint

**Effort: Low (1-2 days)**

Update `DetectorClient` to accumulate frames and use `POST /detect/batch` when multiple frames are pending for different cameras. The server-side implementation is complete.

### Priority 3: Implement Florence-2 Batch Extract Endpoint

**Effort: Medium (3-5 days)**

Add a `/batch-extract` endpoint to Florence-2 that accepts multiple images/prompts and processes them as a batch using the existing `BatchProcessor`. Update `FlorenceClient` and `VisionExtractor` to use batch calls when processing multiple detections.

### Priority 4: Implement CLIP Batch Embedding Endpoint

**Effort: Medium (2-3 days)**

Add a `/batch-embed` endpoint to CLIP that accepts multiple base64 images and returns embeddings for all. Update the re-ID service to use batch calls when extracting embeddings for multiple person/vehicle crops.

### Priority 5: Fix Coalescer `remove_candidates`

**Effort: Low (0.5 days)**

Store camera_id in the `CoalesceCandidate` (already present) and use it to target the correct sorted set key in `remove_candidates()`.

---

## 10. Performance Metrics to Track

The following metrics should be monitored to validate batching effectiveness:

| Metric                                   | Current Status               | Purpose                                                       |
| ---------------------------------------- | ---------------------------- | ------------------------------------------------------------- |
| `hsi_batch_max_detections_reached_total` | Implemented                  | Tracks batches hitting the 500-detection cap                  |
| `hsi_enrichment_pipeline_stage_seconds`  | Implemented                  | Per-phase timing (phase1_and_florence, phase2, phase3, total) |
| `hsi_enrichment_pipeline_timeout_total`  | Implemented                  | Pipeline timeout frequency                                    |
| `hsi_enrichment_model_call_total`        | Implemented                  | Per-model call counts                                         |
| `hsi_enrichment_model_error_total`       | Implemented                  | Per-model error counts                                        |
| `hsi_enrichment_model_duration_seconds`  | Implemented                  | Per-model latency                                             |
| Coalescer merge rate                     | Implemented (in-memory only) | `CoalescerMetrics.avg_inference_reduction_pct`                |
| **Batch close latency**                  | **Not tracked**              | Time from first detection to batch close                      |
| **Analysis queue depth**                 | **Not tracked**              | Number of pending batches awaiting Nemotron analysis          |
| **HTTP calls per batch**                 | **Not tracked**              | Number of AI service HTTP calls per enrichment run            |
| **Florence-2 calls per detection**       | **Not tracked**              | VQA query count per detection type                            |
| **Coalescer Prometheus metrics**         | **Not exported**             | In-memory metrics not exposed to Prometheus                   |

### Recommended New Metrics

1. **`hsi_batch_close_latency_seconds`** (histogram): Time from batch creation to close, labeled by close_reason (timeout/idle/max_size).
2. **`hsi_analysis_queue_depth`** (gauge): Current depth of the analysis_queue in Redis.
3. **`hsi_enrichment_http_calls_per_batch`** (histogram): Total HTTP calls to AI services per enrichment pipeline run.
4. **`hsi_coalescer_merges_total`** (counter): Prometheus-exported coalescer merge count.
5. **`hsi_coalescer_inference_reduction_percent`** (histogram): Per-merge inference reduction percentage.

---

## 11. Summary

The batching and scheduling optimization (Phase 5) has a solid foundation:

- **Batch aggregation** is production-ready with robust Redis state management, multi-level concurrency safety, and appropriate timeout configuration.
- **The enrichment pipeline** demonstrates excellent parallel architecture with 3-phase execution, per-service semaphores, and graceful degradation.
- **Fast path bypasses** ensure critical security events are not delayed by batching.

The primary gaps are:

1. **BatchCoalescer is implemented but not wired into the pipeline** -- the 20-40% inference reduction it promises is currently unrealized.
2. **HTTP batch inference is underutilized** -- YOLO26 has a batch endpoint the backend ignores, and Florence-2/CLIP process one detection at a time despite having BatchProcessor infrastructure.
3. **Several performance metrics** that would validate batching effectiveness are not yet tracked.

Addressing gaps #1 and #2 would yield the most significant performance improvement, estimated at 30-50% reduction in per-batch processing time for multi-detection frames.
