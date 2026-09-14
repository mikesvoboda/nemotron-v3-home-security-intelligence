"""Unit tests for events API schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.events import EventListResponse, EventResponse, EventUpdate
from backend.tests.factories import EventFactory


class TestEventResponseSchema:
    """Tests for EventResponse schema validation."""

    def test_event_response_valid(self):
        """Test EventResponse with valid data using factory.

        Note: risk_level is now a computed field derived from risk_score (NEM-3398).
        With risk_score=75, risk_level is computed as "high" (60-84 range).
        """
        # Generate event data using factory
        factory_event = EventFactory(
            id=1,
            camera_id="123e4567-e89b-12d3-a456-426614174000",
            started_at=datetime(2025, 12, 23, 12, 0, 0),
            ended_at=datetime(2025, 12, 23, 12, 2, 30),
            risk_score=75,
            risk_level="high",  # Computed from score (60-84 = high)
            summary="Person detected near front entrance",
            reviewed=False,
        )

        data = {
            "id": factory_event.id,
            "camera_id": factory_event.camera_id,
            "started_at": factory_event.started_at,
            "ended_at": factory_event.ended_at,
            "risk_score": factory_event.risk_score,
            # Note: risk_level is not passed - it's computed from risk_score
            "summary": factory_event.summary,
            "reviewed": factory_event.reviewed,
            "detection_count": 5,
            "detection_ids": [1, 2, 3, 4, 5],
        }
        event = EventResponse(**data)
        assert event.id == 1
        assert event.camera_id == "123e4567-e89b-12d3-a456-426614174000"
        assert event.risk_score == 75
        assert event.risk_level == "high"  # Computed from risk_score=75
        assert event.summary == "Person detected near front entrance"
        assert event.reviewed is False
        assert event.detection_count == 5
        assert event.detection_ids == [1, 2, 3, 4, 5]

    def test_event_response_minimal(self):
        """Test EventResponse with minimal required fields."""
        data = {
            "id": 1,
            "camera_id": "123e4567-e89b-12d3-a456-426614174000",
            "started_at": datetime(2025, 12, 23, 12, 0, 0),
            "ended_at": None,
            "risk_score": None,
            "risk_level": None,
            "summary": None,
            "reviewed": False,
            "detection_count": 0,
        }
        event = EventResponse(**data)
        assert event.id == 1
        assert event.camera_id == "123e4567-e89b-12d3-a456-426614174000"
        assert event.ended_at is None
        assert event.risk_score is None
        assert event.risk_level is None
        assert event.summary is None
        assert event.reviewed is False
        assert event.detection_count == 0
        assert event.detection_ids == []  # Default to empty list

    def test_event_response_missing_required_field(self):
        """Test EventResponse raises ValidationError when required field is missing."""
        data = {
            "camera_id": "123e4567-e89b-12d3-a456-426614174000",
            "started_at": datetime(2025, 12, 23, 12, 0, 0),
            # Missing 'id'
        }
        with pytest.raises(ValidationError) as exc_info:
            EventResponse(**data)
        assert "id" in str(exc_info.value)

    def test_event_response_invalid_type(self):
        """Test EventResponse raises ValidationError with invalid field type."""
        data = {
            "id": "not_an_integer",  # Should be int
            "camera_id": "123e4567-e89b-12d3-a456-426614174000",
            "started_at": datetime(2025, 12, 23, 12, 0, 0),
            "ended_at": None,
            "risk_score": None,
            "risk_level": None,
            "summary": None,
            "reviewed": False,
            "detection_count": 0,
        }
        with pytest.raises(ValidationError) as exc_info:
            EventResponse(**data)
        assert "id" in str(exc_info.value)

    def test_event_response_from_orm(self):
        """Test EventResponse can be created from ORM model attributes."""

        # Simulate ORM model with attributes
        class MockEvent:
            id = 1
            camera_id = "123e4567-e89b-12d3-a456-426614174000"
            started_at = datetime(2025, 12, 23, 12, 0, 0)
            ended_at = datetime(2025, 12, 23, 12, 2, 30)
            risk_score = 75
            risk_level = "medium"
            summary = "Person detected near front entrance"
            reviewed = False
            notes = None
            detection_count = 5

            def __init__(self):
                self.detection_ids = [1, 2, 3, 4, 5]

        event = EventResponse.model_validate(MockEvent())
        assert event.id == 1
        assert event.camera_id == "123e4567-e89b-12d3-a456-426614174000"
        assert event.risk_score == 75
        assert event.notes is None
        assert event.detection_ids == [1, 2, 3, 4, 5]

    def test_event_response_with_notes(self):
        """Test EventResponse with notes field."""
        data = {
            "id": 1,
            "camera_id": "123e4567-e89b-12d3-a456-426614174000",
            "started_at": datetime(2025, 12, 23, 12, 0, 0),
            "ended_at": datetime(2025, 12, 23, 12, 2, 30),
            "risk_score": 75,
            "risk_level": "medium",
            "summary": "Person detected near front entrance",
            "reviewed": True,
            "notes": "Verified - known visitor",
            "detection_count": 5,
        }
        event = EventResponse(**data)
        assert event.notes == "Verified - known visitor"
        assert event.reviewed is True

    def test_event_response_with_reasoning(self):
        """Test EventResponse with reasoning field."""
        data = {
            "id": 1,
            "camera_id": "123e4567-e89b-12d3-a456-426614174000",
            "started_at": datetime(2025, 12, 23, 12, 0, 0),
            "ended_at": datetime(2025, 12, 23, 12, 2, 30),
            "risk_score": 85,
            "risk_level": "high",
            "summary": "Person detected at unusual hour",
            "reasoning": "Person detected at 2 AM near restricted area with suspicious behavior",
            "reviewed": False,
            "detection_count": 3,
        }
        event = EventResponse(**data)
        assert (
            event.reasoning
            == "Person detected at 2 AM near restricted area with suspicious behavior"
        )

    def test_event_response_reasoning_none(self):
        """Test EventResponse with None reasoning field."""
        data = {
            "id": 1,
            "camera_id": "123e4567-e89b-12d3-a456-426614174000",
            "started_at": datetime(2025, 12, 23, 12, 0, 0),
            "ended_at": None,
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Test summary",
            "reasoning": None,
            "reviewed": False,
            "detection_count": 0,
        }
        event = EventResponse(**data)
        assert event.reasoning is None

    def test_event_response_from_orm_with_reasoning(self):
        """Test EventResponse can be created from ORM model with reasoning attribute."""

        # Simulate ORM model with attributes including reasoning
        class MockEventWithReasoning:
            id = 1
            camera_id = "123e4567-e89b-12d3-a456-426614174000"
            started_at = datetime(2025, 12, 23, 12, 0, 0)
            ended_at = datetime(2025, 12, 23, 12, 2, 30)
            risk_score = 75
            risk_level = "medium"
            summary = "Person detected near front entrance"
            reasoning = "LLM explanation for risk score"
            reviewed = False
            notes = None
            detection_count = 5

        event = EventResponse.model_validate(MockEventWithReasoning())
        assert event.reasoning == "LLM explanation for risk score"


class TestEventUpdateSchema:
    """Tests for EventUpdate schema validation."""

    def test_event_update_valid(self):
        """Test EventUpdate with valid data."""
        data = {"reviewed": True}
        update = EventUpdate(**data)
        assert update.reviewed is True

    def test_event_update_false(self):
        """Test EventUpdate can set reviewed to False."""
        data = {"reviewed": False}
        update = EventUpdate(**data)
        assert update.reviewed is False

    def test_event_update_empty_payload_valid(self):
        """Test EventUpdate accepts empty payload (all fields optional for partial updates)."""
        data = {}
        update = EventUpdate(**data)
        assert update.reviewed is None
        assert update.notes is None

    def test_event_update_with_notes(self):
        """Test EventUpdate with notes field."""
        data = {"notes": "This is a test note"}
        update = EventUpdate(**data)
        assert update.notes == "This is a test note"
        assert update.reviewed is None

    def test_event_update_with_reviewed_and_notes(self):
        """Test EventUpdate with both reviewed and notes fields."""
        data = {"reviewed": True, "notes": "Verified as false alarm"}
        update = EventUpdate(**data)
        assert update.reviewed is True
        assert update.notes == "Verified as false alarm"

    def test_event_update_notes_none(self):
        """Test EventUpdate can set notes to None."""
        data = {"notes": None}
        update = EventUpdate(**data)
        assert update.notes is None

    def test_event_update_notes_long_text(self):
        """Test EventUpdate accepts long notes text."""
        long_text = "A" * 5000
        data = {"notes": long_text}
        update = EventUpdate(**data)
        assert update.notes == long_text
        assert len(update.notes) == 5000

    def test_event_update_invalid_type(self):
        """Test EventUpdate raises ValidationError with invalid field type."""
        data = {"reviewed": "not_a_boolean"}
        with pytest.raises(ValidationError) as exc_info:
            EventUpdate(**data)
        assert "reviewed" in str(exc_info.value)

    def test_event_update_extra_fields_ignored(self):
        """Test EventUpdate ignores extra fields by default."""
        data = {"reviewed": True, "extra_field": "should_be_ignored"}
        update = EventUpdate(**data)
        assert update.reviewed is True
        assert not hasattr(update, "extra_field")


class TestEventListResponseSchema:
    """Tests for EventListResponse schema validation."""

    def test_event_list_response_valid(self):
        """Test EventListResponse with valid data."""
        data = {
            "items": [
                {
                    "id": 1,
                    "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                    "started_at": datetime(2025, 12, 23, 12, 0, 0),
                    "ended_at": datetime(2025, 12, 23, 12, 2, 30),
                    "risk_score": 75,
                    "risk_level": "medium",
                    "summary": "Person detected near front entrance",
                    "reviewed": False,
                    "detection_count": 5,
                }
            ],
            "pagination": {
                "total": 1,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        }
        response = EventListResponse(**data)
        assert len(response.items) == 1
        assert response.pagination.total == 1
        assert response.pagination.limit == 50
        assert response.pagination.offset == 0

    def test_event_list_response_empty(self):
        """Test EventListResponse with empty events list."""
        data = {
            "items": [],
            "pagination": {
                "total": 0,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        }
        response = EventListResponse(**data)
        assert response.items == []
        assert response.pagination.total == 0

    def test_event_list_response_multiple_events(self):
        """Test EventListResponse with multiple events."""
        data = {
            "items": [
                {
                    "id": 1,
                    "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                    "started_at": datetime(2025, 12, 23, 12, 0, 0),
                    "ended_at": None,
                    "risk_score": None,
                    "risk_level": None,
                    "summary": None,
                    "reviewed": False,
                    "detection_count": 0,
                },
                {
                    "id": 2,
                    "camera_id": "223e4567-e89b-12d3-a456-426614174001",
                    "started_at": datetime(2025, 12, 23, 13, 0, 0),
                    "ended_at": datetime(2025, 12, 23, 13, 3, 0),
                    "risk_score": 90,
                    "risk_level": "high",
                    "summary": "Vehicle detected at night",
                    "reviewed": True,
                    "detection_count": 8,
                },
            ],
            "pagination": {
                "total": 2,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        }
        response = EventListResponse(**data)
        assert len(response.items) == 2
        assert response.pagination.total == 2
        assert response.items[0].id == 1
        assert response.items[1].id == 2

    def test_event_list_response_missing_required_field(self):
        """Test EventListResponse raises ValidationError when required field is missing."""
        data = {
            "items": [],
            # Missing 'pagination'
        }
        with pytest.raises(ValidationError) as exc_info:
            EventListResponse(**data)
        assert "pagination" in str(exc_info.value) or "items" in str(exc_info.value)

    def test_event_list_response_invalid_event(self):
        """Test EventListResponse raises ValidationError with invalid event in list."""
        data = {
            "items": [
                {
                    "id": 1,
                    # Missing required fields like camera_id, started_at
                }
            ],
            "pagination": {
                "total": 1,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        }
        with pytest.raises(ValidationError):
            EventListResponse(**data)

    def test_event_list_response_pagination(self):
        """Test EventListResponse with pagination parameters."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 10,
                "offset": 20,
                "has_more": True,
            },
        }
        response = EventListResponse(**data)
        assert response.pagination.total == 100
        assert response.pagination.limit == 10
        assert response.pagination.offset == 20
