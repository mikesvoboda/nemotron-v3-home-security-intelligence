"""Unit tests for events API schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.events import EventListResponse, EventResponse, EventUpdate


class TestEventResponseSchema:
    """Tests for EventResponse schema validation."""

    def test_event_response_valid(self):
        """Test EventResponse with valid data."""
        data = {
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
        event = EventResponse(**data)
        assert event.id == 1
        assert event.camera_id == "123e4567-e89b-12d3-a456-426614174000"
        assert event.risk_score == 75
        assert event.risk_level == "medium"
        assert event.summary == "Person detected near front entrance"
        assert event.reviewed is False
        assert event.detection_count == 5

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
            detection_count = 5

        event = EventResponse.model_validate(MockEvent())
        assert event.id == 1
        assert event.camera_id == "123e4567-e89b-12d3-a456-426614174000"
        assert event.risk_score == 75


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
            "events": [
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
            "count": 1,
            "limit": 50,
            "offset": 0,
        }
        response = EventListResponse(**data)
        assert len(response.events) == 1
        assert response.count == 1
        assert response.limit == 50
        assert response.offset == 0

    def test_event_list_response_empty(self):
        """Test EventListResponse with empty events list."""
        data = {
            "events": [],
            "count": 0,
            "limit": 50,
            "offset": 0,
        }
        response = EventListResponse(**data)
        assert response.events == []
        assert response.count == 0

    def test_event_list_response_multiple_events(self):
        """Test EventListResponse with multiple events."""
        data = {
            "events": [
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
            "count": 2,
            "limit": 50,
            "offset": 0,
        }
        response = EventListResponse(**data)
        assert len(response.events) == 2
        assert response.count == 2
        assert response.events[0].id == 1
        assert response.events[1].id == 2

    def test_event_list_response_missing_required_field(self):
        """Test EventListResponse raises ValidationError when required field is missing."""
        data = {
            "events": [],
            "count": 0,
            # Missing 'limit' and 'offset'
        }
        with pytest.raises(ValidationError) as exc_info:
            EventListResponse(**data)
        assert "limit" in str(exc_info.value) or "offset" in str(exc_info.value)

    def test_event_list_response_invalid_event(self):
        """Test EventListResponse raises ValidationError with invalid event in list."""
        data = {
            "events": [
                {
                    "id": 1,
                    # Missing required fields like camera_id, started_at
                }
            ],
            "count": 1,
            "limit": 50,
            "offset": 0,
        }
        with pytest.raises(ValidationError):
            EventListResponse(**data)

    def test_event_list_response_pagination(self):
        """Test EventListResponse with pagination parameters."""
        data = {
            "events": [],
            "count": 100,
            "limit": 10,
            "offset": 20,
        }
        response = EventListResponse(**data)
        assert response.count == 100
        assert response.limit == 10
        assert response.offset == 20
