"""Summary Detail Service for generating detailed summary views with export support.

This service provides functionality for:
- Building timeline views of events from a summary
- Generating detailed summary data for the expandable detail panel
- Exporting summary data in various formats (JSON, CSV, PDF)

Related Linear issues: NEM-5425, NEM-5426, NEM-5427
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.models.event import Event
    from backend.models.summary import Summary

logger = get_logger(__name__)


@dataclass
class TimelineEvent:
    """Represents an event in the summary timeline.

    Provides a simplified view of an event for display in the
    expandable detail panel's timeline section.
    """

    event_id: int
    timestamp: datetime
    camera_name: str
    summary: str | None
    risk_score: int | None
    risk_level: str | None
    event_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response or export."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "camera_name": self.camera_name,
            "summary": self.summary or "",
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "event_url": self.event_url,
        }


@dataclass
class SummaryDetailData:
    """Complete detail data for a summary.

    Contains all information needed for the expandable detail panel,
    including the full narrative, timeline of events, and export options.
    """

    id: int
    summary_type: str
    content: str
    event_count: int
    window_start: datetime
    window_end: datetime
    generated_at: datetime
    timeline: list[TimelineEvent] = field(default_factory=list)
    export_formats: list[str] = field(default_factory=lambda: ["json", "csv", "pdf"])
    focus_areas: list[str] = field(default_factory=list)
    dominant_patterns: list[str] = field(default_factory=list)
    max_risk_score: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "summary_type": self.summary_type,
            "content": self.content,
            "event_count": self.event_count,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "timeline": [e.to_dict() for e in self.timeline],
            "export_formats": self.export_formats,
            "focus_areas": self.focus_areas,
            "dominant_patterns": self.dominant_patterns,
            "max_risk_score": self.max_risk_score,
        }


class SummaryDetailService:
    """Service for generating detailed summary views with export support.

    This service provides methods for:
    - Building timeline views from events
    - Generating complete detail data for the expandable panel
    - Exporting summary data in JSON, CSV, and PDF formats
    """

    def build_timeline(self, events: Sequence[Event]) -> list[TimelineEvent]:
        """Build a timeline of events for the detail panel.

        Converts Event model instances to TimelineEvent data objects,
        sorted chronologically by timestamp.

        Args:
            events: Sequence of Event objects to convert

        Returns:
            List of TimelineEvent objects sorted by timestamp (earliest first)
        """
        if not events:
            return []

        timeline_events: list[TimelineEvent] = []

        for event in events:
            # Get camera name, falling back to camera_id if relationship not loaded
            camera_name = event.camera_id
            if event.camera is not None:
                camera_name = event.camera.name

            timeline_event = TimelineEvent(
                event_id=event.id,
                timestamp=event.started_at,
                camera_name=camera_name,
                summary=event.summary,
                risk_score=event.risk_score,
                risk_level=event.risk_level,
                event_url=f"/events/{event.id}",
            )
            timeline_events.append(timeline_event)

        # Sort by timestamp (earliest first)
        timeline_events.sort(key=lambda e: e.timestamp)

        return timeline_events

    def generate_detail(
        self,
        summary: Summary,
        events: Sequence[Event],
        focus_areas: list[str] | None = None,
        dominant_patterns: list[str] | None = None,
        max_risk_score: int | None = None,
    ) -> SummaryDetailData:
        """Generate complete detail data for a summary.

        Combines summary data with event timeline and metadata
        for display in the expandable detail panel.

        Args:
            summary: The Summary model instance
            events: Sequence of related Event objects
            focus_areas: Optional list of focus areas (e.g., camera names)
            dominant_patterns: Optional list of dominant patterns detected
            max_risk_score: Optional maximum risk score from events

        Returns:
            SummaryDetailData object with all detail information
        """
        timeline = self.build_timeline(events)

        # Calculate max risk score from events if not provided
        if max_risk_score is None and events:
            scores = [e.risk_score for e in events if e.risk_score is not None]
            if scores:
                max_risk_score = max(scores)

        # Extract focus areas from events if not provided
        if focus_areas is None:
            focus_areas = []
            seen_cameras = set()
            for event in events:
                camera_name = event.camera.name if event.camera else event.camera_id
                if camera_name and camera_name not in seen_cameras:
                    focus_areas.append(camera_name)
                    seen_cameras.add(camera_name)

        return SummaryDetailData(
            id=summary.id,
            summary_type=summary.summary_type,
            content=summary.content,
            event_count=summary.event_count,
            window_start=summary.window_start,
            window_end=summary.window_end,
            generated_at=summary.generated_at,
            timeline=timeline,
            export_formats=["json", "csv", "pdf"],
            focus_areas=focus_areas or [],
            dominant_patterns=dominant_patterns or [],
            max_risk_score=max_risk_score,
        )


# Singleton instance
_detail_service: SummaryDetailService | None = None


def get_summary_detail_service() -> SummaryDetailService:
    """Get the singleton SummaryDetailService instance.

    Returns:
        The shared SummaryDetailService instance
    """
    global _detail_service  # noqa: PLW0603
    if _detail_service is None:
        _detail_service = SummaryDetailService()
    return _detail_service
