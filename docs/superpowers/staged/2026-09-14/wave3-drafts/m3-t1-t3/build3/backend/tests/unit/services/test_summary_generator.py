"""Unit tests for SummaryGenerator service.

Tests cover:
- Generating hourly summary with events
- Generating hourly summary with no events (all clear)
- Generating daily summary
- Generating both summaries
- Fallback behavior when Nemotron fails
- Event context building

Related Linear issue: NEM-2890
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.models.event import Event
from backend.models.summary import Summary, SummaryType
from backend.services.summary_generator import (
    SummaryGenerator,
    get_summary_generator,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture
def mock_event() -> MagicMock:
    """Create a mock Event object with typical values."""
    event = MagicMock(spec=Event)
    event.id = 1
    event.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)
    event.camera_id = "front_door"
    event.camera = MagicMock()
    event.camera.name = "Front Door"
    event.risk_level = "high"
    event.risk_score = 75
    event.summary = "Unrecognized person approached the front door"
    event.object_types = "person"
    return event


@pytest.fixture
def mock_critical_event() -> MagicMock:
    """Create a mock critical Event object."""
    event = MagicMock(spec=Event)
    event.id = 2
    event.started_at = datetime(2026, 1, 18, 14, 30, 0, tzinfo=UTC)
    event.camera_id = "driveway"
    event.camera = MagicMock()
    event.camera.name = "Driveway"
    event.risk_level = "critical"
    event.risk_score = 90
    event.summary = "Vehicle and person detected at unusual hour"
    event.object_types = "person, vehicle"
    return event


@pytest.fixture
def mock_low_risk_event() -> MagicMock:
    """Create a mock low-risk Event object (should be filtered out)."""
    event = MagicMock(spec=Event)
    event.id = 3
    event.started_at = datetime(2026, 1, 18, 10, 0, 0, tzinfo=UTC)
    event.camera_id = "backyard"
    event.camera = MagicMock()
    event.camera.name = "Backyard"
    event.risk_level = "low"
    event.risk_score = 15
    event.summary = "Bird detected in backyard"
    event.object_types = "bird"
    return event


@pytest.fixture
def mock_summary() -> MagicMock:
    """Create a mock Summary object."""
    summary = MagicMock(spec=Summary)
    summary.id = 1
    summary.summary_type = SummaryType.HOURLY.value
    summary.content = "One critical event occurred at 2:15 PM at the front door."
    summary.event_count = 1
    summary.event_ids = [1]
    summary.window_start = datetime(2026, 1, 18, 13, 15, 0, tzinfo=UTC)
    summary.window_end = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)
    summary.generated_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)
    return summary


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_event_repository(mock_event: MagicMock, mock_critical_event: MagicMock) -> MagicMock:
    """Create a mock EventRepository with test events."""
    repo = MagicMock()
    # Return both high and critical events by default
    repo.get_in_date_range = AsyncMock(return_value=[mock_event, mock_critical_event])
    return repo


@pytest.fixture
def mock_summary_repository(mock_summary: MagicMock) -> MagicMock:
    """Create a mock SummaryRepository."""
    repo = MagicMock()
    repo.create_summary = AsyncMock(return_value=mock_summary)
    return repo


# Tests: Hourly Summary Generation


class TestHourlySummaryGeneration:
    """Tests for generating hourly summaries."""

    @pytest.mark.asyncio
    async def test_generate_hourly_summary_with_events(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test generating hourly summary with high/critical events."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mocks
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[mock_event])
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = (
                "Over the past hour, one high-priority event occurred at 2:15 PM "
                "when an unrecognized person approached the front door."
            )

            # Execute
            result = await generator.generate_hourly_summary(session=mock_session)

            # Verify
            assert result == mock_summary
            mock_event_repo.get_in_date_range.assert_called_once()
            mock_nemotron.assert_called_once()
            mock_summary_repo.create_summary.assert_called_once()

            # Verify create_summary call args
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert call_kwargs["summary_type"] == SummaryType.HOURLY
            assert call_kwargs["event_count"] == 1
            assert call_kwargs["event_ids"] == [mock_event.id]

    @pytest.mark.asyncio
    async def test_generate_hourly_summary_no_events(
        self,
        mock_session: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test generating hourly summary with no high/critical events (all clear)."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mocks - no high/critical events
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[])
            mock_event_repo_cls.return_value = mock_event_repo

            # Empty events summary
            mock_summary.event_count = 0
            mock_summary.event_ids = None
            mock_summary.content = (
                "No high-priority security events in the past hour. "
                "The property has been quiet with only routine activity detected."
            )

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = mock_summary.content

            # Execute
            result = await generator.generate_hourly_summary(session=mock_session)

            # Verify
            assert result.event_count == 0
            assert "No high-priority" in result.content

            # Verify create_summary call args
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert call_kwargs["event_count"] == 0
            assert call_kwargs["event_ids"] is None

    @pytest.mark.asyncio
    async def test_generate_hourly_summary_filters_low_risk(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_low_risk_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test that low-risk events are filtered out of summaries."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mocks - return both high and low risk events
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(
                return_value=[mock_event, mock_low_risk_event]
            )
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = "One high-priority event detected."

            # Execute
            await generator.generate_hourly_summary(session=mock_session)

            # Verify only high-risk event is included
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert call_kwargs["event_count"] == 1
            assert call_kwargs["event_ids"] == [mock_event.id]


# Tests: Daily Summary Generation


class TestDailySummaryGeneration:
    """Tests for generating daily summaries."""

    @pytest.mark.asyncio
    async def test_generate_daily_summary_with_events(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test generating daily summary with multiple events."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mocks
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(
                return_value=[mock_event, mock_critical_event]
            )
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary.summary_type = SummaryType.DAILY.value
            mock_summary.event_count = 2
            mock_summary.event_ids = [mock_event.id, mock_critical_event.id]

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = (
                "Today saw 2 high-priority events. At 2:15 PM, an unrecognized person "
                "approached the front door. At 2:30 PM, a vehicle and person were detected "
                "in the driveway at an unusual hour."
            )

            # Execute
            result = await generator.generate_daily_summary(session=mock_session)

            # Verify
            assert result.event_count == 2
            mock_nemotron.assert_called_once()

            # Verify daily type
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert call_kwargs["summary_type"] == SummaryType.DAILY

    @pytest.mark.asyncio
    async def test_generate_daily_summary_time_window(
        self,
        mock_session: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test that daily summary uses correct time window (midnight to now)."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        captured_start = None
        captured_end = None

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Capture the time window arguments
            async def capture_date_range(
                start: datetime, end: datetime, *, eager_load_camera: bool = False
            ):
                nonlocal captured_start, captured_end
                captured_start = start
                captured_end = end
                return []

            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(side_effect=capture_date_range)
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = "All clear for today."

            # Execute
            await generator.generate_daily_summary(session=mock_session)

            # Verify time window - start should be midnight today
            assert captured_start is not None
            assert captured_start.hour == 0
            assert captured_start.minute == 0
            assert captured_start.second == 0


# Tests: Generate All Summaries


class TestGenerateAllSummaries:
    """Tests for generating both hourly and daily summaries."""

    @pytest.mark.asyncio
    async def test_generate_all_summaries(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test generating both hourly and daily summaries in one call."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        daily_summary = MagicMock(spec=Summary)
        daily_summary.id = 2
        daily_summary.summary_type = SummaryType.DAILY.value
        daily_summary.content = "Daily summary content"

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[mock_event])
            mock_event_repo_cls.return_value = mock_event_repo

            # Return different summaries for hourly vs daily
            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(side_effect=[mock_summary, daily_summary])
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = "Summary text"

            # Execute
            result = await generator.generate_all_summaries(session=mock_session)

            # Verify both summaries returned
            assert "hourly" in result
            assert "daily" in result
            assert result["hourly"] == mock_summary
            assert result["daily"] == daily_summary

            # Verify Nemotron called twice (once per summary type)
            assert mock_nemotron.call_count == 2


# Tests: Fallback Behavior


class TestFallbackBehavior:
    """Tests for fallback behavior when Nemotron is unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_when_nemotron_timeout(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test fallback message when Nemotron times out."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[mock_event])
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            # Simulate timeout
            mock_nemotron.side_effect = TimeoutError("Connection timed out")

            # Execute
            await generator.generate_hourly_summary(session=mock_session)

            # Verify fallback content was used
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert "temporarily unavailable" in call_kwargs["content"]
            assert "1 high/critical events" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_fallback_when_nemotron_connection_error(
        self,
        mock_session: MagicMock,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test fallback message when Nemotron connection fails."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(
                return_value=[mock_event, mock_critical_event]
            )
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            # Simulate connection error
            mock_nemotron.side_effect = httpx.ConnectError("Failed to connect")

            # Execute
            await generator.generate_hourly_summary(session=mock_session)

            # Verify fallback content includes event count
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert "2 high/critical events" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_fallback_with_no_events(
        self,
        mock_session: MagicMock,
        mock_summary: MagicMock,
    ) -> None:
        """Test fallback message when no events and Nemotron fails."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        with (
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[])
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            # Simulate connection error
            mock_nemotron.side_effect = httpx.ConnectError("Failed to connect")

            # Execute
            await generator.generate_hourly_summary(session=mock_session)

            # Verify fallback content for zero events
            call_kwargs = mock_summary_repo.create_summary.call_args.kwargs
            assert "No high-priority" in call_kwargs["content"]


# Tests: Event Context Building


class TestEventContextBuilding:
    """Tests for building event context for prompts."""

    def test_build_event_context_basic(
        self,
        mock_event: MagicMock,
    ) -> None:
        """Test building context from a single event."""
        generator = SummaryGenerator()

        context = generator._build_event_context([mock_event])

        assert len(context) == 1
        assert context[0]["camera_name"] == "Front Door"
        assert context[0]["risk_level"] == "high"
        assert context[0]["risk_score"] == 75
        assert context[0]["summary"] == "Unrecognized person approached the front door"
        assert context[0]["object_types"] == "person"

    def test_build_event_context_multiple_events(
        self,
        mock_event: MagicMock,
        mock_critical_event: MagicMock,
    ) -> None:
        """Test building context from multiple events."""
        generator = SummaryGenerator()

        context = generator._build_event_context([mock_event, mock_critical_event])

        assert len(context) == 2
        assert context[0]["camera_name"] == "Front Door"
        assert context[1]["camera_name"] == "Driveway"
        assert context[1]["risk_level"] == "critical"
        assert context[1]["risk_score"] == 90

    def test_build_event_context_empty(self) -> None:
        """Test building context from empty event list."""
        generator = SummaryGenerator()

        context = generator._build_event_context([])

        assert len(context) == 0

    def test_build_event_context_uses_camera_id_fallback(self) -> None:
        """Test that camera_id is used when camera relationship is None."""
        generator = SummaryGenerator()

        event = MagicMock(spec=Event)
        event.id = 1
        event.started_at = datetime(2026, 1, 18, 14, 15, 0, tzinfo=UTC)
        event.camera_id = "garage_camera"
        event.camera = None  # No camera relationship
        event.risk_level = "high"
        event.risk_score = 70
        event.summary = "Motion detected"
        event.object_types = "person"

        context = generator._build_event_context([event])

        assert context[0]["camera_name"] == "garage_camera"


# Tests: Fallback Content Generation


class TestFallbackContent:
    """Tests for fallback content generation."""

    def test_fallback_content_with_events(self) -> None:
        """Test fallback content when there are events."""
        generator = SummaryGenerator()

        content = generator._get_fallback_content(event_count=3)

        assert "temporarily unavailable" in content
        assert "3 high/critical events" in content

    def test_fallback_content_with_no_events(self) -> None:
        """Test fallback content when there are no events (all clear)."""
        generator = SummaryGenerator()

        content = generator._get_fallback_content(event_count=0)

        assert "No high-priority" in content
        assert "quiet" in content


# Tests: Singleton Pattern


class TestSingletonPattern:
    """Tests for the module-level singleton."""

    def test_get_summary_generator_returns_singleton(self) -> None:
        """Test that get_summary_generator returns the same instance."""
        # Reset singleton for this test
        import backend.services.summary_generator as module

        module._summary_generator = None

        generator1 = get_summary_generator()
        generator2 = get_summary_generator()

        assert generator1 is generator2


# Tests: LLM Call


class TestNemotronCall:
    """Tests for Nemotron LLM call functionality."""

    @pytest.mark.asyncio
    async def test_call_nemotron_formats_prompt_correctly(self) -> None:
        """Test that _call_nemotron formats the prompt with ChatML."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": "Generated summary text here."}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await generator._call_nemotron(
                window_start=datetime(2026, 1, 18, 13, 0, 0, tzinfo=UTC),
                window_end=datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC),
                period_type="hour",
                events=[
                    {
                        "timestamp": "2:15 PM",
                        "camera_name": "Front Door",
                        "risk_level": "high",
                        "risk_score": 75,
                        "summary": "Person detected",
                        "object_types": "person",
                    }
                ],
            )

            # Verify result
            assert result == "Generated summary text here."

            # Verify post was called with correct URL
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "/completion" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_call_nemotron_raises_on_empty_response(self) -> None:
        """Test that empty LLM response raises ValueError."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": ""}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="Empty completion"):
                await generator._call_nemotron(
                    window_start=datetime(2026, 1, 18, 13, 0, 0, tzinfo=UTC),
                    window_end=datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC),
                    period_type="hour",
                    events=[],
                )

    @pytest.mark.asyncio
    async def test_call_nemotron_strips_think_tags(self) -> None:
        """Test that think tags are removed from LLM response."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": "<think>internal reasoning here</think>Clean summary text."
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await generator._call_nemotron(
                window_start=datetime(2026, 1, 18, 13, 0, 0, tzinfo=UTC),
                window_end=datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC),
                period_type="hour",
                events=[],
            )

            # Verify think tags are removed
            assert "<think>" not in result
            assert "internal reasoning" not in result
            assert "Clean summary text." in result


# Tests: Authentication Headers


class TestAuthenticationHeaders:
    """Tests for authentication header generation."""

    def test_get_auth_headers_without_api_key(self) -> None:
        """Test that headers are generated without API key."""
        generator = SummaryGenerator(llm_url="http://localhost:8091", api_key=None)

        headers = generator._get_auth_headers()

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "X-API-Key" not in headers

    def test_get_auth_headers_with_string_api_key(self) -> None:
        """Test that headers include API key when provided as string."""
        generator = SummaryGenerator(llm_url="http://localhost:8091", api_key="test-api-key-123")

        headers = generator._get_auth_headers()

        assert "Content-Type" in headers
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test-api-key-123"

    def test_get_auth_headers_with_secret_str_api_key(self) -> None:
        """Test that headers include API key when provided as SecretStr."""
        from pydantic import SecretStr

        secret_key = SecretStr("secret-api-key-456")
        generator = SummaryGenerator(llm_url="http://localhost:8091", api_key=secret_key)

        headers = generator._get_auth_headers()

        assert "Content-Type" in headers
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "secret-api-key-456"


# Tests: Session Management


class TestSessionManagement:
    """Tests for database session management paths."""

    @pytest.mark.asyncio
    async def test_generate_hourly_summary_without_session(self) -> None:
        """Test generating hourly summary without providing a session."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        mock_summary = MagicMock(spec=Summary)
        mock_summary.id = 1
        mock_summary.content = "Hourly summary"

        with (
            patch("backend.services.summary_generator.get_session") as mock_get_session,
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mock session context manager
            mock_session = MagicMock()
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session_ctx

            # Setup event and summary repos
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[])
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = "All clear"

            # Execute without passing session
            result = await generator.generate_hourly_summary(session=None)

            # Verify result and that get_session was called
            assert result == mock_summary
            mock_get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_daily_summary_without_session(self) -> None:
        """Test generating daily summary without providing a session."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        mock_summary = MagicMock(spec=Summary)
        mock_summary.id = 2
        mock_summary.content = "Daily summary"

        with (
            patch("backend.services.summary_generator.get_session") as mock_get_session,
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mock session context manager
            mock_session = MagicMock()
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session_ctx

            # Setup event and summary repos
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[])
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(return_value=mock_summary)
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = "All clear for today"

            # Execute without passing session
            result = await generator.generate_daily_summary(session=None)

            # Verify result and that get_session was called
            assert result == mock_summary
            mock_get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_all_summaries_without_session(self) -> None:
        """Test generating all summaries without providing a session."""
        generator = SummaryGenerator(llm_url="http://localhost:8091")

        mock_hourly_summary = MagicMock(spec=Summary)
        mock_hourly_summary.id = 1
        mock_hourly_summary.content = "Hourly summary"

        mock_daily_summary = MagicMock(spec=Summary)
        mock_daily_summary.id = 2
        mock_daily_summary.content = "Daily summary"

        with (
            patch("backend.services.summary_generator.get_session") as mock_get_session,
            patch("backend.services.summary_generator.EventRepository") as mock_event_repo_cls,
            patch("backend.services.summary_generator.SummaryRepository") as mock_summary_repo_cls,
            patch.object(generator, "_call_nemotron", new_callable=AsyncMock) as mock_nemotron,
        ):
            # Setup mock session context manager
            mock_session = MagicMock()
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session_ctx

            # Setup event and summary repos
            mock_event_repo = MagicMock()
            mock_event_repo.get_in_date_range = AsyncMock(return_value=[])
            mock_event_repo_cls.return_value = mock_event_repo

            mock_summary_repo = MagicMock()
            mock_summary_repo.create_summary = AsyncMock(
                side_effect=[mock_hourly_summary, mock_daily_summary]
            )
            mock_summary_repo_cls.return_value = mock_summary_repo

            mock_nemotron.return_value = "Summary content"

            # Execute without passing session
            result = await generator.generate_all_summaries(session=None)

            # Verify result and that get_session was called
            assert "hourly" in result
            assert "daily" in result
            assert result["hourly"] == mock_hourly_summary
            assert result["daily"] == mock_daily_summary
            mock_get_session.assert_called_once()
