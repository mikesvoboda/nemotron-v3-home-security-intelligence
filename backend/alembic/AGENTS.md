# Alembic Database Migrations Guide

## Purpose

The `backend/alembic/` directory contains Alembic database migration infrastructure for managing schema changes in the PostgreSQL database. Alembic is SQLAlchemy's database migration tool.

## Directory Structure

```
backend/alembic/
├── AGENTS.md            # This file
├── env.py               # Migration environment configuration
├── helpers.py           # Migration helper utilities
├── README               # Alembic-generated readme
├── script.py.mako       # Template for new migrations
└── versions/            # 52 migration scripts (see versions/AGENTS.md)
```

## Current Migration Chain

The migration chain has grown to 52 migrations with multiple merge points. Key migration categories:

**Foundation (initial_schema through enrichment_data):**

- `968b0dff6a9b` - Initial schema (cameras, detections, events, logs, gpu_stats)
- `20251228_fts` - Full-text search vectors
- Alert rules, zones, audit logs, baselines, clip paths
- Datetime timezone fixes, search vector backfill
- LLM prompt storage, event audits, camera constraints
- Enrichment data column for vision model results

**Database Optimization:**

- `add_object_types_gin_trgm_index` - GIN trigram index for LIKE queries
- `add_composite_indexes_for_filters` - Multi-column indexes
- `add_covering_indexes_for_pagination` - Include columns for index-only scans
- `add_deleted_at_indexes` - Soft delete query optimization
- `add_partial_indexes_boolean_columns` - Partial indexes for boolean filters
- `add_gin_brin_specialized_indexes` - GIN and BRIN specialized indexes
- `add_gpu_stats_recorded_at_brin_index` - BRIN index for time-series data
- `add_time_series_partitioning` - Table partitioning for large tables
- `add_search_indexes` - Additional search optimization
- `add_alerts_deduplication_indexes` - Alert dedup performance
- `add_events_backlog_improvement_indexes` - Event backlog queries
- `add_detections_camera_object_index` - Detection lookup optimization
- `add_detections_object_type_detected_at_index` - Detection type queries
- `add_detection_search_vector` - Full-text search on detections

**Feature Additions:**

- `add_prompt_versions_table` - AI prompt version management
- `add_prompt_configs_table` - Prompt configuration storage
- `add_notification_preferences_tables` - User notification settings
- `add_user_feedback_and_calibration` - User feedback and calibration
- `add_entity_model` - Entity tracking (people, vehicles)
- `add_trust_status_to_entities` - Entity trust classification
- `add_job_transitions_table` - Background job state tracking
- `add_event_detections_junction_table` - M2M events/detections
- `add_4_feedback_types` - Extended feedback categorization
- `create_scene_changes_table` - Scene change detection

**Fixes and Maintenance:**

- `fix_camera_timezone_idempotent` - Timezone handling
- `add_check_constraints` - Data integrity constraints
- `add_deleted_at_soft_delete` - Soft delete support
- `drop_detection_ids_column` - Schema cleanup
- `add_snooze_until_column` - Alert snoozing
- `add_alert_version_id_column` - Alert versioning
- `add_row_version_to_prompt_versions` - Optimistic locking
- `add_prompt_version_unique_constraint` - Uniqueness enforcement

**Merge Migrations:**

- `d4cdaa821492_merge_heads` - Primary merge point
- `d896ab921049_merge_user_feedback_and_notification_` - Feature merge
- `eb2e0919ec02_merge_heads_add_notification_` - Notification merge
- `b80664ed1373_merge_migration_branches` - Branch consolidation
- `00c8a000b44f_merge_database_optimization_heads` - Optimization merge
- `071128727b6c_merge_deleted_at_indexes` - Index merge
- `6b206d6591cb_merge_add_4_feedback_types_and_job_` - Feedback/job merge

See `versions/AGENTS.md` for detailed documentation of individual migrations.

## Key Files

### `env.py` - Migration Environment

Configures Alembic to use the application's SQLAlchemy models and database connection:

**Key Functions:**

- `get_database_url()` - Resolves database URL from:

  1. `DATABASE_URL` environment variable (priority)
  2. `sqlalchemy.url` in alembic.ini
  3. Default fallback: `postgresql://security:password@localhost:5432/security`

- `run_migrations_offline()` - Generate SQL scripts without database connection
- `run_migrations_online()` - Apply migrations with live database connection

**Important Details:**

- Converts async URLs to sync for Alembic compatibility:
  - `postgresql+asyncpg://` -> `postgresql://`
- Only PostgreSQL is supported (no SQLite)
- Uses `NullPool` to avoid connection issues
- Imports `backend.models.camera.Base` for metadata

### `helpers.py` - Migration Helpers

Utility functions for common migration operations:

- Index creation/dropping helpers
- Constraint management utilities
- Data migration helpers
- Idempotent operation wrappers

### `script.py.mako` - Migration Template

Mako template for generating new migration files. Includes:

- Revision ID and down_revision
- Timestamp in docstring
- Empty `upgrade()` and `downgrade()` functions

## Common Commands

**Create a new migration (autogenerate from model changes):**

```bash
cd backend
alembic revision --autogenerate -m "description of change"
```

**Create empty migration for manual changes:**

```bash
cd backend
alembic revision -m "description of change"
```

**Apply all pending migrations:**

```bash
alembic upgrade head
```

**Rollback one migration:**

```bash
alembic downgrade -1
```

**Show current revision:**

```bash
alembic current
```

**Show migration history:**

```bash
alembic history --verbose
```

**Generate SQL without applying:**

```bash
alembic upgrade head --sql > migration.sql
```

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string (overrides alembic.ini)

Example:

```bash
export DATABASE_URL=postgresql://security:password@localhost:5432/security
```

## Best Practices

1. **Always review autogenerated migrations** - Alembic may not capture:
   - Enum value changes
   - Index/constraint renames
   - Data migrations
   - PostgreSQL-specific features (JSONB, TSVECTOR, triggers)
2. **Test migrations both ways** - Verify both `upgrade()` and `downgrade()` work
3. **Use descriptive revision messages** - Makes history easier to understand
4. **Keep migrations small** - One logical change per migration
5. **Never modify applied migrations** - Create new migrations instead

## Integration with Application

The application uses SQLAlchemy 2.0 async patterns with asyncpg, while Alembic uses synchronous connections. The `env.py` handles this by:

1. Converting the async database URL to sync format
2. Using standard psycopg2 driver for migrations
3. Sharing the same model metadata (`Base.metadata`) as the application

## Related Documentation

- `versions/AGENTS.md` - Detailed migration file documentation
- `/backend/core/database.py` - Application database module
- `/backend/models/AGENTS.md` - SQLAlchemy model documentation
- `/backend/AGENTS.md` - Backend overview
