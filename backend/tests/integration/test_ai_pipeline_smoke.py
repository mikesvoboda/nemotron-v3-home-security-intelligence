"""CI smoke tests for AI pipeline quality metrics.

Fast integration tests (~2 min) that validate AI pipeline output quality
using the shared metrics library. These tests run in CI to catch regressions
in LLM analysis quality, serialization correctness, and event linkage integrity.

Test cases:
1. Field completeness - All required LLMInteraction fields populated
2. Serialization quality - No Python repr strings in JSON fields
3. Event linkage - Events have associated LLMInteraction records
4. Risk score validity - Risk scores are in valid range (0-100)

The tests use the isolated_db_session fixture for automatic transaction
rollback and skip gracefully if no LLMInteraction data exists (for repos
without seed data).

Usage:
    # Run all AI pipeline smoke tests
    pytest -v backend/tests/integration/test_ai_pipeline_smoke.py -m ai_pipeline

    # Run specific test
    pytest -v backend/tests/integration/test_ai_pipeline_smoke.py::test_llm_interaction_field_completeness
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from backend.models import Camera, Event
from backend.models.llm_interaction import LLMInteraction
from backend.services.ai_quality_metrics import AIQualityAnalyzer, QualityLevel
from backend.tests.conftest import unique_id

# Mark all tests in this module for selective CI execution
pytestmark = [pytest.mark.integration, pytest.mark.ai_pipeline]


def _utcnow() -> datetime:
    """Get current UTC time as a timezone-aware datetime.

    Uses datetime.now(UTC) to avoid deprecation warning from datetime.utcnow().
    Returns timezone-aware datetime to match SQLAlchemy DateTime(timezone=True) columns.
    """
    return datetime.now(UTC)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_prefix():
    """Generate a unique prefix for this test run to ensure isolation."""
    return unique_id("ai_smoke")


@pytest.fixture
async def sample_camera(session, test_prefix):
    """Create a test camera for use in AI pipeline tests.

    Uses unique names and folder paths to prevent conflicts with unique constraints.
    """
    camera_id = f"{test_prefix}_test_camera"
    camera = Camera(
        id=camera_id,
        name=f"Test Camera {camera_id[-8:]}",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def sample_event_with_llm(session, sample_camera):
    """Create a test event with LLMInteraction record for quality testing.

    This fixture creates a complete event with all required fields and a
    properly structured LLMInteraction record to test the quality metrics.
    """
    # Create event
    event = Event(
        batch_id=unique_id("batch"),
        camera_id=sample_camera.id,
        started_at=_utcnow(),
        risk_score=75,
        risk_level="medium",
        summary="Test event for AI pipeline quality validation",
        reasoning="This is a test event created to validate AI pipeline quality metrics",
    )
    session.add(event)
    await session.flush()

    # Create LLMInteraction with proper structure
    llm_interaction = LLMInteraction(
        event_id=event.id,
        raw_response='{"risk_score": 75, "risk_level": "medium", "summary": "Test event", "reasoning": "Test reasoning for validation"}',
        enrichment_snapshot={
            "weather": {"temperature": 72, "condition": "clear"},
            "faces": [],
            "license_plates": [],
            "zones": [],
        },
        context_sources={
            "weather": True,
            "faces": False,
            "license_plates": False,
            "zones": False,
        },
        household_matches=None,  # Optional field
        truncation_log=None,  # Optional field
    )
    session.add(llm_interaction)
    await session.flush()

    return event, llm_interaction


@pytest.fixture
async def analyzer(session):
    """Create an AIQualityAnalyzer instance for the test session."""
    return AIQualityAnalyzer(session)


# =============================================================================
# Helper Functions
# =============================================================================


async def _has_llm_data(session) -> bool:
    """Check if database has any LLMInteraction records.

    Used to skip tests gracefully in repos without seed data.
    """
    result = await session.execute(select(LLMInteraction).limit(1))
    return result.scalar_one_or_none() is not None


# =============================================================================
# Field Completeness Tests
# =============================================================================


class TestLLMInteractionFieldCompleteness:
    """Test that all required LLMInteraction fields are populated."""

    @pytest.mark.asyncio
    async def test_llm_interaction_field_completeness(
        self, session, analyzer, sample_event_with_llm
    ):
        """Verify all required fields are populated in LLMInteraction records.

        Required fields:
        - raw_response: Full LLM output (must be non-null)
        - enrichment_snapshot: Context sent to LLM (must be non-null)

        Optional fields (can be null):
        - household_matches: Person/vehicle matches
        - truncation_log: What context was dropped
        - context_sources: Which fields were populated
        - validation_result: Synthetic data validation
        """
        # Collect field completeness metrics
        metrics = await analyzer.collect_field_completeness()

        # Verify we have at least one record (from fixture)
        assert metrics.total_records >= 1, (
            "Should have at least one LLMInteraction record from fixture"
        )

        # Verify required fields are 100% populated
        assert metrics.raw_response_rate == 1.0, (
            f"All records must have raw_response (got {metrics.raw_response_rate:.2%})"
        )

        assert metrics.enrichment_snapshot_rate == 1.0, (
            f"All records must have enrichment_snapshot (got {metrics.enrichment_snapshot_rate:.2%})"
        )

        # Verify context_sources is populated (helps debugging)
        assert metrics.context_sources_rate >= 0.5, (
            f"Most records should have context_sources (got {metrics.context_sources_rate:.2%})"
        )

    @pytest.mark.asyncio
    async def test_raw_response_is_valid_json(self, session, sample_event_with_llm):
        """Verify raw_response field contains valid JSON."""
        import json

        event, llm_interaction = sample_event_with_llm

        # Fetch the LLMInteraction
        result = await session.execute(
            select(LLMInteraction).where(LLMInteraction.event_id == event.id)
        )
        interaction = result.scalar_one()

        # raw_response should be parseable JSON
        try:
            parsed = json.loads(interaction.raw_response)
            assert isinstance(parsed, dict), "raw_response should parse to a dictionary"
            # Should have key fields from Nemotron response
            assert "summary" in parsed or "risk_score" in parsed, (
                "raw_response should contain analysis fields"
            )
        except json.JSONDecodeError as e:
            pytest.fail(f"raw_response is not valid JSON: {e}")


# =============================================================================
# Serialization Quality Tests
# =============================================================================


class TestSerializationQuality:
    """Test that JSON fields are properly serialized (no Python repr strings)."""

    @pytest.mark.asyncio
    async def test_serialization_no_python_repr(self, session, analyzer, sample_event_with_llm):
        """Verify enrichment_snapshot has no Python repr strings.

        Python repr strings like 'WeatherResult(...)' indicate serialization
        bugs where objects weren't properly converted to JSON. These cause
        frontend parsing errors and break the UI.
        """
        # Collect serialization metrics
        metrics = await analyzer.collect_serialization_metrics()

        # No Python repr strings should be present
        assert metrics.python_repr_count == 0, (
            f"Found {metrics.python_repr_count} Python repr strings in enrichment_snapshot"
        )

        # Weather field should be proper JSON object (not string)
        assert metrics.weather_serialization_ok, (
            "Weather field must be proper JSON object, not string"
        )

        # Array fields should be proper JSON arrays (not strings)
        assert metrics.faces_serialization_ok, "Faces field must be proper JSON array, not string"
        assert metrics.plates_serialization_ok, (
            "License plates field must be proper JSON array, not string"
        )

    @pytest.mark.asyncio
    async def test_enrichment_snapshot_structure(self, session, sample_event_with_llm):
        """Verify enrichment_snapshot has expected structure."""
        event, llm_interaction = sample_event_with_llm

        # Fetch the LLMInteraction
        result = await session.execute(
            select(LLMInteraction).where(LLMInteraction.event_id == event.id)
        )
        interaction = result.scalar_one()

        snapshot = interaction.enrichment_snapshot
        assert isinstance(snapshot, dict), "enrichment_snapshot should be a dictionary"

        # Common fields that should be present (even if empty)
        expected_fields = {"weather", "faces", "license_plates"}
        actual_fields = set(snapshot.keys())

        # At least some expected fields should be present
        assert len(expected_fields & actual_fields) > 0, (
            f"enrichment_snapshot should contain common fields like {expected_fields}, "
            f"got {actual_fields}"
        )

        # If weather is present, it should be a dict (not a string)
        if "weather" in snapshot and snapshot["weather"] is not None:
            assert isinstance(snapshot["weather"], dict), (
                f"Weather should be a dict, got {type(snapshot['weather'])}"
            )

        # If arrays are present, they should be lists (not strings)
        if "faces" in snapshot and snapshot["faces"] is not None:
            assert isinstance(snapshot["faces"], list), (
                f"Faces should be a list, got {type(snapshot['faces'])}"
            )

        if "license_plates" in snapshot and snapshot["license_plates"] is not None:
            assert isinstance(snapshot["license_plates"], list), (
                f"License plates should be a list, got {type(snapshot['license_plates'])}"
            )


# =============================================================================
# Event Linkage Tests
# =============================================================================


class TestEventLinkageIntegrity:
    """Test that events have associated LLMInteraction records."""

    @pytest.mark.asyncio
    async def test_event_linkage_integrity(self, session, analyzer, sample_event_with_llm):
        """Verify all events have LLMInteraction records.

        Every event analyzed by Nemotron should have a corresponding
        LLMInteraction record for observability. Missing records indicate
        a bug in the analysis pipeline.
        """
        # Collect linkage metrics
        metrics = await analyzer.collect_linkage_metrics()

        # Verify we have at least one event (from fixture)
        assert metrics.total_events >= 1, "Should have at least one event from fixture"

        # All events should have LLMInteraction records
        assert metrics.coverage_rate == 1.0, (
            f"All events must have LLMInteraction records (got {metrics.coverage_rate:.2%} coverage)"
        )

        # No orphan interactions (LLMInteraction without valid event)
        assert metrics.orphan_interactions == 0, (
            f"Found {metrics.orphan_interactions} orphan LLMInteraction records without valid events"
        )

    @pytest.mark.asyncio
    async def test_event_llm_relationship(self, session, sample_event_with_llm):
        """Verify Event <-> LLMInteraction relationship is bidirectional."""
        event, llm_interaction = sample_event_with_llm

        # Fetch event with relationship loaded
        result = await session.execute(
            select(Event).where(Event.id == event.id).options()  # Use default lazy loading
        )
        fetched_event = result.scalar_one()

        # Access the relationship (should trigger lazy load)
        interaction_from_event = fetched_event.llm_interaction
        assert interaction_from_event is not None, "Event should have llm_interaction relationship"
        assert interaction_from_event.id == llm_interaction.id, (
            "Event.llm_interaction should point to correct record"
        )

        # Fetch LLMInteraction with relationship loaded
        result = await session.execute(
            select(LLMInteraction).where(LLMInteraction.id == llm_interaction.id).options()
        )
        fetched_interaction = result.scalar_one()

        # Access the relationship (should trigger lazy load)
        event_from_interaction = fetched_interaction.event
        assert event_from_interaction is not None, "LLMInteraction should have event relationship"
        assert event_from_interaction.id == event.id, (
            "LLMInteraction.event should point to correct record"
        )


# =============================================================================
# Risk Score Validity Tests
# =============================================================================


class TestRiskScoreValidity:
    """Test that risk scores are in valid range (0-100)."""

    @pytest.mark.asyncio
    async def test_risk_score_basic_validity(self, session, analyzer, sample_event_with_llm):
        """Verify risk scores are in valid range (0-100).

        Risk scores outside this range indicate a bug in the Nemotron
        analysis pipeline or prompt template.
        """
        # Collect risk distribution metrics
        metrics = await analyzer.collect_risk_distribution()

        # Verify we have at least one event (from fixture)
        assert metrics.total_events >= 1, "Should have at least one event from fixture"

        # All risk scores should be in valid range
        assert 0 <= metrics.min_score <= 100, (
            f"Minimum risk score {metrics.min_score} is out of range [0, 100]"
        )

        assert 0 <= metrics.max_score <= 100, (
            f"Maximum risk score {metrics.max_score} is out of range [0, 100]"
        )

        assert 0 <= metrics.mean_score <= 100, (
            f"Mean risk score {metrics.mean_score} is out of range [0, 100]"
        )

    @pytest.mark.asyncio
    async def test_risk_level_consistency(self, session, sample_event_with_llm):
        """Verify risk_level is consistent with risk_score.

        Standard risk level mapping:
        - low: 0-33
        - medium: 34-66
        - high: 67-100
        """
        event, _ = sample_event_with_llm

        # Fetch the event
        result = await session.execute(select(Event).where(Event.id == event.id))
        fetched_event = result.scalar_one()

        # Verify risk_level matches risk_score
        score = fetched_event.risk_score
        level = fetched_event.risk_level

        if score is not None and level is not None:
            if score <= 33:
                assert level == "low", f"Risk score {score} should map to 'low', got '{level}'"
            elif score <= 66:
                assert level == "medium", (
                    f"Risk score {score} should map to 'medium', got '{level}'"
                )
            else:
                assert level == "high", f"Risk score {score} should map to 'high', got '{level}'"


# =============================================================================
# Comprehensive Quality Report Test
# =============================================================================


class TestQualityReport:
    """Test comprehensive quality analysis report."""

    @pytest.mark.asyncio
    async def test_comprehensive_quality_report(self, session, analyzer, sample_event_with_llm):
        """Run comprehensive quality analysis and verify all metrics pass.

        This test collects all quality metrics and generates a report.
        It verifies that critical checks pass (field completeness, serialization,
        linkage) while allowing warnings for optional metrics (reasoning quality,
        risk distribution).
        """
        # Collect all metrics
        report = await analyzer.collect_all_metrics()

        # Check critical metrics (must pass)
        critical_failures = [
            r
            for r in report.results
            if r.level == QualityLevel.FAIL and not r.name.startswith("risk_")
        ]

        if critical_failures:
            failure_msg = "\n".join(
                f"  - {r.name}: {r.value} (expected {r.expected}) - {r.details}"
                for r in critical_failures
            )
            pytest.fail(
                f"Critical quality checks failed:\n{failure_msg}\n\nFull report:\n{report.summary}"
            )

        # Log warnings (non-critical)
        warnings = [r for r in report.results if r.level == QualityLevel.WARNING]
        if warnings:
            warning_msg = "\n".join(
                f"  - {r.name}: {r.value} (expected {r.expected}) - {r.details}" for r in warnings
            )
            print(f"\n⚠️  Quality warnings (non-critical):\n{warning_msg}")

        # Verify report structure
        assert report.field_completeness is not None, (
            "Report should include field completeness metrics"
        )
        assert report.serialization is not None, "Report should include serialization metrics"
        assert report.linkage is not None, "Report should include linkage metrics"
        assert report.risk_distribution is not None, (
            "Report should include risk distribution metrics"
        )
        assert report.reasoning_quality is not None, (
            "Report should include reasoning quality metrics"
        )

        # Log summary for CI visibility
        print(f"\n📊 AI Pipeline Quality Report:\n{report.summary}")


# =============================================================================
# Skip Condition Tests
# =============================================================================


class TestSkipConditions:
    """Test graceful skipping when no data exists."""

    @pytest.mark.asyncio
    async def test_metrics_with_no_data(self, session):
        """Verify metrics collection handles empty database gracefully.

        This test creates a fresh analyzer on an empty database (no fixtures)
        and verifies that metric collection returns zero values without errors.
        """
        # Create new session scope without fixtures
        analyzer = AIQualityAnalyzer(session)

        # Field completeness should return zeros for empty database
        field_metrics = await analyzer.collect_field_completeness()
        assert field_metrics.total_records == 0, "Empty database should have 0 records"

        # Risk distribution should return zeros
        risk_metrics = await analyzer.collect_risk_distribution()
        assert risk_metrics.total_events == 0, "Empty database should have 0 events"

        # Linkage should return zeros
        linkage_metrics = await analyzer.collect_linkage_metrics()
        assert linkage_metrics.total_events == 0, "Empty database should have 0 events"

        # Serialization should return safe defaults
        serialization_metrics = await analyzer.collect_serialization_metrics()
        assert serialization_metrics.python_repr_count == 0, (
            "Empty database should have 0 repr errors"
        )
