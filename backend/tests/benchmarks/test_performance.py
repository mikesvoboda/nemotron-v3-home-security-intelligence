"""Core performance benchmarks for regression detection.

These benchmarks measure performance of critical operations:
- JSON serialization speed
- Database query performance (simple select)
- Service function call overhead

Usage:
    pytest tests/benchmarks/test_performance.py --benchmark-only
    pytest tests/benchmarks/test_performance.py --benchmark-compare
    pytest tests/benchmarks/test_performance.py --benchmark-compare-fail=mean:20%
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def performance_env() -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL to a temporary per-test database."""
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "perf_test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path

        get_settings.cache_clear()

        try:
            yield test_db_url
        finally:
            if original_db_url is not None:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)

            if original_redis_url is not None:
                os.environ["REDIS_URL"] = original_redis_url
            else:
                os.environ.pop("REDIS_URL", None)

            if original_runtime_env_path is not None:
                os.environ["HSI_RUNTIME_ENV_PATH"] = original_runtime_env_path
            else:
                os.environ.pop("HSI_RUNTIME_ENV_PATH", None)

            get_settings.cache_clear()


@pytest.fixture
async def performance_db(performance_env: str) -> AsyncGenerator[str]:
    """Initialize a temporary SQLite DB for performance tests."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    get_settings.cache_clear()
    await close_db()
    await init_db()

    try:
        yield performance_env
    finally:
        await close_db()
        get_settings.cache_clear()


def run_async(coro):
    """Run an async coroutine in a sync context for benchmarks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Sample Data Generators
# =============================================================================


def generate_event_data(count: int = 100) -> list[dict]:
    """Generate sample event data for serialization benchmarks."""
    return [
        {
            "id": i,
            "event_id": f"evt_{i:08d}",
            "camera_id": f"cam_{i % 5}",
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "motion_detected",
            "severity": "medium",
            "risk_score": 45.5 + (i % 50),
            "description": f"Motion detected in zone {i % 10}",
            "metadata": {
                "zone_id": i % 10,
                "confidence": 0.95,
                "detections": [
                    {"class": "person", "confidence": 0.95, "bbox": [100, 200, 300, 400]},
                    {"class": "car", "confidence": 0.88, "bbox": [50, 100, 150, 200]},
                ],
            },
            "acknowledged": False,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        for i in range(count)
    ]


def generate_detection_data(count: int = 100) -> list[dict]:
    """Generate sample detection data for serialization benchmarks."""
    return [
        {
            "id": i,
            "detection_id": f"det_{i:08d}",
            "event_id": f"evt_{i // 10:08d}",
            "camera_id": f"cam_{i % 5}",
            "class_name": ["person", "car", "dog", "cat", "bicycle"][i % 5],
            "confidence": 0.85 + (i % 15) / 100,
            "bbox": [100 + i, 200 + i, 300 + i, 400 + i],
            "timestamp": datetime.now(UTC).isoformat(),
            "track_id": f"track_{i % 20:04d}",
            "attributes": {
                "color": ["red", "blue", "green", "black", "white"][i % 5],
                "size": ["small", "medium", "large"][i % 3],
            },
        }
        for i in range(count)
    ]


def generate_camera_config(count: int = 10) -> list[dict]:
    """Generate sample camera configuration data."""
    return [
        {
            "id": i,
            "camera_id": f"cam_{i:03d}",
            "name": f"Camera {i}",
            "location": f"Zone {i % 5}",
            "ftp_path": f"/export/foscam/camera_{i}",
            "enabled": True,
            "status": "online",
            "last_seen": datetime.now(UTC).isoformat(),
            "settings": {
                "resolution": "1920x1080",
                "fps": 30,
                "motion_sensitivity": 0.7,
                "night_vision": True,
                "ptz_enabled": i % 3 == 0,
            },
            "zones": [
                {"id": j, "name": f"Zone {j}", "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]}
                for j in range(3)
            ],
        }
        for i in range(count)
    ]


# =============================================================================
# JSON Serialization Benchmarks
# =============================================================================


@pytest.mark.slow
class TestJSONSerializationBenchmarks:
    """Benchmark tests for JSON serialization performance."""

    @pytest.mark.benchmark(group="json-serialize")
    def test_json_dumps_events(self, benchmark):
        """Benchmark JSON serialization of event data."""
        events = generate_event_data(100)

        result = benchmark(json.dumps, events, default=str)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.benchmark(group="json-serialize")
    def test_json_dumps_detections(self, benchmark):
        """Benchmark JSON serialization of detection data."""
        detections = generate_detection_data(100)

        result = benchmark(json.dumps, detections, default=str)
        assert isinstance(result, str)

    @pytest.mark.benchmark(group="json-serialize")
    def test_json_dumps_camera_config(self, benchmark):
        """Benchmark JSON serialization of camera configuration."""
        cameras = generate_camera_config(20)

        result = benchmark(json.dumps, cameras, default=str)
        assert isinstance(result, str)

    @pytest.mark.benchmark(group="json-deserialize")
    def test_json_loads_events(self, benchmark):
        """Benchmark JSON deserialization of event data."""
        events = generate_event_data(100)
        json_str = json.dumps(events, default=str)

        result = benchmark(json.loads, json_str)
        assert isinstance(result, list)
        assert len(result) == 100

    @pytest.mark.benchmark(group="json-deserialize")
    def test_json_loads_detections(self, benchmark):
        """Benchmark JSON deserialization of detection data."""
        detections = generate_detection_data(100)
        json_str = json.dumps(detections, default=str)

        result = benchmark(json.loads, json_str)
        assert isinstance(result, list)
        assert len(result) == 100

    @pytest.mark.benchmark(group="json-roundtrip")
    def test_json_roundtrip_large_payload(self, benchmark):
        """Benchmark JSON round-trip for large payloads."""
        events = generate_event_data(500)

        def roundtrip():
            json_str = json.dumps(events, default=str)
            return json.loads(json_str)

        result = benchmark(roundtrip)
        assert len(result) == 500


# =============================================================================
# Database Query Benchmarks
# =============================================================================


@pytest.mark.slow
class TestDatabaseQueryBenchmarks:
    """Benchmark tests for database query performance."""

    @pytest.mark.benchmark(group="db-simple")
    def test_simple_select_query(self, benchmark, performance_db: str):
        """Benchmark simple SELECT query execution."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        async def run_select():
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar()

        result = benchmark(lambda: run_async(run_select()))
        assert result == 1

    @pytest.mark.benchmark(group="db-simple")
    def test_session_creation(self, benchmark, performance_db: str):
        """Benchmark database session creation overhead."""
        from backend.core.database import get_async_session

        async def create_session():
            async with get_async_session() as session:
                return session is not None

        result = benchmark(lambda: run_async(create_session()))
        assert result is True

    @pytest.mark.benchmark(group="db-transaction")
    def test_transaction_commit(self, benchmark, performance_db: str):
        """Benchmark transaction commit overhead."""
        from sqlalchemy import text

        from backend.core.database import get_async_session

        async def run_transaction():
            async with get_async_session() as session:
                await session.execute(text("SELECT 1"))
                await session.commit()
                return True

        result = benchmark(lambda: run_async(run_transaction()))
        assert result is True


# =============================================================================
# Service Function Call Overhead Benchmarks
# =============================================================================


@pytest.mark.slow
class TestServiceCallOverheadBenchmarks:
    """Benchmark tests for service function call overhead."""

    @pytest.mark.benchmark(group="service-validation")
    def test_pydantic_model_validation(self, benchmark):
        """Benchmark Pydantic model validation overhead."""
        from pydantic import BaseModel, Field

        class DetectionModel(BaseModel):
            id: int
            detection_id: str
            class_name: str
            confidence: float = Field(ge=0, le=1)
            bbox: list[int]

        data = {
            "id": 1,
            "detection_id": "det_00000001",
            "class_name": "person",
            "confidence": 0.95,
            "bbox": [100, 200, 300, 400],
        }

        result = benchmark(DetectionModel.model_validate, data)
        assert result.detection_id == "det_00000001"

    @pytest.mark.benchmark(group="service-validation")
    def test_pydantic_model_serialization(self, benchmark):
        """Benchmark Pydantic model serialization overhead."""
        from pydantic import BaseModel, Field

        class DetectionModel(BaseModel):
            id: int
            detection_id: str
            class_name: str
            confidence: float = Field(ge=0, le=1)
            bbox: list[int]

        model = DetectionModel(
            id=1,
            detection_id="det_00000001",
            class_name="person",
            confidence=0.95,
            bbox=[100, 200, 300, 400],
        )

        result = benchmark(model.model_dump)
        assert result["detection_id"] == "det_00000001"

    @pytest.mark.benchmark(group="service-validation")
    def test_pydantic_batch_validation(self, benchmark):
        """Benchmark Pydantic validation of batch data."""
        from pydantic import BaseModel, Field

        class DetectionModel(BaseModel):
            id: int
            detection_id: str
            class_name: str
            confidence: float = Field(ge=0, le=1)
            bbox: list[int]

        batch_data = [
            {
                "id": i,
                "detection_id": f"det_{i:08d}",
                "class_name": "person",
                "confidence": 0.95,
                "bbox": [100, 200, 300, 400],
            }
            for i in range(100)
        ]

        def validate_batch():
            return [DetectionModel.model_validate(d) for d in batch_data]

        result = benchmark(validate_batch)
        assert len(result) == 100

    @pytest.mark.benchmark(group="service-config")
    def test_settings_access(self, benchmark, performance_env: str):
        """Benchmark settings configuration access overhead."""
        from backend.core.config import get_settings

        # Clear cache to measure cold access
        get_settings.cache_clear()

        def access_settings():
            settings = get_settings()
            return settings.database_url

        result = benchmark(access_settings)
        assert result is not None

    @pytest.mark.benchmark(group="service-config")
    def test_settings_cached_access(self, benchmark, performance_env: str):
        """Benchmark cached settings access (warm cache)."""
        from backend.core.config import get_settings

        # Warm up cache
        get_settings()

        result = benchmark(get_settings)
        assert result is not None


# =============================================================================
# Data Processing Benchmarks
# =============================================================================


@pytest.mark.slow
class TestDataProcessingBenchmarks:
    """Benchmark tests for data processing operations."""

    @pytest.mark.benchmark(group="processing-filter")
    def test_filter_high_confidence_detections(self, benchmark):
        """Benchmark filtering detections by confidence threshold."""
        detections = generate_detection_data(1000)

        def filter_detections():
            return [d for d in detections if d["confidence"] >= 0.9]

        result = benchmark(filter_detections)
        assert isinstance(result, list)

    @pytest.mark.benchmark(group="processing-group")
    def test_group_detections_by_camera(self, benchmark):
        """Benchmark grouping detections by camera."""
        detections = generate_detection_data(1000)

        def group_by_camera():
            result: dict[str, list[dict]] = {}
            for d in detections:
                camera_id = d["camera_id"]
                if camera_id not in result:
                    result[camera_id] = []
                result[camera_id].append(d)
            return result

        result = benchmark(group_by_camera)
        assert len(result) == 5  # 5 cameras

    @pytest.mark.benchmark(group="processing-sort")
    def test_sort_events_by_timestamp(self, benchmark):
        """Benchmark sorting events by timestamp."""
        events = generate_event_data(1000)

        def sort_events():
            return sorted(events, key=lambda e: e["timestamp"], reverse=True)

        result = benchmark(sort_events)
        assert len(result) == 1000

    @pytest.mark.benchmark(group="processing-aggregate")
    def test_aggregate_risk_scores(self, benchmark):
        """Benchmark aggregating risk scores."""
        events = generate_event_data(1000)

        def aggregate_risk():
            scores = [e["risk_score"] for e in events]
            return {
                "min": min(scores),
                "max": max(scores),
                "avg": sum(scores) / len(scores),
                "count": len(scores),
            }

        result = benchmark(aggregate_risk)
        assert "avg" in result
        assert result["count"] == 1000


# =============================================================================
# Async Operation Benchmarks
# =============================================================================


@pytest.mark.slow
class TestAsyncOperationBenchmarks:
    """Benchmark tests for async operation overhead."""

    @pytest.mark.benchmark(group="async-gather")
    def test_asyncio_gather_overhead(self, benchmark):
        """Benchmark asyncio.gather overhead for parallel operations."""

        async def dummy_async_op(n: int) -> int:
            return n * 2

        async def run_gather():
            tasks = [dummy_async_op(i) for i in range(100)]
            return await asyncio.gather(*tasks)

        result = benchmark(lambda: run_async(run_gather()))
        assert len(result) == 100

    @pytest.mark.benchmark(group="async-create-task")
    def test_task_creation_overhead(self, benchmark):
        """Benchmark asyncio task creation overhead."""

        async def dummy_task() -> int:
            return 42

        async def create_tasks():
            tasks = [asyncio.create_task(dummy_task()) for _ in range(100)]
            results = await asyncio.gather(*tasks)
            return results

        result = benchmark(lambda: run_async(create_tasks()))
        assert len(result) == 100
        assert all(r == 42 for r in result)

    @pytest.mark.benchmark(group="async-queue")
    def test_asyncio_queue_throughput(self, benchmark):
        """Benchmark asyncio.Queue put/get throughput."""

        async def queue_operations():
            queue: asyncio.Queue[int] = asyncio.Queue()
            for i in range(100):
                await queue.put(i)
            results = []
            for _ in range(100):
                results.append(await queue.get())
            return results

        result = benchmark(lambda: run_async(queue_operations()))
        assert len(result) == 100
