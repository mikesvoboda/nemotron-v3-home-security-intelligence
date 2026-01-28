# Enrichment Export Scripts

## Purpose

TensorRT export scripts for converting PyTorch AI models to optimized TensorRT engine format for 2-3x inference speedup. These scripts are used during deployment to build GPU-specific engines.

## Directory Structure

```
ai/enrichment/scripts/
├── AGENTS.md                   # This file
├── __init__.py                 # Package marker
├── export_pose_tensorrt.py     # YOLOv8n-pose to TensorRT export
└── export_threat_tensorrt.py   # Threat detector YOLOv8n to TensorRT export
```

## Key Files

### export_pose_tensorrt.py

Exports YOLOv8n-pose model to TensorRT engine for human pose estimation.

| Function             | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| `check_requirements` | Verify CUDA, TensorRT, ultralytics installed    |
| `get_default_model_path` | Get path from POSE_MODEL_PATH env var       |
| `get_default_output_path` | Generate .engine path from .pt path        |
| `export_to_tensorrt` | Main export function using Ultralytics export   |
| `benchmark_engines`  | Compare PyTorch vs TensorRT inference speed     |
| `main`               | CLI entry point with argparse                   |

**Usage:**
```bash
# Export with default settings (FP16 precision)
python export_pose_tensorrt.py

# Export with custom model path
python export_pose_tensorrt.py --model /path/to/yolov8n-pose.pt

# Export with FP32 precision
python export_pose_tensorrt.py --precision fp32

# Export and benchmark
python export_pose_tensorrt.py --benchmark

# Specify GPU device
python export_pose_tensorrt.py --device 0
```

**Environment Variables:**
- `POSE_MODEL_PATH`: Default input model path
- `POSE_TENSORRT_ENGINE_PATH`: Custom output engine path

### export_threat_tensorrt.py

Exports threat detection YOLOv8n model to TensorRT engine for weapon/dangerous object detection.

| Function             | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| `check_cuda_available` | Verify CUDA GPU is available                  |
| `export_to_tensorrt` | Main export with Ultralytics native export      |
| `benchmark_engine`   | Benchmark TensorRT vs PyTorch with timing       |
| `verify_engine`      | Compare detection results between backends      |
| `main`               | CLI entry point                                 |

**Usage:**
```bash
# Export with FP16 precision (recommended)
python export_threat_tensorrt.py --model /path/to/best.pt --precision fp16

# Export with dynamic batch support
python export_threat_tensorrt.py --model /path/to/best.pt --dynamic-batch --max-batch 8

# Benchmark the exported engine
python export_threat_tensorrt.py --model /path/to/best.pt --benchmark

# Full pipeline: export, verify, benchmark
python export_threat_tensorrt.py --model /path/to/best.pt --verify --benchmark
```

**Environment Variables:**
- `THREAT_MODEL_PATH`: Default model path if --model not specified
- `THREAT_TENSORRT_WORKSPACE_GB`: TensorRT workspace size (default: 2GB)

## CLI Options

### Common Options (both scripts)

| Flag         | Description                                    |
| ------------ | ---------------------------------------------- |
| `--model`    | Path to PyTorch .pt model file                 |
| `--output`   | Output .engine file path                       |
| `--precision`| fp16 (default) or fp32                         |
| `--device`   | CUDA device index (default: 0)                 |
| `--benchmark`| Run benchmark after export                     |

### export_pose_tensorrt.py Specific

| Flag          | Description                                   |
| ------------- | --------------------------------------------- |
| `--workspace` | TensorRT workspace size in GB (default: 4)    |
| `--verbose`   | Enable verbose logging during export          |
| `--check-only`| Only check requirements, don't export         |

### export_threat_tensorrt.py Specific

| Flag                  | Description                               |
| --------------------- | ----------------------------------------- |
| `--workspace`         | Workspace size in GB (default: 2)         |
| `--input-size`        | Input image size (default: 640)           |
| `--dynamic-batch`     | Enable dynamic batch sizes                |
| `--max-batch`         | Max batch size for dynamic batching       |
| `--verify`            | Verify TensorRT accuracy against PyTorch  |
| `--benchmark-iterations` | Number of benchmark iterations (default: 100) |

## TensorRT Engine Notes

**GPU Architecture Specificity:**
TensorRT engines are compiled for a specific GPU architecture (SM version). An engine built on RTX 3090 (SM 8.6) will not work on RTX 4090 (SM 8.9). Always rebuild engines on the target GPU.

**Precision Trade-offs:**
| Precision | Accuracy Impact | Speed Improvement | Memory Reduction |
| --------- | --------------- | ----------------- | ---------------- |
| FP32      | None            | 1.5-2x            | 0%               |
| FP16      | Minimal (<1%)   | 2-4x              | ~50%             |

**Output Location:**
Engines are created adjacent to the .pt file or in a custom location:
- `/models/yolov8n-pose.pt` -> `/models/yolov8n-pose.engine`
- With --output: custom path specified

## Requirements

- NVIDIA GPU with CUDA support
- TensorRT installed (`pip install tensorrt`)
- Ultralytics package (`pip install ultralytics`)
- PyTorch with CUDA support

## Entry Points

1. **Pose export**: `python export_pose_tensorrt.py`
2. **Threat export**: `python export_threat_tensorrt.py`
3. **Parent module**: `ai/enrichment/AGENTS.md`
4. **Model implementations**: `ai/enrichment-light/models/`

## Related Documentation

- TensorRT infrastructure: `ai/common/AGENTS.md`
- Pose estimator model: `ai/enrichment-light/models/pose_estimator.py`
- Threat detector model: `ai/enrichment-light/models/threat_detector.py`
- Ultralytics export docs: https://docs.ultralytics.com/modes/export/
