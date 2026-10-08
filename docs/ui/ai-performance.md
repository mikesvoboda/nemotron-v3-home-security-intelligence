# AI Performance

![AI Performance Screenshot](../images/screenshots/ai-performance.png)

The AI Performance page provides real-time monitoring of the AI pipeline that powers security event detection and risk analysis. It displays metrics for the YOLO26 object detector served by `ai-gateway`, the vision-language risk analyzer served by `ai-vlm`, and the overall processing pipeline.

## Overview

The AI Performance page provides real-time monitoring of the AI models that power your security system. Here you can track:

- Model health status (YOLO26 and the VLM serve)
- Processing latency and queue depths
- Detection and event statistics
- Risk score distribution
- **Model Zoo** - the lookup models the pipeline can load (catalog: `models.yml`, 10 rows; `models.yml` is the single source of truth)

## Accessing the AI Performance Page

Click the **Brain icon** or **AI Performance** in the left sidebar, or navigate directly to `/ai`.

## What You're Looking At

The AI Performance page embeds the **AI Services Grafana dashboard** (`/grafana/d/ai-services/ai-services`) in kiosk mode. This provides a unified monitoring experience with all AI metrics visualized through Grafana's powerful charting capabilities.

**Key features displayed in the Grafana dashboard:**

- **Model Health Status** - Real-time health probe of the YOLO26 route on `ai-gateway`
- **Inference Latency** - Average, P50, P95, and P99 latency statistics for each AI service
- **Pipeline Throughput** - Queue depths, detection counts, and event generation rates
- **Historical Trends** - Time-series charts showing performance over time
- **GPU Utilization** - VRAM usage and GPU performance metrics

**Page controls:**

- **Refresh Button** - Manually reload the Grafana iframe to get the latest data
- **Open in Grafana** - Opens the full dashboard in a new tab with editing capabilities (no kiosk mode)

The Grafana dashboard auto-refreshes based on its own configured interval. Use the "Refresh" button in the page header to force a reload.

## Key Metrics Explained

The Grafana dashboard displays metrics from the AI pipeline. Here's what each metric means:

### AI Model Health

**YOLO26 (Object Detection)**

- Detects people, vehicles, and animals in camera images
- Ultralytics YOLO26 served by Triton inside `ai-gateway` (ONNX FP32 on the CUDA execution
  provider); the backend calls it via `YOLO26_URL` (default `http://ai-gateway:8090/yolo26`)
- Typical inference time: 30-50ms per image
- Health status: `http://localhost:8090/yolo26/health` (healthy/degraded/unhealthy/unknown)

**VLM (Risk Analysis)**

- Reviews up to 4 key frames from each detection batch and produces the verdict, summary,
  reasoning, `risk_score` and `risk_level` that the event carries
- Runs via llama.cpp in the `ai-vlm` container (host port 8098, `http://127.0.0.1:${AI_VLM_PORT:-8098}`),
  reached as `http://ai-vlm:8098/v1/chat/completions`. ai-vlm is the only LLM service.
- Shipped weights are `VLM_MODEL_PATH` (`Qwen3VL-8B-Instruct-Q4_K_M.gguf`) plus the multimodal
  projector `VLM_MMPROJ_PATH` (`mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`); model identity is config,
  not a product requirement
- `ai-vlm` is in the default compose set — a plain `up -d` starts it. On a stack that is
  already running, start just it with
  `podman compose -f docker-compose.prod.yml up -d ai-vlm`
- Typical inference time: seconds per batch, dominated by prompt fitting and prefill
- Health status: `http://localhost:8098/health`

> **A `/health` 200 does not prove the serve can see.** `ai/vlm/Dockerfile` passes `--mmproj` only
> when `MMPROJ_PATH` is non-empty, so a projector-less server answers 200 while every analysis
> degrades. The signature is a run of events with `verification_failed` and a NULL risk score.

### Latency Metrics

The dashboard tracks latency at multiple pipeline stages:

| Stage               | Description                                   | Warning Threshold | Critical Threshold |
| ------------------- | --------------------------------------------- | ----------------- | ------------------ |
| Detection Inference | Time for YOLO26 to process one image          | 500ms             | 2000ms             |
| Analysis Inference  | Time for the VLM to analyze a batch           | 5000ms            | 30000ms            |
| Watch to Detect     | File detection to detection result            | 100ms             | 500ms              |
| Detect to Batch     | Detection result to batch assignment          | 200ms             | 1000ms             |
| Batch to Analyze    | Batch closure to analysis completion          | 100ms             | 500ms              |
| Total Pipeline      | End-to-end from file upload to event creation | Varies            | Varies             |

**Expected end-to-end latency:**

- Normal path (batched): 30-95 seconds (dominated by batch window)
- Fast path (high-confidence person): ~3-6 seconds — **currently disabled by default**
  (`FAST_PATH_ENABLED=false` in compose, and `FAST_PATH_OBJECT_TYPES` is empty)

### Queue Health

**Queue Depths** indicate processing backlog:

- Detection Queue: Images waiting for YOLO26 processing
- Analysis Queue: Batches waiting for VLM analysis

| Queue Depth | Status            | Meaning                   |
| ----------- | ----------------- | ------------------------- |
| < 10 items  | Healthy (green)   | Processing keeping up     |
| 10-50 items | Moderate (yellow) | Some backlog forming      |
| > 50 items  | Backlog (red)     | Processing cannot keep up |

**Throughput Counters:**

- Total Detections: Objects detected by YOLO26
- Total Events: Security events generated by the pipeline

**Error Monitoring:**

- Pipeline Errors: Failures by type (detection errors, analysis errors, etc.)
- Queue Overflows: Items dropped due to queue capacity limits
- Dead Letter Queue (DLQ): Failed jobs awaiting manual review or reprocessing

### Risk Score Distribution

Events are categorized by risk level:

Boundaries come from `severity_low_max` / `severity_medium_max` / `severity_high_max`
(config.py defaults 29 / 59 / 84 — configurable):

| Risk Level | Score Range | Description                                        |
| ---------- | ----------- | -------------------------------------------------- |
| Low        | 0-29        | Normal activity, no concern                        |
| Medium     | 30-59       | Unusual but not threatening                        |
| High       | 60-84       | Suspicious activity requiring attention            |
| Critical   | 85-100      | Potential security threat, immediate action needed |

### Clickable Risk Score Bars

The risk score distribution chart is interactive. Each bar and count is clickable.

**How It Works:**

1. **Click any bar** in the chart to navigate to the Event Timeline
2. The Timeline automatically filters to show only events at that risk level
3. You can quickly investigate all events of a specific severity

| Click Target           | Navigates To                    |
| ---------------------- | ------------------------------- |
| **Low bar/count**      | `/timeline?risk_level=low`      |
| **Medium bar/count**   | `/timeline?risk_level=medium`   |
| **High bar/count**     | `/timeline?risk_level=high`     |
| **Critical bar/count** | `/timeline?risk_level=critical` |

**Visual Feedback:**

- **Hover tooltip** - Shows "Click to view X events" on hover
- **Scale effect** - Bar slightly enlarges on hover
- **Pointer cursor** - Indicates the bar is clickable
- **Focus ring** - Green outline when using keyboard navigation

The bars are implemented as buttons for full keyboard accessibility (Tab to navigate, Enter/Space to select).

### Detection Class Distribution

Objects are detected in these security-relevant categories:

- **People**: person
- **Vehicles**: car, truck, bus, motorcycle, bicycle
- **Animals**: dog, cat, bird

## Model Zoo Section

The Model Zoo section renders the rows of `models.yml` as live status cards. What the shipped
pipeline puts in this catalog is the **lookup** set: the face leg (SCRFD-10G-KPS + ArcFace
w600k_r50), the person re-ID leg (OSNet-AIN x1.0) and the plate leg (FastALPR, with PaddleOCR
kept for general text), plus the YOLO detection helpers and the Triton `threat` engine. They
answer "who is this / what plate is this" by matching against the enrolled gallery; the
scene-level "what is happening" question belongs to the VLM, not to the Model Zoo.

### Summary Bar

The Model Zoo summary bar at the top displays key statistics:

| Indicator    | Description                                  |
| ------------ | -------------------------------------------- |
| **Loaded**   | Models currently in GPU memory (green dot)   |
| **Unloaded** | Available models not currently loaded (gray) |
| **Disabled** | Temporarily disabled models (yellow)         |
| **VRAM**     | GPU memory usage (used/budget)               |

**VRAM (Video RAM)** is the GPU memory used by loaded models. The Model Zoo has a dedicated budget of 1650 MB separate from core AI models.

### Latency Chart

The latency chart shows inference time trends for any Model Zoo model:

1. **Select a model** using the dropdown menu at the top right
2. **View timing data** displayed as three lines:
   - **Avg (ms)** - Average inference time (emerald green)
   - **P50 (ms)** - Median inference time (blue)
   - **P95 (ms)** - 95th percentile time (amber)
3. **Time axis** shows the last 60 minutes of data

**Chart Legend:**

| Line Color  | Metric     | Meaning                                 |
| ----------- | ---------- | --------------------------------------- |
| **Emerald** | Average    | Typical inference time                  |
| **Blue**    | P50/Median | Half of inferences are faster than this |
| **Amber**   | P95        | 95% of inferences are faster than this  |

> **No data?** If a model shows "No data available," it either has not been used recently or is disabled.

### Model Status Cards

Below the chart, each Model Zoo model appears as a status card with:

| Element          | Description                                        |
| ---------------- | -------------------------------------------------- |
| **Model Name**   | Human-readable name of the model                   |
| **Status Dot**   | Color-coded health indicator                       |
| **Status Label** | Current state (Loaded, Unloaded, Loading, etc.)    |
| **VRAM**         | GPU memory required when loaded                    |
| **Last Used**    | Time since model was last used ("2h ago", "Never") |
| **Category**     | Model type (Detection, Classification, etc.)       |

### Model Status Indicators

| Status       | Dot Color      | Meaning                          |
| ------------ | -------------- | -------------------------------- |
| **Loaded**   | Green          | Model is in GPU memory and ready |
| **Loading**  | Blue (pulsing) | Model is currently being loaded  |
| **Unloaded** | Gray           | Model available but not loaded   |
| **Disabled** | Yellow         | Model is turned off              |
| **Error**    | Red            | Model failed to load             |

### Active vs Disabled Models

Models are organized into two sections:

- **Active Models** - Enabled and available for use
- **Disabled Models** - Turned off (grayed out, appear at bottom)

**Why are some models disabled?**

- Incompatible with current software versions
- Moved to a dedicated service
- Not yet released
- Temporarily turned off for maintenance

### The Catalog `models.yml` Ships Today

VRAM figures are the `vram_mb` estimates from `models.yml`; `models.yml` is the source of truth
and this table is a snapshot of it. Ten rows:

| Model                      | Category  | VRAM   | Enabled | Preload | What it does                                                                      |
| -------------------------- | --------- | ------ | ------- | ------- | --------------------------------------------------------------------------------- |
| `yolo26`                   | detection | 0 MB   | false   | false   | Primary object detection; served by Triton in `ai-gateway`, not loaded by backend |
| `osnet-ain-x1-0`           | embedding | 100 MB | true    | true    | Person re-ID vectors (the `person_reid` lookup leg)                               |
| `face-detector-scrfd`      | detection | 0 MB   | true    | true    | SCRFD-10G-KPS face boxes + landmarks                                              |
| `face-recognizer`          | embedding | 0 MB   | true    | true    | ArcFace w600k_r50 512-d face embedding                                            |
| `threat-detection-yolov8n` | detection | 300 MB | true    | false   | Triton `threat` engine (opt-in lane, see below)                                   |
| `yolo11-face`              | detection | 200 MB | true    | false   | YOLO11n face detection on person crops                                            |
| `yolo11-license-plate`     | detection | 300 MB | true    | false   | YOLO11n license-plate detection                                                   |
| `fast-alpr`                | alpr      | 28 MB  | true    | false   | End-to-end plate detection + character reading (the `plates` lookup leg)          |
| `paddleocr`                | ocr       | 100 MB | true    | false   | General text recognition (plates are handled by FastALPR)                         |
| `yolo26-general`           | detection | 400 MB | false   | false   | Placeholder for a future ultralytics general model                                |

Two residency facts explain most "why does this card say Unloaded" questions:

- The three lookup legs (`faces`, `plates`, `person_reid`) read a **handle from the model
  registry and never trigger a load themselves**. That handle only exists if the boot preload
  sweep ran, and the sweep is gated on `BACKEND_MODEL_PRELOAD`, which ships **`false`**. So on a
  host under 24 GB of VRAM (or where the operator answered no) the face and re-ID cards read
  unloaded forever and nothing fails — the specialist line on every event renders
  `unavailable: specialist did not run`. The plate leg is the exception: FastALPR loads on demand.
- `GATEWAY_ENABLE_THREAT` ships **`false`**. When it is true, the Triton `threat` engine is loaded
  into `ai-gateway` residency as an opt-in lane; the F12 ruling keeps the threat leg out of the
  VLM specialist gather either way.

### Understanding Model Memory (VRAM)

Models load into your GPU's video memory (VRAM) when needed:

- **VRAM Budget** — the `used/budget` figure in the Model Zoo summary bar comes from the
  `/api/system/model-zoo/status` response (`vram_used_mb` / `vram_budget_mb`), not from a number
  written into this page
- **Loading Strategy:** the boot preload sweep loads one model at a time (sequential)
- **No automatic management:** once the preload sweep has run (or FastALPR loads on demand),
  the page shows what is loaded — there is no LRU eviction or demand-based unloading pass in
  the shipped `ModelManager`, so a card does not flip to Unloaded on its own

**Why does this matter?**

- **Loaded models** respond instantly
- **Unloaded models** need time to load before first use
- **VRAM constraints** limit how many models can be loaded simultaneously

> **Note:** The core detection model (YOLO26, loaded by Triton in `ai-gateway`) and the VLM GGUF
> pair (loaded by llama.cpp in `ai-vlm`) live outside this budget — they are resident on their own
> GPUs (`GPU_AI_SERVICES` / `GPU_LLM`).

## Settings & Configuration

### Grafana Configuration

The AI Performance page embeds a Grafana dashboard. The dashboard URL is fetched from the backend configuration API.

| Setting       | Environment Variable | Default                           | Description                                                                  |
| ------------- | -------------------- | --------------------------------- | ---------------------------------------------------------------------------- |
| Grafana URL   | `GRAFANA_URL`        | served under `/grafana/` on :3002 | URL of the Grafana instance (resolved by `frontend/src/utils/grafanaUrl.ts`) |
| Dashboard UID | N/A                  | `ai-services`                     | The dashboard to display                                                     |

The page loads the dashboard at: `{grafana_url}/d/ai-services/ai-services?orgId=1&kiosk=1&theme=dark&refresh=30s`

To access Grafana directly with full editing capabilities, click the "Open in Grafana" button in the page header. This opens the same dashboard without kiosk mode, allowing you to:

- Adjust time ranges
- Modify queries
- Create alerts
- Export data

### AI Service Configuration

| Setting               | Environment Variable                 | Default                                                                                    | Description                                                     |
| --------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| YOLO26 URL            | `YOLO26_URL`                         | `http://ai-gateway:8090/yolo26` (config default)                                           | Detection service endpoint                                      |
| AI Gateway URL        | `AI_GATEWAY_URL`                     | `http://ai-gateway:8090` (compose, `.env.example`)                                         | Gateway base; used when `USE_AI_GATEWAY=true`                   |
| VLM URL               | `AI_VLM_URL`                         | `http://localhost:8098` config default; compose `http://ai-vlm:8098`                       | VLM analysis endpoint (ai-vlm)                                  |
| VLM host port         | `AI_VLM_PORT`                        | `8098` (compose maps `127.0.0.1:8098:8098`)                                                | Host-side mapping for the VLM serve                             |
| VLM weights           | `VLM_MODEL_PATH` / `VLM_MMPROJ_PATH` | `/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf` / `/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` | GGUF + projector served by llama.cpp                            |
| Backend model preload | `BACKEND_MODEL_PRELOAD`              | `false` (`.env.example`, compose)                                                          | Boot-load the face and re-ID lookup legs (needs a >=24 GB host) |
| Detection Confidence  | `DETECTION_CONFIDENCE_THRESHOLD`     | `0.5` in `.env.example` (config default 0.40)                                              | Minimum confidence to store detection                           |
| Batch Window          | `BATCH_WINDOW_SECONDS`               | `90`                                                                                       | Maximum batch duration                                          |
| Idle Timeout          | `BATCH_IDLE_TIMEOUT_SECONDS`         | `30`                                                                                       | Close batch after this idle period                              |
| Fast Path Enabled     | `FAST_PATH_ENABLED`                  | `false` (compose) — fast path is currently OFF                                             | Master switch for fast path                                     |
| Fast Path Confidence  | `FAST_PATH_CONFIDENCE_THRESHOLD`     | config default `2.0` (disables it); compose overrides with `0.90`                          | Confidence for immediate analysis                               |
| Fast Path Types       | `FAST_PATH_OBJECT_TYPES`             | `[]` in config; `.env.example` shows `["person"]` commented out                            | Object types eligible for fast path                             |

### Refresh Settings

The AI Performance page relies on Grafana's built-in refresh mechanism. The dashboard's refresh interval is configured within Grafana itself.

| Setting           | Location                   | Description                                      |
| ----------------- | -------------------------- | ------------------------------------------------ |
| Dashboard Refresh | Grafana dashboard settings | Auto-refresh interval for the embedded dashboard |
| Manual Refresh    | Page header button         | Reloads the Grafana iframe on demand             |

**Note:** The standalone AI metrics components (available for other pages) use a 5-second polling interval with a 60-minute latency history window.

## Troubleshooting

### Grafana Dashboard Shows "Failed to Load"

1. Verify Grafana is running: `curl http://localhost:3002/api/health`
2. Check the backend config endpoint returns `grafana_url`: `curl http://localhost:8000/api/system/config`
3. Ensure network/firewall allows iframe embedding from Grafana
4. Check browser console for CORS or content security policy errors

### Model Shows "Unhealthy" Status

**YOLO26 (served by the `ai-gateway` Triton container):**

1. Check if the detection server is running: `curl http://localhost:8090/yolo26/health`
2. Verify GPU is available: `nvidia-smi`
3. Check container logs: `podman logs ai-gateway`
4. VRAM exhaustion may require restarting the service (`podman compose -f docker-compose.prod.yml restart ai-gateway`)

**VLM (`ai-vlm`, llama.cpp):**

1. Check if llama.cpp server is running: `curl http://localhost:8098/health`
2. Confirm the container is actually up — `ai-vlm` is in the default compose set, so a plain
   `up -d` starts it; if it is not running, start it with
   `podman compose -f docker-compose.prod.yml up -d ai-vlm`
3. Confirm the serve is multimodal, not text-only: a projector-less `llama-server` answers 200 on
   `/health`. `podman exec ai-vlm sh -c 'echo "MMPROJ_PATH=$MMPROJ_PATH"'` must be non-empty, and
   both GGUFs must exist under `$AI_MODELS_PATH/vlm/`.
4. Check VRAM availability and review the llama.cpp logs for memory allocation errors.

**A run of events with `verification_failed` and a NULL risk score is the signature of the VLM
being unreachable or blind** — not of an empty camera. It is also the only strong degradation
signal the dashboard has: a specialist leg that never loaded degrades into prompt text and does
not raise it.

### High Latency Detected

**Detection Latency > 500ms:**

- GPU may be under thermal throttling
- Check for other GPU workloads
- Verify CUDA is being used (not CPU fallback)

**Analysis Latency > 30s:**

- LLM context may be too large
- Consider reducing batch size
- Check if model is fully loaded in VRAM

**Queue Backlogs:**

- Processing cannot keep up with incoming images
- Consider scaling camera upload frequency
- Check for downstream service bottlenecks

### Dead Letter Queue Items Appearing

Items in the DLQ indicate failed processing jobs. To investigate:

1. Check the DLQ Monitor in Settings or use the API
2. Review the error messages for each failed job (includes error type, stack trace, HTTP status)
3. Common causes:
   - Temporary service unavailability
   - Malformed image files
   - LLM response parsing failures
   - Network timeouts

**DLQ API Endpoints:**

View DLQ statistics:

```bash
curl http://localhost:8000/api/dlq/stats
```

List jobs in a specific DLQ:

```bash
# Detection queue DLQ
curl "http://localhost:8000/api/dlq/jobs/dlq:detection_queue?start=0&limit=10"

# Analysis queue DLQ
curl "http://localhost:8000/api/dlq/jobs/dlq:analysis_queue?start=0&limit=10"
```

Requeue all jobs from a DLQ back to processing (requires API key if authentication enabled):

```bash
# Requeue detection queue DLQ items
curl -X POST http://localhost:8000/api/dlq/requeue-all/dlq:detection_queue

# Requeue analysis queue DLQ items
curl -X POST http://localhost:8000/api/dlq/requeue-all/dlq:analysis_queue
```

Clear a DLQ (permanently removes all jobs):

```bash
curl -X DELETE http://localhost:8000/api/dlq/dlq:detection_queue
```

### Metrics Not Updating

1. Verify backend is healthy: `curl http://localhost:8000/api/system/health`
2. Check Prometheus metrics endpoint: `curl http://localhost:8000/api/metrics`
3. Verify Redis is connected (used for queue depth metrics)
4. Try manual refresh using the "Refresh" button

### Model Zoo Troubleshooting

#### Model Showing "Error" Status

**Symptoms:** Model card shows red dot and "Error" label.

**Possible causes:**

- Model file is missing or corrupted
- Insufficient GPU memory
- Model incompatible with current GPU

**What to do:**

1. Check the System page for GPU memory status
2. Note the model name and check system logs
3. Restart the AI service if multiple models show errors

#### Model Never Loads

**Symptoms:** Model stays "Unloaded" even when its function should trigger.

**Possible causes:**

- No detections that require this model (e.g., no license plates seen)
- Model is disabled in configuration
- Queue is backed up with other processing

**What to do:**

1. Check if the model is in the "Disabled Models" section
2. Wait for normal detection activity
3. Check the Pipeline Health panel for queue issues

#### High Latency on a Model

**Symptoms:** Latency chart shows consistently high times (P95 above 500ms for detection models).

**Possible causes:**

- GPU under heavy load
- Model being loaded/unloaded frequently
- Large number of objects in images

**What to do:**

1. Check GPU utilization on the System page
2. Look for patterns in the latency chart
3. Normal during high-activity periods

#### "No Data Available" for Model Latency

**Symptoms:** Latency chart shows "No data available for [model name]"

**This is normal when:**

- The model has not been used in the last hour
- The model is disabled
- No detections have triggered this model type

**What to do:**
Nothing - this is informational. Data appears when the model is used.

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Pipeline current state**: [AI pipeline: current state](../architecture/ai-pipeline-current-state.md) — the measured, hop-by-hop description of what runs today
- **YOLO26 Integration**: Ultralytics YOLO26 served by Triton inside `ai-gateway`
- **VLM risk analysis**: llama.cpp serving a vision-language GGUF + multimodal projector in `ai-vlm`
- **Batch Aggregation**: Time-window based grouping of related detections
- **Specialist lookups**: `backend/services/vlm_specialists.py` — the in-process faces / plates /
  person_reid legs whose results are written into the VLM prompt

### Data Flow

```
Camera FTP Upload
        |
        v
FileWatcher (inotify/FSEvents)
        |
        v
detections:stream (Redis Streams)
        |
        v
YOLO26 via ai-gateway (:8090, /yolo26)
        |
        v
BatchAggregator  (closes on 90s window | 30s idle | 500 detections)
        |
        v
analysis:stream (Redis Streams)
        |
        v
VlmAnalyzer
   |-- select_key_frames (1..4 stills)
   |-- collect_specialist_outputs (faces / plates / person_reid, in-process)
   |-- POST ai-vlm:8098/v1/chat/completions (llama.cpp + mmproj)
   `-- apply_verdict_invariants
        |
        v
Event + EventVerification written, then WebSocket broadcast (best-effort)
```

### API Endpoints

| Endpoint                       | Description                             |
| ------------------------------ | --------------------------------------- |
| `/api/metrics`                 | Prometheus metrics in exposition format |
| `/api/system/health`           | Overall system and AI service health    |
| `/api/system/telemetry`        | Queue depths and basic stats            |
| `/api/system/pipeline-latency` | Detailed pipeline latency percentiles   |
| `/api/detections/stats`        | Detection class distribution            |
| `/api/events/stats`            | Risk level distribution                 |
| `/api/dlq/stats`               | Dead letter queue counts                |

### Related Code

**AI Performance Page (Grafana Embed):**

| Component           | File Path                                          |
| ------------------- | -------------------------------------------------- |
| AI Performance Page | `frontend/src/components/ai/AIPerformancePage.tsx` |
| Config API Service  | `frontend/src/services/api.ts` (fetchConfig)       |

**Standalone AI Metrics Components** (available for use elsewhere, not currently used on AI Performance page):

| Component             | File Path                                            | Purpose                                                 |
| --------------------- | ---------------------------------------------------- | ------------------------------------------------------- |
| AI Metrics Hook       | `frontend/src/hooks/useAIMetrics.ts`                 | Fetches and combines AI metrics from multiple endpoints |
| Metrics Parser        | `frontend/src/services/metricsParser.ts`             | Parses Prometheus metrics format                        |
| Model Status Cards    | `frontend/src/components/ai/ModelStatusCards.tsx`    | Detector and VLM serve status badges                    |
| Latency Panel         | `frontend/src/components/ai/LatencyPanel.tsx`        | Latency histograms with percentiles                     |
| Pipeline Health Panel | `frontend/src/components/ai/PipelineHealthPanel.tsx` | Queue depths and error counts                           |
| Insights Charts       | `frontend/src/components/ai/InsightsCharts.tsx`      | Detection and risk distribution charts                  |

**Backend Services:**

| Component          | File Path                              |
| ------------------ | -------------------------------------- |
| Backend Metrics    | `backend/core/metrics.py`              |
| System Routes      | `backend/api/routes/system.py`         |
| DLQ Routes         | `backend/api/routes/dlq.py`            |
| Detector Client    | `backend/services/detector_client.py`  |
| VLM Analyzer       | `backend/services/vlm_analyzer.py`     |
| VLM Client         | `backend/services/vlm_client.py`       |
| Specialist Lookups | `backend/services/vlm_specialists.py`  |
| Batch Aggregator   | `backend/services/batch_aggregator.py` |

**Note:** The standalone AI metrics components are exported from `frontend/src/components/ai/index.ts` and can be used on other pages that need to display AI metrics directly (without Grafana). The AI Performance page itself renders only `ModelZooSection` plus the Grafana iframe.

### GPU Requirements

| Service             | Model                                               | VRAM             | Container / Port                                       | Serve shape                                                                  |
| ------------------- | --------------------------------------------------- | ---------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| YOLO26 (via Triton) | Ultralytics YOLO26 (ONNX FP32 CUDA)                 | model-dependent  | `ai-gateway` :8090 (`/yolo26`)                         | Triton instance group; `/enrich-lt` adds `/threat-detect` + `/person-reid`   |
| VLM (llama.cpp)     | GGUF weight + mmproj projector (identity is config) | weight-dependent | `ai-vlm` :8098 (default compose set, `127.0.0.1` only) | `VLM_CTX_SIZE=32768` split across `VLM_PARALLEL=2` slots → 16384 tokens/slot |

The VLM weights and projector are host-mounted from `$AI_MODELS_PATH/vlm/` and are **not**
fetched by `ai/download_models.sh` — an operator places both files. Without the projector the
serve is text-only and every analysis degrades silently while `/health` keeps answering 200.

`BACKEND_MODEL_PRELOAD` (ships `false`) is a separate residency question from the two AI
services above: it decides whether the face and re-ID lookup legs are resident in the **backend**
process at boot. `setup.py` auto-sets it only when it detects 24 GB or more of VRAM.
