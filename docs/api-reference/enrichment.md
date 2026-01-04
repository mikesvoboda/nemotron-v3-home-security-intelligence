---
title: Enrichment API
description: REST API endpoints for accessing enrichment data from vision model analysis
source_refs:
  - backend/api/routes/detections.py
  - backend/api/routes/events.py
  - backend/api/schemas/enrichment.py
  - backend/services/enrichment_pipeline.py
---

# Enrichment API

The Enrichment API provides access to structured results from the 18+ vision models that analyze each detection during the enrichment pipeline. These endpoints expose rich contextual data beyond basic object detection.

## Overview

When the AI pipeline processes camera images, it performs two stages:

1. **Detection** (RT-DETRv2) - Identifies objects in the frame (person, car, etc.)
2. **Enrichment** (Model Zoo) - Runs specialized models on each detection to extract additional context

The enrichment pipeline produces structured data including:

- **License plates** - Detection, bounding box, and OCR text extraction
- **Faces** - Detection count and confidence scores
- **Vehicle classification** - Type, color, commercial status, and damage detection
- **Clothing analysis** - Upper/lower body descriptions, suspicious attire flags
- **Violence detection** - Binary classification with confidence score
- **Image quality** - Quality score, blur detection, quality issues
- **Pet classification** - Cat/dog identification for false positive reduction

## Endpoints Overview

| Method | Endpoint                                    | Description                                        |
| ------ | ------------------------------------------- | -------------------------------------------------- |
| GET    | `/api/detections/{detection_id}/enrichment` | Get enrichment data for a single detection         |
| GET    | `/api/events/{event_id}/enrichments`        | Get enrichment data for all detections in an event |

---

## GET /api/detections/{detection_id}/enrichment

Get structured enrichment data for a single detection.

**Source:** [`get_detection_enrichment`](../../backend/api/routes/detections.py:397)

**Parameters:**

| Name           | Type    | In   | Required | Description  |
| -------------- | ------- | ---- | -------- | ------------ |
| `detection_id` | integer | path | Yes      | Detection ID |

**Response:** `200 OK`

```json
{
  "detection_id": 12345,
  "enriched_at": "2026-01-03T10:30:00Z",
  "license_plate": {
    "detected": true,
    "confidence": 0.92,
    "text": "ABC-1234",
    "ocr_confidence": 0.88,
    "bbox": [100.0, 200.0, 300.0, 250.0]
  },
  "face": {
    "detected": true,
    "count": 1,
    "confidence": 0.88
  },
  "vehicle": {
    "type": "sedan",
    "color": null,
    "confidence": 0.91,
    "is_commercial": false,
    "damage_detected": false,
    "damage_types": []
  },
  "clothing": {
    "upper": "dark hoodie",
    "lower": "blue jeans",
    "is_suspicious": false,
    "is_service_uniform": false,
    "has_face_covered": false,
    "has_bag": true,
    "clothing_items": ["hoodie", "jeans", "backpack"]
  },
  "violence": {
    "detected": false,
    "score": 0.12,
    "confidence": 0.88
  },
  "weather": null,
  "pose": null,
  "depth": null,
  "image_quality": {
    "score": 85.0,
    "is_blurry": false,
    "is_low_quality": false,
    "quality_issues": [],
    "quality_change_detected": false
  },
  "pet": null,
  "processing_time_ms": 125.5,
  "errors": []
}
```

**Response Fields:**

| Field                | Type     | Description                                      |
| -------------------- | -------- | ------------------------------------------------ |
| `detection_id`       | integer  | Detection ID                                     |
| `enriched_at`        | datetime | Timestamp when enrichment was performed          |
| `license_plate`      | object   | License plate detection and OCR results          |
| `face`               | object   | Face detection results                           |
| `vehicle`            | object   | Vehicle classification results (nullable)        |
| `clothing`           | object   | Clothing analysis results (nullable)             |
| `violence`           | object   | Violence detection results                       |
| `weather`            | object   | Weather classification results (nullable)        |
| `pose`               | object   | Pose estimation results (nullable)               |
| `depth`              | object   | Depth estimation results (nullable)              |
| `image_quality`      | object   | Image quality assessment (nullable)              |
| `pet`                | object   | Pet classification results (nullable)            |
| `processing_time_ms` | float    | Enrichment processing time in milliseconds       |
| `errors`             | array    | Errors encountered during enrichment (sanitized) |

### License Plate Object

| Field            | Type    | Description                              |
| ---------------- | ------- | ---------------------------------------- |
| `detected`       | boolean | Whether a license plate was detected     |
| `confidence`     | float   | Detection confidence (0.0-1.0)           |
| `text`           | string  | OCR-extracted plate text (nullable)      |
| `ocr_confidence` | float   | OCR confidence score (nullable)          |
| `bbox`           | array   | Bounding box [x1, y1, x2, y2] (nullable) |

### Face Object

| Field        | Type    | Description                        |
| ------------ | ------- | ---------------------------------- |
| `detected`   | boolean | Whether faces were detected        |
| `count`      | integer | Number of faces detected           |
| `confidence` | float   | Highest face confidence (nullable) |

### Vehicle Object

| Field             | Type    | Description                            |
| ----------------- | ------- | -------------------------------------- |
| `type`            | string  | Vehicle type (sedan, suv, truck, etc.) |
| `color`           | string  | Vehicle color (nullable)               |
| `confidence`      | float   | Classification confidence              |
| `is_commercial`   | boolean | Whether vehicle is commercial/delivery |
| `damage_detected` | boolean | Whether vehicle damage was detected    |
| `damage_types`    | array   | Types of damage (cracks, dents, etc.)  |

### Clothing Object

| Field                | Type    | Description                                     |
| -------------------- | ------- | ----------------------------------------------- |
| `upper`              | string  | Upper body clothing description                 |
| `lower`              | string  | Lower body clothing description                 |
| `is_suspicious`      | boolean | Whether clothing is flagged as suspicious       |
| `is_service_uniform` | boolean | Whether wearing service uniform (delivery, etc) |
| `has_face_covered`   | boolean | Whether face is covered (hat/sunglasses/mask)   |
| `has_bag`            | boolean | Whether person is carrying a bag                |
| `clothing_items`     | array   | List of detected clothing items                 |

### Violence Object

| Field        | Type    | Description                          |
| ------------ | ------- | ------------------------------------ |
| `detected`   | boolean | Whether violence was detected        |
| `score`      | float   | Violence probability score (0.0-1.0) |
| `confidence` | float   | Model confidence (nullable)          |

### Image Quality Object

| Field                     | Type    | Description                                |
| ------------------------- | ------- | ------------------------------------------ |
| `score`                   | float   | Quality score (0-100)                      |
| `is_blurry`               | boolean | Whether image is blurry                    |
| `is_low_quality`          | boolean | Whether image has low quality              |
| `quality_issues`          | array   | List of detected quality issues            |
| `quality_change_detected` | boolean | Whether sudden quality change was detected |

### Pet Object

| Field              | Type    | Description                         |
| ------------------ | ------- | ----------------------------------- |
| `detected`         | boolean | Whether a pet was detected          |
| `type`             | string  | Pet type (cat, dog)                 |
| `confidence`       | float   | Classification confidence           |
| `is_household_pet` | boolean | Whether classified as household pet |

**Errors:**

| Code | Description                           |
| ---- | ------------------------------------- |
| 404  | Detection with specified ID not found |

**Example Request:**

```bash
curl http://localhost:8000/api/detections/12345/enrichment
```

---

## GET /api/events/{event_id}/enrichments

Get enrichment data for all detections in an event.

**Source:** [`get_event_enrichments`](../../backend/api/routes/events.py:877)

**Parameters:**

| Name       | Type    | In   | Required | Description |
| ---------- | ------- | ---- | -------- | ----------- |
| `event_id` | integer | path | Yes      | Event ID    |

**Response:** `200 OK`

```json
{
  "event_id": 100,
  "enrichments": [
    {
      "detection_id": 1,
      "enriched_at": "2026-01-03T10:30:00Z",
      "license_plate": {
        "detected": true,
        "text": "ABC-1234",
        "confidence": 0.92
      },
      "face": {
        "detected": false,
        "count": 0
      },
      "violence": {
        "detected": false,
        "score": 0.0
      },
      "processing_time_ms": 120.5,
      "errors": []
    },
    {
      "detection_id": 2,
      "enriched_at": "2026-01-03T10:30:05Z",
      "license_plate": {
        "detected": false
      },
      "face": {
        "detected": true,
        "count": 1,
        "confidence": 0.95
      },
      "clothing": {
        "upper": "red t-shirt",
        "lower": "black pants",
        "is_suspicious": false
      },
      "violence": {
        "detected": false,
        "score": 0.05
      },
      "processing_time_ms": 145.2,
      "errors": []
    }
  ],
  "count": 2
}
```

**Response Fields:**

| Field         | Type    | Description                               |
| ------------- | ------- | ----------------------------------------- |
| `event_id`    | integer | Event ID                                  |
| `enrichments` | array   | Enrichment data for each detection        |
| `count`       | integer | Number of detections with enrichment data |

Each item in `enrichments` follows the same structure as the single detection enrichment response.

**Errors:**

| Code | Description                       |
| ---- | --------------------------------- |
| 404  | Event with specified ID not found |

**Example Request:**

```bash
curl http://localhost:8000/api/events/100/enrichments
```

---

## Security Considerations

### Error Message Sanitization

Error messages from enrichment processing may contain sensitive information such as file paths, model names, or internal stack traces. The API sanitizes these errors before returning them to clients:

- Internal errors are replaced with generic messages
- File paths are redacted
- Model-specific errors are generalized

Example sanitized error:

```json
{
  "errors": ["Enrichment processing error"]
}
```

---

## Integration Patterns

### Processing Event Enrichments

```python
import requests

def analyze_event_enrichments(event_id):
    """Analyze enrichment data for security insights."""
    response = requests.get(f"http://localhost:8000/api/events/{event_id}/enrichments")
    data = response.json()

    insights = {
        "license_plates": [],
        "faces_detected": 0,
        "suspicious_clothing": False,
        "violence_detected": False,
    }

    for enrichment in data["enrichments"]:
        # Collect license plates
        lp = enrichment.get("license_plate", {})
        if lp.get("detected") and lp.get("text"):
            insights["license_plates"].append({
                "text": lp["text"],
                "confidence": lp.get("ocr_confidence", 0)
            })

        # Count faces
        face = enrichment.get("face", {})
        if face.get("detected"):
            insights["faces_detected"] += face.get("count", 0)

        # Check for suspicious clothing
        clothing = enrichment.get("clothing", {})
        if clothing and clothing.get("is_suspicious"):
            insights["suspicious_clothing"] = True

        # Check for violence
        violence = enrichment.get("violence", {})
        if violence and violence.get("detected"):
            insights["violence_detected"] = True

    return insights
```

### Building a Detection Detail View

```javascript
// Fetch enrichment data for detection detail modal
async function fetchDetectionEnrichment(detectionId) {
  const response = await fetch(`/api/detections/${detectionId}/enrichment`);
  const data = await response.json();

  return {
    // License plate info
    licensePlate: data.license_plate?.detected
      ? {
          text: data.license_plate.text,
          confidence: Math.round(data.license_plate.confidence * 100),
        }
      : null,

    // Face detection
    faceCount: data.face?.count || 0,

    // Vehicle info
    vehicle: data.vehicle
      ? {
          type: data.vehicle.type,
          isCommercial: data.vehicle.is_commercial,
          hasDamage: data.vehicle.damage_detected,
        }
      : null,

    // Clothing description
    clothing: data.clothing
      ? {
          description: `${data.clothing.upper}, ${data.clothing.lower}`,
          isSuspicious: data.clothing.is_suspicious,
          isServiceWorker: data.clothing.is_service_uniform,
        }
      : null,

    // Safety flags
    safety: {
      violenceScore: data.violence?.score || 0,
      violenceDetected: data.violence?.detected || false,
    },

    // Quality assessment
    quality: data.image_quality
      ? {
          score: data.image_quality.score,
          issues: data.image_quality.quality_issues,
        }
      : null,

    processingTime: data.processing_time_ms,
  };
}
```

### Filtering Events by Enrichment Data

While the API doesn't support direct filtering by enrichment data, you can implement client-side filtering:

```python
def find_events_with_license_plates(events_response):
    """Find events that captured license plates."""
    events_with_plates = []

    for event in events_response["events"]:
        # Fetch enrichments for each event
        enrichments = requests.get(
            f"http://localhost:8000/api/events/{event['id']}/enrichments"
        ).json()

        # Check if any detection has a license plate
        for e in enrichments["enrichments"]:
            if e.get("license_plate", {}).get("detected"):
                events_with_plates.append({
                    "event_id": event["id"],
                    "plate_text": e["license_plate"].get("text"),
                    "timestamp": event["started_at"],
                })
                break

    return events_with_plates
```

---

## Related Documentation

- [Model Zoo API](model-zoo.md) - Status and latency monitoring for enrichment models
- [Detections API](detections.md) - Core detection endpoints
- [Events API](events.md) - Event management and querying
- [AI Pipeline Architecture](../../docs/architecture/ai-pipeline.md) - Pipeline design details
