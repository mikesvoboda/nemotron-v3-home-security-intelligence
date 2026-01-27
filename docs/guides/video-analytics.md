# Video Analytics Guide

Comprehensive guide to the AI-powered video analytics features in Home Security Intelligence.

## Overview

Home Security Intelligence provides a multi-model AI pipeline that transforms raw camera footage into actionable security insights. The video analytics system processes images through multiple specialized models to detect, classify, track, and assess security risks in real-time.

### Key Capabilities

| Feature                 | Description                                     | Models Used              |
| ----------------------- | ----------------------------------------------- | ------------------------ |
| **Object Detection**    | Detect people, vehicles, animals, and objects   | YOLO26                   |
| **Scene Understanding** | Generate captions and descriptions              | Florence-2               |
| **Anomaly Detection**   | Compare against learned baselines               | CLIP ViT-L/14            |
| **Threat Detection**    | Identify weapons and dangerous items            | Threat-Detection-YOLOv8n |
| **Person Analysis**     | Pose, demographics, clothing, re-identification | Multiple models          |
| **Vehicle Analysis**    | Vehicle type, damage, license plates            | Multiple models          |
| **Risk Assessment**     | LLM-based contextual risk analysis              | Nemotron-3-Nano-30B      |

---

## Architecture

### Detection Pipeline

```
Camera Upload -> File Watcher -> Object Detection -> Batch Aggregator -> Enrichment -> Risk Analysis -> Event
     (1)            (2)              (3)                  (4)              (5)            (6)          (7)
```

1. **Camera Upload**: Cameras upload images via FTP to `/export/foscam/{camera_name}/`
2. **File Watcher**: Monitors directories for new images with deduplication
3. **Object Detection**: YOLO26 identifies objects and their bounding boxes
4. **Batch Aggregator**: Groups detections into 90-second time windows
5. **Enrichment**: Model Zoo extracts additional context (clothing, pose, etc.)
6. **Risk Analysis**: Nemotron LLM evaluates the complete context
7. **Event Creation**: Security events are created and broadcast via WebSocket

### Always-Loaded Models (~2.65GB VRAM)

These models are permanently loaded for real-time processing:

| Model                | Purpose                       | VRAM   | Port |
| -------------------- | ----------------------------- | ------ | ---- |
| **YOLO26**           | Primary object detection      | ~650MB | 8091 |
| **Florence-2-large** | Scene understanding, captions | ~1.2GB | 8092 |
| **CLIP ViT-L/14**    | Anomaly detection baseline    | ~800MB | 8093 |

### On-Demand Models (~6.8GB Budget)

Loaded when needed and evicted using LRU with priority ordering:

| Model              | Purpose                  | VRAM   | Priority |
| ------------------ | ------------------------ | ------ | -------- |
| Threat Detector    | Weapon detection         | ~400MB | CRITICAL |
| Pose Estimator     | Body posture analysis    | ~300MB | HIGH     |
| Demographics       | Age/gender estimation    | ~500MB | HIGH     |
| FashionCLIP        | Clothing analysis        | ~800MB | HIGH     |
| OSNet Re-ID        | Person re-identification | ~100MB | MEDIUM   |
| Vehicle Classifier | Vehicle type             | ~1.5GB | MEDIUM   |
| Pet Classifier     | Cat/dog detection        | ~200MB | MEDIUM   |
| Depth Anything v2  | Distance estimation      | ~150MB | LOW      |
| X-CLIP             | Action recognition       | ~1.5GB | LOW      |

---

## Object Detection

### YOLO26 Detection

The primary object detector uses YOLO26 for fast, accurate detection:

```bash
# Check detector health
curl http://localhost:8091/health

# Detection endpoint (internal use)
POST http://localhost:8091/detect
Content-Type: multipart/form-data
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
      "confidence": 0.92,
      "bbox": [120, 80, 280, 450],
      "center": [200, 265]
    }
  ],
  "inference_time_ms": 5.76
}
```

### Detection Filtering

Detections are filtered by:

- **Confidence threshold**: Configurable minimum confidence (default: 0.5)
- **Object classes**: Filter to security-relevant objects
- **Zone filtering**: Only process detections in defined zones

---

## Scene Understanding

### Florence-2 Captioning

Florence-2 provides rich scene descriptions:

```bash
# Health check
curl http://localhost:8092/health

# Caption endpoint
POST http://localhost:8092/caption
{
  "image": "<base64>",
  "task": "detailed_caption"
}
```

**Available Tasks:**

| Task                    | Description                    |
| ----------------------- | ------------------------------ |
| `caption`               | Brief scene description        |
| `detailed_caption`      | Comprehensive scene analysis   |
| `more_detailed_caption` | Extended detailed description  |
| `ocr`                   | Text detection and recognition |
| `dense_region_caption`  | Per-region descriptions        |
| `object_detection`      | Bounding box detection         |

**Response Example:**

```json
{
  "caption": "A person in a blue jacket approaches the front door carrying a package",
  "inference_time_ms": 145.2
}
```

---

## Anomaly Detection

### CLIP Baseline Comparison

The system learns normal activity patterns and detects anomalies:

**How It Works:**

1. CLIP generates embeddings for each scene
2. Embeddings are compared against historical baselines
3. Significant deviations trigger anomaly flags

**Baseline Metrics:**

| Metric                  | Description                            |
| ----------------------- | -------------------------------------- |
| `hourly_pattern`        | Expected activity by hour (24 buckets) |
| `day_of_week_pattern`   | Expected activity by day (7 buckets)   |
| `typical_dwell_time`    | Average time objects stay in view      |
| `typical_crossing_rate` | Expected zone crossings per hour       |

**Anomaly Types:**

- **Unusual time**: Activity outside normal hours
- **Unusual frequency**: Detection spike or drop (3+ std deviations)
- **Unusual dwell**: Object lingering 2x longer than typical
- **Unusual entity**: First-time visitor to sensitive zone

---

## Person Analysis

### Pose Estimation

YOLOv8n-pose detects 17 COCO keypoints:

```json
{
  "keypoints": [
    { "name": "nose", "x": 0.45, "y": 0.12, "confidence": 0.95 },
    { "name": "left_shoulder", "x": 0.42, "y": 0.25, "confidence": 0.92 }
  ],
  "posture": "standing",
  "is_suspicious": false
}
```

**Posture Classifications:**

| Posture       | Description                      |
| ------------- | -------------------------------- |
| `standing`    | Upright position                 |
| `walking`     | Moving, upright                  |
| `running`     | Fast movement                    |
| `crouching`   | Low position (suspicious)        |
| `lying_down`  | Horizontal position              |
| `reaching_up` | Arms raised (potential climbing) |

**Suspicious Poses:**

- `crouching` - Potential hiding/break-in behavior
- `crawling` - Unusual movement pattern
- `hiding` - Concealment attempt
- `reaching_up` - Potential climbing/entry

### Demographics

ViT-based age and gender estimation:

```json
{
  "age_range": "21-35",
  "gender": "male",
  "confidence": 0.87
}
```

**Age Ranges:** 0-10, 11-20, 21-35, 36-50, 51-65, 65+

### Clothing Analysis

FashionCLIP zero-shot clothing classification:

```json
{
  "type": "casual",
  "colors": ["blue", "black"],
  "is_suspicious": false,
  "description": "Blue jacket, black pants"
}
```

### Person Re-Identification

OSNet generates 512-dimensional embeddings for tracking across cameras:

```json
{
  "embedding": [0.12, -0.34, ...],
  "embedding_hash": "abc123...",
  "match_threshold": 0.7
}
```

**Use Cases:**

- Track individuals across multiple cameras
- Identify repeat visitors
- Link detections to known household members

---

## Vehicle Analysis

### Vehicle Classification

ViT-based vehicle type classification:

```json
{
  "vehicle_type": "car",
  "display_name": "Sedan",
  "confidence": 0.91
}
```

**Vehicle Classes:**

- articulated_truck, bus, car, motorcycle, bicycle
- pickup_truck, single_unit_truck, work_van
- non_motorized_vehicle

### License Plate Detection

YOLO-based license plate detection with PaddleOCR:

```json
{
  "plates": [
    {
      "text": "ABC 1234",
      "confidence": 0.88,
      "bbox": [100, 200, 200, 240]
    }
  ]
}
```

---

## Threat Detection

### Weapon Detection

CRITICAL priority detection for security threats:

```json
{
  "threats": [
    {
      "threat_type": "knife",
      "confidence": 0.85,
      "bbox": [150, 200, 180, 280],
      "severity": "high"
    }
  ],
  "has_threat": true,
  "max_severity": "high"
}
```

**Threat Classes:**

| Class              | Severity |
| ------------------ | -------- |
| gun, rifle, pistol | CRITICAL |
| knife              | HIGH     |
| bat, crowbar       | MEDIUM   |

---

## Risk Assessment

### Nemotron LLM Analysis

The Nemotron-3-Nano-30B model provides contextual risk assessment:

**Input Context:**

- All detections in the batch
- Florence captions and descriptions
- Zone information and types
- Historical baseline comparison
- Household member matching
- Time of day and patterns

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

All analytics endpoints accept:

| Parameter    | Type   | Description                       |
| ------------ | ------ | --------------------------------- |
| `start_date` | Date   | Start date (ISO format, required) |
| `end_date`   | Date   | End date (ISO format, required)   |
| `camera_id`  | String | Filter by camera (optional)       |

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

### Check Model Status

```bash
# Get all model statuses
curl http://localhost:8094/models/status

# Response
{
  "vram_budget_mb": 6963.2,
  "vram_used_mb": 2500,
  "vram_utilization_percent": 35.9,
  "loaded_models": [
    {"name": "pose_estimator", "vram_mb": 300, "priority": "HIGH"}
  ]
}
```

### Preload Models

```bash
# Preload a model before use
curl -X POST "http://localhost:8094/models/preload?model_name=threat_detector"
```

---

## Best Practices

### Optimizing Detection Quality

1. **Camera Placement**: Ensure cameras have clear views of entry points
2. **Lighting**: Good lighting improves detection accuracy
3. **Resolution**: Higher resolution enables better detail extraction
4. **Zone Configuration**: Focus analysis on important areas

### Managing VRAM

1. **Priority Models**: Keep critical models (threat detection) always ready
2. **Preloading**: Preload expected models before high-activity periods
3. **Monitoring**: Watch VRAM utilization via `/models/status`

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
3. Check YOLO26 health: `curl http://localhost:8091/health`
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
