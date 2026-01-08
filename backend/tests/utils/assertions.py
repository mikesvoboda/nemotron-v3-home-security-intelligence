"""Common assertion helpers for test validation.

This module provides reusable assertion functions for validating HTTP responses,
JSON data structures, and common API patterns used throughout the backend tests.

Usage Examples
==============

Assert response contains expected keys:

    >>> response = await client.get("/api/cameras")
    >>> assert_json_contains(response, ["id", "name", "status"])

Assert response is successful:

    >>> response = await client.get("/api/health")
    >>> assert_status_ok(response)

Assert validation error for a specific field:

    >>> response = await client.post("/api/cameras", json={"name": ""})
    >>> assert_validation_error(response, "name")

Assert response matches schema keys:

    >>> response = await client.get("/api/cameras/front_door")
    >>> assert_json_schema(response, {"id": str, "name": str, "status": str})
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx import Response


def assert_json_contains(response: Response, expected_keys: list[str]) -> None:
    """Assert that response JSON contains all expected keys.

    Args:
        response: HTTP response object with .json() method
        expected_keys: List of keys that must be present in the response JSON

    Raises:
        AssertionError: If any expected key is missing from the response

    Example:
        >>> response = await client.get("/api/cameras/front_door")
        >>> assert_json_contains(response, ["id", "name", "status", "last_seen"])
    """
    data = response.json()
    missing_keys = [key for key in expected_keys if key not in data]
    if missing_keys:
        raise AssertionError(
            f"Response JSON missing expected keys: {missing_keys}. Got keys: {list(data.keys())}"
        )


def assert_json_not_contains(response: Response, forbidden_keys: list[str]) -> None:
    """Assert that response JSON does not contain any forbidden keys.

    Useful for testing that sensitive data is not exposed in API responses.

    Args:
        response: HTTP response object with .json() method
        forbidden_keys: List of keys that must NOT be present in the response JSON

    Raises:
        AssertionError: If any forbidden key is found in the response

    Example:
        >>> response = await client.get("/api/users/me")
        >>> assert_json_not_contains(response, ["password_hash", "api_key_hash"])
    """
    data = response.json()
    found_keys = [key for key in forbidden_keys if key in data]
    if found_keys:
        raise AssertionError(
            f"Response JSON contains forbidden keys: {found_keys}. "
            f"These should not be exposed in API responses."
        )


def assert_status_ok(response: Response) -> None:
    """Assert that response has a successful HTTP status code (2xx).

    Args:
        response: HTTP response object with .status_code attribute

    Raises:
        AssertionError: If status code is not in the 2xx range

    Example:
        >>> response = await client.get("/api/health")
        >>> assert_status_ok(response)
    """
    if not 200 <= response.status_code < 300:
        try:
            body = response.json()
        except Exception:
            body = response.text[:500] if response.text else "(empty body)"
        raise AssertionError(
            f"Expected successful status (2xx), got {response.status_code}. Response body: {body}"
        )


def assert_status_code(response: Response, expected: int) -> None:
    """Assert that response has a specific HTTP status code.

    Args:
        response: HTTP response object with .status_code attribute
        expected: Expected HTTP status code

    Raises:
        AssertionError: If status code does not match expected

    Example:
        >>> response = await client.post("/api/cameras", json={})
        >>> assert_status_code(response, 422)
    """
    if response.status_code != expected:
        try:
            body = response.json()
        except Exception:
            body = response.text[:500] if response.text else "(empty body)"
        raise AssertionError(
            f"Expected status {expected}, got {response.status_code}. Response body: {body}"
        )


def assert_validation_error(response: Response, field: str) -> None:
    """Assert that response is a 422 validation error mentioning a specific field.

    Args:
        response: HTTP response object
        field: Field name that should be mentioned in the validation error

    Raises:
        AssertionError: If response is not 422 or field is not mentioned

    Example:
        >>> response = await client.post("/api/cameras", json={"name": ""})
        >>> assert_validation_error(response, "name")
    """
    if response.status_code != 422:
        raise AssertionError(
            f"Expected 422 validation error, got {response.status_code}. "
            f"Response: {response.text[:500]}"
        )

    try:
        data = response.json()
    except Exception as e:
        raise AssertionError(f"Could not parse response JSON: {e}") from e

    # FastAPI validation errors have {"detail": [...]} structure
    detail = data.get("detail", [])
    if isinstance(detail, list):
        # Check if field is mentioned in any error
        error_str = str(detail)
        if field.lower() not in error_str.lower():
            raise AssertionError(
                f"Validation error does not mention field '{field}'. Got errors: {detail}"
            )
    # String error message
    elif field.lower() not in str(detail).lower():
        raise AssertionError(
            f"Validation error does not mention field '{field}'. Got error: {detail}"
        )


def assert_json_schema(response: Response, schema: dict[str, type]) -> None:
    """Assert that response JSON matches a simple type schema.

    This is a lightweight schema validation for basic type checking.
    For complex schemas, consider using pydantic models instead.

    Args:
        response: HTTP response object with .json() method
        schema: Dict mapping key names to expected types

    Raises:
        AssertionError: If any key is missing or has wrong type

    Example:
        >>> response = await client.get("/api/cameras/front_door")
        >>> assert_json_schema(response, {
        ...     "id": str,
        ...     "name": str,
        ...     "status": str,
        ...     "enabled": bool,
        ... })
    """
    data = response.json()
    errors = []

    for key, expected_type in schema.items():
        if key not in data:
            errors.append(f"Missing key: '{key}'")
            continue

        value = data[key]
        # Allow None for optional fields (type is Optional[X])
        if value is None:
            continue

        if not isinstance(value, expected_type):
            errors.append(
                f"Key '{key}' has wrong type: expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

    if errors:
        raise AssertionError(f"Schema validation failed: {'; '.join(errors)}")


def assert_json_list(
    response: Response,
    min_length: int = 0,
    max_length: int | None = None,
    item_keys: list[str] | None = None,
) -> None:
    """Assert that response JSON is a list with optional constraints.

    Args:
        response: HTTP response object with .json() method
        min_length: Minimum expected list length (default 0)
        max_length: Maximum expected list length (default None for no limit)
        item_keys: If provided, assert each item contains these keys

    Raises:
        AssertionError: If response is not a list or constraints are violated

    Example:
        >>> response = await client.get("/api/cameras")
        >>> assert_json_list(response, min_length=1, item_keys=["id", "name"])
    """
    data = response.json()

    if not isinstance(data, list):
        raise AssertionError(f"Expected list response, got {type(data).__name__}")

    if len(data) < min_length:
        raise AssertionError(f"Expected at least {min_length} items, got {len(data)}")

    if max_length is not None and len(data) > max_length:
        raise AssertionError(f"Expected at most {max_length} items, got {len(data)}")

    if item_keys:
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise AssertionError(f"Item {i} is not a dict: got {type(item).__name__}")
            missing_keys = [k for k in item_keys if k not in item]
            if missing_keys:
                raise AssertionError(
                    f"Item {i} missing keys: {missing_keys}. Got: {list(item.keys())}"
                )


def assert_error_response(
    response: Response,
    status_code: int,
    message_contains: str | None = None,
) -> None:
    """Assert that response is an error with specific status and optional message.

    Args:
        response: HTTP response object
        status_code: Expected HTTP status code (4xx or 5xx)
        message_contains: Optional substring to find in the error message

    Raises:
        AssertionError: If status code doesn't match or message not found

    Example:
        >>> response = await client.get("/api/cameras/nonexistent")
        >>> assert_error_response(response, 404, message_contains="not found")
    """
    if response.status_code != status_code:
        raise AssertionError(
            f"Expected status {status_code}, got {response.status_code}. "
            f"Response: {response.text[:500]}"
        )

    if message_contains:
        try:
            data = response.json()
            # Check common error message locations
            error_text = str(data.get("detail", "")) + str(data.get("message", ""))
        except Exception:
            error_text = response.text

        if message_contains.lower() not in error_text.lower():
            raise AssertionError(
                f"Error message does not contain '{message_contains}'. Got: {error_text[:500]}"
            )


def assert_pagination_response(
    response: Response,
    items_key: str = "items",
    total_key: str = "total",
    page_key: str = "page",
    page_size_key: str = "page_size",
) -> dict[str, Any]:
    """Assert that response is a paginated response with expected structure.

    Args:
        response: HTTP response object with .json() method
        items_key: Key for the list of items (default "items")
        total_key: Key for total count (default "total")
        page_key: Key for current page (default "page")
        page_size_key: Key for page size (default "page_size")

    Returns:
        The parsed response data for further assertions

    Raises:
        AssertionError: If pagination structure is invalid

    Example:
        >>> response = await client.get("/api/events?page=1&page_size=10")
        >>> data = assert_pagination_response(response)
        >>> assert data["total"] >= 0
        >>> assert len(data["items"]) <= data["page_size"]
    """
    assert_status_ok(response)
    data = response.json()

    required_keys = [items_key, total_key, page_key, page_size_key]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise AssertionError(
            f"Pagination response missing keys: {missing}. Got: {list(data.keys())}"
        )

    if not isinstance(data[items_key], list):
        raise AssertionError(
            f"'{items_key}' should be a list, got {type(data[items_key]).__name__}"
        )

    if not isinstance(data[total_key], int) or data[total_key] < 0:
        raise AssertionError(
            f"'{total_key}' should be a non-negative integer, got {data[total_key]}"
        )

    return data


def assert_json_equals(response: Response, expected: dict[str, Any]) -> None:
    """Assert that response JSON exactly equals expected dict.

    Args:
        response: HTTP response object with .json() method
        expected: Expected JSON data

    Raises:
        AssertionError: If response JSON doesn't match expected

    Example:
        >>> response = await client.get("/api/health")
        >>> assert_json_equals(response, {"status": "healthy"})
    """
    actual = response.json()
    if actual != expected:
        raise AssertionError(
            f"Response JSON does not match expected.\nExpected: {expected}\nActual: {actual}"
        )


def assert_datetime_field(
    response: Response,
    field: str,
    allow_none: bool = False,
) -> None:
    """Assert that a response field contains a valid ISO 8601 datetime string.

    Args:
        response: HTTP response object with .json() method
        field: Name of the field to check
        allow_none: Whether None is an acceptable value (default False)

    Raises:
        AssertionError: If field is not a valid datetime

    Example:
        >>> response = await client.get("/api/cameras/front_door")
        >>> assert_datetime_field(response, "last_seen", allow_none=True)
        >>> assert_datetime_field(response, "created_at")
    """
    from datetime import datetime

    data = response.json()
    if field not in data:
        raise AssertionError(f"Response missing field '{field}'")

    value = data[field]
    if value is None:
        if not allow_none:
            raise AssertionError(f"Field '{field}' is None but allow_none=False")
        return

    if not isinstance(value, str):
        raise AssertionError(
            f"Field '{field}' should be a string datetime, got {type(value).__name__}"
        )

    try:
        # Try parsing as ISO 8601
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise AssertionError(
            f"Field '{field}' is not a valid ISO 8601 datetime: '{value}'. Parse error: {e}"
        ) from e


def assert_uuid_field(response: Response, field: str, allow_none: bool = False) -> None:
    """Assert that a response field contains a valid UUID string.

    Args:
        response: HTTP response object with .json() method
        field: Name of the field to check
        allow_none: Whether None is an acceptable value (default False)

    Raises:
        AssertionError: If field is not a valid UUID

    Example:
        >>> response = await client.get("/api/events/123")
        >>> assert_uuid_field(response, "batch_id")
    """
    import uuid

    data = response.json()
    if field not in data:
        raise AssertionError(f"Response missing field '{field}'")

    value = data[field]
    if value is None:
        if not allow_none:
            raise AssertionError(f"Field '{field}' is None but allow_none=False")
        return

    if not isinstance(value, str):
        raise AssertionError(f"Field '{field}' should be a string UUID, got {type(value).__name__}")

    try:
        uuid.UUID(value)
    except ValueError as e:
        raise AssertionError(
            f"Field '{field}' is not a valid UUID: '{value}'. Parse error: {e}"
        ) from e


def assert_in_range(
    value: int | float,
    min_value: int | float,
    max_value: int | float,
    name: str = "value",
) -> None:
    """Assert that a numeric value is within an expected range.

    Args:
        value: The value to check
        min_value: Minimum acceptable value (inclusive)
        max_value: Maximum acceptable value (inclusive)
        name: Name of the value for error messages

    Raises:
        AssertionError: If value is outside the range

    Example:
        >>> response = await client.get("/api/events/123")
        >>> data = response.json()
        >>> assert_in_range(data["risk_score"], 0, 100, "risk_score")
    """
    if not min_value <= value <= max_value:
        raise AssertionError(
            f"Expected {name} to be in range [{min_value}, {max_value}], got {value}"
        )
