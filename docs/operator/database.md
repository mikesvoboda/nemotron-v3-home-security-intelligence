# PostgreSQL Database Setup and Management

> Complete guide to setting up, configuring, and maintaining PostgreSQL for Home Security Intelligence.

**Time to read:** ~12 min
**Prerequisites:** Container runtime (Docker/Podman), PostgreSQL basics

---

## Database Overview

Home Security Intelligence uses **PostgreSQL 16+** as its primary data store. PostgreSQL was chosen for full-text search (TSVECTOR), JSONB support, and robust async performance via asyncpg.

> **Note:** SQLite is not supported. PostgreSQL is required for all deployments.

### Schema Summary

| Table Group   | Tables                                        | Purpose              |
| ------------- | --------------------------------------------- | -------------------- |
| Security Data | `cameras`, `events`, `detections`, `zones`    | Core monitoring data |
| Alerting      | `alerts`, `alert_rules`                       | Notification system  |
| System        | `gpu_stats`, `logs`, `audit_logs`, `api_keys` | Operations and audit |
| Analytics     | `activity_baselines`, `class_baselines`       | Anomaly detection    |

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
docker compose -f docker-compose.prod.yml up -d postgres

# Verify health
docker compose -f docker-compose.prod.yml ps postgres
```

**Default credentials (from docker-compose.prod.yml):**

```bash
POSTGRES_USER=security
POSTGRES_PASSWORD=security_dev_password
POSTGRES_DB=security
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

### Run Migrations

```bash
source .venv/bin/activate
cd backend
alembic upgrade head

# Verify
alembic current
```

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

Default pool configuration (tunable in `backend/core/database.py`):

| Setting        | Default | Description         |
| -------------- | ------- | ------------------- |
| `pool_size`    | 10      | Base connections    |
| `max_overflow` | 20      | Burst capacity      |
| `pool_timeout` | 30s     | Wait for connection |
| `pool_recycle` | 1800s   | Connection lifetime |

---

## Migrations

### Common Commands

```bash
cd backend

# Apply all migrations
alembic upgrade head

# Check status
alembic current
alembic history

# Roll back one migration
alembic downgrade -1

# Roll back to specific revision
alembic downgrade <revision_id>
```

### Creating Migrations (Developers)

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "description"

# Preview SQL without applying
alembic upgrade head --sql
```

### Handling Failures

1. Check error: `alembic upgrade head 2>&1`
2. Verify state: `SELECT * FROM alembic_version;`
3. Fix and stamp: `alembic stamp <revision_id>`

---

## Maintenance

### Vacuum and Analyze

```bash
# Via container
docker compose exec postgres psql -U security -d security -c "VACUUM ANALYZE;"
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

```bash
curl http://localhost:8000/api/system/cleanup/preview
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
docker compose -f docker-compose.prod.yml ps postgres

# Test connectivity
pg_isready -h localhost -p 5432 -U security

# Check logs
docker compose -f docker-compose.prod.yml logs postgres
```

**Fix:** Ensure `DATABASE_URL` uses `postgres` for container or `localhost` for native.

### Authentication Failed

```bash
# Test credentials
docker compose exec postgres psql -U security -d security -c "SELECT 1;"

# Reset password
docker compose exec postgres psql -U postgres -c \
  "ALTER USER security WITH PASSWORD 'new_password';"
```

### Migration Conflicts

```bash
# Check state
alembic current

# If schema matches but tracking is off
alembic stamp <revision_id>
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
docker system df

# Emergency cleanup
DELETE FROM gpu_stats WHERE recorded_at < NOW() - INTERVAL '7 days';
VACUUM FULL;
```

---

## Quick Reference

### Essential Commands

```bash
# Start database
docker compose -f docker-compose.prod.yml up -d postgres

# Connect to database
docker compose exec postgres psql -U security -d security

# Run migrations
cd backend && alembic upgrade head

# Check health
docker compose exec postgres pg_isready -U security -d security

# Backup
docker compose exec postgres pg_dump -U security security > backup.sql

# Restore
docker compose exec -T postgres psql -U security security < backup.sql
```

### Connection URLs

| Environment | URL                                                              |
| ----------- | ---------------------------------------------------------------- |
| Container   | `postgresql+asyncpg://security:password@postgres:5432/security`  |
| Native      | `postgresql+asyncpg://security:password@localhost:5432/security` |

---

## Next Steps

- [Backup and Recovery](../DOCKER_DEPLOYMENT.md#backup-and-recovery) - Database backup procedures
- [Monitoring](../admin-guide/monitoring.md) - Monitor database health
- [Storage Retention](../admin-guide/storage-retention.md) - Configure retention policies

---

[Back to Operator Hub](../operator-hub.md)
