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
    audit.has_yolo26 = True
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
        assert data["contributions"]["yolo26"] is True
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
                "yolo26": 1.0,
                "florence": 0.5,
                "clip": 0.3,
                "violence": 0.1,
            },
            "audits_by_day": [
                {"date": "2025-12-22", "day_of_week": "Sunday", "count": 40},
                {"date": "2025-12-23", "day_of_week": "Monday", "count": 35},
            ],
        }

        response = client.get("/api/ai-audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 100
        assert data["audited_events"] == 100
        assert data["fully_evaluated_events"] == 75
        assert data["avg_quality_score"] == 4.2
        assert data["model_contribution_rates"]["yolo26"] == 1.0
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
                "model_name": "yolo26",
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
        assert data["entries"][0]["model_name"] == "yolo26"
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
        assert contributions.yolo26 is False
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
            contributions=ModelContributions(yolo26=True, florence=True),
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
        assert response.contributions.yolo26 is True
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
            model_contribution_rates={"yolo26": 1.0},
            audits_by_day=[],
        )
        assert response.total_events == 100
        assert response.model_contribution_rates["yolo26"] == 1.0

    def test_model_leaderboard_entry(self) -> None:
        """Test ModelLeaderboardEntry creation."""
        entry = ModelLeaderboardEntry(
            model_name="yolo26",
            contribution_rate=0.95,
            quality_correlation=0.82,
            event_count=100,
        )
        assert entry.model_name == "yolo26"
        assert entry.contribution_rate == 0.95

    def test_leaderboard_response(self) -> None:
        """Test LeaderboardResponse creation."""
        response = LeaderboardResponse(
            entries=[
                ModelLeaderboardEntry(
                    model_name="yolo26",
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
        audit.has_yolo26 = True
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

        assert response.contributions.yolo26 is True
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


# Note: Prompt-related test classes have been moved to test_prompt_management.py
# following consolidation of prompt endpoints from ai_audit.py to prompt_management.py (NEM-2695)


class TestBatchAuditJobBackgroundTask:
    """Tests for _run_batch_audit_job background task function."""

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_success(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test successful batch audit job execution."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        # Create test events
        event_ids = [1, 2, 3]
        job_id = mock_job_tracker.create_job("batch_audit")

        # Mock event and audit data
        mock_event1 = create_mock_event(event_id=1)
        mock_event2 = create_mock_event(event_id=2)
        mock_event3 = create_mock_event(event_id=3)

        mock_audit1 = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)
        mock_audit2 = create_mock_audit(audit_id=2, event_id=2, is_evaluated=False)
        mock_audit3 = create_mock_audit(audit_id=3, event_id=3, is_evaluated=False)

        # Mock database session
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        # Setup execute returns for events and audits
        event_results = [mock_event1, mock_event2, mock_event3]
        audit_results = [mock_audit1, mock_audit2, mock_audit3]

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            # Check if it's an event query or audit query based on call order
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            # Alternate between event and audit queries
            if execute_side_effect.call_count % 2 == 1:
                # Event query
                idx = (execute_side_effect.call_count - 1) // 2
                result.scalar_one_or_none.return_value = event_results[idx]
            else:
                # Audit query
                idx = (execute_side_effect.call_count - 2) // 2
                result.scalar_one_or_none.return_value = audit_results[idx]

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = MagicMock()

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=False,
                    job_tracker=mock_job_tracker,
                )

        # Verify job tracker calls
        mock_job_tracker.start_job.assert_called_once()
        mock_job_tracker.complete_job.assert_called_once()

        # Verify the result - use kwargs for result parameter
        call_kwargs = mock_job_tracker.complete_job.call_args.kwargs
        completed_result = call_kwargs.get("result")
        assert completed_result is not None
        assert completed_result["total_events"] == 3
        assert completed_result["processed_events"] == 3
        assert completed_result["failed_events"] == 0

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_event_not_found(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job when event is not found."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1, 2]
        job_id = mock_job_tracker.create_job("batch_audit")

        mock_event1 = create_mock_event(event_id=1)
        mock_audit1 = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            # First event exists, second event is None
            if execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = mock_event1
            elif execute_side_effect.call_count == 2:
                result.scalar_one_or_none.return_value = mock_audit1
            elif execute_side_effect.call_count == 3:
                result.scalar_one_or_none.return_value = None  # Event not found
            else:
                result.scalar_one_or_none.return_value = None

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=False,
                    job_tracker=mock_job_tracker,
                )

        # Verify result includes failed event
        call_kwargs = mock_job_tracker.complete_job.call_args.kwargs
        completed_result = call_kwargs.get("result")
        assert completed_result is not None
        assert completed_result["total_events"] == 2
        assert completed_result["processed_events"] == 1
        assert completed_result["failed_events"] == 1

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_creates_partial_audit(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job creates partial audit when missing."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1]
        job_id = mock_job_tracker.create_job("batch_audit")

        mock_event = create_mock_event(event_id=1)
        mock_partial_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)

        mock_audit_service.create_partial_audit.return_value = mock_partial_audit

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            if execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = mock_event
            else:
                result.scalar_one_or_none.return_value = None  # No audit exists

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = MagicMock()

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=False,
                    job_tracker=mock_job_tracker,
                )

        # Verify partial audit was created
        mock_audit_service.create_partial_audit.assert_called_once()
        mock_session.add.assert_called_once_with(mock_partial_audit)
        mock_session.commit.assert_called()
        mock_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_skips_already_evaluated(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job skips already evaluated audits without force."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1]
        job_id = mock_job_tracker.create_job("batch_audit")

        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            if execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = mock_event
            else:
                result.scalar_one_or_none.return_value = mock_audit

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=False,
                    job_tracker=mock_job_tracker,
                )

        # Verify run_full_evaluation was not called
        mock_audit_service.run_full_evaluation.assert_not_called()

        # Verify job completed successfully
        call_kwargs = mock_job_tracker.complete_job.call_args.kwargs
        completed_result = call_kwargs.get("result")
        assert completed_result is not None
        assert completed_result["processed_events"] == 1
        assert completed_result["failed_events"] == 0

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_force_reevaluate(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job re-evaluates with force flag."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1]
        job_id = mock_job_tracker.create_job("batch_audit")

        mock_event = create_mock_event(event_id=1)
        mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            if execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = mock_event
            else:
                result.scalar_one_or_none.return_value = mock_audit

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=True,
                    job_tracker=mock_job_tracker,
                )

        # Verify run_full_evaluation was called even though already evaluated
        mock_audit_service.run_full_evaluation.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_handles_evaluation_error(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job handles errors during evaluation."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1, 2]
        job_id = mock_job_tracker.create_job("batch_audit")

        mock_event1 = create_mock_event(event_id=1)
        mock_event2 = create_mock_event(event_id=2)
        mock_audit1 = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)
        mock_audit2 = create_mock_audit(audit_id=2, event_id=2, is_evaluated=False)

        # Make evaluation fail for first event
        mock_audit_service.run_full_evaluation.side_effect = [
            Exception("Evaluation failed"),
            None,
        ]

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            if execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = mock_event1
            elif execute_side_effect.call_count == 2:
                result.scalar_one_or_none.return_value = mock_audit1
            elif execute_side_effect.call_count == 3:
                result.scalar_one_or_none.return_value = mock_event2
            else:
                result.scalar_one_or_none.return_value = mock_audit2

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=False,
                    job_tracker=mock_job_tracker,
                )

        # Verify result includes failed event
        call_kwargs = mock_job_tracker.complete_job.call_args.kwargs
        completed_result = call_kwargs.get("result")
        assert completed_result is not None
        assert completed_result["total_events"] == 2
        assert completed_result["processed_events"] == 1
        assert completed_result["failed_events"] == 1

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_handles_fatal_error(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job handles fatal errors and marks job as failed."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1]
        job_id = mock_job_tracker.create_job("batch_audit")

        # Make get_session raise an exception
        with patch(
            "backend.api.routes.ai_audit.get_session",
            side_effect=Exception("Database connection failed"),
        ):
            await _run_batch_audit_job(
                job_id=job_id,
                event_ids=event_ids,
                force_reevaluate=False,
                job_tracker=mock_job_tracker,
            )

        # Verify job was marked as failed
        mock_job_tracker.fail_job.assert_called_once()
        assert "Database connection failed" in mock_job_tracker.fail_job.call_args[0][1]

    @pytest.mark.asyncio
    async def test_run_batch_audit_job_updates_progress(
        self,
        mock_audit_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """Test batch audit job updates progress during execution."""
        from backend.api.routes.ai_audit import _run_batch_audit_job

        event_ids = [1, 2, 3]
        job_id = mock_job_tracker.create_job("batch_audit")

        mock_event1 = create_mock_event(event_id=1)
        mock_event2 = create_mock_event(event_id=2)
        mock_event3 = create_mock_event(event_id=3)

        mock_audit1 = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)
        mock_audit2 = create_mock_audit(audit_id=2, event_id=2, is_evaluated=False)
        mock_audit3 = create_mock_audit(audit_id=3, event_id=3, is_evaluated=False)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            event_results = [mock_event1, mock_event2, mock_event3]
            audit_results = [mock_audit1, mock_audit2, mock_audit3]

            if execute_side_effect.call_count % 2 == 1:
                idx = (execute_side_effect.call_count - 1) // 2
                result.scalar_one_or_none.return_value = event_results[idx]
            else:
                idx = (execute_side_effect.call_count - 2) // 2
                result.scalar_one_or_none.return_value = audit_results[idx]

            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session):
            with patch(
                "backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service
            ):
                await _run_batch_audit_job(
                    job_id=job_id,
                    event_ids=event_ids,
                    force_reevaluate=False,
                    job_tracker=mock_job_tracker,
                )

        # Verify progress updates
        assert mock_job_tracker.update_progress.call_count >= 3
        # Check that progress was updated with correct percentages
        progress_calls = [call[0][1] for call in mock_job_tracker.update_progress.call_args_list]
        assert 0 in progress_calls  # 0/3 = 0%
        assert 33 in progress_calls  # 1/3 = 33%
        assert 66 in progress_calls  # 2/3 = 66%


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
