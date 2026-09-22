# Migrations

> How the database schema is actually created and changed in this project.

## Overview

**This project does not use Alembic migrations.** The schema is created
directly from the SQLAlchemy models:

- **At runtime**: `backend/core/database.py` (`init_db`, ~`:390-415`) runs
  `ModelsBase.metadata.create_all` inside an advisory-lock-protected
  `engine.begin()` block, so concurrent pytest-xdist workers / app
  processes don't race on schema creation.
- **From the CLI**: `python -m backend.scripts.init_schema`
  (`backend/scripts/init_schema.py`) drops all tables and recreates them
  from the models. NEM-4482 safeguards make it refuse to run against a
  production-looking `DATABASE_URL`/`ENVIRONMENT` unless `--force` is
  passed.

The Alembic tree lived at `backend/alembic/` until PR #4465
(`refactor(db): flatten database schema by removing alembic migrations`)
removed it. The alembic package is still installed as a **dev
dependency** only ("Database migrations testing", `pyproject.toml:118`),
and `backend/tests/integration/test_alembic_migrations.py` is a skipped
placeholder suite for a future Alembic adoption.

## Changing the Schema

The workflow is model-first:

1. Edit the SQLAlchemy model in `backend/models/`.
2. Development databases pick the change up via `create_all` on next
   startup — but `create_all` only adds **new** tables/columns-safe
   operations; it never alters existing columns, types, or indexes.
3. For destructive changes (column rename, type change, constraint),
   apply them by hand against the dev DB
   (`psql`/`podman exec postgres psql …`), or recreate the database with
   `python -m backend.scripts.init_schema`.
4. Partitioned tables (`events`, `detections`, `logs`, `gpu_stats`)
   additionally need their partition maintenance — see
   `backend/scripts/` partition jobs — because `create_all` creates the
   parent, not future monthly partitions.

## Recreating the Schema (Development)

```bash
# Recreate all tables from models (destructive — prompts, refuses on prod URLs)
uv run python -m backend.scripts.init_schema

# Skip the confirmation prompt (still refuses production-looking URLs)
uv run python -m backend.scripts.init_schema --force
```

Integration tests do not use this script — each pytest-xdist worker
creates its own `security_test_gwN` database and lets
`init_db`'s `create_all` build the schema (see
[Testing: Integration](../testing/integration-testing.md)).

## Reference: Historical Alembic Patterns

<details>
<summary>Pre-#4465 workflow (historical — no tooling exists to run this)</summary>

Before the flattening, the repo carried `backend/alembic/env.py` plus
`versions/` migrations (`968b0dff6a9b_initial_schema.py`,
`add_zones_table.py`, `fix_datetime_timezone.py`, …) and the workflow was:

```bash
uv run alembic upgrade head          # apply all migrations
uv run alembic downgrade -1          # roll back one revision
uv run alembic current               # show applied revision
uv run alembic revision --autogenerate -m "add_new_feature"
```

Migration modules followed the usual `upgrade()`/`downgrade()` patterns
(creating tables with indexes, enum types, GIN indexes for JSONB, BRIN
indexes on time columns, partial indexes, table/constraint renames,
columns with defaults, junction tables, SAVEPOINT-guarded queries).

</details>

## Related Documentation

- [Data Model Overview](./README.md)
- [Core Entities](./core-entities.md)
- [Indexes and Performance](./indexes-and-performance.md)
- [Integration Testing](../testing/integration-testing.md) - Per-worker schema creation
