"""Integration tests for AI pipeline quality metrics service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.models.event import Event
from backend.services.ai_quality_metrics import (
    AIQualityAnalyzer,
    MetricResult,
    QualityLevel,
)


class TestAIQualityAnalyzer:
    """Integration tests for AIQualityAnalyzer service."""

    @pytest.mark.asyncio
    async def test_analyzer_handles_empty_database(self, session: AsyncSession) -> None:
        """Test that analyzer handles empty database gracefully."""
        analyzer = AIQualityAnalyzer(session)
        results = await analyzer.analyze_recent_events(hours=24)

        # Should return results even with no events
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_analyzer_with_events(self, session: AsyncSession) -> None:
        """Test analyzer correctly analyzes events from database."""
        # Create test camera
        camera = Camera(
            name="test_camera",
            rtsp_url="rtsp://test",
            enabled=True,
        )
        session.add(camera)
        await session.flush()

        # Create test events with different risk levels
        for risk_score in [10, 30, 50, 70, 90]:
            event = Event(
                camera_id=camera.id,
                risk_score=risk_score,
                risk_level="low" if risk_score < 40 else "medium" if risk_score < 70 else "high",
                summary=f"Test event with risk {risk_score}",
                reasoning="Test reasoning for quality analysis",
            )
            session.add(event)
        await session.commit()

        analyzer = AIQualityAnalyzer(session)
        results = await analyzer.analyze_recent_events(hours=24)

        # Should analyze the events
        assert isinstance(results, list)
        # Results should be MetricResult instances
        for result in results:
            assert isinstance(result, MetricResult)
            assert result.name
            assert result.level in QualityLevel

    @pytest.mark.asyncio
    async def test_field_completeness_check(self, session: AsyncSession) -> None:
        """Test that field completeness check works with real data."""
        # Create camera and event with all fields populated
        camera = Camera(
            name="complete_camera",
            rtsp_url="rtsp://complete",
            enabled=True,
        )
        session.add(camera)
        await session.flush()

        event = Event(
            camera_id=camera.id,
            risk_score=45,
            risk_level="medium",
            summary="Complete test event summary",
            reasoning="Detailed reasoning explaining why this event was flagged",
        )
        session.add(event)
        await session.commit()

        analyzer = AIQualityAnalyzer(session)
        results = await analyzer.check_field_completeness()

        assert isinstance(results, list)
        # At least some completeness metrics should be returned
        if results:
            assert all(isinstance(r, MetricResult) for r in results)
