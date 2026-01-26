#!/usr/bin/env python3
"""Quick test to exercise all AI models with specific test images."""

import base64
import sys
from pathlib import Path

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


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def test_image(image_path: Path, client: httpx.Client) -> dict:
    """Test a single image through all models."""
    results = {"image": image_path.name}
    image_b64 = encode_image(str(image_path))
    detections_data = []  # Store raw detections for enrichment

    # 1. YOLO26 Detection
    try:
        with open(image_path, "rb") as f:
            r = client.post(
                f"{SERVICES['detector']}/detect",
                files={"file": (image_path.name, f, "image/jpeg")},
                timeout=30,
            )
        if r.status_code == 200:
            dets = r.json().get("detections", [])
            detections_data = dets  # Store for enrichment
            results["detections"] = [f"{d['class']}({d['confidence']:.2f})" for d in dets[:5]]
        else:
            results["detections"] = f"Error: {r.status_code}"
    except Exception as e:
        results["detections"] = f"Error: {e}"

    # 2. Florence-2 Caption
    try:
        r = client.post(
            f"{SERVICES['florence']}/extract",
            json={"image": image_b64, "prompt": "<MORE_DETAILED_CAPTION>"},
            timeout=60,
        )
        if r.status_code == 200:
            caption = r.json().get("result", "")
            results["caption"] = caption[:150] + "..." if len(caption) > 150 else caption
        else:
            results["caption"] = f"Error: {r.status_code}"
    except Exception as e:
        results["caption"] = f"Error: {e}"

    # 3. CLIP Embedding
    try:
        r = client.post(
            f"{SERVICES['clip']}/embed",
            json={"image": image_b64},
            timeout=30,
        )
        if r.status_code == 200:
            emb = r.json().get("embedding", [])
            results["clip_embedding"] = f"{len(emb)}-dim vector"
        else:
            results["clip_embedding"] = f"Error: {r.status_code}"
    except Exception as e:
        results["clip_embedding"] = f"Error: {e}"

    # 4. Vehicle Classification (base64 JSON with bbox from detection)
    vehicle_dets = [
        d for d in detections_data if d.get("class") in ("car", "truck", "bus", "motorcycle")
    ]
    if vehicle_dets:
        try:
            # Use bbox from first vehicle detection
            # Convert {x, y, width, height} to [x1, y1, x2, y2] format
            det = vehicle_dets[0]
            bbox = det.get("bbox", {})
            x1 = bbox.get("x", 0)
            y1 = bbox.get("y", 0)
            x2 = x1 + bbox.get("width", 0)
            y2 = y1 + bbox.get("height", 0)
            r = client.post(
                f"{SERVICES['enrichment']}/vehicle-classify",
                json={
                    "image": image_b64,
                    "bbox": [x1, y1, x2, y2],
                },
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                # Response format: vehicle_type, display_name, confidence, is_commercial, all_scores
                vtype = data.get("vehicle_type", "unknown")
                display = data.get("display_name", vtype)
                conf = data.get("confidence", 0)
                commercial = "commercial" if data.get("is_commercial") else "non-commercial"
                results["vehicle"] = f"{display}({conf:.2f}) [{commercial}]"
            else:
                results["vehicle"] = f"Error: {r.status_code}"
        except Exception as e:
            results["vehicle"] = f"Error: {e}"
    else:
        results["vehicle"] = "No vehicle in detections"

    # 5. Pet Classification (base64 JSON with bbox from detection)
    pet_dets = [d for d in detections_data if d.get("class") in ("dog", "cat")]
    if pet_dets:
        try:
            # Use bbox from first pet detection
            # Convert {x, y, width, height} to [x1, y1, x2, y2] format
            det = pet_dets[0]
            bbox = det.get("bbox", {})
            x1 = bbox.get("x", 0)
            y1 = bbox.get("y", 0)
            x2 = x1 + bbox.get("width", 0)
            y2 = y1 + bbox.get("height", 0)
            r = client.post(
                f"{SERVICES['enrichment']}/pet-classify",
                json={
                    "image": image_b64,
                    "bbox": [x1, y1, x2, y2],
                },
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                # Response format: pet_type, breed, confidence, is_household_pet
                ptype = data.get("pet_type", "unknown")
                breed = data.get("breed", "unknown")
                conf = data.get("confidence", 0)
                household = "household" if data.get("is_household_pet") else "non-household"
                results["pet"] = f"{ptype}/{breed}({conf:.2f}) [{household}]"
            else:
                results["pet"] = f"Error: {r.status_code}"
        except Exception as e:
            results["pet"] = f"Error: {e}"
    else:
        results["pet"] = "No pet in detections"

    # 6. Clothing Classification (base64 JSON with bbox from person detection)
    person_dets = [d for d in detections_data if d.get("class") == "person"]
    if person_dets:
        try:
            # Use bbox from first person detection
            # Convert {x, y, width, height} to [x1, y1, x2, y2] format
            det = person_dets[0]
            bbox = det.get("bbox", {})
            x1 = bbox.get("x", 0)
            y1 = bbox.get("y", 0)
            x2 = x1 + bbox.get("width", 0)
            y2 = y1 + bbox.get("height", 0)
            r = client.post(
                f"{SERVICES['enrichment']}/clothing-classify",
                json={
                    "image": image_b64,
                    "bbox": [x1, y1, x2, y2],
                },
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                # Response format: clothing_type, color, style, confidence, is_suspicious, is_service_worker
                ctype = data.get("clothing_type", "unknown")
                color = data.get("color", "unknown")
                style = data.get("style", "unknown")
                conf = data.get("confidence", 0)
                flags = []
                if data.get("is_suspicious"):
                    flags.append("suspicious")
                if data.get("is_service_worker"):
                    flags.append("service")
                flag_str = f" [{','.join(flags)}]" if flags else ""
                results["clothing"] = f"{color} {ctype} ({style}, {conf:.2f}){flag_str}"
            elif r.status_code == 503:
                results["clothing"] = "FashionCLIP not loaded"
            else:
                results["clothing"] = f"Error: {r.status_code}"
        except Exception as e:
            results["clothing"] = f"Error: {e}"
    else:
        results["clothing"] = "No person in detections"

    return results


def main():
    # Select test images by category
    test_images = {
        "vehicles": [
            "test_vehicle_sedan_road.jpg",
            "test_vehicle_car_house.jpg",
            "test_vehicle_compact_building.jpg",
        ],
        "pets": [
            "test_pet_dog_yard_labrador.jpg",
            "test_pet_dog_grass_brown.jpg",
            "test_pet_cat_porch_tabby.jpg",
        ],
        "people/scenes": [
            "test_person_house_front.jpg",
            "test_person_porch_1.jpg",
            "test_person_walking_dog.jpg",
        ],
    }

    print("=" * 80)
    print("AI Model Zoo - Comprehensive Test")
    print("=" * 80)

    with httpx.Client(timeout=60) as client:
        for category, images in test_images.items():
            print(f"\n{'=' * 80}")
            print(f"Category: {category.upper()}")
            print("=" * 80)

            for img_name in images:
                img_path = FIXTURE_DIR / img_name
                if not img_path.exists():
                    print(f"\n⚠ {img_name}: NOT FOUND")
                    continue

                print(f"\n--- {img_name} ---")
                results = test_image(img_path, client)

                # Print results
                print(f"  Detections:  {results.get('detections', 'N/A')}")
                print(f"  Caption:     {results.get('caption', 'N/A')}")
                print(f"  CLIP:        {results.get('clip_embedding', 'N/A')}")
                print(f"  Vehicle:     {results.get('vehicle', 'N/A')}")
                print(f"  Pet:         {results.get('pet', 'N/A')}")
                print(f"  Clothing:    {results.get('clothing', 'N/A')}")

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
