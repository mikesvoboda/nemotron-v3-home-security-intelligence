"""Unit tests for detection API cache invalidation (NEM-1951).

Tests verify that cache is properly invalidated when detections are mutated.
This prevents stale data from being served after mutations.

Related Linear issue: NEM-1951
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_cache_service_dep
from backend.api.routes.detections import _bulk_rate_limiter, router
from backend.core.constants import CacheInvalidationReason
from backend.core.database import get_db
from backend.models.camera import Camera
from backend.models.detection import Detection

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_detection() -> Detection:
    """Create a sample detection for testing."""
    return Detection(
        id=1,
        camera_id="front_door",
        file_path="/path/to/image.jpg",
        file_type="image/jpeg",
        detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        object_type="person",
        confidence=0.95,
        bbox_x=100,
        bbox_y=200,
        bbox_width=150,
        bbox_height=300,
    )


@pytest.fixture
def sample_camera() -> Camera:
    """Create a sample camera for testing."""
    camera = Camera(
        id="front_door",
        name="Front Door",
        folder_path="/export/foscam/Front Door",
    )
    return camera


@pytest.fixture
def mock_db_session(sample_detection: Detection, sample_camera: Camera) -> AsyncMock:
    """Create a mock database session that returns the sample detection.

    This mock is designed to handle different query patterns:
    - Camera ID lookups for bulk create: returns valid camera IDs
    - Detection queries for update/delete: returns sample detection(s)
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()

    # Create a unified mock result that handles both camera and detection queries
    # The mock is flexible enough to handle different query patterns
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_detection]
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = sample_detection
    # For camera ID queries (returns list of tuples with camera IDs)
    mock_result.all.return_value = [(sample_camera.id,)]

    session.execute = AsyncMock(return_value=mock_result)

    # Mock refresh to be a no-op
    async def mock_refresh(obj: object) -> None:
        pass

    session.refresh = mock_refresh

    return session


@pytest.fixture
def mock_cache_service() -> MagicMock:
    """Create a mock cache service that tracks invalidation calls.

    This mock implements the CacheService interface used by routes.
    """
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)  # Cache miss
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=0)
    mock_cache.invalidate_detections = AsyncMock(return_value=1)  # Simulates 1 key deleted
    mock_cache.invalidate_detection_stats = AsyncMock(return_value=1)  # Simulates 1 key deleted
    mock_cache.invalidate_events = AsyncMock(return_value=1)  # Related event caches
    mock_cache.invalidate_event_stats = AsyncMock(return_value=1)  # Related event stats caches
    return mock_cache


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_cache_service: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies.

    Uses FastAPI dependency_overrides for clean dependency injection.
    """
    app = FastAPI()
    app.include_router(router)

    # Override the database dependency
    async def override_get_db() -> AsyncMock:
        yield mock_db_session

    # Override the cache service dependency
    async def override_cache_service() -> MagicMock:
        yield mock_cache_service

    # Override the rate limiter dependency (NEM-2600)
    async def override_rate_limiter() -> None:
        yield None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service_dep] = override_cache_service
    app.dependency_overrides[_bulk_rate_limiter] = override_rate_limiter

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# Cache Invalidation Tests - Bulk Create (POST /bulk)
# =============================================================================


class TestDetectionBulkCreateCacheInvalidation:
    """Tests for cache invalidation when creating detections via POST /bulk endpoint."""

    def test_bulk_create_detections_invalidates_detections_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk creating detections invalidates detections cache.

        When detections are created, the detection list caches should be
        invalidated to ensure queries return fresh data.
        """
        response = client.post(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "camera_id": "front_door",
                        "object_type": "person",
                        "confidence": 0.95,
                        "detected_at": "2025-12-23T10:00:00Z",
                        "file_path": "/path/to/image.jpg",
                        "bbox_x": 100,
                        "bbox_y": 200,
                        "bbox_width": 150,
                        "bbox_height": 300,
                    }
                ]
            },
        )

        # Verify the endpoint returned multi-status
        assert response.status_code == 207

        # Verify detections cache invalidation was called
        mock_cache_service.invalidate_detections.assert_called_once()

    def test_bulk_create_detections_invalidates_events_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk creating detections invalidates events cache.

        Since detections link to events, event caches should also be
        invalidated to ensure accurate detection counts.
        """
        response = client.post(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "camera_id": "front_door",
                        "object_type": "vehicle",
                        "confidence": 0.88,
                        "detected_at": "2025-12-23T10:05:00Z",
                        "file_path": "/path/to/image2.jpg",
                        "bbox_x": 50,
                        "bbox_y": 100,
                        "bbox_width": 200,
                        "bbox_height": 150,
                    }
                ]
            },
        )

        assert response.status_code == 207

        # Verify event-related cache invalidation was called
        mock_cache_service.invalidate_event_stats.assert_called_once()

    def test_bulk_create_uses_correct_invalidation_reason(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk create uses the correct reason for metrics tracking."""
        response = client.post(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "camera_id": "front_door",
                        "object_type": "person",
                        "confidence": 0.9,
                        "detected_at": "2025-12-23T10:00:00Z",
                        "file_path": "/path/to/image.jpg",
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_width": 100,
                        "bbox_height": 100,
                    }
                ]
            },
        )

        assert response.status_code == 207

        # Verify the correct reason was passed
        mock_cache_service.invalidate_detections.assert_called_once_with(
            reason=CacheInvalidationReason.DETECTION_CREATED
        )
        mock_cache_service.invalidate_event_stats.assert_called_once_with(
            reason=CacheInvalidationReason.DETECTION_CREATED
        )


# =============================================================================
# Cache Invalidation Tests - Bulk Update (PATCH /bulk)
# =============================================================================


class TestDetectionBulkUpdateCacheInvalidation:
    """Tests for cache invalidation when updating detections via PATCH /bulk endpoint."""

    def test_bulk_update_detections_invalidates_detections_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk updating detections invalidates detections cache.

        When detections are updated, the detection caches should be
        invalidated to reflect the changes.
        """
        response = client.patch(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "id": 1,
                        "object_type": "vehicle",
                        "confidence": 0.92,
                    }
                ]
            },
        )

        # Verify the endpoint returned multi-status
        assert response.status_code == 207

        # Verify detections cache invalidation was called
        mock_cache_service.invalidate_detections.assert_called_once()

    def test_bulk_update_detections_invalidates_events_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk updating detections invalidates event-related caches.

        Since detections link to events and detection stats affect event displays,
        event caches should be invalidated.
        """
        response = client.patch(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "id": 1,
                        "confidence": 0.75,
                    }
                ]
            },
        )

        assert response.status_code == 207

        # Verify event-related cache invalidation was called
        mock_cache_service.invalidate_event_stats.assert_called_once()

    def test_bulk_update_uses_correct_invalidation_reason(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk update uses the correct reason for metrics tracking."""
        response = client.patch(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "id": 1,
                        "object_type": "truck",
                    }
                ]
            },
        )

        assert response.status_code == 207

        # Verify the correct reason was passed
        mock_cache_service.invalidate_detections.assert_called_once_with(
            reason=CacheInvalidationReason.DETECTION_UPDATED
        )
        mock_cache_service.invalidate_event_stats.assert_called_once_with(
            reason=CacheInvalidationReason.DETECTION_UPDATED
        )


# =============================================================================
# Cache Invalidation Tests - Bulk Delete (DELETE /bulk)
# =============================================================================


class TestDetectionBulkDeleteCacheInvalidation:
    """Tests for cache invalidation when deleting detections via DELETE /bulk endpoint."""

    def test_bulk_delete_detections_invalidates_detections_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk deleting detections invalidates detections cache.

        When detections are deleted, the detection list caches should be
        invalidated so queries no longer return the deleted items.
        """
        response = client.request(
            "DELETE",
            "/api/detections/bulk",
            json={"detection_ids": [1]},
        )

        # Verify the endpoint returned multi-status
        assert response.status_code == 207

        # Verify detections cache invalidation was called
        mock_cache_service.invalidate_detections.assert_called_once()

    def test_bulk_delete_detections_invalidates_events_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk deleting detections invalidates event-related caches.

        Since detections link to events, removing detections affects event
        detection counts, so event caches should be invalidated.
        """
        response = client.request(
            "DELETE",
            "/api/detections/bulk",
            json={"detection_ids": [1, 2, 3]},
        )

        assert response.status_code == 207

        # Verify event-related cache invalidation was called
        mock_cache_service.invalidate_event_stats.assert_called_once()

    def test_bulk_delete_uses_correct_invalidation_reason(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that bulk delete uses the correct reason for metrics tracking."""
        response = client.request(
            "DELETE",
            "/api/detections/bulk",
            json={"detection_ids": [1]},
        )

        assert response.status_code == 207

        # Verify the correct reason was passed
        mock_cache_service.invalidate_detections.assert_called_once_with(
            reason=CacheInvalidationReason.DETECTION_DELETED
        )
        mock_cache_service.invalidate_event_stats.assert_called_once_with(
            reason=CacheInvalidationReason.DETECTION_DELETED
        )


# =============================================================================
# Cache Invalidation Failure Tests
# =============================================================================


class TestDetectionCacheInvalidationFailure:
    """Tests for graceful handling of cache invalidation failures."""

    def test_bulk_create_succeeds_when_cache_invalidation_fails(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cache invalidation failure doesn't fail the create request.

        Cache invalidation should be best-effort - if Redis is down, the
        mutation should still succeed.
        """
        # Make cache invalidation fail
        mock_cache_service.invalidate_detections.side_effect = Exception("Redis connection error")
        mock_cache_service.invalidate_event_stats.side_effect = Exception("Redis connection error")

        response = client.post(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "camera_id": "front_door",
                        "object_type": "person",
                        "confidence": 0.95,
                        "detected_at": "2025-12-23T10:00:00Z",
                        "file_path": "/path/to/image.jpg",
                        "bbox_x": 100,
                        "bbox_y": 200,
                        "bbox_width": 150,
                        "bbox_height": 300,
                    }
                ]
            },
        )

        # Request should still succeed despite cache invalidation failure
        assert response.status_code == 207

    def test_bulk_update_succeeds_when_cache_invalidation_fails(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cache invalidation failure doesn't fail the update request."""
        # Make cache invalidation fail
        mock_cache_service.invalidate_detections.side_effect = Exception("Redis connection error")
        mock_cache_service.invalidate_event_stats.side_effect = Exception("Redis connection error")

        response = client.patch(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "id": 1,
                        "confidence": 0.85,
                    }
                ]
            },
        )

        # Request should still succeed
        assert response.status_code == 207

    def test_bulk_delete_succeeds_when_cache_invalidation_fails(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cache invalidation failure doesn't fail the delete request."""
        # Make cache invalidation fail
        mock_cache_service.invalidate_detections.side_effect = Exception("Redis connection error")
        mock_cache_service.invalidate_event_stats.side_effect = Exception("Redis connection error")

        response = client.request(
            "DELETE",
            "/api/detections/bulk",
            json={"detection_ids": [1]},
        )

        # Request should still succeed
        assert response.status_code == 207


# =============================================================================
# No Cache Invalidation on Failed Operations
# =============================================================================


class TestDetectionNoCacheInvalidationOnFailure:
    """Tests that cache is NOT invalidated when mutations fail."""

    def test_bulk_create_no_invalidation_when_all_fail(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that failed bulk creates don't invalidate cache.

        When all operations in a bulk create fail (e.g., invalid camera IDs),
        the cache should NOT be invalidated since no data changed.
        """

        # Override mock to simulate camera not found (empty camera results)
        async def mock_execute_no_cameras(query: Any) -> MagicMock:
            mock_result = MagicMock()
            mock_result.all.return_value = []  # No valid cameras found
            mock_result.scalar_one_or_none.return_value = None
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            return mock_result

        mock_db_session.execute = mock_execute_no_cameras

        response = client.post(
            "/api/detections/bulk",
            json={
                "detections": [
                    {
                        "camera_id": "nonexistent_camera",
                        "object_type": "person",
                        "confidence": 0.95,
                        "detected_at": "2025-12-23T10:00:00Z",
                        "file_path": "/path/to/image.jpg",
                        "bbox_x": 100,
                        "bbox_y": 200,
                        "bbox_width": 150,
                        "bbox_height": 300,
                    }
                ]
            },
        )

        # Endpoint returns 207 with failed results
        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 0
        assert data["failed"] == 1

        # Cache should NOT be invalidated when all operations fail
        mock_cache_service.invalidate_detections.assert_not_called()
        mock_cache_service.invalidate_event_stats.assert_not_called()
