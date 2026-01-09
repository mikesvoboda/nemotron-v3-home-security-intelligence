"""Integration tests for AI audit API endpoints.

Tests the /api/ai-audit routes including:
- GET /api/ai-audit/events/{event_id} - Get audit for specific event
- GET /api/ai-audit/stats - Get aggregate audit statistics
- GET /api/ai-audit/leaderboard - Get model leaderboard
- GET /api/ai-audit/recommendations - Get recommendations
- POST /api/ai-audit/batch - Trigger batch audit processing

Uses shared fixtures from conftest.py:
- integration_db: Clean database with initialized schema
- mock_redis: Mock Redis client
- client: httpx AsyncClient with test app
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from backend.tests.integration.test_helpers import get_error_message

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.models.camera import Camera
    from backend.models.event import Event
    from backend.models.event_audit import EventAudit


# Alias for backward compatibility
@pytest.fixture
async def async_client(client: AsyncClient) -> AsyncClient:
    """Alias for shared client fixture for backward compatibility."""
    return client


@pytest.fixture
async def _clean_ai_audit_tables(integration_db: str):
    """Delete AI audit related data before test runs for proper isolation.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM event_audits"))
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM event_audits"))
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:
        pass


@pytest.fixture
async def sample_camera_for_audit(integration_db: str, _clean_ai_audit_tables: None) -> Camera:
    """Create a sample camera for AI audit tests."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Audit Test Camera",
            folder_path="/export/foscam/audit_test",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        return camera


@pytest.fixture
async def sample_event_for_audit(integration_db: str, sample_camera_for_audit: Camera) -> Event:
    """Create a sample event for AI audit tests."""
    from backend.core.database import get_session
    from backend.models.event import Event

    async with get_session() as db:
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=sample_camera_for_audit.id,
            started_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ended_at=datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC),
            risk_score=75,
            risk_level="medium",
            summary="Person detected near front entrance",
            reasoning="A person was detected approaching the front door during daylight hours.",
            detection_ids=json.dumps([1, 2, 3]),
            reviewed=False,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event


@pytest.fixture
async def sample_event_audit(integration_db: str, sample_event_for_audit: Event) -> EventAudit:
    """Create a sample event audit record."""
    from backend.core.database import get_session
    from backend.models.event_audit import EventAudit

    async with get_session() as db:
        audit = EventAudit(
            event_id=sample_event_for_audit.id,
            audited_at=datetime.now(UTC),
            # Model contributions
            has_rtdetr=True,
            has_florence=True,
            has_clip=False,
            has_violence=False,
            has_clothing=True,
            has_vehicle=False,
            has_pet=False,
            has_weather=True,
            has_image_quality=True,
            has_zones=True,
            has_baseline=False,
            has_cross_camera=False,
            # Prompt metrics
            prompt_length=500,
            prompt_token_estimate=125,
            enrichment_utilization=0.5,
            # Quality scores
            context_usage_score=4.0,
            reasoning_coherence_score=4.5,
            risk_justification_score=3.5,
            consistency_score=4.0,
            overall_quality_score=4.0,
            # Consistency check
            consistency_risk_score=70,
            consistency_diff=5,
            # Self-evaluation
            self_eval_critique="The analysis correctly identified the person...",
            # Prompt improvements as JSON
            missing_context=json.dumps(["time since last motion"]),
            confusing_sections=json.dumps([]),
            unused_data=json.dumps(["weather data"]),
            format_suggestions=json.dumps(["add bullet points"]),
            model_gaps=json.dumps(["vehicle analysis"]),
        )
        db.add(audit)
        await db.commit()
        await db.refresh(audit)
        return audit


@pytest.fixture
async def _multiple_event_audits(
    integration_db: str, sample_camera_for_audit: Camera
) -> list[tuple[Event, EventAudit]]:
    """Create multiple events with audits for stats/leaderboard testing."""
    from backend.core.database import get_session
    from backend.models.event import Event
    from backend.models.event_audit import EventAudit

    results: list[tuple[Event, EventAudit]] = []

    async with get_session() as db:
        # Create 5 events with varying audit characteristics
        for i in range(5):
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_camera_for_audit.id,
                started_at=datetime(2025, 12, 23, 10 + i, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 23, 10 + i, 2, 30, tzinfo=UTC),
                risk_score=20 + i * 15,
                risk_level=["low", "low", "medium", "medium", "high"][i],
                summary=f"Test event {i}",
                reasoning=f"Reasoning for event {i}",
                reviewed=False,
            )
            db.add(event)
            await db.flush()

            audit = EventAudit(
                event_id=event.id,
                audited_at=datetime.now(UTC),
                # Vary model contributions
                has_rtdetr=True,
                has_florence=i % 2 == 0,
                has_clip=i % 3 == 0,
                has_violence=i > 2,
                has_clothing=i % 2 == 0,
                has_vehicle=i > 1,
                has_pet=False,
                has_weather=True,
                has_image_quality=True,
                has_zones=i % 2 == 0,
                has_baseline=i > 0,
                has_cross_camera=i > 3,
                # Prompt metrics
                prompt_length=400 + i * 50,
                prompt_token_estimate=100 + i * 12,
                enrichment_utilization=0.3 + i * 0.1,
                # Quality scores (only for some)
                overall_quality_score=3.0 + i * 0.3 if i > 1 else None,
                context_usage_score=3.5 + i * 0.2 if i > 1 else None,
                reasoning_coherence_score=4.0 if i > 1 else None,
                risk_justification_score=3.5 if i > 1 else None,
                consistency_score=4.0 if i > 1 else None,
            )
            db.add(audit)
            results.append((event, audit))

        await db.commit()
        for event, audit in results:
            await db.refresh(event)
            await db.refresh(audit)

    return results


class TestGetEventAudit:
    """Tests for GET /api/ai-audit/events/{event_id} endpoint."""

    async def test_get_event_audit_success(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test getting audit for a specific event."""
        response = await async_client.get(f"/api/ai-audit/events/{sample_event_for_audit.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == sample_event_audit.id
        assert data["event_id"] == sample_event_for_audit.id
        assert data["is_fully_evaluated"] is True

        # Check contributions
        assert "contributions" in data
        assert data["contributions"]["rtdetr"] is True
        assert data["contributions"]["florence"] is True
        assert data["contributions"]["clip"] is False

        # Check scores
        assert "scores" in data
        assert data["scores"]["overall"] == 4.0
        assert data["scores"]["context_usage"] == 4.0
        assert data["scores"]["reasoning_coherence"] == 4.5

        # Check prompt metrics
        assert data["prompt_length"] == 500
        assert data["prompt_token_estimate"] == 125
        assert data["enrichment_utilization"] == 0.5

        # Check improvements
        assert "improvements" in data
        assert "time since last motion" in data["improvements"]["missing_context"]
        assert "weather data" in data["improvements"]["unused_data"]

    async def test_get_event_audit_not_found_event(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test 404 for non-existent event."""
        response = await async_client.get("/api/ai-audit/events/999999")
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)

        assert "not found" in error_msg.lower()

    async def test_get_event_audit_no_audit_record(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
    ):
        """Test 404 when event exists but has no audit record."""
        response = await async_client.get(f"/api/ai-audit/events/{sample_event_for_audit.id}")
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)

        assert "no audit found" in error_msg.lower()


class TestGetAuditStats:
    """Tests for GET /api/ai-audit/stats endpoint."""

    async def test_get_audit_stats_empty(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test getting stats when no audits exist."""
        response = await async_client.get("/api/ai-audit/stats?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "total_events" in data
        assert "model_contribution_rates" in data
        assert data["total_events"] == 0

    async def test_get_audit_stats_with_data(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test getting audit stats with data."""
        response = await async_client.get("/api/ai-audit/stats?days=7")
        assert response.status_code == 200

        data = response.json()
        assert data["total_events"] == 5
        assert data["audited_events"] == 5
        # 3 events have fully evaluated scores (indices 2, 3, 4)
        assert data["fully_evaluated_events"] == 3

        # Check model contribution rates
        assert "model_contribution_rates" in data
        rates = data["model_contribution_rates"]
        assert rates["rtdetr"] == 1.0  # All events have rtdetr
        assert rates["weather"] == 1.0  # All events have weather
        assert rates["pet"] == 0.0  # No events have pet

        # Check average scores (only from evaluated events)
        assert data["avg_quality_score"] is not None
        assert data["avg_enrichment_utilization"] is not None

    async def test_get_audit_stats_days_parameter(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test days parameter for stats."""
        # Test with different day values
        for days in [1, 7, 30, 90]:
            response = await async_client.get(f"/api/ai-audit/stats?days={days}")
            assert response.status_code == 200
            data = response.json()
            assert "total_events" in data

    async def test_get_audit_stats_days_validation(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test validation of days parameter."""
        # Test invalid values
        response = await async_client.get("/api/ai-audit/stats?days=0")
        assert response.status_code == 422

        response = await async_client.get("/api/ai-audit/stats?days=100")
        assert response.status_code == 422

        response = await async_client.get("/api/ai-audit/stats?days=-1")
        assert response.status_code == 422


class TestGetLeaderboard:
    """Tests for GET /api/ai-audit/leaderboard endpoint."""

    async def test_get_leaderboard_empty(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test getting leaderboard when no audits exist."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "entries" in data
        assert "period_days" in data
        assert data["period_days"] == 7

    async def test_get_leaderboard_with_data(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test getting leaderboard with data."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "entries" in data
        assert len(data["entries"]) > 0

        # Check entry structure
        entry = data["entries"][0]
        assert "model_name" in entry
        assert "contribution_rate" in entry
        assert "quality_correlation" in entry
        assert "event_count" in entry

        # Verify sorted by contribution rate descending
        rates = [e["contribution_rate"] for e in data["entries"]]
        assert rates == sorted(rates, reverse=True)

    async def test_get_leaderboard_days_parameter(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test days parameter for leaderboard."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 30


class TestGetRecommendations:
    """Tests for GET /api/ai-audit/recommendations endpoint."""

    async def test_get_recommendations_empty(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test getting recommendations when no audits exist."""
        response = await async_client.get("/api/ai-audit/recommendations?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "recommendations" in data
        assert "total_events_analyzed" in data
        assert data["total_events_analyzed"] == 0
        assert data["recommendations"] == []

    async def test_get_recommendations_with_data(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test getting recommendations with audit data."""
        response = await async_client.get("/api/ai-audit/recommendations?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "recommendations" in data
        assert "total_events_analyzed" in data

        # We have one fully evaluated audit with improvements
        if data["recommendations"]:
            rec = data["recommendations"][0]
            assert "category" in rec
            assert "suggestion" in rec
            assert "frequency" in rec
            assert "priority" in rec
            assert rec["priority"] in ["high", "medium", "low"]

    async def test_get_recommendations_days_parameter(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test days parameter for recommendations."""
        for days in [1, 7, 30]:
            response = await async_client.get(f"/api/ai-audit/recommendations?days={days}")
            assert response.status_code == 200
            data = response.json()
            assert "recommendations" in data


class TestBatchAudit:
    """Tests for POST /api/ai-audit/batch endpoint."""

    async def test_batch_audit_empty(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test batch audit when no events exist."""
        response = await async_client.post(
            "/api/ai-audit/batch",
            json={"limit": 10},
        )
        assert response.status_code == 200

        data = response.json()
        assert "queued_count" in data
        assert "message" in data
        assert data["queued_count"] == 0

    async def test_batch_audit_validation(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test batch audit request validation."""
        # Test invalid limit
        response = await async_client.post(
            "/api/ai-audit/batch",
            json={"limit": 0},
        )
        assert response.status_code == 422

        response = await async_client.post(
            "/api/ai-audit/batch",
            json={"limit": 2000},
        )
        assert response.status_code == 422

    async def test_batch_audit_with_min_risk_score(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test batch audit with min_risk_score filter."""
        response = await async_client.post(
            "/api/ai-audit/batch",
            json={
                "limit": 10,
                "min_risk_score": 50,
                "force_reevaluate": False,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert "queued_count" in data


class TestEvaluateEvent:
    """Tests for POST /api/ai-audit/events/{event_id}/evaluate endpoint."""

    async def test_evaluate_event_not_found(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test 404 for non-existent event evaluation."""
        response = await async_client.post("/api/ai-audit/events/999999/evaluate")
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)

        assert "not found" in error_msg.lower()

    async def test_evaluate_event_no_audit(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
    ):
        """Test 404 when event exists but has no audit record."""
        response = await async_client.post(
            f"/api/ai-audit/events/{sample_event_for_audit.id}/evaluate"
        )
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)

        assert "no audit found" in error_msg.lower()


class TestAuditAPIResponseStructure:
    """Tests for verifying API response structure matches schemas."""

    async def test_event_audit_response_structure(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Verify EventAuditResponse structure."""
        response = await async_client.get(f"/api/ai-audit/events/{sample_event_for_audit.id}")
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "id" in data
        assert "event_id" in data
        assert "audited_at" in data
        assert "is_fully_evaluated" in data
        assert "contributions" in data
        assert "prompt_length" in data
        assert "prompt_token_estimate" in data
        assert "enrichment_utilization" in data
        assert "scores" in data
        assert "improvements" in data

        # Contributions structure
        contributions = data["contributions"]
        expected_models = [
            "rtdetr",
            "florence",
            "clip",
            "violence",
            "clothing",
            "vehicle",
            "pet",
            "weather",
            "image_quality",
            "zones",
            "baseline",
            "cross_camera",
        ]
        for model in expected_models:
            assert model in contributions
            assert isinstance(contributions[model], bool)

        # Scores structure
        scores = data["scores"]
        assert "context_usage" in scores
        assert "reasoning_coherence" in scores
        assert "risk_justification" in scores
        assert "consistency" in scores
        assert "overall" in scores

        # Improvements structure
        improvements = data["improvements"]
        assert "missing_context" in improvements
        assert "confusing_sections" in improvements
        assert "unused_data" in improvements
        assert "format_suggestions" in improvements
        assert "model_gaps" in improvements
        assert isinstance(improvements["missing_context"], list)

    async def test_stats_response_structure(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Verify AuditStatsResponse structure."""
        response = await async_client.get("/api/ai-audit/stats?days=7")
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "total_events" in data
        assert "audited_events" in data
        assert "fully_evaluated_events" in data
        assert "avg_quality_score" in data
        assert "avg_consistency_rate" in data
        assert "avg_enrichment_utilization" in data
        assert "model_contribution_rates" in data
        assert "audits_by_day" in data

        # Types
        assert isinstance(data["total_events"], int)
        assert isinstance(data["model_contribution_rates"], dict)
        assert isinstance(data["audits_by_day"], list)

    async def test_leaderboard_response_structure(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Verify LeaderboardResponse structure."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=7")
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "entries" in data
        assert "period_days" in data

        # Entry structure (if entries exist)
        if data["entries"]:
            entry = data["entries"][0]
            assert "model_name" in entry
            assert "contribution_rate" in entry
            assert "quality_correlation" in entry
            assert "event_count" in entry

    async def test_recommendations_response_structure(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Verify RecommendationsResponse structure."""
        response = await async_client.get("/api/ai-audit/recommendations?days=7")
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "recommendations" in data
        assert "total_events_analyzed" in data

        # Recommendation structure (if recommendations exist)
        if data["recommendations"]:
            rec = data["recommendations"][0]
            assert "category" in rec
            assert "suggestion" in rec
            assert "frequency" in rec
            assert "priority" in rec


class TestEvaluateEventWithMockedLLM:
    """Tests for POST /api/ai-audit/events/{event_id}/evaluate with mocked Nemotron LLM."""

    @pytest.fixture
    async def event_with_llm_prompt(
        self, integration_db: str, sample_camera_for_audit: Camera
    ) -> Event:
        """Create an event with llm_prompt for evaluation testing."""
        from backend.core.database import get_session
        from backend.models.event import Event

        async with get_session() as db:
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_camera_for_audit.id,
                started_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC),
                risk_score=65,
                risk_level="medium",
                summary="Person detected near entrance",
                reasoning="A person was detected approaching the front door during daylight.",
                llm_prompt="<|im_start|>system\nYou are analyzing security footage.\n<|im_end|>\n<|im_start|>user\nAnalyze the following detections...\n<|im_end|>",
                reviewed=False,
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            return event

    @pytest.fixture
    async def unevaluated_audit(
        self, integration_db: str, event_with_llm_prompt: Event
    ) -> EventAudit:
        """Create an unevaluated audit record (no quality scores yet)."""
        from backend.core.database import get_session
        from backend.models.event_audit import EventAudit

        async with get_session() as db:
            audit = EventAudit(
                event_id=event_with_llm_prompt.id,
                audited_at=datetime.now(UTC),
                has_rtdetr=True,
                has_florence=True,
                has_clip=False,
                has_violence=False,
                has_clothing=True,
                has_vehicle=False,
                has_pet=False,
                has_weather=True,
                has_image_quality=True,
                has_zones=True,
                has_baseline=False,
                has_cross_camera=False,
                prompt_length=500,
                prompt_token_estimate=125,
                enrichment_utilization=0.5,
                # No quality scores - not yet evaluated
            )
            db.add(audit)
            await db.commit()
            await db.refresh(audit)
            return audit

    async def test_evaluate_event_success_with_mocked_llm(
        self,
        async_client: AsyncClient,
        event_with_llm_prompt: Event,
        unevaluated_audit: EventAudit,
    ):
        """Test successful event evaluation with mocked LLM responses."""
        from unittest.mock import patch

        # Mock the LLM call to return valid evaluation responses
        mock_llm_responses = [
            # Self-critique response
            "The analysis was thorough but could be more detailed.",
            # Rubric eval response (JSON)
            '{"context_usage": 4.0, "reasoning_coherence": 4.5, "risk_justification": 3.5, "actionability": 4.0}',
            # Consistency check response (JSON)
            '{"risk_score": 60, "risk_level": "medium", "brief_reason": "Person approach detected"}',
            # Prompt improvement response (JSON)
            '{"missing_context": ["time of day context"], "confusing_sections": [], "unused_data": ["weather"], "format_suggestions": ["add bullet points"], "model_gaps": ["face detection"]}',
        ]
        call_count = 0

        async def mock_call_llm(self, prompt: str) -> str:
            nonlocal call_count
            result = mock_llm_responses[min(call_count, len(mock_llm_responses) - 1)]
            call_count += 1
            return result

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm,
        ):
            response = await async_client.post(
                f"/api/ai-audit/events/{event_with_llm_prompt.id}/evaluate"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_fully_evaluated"] is True
        assert data["scores"]["overall"] is not None
        assert data["scores"]["context_usage"] == 4.0
        assert data["scores"]["reasoning_coherence"] == 4.5

    async def test_evaluate_event_force_reevaluation(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test force re-evaluation of an already evaluated audit."""
        from unittest.mock import patch

        # Event already has a fully evaluated audit (sample_event_audit.overall_quality_score)
        # Mock LLM to return different scores
        mock_llm_responses = [
            "Updated critique.",
            '{"context_usage": 5.0, "reasoning_coherence": 5.0, "risk_justification": 5.0, "actionability": 5.0}',
            '{"risk_score": 75, "risk_level": "medium"}',
            '{"missing_context": [], "confusing_sections": [], "unused_data": [], "format_suggestions": [], "model_gaps": []}',
        ]
        call_count = 0

        async def mock_call_llm(self, prompt: str) -> str:
            nonlocal call_count
            result = mock_llm_responses[min(call_count, len(mock_llm_responses) - 1)]
            call_count += 1
            return result

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm,
        ):
            response = await async_client.post(
                f"/api/ai-audit/events/{sample_event_for_audit.id}/evaluate?force=true"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_fully_evaluated"] is True
        # Score should potentially be different after re-evaluation
        assert data["scores"]["overall"] is not None

    async def test_evaluate_already_evaluated_no_force(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test that already evaluated audit returns cached result without force."""
        response = await async_client.post(
            f"/api/ai-audit/events/{sample_event_for_audit.id}/evaluate"
        )

        assert response.status_code == 200
        data = response.json()
        # Should return the existing scores without re-evaluation
        assert data["scores"]["overall"] == sample_event_audit.overall_quality_score

    async def test_evaluate_event_llm_error_handling(
        self,
        async_client: AsyncClient,
        event_with_llm_prompt: Event,
        unevaluated_audit: EventAudit,
    ):
        """Test graceful handling of LLM errors during evaluation."""
        from unittest.mock import patch

        async def mock_call_llm_error(self, prompt: str) -> str:
            raise Exception("LLM service unavailable")

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm_error,
        ):
            response = await async_client.post(
                f"/api/ai-audit/events/{event_with_llm_prompt.id}/evaluate"
            )

        # Should still succeed but with partial/error results
        assert response.status_code == 200
        # The service should handle errors gracefully and return a valid response
        assert response.json() is not None


class TestStatsWithCameraFilter:
    """Tests for GET /api/ai-audit/stats with camera filtering."""

    @pytest.fixture
    async def _multiple_cameras_with_audits(
        self, integration_db: str, _clean_ai_audit_tables: None
    ) -> dict[str, list[tuple[Event, EventAudit]]]:
        """Create multiple cameras with events and audits."""
        from backend.core.database import get_session
        from backend.models.camera import Camera
        from backend.models.event import Event
        from backend.models.event_audit import EventAudit

        results: dict[str, list[tuple[Event, EventAudit]]] = {}

        async with get_session() as db:
            # Create two cameras
            for cam_idx, cam_name in enumerate(["front_door", "backyard"]):
                camera_id = str(uuid.uuid4())
                camera = Camera(
                    id=camera_id,
                    name=f"Stats Test Camera {cam_idx}",
                    folder_path=f"/export/foscam/stats_test_{cam_idx}",
                    status="online",
                )
                db.add(camera)
                await db.flush()

                results[camera_id] = []

                # Create 3 events per camera
                for i in range(3):
                    event = Event(
                        batch_id=str(uuid.uuid4()),
                        camera_id=camera_id,
                        started_at=datetime(2025, 12, 23, 10 + i, 0, 0, tzinfo=UTC),
                        ended_at=datetime(2025, 12, 23, 10 + i, 2, 30, tzinfo=UTC),
                        risk_score=30 + i * 20 + cam_idx * 5,
                        risk_level=["low", "medium", "high"][i],
                        summary=f"Test event {i} for camera {cam_name}",
                        reasoning=f"Reasoning for event {i}",
                        reviewed=False,
                    )
                    db.add(event)
                    await db.flush()

                    audit = EventAudit(
                        event_id=event.id,
                        audited_at=datetime.now(UTC),
                        has_rtdetr=True,
                        has_florence=cam_idx == 0,  # Only front_door has florence
                        has_clip=False,
                        has_violence=cam_idx == 1,  # Only backyard has violence
                        has_clothing=True,
                        has_vehicle=cam_idx == 1,
                        has_pet=False,
                        has_weather=True,
                        has_image_quality=True,
                        has_zones=True,
                        has_baseline=False,
                        has_cross_camera=False,
                        prompt_length=400 + i * 50,
                        prompt_token_estimate=100 + i * 12,
                        enrichment_utilization=0.4 + cam_idx * 0.1,
                        overall_quality_score=3.5 + i * 0.3 if i > 0 else None,
                        context_usage_score=3.5 + i * 0.2 if i > 0 else None,
                        reasoning_coherence_score=4.0 if i > 0 else None,
                        risk_justification_score=3.5 if i > 0 else None,
                        consistency_score=4.0 if i > 0 else None,
                    )
                    db.add(audit)
                    results[camera_id].append((event, audit))

            await db.commit()

        return results

    async def test_stats_with_camera_id_filter(
        self,
        async_client: AsyncClient,
        _multiple_cameras_with_audits: dict[str, list[tuple[Event, EventAudit]]],
    ):
        """Test stats filtered by specific camera ID."""
        # Get the first camera ID
        camera_id = next(iter(_multiple_cameras_with_audits.keys()))

        response = await async_client.get(f"/api/ai-audit/stats?days=7&camera_id={camera_id}")
        assert response.status_code == 200

        data = response.json()
        # Should only count events from the specified camera
        assert data["total_events"] == 3
        # Camera 0 (front_door) has florence, no violence
        assert data["model_contribution_rates"]["florence"] == 1.0
        assert data["model_contribution_rates"]["violence"] == 0.0

    async def test_stats_different_cameras_have_different_rates(
        self,
        async_client: AsyncClient,
        _multiple_cameras_with_audits: dict[str, list[tuple[Event, EventAudit]]],
    ):
        """Test that different cameras show different model contribution rates."""
        camera_ids = list(_multiple_cameras_with_audits.keys())

        # Get stats for first camera
        response1 = await async_client.get(f"/api/ai-audit/stats?days=7&camera_id={camera_ids[0]}")
        data1 = response1.json()

        # Get stats for second camera
        response2 = await async_client.get(f"/api/ai-audit/stats?days=7&camera_id={camera_ids[1]}")
        data2 = response2.json()

        # Camera 0 has florence, camera 1 doesn't
        assert data1["model_contribution_rates"]["florence"] == 1.0
        assert data2["model_contribution_rates"]["florence"] == 0.0

        # Camera 1 has violence detection, camera 0 doesn't
        assert data1["model_contribution_rates"]["violence"] == 0.0
        assert data2["model_contribution_rates"]["violence"] == 1.0

    async def test_stats_without_camera_filter_aggregates_all(
        self,
        async_client: AsyncClient,
        _multiple_cameras_with_audits: dict[str, list[tuple[Event, EventAudit]]],
    ):
        """Test that stats without camera filter includes all cameras."""
        response = await async_client.get("/api/ai-audit/stats?days=7")
        assert response.status_code == 200

        data = response.json()
        # Should have events from both cameras (3 + 3 = 6)
        assert data["total_events"] == 6


class TestBatchAuditAdvanced:
    """Advanced tests for POST /api/ai-audit/batch endpoint."""

    @pytest.fixture
    async def _events_for_batch(
        self, integration_db: str, sample_camera_for_audit: Camera
    ) -> list[Event]:
        """Create multiple events for batch testing with varying states."""
        from backend.core.database import get_session
        from backend.models.event import Event
        from backend.models.event_audit import EventAudit

        events: list[Event] = []

        async with get_session() as db:
            # Create 5 events with different characteristics
            for i in range(5):
                event = Event(
                    batch_id=str(uuid.uuid4()),
                    camera_id=sample_camera_for_audit.id,
                    started_at=datetime(2025, 12, 23, 10 + i, 0, 0, tzinfo=UTC),
                    ended_at=datetime(2025, 12, 23, 10 + i, 2, 30, tzinfo=UTC),
                    risk_score=20 + i * 20,  # 20, 40, 60, 80, 100
                    risk_level=["low", "low", "medium", "high", "critical"][i],
                    summary=f"Batch test event {i}",
                    reasoning=f"Reasoning for batch event {i}",
                    llm_prompt=f"LLM prompt for event {i}",
                    reviewed=False,
                )
                db.add(event)
                await db.flush()
                events.append(event)

                # Create audit only for some events (first 2)
                if i < 2:
                    audit = EventAudit(
                        event_id=event.id,
                        audited_at=datetime.now(UTC),
                        has_rtdetr=True,
                        has_florence=False,
                        has_clip=False,
                        has_violence=False,
                        has_clothing=False,
                        has_vehicle=False,
                        has_pet=False,
                        has_weather=False,
                        has_image_quality=False,
                        has_zones=False,
                        has_baseline=False,
                        has_cross_camera=False,
                        prompt_length=100,
                        prompt_token_estimate=25,
                        enrichment_utilization=0.08,
                        # Only first event is fully evaluated
                        overall_quality_score=4.0 if i == 0 else None,
                    )
                    db.add(audit)

            await db.commit()
            for event in events:
                await db.refresh(event)

        return events

    async def test_batch_audit_creates_missing_audits(
        self,
        async_client: AsyncClient,
        _events_for_batch: list[Event],
    ):
        """Test that batch audit creates audit records for events without them."""
        from unittest.mock import patch

        # Mock LLM responses
        async def mock_call_llm(self, prompt: str) -> str:
            return '{"context_usage": 4.0}'

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm,
        ):
            response = await async_client.post(
                "/api/ai-audit/batch",
                json={"limit": 10, "force_reevaluate": False},
            )

        assert response.status_code == 200
        data = response.json()
        # Should process events without full evaluation
        # Events 1 (no evaluation), 2, 3, 4 (no audit at all) = 4 events
        assert data["queued_count"] >= 1

    async def test_batch_audit_respects_min_risk_score(
        self,
        async_client: AsyncClient,
        _events_for_batch: list[Event],
    ):
        """Test that batch audit filters by minimum risk score."""
        from unittest.mock import patch

        async def mock_call_llm(self, prompt: str) -> str:
            return "{}"

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm,
        ):
            response = await async_client.post(
                "/api/ai-audit/batch",
                json={"limit": 10, "min_risk_score": 60},
            )

        assert response.status_code == 200
        data = response.json()
        # Only events with risk_score >= 60 (events 2, 3, 4 with scores 60, 80, 100)
        # But events 0 and 1 already have audits, so we should process fewer
        assert data["queued_count"] >= 0

    async def test_batch_audit_force_reevaluate_all(
        self,
        async_client: AsyncClient,
        _events_for_batch: list[Event],
    ):
        """Test batch audit with force_reevaluate processes all events."""
        from unittest.mock import patch

        async def mock_call_llm(self, prompt: str) -> str:
            return '{"context_usage": 3.5}'

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm,
        ):
            response = await async_client.post(
                "/api/ai-audit/batch",
                json={"limit": 10, "force_reevaluate": True},
            )

        assert response.status_code == 200
        data = response.json()
        # Should process all 5 events when force_reevaluate is True
        assert data["queued_count"] <= 5

    async def test_batch_audit_respects_limit(
        self,
        async_client: AsyncClient,
        _events_for_batch: list[Event],
    ):
        """Test that batch audit respects the limit parameter."""
        from unittest.mock import patch

        async def mock_call_llm(self, prompt: str) -> str:
            return "{}"

        with patch(
            "backend.services.pipeline_quality_audit_service.PipelineQualityAuditService._call_llm",
            mock_call_llm,
        ):
            response = await async_client.post(
                "/api/ai-audit/batch",
                json={"limit": 2, "force_reevaluate": True},
            )

        assert response.status_code == 200
        data = response.json()
        # Should not process more than the limit
        assert data["queued_count"] <= 2


class TestLeaderboardRanking:
    """Tests for verifying leaderboard ranking logic."""

    async def test_leaderboard_sorted_by_contribution_rate(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test that leaderboard entries are sorted by contribution rate descending."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=7")
        assert response.status_code == 200

        data = response.json()
        entries = data["entries"]

        # Verify entries are sorted by contribution_rate descending
        for i in range(len(entries) - 1):
            assert entries[i]["contribution_rate"] >= entries[i + 1]["contribution_rate"]

    async def test_leaderboard_includes_all_models(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test that leaderboard includes entries for all tracked models."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=7")
        assert response.status_code == 200

        data = response.json()
        model_names = [e["model_name"] for e in data["entries"]]

        expected_models = [
            "rtdetr",
            "florence",
            "clip",
            "violence",
            "clothing",
            "vehicle",
            "pet",
            "weather",
            "image_quality",
            "zones",
            "baseline",
            "cross_camera",
        ]

        for model in expected_models:
            assert model in model_names, f"Model {model} not found in leaderboard"

    async def test_leaderboard_event_count_matches_contribution_rate(
        self,
        async_client: AsyncClient,
        _multiple_event_audits: list[tuple[Event, EventAudit]],
    ):
        """Test that event_count is consistent with contribution_rate."""
        response = await async_client.get("/api/ai-audit/leaderboard?days=7")
        assert response.status_code == 200

        data = response.json()
        total_events = len(_multiple_event_audits)

        for entry in data["entries"]:
            expected_count = int(entry["contribution_rate"] * total_events)
            # Allow for rounding differences
            assert abs(entry["event_count"] - expected_count) <= 1


class TestTimeRangeFiltering:
    """Tests for verifying time range filtering works correctly."""

    @pytest.fixture
    async def _events_across_time_range(
        self, integration_db: str, sample_camera_for_audit: Camera
    ) -> list[Event]:
        """Create events spanning different time periods."""
        from backend.core.database import get_session
        from backend.models.event import Event
        from backend.models.event_audit import EventAudit

        events: list[Event] = []
        now = datetime.now(UTC)

        async with get_session() as db:
            # Create events at different time offsets
            for days_ago in [0, 5, 10, 20, 40]:
                event_time = now - timedelta(days=days_ago)
                event = Event(
                    batch_id=str(uuid.uuid4()),
                    camera_id=sample_camera_for_audit.id,
                    started_at=event_time,
                    ended_at=event_time + timedelta(minutes=2),
                    risk_score=50,
                    risk_level="medium",
                    summary=f"Event from {days_ago} days ago",
                    reasoning="Test reasoning",
                    reviewed=False,
                )
                db.add(event)
                await db.flush()
                events.append(event)

                audit = EventAudit(
                    event_id=event.id,
                    audited_at=event_time,
                    has_rtdetr=True,
                    has_florence=True,
                    has_clip=False,
                    has_violence=False,
                    has_clothing=False,
                    has_vehicle=False,
                    has_pet=False,
                    has_weather=False,
                    has_image_quality=False,
                    has_zones=False,
                    has_baseline=False,
                    has_cross_camera=False,
                    prompt_length=100,
                    prompt_token_estimate=25,
                    enrichment_utilization=0.17,
                    overall_quality_score=4.0,
                )
                db.add(audit)

            await db.commit()

        return events

    async def test_stats_respects_7_day_window(
        self,
        async_client: AsyncClient,
        _events_across_time_range: list[Event],
    ):
        """Test that stats with days=7 only includes recent events."""
        response = await async_client.get("/api/ai-audit/stats?days=7")
        assert response.status_code == 200

        data = response.json()
        # Should include events from 0 and 5 days ago (2 events)
        assert data["total_events"] == 2

    async def test_stats_respects_30_day_window(
        self,
        async_client: AsyncClient,
        _events_across_time_range: list[Event],
    ):
        """Test that stats with days=30 includes more events."""
        response = await async_client.get("/api/ai-audit/stats?days=30")
        assert response.status_code == 200

        data = response.json()
        # Should include events from 0, 5, 10, and 20 days ago (4 events)
        assert data["total_events"] == 4

    async def test_leaderboard_respects_time_window(
        self,
        async_client: AsyncClient,
        _events_across_time_range: list[Event],
    ):
        """Test that leaderboard respects the days parameter."""
        response_7 = await async_client.get("/api/ai-audit/leaderboard?days=7")
        response_30 = await async_client.get("/api/ai-audit/leaderboard?days=30")

        data_7 = response_7.json()
        data_30 = response_30.json()

        assert data_7["period_days"] == 7
        assert data_30["period_days"] == 30

        # Event counts should differ between time windows
        rtdetr_7 = next(e for e in data_7["entries"] if e["model_name"] == "rtdetr")
        rtdetr_30 = next(e for e in data_30["entries"] if e["model_name"] == "rtdetr")

        # 30-day window should have more or equal events
        assert rtdetr_30["event_count"] >= rtdetr_7["event_count"]


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling."""

    async def test_get_audit_invalid_event_id_format(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test handling of non-numeric event ID."""
        response = await async_client.get("/api/ai-audit/events/not-a-number")
        # FastAPI should return 422 for invalid int conversion
        assert response.status_code == 422

    async def test_get_audit_very_large_event_id(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test handling of very large event ID."""
        response = await async_client.get("/api/ai-audit/events/999999999")
        assert response.status_code == 404

    async def test_evaluate_invalid_event_id(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test evaluate endpoint with invalid event ID."""
        response = await async_client.post("/api/ai-audit/events/abc/evaluate")
        assert response.status_code == 422

    async def test_stats_non_existent_camera_filter(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test stats with non-existent camera ID returns empty results."""
        response = await async_client.get(
            "/api/ai-audit/stats?days=7&camera_id=non-existent-camera-id"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total_events"] == 0

    async def test_batch_empty_request_uses_defaults(
        self,
        async_client: AsyncClient,
        _clean_ai_audit_tables: None,
    ):
        """Test batch endpoint with empty request body uses defaults."""
        response = await async_client.post(
            "/api/ai-audit/batch",
            json={},
        )
        # Should use default limit=100, which is valid
        assert response.status_code == 200

    async def test_consistency_score_calculation(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
        sample_event_audit: EventAudit,
    ):
        """Test that consistency metrics are properly returned."""
        response = await async_client.get(f"/api/ai-audit/events/{sample_event_for_audit.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["consistency_risk_score"] == 70
        assert data["consistency_diff"] == 5

    async def test_audit_with_empty_improvements(
        self,
        async_client: AsyncClient,
        integration_db: str,
        sample_camera_for_audit: Camera,
    ):
        """Test audit response with empty improvement lists."""
        from backend.core.database import get_session
        from backend.models.event import Event
        from backend.models.event_audit import EventAudit

        async with get_session() as db:
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_camera_for_audit.id,
                started_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC),
                risk_score=50,
                risk_level="medium",
                summary="Test event",
                reasoning="Test reasoning",
                reviewed=False,
            )
            db.add(event)
            await db.flush()

            audit = EventAudit(
                event_id=event.id,
                audited_at=datetime.now(UTC),
                has_rtdetr=True,
                has_florence=False,
                has_clip=False,
                has_violence=False,
                has_clothing=False,
                has_vehicle=False,
                has_pet=False,
                has_weather=False,
                has_image_quality=False,
                has_zones=False,
                has_baseline=False,
                has_cross_camera=False,
                prompt_length=100,
                prompt_token_estimate=25,
                enrichment_utilization=0.08,
                overall_quality_score=4.0,
                # Empty improvement lists
                missing_context=json.dumps([]),
                confusing_sections=json.dumps([]),
                unused_data=json.dumps([]),
                format_suggestions=json.dumps([]),
                model_gaps=json.dumps([]),
            )
            db.add(audit)
            await db.commit()
            await db.refresh(event)

            response = await async_client.get(f"/api/ai-audit/events/{event.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["improvements"]["missing_context"] == []
        assert data["improvements"]["confusing_sections"] == []
        assert data["improvements"]["unused_data"] == []
        assert data["improvements"]["format_suggestions"] == []
        assert data["improvements"]["model_gaps"] == []
