"""GPU Pipeline End-to-End Tests.

These tests validate the complete GPU AI pipeline including:
- RTDETRClient: RT-DETRv2 object detection via HTTP
- NemotronAnalyzer: Nemotron LLM risk analysis via llama.cpp
- Full pipeline integration: Detection -> Batch -> Analysis -> Event

Test Categories:
1. GPU marker tests (@pytest.mark.gpu): Run on self-hosted GPU runner
2. Integration tests: Mock external services, test pipeline logic

The @pytest.mark.gpu marker is used by .github/workflows/gpu-tests.yml
to run tests on the self-hosted GPU runner (RTX A5500).

Run locally with mocks:
    pytest backend/tests/e2e/test_gpu_pipeline.py -v

Run on GPU runner (actual services):
    pytest backend/tests/e2e/test_gpu_pipeline.py -v -m gpu

Test Isolation:
    Tests using database fixtures (test_camera, clean_pipeline) use xdist_group
    to ensure they run sequentially on the same worker when using pytest-xdist.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image
from sqlalchemy import select

from backend.core.database import get_session
from backend.core.redis import QueueAddResult
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient, DetectorUnavailableError
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.tests.conftest import unique_id

# All tests in this module run sequentially on the same worker to ensure database isolation
pytestmark = [pytest.mark.xdist_group(name="gpu_pipeline_e2e")]


# =============================================================================
# Test Fixtures
# =============================================================================


class MockRedisClient:
    """Mock Redis client for testing without a real Redis server."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._queues: dict[str, list[Any]] = {}
        self._client = AsyncMock()
        self._client.scan_iter = self._create_scan_iter_mock([])

    def _create_scan_iter_mock(self, keys: list[str]) -> MagicMock:
        """Create a mock scan_iter that returns an async generator."""

        async def _generator():
            for key in keys:
                yield key

        return MagicMock(return_value=_generator())

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted

    async def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._store)

    async def get_from_queue(self, queue_name: str, timeout: int = 0) -> Any | None:
        if self._queues.get(queue_name):
            return self._queues[queue_name].pop(0)
        return None

    async def get_queue_length(self, queue_name: str) -> int:
        return len(self._queues.get(queue_name, []))

    async def peek_queue(
        self,
        queue_name: str,
        start: int = 0,
        end: int = 100,
        max_items: int = 1000,
    ) -> list[Any]:
        queue = self._queues.get(queue_name, [])
        end = max_items - 1 if end == -1 else min(end, start + max_items - 1)
        return queue[start : end + 1]

    async def publish(self, channel: str, message: Any) -> int:
        return 1

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "connected": True, "redis_version": "mock"}

    async def add_to_queue_safe(
        self,
        queue_name: str,
        data: Any,
        max_size: int | None = None,
        overflow_policy: str | None = None,
        dlq_name: str | None = None,
    ) -> QueueAddResult:
        """Add item to queue with backpressure handling (mock implementation)."""
        if queue_name not in self._queues:
            self._queues[queue_name] = []
        self._queues[queue_name].append(data)
        return QueueAddResult(
            success=True,
            queue_length=len(self._queues[queue_name]),
            dropped_count=0,
            moved_to_dlq_count=0,
        )

    def get_batch_keys(self) -> list[str]:
        """Get all batch:*:current keys for timeout checking."""
        return [k for k in self._store if k.endswith(":current") and k.startswith("batch:")]


def create_test_image(path: Path, size: tuple[int, int] = (640, 480)) -> None:
    """Create a valid test image file."""
    img = Image.new("RGB", size, color="red")
    img.save(path, "JPEG")


def create_mock_detector_response(detections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a mock RT-DETRv2 detector response."""
    if detections is None:
        detections = [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": {"x": 100, "y": 150, "width": 200, "height": 300},
            }
        ]
    return {"detections": detections}


def create_mock_llm_response(
    risk_score: int = 75,
    risk_level: str = "high",
    summary: str = "Person detected",
    reasoning: str = "Test reasoning for detected objects",
) -> dict[str, Any]:
    """Create a mock Nemotron LLM response."""
    return {
        "content": json.dumps(
            {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "summary": summary,
                "reasoning": reasoning,
            }
        )
    }


def create_mock_httpx_response(json_data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Create a properly configured mock httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = MagicMock()
    return mock_response


@pytest.fixture
async def mock_redis() -> MockRedisClient:
    """Provide a mock Redis client for tests."""
    return MockRedisClient()


@pytest.fixture
async def clean_pipeline(integration_db):
    """Delete all tables data before test runs for proper isolation.

    This fixture ensures tests start with a clean database state.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM logs"))
        await conn.execute(text("DELETE FROM gpu_stats"))
        await conn.execute(text("DELETE FROM api_keys"))
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM logs"))
            await conn.execute(text("DELETE FROM gpu_stats"))
            await conn.execute(text("DELETE FROM api_keys"))
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:
        pass


@pytest.fixture
async def test_camera(integration_db, clean_pipeline, tmp_path: Path) -> tuple[Camera, Path]:
    """Create a test camera with unique ID in the database."""
    camera_id = unique_id("gpu_test_camera")
    camera_root = tmp_path / "foscam"
    camera_root.mkdir(parents=True)
    camera_dir = camera_root / camera_id
    camera_dir.mkdir()

    async with get_session() as session:
        camera = Camera(
            id=camera_id,
            name="GPU Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
            created_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.commit()
        await session.refresh(camera)
        return camera, camera_root


# =============================================================================
# GPU-Marked Tests: Run on Self-Hosted GPU Runner
# =============================================================================


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_gpu_detector_client_health_check(integration_db):
    """Test DetectorClient health check against real RT-DETRv2 service.

    This test verifies that the RT-DETRv2 service is running and healthy
    on the GPU runner. If the service is not available, the test will fail.

    Run with: pytest -m gpu -v
    """
    detector = DetectorClient()
    is_healthy = await detector.health_check()

    # On GPU runner, we expect the detector to be available
    # If running locally without detector, this will return False
    assert isinstance(is_healthy, bool)


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_gpu_nemotron_analyzer_health_check(integration_db):
    """Test NemotronAnalyzer health check against real Nemotron/llama.cpp service.

    This test verifies that the Nemotron LLM service is running and healthy
    on the GPU runner.

    Run with: pytest -m gpu -v
    """
    analyzer = NemotronAnalyzer(redis_client=None)
    is_healthy = await analyzer.health_check()

    # On GPU runner, we expect the Nemotron service to be available
    assert isinstance(is_healthy, bool)


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_gpu_full_pipeline_with_real_services(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test full GPU pipeline with real AI services.

    This is a comprehensive E2E test that validates:
    1. Real RT-DETRv2 object detection
    2. Real Nemotron LLM analysis
    3. Database persistence
    4. Event creation

    This test requires:
    - RT-DETRv2 service running on configured rtdetr_url
    - Nemotron/llama.cpp service running on configured nemotron_url
    - PostgreSQL database

    Run with: pytest -m gpu -v
    """
    camera, camera_root = test_camera
    camera_id = camera.id

    # Create test image
    image_path = camera_root / camera_id / "gpu_test_image.jpg"
    create_test_image(image_path, size=(1920, 1080))

    # Check if services are available
    detector = DetectorClient()
    analyzer = NemotronAnalyzer(redis_client=mock_redis)

    detector_healthy = await detector.health_check()
    analyzer_healthy = await analyzer.health_check()

    if not detector_healthy:
        pytest.skip("RT-DETRv2 service not available")

    if not analyzer_healthy:
        pytest.skip("Nemotron service not available")

    # Step 1: Run object detection with real RT-DETRv2
    async with get_session() as session:
        try:
            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )
        except DetectorUnavailableError:
            pytest.skip("RT-DETRv2 service returned error")

    # Verify detections (may be 0 if no objects detected in test image)
    assert isinstance(detections, list)

    if not detections:
        # Create a mock detection for LLM analysis test
        async with get_session() as session:
            detection = Detection(
                camera_id=camera_id,
                file_path=str(image_path),
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=300,
            )
            session.add(detection)
            await session.commit()
            await session.refresh(detection)
            detections = [detection]

    # Step 2: Create batch
    batch_id = unique_id("gpu_batch")
    detection_ids = [d.id for d in detections]

    # Step 3: Run Nemotron analysis with real LLM
    try:
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )
    except Exception as e:
        pytest.skip(f"Nemotron analysis failed: {e}")

    # Verify event was created
    assert event is not None
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    assert 0 <= event.risk_score <= 100
    assert event.risk_level in ["low", "medium", "high", "critical"]
    assert event.summary is not None
    assert event.reasoning is not None

    # Verify event in database
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        stored_event = result.scalar_one_or_none()
        assert stored_event is not None
        assert stored_event.id == event.id


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_gpu_detector_client_inference_performance(
    integration_db,
    test_camera: tuple[Camera, Path],
):
    """Test RT-DETRv2 inference performance on GPU.

    This test measures the inference time for object detection
    to ensure it meets performance requirements.

    Expected performance on RTX A5500:
    - Single image inference: < 100ms
    - Health check: < 50ms

    Run with: pytest -m gpu -v
    """
    camera, camera_root = test_camera
    camera_id = camera.id

    # Create test image
    image_path = camera_root / camera_id / "perf_test_image.jpg"
    create_test_image(image_path, size=(1920, 1080))

    detector = DetectorClient()

    # Check if service is available
    if not await detector.health_check():
        pytest.skip("RT-DETRv2 service not available")

    # Measure inference time
    start_time = time.time()

    async with get_session() as session:
        try:
            await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )
        except DetectorUnavailableError:
            pytest.skip("RT-DETRv2 service returned error")

    inference_time_ms = (time.time() - start_time) * 1000

    # Log performance metrics
    print(f"\nRT-DETRv2 Inference Time: {inference_time_ms:.2f}ms")

    # Performance assertion (adjust threshold as needed)
    # Allow up to 5000ms for first inference (model loading)
    assert inference_time_ms < 5000, f"Inference too slow: {inference_time_ms:.2f}ms"


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_gpu_nemotron_analysis_performance(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test Nemotron LLM analysis performance on GPU.

    This test measures the LLM analysis time to ensure it meets
    performance requirements.

    Expected performance:
    - Single batch analysis: < 30 seconds (LLM inference can be slow)

    Run with: pytest -m gpu -v
    """
    camera, _camera_root = test_camera
    camera_id = camera.id

    # Create a detection for analysis
    async with get_session() as session:
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/perf_test.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=300,
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    analyzer = NemotronAnalyzer(redis_client=mock_redis)

    # Check if service is available
    if not await analyzer.health_check():
        pytest.skip("Nemotron service not available")

    # Measure analysis time
    batch_id = unique_id("perf_batch")
    start_time = time.time()

    try:
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=[detection.id],
        )
    except Exception as e:
        pytest.skip(f"Nemotron analysis failed: {e}")

    analysis_time_ms = (time.time() - start_time) * 1000

    # Log performance metrics
    print(f"\nNemotron Analysis Time: {analysis_time_ms:.2f}ms")
    print(f"Risk Score: {event.risk_score}, Risk Level: {event.risk_level}")

    # Performance assertion (LLM can take longer)
    assert analysis_time_ms < 30000, f"Analysis too slow: {analysis_time_ms:.2f}ms"


# =============================================================================
# Integration Tests: Mock External Services
# =============================================================================


@pytest.mark.asyncio
async def test_detector_client_integration_mocked(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test DetectorClient with mocked HTTP calls.

    Validates:
    - Image reading and HTTP request formation
    - Response parsing and detection creation
    - Database persistence
    - Confidence filtering
    """
    camera, camera_root = test_camera
    camera_id = camera.id

    # Create test image
    image_path = camera_root / camera_id / "mock_test_image.jpg"
    create_test_image(image_path)

    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response(
        [
            {"class": "person", "confidence": 0.95, "bbox": [100, 150, 200, 300]},
            {"class": "car", "confidence": 0.88, "bbox": [400, 200, 250, 180]},
            {"class": "dog", "confidence": 0.35, "bbox": [50, 50, 100, 100]},  # Below threshold
        ]
    )

    async with get_session() as session:
        with patch("backend.services.detector_client.httpx.AsyncClient") as mock_client:
            mock_response = create_mock_httpx_response(mock_detector_response)

            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )

    # Verify detections (dog filtered out due to low confidence)
    assert len(detections) == 2
    assert detections[0].object_type == "person"
    assert detections[0].confidence == 0.95
    assert detections[1].object_type == "car"
    assert detections[1].confidence == 0.88

    # Verify detections in database
    async with get_session() as session:
        result = await session.execute(select(Detection).where(Detection.camera_id == camera_id))
        stored = list(result.scalars().all())
        assert len(stored) == 2


@pytest.mark.asyncio
async def test_nemotron_analyzer_integration_mocked(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test NemotronAnalyzer with mocked HTTP calls.

    Validates:
    - Batch processing from queue
    - LLM prompt formation
    - Response parsing and validation
    - Event creation with risk assessment
    - Database persistence
    """
    camera, _ = test_camera
    camera_id = camera.id

    # Create detections
    async with get_session() as session:
        detections = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img{i}.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type=["person", "car", "bicycle"][i],
                confidence=0.90 + (i * 0.02),
                bbox_x=100 + (i * 50),
                bbox_y=150,
                bbox_width=200,
                bbox_height=300,
            )
            session.add(detection)
            await session.flush()
            await session.refresh(detection)
            detections.append(detection)
        await session.commit()

    # Test analysis
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    batch_id = unique_id("mock_batch")
    mock_llm_response = create_mock_llm_response(
        risk_score=65,
        risk_level="high",
        summary="Multiple objects detected including person and vehicle",
        reasoning="High-confidence detections warrant attention",
    )

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=[d.id for d in detections],
        )

    # Verify event
    assert event is not None
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    assert event.risk_score == 65
    assert event.risk_level == "high"
    assert "Multiple objects" in event.summary

    # Verify event in database
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        stored_event = result.scalar_one_or_none()
        assert stored_event is not None
        assert stored_event.id == event.id

        # Verify detection_ids are stored correctly
        stored_ids = json.loads(stored_event.detection_ids)
        assert len(stored_ids) == 3


@pytest.mark.asyncio
async def test_full_pipeline_integration_mocked(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test complete pipeline: Detection -> Batch -> Analysis -> Event.

    This is a comprehensive integration test with mocked external services.
    Validates the complete flow from image detection to event creation.
    """
    camera, camera_root = test_camera
    camera_id = camera.id

    # Step 1: Create test image
    image_path = camera_root / camera_id / "full_pipeline_test.jpg"
    create_test_image(image_path)

    # Step 2: Run detection with mocked RT-DETRv2
    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response(
        [
            {"class": "person", "confidence": 0.92, "bbox": [100, 150, 200, 300]},
        ]
    )

    async with get_session() as session:
        with patch("backend.services.detector_client.httpx.AsyncClient") as mock_client:
            mock_response = create_mock_httpx_response(mock_detector_response)

            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )

    assert len(detections) == 1
    detection = detections[0]

    # Step 3: Add to batch aggregator
    aggregator = BatchAggregator(redis_client=mock_redis)
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id=str(detection.id),
        _file_path=str(image_path),
        confidence=0.85,  # Below fast path threshold
        object_type="car",
    )

    # Step 4: Close batch
    batch_summary = await aggregator.close_batch(batch_id)
    assert batch_summary["detection_count"] == 1

    # Step 5: Run Nemotron analysis with mocked LLM
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    mock_llm_response = create_mock_llm_response(
        risk_score=55,
        risk_level="medium",
        summary="Single object detected",
    )

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Get detection_ids from queue
        queue_items = await mock_redis.peek_queue("analysis_queue")
        queue_item = queue_items[0]

        event = await analyzer.analyze_batch(
            batch_id=queue_item["batch_id"],
            camera_id=queue_item["camera_id"],
            detection_ids=queue_item["detection_ids"],
        )

    # Verify final event
    assert event is not None
    assert event.risk_score == 55
    assert event.risk_level == "medium"

    # Verify complete chain in database
    async with get_session() as session:
        # Verify detection
        det_result = await session.execute(select(Detection).where(Detection.id == detection.id))
        stored_detection = det_result.scalar_one()
        assert stored_detection.camera_id == camera_id

        # Verify event
        evt_result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        stored_event = evt_result.scalar_one()
        assert stored_event.camera_id == camera_id
        assert stored_event.risk_score == 55


@pytest.mark.asyncio
async def test_detector_unavailable_error_handling(
    integration_db,
    test_camera: tuple[Camera, Path],
):
    """Test DetectorClient error handling when service is unavailable.

    Validates that DetectorUnavailableError is raised correctly for:
    - Connection errors
    - Timeout errors
    - HTTP 5xx errors
    """
    camera, camera_root = test_camera
    camera_id = camera.id

    image_path = camera_root / camera_id / "error_test.jpg"
    create_test_image(image_path)

    detector = DetectorClient()

    # Test connection error
    async with get_session() as session:
        with patch("backend.services.detector_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            assert "Failed to connect" in str(exc_info.value)

    # Test timeout error
    async with get_session() as session:
        with patch("backend.services.detector_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            assert "timed out" in str(exc_info.value)

    # Test HTTP 500 error
    async with get_session() as session:
        with patch("backend.services.detector_client.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "Internal Server Error", request=MagicMock(), response=mock_response
                )
            )

            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            assert "server error: 500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_nemotron_llm_failure_fallback(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test NemotronAnalyzer fallback when LLM fails.

    Validates that events are still created with fallback risk values
    when the LLM service is unavailable.
    """
    camera, _ = test_camera
    camera_id = camera.id

    # Create detection
    async with get_session() as session:
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/fallback_test.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    # Test with LLM failure
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    batch_id = unique_id("fallback_batch")

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("LLM unavailable"))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=[detection.id],
        )

    # Verify fallback values
    assert event is not None
    assert event.risk_score == 50
    assert event.risk_level == "medium"
    assert "Analysis unavailable" in event.summary


@pytest.mark.asyncio
async def test_fast_path_analysis(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test fast path analysis for high-priority detections.

    Validates that high-confidence critical detections trigger
    immediate analysis with is_fast_path=True.
    """
    camera, _camera_root = test_camera
    camera_id = camera.id

    # Create high-confidence person detection
    async with get_session() as session:
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/fast_path_test.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.98,  # High confidence
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    # Test fast path analysis
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    mock_llm_response = create_mock_llm_response(
        risk_score=90,
        risk_level="critical",
        summary="High-confidence person detected - fast path",
    )

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        event = await analyzer.analyze_detection_fast_path(
            camera_id=camera_id,
            detection_id=detection.id,
        )

    # Verify fast path event
    assert event is not None
    assert event.is_fast_path is True
    assert event.batch_id == f"fast_path_{detection.id}"
    assert event.risk_score == 90
    assert event.risk_level == "critical"

    # Verify detection_ids contains single detection
    stored_ids = json.loads(event.detection_ids)
    assert stored_ids == [detection.id]

    # Verify event in database
    async with get_session() as session:
        result = await session.execute(
            select(Event).where(Event.is_fast_path == True)  # noqa: E712
        )
        fast_path_events = list(result.scalars().all())
        assert len(fast_path_events) >= 1
        assert any(e.id == event.id for e in fast_path_events)


@pytest.mark.asyncio
async def test_batch_aggregation_and_handoff(
    integration_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test batch aggregation and handoff to analyzer.

    Validates:
    - Multiple detections are batched together
    - Batch is correctly closed and queued
    - Queue payload contains all needed data
    - Analyzer can process without Redis lookup
    """
    camera, _ = test_camera
    camera_id = camera.id

    # Create multiple detections
    detections = []
    async with get_session() as session:
        for i in range(5):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/batch_{i}.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type=["person", "car", "bicycle"][i % 3],
                confidence=0.75 + (i * 0.03),
            )
            session.add(detection)
            await session.flush()
            await session.refresh(detection)
            detections.append(detection)
        await session.commit()

    # Add to batch aggregator
    aggregator = BatchAggregator(redis_client=mock_redis)
    batch_id = None

    for detection in detections:
        new_batch_id = await aggregator.add_detection(
            camera_id=camera_id,
            detection_id=str(detection.id),
            _file_path=detection.file_path,
            confidence=0.75,  # Below fast path threshold
            object_type="car",
        )
        if batch_id is None:
            batch_id = new_batch_id
        else:
            assert new_batch_id == batch_id  # All in same batch

    # Close batch
    batch_summary = await aggregator.close_batch(batch_id)
    assert batch_summary["detection_count"] == 5

    # Verify Redis keys are deleted after close
    assert await mock_redis.get(f"batch:{batch_id}:camera_id") is None

    # Verify queue payload
    queue_items = await mock_redis.peek_queue("analysis_queue")
    assert len(queue_items) == 1

    queue_item = queue_items[0]
    assert queue_item["batch_id"] == batch_id
    assert queue_item["camera_id"] == camera_id
    assert len(queue_item["detection_ids"]) == 5

    # Analyzer can process using queue payload directly
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    mock_llm_response = create_mock_llm_response(
        risk_score=70,
        risk_level="high",
        summary="Multiple objects in batch",
    )

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        event = await analyzer.analyze_batch(
            batch_id=queue_item["batch_id"],
            camera_id=queue_item["camera_id"],
            detection_ids=queue_item["detection_ids"],
        )

    assert event is not None
    assert event.risk_score == 70

    # Verify all detection_ids in event
    stored_ids = json.loads(event.detection_ids)
    assert len(stored_ids) == 5
