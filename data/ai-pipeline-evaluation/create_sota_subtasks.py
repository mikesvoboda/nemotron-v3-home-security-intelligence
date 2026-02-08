#!/usr/bin/env python3
"""Create Linear subtasks for SOTA model upgrades and additions."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

EPIC = "NEM-5537"

# First, update the 3 existing Sprint 6 evaluation tasks with corrected recommendations

updates = [
    # NEM-5561: SigLIP 2 — hydrate with ONNX availability
    {
        "id": "NEM-5561",
        "title": "[Sprint 6] Replace CLIP ViT-L with SigLIP 2 Base (-1,035MB VRAM)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (-1,035MB VRAM, better accuracy) | **Effort:** 4-8h | **Source:** SOTA Vision Models Research (Report 07)

## Change
Replace CLIP ViT-L (1.2GB) with SigLIP 2 Base ViT-B/16-224 (165MB FP16).

## Why This Is Ready Now
- **Pre-converted ONNX weights already exist**: `onnx-community/siglip2-base-patch16-224-ONNX` on HuggingFace
- Apache 2.0 license (commercial use OK)
- 7x smaller than current CLIP ViT-L
- SigLIP 2 outperforms original SigLIP at all scales with improved localization and dense features
- Multilingual support (bonus for international deployment)

## VRAM Savings
```
Current:  CLIP ViT-L    = 1,200 MB
Proposed: SigLIP 2 Base =   165 MB (FP16)
Savings:                  1,035 MB
```

## Implementation Steps

### 1. Download ONNX model
```bash
# From HuggingFace
huggingface-cli download onnx-community/siglip2-base-patch16-224-ONNX --local-dir /export/ai_models/model-zoo/siglip2-base
```

### 2. Update Triton model config
Replace `ai/triton/model_repository/clip/` config to load SigLIP 2 ONNX instead of CLIP ViT-L ONNX.

### 3. Update gateway adapter
Update `ai/gateway/adapters/clip.py` preprocessing to match SigLIP 2 input format (224x224, different normalization).

### 4. Update backend CLIP client
The embedding dimensionality may differ (CLIP ViT-L = 768-dim, SigLIP 2 Base = 768-dim). Verify compatibility.

### 5. Benchmark
- Compare embedding quality on security camera person/vehicle re-identification
- Compare zero-shot classification accuracy
- Measure inference latency

## Runner-ups
- **DINOv2-Small** (42MB FP16, ONNX available) — if text matching not needed, pure visual features
- **MobileCLIP-S2** (~400MB) — if latency is critical, 2.3x faster inference

## References
- [SigLIP 2 ONNX](https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX)
- [SigLIP 2 blog](https://huggingface.co/blog/siglip2)
""",
    },
    # NEM-5562: ReID — update from ReIDMamba to OSNet-AIN x1.0
    {
        "id": "NEM-5562",
        "title": "[Sprint 6] Upgrade OSNet x0.25 to OSNet-AIN x1.0 (4x accuracy, ONNX ready)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (4x accuracy improvement) | **Effort:** 2-4h | **Source:** SOTA Vision Models Research (Report 07)

## Change
Replace OSNet x0.25 (2019, low accuracy) with OSNet-AIN x1.0 (verified ONNX, 4x better accuracy).

## Why OSNet-AIN x1.0 over ReIDMamba
The original recommendation was ReIDMamba, but research found:
- ReIDMamba is research-only (Nov 2025 arxiv), unknown license, untested ONNX export
- OSNet-AIN x1.0 has **verified ONNX weights** (`osnet_ain_x1_0_msmt17.onnx`)
- Same architecture family as current OSNet x0.25 (drop-in upgrade)
- MIT license, production-ready
- MSMT17 pretraining provides better cross-domain generalization for outdoor security cameras

## Performance
| Model | Market1501 R1 | Market1501 mAP | Size | ONNX |
|-------|--------------|----------------|------|------|
| OSNet x0.25 (current) | ~85% | ~70% | 2.5MB | Yes |
| **OSNet-AIN x1.0** | ~95% | ~86% | 9MB | **Yes (verified)** |

## Implementation Steps

### 1. Download ONNX model
```bash
# From torchreid / deep-person-reid
# Export or download osnet_ain_x1_0_msmt17.onnx
```

### 2. Update Triton model config
Replace `ai/triton/model_repository/reid/` model with OSNet-AIN x1.0 ONNX.

### 3. Update loader
Update `backend/services/osnet_loader.py` model path and verify input dimensions match (256x128).

### 4. Verify embedding compatibility
OSNet-AIN x1.0 produces 512-dim embeddings (same as x0.25). Existing matching logic should work.

## Dark Horse: Pose2ID (CVPR 2025)
Training-free ReID using pose keypoints from existing YOLOv8n-Pose. Zero additional VRAM. Worth prototyping alongside this upgrade.

## References
- [deep-person-reid (torchreid)](https://github.com/KaiyangZhou/deep-person-reid)
- [Pose2ID (CVPR 2025)](https://github.com/yuanc3/Pose2ID)
""",
    },
    # NEM-5563: X-CLIP replacement — update to ST-GCN++
    {
        "id": "NEM-5563",
        "title": "[Sprint 6] Replace X-CLIP with ST-GCN++ skeleton action recognition (-1,986MB VRAM)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (-1,986MB VRAM, reuses existing pose model) | **Effort:** 8-16h | **Source:** SOTA Vision Models Research (Report 07)

## Change
Replace X-CLIP Base (~2GB, requires 16 video frames) with ST-GCN++ (~14MB, uses pose keypoints).

## Key Insight
The pipeline already runs **YOLOv8n-Pose** which extracts 17 COCO keypoints per person. ST-GCN++ takes these keypoints as input — no image processing needed. This turns a 2GB video model into a 14MB skeleton classifier.

## VRAM Savings
```
Current:  X-CLIP Base Patch32 = 2,000 MB (+ cannot export to ONNX)
Proposed: ST-GCN++ (PYSKL)   =    14 MB (ONNX exportable)
Savings:                       1,986 MB
```

## Architecture
```
YOLOv8n-Pose (already running, ~200MB shared)
    ↓ extracts 17 keypoints per person per frame
Buffer 30-60 frames of keypoints per tracked person (~minimal memory)
    ↓
ST-GCN++ classifies keypoint sequence into actions (~14MB)
    ↓
Actions: fighting, falling, running, loitering, normal walking
```

## Implementation Steps

### 1. Install PYSKL / ST-GCN++
```bash
pip install pyskl  # or clone from github.com/kennymckormick/pyskl
```

### 2. Export to ONNX
ST-GCN++ supports ONNX export (opset 12+, requires 5D tensor handling).

### 3. Create keypoint buffer
Buffer 30-60 frames of pose keypoints per tracked person_id in the enrichment pipeline.

### 4. Classify actions
Feed buffered keypoint sequences to ST-GCN++ for action classification.

### 5. Wire into pipeline
Replace X-CLIP calls in `enrichment_pipeline.py` and `action_recognition_service.py` with ST-GCN++ skeleton-based classification.

### 6. Fine-tune for security actions
Fine-tune on NTU-RGB+D mutual actions subset + UCF-Crime skeleton data for:
- Fighting / violence
- Falling (elderly safety)
- Running (fleeing)
- Loitering (suspicious)
- Normal walking (baseline)

## For Violence Detection Specifically
ESTS-GCN paper shows skeleton GCNs achieve strong violence detection results. Consider combining ST-GCN++ with ESTS-GCN violence-specific head.

## References
- [PYSKL (ST-GCN++)](https://github.com/kennymckormick/pyskl)
- [MMAction2 skeleton models](https://mmaction2.readthedocs.io/en/latest/model_zoo/skeleton.html)
- [ESTS-GCN for violence](https://onlinelibrary.wiley.com/doi/10.1155/2024/2323337)
""",
    },
]

# New subtasks
new_subtasks = [
    {
        "title": "[Sprint 6] Add Zero-DCE++ night vision preprocessing (40KB, 1000 FPS)",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (5-15% better night detection) | **Effort:** 2-4h | **Source:** SOTA Vision Models Research (Report 07)

## What
Add Zero-DCE++ as a preprocessing step for low-light frames before YOLO detection.

## Why This Is Essentially Free
- **10K parameters, ~40KB model size**
- Runs at **1000 FPS on GPU** — adds <1ms latency per frame
- No reference images needed (unsupervised curve estimation)
- BSD-3-Clause license

## Implementation
1. Download from [Zero-DCE](https://github.com/Li-Chongyi/Zero-DCE)
2. Export to ONNX (~40KB)
3. Deploy as Triton model or in-process preprocessor
4. Apply conditionally:
   - During night hours (configurable schedule)
   - OR when BRISQUE quality score indicates low quality (already running in pipeline)
5. Feed enhanced frames to YOLO26 for detection

## Expected Impact
- 5-15% improved detection accuracy in low-light conditions
- Better person/vehicle detection from night-time security cameras
- Near-zero computational overhead

## Alternative
If Zero-DCE++ quality is insufficient: **Retinexformer** (~6MB, ICCV 2023, MIT license) provides SOTA quality.

## References
- [Zero-DCE](https://github.com/Li-Chongyi/Zero-DCE)
- [Retinexformer](https://github.com/caiyuanhao1998/Retinexformer)
""",
    },
    {
        "title": "[Sprint 6] Add Anomalib PatchCore for scene anomaly detection (~100MB)",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (new capability) | **Effort:** 8-16h | **Source:** SOTA Vision Models Research (Report 07)

## What
Add scene-level anomaly detection using Anomalib PatchCore. Train on "normal" camera views to detect deviations (unusual objects, tampered cameras, structural changes).

## Why Anomalib
- Production-grade library from Intel's Open Edge Platform
- Built-in ONNX and OpenVINO export
- Apache 2.0 license
- Designed for edge deployment
- ~50-200MB depending on backbone

## Implementation Strategy (Two-Pronged)

### Approach A: Skeleton-based (zero VRAM)
Use ST-GCN++ action classification (if implemented from NEM-5563) + LLM reasoning for behavioral anomaly detection. No additional model needed.

### Approach B: Anomalib PatchCore (~100MB)
1. Install: `pip install anomalib`
2. Train PatchCore on "normal" camera views (requires collecting ~100 normal frames per camera)
3. Export to ONNX
4. Deploy to Triton (CPU backend)
5. Score each frame for anomaly — high scores trigger additional enrichment

## Use Cases
- Unusual objects appearing in scene (abandoned packages)
- Camera tampering (view obstruction, angle change)
- Structural changes (broken fence, open gate)
- Unexpected scene activity patterns

## References
- [Anomalib](https://github.com/open-edge-platform/anomalib)
- [GiCiSAD (WACV 2025)](https://arxiv.org/abs/2403.12172)
""",
    },
    {
        "title": "[Sprint 6] Evaluate FastALPR as PaddleOCR replacement for plate recognition (-372MB)",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (-372MB, better accuracy) | **Effort:** 4-8h | **Source:** SOTA Vision Models Research (Report 07)

## What
Replace current yolo11-license-plate + PaddleOCR (~400MB) with FastALPR (~28MB total).

## FastALPR Details
- `yolo-v9-t-384-license-plate-end2end` detector + `cct-xs-v1-global-model` OCR
- **Native ONNX support** (ONNX by default)
- 28MB total vs current ~400MB
- MIT license
- 98.15% accuracy (EU), 95.61% (BR)

## Immediate Quick Win
Even without full FastALPR migration, `fast-plate-ocr` CCT-XS model (~8MB) is a drop-in PaddleOCR replacement at 1/12th the size.

## Implementation
1. `pip install fast-alpr`
2. Benchmark against current pipeline on test plates
3. If better: replace PaddleOCR with fast-plate-ocr in plate recognition pipeline
4. Export models to ONNX for Triton deployment

## References
- [FastALPR](https://github.com/ankandrew/fast-alpr)
- [fast-plate-ocr](https://github.com/ankandrew/fast-plate-ocr)
""",
    },
]

# --- Execute updates ---
print(  # noqa: T201 # noqa: T201 # noqa: T201
    "Updating 3 existing subtasks with SOTA findings...\n"
)

for update in updates:
    internal_id = client._resolve_issue_id(update["id"])
    escaped_title = update["title"].replace('"', '\\"')
    escaped_desc = (
        update["description"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )

    mutation = f'''
    mutation {{
        issueUpdate(id: "{internal_id}", input: {{
            title: "{escaped_title}",
            description: "{escaped_desc}",
            priority: {update["priority"]}
        }}) {{
            success
            issue {{ identifier title }}
        }}
    }}
    '''
    try:
        result = client._query(mutation)
        issue = result["issueUpdate"]["issue"]
        print(  # noqa: T201 # noqa: T201
            f"  Updated {issue['identifier']}: {issue['title'][:70]}"
        )
    except Exception as e:
        print(  # noqa: T201 # noqa: T201
            f"  FAILED {update['id']}: {e}"
        )

# --- Create new subtasks ---
print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"\nCreating {len(new_subtasks)} new subtasks under {EPIC}...\n"
)

for task in new_subtasks:
    result = client.create_subtask(
        parent_identifier=EPIC,
        title=task["title"],
        description=task["description"],
        priority=task["priority"],
        status="backlog",
    )
    issue = result["issue"]
    print(  # noqa: T201 # noqa: T201
        f"  Created {issue['identifier']}: {task['title'][:70]}"
    )

print(  # noqa: T201 # noqa: T201 # noqa: T201
    "\nDone!"
)
