# YOLO26 Package

## Purpose

**Pure-leaf contract home for backend prompt-building** — since the 2026-09-23
retirement of the standalone GPU image, this package's load-bearing live role
is `contract.py`: `backend/services/prompts.py::format_detections_with_quality()`
imports `ConfidenceQuality` / `EnhancedDetection` / `enhance_detections` from
`ai.yolo26.contract` at call time (stdlib + pydantic only, zero torch — see the
module docstring; parity is pinned by `backend/tests/unit/services/test_prompts.py`).

**Retired 2026-09-23 (owner ruling): the standalone `ai-yolo26` GPU image.**
Production detection is served by Triton inside the `ai-gateway` container
(FastAPI router prefix `/yolo26` on port 8090; yolo26 is one of the 14 served
models — see `ai/gateway/AGENTS.md` and `ai/gateway/adapters/yolo26.py`).
The compose stack has no `ai-yolo26` service and no CI or deploy job builds the
image any more. The serving build recipe, `requirements.txt`, `export_tensorrt.py`
and the era's `README.md` are archived at
`archive/ai-yolo26-image/` (`Dockerfile` there keeps the full build recipe for
reference; the earlier benchmark image is `archive/Dockerfile.yolo26-benchmark`).

## What Stays Here (and Why)

```
ai/yolo26/
├── AGENTS.md            # This file
├── __init__.py          # Package init
├── contract.py          # LIVE: pure-leaf import by backend prompt-building
├── model.py             # Kept: AI-contract conformance tests AST-read it
│                        #   (SECURITY_CLASSES, _DEFAULT_CLASS_CONFIDENCE_THRESHOLDS,
│                        #   /track deletion markers - see backend/tests/contracts/
│                        #   ai_providers/) + host-run dev server
├── metrics.py           # Kept: imported by model.py (and its test battery)
├── pose_estimation.py   # Kept: conformance tests AST-read KEYPOINT_NAMES /
│                        #   classify_pose (test_conformance_semantics.py,
│                        #   test_conformance_dbvocabulary.py)
├── security.py          # Kept: model.py flat-imports it
├── build_engine.py      # Kept: model.py imports it; scripts/prebuild-tensorrt-engines.sh
│                        #   invokes it for host-side engine builds
├── test_model.py        # Server test battery (imports model.py)
└── tests/               # Unit test battery - see tests/AGENTS.md
```

`model.py` remains runnable as a **host-run dev server** (`./ai/start_detector.sh`,
port 8090 via `YOLO26_PORT`) as a stand-in for the gateway's `/yolo26` router
while debugging — that path never used the retired image. Its GPU dependencies
(torch/ultralytics) are not installed for the backend CI tier, which is why
`prompts.py` imports the leaf `contract.py`, never `model.py`.

## Directory Contents

```
ai/yolo26/
├── AGENTS.md            # This file
├── __init__.py          # Package init
├── build_engine.py      # TensorRT engine builder (host CLI + model.py)
├── contract.py          # Pure-leaf detection-quality contract
├── metrics.py           # Prometheus metrics definitions (legacy server)
├── model.py             # FastAPI dev server (contract seam + security classes)
├── pose_estimation.py   # Pose/behavior estimation module
├── security.py          # Path-security validation helpers
├── test_model.py        # Flat-import server test battery
└── tests/               # Unit tests - see tests/AGENTS.md
```

## The contract.py Seam

`contract.py` defines `ConfidenceQuality`, `SpatialContext`, `EnhancedDetection`,
`compute_confidence_quality()`, `compute_spatial_context()`, `enhance_detections()`
and `get_confidence_explanation()`. `model.py` imports the same seven names
(`from contract import ...` via its `_here_dir` sys.path shim), so the repo,
the host-run dev server, and the backend all share ONE definition.
`ai/yolo26/tests/test_model.py::TestContractSeam` ratchets that identity
repo-side; the container-side half of that proof retired with the image
(the former `ai-yolo26-image-smoke` CI job).

## Historical Server Documentation

The retired server's API surface (`/health`, `/detect`, `/detect/batch`),
environment variables, TensorRT fallback behavior, and metrics tables are
documented in the archived `archive/ai-yolo26-image/README.md` and in this
file's git history (pre-2026-09-23 revisions). Production request shapes are
owned by the gateway adapter contract
(`backend/ai_contract/operations.py`, 37 operations).

## Entry Points

1. **Backend consumers**: `backend/services/prompts.py` (runtime import of the
   contract seam) — parity-tested by `backend/tests/unit/services/test_prompts.py`
2. **Gateway serving path**: `ai/gateway/adapters/yolo26.py` (Triton-backed `/yolo26` router)
3. **Host-run dev server**: `ai/start_detector.sh` → `model.py`
4. **Conformance reads**: `backend/tests/contracts/ai_providers/` (AST-pinned tables
   in `model.py` and `pose_estimation.py`)
