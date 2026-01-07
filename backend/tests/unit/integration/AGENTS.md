# Integration Test Helpers Unit Tests

## Purpose

Unit tests for integration test helper functions that are used across integration tests for error handling and response validation.

## Directory Structure

```
backend/tests/unit/integration/
├── AGENTS.md              # This file
└── test_helpers_unit.py   # Integration test helper function tests (4.9KB)
```

## Running Tests

```bash
# All integration helper tests
pytest backend/tests/unit/integration/ -v

# Specific test file
pytest backend/tests/unit/integration/test_helpers_unit.py -v

# With coverage
pytest backend/tests/unit/integration/ -v --cov=backend.tests.integration --cov-report=html
```

## Test Files (1 total)

### `test_helpers_unit.py`

Tests for integration test helper functions:

**Test Classes:**

| Test Class            | Coverage                                |
| --------------------- | --------------------------------------- |
| `TestGetErrorMessage` | Error message extraction from responses |
| `TestHasError`        | Error presence detection in responses   |

**Key Test Coverage:**

- Old error format (string detail field)
- New error format (structured error object)
- Simple error messages
- Validation error messages (single and multiple)
- Error code extraction
- Field-level error messages
- Edge cases (missing fields, empty errors)

**Helper Functions Tested:**

```python
def get_error_message(data: dict) -> str:
    """Extract error message from API response.

    Handles both old format:
        {"detail": "Camera not found"}

    And new format:
        {"error": {"code": "NOT_FOUND", "message": "Camera not found"}}
    """

def has_error(data: dict, code: str = None) -> bool:
    """Check if response contains an error, optionally matching a code."""
```

**Test Patterns:**

```python
def test_old_format_detail_string(self):
    """Test extracting message from old format with string detail."""
    data = {"detail": "Camera not found"}
    assert get_error_message(data) == "Camera not found"

def test_new_format_simple_error(self):
    """Test extracting message from new format with simple error."""
    data = {"error": {"code": "NOT_FOUND", "message": "Camera not found"}}
    assert get_error_message(data) == "Camera not found"

def test_new_format_validation_error_single(self):
    """Test extracting message from new format with single validation error."""
    data = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "errors": [
                {
                    "field": "query.limit",
                    "message": "Input should be less than or equal to 100",
                    "value": "500",
                }
            ],
        }
    }
    expected = "query.limit: Input should be less than or equal to 100"
    assert get_error_message(data) == expected
```

## Usage Context

These helper functions are used throughout integration tests to:

- Validate error responses in a consistent way
- Extract meaningful error messages for assertions
- Handle both old and new error response formats
- Support API contract evolution without breaking tests

## Related Documentation

- `/backend/tests/integration/test_helpers.py` - Helper function implementations
- `/backend/tests/integration/AGENTS.md` - Integration tests overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
