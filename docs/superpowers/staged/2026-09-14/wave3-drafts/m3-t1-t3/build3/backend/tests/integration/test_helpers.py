"""Helper functions for integration tests.

Provides utilities for extracting error messages from API responses
and other common test operations.
"""


def get_error_message(data: dict) -> str:
    """Extract error message from response data, supporting both old and new formats.

    New format (NEM-1499):
        {"error": {"code": "ERROR_CODE", "message": "error message", ...}}

    New format with validation errors:
        {"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "errors": [...]}}

    Old format (legacy):
        {"detail": "error message"}

    Args:
        data: The JSON response data

    Returns:
        The error message string, or concatenated field-level errors for validation errors

    Raises:
        KeyError: If neither format is present
    """
    if "error" in data and isinstance(data["error"], dict):
        error = data["error"]
        # For validation errors, concatenate field-level error messages
        if error.get("code") == "VALIDATION_ERROR" and "errors" in error:
            field_errors = []
            for err in error["errors"]:
                field = err.get("field", "")
                msg = err.get("message", "")
                if field and msg:
                    field_errors.append(f"{field}: {msg}")
                elif msg:
                    field_errors.append(msg)
            if field_errors:
                return " | ".join(field_errors)
        # For other errors, return the top-level message
        return error.get("message", "")
    if "detail" in data:
        return data["detail"]
    raise KeyError("No error message found in response data")


def has_error(data: dict) -> bool:
    """Check if response data contains an error in either format.

    Args:
        data: The JSON response data

    Returns:
        True if the response contains an error
    """
    return ("error" in data and isinstance(data["error"], dict)) or "detail" in data
