"""Example client for RT-DETRv2 detection server.

Demonstrates how to call the detection API from Python.
"""

import asyncio
import base64
from pathlib import Path

import httpx


async def check_health(base_url: str = "http://localhost:8090") -> dict:
    """Check server health status.

    Args:
        base_url: Base URL of detection server

    Returns:
        Health status dictionary
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/health")
        response.raise_for_status()
        return response.json()


async def detect_from_file(image_path: str | Path, base_url: str = "http://localhost:8090") -> dict:
    """Run object detection on an image file.

    Args:
        image_path: Path to image file
        base_url: Base URL of detection server

    Returns:
        Detection results dictionary
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        with Path(image_path).open("rb") as f:
            files = {"file": (image_path.name, f, "image/jpeg")}
            response = await client.post(f"{base_url}/detect", files=files)
            response.raise_for_status()
            return response.json()


async def detect_from_base64(
    image_path: str | Path, base_url: str = "http://localhost:8090"
) -> dict:
    """Run object detection using base64-encoded image.

    Args:
        image_path: Path to image file
        base_url: Base URL of detection server

    Returns:
        Detection results dictionary
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Read and encode image
    with Path(image_path).open("rb") as f:
        image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{base_url}/detect", json={"image_base64": image_base64})
        response.raise_for_status()
        return response.json()


async def detect_batch(
    image_paths: list[str | Path], base_url: str = "http://localhost:8090"
) -> dict:
    """Run batch object detection on multiple images.

    Args:
        image_paths: List of image file paths
        base_url: Base URL of detection server

    Returns:
        Batch detection results dictionary
    """
    files = []
    for image_path_item in image_paths:
        img_path = Path(image_path_item)
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")

        with img_path.open("rb") as f:
            files.append(("files", (img_path.name, f.read(), "image/jpeg")))

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{base_url}/detect/batch", files=files)
        response.raise_for_status()
        return response.json()


def print_detections(result: dict) -> None:
    """Pretty-print detection results.

    Args:
        result: Detection result dictionary
    """
    print(f"\nImage: {result.get('image_width')}x{result.get('image_height')}")
    print(f"Inference time: {result.get('inference_time_ms', 0):.1f}ms")
    print(f"Detections: {len(result.get('detections', []))}")

    for i, detection in enumerate(result.get("detections", []), 1):
        bbox = detection["bbox"]
        print(
            f"  {i}. {detection['class']} "
            f"({detection['confidence']:.2f}) "
            f"at [{bbox['x']}, {bbox['y']}, {bbox['width']}, {bbox['height']}]"
        )


async def main():
    """Example usage of detection client."""
    base_url = "http://localhost:8090"

    # Check server health
    print("Checking server health...")
    try:
        health = await check_health(base_url)
        print(f"Server status: {health['status']}")
        print(f"Model loaded: {health['model_loaded']}")
        print(f"Device: {health['device']}")
        print(f"CUDA available: {health['cuda_available']}")
        if health.get("vram_used_gb"):
            print(f"VRAM used: {health['vram_used_gb']:.2f} GB")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the detection server is running on port 8001")
        return

    # Example: Detect from file
    # Uncomment and provide a real image path to test
    """
    print("\n--- Single Image Detection ---")
    try:
        result = await detect_from_file("/path/to/image.jpg", base_url)
        print_detections(result)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Detection error: {e}")
    """

    # Example: Batch detection
    # Uncomment and provide real image paths to test
    """
    print("\n--- Batch Detection ---")
    try:
        image_paths = [
            "/path/to/image1.jpg",
            "/path/to/image2.jpg",
        ]
        result = await detect_batch(image_paths, base_url)
        print(f"Total inference time: {result['total_inference_time_ms']:.1f}ms")
        print(f"Images processed: {result['num_images']}")

        for img_result in result['results']:
            print(f"\n{img_result['filename']}:")
            print(f"  Detections: {len(img_result['detections'])}")
            for detection in img_result['detections']:
                bbox = detection['bbox']
                print(
                    f"    - {detection['class']} "
                    f"({detection['confidence']:.2f}) "
                    f"at [{bbox['x']}, {bbox['y']}]"
                )
    except Exception as e:
        print(f"Batch detection error: {e}")
    """

    print("\nExample client completed. Uncomment the example code to test with real images.")


if __name__ == "__main__":
    asyncio.run(main())
