# Fashion-CLIP Prompts Directory - Agent Guide

## Purpose

This directory contains configuration files for Fashion-CLIP, a CLIP-based model specialized for clothing and attire analysis. Fashion-CLIP classifies person detections into clothing categories and identifies suspicious attire patterns (e.g., all black clothing, face coverings, hoodies).

## Files

| File              | Purpose                                                         | Version Control  |
| ----------------- | --------------------------------------------------------------- | ---------------- |
| `current.json`    | Current active configuration (clothing categories + indicators) | Runtime-managed  |
| `history/`        | Version history directory                                       | -                |
| `history/v1.json` | Initial default configuration (17 categories + 6 indicators)    | Checked into git |

## Configuration Schema

```json
{
  "model_name": "fashion_clip",
  "config": {
    "clothing_categories": [
      "casual wear",
      "formal wear",
      "athletic wear",
      "work uniform",
      "delivery uniform",
      "all black clothing",
      "hoodie",
      "face mask",
      "sunglasses",
      "hat or cap",
      "gloves",
      "high visibility vest"
    ],
    "suspicious_indicators": [
      "all black",
      "face mask",
      "hoodie up",
      "gloves at night",
      "balaclava",
      "face covering"
    ]
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587943+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.587943+00:00"
}
```

## Configuration Fields

### `clothing_categories` (array of strings, required)

List of clothing categories that Fashion-CLIP should classify. The model uses CLIP's zero-shot classification to match person detections against these text descriptions.

**Default categories (v1):**

| Category               | Purpose                              | Risk Relevance                       |
| ---------------------- | ------------------------------------ | ------------------------------------ |
| `casual wear`          | Everyday clothing                    | Neutral                              |
| `formal wear`          | Business attire, suits               | Low risk (likely resident/guest)     |
| `athletic wear`        | Sportswear, gym clothes              | Neutral                              |
| `work uniform`         | Generic work uniforms                | Low risk (service worker)            |
| `delivery uniform`     | Delivery company uniforms            | Low risk (expected activity)         |
| `all black clothing`   | All-black outfit                     | **High risk (suspicious)**           |
| `hoodie`               | Hooded sweatshirt                    | Moderate risk (concealment)          |
| `face mask`            | Medical or non-medical face covering | Context-dependent                    |
| `sunglasses`           | Eyewear                              | Moderate risk (identity concealment) |
| `hat or cap`           | Head covering                        | Low risk (common)                    |
| `gloves`               | Hand covering                        | **High risk at night**               |
| `high visibility vest` | Safety/construction vest             | Low risk (worker)                    |

**Requirements:**

- Must have at least one category
- Categories should be descriptive phrases (not single words)
- Categories are matched using CLIP text embeddings (semantic similarity)

### `suspicious_indicators` (array of strings, required)

List of attire patterns that indicate potentially suspicious behavior. These are flagged by the risk analysis system for elevated scrutiny.

**Default indicators (v1):**

| Indicator         | When Suspicious                      | Risk Interpretation            |
| ----------------- | ------------------------------------ | ------------------------------ |
| `all black`       | Especially at night                  | Concealment intent             |
| `face mask`       | Non-medical context or at night      | Identity concealment           |
| `hoodie up`       | Hood covering face                   | Identity concealment           |
| `gloves at night` | Gloves after dark (not cold weather) | Avoiding fingerprints          |
| `balaclava`       | Full face covering                   | **Critical - immediate alert** |
| `face covering`   | Any non-medical face covering        | Identity concealment           |

**Usage in risk analysis:**

The Nemotron risk analyzer receives Fashion-CLIP attributes and applies this interpretation guide:

```
### Clothing/Attire Risk Factors
- All black + face covering (mask/balaclava) = HIGH RISK
- Dark hoodie + gloves at night = suspicious, warrant attention
- High-visibility vest or delivery uniform = likely service worker (lower risk)
```

## How Fashion-CLIP Works

1. **Person detection:** RT-DETR detects a person in the image
2. **Region cropping:** The system crops the image around the person's bounding box
3. **CLIP encoding:** Fashion-CLIP encodes the cropped image into an embedding
4. **Category matching:** The model compares the image embedding against all category text embeddings
5. **Top-K selection:** The top 3-5 most similar categories are selected (based on cosine similarity)
6. **Suspicious indicator check:** The selected categories are cross-referenced with `suspicious_indicators`
7. **Attribute storage:** Results are stored as detection attributes in PostgreSQL

**Example flow:**

```
Detection: person (x=100, y=200, w=150, h=300)
  ↓ Crop region (100, 200, 150, 300)
  ↓ Fashion-CLIP classification
  ↓ Top matches: ["all black clothing" (0.92), "hoodie" (0.87), "gloves" (0.78)]
  ↓ Check suspicious indicators: ✓ "all black", ✓ "hoodie up"
  ↓ Store: detection.attributes['fashion_clip'] = {
      "categories": ["all black clothing", "hoodie", "gloves"],
      "suspicious_indicators": ["all black", "hoodie up"],
      "risk_level": "high"
    }
```

## Use Cases for Custom Categories

### Site-Specific Uniforms

Add categories for known service workers at your location:

```json
"clothing_categories": [
  "casual wear",
  "work uniform",
  "delivery uniform",
  "postal service uniform",
  "UPS brown uniform",
  "FedEx uniform",
  "Amazon delivery vest",
  "landscaping company uniform",
  "pool cleaning uniform",
  "high visibility vest"
]
```

### Enhanced Suspicious Indicators

Add more granular suspicious attire patterns:

```json
"suspicious_indicators": [
  "all black",
  "face mask",
  "hoodie up",
  "gloves at night",
  "balaclava",
  "face covering",
  "dark sunglasses at night",
  "tactical vest",
  "backpack and gloves",
  "face bandana"
]
```

### Seasonal Adjustments

Adjust for weather-appropriate clothing:

**Winter configuration:**

```json
"suspicious_indicators": [
  "all black",
  "balaclava",
  "face covering excluding winter scarf",
  "gloves at night excluding cold weather"
]
```

**Summer configuration:**

```json
"suspicious_indicators": [
  "all black",
  "hoodie in hot weather",
  "gloves in hot weather",
  "winter clothing in summer",
  "balaclava",
  "face covering"
]
```

## Integration with Risk Analysis

Fashion-CLIP attributes are incorporated into Nemotron's risk analysis prompt:

```
## Person Analysis
Person 1 (confidence: 0.95):
- Clothing (Fashion-CLIP): all_black_clothing, hoodie, gloves
- Suspicious indicators: all black, hoodie up, gloves at night
- VQA (Florence-2): "black hoodie with hood up, dark gloves"
- Action (X-CLIP): crouching, looking around

Risk interpretation:
- All black + face covering + crouching = HIGH RISK
- Behavior suggests concealment and suspicious activity
```

Nemotron uses Fashion-CLIP attributes as a key factor in risk scoring, especially for person detections at night.

## Performance Considerations

- **Category count:** Each category adds ~10-20ms inference time per person
- **Semantic similarity:** Categories with overlapping meanings may cause ambiguous classifications
- **Image quality:** Poor lighting or low resolution reduces classification accuracy
- **Partial visibility:** Cropped or obscured persons may produce incorrect classifications

**Recommended category count:** 8-15 categories for optimal balance of coverage and performance.

## Best Practices

### Category Design

- Use descriptive phrases (not single words): "delivery uniform" > "uniform"
- Avoid ambiguous categories: "dark clothing" vs "all black clothing"
- Include context: "gloves at night" vs "gloves" (handled in suspicious indicators)
- Test with representative images: Verify categories match expected visual patterns

### Suspicious Indicator Design

- Be specific about context: "gloves at night" (not just "gloves")
- Separate indicators from categories: Categories describe, indicators flag risk
- Consider false positives: "face mask" during flu season (low risk) vs at night (high risk)
- Use Nemotron's context: Time of day, weather, and other attributes refine suspicious indicators

### Avoiding False Positives

Common false positives and how to handle them:

| False Positive           | Cause                | Mitigation                           |
| ------------------------ | -------------------- | ------------------------------------ |
| "Hoodie" in cold weather | Common winter attire | Use context: weather + time of day   |
| "Face mask" in 2020-2023 | COVID-19 pandemic    | Check date or remove from indicators |
| "All black" at funeral   | Formal black attire  | Cross-check with "formal wear"       |
| "Gloves" for gardening   | Work gloves          | Cross-check with "work uniform"      |

## Version History

Version history tracks changes to clothing categories and suspicious indicators. Use the API to:

- View history: `GET /api/prompts/fashion_clip/history`
- Restore version: `POST /api/prompts/fashion_clip/versions/{version}/restore`
- Compare configurations: Diff JSON files in `history/`

## Testing Configuration Changes

1. **Test with known images:** Use test dataset with labeled clothing types
2. **Review classification accuracy:** Check top-K matches for representative samples
3. **Monitor false positive rate:** Track alerts triggered by benign clothing patterns
4. **Adjust suspicious indicators:** Refine based on actual security events

## Related Documentation

- `/backend/services/enrichment/fashion_clip_enrichment.py` - Fashion-CLIP service
- `/backend/services/risk_analysis.py` - Risk analysis using Fashion-CLIP attributes
- `/backend/api/routes/prompt_management.py` - Prompt configuration API
- `/backend/data/prompts/AGENTS.md` - Prompts directory overview
