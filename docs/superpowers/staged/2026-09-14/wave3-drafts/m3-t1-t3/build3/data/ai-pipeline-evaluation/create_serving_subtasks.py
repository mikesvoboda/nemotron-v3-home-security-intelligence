#!/usr/bin/env python3
"""Create Linear subtasks for model serving optimization findings."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

EPIC = "NEM-5537"

subtasks = [
    {
        "title": "[Sprint 3] Implement model cascading — skip enrichment for empty frames (80-90% compute reduction)",
        "priority": 1,  # Urgent
        "description": """**Impact:** CRITICAL (80-90% compute reduction) | **Effort:** 2-3 days | **Source:** Model Serving Optimization Research (Report 08)

## The Insight
In home security, **80-95% of frames are empty** (no detections). Currently the pipeline processes every frame through enrichment models regardless. Cascading means: only run enrichment models when YOLO actually detects something.

## Current Flow (wasteful)
```
Frame → YOLO → enrichment (runs on ALL frames) → LLM
```

## Proposed Flow (cascading)
```
Frame → YOLO → if detections > 0 → enrichment → LLM
              → if detections == 0 → skip (save 80-95% of enrichment compute)
```

## Implementation Levels

### Level 1: Basic cascade (highest impact, easiest)
Skip ALL enrichment when YOLO returns zero detections.

### Level 2: Adaptive frame processing
Add background subtraction to reduce YOLO invocations:
- During quiet periods: reduce from 15 FPS to 1-2 FPS
- On motion detected: ramp back up to full FPS
- Expected: 70-80% reduction in YOLO calls during quiet hours

### Level 3: Confidence-based deferral
Only call expensive models (Florence-2, X-CLIP/ST-GCN++) for ambiguous detections:
- High confidence person (>0.8): skip Florence-2 captioning, go straight to LLM
- Low confidence detection (<0.5): run Florence-2 for disambiguation
- Expected: 60-80% reduction in Florence-2 invocations

## Where to Implement
- `backend/services/enrichment_pipeline.py` — main orchestration point
- Gateway adapter level — could short-circuit at Triton gateway
- Triton BLS (Business Logic Scripting) — implement cascade within Triton itself, eliminating HTTP round-trips

## Verification
- Count enrichment model invocations per hour before/after
- Compare event processing latency
- Ensure no detections are missed (cascade only skips when YOLO returns empty)
""",
    },
    {
        "title": "[Sprint 3] Configure Triton rate limiter for GPU memory budgeting",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (prevents OOM, better GPU scheduling) | **Effort:** 4-8h | **Source:** Model Serving Optimization Research (Report 08)

## What
Triton's rate limiter enables cross-model GPU memory budgeting with priority-based scheduling. This prevents OOM when multiple GPU models run concurrently.

## Current Problem
Three GPU models (yolo26, clip, florence2) can potentially execute concurrently on the A400 (4GB). Without rate limiting, concurrent execution can exceed VRAM.

## Configuration
Add to each GPU model's `config.pbtxt`:

```protobuf
# yolo26 — highest priority (critical path)
model_transaction_policy {
  decoupled: false
}
rate_limiter {
  resources [
    { name: "GPU_MEMORY" count: 1 }
  ]
  priority: 1  # Highest
}

# clip — medium priority
rate_limiter {
  resources [
    { name: "GPU_MEMORY" count: 1 }
  ]
  priority: 2
}

# florence2 — lower priority (can wait)
rate_limiter {
  resources [
    { name: "GPU_MEMORY" count: 1 }
  ]
  priority: 3
}
```

## Also: Dynamic model loading (EXPLICIT mode)
Florence-2 is used intermittently. Configure Triton model control to unload Florence-2 when idle, freeing ~460MB VRAM for other models.

## References
- [Triton Rate Limiter](https://github.com/triton-inference-server/server/blob/main/docs/user_guide/rate_limiter.md)
- [Triton Model Management](https://github.com/triton-inference-server/server/blob/main/docs/user_guide/model_management.md)
""",
    },
    {
        "title": "[Sprint 3] Apply INT8 dynamic quantization to all CPU ONNX models",
        "priority": 2,  # High
        "description": """**Impact:** HIGH (20-40% CPU speedup, 75% memory reduction) | **Effort:** 1-2 days | **Source:** Model Serving Optimization Research (Report 08)

## What
Apply ONNX Runtime dynamic INT8 quantization to all 10 CPU-bound Triton models. Dynamic quantization requires zero calibration data.

## Target Models
All CPU ONNX models in Triton:
- fashion_clip (372MB)
- demographics_age (344MB)
- demographics_gender (344MB)
- depth (101MB)
- vehicle (94MB)
- pet (45MB)
- pose (14MB)
- threat (12MB)
- reid (1.5MB)

## Implementation
```python
from onnxruntime.quantization import quantize_dynamic, QuantType

for model_dir in triton_cpu_models:
    quantize_dynamic(
        model_input=f"{model_dir}/1/model.onnx",
        model_output=f"{model_dir}/1/model_int8.onnx",
        weight_type=QuantType.QInt8,
    )
```

Then update each model's config.pbtxt to load the quantized version.

## Expected Impact
- **20-40% faster CPU inference** per model
- **~75% memory reduction** for model weights
- Zero accuracy loss for most models (dynamic quant only affects weights, not activations)

## Also: Enable ORT graph optimization
Add to Triton ONNX Runtime session config:
```
optimization {
  graph {
    level: 99  # ORT_ENABLE_ALL
  }
}
```
This enables constant folding, redundant node elimination, and operator fusion. 10-30% additional speedup.
""",
    },
    {
        "title": "[Sprint 3] Evaluate OpenVINO EP for CPU models (if Intel CPU)",
        "priority": 3,  # Medium
        "description": """**Impact:** MEDIUM (1.3-2x CPU speedup) | **Effort:** 4-8h | **Source:** Model Serving Optimization Research (Report 08)

## What
If the host has an Intel CPU, switching Triton's ONNX Runtime backend from default CPU EP to OpenVINO EP yields 1.3-2x speedup for ViT, ResNet, and YOLO models. This is a configuration-only change.

## Prerequisite
Check CPU: `lscpu | grep "Model name"`
- If Intel: OpenVINO EP is beneficial
- If AMD: Stick with default ONNX Runtime CPU EP

## Configuration
Update Triton model config for CPU models:
```protobuf
optimization {
  execution_accelerators {
    cpu_execution_accelerator: [{
      name: "openvino"
    }]
  }
}
```

## References
- [Triton ONNX Runtime OpenVINO](https://github.com/triton-inference-server/onnxruntime_backend#openvino)
""",
    },
]

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"Creating {len(subtasks)} model serving optimization subtasks under {EPIC}...\n"
)

for task in subtasks:
    result = client.create_subtask(
        parent_identifier=EPIC,
        title=task["title"],
        description=task["description"],
        priority=task["priority"],
        status="backlog",
    )
    issue = result["issue"]
    print(  # noqa: T201 # noqa: T201
        f"  Created {issue['identifier']}: {task['title'][:72]}"
    )

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"\nDone! Epic {EPIC} updated."
)
