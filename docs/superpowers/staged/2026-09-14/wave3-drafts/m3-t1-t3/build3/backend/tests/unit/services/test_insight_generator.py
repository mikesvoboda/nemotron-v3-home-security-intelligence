"""Unit tests for InsightGenerator service.

Tests cover:
- Generating camera-focused insights
- Generating entity-focused insights
- Generating trend-focused insights
- Priority sorting of insights
- Edge cases (no events, partial data)

Related Linear issues: NEM-5418, NEM-5419, NEM-5420, NEM-5421
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.services.insight_generator import (
    Insight,
    InsightGenerator,
    InsightType,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture
def mock_event() -> MagicMock:
    """Create a mock Event object with typical values."""
    event = MagicMock()
    event.id = 1
    event.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)
    event.camera_id = "front_door"
    event.camera = MagicMock()
    event.camera.name = "Front Door"
    event.risk_level = "high"
    event.risk_score = 75
    event.summary = "Unrecognized person approached the front door"
    event.object_types = "person"
    event.entities = [{"type": "person", "recognized": False}]
    return event


@pytest.fixture
def mock_critical_event() -> MagicMock:
    """Create a mock critical Event object."""
    event = MagicMock()
    event.id = 2
    event.started_at = datetime(2026, 1, 18, 14, 30, 0, tzinfo=UTC)
    event.camera_id = "driveway"
    event.camera = MagicMock()
    event.camera.name = "Driveway"
    event.risk_level = "critical"
    event.risk_score = 90
    event.summary = "Vehicle and person detected at unusual hour"
    event.object_types = "person, vehicle"
    event.entities = [{"type": "person", "recognized": False}, {"type": "vehicle"}]
    return event


@pytest.fixture
def mock_known_person_event() -> MagicMock:
    """Create a mock event with a known person."""
    event = MagicMock()
    event.id = 3
    event.started_at = datetime(2026, 1, 18, 12, 0, 0, tzinfo=UTC)
    event.camera_id = "backyard"
    event.camera = MagicMock()
    event.camera.name = "Backyard"
    event.risk_level = "low"
    event.risk_score = 15
    event.summary = "Family member detected"
    event.object_types = "person"
    event.entities = [{"type": "person", "recognized": True, "name": "John"}]
    return event


@pytest.fixture
def insight_generator() -> InsightGenerator:
    """Create an InsightGenerator instance."""
    return InsightGenerator()


# Tests: Insight Data Model


class TestInsightDataModel:
    """Tests for the Insight data model."""

    def test_insight_creation(self) -> None:
        """Test creating an Insight with all fields."""
        insight = Insight(
            type=InsightType.CAMERA,
            priority=8,
            title="High Activity Camera",
            description="Review 5 events from Front Door",
            action_url="/timeline?camera_id=front_door",
        )

        assert insight.type == InsightType.CAMERA
        assert insight.priority == 8
        assert insight.title == "High Activity Camera"
        assert insight.description == "Review 5 events from Front Door"
        assert insight.action_url == "/timeline?camera_id=front_door"

    def test_insight_without_action_url(self) -> None:
        """Test creating an Insight without an action URL."""
        insight = Insight(
            type=InsightType.TREND,
            priority=5,
            title="Activity Trend",
            description="Activity is 20% below baseline",
        )

        assert insight.action_url is None

    def test_insight_type_enum(self) -> None:
        """Test InsightType enum values."""
        assert InsightType.CAMERA.value == "camera"
        assert InsightType.ENTITY.value == "entity"
        assert InsightType.TREND.value == "trend"


# Tests: Camera-Focused Insights


class TestCameraInsights:
    """Tests for camera-focused insight generation."""

    def test_generate_camera_insight_single_camera(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test generating insight for a single camera with events."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events)

        camera_insights = [i for i in insights if i.type == InsightType.CAMERA]
        assert len(camera_insights) >= 1
        assert "Front Door" in camera_insights[0].description

    def test_generate_camera_insight_multiple_cameras(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test generating insights for multiple cameras."""
        events = [mock_event, mock_critical_event]

        insights = insight_generator.generate_insights(events)

        camera_insights = [i for i in insights if i.type == InsightType.CAMERA]
        # Should have insights for cameras with significant activity
        assert len(camera_insights) >= 1

    def test_camera_insight_includes_event_count(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test that camera insights include event counts."""
        # Create multiple events for same camera
        event2 = MagicMock()
        event2.id = 10
        event2.camera_id = "front_door"
        event2.camera = MagicMock()
        event2.camera.name = "Front Door"
        event2.risk_level = "high"
        event2.risk_score = 70
        event2.object_types = "person"
        event2.entities = []
        event2.started_at = datetime(2026, 1, 18, 14, 20, 0, tzinfo=UTC)

        events = [mock_event, event2]

        insights = insight_generator.generate_insights(events)

        camera_insights = [i for i in insights if i.type == InsightType.CAMERA]
        assert len(camera_insights) >= 1
        # Should mention the count
        assert (
            "2" in camera_insights[0].description
            or "events" in camera_insights[0].description.lower()
        )

    def test_camera_insight_action_url(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test that camera insights have correct action URLs."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events)

        camera_insights = [i for i in insights if i.type == InsightType.CAMERA]
        assert len(camera_insights) >= 1
        assert camera_insights[0].action_url is not None
        assert (
            "camera" in camera_insights[0].action_url
            or "front_door" in camera_insights[0].action_url
        )


# Tests: Entity-Focused Insights


class TestEntityInsights:
    """Tests for entity-focused insight generation."""

    def test_generate_unknown_person_insight(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test generating insight for unknown persons detected."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events)

        entity_insights = [i for i in insights if i.type == InsightType.ENTITY]
        # Should have an insight about unknown person
        unknown_person_insights = [
            i
            for i in entity_insights
            if "unknown" in i.title.lower() or "unrecognized" in i.title.lower()
        ]
        assert len(unknown_person_insights) >= 1

    def test_unknown_person_high_priority(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test that unknown person insights have high priority."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events)

        entity_insights = [i for i in insights if i.type == InsightType.ENTITY]
        unknown_person_insights = [
            i
            for i in entity_insights
            if "unknown" in i.title.lower() or "unrecognized" in i.title.lower()
        ]
        assert len(unknown_person_insights) >= 1
        # Unknown persons should be high priority (8-10)
        assert unknown_person_insights[0].priority >= 8

    def test_known_person_lower_priority(
        self,
        insight_generator: InsightGenerator,
        mock_known_person_event: MagicMock,
    ) -> None:
        """Test that known person insights have lower priority."""
        events = [mock_known_person_event]

        insights = insight_generator.generate_insights(events)

        # Known persons should have lower priority or not generate entity insights
        entity_insights = [i for i in insights if i.type == InsightType.ENTITY]
        if entity_insights:
            known_person_insights = [
                i
                for i in entity_insights
                if "known" in i.title.lower() or "recognized" in i.title.lower()
            ]
            if known_person_insights:
                assert known_person_insights[0].priority < 8

    def test_multiple_unknown_persons_count(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test that multiple unknown persons are counted correctly."""
        events = [mock_event, mock_critical_event]

        insights = insight_generator.generate_insights(events)

        entity_insights = [i for i in insights if i.type == InsightType.ENTITY]
        unknown_person_insights = [
            i
            for i in entity_insights
            if "unknown" in i.title.lower() or "unrecognized" in i.title.lower()
        ]
        assert len(unknown_person_insights) >= 1
        # Should mention count of unknown persons
        description = unknown_person_insights[0].description.lower()
        assert "2" in description or "multiple" in description or "persons" in description


# Tests: Trend-Focused Insights


class TestTrendInsights:
    """Tests for trend-focused insight generation."""

    def test_generate_activity_trend_insight(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test generating activity trend insights."""
        events = [mock_event, mock_critical_event]

        # Set a baseline for comparison
        baseline_count = 1  # Lower than current activity

        insights = insight_generator.generate_insights(events, baseline_event_count=baseline_count)

        trend_insights = [i for i in insights if i.type == InsightType.TREND]
        # Should have a trend insight about activity increase
        if len(events) > baseline_count:
            assert len(trend_insights) >= 1

    def test_activity_above_baseline(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test insight when activity is above baseline."""
        events = [mock_event, mock_critical_event]
        baseline_count = 1

        insights = insight_generator.generate_insights(events, baseline_event_count=baseline_count)

        trend_insights = [i for i in insights if i.type == InsightType.TREND]
        above_baseline = [
            i
            for i in trend_insights
            if "above" in i.description.lower() or "increase" in i.description.lower()
        ]
        assert len(above_baseline) >= 1

    def test_activity_below_baseline(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test insight when activity is below baseline."""
        events = [mock_event]
        baseline_count = 5  # Higher than current activity

        insights = insight_generator.generate_insights(events, baseline_event_count=baseline_count)

        trend_insights = [i for i in insights if i.type == InsightType.TREND]
        # Below baseline might generate a "quiet period" insight or no trend insight
        # Either behavior is acceptable
        if trend_insights:
            description = trend_insights[0].description.lower()
            assert "below" in description or "quiet" in description or "decrease" in description

    def test_trend_insight_percentage(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test that trend insights include percentage when significant."""
        events = [mock_event, mock_critical_event]
        baseline_count = 1  # 100% increase

        insights = insight_generator.generate_insights(events, baseline_event_count=baseline_count)

        trend_insights = [i for i in insights if i.type == InsightType.TREND]
        if trend_insights:
            # Should include percentage in description
            description = trend_insights[0].description
            assert "%" in description or "above" in description.lower()


# Tests: Priority Sorting


class TestPrioritySorting:
    """Tests for insight priority sorting."""

    def test_insights_sorted_by_priority(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test that insights are sorted by priority (highest first)."""
        events = [mock_event, mock_critical_event]

        insights = insight_generator.generate_insights(events)

        if len(insights) > 1:
            for i in range(len(insights) - 1):
                assert insights[i].priority >= insights[i + 1].priority

    def test_unknown_person_highest_priority(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test that unknown person insights are highest priority."""
        events = [mock_event, mock_critical_event]

        insights = insight_generator.generate_insights(events)

        if insights:
            # First insight should be entity-related (unknown person) based on priority rules
            # Priority order: Unknown persons > Unusual trends > Camera activity > Known entities
            first_insight = insights[0]
            assert first_insight.priority >= 8

    def test_limit_insights_returned(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test that insights are limited to top N."""
        events = [mock_event, mock_critical_event]

        insights = insight_generator.generate_insights(events, max_insights=3)

        assert len(insights) <= 3


# Tests: Edge Cases


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_no_events(
        self,
        insight_generator: InsightGenerator,
    ) -> None:
        """Test generating insights with no events."""
        events: list = []

        insights = insight_generator.generate_insights(events)

        # Should return empty list or a "no activity" insight
        assert len(insights) <= 1
        if insights:
            assert "no" in insights[0].title.lower() or "quiet" in insights[0].title.lower()

    def test_events_without_entities(
        self,
        insight_generator: InsightGenerator,
    ) -> None:
        """Test handling events without entity data."""
        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.camera = MagicMock()
        event.camera.name = "Front Door"
        event.risk_level = "medium"
        event.risk_score = 50
        event.object_types = "person"
        event.entities = None  # No entity data
        event.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)

        insights = insight_generator.generate_insights([event])

        # Should still generate camera insights
        assert any(i.type == InsightType.CAMERA for i in insights)

    def test_event_with_empty_entities(
        self,
        insight_generator: InsightGenerator,
    ) -> None:
        """Test handling events with empty entity list."""
        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.camera = MagicMock()
        event.camera.name = "Front Door"
        event.risk_level = "medium"
        event.risk_score = 50
        event.object_types = "person"
        event.entities = []  # Empty entity list
        event.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)

        insights = insight_generator.generate_insights([event])

        # Should not crash, may generate camera insight
        assert isinstance(insights, list)

    def test_event_without_camera_relationship(
        self,
        insight_generator: InsightGenerator,
    ) -> None:
        """Test handling events without camera relationship loaded."""
        event = MagicMock()
        event.id = 1
        event.camera_id = "unknown_camera"
        event.camera = None  # Camera relationship not loaded
        event.risk_level = "high"
        event.risk_score = 75
        event.object_types = "person"
        event.entities = [{"type": "person", "recognized": False}]
        event.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)

        insights = insight_generator.generate_insights([event])

        # Should use camera_id as fallback
        assert isinstance(insights, list)
        if insights:
            # Camera insight should use camera_id if camera.name not available
            camera_insights = [i for i in insights if i.type == InsightType.CAMERA]
            if camera_insights:
                assert (
                    "unknown_camera" in camera_insights[0].description
                    or "camera" in camera_insights[0].description.lower()
                )

    def test_baseline_zero(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test handling baseline of zero (avoid division by zero)."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events, baseline_event_count=0)

        # Should not crash, may generate trend insight about new activity
        assert isinstance(insights, list)

    def test_negative_baseline(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test handling negative baseline (should be treated as zero)."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events, baseline_event_count=-1)

        # Should not crash
        assert isinstance(insights, list)


# Tests: Integration with Summary


class TestInsightGeneratorIntegration:
    """Tests for integration with summary generation."""

    def test_generate_insights_returns_list(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test that generate_insights returns a list."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events)

        assert isinstance(insights, list)
        for insight in insights:
            assert isinstance(insight, Insight)

    def test_insights_to_dict(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
    ) -> None:
        """Test converting insights to dictionary format for API response."""
        events = [mock_event]

        insights = insight_generator.generate_insights(events)

        if insights:
            insight_dict = insights[0].to_dict()
            assert "type" in insight_dict
            assert "priority" in insight_dict
            assert "title" in insight_dict
            assert "description" in insight_dict
            assert "action_url" in insight_dict

    def test_max_insights_default(
        self,
        insight_generator: InsightGenerator,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test default max_insights limit."""
        events = [mock_event, mock_critical_event]

        insights = insight_generator.generate_insights(events)

        # Default should be 5
        assert len(insights) <= 5
