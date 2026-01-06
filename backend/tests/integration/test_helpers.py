"""Helper functions for integration tests.

Provides utilities for extracting error messages from API responses
and other common test operations.
"""


def get_error_message(data: dict) -> str:
    """Extract error message from response data, supporting both old and new formats.

    New format (NEM-1499):
        {"error": {"code": "ERROR_CODE", "message": "error message", ...}}

    Old format (legacy):
        {"detail": "error message"}

    Args:
        data: The JSON response data

    Returns:
        The error message string

    Raises:
        KeyError: If neither format is present
    """
    if "error" in data and isinstance(data["error"], dict):
        return data["error"].get("message", "")
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
