"""Unit tests for event bulk operation schemas and validation.

Tests the Pydantic schemas used for bulk event operations including
create, update, and delete requests.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.bulk import (
    BulkItemResult,
    BulkOperationResponse,
    BulkOperationStatus,
    EventBulkCreateItem,
    EventBulkCreateRequest,
    EventBulkDeleteRequest,
    EventBulkUpdateItem,
    EventBulkUpdateRequest,
)


class TestBulkOperationStatus:
    """Tests for the BulkOperationStatus enum."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert BulkOperationStatus.SUCCESS == "success"
        assert BulkOperationStatus.FAILED == "failed"
        assert BulkOperationStatus.SKIPPED == "skipped"

    def test_status_is_string_enum(self) -> None:
        """Test that status values are strings."""
        assert isinstance(BulkOperationStatus.SUCCESS.value, str)
        assert isinstance(BulkOperationStatus.FAILED.value, str)
        assert isinstance(BulkOperationStatus.SKIPPED.value, str)


class TestBulkItemResult:
    """Tests for the BulkItemResult schema."""

    def test_valid_success_result(self) -> None:
        """Test creating a successful result."""
        result = BulkItemResult(
            index=0,
            status=BulkOperationStatus.SUCCESS,
            id=123,
            error=None,
        )
        assert result.index == 0
        assert result.status == BulkOperationStatus.SUCCESS
        assert result.id == 123
        assert result.error is None

    def test_valid_failed_result(self) -> None:
        """Test creating a failed result with error message."""
        result = BulkItemResult(
            index=5,
            status=BulkOperationStatus.FAILED,
            id=None,
            error="Event not found",
        )
        assert result.index == 5
        assert result.status == BulkOperationStatus.FAILED
        assert result.id is None
        assert result.error == "Event not found"

    def test_index_must_be_non_negative(self) -> None:
        """Test that index must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            BulkItemResult(
                index=-1,
                status=BulkOperationStatus.SUCCESS,
            )
        assert "index" in str(exc_info.value)


class TestBulkOperationResponse:
    """Tests for the BulkOperationResponse schema."""

    def test_valid_response(self) -> None:
        """Test creating a valid bulk operation response."""
        response = BulkOperationResponse(
            total=10,
            succeeded=8,
            failed=2,
            skipped=0,
            results=[
                BulkItemResult(index=0, status=BulkOperationStatus.SUCCESS, id=1),
                BulkItemResult(index=1, status=BulkOperationStatus.FAILED, error="Not found"),
            ],
        )
        assert response.total == 10
        assert response.succeeded == 8
        assert response.failed == 2
        assert response.skipped == 0
        assert len(response.results) == 2

    def test_counts_must_be_non_negative(self) -> None:
        """Test that all counts must be >= 0."""
        with pytest.raises(ValidationError):
            BulkOperationResponse(
                total=-1,
                succeeded=0,
                failed=0,
            )


class TestEventBulkCreateItem:
    """Tests for the EventBulkCreateItem schema."""

    def test_valid_create_item(self) -> None:
        """Test creating a valid event create item."""
        item = EventBulkCreateItem(
            camera_id="front_door",
            started_at=datetime.now(UTC),
            risk_score=75,
            risk_level="high",
            summary="Person detected at front door",
        )
        assert item.camera_id == "front_door"
        assert item.risk_score == 75
        assert item.risk_level == "high"

    def test_camera_id_pattern_validation(self) -> None:
        """Test that camera_id follows the required pattern."""
        # Valid patterns
        EventBulkCreateItem(
            camera_id="front_door",
            started_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="Test",
        )
        EventBulkCreateItem(
            camera_id="camera-1",
            started_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="Test",
        )

        # Invalid pattern (spaces)
        with pytest.raises(ValidationError):
            EventBulkCreateItem(
                camera_id="front door",
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary="Test",
            )

    def test_risk_score_range(self) -> None:
        """Test that risk_score must be 0-100."""
        # Valid range
        EventBulkCreateItem(
            camera_id="test",
            started_at=datetime.now(UTC),
            risk_score=0,
            risk_level="low",
            summary="Test",
        )
        EventBulkCreateItem(
            camera_id="test",
            started_at=datetime.now(UTC),
            risk_score=100,
            risk_level="critical",
            summary="Test",
        )

        # Out of range
        with pytest.raises(ValidationError):
            EventBulkCreateItem(
                camera_id="test",
                started_at=datetime.now(UTC),
                risk_score=101,
                risk_level="critical",
                summary="Test",
            )
        with pytest.raises(ValidationError):
            EventBulkCreateItem(
                camera_id="test",
                started_at=datetime.now(UTC),
                risk_score=-1,
                risk_level="low",
                summary="Test",
            )

    def test_risk_level_pattern(self) -> None:
        """Test that risk_level follows the required pattern."""
        valid_levels = ["low", "medium", "high", "critical"]
        for level in valid_levels:
            EventBulkCreateItem(
                camera_id="test",
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level=level,
                summary="Test",
            )

        # Invalid level
        with pytest.raises(ValidationError):
            EventBulkCreateItem(
                camera_id="test",
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="invalid",
                summary="Test",
            )

    def test_detection_ids_default_empty(self) -> None:
        """Test that detection_ids defaults to empty list."""
        item = EventBulkCreateItem(
            camera_id="test",
            started_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="Test",
        )
        assert item.detection_ids == []


class TestEventBulkCreateRequest:
    """Tests for the EventBulkCreateRequest schema."""

    def test_valid_request(self) -> None:
        """Test creating a valid bulk create request."""
        request = EventBulkCreateRequest(
            events=[
                EventBulkCreateItem(
                    camera_id="front_door",
                    started_at=datetime.now(UTC),
                    risk_score=75,
                    risk_level="high",
                    summary="Test event 1",
                ),
                EventBulkCreateItem(
                    camera_id="back_door",
                    started_at=datetime.now(UTC),
                    risk_score=25,
                    risk_level="low",
                    summary="Test event 2",
                ),
            ]
        )
        assert len(request.events) == 2

    def test_events_list_cannot_be_empty(self) -> None:
        """Test that events list must have at least 1 item."""
        with pytest.raises(ValidationError):
            EventBulkCreateRequest(events=[])

    def test_events_list_max_length(self) -> None:
        """Test that events list has max 100 items."""
        events = [
            EventBulkCreateItem(
                camera_id=f"camera_{i}",
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary=f"Test event {i}",
            )
            for i in range(101)
        ]
        with pytest.raises(ValidationError):
            EventBulkCreateRequest(events=events)


class TestEventBulkUpdateItem:
    """Tests for the EventBulkUpdateItem schema."""

    def test_valid_update_item(self) -> None:
        """Test creating a valid update item."""
        item = EventBulkUpdateItem(
            id=123,
            reviewed=True,
            notes="Reviewed and cleared",
        )
        assert item.id == 123
        assert item.reviewed is True
        assert item.notes == "Reviewed and cleared"

    def test_id_must_be_positive(self) -> None:
        """Test that id must be > 0."""
        with pytest.raises(ValidationError):
            EventBulkUpdateItem(id=0)
        with pytest.raises(ValidationError):
            EventBulkUpdateItem(id=-1)

    def test_notes_max_length(self) -> None:
        """Test that notes has max length of 2000."""
        # Valid length
        EventBulkUpdateItem(id=1, notes="x" * 2000)

        # Too long
        with pytest.raises(ValidationError):
            EventBulkUpdateItem(id=1, notes="x" * 2001)


class TestEventBulkUpdateRequest:
    """Tests for the EventBulkUpdateRequest schema."""

    def test_valid_request(self) -> None:
        """Test creating a valid bulk update request."""
        request = EventBulkUpdateRequest(
            events=[
                EventBulkUpdateItem(id=1, reviewed=True),
                EventBulkUpdateItem(id=2, reviewed=False, notes="False positive"),
            ]
        )
        assert len(request.events) == 2

    def test_events_list_cannot_be_empty(self) -> None:
        """Test that events list must have at least 1 item."""
        with pytest.raises(ValidationError):
            EventBulkUpdateRequest(events=[])

    def test_events_list_max_length(self) -> None:
        """Test that events list has max 100 items."""
        events = [EventBulkUpdateItem(id=i, reviewed=True) for i in range(1, 102)]
        with pytest.raises(ValidationError):
            EventBulkUpdateRequest(events=events)


class TestEventBulkDeleteRequest:
    """Tests for the EventBulkDeleteRequest schema."""

    def test_valid_request(self) -> None:
        """Test creating a valid bulk delete request."""
        request = EventBulkDeleteRequest(
            event_ids=[1, 2, 3, 4, 5],
            soft_delete=True,
        )
        assert len(request.event_ids) == 5
        assert request.soft_delete is True

    def test_soft_delete_default_true(self) -> None:
        """Test that soft_delete defaults to True."""
        request = EventBulkDeleteRequest(event_ids=[1])
        assert request.soft_delete is True

    def test_event_ids_cannot_be_empty(self) -> None:
        """Test that event_ids must have at least 1 item."""
        with pytest.raises(ValidationError):
            EventBulkDeleteRequest(event_ids=[])

    def test_event_ids_max_length(self) -> None:
        """Test that event_ids has max 100 items."""
        with pytest.raises(ValidationError):
            EventBulkDeleteRequest(event_ids=list(range(1, 102)))
