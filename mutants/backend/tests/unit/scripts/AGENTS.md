# Unit Tests - Scripts

## Purpose

The `backend/tests/unit/scripts/` directory contains unit tests for migration and utility scripts.

## Directory Structure

```
backend/tests/unit/scripts/
└── test_migrate_beads_to_linear.py  # Beads to Linear migration tests
```

## Test Files (1 file)

| File                              | Tests For                                     |
| --------------------------------- | --------------------------------------------- |
| `test_migrate_beads_to_linear.py` | Migration from Beads to Linear issue tracking |

## Running Tests

```bash
# Run script tests
uv run pytest backend/tests/unit/scripts/ -v

# With coverage
uv run pytest backend/tests/unit/scripts/ -v --cov=scripts
```

## Test Coverage

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
