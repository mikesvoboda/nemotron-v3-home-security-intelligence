"""Unit tests for LLM Reasoning Explorer API routes.

Tests the /api/llm-reasoning endpoints that expose LLMInteraction data
for debugging and transparency, including:
- Think block parsing
- Enrichment source extraction
- Truncation information
- Household match parsing
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from backend.api.routes.llm_reasoning import (
    _extract_confidence,
    _extract_key_factors,
    _extract_key_observations,
    _extract_risk_factors,
    _extract_think_block,
    _parse_enrichment_sources,
    _parse_household_matches,
    _parse_reasoning_steps,
    _parse_truncation_info,
    router,
)
from backend.models.event import Event
from backend.models.llm_interaction import LLMInteraction


@pytest.fixture
def app():
    """Create test FastAPI application."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# Unit Tests for Helper Functions
# =============================================================================


class TestExtractThinkBlock:
    """Tests for _extract_think_block function."""

    def test_extracts_think_block(self):
        """Should extract content between <think> tags."""
        response = """
        <think>
        This is my reasoning about the event.
        I see a person at the door.
        </think>
        The risk score is 45.
        """
        result = _extract_think_block(response)
        assert result is not None
        assert "This is my reasoning" in result
        assert "person at the door" in result

    def test_handles_no_think_block(self):
        """Should return None when no think block is present."""
        response = "Just a simple response with no think block."
        result = _extract_think_block(response)
        assert result is None

    def test_handles_case_insensitive_tags(self):
        """Should handle different case variations of think tags."""
        response = "<THINK>Uppercase tags</THINK>"
        result = _extract_think_block(response)
        assert result == "Uppercase tags"

    def test_handles_multiline_content(self):
        """Should handle multiline content in think block."""
        response = """<think>
        Line 1
        Line 2
        Line 3
        </think>"""
        result = _extract_think_block(response)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


class TestParseReasoningSteps:
    """Tests for _parse_reasoning_steps function."""

    def test_parses_numbered_steps(self):
        """Should parse numbered reasoning steps."""
        content = """
        1. First, I observe the person approaching.
        2. They appear to be carrying something.
        3. The time of day is late night.
        """
        steps = _parse_reasoning_steps(content)
        assert len(steps) == 3
        assert steps[0].step_number == 1
        assert "observe the person" in steps[0].content
        assert steps[1].step_number == 2
        assert steps[2].step_number == 3

    def test_parses_paragraph_steps(self):
        """Should fall back to paragraph-based parsing."""
        content = """
        First observation about the scene.

        Second observation with more details.

        Final conclusion.
        """
        steps = _parse_reasoning_steps(content)
        assert len(steps) == 3

    def test_handles_empty_content(self):
        """Should handle empty content gracefully."""
        steps = _parse_reasoning_steps("")
        assert len(steps) == 0

    def test_single_paragraph_creates_one_step(self):
        """Should create a single step for content without breaks."""
        content = "This is a single paragraph of reasoning."
        steps = _parse_reasoning_steps(content)
        assert len(steps) == 1
        assert steps[0].step_number == 1


class TestExtractKeyFactors:
    """Tests for _extract_key_factors function."""

    def test_extracts_due_to_factors(self):
        """Should extract factors from 'due to' phrases."""
        content = "The risk is elevated due to the late hour and unusual behavior."
        factors = _extract_key_factors(content)
        assert len(factors) > 0
        assert any("late hour" in f.lower() for f in factors)

    def test_extracts_because_of_factors(self):
        """Should extract factors from 'because of' phrases."""
        content = "I'm concerned because of the obscured face."
        factors = _extract_key_factors(content)
        assert len(factors) > 0

    def test_limits_factor_count(self):
        """Should limit the number of factors returned."""
        content = """
        Due to factor one, due to factor two, due to factor three,
        due to factor four, due to factor five, due to factor six,
        due to factor seven, due to factor eight.
        """
        factors = _extract_key_factors(content)
        assert len(factors) <= 5


class TestExtractConfidence:
    """Tests for _extract_confidence function."""

    def test_detects_high_confidence(self):
        """Should detect high confidence indicators."""
        content = "I am confident that this is a delivery person."
        result = _extract_confidence(content)
        assert result == "high"

    def test_detects_low_confidence(self):
        """Should detect low confidence indicators."""
        content = "I am uncertain about the identity."
        result = _extract_confidence(content)
        assert result == "low"

    def test_detects_medium_confidence(self):
        """Should detect medium confidence indicators."""
        content = "This is likely a regular visitor."
        result = _extract_confidence(content)
        assert result == "medium"

    def test_returns_none_when_no_indicator(self):
        """Should return None when no confidence indicator is found."""
        content = "There is a person at the door."
        result = _extract_confidence(content)
        assert result is None


class TestExtractKeyObservations:
    """Tests for _extract_key_observations function."""

    def test_extracts_i_observe_patterns(self):
        """Should extract observations starting with 'I observe'."""
        content = "I observe that the person is wearing a uniform."
        observations = _extract_key_observations(content)
        assert len(observations) > 0
        assert any("wearing a uniform" in obs for obs in observations)

    def test_limits_observations(self):
        """Should limit the number of observations returned."""
        content = "\n".join([f"I notice that observation {i}" for i in range(15)])
        observations = _extract_key_observations(content)
        assert len(observations) <= 10


class TestExtractRiskFactors:
    """Tests for _extract_risk_factors function."""

    def test_extracts_explicit_risk_factors(self):
        """Should extract explicitly stated risk factors."""
        content = "Risk factor: unknown individual at late hour."
        factors = _extract_risk_factors(content)
        assert len(factors) > 0

    def test_extracts_keyword_risk_factors(self):
        """Should extract keyword-based risk factors."""
        content = "The person is loitering near the entrance at an unusual time."
        factors = _extract_risk_factors(content)
        assert "loitering" in factors or any("loitering" in f for f in factors)

    def test_limits_risk_factors(self):
        """Should limit the number of risk factors returned."""
        # Generate content with many keywords
        keywords = [
            "late night",
            "unknown person",
            "loitering",
            "suspicious behavior",
            "concealed",
            "obscured face",
            "unusual time",
            "unrecognized",
            "multiple attempts",
            "approaching",
        ] * 2
        content = " ".join(keywords)
        factors = _extract_risk_factors(content)
        assert len(factors) <= 10


class TestParseEnrichmentSources:
    """Tests for _parse_enrichment_sources function."""

    def test_parses_known_sources(self):
        """Should parse known enrichment sources."""
        snapshot = {
            "florence": {"scene_description": "Person at door", "objects": ["person"]},
            "weather": {"condition": "clear"},
            "clip": [],
        }
        sources = _parse_enrichment_sources(snapshot)
        assert len(sources) >= 3
        florence_source = next((s for s in sources if "Florence" in s.name), None)
        assert florence_source is not None
        assert florence_source.populated is True
        assert florence_source.field_count == 2

    def test_handles_empty_sources(self):
        """Should mark empty sources as not populated."""
        snapshot = {"florence": {}, "weather": None}
        sources = _parse_enrichment_sources(snapshot)
        florence_source = next((s for s in sources if "Florence" in s.name), None)
        assert florence_source is not None
        assert florence_source.populated is False

    def test_handles_list_data(self):
        """Should handle list-type enrichment data."""
        snapshot = {
            "detections": [
                {"type": "person", "confidence": 0.9},
                {"type": "vehicle", "confidence": 0.8},
            ]
        }
        sources = _parse_enrichment_sources(snapshot)
        det_source = next((s for s in sources if "Detection" in s.name), None)
        assert det_source is not None
        assert det_source.field_count == 2


class TestParseTruncationInfo:
    """Tests for _parse_truncation_info function."""

    def test_parses_truncation_log(self):
        """Should parse truncation log into structured info."""
        truncation_log = {
            "was_truncated": True,
            "original_length": 8000,
            "truncated_length": 4096,
            "dropped_sections": ["historical_data", "correlations"],
            "reason": "Token limit exceeded",
        }
        info = _parse_truncation_info(truncation_log)
        assert info.was_truncated is True
        assert info.original_length == 8000
        assert info.truncated_length == 4096
        assert len(info.dropped_sections) == 2

    def test_handles_none_log(self):
        """Should handle None truncation log."""
        info = _parse_truncation_info(None)
        assert info.was_truncated is False
        assert info.original_length is None

    def test_handles_empty_log(self):
        """Should handle empty truncation log."""
        info = _parse_truncation_info({})
        assert info.was_truncated is False


class TestParseHouseholdMatches:
    """Tests for _parse_household_matches function."""

    def test_parses_list_format(self):
        """Should parse list format household matches."""
        matches_data = [
            {"entity_type": "person", "entity_name": "John Doe", "similarity_score": 0.92},
            {"entity_type": "vehicle", "name": "Family Car", "similarity_score": 0.85},
        ]
        matches = _parse_household_matches(matches_data)
        assert len(matches) == 2
        assert matches[0].entity_type == "person"
        assert matches[0].entity_name == "John Doe"
        assert matches[0].similarity_score == 0.92

    def test_parses_dict_format(self):
        """Should parse dict format (keyed by entity type)."""
        matches_data = {
            "person": [{"name": "Jane Doe", "similarity": 0.88}],
            "vehicle": {"name": "Truck", "similarity": 0.75},
        }
        matches = _parse_household_matches(matches_data)
        assert len(matches) == 2

    def test_handles_none(self):
        """Should handle None household matches."""
        matches = _parse_household_matches(None)
        assert len(matches) == 0

    def test_handles_empty_dict(self):
        """Should handle empty dict."""
        matches = _parse_household_matches({})
        assert len(matches) == 0


# =============================================================================
# Integration Tests for API Endpoints
# =============================================================================


class TestGetLLMReasoningEndpoint:
    """Tests for GET /api/llm-reasoning/events/{event_id} endpoint."""

    @pytest.mark.asyncio
    async def test_returns_reasoning_data(self, app):
        """Should return LLM reasoning data for valid event."""
        # Create mock data
        mock_interaction = MagicMock(spec=LLMInteraction)
        mock_interaction.id = 1
        mock_interaction.event_id = 123
        mock_interaction.created_at = datetime.now(UTC)
        mock_interaction.raw_response = "<think>Test reasoning</think>"
        mock_interaction.enrichment_snapshot = {"florence": {"test": "data"}}
        mock_interaction.truncation_log = None
        mock_interaction.household_matches = None
        mock_interaction.context_sources = None
        mock_interaction.validation_result = None

        mock_event = MagicMock(spec=Event)
        mock_event.id = 123

        # Mock the database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_interaction
        mock_session.execute.return_value = mock_result

        async def override_get_read_db():
            yield mock_session

        # Apply dependency overrides
        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        # Patch get_event_or_404 since it's called directly in the route, not as a dependency
        with patch(
            "backend.api.routes.llm_reasoning.get_event_or_404",
            return_value=mock_event,
        ):
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as ac:
                    response = await ac.get("/api/llm-reasoning/events/123")

                # Should succeed
                assert response.status_code == 200
                data = response.json()
                assert data["event_id"] == 123
                assert "think_block" in data
                assert "enrichment_sources" in data
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_event(self, app):
        """Should return 404 when event does not exist."""
        from fastapi import HTTPException

        mock_session = AsyncMock()

        async def override_get_read_db():
            yield mock_session

        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        # Patch get_event_or_404 since it's called directly in the route, not as a dependency
        with patch(
            "backend.api.routes.llm_reasoning.get_event_or_404",
            side_effect=HTTPException(status_code=404, detail="Event not found"),
        ):
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as ac:
                    response = await ac.get("/api/llm-reasoning/events/999")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_llm_interaction(self, app):
        """Should return 404 when LLM interaction does not exist."""
        mock_event = MagicMock(spec=Event)
        mock_event.id = 123

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No interaction found
        mock_session.execute.return_value = mock_result

        async def override_get_read_db():
            yield mock_session

        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        # Patch get_event_or_404 since it's called directly in the route, not as a dependency
        with patch(
            "backend.api.routes.llm_reasoning.get_event_or_404",
            return_value=mock_event,
        ):
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as ac:
                    response = await ac.get("/api/llm-reasoning/events/123")

                assert response.status_code == 404
                data = response.json()
                assert "No LLM reasoning data" in data["detail"]["message"]
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_includes_debug_info_when_requested(self, app):
        """Should include debug info when include_debug=true."""
        mock_interaction = MagicMock(spec=LLMInteraction)
        mock_interaction.id = 1
        mock_interaction.event_id = 123
        mock_interaction.created_at = datetime.now(UTC)
        mock_interaction.raw_response = "<think>Test</think>"
        mock_interaction.enrichment_snapshot = {"test": "data"}
        mock_interaction.truncation_log = {"was_truncated": True}
        mock_interaction.household_matches = []
        mock_interaction.context_sources = {"source1": True}
        mock_interaction.validation_result = {"passed": True}

        mock_event = MagicMock(spec=Event)
        mock_event.id = 123

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_interaction
        mock_session.execute.return_value = mock_result

        async def override_get_read_db():
            yield mock_session

        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        # Patch get_event_or_404 since it's called directly in the route, not as a dependency
        with patch(
            "backend.api.routes.llm_reasoning.get_event_or_404",
            return_value=mock_event,
        ):
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as ac:
                    response = await ac.get("/api/llm-reasoning/events/123?include_debug=true")

                assert response.status_code == 200
                data = response.json()
                assert "debug_info" in data
                assert data["debug_info"]["has_truncation_log"] is True
                assert "context_sources" in data["debug_info"]
            finally:
                app.dependency_overrides.clear()


class TestGetLLMPromptDebugEndpoint:
    """Tests for GET /api/llm-reasoning/events/{event_id}/prompt endpoint."""

    @pytest.mark.asyncio
    async def test_returns_full_prompt_data(self, app):
        """Should return full prompt data for debugging."""
        mock_interaction = MagicMock(spec=LLMInteraction)
        mock_interaction.enrichment_snapshot = {"florence": "data"}
        mock_interaction.context_sources = {"source1": True}
        mock_interaction.truncation_log = None
        mock_interaction.household_matches = None
        mock_interaction.validation_result = None

        mock_event = MagicMock(spec=Event)
        mock_event.id = 123
        mock_event.llm_prompt = "Full prompt text here"
        mock_event.llm_interaction = mock_interaction
        mock_event.deleted_at = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_session.execute.return_value = mock_result

        async def override_get_read_db():
            yield mock_session

        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/llm-reasoning/events/123/prompt")

            assert response.status_code == 200
            data = response.json()
            assert data["event_id"] == 123
            assert data["llm_prompt"] == "Full prompt text here"
            assert "enrichment_snapshot" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_event(self, app):
        """Should return 404 when event does not exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        async def override_get_read_db():
            yield mock_session

        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/llm-reasoning/events/999/prompt")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_404_when_no_interaction(self, app):
        """Should return 404 when event has no LLM interaction."""
        mock_event = MagicMock(spec=Event)
        mock_event.id = 123
        mock_event.llm_interaction = None
        mock_event.deleted_at = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_session.execute.return_value = mock_result

        async def override_get_read_db():
            yield mock_session

        from backend.core.database import get_read_db

        app.dependency_overrides[get_read_db] = override_get_read_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/llm-reasoning/events/123/prompt")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
