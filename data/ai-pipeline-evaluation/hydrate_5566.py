#!/usr/bin/env python3
"""Rewrite NEM-5566 from dead code cleanup to model activation."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

new_title = (
    "[Sprint 6] Activate dormant enrichment models (age, gender, osnet, yolo-world, smoke-fire)"
)
new_description = """**Impact:** HIGH (5 new enrichment signals for LLM risk scoring) | **Effort:** 8-16h | **Source:** Loader Audit + Activation Plan

## Overview

5 models exist on disk with production-ready loaders, model_zoo registration, and (for 4 of 5) Triton ONNX exports — but are never called in the enrichment pipeline. This task activates them.

## Model Inventory

| Model | On Disk | Loader | Model Zoo | Triton ONNX | Pipeline | VRAM |
|-------|---------|--------|-----------|-------------|----------|------|
| vit-age-classifier | `/export/ai_models/model-zoo/vit-age-classifier/` (safetensors) | `age_classifier_loader.py` ✅ | enabled=True ✅ | `demographics_age` ✅ | **NOT CALLED** | ~250MB |
| vit-gender-classifier | `/export/ai_models/model-zoo/vit-gender-classifier/` (safetensors) | `gender_classifier_loader.py` ✅ | enabled=True ✅ | `demographics_gender` ✅ | **NOT CALLED** | ~250MB |
| osnet-x0-25 | `/export/ai_models/model-zoo/osnet-x0-25/osnet_x0_25.pth` (2.5MB) | `osnet_loader.py` ✅ | enabled=True, vram_mb=100 ✅ | `reid` ONNX ✅ | **NOT CALLED** | ~100MB |
| threat-detection-yolov8n | `/export/ai_models/model-zoo/threat-detection-yolov8n/weights/best.pt` | `threat_detection_loader.py` ✅ | enabled=True, vram_mb=300 ✅ | `threat` ONNX ✅ | HTTP only (no fallback) | ~300MB |
| yolo-world-s | `/export/ai_models/model-zoo/yolo-world-s/yolov8s-worldv2.pt` | `yolo_world_loader.py` ✅ | enabled=True, vram_mb=1500 ✅ | **NO ONNX** ❌ | **NOT CALLED** | ~1.5GB |
| smoke-fire-yolov8n | **NOT ON DISK** ❌ | `smoke_fire_loader.py` ✅ | CRITICAL, preload=True, never_evict=True ✅ | **NO ONNX** ❌ | **NOT CALLED** | ~350MB |

## Phase 1: Quick Wins — Age + Gender + OSNet (2-3h)

These are lightweight, CPU-friendly models with Triton ONNX already exported.

### 1a. Wire age classification into enrichment pipeline

Add to `enrichment_pipeline.py` in the person enrichment phase (~line 3114, `_enrich_single_detection_unified`):

```python
async def _classify_person_age(self, person_crop: Image.Image, detection_id: str) -> AgeClassificationResult | None:
    try:
        async with self.model_manager.load("vit-age-classifier") as model_dict:
            return await classify_age(model_dict, person_crop)
    except Exception as e:
        logger.warning(f"Age classification failed: {e}")
        return None
```

Wire into person enrichment phase1_tasks when `detection.class_name == "person"`.

### 1b. Wire gender classification (same pattern as age)

```python
async def _classify_person_gender(self, person_crop: Image.Image) -> GenderClassificationResult | None:
    try:
        async with self.model_manager.load("vit-gender-classifier") as model_dict:
            return await classify_gender(model_dict, person_crop)
    except Exception:
        return None
```

Combine both into a demographics context string for Nemotron risk scoring.

### 1c. Wire OSNet person re-identification

```python
async def _extract_person_embedding(self, person_crop: Image.Image, detection_id: str) -> PersonEmbeddingResult | None:
    try:
        async with self.model_manager.load("osnet-x0-25") as model_dict:
            return await extract_person_embedding(model_dict, person_crop, detection_id)
    except Exception:
        return None
```

**Additional work needed:**
- Database schema for person embeddings (detection_id, embedding_vector, timestamp, camera_id)
- Cosine similarity matching logic (threshold 0.7)
- Same person on multiple cameras → escalate risk score

### 1d. Add fields to EnrichedDetection dataclass

```python
age_classification: AgeClassificationResult | None = None
gender_classification: GenderClassificationResult | None = None
person_embedding: PersonEmbeddingResult | None = None
```

### 1e. Add demographics context to Nemotron risk scoring prompt

```python
if enriched.age_classification:
    context += f"Person age group: {enriched.age_classification.age_group} "
if enriched.gender_classification:
    context += f"({enriched.gender_classification.gender}) "
```

## Phase 2: Threat Detection Fallback (1h)

Threat detection already works via HTTP service. Add direct model_manager fallback:

```python
async def _detect_threats_fallback(self, image: Image.Image) -> ThreatDetectionResult | None:
    try:
        async with self.model_manager.load("threat-detection-yolov8n") as model:
            return await detect_threats(model, image, confidence_threshold=0.25)
    except Exception:
        return None
```

Wrap existing HTTP service call (~line 4434) with fallback when service unavailable.

## Phase 3: YOLO-World Zero-Shot Detection (4-6h)

### 3a. Export to ONNX
```bash
python -c "from ultralytics import YOLOWorld; m = YOLOWorld('/export/ai_models/model-zoo/yolo-world-s/yolov8s-worldv2.pt'); m.export(format='onnx')"
```

### 3b. Create Triton config at `ai/triton/model_repository/yolo_world/config.pbtxt`

### 3c. Wire into pipeline
```python
async def _detect_custom_objects(self, image: Image.Image, prompts: list[str] | None = None) -> list[dict] | None:
    try:
        async with self.model_manager.load("yolo-world-s") as model:
            return await detect_with_prompts(model, image, prompts=prompts or SECURITY_PROMPTS, confidence_threshold=0.25)
    except Exception:
        return None
```

The loader already defines 70+ security-specific prompts organized by priority (weapons/critical, suspicious_items/high, packages/medium, etc.)

**VRAM note:** 1.5GB — use on-demand loading, don't preload.

## Phase 4: Smoke/Fire Detection — SAFETY CRITICAL (2-4h)

### 4a. Download model
Smoke-fire-yolov8n is NOT on disk. Need to download or train:
- Check HuggingFace for pretrained smoke-fire YOLOv8n weights
- Or train on public fire/smoke datasets (FIRESENSE, Bilkent fire dataset)

### 4b. Export to ONNX and create Triton config

### 4c. Wire into pipeline — run on EVERY frame (not just person detections)
```python
async def _detect_smoke_fire(self, image: Image.Image) -> SmokeFireDetectionResult | None:
    try:
        async with self.model_manager.load("smoke-fire-yolov8n") as model:
            return await detect_smoke_fire(model, image, confidence_threshold=0.5)
    except Exception:
        logger.error("Smoke/fire detection failed")
        return None
```

### 4d. Alert logic
- Fire detected → IMMEDIATE alert (risk score 100)
- Smoke detected → require 2 consecutive frames (reduce false positives from steam/fog)
- Model is marked `preload=True, never_evict=True` in model_zoo — honor this

## Also: Clean up truly dead standalone servers

The standalone AI servers (`ai/*/model.py`) are superseded by the Triton gateway. These can be archived:
- `ai/yolo26/model.py` (replaced by Triton yolo26 ONNX)
- `ai/florence/model.py` (replaced by Triton florence2 Python backend)
- `ai/clip/model.py` (replaced by Triton clip ONNX)
- `ai/enrichment/model.py` (replaced by Triton enrichment models)
- `ai/enrichment-light/model.py` (replaced by Triton enrichment models)

Keep Dockerfiles for reference but these servers are no longer deployed.

## VRAM Budget Impact

| Phase | Models | Peak VRAM Added | Loading Strategy |
|-------|--------|----------------|-----------------|
| Phase 1 | age + gender + osnet | ~600MB | Sequential via model_manager (auto-unload) |
| Phase 2 | threat fallback | 0 (already loaded via service) | Fallback only |
| Phase 3 | yolo-world | ~1.5GB | On-demand only |
| Phase 4 | smoke-fire | ~350MB | Permanent preload (CRITICAL) |

## Verification
- [ ] Each model loads without errors via model_manager
- [ ] EnrichedDetection fields populated for person detections
- [ ] Demographics context appears in Nemotron risk scoring prompts
- [ ] OSNet embeddings stored in database
- [ ] Threat detection has working fallback when service unavailable
- [ ] Smoke/fire runs on every frame
- [ ] VRAM stays within budget during batch processing

## Source
- Detailed activation plan: `data/ai-pipeline-evaluation/00-dead-loader-activation-plan.md`
- Loader audit: `data/ai-pipeline-evaluation/00-loader-audit.md`
"""

# Update NEM-5566
internal_id = client._resolve_issue_id("NEM-5566")

escaped_title = new_title.replace('"', '\\"')
escaped_desc = new_description.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

mutation = f'''
mutation {{
    issueUpdate(id: "{internal_id}", input: {{
        title: "{escaped_title}",
        description: "{escaped_desc}",
        priority: 2
    }}) {{
        success
        issue {{ identifier title url }}
    }}
}}
'''

result = client._query(mutation)
issue = result["issueUpdate"]["issue"]
print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"Updated {issue['identifier']}: {issue['title']}"
)
print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"URL: {issue['url']}"
)
