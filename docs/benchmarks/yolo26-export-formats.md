# YOLO26 Export Format Evaluation

> **Phase 1.4:** Evaluate export formats for YOLO26 deployment and recommend the best option.

**Date:** 2026-01-26
**Model Evaluated:** yolo26n.pt (Nano variant)
**Source Directory:** /export/ai_models/model-zoo/yolo26
**Export Directory:** /export/ai_models/model-zoo/yolo26/exports

## Executive Summary

This document evaluates export formats for YOLO26 deployment in the home security pipeline. Key findings:

1. **ONNX export successful** - 9.48 MB, 3.33s export time
2. **TensorRT not available** - Requires CUDA-enabled PyTorch
3. **PyTorch baseline** - 35.0ms CPU inference, 5.29 MB file size
4. **Recommendation:** Use TensorRT for production (NVIDIA), ONNX for portability

## System Information

| Component           | Value                             |
| ------------------- | --------------------------------- |
| PyTorch Version     | 2.9.1+cpu                         |
| Ultralytics Version | 8.4.7                             |
| Python Version      | 3.14.2                            |
| CPU                 | AMD Ryzen Threadripper PRO 7975WX |
| CUDA Available      | No (CPU-only PyTorch build)       |
| TensorRT Available  | No                                |

### Available Hardware (Not Used Due to CPU PyTorch)

| GPU              | VRAM      |
| ---------------- | --------- |
| NVIDIA RTX A5500 | 24564 MiB |
| NVIDIA RTX A400  | 4094 MiB  |

## Export Results

### Summary Table

| Format   | Extension         | Status     | Export Time | File Size | Relative Size |
| -------- | ----------------- | ---------- | ----------- | --------- | ------------- |
| PyTorch  | .pt               | BASELINE   | -           | 5.29 MB   | 100%          |
| ONNX     | .onnx             | SUCCESS    | 3.33s       | 9.48 MB   | 179%          |
| TensorRT | .engine           | SKIPPED    | -           | ~5-6 MB\* | ~100-110%     |
| OpenVINO | \_openvino_model/ | NOT TESTED | -           | -         | -             |

\*TensorRT size is estimated based on typical FP16 compression

### ONNX Export Details

**Export Configuration:**

```python
from ultralytics import YOLO

model = YOLO('/export/ai_models/model-zoo/yolo26/yolo26n.pt')
model.export(
    format='onnx',
    imgsz=640,
    simplify=True,
    opset=17
)
```

**Export Metrics:**

- ONNX IR Version: 8
- Opset Version: 17
- Producer: pytorch 2.9.1
- Input Shape: (1, 3, 640, 640) BCHW
- Output Shape: (1, 300, 6) - 300 detections with [x, y, w, h, conf, class]
- Export Time: 3.33s
- Simplification: Enabled

**Output Location:** `/export/ai_models/model-zoo/yolo26/exports/yolo26n.onnx`

### TensorRT Export (Reference)

TensorRT export was not performed due to CPU-only PyTorch in the development environment.

**For production deployment:**

```python
# Requires CUDA-enabled PyTorch
from ultralytics import YOLO

model = YOLO('/export/ai_models/model-zoo/yolo26/yolo26n.pt')
model.export(format='engine', imgsz=640, half=True)  # FP16 for speed
```

**TensorRT Requirements:**

- CUDA 11.8+ or 12.x
- cuDNN 8.6+
- TensorRT 8.6+ (or TensorRT 10.x for CUDA 12)
- NVIDIA GPU with compute capability 7.0+
- PyTorch with CUDA support (e.g., `torch+cu121`)

## Inference Speed Benchmarks

### Test Configuration

- Test images: 5 security camera images from `backend/tests/fixtures/images/pipeline_test/`
- Warmup runs: 3
- Timed runs: 10 per image (50 total inferences)
- Hardware: CPU only

### PyTorch Results

| Metric         | Value   |
| -------------- | ------- |
| Load Time      | 0.02s   |
| Mean Inference | 35.0 ms |
| P50 (Median)   | 34.8 ms |
| P95            | 37.2 ms |
| P99            | 43.6 ms |
| Std Dev        | 2.3 ms  |

### ONNX Results

**Not benchmarked** - ONNXRuntime does not support Python 3.14 as of January 2026.

**Expected performance** (based on Ultralytics documentation):

- CPU: ~30-40ms (similar to PyTorch)
- GPU with CUDA provider: ~10-15ms
- GPU with TensorRT provider: ~5-8ms

### Estimated GPU Performance

Based on typical RTX A5500 performance:

| Format   | Load Time | CPU Mean (ms) | GPU FP32 (ms) | GPU FP16 (ms) |
| -------- | --------- | ------------- | ------------- | ------------- |
| PyTorch  | 0.02s     | 35.0          | ~8-10         | ~4-5          |
| ONNX     | ~0.5s     | ~30-40        | ~10-15        | ~5-8          |
| TensorRT | ~2-5s     | N/A           | ~6-8          | ~3-4          |

## Detection Correctness

### Verification Status

Detection correctness verification was **not completed** due to ONNXRuntime unavailability on Python 3.14.

### Manual Verification

The ONNX export was validated by:

1. Checking file integrity and size
2. Loading with `onnx.load()` - successful
3. Verifying ONNX metadata (IR version, opset, producer)

## Recommendations

### Best Format by Use Case

| Use Case                  | Recommended Format | Reason                               |
| ------------------------- | ------------------ | ------------------------------------ |
| Production (NVIDIA GPU)   | TensorRT (.engine) | Best inference speed with FP16       |
| Cross-platform deployment | ONNX               | Wide compatibility, good performance |
| Intel hardware            | OpenVINO           | Optimized for Intel CPUs/GPUs        |
| Apple Silicon             | CoreML             | Native M1/M2/M3 support              |
| Development/debugging     | PyTorch (.pt)      | Easiest to work with                 |
| Edge devices              | ONNX or TFLite     | Smaller footprint, CPU inference     |

### For This Project (Home Security)

**Primary recommendation: TensorRT**

Given the NVIDIA RTX A5500 in the production environment:

1. **Export to TensorRT** with FP16 for optimal GPU performance
2. **Keep PyTorch** model for development and debugging
3. **Export to ONNX** as portable fallback

**Deployment configuration:**

```yaml
# docker-compose GPU configuration
ai-yolo26:
  environment:
    DETECTOR_MODEL: /models/yolo26/exports/yolo26n.engine
    DETECTOR_DEVICE: cuda:0
    DETECTOR_HALF: true
```

## Version Requirements

### For ONNX Export

| Package     | Minimum Version | Tested Version |
| ----------- | --------------- | -------------- |
| ultralytics | 8.4.0           | 8.4.7          |
| onnx        | 1.12.0          | 1.20.1         |
| onnxslim    | 0.1.71          | 0.1.82         |
| torch       | 2.0.0           | 2.9.1          |

### For TensorRT Export

| Package  | Minimum Version         |
| -------- | ----------------------- |
| torch    | 2.0.0+cu\* (CUDA build) |
| tensorrt | 8.6.0+                  |
| cuda     | 11.8+                   |
| cudnn    | 8.6+                    |

### For ONNX Inference

| Package         | Minimum Version | Python Support |
| --------------- | --------------- | -------------- |
| onnxruntime     | 1.16.0          | 3.8-3.12       |
| onnxruntime-gpu | 1.16.0          | 3.8-3.12       |

**Note:** ONNXRuntime does not support Python 3.14. Use Python 3.12 or 3.13 for ONNX inference.

## Known Limitations

1. **Python 3.14 compatibility**

   - ONNXRuntime does not support Python 3.14
   - Workaround: Use Python 3.12 or 3.13 for production inference

2. **CPU-only PyTorch in dev environment**

   - TensorRT export requires CUDA-enabled PyTorch
   - Solution: Install `torch+cu121` or `torch+cu124` for GPU support

3. **ONNX file size**
   - ONNX files are ~80% larger than PyTorch
   - This is expected due to explicit operator representation
   - TensorRT typically produces similar or smaller files after optimization

## Export Script Usage

The export script is located at `scripts/export_yolo26.py`.

### Basic Commands

```bash
# Export all formats (ONNX + TensorRT if available)
uv run python scripts/export_yolo26.py

# Export ONNX only
uv run python scripts/export_yolo26.py --format onnx

# Export specific model
uv run python scripts/export_yolo26.py --model yolo26s.pt

# Force re-export
uv run python scripts/export_yolo26.py --force

# Benchmark only (skip export)
uv run python scripts/export_yolo26.py --benchmark-only

# Skip verification
uv run python scripts/export_yolo26.py --skip-verification
```

### Output Files

- Exported models: `/export/ai_models/model-zoo/yolo26/exports/`
- Benchmark report: `docs/benchmarks/yolo26-vs-yolo26.md` (appended)
- Local report: `/export/ai_models/model-zoo/yolo26/exports/EXPORT_REPORT.md`

## Related Documentation

- [YOLO26 vs YOLO26 Accuracy Benchmark](./yolo26-vs-yolo26.md)
- [Model Zoo Benchmark](./model-zoo-benchmark.md)
- [YOLO26 Validation Report](/export/ai_models/model-zoo/yolo26/VALIDATION_REPORT.md)
