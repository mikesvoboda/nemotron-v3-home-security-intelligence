# Glossary

> Definitions of key terms used throughout the Home Security Intelligence documentation.

**Time to read:** ~12 min

---

## A

### Alert Rule

A configurable condition that triggers notifications when events match specified criteria. Rules can filter by risk threshold, object types, cameras, time schedules, and other parameters. See [System Operations API](../developer/api/system-ops.md).

### Analysis Worker

Background worker process that sends detection batches to the Nemotron LLM for risk assessment. Part of the [Pipeline](#pipeline).

---

## B

### Batch

A collection of detections from a single camera grouped within a time window. Batches are sent to Nemotron for analysis as a unit. Controlled by `BATCH_WINDOW_SECONDS` and `BATCH_IDLE_TIMEOUT_SECONDS`.

### Batch Aggregation

The process of collecting individual detections over configurable time windows before sending them as a batch for AI analysis. This reduces API calls and allows the LLM to analyze patterns across multiple detections. See [Batch Aggregator](#batch-aggregator).

### Batch Aggregator

Service that groups individual detections into batches based on camera and time proximity. Batches are closed when either the time window expires or idle timeout is reached.

### Bounding Box

The rectangular region in an image where an object was detected. Defined by X/Y coordinates (top-left corner) and width/height in pixels.

---

## C

### Camera

A physical security camera device that uploads images via FTP to the configured `FOSCAM_BASE_PATH`. Each camera has a unique folder where images are stored.

### CDI (Container Device Interface)

A specification for exposing hardware devices (like GPUs) to containers in a standardized way. Used by container runtimes to provide GPU access to AI services. See also [NVIDIA CDI](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html).

### CI/CD (Continuous Integration/Continuous Deployment)

Automated software development practices where code changes are automatically built, tested, and deployed. This project uses GitHub Actions for CI/CD with automated testing, container builds, and deployment verification.

### Circuit Breaker

A fault tolerance pattern that temporarily disables calls to a failing service. When failures exceed a threshold, the circuit "opens" and returns cached errors immediately. After a timeout, it allows test calls to check if the service has recovered.

### CLIP

Contrastive Language-Image Pre-training model used for generating image embeddings that enable re-identification of people and objects across different camera frames.

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

A vector representation of data (such as an image or text) in a high-dimensional space where similar items are positioned close together. Used for similarity search and re-identification. See [CLIP](#clip), [Re-identification](#re-identification-re-id).

### Entity Re-ID

See [Re-identification (Re-ID)](#re-identification-re-id).

### Event

A security incident that may contain one or more detections, analyzed by Nemotron for risk assessment. Events have a risk score, risk level, summary, and reasoning explanation.

### Enrichment Service

Optional AI service that aggregates advanced vision features including vehicle damage detection, clothing segmentation, pet classification, and image quality analysis.

### Event Broadcaster

Service that sends real-time event notifications to connected WebSocket clients.

---

## F

### Florence-2

Vision-language model from Microsoft used for extracting rich visual attributes like detailed descriptions, object attributes, and scene understanding.

### Fast Path

An optimization that bypasses normal batching for high-confidence detections of critical object types. Enables faster alerting for important detections.

### File Watcher

Service that monitors camera directories for new image uploads and submits them for processing through the detection pipeline.

### FTP (File Transfer Protocol)

The protocol used by Foscam cameras to upload images to the server. Images are uploaded to camera-specific folders under `FOSCAM_BASE_PATH`.

---

## G

### GGUF

A file format for storing quantized LLM models, used by llama.cpp. Nemotron models are distributed in GGUF format.

### GPU (Graphics Processing Unit)

The hardware accelerator used to run AI models. This system requires an NVIDIA GPU with CUDA support for optimal performance.

---

## H

### Health Check

An API endpoint that verifies system component status. Used by container orchestrators to determine if the service is operational.

### Hub

A documentation entry point organized around a specific user persona or goal. The three hubs are: Operator Hub (run the system), Developer Hub (extend the system), and How-To Guides (complete specific tasks).

---

## I

### Idle Timeout

The time period after which an inactive batch is closed and sent for analysis, even if the time window hasn't expired. Set by `BATCH_IDLE_TIMEOUT_SECONDS`.

### Inference

The process of running an AI model on input data to produce predictions. For this system: YOLO26 inference detects objects; Nemotron inference analyzes risk.

---

## J

### JWT (JSON Web Token)

A compact, URL-safe token format for securely transmitting claims between parties. Commonly used for authentication and authorization. While this system does not use authentication, JWT is mentioned in security documentation for future multi-user scenarios.

---

## L

### llama.cpp

An open-source C++ implementation for running LLM inference. Used to run the Nemotron model with efficient GPU acceleration.

### Liveness Probe

A health check that indicates whether the application is running. If it fails, the container should be restarted. See `GET /health`.

---

## N

### Nemotron

NVIDIA's family of large language models. Production deployments use **Nemotron-3-Nano-30B-A3B** (~14.7GB VRAM, 128K context) for risk assessment and generating human-readable security analysis. Development environments can use the smaller Nemotron Mini 4B (~3GB VRAM) for testing.

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

1. **File Watcher** detects new image
2. **Detection Worker** sends to YOLO26
3. **Batch Aggregator** groups detections
4. **Analysis Worker** sends to Nemotron
5. **Event** created with risk assessment

### Pipeline Latency

Timing metrics for each stage of the pipeline. Used to identify bottlenecks and monitor performance.

---

## Q

### Queue

A Redis list that holds items waiting to be processed. The system uses separate queues for detection and analysis.

### Quantization

A technique to reduce model size and memory usage by using lower precision numbers. The Nemotron model uses Q4_K_M quantization (4-bit with medium quality K-quants).

---

## R

### Rate Limiting

Protection against excessive API requests. Requests exceeding the limit are rejected with HTTP 429. Configured per endpoint tier.

### Re-identification (Re-ID)

The process of matching detected people or objects across different camera frames or time periods using CLIP embeddings.

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

- **RFC 7807**: Problem Details for HTTP APIs (error response format)
- **RFC 9457**: Updated Problem Details specification
- **RFC 7234**: HTTP Caching
- **RFC 6455**: WebSocket Protocol

### Risk Level

A categorical classification derived from the risk score:

- **Low** (0-29): Routine activity
- **Medium** (30-59): Notable, worth reviewing
- **High** (60-84): Concerning, review soon
- **Critical** (85-100): Immediate attention required

See [Risk Levels Reference](config/risk-levels.md).

### Risk Score

A numeric value from 0-100 assigned by Nemotron indicating the threat level of an event. Higher scores indicate greater concern. The score is used to determine [Risk Level](#risk-level).

### YOLO26

A state-of-the-art real-time object detection model. Uses a transformer architecture for accurate detection with low latency. This system uses the L (Large) variant.

---

## S

### SBOM (Software Bill of Materials)

A formal inventory of all software components, libraries, and dependencies used in an application. Generated during CI/CD builds for security auditing and vulnerability tracking.

### Scene Change Detection

Feature that tracks baseline scene characteristics to detect significant environmental changes like lighting shifts or camera tampering.

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

### Vision Extraction

Process of using Florence-2 to extract detailed visual attributes from detection images, including clothing descriptions, pose information, and contextual details.

### VRAM (Video RAM)

Memory on the GPU used to store models and data during inference. This system requires approximately 7GB VRAM total for both AI services.

---

## W

### WebSocket

A protocol providing full-duplex communication over a single TCP connection. Used for real-time streaming of events and system status.

### Worker

A background process that performs asynchronous tasks. The system has several workers:

- Detection Worker
- Analysis Worker
- GPU Monitor
- Cleanup Service
- System Broadcaster

### Worksteal

A work distribution strategy used by pytest-xdist where test workers "steal" tests from other workers that have finished their assigned work. Results in more efficient parallel test execution compared to static distribution. Enabled with `--dist=worksteal`. See also [Domain Sharding](#domain-sharding).

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
