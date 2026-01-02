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
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

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
    except Exception:  # noqa: S110 - ignore cleanup errors
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
        assert "not found" in data["detail"].lower()

    async def test_get_event_audit_no_audit_record(
        self,
        async_client: AsyncClient,
        sample_event_for_audit: Event,
    ):
        """Test 404 when event exists but has no audit record."""
        response = await async_client.get(f"/api/ai-audit/events/{sample_event_for_audit.id}")
        assert response.status_code == 404
        data = response.json()
        assert "no audit found" in data["detail"].lower()


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
        assert "not found" in data["detail"].lower()

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
        assert "no audit found" in data["detail"].lower()


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
