# Glossary

> Definitions of key terms used throughout the Home Security Intelligence documentation.

**Time to read:** ~12 min

---

## A

### Alert Rule

A stored condition on risk threshold, object types, cameras and schedules (`backend/services/alert_engine.py`, `AlertRuleEngine`), evaluated by the alerts API when it is called — the engine runs no scheduler of its own, so nothing fires on its own. See [System Operations API](../developer/api/system-ops.md).

### Analysis Worker

Background worker process (`backend/services/pipeline_workers.py`, `AnalysisQueueWorker`) that hands a closed batch to `VlmAnalyzer`, which assembles the key frames and the specialist lookups into one request for `ai-vlm`. Part of the [Pipeline](#pipeline).

---

## B

### Batch

A collection of detections from a single camera grouped within a time window. A batch is handed to `ai-vlm` for analysis as a unit. The window and idle timeout come from `BATCH_WINDOW_SECONDS` and `BATCH_IDLE_TIMEOUT_SECONDS`; `batch_max_detections` (500, `backend/core/config.py`, no `.env` override) closes a batch early once it is full.

### Batch Aggregation

The process of collecting individual detections over configurable time windows before sending them as a batch for AI analysis. This reduces API calls and allows the LLM to analyze patterns across multiple detections. See [Batch Aggregator](#batch-aggregator).

### Batch Aggregator

Service that groups individual detections into batches based on camera and time proximity (`backend/services/batch_aggregator.py`). A batch closes when the time window expires, the idle timeout is reached, or `batch_max_detections` is hit.

### Bounding Box

The rectangular region in an image where an object was detected. Defined by X/Y coordinates (top-left corner) and width/height in pixels.

---

## C

### Camera

A physical security camera device that uploads images via FTP to the configured `FOSCAM_BASE_PATH`. Each camera has a unique folder where images are stored. Cameras that support streaming instead of FTP snapshots are ingested via RTSP (served locally by `go2rtc`).

### CDI (Container Device Interface)

A specification for exposing hardware devices (like GPUs) to containers in a standardized way. Used by container runtimes to provide GPU access to AI services. See also [NVIDIA CDI](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html).

### CI/CD (Continuous Integration/Continuous Deployment)

Automated software development practices where code changes are automatically built, tested, and deployed. This project uses GitHub Actions for CI/CD with automated testing, container builds, and deployment verification.

### Circuit Breaker

A fault tolerance pattern that temporarily disables calls to a failing service. When failures exceed a threshold, the circuit "opens" and returns cached errors immediately. After a timeout, it allows test calls to check if the service has recovered.

### Confidence Score

A value from 0.0 to 1.0 indicating how certain the YOLO26 model is about a detection. Higher values mean more certainty. Controlled by `DETECTION_CONFIDENCE_THRESHOLD`.

### COCO Classes

The 80 object categories that YOLO26 can detect, based on the Common Objects in Context (COCO) dataset. Includes person, car, dog, cat, bicycle, and many others.

---

## D

### Dead Letter Queue (DLQ)

A queue where failed messages are stored when they cannot be processed after multiple retry attempts. Allows operators to investigate and reprocess failed items.

### Degradation Mode

A system operating state when some services are unavailable. The system continues operating with reduced functionality. Modes: `normal`, `degraded`, `minimal`, `offline`.

### Detection

A single object instance identified by YOLO26 in an image. Contains object type, confidence score, bounding box coordinates, and timestamp. Multiple detections may be grouped into one [Event](#event).

### Detection Worker

Background worker process that sends images to YOLO26 for object detection. Part of the [Pipeline](#pipeline).

### Domain Sharding

A test parallelization strategy that splits tests by functional domain (API, WebSocket, services, models) rather than arbitrary file distribution. Enables independent CI jobs to run tests in parallel with optimal caching and isolation. See also [Worksteal](#worksteal).

---

## E

### Embedding

A vector representation of an image in a high-dimensional space where similar items sit close together. The one shipped producer is `osnet-ain-x1-0`, and every stored vector carries the `model_id` of the weights that made it so two spaces are never compared. See [Re-identification (Re-ID)](#re-identification-re-id).

### Entity Re-ID

See [Re-identification (Re-ID)](#re-identification-re-id).

### Event

A security incident containing one or more detections from one camera batch. `ai-vlm` grades it; `apply_verdict_invariants()` (`backend/services/vlm_analyzer.py`) validates the answer before the Event is written. An Event has a risk score, risk level, summary, and reasoning explanation — and a `null` score means the scorer failed, so the event is flagged for review.

### Event Broadcaster

Service that sends real-time event notifications to connected WebSocket clients.

---

## F

### Fast Path

An optimization that scores a single high-confidence detection ahead of the batch gate. It ships **off**: `FAST_PATH_CONFIDENCE_THRESHOLD` defaults to `2.0`, a confidence no detector can report, and `FAST_PATH_OBJECT_TYPES` is empty (`backend/core/config.py`). Where it is enabled, the request still runs through `VlmAnalyzer` — there is no second analysis path.

### File Watcher

Service that monitors camera directories for new image uploads and submits them for processing through the detection pipeline.

### FTP (File Transfer Protocol)

The protocol used by Foscam cameras to upload images to the server. Images are uploaded to camera-specific folders under `FOSCAM_BASE_PATH`.

---

## G

### GGUF

A file format for storing a quantized LLM for llama.cpp. `ai-vlm` loads two GGUF files as one identity: the weights named by `VLM_MODEL_PATH` and the vision projector named by `VLM_MMPROJ_PATH`.

### GPU (Graphics Processing Unit)

The hardware accelerator behind the two AI containers. An NVIDIA GPU with CUDA support is required for `ai-vlm` (its verdict latency on CPU runs to tens of seconds) and for Triton's CUDA execution provider in `ai-gateway`; the lookup models run on CPU either way.

---

## H

### Health Check

An API endpoint that verifies system component status. Used by container orchestrators to determine if the service is operational.

### Hub

A documentation entry point organized around a specific user persona or goal. The main hubs are Getting Started (install and first run), User Guide (use the dashboard), Operator Hub (run the system) and Developer Hub (extend the system). See [docs/README.md](../README.md).

---

## I

### Idle Timeout

The time period after which an inactive batch is closed and sent for analysis, even if the time window hasn't expired. Set by `BATCH_IDLE_TIMEOUT_SECONDS`.

### Inference

The process of running an AI model on input data to produce predictions. For this system: Triton runs YOLO26 detection in `ai-gateway`, `ai-vlm` turns a batch into a risk verdict, and the lookup models run in the backend process on CPU.

---

## J

### JWT (JSON Web Token)

A compact, URL-safe token format for securely transmitting claims between parties. The backend's `AuthService` can sign and verify HS256 JWTs (PyJWT), but nothing issues one: `POST /api/auth/login` sets an opaque Redis session cookie, and the `EXPOSE_LAN` auth gate (`AuthMiddleware`) accepts that cookie or an API key, never a JWT. See [Security Architecture](../architecture/security/README.md).

---

## L

### llama.cpp

An open-source C++ inference server. The `ai-vlm` container runs its `llama-server` binary on the configured GGUF; the backend talks to its OpenAI-compatible `/v1/chat/completions`.

### Liveness Probe

A health check that indicates whether the application is running. If it fails, the container should be restarted. See `GET /health`.

---

## N

---

## O

### Object Type

The classification label assigned to a detected object (e.g., "person", "car", "dog"). Corresponds to [COCO Classes](#coco-classes).

### OWASP (Open Web Application Security Project)

A nonprofit foundation focused on improving software security. OWASP publishes security guidelines, vulnerability classifications (like the OWASP Top 10), and testing methodologies used in this project's security scanning.

---

## P

### Pipeline

The end-to-end processing flow for security images:

1. **File Watcher** detects a new image
2. **Detection Worker** sends it to YOLO26 in `ai-gateway`
3. **Batch Aggregator** groups the detections by camera and time
4. **Analysis Worker** runs the specialist lookups and sends the batch to `ai-vlm`
5. **Event** is created with the verified risk assessment

### Pipeline Latency

Timing metrics for each stage of the pipeline. Used to identify bottlenecks and monitor performance.

---

## Q

### Queue

A Redis-backed buffer that holds items waiting to be processed. The main pipeline stages run on Redis **streams** with consumer groups (`detections:stream`, `analysis:stream`, each with a `:dlq` stream), while some auxiliary paths (degradation fallback, admin queue operations) still use Redis lists. The system keeps separate queues for detection and analysis.

### Quantization

Reducing a model's precision to shrink its memory footprint. The shipped VLM defaults are a `Q4_K_M` weights file with a `Q8_0` vision projector (`VLM_MODEL_PATH` / `VLM_MMPROJ_PATH`), and `q8_0` key/value cache types, which about halve the KV cache pool.

---

## R

### Rate Limiting

Protection against excessive API requests. Requests exceeding the limit are rejected with HTTP 429. Configured per endpoint tier.

### Re-identification (Re-ID)

The process of matching detected people across different camera frames or time periods using OSNet-AIN x1.0 person embeddings (512-dim, SHA-256-pinned weights, `model_id` provenance on every stored vector). Vehicles match by license plate; no vehicle embedding producer ships in the resident mode.

### Readiness Probe

A health check that indicates whether the application is ready to receive traffic. If it fails, traffic should not be routed to this instance. See `GET /ready`.

### Redis

An in-memory data store used for:

- Processing queues (detection, analysis)
- Batch state storage
- Rate limiting counters
- File deduplication cache

### Retention Period

The number of days that events, detections, and other data are kept before automatic cleanup. Set by `RETENTION_DAYS`.

### RFC (Request for Comments)

A formal document from standards organizations (like IETF) that describes internet protocols and best practices. This project follows several RFCs including:

- **RFC 7807**: Problem Details for HTTP APIs (the error response format implemented in `backend/api/exception_handlers.py`, served as `application/problem+json`; RFC 9457 is the newer obsoleting spec)
- **RFC 7234**: HTTP Caching (ETag middleware and the RFC 7234 `Warning` header emitted for deprecated endpoints)
- **RFC 6455**: WebSocket Protocol

### Risk Level

A categorical classification derived from the risk score:

- **Low** (0-29): Routine activity
- **Medium** (30-59): Notable, worth reviewing
- **High** (60-84): Concerning, review soon
- **Critical** (85-100): Immediate attention required

See [Risk Levels Reference](config/risk-levels.md).

### Risk Score

A numeric value from 0-100 indicating the threat level of an event, produced by `ai-vlm` and checked by `apply_verdict_invariants()`. Higher scores indicate greater concern, and the score determines the [Risk Level](#risk-level). A `null` score is not a low score: it means the scorer failed and the event needs review.

---

## S

### SBOM (Software Bill of Materials)

A formal inventory of all software components, libraries, and dependencies used in an application. Generated during CI/CD builds for security auditing and vulnerability tracking.

### Scene Change Detection

An SSIM comparison of a camera's frames against its baseline, implemented in `backend/services/scene_change_detector.py` and reported through the settings API. Nothing in the running pipeline calls it, so the lighting-shift and tampering signals it would produce are not part of any verdict.

### Severity

The classification of alert importance: `low`, `medium`, `high`, or `critical`. Used in [Alert Rules](#alert-rule) to prioritize notifications.

### Snapshot

A camera image capture at a specific moment in time.

### System Broadcaster

Service that sends real-time system status updates (GPU stats, queue depths) to connected WebSocket clients.

---

## T

### Thumbnail

A smaller version of a detection image with bounding box overlays. Stored in `VIDEO_THUMBNAILS_DIR` for quick display.

### Time Window

The maximum duration for grouping detections into a batch. Set by `BATCH_WINDOW_SECONDS`.

### TLS (Transport Layer Security)

A cryptographic protocol that provides secure communication over networks. Used for HTTPS connections and secure WebSocket (WSS) communication. Successor to SSL.

---

## U

### UUID (Universally Unique Identifier)

A 128-bit identifier that is unique across space and time. Used extensively in this system for entity IDs (events, detections, cameras, alerts) to ensure no collisions across distributed systems. Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

---

## V

### VRAM (Video RAM)

Memory on the GPU used to store models and data during inference. Two containers hold it: `ai-vlm` (GGUF weights, its vision projector and the KV cache pool) and `ai-gateway` (the Triton CUDA context plus the resident ONNX models). `VLM_GPU_LAYERS` decides how much of the VLM the card gets, and `VLM_CTX_SIZE` / `VLM_PARALLEL` size the KV pool. The face, plate and person-re-ID lookups run on CPU. See [Prerequisites](../getting-started/prerequisites.md) and [VRAM Budget](nvidia-technology-inventory.md#vram-budget).

---

## W

### WebSocket

A protocol providing full-duplex communication over a single TCP connection. Used for real-time streaming of events and system status.

### Worker

A background process that performs asynchronous tasks. The system has several workers:

- Detection Worker (`DetectionQueueWorker`)
- Analysis Worker (`AnalysisQueueWorker`)
- Batch Timeout Worker (`BatchTimeoutWorker`)
- GPU Monitor
- Cleanup Service
- System Broadcaster

### Worksteal

A work distribution strategy used by pytest-xdist where test workers "steal" tests from other workers that have finished their assigned work. Results in more efficient parallel test execution compared to static distribution. Enabled with `--dist=worksteal`. See also [Domain Sharding](#domain-sharding).

---

## Y

### YOLO26

A real-time object detection model from the Ultralytics family (CNN-based, NMS-free). This system uses the **m (Medium)** variant (`yolo26m`) as FP32 ONNX under Triton, in the `ai-gateway` container behind the `/yolo26` router. See [YOLO26 Client](../architecture/ai-orchestration/yolo26-client.md) and [Models Reference](models.md).

---

## Related Resources

- [Environment Variables](config/env-reference.md) - Configuration reference
- [Risk Levels](config/risk-levels.md) - Severity thresholds
- [Troubleshooting](troubleshooting/index.md) - Problem solving guide

---

## See Also

- [Codebase Tour](../developer/codebase-tour.md) - Project structure overview
- [Pipeline Overview](../developer/pipeline-overview.md) - AI pipeline architecture
- [User Hub](../user/README.md) - User documentation

---

[Back to User Hub](../user/README.md) | [Operator Hub](../operator/README.md) | [Developer Hub](../developer/README.md)
