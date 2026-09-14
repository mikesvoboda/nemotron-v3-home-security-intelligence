# Unit Tests - API Schemas

## Purpose

The `backend/tests/unit/api/schemas/` directory contains unit tests for Pydantic schema validation. These tests verify request/response data validation, serialization, and field constraints.

## Directory Structure

```
backend/tests/unit/api/schemas/
├── AGENTS.md                         # This file
├── __init__.py                       # Package initialization
├── test_detections.py                # Detection schema validation
├── test_enrichment_data_validation.py# Enrichment data schemas
├── test_llm_response.py              # LLM response schema validation
├── test_performance_schemas.py       # Performance schema models
└── test_system.py                    # System schema validation
```

## Test Files (5 files)

| File                                 | Tests For                           |
| ------------------------------------ | ----------------------------------- |
| `test_detections.py`                 | Detection request/response schemas  |
| `test_enrichment_data_validation.py` | Enrichment data validation schemas  |
| `test_llm_response.py`               | LLM response parsing and validation |
| `test_performance_schemas.py`        | Performance metrics schemas         |
| `test_system.py`                     | System status/health schemas        |

## Running Tests

```bash
# All schema tests
uv run pytest backend/tests/unit/api/schemas/ -v

# Single test file
uv run pytest backend/tests/unit/api/schemas/test_detections.py -v

# With coverage
uv run pytest backend/tests/unit/api/schemas/ -v --cov=backend/api/schemas
```

## Test Categories

### Field Validation Tests

- Required field presence
- Optional field defaults
- Type coercion and validation
- String length constraints
- Numeric range validation
- Enum value validation

### Serialization Tests

- JSON serialization roundtrip
- Date/datetime formatting
- UUID handling
- Nested object serialization

### Edge Case Tests

- Empty values handling
- Null vs missing fields
- Extra fields rejection/ignoring
- Unicode and special characters

## Common Test Patterns

### Valid Schema Test

```python
def test_valid_schema():
    data = {
        "id": "abc123",
        "confidence": 0.95,
        "label": "person"
    }
    schema = DetectionSchema(**data)
    assert schema.id == "abc123"
    assert schema.confidence == 0.95
```

### Invalid Schema Test

```python
def test_invalid_confidence():
    with pytest.raises(ValidationError) as exc_info:
        DetectionSchema(
            id="abc123",
            confidence=1.5,  # Invalid: > 1.0
            label="person"
        )
    assert "confidence" in str(exc_info.value)
```

### Serialization Test

```python
def test_serialization():
    schema = DetectionSchema(
        id="abc123",
        confidence=0.95,
        label="person"
    )
    data = schema.model_dump()
    assert isinstance(data, dict)
    assert data["id"] == "abc123"
```

### JSON Roundtrip Test

```python
def test_json_roundtrip():
    original = DetectionSchema(id="abc123", confidence=0.95, label="person")
    json_str = original.model_dump_json()
    restored = DetectionSchema.model_validate_json(json_str)
    assert original == restored
```

## Related Documentation

- `/backend/api/schemas/AGENTS.md` - Schema implementation docs
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/unit/api/AGENTS.md` - API layer test overview
