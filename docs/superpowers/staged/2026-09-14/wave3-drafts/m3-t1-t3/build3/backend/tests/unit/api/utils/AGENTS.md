# Unit Tests - API Utils

## Purpose

The `backend/tests/unit/api/utils/` directory contains unit tests for API utility functions used across route handlers.

## Directory Structure

```
backend/tests/unit/api/utils/
├── AGENTS.md             # This file
├── __init__.py           # Package initialization
└── test_field_filter.py  # Field filtering utility tests
```

## Test Files (1 total)

### `test_field_filter.py`

Tests for field filtering utilities used in API responses:

| Test Class              | Coverage                           |
| ----------------------- | ---------------------------------- |
| `TestFieldFilter`       | Response field selection/exclusion |
| `TestNestedFieldFilter` | Nested object field filtering      |
| `TestFieldValidation`   | Invalid field name handling        |

**Key Tests:**

- Select specific fields from response
- Exclude sensitive fields from response
- Nested object field filtering
- Invalid field name rejection
- Empty field list handling

## Running Tests

```bash
# All API utils unit tests
uv run pytest backend/tests/unit/api/utils/ -v

# With coverage
uv run pytest backend/tests/unit/api/utils/ -v --cov=backend.api.utils
```

## Test Patterns

### Field Selection

```python
def test_select_fields_filters_response():
    data = {"id": "123", "name": "Test", "secret": "hidden"}  # pragma: allowlist secret
    filtered = filter_fields(data, include=["id", "name"])
    assert filtered == {"id": "123", "name": "Test"}
    assert "secret" not in filtered
```

### Field Exclusion

```python
def test_exclude_fields_removes_sensitive():
    data = {"id": "123", "password": "secret", "api_key": "key123"}  # pragma: allowlist secret
    filtered = filter_fields(data, exclude=["password", "api_key"])
    assert "password" not in filtered
    assert "api_key" not in filtered
```

## Related Documentation

- `/backend/api/utils/AGENTS.md` - API utility implementations
- `/backend/tests/unit/api/AGENTS.md` - API layer unit tests overview
