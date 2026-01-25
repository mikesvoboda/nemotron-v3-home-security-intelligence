"""Unit tests for event detections ordering feature (NEM-3629).

Tests the order_detections_by parameter for GET /api/events/{id}/detections endpoint.
This feature allows ordering detections by:
- detected_at: Detection timestamp (default)
- created_at: When detection was associated with event (junction table timestamp)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.routes.events import VALID_DETECTION_ORDER_BY


class TestValidDetectionOrderByValues:
    """Tests for VALID_DETECTION_ORDER_BY constant."""

    def test_valid_order_by_values(self):
        """Test that valid order_by values are defined."""
        assert "detected_at" in VALID_DETECTION_ORDER_BY
        assert "created_at" in VALID_DETECTION_ORDER_BY
        assert len(VALID_DETECTION_ORDER_BY) == 2

    def test_order_by_is_frozen_set(self):
        """Test that VALID_DETECTION_ORDER_BY is immutable."""
        assert isinstance(VALID_DETECTION_ORDER_BY, frozenset)


class TestGetEventDetectionsEndpoint:
    """Tests for GET /api/events/{id}/detections endpoint with ordering."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_event(self):
        """Create a mock event with detections."""
        event = MagicMock()
        event.id = 1
        event.detection_id_list = [1, 2, 3]
        return event

    @pytest.mark.asyncio
    async def test_invalid_order_by_returns_400(self):
        """Test that invalid order_detections_by value returns 400 error."""
        from fastapi import FastAPI

        from backend.api.routes.events import router
        from backend.core.database import get_db

        app = FastAPI()
        app.include_router(router)

        # Mock the database dependency using FastAPI's dependency override
        async def mock_db_override():
            return AsyncMock()

        async def mock_get_event_or_404(event_id, db):
            mock_event = MagicMock()
            mock_event.detection_id_list = [1]
            return mock_event

        app.dependency_overrides[get_db] = mock_db_override

        with patch("backend.api.routes.events.get_event_or_404", mock_get_event_or_404):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/events/1/detections?order_detections_by=invalid_value"
                )

        assert response.status_code == 400
        assert "Invalid order_detections_by value" in response.json()["detail"]
        assert "invalid_value" in response.json()["detail"]
        assert "detected_at" in response.json()["detail"]
        assert "created_at" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_default_order_by_detected_at(self):
        """Test that default ordering is by detected_at."""
        from fastapi import FastAPI

        from backend.api.routes.events import router
        from backend.core.database import get_db

        app = FastAPI()
        app.include_router(router)

        # Track the query to verify ordering
        async def mock_db_override():
            db = AsyncMock()

            async def execute_side_effect(query):
                result = MagicMock()
                result.scalar.return_value = 0
                result.scalars.return_value.all.return_value = []
                return result

            db.execute = execute_side_effect
            return db

        async def mock_get_event_or_404(event_id, db):
            mock_event = MagicMock()
            mock_event.detection_id_list = []
            return mock_event

        app.dependency_overrides[get_db] = mock_db_override

        with patch("backend.api.routes.events.get_event_or_404", mock_get_event_or_404):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # No order_detections_by parameter - should use default
                response = await client.get("/api/events/1/detections")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_order_by_created_at_parameter(self):
        """Test ordering by created_at (junction table timestamp)."""
        from fastapi import FastAPI

        from backend.api.routes.events import router
        from backend.core.database import get_db

        app = FastAPI()
        app.include_router(router)

        async def mock_db_override():
            db = AsyncMock()

            async def execute_side_effect(query):
                result = MagicMock()
                result.scalar.return_value = 0
                result.all.return_value = []
                return result

            db.execute = execute_side_effect
            return db

        async def mock_get_event_or_404(event_id, db):
            mock_event = MagicMock()
            mock_event.detection_id_list = []
            return mock_event

        app.dependency_overrides[get_db] = mock_db_override

        with patch("backend.api.routes.events.get_event_or_404", mock_get_event_or_404):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/api/events/1/detections?order_detections_by=created_at"
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_detections_returns_empty_list(self):
        """Test that event with no detections returns empty list regardless of ordering."""
        from fastapi import FastAPI

        from backend.api.routes.events import router
        from backend.core.database import get_db

        app = FastAPI()
        app.include_router(router)

        async def mock_db_override():
            return AsyncMock()

        async def mock_get_event_or_404(event_id, db):
            mock_event = MagicMock()
            mock_event.detection_id_list = []
            return mock_event

        app.dependency_overrides[get_db] = mock_db_override

        with patch("backend.api.routes.events.get_event_or_404", mock_get_event_or_404):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Test with created_at ordering
                response = await client.get(
                    "/api/events/1/detections?order_detections_by=created_at"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0


class TestDetectionResponseSchema:
    """Tests for DetectionResponse schema with association_created_at field."""

    def test_detection_response_accepts_association_created_at(self):
        """Test that DetectionResponse accepts association_created_at field."""
        from backend.api.schemas.detections import DetectionResponse

        now = datetime.now(UTC)
        data = {
            "id": 1,
            "camera_id": "test_camera",
            "file_path": "/path/to/image.jpg",
            "detected_at": now,
            "association_created_at": now,
        }

        response = DetectionResponse(**data)
        assert response.association_created_at == now

    def test_detection_response_association_created_at_optional(self):
        """Test that association_created_at is optional (None by default)."""
        from backend.api.schemas.detections import DetectionResponse

        data = {
            "id": 1,
            "camera_id": "test_camera",
            "file_path": "/path/to/image.jpg",
            "detected_at": datetime.now(UTC),
        }

        response = DetectionResponse(**data)
        assert response.association_created_at is None

    def test_detection_response_model_dump_includes_association_created_at(self):
        """Test that model_dump includes association_created_at when set."""
        from backend.api.schemas.detections import DetectionResponse

        now = datetime.now(UTC)
        data = {
            "id": 1,
            "camera_id": "test_camera",
            "file_path": "/path/to/image.jpg",
            "detected_at": now,
            "association_created_at": now,
        }

        response = DetectionResponse(**data)
        dumped = response.model_dump()
        assert "association_created_at" in dumped
        assert dumped["association_created_at"] == now

    def test_detection_response_model_dump_detail_includes_association_created_at(self):
        """Test that model_dump_detail includes association_created_at."""
        from backend.api.schemas.detections import DetectionResponse

        now = datetime.now(UTC)
        data = {
            "id": 1,
            "camera_id": "test_camera",
            "file_path": "/path/to/image.jpg",
            "detected_at": now,
            "association_created_at": now,
        }

        response = DetectionResponse(**data)
        dumped = response.model_dump_detail()
        assert "association_created_at" in dumped


class TestDetectionOrderByValidation:
    """Tests for order_detections_by parameter validation."""

    def test_detected_at_is_valid(self):
        """Test that 'detected_at' is a valid order_by value."""
        assert "detected_at" in VALID_DETECTION_ORDER_BY

    def test_created_at_is_valid(self):
        """Test that 'created_at' is a valid order_by value."""
        assert "created_at" in VALID_DETECTION_ORDER_BY

    def test_invalid_values_not_in_set(self):
        """Test that invalid values are not in the valid set."""
        assert "invalid" not in VALID_DETECTION_ORDER_BY
        assert "timestamp" not in VALID_DETECTION_ORDER_BY
        assert "id" not in VALID_DETECTION_ORDER_BY
        assert "confidence" not in VALID_DETECTION_ORDER_BY
