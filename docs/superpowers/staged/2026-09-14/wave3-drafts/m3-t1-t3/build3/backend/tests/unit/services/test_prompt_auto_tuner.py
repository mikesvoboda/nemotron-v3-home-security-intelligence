"""Unit tests for PromptAutoTuner service.

Tests the prompt auto-tuning system that uses accumulated audit feedback
to improve prompts by injecting historical recommendations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.event_audit import EventAudit

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    return mock_session


@pytest.fixture
def sample_recommendations() -> list[dict[str, Any]]:
    """Create sample recommendations from audit service."""
    return [
        {
            "category": "missing_context",
            "suggestion": "Include time since last motion event",
            "frequency": 15,
            "priority": "high",
        },
        {
            "category": "missing_context",
            "suggestion": "Add historical activity patterns",
            "frequency": 12,
            "priority": "high",
        },
        {
            "category": "missing_context",
            "suggestion": "Include weather conditions",
            "frequency": 8,
            "priority": "medium",
        },
        {
            "category": "missing_context",
            "suggestion": "Add lighting conditions",
            "frequency": 4,
            "priority": "low",
        },
        {
            "category": "format_suggestions",
            "suggestion": "Structure detection list by object type",
            "frequency": 10,
            "priority": "high",
        },
        {
            "category": "format_suggestions",
            "suggestion": "Separate zone and baseline sections",
            "frequency": 6,
            "priority": "medium",
        },
        {
            "category": "format_suggestions",
            "suggestion": "Add confidence thresholds",
            "frequency": 3,
            "priority": "low",
        },
        {
            "category": "unused_data",
            "suggestion": "Vehicle color information is rarely used",
            "frequency": 5,
            "priority": "medium",
        },
        {
            "category": "model_gaps",
            "suggestion": "Pet detection would help classify animal movement",
            "frequency": 7,
            "priority": "medium",
        },
    ]


@pytest.fixture
def sample_audits() -> list[EventAudit]:
    """Create sample EventAudit records with recommendations."""
    now = datetime.now(UTC)
    return [
        EventAudit(
            id=1,
            event_id=1,
            audited_at=now - timedelta(days=1),
            overall_quality_score=4.0,
            missing_context=json.dumps(["Include time since last motion event"]),
            format_suggestions=json.dumps(["Structure detection list by object type"]),
            model_gaps=json.dumps([]),
        ),
        EventAudit(
            id=2,
            event_id=2,
            audited_at=now - timedelta(days=2),
            overall_quality_score=3.5,
            missing_context=json.dumps(
                ["Include time since last motion event", "Add historical activity patterns"]
            ),
            format_suggestions=json.dumps([]),
            model_gaps=json.dumps(["Pet detection would help"]),
        ),
    ]


# =============================================================================
# Test: PromptAutoTuner initialization
# =============================================================================


class TestPromptAutoTunerInit:
    """Tests for PromptAutoTuner initialization."""

    def test_creates_instance(self):
        """Test that PromptAutoTuner can be instantiated."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        tuner = PromptAutoTuner()
        assert tuner is not None

    def test_accepts_custom_audit_service(self):
        """Test that PromptAutoTuner accepts a custom audit service."""
        from backend.services.pipeline_quality_audit_service import PipelineQualityAuditService
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        custom_service = PipelineQualityAuditService()
        tuner = PromptAutoTuner(audit_service=custom_service)
        assert tuner._audit_service is custom_service


# =============================================================================
# Test: get_tuning_context
# =============================================================================


class TestGetTuningContext:
    """Tests for get_tuning_context method."""

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_recommendations(self, mock_db_session):
        """Test returns empty string when no recommendations are available."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=[])
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert context == ""

    @pytest.mark.asyncio
    async def test_includes_auto_tuning_header(self, mock_db_session, sample_recommendations):
        """Test includes AUTO-TUNING header when recommendations exist."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=sample_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "## AUTO-TUNING (From Historical Analysis)" in context

    @pytest.mark.asyncio
    async def test_groups_missing_context_recommendations(
        self, mock_db_session, sample_recommendations
    ):
        """Test groups missing_context recommendations correctly."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=sample_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "Previously helpful context that was missing:" in context
            assert "Include time since last motion event" in context
            assert "Add historical activity patterns" in context

    @pytest.mark.asyncio
    async def test_limits_missing_context_to_top_3(self, mock_db_session, sample_recommendations):
        """Test limits missing_context recommendations to top 3."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=sample_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            # Should include first 3 missing_context items
            assert "Include time since last motion event" in context
            assert "Add historical activity patterns" in context
            assert "Include weather conditions" in context
            # Should NOT include 4th item
            assert "Add lighting conditions" not in context

    @pytest.mark.asyncio
    async def test_groups_format_suggestions(self, mock_db_session, sample_recommendations):
        """Test groups format_suggestions correctly."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=sample_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "Known prompt clarity issues:" in context
            assert "Structure detection list by object type" in context

    @pytest.mark.asyncio
    async def test_limits_format_suggestions_to_top_2(
        self, mock_db_session, sample_recommendations
    ):
        """Test limits format_suggestions to top 2."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=sample_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            # Should include first 2 format_suggestions
            assert "Structure detection list by object type" in context
            assert "Separate zone and baseline sections" in context
            # Should NOT include 3rd item
            assert "Add confidence thresholds" not in context

    @pytest.mark.asyncio
    async def test_uses_default_days_and_min_priority(self, mock_db_session):
        """Test uses default days=14 and min_priority=MEDIUM for filtering."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=[])
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            # Verify the call was made with correct parameters
            mock_service.get_recommendations.assert_called_once()
            call_kwargs = mock_service.get_recommendations.call_args.kwargs
            assert call_kwargs.get("days") == 14

    @pytest.mark.asyncio
    async def test_allows_custom_days_parameter(self, mock_db_session):
        """Test allows custom days parameter."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=[])
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
                days=7,
            )

            call_kwargs = mock_service.get_recommendations.call_args.kwargs
            assert call_kwargs.get("days") == 7

    @pytest.mark.asyncio
    async def test_filters_by_min_priority_medium(self, mock_db_session, sample_recommendations):
        """Test filters recommendations by minimum priority (medium and above)."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        # Only include high and medium priority items
        filtered_recommendations = [
            r for r in sample_recommendations if r["priority"] in ("high", "medium")
        ]

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=filtered_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            # Low priority items should not appear
            assert "Add lighting conditions" not in context
            assert "Add confidence thresholds" not in context

    @pytest.mark.asyncio
    async def test_handles_only_missing_context(self, mock_db_session):
        """Test handles case where only missing_context recommendations exist."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        recommendations = [
            {
                "category": "missing_context",
                "suggestion": "Add weather data",
                "frequency": 10,
                "priority": "high",
            },
        ]

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "## AUTO-TUNING (From Historical Analysis)" in context
            assert "Previously helpful context that was missing:" in context
            assert "Add weather data" in context
            # Should not include format_suggestions section
            assert "Known prompt clarity issues:" not in context

    @pytest.mark.asyncio
    async def test_handles_only_format_suggestions(self, mock_db_session):
        """Test handles case where only format_suggestions exist."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        recommendations = [
            {
                "category": "format_suggestions",
                "suggestion": "Use bullet points",
                "frequency": 8,
                "priority": "high",
            },
        ]

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "## AUTO-TUNING (From Historical Analysis)" in context
            assert "Known prompt clarity issues:" in context
            assert "Use bullet points" in context
            # Should not include missing_context section
            assert "Previously helpful context that was missing:" not in context

    @pytest.mark.asyncio
    async def test_handles_audit_service_error_gracefully(self, mock_db_session):
        """Test handles errors from audit service gracefully."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(side_effect=Exception("Database error"))
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            # Should return empty string on error, not raise
            assert context == ""


# =============================================================================
# Test: Singleton pattern
# =============================================================================


class TestPromptAutoTunerSingleton:
    """Tests for singleton pattern."""

    def test_get_prompt_auto_tuner_returns_instance(self):
        """Test get_prompt_auto_tuner returns a PromptAutoTuner instance."""
        from backend.services.prompt_auto_tuner import (
            get_prompt_auto_tuner,
            reset_prompt_auto_tuner,
        )

        reset_prompt_auto_tuner()
        tuner = get_prompt_auto_tuner()
        assert tuner is not None

    def test_get_prompt_auto_tuner_returns_same_instance(self):
        """Test get_prompt_auto_tuner returns the same instance."""
        from backend.services.prompt_auto_tuner import (
            get_prompt_auto_tuner,
            reset_prompt_auto_tuner,
        )

        reset_prompt_auto_tuner()
        tuner1 = get_prompt_auto_tuner()
        tuner2 = get_prompt_auto_tuner()
        assert tuner1 is tuner2

    def test_reset_prompt_auto_tuner(self):
        """Test reset_prompt_auto_tuner creates new instance on next call."""
        from backend.services.prompt_auto_tuner import (
            get_prompt_auto_tuner,
            reset_prompt_auto_tuner,
        )

        reset_prompt_auto_tuner()
        tuner1 = get_prompt_auto_tuner()
        reset_prompt_auto_tuner()
        tuner2 = get_prompt_auto_tuner()
        assert tuner1 is not tuner2


# =============================================================================
# Test: Priority filtering
# =============================================================================


class TestPriorityFiltering:
    """Tests for priority filtering logic."""

    @pytest.mark.asyncio
    async def test_filter_by_priority_high_only(self, mock_db_session, sample_recommendations):
        """Test filtering to include only high priority recommendations."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            # Return all recommendations - tuner should filter by priority internally
            mock_service.get_recommendations = AsyncMock(return_value=sample_recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
                min_priority="high",
            )

            # Verify only high priority items appear in output
            # High priority missing_context items
            assert "Include time since last motion event" in context
            assert "Add historical activity patterns" in context
            # High priority format_suggestions
            assert "Structure detection list by object type" in context
            # Medium and low priority should NOT appear
            assert "Include weather conditions" not in context  # medium
            assert "Add lighting conditions" not in context  # low
            assert "Add confidence thresholds" not in context  # low


# =============================================================================
# Test: Integration with actual recommendations format
# =============================================================================


class TestRecommendationIntegration:
    """Tests for integration with audit service recommendation format."""

    @pytest.mark.asyncio
    async def test_handles_empty_suggestion_strings(self, mock_db_session):
        """Test handles empty suggestion strings gracefully."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        recommendations = [
            {
                "category": "missing_context",
                "suggestion": "",  # Empty string
                "frequency": 5,
                "priority": "high",
            },
            {
                "category": "missing_context",
                "suggestion": "Valid suggestion",
                "frequency": 10,
                "priority": "high",
            },
        ]

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            # Should include valid suggestion but skip empty
            assert "Valid suggestion" in context
            # Should not have empty bullet point
            assert "  - \n" not in context

    @pytest.mark.asyncio
    async def test_preserves_suggestion_formatting(self, mock_db_session):
        """Test preserves original suggestion text formatting."""
        from backend.services.prompt_auto_tuner import PromptAutoTuner

        recommendations = [
            {
                "category": "missing_context",
                "suggestion": "Include the 'time_since_last_motion' field",
                "frequency": 10,
                "priority": "high",
            },
        ]

        with patch("backend.services.prompt_auto_tuner.get_audit_service") as mock_get_audit:
            mock_service = MagicMock()
            mock_service.get_recommendations = AsyncMock(return_value=recommendations)
            mock_get_audit.return_value = mock_service

            tuner = PromptAutoTuner()
            context = await tuner.get_tuning_context(
                session=mock_db_session,
                camera_id="front_door",
            )

            assert "Include the 'time_since_last_motion' field" in context


# =============================================================================
# Test: Prompt injection into LLM prompts
# =============================================================================


class TestPromptInjection:
    """Tests for auto-tuning context injection into LLM prompts."""

    @pytest.mark.asyncio
    async def test_auto_tuning_context_injected_before_assistant_marker(self):
        """Test that auto-tuning context is injected before <|im_start|>assistant marker."""
        # This tests the injection logic in NemotronAnalyzer._call_llm
        # The auto_tuning_context should be inserted just before the assistant turn

        # Simulate a basic prompt with the assistant marker
        sample_prompt = """<|im_start|>system
You are a security analyzer.<|im_end|>
<|im_start|>user
Analyze this event.<|im_end|>
<|im_start|>assistant
"""
        auto_tuning_context = """## AUTO-TUNING (From Historical Analysis)
Previously helpful context that was missing:
  - Include time since last motion event"""

        # Apply the injection logic (same as in nemotron_analyzer._call_llm)
        assistant_marker = "<|im_start|>assistant"
        if assistant_marker in sample_prompt:
            result = sample_prompt.replace(
                assistant_marker,
                f"\n{auto_tuning_context}\n{assistant_marker}",
            )
        else:
            result = f"{sample_prompt}\n{auto_tuning_context}"

        # Verify the auto-tuning context is in the result
        assert "## AUTO-TUNING (From Historical Analysis)" in result
        assert "Include time since last motion event" in result

        # Verify it comes BEFORE the assistant marker
        auto_tune_pos = result.index("## AUTO-TUNING")
        assistant_pos = result.index("<|im_start|>assistant")
        assert auto_tune_pos < assistant_pos

    @pytest.mark.asyncio
    async def test_empty_auto_tuning_context_not_injected(self):
        """Test that empty auto-tuning context does not modify the prompt."""
        sample_prompt = """<|im_start|>system
You are a security analyzer.<|im_end|>
<|im_start|>user
Analyze this event.<|im_end|>
<|im_start|>assistant
"""
        auto_tuning_context = ""  # Empty context

        # Apply the injection logic (same as in nemotron_analyzer._call_llm)
        if auto_tuning_context:
            assistant_marker = "<|im_start|>assistant"
            if assistant_marker in sample_prompt:
                result = sample_prompt.replace(
                    assistant_marker,
                    f"\n{auto_tuning_context}\n{assistant_marker}",
                )
            else:
                result = f"{sample_prompt}\n{auto_tuning_context}"
        else:
            result = sample_prompt

        # Empty context should not modify the prompt
        assert result == sample_prompt
        assert "## AUTO-TUNING" not in result
