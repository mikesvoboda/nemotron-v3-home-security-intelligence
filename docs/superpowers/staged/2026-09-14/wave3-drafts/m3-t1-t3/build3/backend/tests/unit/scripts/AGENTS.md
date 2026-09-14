# Unit Tests - Scripts

## Purpose

The `backend/tests/unit/scripts/` directory contains unit tests for migration and utility scripts.

## Directory Structure

```
backend/tests/unit/scripts/
├── AGENTS.md                       # This file
├── test_generate_openapi.py        # OpenAPI schema generation tests (25KB)
└── test_migrate_beads_to_linear.py # Beads to Linear migration tests (11KB)
```

## Test Files (2 files)

| File                              | Tests For                                     |
| --------------------------------- | --------------------------------------------- |
| `test_generate_openapi.py`        | OpenAPI schema generation and validation      |
| `test_migrate_beads_to_linear.py` | Migration from Beads to Linear issue tracking |

## Running Tests

```bash
# Run script tests
uv run pytest backend/tests/unit/scripts/ -v

# With coverage
uv run pytest backend/tests/unit/scripts/ -v --cov=scripts
```

## Test Coverage

### `test_generate_openapi.py`

Tests for OpenAPI schema generation:

- Schema generation from FastAPI app
- Schema validation against OpenAPI spec
- Endpoint documentation completeness
- Response model serialization
- Parameter validation in generated schema

### `test_migrate_beads_to_linear.py`

Tests for the Beads to Linear migration script:

- Issue data transformation
- Field mapping validation
- Error handling for malformed data
- API interaction mocking
- Batch processing logic

## Related Documentation

- `/scripts/AGENTS.md` - Scripts documentation
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
