"""Insight generator service for actionable insights.

This service generates rule-based actionable insights from security events.
Insights are categorized into three types:
- Camera: Activity on specific cameras that need attention
- Entity: Unknown persons or notable entities detected
- Trend: Activity patterns compared to baseline

Insights are prioritized by urgency:
- Priority 10: Unknown persons detected (highest)
- Priority 8-9: Unusual activity trends
- Priority 6-7: High camera activity
- Priority 4-5: Known entities
- Priority 1-3: Informational (lowest)

Related Linear issues: NEM-5418, NEM-5419, NEM-5420, NEM-5421

Example:
    from backend.services.insight_generator import InsightGenerator

    generator = InsightGenerator()
    insights = generator.generate_insights(events, baseline_event_count=5)
    for insight in insights:
        print(f"{insight.title}: {insight.description}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.models.event import Event

__all__ = [
    "Insight",
    "InsightGenerator",
    "InsightType",
    "get_insight_generator",
]

logger = get_logger(__name__)


class InsightType(str, Enum):
    """Types of actionable insights.

    Attributes:
        CAMERA: Camera-focused insight (activity on specific camera)
        ENTITY: Entity-focused insight (unknown persons, notable entities)
        TREND: Trend-focused insight (activity patterns vs baseline)
    """

    CAMERA = "camera"
    ENTITY = "entity"
    TREND = "trend"


@dataclass
class Insight:
    """An actionable insight generated from event analysis.

    Attributes:
        type: The category of insight (camera, entity, or trend)
        priority: Urgency level 1-10 (10 = highest priority)
        title: Short title for the insight
        description: Detailed description with actionable information
        action_url: Optional URL to view related events/data
    """

    type: InsightType
    priority: int
    title: str
    description: str
    action_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert insight to dictionary for API response.

        Returns:
            Dictionary with type, priority, title, description, action_url keys.
        """
        return {
            "type": self.type.value,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "action_url": self.action_url,
        }


@dataclass
class _CameraStats:
    """Statistics for a single camera."""

    camera_id: str
    camera_name: str
    event_count: int = 0
    high_critical_count: int = 0
    max_risk_score: int = 0


@dataclass
class _EntityStats:
    """Statistics for entity detection."""

    unknown_persons: int = 0
    known_persons: int = 0
    vehicles: int = 0
    unknown_person_cameras: list[str] = field(default_factory=list)


class InsightGenerator:
    """Generates actionable insights from security events.

    This service analyzes events and generates prioritized insights
    that help users understand what needs attention.

    Insight Priority Rules (highest to lowest):
    1. Unknown persons detected (priority 9-10)
    2. Unusual activity trends (priority 7-8)
    3. High camera activity (priority 5-6)
    4. Known entities detected (priority 3-4)

    Example:
        generator = InsightGenerator()
        insights = generator.generate_insights(events)
        top_insight = insights[0] if insights else None
    """

    # Priority thresholds
    PRIORITY_UNKNOWN_PERSON = 10
    PRIORITY_TREND_HIGH = 8
    PRIORITY_TREND_LOW = 6
    PRIORITY_CAMERA_HIGH = 6
    PRIORITY_CAMERA_MEDIUM = 5
    PRIORITY_KNOWN_ENTITY = 4
    PRIORITY_QUIET_PERIOD = 3

    # Thresholds for insight generation
    TREND_SIGNIFICANT_INCREASE_PCT = 50  # 50% increase is significant
    TREND_SIGNIFICANT_DECREASE_PCT = 30  # 30% decrease is notable
    MIN_EVENTS_FOR_CAMERA_INSIGHT = 1  # Minimum events to generate camera insight

    def __init__(self) -> None:
        """Initialize the InsightGenerator."""
        pass

    def generate_insights(
        self,
        events: Sequence[Event],
        *,
        baseline_event_count: int | None = None,
        max_insights: int = 5,
    ) -> list[Insight]:
        """Generate actionable insights from events.

        Analyzes the provided events and generates prioritized insights
        based on camera activity, entity detection, and activity trends.

        Args:
            events: Sequence of Event objects to analyze
            baseline_event_count: Optional baseline event count for trend comparison.
                If not provided, trend insights will not be generated.
            max_insights: Maximum number of insights to return (default 5)

        Returns:
            List of Insight objects sorted by priority (highest first)

        Example:
            insights = generator.generate_insights(events, baseline_event_count=10)
            for insight in insights:
                print(f"[{insight.priority}] {insight.title}")
        """
        if not events:
            return self._generate_no_activity_insight()

        all_insights: list[Insight] = []

        # Gather statistics
        camera_stats = self._gather_camera_stats(events)
        entity_stats = self._gather_entity_stats(events)

        # Generate insights by category
        all_insights.extend(self._generate_entity_insights(entity_stats))
        all_insights.extend(self._generate_trend_insights(len(events), baseline_event_count))
        all_insights.extend(self._generate_camera_insights(camera_stats))

        # Sort by priority (highest first) and limit
        all_insights.sort(key=lambda i: i.priority, reverse=True)

        return all_insights[:max_insights]

    def _generate_no_activity_insight(self) -> list[Insight]:
        """Generate insight for when there are no events.

        Returns:
            List with a single quiet period insight or empty list
        """
        return [
            Insight(
                type=InsightType.TREND,
                priority=self.PRIORITY_QUIET_PERIOD,
                title="No Recent Activity",
                description="No high-priority events detected in this period. The property has been quiet.",
                action_url=None,
            )
        ]

    def _gather_camera_stats(self, events: Sequence[Event]) -> dict[str, _CameraStats]:
        """Gather statistics by camera from events.

        Args:
            events: Sequence of events to analyze

        Returns:
            Dictionary mapping camera_id to CameraStats
        """
        stats: dict[str, _CameraStats] = {}

        for event in events:
            camera_id = event.camera_id
            camera_name = camera_id
            if hasattr(event, "camera") and event.camera is not None:
                camera_name = event.camera.name or camera_id

            if camera_id not in stats:
                stats[camera_id] = _CameraStats(
                    camera_id=camera_id,
                    camera_name=camera_name,
                )

            stats[camera_id].event_count += 1

            risk_level = getattr(event, "risk_level", None)
            if risk_level in ("high", "critical"):
                stats[camera_id].high_critical_count += 1

            risk_score = getattr(event, "risk_score", None) or 0
            stats[camera_id].max_risk_score = max(stats[camera_id].max_risk_score, risk_score)

        return stats

    def _gather_entity_stats(self, events: Sequence[Event]) -> _EntityStats:
        """Gather entity statistics from events.

        Args:
            events: Sequence of events to analyze

        Returns:
            EntityStats with counts of different entity types
        """
        stats = _EntityStats()

        for event in events:
            entities = getattr(event, "entities", None)
            if not entities:
                continue

            camera_name = event.camera_id
            if hasattr(event, "camera") and event.camera is not None:
                camera_name = event.camera.name or event.camera_id

            for entity in entities:
                if not isinstance(entity, dict):
                    continue

                entity_type = entity.get("type", "").lower()

                if entity_type == "person":
                    is_recognized = entity.get("recognized", False)
                    if is_recognized:
                        stats.known_persons += 1
                    else:
                        stats.unknown_persons += 1
                        if camera_name not in stats.unknown_person_cameras:
                            stats.unknown_person_cameras.append(camera_name)
                elif entity_type == "vehicle":
                    stats.vehicles += 1

        return stats

    def _generate_entity_insights(self, stats: _EntityStats) -> list[Insight]:
        """Generate entity-focused insights.

        Args:
            stats: Entity statistics

        Returns:
            List of entity-related insights
        """
        insights: list[Insight] = []

        # Unknown persons - highest priority
        if stats.unknown_persons > 0:
            if stats.unknown_persons == 1:
                description = "1 unknown person detected"
            else:
                description = f"{stats.unknown_persons} unknown persons detected"

            if stats.unknown_person_cameras:
                cameras = ", ".join(stats.unknown_person_cameras[:3])
                description += f" at {cameras}"
                if len(stats.unknown_person_cameras) > 3:
                    description += f" and {len(stats.unknown_person_cameras) - 3} more"

            insights.append(
                Insight(
                    type=InsightType.ENTITY,
                    priority=self.PRIORITY_UNKNOWN_PERSON,
                    title="Unknown Persons Detected",
                    description=description,
                    action_url="/timeline?entity_type=person&recognized=false",
                )
            )

        # Known persons - lower priority
        if stats.known_persons > 0:
            if stats.known_persons == 1:
                description = "1 recognized person detected"
            else:
                description = f"{stats.known_persons} recognized persons detected"

            insights.append(
                Insight(
                    type=InsightType.ENTITY,
                    priority=self.PRIORITY_KNOWN_ENTITY,
                    title="Known Persons Activity",
                    description=description,
                    action_url="/timeline?entity_type=person&recognized=true",
                )
            )

        return insights

    def _generate_trend_insights(
        self,
        current_count: int,
        baseline_count: int | None,
    ) -> list[Insight]:
        """Generate trend-focused insights.

        Args:
            current_count: Current number of events
            baseline_count: Baseline event count for comparison

        Returns:
            List of trend-related insights
        """
        insights: list[Insight] = []

        if baseline_count is None:
            return insights

        # Handle edge cases
        if baseline_count <= 0:
            if current_count > 0:
                insights.append(
                    Insight(
                        type=InsightType.TREND,
                        priority=self.PRIORITY_TREND_HIGH,
                        title="New Activity Detected",
                        description=f"{current_count} events detected where none were expected",
                        action_url="/timeline",
                    )
                )
            return insights

        # Calculate percentage change
        pct_change = ((current_count - baseline_count) / baseline_count) * 100

        if pct_change >= self.TREND_SIGNIFICANT_INCREASE_PCT:
            insights.append(
                Insight(
                    type=InsightType.TREND,
                    priority=self.PRIORITY_TREND_HIGH,
                    title="Activity Above Baseline",
                    description=f"Activity is {int(pct_change)}% above baseline ({current_count} vs {baseline_count} events)",
                    action_url="/analytics",
                )
            )
        elif pct_change <= -self.TREND_SIGNIFICANT_DECREASE_PCT:
            insights.append(
                Insight(
                    type=InsightType.TREND,
                    priority=self.PRIORITY_TREND_LOW,
                    title="Quiet Period",
                    description=f"Activity is {int(abs(pct_change))}% below baseline ({current_count} vs {baseline_count} events)",
                    action_url="/analytics",
                )
            )

        return insights

    def _generate_camera_insights(self, camera_stats: dict[str, _CameraStats]) -> list[Insight]:
        """Generate camera-focused insights.

        Args:
            camera_stats: Dictionary of camera statistics

        Returns:
            List of camera-related insights
        """
        insights: list[Insight] = []

        # Sort cameras by event count (descending)
        sorted_cameras = sorted(
            camera_stats.values(),
            key=lambda s: (s.high_critical_count, s.event_count),
            reverse=True,
        )

        for stats in sorted_cameras[:3]:  # Top 3 cameras
            if stats.event_count < self.MIN_EVENTS_FOR_CAMERA_INSIGHT:
                continue

            # Determine priority based on high/critical count
            if stats.high_critical_count > 0:
                priority = self.PRIORITY_CAMERA_HIGH
            else:
                priority = self.PRIORITY_CAMERA_MEDIUM

            # Build description
            if stats.event_count == 1:
                description = f"Review 1 event from {stats.camera_name}"
            else:
                description = f"Review {stats.event_count} events from {stats.camera_name}"

            if stats.high_critical_count > 0:
                description += f" ({stats.high_critical_count} high/critical)"

            insights.append(
                Insight(
                    type=InsightType.CAMERA,
                    priority=priority,
                    title="Camera Activity",
                    description=description,
                    action_url=f"/timeline?camera_id={stats.camera_id}",
                )
            )

        return insights


# Module-level singleton instance
_insight_generator: InsightGenerator | None = None


def get_insight_generator() -> InsightGenerator:
    """Get the singleton InsightGenerator instance.

    Returns:
        The global InsightGenerator instance.

    Example:
        generator = get_insight_generator()
        insights = generator.generate_insights(events)
    """
    global _insight_generator  # noqa: PLW0603
    if _insight_generator is None:
        _insight_generator = InsightGenerator()
    return _insight_generator
