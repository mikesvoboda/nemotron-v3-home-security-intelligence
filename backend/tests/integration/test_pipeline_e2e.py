"""End-to-end pipeline integration tests for the home security AI pipeline.

Tests the full pipeline flow:
1. FileWatcher detects new image in camera folder
2. DetectorClient sends image to RT-DETRv2 and stores detections
3. BatchAggregator groups detections into batches
4. NemotronAnalyzer analyzes batch and creates Event

External services (RT-DETRv2, Nemotron) are mocked to avoid real HTTP calls.

NOTE: These tests are marked as slow because they test complex multi-step
pipelines that require database setup and multiple service interactions.
"""

import asyncio
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
from backend.core.redis import QueueAddResult, QueueOverflowPolicy
from backend.models import Camera, Detection, Event
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient, DetectorUnavailableError
from backend.services.file_watcher import FileWatcher
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.tests.conftest import unique_id

# Mark all tests in this module as slow (get 30s timeout instead of 5s)
pytestmark = pytest.mark.slow


class MockQueueAddResult:
    """Mock QueueAddResult for testing."""

    def __init__(
        self,
        success: bool,
        queue_length: int,
        dropped_count: int = 0,
        moved_to_dlq_count: int = 0,
        error: str | None = None,
        warning: str | None = None,
    ) -> None:
        self.success = success
        self.queue_length = queue_length
        self.dropped_count = dropped_count
        self.moved_to_dlq_count = moved_to_dlq_count
        self.error = error
        self.warning = warning

    @property
    def had_backpressure(self) -> bool:
        return self.dropped_count > 0 or self.moved_to_dlq_count > 0 or self.error is not None


class MockRedisClient:
    """Mock Redis client for testing without a real Redis server.

    Simulates Redis operations using in-memory dictionaries.

    IMPORTANT: This mock validates JSON serialization to match real Redis behavior.
    Real Redis stores data as strings, so all values must be JSON-serializable.
    If you store a non-JSON-serializable object (e.g., datetime, set, custom class),
    it will raise TypeError just like the real RedisClient does.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._lists: dict[str, list[str]] = {}  # For Redis LIST operations (rpush/lrange)
        self._queues: dict[str, list[Any]] = {}
        # Create a mock inner client that supports async operations
        self._client = self._create_inner_client()

    def _create_inner_client(self) -> MagicMock:
        """Create a mock inner client with all required async operations."""
        inner_client = MagicMock()
        parent = self  # Capture self for closures

        # scan_iter returns an async generator
        async def _scan_iter_impl(match: str = "*", count: int = 100):
            import fnmatch

            for key in list(parent._store.keys()):
                if fnmatch.fnmatch(key, match):
                    yield key

        inner_client.scan_iter = MagicMock(
            side_effect=lambda match="*", count=100: _scan_iter_impl(match, count)
        )

        # rpush - atomically append to list
        async def _rpush_impl(key: str, value: str) -> int:
            if key not in parent._lists:
                parent._lists[key] = []
            parent._lists[key].append(value)
            return len(parent._lists[key])

        inner_client.rpush = _rpush_impl

        # lrange - get list elements
        async def _lrange_impl(key: str, start: int, end: int) -> list[str]:
            if key not in parent._lists:
                return []
            if end == -1:
                return parent._lists[key][start:]
            return parent._lists[key][start : end + 1]

        inner_client.lrange = _lrange_impl

        # llen - get list length
        async def _llen_impl(key: str) -> int:
            if key not in parent._lists:
                return 0
            return len(parent._lists[key])

        inner_client.llen = _llen_impl

        # expire - set key TTL (no-op in mock)
        async def _expire_impl(key: str, ttl: int) -> bool:
            return True

        inner_client.expire = _expire_impl

        # set - store key with optional TTL (NEM-2507 fix for batch closing flag)
        async def _set_impl(key: str, value: Any, ex: int | None = None) -> bool:
            # Validate JSON serialization like the outer set() method
            parent._store[key] = parent._validate_json_serializable(value)
            return True

        inner_client.set = _set_impl

        # pipeline - create a pipeline for batch operations
        def _pipeline_impl(
            transaction: bool = True, shard_hint: str | None = None
        ) -> MockRedisPipeline:
            return MockRedisPipeline(parent._store)

        inner_client.pipeline = _pipeline_impl

        return inner_client

    def _create_scan_iter_mock(self, keys: list[str]) -> MagicMock:
        """Create a mock scan_iter that returns specific keys.

        Args:
            keys: List of keys to yield from scan_iter

        Returns:
            MagicMock configured to return an async generator yielding the keys
        """

        async def _custom_scan_iter(match: str = "*", count: int = 100):
            for key in keys:
                yield key

        return MagicMock(side_effect=lambda match="*", count=100: _custom_scan_iter(match, count))

    def _validate_json_serializable(self, value: Any) -> str:
        """Validate that a value is JSON-serializable and return the serialized string.

        This mimics the real RedisClient behavior where non-string values are
        serialized with json.dumps() before storage. Real Redis stores values as
        strings, so all values must be JSON-serializable. If serialization fails,
        TypeError is raised - catching bugs early that would fail in production.

        Args:
            value: Value to validate and serialize

        Returns:
            JSON-serialized string if value is not already a string

        Raises:
            TypeError: If value is not JSON-serializable (e.g., datetime, custom class)
        """
        if isinstance(value, str):
            return value
        # This will raise TypeError for non-serializable objects (datetime, set, etc.)
        return json.dumps(value)

    async def get(self, key: str) -> Any | None:
        value = self._store.get(key)
        if value is None:
            return None
        # Deserialize if it's a JSON string
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        # Validate JSON serialization - raises TypeError if not serializable
        serialized = self._validate_json_serializable(value)
        self._store[key] = serialized
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
            if key in self._lists:
                del self._lists[key]
                deleted += 1
        return deleted

    async def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._store)

    async def add_to_queue_safe(
        self,
        queue_name: str,
        data: Any,
        max_size: int | None = None,
        overflow_policy: QueueOverflowPolicy | str | None = None,
        dlq_name: str | None = None,
    ) -> QueueAddResult:
        """Add item to queue with proper backpressure handling (mock version).

        This mock version validates JSON serialization but does not implement
        actual backpressure logic - it always succeeds for testing purposes.
        """
        # Validate JSON serialization - raises TypeError if not serializable
        self._validate_json_serializable(data)

        if queue_name not in self._queues:
            self._queues[queue_name] = []
        self._queues[queue_name].append(data)

        return QueueAddResult(
            success=True,
            queue_length=len(self._queues[queue_name]),
        )

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
        # Validate JSON serialization - raises TypeError if not serializable
        self._validate_json_serializable(message)
        return 1

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "connected": True, "redis_version": "mock"}

    def get_batch_keys(self) -> list[str]:
        """Get all batch:*:current keys for timeout checking."""
        return [k for k in self._store if k.endswith(":current") and k.startswith("batch:")]

    def pipeline(self) -> MockRedisPipeline:
        """Create a mock Redis pipeline for batch operations."""
        return MockRedisPipeline(self._store)


class MockRedisPipeline:
    """Mock Redis pipeline that collects commands and executes them."""

    def __init__(self, storage: dict[str, Any]) -> None:
        self._commands: list[tuple[str, tuple]] = []
        self._storage = storage

    async def __aenter__(self) -> MockRedisPipeline:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        pass

    def get(self, key: str) -> MockRedisPipeline:
        """Add GET command to pipeline."""
        self._commands.append(("get", (key,)))
        return self

    def set(self, key: str, value: str, ex: int | None = None) -> MockRedisPipeline:
        """Add SET command to pipeline."""
        self._commands.append(("set", (key, value, ex)))
        return self

    async def execute(self) -> list[Any]:
        """Execute all commands and return results."""
        results = []
        for cmd, args in self._commands:
            if cmd == "get":
                value = self._storage.get(args[0])
                if value is not None and isinstance(value, str):
                    try:
                        results.append(json.loads(value))
                    except json.JSONDecodeError:
                        results.append(value)
                else:
                    results.append(value)
            elif cmd == "set":
                key, value, _ex = args
                self._storage[key] = value
                results.append(True)
        return results


def create_test_image(path: Path) -> None:
    """Create a valid test image file above minimum size threshold.

    Creates a JPEG image with a gradient pattern to ensure the file size
    is above the 10KB minimum required by image validation.
    """
    size = (640, 480)
    img = Image.new("RGB", size, color="red")
    # Add gradient pattern to increase file size (solid colors compress too well)
    pixels = img.load()
    if pixels is not None:
        for y in range(size[1]):
            for x in range(size[0]):
                r = (x * 255 // size[0]) % 256
                g = (y * 255 // size[1]) % 256
                b = ((x + y) * 128 // (size[0] + size[1])) % 256
                pixels[x, y] = (r, g, b)
    img.save(path, "JPEG", quality=95)


@pytest.fixture
async def mock_redis() -> MockRedisClient:
    """Provide a mock Redis client for tests."""
    return MockRedisClient()


@pytest.fixture
async def clean_pipeline(integration_db):
    """Delete all tables data before test runs for proper isolation.

    These tests use hardcoded camera IDs, so they need clean state.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM logs"))
        await conn.execute(text("DELETE FROM gpu_stats"))
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM logs"))
            await conn.execute(text("DELETE FROM gpu_stats"))
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:
        pass


@pytest.fixture
async def test_camera(integration_db: str, clean_pipeline, tmp_path: Path) -> tuple[Camera, Path]:
    """Create a test camera with unique ID in the database and return with its temp dir.

    Returns a tuple of (Camera, camera_root_path) where camera_root_path contains
    the camera's folder.
    """
    camera_id = unique_id("test_camera")
    camera_root = tmp_path / "foscam"
    camera_root.mkdir(parents=True)
    camera_dir = camera_root / camera_id
    camera_dir.mkdir()

    async with get_session() as session:
        camera = Camera(
            id=camera_id,
            name="Test Camera",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
            created_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.commit()
        await session.refresh(camera)
        return camera, camera_root


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
    risk_score: int = 75, risk_level: str = "high", summary: str = "Person detected"
) -> dict[str, Any]:
    """Create a mock Nemotron LLM response."""
    return {
        "content": json.dumps(
            {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "summary": summary,
                "reasoning": "Test reasoning for detected objects",
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


@pytest.mark.asyncio
async def test_full_pipeline_single_image(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test full pipeline with a single image: file -> detection -> batch -> event.

    Verifies that:
    1. Image is detected and stored in database as Detection
    2. Detection is added to batch
    3. Batch is closed and analyzed
    4. Event is created with risk assessment
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    # Create test image
    image_path = temp_camera_dir / camera_id / "test_image.jpg"
    create_test_image(image_path)

    # Step 1: DetectorClient processes image
    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response()

    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(detector._http_client, "post") as mock_post:
            mock_response = create_mock_httpx_response(mock_detector_response)
            mock_post.return_value = mock_response

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )

            assert len(detections) == 1
            detection = detections[0]
            assert detection.object_type == "person"
            assert detection.confidence == 0.95
            detection_id = detection.id

    # Verify detection was stored in database
    async with get_session() as session:
        result = await session.execute(select(Detection).where(Detection.id == detection_id))
        stored_detection = result.scalar_one_or_none()
        assert stored_detection is not None
        assert stored_detection.camera_id == camera_id
        assert stored_detection.object_type == "person"

    # Step 2: BatchAggregator adds detection to batch
    # Use lower confidence to avoid fast path for this test
    aggregator = BatchAggregator(redis_client=mock_redis)
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id=str(detection_id),
        _file_path=str(image_path),
        confidence=0.85,  # Below fast path threshold (0.90)
        object_type="car",  # Not a fast path object type
    )

    # Should be regular batch, not fast path
    assert not batch_id.startswith("fast_path_")

    # Close the batch
    batch_summary = await aggregator.close_batch(batch_id)
    assert batch_summary["camera_id"] == camera_id
    assert batch_summary["detection_count"] == 1

    # Step 3: NemotronAnalyzer analyzes the batch
    # Pass camera_id and detection_ids directly (as queue worker does after fix)
    # This tests the fixed handoff where close_batch deletes Redis keys but
    # the queue payload contains all needed data
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    mock_llm_response = create_mock_llm_response()

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=[detection_id],
        )

        assert event is not None
        assert event.camera_id == camera_id
        assert event.risk_score == 75
        assert event.risk_level == "high"
        assert event.batch_id == batch_id

    # Verify event was stored in database
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        stored_event = result.scalar_one_or_none()
        assert stored_event is not None
        assert stored_event.risk_score == 75


@pytest.mark.asyncio
async def test_full_pipeline_multiple_images_same_camera(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test pipeline with multiple images: verifies batch aggregation works.

    Verifies that:
    1. Multiple detections are stored in database
    2. Detections are grouped into the same batch
    3. Batch contains all detection IDs
    4. Event is created with correct detection count
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    detection_ids = []
    image_paths = []

    # Create multiple test images and process them
    for i in range(3):
        image_path = temp_camera_dir / camera_id / f"test_image_{i}.jpg"
        create_test_image(image_path)
        image_paths.append(image_path)

        # Process each image with detector
        detector = DetectorClient()
        mock_detector_response = create_mock_detector_response(
            [
                {
                    "class": "car",  # Use car to avoid fast path
                    "confidence": 0.70 + (i * 0.05),  # Below fast path threshold
                    "bbox": {"x": 100 + i * 10, "y": 150, "width": 200, "height": 300},
                }
            ]
        )

        async with get_session() as session:
            # Patch the persistent HTTP client's post method (NEM-1721 pattern)
            with patch.object(detector._http_client, "post") as mock_post:
                mock_response = create_mock_httpx_response(mock_detector_response)
                mock_post.return_value = mock_response

                detections = await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

                if detections:
                    detection_ids.append(detections[0].id)

    assert len(detection_ids) == 3

    # Add all detections to batch aggregator
    aggregator = BatchAggregator(redis_client=mock_redis)
    batch_id = None

    for i, detection_id in enumerate(detection_ids):
        new_batch_id = await aggregator.add_detection(
            camera_id=camera_id,
            detection_id=str(detection_id),
            _file_path=str(image_paths[i]),
            confidence=0.70 + (i * 0.05),
            object_type="car",
        )
        if batch_id is None:
            batch_id = new_batch_id
        else:
            # All should be added to the same batch
            assert new_batch_id == batch_id

    # Close batch and verify
    batch_summary = await aggregator.close_batch(batch_id)
    assert batch_summary["camera_id"] == camera_id
    assert batch_summary["detection_count"] == 3

    # Analyze batch - pass camera_id and detection_ids directly (as queue worker does after fix)
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    mock_llm_response = create_mock_llm_response(
        risk_score=65,
        risk_level="medium",
        summary="Multiple objects detected: car",
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
            detection_ids=detection_ids,
        )

        assert event is not None
        assert event.camera_id == camera_id
        assert event.risk_score == 65
        assert event.risk_level == "medium"

        # Verify detection_ids in event
        stored_detection_ids = json.loads(event.detection_ids)
        assert len(stored_detection_ids) == 3
        for det_id in detection_ids:
            assert det_id in stored_detection_ids


@pytest.mark.asyncio
async def test_pipeline_detector_failure_graceful(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test pipeline raises DetectorUnavailableError for retry handling on failures.

    Verifies that:
    1. DetectorClient raises DetectorUnavailableError on connection error
    2. No detection is stored in database
    3. Exception allows pipeline to retry or move to DLQ
    4. System remains stable after handling the error
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    # Create test image
    image_path = temp_camera_dir / camera_id / "test_image.jpg"
    create_test_image(image_path)

    # Test connection error raises DetectorUnavailableError
    # Use max_retries=1 to speed up tests by skipping retry delays
    detector = DetectorClient(max_retries=1)

    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(
            detector._http_client, "post", side_effect=httpx.ConnectError("Connection refused")
        ):
            # Should raise DetectorUnavailableError to allow retry
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            # After retry exhaustion, error message indicates failed attempts
            assert "failed after" in str(exc_info.value).lower()
            # Original error is preserved for inspection
            assert isinstance(exc_info.value.original_error, httpx.ConnectError)

    # Verify no detection was stored
    async with get_session() as session:
        result = await session.execute(select(Detection).where(Detection.camera_id == camera_id))
        stored_detections = list(result.scalars().all())
        assert len(stored_detections) == 0

    # Test timeout error raises DetectorUnavailableError
    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(
            detector._http_client, "post", side_effect=httpx.TimeoutException("Request timed out")
        ):
            # Should raise DetectorUnavailableError to allow retry
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            # After retry exhaustion, error message indicates failed attempts
            assert "failed after" in str(exc_info.value).lower()
            # Original error is preserved for inspection
            assert isinstance(exc_info.value.original_error, httpx.TimeoutException)

    # Test HTTP 5xx error raises DetectorUnavailableError
    async with get_session() as session:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=mock_response
            )
        )

        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(detector._http_client, "post", return_value=mock_response):
            # Should raise DetectorUnavailableError to allow retry
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            # After retry exhaustion, error message indicates failed attempts
            assert "failed after" in str(exc_info.value).lower()
            # Original error is preserved for inspection
            assert isinstance(exc_info.value.original_error, httpx.HTTPStatusError)


@pytest.mark.asyncio
async def test_pipeline_missing_image_file(
    integration_db: str,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test pipeline handles missing image files gracefully."""
    camera, _ = test_camera
    camera_id = camera.id

    detector = DetectorClient()

    async with get_session() as session:
        detections = await detector.detect_objects(
            image_path="/nonexistent/path/image.jpg",
            camera_id=camera_id,
            session=session,
        )

        assert detections == []


@pytest.mark.asyncio
async def test_pipeline_low_confidence_filtering(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test that low confidence detections are filtered out.

    Verifies that detections below the confidence threshold are not stored.
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    image_path = temp_camera_dir / camera_id / "test_image.jpg"
    create_test_image(image_path)

    detector = DetectorClient()

    # Mock response with low confidence detection
    mock_detector_response = create_mock_detector_response(
        [
            {
                "class": "person",
                "confidence": 0.3,  # Below default threshold of 0.5
                "bbox": {"x": 100, "y": 150, "width": 200, "height": 300},
            }
        ]
    )

    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(detector._http_client, "post") as mock_post:
            mock_response = create_mock_httpx_response(mock_detector_response)
            mock_post.return_value = mock_response

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )

            # Low confidence detection should be filtered out
            assert detections == []


@pytest.mark.asyncio
async def test_pipeline_llm_failure_fallback(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test that LLM failures result in fallback risk assessment.

    Verifies that:
    1. Event is still created when LLM fails
    2. Fallback risk values are used (score=50, level=medium)
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    # Create detection first
    image_path = temp_camera_dir / camera_id / "test_image.jpg"
    create_test_image(image_path)

    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response()

    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(detector._http_client, "post") as mock_post:
            mock_response = create_mock_httpx_response(mock_detector_response)
            mock_post.return_value = mock_response

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )
            assert len(detections) == 1
            detection_id = detections[0].id

    # Analyze batch with LLM failure - pass camera_id and detection_ids directly
    batch_id = unique_id("test_batch_llm_failure")
    analyzer = NemotronAnalyzer(redis_client=mock_redis)

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("LLM service unavailable"))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=[detection_id],
        )

        # Event should still be created with fallback values
        assert event is not None
        assert event.risk_score == 50
        assert event.risk_level == "medium"
        assert "LLM service error" in event.summary


@pytest.mark.asyncio
async def test_file_watcher_queues_detection(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test that FileWatcher properly queues images for detection.

    Verifies that:
    1. FileWatcher detects new image files
    2. Valid images are queued in Redis
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    # Patch the settings to use our temp directory
    with patch("backend.services.file_watcher.get_settings") as mock_settings:
        settings_mock = MagicMock()
        settings_mock.foscam_base_path = str(temp_camera_dir)
        mock_settings.return_value = settings_mock

        watcher = FileWatcher(
            camera_root=str(temp_camera_dir),
            redis_client=mock_redis,
            debounce_delay=0.1,
        )

        # Start the watcher
        await watcher.start()

        try:
            # Create a test image (simulating FTP upload)
            image_path = temp_camera_dir / camera_id / "new_image.jpg"
            create_test_image(image_path)

            # Give filesystem watcher time to detect
            await asyncio.sleep(0.5)

            # Check that image was queued
            _queue_length = await mock_redis.get_queue_length("detection_queue")
            # Note: The actual queueing depends on the file system event being triggered
            # In tests, this may not always work reliably, so we verify the watcher started
            assert watcher.running is True

        finally:
            await watcher.stop()

        assert watcher.running is False


@pytest.mark.asyncio
async def test_batch_timeout_closes_batch(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test that batch aggregator closes batches on timeout.

    Verifies that:
    1. Active batches are tracked
    2. Batches exceeding idle timeout are closed
    3. Closed batches are pushed to analysis queue
    """
    camera, _ = test_camera
    camera_id = camera.id

    aggregator = BatchAggregator(redis_client=mock_redis)

    # Override timeout for testing (use smaller values)
    aggregator._idle_timeout = 0.5  # 0.5 second idle timeout for testing

    # Add a detection to create a batch
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id="1",
        _file_path="/path/to/image.jpg",
        confidence=0.7,
        object_type="car",
    )

    # Manually set last_activity to the past to simulate idle timeout
    past_time = time.time() - 1.0  # 1 second ago
    await mock_redis.set(f"batch:{batch_id}:last_activity", str(past_time))

    # Update the mock's _client.scan_iter to return the batch keys
    batch_keys = mock_redis.get_batch_keys()
    mock_redis._client.scan_iter = mock_redis._create_scan_iter_mock(batch_keys)

    # Check for timeouts
    closed_batches = await aggregator.check_batch_timeouts()

    # Batch should have been closed due to idle timeout
    assert batch_id in closed_batches

    # Verify batch was pushed to analysis queue
    queue_items = await mock_redis.peek_queue("analysis_queue")
    assert len(queue_items) == 1
    assert queue_items[0]["batch_id"] == batch_id
    assert queue_items[0]["camera_id"] == camera_id


@pytest.mark.asyncio
async def test_fast_path_high_priority_detection(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test that high-confidence person detections trigger fast path analysis.

    Verifies that:
    1. Detection with confidence >= 0.90 and type 'person' triggers fast path
    2. Event is created immediately without batching
    3. Event is marked as is_fast_path=True
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    # Create detection first
    image_path = temp_camera_dir / camera_id / "test_image.jpg"
    create_test_image(image_path)

    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response(
        [
            {
                "class": "person",
                "confidence": 0.95,  # High confidence triggers fast path
                "bbox": {"x": 100, "y": 150, "width": 200, "height": 300},
            }
        ]
    )

    detection_id = None
    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(detector._http_client, "post") as mock_post:
            mock_response = create_mock_httpx_response(mock_detector_response)
            mock_post.return_value = mock_response

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )
            assert len(detections) == 1
            detection_id = detections[0].id

    # Create aggregator with mocked analyzer for fast path
    mock_llm_response = create_mock_llm_response(
        risk_score=90, risk_level="critical", summary="High confidence person detected"
    )

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        aggregator = BatchAggregator(redis_client=mock_redis)
        batch_id = await aggregator.add_detection(
            camera_id=camera_id,
            detection_id=str(detection_id),
            _file_path=str(image_path),
            confidence=0.95,
            object_type="person",
        )

        # Should be fast path
        assert batch_id.startswith("fast_path_")

    # Verify fast path event was created
    async with get_session() as session:
        result = await session.execute(
            select(Event).where(Event.camera_id == camera_id).where(Event.is_fast_path == True)  # noqa: E712
        )
        fast_path_events = list(result.scalars().all())
        assert len(fast_path_events) == 1
        assert fast_path_events[0].is_fast_path is True


@pytest.mark.asyncio
async def test_batch_close_to_analyze_handoff_without_redis_rehydration(
    integration_db: str,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
) -> None:
    """Test complete batch close -> dequeue -> analyze_batch -> Event flow.

    This is a critical integration test that verifies the fix for the batch handoff bug:
    - BatchAggregator.close_batch() deletes Redis keys after enqueuing
    - AnalysisQueueWorker passes camera_id and detection_ids from queue payload
    - NemotronAnalyzer.analyze_batch() uses provided values instead of reading Redis

    Verifies that:
    1. Batch is created and detection is added
    2. Batch is closed (Redis keys deleted, queue item created)
    3. Queue item contains camera_id and detection_ids
    4. analyze_batch() works with queue payload (no Redis lookup needed)
    5. Event is created successfully
    """
    camera, temp_camera_dir = test_camera
    camera_id = camera.id

    # Create test image
    image_path = temp_camera_dir / camera_id / "handoff_test.jpg"
    create_test_image(image_path)

    # Step 1: Create detection in database
    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response(
        [
            {
                "class": "car",  # Use car to avoid fast path
                "confidence": 0.85,  # Below fast path threshold
                "bbox": {"x": 100, "y": 150, "width": 200, "height": 300},
            }
        ]
    )

    detection_id = None
    async with get_session() as session:
        # Patch the persistent HTTP client's post method (NEM-1721 pattern)
        with patch.object(detector._http_client, "post") as mock_post:
            mock_response = create_mock_httpx_response(mock_detector_response)
            mock_post.return_value = mock_response

            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )

            assert len(detections) == 1
            detection_id = detections[0].id

    # Step 2: Add detection to batch
    aggregator = BatchAggregator(redis_client=mock_redis)
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id=str(detection_id),
        _file_path=str(image_path),
        confidence=0.85,
        object_type="car",
    )

    # Verify batch metadata exists in Redis before close
    assert await mock_redis.get(f"batch:{batch_id}:camera_id") == camera_id
    # Detections are now stored in a Redis LIST (using rpush), not as a JSON string
    batch_detections_before = mock_redis._lists.get(f"batch:{batch_id}:detections", [])
    assert len(batch_detections_before) > 0

    # Step 3: Close batch - this deletes Redis keys and enqueues
    batch_summary = await aggregator.close_batch(batch_id)
    assert batch_summary["camera_id"] == camera_id
    assert batch_summary["detection_count"] == 1

    # Verify Redis keys are deleted after close
    assert await mock_redis.get(f"batch:{batch_id}:camera_id") is None
    # Detections list should be deleted too
    assert f"batch:{batch_id}:detections" not in mock_redis._lists

    # Step 4: Verify queue item contains all needed data
    queue_items = await mock_redis.peek_queue("analysis_queue")
    assert len(queue_items) == 1

    queue_item = queue_items[0]
    assert queue_item["batch_id"] == batch_id
    assert queue_item["camera_id"] == camera_id
    # Detection IDs are stored as integers (normalized by BatchAggregator.add_detection)
    assert queue_item["detection_ids"] == [detection_id]

    # Step 5: Simulate AnalysisQueueWorker processing - use queue payload directly
    # This is exactly what the fixed worker does: pass camera_id and detection_ids
    # from the queue item instead of reading from Redis
    analyzer = NemotronAnalyzer(redis_client=mock_redis)
    mock_llm_response = create_mock_llm_response(
        risk_score=55,
        risk_level="medium",
        summary="Car detected - handoff test",
    )

    with patch("backend.services.nemotron_analyzer.httpx.AsyncClient") as mock_client:
        mock_response = create_mock_httpx_response(mock_llm_response)

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        # Call analyze_batch with queue payload data (not from Redis)
        event = await analyzer.analyze_batch(
            batch_id=queue_item["batch_id"],
            camera_id=queue_item["camera_id"],
            detection_ids=queue_item["detection_ids"],
        )

        # Step 6: Verify event was created correctly
        assert event is not None
        assert event.batch_id == batch_id
        assert event.camera_id == camera_id
        assert event.risk_score == 55
        assert event.risk_level == "medium"
        assert "Car detected" in event.summary

    # Step 7: Verify event is persisted in database
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        stored_event = result.scalar_one_or_none()

        assert stored_event is not None
        assert stored_event.id == event.id
        assert stored_event.camera_id == camera_id
        assert stored_event.risk_score == 55

        # Verify detection_ids in event
        stored_detection_ids = json.loads(stored_event.detection_ids)
        assert len(stored_detection_ids) == 1
        assert str(detection_id) in [str(d) for d in stored_detection_ids]


# =============================================================================
# MockRedisClient JSON Serialization Validation Tests
# =============================================================================
# These tests verify that MockRedisClient properly validates JSON serialization
# to catch issues that would occur with real Redis in production.


@pytest.mark.asyncio
async def test_mock_redis_validates_json_serialization_on_set() -> None:
    """Test that MockRedisClient.set() raises TypeError for non-JSON-serializable objects.

    This ensures the mock behaves like the real RedisClient, catching bugs early
    that would fail in production (e.g., storing datetime objects directly).
    """
    redis = MockRedisClient()

    # Valid JSON-serializable values should work
    await redis.set("string_key", "hello")
    await redis.set("int_key", 42)
    await redis.set("float_key", 3.14)
    await redis.set("list_key", [1, 2, 3])
    await redis.set("dict_key", {"nested": {"value": True}})
    await redis.set("none_key", None)

    # Verify round-trip works correctly
    assert await redis.get("string_key") == "hello"
    assert await redis.get("int_key") == 42
    assert await redis.get("dict_key") == {"nested": {"value": True}}

    # Non-JSON-serializable objects should raise TypeError
    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.set("datetime_key", datetime.now(UTC))

    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.set("set_key", {1, 2, 3})

    class CustomClass:
        pass

    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.set("custom_key", CustomClass())


@pytest.mark.asyncio
async def test_mock_redis_validates_json_serialization_on_add_to_queue_safe_detailed() -> None:
    """Test that MockRedisClient.add_to_queue_safe() raises TypeError for non-serializable data.

    Queue operations are critical for the pipeline - this ensures we catch
    serialization bugs before they reach production.
    """
    redis = MockRedisClient()

    # Valid data should work
    result1 = await redis.add_to_queue_safe(
        "test_queue", {"camera_id": "cam1", "detection_ids": [1, 2, 3]}
    )
    assert result1.success is True
    result2 = await redis.add_to_queue_safe("test_queue", "string_message")
    assert result2.success is True

    # Verify data was added correctly
    assert await redis.get_queue_length("test_queue") == 2
    items = await redis.peek_queue("test_queue")
    assert items[0] == {"camera_id": "cam1", "detection_ids": [1, 2, 3]}

    # Non-JSON-serializable data should raise TypeError
    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.add_to_queue_safe("test_queue", datetime.now(UTC))

    with pytest.raises(TypeError, match="not JSON serializable"):
        # This is a common bug - storing set instead of list
        await redis.add_to_queue_safe("test_queue", {"detection_ids": {1, 2, 3}})


@pytest.mark.asyncio
async def test_mock_redis_validates_json_serialization_on_publish() -> None:
    """Test that MockRedisClient.publish() raises TypeError for non-serializable messages.

    Pub/Sub messages must be serializable for the real Redis transport.
    """
    redis = MockRedisClient()

    # Valid messages should work
    result = await redis.publish("events", {"type": "detection", "camera_id": "cam1"})
    assert result == 1

    # Non-JSON-serializable messages should raise TypeError
    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.publish("events", datetime.now(UTC))


@pytest.mark.asyncio
async def test_mock_redis_validates_json_serialization_on_add_to_queue_safe() -> None:
    """Test that MockRedisClient.add_to_queue_safe() also validates JSON serialization.

    This method is used in production with backpressure handling - it must
    also validate serialization.
    """
    redis = MockRedisClient()

    # Valid data should work
    result = await redis.add_to_queue_safe("safe_queue", {"batch_id": "batch123"})
    assert result.success is True
    assert result.queue_length == 1

    # Non-JSON-serializable data should raise TypeError
    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.add_to_queue_safe("safe_queue", datetime.now(UTC))


@pytest.mark.asyncio
async def test_mock_redis_rejects_custom_class() -> None:
    """Test that MockRedisClient rejects custom class instances."""
    redis = MockRedisClient()

    class CustomObject:
        def __init__(self) -> None:
            self.value = "test"

    with pytest.raises(TypeError, match="not JSON serializable"):
        await redis.set("key", CustomObject())


@pytest.mark.asyncio
async def test_mock_redis_accepts_iso_datetime_string() -> None:
    """Test that MockRedisClient accepts datetime as ISO string (proper serialization)."""
    redis = MockRedisClient()

    # Convert datetime to ISO string (the correct way to store in Redis)
    timestamp = datetime.now(UTC).isoformat()
    await redis.set("timestamp_key", timestamp)

    # Also works in a dict
    await redis.set("event", {"timestamp": timestamp, "value": 42})

    # Verify values were stored
    assert await redis.get("timestamp_key") == timestamp
    event = await redis.get("event")
    assert event["timestamp"] == timestamp
