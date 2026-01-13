"""Unit tests for AI Audit API endpoints.

Tests cover:
- GET /api/ai-audit/events/{event_id} - Get audit for specific event
- POST /api/ai-audit/events/{event_id}/evaluate - Trigger evaluation for event
- GET /api/ai-audit/stats - Get aggregate audit statistics
- GET /api/ai-audit/leaderboard - Get model leaderboard
- GET /api/ai-audit/recommendations - Get prompt improvement recommendations
- POST /api/ai-audit/batch - Trigger batch audit processing
"""

import json
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from backend.api.routes.ai_audit import router
from backend.api.schemas.ai_audit import (
    AuditStatsResponse,
    BatchAuditJobResponse,
    BatchAuditJobStatusResponse,
    BatchAuditRequest,
    BatchAuditResponse,
    EventAuditResponse,
    LeaderboardResponse,
    ModelContributions,
    ModelLeaderboardEntry,
    PromptImprovements,
    QualityScores,
    RecommendationItem,
    RecommendationsResponse,
)
from backend.models.event import Event
from backend.models.event_audit import EventAudit


def create_mock_event(
    event_id: int = 1,
    risk_score: int = 75,
    llm_prompt: str | None = "Test LLM prompt",
    summary: str = "Test summary",
    reasoning: str = "Test reasoning",
) -> MagicMock:
    """Create a mock Event object."""
    event = MagicMock(spec=Event)
    event.id = event_id
    event.camera_id = "test_camera"
    event.batch_id = "test_batch_001"
    event.risk_score = risk_score
    event.llm_prompt = llm_prompt
    event.summary = summary
    event.reasoning = reasoning
    event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
    event.ended_at = datetime(2025, 12, 23, 12, 5, 0, tzinfo=UTC)
    return event


def create_mock_audit(
    audit_id: int = 1,
    event_id: int = 1,
    is_evaluated: bool = False,
    overall_score: float | None = None,
) -> MagicMock:
    """Create a mock EventAudit object."""
    audit = MagicMock(spec=EventAudit)
    audit.id = audit_id
    audit.event_id = event_id
    audit.audited_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

    # Model contributions
    audit.has_rtdetr = True
    audit.has_florence = False
    audit.has_clip = False
    audit.has_violence = False
    audit.has_clothing = False
    audit.has_vehicle = False
    audit.has_pet = False
    audit.has_weather = False
    audit.has_image_quality = False
    audit.has_zones = False
    audit.has_baseline = False
    audit.has_cross_camera = False

    # Prompt metrics
    audit.prompt_length = 1000
    audit.prompt_token_estimate = 250
    audit.enrichment_utilization = 0.08

    # Quality scores
    audit.context_usage_score = 4.0 if is_evaluated else None
    audit.reasoning_coherence_score = 3.5 if is_evaluated else None
    audit.risk_justification_score = 4.0 if is_evaluated else None
    audit.consistency_score = 4.5 if is_evaluated else None
    audit.overall_quality_score = overall_score

    # Consistency check
    audit.consistency_risk_score = 70 if is_evaluated else None
    audit.consistency_diff = 5 if is_evaluated else None

    # Self-evaluation
    audit.self_eval_critique = "Good analysis" if is_evaluated else None

    # Improvements (JSON strings)
    audit.missing_context = json.dumps(["time_of_day"]) if is_evaluated else None
    audit.confusing_sections = None
    audit.unused_data = None
    audit.format_suggestions = None
    audit.model_gaps = None

    # Property
    audit.is_fully_evaluated = is_evaluated

    return audit


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_audit_service() -> MagicMock:
    """Create a mock audit service."""
    service = MagicMock()
    service.run_full_evaluation = AsyncMock()
    service.get_stats = AsyncMock()
    service.get_leaderboard = AsyncMock()
    service.get_recommendations = AsyncMock()
    service.create_partial_audit = MagicMock()
    return service


@pytest.fixture
def mock_job_tracker() -> MagicMock:
    """Create a mock job tracker."""
    job_tracker = MagicMock()
    # Track created jobs for testing
    job_tracker._jobs = {}

    def create_job_side_effect(job_type: str) -> str:
        import uuid

        job_id = str(uuid.uuid4())
        job_tracker._jobs[job_id] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "pending",
            "progress": 0,
            "message": None,
            "created_at": "2026-01-03T12:00:00Z",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        return job_id

    def start_job_side_effect(job_id: str, message: str | None = None) -> None:
        if job_id in job_tracker._jobs:
            job_tracker._jobs[job_id]["status"] = "running"
            job_tracker._jobs[job_id]["message"] = message
            job_tracker._jobs[job_id]["started_at"] = "2026-01-03T12:00:01Z"

    def update_progress_side_effect(job_id: str, progress: int, message: str | None = None) -> None:
        if job_id in job_tracker._jobs:
            job_tracker._jobs[job_id]["progress"] = progress
            job_tracker._jobs[job_id]["message"] = message

    def complete_job_side_effect(job_id: str, result: dict | None = None) -> None:
        if job_id in job_tracker._jobs:
            job_tracker._jobs[job_id]["status"] = "completed"
            job_tracker._jobs[job_id]["progress"] = 100
            job_tracker._jobs[job_id]["completed_at"] = "2026-01-03T12:05:00Z"
            job_tracker._jobs[job_id]["result"] = result

    def fail_job_side_effect(job_id: str, error: str) -> None:
        if job_id in job_tracker._jobs:
            job_tracker._jobs[job_id]["status"] = "failed"
            job_tracker._jobs[job_id]["completed_at"] = "2026-01-03T12:05:00Z"
            job_tracker._jobs[job_id]["error"] = error

    def get_job_side_effect(job_id: str):
        return job_tracker._jobs.get(job_id)

    job_tracker.create_job = MagicMock(side_effect=create_job_side_effect)
    job_tracker.start_job = MagicMock(side_effect=start_job_side_effect)
    job_tracker.update_progress = MagicMock(side_effect=update_progress_side_effect)
    job_tracker.complete_job = MagicMock(side_effect=complete_job_side_effect)
    job_tracker.fail_job = MagicMock(side_effect=fail_job_side_effect)
    job_tracker.get_job = MagicMock(side_effect=get_job_side_effect)
    job_tracker.get_job_from_redis = AsyncMock(return_value=None)

    return job_tracker


@pytest.fixture
def client(
    mock_db_session: MagicMock, mock_audit_service: MagicMock, mock_job_tracker: MagicMock
) -> TestClient:
    """Create a test client with mocked dependencies."""
    from backend.api.dependencies import get_job_tracker_dep
    from backend.core.database import get_db

    app = FastAPI()
    app.include_router(router)

    # Override the database dependency
    async def override_get_db():
        yield mock_db_session

    # Override the job tracker dependency
    def override_get_job_tracker():
        return mock_job_tracker

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_job_tracker_dep] = override_get_job_tracker

    with (
        patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service),
        TestClient(app) as test_client,
    ):
        yield test_client


class TestGetEventAuditEndpoint:
    """Tests for GET /api/ai-audit/events/{event_id} endpoint."""

    def test_get_event_audit_success(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test successful retrieval of event audit."""
        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)

        # Mock database queries
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])

        response = client.get("/api/ai-audit/events/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["event_id"] == 1
        assert data["is_fully_evaluated"] is True
        assert data["contributions"]["rtdetr"] is True
        assert data["contributions"]["florence"] is False
        assert data["scores"]["context_usage"] == 4.0
        assert data["scores"]["overall"] == 4.0
        assert "time_of_day" in data["improvements"]["missing_context"]

    def test_get_event_audit_not_evaluated(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test retrieval of audit that hasn't been evaluated yet."""
        mock_event = create_mock_event(event_id=2)
        mock_audit = create_mock_audit(audit_id=2, event_id=2, is_evaluated=False)

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])

        response = client.get("/api/ai-audit/events/2")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert data["is_fully_evaluated"] is False
        assert data["scores"]["overall"] is None
        assert data["consistency_risk_score"] is None

    def test_get_event_audit_event_not_found(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 when event does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/ai-audit/events/999")

        assert response.status_code == 404
        data = response.json()
        assert (
            "Event" in data["detail"] and "999" in data["detail"] and "not found" in data["detail"]
        )

    def test_get_event_audit_no_audit_for_event(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 when event exists but has no audit record."""
        mock_event = create_mock_event(event_id=3)

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])

        response = client.get("/api/ai-audit/events/3")

        assert response.status_code == 404
        data = response.json()
        assert "No audit found for event 3" in data["detail"]

    def test_get_event_audit_invalid_event_id(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid event ID."""
        response = client.get("/api/ai-audit/events/invalid")

        assert response.status_code == 422


class TestEvaluateEventEndpoint:
    """Tests for POST /api/ai-audit/events/{event_id}/evaluate endpoint."""

    def test_evaluate_event_success(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test successful evaluation of event."""
        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)
        mock_updated_audit = create_mock_audit(
            audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])
        mock_audit_service.run_full_evaluation.return_value = mock_updated_audit

        response = client.post("/api/ai-audit/events/1/evaluate")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["is_fully_evaluated"] is True
        mock_audit_service.run_full_evaluation.assert_called_once()

    def test_evaluate_event_logs_audit_entry(
        self,
        mock_db_session: MagicMock,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test that AI re-evaluation logs an audit entry."""
        from backend.core.database import get_db
        from backend.models.audit import AuditAction
        from backend.services.audit import AuditService

        app = FastAPI()
        app.include_router(router)

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)
        mock_updated_audit = create_mock_audit(
            audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])
        mock_audit_service.run_full_evaluation.return_value = mock_updated_audit

        with (
            patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service),
            patch.object(AuditService, "log_action", new_callable=AsyncMock) as mock_log_action,
            TestClient(app) as test_client,
        ):
            response = test_client.post("/api/ai-audit/events/1/evaluate")

            assert response.status_code == 200
            # Verify audit logging was called with correct parameters
            mock_log_action.assert_called_once()
            call_args = mock_log_action.call_args
            assert call_args.kwargs["action"] == AuditAction.AI_REEVALUATED
            assert call_args.kwargs["resource_type"] == "event"
            assert call_args.kwargs["resource_id"] == "1"
            assert "is_force" in call_args.kwargs["details"]

    def test_evaluate_event_force_logs_audit_with_force_flag(
        self,
        mock_db_session: MagicMock,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test that force re-evaluation logs audit entry with is_force=True."""
        from backend.core.database import get_db
        from backend.models.audit import AuditAction
        from backend.services.audit import AuditService

        app = FastAPI()
        app.include_router(router)

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)
        mock_updated_audit = create_mock_audit(
            audit_id=1, event_id=1, is_evaluated=True, overall_score=4.5
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])
        mock_audit_service.run_full_evaluation.return_value = mock_updated_audit

        with (
            patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service),
            patch.object(AuditService, "log_action", new_callable=AsyncMock) as mock_log_action,
            TestClient(app) as test_client,
        ):
            response = test_client.post("/api/ai-audit/events/1/evaluate?force=true")

            assert response.status_code == 200
            mock_log_action.assert_called_once()
            call_args = mock_log_action.call_args
            assert call_args.kwargs["action"] == AuditAction.AI_REEVALUATED
            assert call_args.kwargs["details"]["is_force"] is True

    def test_evaluate_event_already_evaluated_no_force(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test that already evaluated event is not re-evaluated without force flag."""
        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])

        response = client.post("/api/ai-audit/events/1/evaluate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_fully_evaluated"] is True
        mock_audit_service.run_full_evaluation.assert_not_called()

    def test_evaluate_event_force_reevaluate(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test force re-evaluation of already evaluated event."""
        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)
        mock_updated_audit = create_mock_audit(
            audit_id=1, event_id=1, is_evaluated=True, overall_score=4.5
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = mock_audit

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])
        mock_audit_service.run_full_evaluation.return_value = mock_updated_audit

        response = client.post("/api/ai-audit/events/1/evaluate?force=true")

        assert response.status_code == 200
        data = response.json()
        assert data["scores"]["overall"] == 4.5
        mock_audit_service.run_full_evaluation.assert_called_once()

    def test_evaluate_event_not_found(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 when event does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post("/api/ai-audit/events/999/evaluate")

        assert response.status_code == 404
        assert "Event" in response.json()["detail"] and "999" in response.json()["detail"]

    def test_evaluate_event_no_audit(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 when event has no audit record."""
        mock_event = create_mock_event(event_id=1)

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_event_result, mock_audit_result])

        response = client.post("/api/ai-audit/events/1/evaluate")

        assert response.status_code == 404
        assert "No audit found for event 1" in response.json()["detail"]


class TestGetAuditStatsEndpoint:
    """Tests for GET /api/ai-audit/stats endpoint."""

    def test_get_stats_success(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test successful retrieval of audit statistics."""
        mock_audit_service.get_stats.return_value = {
            "total_events": 100,
            "audited_events": 100,
            "fully_evaluated_events": 75,
            "avg_quality_score": 4.2,
            "avg_consistency_rate": 4.5,
            "avg_enrichment_utilization": 0.35,
            "model_contribution_rates": {
                "rtdetr": 1.0,
                "florence": 0.5,
                "clip": 0.3,
                "violence": 0.1,
            },
            "audits_by_day": [
                {"date": "2025-12-22", "count": 40},
                {"date": "2025-12-23", "count": 35},
            ],
        }

        response = client.get("/api/ai-audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 100
        assert data["audited_events"] == 100
        assert data["fully_evaluated_events"] == 75
        assert data["avg_quality_score"] == 4.2
        assert data["model_contribution_rates"]["rtdetr"] == 1.0
        assert len(data["audits_by_day"]) == 2

    def test_get_stats_with_days_param(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test stats with custom days parameter."""
        mock_audit_service.get_stats.return_value = {
            "total_events": 50,
            "audited_events": 50,
            "fully_evaluated_events": 40,
            "avg_quality_score": 4.0,
            "avg_consistency_rate": 4.2,
            "avg_enrichment_utilization": 0.30,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        response = client.get("/api/ai-audit/stats?days=30")

        assert response.status_code == 200
        mock_audit_service.get_stats.assert_called()
        # Verify days parameter was passed
        call_args = mock_audit_service.get_stats.call_args
        assert call_args.kwargs.get("days") == 30 or call_args.args[1] == 30

    def test_get_stats_with_camera_filter(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test stats with camera filter."""
        mock_audit_service.get_stats.return_value = {
            "total_events": 20,
            "audited_events": 20,
            "fully_evaluated_events": 15,
            "avg_quality_score": 3.8,
            "avg_consistency_rate": 4.0,
            "avg_enrichment_utilization": 0.25,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        response = client.get("/api/ai-audit/stats?camera_id=front_door")

        assert response.status_code == 200
        mock_audit_service.get_stats.assert_called()
        call_args = mock_audit_service.get_stats.call_args
        assert call_args.kwargs.get("camera_id") == "front_door"

    def test_get_stats_empty_data(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test stats when no audit data exists."""
        mock_audit_service.get_stats.return_value = {
            "total_events": 0,
            "audited_events": 0,
            "fully_evaluated_events": 0,
            "avg_quality_score": None,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": None,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        response = client.get("/api/ai-audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0
        assert data["avg_quality_score"] is None

    def test_get_stats_invalid_days_param(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid days parameter."""
        response = client.get("/api/ai-audit/stats?days=0")
        assert response.status_code == 422

        response = client.get("/api/ai-audit/stats?days=100")
        assert response.status_code == 422


class TestGetLeaderboardEndpoint:
    """Tests for GET /api/ai-audit/leaderboard endpoint."""

    def test_get_leaderboard_success(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test successful retrieval of model leaderboard."""
        mock_audit_service.get_leaderboard.return_value = [
            {
                "model_name": "rtdetr",
                "contribution_rate": 1.0,
                "quality_correlation": 0.85,
                "event_count": 100,
            },
            {
                "model_name": "florence",
                "contribution_rate": 0.6,
                "quality_correlation": 0.72,
                "event_count": 60,
            },
            {
                "model_name": "clip",
                "contribution_rate": 0.3,
                "quality_correlation": None,
                "event_count": 30,
            },
        ]

        response = client.get("/api/ai-audit/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 3
        assert data["period_days"] == 7  # Default
        assert data["entries"][0]["model_name"] == "rtdetr"
        assert data["entries"][0]["contribution_rate"] == 1.0
        assert data["entries"][2]["quality_correlation"] is None

    def test_get_leaderboard_with_days_param(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test leaderboard with custom days parameter."""
        mock_audit_service.get_leaderboard.return_value = []

        response = client.get("/api/ai-audit/leaderboard?days=14")

        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 14
        mock_audit_service.get_leaderboard.assert_called()

    def test_get_leaderboard_empty(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test leaderboard with no data."""
        mock_audit_service.get_leaderboard.return_value = []

        response = client.get("/api/ai-audit/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert data["entries"] == []


class TestGetRecommendationsEndpoint:
    """Tests for GET /api/ai-audit/recommendations endpoint."""

    def test_get_recommendations_success(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test successful retrieval of recommendations."""
        mock_audit_service.get_recommendations.return_value = [
            {
                "category": "missing_context",
                "suggestion": "Add time of day information",
                "frequency": 25,
                "priority": "high",
            },
            {
                "category": "model_gaps",
                "suggestion": "Enable weather classification",
                "frequency": 15,
                "priority": "medium",
            },
        ]
        mock_audit_service.get_stats.return_value = {
            "total_events": 100,
            "audited_events": 100,
            "fully_evaluated_events": 50,
            "avg_quality_score": 4.0,
            "avg_consistency_rate": 4.2,
            "avg_enrichment_utilization": 0.3,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        response = client.get("/api/ai-audit/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert len(data["recommendations"]) == 2
        assert data["total_events_analyzed"] == 50
        assert data["recommendations"][0]["category"] == "missing_context"
        assert data["recommendations"][0]["priority"] == "high"

    def test_get_recommendations_with_days_param(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test recommendations with custom days parameter."""
        mock_audit_service.get_recommendations.return_value = []
        mock_audit_service.get_stats.return_value = {
            "total_events": 0,
            "audited_events": 0,
            "fully_evaluated_events": 0,
            "avg_quality_score": None,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": None,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        response = client.get("/api/ai-audit/recommendations?days=30")

        assert response.status_code == 200
        mock_audit_service.get_recommendations.assert_called()

    def test_get_recommendations_empty(
        self,
        client: TestClient,
        mock_audit_service: MagicMock,
    ) -> None:
        """Test recommendations when no suggestions available."""
        mock_audit_service.get_recommendations.return_value = []
        mock_audit_service.get_stats.return_value = {
            "total_events": 0,
            "audited_events": 0,
            "fully_evaluated_events": 0,
            "avg_quality_score": None,
            "avg_consistency_rate": None,
            "avg_enrichment_utilization": None,
            "model_contribution_rates": {},
            "audits_by_day": [],
        }

        response = client.get("/api/ai-audit/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["recommendations"] == []
        assert data["total_events_analyzed"] == 0


class TestBatchAuditEndpoint:
    """Tests for POST /api/ai-audit/batch endpoint (async version).

    NEM-2473: Batch audit now runs asynchronously and returns 202 Accepted
    with a job ID that can be used to track progress.
    """

    def test_batch_audit_returns_202_with_job_id(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit returns 202 with job ID for async processing."""
        mock_event1 = create_mock_event(event_id=1)
        mock_event2 = create_mock_event(event_id=2)

        # Mock the query result for events
        mock_events_result = MagicMock()
        mock_events_scalars = MagicMock()
        mock_events_scalars.all.return_value = [mock_event1, mock_event2]
        mock_events_result.scalars.return_value = mock_events_scalars

        mock_db_session.execute = AsyncMock(return_value=mock_events_result)

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 100, "force_reevaluate": False},
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["total_events"] == 2
        assert "/api/ai-audit/batch/" in data["message"]

    def test_batch_audit_creates_job_with_correct_type(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test that batch audit creates a job with type 'batch_audit'."""
        mock_event = create_mock_event(event_id=1)

        mock_events_result = MagicMock()
        mock_events_scalars = MagicMock()
        mock_events_scalars.all.return_value = [mock_event]
        mock_events_result.scalars.return_value = mock_events_scalars

        mock_db_session.execute = AsyncMock(return_value=mock_events_result)

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 100},
        )

        assert response.status_code == 202
        mock_job_tracker.create_job.assert_called_once_with("batch_audit")

    def test_batch_audit_with_min_risk_score(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit with minimum risk score filter."""
        mock_event = create_mock_event(event_id=1, risk_score=80)

        mock_events_result = MagicMock()
        mock_events_scalars = MagicMock()
        mock_events_scalars.all.return_value = [mock_event]
        mock_events_result.scalars.return_value = mock_events_scalars

        mock_db_session.execute = AsyncMock(return_value=mock_events_result)

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 50, "min_risk_score": 70, "force_reevaluate": False},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["total_events"] == 1

    def test_batch_audit_no_matching_events_returns_completed(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit when no events match criteria returns completed immediately."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 100},
        )

        # Still returns 202 but status is 'completed' since no work to do
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "completed"
        assert data["total_events"] == 0
        assert "no events found" in data["message"].lower()

    def test_batch_audit_force_reevaluate(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit with force re-evaluation flag."""
        mock_event = create_mock_event(event_id=1)

        mock_events_result = MagicMock()
        mock_events_scalars = MagicMock()
        mock_events_scalars.all.return_value = [mock_event]
        mock_events_result.scalars.return_value = mock_events_scalars

        mock_db_session.execute = AsyncMock(return_value=mock_events_result)

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 100, "force_reevaluate": True},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["total_events"] == 1

    def test_batch_audit_invalid_limit(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid limit."""
        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 0},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 2000},
        )
        assert response.status_code == 422

    def test_batch_audit_invalid_risk_score(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid risk score."""
        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 100, "min_risk_score": -1},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/ai-audit/batch",
            json={"limit": 100, "min_risk_score": 150},
        )
        assert response.status_code == 422


class TestBatchAuditStatusEndpoint:
    """Tests for GET /api/ai-audit/batch/{job_id} endpoint.

    NEM-2473: Added status endpoint for polling batch audit job progress.
    """

    def test_get_batch_audit_status_success(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test successful retrieval of batch audit job status."""
        # Set up a job in the mock job tracker
        job_id = mock_job_tracker.create_job("batch_audit")
        mock_job_tracker.start_job(job_id, message="Processing events...")
        mock_job_tracker.update_progress(job_id, 50, message="Processing event 5 of 10")

        response = client.get(f"/api/ai-audit/batch/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "running"
        assert data["progress"] == 50
        assert data["message"] == "Processing event 5 of 10"

    def test_get_batch_audit_status_completed(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test retrieval of completed batch audit job status."""
        job_id = mock_job_tracker.create_job("batch_audit")
        mock_job_tracker.start_job(job_id, message="Starting...")
        mock_job_tracker.complete_job(
            job_id,
            result={
                "total_events": 10,
                "processed_events": 10,
                "failed_events": 0,
            },
        )

        response = client.get(f"/api/ai-audit/batch/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["total_events"] == 10
        assert data["processed_events"] == 10
        assert data["failed_events"] == 0
        assert data["completed_at"] is not None

    def test_get_batch_audit_status_failed(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test retrieval of failed batch audit job status."""
        job_id = mock_job_tracker.create_job("batch_audit")
        mock_job_tracker.start_job(job_id, message="Starting...")
        mock_job_tracker.fail_job(job_id, error="Database connection failed")

        response = client.get(f"/api/ai-audit/batch/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "failed"
        assert data["error"] == "Database connection failed"

    def test_get_batch_audit_status_not_found(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test 404 when job not found."""
        response = client.get("/api/ai-audit/batch/non-existent-job-id")

        assert response.status_code == 404
        data = response.json()
        # Check that the error message indicates job was not found
        assert "no batch audit job found" in data["detail"].lower()

    def test_get_batch_audit_status_pending(
        self,
        client: TestClient,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test retrieval of pending batch audit job status."""
        job_id = mock_job_tracker.create_job("batch_audit")

        response = client.get(f"/api/ai-audit/batch/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"
        assert data["progress"] == 0


class TestAuditSchemas:
    """Tests for AI Audit Pydantic schemas."""

    def test_model_contributions_defaults(self) -> None:
        """Test ModelContributions has correct defaults."""
        contributions = ModelContributions()
        assert contributions.rtdetr is False
        assert contributions.florence is False
        assert contributions.clip is False
        assert contributions.violence is False

    def test_quality_scores_valid_range(self) -> None:
        """Test QualityScores validates 1-5 range."""
        scores = QualityScores(
            context_usage=3.5,
            reasoning_coherence=4.0,
            risk_justification=5.0,
            consistency=1.0,
            overall=3.0,
        )
        assert scores.context_usage == 3.5
        assert scores.overall == 3.0

    def test_quality_scores_none_values(self) -> None:
        """Test QualityScores allows None values."""
        scores = QualityScores()
        assert scores.context_usage is None
        assert scores.overall is None

    def test_prompt_improvements_defaults(self) -> None:
        """Test PromptImprovements has empty list defaults."""
        improvements = PromptImprovements()
        assert improvements.missing_context == []
        assert improvements.confusing_sections == []
        assert improvements.unused_data == []

    def test_event_audit_response_complete(self) -> None:
        """Test EventAuditResponse with all fields."""
        response = EventAuditResponse(
            id=1,
            event_id=1,
            audited_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            is_fully_evaluated=True,
            contributions=ModelContributions(rtdetr=True, florence=True),
            prompt_length=1000,
            prompt_token_estimate=250,
            enrichment_utilization=0.5,
            scores=QualityScores(overall=4.0),
            consistency_risk_score=70,
            consistency_diff=5,
            self_eval_critique="Good analysis",
            improvements=PromptImprovements(missing_context=["time_of_day"]),
        )
        assert response.id == 1
        assert response.contributions.rtdetr is True
        assert response.scores.overall == 4.0

    def test_audit_stats_response(self) -> None:
        """Test AuditStatsResponse creation."""
        response = AuditStatsResponse(
            total_events=100,
            audited_events=100,
            fully_evaluated_events=75,
            avg_quality_score=4.2,
            avg_consistency_rate=4.5,
            avg_enrichment_utilization=0.35,
            model_contribution_rates={"rtdetr": 1.0},
            audits_by_day=[],
        )
        assert response.total_events == 100
        assert response.model_contribution_rates["rtdetr"] == 1.0

    def test_model_leaderboard_entry(self) -> None:
        """Test ModelLeaderboardEntry creation."""
        entry = ModelLeaderboardEntry(
            model_name="rtdetr",
            contribution_rate=0.95,
            quality_correlation=0.82,
            event_count=100,
        )
        assert entry.model_name == "rtdetr"
        assert entry.contribution_rate == 0.95

    def test_leaderboard_response(self) -> None:
        """Test LeaderboardResponse creation."""
        response = LeaderboardResponse(
            entries=[
                ModelLeaderboardEntry(
                    model_name="rtdetr",
                    contribution_rate=1.0,
                    quality_correlation=None,
                    event_count=100,
                )
            ],
            period_days=7,
        )
        assert len(response.entries) == 1
        assert response.period_days == 7

    def test_recommendation_item(self) -> None:
        """Test RecommendationItem creation."""
        item = RecommendationItem(
            category="missing_context",
            suggestion="Add weather data",
            frequency=25,
            priority="high",
        )
        assert item.category == "missing_context"
        assert item.priority == "high"

    def test_recommendations_response(self) -> None:
        """Test RecommendationsResponse creation."""
        response = RecommendationsResponse(
            recommendations=[
                RecommendationItem(
                    category="model_gaps",
                    suggestion="Enable CLIP",
                    frequency=10,
                    priority="medium",
                )
            ],
            total_events_analyzed=50,
        )
        assert len(response.recommendations) == 1
        assert response.total_events_analyzed == 50

    def test_batch_audit_request_defaults(self) -> None:
        """Test BatchAuditRequest default values."""
        request = BatchAuditRequest()
        assert request.limit == 100
        assert request.min_risk_score is None
        assert request.force_reevaluate is False

    def test_batch_audit_request_custom(self) -> None:
        """Test BatchAuditRequest with custom values."""
        request = BatchAuditRequest(limit=50, min_risk_score=70, force_reevaluate=True)
        assert request.limit == 50
        assert request.min_risk_score == 70
        assert request.force_reevaluate is True

    def test_batch_audit_response(self) -> None:
        """Test BatchAuditResponse creation (legacy sync response)."""
        response = BatchAuditResponse(
            queued_count=10,
            message="Successfully processed 10 events",
        )
        assert response.queued_count == 10
        assert "10" in response.message

    def test_batch_audit_job_response(self) -> None:
        """Test BatchAuditJobResponse creation (NEM-2473 async response)."""
        response = BatchAuditJobResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="pending",
            message="Batch audit job created",
            total_events=25,
        )
        assert response.job_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.status == "pending"
        assert response.total_events == 25

    def test_batch_audit_job_status_response(self) -> None:
        """Test BatchAuditJobStatusResponse creation (NEM-2473 status response)."""
        response = BatchAuditJobStatusResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="running",
            progress=45,
            message="Processing event 45 of 100",
            total_events=100,
            processed_events=44,
            failed_events=1,
            created_at=datetime(2026, 1, 3, 12, 0, 0, tzinfo=UTC),
            started_at=datetime(2026, 1, 3, 12, 0, 1, tzinfo=UTC),
            completed_at=None,
            error=None,
        )
        assert response.job_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.status == "running"
        assert response.progress == 45
        assert response.total_events == 100
        assert response.processed_events == 44
        assert response.failed_events == 1
        assert response.started_at is not None
        assert response.completed_at is None

    def test_batch_audit_job_status_response_defaults(self) -> None:
        """Test BatchAuditJobStatusResponse uses correct defaults."""
        response = BatchAuditJobStatusResponse(
            job_id="test-job-id",
            status="pending",
            progress=0,
            total_events=10,
            processed_events=0,
            created_at=datetime(2026, 1, 3, 12, 0, 0, tzinfo=UTC),
        )
        assert response.message is None
        assert response.failed_events == 0
        assert response.started_at is None
        assert response.completed_at is None
        assert response.error is None


class TestAuditToResponseConversion:
    """Tests for _audit_to_response helper function."""

    def test_conversion_with_json_improvements(self) -> None:
        """Test conversion handles JSON-encoded improvement fields."""
        from backend.api.routes.ai_audit import _audit_to_response

        audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)
        audit.missing_context = json.dumps(["item1", "item2"])
        audit.confusing_sections = json.dumps(["section1"])
        audit.unused_data = None
        audit.format_suggestions = "invalid json"  # Should handle gracefully
        audit.model_gaps = json.dumps([])

        response = _audit_to_response(audit)

        assert response.improvements.missing_context == ["item1", "item2"]
        assert response.improvements.confusing_sections == ["section1"]
        assert response.improvements.unused_data == []
        assert response.improvements.format_suggestions == []  # Invalid JSON -> empty list
        assert response.improvements.model_gaps == []

    def test_conversion_with_null_json_fields(self) -> None:
        """Test conversion handles None JSON fields."""
        from backend.api.routes.ai_audit import _audit_to_response

        audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)
        audit.missing_context = None
        audit.confusing_sections = None
        audit.unused_data = None
        audit.format_suggestions = None
        audit.model_gaps = None

        response = _audit_to_response(audit)

        assert response.improvements.missing_context == []
        assert response.improvements.confusing_sections == []
        assert response.improvements.unused_data == []

    def test_conversion_model_contributions_mapping(self) -> None:
        """Test all model contribution flags are correctly mapped."""
        from backend.api.routes.ai_audit import _audit_to_response

        audit = create_mock_audit(audit_id=1, event_id=1)
        audit.has_rtdetr = True
        audit.has_florence = True
        audit.has_clip = False
        audit.has_violence = True
        audit.has_clothing = False
        audit.has_vehicle = True
        audit.has_pet = False
        audit.has_weather = True
        audit.has_image_quality = False
        audit.has_zones = True
        audit.has_baseline = False
        audit.has_cross_camera = True

        response = _audit_to_response(audit)

        assert response.contributions.rtdetr is True
        assert response.contributions.florence is True
        assert response.contributions.clip is False
        assert response.contributions.violence is True
        assert response.contributions.clothing is False
        assert response.contributions.vehicle is True
        assert response.contributions.pet is False
        assert response.contributions.weather is True
        assert response.contributions.image_quality is False
        assert response.contributions.zones is True
        assert response.contributions.baseline is False
        assert response.contributions.cross_camera is True

    def test_conversion_quality_scores_mapping(self) -> None:
        """Test quality scores are correctly mapped."""
        from backend.api.routes.ai_audit import _audit_to_response

        audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.2)
        audit.context_usage_score = 4.5
        audit.reasoning_coherence_score = 3.8
        audit.risk_justification_score = 4.0
        audit.consistency_score = 4.5

        response = _audit_to_response(audit)

        assert response.scores.context_usage == 4.5
        assert response.scores.reasoning_coherence == 3.8
        assert response.scores.risk_justification == 4.0
        assert response.scores.consistency == 4.5
        assert response.scores.overall == 4.2


class TestCustomTestPromptEndpoint:
    """Tests for POST /api/ai-audit/test-prompt endpoint.

    This endpoint allows testing a custom prompt against an existing event
    for A/B testing in the Prompt Playground. Results are NOT persisted.
    """

    def test_test_prompt_returns_results(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test successful custom prompt testing returns expected results."""
        mock_event = create_mock_event(
            event_id=1,
            risk_score=65,
            summary="Person detected near front door",
            reasoning="Person approaching property at night is suspicious.",
        )

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Analyze this event for security risks.",
                "temperature": 0.7,
                "max_tokens": 2048,
                "model": "nemotron",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        assert "risk_score" in data
        assert "risk_level" in data
        assert "reasoning" in data
        assert "summary" in data
        assert "entities" in data
        assert "flags" in data
        assert "recommended_action" in data
        assert "processing_time_ms" in data
        assert "tokens_used" in data

        # Verify values are sensible
        assert data["risk_score"] == 65  # Should match event's risk_score
        assert data["risk_level"] == "high"  # 65 -> high
        assert data["summary"] == "Person detected near front door"
        assert data["reasoning"] == "Person approaching property at night is suspicious."
        assert data["processing_time_ms"] >= 0
        assert data["tokens_used"] > 0

    def test_test_prompt_event_not_found_404(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that 404 is returned when event does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 999,
                "custom_prompt": "Test prompt for non-existent event.",
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert (
            "Event" in data["detail"] and "999" in data["detail"] and "not found" in data["detail"]
        )

    def test_test_prompt_empty_prompt_400(
        self,
        client: TestClient,
    ) -> None:
        """Test that 400 is returned when prompt is empty."""
        # Test with completely empty string
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "",
            },
        )

        assert response.status_code == 422  # Pydantic validation error (min_length=1)

    def test_test_prompt_whitespace_only_prompt_400(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that 400 is returned when prompt contains only whitespace."""
        # Need to pass Pydantic validation but fail our custom check
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "   ",  # Only whitespace
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "empty" in data["detail"].lower()

    def test_test_prompt_with_default_parameters(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that default parameters are used when not specified."""
        mock_event = create_mock_event(event_id=1, risk_score=30)

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        # Only required fields, no optional parameters
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Minimal test prompt.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] == 30
        assert data["risk_level"] == "medium"  # 30 -> medium

    def test_test_prompt_risk_level_mapping(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test risk level mapping for various risk scores."""
        test_cases = [
            (10, "low"),  # < 25 -> low
            (24, "low"),  # < 25 -> low
            (25, "medium"),  # >= 25, < 50 -> medium
            (49, "medium"),  # >= 25, < 50 -> medium
            (50, "high"),  # >= 50, < 75 -> high
            (74, "high"),  # >= 50, < 75 -> high
            (75, "critical"),  # >= 75 -> critical
            (100, "critical"),  # >= 75 -> critical
        ]

        for risk_score, expected_level in test_cases:
            mock_event = create_mock_event(event_id=1, risk_score=risk_score)
            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_db_session.execute = AsyncMock(return_value=mock_event_result)

            response = client.post(
                "/api/ai-audit/test-prompt",
                json={
                    "event_id": 1,
                    "custom_prompt": f"Test with score {risk_score}.",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["risk_level"] == expected_level, (
                f"Expected {expected_level} for score {risk_score}, got {data['risk_level']}"
            )

    def test_test_prompt_event_without_risk_score(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test handling of event with no risk score (defaults to 50)."""
        mock_event = create_mock_event(event_id=1, risk_score=75)
        mock_event.risk_score = None  # Override to None

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Test event with no score.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] == 50  # Default value
        assert data["risk_level"] == "high"  # 50 -> high

    def test_test_prompt_invalid_event_id(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid event ID."""
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 0,  # Must be >= 1
                "custom_prompt": "Test prompt.",
            },
        )

        assert response.status_code == 422  # Pydantic validation error

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": -1,  # Negative
                "custom_prompt": "Test prompt.",
            },
        )

        assert response.status_code == 422

    def test_test_prompt_invalid_temperature(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid temperature."""
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Test prompt.",
                "temperature": 3.0,  # Max is 2.0
            },
        )

        assert response.status_code == 422

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Test prompt.",
                "temperature": -0.5,  # Min is 0.0
            },
        )

        assert response.status_code == 422

    def test_test_prompt_invalid_max_tokens(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid max_tokens."""
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Test prompt.",
                "max_tokens": 50,  # Min is 100
            },
        )

        assert response.status_code == 422

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Test prompt.",
                "max_tokens": 10000,  # Max is 8192
            },
        )

        assert response.status_code == 422

    def test_test_prompt_tokens_estimation(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that tokens_used estimation is reasonable."""
        mock_event = create_mock_event(event_id=1, risk_score=50)

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        # Short prompt
        short_prompt = "Short test."
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": short_prompt,
            },
        )

        assert response.status_code == 200
        short_tokens = response.json()["tokens_used"]

        # Long prompt
        long_prompt = "A" * 1000  # 1000 characters
        mock_db_session.execute = AsyncMock(return_value=mock_event_result)
        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": long_prompt,
            },
        )

        assert response.status_code == 200
        long_tokens = response.json()["tokens_used"]

        # Long prompt should use more tokens
        assert long_tokens > short_tokens

    def test_test_prompt_event_with_no_summary_or_reasoning(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test handling of event with no summary or reasoning (uses defaults)."""
        mock_event = create_mock_event(event_id=1, risk_score=40)
        mock_event.summary = None
        mock_event.reasoning = None

        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        response = client.post(
            "/api/ai-audit/test-prompt",
            json={
                "event_id": 1,
                "custom_prompt": "Test with missing data.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Should have fallback values
        assert "not available" in data["summary"].lower() or data["summary"]
        assert "not available" in data["reasoning"].lower() or data["reasoning"]


class TestCustomTestPromptSchemas:
    """Tests for CustomTestPromptRequest and CustomTestPromptResponse schemas."""

    def test_request_with_all_fields(self) -> None:
        """Test CustomTestPromptRequest with all fields."""
        from backend.api.schemas.ai_audit import CustomTestPromptRequest

        request = CustomTestPromptRequest(
            event_id=1,
            custom_prompt="Test prompt",
            temperature=0.5,
            max_tokens=1024,
            model="nemotron",
        )
        assert request.event_id == 1
        assert request.custom_prompt == "Test prompt"
        assert request.temperature == 0.5
        assert request.max_tokens == 1024
        assert request.model == "nemotron"

    def test_request_with_defaults(self) -> None:
        """Test CustomTestPromptRequest uses defaults for optional fields."""
        from backend.api.schemas.ai_audit import CustomTestPromptRequest

        request = CustomTestPromptRequest(
            event_id=1,
            custom_prompt="Test prompt",
        )
        assert request.event_id == 1
        assert request.custom_prompt == "Test prompt"
        assert request.temperature == 0.7  # Default
        assert request.max_tokens == 2048  # Default
        assert request.model == "nemotron"  # Default

    def test_response_creation(self) -> None:
        """Test CustomTestPromptResponse creation."""
        from backend.api.schemas.ai_audit import CustomTestPromptResponse

        response = CustomTestPromptResponse(
            risk_score=75,
            risk_level="critical",
            reasoning="High risk detected.",
            summary="Person detected at night.",
            entities=[{"type": "person", "confidence": 0.95}],
            flags=[{"type": "time_of_day", "value": "night"}],
            recommended_action="Alert - Immediate attention required",
            processing_time_ms=150,
            tokens_used=500,
        )
        assert response.risk_score == 75
        assert response.risk_level == "critical"
        assert len(response.entities) == 1
        assert len(response.flags) == 1
        assert response.processing_time_ms == 150
        assert response.tokens_used == 500

    def test_response_with_defaults(self) -> None:
        """Test CustomTestPromptResponse uses defaults for optional fields."""
        from backend.api.schemas.ai_audit import CustomTestPromptResponse

        response = CustomTestPromptResponse(
            risk_score=50,
            risk_level="high",
            reasoning="Moderate risk.",
            summary="Activity detected.",
            processing_time_ms=100,
            tokens_used=200,
        )
        assert response.entities == []  # Default
        assert response.flags == []  # Default
        assert response.recommended_action == ""  # Default


class TestHelperFunctions:
    """Tests for helper functions in ai_audit module."""

    def test_safe_parse_datetime_valid_iso(self) -> None:
        """Test parsing valid ISO datetime strings."""
        from backend.api.routes.ai_audit import safe_parse_datetime

        result = safe_parse_datetime("2025-12-23T12:00:00Z")
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 23
        assert result.hour == 12

    def test_safe_parse_datetime_valid_with_offset(self) -> None:
        """Test parsing ISO datetime with timezone offset."""
        from backend.api.routes.ai_audit import safe_parse_datetime

        result = safe_parse_datetime("2025-12-23T12:00:00+00:00")
        assert result.year == 2025
        assert result.month == 12

    def test_safe_parse_datetime_none_uses_fallback(self) -> None:
        """Test that None value returns fallback."""
        from backend.api.routes.ai_audit import safe_parse_datetime

        fallback = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = safe_parse_datetime(None, fallback=fallback)
        assert result == fallback

    def test_safe_parse_datetime_empty_string_uses_fallback(self) -> None:
        """Test that empty string returns fallback."""
        from backend.api.routes.ai_audit import safe_parse_datetime

        fallback = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = safe_parse_datetime("", fallback=fallback)
        assert result == fallback

    def test_safe_parse_datetime_invalid_format_uses_fallback(self) -> None:
        """Test that invalid format returns fallback and logs warning."""
        from backend.api.routes.ai_audit import safe_parse_datetime

        fallback = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = safe_parse_datetime("not-a-date", fallback=fallback)
        assert result == fallback

    def test_safe_parse_datetime_no_fallback_uses_now(self) -> None:
        """Test that no fallback uses current time."""
        from backend.api.routes.ai_audit import safe_parse_datetime

        result = safe_parse_datetime("invalid")
        # Should be close to now
        now = datetime.now(UTC)
        assert abs((now - result).total_seconds()) < 1

    def test_get_risk_level_low(self) -> None:
        """Test risk level mapping for low scores."""
        from backend.api.routes.ai_audit import _get_risk_level

        assert _get_risk_level(0) == "low"
        assert _get_risk_level(10) == "low"
        assert _get_risk_level(24) == "low"

    def test_get_risk_level_medium(self) -> None:
        """Test risk level mapping for medium scores."""
        from backend.api.routes.ai_audit import _get_risk_level

        assert _get_risk_level(25) == "medium"
        assert _get_risk_level(35) == "medium"
        assert _get_risk_level(49) == "medium"

    def test_get_risk_level_high(self) -> None:
        """Test risk level mapping for high scores."""
        from backend.api.routes.ai_audit import _get_risk_level

        assert _get_risk_level(50) == "high"
        assert _get_risk_level(60) == "high"
        assert _get_risk_level(74) == "high"

    def test_get_risk_level_critical(self) -> None:
        """Test risk level mapping for critical scores."""
        from backend.api.routes.ai_audit import _get_risk_level

        assert _get_risk_level(75) == "critical"
        assert _get_risk_level(85) == "critical"
        assert _get_risk_level(100) == "critical"

    def test_get_recommended_action_all_levels(self) -> None:
        """Test recommended actions for all risk levels."""
        from backend.api.routes.ai_audit import _get_recommended_action

        assert _get_recommended_action("low") == "Monitor - No immediate action required"
        assert _get_recommended_action("medium") == "Review - Check event details when convenient"
        assert _get_recommended_action("high") == "Investigate - Review event details promptly"
        assert _get_recommended_action("critical") == "Alert - Immediate attention required"

    def test_get_recommended_action_unknown_level(self) -> None:
        """Test recommended action for unknown risk level."""
        from backend.api.routes.ai_audit import _get_recommended_action

        assert _get_recommended_action("unknown") == "Review event details"
        assert _get_recommended_action("") == "Review event details"


class TestPromptPlaygroundEndpoints:
    """Tests for Prompt Playground API endpoints."""

    def test_get_all_prompts_success(self, client: TestClient) -> None:
        """Test successful retrieval of all prompt configurations."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_all_configs.return_value = {
                "nemotron": {
                    "config": {"system_prompt": "Test prompt"},
                    "version": 1,
                    "updated_at": "2025-12-23T12:00:00Z",
                },
                "florence2": {
                    "config": {"system_prompt": "Florence prompt"},
                    "version": 2,
                    "updated_at": "2025-12-23T13:00:00Z",
                },
            }
            mock_storage.return_value = mock_storage_instance

            response = client.get("/api/ai-audit/prompts")

            assert response.status_code == 200
            data = response.json()
            assert "prompts" in data
            assert "nemotron" in data["prompts"]
            assert "florence2" in data["prompts"]
            assert data["prompts"]["nemotron"]["version"] == 1
            assert data["prompts"]["florence2"]["version"] == 2

    def test_get_model_prompt_success(self, client: TestClient) -> None:
        """Test successful retrieval of specific model prompt."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_config_with_metadata.return_value = {
                "config": {"system_prompt": "Nemotron test prompt"},
                "version": 3,
                "updated_at": "2025-12-23T12:00:00Z",
            }
            mock_storage.return_value = mock_storage_instance

            response = client.get("/api/ai-audit/prompts/nemotron")

            assert response.status_code == 200
            data = response.json()
            assert data["model_name"] == "nemotron"
            assert data["version"] == 3
            assert data["config"]["system_prompt"] == "Nemotron test prompt"

    def test_get_model_prompt_invalid_model(self, client: TestClient) -> None:
        """Test 404 for invalid model name."""
        response = client.get("/api/ai-audit/prompts/invalid_model")
        assert response.status_code == 404

    def test_update_model_prompt_success(self, client: TestClient) -> None:
        """Test successful update of model prompt configuration."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.validate_config.return_value = []
            mock_version = MagicMock()
            mock_version.version = 4
            mock_version.config = {"system_prompt": "Updated prompt"}
            mock_storage_instance.update_config.return_value = mock_version
            mock_storage.return_value = mock_storage_instance

            response = client.put(
                "/api/ai-audit/prompts/nemotron",
                json={"config": {"system_prompt": "Updated prompt"}, "description": "Test update"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["model_name"] == "nemotron"
            assert data["version"] == 4
            assert "updated" in data["message"].lower()

    def test_update_model_prompt_invalid_config(self, client: TestClient) -> None:
        """Test 400 for invalid configuration."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.validate_config.return_value = [
                "Invalid field X",
                "Missing field Y",
            ]
            mock_storage.return_value = mock_storage_instance

            response = client.put(
                "/api/ai-audit/prompts/nemotron",
                json={"config": {"invalid": "config"}},
            )

            assert response.status_code == 400
            assert "Invalid configuration" in response.json()["detail"]

    def test_test_prompt_success(self, client: TestClient, mock_db_session: MagicMock) -> None:
        """Test successful prompt testing endpoint."""
        mock_event = create_mock_event(event_id=1, risk_score=65)
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.run_mock_test = AsyncMock(
                return_value={
                    "before": {"score": 65, "risk_level": "high", "summary": "Before summary"},
                    "after": {"score": 70, "risk_level": "high", "summary": "After summary"},
                    "improved": True,
                    "inference_time_ms": 150,
                }
            )
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/test",
                json={
                    "model": "nemotron",
                    "config": {"system_prompt": "Test prompt"},
                    "event_id": 1,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["before"]["score"] == 65
            assert data["after"]["score"] == 70
            assert data["improved"] is True

    def test_test_prompt_event_not_found(
        self, client: TestClient, mock_db_session: MagicMock
    ) -> None:
        """Test 404 when event not found for prompt testing."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "nemotron",
                "config": {"system_prompt": "Test"},
                "event_id": 999,
            },
        )

        assert response.status_code == 404

    def test_test_prompt_invalid_config(
        self, client: TestClient, mock_db_session: MagicMock
    ) -> None:
        """Test 400 when config is invalid."""
        mock_event = create_mock_event(event_id=1)
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_db_session.execute = AsyncMock(return_value=mock_event_result)

        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.run_mock_test = AsyncMock(
                side_effect=ValueError("Invalid config")
            )
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/test",
                json={
                    "model": "nemotron",
                    "config": {"invalid": "config"},
                    "event_id": 1,
                },
            )

            assert response.status_code == 400

    def test_get_all_prompts_history_success(self, client: TestClient) -> None:
        """Test successful retrieval of prompt history for all models."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_version = MagicMock()
            mock_version.version = 1
            mock_version.config = {"system_prompt": "Test"}
            mock_version.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
            mock_version.created_by = "user"
            mock_version.description = "Initial version"

            mock_storage_instance.get_history.return_value = [mock_version]
            mock_storage_instance.get_total_versions.return_value = 1
            mock_storage.return_value = mock_storage_instance

            response = client.get("/api/ai-audit/prompts/history?limit=5")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            # Should have entries for supported models
            for model_name in data:
                assert "model_name" in data[model_name]
                assert "versions" in data[model_name]
                assert "total_versions" in data[model_name]

    def test_get_model_history_success(self, client: TestClient) -> None:
        """Test successful retrieval of single model history."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_version1 = MagicMock()
            mock_version1.version = 2
            mock_version1.config = {"system_prompt": "Version 2"}
            mock_version1.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
            mock_version1.created_by = "user"
            mock_version1.description = "Update 2"

            mock_version2 = MagicMock()
            mock_version2.version = 1
            mock_version2.config = {"system_prompt": "Version 1"}
            mock_version2.created_at = datetime(2025, 12, 22, 12, 0, 0, tzinfo=UTC)
            mock_version2.created_by = "system"
            mock_version2.description = "Initial"

            mock_storage_instance.get_history.return_value = [mock_version1, mock_version2]
            mock_storage_instance.get_total_versions.return_value = 2
            mock_storage.return_value = mock_storage_instance

            response = client.get("/api/ai-audit/prompts/history/nemotron?limit=10&offset=0")

            assert response.status_code == 200
            data = response.json()
            assert data["model_name"] == "nemotron"
            assert len(data["versions"]) == 2
            assert data["total_versions"] == 2
            assert data["versions"][0]["version"] == 2
            assert data["versions"][1]["version"] == 1

    def test_export_prompts_success(self, client: TestClient) -> None:
        """Test successful export of all prompts."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.export_all.return_value = {
                "exported_at": "2025-12-23T12:00:00Z",
                "version": "1.0",
                "prompts": {
                    "nemotron": {"system_prompt": "Test"},
                    "florence2": {"system_prompt": "Florence"},
                },
            }
            mock_storage.return_value = mock_storage_instance

            response = client.get("/api/ai-audit/prompts/export")

            assert response.status_code == 200
            data = response.json()
            assert "exported_at" in data
            assert data["version"] == "1.0"
            assert "nemotron" in data["prompts"]
            assert "florence2" in data["prompts"]

    def test_import_prompts_success(self, client: TestClient) -> None:
        """Test successful import of prompts."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.validate_config.return_value = []
            mock_storage_instance.import_configs.return_value = {
                "imported": "nemotron, florence2",
                "skipped": "none",
                "errors": "none",
            }
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/import",
                json={
                    "prompts": {
                        "nemotron": {"system_prompt": "Test"},
                        "florence2": {"system_prompt": "Florence"},
                    },
                    "overwrite": False,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["imported_count"] == 2
            assert data["skipped_count"] == 0
            assert len(data["errors"]) == 0

    def test_import_prompts_no_prompts(self, client: TestClient) -> None:
        """Test 400 when no prompts provided for import."""
        response = client.post(
            "/api/ai-audit/prompts/import",
            json={"prompts": {}, "overwrite": False},
        )

        assert response.status_code == 400
        assert "No prompts provided" in response.json()["detail"]

    def test_import_prompts_with_validation_errors(self, client: TestClient) -> None:
        """Test import with validation errors."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.validate_config.return_value = ["Invalid field X"]
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/import",
                json={
                    "prompts": {"nemotron": {"invalid": "config"}},
                    "overwrite": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["imported_count"] == 0
            assert len(data["errors"]) > 0

    def test_import_prompts_unsupported_model(self, client: TestClient) -> None:
        """Test import with unsupported model name."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.validate_config.return_value = []
            mock_storage_instance.import_configs.return_value = {
                "imported": "none",
                "skipped": "none",
                "errors": "none",
            }
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/import",
                json={
                    "prompts": {"unsupported_model": {"system_prompt": "Test"}},
                    "overwrite": False,
                },
            )

            assert response.status_code == 200
            data = response.json()
            # Should have validation error for unsupported model (added during validation phase)
            assert data["imported_count"] == 0
            assert len(data["errors"]) > 0
            assert any("unsupported_model" in err for err in data["errors"])

    def test_restore_prompt_version_success(self, client: TestClient) -> None:
        """Test successful restore of prompt version."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_old_version = MagicMock()
            mock_old_version.version = 2
            mock_storage_instance.get_version.return_value = mock_old_version

            mock_new_version = MagicMock()
            mock_new_version.version = 5
            mock_storage_instance.restore_version.return_value = mock_new_version
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/history/2?model=nemotron",
                json={"description": "Restored version 2"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["model_name"] == "nemotron"
            assert data["restored_version"] == 2
            assert data["new_version"] == 5

    def test_restore_prompt_version_not_found(self, client: TestClient) -> None:
        """Test 404 when restoring non-existent version."""
        with patch("backend.api.routes.ai_audit.get_prompt_storage") as mock_storage:
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_version.return_value = None
            mock_storage.return_value = mock_storage_instance

            response = client.post(
                "/api/ai-audit/prompts/history/999?model=nemotron",
                json={"description": "Restore missing"},
            )

            assert response.status_code == 404


class TestDatabaseBackedPromptConfigEndpoints:
    """Tests for database-backed prompt config endpoints."""

    def test_get_prompt_config_success(
        self, client: TestClient, mock_db_session: MagicMock
    ) -> None:
        """Test successful retrieval of database-backed prompt config."""
        # Create a proper mock with all required attributes
        mock_config = MagicMock()
        # Set attributes directly (not spec since that causes issues)
        mock_config.model = "nemotron"
        mock_config.system_prompt = "Test system prompt"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2048
        mock_config.version = 1
        mock_config.updated_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/ai-audit/prompt-config/nemotron")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        # FastAPI converts snake_case to camelCase in JSON responses
        assert data["systemPrompt"] == "Test system prompt"
        assert data["temperature"] == 0.7
        assert data["maxTokens"] == 2048
        assert data["version"] == 1

    def test_get_prompt_config_not_found(
        self, client: TestClient, mock_db_session: MagicMock
    ) -> None:
        """Test 404 when config not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/ai-audit/prompt-config/nemotron")

        assert response.status_code == 404
        assert "No configuration found" in response.json()["detail"]

    def test_get_prompt_config_invalid_model(self, client: TestClient) -> None:
        """Test 404 for invalid model name."""
        response = client.get("/api/ai-audit/prompt-config/invalid-model")
        assert response.status_code == 404

    def test_update_prompt_config_create_new(
        self, client: TestClient, mock_db_session: MagicMock
    ) -> None:
        """Test creating new prompt config."""
        # First query returns None (config doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def mock_refresh(obj):
            # Simulate refresh by updating attributes
            obj.model = "nemotron"
            obj.system_prompt = "New prompt"
            obj.temperature = 0.8
            obj.max_tokens = 1024
            obj.version = 1
            obj.updated_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "system_prompt": "New prompt",
                "temperature": 0.8,
                "max_tokens": 1024,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["version"] == 1
        # FastAPI converts snake_case to camelCase
        assert data["systemPrompt"] == "New prompt"
        assert data["maxTokens"] == 1024

    def test_update_prompt_config_update_existing(
        self, client: TestClient, mock_db_session: MagicMock
    ) -> None:
        """Test updating existing prompt config."""
        # Create mock with all attributes
        mock_config = MagicMock()
        mock_config.model = "nemotron"
        mock_config.system_prompt = "Old prompt"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 2048
        mock_config.version = 1
        mock_config.updated_at = datetime(2025, 12, 22, 12, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def mock_refresh(obj):
            # Simulate the actual update that happened in the route
            obj.system_prompt = "Updated prompt"
            obj.temperature = 0.9
            obj.max_tokens = 4096
            obj.version = 2
            obj.updated_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "system_prompt": "Updated prompt",
                "temperature": 0.9,
                "max_tokens": 4096,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["version"] == 2
        # FastAPI converts snake_case to camelCase
        assert data["systemPrompt"] == "Updated prompt"
        assert data["maxTokens"] == 4096
