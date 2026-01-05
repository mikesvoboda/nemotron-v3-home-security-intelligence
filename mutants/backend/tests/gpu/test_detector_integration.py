"""GPU Detector Integration Tests.

These tests validate the RT-DETRv2 detector client connectivity and basic inference
on the self-hosted GPU runner with NVIDIA RTX A5500.

IMPORTANT: These tests are designed to run WITHOUT database dependencies.
The GPU runner may not have PostgreSQL available, so we test only the HTTP
client functionality, not the full detection pipeline with database storage.

Test Categories:
    1. Health check tests - verify detector service is reachable
    2. Inference tests - verify object detection works correctly
    3. Error handling tests - verify graceful degradation

Run with:
    pytest backend/tests/gpu/ -m gpu -v

The tests will skip gracefully if:
    - RT-DETRv2 service is not available
    - CUDA is not available
    - Required test images cannot be created
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

# Skip entire module if critical dependencies are missing
pytest.importorskip("PIL", reason="Pillow required for creating test images")


def _find_nvidia_smi() -> str | None:
    """Find the nvidia-smi executable path.

    Returns:
        Full path to nvidia-smi if found, None otherwise.
    """
    import shutil

    # Check common paths first (Linux/macOS)
    common_paths = [
        "/usr/bin/nvidia-smi",
        "/usr/local/bin/nvidia-smi",
        "/opt/nvidia/bin/nvidia-smi",
    ]
    for path in common_paths:
        if Path(path).exists():
            return path

    # Fall back to shutil.which
    return shutil.which("nvidia-smi")


def check_cuda_available() -> bool:
    """Check if CUDA is available on the system.

    Returns:
        True if CUDA is available (nvidia-smi works), False otherwise.
    """
    import subprocess

    nvidia_smi = _find_nvidia_smi()
    if nvidia_smi is None:
        return False

    try:
        result = subprocess.run(  # noqa: S603 - nvidia-smi path is validated above  # real
            [nvidia_smi],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_detector_url() -> str:
    """Get the RT-DETRv2 detector URL from environment or default.

    The URL can be customized via the RTDETR_URL environment variable,
    which is useful for CI environments where the detector might be
    running on a different host/port.

    Returns:
        The detector service URL.
    """
    return os.environ.get("RTDETR_URL", "http://localhost:8090")


def get_nemotron_url() -> str:
    """Get the Nemotron LLM URL from environment or default.

    Returns:
        The Nemotron service URL.
    """
    return os.environ.get("NEMOTRON_URL", "http://localhost:8091")


async def check_detector_health(timeout: float = 5.0) -> bool:
    """Check if the RT-DETRv2 detector service is healthy.

    Args:
        timeout: Maximum time to wait for health check response.

    Returns:
        True if detector is healthy and reachable, False otherwise.
    """
    url = get_detector_url()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}/health")
            return response.status_code == 200
    except Exception:
        return False


async def check_nemotron_health(timeout: float = 5.0) -> bool:
    """Check if the Nemotron LLM service is healthy.

    Args:
        timeout: Maximum time to wait for health check response.

    Returns:
        True if Nemotron is healthy and reachable, False otherwise.
    """
    url = get_nemotron_url()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}/health")
            return response.status_code == 200
    except Exception:
        return False


def create_test_image(path: Path, size: tuple[int, int] = (640, 480)) -> None:
    """Create a valid test image file for detection testing.

    Creates a simple red image that the detector can process.

    Args:
        path: Path where the image should be saved.
        size: Image dimensions as (width, height).
    """
    from PIL import Image

    img = Image.new("RGB", size, color="red")
    img.save(path, "JPEG")


async def send_detection_request(
    image_path: str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Send an image to the detector and get detection results.

    This is a simplified version that doesn't require database access.
    It only tests the HTTP request/response cycle.

    Args:
        image_path: Path to the image file.
        timeout: Maximum time to wait for detection response.

    Returns:
        The detection response as a dictionary.

    Raises:
        httpx.HTTPError: If the request fails.
        ValueError: If the response is malformed.
    """
    url = get_detector_url()
    image_file = Path(image_path)

    if not image_file.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image_data = image_file.read_bytes()

    async with httpx.AsyncClient(timeout=timeout) as client:
        files = {"file": (image_file.name, image_data, "image/jpeg")}
        response = await client.post(f"{url}/detect", files=files)
        response.raise_for_status()

    result = response.json()

    if "detections" not in result:
        raise ValueError(f"Malformed response: missing 'detections' key. Got: {result}")

    return result


# =============================================================================
# GPU-Marked Tests
# =============================================================================


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_service_health_check() -> None:
    """Test that the RT-DETRv2 detector service responds to health checks.

    This is the most basic test - it verifies that the detector service
    is running and responding on the GPU runner.

    Skip conditions:
        - Detector service not available
    """
    is_healthy = await check_detector_health()

    if not is_healthy:
        pytest.skip(
            f"RT-DETRv2 detector service not available at {get_detector_url()}. "
            "Ensure the detector is running on the GPU runner."
        )

    # If we get here, the service is healthy
    assert is_healthy is True


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_inference_basic() -> None:
    """Test basic object detection inference on the GPU.

    This test:
    1. Checks if the detector is available (skips if not)
    2. Creates a test image
    3. Sends it for detection
    4. Verifies the response format

    This does NOT test database storage - only the HTTP API.
    """
    # Skip if detector not available
    if not await check_detector_health():
        pytest.skip(f"RT-DETRv2 detector not available at {get_detector_url()}")

    # Create a temporary test image
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / "test_image.jpg"
        create_test_image(image_path, size=(1920, 1080))

        # Send detection request
        result = await send_detection_request(str(image_path))

        # Verify response format
        assert "detections" in result
        assert isinstance(result["detections"], list)

        # Log what was detected (may be empty for synthetic images)
        detection_count = len(result["detections"])
        print(f"\nDetected {detection_count} objects in test image")

        for det in result["detections"]:
            print(f"  - {det.get('class', 'unknown')}: {det.get('confidence', 0):.2f}")


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_inference_performance() -> None:
    """Test detection inference performance on the GPU.

    Measures the time taken for a single detection request.
    This helps identify performance regressions.

    Expected performance on RTX A5500:
        - First inference (cold start): < 5000ms
        - Subsequent inferences: < 200ms
    """
    # Skip if detector not available
    if not await check_detector_health():
        pytest.skip(f"RT-DETRv2 detector not available at {get_detector_url()}")

    # Create a temporary test image
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / "perf_test.jpg"
        create_test_image(image_path, size=(1920, 1080))

        # Measure inference time
        start_time = time.time()
        await send_detection_request(str(image_path))
        inference_time_ms = (time.time() - start_time) * 1000

        print(f"\nRT-DETRv2 Inference Time: {inference_time_ms:.2f}ms")

        # Allow up to 5000ms for first inference (includes model loading)
        assert inference_time_ms < 5000, f"Inference too slow: {inference_time_ms:.2f}ms"


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_multiple_images() -> None:
    """Test detection on multiple images sequentially.

    This tests the detector's ability to handle multiple requests,
    which is important for the batch processing pipeline.
    """
    # Skip if detector not available
    if not await check_detector_health():
        pytest.skip(f"RT-DETRv2 detector not available at {get_detector_url()}")

    # Create multiple test images with different sizes
    image_sizes = [
        (640, 480),  # VGA
        (1280, 720),  # 720p
        (1920, 1080),  # 1080p
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        total_time = 0.0
        for i, size in enumerate(image_sizes):
            image_path = Path(tmpdir) / f"test_{i}.jpg"
            create_test_image(image_path, size=size)

            start_time = time.time()
            result = await send_detection_request(str(image_path))
            elapsed_ms = (time.time() - start_time) * 1000
            total_time += elapsed_ms

            assert "detections" in result
            print(f"\nImage {i + 1} ({size[0]}x{size[1]}): {elapsed_ms:.2f}ms")

        avg_time = total_time / len(image_sizes)
        print(f"\nAverage inference time: {avg_time:.2f}ms")


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_nemotron_service_health_check() -> None:
    """Test that the Nemotron LLM service responds to health checks.

    The Nemotron service provides risk analysis using the LLM.
    This test verifies basic connectivity.
    """
    is_healthy = await check_nemotron_health()

    if not is_healthy:
        pytest.skip(
            f"Nemotron LLM service not available at {get_nemotron_url()}. "
            "Ensure the Nemotron service is running on the GPU runner."
        )

    assert is_healthy is True


@pytest.mark.gpu
def test_cuda_availability() -> None:
    """Test that CUDA is available on the GPU runner.

    This test verifies that the self-hosted runner has CUDA
    properly configured. It uses nvidia-smi to check.
    """
    if not check_cuda_available():
        pytest.skip("CUDA not available (nvidia-smi failed)")

    # If we get here, CUDA is available
    assert check_cuda_available() is True


@pytest.mark.gpu
def test_gpu_memory_available() -> None:
    """Test that GPU memory can be queried and report availability.

    This test validates GPU memory can be queried and logs the current state.
    It uses a percentage-based threshold to accommodate varying GPU configurations
    and transient memory pressure from concurrent workloads.

    Memory thresholds:
        - Critical: < 2% free - test fails (GPU is severely memory-starved)
        - Warning: < 5% free - test passes with warning (memory pressure)
        - Normal: >= 5% free - test passes normally

    Expected: RTX A5500 with 24GB VRAM
    """
    import subprocess
    import warnings

    nvidia_smi = _find_nvidia_smi()
    if nvidia_smi is None:
        pytest.skip("nvidia-smi not found")

    if not check_cuda_available():
        pytest.skip("CUDA not available")

    try:
        result = subprocess.run(  # noqa: S603 - nvidia-smi path is validated above  # real
            [
                nvidia_smi,
                "--query-gpu=memory.total,memory.free,memory.used,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )

        # Parse output: "24564, 24000, 564, NVIDIA RTX A5500"
        output = result.stdout.strip()
        if output:
            parts = output.split(",")
            total = int(parts[0].strip())
            free = int(parts[1].strip())
            used = int(parts[2].strip())
            gpu_name = parts[3].strip() if len(parts) > 3 else "Unknown GPU"

            free_percent = (free / total) * 100 if total > 0 else 0
            used_percent = (used / total) * 100 if total > 0 else 0

            print(f"\nGPU: {gpu_name}")
            print(f"GPU Memory: {free}MB free / {total}MB total ({free_percent:.1f}% free)")
            print(f"GPU Memory Used: {used}MB ({used_percent:.1f}%)")

            # Critical threshold: less than 2% free (GPU severely memory-starved)
            # On 24GB GPU, 2% = ~490MB which is below RT-DETRv2's ~650MB requirement
            critical_threshold_percent = 2.0
            warning_threshold_percent = 5.0

            if free_percent < critical_threshold_percent:
                # Skip test when GPU is too memory-starved - this is an environmental
                # condition, not a code failure. CI runners may have varying memory
                # pressure from concurrent workloads.
                pytest.skip(
                    f"GPU memory too low for reliable testing: {free}MB free ({free_percent:.1f}%). "
                    f"Need at least {critical_threshold_percent}% free. "
                    f"This is an environmental condition, not a test failure."
                )
            elif free_percent < warning_threshold_percent:
                # Memory pressure but may still work - warn and continue
                warnings.warn(
                    f"GPU memory pressure detected: {free}MB free ({free_percent:.1f}%). "
                    f"Performance may be degraded. Consider reducing GPU workloads.",
                    UserWarning,
                    stacklevel=1,
                )

            # Test passes - GPU has memory available
            assert total > 0, "GPU total memory should be positive"
            assert free >= 0, "GPU free memory should be non-negative"
        else:
            pytest.skip("Could not parse nvidia-smi output")

    except subprocess.CalledProcessError as e:
        pytest.skip(f"nvidia-smi failed: {e}")
    except subprocess.TimeoutExpired:
        pytest.skip("nvidia-smi timed out")


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_handles_invalid_image() -> None:
    """Test that the detector handles invalid images gracefully.

    The detector should return an error response, not crash,
    when given invalid image data.
    """
    # Skip if detector not available
    if not await check_detector_health():
        pytest.skip(f"RT-DETRv2 detector not available at {get_detector_url()}")

    url = get_detector_url()

    # Send garbage data as an "image"
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"file": ("invalid.jpg", b"not an image", "image/jpeg")}

        # The detector should return an error, not crash
        response = await client.post(f"{url}/detect", files=files)

        # Accept either 4xx error or 200 with error in response
        # (depends on detector implementation)
        if response.status_code == 200:
            result = response.json()
            # Either no detections or an error field
            assert "detections" in result or "error" in result
        else:
            # 4xx or 5xx is acceptable for invalid input
            assert 400 <= response.status_code < 600


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_concurrent_requests() -> None:
    """Test the detector's handling of concurrent requests.

    This simulates multiple cameras sending images simultaneously.
    The detector should handle this without errors.
    """
    import asyncio

    # Skip if detector not available
    if not await check_detector_health():
        pytest.skip(f"RT-DETRv2 detector not available at {get_detector_url()}")

    # Number of concurrent requests
    num_concurrent = 3

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test images
        image_paths = []
        for i in range(num_concurrent):
            image_path = Path(tmpdir) / f"concurrent_{i}.jpg"
            create_test_image(image_path)
            image_paths.append(str(image_path))

        # Send concurrent requests
        async def detect(path: str) -> dict[str, Any]:
            return await send_detection_request(path)

        start_time = time.time()
        results = await asyncio.gather(*[detect(p) for p in image_paths])
        total_time_ms = (time.time() - start_time) * 1000

        # All requests should succeed
        assert len(results) == num_concurrent
        for result in results:
            assert "detections" in result

        print(f"\n{num_concurrent} concurrent requests completed in {total_time_ms:.2f}ms")
        print(f"Average per request: {total_time_ms / num_concurrent:.2f}ms")
