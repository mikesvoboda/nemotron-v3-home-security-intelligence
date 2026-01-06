# Unit Tests - API Layer

## Purpose

The `backend/tests/unit/api/` directory contains unit tests for the API layer, including route handlers and Pydantic schema validation tests.

## Directory Structure

```
backend/tests/unit/api/
├── AGENTS.md                      # This file
├── __init__.py                    # Package initialization
├── test_date_filter_validation.py # Date filter validation tests
├── routes/                        # Route handler tests (17 files)
└── schemas/                       # Pydantic schema tests (5 files)
```

## Test Files

### Root Level (1 file)

| File                             | Tests For                              |
| -------------------------------- | -------------------------------------- |
| `test_date_filter_validation.py` | Date filter query parameter validation |

### Subdirectories

- **`routes/`**: API endpoint handler tests (17 files)
- **`schemas/`**: Pydantic schema validation tests (5 files)

## Running Tests

```bash
# All API unit tests
uv run pytest backend/tests/unit/api/ -v

# Route tests only
uv run pytest backend/tests/unit/api/routes/ -v

# Schema tests only
uv run pytest backend/tests/unit/api/schemas/ -v

# With coverage
uv run pytest backend/tests/unit/api/ -v --cov=backend/api
```

## Test Patterns

### Route Testing Pattern

```python
@pytest.mark.asyncio
async def test_endpoint(client, mock_session):
    with patch("backend.api.routes.module.get_db", return_value=mock_session):
        response = await client.get("/api/endpoint")
        assert response.status_code == 200
```

### Schema Validation Pattern

```python
def test_schema_validation():
    # Valid data
    schema = MySchema(field="value")
    assert schema.field == "value"

    # Invalid data raises ValidationError
    with pytest.raises(ValidationError):
        MySchema(field=None)
```

## Related Documentation

- `/backend/tests/unit/api/routes/AGENTS.md` - Route test details
- `/backend/tests/unit/api/schemas/AGENTS.md` - Schema test details
- `/backend/api/AGENTS.md` - API layer documentation
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
