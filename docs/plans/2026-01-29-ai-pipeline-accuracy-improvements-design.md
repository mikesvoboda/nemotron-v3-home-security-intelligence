# AI Pipeline Accuracy Improvements Design

**Date:** 2026-01-29
**Status:** Draft
**Author:** Mike Svoboda + Claude

## Problem Statement

Analysis of synthetic data processing revealed that risk scores often don't match expectations due to misattribution - the LLM's reasoning references incorrect attributes from enrichment models. Root causes include:

1. **No observability** into what Nemotron actually received and responded
2. **Sequential enrichment** causing 60-120+ second latency and timeout risk
3. **Temperature inconsistency** (0.3 vs 0.7) causing score variability
4. **Batch-level household matching** bleeding context across detections
5. **Redundant embedding computation** causing latency and potential inconsistency

### Evidence

Investigation of synthetic data (delivery driver, loitering, break-in scenarios) confirmed the misattribution cascade:

```
Vision Model Misclassification
     ↓
enrichment_data contains wrong attributes
     ↓
Nemotron receives corrupted context
     ↓
LLM reasoning based on false premises
     ↓
Risk score wrong (e.g., 45 instead of 8)
```

**8 specific misattribution points identified:**

| Stage              | Example Failure                                |
| ------------------ | ---------------------------------------------- |
| Face Detection     | Side profile causes detection to fail          |
| Clothing           | "uniform" → "casual" due to fisheye distortion |
| OCR                | "AMAZON" → "AMA" if branding at angle          |
| Pose               | "bending" → "searching"                        |
| Action             | "delivering" → "suspicious rummaging"          |
| Florence Caption   | Missing objects (no package mention)           |
| Household Matching | Delivery driver matches resident at 85%        |
| Nemotron           | Missing face + partial OCR = inflated risk     |

---

## Solution Overview

Five improvements addressing observability, performance, and accuracy:

| Component                    | Change                                    | Impact                               |
| ---------------------------- | ----------------------------------------- | ------------------------------------ |
| `llm_interactions` table     | New table for prompt/response audit trail | Debug misattribution                 |
| Enrichment parallelization   | Two-phase pipeline with dynamic loading   | 60-120s → 15-30s latency             |
| Temperature alignment        | Both paths use 0.3                        | Consistent risk scores               |
| Household matching isolation | Detection-attributed context              | Correct person attribution           |
| Embedding caching            | Store in enrichment_data                  | Single computation, reuse everywhere |

---

## Detailed Design

### 1. LLM Interactions Table

**Purpose:** Capture what Nemotron received and responded for debugging accuracy issues.

**Note:** The `Event` model already stores `llm_prompt` (discovered during investigation). This table adds response storage and enrichment audit trail.

#### Schema

```sql
CREATE TABLE llm_interactions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    raw_response TEXT NOT NULL,
    enrichment_snapshot JSONB NOT NULL,
    household_matches JSONB,
    truncation_log JSONB,
    context_sources JSONB,
    validation_result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_llm_interactions_event_id ON llm_interactions(event_id);
CREATE INDEX idx_llm_interactions_created_at ON llm_interactions(created_at);
```

#### Column Definitions

| Column                | Type        | Purpose                                                |
| --------------------- | ----------- | ------------------------------------------------------ |
| `event_id`            | FK → events | Link to parent event                                   |
| `raw_response`        | TEXT        | Full LLM output including `<think>` blocks             |
| `enrichment_snapshot` | JSONB       | Frozen copy of enrichment_data at analysis time        |
| `household_matches`   | JSONB       | Person/vehicle matches with similarity scores          |
| `truncation_log`      | JSONB       | What context sections were dropped due to token limits |
| `context_sources`     | JSONB       | Which enrichment fields were populated vs empty        |
| `validation_result`   | JSONB       | Expected vs actual comparison (for synthetic data)     |
| `created_at`          | TIMESTAMP   | When analysis occurred                                 |

#### validation_result Structure

```json
{
  "passed": false,
  "scenario_id": "delivery_driver_20260125_180349",
  "checks": {
    "risk_score": {
      "expected": [0, 15],
      "actual": 45,
      "passed": false
    },
    "face_detected": {
      "expected": true,
      "actual": false,
      "passed": false
    },
    "clothing_type": {
      "expected": "uniform",
      "actual": "casual",
      "passed": false
    },
    "ocr_text": {
      "expected": ["AMAZON"],
      "actual": ["AMA"],
      "passed": false
    },
    "florence_must_contain": {
      "expected": ["person", "package"],
      "actual": ["person"],
      "missing": ["package"],
      "passed": false
    }
  }
}
```

#### SQLAlchemy Model

```python
# backend/models/llm_interaction.py
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base

class LLMInteraction(Base):
    __tablename__ = "llm_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    enrichment_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    household_matches: Mapped[dict | None] = mapped_column(JSONB)
    truncation_log: Mapped[dict | None] = mapped_column(JSONB)
    context_sources: Mapped[dict | None] = mapped_column(JSONB)
    validation_result: Mapped[dict | None] = mapped_column(JSONB)

    # Relationship
    event: Mapped["Event"] = relationship(back_populates="llm_interaction")
```

#### Usage in NemotronAnalyzer

```python
# In nemotron_analyzer.py, after LLM call completes

llm_interaction = LLMInteraction(
    event_id=event.id,
    raw_response=raw_llm_response,
    enrichment_snapshot={
        detection_id: detection.enrichment_data
        for detection in detections
    },
    household_matches={
        "persons": [
            {"detection_id": d.id, "member_name": m.name, "similarity": m.similarity}
            for d, m in person_matches
        ],
        "vehicles": [
            {"detection_id": d.id, "plate": v.plate, "description": v.description}
            for d, v in vehicle_matches
        ]
    },
    truncation_log=truncation_tracker.get_log(),
    context_sources={
        "face_detection": bool(enrichment.faces),
        "clothing": bool(enrichment.clothing),
        "ocr": bool(enrichment.license_plates),
        "pose": bool(enrichment.pose),
        "action": bool(enrichment.action),
        "florence_caption": bool(enrichment.florence_caption),
    },
    validation_result=validate_against_expected(scenario_id, event) if scenario_id else None
)
session.add(llm_interaction)
```

---

### 2. Enrichment Parallelization

**Purpose:** Reduce enrichment latency from 60-120s to 15-30s by running independent models in parallel.

#### Current Flow (Sequential)

```
License Plate Detection (2s) → OCR (1s) → Face Detection (1s) →
Face Recognition (2s) → Vehicle Classification (3s) → Clothing (2s) →
Violence (1s) → Image Quality (0.5s) → Weather (1s) →
Action Recognition (5s) → Pose (2s) → Depth (2s)

Total: ~22s per detection × 5 detections = 110s
```

#### New Flow (Two-Phase Parallel)

```
PHASE 1 (Parallel - ~8s):
┌─────────────────────────────────────────────────────────────┐
│ Face Detection ─────┐                                       │
│ License Plate ──────┤                                       │
│ Violence ───────────┤                                       │
│ Image Quality ──────┼──► asyncio.gather() ──► Phase 1 Done │
│ Weather ────────────┤                                       │
│ Clothing ───────────┤                                       │
│ Pose ───────────────┤                                       │
│ Depth ──────────────┤                                       │
│ Action Recognition ─┤                                       │
│ Vehicle Class ──────┘                                       │
└─────────────────────────────────────────────────────────────┘

PHASE 2 (After Prerequisites - ~3s):
┌─────────────────────────────────────────────────────────────┐
│ OCR (needs License Plate) ────────┐                         │
│                                   ├──► asyncio.gather()     │
│ Face Re-ID (needs Face Detection) ┘                         │
└─────────────────────────────────────────────────────────────┘

Total: ~11s per detection (vs 22s sequential)
```

#### Implementation

```python
# backend/services/enrichment_pipeline.py

async def run_enrichment_parallel(
    detections: list[Detection],
    frame: np.ndarray,
    model_manager: ModelManager,
) -> dict[int, EnrichmentData]:
    """Run enrichment models in two phases with dynamic VRAM management."""

    results = {}

    for detection in detections:
        crop = extract_crop(frame, detection.bbox)

        # Phase 1: Independent models (parallel)
        phase1_tasks = {
            "face": run_model(model_manager, "yolo11-face", crop),
            "plate": run_model(model_manager, "yolo11-license-plate", crop),
            "violence": run_model(model_manager, "violence-detection", frame),
            "quality": run_model(model_manager, "brisque-quality", frame),
            "weather": run_model(model_manager, "weather-classification", frame),
            "clothing": run_model(model_manager, "fashion-clip", crop),
            "pose": run_model(model_manager, "vitpose-small", crop),
            "depth": run_model(model_manager, "depth-anything-v2-small", frame),
            "action": run_model(model_manager, "xclip-base", [frame]),
            "vehicle": run_model(model_manager, "vehicle-segment-classification", crop),
        }

        phase1_results = await asyncio.gather(
            *phase1_tasks.values(),
            return_exceptions=True
        )
        phase1 = dict(zip(phase1_tasks.keys(), phase1_results))

        # Phase 2: Dependent models (after prerequisites)
        phase2_tasks = {}

        if phase1["plate"] and not isinstance(phase1["plate"], Exception):
            if phase1["plate"].has_detections:
                plate_crop = extract_crop(crop, phase1["plate"].bbox)
                phase2_tasks["ocr"] = run_model(model_manager, "paddleocr", plate_crop)

        if phase1["face"] and not isinstance(phase1["face"], Exception):
            if phase1["face"].has_detections:
                face_crop = extract_crop(crop, phase1["face"].bbox)
                phase2_tasks["reid"] = run_model(model_manager, "osnet-x0-25", face_crop)

        if phase2_tasks:
            phase2_results = await asyncio.gather(
                *phase2_tasks.values(),
                return_exceptions=True
            )
            phase2 = dict(zip(phase2_tasks.keys(), phase2_results))
        else:
            phase2 = {}

        # Combine results
        results[detection.id] = build_enrichment_data(phase1, phase2)

    return results


async def run_model(
    manager: ModelManager,
    model_name: str,
    input_data: Any,
) -> Any:
    """Run a single model with dynamic VRAM management."""
    try:
        async with manager.load(model_name) as model:
            return await run_inference(model, input_data)
    except Exception as e:
        logger.warning(f"Model {model_name} failed: {e}")
        return None
```

#### VRAM Management

The existing `ModelManager` handles VRAM constraints:

- Reference counting prevents premature unloading
- `asyncio.Lock` serializes load/unload operations
- Models unload when refcount reaches 0
- `torch.cuda.empty_cache()` called after unload

No additional VRAM management needed - parallel `async with manager.load()` calls naturally throttle based on available memory.

---

### 3. Temperature Alignment

**Purpose:** Ensure consistent risk scores between streaming and non-streaming analysis.

#### Current State

| File                        | Temperature | Usage              |
| --------------------------- | ----------- | ------------------ |
| `nemotron_analyzer.py:3059` | 0.3         | Standard analysis  |
| `nemotron_streaming.py:74`  | 0.7         | Streaming analysis |

#### Change

```python
# nemotron_streaming.py, line 74
# Before:
payload = {
    "prompt": prompt,
    "temperature": 0.7,  # WRONG
    ...
}

# After:
payload = {
    "prompt": prompt,
    "temperature": 0.3,  # Aligned with standard analysis
    ...
}
```

**Impact:** Streaming responses will have same consistency as non-streaming. Risk scores will be reproducible.

---

### 4. Household Matching Isolation

**Purpose:** Prevent household context from one detection influencing risk assessment of other detections in the same batch.

#### Current Problem

```
Batch contains:
  - Detection 1: Resident "Mike" arriving (matches household)
  - Detection 2: Unknown person in backyard (no match)

Current prompt:
  KNOWN PERSONS:
  - Mike (resident, 92% match)

→ Nemotron may lower risk for BOTH detections
```

#### Solution: Detection-Attributed Context

```
New prompt format:
  HOUSEHOLD MATCHES BY DETECTION:
  - Detection #1 (person, front_door, 14:32:05): KNOWN PERSON "Mike" (resident, 92% match)
  - Detection #2 (person, backyard, 14:32:08): NO MATCH
  - Detection #3 (vehicle, driveway, 14:32:10): REGISTERED VEHICLE "Honda Civic" (ABC-1234)
```

#### Implementation

```python
# backend/services/prompts.py

def format_household_context_by_detection(
    detections: list[Detection],
    person_matches: dict[int, HouseholdMatch],  # detection_id -> match
    vehicle_matches: dict[int, HouseholdMatch],
    current_time: datetime,
) -> str:
    """Format household matches attributed to specific detections."""

    lines = ["HOUSEHOLD MATCHES BY DETECTION:"]

    for detection in detections:
        det_id = detection.id
        location = detection.zone_name or "unknown"
        time_str = detection.detected_at.strftime("%H:%M:%S")
        obj_type = detection.object_type

        # Check for person match
        if det_id in person_matches:
            match = person_matches[det_id]
            lines.append(
                f"- Detection #{det_id} ({obj_type}, {location}, {time_str}): "
                f"KNOWN PERSON \"{match.member_name}\" ({match.role}, {match.similarity:.0%} match)"
            )
            if match.schedule_status:
                lines.append(f"  Schedule: {match.schedule_status}")

        # Check for vehicle match
        elif det_id in vehicle_matches:
            match = vehicle_matches[det_id]
            lines.append(
                f"- Detection #{det_id} ({obj_type}, {location}, {time_str}): "
                f"REGISTERED VEHICLE \"{match.vehicle_description}\" ({match.plate})"
            )

        # No match
        else:
            lines.append(
                f"- Detection #{det_id} ({obj_type}, {location}, {time_str}): NO MATCH"
            )

    return "\n".join(lines)
```

```python
# backend/services/household_matcher.py

async def match_detections(
    self,
    detections: list[Detection],
    enrichment_data: dict[int, EnrichmentData],
) -> tuple[dict[int, HouseholdMatch], dict[int, HouseholdMatch]]:
    """Match each detection individually, returning per-detection matches."""

    person_matches: dict[int, HouseholdMatch] = {}
    vehicle_matches: dict[int, HouseholdMatch] = {}

    for detection in detections:
        enrichment = enrichment_data.get(detection.id)
        if not enrichment:
            continue

        # Person matching
        if detection.object_type == "person" and enrichment.embeddings:
            person_embedding = enrichment.embeddings.get("person_reid")
            if person_embedding:
                match = await self._match_person_embedding(person_embedding)
                if match and match.similarity >= self.threshold:
                    person_matches[detection.id] = match

        # Vehicle matching
        elif detection.object_type in ("car", "truck", "motorcycle"):
            # Try plate match first
            if enrichment.license_plates:
                plate_text = enrichment.license_plates[0].text
                match = await self._match_vehicle_plate(plate_text)
                if match:
                    vehicle_matches[detection.id] = match
                    continue

            # Fallback to visual match
            vehicle_embedding = enrichment.embeddings.get("vehicle_visual")
            if vehicle_embedding:
                match = await self._match_vehicle_embedding(vehicle_embedding)
                if match and match.similarity >= self.threshold:
                    vehicle_matches[detection.id] = match

    return person_matches, vehicle_matches
```

---

### 5. Embedding Caching

**Purpose:** Compute embeddings once during enrichment, store in `enrichment_data`, reuse everywhere.

#### Current Problem

Same detection may have embeddings computed multiple times:

1. Enrichment pipeline computes face embedding
2. Household matching computes face embedding again
3. Entity clustering computes face embedding again
4. Re-ID service computes face embedding again

#### Solution: Store in enrichment_data

```python
# Enrichment data structure with embeddings
enrichment_data = {
    "faces": [...],
    "clothing": {...},
    "license_plates": [...],

    # NEW: Embeddings stored here
    "embeddings": {
        "person_reid": [0.123, -0.456, ...],   # 512-dim OSNet
        "face_clip": [0.789, 0.012, ...],      # 768-dim CLIP (if face detected)
        "vehicle_visual": [0.345, -0.678, ...] # 768-dim CLIP (if vehicle)
    }
}
```

#### Schema Update

```python
# backend/api/schemas/enrichment_data.py

class EmbeddingsData(BaseModel):
    """Cached embeddings for reuse across services."""

    person_reid: list[float] | None = None      # 512-dim OSNet
    face_clip: list[float] | None = None        # 768-dim CLIP
    vehicle_visual: list[float] | None = None   # 768-dim CLIP

    model_config = ConfigDict(extra="allow")


class EnrichmentData(BaseModel):
    """Complete enrichment data for a detection."""

    faces: list[FaceItem] | None = None
    license_plates: list[LicensePlateItem] | None = None
    clothing: ClothingData | None = None
    pose: PoseData | None = None
    action: ActionData | None = None
    florence_caption: FlorenceCaptionData | None = None
    image_quality: ImageQualityData | None = None

    # NEW
    embeddings: EmbeddingsData | None = None
```

#### Usage in Downstream Services

```python
# backend/services/household_matcher.py

async def match_person(self, detection: Detection) -> HouseholdMatch | None:
    """Match person using cached embedding from enrichment_data."""

    enrichment = detection.enrichment_data
    if not enrichment or not enrichment.get("embeddings"):
        return None

    # Use cached embedding instead of recomputing
    embedding = enrichment["embeddings"].get("person_reid")
    if not embedding:
        return None

    return await self._find_best_match(embedding)
```

```python
# backend/services/entity_clustering_service.py

async def find_or_create_entity(self, detection: Detection) -> Entity:
    """Find matching entity using cached embedding."""

    enrichment = detection.enrichment_data
    embedding = enrichment.get("embeddings", {}).get("person_reid")

    if not embedding:
        # Fallback: compute embedding (shouldn't happen normally)
        embedding = await self._compute_embedding(detection)

    # Use cached embedding for similarity search
    return await self._match_or_create(embedding, detection)
```

---

## Migration Plan

### Phase 1: Observability (Low Risk)

1. Create `llm_interactions` table migration
2. Add `LLMInteraction` model
3. Update `NemotronAnalyzer` to populate table
4. Deploy and validate data collection

### Phase 2: Quick Wins (Low Risk)

1. Fix temperature in `nemotron_streaming.py` (one-line change)
2. Update prompt formatting for detection-attributed household context
3. Deploy and validate consistency improvements

### Phase 3: Embedding Caching (Medium Risk)

1. Add `embeddings` field to `EnrichmentData` schema
2. Update enrichment pipeline to store embeddings
3. Update household matcher to use cached embeddings
4. Update entity clustering to use cached embeddings
5. Deploy with feature flag for gradual rollout

### Phase 4: Enrichment Parallelization (Higher Risk)

1. Refactor `EnrichmentPipeline` to two-phase architecture
2. Add comprehensive error handling for partial failures
3. Load test with synthetic data
4. Deploy with monitoring for VRAM exhaustion
5. Tune concurrency based on production metrics

---

## Testing Strategy

### Unit Tests

```python
# test_llm_interaction.py
def test_llm_interaction_captures_enrichment_snapshot():
    """Verify enrichment state is frozen at analysis time."""

def test_validation_result_structure():
    """Verify validation comparison format."""

# test_enrichment_parallel.py
def test_phase1_runs_parallel():
    """Verify independent models run concurrently."""

def test_phase2_waits_for_prerequisites():
    """Verify OCR waits for plate detection."""

def test_partial_failure_continues():
    """Verify one model failure doesn't block others."""

# test_household_matching_isolation.py
def test_matches_attributed_to_specific_detection():
    """Verify each match links to correct detection."""

def test_no_match_explicitly_stated():
    """Verify unmatched detections show NO MATCH."""
```

### Integration Tests

```python
# test_synthetic_validation.py
def test_delivery_driver_scenario():
    """Run delivery driver synthetic through pipeline, validate accuracy."""

def test_loitering_scenario():
    """Run loitering synthetic through pipeline, validate accuracy."""

def test_break_in_scenario():
    """Run break-in synthetic through pipeline, validate accuracy."""
```

### Load Tests

- Run 100 concurrent batches with parallelized enrichment
- Monitor VRAM usage and model loading/unloading
- Validate no OOM errors or deadlocks

---

## Success Metrics

| Metric                             | Current | Target                     |
| ---------------------------------- | ------- | -------------------------- |
| Enrichment latency (p50)           | 60s     | 20s                        |
| Enrichment latency (p95)           | 120s    | 40s                        |
| Risk score accuracy (synthetic)    | Unknown | 90%+ within expected range |
| Household misattribution rate      | Unknown | <1%                        |
| Debugging time for accuracy issues | Hours   | Minutes                    |

---

## Open Questions

1. **Embedding versioning:** Should we track which model version produced each embedding for reproducibility?
2. **Validation automation:** Should synthetic data validation run automatically in CI?
3. **Retention policy:** How long should `llm_interactions` records be retained?

---

## References

- Audit findings from synthetic data investigation (2026-01-29)
- Model zoo architecture: `backend/services/model_zoo.py`
- Nemotron analyzer: `backend/services/nemotron_analyzer.py`
- Enrichment pipeline: `backend/services/enrichment_pipeline.py`
- Household matcher: `backend/services/household_matcher.py`
