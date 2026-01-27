# Face Recognition Guide

Guide to the face detection and person identification features in Home Security Intelligence.

## Overview

Home Security Intelligence includes face detection capabilities that work alongside person re-identification to track individuals across cameras and match them against household members. This enables features like:

- **Household Member Recognition**: Identify known family members
- **Cross-Camera Tracking**: Follow individuals across multiple cameras
- **Unknown Person Alerts**: Get notified when unfamiliar faces are detected
- **Demographics Analysis**: Estimate age and gender for identification context

---

## Architecture

### Face Detection Pipeline

```
Person Detection -> Head Region Extraction -> Face Detection -> Embedding Generation -> Matching
       (1)                  (2)                    (3)                 (4)               (5)
```

1. **Person Detection**: YOLO26 identifies person bounding boxes
2. **Head Region Extraction**: Upper 40% of person bbox extracted
3. **Face Detection**: YOLO11 face model detects faces in head region
4. **Embedding Generation**: OSNet generates 512-dimensional embeddings
5. **Matching**: Embeddings compared against household member database

### Models Used

| Model        | Purpose          | VRAM   | Priority      |
| ------------ | ---------------- | ------ | ------------- |
| YOLO26       | Person detection | ~650MB | Always loaded |
| YOLO11-face  | Face detection   | ~41MB  | On-demand     |
| OSNet-x0.25  | Re-ID embeddings | ~100MB | MEDIUM        |
| Demographics | Age/gender       | ~500MB | HIGH          |

---

## Face Detection

### How It Works

The face detector operates on person detections:

```python
# Head region extraction
HEAD_REGION_RATIO = 0.4  # Top 40% of person bbox

# For a person at [x, y, width, height]
head_region = [x, y, width, height * 0.4]
```

**Why Head Region?**

For a standing person, the face is typically in the top 40% of the bounding box. This reduces false positives and improves detection accuracy.

### Face Detection Output

```json
{
  "faces": [
    {
      "bbox": [120, 80, 180, 140],
      "confidence": 0.92,
      "person_detection_id": 12345
    }
  ]
}
```

### Configuration

| Setting                | Default | Description                             |
| ---------------------- | ------- | --------------------------------------- |
| `head_ratio`           | 0.4     | Fraction of person bbox for head region |
| `padding`              | 0.2     | Padding around head bbox (20%)          |
| `confidence_threshold` | 0.3     | Minimum face detection confidence       |

---

## Person Re-Identification

### Embedding Generation

OSNet generates 512-dimensional normalized embeddings:

```json
{
  "embedding": [0.123, -0.456, 0.789, ...],
  "embedding_hash": "abc123def456...",
  "inference_time_ms": 15.2
}
```

**Embedding Properties:**

- **Dimensionality**: 512 values
- **Normalization**: L2 normalized (unit length)
- **Comparison**: Cosine similarity
- **Threshold**: 0.7 default match threshold

### Similarity Matching

Two embeddings are compared using cosine similarity:

```
similarity = dot(embedding_a, embedding_b)

if similarity >= threshold:
    # Same person
else:
    # Different people
```

**Threshold Guidelines:**

| Threshold | Use Case                                |
| --------- | --------------------------------------- |
| 0.6       | Lenient matching (more false positives) |
| 0.7       | Balanced (default)                      |
| 0.8       | Strict matching (fewer false positives) |
| 0.9       | Very strict (may miss matches)          |

---

## Demographics Analysis

### Age Estimation

ViT-based age range classification:

```json
{
  "age_range": "21-35",
  "confidence": 0.87
}
```

**Age Ranges:**

| Range | Description      |
| ----- | ---------------- |
| 0-10  | Child            |
| 11-20 | Teen/young adult |
| 21-35 | Young adult      |
| 36-50 | Middle-aged      |
| 51-65 | Older adult      |
| 65+   | Senior           |

### Gender Estimation

ViT-based gender classification:

```json
{
  "gender": "male",
  "confidence": 0.91
}
```

**Privacy Note:** Demographics are used for identification context only and are not stored long-term. They help distinguish between individuals when other identifying features are similar.

---

## Household Member Registration

### Adding Household Members

```bash
POST /api/household/members
Content-Type: application/json

{
  "name": "John Smith",
  "relationship": "family",
  "trust_level": "full",
  "notify_on_arrival": true,
  "notify_on_departure": false
}
```

**Response:**

```json
{
  "id": "member-uuid",
  "name": "John Smith",
  "relationship": "family",
  "trust_level": "full",
  "embedding_count": 0,
  "created_at": "2026-01-26T10:00:00Z"
}
```

### Adding Member Embeddings

Add face embeddings from existing detections:

```bash
POST /api/household/members/{member_id}/embeddings
Content-Type: application/json

{
  "event_id": "event-uuid",
  "detection_id": 12345,
  "notes": "Front door arrival, clear view"
}
```

**Best Practices for Embeddings:**

1. **Multiple angles**: Add embeddings from different camera angles
2. **Different lighting**: Include day and night conditions
3. **Various expressions**: Include neutral and smiling
4. **Quality threshold**: Only use high-confidence detections
5. **Minimum count**: At least 3-5 embeddings per person

### Trust Levels

| Level        | Description                       | Alert Behavior             |
| ------------ | --------------------------------- | -------------------------- |
| `full`       | Family members                    | No alerts                  |
| `partial`    | Regular visitors, service workers | Alerts outside schedule    |
| `monitor`    | Known but tracked                 | Log only, no notifications |
| `restricted` | Should not be on property         | High-priority alerts       |

---

## Cross-Camera Tracking

### Entity Tracking

When a person is detected, the system:

1. Generates an embedding for the detection
2. Compares against recent embeddings from other cameras
3. Links detections if similarity exceeds threshold
4. Creates an entity record for tracking

**Entity Response:**

```json
{
  "entity_id": "entity-uuid",
  "entity_type": "person",
  "first_seen": "2026-01-26T14:00:00Z",
  "last_seen": "2026-01-26T14:15:00Z",
  "cameras_seen": ["front_door", "driveway"],
  "appearance_count": 3,
  "matched_member": {
    "id": "member-uuid",
    "name": "John Smith"
  }
}
```

### Entity History

```bash
GET /api/entities/{entity_id}/history
```

**Response:**

```json
{
  "entity_id": "entity-uuid",
  "appearances": [
    {
      "timestamp": "2026-01-26T14:00:00Z",
      "camera_id": "front_door",
      "zone": "Front Porch",
      "thumbnail_url": "/api/media/thumbnails/abc123.jpg",
      "duration_seconds": 45
    },
    {
      "timestamp": "2026-01-26T14:05:00Z",
      "camera_id": "driveway",
      "zone": "Driveway",
      "thumbnail_url": "/api/media/thumbnails/def456.jpg",
      "duration_seconds": 30
    }
  ]
}
```

---

## API Reference

### Household Members

| Endpoint                                 | Method | Description        |
| ---------------------------------------- | ------ | ------------------ |
| `/api/household/members`                 | GET    | List all members   |
| `/api/household/members`                 | POST   | Create new member  |
| `/api/household/members/{id}`            | GET    | Get member details |
| `/api/household/members/{id}`            | PATCH  | Update member      |
| `/api/household/members/{id}`            | DELETE | Delete member      |
| `/api/household/members/{id}/embeddings` | POST   | Add embedding      |

### Household Vehicles

| Endpoint                       | Method | Description          |
| ------------------------------ | ------ | -------------------- |
| `/api/household/vehicles`      | GET    | List all vehicles    |
| `/api/household/vehicles`      | POST   | Register new vehicle |
| `/api/household/vehicles/{id}` | GET    | Get vehicle details  |
| `/api/household/vehicles/{id}` | PATCH  | Update vehicle       |
| `/api/household/vehicles/{id}` | DELETE | Delete vehicle       |

### Entities

| Endpoint                     | Method | Description             |
| ---------------------------- | ------ | ----------------------- |
| `/api/entities`              | GET    | List tracked entities   |
| `/api/entities/{id}`         | GET    | Get entity details      |
| `/api/entities/{id}/history` | GET    | Get appearance timeline |

### Query Parameters (Entities)

| Parameter     | Type     | Description                     |
| ------------- | -------- | ------------------------------- |
| `entity_type` | String   | Filter by 'person' or 'vehicle' |
| `camera_id`   | String   | Filter by camera                |
| `since`       | DateTime | Entities seen since timestamp   |
| `limit`       | Integer  | Pagination limit (default: 50)  |
| `offset`      | Integer  | Pagination offset               |

---

## Matching Algorithm

### Person-to-Member Matching

```
For each detected person:
  1. Generate embedding
  2. For each household member:
     - Get member embeddings (up to 10 most recent)
     - Calculate average similarity
     - If similarity >= threshold:
       - Mark as matched
       - Record confidence
  3. If no match found:
     - Mark as "Unknown"
     - Create/update entity record
```

### Confidence Calculation

Match confidence is based on:

1. **Face detection confidence** (0-1)
2. **Embedding similarity** (0-1)
3. **Number of matching embeddings** (more = higher confidence)

```
confidence = face_conf * avg_similarity * min(embedding_matches / 3, 1.0)
```

---

## Alert Integration

### Unknown Person Alerts

When an unknown person is detected:

```json
{
  "type": "unknown_person",
  "severity": "medium",
  "zone_type": "entry_point",
  "details": {
    "entity_id": "entity-uuid",
    "camera": "Front Door",
    "zone": "Front Porch",
    "demographics": {
      "age_range": "21-35",
      "gender": "male"
    }
  }
}
```

**Severity Based on Zone Type:**

| Zone Type   | Unknown Person Severity |
| ----------- | ----------------------- |
| entry_point | High                    |
| restricted  | Critical                |
| monitored   | Medium                  |
| other       | Low                     |

### Known Person Notifications

For household members with notifications enabled:

```json
{
  "type": "member_arrival",
  "member_id": "member-uuid",
  "member_name": "John Smith",
  "camera": "Front Door",
  "timestamp": "2026-01-26T14:00:00Z"
}
```

---

## Privacy Considerations

### Data Retention

| Data Type            | Retention | Notes                |
| -------------------- | --------- | -------------------- |
| Face detections      | 30 days   | With events          |
| Embeddings (events)  | 30 days   | Linked to detections |
| Embeddings (members) | Permanent | Until member deleted |
| Entity tracks        | 7 days    | Short-term tracking  |
| Demographics         | 30 days   | With events          |

### Data Minimization

- Face images are not stored separately
- Embeddings are numerical vectors only
- Demographics are estimates, not identity
- All data can be deleted via member deletion

### Local Processing

All face recognition processing happens locally:

- No cloud services
- No third-party APIs
- Data stays on your network
- Full control over retention

---

## Best Practices

### For Accurate Recognition

1. **Quality Images**: Ensure cameras have good resolution and lighting
2. **Multiple Embeddings**: Add 5+ embeddings per household member
3. **Varied Conditions**: Include different lighting, angles, expressions
4. **Regular Updates**: Re-add embeddings if appearance changes significantly
5. **Threshold Tuning**: Adjust match threshold based on your needs

### For Privacy

1. **Minimal Registration**: Only register necessary household members
2. **Trust Levels**: Use appropriate trust levels for different relationships
3. **Regular Cleanup**: Review and remove outdated member data
4. **Notification Control**: Configure notifications thoughtfully

### For Performance

1. **Embedding Limit**: Keep member embedding count reasonable (10-20)
2. **Model Priority**: Demographics model has HIGH priority for quick loading
3. **Batch Processing**: Face detection runs in batches with other enrichment

---

## Troubleshooting

### Faces Not Detected

**Check:**

1. Person fully visible in frame
2. Face not obscured (hat, mask, angle)
3. Sufficient lighting
4. Camera resolution adequate

**Fix:**

- Adjust camera position for better face visibility
- Improve lighting conditions
- Lower confidence threshold (may increase false positives)

### Wrong Person Matched

**Causes:**

1. Insufficient embeddings for member
2. Similar-looking individuals
3. Match threshold too low

**Fix:**

- Add more diverse embeddings for the member
- Increase match threshold
- Remove problematic embeddings

### Known Member Not Recognized

**Check:**

1. Member has sufficient embeddings (5+)
2. Embeddings are from varied conditions
3. Appearance hasn't changed significantly
4. Detection quality is adequate

**Fix:**

- Add new embeddings from recent detections
- Remove old/poor quality embeddings
- Lower match threshold slightly

### Too Many Unknown Alerts

**Options:**

1. Register more household members
2. Configure trust levels for regular visitors
3. Adjust zone-based alert severity
4. Set up quiet hours for specific times

---

## Related Documentation

- [Video Analytics Guide](video-analytics.md) - AI pipeline overview
- [Zone Configuration Guide](zone-configuration.md) - Zone setup
- [Entities](../ui/entities.md) - Entity tracking UI
- [Settings](../ui/settings.md) - Household management
