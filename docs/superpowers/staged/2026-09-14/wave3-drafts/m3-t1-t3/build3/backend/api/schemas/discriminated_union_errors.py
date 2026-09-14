"""Improved discriminated union error messages (NEM-3777).

This module provides utilities for generating better error messages when
validating discriminated unions in Pydantic models. Clear error messages help
with debugging by showing:
- Which discriminator value was invalid
- What valid values are available
- Which model variant failed validation
- Suggestions for similar values (typo detection)

Usage:
    from backend.api.schemas.discriminated_union_errors import (
        DiscriminatedUnionErrorHandler,
        format_discriminated_union_error,
    )

    # Create handler for a discriminated union
    handler = DiscriminatedUnionErrorHandler(
        MyUnionType,
        discriminator="type",
        context="API request",
    )

    # Format error for invalid input
    error = handler.format_error({"type": "invalid_value"})
    print(error.message)
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, get_args, get_origin

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "DiscriminatedUnionError",
    "DiscriminatedUnionErrorHandler",
    "extract_discriminator_error",
    "format_discriminated_union_error",
    "get_valid_discriminator_values",
]

UnionT = TypeVar("UnionT")


@dataclass
class DiscriminatedUnionError:
    """Structured error information for discriminated union validation failures.

    Attributes:
        discriminator_field: Name of the discriminator field
        invalid_value: The invalid discriminator value that was provided
        valid_values: List of valid discriminator values
        message: Formatted error message
        context: Optional context about where the error occurred
        path: Optional path to the error location in nested structures
    """

    discriminator_field: str | None
    invalid_value: Any
    valid_values: list[str]
    message: str
    context: str | None = None
    path: list[str] = field(default_factory=list)


class DiscriminatedUnionErrorHandler:
    """Handler for creating clear error messages for discriminated unions.

    This class inspects a discriminated union type and provides methods
    for generating helpful error messages when validation fails.

    Attributes:
        union_type: The discriminated union type being handled
        discriminator: Name of the discriminator field
        valid_values: Set of valid discriminator values
        context: Optional context string for error messages
    """

    def __init__(
        self,
        union_type: type[Any],
        discriminator: str,
        context: str | None = None,
    ) -> None:
        """Initialize the error handler.

        Args:
            union_type: The discriminated union type (Annotated[A | B, Discriminator("type")])
            discriminator: Name of the discriminator field
            context: Optional context for error messages (e.g., "WebSocket message")
        """
        self.union_type = union_type
        self.discriminator = discriminator
        self.context = context
        self.valid_values = get_valid_discriminator_values(union_type, discriminator)

    def format_error(self, data: dict[str, Any]) -> DiscriminatedUnionError:
        """Format an error message for invalid input data.

        Args:
            data: The input data that failed validation

        Returns:
            DiscriminatedUnionError with formatted message and metadata
        """
        invalid_value = data.get(self.discriminator)

        if invalid_value is None:
            # Missing discriminator field
            message = self._format_missing_discriminator_message()
        else:
            # Invalid discriminator value
            message = self._format_invalid_value_message(invalid_value)

        return DiscriminatedUnionError(
            discriminator_field=self.discriminator,
            invalid_value=invalid_value,
            valid_values=sorted(self.valid_values),
            message=message,
            context=self.context,
        )

    def _format_missing_discriminator_message(self) -> str:
        """Format message for missing discriminator field."""
        valid_list = ", ".join(f"'{v}'" for v in sorted(self.valid_values))
        context_str = f" for {self.context}" if self.context else ""

        return (
            f"Missing required field '{self.discriminator}'{context_str}. "
            f"Valid values are: {valid_list}"
        )

    def _format_invalid_value_message(self, invalid_value: Any) -> str:
        """Format message for invalid discriminator value."""
        valid_list = ", ".join(f"'{v}'" for v in sorted(self.valid_values))
        context_str = f" for {self.context}" if self.context else ""

        message = (
            f"Invalid {self.discriminator} value '{invalid_value}'{context_str}. "
            f"Valid values are: {valid_list}"
        )

        # Add suggestion if there's a close match
        suggestion = self._find_similar_value(str(invalid_value))
        if suggestion:
            message += f". Did you mean '{suggestion}'?"

        return message

    def _find_similar_value(self, value: str) -> str | None:
        """Find a similar valid value for typo suggestions.

        Args:
            value: The invalid value to find matches for

        Returns:
            The most similar valid value, or None if no close match
        """
        matches = difflib.get_close_matches(
            value.lower(),
            [v.lower() for v in self.valid_values],
            n=1,
            cutoff=0.6,
        )
        if matches:
            # Find the original case version
            for valid in self.valid_values:
                if valid.lower() == matches[0]:
                    return valid
        return None


def get_valid_discriminator_values(union_type: type[Any], discriminator: str) -> set[str]:
    """Extract valid discriminator values from a discriminated union type.

    Inspects the union type to find all Literal values used for the
    discriminator field across all variants.

    Args:
        union_type: The discriminated union type
        discriminator: Name of the discriminator field

    Returns:
        Set of valid discriminator values

    Example:
        class MsgA(BaseModel):
            type: Literal["a"]

        class MsgB(BaseModel):
            type: Literal["b", "c"]

        Union = Annotated[MsgA | MsgB, Discriminator("type")]
        values = get_valid_discriminator_values(Union, "type")
        # Returns {"a", "b", "c"}
    """
    import types
    from typing import Union

    valid_values: set[str] = set()

    # Handle Annotated types
    origin = get_origin(union_type)
    if origin is Annotated:
        args = get_args(union_type)
        if args:
            union_type = args[0]
            origin = get_origin(union_type)

    # Get union members - handle both typing.Union and types.UnionType (Python 3.10+)
    union_args: Sequence[type[Any]] = []
    if origin is Union or origin is types.UnionType:
        # It's a Union type
        union_args = get_args(union_type)
    elif origin is not None:
        # Some other generic type
        union_args = get_args(union_type)
    # Single type or types.UnionType itself
    # Check if it's a UnionType directly (for A | B syntax)
    elif hasattr(union_type, "__args__"):
        union_args = union_type.__args__
    else:
        union_args = [union_type]

    # Extract Literal values from each member
    for member in union_args:
        if isinstance(member, type) and issubclass(member, BaseModel):
            # Get the discriminator field's type hints
            # Use model_fields for Pydantic v2 compatibility
            if hasattr(member, "model_fields"):
                # Pydantic v2
                model_fields = member.model_fields
                if discriminator in model_fields:
                    field_info = model_fields[discriminator]
                    # Get annotation from the field
                    field_type = field_info.annotation
                    if field_type is not None:
                        literal_values = _extract_literal_values(field_type)
                        valid_values.update(literal_values)
            else:
                # Fallback to __annotations__
                hints = getattr(member, "__annotations__", {})
                if discriminator in hints:
                    field_type = hints[discriminator]
                    literal_values = _extract_literal_values(field_type)
                    valid_values.update(literal_values)

    return valid_values


def _extract_literal_values(field_type: type[Any]) -> set[str]:
    """Extract values from a Literal type.

    Args:
        field_type: A Literal type annotation

    Returns:
        Set of literal values as strings
    """
    origin = get_origin(field_type)

    # Handle Literal directly
    from typing import Literal

    if origin is Literal:
        args = get_args(field_type)
        return {str(arg) for arg in args}

    # Handle nested types (e.g., Annotated[Literal[...], ...])
    if origin is Annotated:
        args = get_args(field_type)
        if args:
            return _extract_literal_values(args[0])

    return set()


def extract_discriminator_error(error: ValidationError) -> DiscriminatedUnionError | None:
    """Extract discriminator error information from a ValidationError.

    Parses a Pydantic ValidationError to extract information about
    discriminator validation failures.

    Args:
        error: The ValidationError to extract from

    Returns:
        DiscriminatedUnionError if a discriminator error was found, None otherwise
    """
    for err in error.errors():
        err_type = err.get("type", "")

        # Check for discriminator-related error types
        if "union_tag_invalid" in err_type:
            # For Pydantic v2 discriminator errors, the field name is in ctx
            ctx = err.get("ctx", {})
            discriminator_raw = ctx.get("discriminator", "")
            # The discriminator is quoted, e.g., "'type'" -> "type"
            discriminator_field = discriminator_raw.strip("'\"") if discriminator_raw else None

            # Get the invalid value from ctx
            invalid_value = ctx.get("tag")

            # Get expected tags from ctx
            expected_tags_raw = ctx.get("expected_tags", "")
            valid_values = [
                t.strip().strip("'\"") for t in expected_tags_raw.split(",") if t.strip()
            ]

            loc = err.get("loc", ())

            return DiscriminatedUnionError(
                discriminator_field=discriminator_field,
                invalid_value=invalid_value,
                valid_values=valid_values,
                message=str(err.get("msg", "")),
                path=[str(item) for item in loc],
            )

        # Check for literal_error (when discriminator matched but literal value wrong)
        if "literal_error" in err_type:
            loc = err.get("loc", ())
            discriminator_field = str(loc[-1]) if loc else None

            ctx = err.get("ctx", {})
            invalid_value = ctx.get("given")

            return DiscriminatedUnionError(
                discriminator_field=discriminator_field,
                invalid_value=invalid_value,
                valid_values=[],
                message=str(err.get("msg", "")),
                path=[str(item) for item in loc],
            )

        # Check for missing field that's the discriminator
        if err_type == "missing":
            loc = err.get("loc", ())
            return DiscriminatedUnionError(
                discriminator_field=str(loc[-1]) if loc else None,
                invalid_value=None,
                valid_values=[],
                message=str(err.get("msg", "")),
                path=[str(item) for item in loc],
            )

    return None


def format_discriminated_union_error(
    error: DiscriminatedUnionError,
    suggest_similar: bool = True,
) -> str:
    """Format a discriminated union error into a user-friendly message.

    Args:
        error: The error information to format
        suggest_similar: Whether to include suggestions for similar values

    Returns:
        Formatted error message string
    """
    if error.discriminator_field is None:
        return error.message or "Unknown validation error"

    # Build the base message
    if error.invalid_value is None:
        message = f"Missing required field '{error.discriminator_field}'"
    else:
        message = f"Invalid value '{error.invalid_value}' for field '{error.discriminator_field}'"

    # Add context if available
    if error.context:
        message += f" in {error.context}"

    # Add valid values
    if error.valid_values:
        valid_list = ", ".join(f"'{v}'" for v in error.valid_values)
        message += f". Valid values are: {valid_list}"

    # Add suggestion if enabled and there's a close match
    if suggest_similar and error.invalid_value is not None and error.valid_values:
        suggestion = _find_closest_match(str(error.invalid_value), error.valid_values)
        if suggestion:
            message += f". Did you mean '{suggestion}'?"

    # Add path information for nested errors
    if error.path and len(error.path) > 1:
        path_str = ".".join(error.path)
        message += f" (at path: {path_str})"

    return message


def _find_closest_match(value: str, candidates: list[str]) -> str | None:
    """Find the closest matching candidate for a value.

    Args:
        value: The value to match
        candidates: List of candidate values

    Returns:
        The closest match, or None if no close match found
    """
    matches = difflib.get_close_matches(
        value.lower(),
        [c.lower() for c in candidates],
        n=1,
        cutoff=0.6,
    )
    if matches:
        # Return original case version
        for candidate in candidates:
            if candidate.lower() == matches[0]:
                return candidate
    return None
