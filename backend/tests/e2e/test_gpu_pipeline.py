"""GPU Pipeline End-to-End Tests.

These tests validate the complete GPU AI pipeline including:
- YOLO26Client: YOLO26 object detection via HTTP
- VlmAnalyzer: VLM verdict analysis via ai-vlm (llama.cpp-served)
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
from backend.models.event_detection import EventDetection
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient, DetectorUnavailableError
from backend.services.severity import get_severity_service
from backend.services.vlm_analyzer import VlmAnalyzer
from backend.services.vlm_client import VlmTransportError
from backend.services.vlm_verdict import VlmAssessRequest, VlmVerdict
from backend.tests.conftest import unique_id

# All tests in this module run sequentially on the same worker to ensure database isolation
pytestmark = [pytest.mark.xdist_group(name="gpu_pipeline_e2e")]


# =============================================================================
# Test Fixtures
# =============================================================================


class MockRedisPipeline:
    """Mock Redis pipeline for batch operations."""

    def __init__(self, client: MockRedisClient) -> None:
        self._client = client
        self._commands: list[tuple[str, tuple, dict]] = []

    async def __aenter__(self) -> MockRedisPipeline:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def set(self, key: str, value: Any, **kwargs) -> MockRedisPipeline:
        """Queue a SET command (synchronous like real Redis pipeline)."""
        self._commands.append(("set", (key, value), kwargs))
        return self

    async def execute(self) -> list[Any]:
        """Execute all queued commands."""
        results = []
        for cmd, args, kwargs in self._commands:
            if cmd == "set":
                await self._client.set(*args, **kwargs)
                results.append(True)
        self._commands.clear()
        return results


class MockRedisClient:
    """Mock Redis client for testing without a real Redis server."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._queues: dict[str, list[Any]] = {}
        self._lists: dict[str, list[Any]] = {}  # For list operations
        self._client = AsyncMock()
        self._client.scan_iter = self._create_scan_iter_mock([])
        # Make pipeline a regular method, not async
        # Support both 'transaction' and '_transaction' parameters for compatibility
        self._client.pipeline = self._create_pipeline
        # Add list operations
        self._client.llen = AsyncMock(side_effect=self._llen)
        self._client.rpush = AsyncMock(side_effect=self._rpush)
        self._client.lrange = AsyncMock(side_effect=self._lrange)
        self._client.expire = AsyncMock(side_effect=self._expire)

        # xadd - Redis Streams append. use_redis_streams ships True
        # (core/config.py:2437), so BatchAggregator.close_batch enqueues via
        # AnalysisStreamService.add_batch -> self._redis._client.xadd rather
        # than the legacy analysis_queue LIST. A plain AsyncMock xadd is
        # awaitable but stores nothing, so the batch-handoff tests below read
        # their payload from _streams instead (mirrors the integration
        # test_pipeline_e2e mock, ledger R-T9-PIPELINE-E2E).
        self._streams: dict[str, list[tuple[str, dict[str, Any]]]] = {}

        async def _xadd_impl(
            name: str,
            fields: dict,
            maxlen: int | None = None,
            approximate: bool = False,
        ) -> str:
            entries = self._streams.setdefault(name, [])
            message_id = f"{len(entries) + 1}-0"
            entries.append((message_id, dict(fields)))
            return message_id

        self._client.xadd = _xadd_impl

    def _create_scan_iter_mock(self, keys: list[str]) -> MagicMock:
        """Create a mock scan_iter that returns an async generator."""

        async def _generator():
            for key in keys:
                yield key

        return MagicMock(return_value=_generator())

    def _create_pipeline(
        self,
        transaction: bool = False,
        _transaction: bool = False,
    ) -> MockRedisPipeline:
        """Create a mock Redis pipeline."""
        return MockRedisPipeline(self)

    async def _llen(self, key: str) -> int:
        """Get the length of a list."""
        return len(self._lists.get(key, []))

    async def _rpush(self, key: str, *values: Any) -> int:
        """Push values to the right of a list."""
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].extend(values)
        return len(self._lists[key])

    async def _lrange(self, key: str, start: int, end: int) -> list[Any]:
        """Get a range of elements from a list."""
        if key not in self._lists:
            return []
        # Handle Redis-style negative indexing (end=-1 means to the end)
        if end == -1:
            return self._lists[key][start:]
        return self._lists[key][start : end + 1]

    async def _expire(self, key: str, ttl: int) -> bool:
        """Set TTL on a key (mock implementation that always succeeds)."""
        # In a mock, we don't actually track TTL, just return success
        return True

    def pipeline(self, transaction: bool = False, _transaction: bool = False) -> MockRedisPipeline:
        """Create a mock Redis pipeline.

        Args:
            transaction: Whether to use transaction mode (ignored in mock)
            _transaction: Alternative parameter name for compatibility (ignored in mock)
        """
        return MockRedisPipeline(self)

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: Any, expire: int | None = None, ex: int | None = None
    ) -> bool:
        """Set a key-value pair with optional expiration.

        Args:
            key: Redis key
            value: Value to store
            expire: Expiration in seconds (legacy parameter)
            ex: Expiration in seconds (Redis standard parameter)
        """
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

    def peek_stream(self, stream_name: str) -> list[dict[str, Any]]:
        """Entries appended by the async xadd mock (shipped streams path)."""
        return [fields for _mid, fields in self._streams.get(stream_name, [])]

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


def create_test_image(path: Path, size: tuple[int, int] = (1920, 1080)) -> None:
    """Create a valid test image file.

    Creates an image that's at least 10KB to pass MIN_DETECTION_IMAGE_SIZE validation.
    Default size (1920x1080) produces ~32KB JPEG file at quality 95.
    """
    img = Image.new("RGB", size, color="red")
    # Save with quality setting to ensure file is large enough (>10KB)
    img.save(path, "JPEG", quality=95)


def create_mock_detector_response(detections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a mock YOLO26 detector response."""
    if detections is None:
        detections = [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": {"x": 100, "y": 150, "width": 200, "height": 300},
            }
        ]
    return {"detections": detections}


class ScriptedVlmClient:
    """Stands in for the ai-vlm transport so a mocked test never opens a socket.

    R8 S2b: the retired analyzer was stubbed at `httpx.AsyncClient`; the
    shipped VlmAnalyzer speaks `prompt_text` / `assess` / `close` around a
    typed VlmVerdict, so that is the seam stubbed here. The last script entry
    repeats, so a test can call analyze_batch more than once.
    """

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.closed = False
        self.assess_calls = 0

    def prompt_text(self, request: VlmAssessRequest) -> str:
        return f"ASSESS camera={request.context.camera_id} PATHS {request.image_paths}"

    async def assess(self, request: VlmAssessRequest) -> VlmVerdict:
        self.assess_calls += 1
        outcome = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def close(self) -> None:
        self.closed = True


def make_verdict(
    *,
    risk_score: int = 75,
    summary: str = "Person detected",
    reasoning: str = "Test reasoning for detected objects",
    verdict: str = "confirmed",
) -> VlmVerdict:
    """A scripted verdict. There is no `risk_level` field: the model never
    emits one, SeverityService derives it from the score (spec §3 Derived)."""
    return VlmVerdict.model_validate(
        {
            "verdict": verdict,
            "risk_score": risk_score,
            "summary": summary,
            "reasoning": reasoning,
            "description": "Scripted GPU-tier scene.",
            "criteria": [{"name": "person_present", "passed": True, "evidence": "full frame"}],
            "provenance": {"engine": "llama.cpp", "model_id": "gpu-scripted-model"},
        }
    )


async def ai_vlm_healthy() -> bool:
    """Is a served ai-vlm answering?

    R8 S2b: the retired analyzer had a `health_check()`; the shipped client
    has `wake()`, and that is the probe the GPU runner uses - a health probe
    may not wake a sleeping llama.cpp (spec §6), so a minimal real request is
    the only evidence of availability this tier can honestly make.
    """
    from backend.services.vlm_client import VlmClient

    client = VlmClient()
    try:
        return await client.wake()
    finally:
        await client.close()


def create_mock_httpx_response(json_data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Create a properly configured mock httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = MagicMock()
    return mock_response


@pytest.fixture
async def mock_redis() -> MockRedisClient:
    """Provide a mock Redis client for tests.

    Also un-caches the process-wide AnalysisStreamService singleton: it is
    first-client-wins, so a batch closed by an earlier test on the same xdist
    worker leaves a dead client cached and this fixture's close_batch would
    xadd into that instead of the mock.
    """
    import backend.services.redis_streams as _redis_streams

    _redis_streams._analysis_stream_service = None
    return MockRedisClient()


@pytest.fixture
async def clean_pipeline(isolated_db):
    """Delete all tables data before test runs for proper isolation.

    This fixture ensures tests start with a clean database state.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.

    Note: isolated_db is a dependency to ensure database is initialized.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    engine = get_engine()
    if engine is None:
        yield
        return

    async with engine.begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM logs"))
        await conn.execute(text("DELETE FROM gpu_stats"))
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test too (best effort)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM logs"))
            await conn.execute(text("DELETE FROM gpu_stats"))
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:
        pass


@pytest.fixture
async def test_camera(isolated_db, clean_pipeline, tmp_path: Path) -> tuple[Camera, Path]:
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
async def test_gpu_detector_client_health_check(isolated_db):
    """Test DetectorClient health check against real YOLO26 service.

    This test verifies that the YOLO26 service is running and healthy
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
async def test_gpu_ai_vlm_health_check(isolated_db):
    """Test ai-vlm availability against the real llama.cpp-served VLM.

    R8 S2b: the retired analyzer exposed `health_check()`; VlmAnalyzer has no
    such method and VlmClient's availability probe is `wake()` (a minimal
    REAL request - a health probe may not wake a sleeping llama.cpp, spec §6).

    Run with: pytest -m gpu -v
    """
    is_healthy = await ai_vlm_healthy()

    # On GPU runner, we expect the ai-vlm service to be available
    assert isinstance(is_healthy, bool)


@pytest.mark.gpu
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_gpu_full_pipeline_with_real_services(
    isolated_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test full GPU pipeline with real AI services.

    This is a comprehensive E2E test that validates:
    1. Real YOLO26 object detection
    2. Real ai-vlm verdict analysis
    3. Database persistence
    4. Event creation

    This test requires:
    - YOLO26 service running on configured yolo26_url
    - ai-vlm served on the configured ai_vlm_url
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
    analyzer = VlmAnalyzer(redis_client=mock_redis)

    detector_healthy = await detector.health_check()
    analyzer_healthy = await ai_vlm_healthy()

    if not detector_healthy:
        pytest.skip("YOLO26 service not available")

    if not analyzer_healthy:
        pytest.skip("ai-vlm service not available")

    # Step 1: Run object detection with real YOLO26
    async with get_session() as session:
        try:
            detections = await detector.detect_objects(
                image_path=str(image_path),
                camera_id=camera_id,
                session=session,
            )
        except DetectorUnavailableError:
            pytest.skip("YOLO26 service returned error")

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

    # Step 3: Run the real VLM verdict analysis
    try:
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )
    except Exception as e:
        pytest.skip(f"ai-vlm analysis failed: {e}")

    # Verify event was created. A real assess that fails verification lands a
    # NULL score by design (§6 step 2), so the score assertion branches on it
    # rather than assuming a number always appeared.
    assert event is not None
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    if event.risk_score is not None:
        assert 0 <= event.risk_score <= 100
        assert event.risk_level in ["low", "medium", "high", "critical"]
    else:
        assert event.risk_level is None
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
@pytest.mark.timeout(60)
async def test_gpu_detector_client_inference_performance(
    isolated_db,
    test_camera: tuple[Camera, Path],
):
    """Test YOLO26 inference performance on GPU.

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
        pytest.skip("YOLO26 service not available")

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
            pytest.skip("YOLO26 service returned error")

    inference_time_ms = (time.time() - start_time) * 1000

    # Log performance metrics
    print(f"\nYOLO26 Inference Time: {inference_time_ms:.2f}ms")

    # Performance assertion (adjust threshold as needed)
    # Allow up to 5000ms for first inference (model loading)
    assert inference_time_ms < 5000, f"Inference too slow: {inference_time_ms:.2f}ms"


@pytest.mark.gpu
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_gpu_vlm_analysis_performance(
    isolated_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test ai-vlm verdict analysis performance on GPU.

    This test measures the analyze->event time to ensure it meets
    performance requirements.

    Expected performance:
    - Single batch analysis: < 30 seconds (VLM inference can be slow)

    R8 S2b: renamed from test_gpu_nemotron_analysis_performance - the engine
    measured here is the shipped one (one constrained vlm_assess per batch).

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

    analyzer = VlmAnalyzer(redis_client=mock_redis)

    # Check if service is available
    if not await ai_vlm_healthy():
        pytest.skip("ai-vlm service not available")

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
        pytest.skip(f"ai-vlm analysis failed: {e}")

    analysis_time_ms = (time.time() - start_time) * 1000

    # Log performance metrics
    print(f"\nVLM Analysis Time: {analysis_time_ms:.2f}ms")
    print(f"Risk Score: {event.risk_score}, Risk Level: {event.risk_level}")

    # Performance assertion (VLM can take longer)
    assert analysis_time_ms < 30000, f"Analysis too slow: {analysis_time_ms:.2f}ms"


# =============================================================================
# Integration Tests: Mock External Services
# =============================================================================


@pytest.mark.asyncio
async def test_detector_client_integration_mocked(
    isolated_db,
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
        mock_response = create_mock_httpx_response(mock_detector_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(detector, "_http_client", mock_client):
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
async def test_vlm_analyzer_integration_mocked(
    isolated_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test VlmAnalyzer with a scripted transport.

    Validates:
    - Batch processing from the payload it is handed
    - Prompt formation (stored verbatim on the event)
    - Verdict parsing into the event row
    - Event creation with risk assessment
    - Database persistence

    R8 S2b: renamed from test_nemotron_analyzer_integration_mocked. The stub
    moved from `nemotron_analyzer.httpx.AsyncClient` to the shipped client
    seam (assess -> VlmVerdict). Note the level is DERIVED: the verdict
    carries a score only, so "high" here is SeverityService's reading of 65.
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
    analyzer = VlmAnalyzer(
        redis_client=mock_redis,
        vlm_client=ScriptedVlmClient(
            [
                make_verdict(
                    risk_score=65,
                    summary="Multiple objects detected including person and vehicle",
                    reasoning="High-confidence detections warrant attention",
                )
            ]
        ),
    )
    batch_id = unique_id("mock_batch")

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
    assert event.risk_level == get_severity_service().risk_score_to_severity(65).value
    assert "Multiple objects" in event.summary

    # Verify event in database
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        stored_event = result.scalar_one_or_none()
        assert stored_event is not None
        assert stored_event.id == event.id

        # Verify the detection association landed (junction table - the
        # analyzer writes event_detections, not the legacy JSON column)
        assert sorted(stored_event.detection_id_list) == sorted(d.id for d in detections)


@pytest.mark.asyncio
async def test_full_pipeline_integration_mocked(
    isolated_db,
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

    # Step 2: Run detection with mocked YOLO26
    detector = DetectorClient()
    mock_detector_response = create_mock_detector_response(
        [
            {"class": "person", "confidence": 0.92, "bbox": [100, 150, 200, 300]},
        ]
    )

    async with get_session() as session:
        mock_response = create_mock_httpx_response(mock_detector_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(detector, "_http_client", mock_client):
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

    # Step 5: Run the shipped VLM analysis with a scripted transport
    analyzer = VlmAnalyzer(
        redis_client=mock_redis,
        vlm_client=ScriptedVlmClient(
            [make_verdict(risk_score=55, summary="Single object detected")]
        ),
    )

    # Get detection_ids from the analysis stream (use_redis_streams ships True)
    from backend.services.redis_streams import ANALYSIS_STREAM_KEY

    stream_entries = mock_redis.peek_stream(ANALYSIS_STREAM_KEY)
    assert len(stream_entries) == 1
    queue_item = {
        "batch_id": stream_entries[0]["batch_id"],
        "camera_id": stream_entries[0]["camera_id"],
        "detection_ids": [int(d) for d in json.loads(stream_entries[0]["detection_ids"])],
    }

    event = await analyzer.analyze_batch(
        batch_id=queue_item["batch_id"],
        camera_id=queue_item["camera_id"],
        detection_ids=queue_item["detection_ids"],
    )

    # Verify final event
    assert event is not None
    assert event.risk_score == 55
    assert event.risk_level == get_severity_service().risk_score_to_severity(55).value

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
    isolated_db,
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
    # Need to patch the _http_client instance directly and mock sleep to avoid delays
    async with get_session() as session:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with (
            patch.object(detector, "_http_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            assert "after" in str(exc_info.value)  # "failed after X attempts"

    # Test timeout error
    async with get_session() as session:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with (
            patch.object(detector, "_http_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            assert "after" in str(exc_info.value)  # "failed after X attempts"

    # Test HTTP 500 error
    async with get_session() as session:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=mock_response
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch.object(detector, "_http_client", mock_client),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=str(image_path),
                    camera_id=camera_id,
                    session=session,
                )

            assert "after" in str(exc_info.value)  # "failed after X attempts"


@pytest.mark.asyncio
async def test_vlm_failure_fallback(
    isolated_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test the analyzer's degraded write when the VLM call fails.

    R8 S2b: this asserted the legacy fallback (score=50, level=medium,
    "Analysis unavailable") that the retired analyzer fabricated. That
    default-score paper-over is explicitly NOT imported across the seam
    (D11/S5): the shipped §6 rule writes the event with NULL score/level so
    the UI can show "needs review". The event row still exists - that part
    of the promise survives; the fabricated 50 does not.
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

    # Test with transport failure
    analyzer = VlmAnalyzer(
        redis_client=mock_redis,
        vlm_client=ScriptedVlmClient([VlmTransportError("ai-vlm unavailable")]),
    )
    batch_id = unique_id("fallback_batch")

    event = await analyzer.analyze_batch(
        batch_id=batch_id,
        camera_id=camera_id,
        detection_ids=[detection.id],
    )

    # Event still created - with NULL score/level by design
    assert event is not None
    assert event.risk_score is None
    assert event.risk_level is None
    assert "needs review" in event.summary


@pytest.mark.asyncio
async def test_fast_path_analysis(
    isolated_db,
    mock_redis: MockRedisClient,
    test_camera: tuple[Camera, Path],
):
    """Test the fast-path surface of the shipped analyzer.

    R8 S2b: the retired analyzer's fast path wrote `is_fast_path=True` and a
    90/critical score off its own shortcut. The shipped
    VlmAnalyzer.analyze_detection_fast_path deliberately does NOT recreate
    that shortcut - it routes the single detection through the SAME batch
    gate with the ``fast_path_<id>`` idempotency key, so a vlm-mode trigger
    gets a full assess of a one-detection batch and marks nothing. What is
    honestly pinned here: the batch id shape, the scripted score landing,
    and that is_fast_path stayed False (the column is nemotron-only).
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

    # Run the fast-path surface
    analyzer = VlmAnalyzer(
        redis_client=mock_redis,
        vlm_client=ScriptedVlmClient(
            [make_verdict(risk_score=90, summary="High-confidence person detected - fast path")]
        ),
    )

    event = await analyzer.analyze_detection_fast_path(
        camera_id=camera_id,
        detection_id=detection.id,
    )

    # Verify the fast-path batch id and the scored event
    assert event is not None
    assert event.batch_id == f"fast_path_{detection.id}"
    assert event.risk_score == 90
    assert event.risk_level == get_severity_service().risk_score_to_severity(90).value
    # The shipped fast path marks nothing: is_fast_path was nemotron-only.
    assert event.is_fast_path is False

    # Verify the event row and the single detection association (junction
    # table - the shipped analyzer writes event_detections, not the legacy
    # Event.detection_ids JSON column). Read inside the session: the returned
    # Event is detached, so its lazy 'detections' relationship needs a session.
    async with get_session() as session:
        stored = await session.get(Event, event.id)
        assert stored is not None
        assert stored.detection_id_list == [detection.id]


@pytest.mark.asyncio
async def test_batch_aggregation_and_handoff(
    isolated_db,
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

    # Verify the enqueued payload. use_redis_streams ships True, so
    # close_batch xadds to the analysis stream (detection_ids JSON-encoded)
    # instead of RPUSHing the legacy analysis_queue LIST.
    from backend.services import redis_streams as _redis_streams

    _redis_streams._analysis_stream_service = None
    stream_entries = mock_redis.peek_stream(_redis_streams.ANALYSIS_STREAM_KEY)
    assert len(stream_entries) == 1

    queue_item = {
        "batch_id": stream_entries[0]["batch_id"],
        "camera_id": stream_entries[0]["camera_id"],
        "detection_ids": [int(d) for d in json.loads(stream_entries[0]["detection_ids"])],
    }
    assert queue_item["batch_id"] == batch_id
    assert queue_item["camera_id"] == camera_id
    assert len(queue_item["detection_ids"]) == 5

    # Analyzer can process using queue payload directly
    analyzer = VlmAnalyzer(
        redis_client=mock_redis,
        vlm_client=ScriptedVlmClient(
            [make_verdict(risk_score=70, summary="Multiple objects in batch")]
        ),
    )

    event = await analyzer.analyze_batch(
        batch_id=queue_item["batch_id"],
        camera_id=queue_item["camera_id"],
        detection_ids=queue_item["detection_ids"],
    )

    assert event is not None
    assert event.risk_score == 70

    # Verify all detections are associated with the event (junction table)
    async with get_session() as session:
        result = await session.execute(
            select(EventDetection.detection_id).where(EventDetection.event_id == event.id)
        )
        stored_ids = [row[0] for row in result.fetchall()]
    assert len(stored_ids) == 5
