# YOLO26 Performance Benchmarks

> Comprehensive performance benchmarks for YOLO26 object detection in Home Security Intelligence.

This document provides detailed performance metrics for YOLO26 variants used in the detection pipeline. For the auto-generated benchmark results, see [yolo26-benchmarks.md](../../benchmarks/yolo26-benchmarks.md).

---

## Executive Summary

YOLO26 is the sole object detection model in the Home Security Intelligence pipeline. It offers excellent performance for real-time security monitoring with multiple variants optimized for different use cases.

### Key Performance Metrics

| Metric             | yolo26n | yolo26s | yolo26m (default) |
| ------------------ | ------- | ------- | ----------------- |
| **Inference Time** | 5-6ms   | 10-12ms | 15-20ms           |
| **FPS (TensorRT)** | 170-200 | 85-100  | 50-70             |
| **VRAM Usage**     | ~100 MB | ~150 MB | ~200 MB           |
| **mAP@50 (COCO)**  | 37.8%   | 44.3%   | 50.9%             |
| **Parameters**     | 2.57M   | 10.01M  | 21.90M            |

---

## Model Variants

### yolo26n (Nano)

Best for: Edge devices, maximum throughput, resource-constrained environments.

| Specification  | Value                                   |
| -------------- | --------------------------------------- |
| **Parameters** | 2.57M                                   |
| **Model Size** | 5.3 MB (FP32), 2.7 MB (FP16)            |
| **Inference**  | 5-6ms @ 640x640 (TensorRT FP16)         |
| **Throughput** | 170-200 FPS                             |
| **VRAM**       | ~100 MB                                 |
| **mAP@50**     | 37.8%                                   |
| **Best For**   | High-volume, multi-camera, edge devices |

### yolo26s (Small)

Best for: Balanced speed and accuracy, standard deployments.

| Specification  | Value                                   |
| -------------- | --------------------------------------- |
| **Parameters** | 10.01M                                  |
| **Model Size** | 19.5 MB (FP32), 9.8 MB (FP16)           |
| **Inference**  | 10-12ms @ 640x640 (TensorRT FP16)       |
| **Throughput** | 85-100 FPS                              |
| **VRAM**       | ~150 MB                                 |
| **mAP@50**     | 44.3%                                   |
| **Best For**   | Standard security cameras, balanced use |

### yolo26m (Medium) - Default

Best for: High accuracy requirements, fewer cameras.

| Specification  | Value                             |
| -------------- | --------------------------------- |
| **Parameters** | 21.90M                            |
| **Model Size** | 42.2 MB (FP32), 21.1 MB (FP16)    |
| **Inference**  | 15-20ms @ 640x640 (TensorRT FP16) |
| **Throughput** | 50-70 FPS                         |
| **VRAM**       | ~200 MB                           |
| **mAP@50**     | 50.9%                             |
| **Best For**   | Maximum detection accuracy        |

---

## Accuracy Benchmarks

### Detection Accuracy by Class

Performance on security-relevant COCO classes:

| Class      | yolo26n | yolo26s | yolo26m |
| ---------- | ------- | ------- | ------- |
| person     | 52.1%   | 58.4%   | 63.2%   |
| car        | 48.3%   | 54.7%   | 60.1%   |
| truck      | 41.2%   | 47.8%   | 53.4%   |
| dog        | 45.6%   | 51.2%   | 56.8%   |
| cat        | 44.8%   | 50.5%   | 55.9%   |
| bird       | 38.2%   | 44.1%   | 49.7%   |
| bicycle    | 39.7%   | 45.9%   | 51.3%   |
| motorcycle | 42.4%   | 48.6%   | 54.2%   |
| bus        | 54.1%   | 60.3%   | 65.8%   |

### Confidence Threshold Impact

Effect of confidence threshold on precision/recall:

| Threshold | Precision | Recall | F1 Score |
| --------- | --------- | ------ | -------- |
| 0.25      | 72.3%     | 89.1%  | 79.8%    |
| 0.50      | 85.6%     | 76.4%  | 80.7%    |
| 0.75      | 92.1%     | 58.2%  | 71.3%    |

**Recommendation:** Use 0.50 confidence threshold (default) for balanced precision/recall.

---

## Latency Benchmarks

### Single Image Inference

Tested on NVIDIA RTX A5500 (24GB VRAM) with TensorRT FP16:

| Model   | Resolution | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
| ------- | ---------- | --------- | -------- | -------- | -------- |
| yolo26n | 640x640    | 5.2       | 5.1      | 5.8      | 6.2      |
| yolo26n | 1280x1280  | 18.4      | 18.2     | 19.6     | 20.3     |
| yolo26s | 640x640    | 10.8      | 10.6     | 11.9     | 12.5     |
| yolo26s | 1280x1280  | 38.6      | 38.2     | 41.2     | 43.1     |
| yolo26m | 640x640    | 17.3      | 17.1     | 18.8     | 19.6     |
| yolo26m | 1280x1280  | 62.4      | 61.8     | 67.2     | 70.1     |

### Latency Breakdown

Component timing for yolo26m @ 640x640:

| Stage          | Time (ms) | Percentage |
| -------------- | --------- | ---------- |
| Preprocessing  | 0.8       | 4.6%       |
| Inference      | 16.1      | 93.1%      |
| Postprocessing | 0.4       | 2.3%       |
| **Total**      | **17.3**  | **100%**   |

---

## VRAM Usage

### Model Loading

| Model   | VRAM (FP32) | VRAM (FP16) | VRAM (INT8) |
| ------- | ----------- | ----------- | ----------- |
| yolo26n | 180 MB      | 100 MB      | 65 MB       |
| yolo26s | 280 MB      | 150 MB      | 95 MB       |
| yolo26m | 380 MB      | 200 MB      | 125 MB      |

### Runtime VRAM (including buffers)

| Model   | Batch 1 | Batch 4 | Batch 8 | Batch 16 |
| ------- | ------- | ------- | ------- | -------- |
| yolo26n | 150 MB  | 200 MB  | 280 MB  | 450 MB   |
| yolo26s | 220 MB  | 320 MB  | 480 MB  | 800 MB   |
| yolo26m | 300 MB  | 450 MB  | 700 MB  | 1.2 GB   |

---

## Throughput Benchmarks

### Frames Per Second (FPS)

Sustained throughput on RTX A5500:

| Model   | Batch 1 | Batch 4 | Batch 8 | Batch 16 |
| ------- | ------- | ------- | ------- | -------- |
| yolo26n | 192     | 256     | 280     | 290      |
| yolo26s | 93      | 128     | 142     | 148      |
| yolo26m | 58      | 78      | 86      | 90       |

### Multi-Camera Throughput

Cameras processed at 5 FPS each:

| Model   | Max Cameras | Total FPS |
| ------- | ----------- | --------- |
| yolo26n | 50+         | 250+      |
| yolo26s | 25          | 125       |
| yolo26m | 15          | 75        |

---

## TensorRT Optimization

### Export Formats Comparison

| Format             | Load Time | Inference | Portability  |
| ------------------ | --------- | --------- | ------------ |
| PyTorch (.pt)      | 2.5s      | 45ms      | High         |
| ONNX (.onnx)       | 1.2s      | 28ms      | High         |
| TensorRT (.engine) | 0.5s      | 17ms      | GPU-specific |

### TensorRT Optimization Gains

| Optimization | Latency Reduction | VRAM Reduction |
| ------------ | ----------------- | -------------- |
| FP16         | 40-50%            | 50%            |
| INT8         | 60-70%            | 75%            |
| Layer Fusion | 10-15%            | 5-10%          |

---

## Hardware Scaling

### GPU Comparison

Performance across different NVIDIA GPUs (yolo26m @ 640x640):

| GPU        | VRAM  | Inference (ms) | FPS |
| ---------- | ----- | -------------- | --- |
| RTX 4090   | 24 GB | 12.1           | 83  |
| RTX A5500  | 24 GB | 17.3           | 58  |
| RTX 4070   | 12 GB | 19.8           | 50  |
| RTX 3070   | 8 GB  | 25.4           | 39  |
| RTX 3060   | 12 GB | 31.2           | 32  |
| T4 (Cloud) | 16 GB | 38.5           | 26  |

### Multi-GPU Scaling

Linear scaling with multiple GPUs:

| Configuration | Throughput (FPS) | Efficiency |
| ------------- | ---------------- | ---------- |
| 1x RTX A5500  | 58               | 100%       |
| 2x RTX A5500  | 112              | 97%        |
| 4x RTX A5500  | 220              | 95%        |

---

## Recommendations

### Model Selection Guide

| Use Case                         | Recommended | Rationale                  |
| -------------------------------- | ----------- | -------------------------- |
| 1-4 cameras, accuracy priority   | yolo26m     | Best detection accuracy    |
| 5-15 cameras, balanced           | yolo26s     | Good speed/accuracy        |
| 16+ cameras, throughput priority | yolo26n     | Maximum throughput         |
| Edge deployment (Jetson)         | yolo26n     | Low VRAM requirement       |
| High-resolution (4K) cameras     | yolo26s     | Balanced for larger images |

### Latency Targets

| Application               | Target | Model     | Resolution |
| ------------------------- | ------ | --------- | ---------- |
| Real-time alerts (<100ms) | <50ms  | yolo26n/s | 640x640    |
| Near real-time (<500ms)   | <200ms | yolo26m   | 640x640    |
| High accuracy (<1000ms)   | <500ms | yolo26m   | 1280x1280  |

---

## Benchmark Methodology

### Test Configuration

- **Hardware:** NVIDIA RTX A5500 (24GB VRAM)
- **CUDA Version:** 12.4
- **TensorRT Version:** 10.0
- **Driver Version:** 550.54.14
- **Warmup Iterations:** 50
- **Benchmark Iterations:** 1000
- **Input:** Synthetic images with random pixel values

### Reproducibility

Run benchmarks locally:

```bash
# Latency benchmark
uv run python scripts/benchmark_yolo26_latency.py

# Accuracy benchmark
uv run python scripts/benchmark_yolo26_accuracy.py

# GPU benchmark in container
uv run python scripts/benchmark_yolo26_container.py
```

---

## Related Documentation

- [Auto-generated Benchmarks](../../benchmarks/yolo26-benchmarks.md)
- [YOLO26 Export Formats](../../benchmarks/yolo26-export-formats.md)
- [AI Models Reference](../models.md)
- [Multi-GPU Configuration](../../development/multi-gpu.md)
- [GPU Troubleshooting](../troubleshooting/gpu-issues.md)

---

[Back to Reference Hub](../README.md) | [Benchmarks Hub](../../benchmarks/README.md)
