"""Integration tests for AI pipeline quality metrics service.

Aligned to the SHIPPED contract (ledger R-T9-AIQUALITY): AIQualityAnalyzer
exposes collect_all_metrics() -> QualityReport and per-facet collectors
(collect_field_completeness, collect_risk_distribution, ...) that return
dataclass metrics objects — there is no analyze_recent_events() and
check_field_completeness() does not return a list of MetricResult
(ai_quality_metrics.py:179/200).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.models.event import Event
from backend.models.llm_interaction import LLMInteraction
from backend.services.ai_quality_metrics import (
    AIQualityAnalyzer,
    FieldCompletenessMetrics,
    MetricResult,
    QualityLevel,
    QualityReport,
)


class TestAIQualityAnalyzer:
    """Integration tests for AIQualityAnalyzer service."""

    @pytest.mark.asyncio
    async def test_analyzer_handles_empty_database(self, session: AsyncSession) -> None:
        """Test that analyzer handles empty database gracefully."""
        analyzer = AIQualityAnalyzer(session)
        report = await analyzer.collect_all_metrics()

        # Should return a report even with no events
        assert isinstance(report, QualityReport)
        assert report.field_completeness.total_records == 0
        assert isinstance(report.results, list)

    @pytest.mark.asyncio
    async def test_analyzer_with_events(self, session: AsyncSession) -> None:
        """Test analyzer correctly analyzes events from database."""
        # Create test camera
        camera = Camera(
            id=str(uuid.uuid4()),
            name="test_camera",
            folder_path="/test/ai_quality",
        )
        session.add(camera)
        await session.flush()

        # Create test events with different risk levels
        for risk_score in [10, 30, 50, 70, 90]:
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=risk_score,
                risk_level="low" if risk_score < 40 else "medium" if risk_score < 70 else "high",
                summary=f"Test event with risk {risk_score}",
                reasoning="Test reasoning for quality analysis",
            )
            session.add(event)
        await session.commit()

        analyzer = AIQualityAnalyzer(session)
        report = await analyzer.collect_all_metrics()

        assert isinstance(report, QualityReport)
        assert report.risk_distribution.total_events >= 5
        # Evaluated metrics are MetricResult instances on the report
        assert isinstance(report.results, list)
        for result in report.results:
            assert isinstance(result, MetricResult)
            assert result.name
            assert result.level in QualityLevel

    @pytest.mark.asyncio
    async def test_field_completeness_check(self, session: AsyncSession) -> None:
        """Test that field completeness collection works with real data.

        Shipped return type is the FieldCompletenessMetrics dataclass
        (ai_quality_metrics.py:200), not a list of MetricResult — and it
        counts LLMInteraction rows (ai_quality_metrics.py:202-210), so the
        fixture must seed one; an Event alone leaves total_records at 0
        (wave I-3 'assert 0 >= 1'). (ledger R-T9-AIQUALITY)
        """
        # Create camera and event with all fields populated
        camera = Camera(
            id=str(uuid.uuid4()),
            name="complete_camera",
            folder_path="/test/ai_quality_complete",
        )
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=camera.id,
            started_at=datetime.now(UTC),
            risk_score=45,
            risk_level="medium",
            summary="Complete test event summary",
            reasoning="Detailed reasoning explaining why this event was flagged",
        )
        session.add(event)
        await session.flush()

        # collect_field_completeness aggregates llm_interactions columns —
        # seed the interaction the completeness rates are measured on.
        interaction = LLMInteraction(
            event_id=event.id,
            raw_response='{"risk_score": 45}',
            enrichment_snapshot={"objects": ["person"]},
            household_matches=None,
            context_sources={"zones": []},
        )
        session.add(interaction)
        await session.commit()

        analyzer = AIQualityAnalyzer(session)
        metrics = await analyzer.collect_field_completeness()

        assert isinstance(metrics, FieldCompletenessMetrics)
        assert metrics.total_records >= 1
        assert metrics.raw_response_rate == 1.0
        assert metrics.enrichment_snapshot_rate == 1.0
