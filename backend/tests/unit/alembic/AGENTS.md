# Unit Tests - Alembic Migrations

## Purpose

The `backend/tests/unit/alembic/` directory contains unit tests for Alembic migration helper functions and utilities.

## Directory Structure

```
backend/tests/unit/alembic/
├── AGENTS.md            # This file
├── __init__.py          # Package initialization
└── test_helpers.py      # Migration helper function tests (34KB)
```

## Test Files (1 total)

### `test_helpers.py`

Tests for Alembic migration helper functions:

| Test Class                | Coverage                        |
| ------------------------- | ------------------------------- |
| `TestIndexHelpers`        | Index creation/drop utilities   |
| `TestColumnHelpers`       | Column modification utilities   |
| `TestConstraintHelpers`   | Constraint management utilities |
| `TestMigrationValidation` | Migration script validation     |

**Key Tests:**

- Index creation with proper naming conventions
- Column type changes with data preservation
- Foreign key constraint management
- Migration rollback safety verification
- Schema introspection utilities

## Running Tests

```bash
# All Alembic unit tests
uv run pytest backend/tests/unit/alembic/ -v

# With coverage
uv run pytest backend/tests/unit/alembic/ -v --cov=backend.core.database
```

## Test Patterns

### Index Helper Testing

```python
def test_create_index_generates_correct_sql():
    sql = create_index_sql(
        table="events",
        columns=["camera_id", "created_at"],
        name="ix_events_camera_created"
    )
    assert "CREATE INDEX" in sql
    assert "ix_events_camera_created" in sql
    assert "camera_id, created_at" in sql
```

### Migration Validation

```python
def test_migration_has_downgrade():
    """Verify all migrations have downgrade functions."""
    migration_dir = Path("backend/alembic/versions")
    for migration_file in migration_dir.glob("*.py"):
        content = migration_file.read_text()
        assert "def downgrade()" in content
```

## Related Documentation

- `/backend/alembic/AGENTS.md` - Alembic migration documentation
- `/backend/core/database.py` - Database configuration
- `/backend/tests/integration/test_alembic_migrations.py` - Integration tests
