#!/usr/bin/env python3
"""End-to-end test for the AI model zoo pipeline.

Tests all AI services in sequence:
1. RT-DETRv2 (object detection) - port 8090
2. Florence-2 (dense captioning) - port 8092
3. CLIP (entity embeddings) - port 8093
4. Enrichment (vehicle/pet/clothing) - port 8094
5. Nemotron (risk analysis) - port 8091

Saves test images and results for integration testing.
"""

import argparse
import base64
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# Default service URLs for local development
# These can be overridden via environment variables:
#   RTDETR_URL     - RT-DETRv2 object detection (default: http://localhost:8090)
#   NEMOTRON_URL   - Nemotron LLM risk analysis (default: http://localhost:8091)
#   FLORENCE_URL   - Florence-2 dense captioning (default: http://localhost:8092)
#   CLIP_URL       - CLIP entity embeddings (default: http://localhost:8093)
#   ENRICHMENT_URL - Enrichment service (default: http://localhost:8094)
SERVICES = {
    "detector": os.environ.get("RTDETR_URL", "http://localhost:8090"),
    "llm": os.environ.get("NEMOTRON_URL", "http://localhost:8091"),
    "florence": os.environ.get("FLORENCE_URL", "http://localhost:8092"),
    "clip": os.environ.get("CLIP_URL", "http://localhost:8093"),
    "enrichment": os.environ.get("ENRICHMENT_URL", "http://localhost:8094"),
}


@dataclass
class PipelineResult:
    """Results from a single image through the pipeline."""

    image_path: str
    detections: list = field(default_factory=list)
    caption: str = ""
    embeddings: list = field(default_factory=list)
    vehicle_class: dict = field(default_factory=dict)
    pet_class: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)


def check_services() -> dict[str, bool]:
    """Check health of all AI services."""
    status = {}
    for name, url in SERVICES.items():
        try:
            r = httpx.get(f"{url}/health", timeout=5)
            status[name] = r.status_code == 200
        except Exception:
            status[name] = False
    return status


def encode_image(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def detect_objects(image_path: str, client: httpx.Client) -> tuple[list, float]:
    """Run RT-DETRv2 object detection."""
    start = time.time()
    with open(image_path, "rb") as f:
        files = {"file": (Path(image_path).name, f, "image/jpeg")}
        r = client.post(f"{SERVICES['detector']}/detect", files=files, timeout=30)

    elapsed = time.time() - start
    if r.status_code == 200:
        return r.json().get("detections", []), elapsed
    return [], elapsed


def get_caption(image_path: str, client: httpx.Client) -> tuple[str, float]:
    """Get Florence-2 dense caption."""
    start = time.time()
    image_b64 = encode_image(image_path)
    r = client.post(
        f"{SERVICES['florence']}/extract",
        json={"image": image_b64, "prompt": "<MORE_DETAILED_CAPTION>"},
        timeout=60,
    )

    elapsed = time.time() - start
    if r.status_code == 200:
        return r.json().get("result", ""), elapsed
    return "", elapsed


def get_embedding(image_path: str, client: httpx.Client) -> tuple[list, float]:
    """Get CLIP embedding for image."""
    start = time.time()
    image_b64 = encode_image(image_path)
    r = client.post(
        f"{SERVICES['clip']}/embed",
        json={"image": image_b64},
        timeout=30,
    )

    elapsed = time.time() - start
    if r.status_code == 200:
        return r.json().get("embedding", []), elapsed
    return [], elapsed


def classify_vehicle(image_path: str, client: httpx.Client) -> tuple[dict, float]:
    """Classify vehicle using enrichment service."""
    start = time.time()
    with open(image_path, "rb") as f:
        files = {"file": (Path(image_path).name, f, "image/jpeg")}
        r = client.post(f"{SERVICES['enrichment']}/vehicle-classify", files=files, timeout=30)

    elapsed = time.time() - start
    if r.status_code == 200:
        return r.json(), elapsed
    return {}, elapsed


def classify_pet(image_path: str, client: httpx.Client) -> tuple[dict, float]:
    """Classify pet using enrichment service."""
    start = time.time()
    with open(image_path, "rb") as f:
        files = {"file": (Path(image_path).name, f, "image/jpeg")}
        r = client.post(f"{SERVICES['enrichment']}/pet-classify", files=files, timeout=30)

    elapsed = time.time() - start
    if r.status_code == 200:
        return r.json(), elapsed
    return {}, elapsed


def parse_timestamp_from_filename(filename_stem: str) -> str:
    """Parse timestamp from a filename stem.

    Attempts to extract a timestamp from the filename. Foscam cameras typically
    produce filenames like: MDAlarm_20250103_153045.jpg (date_time format).

    NEM-1096: Handles non-standard filename formats gracefully by logging a
    warning and returning "unknown" instead of crashing.

    Args:
        filename_stem: The filename without extension (e.g., "MDAlarm_20250103_153045")

    Returns:
        Extracted timestamp string, or "unknown" if parsing fails
    """
    try:
        # Expected format: {prefix}_{date}_{time} or just {date}_{time}
        # Example: MDAlarm_20250103_153045 -> "20250103_153045"
        if "_" not in filename_stem:
            print(f"  [Warning] Non-standard filename format (no underscore): {filename_stem}")
            return "unknown"

        parts = filename_stem.split("_")
        if len(parts) < 2:
            print(f"  [Warning] Non-standard filename format (insufficient parts): {filename_stem}")
            return "unknown"

        # Try to find date and time parts (8 digits for date, 6 for time)
        # Common patterns:
        # - MDAlarm_20250103_153045 -> parts[1] = date, parts[2] = time
        # - 20250103_153045 -> parts[0] = date, parts[1] = time
        # - camera_front_20250103_153045 -> last two parts are date and time
        for idx in range(len(parts) - 1):
            date_part = parts[idx]
            time_part = parts[idx + 1]
            # Check if these look like date (8 digits) and time (6 digits)
            if (
                len(date_part) == 8
                and date_part.isdigit()
                and len(time_part) == 6
                and time_part.isdigit()
            ):
                return f"{date_part}_{time_part}"

        # Fallback: return the last part which may be a timestamp
        last_part = parts[-1]
        if last_part.isdigit() and len(last_part) >= 6:
            return last_part

        print(f"  [Warning] Could not parse timestamp from filename: {filename_stem}")
        return "unknown"

    except Exception as e:
        print(f"  [Warning] Error parsing timestamp from {filename_stem}: {e}")
        return "unknown"


def analyze_with_nemotron(results: list[PipelineResult], client: httpx.Client) -> tuple[str, float]:
    """Send aggregated results to Nemotron for risk analysis.

    NEM-1095: Uses efficient list.append() + ''.join() pattern instead of
    string concatenation with += which is O(n^2) for large prompts.
    """
    # Build prompt from pipeline results using efficient list pattern
    prompt_parts: list[str] = []

    prompt_parts.append(
        """You are a home security AI analyst. Analyze the following camera detections and provide a risk assessment.

DETECTION SUMMARY:
"""
    )

    for i, result in enumerate(results, 1):
        # Build image header
        image_path = Path(result.image_path)
        # NEM-1096: Use robust timestamp parsing with graceful error handling
        timestamp = parse_timestamp_from_filename(image_path.stem)
        prompt_parts.append(
            f"""
--- Image {i}: {image_path.name} ---
Camera: {image_path.parent.parent.parent.name}
Timestamp: {timestamp}

Objects Detected ({len(result.detections)}):
"""
        )

        # Add detections (limit to top 10)
        for det in result.detections[:10]:
            label = det.get("label", "unknown")
            confidence = det.get("confidence", 0)
            prompt_parts.append(f"  - {label} (confidence: {confidence:.2f})\n")

        if result.caption:
            prompt_parts.append(f"\nScene Description (Florence-2):\n  {result.caption}\n")

        if result.vehicle_class:
            prompt_parts.append(
                f"\nVehicle Classification:\n  {json.dumps(result.vehicle_class, indent=2)}\n"
            )

        if result.pet_class and result.pet_class.get("predictions"):
            prompt_parts.append(
                f"\nPet Classification:\n  {json.dumps(result.pet_class, indent=2)}\n"
            )

        if result.embeddings:
            prompt_parts.append(
                f"\nCLIP Embedding: {len(result.embeddings)}-dimensional vector (for re-identification)\n"
            )

    prompt_parts.append(
        """
ANALYSIS REQUEST:
Based on the above detections from multiple cameras, provide:
1. Overall risk score (0-100)
2. Key observations
3. Any anomalies or concerns
4. Recommended actions

Be concise."""
    )

    # Join all parts efficiently in one operation
    prompt = "".join(prompt_parts)

    start = time.time()
    r = client.post(
        f"{SERVICES['llm']}/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.3,
        },
        timeout=120,
    )

    elapsed = time.time() - start
    if r.status_code == 200:
        data = r.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"].get("content", ""), elapsed
    return "", elapsed


def process_image(image_path: str, client: httpx.Client, verbose: bool = True) -> PipelineResult:
    """Process a single image through all pipeline stages."""
    result = PipelineResult(image_path=image_path)

    if verbose:
        print(f"\n  Processing: {Path(image_path).name}")

    # 1. Object Detection
    try:
        detections, elapsed = detect_objects(image_path, client)
        result.detections = detections
        result.timings["detection"] = elapsed
        if verbose:
            print(f"    [OK] Detection: {len(detections)} objects ({elapsed:.2f}s)")
    except Exception as e:
        result.errors.append(f"Detection failed: {e}")
        if verbose:
            print(f"    [FAIL] Detection failed: {e}")

    # 2. Florence-2 Caption
    try:
        caption, elapsed = get_caption(image_path, client)
        result.caption = caption
        result.timings["caption"] = elapsed
        if verbose:
            preview = caption[:80] + "..." if len(caption) > 80 else caption
            print(f'    [OK] Caption: "{preview}" ({elapsed:.2f}s)')
    except Exception as e:
        result.errors.append(f"Caption failed: {e}")
        if verbose:
            print(f"    [FAIL] Caption failed: {e}")

    # 3. CLIP Embedding
    try:
        embedding, elapsed = get_embedding(image_path, client)
        result.embeddings = embedding
        result.timings["embedding"] = elapsed
        if verbose:
            print(f"    [OK] CLIP Embedding: {len(embedding)}-dim ({elapsed:.2f}s)")
    except Exception as e:
        result.errors.append(f"Embedding failed: {e}")
        if verbose:
            print(f"    [FAIL] Embedding failed: {e}")

    # 4. Vehicle Classification
    try:
        vehicle, elapsed = classify_vehicle(image_path, client)
        result.vehicle_class = vehicle
        result.timings["vehicle"] = elapsed
        if verbose:
            if vehicle.get("predictions"):
                top = vehicle["predictions"][0]
                print(
                    f"    [OK] Vehicle: {top.get('label', 'none')} ({top.get('confidence', 0):.2f}) ({elapsed:.2f}s)"
                )
            else:
                print(f"    [OK] Vehicle: no vehicle detected ({elapsed:.2f}s)")
    except Exception as e:
        result.errors.append(f"Vehicle classification failed: {e}")
        if verbose:
            print(f"    [FAIL] Vehicle classification failed: {e}")

    # 5. Pet Classification
    try:
        pet, elapsed = classify_pet(image_path, client)
        result.pet_class = pet
        result.timings["pet"] = elapsed
        if verbose:
            if pet.get("predictions"):
                top = pet["predictions"][0]
                print(
                    f"    [OK] Pet: {top.get('label', 'none')} ({top.get('confidence', 0):.2f}) ({elapsed:.2f}s)"
                )
            else:
                print(f"    [OK] Pet: no pet detected ({elapsed:.2f}s)")
    except Exception as e:
        result.errors.append(f"Pet classification failed: {e}")
        if verbose:
            print(f"    [FAIL] Pet classification failed: {e}")

    return result


def save_test_fixtures(image_paths: list[str], output_dir: Path) -> None:
    """Copy test images to fixtures directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in image_paths:
        src = Path(path)
        dst = output_dir / src.name
        shutil.copy2(src, dst)
        print(f"  Saved: {dst}")


def main():
    parser = argparse.ArgumentParser(description="End-to-end AI pipeline test")
    parser.add_argument(
        "--images",
        nargs="+",
        help="Image paths to process (default: auto-select from /export/foscam)",
    )
    parser.add_argument(
        "--save-fixtures",
        action="store_true",
        help="Save test images to backend/tests/fixtures/images/",
    )
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    print("=" * 70)
    print("AI Model Zoo End-to-End Pipeline Test")
    print("=" * 70)

    # Check services
    print("\n1. Checking AI Services...")
    status = check_services()
    all_healthy = True
    for name, healthy in status.items():
        icon = "[OK]" if healthy else "[FAIL]"
        print(f"   {icon} {name}: {'healthy' if healthy else 'NOT AVAILABLE'}")
        if not healthy:
            all_healthy = False

    if not all_healthy:
        print("\n[Warning] Some services unavailable. Results may be incomplete.")

    # Select images
    if args.images:
        image_paths = args.images
    else:
        # Auto-select diverse images from different cameras
        print("\n2. Selecting test images...")
        foscam_base = Path("/export/foscam")
        image_paths = []
        for camera_dir in foscam_base.iterdir():
            if camera_dir.is_dir():
                images = list(camera_dir.rglob("*.jpg"))
                if images:
                    # Get most recent image
                    images.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    image_paths.append(str(images[0]))
                    print(f"   Selected: {images[0].name} from {camera_dir.name}")
                if len(image_paths) >= 4:  # Limit to 4 cameras
                    break

    if not image_paths:
        print("No images found!")
        return 1

    # Process images
    print(f"\n3. Processing {len(image_paths)} images through pipeline...")
    results = []

    with httpx.Client(timeout=60) as client:
        for path in image_paths:
            result = process_image(path, client, verbose=not args.quiet)
            results.append(result)

        # Nemotron analysis
        print("\n4. Running Nemotron risk analysis...")
        try:
            analysis, elapsed = analyze_with_nemotron(results, client)
            print(f"   [OK] Analysis complete ({elapsed:.2f}s)")
        except Exception as e:
            analysis = ""
            print(f"   [FAIL] Analysis failed: {e}")

    # Save fixtures if requested
    if args.save_fixtures:
        print("\n5. Saving test fixtures...")
        fixture_dir = Path("backend/tests/fixtures/images/pipeline_test")
        save_test_fixtures(image_paths, fixture_dir)

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    total_detections = sum(len(r.detections) for r in results)
    total_errors = sum(len(r.errors) for r in results)
    avg_times = {}
    for key in ["detection", "caption", "embedding", "vehicle", "pet"]:
        times = [r.timings.get(key, 0) for r in results if key in r.timings]
        if times:
            avg_times[key] = sum(times) / len(times)

    print(f"Images processed:     {len(results)}")
    print(f"Total detections:     {total_detections}")
    print(f"Total errors:         {total_errors}")
    print("\nAverage timings:")
    for key, val in avg_times.items():
        print(f"  {key:15} {val:.2f}s")

    if analysis:
        print(f"\n{'=' * 70}")
        print("NEMOTRON RISK ANALYSIS")
        print("=" * 70)
        print(analysis)

    print("\n" + "=" * 70)
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
