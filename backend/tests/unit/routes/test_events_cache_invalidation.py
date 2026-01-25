"""Unit tests for event API cache invalidation (NEM-1938).

Tests verify that cache is properly invalidated when events are mutated.
This prevents stale data from being served after mutations.

Related Linear issue: NEM-1938
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_cache_service_dep
from backend.api.routes.events import router
from backend.core.constants import CacheInvalidationReason
from backend.core.database import get_db
from backend.models.event import Event

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    return Event(
        id=1,
        batch_id="batch-123",
        camera_id="front_door",
        started_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2025, 12, 23, 10, 5, 0, tzinfo=UTC),
        risk_score=75,
        risk_level="high",
        summary="Person detected at front door",
        reasoning="High confidence person detection during unusual hours",
        reviewed=False,
        notes=None,
        is_fast_path=False,
        object_types="person",
        version=1,  # Optimistic locking version (NEM-3625)
    )


@pytest.fixture
def mock_db_session(sample_event: Event) -> AsyncMock:
    """Create a mock database session that returns the sample event."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    # Mock execute to return the sample event via scalar_one_or_none
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_event
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
    mock_cache.invalidate_events = AsyncMock(return_value=1)  # Simulates 1 key deleted
    mock_cache.invalidate_event_stats = AsyncMock(return_value=1)  # Simulates 1 key deleted
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service_dep] = override_cache_service

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# Cache Invalidation Tests - Event Update (PATCH)
# =============================================================================


class TestEventUpdateCacheInvalidation:
    """Tests for cache invalidation when updating events via PATCH endpoint."""

    def test_update_event_reviewed_invalidates_event_stats_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that marking an event as reviewed invalidates event stats cache.

        When an event is marked as reviewed, the event stats cache should be
        invalidated to ensure the dashboard shows updated statistics.
        """
        # Patch AuditService to avoid side effects
        with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
            response = client.patch(
                "/api/events/1",
                json={"reviewed": True},
            )

        # Verify the endpoint succeeded
        assert response.status_code == 200

        # Verify cache invalidation was called
        mock_cache_service.invalidate_event_stats.assert_called_once()

    def test_update_event_notes_invalidates_events_cache(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that updating event notes invalidates the events cache.

        When an event is updated with notes, the events cache should be
        invalidated so lists reflect the updated data.
        """
        # Patch AuditService to avoid side effects
        with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
            response = client.patch(
                "/api/events/1",
                json={"notes": "Verified - false alarm"},
            )

        # Verify the endpoint succeeded
        assert response.status_code == 200

        # Verify events cache invalidation was called
        mock_cache_service.invalidate_events.assert_called_once()

    def test_update_event_invalidates_both_caches_when_reviewed_changes(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that updating reviewed status invalidates both caches.

        When reviewed status changes, both event stats and events list caches
        should be invalidated.
        """
        # Patch AuditService to avoid side effects
        with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
            response = client.patch(
                "/api/events/1",
                json={"reviewed": True, "notes": "Reviewed and confirmed"},
            )

        # Verify the endpoint succeeded
        assert response.status_code == 200

        # Verify both caches were invalidated
        mock_cache_service.invalidate_event_stats.assert_called_once()
        mock_cache_service.invalidate_events.assert_called_once()

    def test_update_event_cache_invalidation_failure_does_not_fail_request(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cache invalidation failure doesn't fail the update request.

        Cache invalidation should be best-effort - if Redis is down, the
        mutation should still succeed.
        """
        # Make cache invalidation fail
        mock_cache_service.invalidate_event_stats.side_effect = Exception("Redis connection error")
        mock_cache_service.invalidate_events.side_effect = Exception("Redis connection error")

        # Patch AuditService to avoid side effects
        with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
            response = client.patch(
                "/api/events/1",
                json={"reviewed": True},
            )

        # Request should still succeed despite cache invalidation failure
        assert response.status_code == 200


# =============================================================================
# Cache Invalidation Tests - Event Not Found
# =============================================================================


class TestEventNotFoundCacheInvalidation:
    """Tests for cache behavior when event is not found."""

    def test_update_nonexistent_event_does_not_invalidate_cache(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that updating a non-existent event doesn't invalidate cache.

        When an event is not found, no cache invalidation should occur.
        """
        # Override mock to return None (event not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.patch(
            "/api/events/999",
            json={"reviewed": True},
        )

        # Verify 404 returned
        assert response.status_code == 404

        # Verify cache was NOT invalidated
        mock_cache_service.invalidate_event_stats.assert_not_called()
        mock_cache_service.invalidate_events.assert_not_called()


# =============================================================================
# Cache Invalidation Tests - Invalidation Reason Tracking
# =============================================================================


class TestCacheInvalidationReason:
    """Tests for cache invalidation reason tracking."""

    def test_update_event_uses_correct_invalidation_reason(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cache invalidation uses the correct reason for tracking.

        The reason should indicate "event_updated" for metrics/debugging purposes.
        """
        # Patch AuditService to avoid side effects
        with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
            response = client.patch(
                "/api/events/1",
                json={"reviewed": True},
            )

        # Verify the endpoint succeeded
        assert response.status_code == 200

        # Verify the correct reason was passed
        mock_cache_service.invalidate_event_stats.assert_called_once_with(
            reason=CacheInvalidationReason.EVENT_UPDATED
        )
        mock_cache_service.invalidate_events.assert_called_once_with(
            reason=CacheInvalidationReason.EVENT_UPDATED
        )
