# YOLO-World Prompts Directory - Agent Guide

## Purpose

This directory contains configuration files for YOLO-World, an open-vocabulary object detection model that can detect custom object classes defined via text prompts. YOLO-World supplements RT-DETR's fixed object classes with user-defined detection categories.

## Files

| File              | Purpose                                                           | Version Control  |
| ----------------- | ----------------------------------------------------------------- | ---------------- |
| `current.json`    | Current active configuration (object classes + threshold)         | Runtime-managed  |
| `history/`        | Version history directory                                         | -                |
| `history/v1.json` | Initial default configuration (14 object classes + 0.5 threshold) | Checked into git |

## Configuration Schema

```json
{
  "model_name": "yolo_world",
  "config": {
    "object_classes": [
      "person",
      "car",
      "truck",
      "motorcycle",
      "bicycle",
      "dog",
      "cat",
      "backpack",
      "handbag",
      "suitcase",
      "knife",
      "baseball bat",
      "skateboard",
      "umbrella"
    ],
    "confidence_threshold": 0.5
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.588185+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.588185+00:00"
}
```

## Configuration Fields

### `object_classes` (array of strings, required)

List of object categories that YOLO-World should detect. Unlike traditional YOLO models with fixed classes, YOLO-World uses vision-language alignment to detect any object described by text.

**Default object classes (v1):**

| Object Class   | Category    | Security Relevance                     |
| -------------- | ----------- | -------------------------------------- |
| `person`       | Primary     | Core detection target                  |
| `car`          | Vehicle     | Parking lot security, unknown vehicles |
| `truck`        | Vehicle     | Delivery tracking, unusual vehicles    |
| `motorcycle`   | Vehicle     | Two-wheel vehicle tracking             |
| `bicycle`      | Vehicle     | Recreation, theft monitoring           |
| `dog`          | Pet         | False positive filtering (not threat)  |
| `cat`          | Pet         | False positive filtering (not threat)  |
| `backpack`     | Item        | Suspicious if carried at night         |
| `handbag`      | Item        | Context-dependent                      |
| `suitcase`     | Item        | Unusual in residential area            |
| `knife`        | Weapon      | **Critical - immediate alert**         |
| `baseball bat` | Weapon/Item | **Suspicious - potential weapon**      |
| `skateboard`   | Recreation  | Neutral (youth activity)               |
| `umbrella`     | Item        | Context-dependent (weather)            |

**Requirements:**

- Must have at least one object class
- Object classes should be noun phrases (describing objects, not actions)
- Classes use zero-shot detection (no training required)

### `confidence_threshold` (float, optional)

Minimum confidence score (0.0-1.0) for detections to be considered valid.

- **Range:** 0.0 to 1.0
- **Default:** 0.5 (50% confidence)
- **Lower values (0.3-0.4):** More detections, higher false positive rate
- **Higher values (0.6-0.8):** Fewer detections, higher precision

**Recommended thresholds by object type:**

| Object Type | Recommended Threshold | Reasoning                              |
| ----------- | --------------------- | -------------------------------------- |
| Weapons     | 0.6-0.7               | Reduce false positives (sticks, tools) |
| Vehicles    | 0.5                   | Balanced precision/recall              |
| Pets        | 0.7-0.8               | High confidence = likely real pet      |
| Items       | 0.5                   | Balanced detection                     |

## How YOLO-World Works

1. **Text encoding:** YOLO-World encodes each object class into a text embedding
2. **Image processing:** The model processes the input image through a vision encoder
3. **Region proposals:** The model generates bounding box proposals
4. **Classification:** Each proposal is compared against all object class embeddings
5. **NMS filtering:** Non-maximum suppression removes duplicate detections
6. **Confidence filtering:** Detections below `confidence_threshold` are discarded
7. **Output:** Bounding boxes with class labels and confidence scores

**Example flow:**

```
Input: security_camera_frame.jpg
Object classes: ["person", "car", "backpack", "knife"]
  ↓ Text encoding: ["person" → embedding_1, "car" → embedding_2, ...]
  ↓ Image encoding + region proposals
  ↓ Detected: [
      {"class": "person", "confidence": 0.92, "bbox": [100, 200, 150, 300]},
      {"class": "backpack", "confidence": 0.78, "bbox": [120, 250, 40, 60]},
      {"class": "car", "confidence": 0.55, "bbox": [300, 400, 200, 150]}
    ]
  ↓ Filter by threshold (0.5): All pass
  ↓ Store detections in PostgreSQL
```

## Relationship to RT-DETR

This system uses both RT-DETR and YOLO-World for object detection:

| Model      | Object Classes                | Speed      | Use Case                               |
| ---------- | ----------------------------- | ---------- | -------------------------------------- |
| RT-DETR    | 80 COCO classes (fixed)       | ~50-80ms   | Primary detection (person, car, etc.)  |
| YOLO-World | User-defined via text prompts | ~100-150ms | Custom objects (tools, specific items) |

**Typical workflow:**

1. RT-DETR detects core objects (person, car, truck, dog, cat)
2. YOLO-World detects custom objects (knife, baseball bat, specific items)
3. Both results are merged and deduplicated (NMS across models)
4. Combined detections are stored in the database

**When to use YOLO-World:**

- Detecting objects not in COCO-80 (e.g., "crowbar", "ladder", "spray paint")
- Site-specific objects (e.g., "pool equipment", "patio furniture")
- Custom weapon categories (e.g., "golf club", "tire iron")

## Use Cases for Custom Object Classes

### Enhanced Weapon Detection

Add more weapon categories for comprehensive threat detection:

```json
"object_classes": [
  "person",
  "knife",
  "baseball bat",
  "crowbar",
  "hammer",
  "axe",
  "gun",
  "rifle",
  "golf club",
  "tire iron",
  "chain",
  "metal pipe"
]
```

### Tool and Equipment Monitoring

Detect suspicious tools that could indicate break-in attempts:

```json
"object_classes": [
  "person",
  "ladder",
  "crowbar",
  "bolt cutters",
  "power drill",
  "saw",
  "screwdriver",
  "flashlight",
  "lock pick",
  "glass cutter"
]
```

### Package and Delivery Tracking

Monitor package deliveries and theft:

```json
"object_classes": [
  "person",
  "car",
  "truck",
  "package box",
  "cardboard box",
  "envelope",
  "amazon package",
  "ups box",
  "fedex box",
  "shopping bag"
]
```

### Pet and Wildlife Monitoring

Distinguish between security threats and animals:

```json
"object_classes": [
  "person",
  "dog",
  "cat",
  "raccoon",
  "deer",
  "coyote",
  "bear",
  "bird",
  "squirrel"
]
```

## Integration with Risk Analysis

YOLO-World detections are incorporated into Nemotron's risk analysis:

```
## Detections with Full Enrichment
1. Person (conf: 0.92) - RT-DETR
   - Clothing: all_black_clothing, hoodie, gloves
   - Action: crouching, looking around

2. Crowbar (conf: 0.87) - YOLO-World
   - Risk: CRITICAL - burglary tool detected
   - Location: Near front door entry point

Risk interpretation:
- Person + crowbar + crouching near entry = CRITICAL THREAT
- Immediate alert recommended
```

Nemotron uses YOLO-World detections to identify suspicious items that elevate risk scores.

## Performance Considerations

- **Object class count:** Each class adds ~5-10ms inference time
- **Semantic ambiguity:** Similar objects (knife vs blade) may overlap
- **False positive rate:** Lower confidence thresholds increase false positives
- **Zero-shot accuracy:** YOLO-World is less accurate than trained models (RT-DETR)

**Recommended object class count:** 10-20 objects for optimal performance.

## Best Practices

### Object Class Design

- Use specific noun phrases: "crowbar" > "tool"
- Avoid ambiguous categories: "weapon" (too broad)
- Include common objects: "backpack", "bag" (context-dependent risk)
- Test with representative images: Verify objects match visual appearance

### Confidence Threshold Tuning

**Iterative tuning process:**

1. Start with default (0.5)
2. Review detection logs for false positives/negatives
3. Adjust threshold based on object type:
   - High risk objects (weapons): Increase threshold (0.6-0.7)
   - Common objects (backpack): Keep moderate (0.5)
   - Rare objects (specific tools): Lower threshold (0.4-0.5)
4. Monitor alert quality over time

### Avoiding False Positives

Common false positives and mitigation strategies:

| False Positive            | Cause                     | Mitigation                              |
| ------------------------- | ------------------------- | --------------------------------------- |
| "Knife" for stick         | Visual similarity         | Increase confidence threshold (0.6-0.7) |
| "Baseball bat" for branch | Zero-shot confusion       | Add context: near building = suspicious |
| "Crowbar" for pipe        | Shape ambiguity           | Refine prompt: "metal crowbar"          |
| "Backpack" for shadow     | Low-light false detection | Increase confidence threshold (0.6)     |

## Zero-Shot Detection Limitations

YOLO-World uses zero-shot detection, which has limitations:

**Strengths:**

- No training required for new objects
- Flexible, user-defined object classes
- Works well for common objects with clear visual features

**Weaknesses:**

- Less accurate than trained models (RT-DETR)
- Semantic ambiguity (knife vs blade vs tool)
- Struggles with fine-grained distinctions (baseball bat vs stick)
- False positives on visually similar objects

**Best practices:**

- Use YOLO-World for custom objects not in RT-DETR's COCO-80
- Increase confidence threshold for high-risk objects (weapons)
- Cross-validate with RT-DETR when both models detect the same object

## Version History

Version history tracks changes to object classes and confidence thresholds. Use the API to:

- View history: `GET /api/prompts/yolo_world/history`
- Restore version: `POST /api/prompts/yolo_world/versions/{version}/restore`
- Compare configurations: Diff JSON files in `history/`

## Testing Configuration Changes

1. **Test with known images:** Use test dataset with labeled objects
2. **Review detection accuracy:** Check precision/recall for each object class
3. **Tune confidence threshold:** Adjust based on false positive/negative rate
4. **Monitor inference time:** Measure P95 latency with new object count

## Related Documentation

- `/backend/services/detection/yolo_world_detection.py` - YOLO-World detection service
- `/backend/services/risk_analysis.py` - Risk analysis using YOLO-World detections
- `/backend/api/routes/prompt_management.py` - Prompt configuration API
- `/backend/data/prompts/AGENTS.md` - Prompts directory overview
- `/ai/yolo_world/AGENTS.md` - YOLO-World model server setup (if applicable)
