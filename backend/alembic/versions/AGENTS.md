# Alembic Migration Versions - Agent Guide

## Purpose

This directory contains 52 PostgreSQL database migration scripts managed by Alembic. Each migration file represents a schema change that can be applied (upgrade) or reversed (downgrade).

## Migration Categories

The migrations are organized into several categories:

### Foundation Migrations

Establish core schema and tables.

### Database Optimization Migrations

Add indexes, partitioning, and performance improvements.

### Feature Addition Migrations

Add new tables and columns for new functionality.

### Fix and Maintenance Migrations

Fix issues and maintain data integrity.

### Merge Migrations

Consolidate parallel migration branches (7 merge points).

## Migration Files

### `968b0dff6a9b_initial_schema.py`

**Revision ID:** `968b0dff6a9b`
**Parent:** None (first migration)

Creates the foundational tables:

| Table        | Purpose                            |
| ------------ | ---------------------------------- |
| `api_keys`   | API key storage with SHA256 hashes |
| `cameras`    | Camera definitions and status      |
| `gpu_stats`  | GPU metrics history                |
| `logs`       | Application log storage            |
| `detections` | Individual object detections       |
| `events`     | Aggregated security events         |

Key indexes: `idx_detections_camera_time`, `idx_events_started_at`, `idx_logs_timestamp`

### `20251228_add_fts_search_vector.py`

**Revision ID:** `20251228_fts`
**Parent:** `968b0dff6a9b`

Adds full-text search to events:

- `object_types` column (cached detection classes)
- `search_vector` TSVECTOR column
- `events_search_vector_update()` trigger function
- GIN index on `search_vector` for fast searches
- Backfills existing events with search vectors

### `add_alerts_and_alert_rules.py`

**Revision ID:** `add_alerts_rules`
**Parent:** `20251228_fts`

Creates the alerting system:

| Table         | Purpose                                |
| ------------- | -------------------------------------- |
| `alert_rules` | Alert rule definitions with conditions |
| `alerts`      | Triggered alerts with delivery status  |

PostgreSQL ENUM types created:

- `alert_severity`: low, medium, high, critical
- `alert_status`: pending, delivered, acknowledged, dismissed

### `add_zones_table.py`

**Revision ID:** `add_zones_001`
**Parent:** `add_alerts_rules`

Adds camera zone definitions:

| Table   | Purpose                       |
| ------- | ----------------------------- |
| `zones` | Geographic regions per camera |

PostgreSQL ENUM types created:

- `zone_type_enum`: entry_point, driveway, sidewalk, yard, other
- `zone_shape_enum`: rectangle, polygon

Columns: `id`, `camera_id`, `name`, `zone_type`, `coordinates` (JSONB), `shape`, `color`, `enabled`, `priority`, timestamps

### `audit_logs_table.py`

**Revision ID:** `add_audit_logs`
**Parent:** `add_zones_001`

Creates audit logging for security:

| Table        | Purpose                            |
| ------------ | ---------------------------------- |
| `audit_logs` | Security-sensitive action tracking |

Columns: `timestamp`, `action`, `resource_type`, `resource_id`, `actor`, `ip_address`, `user_agent`, `details` (JSON), `status`

### `add_baseline_tables.py`

**Revision ID:** `add_baselines`
**Parent:** `add_audit_logs`

Creates baseline tables for anomaly detection:

| Table                | Purpose                              |
| -------------------- | ------------------------------------ |
| `activity_baselines` | Per-camera activity rate by hour/day |
| `class_baselines`    | Detection class frequency by hour    |

These tables support anomaly detection by comparing current detections against historical patterns with exponential decay.

### `add_clip_path_column.py`

**Revision ID:** `add_clip_path`
**Parent:** `add_baselines`

Adds clip_path column to events table:

- `clip_path` column (VARCHAR) for storing video clip file paths

### `fix_datetime_timezone.py`

**Revision ID:** `fix_datetime_tz`
**Parent:** `add_clip_path`

Fixes datetime timezone awareness:

- Updates datetime columns to use timezone-aware timestamps
- Ensures consistent UTC handling across all timestamp fields

### `fix_search_vector_backfill.py`

**Revision ID:** `fix_search_vector_backfill`
**Parent:** `fix_datetime_tz`

Backfills NULL search_vector values for existing events that were created before the FTS trigger was added.

### `add_llm_prompt_column.py`

**Revision ID:** `add_llm_prompt`
**Parent:** `fix_search_vector_backfill`

Adds `llm_prompt` column to events table for storing the full prompt sent to Nemotron LLM.

### `add_event_audits_table.py`

**Revision ID:** `add_event_audits`
**Parent:** `add_llm_prompt`

Creates `event_audits` table for AI pipeline performance tracking and self-evaluation.

### `add_camera_unique_constraints.py`

**Revision ID:** `add_camera_unique_constraints`
**Parent:** `add_event_audits`

Adds unique constraints on cameras.name and cameras.folder_path columns after cleaning up duplicates.

### `add_enrichment_data_column.py`

**Revision ID:** `add_enrichment_data`
**Parent:** `add_camera_unique_constraints`

Adds `enrichment_data` JSONB column to detections table for storing vision model results.

### `add_object_types_gin_trgm_index.py`

**Revision ID:** `add_object_types_gin_trgm`
**Parent:** `add_enrichment_data`

Adds GIN trigram index on events.object_types for efficient LIKE/ILIKE queries:

- Enables pg_trgm extension
- Creates `idx_events_object_types_trgm` using gin_trgm_ops operator class
- Optimizes queries like `object_types LIKE '%person%'` that previously caused full table scans

### `add_prompt_versions_table.py`

**Revision ID:** `add_prompt_versions`
**Parent:** `add_event_audits`

Creates `prompt_versions` table for AI model prompt configuration tracking:

- PostgreSQL ENUM type `aimodel`: nemotron, florence2, yolo_world, xclip, fashion_clip
- Columns: `id`, `model`, `version`, `created_at`, `created_by`, `config` (JSONB), `is_active`, `performance_score`
- Supports version history and A/B testing of prompts

### `d4cdaa821492_merge_heads.py`

**Revision ID:** `d4cdaa821492`
**Parents:** `add_object_types_gin_trgm`, `add_prompt_versions`

Merge migration that combines two parallel branches.

## Additional Migration Files (Post-Merge)

### Database Optimization Migrations

| File                                              | Purpose                                 |
| ------------------------------------------------- | --------------------------------------- |
| `add_composite_indexes_for_filters.py`            | Multi-column indexes for filter queries |
| `add_covering_indexes_for_pagination.py`          | Include columns for index-only scans    |
| `add_deleted_at_indexes.py`                       | Soft delete query optimization          |
| `add_partial_indexes_boolean_columns.py`          | Partial indexes for boolean filters     |
| `add_gin_brin_specialized_indexes.py`             | GIN and BRIN specialized indexes        |
| `add_gpu_stats_recorded_at_brin_index.py`         | BRIN index for time-series data         |
| `add_time_series_partitioning.py`                 | Table partitioning for large tables     |
| `1c42824dcb07_add_search_indexes.py`              | Additional search optimization          |
| `add_alerts_deduplication_indexes.py`             | Alert dedup performance                 |
| `add_events_backlog_improvement_indexes.py`       | Event backlog query optimization        |
| `add_detections_camera_object_index.py`           | Detection lookup optimization           |
| `add_detections_object_type_detected_at_index.py` | Detection type queries                  |
| `add_detection_search_vector.py`                  | Full-text search on detections          |

### Feature Addition Migrations

| File                                     | Purpose                            |
| ---------------------------------------- | ---------------------------------- |
| `add_prompt_configs_table.py`            | Prompt configuration storage       |
| `add_notification_preferences_tables.py` | User notification settings         |
| `add_user_feedback_and_calibration.py`   | User feedback and calibration      |
| `add_entity_model.py`                    | Entity tracking (people, vehicles) |
| `add_trust_status_to_entities.py`        | Entity trust classification        |
| `add_job_transitions_table.py`           | Background job state tracking      |
| `add_event_detections_junction_table.py` | M2M events/detections              |
| `add_4_feedback_types.py`                | Extended feedback categorization   |
| `create_scene_changes_table.py`          | Scene change detection             |

### Fixes and Maintenance Migrations

| File                                      | Purpose                    |
| ----------------------------------------- | -------------------------- |
| `fix_camera_timezone_idempotent.py`       | Timezone handling          |
| `add_check_constraints.py`                | Data integrity constraints |
| `add_deleted_at_soft_delete.py`           | Soft delete support        |
| `drop_detection_ids_column.py`            | Schema cleanup             |
| `add_snooze_until_column.py`              | Alert snoozing             |
| `add_alert_version_id_column.py`          | Alert versioning           |
| `add_row_version_to_prompt_versions.py`   | Optimistic locking         |
| `add_prompt_version_unique_constraint.py` | Uniqueness enforcement     |

### Merge Migrations

| File                                                    | Purpose              |
| ------------------------------------------------------- | -------------------- |
| `d896ab921049_merge_user_feedback_and_notification_.py` | Feature merge        |
| `eb2e0919ec02_merge_heads_add_notification_.py`         | Notification merge   |
| `b80664ed1373_merge_migration_branches.py`              | Branch consolidation |
| `00c8a000b44f_merge_database_optimization_heads.py`     | Optimization merge   |
| `071128727b6c_merge_deleted_at_indexes.py`              | Index merge          |
| `6b206d6591cb_merge_add_4_feedback_types_and_job_.py`   | Feedback/job merge   |

## Creating New Migrations

### 1. Autogenerate from model changes

```bash
cd backend
alembic revision --autogenerate -m "description of change"
```

**Always review autogenerated migrations** - Alembic may not detect:

- Enum value changes
- Index/constraint renames
- Data migrations
- PostgreSQL-specific features (JSONB, TSVECTOR, triggers)

### 2. Empty migration for manual changes

```bash
cd backend
alembic revision -m "description of change"
```

Use for:

- Custom SQL (triggers, functions)
- Data migrations
- PostgreSQL extensions

### 3. Migration structure

```python
"""Description of migration

Revision ID: unique_id
Revises: parent_id
Create Date: timestamp
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "unique_id"
down_revision: str | Sequence[str] | None = "parent_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply schema changes."""
    pass


def downgrade() -> None:
    """Reverse schema changes."""
    pass
```

## Migration Patterns

### Creating ENUM types

```python
def upgrade():
    op.execute("CREATE TYPE status_enum AS ENUM ('active', 'inactive')")
    # Then use in column definition

def downgrade():
    op.drop_table("table_using_enum")
    op.execute("DROP TYPE IF EXISTS status_enum")
```

### Adding PostgreSQL triggers

```python
def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION my_trigger_func() RETURNS trigger AS $$
        BEGIN
            -- trigger logic
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER my_trigger
        BEFORE INSERT OR UPDATE ON my_table
        FOR EACH ROW EXECUTE FUNCTION my_trigger_func();
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS my_trigger ON my_table")
    op.execute("DROP FUNCTION IF EXISTS my_trigger_func()")
```

### Adding GIN indexes for JSONB/TSVECTOR

```python
op.create_index(
    "idx_name",
    "table",
    ["column"],
    unique=False,
    postgresql_using="gin",
)
```

## Common Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 968b0dff6a9b

# Show current revision
alembic current

# Show migration history
alembic history --verbose

# Generate SQL without applying
alembic upgrade head --sql > migration.sql
```

## Best Practices

1. **Test both directions** - Always verify `upgrade()` and `downgrade()` work
2. **One change per migration** - Keep migrations focused and atomic
3. **Never modify applied migrations** - Create new migrations for fixes
4. **Include data migrations** - Backfill data when adding non-nullable columns
5. **Drop indexes before columns** - Required for proper downgrade order
6. **Drop constraints before tables** - Foreign keys must be dropped first
