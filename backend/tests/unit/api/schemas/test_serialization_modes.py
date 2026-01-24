"""Unit tests for response serialization modes (NEM-3432).

Tests for model_dump_list() and model_dump_detail() methods that optimize
response payload sizes by excluding large fields from list views.

Following TDD: Tests written FIRST before implementation.
"""

from datetime import UTC, datetime

import pytest

from backend.api.schemas.detections import DetectionResponse
from backend.api.schemas.events import EnrichmentStatusEnum, EnrichmentStatusResponse, EventResponse


class TestEventResponseSerializationModes:
    """Tests for EventResponse serialization modes."""

    @pytest.fixture
    def sample_event_response(self) -> EventResponse:
        """Create a sample EventResponse with all fields populated."""
        return EventResponse(
            id=1,
            camera_id="front_door",
            started_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            ended_at=datetime(2026, 1, 15, 12, 5, 0, tzinfo=UTC),
            risk_score=75,
            risk_level="medium",
            summary="Person detected near front entrance",
            reasoning="Person approaching entrance during daytime, no suspicious behavior",
            llm_prompt="<|im_start|>system\nYou are a home security risk analyzer...",
            reviewed=False,
            notes="Test note",
            snooze_until=None,
            detection_count=5,
            detection_ids=[1, 2, 3, 4, 5],
            thumbnail_url="/api/detections/1/image",
            enrichment_status=EnrichmentStatusResponse(
                status=EnrichmentStatusEnum.FULL,
                successful_models=["violence", "weather", "face", "clothing"],
                failed_models=[],
                errors={},
                success_rate=1.0,
            ),
            deleted_at=None,
        )

    def test_model_dump_list_excludes_large_fields(self, sample_event_response: EventResponse):
        """Test that model_dump_list excludes llm_prompt and reasoning."""
        result = sample_event_response.model_dump_list()

        # Should NOT include large detail-only fields
        assert "llm_prompt" not in result
        assert "reasoning" not in result

        # Should include essential list view fields
        assert result["id"] == 1
        assert result["camera_id"] == "front_door"
        assert result["risk_score"] == 75
        # risk_level is computed from risk_score (75 = high per severity taxonomy)
        assert result["risk_level"] == "high"
        assert result["summary"] == "Person detected near front entrance"
        assert result["reviewed"] is False
        assert result["detection_count"] == 5

    def test_model_dump_list_excludes_none_values(self, sample_event_response: EventResponse):
        """Test that model_dump_list excludes None values."""
        sample_event_response.snooze_until = None
        sample_event_response.deleted_at = None

        result = sample_event_response.model_dump_list()

        # None values should be excluded
        assert "snooze_until" not in result
        assert "deleted_at" not in result

    def test_model_dump_list_includes_essential_fields(self, sample_event_response: EventResponse):
        """Test that model_dump_list includes all essential list view fields."""
        result = sample_event_response.model_dump_list()

        # Essential fields for list views
        expected_fields = {
            "id",
            "camera_id",
            "started_at",
            "ended_at",
            "risk_score",
            "risk_level",
            "summary",
            "reviewed",
            "notes",
            "detection_count",
            "detection_ids",
            "thumbnail_url",
            "enrichment_status",
        }

        # All essential fields should be present (except None ones)
        for field in expected_fields:
            value = getattr(sample_event_response, field)
            if value is not None:
                assert field in result, f"Field '{field}' should be in list serialization"

    def test_model_dump_detail_includes_all_fields(self, sample_event_response: EventResponse):
        """Test that model_dump_detail includes all fields including large ones."""
        result = sample_event_response.model_dump_detail()

        # Should include ALL fields including large detail-only fields
        assert "llm_prompt" in result
        assert "reasoning" in result
        assert result["llm_prompt"] == sample_event_response.llm_prompt
        assert result["reasoning"] == sample_event_response.reasoning

        # Should also include all other fields
        assert result["id"] == 1
        assert result["summary"] == "Person detected near front entrance"
        assert result["risk_score"] == 75

    def test_model_dump_detail_excludes_none_values(self, sample_event_response: EventResponse):
        """Test that model_dump_detail excludes None values."""
        sample_event_response.snooze_until = None

        result = sample_event_response.model_dump_detail()

        assert "snooze_until" not in result

    def test_model_dump_list_returns_dict(self, sample_event_response: EventResponse):
        """Test that model_dump_list returns a dict."""
        result = sample_event_response.model_dump_list()
        assert isinstance(result, dict)

    def test_model_dump_detail_returns_dict(self, sample_event_response: EventResponse):
        """Test that model_dump_detail returns a dict."""
        result = sample_event_response.model_dump_detail()
        assert isinstance(result, dict)

    def test_model_dump_list_smaller_than_detail(self, sample_event_response: EventResponse):
        """Test that list serialization produces smaller payload than detail."""
        list_result = sample_event_response.model_dump_list()
        detail_result = sample_event_response.model_dump_detail()

        # List result should have fewer fields
        assert len(list_result) < len(detail_result)

    def test_model_dump_list_with_minimal_event(self):
        """Test model_dump_list with minimal required fields."""
        minimal_event = EventResponse(
            id=1,
            camera_id="test_camera",
            started_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        result = minimal_event.model_dump_list()

        assert result["id"] == 1
        assert result["camera_id"] == "test_camera"
        assert "llm_prompt" not in result
        assert "reasoning" not in result


class TestDetectionResponseSerializationModes:
    """Tests for DetectionResponse serialization modes."""

    @pytest.fixture
    def sample_detection_response(self) -> DetectionResponse:
        """Create a sample DetectionResponse with all fields populated."""
        return DetectionResponse(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/20251223_120000.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            thumbnail_path="/data/thumbnails/1_thumb.jpg",
            media_type="image",
            duration=None,
            video_codec=None,
            video_width=None,
            video_height=None,
            enrichment_data={
                "vehicle": {"vehicle_type": "sedan", "vehicle_color": "blue"},
                "person": {"clothing_description": "dark jacket", "action": "walking"},
                "errors": [],
            },
        )

    def test_model_dump_list_excludes_large_fields(
        self, sample_detection_response: DetectionResponse
    ):
        """Test that model_dump_list excludes enrichment_data."""
        result = sample_detection_response.model_dump_list()

        # Should NOT include large detail-only fields
        assert "enrichment_data" not in result

        # Should include essential list view fields
        assert result["id"] == 1
        assert result["camera_id"] == "front_door"
        assert result["object_type"] == "person"
        assert result["confidence"] == 0.95

    def test_model_dump_list_excludes_none_values(
        self, sample_detection_response: DetectionResponse
    ):
        """Test that model_dump_list excludes None values."""
        sample_detection_response.duration = None
        sample_detection_response.video_codec = None

        result = sample_detection_response.model_dump_list()

        # None values should be excluded
        assert "duration" not in result
        assert "video_codec" not in result

    def test_model_dump_list_includes_essential_fields(
        self, sample_detection_response: DetectionResponse
    ):
        """Test that model_dump_list includes all essential list view fields."""
        result = sample_detection_response.model_dump_list()

        # Essential fields for list views
        expected_fields = {
            "id",
            "camera_id",
            "file_path",
            "file_type",
            "detected_at",
            "object_type",
            "confidence",
            "bbox_x",
            "bbox_y",
            "bbox_width",
            "bbox_height",
            "thumbnail_path",
            "media_type",
        }

        # All essential fields should be present (except None ones)
        for field in expected_fields:
            value = getattr(sample_detection_response, field)
            if value is not None:
                assert field in result, f"Field '{field}' should be in list serialization"

    def test_model_dump_detail_includes_all_fields(
        self, sample_detection_response: DetectionResponse
    ):
        """Test that model_dump_detail includes all fields including large ones."""
        result = sample_detection_response.model_dump_detail()

        # Should include ALL fields including large detail-only fields
        assert "enrichment_data" in result
        assert result["enrichment_data"] is not None

        # Should also include all other fields
        assert result["id"] == 1
        assert result["object_type"] == "person"
        assert result["confidence"] == 0.95

    def test_model_dump_detail_excludes_none_values(
        self, sample_detection_response: DetectionResponse
    ):
        """Test that model_dump_detail excludes None values."""
        sample_detection_response.duration = None

        result = sample_detection_response.model_dump_detail()

        assert "duration" not in result

    def test_model_dump_list_returns_dict(self, sample_detection_response: DetectionResponse):
        """Test that model_dump_list returns a dict."""
        result = sample_detection_response.model_dump_list()
        assert isinstance(result, dict)

    def test_model_dump_detail_returns_dict(self, sample_detection_response: DetectionResponse):
        """Test that model_dump_detail returns a dict."""
        result = sample_detection_response.model_dump_detail()
        assert isinstance(result, dict)

    def test_model_dump_list_smaller_than_detail(
        self, sample_detection_response: DetectionResponse
    ):
        """Test that list serialization produces smaller payload than detail."""
        list_result = sample_detection_response.model_dump_list()
        detail_result = sample_detection_response.model_dump_detail()

        # List result should have fewer fields (enrichment_data excluded)
        assert len(list_result) < len(detail_result)

    def test_model_dump_list_with_minimal_detection(self):
        """Test model_dump_list with minimal required fields."""
        minimal_detection = DetectionResponse(
            id=1,
            camera_id="test_camera",
            file_path="/path/to/file.jpg",
            detected_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        result = minimal_detection.model_dump_list()

        assert result["id"] == 1
        assert result["camera_id"] == "test_camera"
        assert "enrichment_data" not in result


class TestSerializationModesPayloadSize:
    """Tests verifying payload size reduction from serialization modes."""

    def test_event_list_serialization_reduces_payload(self):
        """Test that event list serialization provides significant size reduction."""
        # Create event with realistic large fields
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            ended_at=datetime(2026, 1, 15, 12, 5, 0, tzinfo=UTC),
            risk_score=75,
            summary="Person detected near front entrance",
            reasoning="A" * 500,  # Simulate 500 char reasoning
            llm_prompt="B" * 1000,  # Simulate 1000 char prompt
            reviewed=False,
            detection_count=5,
            detection_ids=[1, 2, 3, 4, 5],
            thumbnail_url="/api/detections/1/image",
        )

        import json

        # Use model_dump with mode='json' to serialize datetimes properly
        list_json = json.dumps(
            event.model_dump(mode="json", exclude={"llm_prompt", "reasoning"}, exclude_none=True)
        )
        detail_json = json.dumps(event.model_dump(mode="json", exclude_none=True))

        # List serialization should be significantly smaller
        # (at least 30% smaller based on task requirements)
        size_reduction = 1 - (len(list_json) / len(detail_json))
        assert size_reduction >= 0.30, f"Expected 30%+ reduction, got {size_reduction:.1%}"

    def test_detection_list_serialization_reduces_payload(self):
        """Test that detection list serialization provides size reduction."""
        # Create detection with realistic large enrichment_data
        detection = DetectionResponse(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/20251223_120000.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            thumbnail_path="/data/thumbnails/1_thumb.jpg",
            media_type="image",
            enrichment_data={
                "vehicle": {
                    "vehicle_type": "sedan",
                    "vehicle_color": "blue",
                    "has_damage": False,
                    "is_commercial": False,
                },
                "person": {
                    "clothing_description": "dark jacket, blue jeans",
                    "action": "walking",
                    "carrying": ["backpack", "phone"],
                    "is_suspicious": False,
                },
                "pet": None,
                "weather": "sunny",
                "errors": [],
                "extra_data": {"key": "value" * 100},  # Simulate additional data
            },
        )

        import json

        # Use model_dump with mode='json' to serialize datetimes properly
        list_json = json.dumps(
            detection.model_dump(mode="json", exclude={"enrichment_data"}, exclude_none=True)
        )
        detail_json = json.dumps(detection.model_dump(mode="json", exclude_none=True))

        # List serialization should be smaller
        assert len(list_json) < len(detail_json)
