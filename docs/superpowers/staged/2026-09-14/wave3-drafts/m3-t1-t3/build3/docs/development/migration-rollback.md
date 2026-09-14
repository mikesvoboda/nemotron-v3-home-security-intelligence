# Migration Rollback Procedures

This document describes how to safely handle database migration failures and rollback procedures.

**Related Linear issue:** NEM-2610

## Overview

Database migrations can fail for various reasons:

- Data integrity violations (duplicate keys, FK constraints)
- Schema conflicts (table/column already exists)
- Resource issues (connection timeouts, disk space)
- Logic errors in migration scripts

Our migration system includes automatic transaction rollback, but some scenarios require manual intervention.

## Automatic Rollback

All migrations run within a transaction. If any step fails:

1. **PostgreSQL automatically rolls back** all changes made during the migration
2. **The database state remains unchanged** from before the migration attempt
3. **Error details are logged** with specific guidance for resolution

Example error output:

```
ERROR - Migration failed due to integrity constraint: duplicate key value violates unique constraint
ROLLBACK: Transaction has been rolled back. Check for duplicate keys, foreign key violations, or constraint conflicts.
```

## Manual Rollback Commands

### Rolling Back to Previous Migration

```bash
# Rollback one migration step
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback to base (removes all tables)
alembic downgrade base
```

### Finding Current Revision

```bash
# Show current revision
alembic current

# Show migration history
alembic history --verbose
```

## Using Migration Helpers

The `backend/alembic/helpers.py` module provides safe operations with pre-flight checks.

### Safe Table Rename

```python
from backend.alembic.helpers import MigrationContext

def upgrade() -> None:
    with MigrationContext("rename_users_table") as ctx:
        # Pre-flight checks are automatic
        ctx.safe_table_rename("users", "accounts")
        # Verification is automatic
```

### Safe Column Operations

```python
from backend.alembic.helpers import MigrationContext

def upgrade() -> None:
    with MigrationContext("add_email_column") as ctx:
        # Won't fail if column already exists
        ctx.safe_column_add(
            "users",
            "email",
            "VARCHAR(255)",
            nullable=True
        )
        ctx.verify_column_exists("users", "email")
```

### Using Savepoints for Partial Rollback

```python
from backend.alembic.helpers import (
    MigrationContext,
    ensure_transaction_savepoint,
    rollback_to_savepoint,
    release_savepoint,
)

def upgrade() -> None:
    with MigrationContext("multi_step_migration") as ctx:
        conn = ctx._ensure_connection()

        # Step 1 - safe
        ctx.safe_column_add("users", "col1", "INTEGER")
        ensure_transaction_savepoint(conn, "after_step1")

        try:
            # Step 2 - might fail
            ctx.execute("ALTER TABLE users ADD CONSTRAINT ...")
            release_savepoint(conn, "after_step1")
        except Exception:
            # Rollback only step 2, keep step 1
            rollback_to_savepoint(conn, "after_step1")
            raise
```

## Common Failure Scenarios

### 1. Duplicate Key Violation

**Symptom:**

```
IntegrityError: duplicate key value violates unique constraint "idx_users_email"
```

**Resolution:**

1. Identify duplicate data: `SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1`
2. Clean up duplicates (keep oldest/newest based on business rules)
3. Retry migration

### 2. Foreign Key Violation

**Symptom:**

```
IntegrityError: update or delete on table "cameras" violates foreign key constraint
```

**Resolution:**

1. Identify orphaned records
2. Either delete orphans or update FKs
3. Retry migration

### 3. Table/Column Already Exists

**Symptom:**

```
ProgrammingError: relation "users" already exists
```

**Resolution:**

1. Check if previous migration was partially applied
2. Use `alembic stamp <revision>` to mark as applied without running
3. Or manually drop the object and retry

### 4. Connection Timeout During Migration

**Symptom:**

```
OperationalError: SSL connection has been closed unexpectedly
```

**Resolution:**

1. Check database connectivity
2. Consider running during maintenance window
3. For large data migrations, break into smaller batches

## Pre-Migration Checklist

Before running migrations, especially on production:

1. **Backup the database**

   ```bash
   pg_dump -h host -U user -d security > backup_$(date +%Y%m%d).sql
   ```

2. **Review the migration**

   ```bash
   # Generate SQL without executing
   alembic upgrade head --sql
   ```

3. **Check for large tables**

   - Migrations on tables with millions of rows may take minutes
   - Consider running during off-peak hours

4. **Test on staging first**
   - Run the exact migration on a staging database
   - Verify application functionality after migration

## Recovery Procedures

### If Migration Fails Mid-Way

1. **Check current state:**

   ```bash
   alembic current
   ```

2. **Review logs** for specific error details

3. **If database is inconsistent:**

   ```bash
   # Rollback to last known good state
   alembic downgrade <last_good_revision>
   ```

4. **Fix the issue** in the migration script

5. **Retry:**
   ```bash
   alembic upgrade head
   ```

### If You Need to Skip a Migration

**Only use this if you've manually applied the migration or it's not needed:**

```bash
# Mark migration as complete without running it
alembic stamp <revision_id>
```

### Emergency: Restoring from Backup

If migrations cannot be rolled back cleanly:

```bash
# Drop and recreate database
dropdb security
createdb security

# Restore from backup
psql -h host -U user -d security < backup_20260113.sql

# Re-run migrations if needed
alembic upgrade head
```

## Writing Safe Migrations

### DO

- Use `MigrationContext` for automatic logging and verification
- Add pre-flight checks before destructive operations
- Include both `upgrade()` and `downgrade()` functions
- Test migrations on a copy of production data
- Use `IF EXISTS` / `IF NOT EXISTS` where appropriate

### DON'T

- Never modify data and schema in the same migration without savepoints
- Don't run migrations during peak traffic
- Don't skip testing on staging
- Don't remove columns that may still be accessed by running code

## Monitoring Migrations

### Log Levels

Configure in `alembic.ini`:

```ini
[logger_alembic]
level = INFO
handlers = console
qualname = alembic
```

For debugging:

```ini
level = DEBUG
```

### Migration State Logging

The env.py automatically logs:

- Current revision before/after migration
- Table count before/after migration
- Detailed error information on failure

## See Also

- [Testing Guide](testing.md) - Running migration tests
- [Code Quality](code-quality.md) - Pre-commit hooks for migrations
- [Git Workflow](git-workflow.md) - Committing migration files
