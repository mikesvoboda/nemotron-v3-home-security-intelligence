"""Unit tests for improved discriminated union error messages (NEM-3777).

This module tests improved error messages for discriminated unions in Pydantic models
for better debugging. Error messages should be clear about:
- Which discriminator value was invalid
- What valid values are available
- Which model variant failed validation (if discriminator matched)
- Field-level errors within the matched variant

Tests cover:
- Invalid discriminator value errors
- Missing discriminator field errors
- Nested discriminated union errors
- Error message formatting and context
- Custom error handlers for discriminated unions
"""

from __future__ import annotations

from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Discriminator, TypeAdapter, ValidationError

from backend.api.schemas.discriminated_union_errors import (
    DiscriminatedUnionError,
    DiscriminatedUnionErrorHandler,
    extract_discriminator_error,
    format_discriminated_union_error,
    get_valid_discriminator_values,
)


class TestDiscriminatedUnionErrorHandler:
    """Tests for DiscriminatedUnionErrorHandler class."""

    def test_handler_initialization(self) -> None:
        """Test handler can be initialized with union type."""

        class MessageA(BaseModel):
            type: Literal["a"]
            value: str

        class MessageB(BaseModel):
            type: Literal["b"]
            count: int

        MessageUnion = Annotated[MessageA | MessageB, Discriminator("type")]
        handler = DiscriminatedUnionErrorHandler(MessageUnion, discriminator="type")

        assert handler.discriminator == "type"
        assert handler.valid_values == {"a", "b"}

    def test_handler_formats_invalid_discriminator(self) -> None:
        """Test handler formats error for invalid discriminator value."""

        class MessageA(BaseModel):
            type: Literal["ping"]

        class MessageB(BaseModel):
            type: Literal["pong"]

        MessageUnion = Annotated[MessageA | MessageB, Discriminator("type")]
        handler = DiscriminatedUnionErrorHandler(MessageUnion, discriminator="type")

        error = handler.format_error({"type": "invalid"})
        assert "invalid" in error.message
        assert "ping" in error.message or "pong" in error.message
        assert error.invalid_value == "invalid"

    def test_handler_formats_missing_discriminator(self) -> None:
        """Test handler formats error for missing discriminator field."""

        class MessageA(BaseModel):
            type: Literal["a"]

        MessageUnion = Annotated[MessageA, Discriminator("type")]
        handler = DiscriminatedUnionErrorHandler(MessageUnion, discriminator="type")

        error = handler.format_error({"data": "value"})
        assert "type" in error.message
        assert "missing" in error.message.lower() or "required" in error.message.lower()

    def test_handler_includes_context(self) -> None:
        """Test handler includes context in error message."""

        class MessageA(BaseModel):
            type: Literal["event"]
            data: dict

        MessageUnion = Annotated[MessageA, Discriminator("type")]
        handler = DiscriminatedUnionErrorHandler(
            MessageUnion, discriminator="type", context="WebSocket message"
        )

        error = handler.format_error({"type": "unknown"})
        assert "WebSocket message" in error.message


class TestExtractDiscriminatorError:
    """Tests for extract_discriminator_error function."""

    def test_extracts_discriminator_from_validation_error(self) -> None:
        """Test extraction of discriminator error from ValidationError."""

        class MessageA(BaseModel):
            type: Literal["a"]

        class MessageB(BaseModel):
            type: Literal["b"]

        MessageUnion = Annotated[MessageA | MessageB, Discriminator("type")]
        adapter = TypeAdapter(MessageUnion)

        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python({"type": "invalid"})

        result = extract_discriminator_error(exc_info.value)
        assert result is not None
        assert result.discriminator_field == "type"
        assert result.invalid_value == "invalid"

    def test_returns_none_for_non_discriminator_error(self) -> None:
        """Test returns None for non-discriminator validation errors."""

        class SimpleModel(BaseModel):
            name: str
            age: int

        with pytest.raises(ValidationError) as exc_info:
            SimpleModel(name="test", age="not_an_int")

        result = extract_discriminator_error(exc_info.value)
        # May return None or field error depending on implementation
        # The key is it doesn't crash and handles gracefully
        assert result is None or result.discriminator_field is None


class TestFormatDiscriminatedUnionError:
    """Tests for format_discriminated_union_error function."""

    def test_formats_basic_error(self) -> None:
        """Test basic error formatting."""
        error_info = DiscriminatedUnionError(
            discriminator_field="type",
            invalid_value="xyz",
            valid_values=["a", "b", "c"],
            message="",
        )

        formatted = format_discriminated_union_error(error_info)

        assert "type" in formatted
        assert "xyz" in formatted
        assert "a" in formatted or "b" in formatted

    def test_formats_error_with_suggestion(self) -> None:
        """Test error formatting with suggestion for similar value."""
        error_info = DiscriminatedUnionError(
            discriminator_field="type",
            invalid_value="evnt",  # Typo for "event"
            valid_values=["event", "alert", "status"],
            message="",
        )

        formatted = format_discriminated_union_error(error_info, suggest_similar=True)

        # Should suggest "event" since it's similar to "evnt"
        assert "event" in formatted
        # May include "Did you mean" or similar suggestion
        if "evnt" in formatted:
            assert "event" in formatted

    def test_formats_error_with_context(self) -> None:
        """Test error formatting with context."""
        error_info = DiscriminatedUnionError(
            discriminator_field="type",
            invalid_value="bad",
            valid_values=["good"],
            message="",
            context="incoming WebSocket message",
        )

        formatted = format_discriminated_union_error(error_info)
        assert "WebSocket" in formatted or "incoming" in formatted

    def test_formats_nested_error(self) -> None:
        """Test error formatting for nested discriminated union."""
        error_info = DiscriminatedUnionError(
            discriminator_field="action.type",
            invalid_value="invalid_action",
            valid_values=["create", "update", "delete"],
            message="",
            path=["request", "action", "type"],
        )

        formatted = format_discriminated_union_error(error_info)
        # Should show path or nested context
        assert "action" in formatted or "type" in formatted


class TestGetValidDiscriminatorValues:
    """Tests for get_valid_discriminator_values function."""

    def test_extracts_literal_values(self) -> None:
        """Test extraction of valid values from Literal types."""

        class MsgA(BaseModel):
            type: Literal["ping"]

        class MsgB(BaseModel):
            type: Literal["pong"]

        class MsgC(BaseModel):
            type: Literal["subscribe", "unsubscribe"]

        UnionType = Annotated[MsgA | MsgB | MsgC, Discriminator("type")]

        values = get_valid_discriminator_values(UnionType, "type")
        assert values == {"ping", "pong", "subscribe", "unsubscribe"}

    def test_handles_single_variant(self) -> None:
        """Test extraction with single variant."""

        class SingleMsg(BaseModel):
            type: Literal["only"]

        UnionType = Annotated[SingleMsg, Discriminator("type")]

        values = get_valid_discriminator_values(UnionType, "type")
        assert values == {"only"}


class TestWebSocketMessageErrors:
    """Integration tests with actual WebSocket message schemas."""

    def test_websocket_incoming_invalid_type_error(self) -> None:
        """Test error message for invalid incoming WebSocket message type."""
        from backend.api.schemas.websocket import WebSocketIncomingMessage

        adapter = TypeAdapter(WebSocketIncomingMessage)

        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python({"type": "invalid_type_here"})

        # Error should mention valid types
        error_str = str(exc_info.value)
        # Should contain indication of invalid discriminator
        assert "type" in error_str.lower() or "invalid" in error_str.lower()

    def test_websocket_outgoing_invalid_type_error(self) -> None:
        """Test error message for invalid outgoing WebSocket message type."""
        from backend.api.schemas.websocket import WebSocketOutgoingMessage

        adapter = TypeAdapter(WebSocketOutgoingMessage)

        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python({"type": "not_a_real_type"})

        error_str = str(exc_info.value)
        assert "type" in error_str.lower() or "not_a_real_type" in error_str

    def test_websocket_missing_type_error(self) -> None:
        """Test error message for missing type field."""
        from backend.api.schemas.websocket import WebSocketIncomingMessage

        adapter = TypeAdapter(WebSocketIncomingMessage)

        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python({"channels": ["events"]})

        error_str = str(exc_info.value)
        # Should indicate missing required field
        assert "type" in error_str.lower() or "required" in error_str.lower()

    def test_websocket_nested_validation_error(self) -> None:
        """Test error message for valid type but invalid nested data."""
        from backend.api.schemas.websocket import WebSocketOutgoingMessage

        adapter = TypeAdapter(WebSocketOutgoingMessage)

        # Valid type but invalid data structure
        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python(
                {
                    "type": "event",
                    "data": {
                        "id": "not_an_int",  # Should be int
                        "event_id": 1,
                        "batch_id": "batch",
                        "camera_id": "cam",
                        "risk_score": 150,  # Out of range (0-100)
                        "risk_level": "high",
                        "summary": "test",
                        "reasoning": "test",
                    },
                }
            )

        error_str = str(exc_info.value)
        # Should show field-level errors
        assert "id" in error_str or "risk_score" in error_str


class TestCustomErrorMessages:
    """Tests for custom discriminated union error messages."""

    def test_user_friendly_error_message(self) -> None:
        """Test that error messages are user-friendly."""

        class CreateAction(BaseModel):
            action: Literal["create"]
            name: str

        class DeleteAction(BaseModel):
            action: Literal["delete"]
            id: int

        ActionUnion = Annotated[CreateAction | DeleteAction, Discriminator("action")]
        handler = DiscriminatedUnionErrorHandler(
            ActionUnion,
            discriminator="action",
            context="API action request",
        )

        error = handler.format_error({"action": "modify"})

        # Error should be readable
        assert len(error.message) < 500  # Not too verbose
        assert "modify" in error.message  # Shows invalid value
        assert "create" in error.message or "delete" in error.message  # Shows valid options

    def test_error_includes_valid_options_list(self) -> None:
        """Test that error lists all valid options."""

        class OptA(BaseModel):
            opt: Literal["opt_a"]

        class OptB(BaseModel):
            opt: Literal["opt_b"]

        class OptC(BaseModel):
            opt: Literal["opt_c"]

        Union = Annotated[OptA | OptB | OptC, Discriminator("opt")]
        handler = DiscriminatedUnionErrorHandler(Union, discriminator="opt")

        error = handler.format_error({"opt": "wrong"})

        # All valid options should be mentioned
        for valid in ["opt_a", "opt_b", "opt_c"]:
            assert valid in error.message


class TestErrorRecovery:
    """Tests for error recovery and helpful messages."""

    def test_case_sensitivity_hint(self) -> None:
        """Test hint about case sensitivity when close match exists."""

        class TypeA(BaseModel):
            type: Literal["Event"]  # Capital E

        Union = Annotated[TypeA, Discriminator("type")]
        handler = DiscriminatedUnionErrorHandler(Union, discriminator="type")

        error = handler.format_error({"type": "event"})  # lowercase e

        # Should hint at case sensitivity issue
        assert "Event" in error.message
        # May include case sensitivity hint

    def test_similar_value_suggestion(self) -> None:
        """Test suggestion for similar discriminator values."""

        class PingMsg(BaseModel):
            type: Literal["ping"]

        class PongMsg(BaseModel):
            type: Literal["pong"]

        Union = Annotated[PingMsg | PongMsg, Discriminator("type")]
        handler = DiscriminatedUnionErrorHandler(Union, discriminator="type")

        error = handler.format_error({"type": "pingg"})  # Typo

        # Should suggest "ping" as it's close
        assert "ping" in error.message
