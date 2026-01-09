#!/usr/bin/env python3
"""Comprehensive AI Model Zoo test with GPU monitoring and latency tracking.

Exercises ALL available endpoints across all AI services:
- RT-DETRv2: /detect, /detect/batch
- Florence-2: /extract with 8 different prompts
- CLIP: /embed
- Enrichment: /vehicle-classify, /pet-classify, /clothing-classify
"""

import base64
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

FIXTURE_DIR = Path(
    "/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/tests/fixtures/images/pipeline_test"
)

SERVICES = {
    "detector": "http://localhost:8090",
    "florence": "http://localhost:8092",
    "clip": "http://localhost:8093",
    "enrichment": "http://localhost:8094",
}

# Florence-2 supported prompts
FLORENCE_PROMPTS = [
    "<CAPTION>",
    "<DETAILED_CAPTION>",
    "<MORE_DETAILED_CAPTION>",
    "<OD>",
    "<DENSE_REGION_CAPTION>",
    "<REGION_PROPOSAL>",
    "<OCR>",
    "<OCR_WITH_REGION>",
]


@dataclass
class GPUStats:
    """GPU memory statistics."""

    used_mb: int = 0
    total_mb: int = 0
    free_mb: int = 0
    utilization_pct: int = 0


@dataclass
class LatencyResult:
    """Result of a single API call with latency."""

    endpoint: str
    latency_ms: float
    success: bool
    result_preview: str = ""
    error: str = ""
    gpu_before_mb: int = 0
    gpu_after_mb: int = 0


@dataclass
class ModelTestResults:
    """Aggregated results for a model."""

    model_name: str
    endpoint_results: list[LatencyResult] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        successful = [r for r in self.endpoint_results if r.success]
        if not successful:
            return 0.0
        return sum(r.latency_ms for r in successful) / len(successful)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.endpoint_results if r.success)

    @property
    def total_count(self) -> int:
        return len(self.endpoint_results)


def get_gpu_stats() -> GPUStats:
    """Get current GPU statistics using nvidia-smi."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return GPUStats()

    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=memory.used,memory.total,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        parts = result.stdout.strip().split(", ")
        if len(parts) >= 4:
            return GPUStats(
                used_mb=int(parts[0]),
                total_mb=int(parts[1]),
                free_mb=int(parts[2]),
                utilization_pct=int(parts[3]),
            )
    except Exception:
        return GPUStats()
    return GPUStats()


def encode_image(path: str) -> str:
    """Encode image to base64."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def test_rtdetr_detect(image_path: Path, client: httpx.Client) -> LatencyResult:
    """Test RT-DETRv2 single image detection."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        with open(image_path, "rb") as f:
            r = client.post(
                f"{SERVICES['detector']}/detect",
                files={"file": (image_path.name, f, "image/jpeg")},
                timeout=60,
            )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            dets = r.json().get("detections", [])
            preview = ", ".join(f"{d['class']}({d['confidence']:.2f})" for d in dets[:3])
            return LatencyResult(
                endpoint="/detect",
                latency_ms=latency,
                success=True,
                result_preview=f"{len(dets)} objects: {preview}",
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint="/detect",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint="/detect",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def test_rtdetr_batch(image_paths: list[Path], client: httpx.Client) -> LatencyResult:
    """Test RT-DETRv2 batch detection."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        files = []
        for path in image_paths:
            with open(path, "rb") as f:
                files.append(("files", (path.name, f.read(), "image/jpeg")))

        r = client.post(
            f"{SERVICES['detector']}/detect/batch",
            files=files,
            timeout=120,
        )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            results = r.json().get("results", [])
            total_dets = sum(len(res.get("detections", [])) for res in results)
            return LatencyResult(
                endpoint="/detect/batch",
                latency_ms=latency,
                success=True,
                result_preview=f"{len(results)} images, {total_dets} total detections",
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint="/detect/batch",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}: {r.text[:100]}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint="/detect/batch",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def test_florence_prompt(
    _image_path: Path, prompt: str, image_b64: str, client: httpx.Client
) -> LatencyResult:
    """Test Florence-2 with a specific prompt."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        r = client.post(
            f"{SERVICES['florence']}/extract",
            json={"image": image_b64, "prompt": prompt},
            timeout=120,
        )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            result = r.json().get("result", "")
            # Truncate long results
            preview = result[:100] + "..." if len(result) > 100 else result
            return LatencyResult(
                endpoint=f"/extract [{prompt}]",
                latency_ms=latency,
                success=True,
                result_preview=preview,
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint=f"/extract [{prompt}]",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}: {r.text[:100]}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint=f"/extract [{prompt}]",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def test_clip_embed(_image_path: Path, image_b64: str, client: httpx.Client) -> LatencyResult:
    """Test CLIP embedding generation."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        r = client.post(
            f"{SERVICES['clip']}/embed",
            json={"image": image_b64},
            timeout=60,
        )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            embedding = r.json().get("embedding", [])
            # Calculate embedding stats
            if embedding:
                import statistics

                mean = statistics.mean(embedding[:100])  # Sample mean
                preview = f"{len(embedding)}-dim vector (mean: {mean:.4f})"
            else:
                preview = "Empty embedding"
            return LatencyResult(
                endpoint="/embed",
                latency_ms=latency,
                success=True,
                result_preview=preview,
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint="/embed",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint="/embed",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def test_enrichment_vehicle(
    image_b64: str, bbox: list[int] | None, client: httpx.Client
) -> LatencyResult:
    """Test vehicle classification."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        payload: dict[str, Any] = {"image": image_b64}
        if bbox:
            payload["bbox"] = bbox

        r = client.post(
            f"{SERVICES['enrichment']}/vehicle-classify",
            json=payload,
            timeout=60,
        )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            data = r.json()
            vtype = data.get("display_name", data.get("vehicle_type", "unknown"))
            conf = data.get("confidence", 0)
            commercial = "commercial" if data.get("is_commercial") else "non-commercial"
            preview = f"{vtype} ({conf:.2f}) [{commercial}]"
            return LatencyResult(
                endpoint="/vehicle-classify",
                latency_ms=latency,
                success=True,
                result_preview=preview,
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint="/vehicle-classify",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint="/vehicle-classify",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def test_enrichment_pet(
    image_b64: str, bbox: list[int] | None, client: httpx.Client
) -> LatencyResult:
    """Test pet classification."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        payload: dict[str, Any] = {"image": image_b64}
        if bbox:
            payload["bbox"] = bbox

        r = client.post(
            f"{SERVICES['enrichment']}/pet-classify",
            json=payload,
            timeout=60,
        )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            data = r.json()
            ptype = data.get("pet_type", "unknown")
            breed = data.get("breed", "unknown")
            conf = data.get("confidence", 0)
            preview = f"{ptype}/{breed} ({conf:.2f})"
            return LatencyResult(
                endpoint="/pet-classify",
                latency_ms=latency,
                success=True,
                result_preview=preview,
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint="/pet-classify",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint="/pet-classify",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def test_enrichment_clothing(
    image_b64: str, bbox: list[int] | None, client: httpx.Client
) -> LatencyResult:
    """Test clothing classification (FashionCLIP)."""
    gpu_before = get_gpu_stats()
    start = time.perf_counter()

    try:
        payload: dict[str, Any] = {"image": image_b64}
        if bbox:
            payload["bbox"] = bbox

        r = client.post(
            f"{SERVICES['enrichment']}/clothing-classify",
            json=payload,
            timeout=60,
        )

        latency = (time.perf_counter() - start) * 1000
        gpu_after = get_gpu_stats()

        if r.status_code == 200:
            data = r.json()
            ctype = data.get("clothing_type", "unknown")
            color = data.get("color", "unknown")
            style = data.get("style", "unknown")
            conf = data.get("confidence", 0)
            preview = f"{color} {ctype} ({style}, {conf:.2f})"
            return LatencyResult(
                endpoint="/clothing-classify",
                latency_ms=latency,
                success=True,
                result_preview=preview,
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        elif r.status_code == 503:
            return LatencyResult(
                endpoint="/clothing-classify",
                latency_ms=latency,
                success=False,
                error="FashionCLIP not loaded",
                gpu_before_mb=gpu_before.used_mb,
                gpu_after_mb=gpu_after.used_mb,
            )
        return LatencyResult(
            endpoint="/clothing-classify",
            latency_ms=latency,
            success=False,
            error=f"HTTP {r.status_code}",
            gpu_before_mb=gpu_before.used_mb,
            gpu_after_mb=gpu_after.used_mb,
        )
    except Exception as e:
        return LatencyResult(
            endpoint="/clothing-classify",
            latency_ms=(time.perf_counter() - start) * 1000,
            success=False,
            error=str(e),
        )


def get_detection_bbox(
    image_path: Path, target_class: str, client: httpx.Client
) -> tuple[list[int] | None, dict | None]:
    """Get bounding box for a specific class from detection."""
    try:
        with open(image_path, "rb") as f:
            r = client.post(
                f"{SERVICES['detector']}/detect",
                files={"file": (image_path.name, f, "image/jpeg")},
                timeout=60,
            )
        if r.status_code == 200:
            dets = r.json().get("detections", [])
            for det in dets:
                if det.get("class") == target_class:
                    bbox = det.get("bbox", {})
                    x1 = bbox.get("x", 0)
                    y1 = bbox.get("y", 0)
                    x2 = x1 + bbox.get("width", 0)
                    y2 = y1 + bbox.get("height", 0)
                    return [x1, y1, x2, y2], det
    except Exception:
        return None, None
    return None, None


def print_header(title: str, width: int = 100) -> None:
    """Print a formatted header."""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def print_subheader(title: str, width: int = 100) -> None:
    """Print a formatted subheader."""
    print(f"\n--- {title} " + "-" * (width - len(title) - 5))


def main() -> int:  # noqa: PLR0912 - comprehensive test requires many branches
    """Run comprehensive model tests with GPU monitoring."""
    print_header("AI MODEL ZOO - COMPREHENSIVE TEST WITH GPU MONITORING")

    # Get initial GPU stats
    initial_gpu = get_gpu_stats()
    print("\nInitial GPU State:")
    print(f"  VRAM Used:     {initial_gpu.used_mb:,} MB / {initial_gpu.total_mb:,} MB")
    print(f"  VRAM Free:     {initial_gpu.free_mb:,} MB")
    print(f"  GPU Util:      {initial_gpu.utilization_pct}%")

    # Collect test images
    test_images = list(FIXTURE_DIR.glob("*.jpg"))
    if not test_images:
        print(f"\nERROR: No test images found in {FIXTURE_DIR}")
        return 1

    print(f"\nTest images found: {len(test_images)}")

    # Results storage
    all_results: dict[str, ModelTestResults] = {
        "RT-DETRv2": ModelTestResults(model_name="RT-DETRv2"),
        "Florence-2": ModelTestResults(model_name="Florence-2"),
        "CLIP": ModelTestResults(model_name="CLIP"),
        "Vehicle Classifier": ModelTestResults(model_name="Vehicle Classifier"),
        "Pet Classifier": ModelTestResults(model_name="Pet Classifier"),
        "Clothing Classifier": ModelTestResults(model_name="Clothing Classifier"),
    }

    with httpx.Client(timeout=120) as client:
        # Select representative test images
        vehicle_img = next((p for p in test_images if "vehicle" in p.name), test_images[0])
        person_img = next((p for p in test_images if "person" in p.name), test_images[0])

        # Pre-encode images for Florence tests
        vehicle_b64 = encode_image(str(vehicle_img))
        person_b64 = encode_image(str(person_img))

        # =========================================
        # 1. RT-DETRv2 Detection Tests
        # =========================================
        print_header("RT-DETRv2 OBJECT DETECTION (Port 8090)")

        # Single detection on all images
        print_subheader("Single Image Detection (/detect)")
        for img_path in test_images[:5]:  # Test first 5 images
            result = test_rtdetr_detect(img_path, client)
            all_results["RT-DETRv2"].endpoint_results.append(result)
            status = "OK" if result.success else "FAIL"
            print(
                f"  [{status}] {img_path.name}: {result.latency_ms:.1f}ms | "
                f"GPU: {result.gpu_before_mb}MB -> {result.gpu_after_mb}MB | "
                f"{result.result_preview if result.success else result.error}"
            )

        # Batch detection
        print_subheader("Batch Detection (/detect/batch)")
        batch_result = test_rtdetr_batch(test_images[:4], client)
        all_results["RT-DETRv2"].endpoint_results.append(batch_result)
        status = "OK" if batch_result.success else "FAIL"
        print(
            f"  [{status}] Batch of {len(test_images[:4])} images: {batch_result.latency_ms:.1f}ms | "
            f"GPU: {batch_result.gpu_before_mb}MB -> {batch_result.gpu_after_mb}MB | "
            f"{batch_result.result_preview if batch_result.success else batch_result.error}"
        )

        # =========================================
        # 2. Florence-2 Vision-Language Tests
        # =========================================
        print_header("FLORENCE-2 VISION-LANGUAGE (Port 8092)")
        print(f"Testing all {len(FLORENCE_PROMPTS)} supported prompts...")

        for prompt in FLORENCE_PROMPTS:
            print_subheader(f"Florence-2 {prompt}")

            # Use appropriate image for each prompt type
            if prompt in ("<OD>", "<REGION_PROPOSAL>", "<DENSE_REGION_CAPTION>"):
                test_img = vehicle_img  # Complex scene for detection tasks
                test_b64 = vehicle_b64
            elif prompt in ("<OCR>", "<OCR_WITH_REGION>"):
                test_img = vehicle_img  # May have license plates
                test_b64 = vehicle_b64
            else:
                test_img = person_img  # General captioning
                test_b64 = person_b64

            result = test_florence_prompt(test_img, prompt, test_b64, client)
            all_results["Florence-2"].endpoint_results.append(result)
            status = "OK" if result.success else "FAIL"
            print(
                f"  [{status}] {test_img.name}: {result.latency_ms:.1f}ms | "
                f"GPU: {result.gpu_before_mb}MB -> {result.gpu_after_mb}MB"
            )
            if result.success:
                print(f"      Result: {result.result_preview}")
            else:
                print(f"      Error: {result.error}")

        # =========================================
        # 3. CLIP Embedding Tests
        # =========================================
        print_header("CLIP ViT-L EMBEDDINGS (Port 8093)")

        print_subheader("Embedding Generation (/embed)")
        for img_path in test_images[:5]:
            img_b64 = encode_image(str(img_path))
            result = test_clip_embed(img_path, img_b64, client)
            all_results["CLIP"].endpoint_results.append(result)
            status = "OK" if result.success else "FAIL"
            print(
                f"  [{status}] {img_path.name}: {result.latency_ms:.1f}ms | "
                f"GPU: {result.gpu_before_mb}MB -> {result.gpu_after_mb}MB | "
                f"{result.result_preview if result.success else result.error}"
            )

        # =========================================
        # 4. Enrichment Service Tests
        # =========================================
        print_header("ENRICHMENT SERVICE (Port 8094)")

        # Vehicle Classification
        print_subheader("Vehicle Classification (/vehicle-classify)")
        vehicle_images = [p for p in test_images if "vehicle" in p.name]
        for img_path in vehicle_images or [test_images[0]]:
            img_b64 = encode_image(str(img_path))
            # Get bbox from detection
            bbox, _det = get_detection_bbox(img_path, "car", client)
            if not bbox:
                bbox, _det = get_detection_bbox(img_path, "truck", client)

            result = test_enrichment_vehicle(img_b64, bbox, client)
            all_results["Vehicle Classifier"].endpoint_results.append(result)
            status = "OK" if result.success else "FAIL"
            bbox_info = f"bbox={bbox}" if bbox else "full image"
            print(
                f"  [{status}] {img_path.name} ({bbox_info}): {result.latency_ms:.1f}ms | "
                f"GPU: {result.gpu_before_mb}MB -> {result.gpu_after_mb}MB | "
                f"{result.result_preview if result.success else result.error}"
            )

        # Pet Classification
        print_subheader("Pet Classification (/pet-classify)")
        pet_images = [p for p in test_images if "pet" in p.name]
        for img_path in pet_images or [test_images[0]]:
            img_b64 = encode_image(str(img_path))
            # Get bbox from detection
            bbox, _det = get_detection_bbox(img_path, "dog", client)
            if not bbox:
                bbox, _det = get_detection_bbox(img_path, "cat", client)

            result = test_enrichment_pet(img_b64, bbox, client)
            all_results["Pet Classifier"].endpoint_results.append(result)
            status = "OK" if result.success else "FAIL"
            bbox_info = f"bbox={bbox}" if bbox else "full image"
            print(
                f"  [{status}] {img_path.name} ({bbox_info}): {result.latency_ms:.1f}ms | "
                f"GPU: {result.gpu_before_mb}MB -> {result.gpu_after_mb}MB | "
                f"{result.result_preview if result.success else result.error}"
            )

        # Clothing Classification
        print_subheader("Clothing Classification (/clothing-classify) - FashionCLIP")
        person_images = [p for p in test_images if "person" in p.name]
        for img_path in person_images or [test_images[0]]:
            img_b64 = encode_image(str(img_path))
            # Get bbox from detection
            bbox, _det = get_detection_bbox(img_path, "person", client)

            result = test_enrichment_clothing(img_b64, bbox, client)
            all_results["Clothing Classifier"].endpoint_results.append(result)
            status = "OK" if result.success else "FAIL"
            bbox_info = f"bbox={bbox}" if bbox else "full image"
            print(
                f"  [{status}] {img_path.name} ({bbox_info}): {result.latency_ms:.1f}ms | "
                f"GPU: {result.gpu_before_mb}MB -> {result.gpu_after_mb}MB | "
                f"{result.result_preview if result.success else result.error}"
            )

    # =========================================
    # Summary Report
    # =========================================
    print_header("COMPREHENSIVE TEST SUMMARY")

    # Final GPU stats
    final_gpu = get_gpu_stats()
    print("\nFinal GPU State:")
    print(f"  VRAM Used:     {final_gpu.used_mb:,} MB / {final_gpu.total_mb:,} MB")
    print(f"  VRAM Free:     {final_gpu.free_mb:,} MB")
    print(f"  GPU Util:      {final_gpu.utilization_pct}%")
    print(f"  Delta:         {final_gpu.used_mb - initial_gpu.used_mb:+,} MB")

    # Per-model statistics
    print("\n" + "-" * 100)
    print(f"{'Model':<25} {'Success':<12} {'Avg Latency':<15} {'Min':<12} {'Max':<12} {'Status'}")
    print("-" * 100)

    total_success = 0
    total_tests = 0

    for model_name, results in all_results.items():
        if not results.endpoint_results:
            continue

        successful = [r for r in results.endpoint_results if r.success]
        total_success += len(successful)
        total_tests += len(results.endpoint_results)

        if successful:
            latencies = [r.latency_ms for r in successful]
            avg_lat = sum(latencies) / len(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
        else:
            avg_lat = min_lat = max_lat = 0

        status = "OK" if len(successful) == len(results.endpoint_results) else "PARTIAL"
        if not successful:
            status = "FAILED"

        print(
            f"{model_name:<25} "
            f"{len(successful)}/{len(results.endpoint_results):<10} "
            f"{avg_lat:>8.1f} ms     "
            f"{min_lat:>8.1f} ms  "
            f"{max_lat:>8.1f} ms  "
            f"{status}"
        )

    print("-" * 100)
    print(
        f"\nTotal: {total_success}/{total_tests} tests passed ({100 * total_success / total_tests:.1f}%)"
    )

    # Detailed endpoint breakdown
    print_header("ENDPOINT LATENCY BREAKDOWN")
    print(f"{'Endpoint':<40} {'Latency':<12} {'Status':<10}")
    print("-" * 70)

    for _model_name, results in all_results.items():
        for r in results.endpoint_results:
            status = "OK" if r.success else "FAIL"
            print(f"{r.endpoint:<40} {r.latency_ms:>8.1f} ms  {status:<10}")

    print("\n" + "=" * 100)
    print("TEST COMPLETE")
    print("=" * 100)

    return 0 if total_success == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
