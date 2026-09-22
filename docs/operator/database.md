# PostgreSQL Database Setup and Management

> Complete guide to setting up, configuring, and maintaining PostgreSQL for Home Security Intelligence.

**Time to read:** ~12 min
**Prerequisites:** Container runtime (Docker/Podman), PostgreSQL basics

---

## Database Overview

Home Security Intelligence uses **PostgreSQL 16+** as its primary data store. PostgreSQL was chosen for full-text search (TSVECTOR), JSONB support, and robust async performance via asyncpg.

> **Note:** SQLite is not supported. PostgreSQL is required for all deployments.

### Schema Summary

| Table Group   | Tables                                                                             | Purpose              |
| ------------- | ---------------------------------------------------------------------------------- | -------------------- |
| Security Data | `cameras`, `events`, `detections`, `camera_zones`, `line_zones`, `polygon_zones`   | Core monitoring data |
| Alerting      | `alerts`, `alert_rules`                                                            | Notification system  |
| System        | `gpu_stats`, `gpu_devices`, `gpu_configurations`, `logs`, `audit_logs`, `api_keys` | Operations and audit |
| Analytics     | `activity_baselines`, `class_baselines`, `heatmap_data`, `dwell_time_records`      | Anomaly detection    |

The full table list is `__tablename__` in `backend/models/*.py`; see
[Data Model](../architecture/data-model/README.md).

### Storage Estimates

| Deployment | Cameras | Monthly Growth |
| ---------- | ------- | -------------- |
| Small      | 1-4     | 500MB-2GB      |
| Medium     | 5-8     | 2GB-5GB        |
| Large      | 8+      | 5GB+           |

GPU stats at 5-second polling adds ~100MB/month.

---

## Initial Setup

### Option 1: Container-Based (Recommended)

```bash
# Start PostgreSQL container
podman compose -f docker-compose.prod.yml up -d postgres

# Verify health
podman compose -f docker-compose.prod.yml ps postgres
```

**Required credentials (must be set in .env):**

> **IMPORTANT:** There is no default password. `POSTGRES_PASSWORD` must be explicitly set or the container will fail to start. See [Security - Database Credentials](admin/security.md#database-credentials-required) for details.

```bash
POSTGRES_USER=security                  # Default username
POSTGRES_PASSWORD=<your-secure-password>  # REQUIRED - generate with: openssl rand -base64 32
POSTGRES_DB=security                    # Default database name
```

### Option 2: Native PostgreSQL

```bash
# Install (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE USER security WITH PASSWORD 'your_secure_password';
CREATE DATABASE security OWNER security;
\q
```

### Schema Creation

There is **no Alembic step** — the Alembic migrations tree was removed (PR #4465). The
schema is created/synced by `init_db()` (`Base.metadata.create_all`) when the backend
starts; the backend entrypoint only waits for the database to be reachable. See
[Migrations](../architecture/data-model/migrations.md).

---

## Configuration

### DATABASE_URL Format

```bash
postgresql+asyncpg://username:password@host:port/database
```

**Examples:**

```bash
# Container deployment
DATABASE_URL=postgresql+asyncpg://security:password@postgres:5432/security

# Native development
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security
```

### Connection Pool Settings

Pool settings come from `backend/core/config.py` and are applied in
`backend/core/database.py`:

| Setting                  | Default | Env var                  | Description                                                                |
| ------------------------ | ------- | ------------------------ | -------------------------------------------------------------------------- |
| `database_pool_size`     | 20      | `DATABASE_POOL_SIZE`     | Base connections                                                           |
| `database_pool_overflow` | 30      | `DATABASE_POOL_OVERFLOW` | Burst capacity (20 + 30 = 50 max connections; earlier defaults were 10/20) |
| `database_pool_timeout`  | 30      | `DATABASE_POOL_TIMEOUT`  | Wait for connection (s)                                                    |
| `database_pool_recycle`  | 1800    | `DATABASE_POOL_RECYCLE`  | Connection lifetime (s)                                                    |

---

## Schema Management (No Alembic)

There are **no Alembic migrations** in this repository — the migrations tree was removed
(PR #4465) and there is no `alembic.ini` or `backend/alembic/`. The schema is created by
`init_db()` via `Base.metadata.create_all` on backend startup: new columns from model
changes are created for fresh databases, but **existing columns are never altered** by
`create_all` — a model change that modifies an existing column needs a manual `ALTER
TABLE` (or a wipe + recreate in dev). The old "Database Migration Timeline" diagram in
`docs/images/architecture/` is a leftover artifact from the Alembic era.

See [Migrations](../architecture/data-model/migrations.md) for the full policy.

---

## Maintenance

### Vacuum and Analyze

```bash
# Via container
podman compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "VACUUM ANALYZE;"
```

```sql
-- High-churn tables specifically
VACUUM ANALYZE detections;
VACUUM ANALYZE events;
VACUUM ANALYZE gpu_stats;
```

### Monitor Database Size

```sql
-- Total size
SELECT pg_size_pretty(pg_database_size('security'));

-- By table
SELECT tablename,
  pg_size_pretty(pg_total_relation_size('public.' || tablename)) as size
FROM pg_tables WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.' || tablename) DESC;
```

### Index Health

```sql
-- Check index usage
SELECT indexname, idx_scan as scans
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC LIMIT 10;
```

---

## Data Retention

### Configuration

| Data Type                     | Default | Variable             |
| ----------------------------- | ------- | -------------------- |
| Events, Detections, GPU Stats | 30 days | `RETENTION_DAYS`     |
| Logs                          | 7 days  | `LOG_RETENTION_DAYS` |

CleanupService runs daily at 03:00.

### Preview Cleanup

The cleanup endpoint is guarded by `verify_api_key` — send `X-API-Key` when
`API_KEY_ENABLED=true`:

```bash
curl -X POST "http://localhost:8000/api/system/cleanup?dry_run=true" \
  -H "X-API-Key: your-api-key"
```

### Manual Cleanup

```sql
-- Delete old events (cascades to detections)
DELETE FROM events WHERE started_at < NOW() - INTERVAL '30 days';

-- Reclaim space
VACUUM ANALYZE;
```

---

## Troubleshooting

### Connection Refused

```bash
# Verify PostgreSQL is running
podman compose -f docker-compose.prod.yml ps postgres

# Test connectivity
pg_isready -h localhost -p 5432 -U security

# Check logs
podman compose -f docker-compose.prod.yml logs postgres
```

**Fix:** Ensure `DATABASE_URL` uses `postgres` for container or `localhost` for native.

### Authentication Failed

```bash
# Test credentials
podman compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "SELECT 1;"

# Reset password
podman compose -f docker-compose.prod.yml exec postgres psql -U postgres -c \
  "ALTER USER security WITH PASSWORD 'new_password';"
```

### Schema Drift After a Model Change

`create_all` does not alter existing columns. If a deploy changes a column's type or adds
a constraint, inspect and fix it manually, then restart the backend:

```bash
podman compose -f docker-compose.prod.yml exec -T postgres \
  psql -U security -d security -c "\d+ events"
```

### Slow Queries

```sql
-- Find slow queries
SELECT pid, now() - query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - query_start) > interval '5 seconds';

-- Analyze a query
EXPLAIN ANALYZE SELECT * FROM events WHERE risk_score > 70;

-- Run maintenance
VACUUM ANALYZE;
```

### Disk Full

```bash
# Check space
podman system df

# Emergency cleanup
DELETE FROM gpu_stats WHERE recorded_at < NOW() - INTERVAL '7 days';
VACUUM FULL;
```

---

## Quick Reference

### Essential Commands

```bash
# Start database
podman compose -f docker-compose.prod.yml up -d postgres

# Connect to database
podman compose -f docker-compose.prod.yml exec postgres psql -U security -d security

# Check health
podman compose -f docker-compose.prod.yml exec postgres pg_isready -U security -d security

# Backup
podman compose -f docker-compose.prod.yml exec postgres pg_dump -U security security > backup.sql

# Restore
podman compose -f docker-compose.prod.yml exec -T postgres psql -U security security < backup.sql
```

### Connection URLs

| Environment | URL                                                              |
| ----------- | ---------------------------------------------------------------- |
| Container   | `postgresql+asyncpg://security:password@postgres:5432/security`  |
| Native      | `postgresql+asyncpg://security:password@localhost:5432/security` |

---

## Next Steps

- [Backup and Recovery](backup.md) - Database backup procedures
- [Data Model](../developer/data-model.md) - Database schema details

---

## See Also

- [Database Troubleshooting](../reference/troubleshooting/database-issues.md) - Solve PostgreSQL problems
- [Environment Variable Reference](../reference/config/env-reference.md) - DATABASE_URL and retention configuration
- [Alerts](../developer/alerts.md) - How alert rules use the database

---

[Back to Operator Hub](README.md)
