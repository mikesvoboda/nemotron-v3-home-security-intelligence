"""Unit tests for WebSocket summary message schemas (NEM-2893).

Tests cover:
- WebSocketSummaryData model validation
- WebSocketSummaryUpdateData model validation
- WebSocketSummaryUpdateMessage schema
- Field validation and error handling
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    WebSocketSummaryData,
    WebSocketSummaryUpdateData,
    WebSocketSummaryUpdateMessage,
)


class TestWebSocketSummaryData:
    """Tests for WebSocketSummaryData schema validation."""

    @pytest.fixture
    def valid_summary_data(self) -> dict:
        """Create valid summary data for testing."""
        return {
            "id": 1,
            "content": (
                "Over the past hour, one critical event occurred at 2:15 PM "
                "when an unrecognized person approached the front door."
            ),
            "event_count": 1,
            "window_start": "2026-01-18T14:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }

    def test_valid_summary_data(self, valid_summary_data: dict) -> None:
        """Test that valid summary data passes validation."""
        data = WebSocketSummaryData.model_validate(valid_summary_data)
        assert data.id == valid_summary_data["id"]
        assert data.content == valid_summary_data["content"]
        assert data.event_count == valid_summary_data["event_count"]
        assert data.window_start == valid_summary_data["window_start"]
        assert data.window_end == valid_summary_data["window_end"]
        assert data.generated_at == valid_summary_data["generated_at"]

    def test_summary_data_with_zero_events(self, valid_summary_data: dict) -> None:
        """Test that summary with zero events passes validation."""
        valid_summary_data["event_count"] = 0
        valid_summary_data["content"] = "All clear. No high-priority events detected."
        data = WebSocketSummaryData.model_validate(valid_summary_data)
        assert data.event_count == 0

    def test_missing_id_fails(self, valid_summary_data: dict) -> None:
        """Test that missing id fails validation."""
        del valid_summary_data["id"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "id" in str(exc_info.value)

    def test_missing_content_fails(self, valid_summary_data: dict) -> None:
        """Test that missing content fails validation."""
        del valid_summary_data["content"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "content" in str(exc_info.value)

    def test_missing_event_count_fails(self, valid_summary_data: dict) -> None:
        """Test that missing event_count fails validation."""
        del valid_summary_data["event_count"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "event_count" in str(exc_info.value)

    def test_negative_event_count_fails(self, valid_summary_data: dict) -> None:
        """Test that negative event_count fails validation."""
        valid_summary_data["event_count"] = -1
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "event_count" in str(exc_info.value)

    def test_missing_window_start_fails(self, valid_summary_data: dict) -> None:
        """Test that missing window_start fails validation."""
        del valid_summary_data["window_start"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "window_start" in str(exc_info.value)

    def test_missing_window_end_fails(self, valid_summary_data: dict) -> None:
        """Test that missing window_end fails validation."""
        del valid_summary_data["window_end"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "window_end" in str(exc_info.value)

    def test_missing_generated_at_fails(self, valid_summary_data: dict) -> None:
        """Test that missing generated_at fails validation."""
        del valid_summary_data["generated_at"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryData.model_validate(valid_summary_data)
        assert "generated_at" in str(exc_info.value)


class TestWebSocketSummaryUpdateData:
    """Tests for WebSocketSummaryUpdateData schema validation."""

    @pytest.fixture
    def valid_hourly_summary(self) -> dict:
        """Create valid hourly summary for testing."""
        return {
            "id": 1,
            "content": "Hourly summary content.",
            "event_count": 1,
            "window_start": "2026-01-18T14:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }

    @pytest.fixture
    def valid_daily_summary(self) -> dict:
        """Create valid daily summary for testing."""
        return {
            "id": 2,
            "content": "Daily summary content.",
            "event_count": 3,
            "window_start": "2026-01-18T00:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }

    def test_valid_with_both_summaries(
        self, valid_hourly_summary: dict, valid_daily_summary: dict
    ) -> None:
        """Test that valid data with both summaries passes validation."""
        data = WebSocketSummaryUpdateData.model_validate(
            {"hourly": valid_hourly_summary, "daily": valid_daily_summary}
        )
        assert data.hourly is not None
        assert data.hourly.id == 1
        assert data.daily is not None
        assert data.daily.id == 2

    def test_valid_with_only_hourly(self, valid_hourly_summary: dict) -> None:
        """Test that valid data with only hourly passes validation."""
        data = WebSocketSummaryUpdateData.model_validate(
            {"hourly": valid_hourly_summary, "daily": None}
        )
        assert data.hourly is not None
        assert data.hourly.id == 1
        assert data.daily is None

    def test_valid_with_only_daily(self, valid_daily_summary: dict) -> None:
        """Test that valid data with only daily passes validation."""
        data = WebSocketSummaryUpdateData.model_validate(
            {"hourly": None, "daily": valid_daily_summary}
        )
        assert data.hourly is None
        assert data.daily is not None
        assert data.daily.id == 2

    def test_valid_with_both_none(self) -> None:
        """Test that valid data with both None passes validation."""
        data = WebSocketSummaryUpdateData.model_validate({"hourly": None, "daily": None})
        assert data.hourly is None
        assert data.daily is None

    def test_valid_with_omitted_fields(self) -> None:
        """Test that omitted fields default to None."""
        data = WebSocketSummaryUpdateData.model_validate({})
        assert data.hourly is None
        assert data.daily is None

    def test_invalid_hourly_fails(self, valid_daily_summary: dict) -> None:
        """Test that invalid hourly summary fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryUpdateData.model_validate(
                {"hourly": {"id": "not-an-int"}, "daily": valid_daily_summary}
            )
        assert "hourly" in str(exc_info.value)

    def test_invalid_daily_fails(self, valid_hourly_summary: dict) -> None:
        """Test that invalid daily summary fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSummaryUpdateData.model_validate(
                {"hourly": valid_hourly_summary, "daily": {"missing": "fields"}}
            )
        assert "daily" in str(exc_info.value)


class TestWebSocketSummaryUpdateMessage:
    """Tests for WebSocketSummaryUpdateMessage schema validation."""

    @pytest.fixture
    def valid_hourly_summary(self) -> dict:
        """Create valid hourly summary for testing."""
        return {
            "id": 1,
            "content": "Hourly summary content.",
            "event_count": 1,
            "window_start": "2026-01-18T14:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }

    @pytest.fixture
    def valid_daily_summary(self) -> dict:
        """Create valid daily summary for testing."""
        return {
            "id": 2,
            "content": "Daily summary content.",
            "event_count": 3,
            "window_start": "2026-01-18T00:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }

    def test_valid_message(self, valid_hourly_summary: dict, valid_daily_summary: dict) -> None:
        """Test that valid message passes validation."""
        message = WebSocketSummaryUpdateMessage.model_validate(
            {
                "type": "summary_update",
                "data": {"hourly": valid_hourly_summary, "daily": valid_daily_summary},
            }
        )
        assert message.type == "summary_update"
        assert message.data.hourly is not None
        assert message.data.daily is not None

    def test_type_defaults_to_summary_update(self, valid_hourly_summary: dict) -> None:
        """Test that type defaults to 'summary_update'."""
        message = WebSocketSummaryUpdateMessage(
            data=WebSocketSummaryUpdateData(
                hourly=WebSocketSummaryData.model_validate(valid_hourly_summary)
            )
        )
        assert message.type == "summary_update"

    def test_invalid_type_fails(
        self, valid_hourly_summary: dict, valid_daily_summary: dict
    ) -> None:
        """Test that invalid type fails validation."""
        with pytest.raises(ValidationError):
            WebSocketSummaryUpdateMessage.model_validate(
                {
                    "type": "wrong_type",
                    "data": {"hourly": valid_hourly_summary, "daily": valid_daily_summary},
                }
            )

    def test_model_dump_json(self, valid_hourly_summary: dict, valid_daily_summary: dict) -> None:
        """Test that model_dump produces correct JSON structure."""
        message = WebSocketSummaryUpdateMessage.model_validate(
            {
                "type": "summary_update",
                "data": {"hourly": valid_hourly_summary, "daily": valid_daily_summary},
            }
        )
        dumped = message.model_dump(mode="json")

        assert dumped["type"] == "summary_update"
        assert "data" in dumped
        assert dumped["data"]["hourly"]["id"] == 1
        assert dumped["data"]["daily"]["id"] == 2

    def test_message_with_null_summaries(self) -> None:
        """Test that message with null summaries passes validation."""
        message = WebSocketSummaryUpdateMessage.model_validate(
            {
                "type": "summary_update",
                "data": {"hourly": None, "daily": None},
            }
        )
        assert message.type == "summary_update"
        assert message.data.hourly is None
        assert message.data.daily is None
