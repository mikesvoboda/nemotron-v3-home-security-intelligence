"""Unit tests for computed_field with cached_property in Pydantic schemas.

This module tests the computed field implementation for risk_level derived from risk_score.
The computed field pattern reduces data redundancy and eliminates inconsistency between
risk_score and risk_level fields.

NEM-3398: Use computed_field with cached_property for derived fields.
"""

from backend.api.schemas.events import EventResponse
from backend.api.schemas.search import SearchResult


class TestEventResponseComputedRiskLevel:
    """Tests for EventResponse.risk_level as a computed field from risk_score."""

    def test_risk_level_computed_from_low_score(self):
        """Test risk_level is computed as 'low' for scores 0-29."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=15,
        )
        assert event.risk_level == "low"

    def test_risk_level_computed_from_medium_score(self):
        """Test risk_level is computed as 'medium' for scores 30-59."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=45,
        )
        assert event.risk_level == "medium"

    def test_risk_level_computed_from_high_score(self):
        """Test risk_level is computed as 'high' for scores 60-84."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=75,
        )
        assert event.risk_level == "high"

    def test_risk_level_computed_from_critical_score(self):
        """Test risk_level is computed as 'critical' for scores 85-100."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=95,
        )
        assert event.risk_level == "critical"

    def test_risk_level_none_when_score_is_none(self):
        """Test risk_level is None when risk_score is None."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=None,
        )
        assert event.risk_level is None

    def test_risk_level_boundary_low_to_medium(self):
        """Test boundary at 29 (low) and 30 (medium)."""
        event_low = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=29,
        )
        assert event_low.risk_level == "low"

        event_medium = EventResponse(
            id=2,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=30,
        )
        assert event_medium.risk_level == "medium"

    def test_risk_level_boundary_medium_to_high(self):
        """Test boundary at 59 (medium) and 60 (high)."""
        event_medium = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=59,
        )
        assert event_medium.risk_level == "medium"

        event_high = EventResponse(
            id=2,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=60,
        )
        assert event_high.risk_level == "high"

    def test_risk_level_boundary_high_to_critical(self):
        """Test boundary at 84 (high) and 85 (critical)."""
        event_high = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=84,
        )
        assert event_high.risk_level == "high"

        event_critical = EventResponse(
            id=2,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=85,
        )
        assert event_critical.risk_level == "critical"

    def test_risk_level_extreme_values(self):
        """Test risk_level with extreme scores (0 and 100)."""
        event_zero = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=0,
        )
        assert event_zero.risk_level == "low"

        event_hundred = EventResponse(
            id=2,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=100,
        )
        assert event_hundred.risk_level == "critical"

    def test_risk_level_serialization_in_json(self):
        """Test that computed risk_level is included in JSON serialization."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=75,
        )
        json_data = event.model_dump()
        assert "risk_level" in json_data
        assert json_data["risk_level"] == "high"

    def test_risk_level_serialization_mode_json(self):
        """Test that computed risk_level is included in mode='json' serialization."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=45,
        )
        json_data = event.model_dump(mode="json")
        assert "risk_level" in json_data
        assert json_data["risk_level"] == "medium"

    def test_risk_level_cached_property(self):
        """Test that risk_level computation is cached (multiple accesses return same value)."""
        event = EventResponse(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=50,
        )
        # Access multiple times - should return same value
        level1 = event.risk_level
        level2 = event.risk_level
        level3 = event.risk_level
        assert level1 == level2 == level3 == "medium"


class TestSearchResultComputedRiskLevel:
    """Tests for SearchResult.risk_level as a computed field from risk_score."""

    def test_risk_level_computed_from_score(self):
        """Test risk_level is computed from risk_score in SearchResult."""
        result = SearchResult(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=75,
            relevance_score=0.85,
        )
        assert result.risk_level == "high"

    def test_risk_level_none_when_score_is_none(self):
        """Test risk_level is None when risk_score is None."""
        result = SearchResult(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=None,
            relevance_score=0.5,
        )
        assert result.risk_level is None

    def test_risk_level_all_levels(self):
        """Test all risk levels in SearchResult."""
        # Low
        result_low = SearchResult(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=20,
            relevance_score=0.5,
        )
        assert result_low.risk_level == "low"

        # Medium
        result_medium = SearchResult(
            id=2,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=50,
            relevance_score=0.5,
        )
        assert result_medium.risk_level == "medium"

        # High
        result_high = SearchResult(
            id=3,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=70,
            relevance_score=0.5,
        )
        assert result_high.risk_level == "high"

        # Critical
        result_critical = SearchResult(
            id=4,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=90,
            relevance_score=0.5,
        )
        assert result_critical.risk_level == "critical"

    def test_risk_level_serialization(self):
        """Test that computed risk_level is included in JSON serialization."""
        result = SearchResult(
            id=1,
            camera_id="front_door",
            started_at="2026-01-01T00:00:00Z",
            risk_score=60,
            relevance_score=0.5,
        )
        json_data = result.model_dump()
        assert "risk_level" in json_data
        assert json_data["risk_level"] == "high"


class TestComputedFieldsWithORMModel:
    """Tests for computed fields working with ORM model serialization."""

    def test_event_response_from_attributes(self):
        """Test EventResponse can be created from ORM model attributes.

        When using from_attributes=True (ORM mode), the computed field
        should still work correctly.
        """

        # Simulate ORM model attributes using a simple namespace-like object
        class MockEvent:
            def __init__(self):
                self.id = 1
                self.camera_id = "front_door"
                self.started_at = "2026-01-01T00:00:00Z"
                self.ended_at = None
                self.risk_score = 65
                self.summary = "Test summary"
                self.reasoning = "Test reasoning"
                self.llm_prompt = None
                self.reviewed = False
                self.notes = None
                self.snooze_until = None
                self.detection_count = 0
                self.detection_ids: list[int] = []
                self.thumbnail_url = None
                self.enrichment_status = None
                self.deleted_at = None

        # Need to instantiate the mock class for from_attributes to work
        event = EventResponse.model_validate(MockEvent())
        # risk_level should be computed from risk_score
        assert event.risk_level == "high"
        assert event.risk_score == 65
