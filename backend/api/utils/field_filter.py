"""Field filtering utility for sparse fieldsets (NEM-1434).

This module provides utilities for field selection in API responses, allowing
clients to request only specific fields to reduce payload size and bandwidth.

Usage:
    GET /api/events?fields=id,camera_id,risk_level,summary,reviewed

Example:
    from backend.api.utils.field_filter import parse_fields_param, validate_fields, filter_fields

    # Parse the fields query parameter
    requested_fields = parse_fields_param(fields_param)

    # Validate against allowed fields for the endpoint
    validated_fields = validate_fields(requested_fields, VALID_EVENT_FIELDS)

    # Filter each item in the response
    filtered_events = [filter_fields(event, validated_fields) for event in events]
"""

from __future__ import annotations

from typing import Any


class FieldFilterError(Exception):
    """Exception raised when invalid fields are requested.

    Attributes:
        invalid_fields: Set of field names that were not valid
        valid_fields: Set of valid field names for reference
    """

    def __init__(self, invalid_fields: set[str], valid_fields: set[str]) -> None:
        """Initialize FieldFilterError with invalid and valid fields.

        Args:
            invalid_fields: Set of field names that were not valid
            valid_fields: Set of valid field names for reference
        """
        self.invalid_fields = invalid_fields
        self.valid_fields = valid_fields
        invalid_list = ", ".join(sorted(invalid_fields))
        valid_list = ", ".join(sorted(valid_fields))
        message = f"Invalid field(s) requested: {invalid_list}. Valid fields are: {valid_list}"
        super().__init__(message)


def parse_fields_param(fields: str | None | Any) -> set[str] | None:
    """Parse the fields query parameter into a set of field names.

    Handles comma-separated field names with optional whitespace.
    Field names are normalized to lowercase.

    Args:
        fields: Comma-separated string of field names, None, or a FastAPI Query object

    Returns:
        Set of lowercase field names, or None if no fields specified
        (meaning no filtering should be applied)

    Examples:
        >>> parse_fields_param("id,name,status")
        {'id', 'name', 'status'}
        >>> parse_fields_param("id , name , status")
        {'id', 'name', 'status'}
        >>> parse_fields_param(None)
        None
        >>> parse_fields_param("")
        None
    """
    # Handle FastAPI Query objects (occurs when tests call route handlers directly)
    if hasattr(fields, "default"):
        fields = fields.default  # type: ignore[union-attr]

    if fields is None or (isinstance(fields, str) and fields.strip() == ""):
        return None

    # Split by comma, strip whitespace, normalize to lowercase, filter empty
    parsed = {field.strip().lower() for field in fields.split(",") if field.strip()}

    return parsed if parsed else None


def validate_fields(
    requested: set[str] | None,
    allowed: set[str],
) -> set[str] | None:
    """Validate requested fields against allowed fields.

    Args:
        requested: Set of requested field names, or None for no filtering
        allowed: Set of valid field names for the endpoint

    Returns:
        The validated set of fields, or None if no fields were requested

    Raises:
        FieldFilterError: If any requested fields are not in the allowed set
    """
    if requested is None:
        return None

    invalid = requested - allowed
    if invalid:
        raise FieldFilterError(invalid_fields=invalid, valid_fields=allowed)

    return requested


def filter_fields(data: dict, allowed_fields: set[str] | None) -> dict:
    """Filter a dictionary to include only specified fields.

    Preserves the order of keys from the original dictionary.
    Handles nested dictionaries and lists by preserving them as-is.

    Args:
        data: Dictionary to filter
        allowed_fields: Set of field names to include, or None for all fields

    Returns:
        New dictionary containing only the allowed fields.
        If allowed_fields is None, returns a shallow copy of the original dict.

    Examples:
        >>> filter_fields({"id": 1, "name": "test", "status": "active"}, {"id", "name"})
        {'id': 1, 'name': 'test'}
        >>> filter_fields({"id": 1, "name": "test"}, None)
        {'id': 1, 'name': 'test'}
    """
    if allowed_fields is None:
        # Return a copy to ensure caller can't accidentally modify original
        return dict(data)

    # Filter while preserving key order from original dict
    return {key: value for key, value in data.items() if key in allowed_fields}
