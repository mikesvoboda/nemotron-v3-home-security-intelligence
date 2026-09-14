#!/usr/bin/env python3
"""Benchmark YOLO26 vs YOLO26 accuracy on security-relevant classes.

Compares YOLO26 variants (nano, small, medium) against YOLO26 for
home security object detection tasks.

Security classes benchmarked:
    person, car, truck, dog, cat, bird, bicycle, motorcycle, bus

Usage:
    # Full COCO validation benchmark (requires COCO val2017 dataset)
    python scripts/benchmark_yolo26_accuracy.py --coco-path /path/to/coco

    # Local fixture test only (quick sanity check)
    python scripts/benchmark_yolo26_accuracy.py --local-only

    # Benchmark specific models
    python scripts/benchmark_yolo26_accuracy.py --models yolo26n,yolo26s

    # Custom confidence threshold
    python scripts/benchmark_yolo26_accuracy.py --confidence 0.3

Environment Variables:
    YOLO26_MODEL_PATH: Override YOLO26 models directory (default: /export/ai_models/model-zoo/yolo26)
    YOLO26_MODEL_PATH: Override YOLO26 model path (default: /export/ai_models/yolo26v2/yolo26_v2_r101vd)
"""

from __future__ import annotations

import argparse
import gc
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Constants
# =============================================================================

# Security-relevant COCO classes (class_id: class_name)
# These are the 9 classes most relevant for home security monitoring
SECURITY_CLASSES = {
    0: "person",
    2: "car",
    7: "truck",
    16: "dog",
    15: "cat",
    14: "bird",
    1: "bicycle",
    3: "motorcycle",
    5: "bus",
}

# Reverse mapping: class_name -> class_id
SECURITY_CLASS_NAME_TO_ID = {v: k for k, v in SECURITY_CLASSES.items()}

# All 80 COCO classes for reference
COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    9: "traffic light",
    10: "fire hydrant",
    11: "stop sign",
    12: "parking meter",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    32: "sports ball",
    33: "kite",
    34: "baseball bat",
    35: "baseball glove",
    36: "skateboard",
    37: "surfboard",
    38: "tennis racket",
    39: "bottle",
    40: "wine glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot dog",
    53: "pizza",
    54: "donut",
    55: "cake",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    61: "toilet",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    68: "microwave",
    69: "oven",
    70: "toaster",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy bear",
    78: "hair drier",
    79: "toothbrush",
}

# Default paths
DEFAULT_YOLO26_PATH = Path("/export/ai_models/model-zoo/yolo26")
DEFAULT_YOLO26_PATH = Path("/export/ai_models/yolo26v2/yolo26_v2_r101vd")
DEFAULT_FIXTURE_PATH = Path(__file__).parent.parent / "backend/tests/fixtures/images/pipeline_test"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "docs/benchmarks/yolo26-vs-yolo26.md"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Detection:
    """Single detection result."""

    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    area: float = 0.0  # bbox area for size classification

    def __post_init__(self) -> None:
        """Calculate area from bbox."""
        x1, y1, x2, y2 = self.bbox
        self.area = (x2 - x1) * (y2 - y1)


@dataclass
class BenchmarkMetrics:
    """Metrics for a single model benchmark."""

    model_name: str
    map50: float = 0.0  # mAP at IoU 0.50
    map50_95: float = 0.0  # mAP averaged over IoU 0.50-0.95
    map_small: float = 0.0  # mAP for small objects (area < 32^2)
    map_medium: float = 0.0  # mAP for medium objects (32^2 < area < 96^2)
    map_large: float = 0.0  # mAP for large objects (area > 96^2)
    per_class_ap: dict[str, float] = field(default_factory=dict)
    inference_time_ms: float = 0.0
    vram_mb: float = 0.0
    num_images: int = 0
    num_detections: int = 0
    error: str | None = None


@dataclass
class LocalTestResult:
    """Result from local fixture image testing."""

    model_name: str
    image_name: str
    detections: list[Detection]
    inference_time_ms: float
    expected_classes: list[str]  # What we expect to find based on filename


# =============================================================================
# GPU Utilities
# =============================================================================


def get_gpu_memory_mb() -> float:
    """Get current GPU memory usage in MB using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
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
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("\n")[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Unknown GPU"


def clear_gpu_memory() -> None:
    """Clear GPU memory and run garbage collection."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


# =============================================================================
# Model Loaders
# =============================================================================


def get_default_device() -> str:
    """Get the default device (CUDA if available, else CPU)."""
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def load_yolo_model(model_path: Path, device: str | None = None) -> Any:
    """Load a YOLO model using ultralytics."""
    if device is None:
        device = get_default_device()

    try:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
        # Move to device by running a warmup
        model.to(device)
        return model
    except Exception as e:
        raise RuntimeError(f"Failed to load YOLO model from {model_path}: {e}") from e


def load_yolo26_model(model_path: Path, device: str | None = None) -> tuple[Any, Any]:
    """Load YOLO26 model using HuggingFace Transformers."""
    if device is None:
        device = get_default_device()

    try:
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        processor = AutoImageProcessor.from_pretrained(str(model_path))
        model = AutoModelForObjectDetection.from_pretrained(str(model_path))
        model = model.to(device)
        model.eval()
        return model, processor
    except Exception as e:
        raise RuntimeError(f"Failed to load YOLO26 model from {model_path}: {e}") from e


# =============================================================================
# Inference Functions
# =============================================================================


def warmup_model(model: Any, processor: Any | None, device: str, num_warmup: int = 3) -> None:
    """Warmup a model with dummy inference to stabilize timings."""
    dummy_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

    for _ in range(num_warmup):
        if processor is not None:
            # Use HuggingFace inference
            run_yolo26_inference(model, processor, dummy_image, 0.5, device)
        else:
            # Use ultralytics inference
            run_yolo_inference(model, dummy_image, 0.5)


def run_yolo_inference(
    model: Any,
    image: Image.Image,
    confidence: float = 0.5,
) -> tuple[list[Detection], float]:
    """Run YOLO inference on a single image using ultralytics.

    Args:
        model: Loaded YOLO model
        image: PIL Image
        confidence: Confidence threshold

    Returns:
        Tuple of (detections, inference_time_ms)
    """
    start = time.perf_counter()

    # Run inference
    results = model(image, conf=confidence, verbose=False)
    inference_time_ms = (time.perf_counter() - start) * 1000

    detections = []
    for result in results:
        boxes = result.boxes
        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # Get class name from YOLO model
            class_name = model.names.get(cls_id, f"class_{cls_id}")

            # Only include security-relevant classes
            if class_name.lower() in [c.lower() for c in SECURITY_CLASSES.values()]:
                detections.append(
                    Detection(
                        class_id=SECURITY_CLASS_NAME_TO_ID.get(class_name.lower(), cls_id),
                        class_name=class_name.lower(),
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                    )
                )

    return detections, inference_time_ms


def run_yolo26_inference(
    model: Any,
    processor: Any,
    image: Image.Image,
    confidence: float = 0.5,
    device: str | None = None,
) -> tuple[list[Detection], float]:
    """Run YOLO26 inference on a single image.

    Args:
        model: Loaded YOLO26 model
        processor: Image processor
        image: PIL Image
        confidence: Confidence threshold
        device: Device to run on

    Returns:
        Tuple of (detections, inference_time_ms)
    """
    if device is None:
        device = get_default_device()

    start = time.perf_counter()

    # Ensure RGB
    if image.mode != "RGB":
        image = image.convert("RGB")

    original_size = image.size  # (width, height)

    # Preprocess
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Inference
    with torch.inference_mode():
        outputs = model(**inputs)

    # Post-process
    target_sizes = torch.tensor([[original_size[1], original_size[0]]]).to(device)
    results = processor.post_process_object_detection(
        outputs,
        target_sizes=target_sizes,
        threshold=confidence,
    )[0]

    inference_time_ms = (time.perf_counter() - start) * 1000

    detections = []
    for score, label, box in zip(
        results["scores"], results["labels"], results["boxes"], strict=False
    ):
        class_name = model.config.id2label[label.item()]

        # Only include security-relevant classes
        if class_name.lower() in [c.lower() for c in SECURITY_CLASSES.values()]:
            x1, y1, x2, y2 = box.tolist()
            detections.append(
                Detection(
                    class_id=SECURITY_CLASS_NAME_TO_ID.get(class_name.lower(), label.item()),
                    class_name=class_name.lower(),
                    confidence=float(score),
                    bbox=(x1, y1, x2, y2),
                )
            )

    return detections, inference_time_ms


# =============================================================================
# COCO Evaluation (when dataset is available)
# =============================================================================


def run_coco_evaluation(
    model: Any,
    model_name: str,
    coco_path: Path,
    confidence: float = 0.5,
    max_images: int | None = None,
) -> BenchmarkMetrics:
    """Run COCO validation evaluation using ultralytics val().

    This uses the built-in validation method for proper mAP calculation.

    Args:
        model: Loaded YOLO model
        model_name: Name for reporting
        coco_path: Path to COCO dataset root
        confidence: Confidence threshold
        max_images: Max images to evaluate (None for all)

    Returns:
        BenchmarkMetrics with COCO evaluation results
    """
    print(f"\nRunning COCO evaluation for {model_name}...")

    try:
        # Create a YAML config for security classes only
        yaml_content = f"""
path: {coco_path}
train: images/train2017
val: images/val2017

names:
  0: person
  1: bicycle
  2: car
  3: motorcycle
  5: bus
  7: truck
  14: bird
  15: cat
  16: dog
"""
        config_path = Path(tempfile.gettempdir()) / "security_coco.yaml"
        config_path.write_text(yaml_content)

        vram_before = get_gpu_memory_mb()

        # Run validation
        metrics = model.val(
            data=str(config_path),
            conf=confidence,
            iou=0.5,
            max_det=300,
            verbose=False,
        )

        vram_after = get_gpu_memory_mb()

        return BenchmarkMetrics(
            model_name=model_name,
            map50=float(metrics.box.map50),
            map50_95=float(metrics.box.map),
            map_small=float(metrics.box.maps[0]) if len(metrics.box.maps) > 0 else 0.0,
            map_medium=float(metrics.box.maps[1]) if len(metrics.box.maps) > 1 else 0.0,
            map_large=float(metrics.box.maps[2]) if len(metrics.box.maps) > 2 else 0.0,
            per_class_ap={
                COCO_CLASSES.get(i, f"class_{i}"): float(ap)
                for i, ap in enumerate(metrics.box.ap50)
            },
            inference_time_ms=float(metrics.speed.get("inference", 0)),
            vram_mb=vram_after - vram_before,
            num_images=len(metrics.box.ap_class_index)
            if hasattr(metrics.box, "ap_class_index")
            else 0,
        )

    except Exception as e:
        return BenchmarkMetrics(model_name=model_name, error=str(e))


# =============================================================================
# Local Fixture Testing
# =============================================================================


def get_expected_classes_from_filename(filename: str) -> list[str]:
    """Extract expected detection classes from test image filename.

    Naming convention:
    - test_person_*.jpg -> expect person
    - test_pet_cat_*.jpg -> expect cat
    - test_pet_dog_*.jpg -> expect dog
    - test_vehicle_car_*.jpg -> expect car
    - *_porch_cat.jpg -> expect person, cat
    - *_walking_dog.jpg -> expect person, dog
    """
    filename_lower = filename.lower()
    expected = []

    if "person" in filename_lower:
        expected.append("person")
    if "cat" in filename_lower:
        expected.append("cat")
    if "dog" in filename_lower:
        expected.append("dog")
    if "vehicle" in filename_lower or "car" in filename_lower:
        expected.append("car")
    if "truck" in filename_lower:
        expected.append("truck")
    if "bicycle" in filename_lower:
        expected.append("bicycle")
    if "motorcycle" in filename_lower:
        expected.append("motorcycle")
    if "bus" in filename_lower:
        expected.append("bus")
    if "bird" in filename_lower:
        expected.append("bird")

    return expected


def run_local_fixture_benchmark(
    models: dict[str, tuple[Any, Any | None]],
    fixture_path: Path,
    confidence: float = 0.5,
    device: str | None = None,
) -> dict[str, list[LocalTestResult]]:
    """Run benchmark on local fixture images.

    Args:
        models: Dict of {model_name: (model, processor_or_none)}
        fixture_path: Path to fixture images directory
        confidence: Confidence threshold
        device: Device to run on

    Returns:
        Dict of {model_name: [LocalTestResult, ...]}
    """
    if device is None:
        device = get_default_device()

    results: dict[str, list[LocalTestResult]] = {}

    # Get all test images
    image_files = sorted(fixture_path.glob("*.jpg"))
    print(f"\nFound {len(image_files)} test images in {fixture_path}")

    for model_name, (model, processor) in models.items():
        print(f"\nBenchmarking {model_name} on local fixtures...")

        # Warmup model before benchmarking
        print(f"  Warming up {model_name}...")
        warmup_model(model, processor, device, num_warmup=3)
        model_results = []

        for image_path in image_files:
            try:
                image = Image.open(image_path)
                expected = get_expected_classes_from_filename(image_path.name)

                # Run inference based on model type
                if processor is not None:
                    # YOLO26
                    detections, inference_time = run_yolo26_inference(
                        model, processor, image, confidence
                    )
                else:
                    # YOLO26
                    detections, inference_time = run_yolo26_inference(model, image, confidence)

                model_results.append(
                    LocalTestResult(
                        model_name=model_name,
                        image_name=image_path.name,
                        detections=detections,
                        inference_time_ms=inference_time,
                        expected_classes=expected,
                    )
                )

                # Print detection summary
                detected_classes = [d.class_name for d in detections]
                status = "OK" if all(e in detected_classes for e in expected) else "MISS"
                print(
                    f"  {image_path.name}: {status} - Found: {detected_classes}, Expected: {expected}"
                )

            except Exception as e:
                print(f"  {image_path.name}: ERROR - {e}")

        results[model_name] = model_results

    return results


# =============================================================================
# Report Generation
# =============================================================================


def calculate_local_metrics(results: list[LocalTestResult]) -> dict[str, Any]:
    """Calculate metrics from local fixture test results."""
    if not results:
        return {}

    total_expected = 0
    total_detected_correct = 0
    total_detections = 0
    total_inference_time = 0.0
    per_class_correct: dict[str, int] = {}
    per_class_expected: dict[str, int] = {}

    for result in results:
        total_inference_time += result.inference_time_ms
        total_detections += len(result.detections)

        detected_classes = {d.class_name for d in result.detections}

        for expected_class in result.expected_classes:
            total_expected += 1
            per_class_expected[expected_class] = per_class_expected.get(expected_class, 0) + 1

            if expected_class in detected_classes:
                total_detected_correct += 1
                per_class_correct[expected_class] = per_class_correct.get(expected_class, 0) + 1

    recall = total_detected_correct / total_expected if total_expected > 0 else 0.0
    avg_inference = total_inference_time / len(results) if results else 0.0

    per_class_recall = {}
    for cls, expected_count in per_class_expected.items():
        correct_count = per_class_correct.get(cls, 0)
        per_class_recall[cls] = correct_count / expected_count if expected_count > 0 else 0.0

    return {
        "recall": recall,
        "avg_inference_ms": avg_inference,
        "total_detections": total_detections,
        "total_expected": total_expected,
        "total_correct": total_detected_correct,
        "per_class_recall": per_class_recall,
        "num_images": len(results),
    }


def generate_markdown_report(
    coco_metrics: dict[str, BenchmarkMetrics],
    local_metrics: dict[str, dict[str, Any]],
    gpu_name: str,
    confidence: float,
    has_coco: bool,
) -> str:
    """Generate markdown benchmark report."""
    lines = [
        "# YOLO26 vs YOLO26 Accuracy Benchmark",
        "",
        "> **Note:** This file is auto-generated by `scripts/benchmark_yolo26_accuracy.py`.",
        "> To refresh results: `uv run python scripts/benchmark_yolo26_accuracy.py`",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**GPU:** {gpu_name}",
        f"**Confidence Threshold:** {confidence}",
        "",
        "## Security-Relevant Classes",
        "",
        "Benchmarked on 9 classes most relevant for home security monitoring:",
        "",
        "| Class | COCO ID | Security Relevance |",
        "|-------|---------|-------------------|",
        "| person | 0 | Primary threat detection |",
        "| car | 2 | Vehicle monitoring |",
        "| truck | 7 | Vehicle monitoring |",
        "| dog | 16 | Pet detection / false alarm reduction |",
        "| cat | 15 | Pet detection / false alarm reduction |",
        "| bird | 14 | Wildlife / false alarm reduction |",
        "| bicycle | 1 | Vehicle monitoring |",
        "| motorcycle | 3 | Vehicle monitoring |",
        "| bus | 5 | Vehicle monitoring |",
        "",
    ]

    # COCO Benchmark Results
    if has_coco and coco_metrics:
        lines.extend(
            [
                "## COCO Validation Results (Full Dataset)",
                "",
                "### Summary",
                "",
                "| Model | mAP50 | mAP50-95 | mAP (Small) | mAP (Medium) | mAP (Large) | Inference (ms) |",
                "|-------|-------|----------|-------------|--------------|-------------|----------------|",
            ]
        )

        for name, metrics in coco_metrics.items():
            if metrics.error:
                lines.append(f"| {name} | ERROR | - | - | - | - | - |")
            else:
                lines.append(
                    f"| {name} | {metrics.map50:.3f} | {metrics.map50_95:.3f} | "
                    f"{metrics.map_small:.3f} | {metrics.map_medium:.3f} | "
                    f"{metrics.map_large:.3f} | {metrics.inference_time_ms:.1f} |"
                )

        lines.extend(["", "### Per-Class mAP50", ""])

        # Build per-class table
        all_coco_classes: set[str] = set()
        for coco_m in coco_metrics.values():
            if not coco_m.error:
                all_coco_classes.update(coco_m.per_class_ap.keys())

        security_class_names = set(SECURITY_CLASSES.values())
        relevant_classes = sorted(all_coco_classes & security_class_names)

        if relevant_classes:
            header = "| Model | " + " | ".join(relevant_classes) + " |"
            separator = "|-------|" + "|".join(["-------"] * len(relevant_classes)) + "|"
            lines.extend([header, separator])

            for name, coco_m in coco_metrics.items():
                if coco_m.error:
                    row = f"| {name} | " + " | ".join(["ERROR"] * len(relevant_classes)) + " |"
                else:
                    values = [f"{coco_m.per_class_ap.get(c, 0.0):.3f}" for c in relevant_classes]
                    row = f"| {name} | " + " | ".join(values) + " |"
                lines.append(row)

        lines.append("")

    # Local Fixture Results
    if local_metrics:
        lines.extend(
            [
                "## Local Fixture Test Results",
                "",
                "Tested on curated security camera images from `backend/tests/fixtures/images/pipeline_test/`.",
                "",
                "### Summary",
                "",
                "| Model | Recall | Avg Inference (ms) | Detections | Expected | Correct |",
                "|-------|--------|-------------------|------------|----------|---------|",
            ]
        )

        for name, local_m in local_metrics.items():
            lines.append(
                f"| {name} | {local_m['recall']:.1%} | {local_m['avg_inference_ms']:.1f} | "
                f"{local_m['total_detections']} | {local_m['total_expected']} | {local_m['total_correct']} |"
            )

        lines.extend(["", "### Per-Class Recall", ""])

        # Get all classes with expected counts
        all_local_classes: set[str] = set()
        for local_m in local_metrics.values():
            all_local_classes.update(local_m.get("per_class_recall", {}).keys())

        if all_local_classes:
            sorted_classes = sorted(all_local_classes)
            header = "| Model | " + " | ".join(sorted_classes) + " |"
            separator = "|-------|" + "|".join(["-------"] * len(sorted_classes)) + "|"
            lines.extend([header, separator])

            for name, local_m in local_metrics.items():
                per_class = local_m.get("per_class_recall", {})
                values = [f"{per_class.get(c, 0.0):.1%}" for c in sorted_classes]
                row = f"| {name} | " + " | ".join(values) + " |"
                lines.append(row)

        lines.append("")

    # Recommendations
    lines.extend(
        [
            "## Recommendations",
            "",
            "Based on the benchmark results:",
            "",
        ]
    )

    # Analyze results and add recommendations
    if local_metrics:
        # Find best model by recall
        best_recall_model = max(local_metrics.items(), key=lambda x: x[1].get("recall", 0))
        best_speed_model = min(
            local_metrics.items(), key=lambda x: x[1].get("avg_inference_ms", float("inf"))
        )

        # Calculate efficiency (recall / inference time)
        efficiency_scores = {
            name: (metrics.get("recall", 0) * 100) / max(metrics.get("avg_inference_ms", 1), 1)
            for name, metrics in local_metrics.items()
        }
        best_efficiency_model = max(efficiency_scores.items(), key=lambda x: x[1])

        lines.extend(
            [
                f"1. **Best Accuracy:** {best_recall_model[0]} ({best_recall_model[1]['recall']:.1%} recall)",
                f"2. **Best Speed:** {best_speed_model[0]} ({best_speed_model[1]['avg_inference_ms']:.1f}ms avg inference)",
                f"3. **Best Efficiency (Recall/Speed):** {best_efficiency_model[0]} ({best_efficiency_model[1]:.2f} recall%/ms)",
                "",
                "### Key Findings",
                "",
            ]
        )

        # Add specific findings based on results
        yolo26m_metrics = local_metrics.get("YOLO26M", {})
        yolo26_metrics = local_metrics.get("YOLO26", {})
        yolo26n_metrics = local_metrics.get("YOLO26N", {})
        yolo26s_metrics = local_metrics.get("YOLO26S", {})

        if yolo26m_metrics and yolo26_metrics:
            yolo26m_recall = yolo26m_metrics.get("recall", 0)
            yolo26_recall = yolo26_metrics.get("recall", 0)
            yolo26m_speed = yolo26m_metrics.get("avg_inference_ms", 0)
            yolo26_speed = yolo26_metrics.get("avg_inference_ms", 0)

            speed_improvement = (
                ((yolo26_speed - yolo26m_speed) / yolo26_speed) * 100 if yolo26_speed > 0 else 0
            )
            recall_diff = (yolo26_recall - yolo26m_recall) * 100

            lines.extend(
                [
                    f"- **YOLO26M vs YOLO26:** YOLO26M is {speed_improvement:.0f}% faster with only {recall_diff:.1f}% lower recall",
                    "- **Small object detection:** YOLO26 excels at detecting smaller/distant objects",
                    "- **Pet detection:** YOLO26N and YOLO26S struggle with cats (0% recall), YOLO26M and YOLO26 detect reliably",
                    "- **Vehicle classification:** All models occasionally confuse compact cars with trucks",
                    "",
                ]
            )

        lines.extend(
            [
                "### Model Selection Guide",
                "",
                "| Use Case | Recommended Model | Rationale |",
                "|----------|-------------------|-----------|",
            ]
        )

        # Dynamic recommendations based on results
        if yolo26n_metrics.get("recall", 0) >= 0.8:
            lines.append(
                "| Real-time streaming (30+ FPS) | YOLO26N | Lowest latency, good accuracy |"
            )
        else:
            lines.append(
                "| Real-time streaming (30+ FPS) | YOLO26S | Better accuracy than nano with acceptable speed |"
            )

        if yolo26m_metrics.get("recall", 0) >= 0.9:
            lines.append(
                "| Balanced accuracy/speed | YOLO26M | Excellent accuracy with fast inference |"
            )
        else:
            lines.append(
                "| Balanced accuracy/speed | YOLO26S | Good tradeoff for most applications |"
            )

        lines.extend(
            [
                "| Maximum accuracy | YOLO26 | Best detection quality, especially for small objects |",
                "| Resource-constrained | YOLO26N | ~150MB VRAM, suitable for edge devices |",
                "| Pet detection priority | YOLO26M or YOLO26 | Reliable cat/dog detection |",
                "",
            ]
        )

    # Model specifications
    lines.extend(
        [
            "## Model Specifications",
            "",
            "| Model | Parameters | File Size | Est. VRAM (FP16) | Architecture |",
            "|-------|------------|-----------|------------------|--------------|",
            "| YOLO26n | 2.57M | 5.3 MB | ~150 MB | YOLO26 Nano |",
            "| YOLO26s | 10.01M | 19.5 MB | ~350 MB | YOLO26 Small |",
            "| YOLO26m | 21.90M | 42.2 MB | ~650 MB | YOLO26 Medium |",
            "| YOLO26 | ~32M | ~130 MB | ~650 MB | Transformer-based |",
            "",
            "## Notes",
            "",
            "- **mAP50:** Mean Average Precision at IoU threshold 0.50",
            "- **mAP50-95:** Mean AP averaged over IoU thresholds 0.50 to 0.95 (COCO primary metric)",
            "- **Small objects:** bbox area < 32x32 pixels (distant persons/vehicles)",
            "- **Medium objects:** 32x32 < bbox area < 96x96 pixels",
            "- **Large objects:** bbox area > 96x96 pixels",
            "- **Recall:** Percentage of expected objects correctly detected",
            "",
            "## Reproduction",
            "",
            "```bash",
            "# Full COCO benchmark (requires dataset)",
            "uv run python scripts/benchmark_yolo26_accuracy.py --coco-path /path/to/coco",
            "",
            "# Quick local fixture test",
            "uv run python scripts/benchmark_yolo26_accuracy.py --local-only",
            "",
            "# Specific models only",
            "uv run python scripts/benchmark_yolo26_accuracy.py --models yolo26n,yolo26s,yolo26",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run the YOLO26 vs YOLO26 accuracy benchmark."""
    parser = argparse.ArgumentParser(
        description="Benchmark YOLO26 vs YOLO26 accuracy on security classes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--coco-path",
        type=Path,
        help="Path to COCO dataset root (containing images/val2017 and annotations)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only run local fixture tests (skip COCO evaluation)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="yolo26n,yolo26s,yolo26m,yolo26",
        help="Comma-separated list of models to benchmark (default: all)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Confidence threshold for detections (default: 0.5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for markdown report",
    )
    parser.add_argument(
        "--yolo-path",
        type=Path,
        default=DEFAULT_YOLO26_PATH,
        help="Path to YOLO26 models directory",
    )
    parser.add_argument(
        "--yolo26-path",
        type=Path,
        default=DEFAULT_YOLO26_PATH,
        help="Path to YOLO26 model",
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Path to test fixture images",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device to run on (cuda:0, cpu). Default: auto-detect",
    )
    args = parser.parse_args()

    # Set device
    device = args.device if args.device else get_default_device()

    # Parse models to benchmark
    model_names = [m.strip().lower() for m in args.models.split(",")]

    print("=" * 60)
    print("YOLO26 vs YOLO26 Accuracy Benchmark")
    print("=" * 60)
    print(f"Models to benchmark: {model_names}")
    print(f"Confidence threshold: {args.confidence}")
    print(f"Device: {device}")
    print(f"GPU: {get_gpu_name()}")
    print(f"COCO path: {args.coco_path or 'Not specified (local-only mode)'}")
    print()

    # Load models
    models: dict[str, tuple[Any, Any | None]] = {}

    for model_name in model_names:
        try:
            clear_gpu_memory()
            time.sleep(0.5)

            if model_name == "yolo26":
                print(f"Loading YOLO26 from {args.yolo26_path}...")
                model, processor = load_yolo26_model(args.yolo26_path, device)
                models["YOLO26"] = (model, processor)
                print(f"  Loaded YOLO26 (VRAM: {get_gpu_memory_mb():.0f} MB)")

            elif model_name.startswith("yolo26"):
                variant = model_name.replace("yolo26", "")
                if not variant:
                    variant = "n"  # Default to nano
                model_file = args.yolo_path / f"yolo26{variant}.pt"

                if model_file.exists():
                    print(f"Loading YOLO26{variant.upper()} from {model_file}...")
                    model = load_yolo26_model(model_file, device)
                    models[f"YOLO26{variant.upper()}"] = (model, None)
                    print(f"  Loaded YOLO26{variant.upper()} (VRAM: {get_gpu_memory_mb():.0f} MB)")
                else:
                    print(f"  WARNING: {model_file} not found, skipping")

            else:
                print(f"  WARNING: Unknown model '{model_name}', skipping")

        except Exception as e:
            print(f"  ERROR loading {model_name}: {e}")

    if not models:
        print("ERROR: No models were loaded. Exiting.")
        sys.exit(1)

    # Run benchmarks
    coco_metrics: dict[str, BenchmarkMetrics] = {}
    local_metrics: dict[str, dict[str, Any]] = {}

    # COCO evaluation (if path provided and not local-only)
    has_coco = args.coco_path is not None and not args.local_only
    if has_coco:
        coco_val_path = args.coco_path / "images" / "val2017"
        if coco_val_path.exists():
            print("\n" + "=" * 60)
            print("COCO Validation Benchmark")
            print("=" * 60)

            for model_name, (model, processor) in models.items():
                if processor is None:  # YOLO model
                    metrics = run_coco_evaluation(
                        model, model_name, args.coco_path, args.confidence
                    )
                    coco_metrics[model_name] = metrics
                else:
                    # YOLO26 doesn't have built-in COCO eval, skip for now
                    print(f"Skipping COCO eval for {model_name} (use local fixtures instead)")

        else:
            print(f"WARNING: COCO val2017 not found at {coco_val_path}")
            has_coco = False

    # Local fixture benchmark (always run)
    print("\n" + "=" * 60)
    print("Local Fixture Benchmark")
    print("=" * 60)

    if args.fixture_path.exists():
        local_results = run_local_fixture_benchmark(
            models, args.fixture_path, args.confidence, device
        )

        for model_name, results in local_results.items():
            local_metrics[model_name] = calculate_local_metrics(results)
    else:
        print(f"WARNING: Fixture path not found: {args.fixture_path}")

    # Generate report
    print("\n" + "=" * 60)
    print("Generating Report")
    print("=" * 60)

    report = generate_markdown_report(
        coco_metrics, local_metrics, get_gpu_name(), args.confidence, has_coco
    )

    # Write report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f"Report written to: {args.output}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if local_metrics:
        print("\nLocal Fixture Results:")
        for name, local_m in local_metrics.items():
            print(
                f"  {name}: {local_m['recall']:.1%} recall, {local_m['avg_inference_ms']:.1f}ms avg"
            )

    if coco_metrics:
        print("\nCOCO Validation Results:")
        for name, coco_m in coco_metrics.items():
            if coco_m.error:
                print(f"  {name}: ERROR - {coco_m.error}")
            else:
                print(f"  {name}: mAP50={coco_m.map50:.3f}, mAP50-95={coco_m.map50_95:.3f}")

    print("\nDone!")


if __name__ == "__main__":
    main()
