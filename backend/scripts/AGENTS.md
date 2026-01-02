# Backend Scripts

## Purpose

The `backend/scripts/` directory contains utility scripts for development, benchmarking, and operations tasks that are not part of the main application runtime.

## Files

### `benchmark_vram.py`

**Purpose:** VRAM usage benchmarking script for vision extraction models.

**Description:** Measures VRAM consumption and loading times for all models in the Model Zoo. Run it on a system with a GPU to understand the VRAM requirements of the vision extraction pipeline.

**Features:**

- Measures baseline GPU VRAM usage
- Loads each enabled model individually and measures:
  - Loading time (seconds)
  - VRAM consumption (MB)
  - Model availability status
- Generates a summary report in markdown format
- Saves report to `docs/vram-benchmark.md`

**Usage:**

```bash
# From project root with uv (recommended)
uv run python backend/scripts/benchmark_vram.py

# Or from backend directory
cd backend
python scripts/benchmark_vram.py
```

**Requirements:**

- NVIDIA GPU with CUDA support
- `pynvml` library OR `nvidia-smi` command available
- Model dependencies (transformers, ultralytics, etc.)

### Sample Output

```
============================================================
VRAM Benchmark for Vision Extraction Models
============================================================

Measuring baseline GPU memory...
  Total GPU Memory: 24,564 MB
  Baseline VRAM: 412 MB
  Available: 24,152 MB

Benchmarking 6 enabled models...

  Loading rtdetr_v2... OK (3.24s, 1,847 MB)
  Loading clip_vit_l14... OK (1.12s, 932 MB)
  Loading florence2_base... OK (2.87s, 1,203 MB)
  Loading depth_anything_v2... OK (0.94s, 445 MB)
  Loading yolov8_pose... OK (0.67s, 156 MB)
  Loading clothing_classifier... OK (0.43s, 312 MB)

============================================================
BENCHMARK COMPLETE
============================================================

# VRAM Benchmark Report

**Timestamp:** 2025-01-15T10:30:45+00:00
**GPU Total Memory:** 24,564 MB
**Baseline VRAM Usage:** 412 MB
**Available for Models:** 24,152 MB

## Model Results

| Model | Category | Est. VRAM | Actual VRAM | Load Time | Status |
|-------|----------|-----------|-------------|-----------|--------|
| rtdetr_v2 | detection | 1,800 MB | 1,847 MB | 3.24s | OK |
| clip_vit_l14 | embedding | 900 MB | 932 MB | 1.12s | OK |
| florence2_base | caption | 1,200 MB | 1,203 MB | 2.87s | OK |
| depth_anything_v2 | depth | 400 MB | 445 MB | 0.94s | OK |
| yolov8_pose | pose | 150 MB | 156 MB | 0.67s | OK |
| clothing_classifier | classifier | 300 MB | 312 MB | 0.43s | OK |

## Summary

- **Successful loads:** 6/6
- **Total VRAM (all models):** 4,895 MB
- **Peak VRAM (single model):** 1,847 MB
- **Average load time:** 1.55s

Report saved to: /path/to/docs/vram-benchmark.md
```

### Interpreting Results

| Metric                     | What It Means                        | Action If Concerning                            |
| -------------------------- | ------------------------------------ | ----------------------------------------------- |
| **Actual > Estimated**     | Model uses more VRAM than configured | Update `ModelConfig.vram_mb` in `model_zoo.py`  |
| **Load Time > 5s**         | Slow model initialization            | Consider lazy loading or model warmup           |
| **Status: FAIL**           | Model couldn't load                  | Check dependencies, model path, or CUDA version |
| **Total VRAM > Available** | Can't load all models simultaneously | Disable some models or use model swapping       |

**VRAM Planning Guidelines:**

- **Peak VRAM** - Minimum GPU memory needed to load any single model
- **Total VRAM** - Memory needed if all models loaded simultaneously (not typical)
- **Available** - Baseline subtracted from total; usable for models
- Keep 10-15% headroom for inference buffers and PyTorch overhead

### Key Classes

| Class             | Description                                                                           |
| ----------------- | ------------------------------------------------------------------------------------- |
| `BenchmarkResult` | Single model result: name, category, estimated/actual VRAM, load time, success status |
| `BenchmarkReport` | Complete report: baseline, total memory, list of results, markdown generator          |

**Data Collected Per Model:**

- Model name and category (from `ModelConfig`)
- Estimated VRAM (from `ModelConfig.vram_mb`)
- Actual VRAM consumption (measured via pynvml/nvidia-smi)
- Loading time in seconds
- Unloading time in seconds
- Success/failure status with error messages (truncated to 100 chars)

### Troubleshooting

| Problem                              | Cause                                    | Solution                                               |
| ------------------------------------ | ---------------------------------------- | ------------------------------------------------------ |
| "No GPU detected"                    | CUDA not available or nvidia-smi missing | Install NVIDIA drivers, verify `nvidia-smi` works      |
| "pynvml not found"                   | pynvml package not installed             | `uv add pynvml` or script falls back to nvidia-smi     |
| Model FAIL with "CUDA out of memory" | Previous model not fully unloaded        | Restart script; GPU cache clearing may be incomplete   |
| VRAM shows 0 MB                      | nvidia-smi/pynvml permission issue       | Run as user with GPU access; check nvidia-smi manually |
| "Model not found" error              | Model path incorrect in ModelConfig      | Verify paths in `backend/services/model_zoo.py`        |

## Running Scripts

All scripts should be run from the project root using uv:

```bash
# Recommended: use uv from project root
uv run python backend/scripts/benchmark_vram.py

# Alternative: from backend directory
cd /Users/msvoboda/github/home_security_intelligence/backend
python scripts/benchmark_vram.py
```

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/services/model_zoo.py` - Model configuration and management
- `/backend/services/AGENTS.md` - Service layer documentation
- `/ai/AGENTS.md` - AI pipeline overview with VRAM breakdown
- `/docs/vram-benchmark.md` - Generated benchmark report (after running script)
