# Comprehensive Scene OCR for Nemotron Context Enrichment

**Date:** 2026-02-04
**Status:** Design Complete
**Author:** Mike Svoboda + Claude

## Overview

Expand PaddleOCR usage beyond license plates to extract all readable text from security camera frames. This enriches Nemotron's context for risk assessment by identifying service workers, delivery vehicles, packages, and scene elements.

## Goals

1. **Identify service workers** - Read "FedEx", "Amazon", "Joe's Plumbing" from uniforms and vehicles to auto-classify as low-risk
2. **Package/delivery context** - Read shipping labels to confirm legitimate deliveries
3. **Scene understanding** - Read street signs, business names, house numbers for location context
4. **Vehicle identification** - Read company names, taxi numbers, fleet IDs beyond just license plates

## Architecture

### OCR Strategy: Full Frame + Targeted Crops

Run PaddleOCR on both the full frame (for scene text) and detection crops (for object-specific text):

| Source        | Pipeline Phase       | Purpose                            | Examples                  |
| ------------- | -------------------- | ---------------------------------- | ------------------------- |
| Full frame    | Phase 1 (parallel)   | Signs, house numbers, distant text | "STOP", "123", "Main St"  |
| Person crops  | Phase 2 (sequential) | Uniforms, badges, shirt text       | "FedEx", "ABC Plumbing"   |
| Vehicle crops | Phase 2 (sequential) | Company names, fleet IDs           | "Amazon Prime", "Unit 47" |
| Package crops | Phase 2 (sequential) | Shipping labels                    | "FedEx", "USPS"           |

### Pipeline Integration

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1 - Parallel (asyncio.gather)                             │
├─────────────────────────────────────────────────────────────────┤
│ • Face Detection          • Violence Detection                  │
│ • License Plate Detection • Weather Classification              │
│ • Clothing Classification • Pose Estimation                     │
│ • Depth Estimation        • Action Recognition                  │
│ • Vehicle Classification  • Vehicle Damage                      │
│ • Pet Classification      • Clothing Segmentation               │
│ • Image Quality (CPU)                                           │
│ • [NEW] Full Frame OCR    ← Runs in parallel, no dependencies   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2 - Sequential (depends on Phase 1)                       │
├─────────────────────────────────────────────────────────────────┤
│ • Plate OCR (existing)                                          │
│ • [NEW] Person Crop OCR   ← Needs detection bboxes              │
│ • [NEW] Vehicle Crop OCR  ← Needs detection bboxes              │
│ • [NEW] Package Crop OCR  ← Needs detection bboxes              │
│ • Florence-2 Vision Extraction                                  │
│ • Re-ID (CLIP embeddings)                                       │
│ • Scene Change Detection                                        │
│ • Household Matching                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Output Format: JSON

Structured JSON format integrated with existing detection context for clear parsing by Nemotron.

### Detection-Associated OCR

```json
{
  "detections": [
    {
      "id": "det_001",
      "class": "person",
      "confidence": 0.92,
      "bbox": [100, 50, 300, 400],
      "enrichment": {
        "clothing": {
          "description": "work uniform",
          "confidence": 0.85,
          "is_service_uniform": true
        },
        "pose": {
          "action": "standing",
          "carrying": "clipboard"
        },
        "ocr": {
          "texts": [{ "value": "Joe's Plumbing", "confidence": 0.91, "region": "chest" }],
          "service_match": {
            "provider": "Joe's Plumbing",
            "category": "PLUMBING",
            "confidence": 0.95,
            "risk_modifier": "low_risk_service"
          }
        }
      }
    },
    {
      "id": "det_002",
      "class": "car",
      "confidence": 0.88,
      "bbox": [400, 200, 800, 500],
      "enrichment": {
        "vehicle_type": "Van",
        "is_commercial": true,
        "ocr": {
          "texts": [
            { "value": "FedEx", "confidence": 0.94, "region": "side" },
            { "value": "Ground", "confidence": 0.89, "region": "side" }
          ],
          "service_match": {
            "provider": "FedEx",
            "category": "DELIVERY",
            "confidence": 0.97,
            "risk_modifier": "low_risk_service"
          }
        },
        "plate": {
          "text": "ABC1234",
          "confidence": 0.91
        }
      }
    }
  ],
  "scene_text": [
    { "value": "123", "type": "house_number", "confidence": 0.88, "bbox": [50, 20, 90, 45] },
    { "value": "Main St", "type": "street_sign", "confidence": 0.92, "bbox": [200, 10, 320, 40] },
    { "value": "STOP", "type": "sign", "confidence": 0.96, "bbox": [600, 30, 680, 110] }
  ]
}
```

## Service Provider Matching

### Curated Provider Database

Maintain a static list of ~100-200 known service providers with categories:

```json
{
  "providers": [
    {
      "name": "FedEx",
      "aliases": ["FEDEX", "FedEx Ground", "FedEx Express"],
      "category": "DELIVERY"
    },
    { "name": "UPS", "aliases": ["UPS", "United Parcel Service"], "category": "DELIVERY" },
    { "name": "Amazon", "aliases": ["AMAZON", "Amazon Prime", "AMZ"], "category": "DELIVERY" },
    {
      "name": "USPS",
      "aliases": ["USPS", "US Postal Service", "United States Postal"],
      "category": "DELIVERY"
    },
    { "name": "DHL", "aliases": ["DHL", "DHL Express"], "category": "DELIVERY" },
    { "name": "OnTrac", "aliases": ["ONTRAC", "OnTrac"], "category": "DELIVERY" },
    { "name": "PG&E", "aliases": ["PG&E", "Pacific Gas"], "category": "UTILITY" },
    { "name": "ComEd", "aliases": ["COMED", "Commonwealth Edison"], "category": "UTILITY" },
    { "name": "AT&T", "aliases": ["AT&T", "ATT"], "category": "TELECOM" },
    { "name": "Comcast", "aliases": ["COMCAST", "Xfinity"], "category": "TELECOM" },
    { "name": "Verizon", "aliases": ["VERIZON", "Verizon Fios"], "category": "TELECOM" },
    { "name": "Roto-Rooter", "aliases": ["ROTO-ROOTER", "Roto Rooter"], "category": "PLUMBING" },
    {
      "name": "ServiceMaster",
      "aliases": ["SERVICEMASTER", "Service Master"],
      "category": "HOME_SERVICES"
    }
  ],
  "categories": {
    "DELIVERY": { "risk_modifier": "low_risk_service", "description": "Package/mail delivery" },
    "UTILITY": { "risk_modifier": "low_risk_service", "description": "Gas, electric, water" },
    "TELECOM": { "risk_modifier": "low_risk_service", "description": "Internet, phone, cable" },
    "PLUMBING": { "risk_modifier": "low_risk_service", "description": "Plumbing services" },
    "HVAC": { "risk_modifier": "low_risk_service", "description": "Heating/cooling" },
    "ELECTRICAL": { "risk_modifier": "low_risk_service", "description": "Electrical services" },
    "LANDSCAPING": { "risk_modifier": "low_risk_service", "description": "Lawn/garden" },
    "PEST_CONTROL": { "risk_modifier": "low_risk_service", "description": "Pest management" },
    "MEDICAL": { "risk_modifier": "low_risk_service", "description": "Medical/healthcare" },
    "SECURITY": { "risk_modifier": "low_risk_service", "description": "Security services" },
    "FOOD_DELIVERY": { "risk_modifier": "low_risk_service", "description": "Food delivery apps" }
  }
}
```

### Fuzzy Matching Algorithm

Handle OCR errors and partial matches using Levenshtein distance:

```python
def match_service_provider(ocr_text: str, providers: list[Provider]) -> ServiceMatch | None:
    """Match OCR text against known service providers with fuzzy matching."""
    ocr_normalized = ocr_text.upper().strip()

    best_match = None
    best_score = 0.0

    for provider in providers:
        for alias in provider.aliases:
            # Exact match
            if ocr_normalized == alias.upper():
                return ServiceMatch(provider=provider.name, category=provider.category, confidence=1.0)

            # Fuzzy match using Levenshtein ratio
            score = levenshtein_ratio(ocr_normalized, alias.upper())
            if score >= 0.85 and score > best_score:
                best_match = provider
                best_score = score

    if best_match:
        return ServiceMatch(provider=best_match.name, category=best_match.category, confidence=best_score)

    return None
```

**Fuzzy match examples:**

- "FedE x" → FedEx (OCR space insertion)
- "AMAZ0N" → Amazon (OCR digit/letter confusion)
- "Fed Ex Ground" → FedEx (partial match)

## Confidence Thresholds

| Confidence  | Action                                             | Rationale                             |
| ----------- | -------------------------------------------------- | ------------------------------------- |
| ≥ 0.80      | Include in context, high weight                    | Reliable OCR result                   |
| 0.50 - 0.79 | Include with "uncertain" flag, attempt fuzzy match | May be valid, service match can boost |
| < 0.50      | Exclude from Nemotron context                      | Likely noise (shadows, textures)      |

**Special case:** If low-confidence text (0.50-0.79) fuzzy matches a known provider with similarity ≥0.85, boost to "include" status.

## Deduplication Strategy

Running OCR on both full frame and crops produces duplicates. Deduplication rules:

1. **Spatial overlap (IoU > 70%)** → Keep higher confidence result
2. **Similar confidence (within 0.05)** → Prefer crop over frame (higher resolution)
3. **Text association:**
   - Crop OCR text → directly associated with detection
   - Frame OCR text with bbox overlap > 50% with detection → associate with that detection
   - Frame OCR text with no detection overlap → classify as `scene_text`

## New Components

| Component                    | Location                                       | Purpose                             |
| ---------------------------- | ---------------------------------------------- | ----------------------------------- |
| `SceneOCRService`            | `backend/services/scene_ocr_service.py`        | Orchestrates full-frame + crop OCR  |
| `ServiceProviderMatcher`     | `backend/services/service_provider_matcher.py` | Fuzzy matching against curated list |
| `SERVICE_PROVIDERS`          | `backend/data/service_providers.json`          | Curated provider database           |
| `format_scene_ocr_context()` | `backend/services/prompts.py`                  | JSON formatter for Nemotron         |
| `SceneOCRResult`             | `backend/services/scene_ocr_service.py`        | Dataclass for OCR results           |

### SceneOCRService Interface

```python
@dataclass
class SceneTextResult:
    """Text detected in scene (not associated with a detection)."""
    value: str
    confidence: float
    bbox: tuple[int, int, int, int]
    text_type: str | None = None  # "house_number", "sign", "street_sign", etc.

@dataclass
class DetectionOCRResult:
    """OCR results for a specific detection."""
    detection_id: str
    texts: list[dict]  # {"value": str, "confidence": float, "region": str}
    service_match: ServiceMatch | None = None

@dataclass
class SceneOCRResult:
    """Complete OCR results for a frame."""
    scene_texts: list[SceneTextResult]
    detection_ocr: dict[str, DetectionOCRResult]  # detection_id -> results
    processing_time_ms: float = 0.0

class SceneOCRService:
    """Comprehensive scene OCR service."""

    async def process_frame(
        self,
        image: Image.Image,
        detections: list[DetectionInput],
    ) -> SceneOCRResult:
        """Run full-frame and crop OCR, deduplicate, match providers."""
        ...

    async def _run_full_frame_ocr(self, image: Image.Image) -> list[RawOCRResult]:
        """Run PaddleOCR on full frame."""
        ...

    async def _run_crop_ocr(
        self,
        image: Image.Image,
        detections: list[DetectionInput],
    ) -> dict[str, list[RawOCRResult]]:
        """Run PaddleOCR on detection crops."""
        ...

    def _deduplicate(
        self,
        frame_results: list[RawOCRResult],
        crop_results: dict[str, list[RawOCRResult]],
        detections: list[DetectionInput],
    ) -> SceneOCRResult:
        """Deduplicate and associate text with detections."""
        ...
```

## Integration with EnrichmentResult

Add new fields to `EnrichmentResult`:

```python
@dataclass
class EnrichmentResult:
    # ... existing fields ...

    # Scene OCR (new)
    scene_ocr: SceneOCRResult | None = None
```

## Prompt Formatting

New formatter function for Nemotron context:

```python
def format_scene_ocr_context(scene_ocr: SceneOCRResult) -> str:
    """Format scene OCR results as JSON for Nemotron."""
    if not scene_ocr:
        return ""

    output = {
        "scene_text": [
            {
                "value": t.value,
                "type": t.text_type,
                "confidence": t.confidence,
            }
            for t in scene_ocr.scene_texts
            if t.confidence >= 0.50
        ],
        "detection_ocr": {
            det_id: {
                "texts": result.texts,
                "service_match": asdict(result.service_match) if result.service_match else None,
            }
            for det_id, result in scene_ocr.detection_ocr.items()
        },
    }

    return json.dumps(output, indent=2)
```

## VRAM Considerations

PaddleOCR uses ~500MB VRAM in GPU mode. Current VRAM budget:

| Component             | VRAM      |
| --------------------- | --------- |
| Nemotron LLM          | 21,700 MB |
| YOLO26                | 650 MB    |
| Model Zoo (available) | ~1,650 MB |

PaddleOCR fits within Model Zoo budget. Full-frame OCR in Phase 1 runs parallel with other models that share the GPU. Crop OCR in Phase 2 reuses the loaded PaddleOCR model.

## Performance Estimates

| Operation                 | Estimated Latency |
| ------------------------- | ----------------- |
| Full frame OCR            | 50-150ms          |
| Crop OCR (per detection)  | 20-50ms           |
| Service provider matching | <5ms              |
| Deduplication             | <5ms              |

Total added latency: ~100-300ms per batch (acceptable within current 15-30s enrichment budget).

## Testing Strategy

1. **Unit tests:**

   - `test_service_provider_matcher.py` - Fuzzy matching accuracy
   - `test_scene_ocr_service.py` - Deduplication, text association
   - `test_format_scene_ocr_context.py` - JSON formatting

2. **Integration tests:**

   - Full pipeline with scene OCR enabled
   - Verify Nemotron receives formatted context

3. **Accuracy evaluation:**
   - Curate test set with known service vehicles/uniforms
   - Measure precision/recall of service provider matching

## Rollout Plan

1. **Phase 1:** Implement `SceneOCRService` and `ServiceProviderMatcher`
2. **Phase 2:** Integrate into enrichment pipeline (behind feature flag)
3. **Phase 3:** Add `format_scene_ocr_context()` and update prompts
4. **Phase 4:** Enable by default, monitor Nemotron response quality

## Success Criteria

- Service provider detection accuracy ≥90% on test set
- False positive rate (incorrect service match) <5%
- No significant latency regression (enrichment stays under 30s)
- Nemotron risk scores improve for delivery/service worker scenarios

## Open Questions

None - design is complete and ready for implementation.
