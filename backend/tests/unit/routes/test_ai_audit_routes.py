"""Unit tests for AI audit API routes.

Tests cover all 8 endpoints in backend/api/routes/ai_audit.py:
- GET  /api/ai-audit/events/{event_id} - Get audit for specific event
- POST /api/ai-audit/events/{event_id}/evaluate - Trigger evaluation
- GET  /api/ai-audit/stats - Get aggregate statistics
- GET  /api/ai-audit/leaderboard - Get model leaderboard
- GET  /api/ai-audit/recommendations - Get prompt recommendations
- POST /api/ai-audit/batch - Trigger batch audit processing
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_job_tracker_dep
from backend.api.routes.ai_audit import router
from backend.core.database import get_db
from backend.models.event import Event
from backend.models.event_audit import EventAudit

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_job_tracker() -> MagicMock:
    """Create a mock job tracker."""
    tracker = MagicMock()
    tracker.create_job.return_value = "test-job-id"
    tracker.start_job.return_value = None
    tracker.complete_job.return_value = None
    tracker.fail_job.return_value = None
    tracker.get_job.return_value = {
        "job_id": "test-job-id",
        "status": "completed",
        "created_at": datetime.now(UTC).isoformat(),
        "result": {"total_events": 0, "processed_events": 0, "failed_events": 0},
    }
    tracker.get_job_from_redis = AsyncMock(return_value=None)
    return tracker


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_job_tracker: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    def override_get_job_tracker():
        return mock_job_tracker

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_job_tracker_dep] = override_get_job_tracker

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    event = Event(
        id=1,
        batch_id="batch-123",
        camera_id="cam-001",
        started_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        risk_score=65,
        risk_level="medium",
        summary="Person detected near entrance",
        reasoning="A person was detected approaching the front door.",
        llm_prompt="Analyze this security event...",
    )
    return event


@pytest.fixture
def sample_audit() -> EventAudit:
    """Create a sample event audit for testing."""
    audit = EventAudit(
        id=1,
        event_id=1,
        audited_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
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
        has_baseline=True,
        has_cross_camera=False,
        # Prompt metrics
        prompt_length=1500,
        prompt_token_estimate=375,
        enrichment_utilization=0.58,
        # Quality scores
        context_usage_score=4.2,
        reasoning_coherence_score=3.8,
        risk_justification_score=4.0,
        consistency_score=4.5,
        overall_quality_score=4.1,
        # Consistency check
        consistency_risk_score=60,
        consistency_diff=5,
        # Self-evaluation
        self_eval_critique="The analysis was thorough but could use more context.",
        # Improvements (JSON strings)
        missing_context=json.dumps(["historical patterns", "time of day context"]),
        confusing_sections=json.dumps([]),
        unused_data=json.dumps(["weather data"]),
        format_suggestions=json.dumps(["use bullet points"]),
        model_gaps=json.dumps(["face recognition"]),
    )
    return audit


@pytest.fixture
def unevaluated_audit() -> EventAudit:
    """Create an unevaluated audit (no quality scores)."""
    audit = EventAudit(
        id=2,
        event_id=2,
        audited_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
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
        prompt_length=500,
        prompt_token_estimate=125,
        enrichment_utilization=0.08,
        # No quality scores set
    )
    return audit


# =============================================================================
# GET /api/ai-audit/events/{event_id} Tests
# =============================================================================


class TestGetEventAudit:
    """Tests for GET /api/ai-audit/events/{event_id} endpoint."""

    def test_get_event_audit_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
        sample_audit: EventAudit,
    ) -> None:
        """Test successfully getting an event audit."""
        # Mock event query
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        # Mock audit query
        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = sample_audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        response = client.get("/api/ai-audit/events/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["event_id"] == 1
        assert data["is_fully_evaluated"] is True
        assert data["contributions"]["rtdetr"] is True
        assert data["contributions"]["florence"] is True
        assert data["contributions"]["clip"] is False
        assert data["scores"]["context_usage"] == 4.2
        assert data["scores"]["overall"] == 4.1
        assert data["prompt_length"] == 1500
        assert data["enrichment_utilization"] == 0.58
        assert "historical patterns" in data["improvements"]["missing_context"]

    def test_get_event_audit_event_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test 404 when event does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/ai-audit/events/999")

        assert response.status_code == 404
        assert "Event with id 999 not found" in response.json()["detail"]

    def test_get_event_audit_audit_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test 404 when event exists but audit does not."""
        # Mock event query - found
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        # Mock audit query - not found
        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        response = client.get("/api/ai-audit/events/1")

        assert response.status_code == 404
        assert "No audit found for event 1" in response.json()["detail"]

    def test_get_event_audit_with_null_scores(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
        unevaluated_audit: EventAudit,
    ) -> None:
        """Test getting an unevaluated audit with null scores."""
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = unevaluated_audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        response = client.get("/api/ai-audit/events/2")

        assert response.status_code == 200
        data = response.json()
        assert data["is_fully_evaluated"] is False
        assert data["scores"]["context_usage"] is None
        assert data["scores"]["overall"] is None

    def test_get_event_audit_with_malformed_json_improvements(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test audit with malformed JSON in improvements fields."""
        audit = EventAudit(
            id=3,
            event_id=1,
            audited_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
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
            # Malformed JSON
            missing_context="not valid json",
            confusing_sections=None,
            unused_data="{}",  # Valid but not a list
            format_suggestions=json.dumps(["valid item"]),
            model_gaps=json.dumps([]),
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        response = client.get("/api/ai-audit/events/1")

        assert response.status_code == 200
        data = response.json()
        # Malformed JSON should return empty lists
        assert data["improvements"]["missing_context"] == []
        assert data["improvements"]["confusing_sections"] == []
        assert data["improvements"]["unused_data"] == []
        assert data["improvements"]["format_suggestions"] == ["valid item"]


# =============================================================================
# POST /api/ai-audit/events/{event_id}/evaluate Tests
# =============================================================================


class TestEvaluateEvent:
    """Tests for POST /api/ai-audit/events/{event_id}/evaluate endpoint."""

    def test_evaluate_event_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
        unevaluated_audit: EventAudit,
    ) -> None:
        """Test successfully triggering evaluation."""
        # Mock event query
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        # Mock audit query
        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = unevaluated_audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        # Create evaluated audit to return
        evaluated_audit = EventAudit(
            id=2,
            event_id=2,
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
            prompt_length=500,
            prompt_token_estimate=125,
            enrichment_utilization=0.08,
            overall_quality_score=3.5,
            context_usage_score=3.5,
            reasoning_coherence_score=3.5,
            risk_justification_score=3.5,
            consistency_score=3.5,
        )

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.run_full_evaluation = AsyncMock(return_value=evaluated_audit)
            mock_get_service.return_value = mock_service

            response = client.post("/api/ai-audit/events/2/evaluate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_fully_evaluated"] is True
        assert data["scores"]["overall"] == 3.5

    def test_evaluate_event_already_evaluated_no_force(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
        sample_audit: EventAudit,
    ) -> None:
        """Test that already evaluated audits are returned without re-evaluation."""
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = sample_audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.run_full_evaluation = AsyncMock()
            mock_get_service.return_value = mock_service

            response = client.post("/api/ai-audit/events/1/evaluate")

        assert response.status_code == 200
        # Should not call run_full_evaluation since already evaluated
        mock_service.run_full_evaluation.assert_not_called()

    def test_evaluate_event_force_reevaluation(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
        sample_audit: EventAudit,
    ) -> None:
        """Test force re-evaluation of already evaluated audit."""
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = sample_audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.run_full_evaluation = AsyncMock(return_value=sample_audit)
            mock_get_service.return_value = mock_service

            response = client.post("/api/ai-audit/events/1/evaluate?force=true")

        assert response.status_code == 200
        # Should call run_full_evaluation since force=true
        mock_service.run_full_evaluation.assert_called_once()

    def test_evaluate_event_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test 404 when event does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/ai-audit/events/999/evaluate")

        assert response.status_code == 404
        assert "Event with id 999 not found" in response.json()["detail"]

    def test_evaluate_event_audit_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test 404 when event exists but audit does not."""
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        response = client.post("/api/ai-audit/events/1/evaluate")

        assert response.status_code == 404
        assert "No audit found for event 1" in response.json()["detail"]


# =============================================================================
# GET /api/ai-audit/stats Tests
# =============================================================================


class TestGetAuditStats:
    """Tests for GET /api/ai-audit/stats endpoint."""

    def test_get_audit_stats_success(self, client: TestClient) -> None:
        """Test getting audit statistics."""
        mock_stats = {
            "total_events": 100,
            "audited_events": 95,
            "fully_evaluated_events": 80,
            "avg_quality_score": 3.8,
            "avg_consistency_rate": 4.2,
            "avg_enrichment_utilization": 0.65,
            "model_contribution_rates": {
                "rtdetr": 1.0,
                "florence": 0.85,
                "clip": 0.45,
                "violence": 0.1,
                "clothing": 0.6,
                "vehicle": 0.3,
                "pet": 0.15,
                "weather": 0.7,
                "image_quality": 0.8,
                "zones": 0.9,
                "baseline": 0.5,
                "cross_camera": 0.2,
            },
            "audits_by_day": [
                {"date": "2025-12-22", "count": 15},
                {"date": "2025-12-23", "count": 20},
            ],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 100
        assert data["audited_events"] == 95
        assert data["fully_evaluated_events"] == 80
        assert data["avg_quality_score"] == 3.8
        assert data["model_contribution_rates"]["rtdetr"] == 1.0

    def test_get_audit_stats_with_days_param(self, client: TestClient) -> None:
        """Test stats with custom days parameter."""
        mock_stats = {
            "total_events": 50,
            "audited_events": 50,
            "fully_evaluated_events": 40,
            "avg_quality_score": 4.0,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": 0.5,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/stats?days=30")

        assert response.status_code == 200
        mock_service.get_stats.assert_called_once()
        call_kwargs = mock_service.get_stats.call_args.kwargs
        assert call_kwargs["days"] == 30

    def test_get_audit_stats_with_camera_filter(self, client: TestClient) -> None:
        """Test stats filtered by camera ID."""
        mock_stats = {
            "total_events": 25,
            "audited_events": 25,
            "fully_evaluated_events": 20,
            "avg_quality_score": 3.5,
            "avg_consistency_rate": 4.0,
            "avg_enrichment_utilization": 0.6,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/stats?camera_id=cam-001")

        assert response.status_code == 200
        call_kwargs = mock_service.get_stats.call_args.kwargs
        assert call_kwargs["camera_id"] == "cam-001"

    def test_get_audit_stats_days_validation_min(self, client: TestClient) -> None:
        """Test that days parameter has minimum validation."""
        response = client.get("/api/ai-audit/stats?days=0")
        assert response.status_code == 422  # Validation error

    def test_get_audit_stats_days_validation_max(self, client: TestClient) -> None:
        """Test that days parameter has maximum validation."""
        response = client.get("/api/ai-audit/stats?days=100")
        assert response.status_code == 422  # Validation error

    def test_get_audit_stats_empty_results(self, client: TestClient) -> None:
        """Test stats when no audits exist."""
        mock_stats = {
            "total_events": 0,
            "audited_events": 0,
            "fully_evaluated_events": 0,
            "avg_quality_score": None,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": None,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0
        assert data["avg_quality_score"] is None


# =============================================================================
# GET /api/ai-audit/leaderboard Tests
# =============================================================================


class TestGetModelLeaderboard:
    """Tests for GET /api/ai-audit/leaderboard endpoint."""

    def test_get_leaderboard_success(self, client: TestClient) -> None:
        """Test getting model leaderboard."""
        mock_entries = [
            {
                "model_name": "rtdetr",
                "contribution_rate": 1.0,
                "quality_correlation": 0.85,
                "event_count": 100,
            },
            {
                "model_name": "florence",
                "contribution_rate": 0.85,
                "quality_correlation": 0.72,
                "event_count": 85,
            },
            {
                "model_name": "zones",
                "contribution_rate": 0.9,
                "quality_correlation": None,
                "event_count": 90,
            },
        ]

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_leaderboard = AsyncMock(return_value=mock_entries)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 3
        assert data["entries"][0]["model_name"] == "rtdetr"
        assert data["entries"][0]["contribution_rate"] == 1.0
        assert data["period_days"] == 7  # Default

    def test_get_leaderboard_with_days_param(self, client: TestClient) -> None:
        """Test leaderboard with custom days parameter."""
        mock_entries = []

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_leaderboard = AsyncMock(return_value=mock_entries)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/leaderboard?days=14")

        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 14
        mock_service.get_leaderboard.assert_called_once()
        call_kwargs = mock_service.get_leaderboard.call_args.kwargs
        assert call_kwargs["days"] == 14

    def test_get_leaderboard_empty(self, client: TestClient) -> None:
        """Test leaderboard with no data."""
        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_leaderboard = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert data["entries"] == []
        assert data["period_days"] == 7

    def test_get_leaderboard_days_validation(self, client: TestClient) -> None:
        """Test days parameter validation."""
        # Below minimum
        response = client.get("/api/ai-audit/leaderboard?days=0")
        assert response.status_code == 422

        # Above maximum
        response = client.get("/api/ai-audit/leaderboard?days=91")
        assert response.status_code == 422


# =============================================================================
# GET /api/ai-audit/recommendations Tests
# =============================================================================


class TestGetRecommendations:
    """Tests for GET /api/ai-audit/recommendations endpoint."""

    def test_get_recommendations_success(self, client: TestClient) -> None:
        """Test getting recommendations."""
        mock_recommendations = [
            {
                "category": "missing_context",
                "suggestion": "Include historical activity patterns",
                "frequency": 45,
                "priority": "high",
            },
            {
                "category": "model_gaps",
                "suggestion": "Add face recognition",
                "frequency": 30,
                "priority": "medium",
            },
            {
                "category": "format_suggestions",
                "suggestion": "Use bullet points for clarity",
                "frequency": 15,
                "priority": "low",
            },
        ]
        mock_stats = {
            "total_events": 100,
            "audited_events": 100,
            "fully_evaluated_events": 80,
            "avg_quality_score": 3.8,
            "avg_consistency_rate": 4.0,
            "avg_enrichment_utilization": 0.6,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=mock_recommendations)
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert len(data["recommendations"]) == 3
        assert data["recommendations"][0]["category"] == "missing_context"
        assert data["recommendations"][0]["priority"] == "high"
        assert data["total_events_analyzed"] == 80

    def test_get_recommendations_with_days_param(self, client: TestClient) -> None:
        """Test recommendations with custom days parameter."""
        mock_stats = {
            "total_events": 50,
            "audited_events": 50,
            "fully_evaluated_events": 40,
            "avg_quality_score": 4.0,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": 0.5,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=[])
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/recommendations?days=30")

        assert response.status_code == 200
        mock_service.get_recommendations.assert_called_once()
        call_kwargs = mock_service.get_recommendations.call_args.kwargs
        assert call_kwargs["days"] == 30

    def test_get_recommendations_empty(self, client: TestClient) -> None:
        """Test recommendations with no data."""
        mock_stats = {
            "total_events": 0,
            "audited_events": 0,
            "fully_evaluated_events": 0,
            "avg_quality_score": None,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": None,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=[])
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["recommendations"] == []
        assert data["total_events_analyzed"] == 0

    def test_get_recommendations_days_validation(self, client: TestClient) -> None:
        """Test days parameter validation."""
        response = client.get("/api/ai-audit/recommendations?days=-1")
        assert response.status_code == 422


# =============================================================================
# POST /api/ai-audit/batch Tests
# =============================================================================


class TestTriggerBatchAudit:
    """Tests for POST /api/ai-audit/batch endpoint."""

    def test_batch_audit_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test successful batch audit processing."""
        # Mock query to find events
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_event]
        mock_db_session.execute.return_value = mock_result

        # Create an audit to return for the audit query
        audit = EventAudit(
            id=1,
            event_id=1,
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
        )

        # Set up execute to return different results for different queries
        audit_result = MagicMock()
        audit_result.scalar_one_or_none.return_value = audit

        mock_db_session.execute.side_effect = [mock_result, audit_result]

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.run_full_evaluation = AsyncMock(return_value=audit)
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": 10},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["total_events"] == 1
        assert data["status"] in ["pending", "completed"]

    def test_batch_audit_creates_missing_audits(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test that batch audit creates audits for events without them."""
        # Mock query to find events
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_event]
        mock_db_session.execute.return_value = mock_result

        # No existing audit
        audit_result = MagicMock()
        audit_result.scalar_one_or_none.return_value = None

        new_audit = EventAudit(
            id=1,
            event_id=1,
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
        )

        mock_db_session.execute.side_effect = [mock_result, audit_result]

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.create_partial_audit = MagicMock(return_value=new_audit)
            mock_service.run_full_evaluation = AsyncMock(return_value=new_audit)
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": 10},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["total_events"] == 1

    def test_batch_audit_with_min_risk_score(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test batch audit with min_risk_score filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": 50, "min_risk_score": 70},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["total_events"] == 0

    def test_batch_audit_force_reevaluate(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test batch audit with force_reevaluate flag."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": 100, "force_reevaluate": True},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data

    def test_batch_audit_limit_validation(self, client: TestClient) -> None:
        """Test batch audit limit validation."""
        # Below minimum
        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 0},
        )
        assert response.status_code == 422

        # Above maximum
        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 1001},
        )
        assert response.status_code == 422

    def test_batch_audit_risk_score_validation(self, client: TestClient) -> None:
        """Test batch audit min_risk_score validation."""
        # Below minimum
        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 10, "min_risk_score": -1},
        )
        assert response.status_code == 422

        # Above maximum
        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 10, "min_risk_score": 101},
        )
        assert response.status_code == 422

    def test_batch_audit_empty_results(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test batch audit when no events match criteria."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch("backend.api.routes.ai_audit.get_audit_service"):
            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": 10},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["total_events"] == 0
        # When no events match, the job is immediately marked as completed
        assert data["status"] == "completed"
        assert "No events found matching criteria" in data["message"]


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_event_audit_negative_event_id(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test handling of negative event ID."""
        # FastAPI/Pydantic should accept it (it's just an int)
        # The database query will return no results
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/ai-audit/events/-1")
        # Will get 404 since no event exists with negative ID
        assert response.status_code == 404

    def test_audit_response_all_model_contributions(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_event: Event,
    ) -> None:
        """Test audit response with all model contributions enabled."""
        full_audit = EventAudit(
            id=1,
            event_id=1,
            audited_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            has_rtdetr=True,
            has_florence=True,
            has_clip=True,
            has_violence=True,
            has_clothing=True,
            has_vehicle=True,
            has_pet=True,
            has_weather=True,
            has_image_quality=True,
            has_zones=True,
            has_baseline=True,
            has_cross_camera=True,
            prompt_length=5000,
            prompt_token_estimate=1250,
            enrichment_utilization=1.0,
            overall_quality_score=5.0,
            context_usage_score=5.0,
            reasoning_coherence_score=5.0,
            risk_justification_score=5.0,
            consistency_score=5.0,
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = sample_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = full_audit

        mock_db_session.execute.side_effect = [mock_event_result, mock_audit_result]

        response = client.get("/api/ai-audit/events/1")

        assert response.status_code == 200
        data = response.json()
        contributions = data["contributions"]
        assert all(contributions.values())  # All should be True
        assert data["enrichment_utilization"] == 1.0

    def test_stats_boundary_days_values(self, client: TestClient) -> None:
        """Test stats with boundary day values."""
        mock_stats = {
            "total_events": 0,
            "audited_events": 0,
            "fully_evaluated_events": 0,
            "avg_quality_score": None,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": None,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            # Test minimum boundary (1)
            response = client.get("/api/ai-audit/stats?days=1")
            assert response.status_code == 200

            # Test maximum boundary (90)
            response = client.get("/api/ai-audit/stats?days=90")
            assert response.status_code == 200

    def test_leaderboard_entry_null_quality_correlation(self, client: TestClient) -> None:
        """Test leaderboard with null quality correlation."""
        mock_entries = [
            {
                "model_name": "rtdetr",
                "contribution_rate": 1.0,
                "quality_correlation": None,
                "event_count": 100,
            },
        ]

        with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_leaderboard = AsyncMock(return_value=mock_entries)
            mock_get_service.return_value = mock_service

            response = client.get("/api/ai-audit/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert data["entries"][0]["quality_correlation"] is None


# =============================================================================
# Parametrized Tests
# =============================================================================


class TestParametrized:
    """Parametrized tests for various scenarios."""

    @pytest.mark.parametrize(
        "days,expected_status",
        [
            (1, 200),
            (7, 200),
            (30, 200),
            (90, 200),
            (0, 422),
            (-1, 422),
            (91, 422),
            (100, 422),
        ],
    )
    def test_stats_days_parameter_values(
        self, client: TestClient, days: int, expected_status: int
    ) -> None:
        """Test various days parameter values for stats endpoint."""
        if expected_status == 200:
            mock_stats = {
                "total_events": 0,
                "audited_events": 0,
                "fully_evaluated_events": 0,
                "avg_quality_score": None,
                "avg_consistency_rate": None,
                "avg_enrichment_utilization": None,
                "model_contribution_rates": {},
                "audits_by_day": [],
            }
            with patch("backend.api.routes.ai_audit.get_audit_service") as mock_get_service:
                mock_service = MagicMock()
                mock_service.get_stats = AsyncMock(return_value=mock_stats)
                mock_get_service.return_value = mock_service

                response = client.get(f"/api/ai-audit/stats?days={days}")
        else:
            response = client.get(f"/api/ai-audit/stats?days={days}")

        assert response.status_code == expected_status

    @pytest.mark.parametrize(
        "limit,expected_status",
        [
            (1, 202),
            (100, 202),
            (1000, 202),
            (0, 422),
            (-1, 422),
            (1001, 422),
        ],
    )
    def test_batch_limit_parameter_values(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        limit: int,
        expected_status: int,
    ) -> None:
        """Test various limit parameter values for batch endpoint."""
        if expected_status == 202:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db_session.execute.return_value = mock_result

            with patch("backend.api.routes.ai_audit.get_audit_service"):
                response = client.post(
                    "/api/ai-audit/batch",
                    json={"limit": limit},
                )
        else:
            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": limit},
            )

        assert response.status_code == expected_status

    @pytest.mark.parametrize(
        "min_risk_score,expected_status",
        [
            (0, 202),
            (50, 202),
            (100, 202),
            (-1, 422),
            (101, 422),
            (None, 202),
        ],
    )
    def test_batch_min_risk_score_values(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        min_risk_score: int | None,
        expected_status: int,
    ) -> None:
        """Test various min_risk_score parameter values for batch endpoint."""
        if expected_status == 202:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db_session.execute.return_value = mock_result

            with patch("backend.api.routes.ai_audit.get_audit_service"):
                payload = {"limit": 10}
                if min_risk_score is not None:
                    payload["min_risk_score"] = min_risk_score
                response = client.post("/api/ai-audit/batch", json=payload)
        else:
            response = client.post(
                "/api/ai-audit/batch",
                json={"limit": 10, "min_risk_score": min_risk_score},
            )

        assert response.status_code == expected_status
