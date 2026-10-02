# Video Analytics Guide

Comprehensive guide to the AI-powered video analytics features in Home Security Intelligence.

## Overview

Home Security Intelligence runs one AI pipeline: a generalist vision-language
model reasons over what the camera saw, backed by a lookup lane for the
questions a generalist can't be trusted to answer precisely — who this person
is, what the plate reads, which stored person-vector matches a registration.
The VLM describes the scene in one pass; no per-attribute model runs beside it
to re-derive what it already said (ledger ruling D5: model identity is config).

### Key Capabilities

| Feature                 | Description                                   | Serves it                                  |
| ----------------------- | --------------------------------------------- | ------------------------------------------ |
| **Object Detection**    | Detect people, vehicles, animals, and objects | YOLO26 (gateway `/yolo26`)                 |
| **Scene Understanding** | Describe and assess each event visually       | `ai-vlm` engine (identity is config)       |
| **Face Identification** | Match faces against enrolled known persons    | in-process face leg (backend)              |
| **License Plates**      | Read plates and match registered vehicles     | in-process plate leg (backend)             |
| **Person Re-ID**        | Person vectors matched against registrations  | in-process re-ID leg (backend)             |
| **Weapon Detection**    | Opt-in Triton model behind `/enrich-lt`       | gateway `threat` (`GATEWAY_ENABLE_THREAT`) |
| **Anomaly Detection**   | Compare against learned per-zone baselines    | backend statistical baselines              |
| **Risk Assessment**     | VLM-based contextual risk analysis            | `ai-vlm` engine                            |

---

## Architecture

### Detection Pipeline

```
Camera Upload -> File Watcher -> Object Detection -> Batch Aggregator -> VLM Reasoning -> Event
     (1)            (2)              (3)                  (4)                (5)         (6)
```

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart LR
    subgraph Input["1. Image Input"]
        CAM[Camera]
        FTP[FTP Server<br/>/export/foscam/]
        FW[FileWatcher<br/>inotify + debounce]
    end

    subgraph Detection["2. Object Detection"]
        DQ[(detection_queue)]
        YOLO[YOLO26<br/>ai-gateway /yolo26<br/>port 8090]
    end

    subgraph Batching["3. Batch Aggregation"]
        BA[BatchAggregator<br/>90s window / 30s idle]
        AQ[(analysis_queue)]
    end

    subgraph Lookups["4. Specialist Lookups (in-process, backend)"]
        SP[collect_specialist_outputs<br/>faces + plates + person_reid<br/>gallery match against Postgres]
    end

    subgraph Analysis["5. Risk Reasoning"]
        VLM[ai-vlm llama.cpp engine<br/>POST /v1/chat/completions<br/>port AI_VLM_PORT default 8098<br/>model identity is config]
    end

    subgraph Output["6. Event Output"]
        DB[(PostgreSQL<br/>Event storage)]
        WS[WebSocket<br/>Real-time broadcast]
        UI[React Dashboard]
    end

    CAM -->|FTP upload| FTP
    FTP -->|inotify| FW
    FW -->|queue job| DQ
    DQ --> YOLO
    YOLO -->|detections| BA
    BA -->|batch ready| AQ
    AQ --> SP
    SP -->|detections + lookup lines| VLM
    VLM -->|verdict| DB
    VLM -->|event| WS
    WS --> UI
```

1. **Camera Upload**: Cameras upload images via FTP to `/export/foscam/{camera_name}/`
2. **File Watcher**: Monitors directories for new images with deduplication
3. **Object Detection**: YOLO26 identifies objects and their bounding boxes
4. **Batch Aggregator**: Groups detections into 90-second time windows
5. **Specialist Lookups**: `backend/services/vlm_specialists.py` runs the three
   event-path legs — `faces`, `plates`, `person_reid` — in the backend process
   against their own loaders, then matches each result against the database
   gallery
6. **Risk Reasoning**: The `ai-vlm` engine describes the scene and returns the
   verdict (risk score + summary)
7. **Event Creation**: Security events are created and broadcast via WebSocket

### Where the Models Run

Two GPU services (see `docker-compose.prod.yml`):

| Service                                                       | What runs                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai-gateway` (port 8090)                                      | FastAPI front for a Triton Inference Server in the same container. Two routers: `/yolo26` (`/detect`, `/detect/batch`, `/segment`, `/health`) and `/enrich-lt` (`/threat-detect`, `/person-reid`, `/health`). `GATEWAY_MODEL_SET` resolves only `vlm` — any other value hard-raises. Triton loads its models at container start with `--model-control-mode=none` (resident, never unloaded at runtime); the compose healthcheck allows three minutes. |
| `ai-vlm` (`AI_VLM_PORT`, default 8098; compose profile `vlm`) | llama.cpp serving the configured GGUF pair (`VLM_MODEL_PATH` + `VLM_MMPROJ_PATH`) at `/v1/chat/completions`. The backend soft-depends only: with the profile off the stack boots and events degrade (no verdicts) instead of failing.                                                                                                                                                                                                                 |

`ai-gateway` is the only vision service, and `ai-vlm` is the only LLM service.

The gateway's Triton repository holds exactly `yolo26` and `reid`
(`VLM_MODEL_BASE` in `ai/gateway/residency.py`), plus `threat` when
`GATEWAY_ENABLE_THREAT=true` — which ships `false` in `.env.example`, so a
default host brings up two models. `/enrich-lt` is a live, health-checked
router (`model_management.py` reads its `/health` when reporting model status),
but the per-event lookups run in the backend process, not over HTTP.

### Models Used Per Analysis Step

Per-model VRAM from `models.yml` (the live catalogue):

| Model                    | Purpose                       | VRAM (MB)           | Where it runs      |
| ------------------------ | ----------------------------- | ------------------- | ------------------ |
| yolo26                   | Object detection              | 0 (Triton-resident) | gateway `/yolo26`  |
| osnet-ain-x1-0           | Person re-identification      | 100                 | gateway `reid`     |
| threat-detection-yolov8n | Weapon detection (opt-in)     | 300                 | gateway `threat`   |
| face-detector-scrfd      | Face detection (CPU)          | 0 (CPU)             | backend in-process |
| face-recognizer          | Face matching (CPU)           | 0 (CPU)             | backend in-process |
| yolo11-face              | Face detection on crops       | 200                 | backend model zoo  |
| yolo11-license-plate     | Plate detection               | 300                 | backend model zoo  |
| fast-alpr                | Plate read (end-to-end)       | 28                  | backend model zoo  |
| paddleocr                | Plate read (fallback OCR)     | 100                 | backend model zoo  |
| yolo26-general           | Alternate detector (disabled) | 400                 | backend model zoo  |

The three event-path legs load their own weights in-process
(`face_recognizer_loader.py`, `fast_alpr_loader.py`, `osnet_loader.py`) and are
gated by `BACKEND_MODEL_PRELOAD` (default `false` in `.env.example`): on a host
that leaves it off the legs report `unavailable` and the event still ships with
a VLM verdict. A leg that cannot run is counted by
`hsi_specialist_unavailable_total` — the only degradation signal.

---

## Object Detection

### YOLO26 Detection

The primary object detector uses YOLO26 for fast, accurate detection. Run the
requests against the AI gateway, not a standalone detector container:

```bash
# Check detector health
curl http://localhost:8090/yolo26/health

# Single-image detection (multipart upload)
curl -F "file=@frame.jpg" http://localhost:8090/yolo26/detect

# Batch detection
curl -F "files=@a.jpg" -F "files=@b.jpg" http://localhost:8090/yolo26/detect/batch
```

**Detected Object Classes:**

- **People**: person
- **Vehicles**: car, truck, bus, motorcycle, bicycle
- **Animals**: dog, cat, bird
- **Objects**: backpack, handbag, suitcase, umbrella
- And 80+ COCO classes

**Detection Response:**

```json
{
  "detections": [
    {
      "class": "person",
      "confidence": 0.9214,
      "bbox": { "x": 120, "y": 80, "width": 160, "height": 370 }
    }
  ],
  "image_width": 1920,
  "image_height": 1080,
  "inference_time_ms": 5.76
}
```

### Detection Filtering

Detections are filtered by:

- **Confidence threshold**: Minimum confidence to keep a detection. `.env.example` ships `DETECTION_CONFIDENCE_THRESHOLD=0.5`; classes listed in `DETECTION_CLASS_THRESHOLDS` use their own value instead. The commented example in `.env.example` reads `{"person": 0.45, "car": 0.70, "truck": 0.70, "bus": 0.70, "motorcycle": 0.65, "bicycle": 0.65, "dog": 0.55, "cat": 0.55, "bird": 0.55, "backpack": 0.60, "handbag": 0.60, "suitcase": 0.60}`
- **Object classes**: Filter to security-relevant objects
- **Zone filtering**: Only process detections in defined zones

---

## Scene Understanding

### VLM Captioning and Reasoning

The analyzer (`backend/services/vlm_analyzer.py`, built only through
`build_pipeline_analyzer`) builds one prompt per batch — the key frames plus
their detections and the specialist lookup lines — and the `ai-vlm` engine
answers with the scene description and the risk verdict in one pass. Model
identity is operator config (`VLM_MODEL_PATH` / `VLM_MMPROJ_PATH`); this guide
names no model.

Inspect the prompt and response a finished event produced:

```bash
curl http://localhost:8000/api/llm-reasoning/events/{event_id}
```

---

## Anomaly Detection

### Zone Baseline Comparison

The system learns normal activity patterns per zone and flags deviations from
them (`backend/services/zone_anomaly_service.py`). Baselines are statistical —
per-zone metric distributions, not embeddings:

1. Detections accumulate into per-zone baselines
2. Each new detection is scored against the baseline in standard deviations
3. A deviation past the threshold raises an anomaly (severity: >= 3.0 std is
   WARNING, >= 4.0 std is CRITICAL)

**Baseline Metrics:**

| Metric                  | Description                            |
| ----------------------- | -------------------------------------- |
| `hourly_pattern`        | Expected activity by hour (24 buckets) |
| `day_of_week_pattern`   | Expected activity by day (7 buckets)   |
| `typical_dwell_time`    | Average time objects stay in view      |
| `typical_crossing_rate` | Expected zone crossings per hour       |

**Anomaly Checks** (all three compare in standard deviations against the
baseline; default trigger is 2.0 std):

- **Unusual time**: detection at an hour the zone is normally quiet
- **Unusual frequency**: a spike or drop in recent detections for the zone
- **Unusual dwell**: an object in view far longer than the zone typical

New people and vehicles are handled separately, by household matching and face
recognition — see [Face Recognition Guide](face-recognition.md).

### Baseline Visualization

The dashboard provides four visualization components for understanding learned activity patterns:

#### 24-Hour Activity Pattern (HourlyPatternChart)

A line chart showing average detections for each hour of the day (0-23):

- **Green line**: Average detections per hour
- **Shaded band**: Confidence interval (+/- 1 standard deviation)
- **Orange dot**: Peak activity hour
- **Point opacity**: Data quality indicator (more samples = more opaque)

**Interpreting the chart:**

- Full opacity points have 20+ samples (high confidence)
- Faded points have fewer samples (still learning)
- Hover over points to see exact values and sample counts

#### Weekly Activity Pattern (DailyPatternChart)

A bar chart showing activity levels for each day of the week:

- **Bar height**: Average detections for that day
- **Bar color intensity**: Activity level relative to the busiest day
- **Orange dot on bar**: Peak hour for that day
- **Weekend bars**: Highlighted in blue

**Interpreting the chart:**

- Hover over bars to see average detections, peak hour, and total samples
- "Busiest day" and "Quietest day" badges identify patterns

#### Current Deviation Status (BaselineDeviationCard)

A color-coded card showing how current activity compares to baseline:

| Color  | Interpretation           | Deviation Range      |
| ------ | ------------------------ | -------------------- |
| Blue   | Far below / Below normal | < -1.0 std dev       |
| Green  | Normal                   | -1.0 to +1.0 std dev |
| Yellow | Slightly above normal    | +1.0 to +2.0 std dev |
| Orange | Above normal             | +2.0 to +3.0 std dev |
| Red    | Far above normal         | >= +3.0 std dev      |

The "far below" and "below normal" bands split again at -2.0 std; both render
in blue.

The card displays:

- **Deviation score**: Number of standard deviations from baseline
- **Contributing factors**: What's causing the deviation (e.g., "high_person_count")
- **Last updated**: When the deviation was calculated

#### Object Baseline Chart (ObjectBaselineChart)

Per-class detection statistics showing frequency patterns by object type:

- **Grouped bars per class**: Average hourly rate, peak hour, total detections
- **Color-coded by class**: Person (blue), Vehicle (green), Animal (orange), etc.
- **Sort options**: By frequency, total detections, peak hour, or alphabetically

### Baseline Tuning

For per-camera baseline configuration, see the **Baseline Tuning Panel** in the camera settings:

- **Sensitivity threshold**: Adjusts how many standard deviations trigger an anomaly (0.5-5.0)
- **Minimum samples**: Sets how many data points are needed before detection is reliable
- **Reset baseline**: Clears all learned data to start fresh

API endpoints for programmatic control are documented in [Baseline Configuration API](../api/analytics-endpoints.md#baseline-configuration-api).

---

## Person Analysis

### Face Identification

The face leg (`vlm_specialists._collect_face_texts`) runs SCRFD-10G-KPS for
detection and ArcFace `w600k_r50` for the 512-d comparison vector, both
CPU-onnxruntime in the backend process (`backend/services/face_recognizer_loader.py`).
Each candidate is graded with a four-outcome vocabulary — `match`, `unknown`,
`not_identifiable`, `unavailable` — and rendered into one prompt line per
frame. Enrolment, gallery management and thresholds are in
[Face Recognition Guide](face-recognition.md).

### Person Re-Identification

The re-ID leg extracts a normalized 512-dimensional OSNet-AIN x1.0 vector per
person crop in-process (`backend/services/osnet_loader.py`) and matches it
against the stored `person_embeddings` gallery. There is exactly one person-
vector space in this system, and it is OSNet's.

Matching and thresholds live in the backend, not the gateway:

| Value                                         | Where                    | Default                          |
| --------------------------------------------- | ------------------------ | -------------------------------- |
| `reid_similarity_threshold`                   | `backend/core/config.py` | `0.7`                            |
| Face match threshold (`face_match_threshold`) | `backend/core/config.py` | `0.68`                           |
| Embedding dimension                           | `osnet_loader.py`        | 512                              |
| Embedding cache TTL                           | `reid_service.py`        | 86400s (`EMBEDDING_TTL_SECONDS`) |

**Use Cases:**

- Track individuals across multiple cameras
- Identify repeat visitors
- Link detections to known household members

---

## Vehicle Analysis

### License Plate Detection

The plate leg prefers FastALPR (end-to-end detection plus OCR,
`backend/services/fast_alpr_loader.py`). When FastALPR is unavailable it falls
back to yolo11-license-plate detection followed by PaddleOCR. Either path
produces plate text plus a box, which the leg then matches against registered
household vehicles:

```json
{
  "license_plates": [
    {
      "text": "ABC 1234",
      "ocr_confidence": 0.88,
      "bbox": { "x": 100, "y": 200, "width": 100, "height": 40 }
    }
  ]
}
```

---

## Threat Detection

### Weapon Detection (opt-in)

The Triton model `threat` serves
`POST http://localhost:8090/enrich-lt/threat-detect`:

```json
{
  "threats_detected": [
    {
      "class": "knife",
      "confidence": 0.85,
      "bbox": { "x": 150, "y": 200, "width": 30, "height": 80 }
    }
  ],
  "is_threat": true,
  "max_confidence": 0.85,
  "inference_time_ms": 9.1
}
```

`GATEWAY_ENABLE_THREAT` (`false` in `.env.example`) decides whether Triton
loads the directory at all. Even when it is loaded, the VLM prompt never
learns about threat scoring: the `threat` key is absent from
`SPECIALIST_KEYS` and `collect_threat_text()` returns an explicit
`not_included` line, per the F12 owner ruling. The route is live and pinned by
the `ai_contract` tier; a caller has to ask for it.

A detection that does arrive labelled with a `threat_type` takes the batch
aggregator's fast path (`should_bypass_batch`), skipping the 90-second window
and creating an alert through `ThreatMonitorService`. The backend maps threat
types to alert severity in `backend/services/threat_monitor_service.py`
(`get_threat_severity`: firearms — gun/pistol/rifle/handgun — are CRITICAL,
bladed weapons HIGH, and so on; the category enum lives in
`backend/services/threat_categories.py`).

---

## Risk Assessment

### VLM Analysis

Risk reasoning runs on the `ai-vlm` llama.cpp engine — compose profile `vlm`,
host port `AI_VLM_PORT` (default 8098); model identity is config
(`VLM_MODEL_PATH`/`VLM_MMPROJ_PATH`, D5). Inspect a finished event's prompt and
response through the backend at `/api/llm-reasoning/events/{event_id}`.

**Input Context:**

- The batch's key frames (1-4 stills, `key_frame_selector.py`) and their detections
- The specialist lookup lines (`faces`, `plates`, `person_reid`)
- Zone information and types
- Time of day and baseline context

**Output:**

```json
{
  "risk_score": 45,
  "risk_level": "medium",
  "summary": "Unknown person approached front door at unusual hour",
  "reasoning": "Activity at 2:14 AM when no family members are expected...",
  "recommended_actions": ["Review footage", "Check if visitor expected"]
}
```

**Risk Score Mapping:**

| Score  | Level    | Color  | Action                 |
| ------ | -------- | ------ | ---------------------- |
| 0-29   | Low      | Green  | Informational only     |
| 30-59  | Medium   | Yellow | Review when convenient |
| 60-84  | High     | Orange | Prompt review          |
| 85-100 | Critical | Red    | Immediate attention    |

---

## API Reference

### Analytics Endpoints

| Endpoint                                 | Method | Description                       |
| ---------------------------------------- | ------ | --------------------------------- |
| `/api/analytics/detection-trends`        | GET    | Daily detection counts            |
| `/api/analytics/risk-history`            | GET    | Risk level distribution over time |
| `/api/analytics/camera-uptime`           | GET    | Uptime percentage per camera      |
| `/api/analytics/object-distribution`     | GET    | Detection counts by object type   |
| `/api/analytics/risk-score-distribution` | GET    | Risk score histogram              |
| `/api/analytics/risk-score-trends`       | GET    | Average risk score over time      |

### Query Parameters

All analytics endpoints accept `start_date` and `end_date`, both required, both
ISO format (YYYY-MM-DD), both inclusive. There is no `camera_id` filter —
analytics aggregate across all cameras (`camera-uptime` reports per camera).

### Example Request

```bash
curl "http://localhost:8000/api/analytics/detection-trends?start_date=2026-01-01&end_date=2026-01-26"
```

### Response Format

```json
{
  "data_points": [
    { "date": "2026-01-01", "count": 156 },
    { "date": "2026-01-02", "count": 203 }
  ],
  "total_detections": 4521,
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

---

## Model Status API

Model status goes through the backend under `/api/system/models`
(`backend/api/routes/model_management.py`). Do not call gateway routers
directly for status.

```bash
# Every model in the registry, with runtime state
curl http://localhost:8000/api/system/models

# One model
curl http://localhost:8000/api/system/models/yolo11-license-plate/status

# Combined VRAM totals
curl http://localhost:8000/api/system/models/vram-summary
```

There is no runtime load/unload: gateway models are Triton-resident
(`--model-control-mode=none`) and the gateway exposes no load API, so `POST
/{model_name}/load`, `/unload` and `/reload` answer **501** with an
explanation. Backend-process models load lazily on first use, gated by
`BACKEND_MODEL_PRELOAD`.

`GET /api/system/models` returns one entry per registry model. The `service`
label is a lane name — `ai-enrichment-light` for the two models the `/enrich-lt`
router declares (`threat-detection-yolov8n`, `osnet-ain-x1-0`, per
`model_management.LIGHT_MODELS`) and `ai-gateway` for the rest — and
`service_status` carries exactly those two rows:

```json
{
  "models": [
    {
      "name": "osnet-ain-x1-0",
      "category": "embedding",
      "estimated_vram_mb": 100,
      "enabled": true,
      "service": "ai-enrichment-light",
      "gpu_id": 1,
      "runtime": {
        "loaded": true,
        "actual_vram_mb": 96,
        "last_used": "2026-09-22T10:30:00Z",
        "load_count": 5
      }
    }
  ],
  "service_status": {
    "ai-enrichment-light": "healthy",
    "ai-gateway": "healthy"
  }
}
```

`backend/api/routes/system.py` exposes a second, simpler pair: `GET
/api/system/models` for names and `GET /api/system/models/{model_name}` for one
model. `model_management.py` is registered first, so it answers the bare
`/api/system/models` request.

---

## Best Practices

### Optimizing Detection Quality

1. **Camera Placement**: Ensure cameras have clear views of entry points
2. **Lighting**: Good lighting improves detection accuracy
3. **Resolution**: Higher resolution enables better detail extraction
4. **Zone Configuration**: Focus analysis on important areas

### Managing VRAM

1. **VLM sizing**: `VLM_GPU_LAYERS=auto` (default) fits the engine to the card;
   set an explicit layer count to reserve headroom for the gateway
2. **Specialist residency**: `BACKEND_MODEL_PRELOAD=true` brings the face and
   re-ID legs up loaded on a host with the VRAM for them (~24GB); left `false`
   they report `unavailable` instead of loading mid-event
3. **Monitoring**: Watch VRAM utilization via `/api/system/models/vram-summary`

### Reducing False Positives

1. **Zone Configuration**: Exclude high-motion areas (trees, roads)
2. **Household Registration**: Add known people and vehicles
3. **Baseline Learning**: Allow system to learn normal patterns
4. **Feedback**: Use the feedback system to improve calibration

---

## Troubleshooting

### No Detections

1. Check camera is uploading to correct directory
2. Verify file watcher is running: `curl http://localhost:8000/api/system/pipeline`
3. Check the AI gateway: `curl http://localhost:8090/yolo26/health`
4. Review detection queue depth in system telemetry

### Slow Analysis

1. Check GPU utilization: `curl http://localhost:8000/api/system/gpu`
2. Review pipeline latency: `curl http://localhost:8000/api/system/pipeline-latency`
3. Consider adjusting batch window settings
4. Check for VRAM pressure in model status

### Inaccurate Risk Scores

1. Review recent events for patterns
2. Check zone configuration is accurate
3. Register household members to reduce false positives
4. Allow baseline learning time (7+ days recommended)

---

## Related Documentation

- [Zone Configuration Guide](zone-configuration.md) - Configure detection zones
- [Face Recognition Guide](face-recognition.md) - Person identification
- [Analytics Endpoints](../api/analytics-endpoints.md) - API reference
- [AI Performance](../ui/ai-performance.md) - Model monitoring
