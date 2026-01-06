"""Unit tests for AI audit service (audit_service.py).

These tests cover the AuditService class which handles AI audit evaluations
with LLM integration (Nemotron). Tests use mocked database sessions and
LLM responses - no real database or LLM connection required.

For integration tests with a real database, see backend/tests/integration/
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.services.audit_service import (
    MODEL_NAMES,
    AuditService,
    get_audit_service,
    reset_audit_service,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def audit_service() -> AuditService:
    """Create a fresh AuditService instance for testing."""
    reset_audit_service()
    return AuditService()


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_audit_service()
    yield
    reset_audit_service()


@pytest.fixture
def mock_db_session():
    """Create a mock database session with spec to prevent mocking non-existent attributes."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.execute = AsyncMock()
    return mock_session


@pytest.fixture
def sample_event() -> Event:
    """Create a sample Event for testing."""
    return Event(
        id=1,
        batch_id="batch_123",
        camera_id="front_door",
        started_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
        ended_at=datetime(2025, 12, 23, 14, 31, 0, tzinfo=UTC),
        risk_score=75,
        risk_level="high",
        summary="Person detected at front door",
        reasoning="Unusual activity at late night hours near entry point",
        llm_prompt="<|im_start|>system\nYou are a security AI...",
        reviewed=False,
    )


@pytest.fixture
def sample_event_no_prompt() -> Event:
    """Create a sample Event without an llm_prompt."""
    return Event(
        id=2,
        batch_id="batch_456",
        camera_id="backyard",
        started_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
        risk_score=50,
        risk_level="medium",
        summary="Motion detected",
        reasoning="Standard activity",
        llm_prompt=None,
        reviewed=False,
    )


@dataclass
class MockEnrichedContext:
    """Mock EnrichedContext for testing."""

    camera_name: str = "Front Door Camera"
    camera_id: str = "front_door"
    zones: list[Any] = field(default_factory=list)
    baselines: Any = None
    recent_events: list[Any] = field(default_factory=list)
    cross_camera: list[Any] = field(default_factory=list)


@dataclass
class MockEnrichmentResult:
    """Mock EnrichmentResult for testing."""

    has_vision_extraction: bool = False
    person_reid_matches: dict[str, Any] = field(default_factory=dict)
    vehicle_reid_matches: dict[str, Any] = field(default_factory=dict)
    has_violence: bool = False
    has_clothing_classifications: bool = False
    has_vehicle_classifications: bool = False
    has_vehicle_damage: bool = False
    has_pet_classifications: bool = False
    weather_classification: Any = None
    has_image_quality: bool = False


# =============================================================================
# Test: Singleton Pattern
# =============================================================================


class TestSingletonPattern:
    """Tests for the singleton pattern."""

    def test_get_audit_service_returns_instance(self):
        """Test get_audit_service returns an AuditService instance."""
        service = get_audit_service()
        assert isinstance(service, AuditService)

    def test_get_audit_service_returns_same_instance(self):
        """Test get_audit_service returns the same instance on repeated calls."""
        service1 = get_audit_service()
        service2 = get_audit_service()
        assert service1 is service2

    def test_reset_audit_service(self):
        """Test reset_audit_service creates a new instance on next call."""
        service1 = get_audit_service()
        reset_audit_service()
        service2 = get_audit_service()
        assert service1 is not service2


# =============================================================================
# Test: create_partial_audit
# =============================================================================


class TestCreatePartialAudit:
    """Tests for create_partial_audit method."""

    def test_create_partial_audit_with_all_enrichments(self, audit_service):
        """Test creating an audit with all model contributions active."""
        # Create rich context and result
        context = MockEnrichedContext(
            zones=[{"zone_id": "z1", "zone_name": "Entry Point"}],
            baselines={"hour_of_day": 14},
            cross_camera=[{"camera_id": "cam2"}],
        )
        result = MockEnrichmentResult(
            has_vision_extraction=True,
            person_reid_matches={"person1": [{"similarity": 0.9}]},
            vehicle_reid_matches={"vehicle1": [{"similarity": 0.85}]},
            has_violence=True,
            has_clothing_classifications=True,
            has_vehicle_classifications=True,
            has_vehicle_damage=True,
            has_pet_classifications=True,
            weather_classification={"condition": "clear"},
            has_image_quality=True,
        )

        llm_prompt = "This is a test prompt with 100 characters " * 10

        audit = audit_service.create_partial_audit(
            event_id=1,
            llm_prompt=llm_prompt,
            enriched_context=context,
            enrichment_result=result,
        )

        # Verify basic fields
        assert audit.event_id == 1
        assert audit.audited_at is not None

        # Verify all model contribution flags
        assert audit.has_rtdetr is True  # Always true
        assert audit.has_florence is True
        assert audit.has_clip is True
        assert audit.has_violence is True
        assert audit.has_clothing is True
        assert audit.has_vehicle is True
        assert audit.has_pet is True
        assert audit.has_weather is True
        assert audit.has_image_quality is True
        assert audit.has_zones is True
        assert audit.has_baseline is True
        assert audit.has_cross_camera is True

        # Verify prompt metrics
        assert audit.prompt_length == len(llm_prompt)
        assert audit.prompt_token_estimate == len(llm_prompt) // 4

        # Verify utilization (all 12 models)
        assert audit.enrichment_utilization == 1.0

    def test_create_partial_audit_with_no_enrichments(self, audit_service):
        """Test creating an audit with minimal enrichments."""
        audit = audit_service.create_partial_audit(
            event_id=2,
            llm_prompt="Short prompt",
            enriched_context=None,
            enrichment_result=None,
        )

        # Only rtdetr should be true
        assert audit.has_rtdetr is True
        assert audit.has_florence is False
        assert audit.has_clip is False
        assert audit.has_violence is False
        assert audit.has_clothing is False
        assert audit.has_vehicle is False
        assert audit.has_pet is False
        assert audit.has_weather is False
        assert audit.has_image_quality is False
        assert audit.has_zones is False
        assert audit.has_baseline is False
        assert audit.has_cross_camera is False

        # Utilization should be 1/12 (only rtdetr)
        assert audit.enrichment_utilization == pytest.approx(1 / 12)

    def test_create_partial_audit_with_none_prompt(self, audit_service):
        """Test creating an audit with no LLM prompt."""
        audit = audit_service.create_partial_audit(
            event_id=3,
            llm_prompt=None,
            enriched_context=None,
            enrichment_result=None,
        )

        assert audit.prompt_length == 0
        assert audit.prompt_token_estimate == 0

    def test_create_partial_audit_with_partial_enrichments(self, audit_service):
        """Test creating an audit with some enrichments."""
        context = MockEnrichedContext(
            zones=[{"zone_id": "z1"}],
            baselines=None,
            cross_camera=None,  # Use None instead of [] to not trigger has_cross_camera
        )
        result = MockEnrichmentResult(
            has_vision_extraction=True,
            has_violence=False,
            has_clothing_classifications=True,
            has_pet_classifications=False,
        )

        audit = audit_service.create_partial_audit(
            event_id=4,
            llm_prompt="Test prompt",
            enriched_context=context,
            enrichment_result=result,
        )

        # Check specific flags
        assert audit.has_rtdetr is True
        assert audit.has_florence is True
        assert audit.has_clothing is True
        assert audit.has_zones is True
        assert audit.has_violence is False
        assert audit.has_pet is False
        assert audit.has_baseline is False
        assert audit.has_cross_camera is False

        # 4 models out of 12: rtdetr, florence, clothing, zones
        assert audit.enrichment_utilization == pytest.approx(4 / 12)


# =============================================================================
# Test: Token Estimation
# =============================================================================


class TestTokenEstimation:
    """Tests for token estimation algorithm."""

    def test_estimate_tokens_empty_text(self, audit_service):
        """Test token estimation with empty text."""
        assert audit_service._estimate_tokens(None) == 0
        assert audit_service._estimate_tokens("") == 0

    def test_estimate_tokens_short_text(self, audit_service):
        """Test token estimation with short text."""
        text = "Hello world"  # 11 characters
        assert audit_service._estimate_tokens(text) == 11 // 4  # = 2

    def test_estimate_tokens_long_text(self, audit_service):
        """Test token estimation with longer text."""
        text = "a" * 1000
        assert audit_service._estimate_tokens(text) == 250

    def test_estimate_tokens_unicode(self, audit_service):
        """Test token estimation with unicode characters."""
        text = "Hello"  # 6 chars with emoji
        # Emoji is multiple bytes, but len() counts unicode chars
        assert audit_service._estimate_tokens(text) == len(text) // 4


# =============================================================================
# Test: Utilization Calculation
# =============================================================================


class TestUtilizationCalculation:
    """Tests for enrichment utilization calculation."""

    def test_calc_utilization_none_inputs(self, audit_service):
        """Test utilization with None inputs."""
        util = audit_service._calc_utilization(None, None)
        # Only rtdetr counts (always true)
        assert util == pytest.approx(1 / 12)

    def test_calc_utilization_full_enrichment(self, audit_service):
        """Test utilization with full enrichment."""
        context = MockEnrichedContext(
            zones=[{"z1": True}],
            baselines={"hour": 14},
            cross_camera=[{"cam2": True}],
        )
        result = MockEnrichmentResult(
            has_vision_extraction=True,
            person_reid_matches={"p1": []},
            vehicle_reid_matches={"v1": []},
            has_violence=True,
            has_clothing_classifications=True,
            has_vehicle_classifications=True,
            has_vehicle_damage=True,
            has_pet_classifications=True,
            weather_classification={"clear": True},
            has_image_quality=True,
        )

        util = audit_service._calc_utilization(context, result)
        assert util == 1.0

    def test_calc_utilization_half_enrichment(self, audit_service):
        """Test utilization with approximately half enrichments."""
        context = MockEnrichedContext(
            zones=[{"z1": True}],
            baselines={"hour": 14},
            cross_camera=None,  # Use None instead of [] to not trigger has_cross_camera
        )
        result = MockEnrichmentResult(
            has_vision_extraction=True,
            person_reid_matches={"p1": []},
            has_violence=True,
            has_clothing_classifications=False,
        )

        util = audit_service._calc_utilization(context, result)
        # rtdetr(1) + florence(1) + clip(1) + violence(1) + zones(1) + baseline(1) = 6
        assert util == pytest.approx(6 / 12)


# =============================================================================
# Test: Model Contribution Flags
# =============================================================================


class TestModelContributionFlags:
    """Tests for individual model contribution flag methods."""

    def test_has_florence(self, audit_service):
        """Test Florence detection flag."""
        result_with = MockEnrichmentResult(has_vision_extraction=True)
        result_without = MockEnrichmentResult(has_vision_extraction=False)

        assert audit_service._has_florence(result_with) is True
        assert audit_service._has_florence(result_without) is False
        assert audit_service._has_florence(None) is False

    def test_has_clip(self, audit_service):
        """Test CLIP re-identification flag."""
        result_with_person = MockEnrichmentResult(person_reid_matches={"p1": [{"similarity": 0.9}]})
        result_with_vehicle = MockEnrichmentResult(
            vehicle_reid_matches={"v1": [{"similarity": 0.8}]}
        )
        result_without = MockEnrichmentResult()

        assert audit_service._has_clip(result_with_person) is True
        assert audit_service._has_clip(result_with_vehicle) is True
        assert audit_service._has_clip(result_without) is False
        assert audit_service._has_clip(None) is False

    def test_has_violence(self, audit_service):
        """Test violence detection flag."""
        result_with = MockEnrichmentResult(has_violence=True)
        result_without = MockEnrichmentResult(has_violence=False)

        assert audit_service._has_violence(result_with) is True
        assert audit_service._has_violence(result_without) is False
        assert audit_service._has_violence(None) is False

    def test_has_zones(self, audit_service):
        """Test zones context flag."""
        context_with = MockEnrichedContext(zones=[{"z1": True}])
        context_without = MockEnrichedContext(zones=[])

        assert audit_service._has_zones(context_with) is True
        assert audit_service._has_zones(context_without) is False
        assert audit_service._has_zones(None) is False

    def test_has_baseline(self, audit_service):
        """Test baseline context flag."""
        context_with = MockEnrichedContext(baselines={"hour": 14})
        context_without = MockEnrichedContext(baselines=None)

        assert audit_service._has_baseline(context_with) is True
        assert audit_service._has_baseline(context_without) is False
        assert audit_service._has_baseline(None) is False

    def test_has_cross_camera(self, audit_service):
        """Test cross-camera context flag."""
        context_with = MockEnrichedContext(cross_camera=[{"cam2": True}])
        context_without = MockEnrichedContext(cross_camera=None)

        assert audit_service._has_cross_camera(context_with) is True
        assert audit_service._has_cross_camera(context_without) is False
        assert audit_service._has_cross_camera(None) is False


# =============================================================================
# Test: persist_record
# =============================================================================


class TestPersistRecord:
    """Tests for persist_record method."""

    @pytest.mark.asyncio
    async def test_persist_record_success(self, audit_service, mock_db_session):
        """Test successful persistence of audit record."""
        audit = EventAudit(
            event_id=1,
            audited_at=datetime.now(UTC),
            has_rtdetr=True,
        )

        result = await audit_service.persist_record(audit, mock_db_session)

        mock_db_session.add.assert_called_once_with(audit)
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once_with(audit)
        assert result is audit

    @pytest.mark.asyncio
    async def test_persist_record_db_error(self, audit_service, mock_db_session):
        """Test handling of database error during persistence."""
        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))
        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await audit_service.persist_record(audit, mock_db_session)


# =============================================================================
# Test: run_full_evaluation
# =============================================================================


class TestRunFullEvaluation:
    """Tests for run_full_evaluation method."""

    @pytest.mark.asyncio
    async def test_run_full_evaluation_no_llm_prompt(
        self, audit_service, mock_db_session, sample_event_no_prompt
    ):
        """Test run_full_evaluation returns early when event has no llm_prompt."""
        audit = EventAudit(event_id=2, audited_at=datetime.now(UTC))

        result = await audit_service.run_full_evaluation(
            audit, sample_event_no_prompt, mock_db_session
        )

        # Should return audit unchanged (no LLM calls made)
        assert result is audit
        # No commit should have been called
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_full_evaluation_success(self, audit_service, mock_db_session, sample_event):
        """Test successful full evaluation with all 4 modes."""
        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))

        # Mock all 4 evaluation methods
        with (
            patch.object(
                audit_service,
                "_run_self_critique",
                new_callable=AsyncMock,
                return_value="Good analysis overall, but could improve context usage.",
            ),
            patch.object(
                audit_service,
                "_run_rubric_eval",
                new_callable=AsyncMock,
                return_value={
                    "context_usage": 4.0,
                    "reasoning_coherence": 4.5,
                    "risk_justification": 3.5,
                    "actionability": 4.0,
                },
            ),
            patch.object(
                audit_service,
                "_run_consistency_check",
                new_callable=AsyncMock,
                return_value={"risk_score": 70, "risk_level": "high"},
            ),
            patch.object(
                audit_service,
                "_run_prompt_improvement",
                new_callable=AsyncMock,
                return_value={
                    "missing_context": ["time since last motion"],
                    "confusing_sections": [],
                    "unused_data": ["weather data"],
                    "format_suggestions": ["add more structure"],
                    "model_gaps": ["face detection"],
                },
            ),
        ):
            result = await audit_service.run_full_evaluation(audit, sample_event, mock_db_session)

        # Verify self-critique (Mode 1)
        assert (
            result.self_eval_critique == "Good analysis overall, but could improve context usage."
        )

        # Verify rubric scores (Mode 2)
        assert result.context_usage_score == 4.0
        assert result.reasoning_coherence_score == 4.5
        assert result.risk_justification_score == 3.5
        # Overall quality = average of 4 scores: (4.0 + 4.5 + 3.5 + 4.0) / 4 = 4.0
        assert result.overall_quality_score == 4.0

        # Verify consistency check (Mode 3)
        assert result.consistency_risk_score == 70
        # Consistency diff = |70 - 75| = 5
        assert result.consistency_diff == 5
        # Consistency score = max(1.0, 5.0 - (5 / 5)) = max(1.0, 4.0) = 4.0
        assert result.consistency_score == 4.0

        # Verify prompt improvement (Mode 4)
        assert json.loads(result.missing_context) == ["time since last motion"]
        assert json.loads(result.confusing_sections) == []
        assert json.loads(result.unused_data) == ["weather data"]
        assert json.loads(result.format_suggestions) == ["add more structure"]
        assert json.loads(result.model_gaps) == ["face detection"]

        # Verify self_eval_prompt was stored
        assert result.self_eval_prompt is not None

        # Verify database operations
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once_with(audit)

    @pytest.mark.asyncio
    async def test_run_full_evaluation_consistency_score_calculation(
        self, audit_service, mock_db_session, sample_event
    ):
        """Test consistency score calculation for various diffs."""
        test_cases = [
            # (consistency_risk_score, event_risk_score, expected_diff, expected_score)
            (75, 75, 0, 5.0),  # Perfect match
            (70, 75, 5, 4.0),  # Small diff
            (65, 75, 10, 3.0),  # Moderate diff
            (55, 75, 20, 1.0),  # Large diff (clamped to 1.0)
            (45, 75, 30, 1.0),  # Very large diff (clamped to 1.0)
        ]

        for cons_score, event_score, expected_diff, expected_cons_score in test_cases:
            audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))
            sample_event.risk_score = event_score

            with (
                patch.object(
                    audit_service, "_run_self_critique", new_callable=AsyncMock, return_value=""
                ),
                patch.object(
                    audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value={}
                ),
                patch.object(
                    audit_service,
                    "_run_consistency_check",
                    new_callable=AsyncMock,
                    return_value={"risk_score": cons_score},
                ),
                patch.object(
                    audit_service,
                    "_run_prompt_improvement",
                    new_callable=AsyncMock,
                    return_value={},
                ),
            ):
                result = await audit_service.run_full_evaluation(
                    audit, sample_event, mock_db_session
                )

            assert result.consistency_diff == expected_diff, (
                f"For cons_score={cons_score}, event_score={event_score}"
            )
            assert result.consistency_score == expected_cons_score, (
                f"For cons_score={cons_score}, event_score={event_score}"
            )


# =============================================================================
# Test: _call_llm
# =============================================================================


class TestCallLLM:
    """Tests for _call_llm method."""

    @pytest.mark.asyncio
    async def test_call_llm_success(self, audit_service):
        """Test successful LLM call."""
        mock_response = {"content": "This is the LLM response."}

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            result = await audit_service._call_llm("Test prompt")

        assert result == "This is the LLM response."
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_llm_timeout(self, audit_service):
        """Test LLM call handles timeout."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(httpx.TimeoutException):
                await audit_service._call_llm("Test prompt")

    @pytest.mark.asyncio
    async def test_call_llm_connection_error(self, audit_service):
        """Test LLM call handles connection error."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(httpx.ConnectError):
                await audit_service._call_llm("Test prompt")

    @pytest.mark.asyncio
    async def test_call_llm_http_error(self, audit_service):
        """Test LLM call handles HTTP error."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(spec=httpx.Request),
                response=mock_resp,
            )
            mock_post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                await audit_service._call_llm("Test prompt")


# =============================================================================
# Test: _run_self_critique (Mode 1)
# =============================================================================


class TestRunSelfCritique:
    """Tests for _run_self_critique method (Mode 1)."""

    @pytest.mark.asyncio
    async def test_run_self_critique_success(self, audit_service, sample_event):
        """Test successful self-critique."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            return_value="The analysis was thorough but missed some context.",
        ):
            result = await audit_service._run_self_critique(sample_event)

        assert result == "The analysis was thorough but missed some context."

    @pytest.mark.asyncio
    async def test_run_self_critique_failure(self, audit_service, sample_event):
        """Test self-critique handles LLM failure gracefully."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("LLM unavailable"),
        ):
            result = await audit_service._run_self_critique(sample_event)

        assert "network error" in result.lower()
        assert "LLM unavailable" in result


# =============================================================================
# Test: _run_rubric_eval (Mode 2)
# =============================================================================


class TestRunRubricEval:
    """Tests for _run_rubric_eval method (Mode 2)."""

    @pytest.mark.asyncio
    async def test_run_rubric_eval_success(self, audit_service, sample_event):
        """Test successful rubric evaluation."""
        llm_response = json.dumps(
            {
                "context_usage": 4,
                "reasoning_coherence": 5,
                "risk_justification": 3,
                "actionability": 4,
                "explanation": "Overall good analysis.",
            }
        )

        with patch.object(
            audit_service, "_call_llm", new_callable=AsyncMock, return_value=llm_response
        ):
            result = await audit_service._run_rubric_eval(sample_event)

        assert result["context_usage"] == 4
        assert result["reasoning_coherence"] == 5
        assert result["risk_justification"] == 3
        assert result["actionability"] == 4

    @pytest.mark.asyncio
    async def test_run_rubric_eval_invalid_json(self, audit_service, sample_event):
        """Test rubric evaluation handles invalid JSON."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            return_value="This is not valid JSON at all.",
        ):
            result = await audit_service._run_rubric_eval(sample_event)

        assert result == {}

    @pytest.mark.asyncio
    async def test_run_rubric_eval_llm_failure(self, audit_service, sample_event):
        """Test rubric evaluation handles LLM failure."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await audit_service._run_rubric_eval(sample_event)

        assert result == {}


# =============================================================================
# Test: _run_consistency_check (Mode 3)
# =============================================================================


class TestRunConsistencyCheck:
    """Tests for _run_consistency_check method (Mode 3)."""

    @pytest.mark.asyncio
    async def test_run_consistency_check_success(self, audit_service, sample_event):
        """Test successful consistency check."""
        llm_response = json.dumps(
            {
                "risk_score": 72,
                "risk_level": "high",
                "brief_reason": "Similar assessment to original.",
            }
        )

        with patch.object(
            audit_service, "_call_llm", new_callable=AsyncMock, return_value=llm_response
        ):
            result = await audit_service._run_consistency_check(sample_event)

        assert result["risk_score"] == 72
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_run_consistency_check_strips_assistant_tag(self, audit_service, sample_event):
        """Test consistency check properly strips assistant tag from original prompt."""
        sample_event.llm_prompt = "System prompt here<|im_start|>assistant\nPrevious response"
        llm_response = json.dumps({"risk_score": 70, "risk_level": "high"})

        call_args_captured = []

        async def capture_call_llm(prompt):
            call_args_captured.append(prompt)
            return llm_response

        with patch.object(audit_service, "_call_llm", side_effect=capture_call_llm):
            await audit_service._run_consistency_check(sample_event)

        # Verify the original assistant response was stripped from the prompt
        # The CONSISTENCY_CHECK_PROMPT template adds its own <|im_start|>assistant tag
        # but the content from the original prompt's assistant section should be gone
        assert "Previous response" not in call_args_captured[0]
        assert "System prompt here" in call_args_captured[0]

    @pytest.mark.asyncio
    async def test_run_consistency_check_invalid_json(self, audit_service, sample_event):
        """Test consistency check handles invalid JSON."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            return_value="No JSON here",
        ):
            result = await audit_service._run_consistency_check(sample_event)

        assert result == {}

    @pytest.mark.asyncio
    async def test_run_consistency_check_llm_failure(self, audit_service, sample_event):
        """Test consistency check handles LLM failure."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("LLM timeout"),
        ):
            result = await audit_service._run_consistency_check(sample_event)

        assert result == {}


# =============================================================================
# Test: _run_prompt_improvement (Mode 4)
# =============================================================================


class TestRunPromptImprovement:
    """Tests for _run_prompt_improvement method (Mode 4)."""

    @pytest.mark.asyncio
    async def test_run_prompt_improvement_success(self, audit_service, sample_event):
        """Test successful prompt improvement suggestions."""
        llm_response = json.dumps(
            {
                "missing_context": ["historical activity patterns", "time since last motion"],
                "confusing_sections": ["zone descriptions could be clearer"],
                "unused_data": ["weather information"],
                "format_suggestions": ["use bullet points for detections"],
                "model_gaps": ["face detection", "pose estimation"],
            }
        )

        with patch.object(
            audit_service, "_call_llm", new_callable=AsyncMock, return_value=llm_response
        ):
            result = await audit_service._run_prompt_improvement(sample_event)

        assert len(result["missing_context"]) == 2
        assert "historical activity patterns" in result["missing_context"]
        assert len(result["model_gaps"]) == 2

    @pytest.mark.asyncio
    async def test_run_prompt_improvement_invalid_json(self, audit_service, sample_event):
        """Test prompt improvement handles invalid JSON."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            return_value="Not valid JSON",
        ):
            result = await audit_service._run_prompt_improvement(sample_event)

        assert result == {}

    @pytest.mark.asyncio
    async def test_run_prompt_improvement_llm_failure(self, audit_service, sample_event):
        """Test prompt improvement handles LLM failure."""
        with patch.object(
            audit_service,
            "_call_llm",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Timeout"),
        ):
            result = await audit_service._run_prompt_improvement(sample_event)

        assert result == {}


# =============================================================================
# Test: get_stats
# =============================================================================


class TestGetStats:
    """Tests for get_stats method."""

    def _create_mock_audit(
        self,
        event_id: int,
        audited_at: datetime,
        overall_score: float | None = None,
        consistency_score: float | None = None,
        utilization: float = 0.5,
        **model_flags,
    ) -> EventAudit:
        """Helper to create mock audit records."""
        audit = EventAudit(
            id=event_id,
            event_id=event_id,
            audited_at=audited_at,
            overall_quality_score=overall_score,
            consistency_score=consistency_score,
            enrichment_utilization=utilization,
            has_rtdetr=True,
        )
        for flag, value in model_flags.items():
            setattr(audit, flag, value)
        return audit

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, audit_service, mock_db_session):
        """Test get_stats with no audit records."""
        # Mock execute to return empty list
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        stats = await audit_service.get_stats(mock_db_session, days=7)

        assert stats["total_events"] == 0
        assert stats["audited_events"] == 0
        assert stats["fully_evaluated_events"] == 0
        assert stats["avg_quality_score"] is None
        assert stats["avg_consistency_rate"] is None
        assert stats["avg_enrichment_utilization"] is None

        # All model contribution rates should be 0
        for model in MODEL_NAMES:
            assert stats["model_contribution_rates"][model] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_audits(self, audit_service, mock_db_session):
        """Test get_stats with audit records."""
        now = datetime.now(UTC)
        audits = [
            self._create_mock_audit(
                1,
                now - timedelta(days=1),
                overall_score=4.0,
                consistency_score=4.5,
                utilization=0.8,
                has_florence=True,
                has_clip=True,
            ),
            self._create_mock_audit(
                2,
                now - timedelta(days=2),
                overall_score=3.5,
                consistency_score=3.0,
                utilization=0.6,
                has_florence=True,
            ),
            self._create_mock_audit(
                3,
                now - timedelta(days=3),
                overall_score=None,  # Not fully evaluated
                consistency_score=None,
                utilization=0.4,
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = audits
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        stats = await audit_service.get_stats(mock_db_session, days=7)

        assert stats["total_events"] == 3
        assert stats["audited_events"] == 3
        assert stats["fully_evaluated_events"] == 2  # Only 2 have overall_quality_score

        # Average quality = (4.0 + 3.5) / 2 = 3.75
        assert stats["avg_quality_score"] == pytest.approx(3.75)

        # Average consistency = (4.5 + 3.0) / 2 = 3.75
        assert stats["avg_consistency_rate"] == pytest.approx(3.75)

        # Average utilization = (0.8 + 0.6 + 0.4) / 3 = 0.6
        assert stats["avg_enrichment_utilization"] == pytest.approx(0.6)

        # Model contribution rates
        # rtdetr: 3/3 = 1.0
        assert stats["model_contribution_rates"]["rtdetr"] == pytest.approx(1.0)
        # florence: 2/3 = 0.666...
        assert stats["model_contribution_rates"]["florence"] == pytest.approx(2 / 3)
        # clip: 1/3 = 0.333...
        assert stats["model_contribution_rates"]["clip"] == pytest.approx(1 / 3)

    @pytest.mark.asyncio
    async def test_get_stats_with_camera_filter(self, audit_service, mock_db_session):
        """Test get_stats filters by camera_id."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        stats = await audit_service.get_stats(mock_db_session, days=7, camera_id="front_door")

        # Verify execute was called (query should include camera filter)
        mock_db_session.execute.assert_awaited_once()
        assert stats["total_events"] == 0


# =============================================================================
# Test: get_leaderboard
# =============================================================================


class TestGetLeaderboard:
    """Tests for get_leaderboard method."""

    @pytest.mark.asyncio
    async def test_get_leaderboard_empty(self, audit_service, mock_db_session):
        """Test leaderboard with no audit records."""
        # Mock get_stats to return empty stats
        with patch.object(
            audit_service,
            "get_stats",
            new_callable=AsyncMock,
            return_value={
                "total_events": 0,
                "model_contribution_rates": dict.fromkeys(MODEL_NAMES, 0),
            },
        ):
            leaderboard = await audit_service.get_leaderboard(mock_db_session, days=7)

        assert len(leaderboard) == len(MODEL_NAMES)
        for entry in leaderboard:
            assert entry["contribution_rate"] == 0
            assert entry["event_count"] == 0

    @pytest.mark.asyncio
    async def test_get_leaderboard_sorted_by_contribution(self, audit_service, mock_db_session):
        """Test leaderboard is sorted by contribution rate descending."""
        contribution_rates = dict.fromkeys(MODEL_NAMES, 0.0)
        contribution_rates["rtdetr"] = 1.0
        contribution_rates["florence"] = 0.8
        contribution_rates["clip"] = 0.6
        contribution_rates["violence"] = 0.4

        with patch.object(
            audit_service,
            "get_stats",
            new_callable=AsyncMock,
            return_value={
                "total_events": 100,
                "model_contribution_rates": contribution_rates,
            },
        ):
            leaderboard = await audit_service.get_leaderboard(mock_db_session, days=7)

        # Verify sorted order
        assert leaderboard[0]["model_name"] == "rtdetr"
        assert leaderboard[0]["contribution_rate"] == 1.0
        assert leaderboard[0]["event_count"] == 100

        assert leaderboard[1]["model_name"] == "florence"
        assert leaderboard[1]["contribution_rate"] == 0.8
        assert leaderboard[1]["event_count"] == 80

        assert leaderboard[2]["model_name"] == "clip"
        assert leaderboard[2]["contribution_rate"] == 0.6
        assert leaderboard[2]["event_count"] == 60

    @pytest.mark.asyncio
    async def test_get_leaderboard_schema_compliance(self, audit_service, mock_db_session):
        """Test leaderboard entries match expected schema."""
        with patch.object(
            audit_service,
            "get_stats",
            new_callable=AsyncMock,
            return_value={
                "total_events": 50,
                "model_contribution_rates": dict.fromkeys(MODEL_NAMES, 0.5),
            },
        ):
            leaderboard = await audit_service.get_leaderboard(mock_db_session, days=7)

        for entry in leaderboard:
            assert "model_name" in entry
            assert "contribution_rate" in entry
            assert "quality_correlation" in entry
            assert "event_count" in entry
            assert entry["model_name"] in MODEL_NAMES


# =============================================================================
# Test: get_recommendations
# =============================================================================


class TestGetRecommendations:
    """Tests for get_recommendations method."""

    def _create_audit_with_suggestions(
        self,
        event_id: int,
        missing_context: list[str] | None = None,
        unused_data: list[str] | None = None,
        model_gaps: list[str] | None = None,
        format_suggestions: list[str] | None = None,
    ) -> EventAudit:
        """Helper to create audit with improvement suggestions."""
        audit = EventAudit(
            id=event_id,
            event_id=event_id,
            audited_at=datetime.now(UTC),
            overall_quality_score=4.0,  # Required to be included
        )
        if missing_context:
            audit.missing_context = json.dumps(missing_context)
        if unused_data:
            audit.unused_data = json.dumps(unused_data)
        if model_gaps:
            audit.model_gaps = json.dumps(model_gaps)
        if format_suggestions:
            audit.format_suggestions = json.dumps(format_suggestions)
        return audit

    @pytest.mark.asyncio
    async def test_get_recommendations_empty(self, audit_service, mock_db_session):
        """Test recommendations with no audit records."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        recommendations = await audit_service.get_recommendations(mock_db_session, days=7)

        assert recommendations == []

    @pytest.mark.asyncio
    async def test_get_recommendations_aggregates_suggestions(self, audit_service, mock_db_session):
        """Test recommendations aggregates suggestions across audits."""
        audits = [
            self._create_audit_with_suggestions(
                1,
                missing_context=["time since last motion", "historical patterns"],
                model_gaps=["face detection"],
            ),
            self._create_audit_with_suggestions(
                2,
                missing_context=["time since last motion"],  # Duplicate
                model_gaps=["face detection", "pose estimation"],
            ),
            self._create_audit_with_suggestions(
                3,
                missing_context=["time since last motion"],  # Another duplicate
                unused_data=["weather data"],
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = audits
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        recommendations = await audit_service.get_recommendations(mock_db_session, days=7)

        # Verify recommendations are present
        assert len(recommendations) > 0

        # Find the "time since last motion" recommendation
        time_rec = next(
            (r for r in recommendations if r["suggestion"] == "time since last motion"),
            None,
        )
        assert time_rec is not None
        assert time_rec["category"] == "missing_context"
        assert time_rec["frequency"] == 3  # Appeared in all 3 audits
        assert time_rec["priority"] == "high"  # 3/3 > 30%

        # Find face detection recommendation
        face_rec = next(
            (r for r in recommendations if r["suggestion"] == "face detection"),
            None,
        )
        assert face_rec is not None
        assert face_rec["category"] == "model_gaps"
        assert face_rec["frequency"] == 2

    @pytest.mark.asyncio
    async def test_get_recommendations_priority_levels(self, audit_service, mock_db_session):
        """Test recommendations priority levels are calculated correctly."""
        # Create 10 audits with varying frequencies
        audits = []
        for i in range(10):
            suggestions = []
            if i < 4:  # 40% frequency - high priority (> 30%)
                suggestions.append("high_freq_suggestion")
            if i < 2:  # 20% frequency - medium priority (> 10%)
                suggestions.append("medium_freq_suggestion")
            if i == 0:  # 10% frequency - low priority
                suggestions.append("low_freq_suggestion")
            audits.append(self._create_audit_with_suggestions(i, missing_context=suggestions))

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = audits
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        recommendations = await audit_service.get_recommendations(mock_db_session, days=7)

        # Find each recommendation
        high_rec = next(
            (r for r in recommendations if r["suggestion"] == "high_freq_suggestion"),
            None,
        )
        medium_rec = next(
            (r for r in recommendations if r["suggestion"] == "medium_freq_suggestion"),
            None,
        )
        low_rec = next(
            (r for r in recommendations if r["suggestion"] == "low_freq_suggestion"),
            None,
        )

        assert high_rec is not None
        assert high_rec["priority"] == "high"
        assert high_rec["frequency"] == 4

        assert medium_rec is not None
        assert medium_rec["priority"] == "medium"
        assert medium_rec["frequency"] == 2

        assert low_rec is not None
        assert low_rec["priority"] == "low"
        assert low_rec["frequency"] == 1

    @pytest.mark.asyncio
    async def test_get_recommendations_limits_to_20(self, audit_service, mock_db_session):
        """Test recommendations are limited to 20 entries."""
        # Create audits with many different suggestions
        suggestions = [f"suggestion_{i}" for i in range(30)]
        audits = [
            self._create_audit_with_suggestions(1, missing_context=suggestions),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = audits
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        recommendations = await audit_service.get_recommendations(mock_db_session, days=7)

        assert len(recommendations) <= 20

    @pytest.mark.asyncio
    async def test_get_recommendations_handles_invalid_json(self, audit_service, mock_db_session):
        """Test recommendations handles invalid JSON in suggestion fields."""
        audit = EventAudit(
            id=1,
            event_id=1,
            audited_at=datetime.now(UTC),
            overall_quality_score=4.0,
            missing_context="not valid json",  # Invalid JSON
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [audit]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        # Should not raise exception
        recommendations = await audit_service.get_recommendations(mock_db_session, days=7)

        # Should return empty (invalid JSON is skipped)
        assert recommendations == []


# =============================================================================
# Test: LLM Response Parsing with extract_json_from_llm_response
# =============================================================================


class TestLLMResponseParsing:
    """Tests for JSON parsing from LLM responses."""

    @pytest.mark.asyncio
    async def test_rubric_eval_parses_json_with_extra_text(self, audit_service, sample_event):
        """Test rubric eval handles JSON with surrounding text."""
        llm_response = """
        Based on my analysis, here are the scores:

        {
            "context_usage": 4,
            "reasoning_coherence": 5,
            "risk_justification": 3,
            "actionability": 4
        }

        Let me know if you need more details.
        """

        with patch.object(
            audit_service, "_call_llm", new_callable=AsyncMock, return_value=llm_response
        ):
            result = await audit_service._run_rubric_eval(sample_event)

        assert result["context_usage"] == 4
        assert result["reasoning_coherence"] == 5

    @pytest.mark.asyncio
    async def test_consistency_check_parses_json_with_markdown(self, audit_service, sample_event):
        """Test consistency check handles JSON in markdown code block."""
        llm_response = """
        ```json
        {
            "risk_score": 72,
            "risk_level": "high",
            "brief_reason": "Similar assessment"
        }
        ```
        """

        with patch.object(
            audit_service, "_call_llm", new_callable=AsyncMock, return_value=llm_response
        ):
            result = await audit_service._run_consistency_check(sample_event)

        assert result["risk_score"] == 72
        assert result["risk_level"] == "high"


# =============================================================================
# Test: MODEL_NAMES Constant
# =============================================================================


class TestModelNamesConstant:
    """Tests for the MODEL_NAMES constant."""

    def test_model_names_count(self):
        """Test MODEL_NAMES has expected number of models."""
        assert len(MODEL_NAMES) == 12

    def test_model_names_content(self):
        """Test MODEL_NAMES contains expected model names."""
        expected = [
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
        assert set(MODEL_NAMES) == set(expected)

    def test_model_names_match_audit_flags(self):
        """Test MODEL_NAMES match EventAudit flag attributes."""
        for model in MODEL_NAMES:
            attr_name = f"has_{model}"
            # Verify EventAudit has this attribute
            assert hasattr(EventAudit, attr_name), f"EventAudit missing attribute {attr_name}"


# =============================================================================
# Test: Integration with real LLM prompts
# =============================================================================


class TestPromptFormatting:
    """Tests for prompt formatting in evaluation methods."""

    @pytest.mark.asyncio
    async def test_self_critique_prompt_includes_event_data(self, audit_service, sample_event):
        """Test self-critique prompt includes all event data."""
        captured_prompt = None

        async def capture_prompt(prompt):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "Critique response"

        with patch.object(audit_service, "_call_llm", side_effect=capture_prompt):
            await audit_service._run_self_critique(sample_event)

        assert str(sample_event.risk_score) in captured_prompt
        assert sample_event.summary in captured_prompt
        assert sample_event.reasoning in captured_prompt

    @pytest.mark.asyncio
    async def test_rubric_eval_prompt_format(self, audit_service, sample_event):
        """Test rubric evaluation prompt format."""
        captured_prompt = None

        async def capture_prompt(prompt):
            nonlocal captured_prompt
            captured_prompt = prompt
            return '{"context_usage": 4, "reasoning_coherence": 4, "risk_justification": 4, "actionability": 4}'

        with patch.object(audit_service, "_call_llm", side_effect=capture_prompt):
            await audit_service._run_rubric_eval(sample_event)

        # Verify prompt contains expected elements
        assert "CONTEXT_USAGE" in captured_prompt
        assert "REASONING_COHERENCE" in captured_prompt
        assert "RISK_JUSTIFICATION" in captured_prompt
        assert "ACTIONABILITY" in captured_prompt
        assert "1-5 scale" in captured_prompt

    @pytest.mark.asyncio
    async def test_prompt_improvement_prompt_format(self, audit_service, sample_event):
        """Test prompt improvement suggestion prompt format."""
        captured_prompt = None

        async def capture_prompt(prompt):
            nonlocal captured_prompt
            captured_prompt = prompt
            return '{"missing_context": [], "confusing_sections": [], "unused_data": [], "format_suggestions": [], "model_gaps": []}'

        with patch.object(audit_service, "_call_llm", side_effect=capture_prompt):
            await audit_service._run_prompt_improvement(sample_event)

        # Verify prompt asks for 5 categories
        assert "MISSING_CONTEXT" in captured_prompt
        assert "CONFUSING_SECTIONS" in captured_prompt
        assert "UNUSED_DATA" in captured_prompt
        assert "FORMAT_SUGGESTIONS" in captured_prompt
        assert "MODEL_GAPS" in captured_prompt


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_create_partial_audit_with_empty_zones(self, audit_service):
        """Test creating audit with empty zones list."""
        context = MockEnrichedContext(zones=[])

        audit = audit_service.create_partial_audit(
            event_id=1,
            llm_prompt="Test",
            enriched_context=context,
            enrichment_result=None,
        )

        assert audit.has_zones is False

    def test_create_partial_audit_with_none_baselines(self, audit_service):
        """Test creating audit with None baselines."""
        context = MockEnrichedContext(baselines=None)

        audit = audit_service.create_partial_audit(
            event_id=1,
            llm_prompt="Test",
            enriched_context=context,
            enrichment_result=None,
        )

        assert audit.has_baseline is False

    @pytest.mark.asyncio
    async def test_run_full_evaluation_with_long_prompt(
        self, audit_service, mock_db_session, sample_event
    ):
        """Test full evaluation truncates long prompts in self_eval_prompt."""
        sample_event.llm_prompt = "A" * 1000  # Long prompt
        sample_event.reasoning = "B" * 500  # Long reasoning

        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))

        with (
            patch.object(
                audit_service, "_run_self_critique", new_callable=AsyncMock, return_value=""
            ),
            patch.object(
                audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service, "_run_consistency_check", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service, "_run_prompt_improvement", new_callable=AsyncMock, return_value={}
            ),
        ):
            result = await audit_service.run_full_evaluation(audit, sample_event, mock_db_session)

        # Verify truncation occurred - the service truncates llm_prompt to 500 chars
        # and reasoning to 300 chars, adding "..." suffix
        assert "..." in result.self_eval_prompt
        # The truncated prompt (500+...) + truncated reasoning (300+...) + template overhead
        # should still be significantly shorter than if it included the full 1000+500 chars
        assert "AAA" in result.self_eval_prompt  # Part of truncated prompt
        assert "BBB" in result.self_eval_prompt  # Part of truncated reasoning

    @pytest.mark.asyncio
    async def test_get_stats_handles_none_scores(self, audit_service, mock_db_session):
        """Test get_stats handles audits with all None scores."""
        audit = EventAudit(
            id=1,
            event_id=1,
            audited_at=datetime.now(UTC),
            overall_quality_score=None,
            consistency_score=None,
            enrichment_utilization=0.5,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [audit]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        stats = await audit_service.get_stats(mock_db_session, days=7)

        assert stats["total_events"] == 1
        assert stats["avg_quality_score"] is None
        assert stats["avg_consistency_rate"] is None
        assert stats["avg_enrichment_utilization"] == 0.5

    @pytest.mark.asyncio
    async def test_run_full_evaluation_with_none_risk_score(
        self, audit_service, mock_db_session, sample_event
    ):
        """Test full evaluation handles None risk_score in consistency calculation."""
        sample_event.risk_score = None
        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))

        with (
            patch.object(
                audit_service, "_run_self_critique", new_callable=AsyncMock, return_value=""
            ),
            patch.object(
                audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service,
                "_run_consistency_check",
                new_callable=AsyncMock,
                return_value={"risk_score": 70},
            ),
            patch.object(
                audit_service, "_run_prompt_improvement", new_callable=AsyncMock, return_value={}
            ),
        ):
            result = await audit_service.run_full_evaluation(audit, sample_event, mock_db_session)

        # Consistency diff should not be calculated when event.risk_score is None
        assert result.consistency_risk_score == 70
        assert result.consistency_diff is None
        assert result.consistency_score is None
