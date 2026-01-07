# X-CLIP Prompts Directory - Agent Guide

## Purpose

This directory contains configuration files for X-CLIP, a video-language model adapted for action recognition in security footage. X-CLIP classifies person detections into action categories (walking, running, crouching, loitering, etc.) to provide behavioral context for risk analysis.

## Files

| File              | Purpose                                               | Version Control  |
| ----------------- | ----------------------------------------------------- | ---------------- |
| `current.json`    | Current active configuration (list of action classes) | Runtime-managed  |
| `history/`        | Version history directory                             | -                |
| `history/v1.json` | Initial default configuration (16 action classes)     | Checked into git |

## Configuration Schema

```json
{
  "model_name": "xclip",
  "config": {
    "action_classes": [
      "walking",
      "running",
      "standing",
      "sitting",
      "crouching",
      "crawling",
      "loitering",
      "pacing",
      "looking around",
      "photographing",
      "checking car doors",
      "breaking in",
      "climbing",
      "hiding",
      "fighting",
      "throwing"
    ]
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.588431+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.588431+00:00"
}
```

## Configuration Fields

### `action_classes` (array of strings, required)

List of action categories that X-CLIP should recognize. The model uses vision-language alignment to classify person behavior from image sequences or single frames.

**Default action classes (v1):**

| Action Class         | Description                           | Risk Relevance                    |
| -------------------- | ------------------------------------- | --------------------------------- |
| `walking`            | Normal walking gait                   | Neutral (low risk)                |
| `running`            | Fast movement, jogging                | Context-dependent (flight?)       |
| `standing`           | Stationary, upright position          | Neutral                           |
| `sitting`            | Seated position                       | Neutral                           |
| `crouching`          | Bent down, low posture                | **Suspicious near entry points**  |
| `crawling`           | Moving on hands/knees                 | **Highly suspicious**             |
| `loitering`          | Standing idle for extended time       | **Suspicious (casing location)**  |
| `pacing`             | Walking back and forth repeatedly     | **Suspicious (nervous behavior)** |
| `looking around`     | Scanning surroundings, head turns     | **Suspicious (surveillance)**     |
| `photographing`      | Holding phone/camera, taking pictures | **Suspicious (reconnaissance)**   |
| `checking car doors` | Testing vehicle door handles          | **Critical (theft attempt)**      |
| `breaking in`        | Forcing entry, prying windows/doors   | **Critical (burglary)**           |
| `climbing`           | Scaling fence, wall, or structure     | **Critical (trespassing)**        |
| `hiding`             | Concealing behind objects             | **Critical (evading detection)**  |
| `fighting`           | Physical altercation, violence        | **Critical (assault)**            |
| `throwing`           | Throwing objects                      | **High risk (vandalism/assault)** |

**Requirements:**

- Must have at least one action class
- Action classes should be verb phrases or gerunds (describing behavior)
- Classes are matched using CLIP-style vision-language embeddings

## How X-CLIP Works

1. **Person detection:** RT-DETR detects a person in the image
2. **Temporal context (optional):** If available, use 2-4 second video clip or sequence of frames
3. **Region cropping:** The system crops the image/video around the person's bounding box
4. **X-CLIP encoding:** The model encodes the visual sequence into an embedding
5. **Action matching:** The model compares the video embedding against all action text embeddings
6. **Top-K selection:** The top 1-3 most likely actions are selected (based on cosine similarity)
7. **Attribute storage:** Results are stored as detection attributes in PostgreSQL

**Example flow:**

```
Detection: person (x=150, y=100, w=120, h=280)
  ↓ Crop region + temporal context (last 3 seconds)
  ↓ X-CLIP action recognition
  ↓ Top matches: ["crouching" (0.89), "looking around" (0.76)]
  ↓ Store: detection.attributes['xclip'] = {
      "actions": ["crouching", "looking around"],
      "confidence": {"crouching": 0.89, "looking around": 0.76},
      "risk_level": "high"
    }
```

## Integration with Risk Analysis

X-CLIP action attributes are incorporated into Nemotron's risk analysis prompt:

```
## Behavioral Analysis
Person 1 (confidence: 0.95):
- Actions (X-CLIP): crouching, looking around
- Clothing (Fashion-CLIP): all_black_clothing, hoodie, gloves
- Location: Near front door entry point

Risk interpretation:
- Crouching near entry points = suspicious
- Looking around = surveillance behavior
- Combined with suspicious attire = HIGH RISK
```

Nemotron uses X-CLIP actions as a critical factor in risk scoring, especially for behaviors like:

- Crouching near doors/windows
- Loitering > 30 seconds
- Running away from camera (flight response)
- Checking car doors (theft indicator)

## Use Cases for Custom Action Classes

### Delivery and Service Worker Actions

Add common legitimate activities to reduce false positives:

```json
"action_classes": [
  "walking",
  "standing",
  "carrying package",
  "knocking on door",
  "placing package",
  "taking photo of delivery",
  "checking phone",
  "reading address",
  "returning to vehicle"
]
```

### Enhanced Security-Specific Actions

Add more granular suspicious behaviors:

```json
"action_classes": [
  "walking",
  "running",
  "crouching",
  "loitering",
  "pacing",
  "looking around",
  "photographing",
  "checking car doors",
  "breaking in",
  "climbing",
  "hiding",
  "fighting",
  "throwing",
  "tampering with camera",
  "forcing lock",
  "breaking window",
  "cutting fence",
  "spray painting",
  "vandalizing property"
]
```

### Vehicle-Related Actions

Add actions for parking lot security:

```json
"action_classes": [
  "walking",
  "running",
  "checking car doors",
  "breaking car window",
  "entering vehicle",
  "exiting vehicle",
  "loading vehicle",
  "unloading vehicle",
  "circling vehicle",
  "hiding behind vehicle"
]
```

## Risk Interpretation Guide

The Nemotron prompt includes these X-CLIP action interpretations:

| Action Pattern                | Risk Assessment                         |
| ----------------------------- | --------------------------------------- |
| Crouching near entry points   | Suspicious (picking lock, hiding)       |
| Loitering > 30 seconds        | Increased concern (casing location)     |
| Running away from camera      | Flight response, investigate            |
| Checking car doors            | Potential vehicle crime                 |
| Pacing + looking around       | Nervous behavior, possible surveillance |
| Hiding + crouching            | Critical (evading detection)            |
| Fighting + violence detection | Critical (assault, immediate alert)     |

## Performance Considerations

- **Action class count:** Each class adds ~15-25ms inference time per person
- **Temporal context:** Video clips (2-4 seconds) improve accuracy but increase latency
- **Single-frame mode:** Faster but less accurate for complex actions (e.g., loitering)
- **Action ambiguity:** Similar actions (walking vs pacing) may cause confusion

**Recommended action class count:** 10-20 actions for optimal balance of coverage and performance.

## Best Practices

### Action Class Design

- Use specific verb phrases: "checking car doors" > "checking"
- Avoid overly broad categories: "suspicious behavior" (not actionable)
- Include context: "crouching near door" vs "crouching" (handled in risk analysis)
- Test with representative footage: Verify actions match visual patterns

### Distinguishing Similar Actions

Some actions are visually similar and require careful design:

| Similar Actions            | Distinguishing Features                    |
| -------------------------- | ------------------------------------------ |
| Walking vs pacing          | Pacing: back-and-forth, repetitive pattern |
| Standing vs loitering      | Loitering: extended duration (>30s)        |
| Running vs jogging         | Context: time of day, direction            |
| Photographing vs phone use | Camera orientation, gesture                |

### Handling False Positives

Common false positives and mitigation strategies:

| False Positive                 | Cause                         | Mitigation                           |
| ------------------------------ | ----------------------------- | ------------------------------------ |
| "Loitering" for delivery wait  | Waiting at door for answer    | Time threshold (>60s = loitering)    |
| "Checking car doors" for owner | Owner entering own vehicle    | Cross-check with ReID (known person) |
| "Hiding" for crouching         | Tying shoes, picking up item  | Duration + context (near entry?)     |
| "Breaking in" for key fumbling | Resident struggling with lock | Time of day + ReID (known resident)  |

## Single-Frame vs Multi-Frame Mode

X-CLIP can operate in two modes:

### Single-Frame Mode (Default)

- Input: Single image (current detection)
- Latency: ~100-150ms per person
- Accuracy: Good for static poses (standing, crouching)
- Limitations: Cannot detect temporal actions (loitering, pacing)

### Multi-Frame Mode (Enhanced)

- Input: 2-4 second video clip (16-32 frames)
- Latency: ~300-500ms per person
- Accuracy: Excellent for temporal actions (loitering, pacing, running)
- Requirements: Frame buffer or video input

**Recommendation:** Use single-frame mode for real-time detection, multi-frame mode for post-analysis.

## Version History

Version history tracks changes to action class lists. Use the API to:

- View history: `GET /api/prompts/xclip/history`
- Restore version: `POST /api/prompts/xclip/versions/{version}/restore`
- Compare action lists: Diff JSON files in `history/`

## Testing Configuration Changes

1. **Test with known footage:** Use test videos with labeled actions
2. **Review classification accuracy:** Check top-K matches for representative clips
3. **Monitor false positive rate:** Track alerts triggered by benign actions
4. **Adjust risk thresholds:** Refine Nemotron prompt based on X-CLIP results

## Related Documentation

- `/backend/services/enrichment/xclip_enrichment.py` - X-CLIP action recognition service
- `/backend/services/risk_analysis.py` - Risk analysis using X-CLIP attributes
- `/backend/api/routes/prompt_management.py` - Prompt configuration API
- `/backend/data/prompts/AGENTS.md` - Prompts directory overview
