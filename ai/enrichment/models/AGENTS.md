# AI Enrichment Models

This directory contains on-demand model implementations for the ai-enrichment service. Each model is designed to be loaded lazily when needed to optimize VRAM usage.

## Directory Structure

```
models/
  __init__.py              # Package exports
  demographics.py          # Age/gender classification (existing)
  face_recognizer.py       # Face detection and recognition
  person_reid.py           # Person re-identification (existing)
  plate_ocr.py             # License plate OCR (PaddleOCR)
  pose_estimator.py        # Pose estimation (YOLOv8n-pose)
  threat_detector.py       # Threat/weapon detection
  yolo26_detector.py       # YOLO26 integration for secondary detection
```

## Model Priority Levels

Models are prioritized for VRAM allocation:

| Priority | Level | Models                       |
| -------- | ----- | ---------------------------- |
| CRITICAL | 0     | Threat detection (weapons)   |
| HIGH     | 1     | Pose, demographics, clothing |
| MEDIUM   | 2     | Vehicle, pet, re-ID          |
| LOW      | 3     | Depth, secondary detection   |

## Action Recognition — RETIRED HERE (NEM-5563)

Action recognition no longer runs in this package. The X-CLIP
`ActionRecognizer` (`action_recognizer.py`) was retired with the NEM-5563
migration to skeleton-based ST-GCN++ and now lives in
`archive/ai-enrichment/action_recognizer.py`. Its registry slot
(`action_recognizer`, ~2 GB, LOW) was removed from `model_registry.py`, and
`get_models_for_detection_type()` no longer adds it for suspicious
multi-frame persons (the `is_suspicious` / `has_multiple_frames` params are
accepted for API compatibility only).

Where action recognition runs instead:

- **Serving path**: the ai-gateway's `/action-classify` adapter
  (`ai/gateway/adapters/enrichment.py`) runs Triton **`stgcn_action`**
  (ONNX Runtime) over gateway-computed pose keypoints —
  `ai/triton/model_repository/stgcn_action/` with weights exported by
  `ai/gateway/export/export_stgcn.py`.
- **Backend local path**: `backend/services/enrichment_pipeline.py`
  `_recognize_actions_from_skeleton()`.
- No live X-CLIP code remains: the backend chain (xclip_loader +
  action_recognition_service) was archived under
  `archive/xclip-backend-chain/` with the 2026-09-23 full-removal
  ruling; models.yml keeps the `xclip-base` provenance entry (owner-owned).

## Testing

```bash
# Run unit tests for the models that live here
uv run pytest ai/enrichment/tests/test_pose_estimator.py \
              ai/enrichment/tests/test_threat_detector.py \
              ai/enrichment/tests/test_demographics.py \
              ai/enrichment/tests/test_person_reid.py \
              ai/enrichment/tests/test_plate_ocr.py -v

# Registry (9 models since the xclip action retirement)
uv run pytest ai/enrichment/tests/test_model_registry.py -v
```

The retired X-CLIP tests moved with the module to
`archive/ai-enrichment/test_action_recognizer.py` (archive is outside pytest
`testpaths`).

## Related Documentation

- [Model Zoo Design Document](../../../docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md)
- [Model Manager](../model_manager.py)
- [Model Registry](../model_registry.py)
