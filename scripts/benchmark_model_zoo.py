#!/usr/bin/env python3
"""Benchmark script for Model Zoo performance.

Measures:
1. Model loading time
2. VRAM usage after loading
3. Inference time (single image)
4. Unload time and VRAM recovery

Usage:
    python scripts/benchmark_model_zoo.py [--models MODEL1,MODEL2] [--output PATH]

Examples:
    # Benchmark all enabled models
    python scripts/benchmark_model_zoo.py

    # Benchmark specific models
    python scripts/benchmark_model_zoo.py --models yolo11-license-plate,clip-vit-l

    # Output to specific file
    python scripts/benchmark_model_zoo.py --output docs/benchmarks/results.md

    # Use custom model zoo path (for local development)
    MODEL_ZOO_PATH=/export/ai_models/model-zoo python scripts/benchmark_model_zoo.py

Environment Variables:
    MODEL_ZOO_PATH: Override the default model zoo path (/models/model-zoo)
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Note: MODEL_ZOO_PATH env var is supported by model_zoo.py
# Set it before running this script for local development:
#   MODEL_ZOO_PATH=/export/ai_models/model-zoo python scripts/benchmark_model_zoo.py

from backend.services.model_zoo import ModelManager, get_model_config, get_model_zoo


@dataclass
class BenchmarkResult:
    """Result of benchmarking a single model."""

    model_name: str
    load_time_s: float
    vram_before_mb: float
    vram_after_mb: float
    vram_used_mb: float
    inference_time_s: float | None
    unload_time_s: float
    vram_recovered: bool
    vram_final_mb: float
    error: str | None = None


def get_gpu_memory_mb() -> float:
    """Get current GPU memory usage in MB using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        # Sum all GPUs if multiple
        total = sum(
            float(line.strip()) for line in result.stdout.strip().split("\n") if line.strip()
        )
        return total
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0.0


def get_gpu_name() -> str:
    """Get GPU name using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("\n")[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Unknown GPU"


def create_test_image(width: int = 640, height: int = 480) -> Image.Image:
    """Create a test image for inference benchmarks."""
    # Create a realistic-looking test image with some variation
    np.random.seed(42)
    # Gray background with some noise
    data = np.random.randint(100, 150, (height, width, 3), dtype=np.uint8)
    # Add a rectangle (simulating a detected object)
    data[100:300, 150:400] = [180, 180, 180]
    return Image.fromarray(data)


async def run_inference(model: Any, model_name: str, image: Image.Image) -> float | None:  # noqa: PLR0912
    """Run a single inference and return time in seconds.

    Returns None if inference is not applicable for this model type.
    """
    start = time.perf_counter()

    try:
        if model_name in ("yolo11-license-plate", "yolo11-face"):
            # YOLO models expect numpy array
            img_array = np.array(image)
            _ = model(img_array)

        elif model_name == "paddleocr":
            # PaddleOCR expects numpy array
            img_array = np.array(image)
            _ = model.ocr(img_array, cls=False)

        elif model_name == "clip-vit-l":
            # CLIP returns model and processor
            clip_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(clip_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = clip_model.get_image_features(**inputs)

        elif model_name == "florence-2-large":
            # Florence returns model and processor
            florence_model = model["model"]
            processor = model["processor"]
            inputs = processor(text="<CAPTION>", images=image, return_tensors="pt")
            device = next(florence_model.parameters()).device
            dtype = next(florence_model.parameters()).dtype
            inputs = inputs.to(device, dtype)
            _ = florence_model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=50,
                use_cache=False,
            )

        elif model_name == "yolo-world-s":
            # YOLO-World expects image path or PIL image
            _ = model.predict(image, conf=0.3, verbose=False)

        elif model_name == "vitpose-small":
            # ViTPose expects numpy array and bboxes
            img_array = np.array(image)
            # Simulate a person bbox
            bboxes = [[100, 100, 300, 400]]
            if hasattr(model, "inference"):
                _ = model.inference(img_array, bboxes)

        elif model_name == "depth-anything-v2-small":
            # Depth Anything expects PIL image
            depth_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(depth_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = depth_model(**inputs)

        elif model_name == "violence-detection":
            # Violence detection model
            violence_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(violence_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = violence_model(**inputs)

        elif model_name == "weather-classification":
            # Weather classification
            weather_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(weather_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = weather_model(**inputs)

        elif model_name == "segformer-b2-clothes":
            # Segformer for clothing segmentation
            seg_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(seg_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = seg_model(**inputs)

        elif model_name == "xclip-base":
            # X-CLIP for video action recognition (single frame)
            xclip_model = model["model"]
            processor = model["processor"]
            # X-CLIP expects video frames
            inputs = processor(images=[image], return_tensors="pt")
            device = next(xclip_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = xclip_model.get_image_features(**inputs)

        elif model_name == "fashion-clip":
            # FashionCLIP
            fashion_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(fashion_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = fashion_model.get_image_features(**inputs)

        elif model_name == "brisque-quality":
            # BRISQUE is CPU-based, model is a function
            img_array = np.array(image.convert("L"))  # Grayscale
            if callable(model):
                _ = model(img_array)
            else:
                return None

        elif model_name == "vehicle-segment-classification":
            # Vehicle classifier
            vehicle_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(vehicle_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = vehicle_model(**inputs)

        elif model_name == "vehicle-damage-detection":
            # Vehicle damage detection (YOLO-based)
            _ = model.predict(image, conf=0.3, verbose=False)

        elif model_name == "pet-classifier":
            # Pet classifier
            pet_model = model["model"]
            processor = model["processor"]
            inputs = processor(images=image, return_tensors="pt")
            device = next(pet_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            _ = pet_model(**inputs)

        else:
            # Unknown model type, skip inference
            return None

        return time.perf_counter() - start

    except Exception as e:
        print(f"  Warning: Inference failed for {model_name}: {e}")
        return None


async def benchmark_model(
    model_name: str, manager: ModelManager, test_image: Image.Image
) -> BenchmarkResult:
    """Benchmark a single model."""
    print(f"\nBenchmarking {model_name}...")

    # Get baseline VRAM
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        pass  # torch not installed, skip CUDA operations

    time.sleep(0.5)  # noqa: ASYNC251 - Allow memory to settle (intentional blocking)
    vram_before = get_gpu_memory_mb()
    print(f"  VRAM before: {vram_before:.0f} MB")

    error = None
    load_time = 0.0
    vram_after = vram_before
    inference_time = None

    try:
        # Load model
        load_start = time.perf_counter()
        async with manager.load(model_name) as model:
            load_time = time.perf_counter() - load_start
            print(f"  Load time: {load_time:.2f}s")

            # Measure VRAM after load
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.synchronize()
            except ImportError:
                pass  # torch not installed, skip CUDA synchronization
            time.sleep(0.2)  # noqa: ASYNC251 - Allow memory to settle
            vram_after = get_gpu_memory_mb()
            vram_used = vram_after - vram_before
            print(f"  VRAM after: {vram_after:.0f} MB (+{vram_used:.0f} MB)")

            # Run inference
            inference_time = await run_inference(model, model_name, test_image)
            if inference_time is not None:
                print(f"  Inference time: {inference_time * 1000:.1f}ms")
            else:
                print("  Inference: N/A (model type not supported)")

            unload_start = time.perf_counter()

        # After context manager exits, model should be unloaded
        unload_time = time.perf_counter() - unload_start

    except Exception as e:
        error = str(e)
        print(f"  ERROR: {error}")
        unload_time = 0.0

    # Measure VRAM after unload
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        pass  # torch not installed, skip CUDA cleanup
    time.sleep(0.5)  # noqa: ASYNC251 - Allow memory to settle
    vram_final = get_gpu_memory_mb()
    vram_recovered = abs(vram_final - vram_before) < 100  # Allow 100MB tolerance
    print(f"  VRAM final: {vram_final:.0f} MB (recovered: {vram_recovered})")
    print(f"  Unload time: {unload_time:.2f}s")

    return BenchmarkResult(
        model_name=model_name,
        load_time_s=load_time,
        vram_before_mb=vram_before,
        vram_after_mb=vram_after,
        vram_used_mb=vram_after - vram_before,
        inference_time_s=inference_time,
        unload_time_s=unload_time,
        vram_recovered=vram_recovered,
        vram_final_mb=vram_final,
        error=error,
    )


def generate_markdown_report(results: list[BenchmarkResult], gpu_name: str) -> str:
    """Generate a markdown report from benchmark results."""
    lines = [
        "# Model Zoo Benchmark Results",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**GPU:** {gpu_name}",
        "",
        "## Summary",
        "",
        "| Model | Load Time | VRAM Used | Inference | Recovered | Status |",
        "|-------|-----------|-----------|-----------|-----------|--------|",
    ]

    for r in results:
        status = "ERROR" if r.error else "OK"
        inference = f"{r.inference_time_s * 1000:.0f}ms" if r.inference_time_s else "N/A"
        recovered = "Yes" if r.vram_recovered else "No"
        lines.append(
            f"| {r.model_name} | {r.load_time_s:.2f}s | {r.vram_used_mb:.0f}MB | "
            f"{inference} | {recovered} | {status} |"
        )

    # Add statistics
    successful = [r for r in results if r.error is None]
    if successful:
        total_vram = sum(r.vram_used_mb for r in successful)
        avg_load = sum(r.load_time_s for r in successful) / len(successful)
        all_recovered = all(r.vram_recovered for r in successful)

        lines.extend(
            [
                "",
                "## Statistics",
                "",
                f"- **Models benchmarked:** {len(results)}",
                f"- **Successful:** {len(successful)}",
                f"- **Failed:** {len(results) - len(successful)}",
                f"- **Total VRAM (all models):** {total_vram:.0f}MB",
                f"- **Average load time:** {avg_load:.2f}s",
                f"- **All VRAM recovered:** {'Yes' if all_recovered else 'No'}",
                "",
            ]
        )

    # Add success criteria check
    lines.extend(
        [
            "## Success Criteria",
            "",
            "| Criteria | Target | Actual | Pass |",
            "|----------|--------|--------|------|",
        ]
    )

    # Check criteria
    max_vram = max((r.vram_used_mb for r in successful), default=0)
    max_load = max((r.load_time_s for r in successful), default=0)
    all_recovered = all(r.vram_recovered for r in successful)

    lines.append(
        f"| Max VRAM per model | <1500MB | {max_vram:.0f}MB | {'PASS' if max_vram < 1500 else 'FAIL'} |"
    )
    lines.append(
        f"| Max load time | <5s | {max_load:.2f}s | {'PASS' if max_load < 5 else 'FAIL'} |"
    )
    lines.append(
        f"| VRAM recovered | Yes | {'Yes' if all_recovered else 'No'} | {'PASS' if all_recovered else 'FAIL'} |"
    )

    # Add detailed results
    lines.extend(
        [
            "",
            "## Detailed Results",
            "",
        ]
    )

    for r in results:
        lines.append(f"### {r.model_name}")
        lines.append("")
        if r.error:
            lines.append(f"**ERROR:** {r.error}")
        else:
            lines.append(f"- Load time: {r.load_time_s:.2f}s")
            lines.append(f"- VRAM before: {r.vram_before_mb:.0f}MB")
            lines.append(f"- VRAM after: {r.vram_after_mb:.0f}MB")
            lines.append(f"- VRAM used: {r.vram_used_mb:.0f}MB")
            if r.inference_time_s:
                lines.append(f"- Inference time: {r.inference_time_s * 1000:.1f}ms")
            lines.append(f"- Unload time: {r.unload_time_s:.2f}s")
            lines.append(f"- VRAM final: {r.vram_final_mb:.0f}MB")
            lines.append(f"- VRAM recovered: {'Yes' if r.vram_recovered else 'No'}")
        lines.append("")

    return "\n".join(lines)


async def main() -> None:
    """Run the benchmark."""
    parser = argparse.ArgumentParser(description="Benchmark Model Zoo performance")
    parser.add_argument(
        "--models",
        type=str,
        help="Comma-separated list of models to benchmark (default: all enabled)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/benchmarks/model-zoo-benchmark.md",
        help="Output file path for markdown report",
    )
    args = parser.parse_args()

    # Determine which models to benchmark
    # Initialize MODEL_ZOO (triggers env var handling)
    zoo = get_model_zoo()

    if args.models:
        model_names = [m.strip() for m in args.models.split(",")]
    else:
        # Get all enabled models
        model_names = [name for name, config in zoo.items() if config.enabled]

    print(f"Benchmarking {len(model_names)} models: {', '.join(model_names)}")

    # Get GPU info
    gpu_name = get_gpu_name()
    print(f"GPU: {gpu_name}")

    # Create test image
    test_image = create_test_image()
    print(f"Test image size: {test_image.size}")

    # Create model manager
    manager = ModelManager()

    # Run benchmarks
    results: list[BenchmarkResult] = []
    for model_name in model_names:
        config = get_model_config(model_name)
        if config is None:
            print(f"\nSkipping {model_name}: not found in MODEL_ZOO")
            continue
        if not config.enabled:
            print(f"\nSkipping {model_name}: disabled")
            continue

        result = await benchmark_model(model_name, manager, test_image)
        results.append(result)

    # Generate report
    report = generate_markdown_report(results, gpu_name)

    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"\nReport written to: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]
    print(f"Successful: {len(successful)}/{len(results)}")
    if failed:
        print(f"Failed: {', '.join(r.model_name for r in failed)}")

    # Check success criteria
    if successful:
        max_vram = max(r.vram_used_mb for r in successful)
        max_load = max(r.load_time_s for r in successful)
        all_recovered = all(r.vram_recovered for r in successful)

        print(
            f"\nMax VRAM: {max_vram:.0f}MB (target: <1500MB) {'PASS' if max_vram < 1500 else 'FAIL'}"
        )
        print(f"Max load: {max_load:.2f}s (target: <5s) {'PASS' if max_load < 5 else 'FAIL'}")
        print(
            f"VRAM recovered: {'Yes' if all_recovered else 'No'} {'PASS' if all_recovered else 'FAIL'}"
        )


if __name__ == "__main__":
    asyncio.run(main())
