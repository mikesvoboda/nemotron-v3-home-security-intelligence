# Database Troubleshooting

> Solving PostgreSQL connection, migration, and performance problems.

**Time to read:** ~5 min
**Prerequisites:** None

---

## Missing DATABASE_URL

### Symptoms

- Error: `DATABASE_URL environment variable is required`
- Backend fails to start
- Validation error on startup

### Solutions

**1. Create or update `.env` file:**

```bash
# In project root
cat >> .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://security:your_password@localhost:5432/security
EOF
```

**2. For Docker, use container hostname:**

```bash
DATABASE_URL=postgresql+asyncpg://security:your_password@postgres:5432/security
```

**3. Verify format:**

```
postgresql+asyncpg://user:password@host:port/database
```

Components:

- `postgresql+asyncpg://` - Required prefix (async driver)
- `user:password` - Database credentials
- `host:port` - Database server address
- `database` - Database name

---

## Connection Refused

### Symptoms

- Error: `connection refused`
- Error: `could not connect to server`
- Health check shows database unhealthy

### Diagnosis

```bash
# Check if PostgreSQL is running
docker compose -f docker-compose.prod.yml ps postgres

# Test connection directly
psql -h localhost -U security -d security

# Check PostgreSQL logs
docker compose -f docker-compose.prod.yml logs postgres
```

### Solutions

**1. Start PostgreSQL:**

```bash
docker compose -f docker-compose.prod.yml up -d postgres
```

**2. Check port:**

```bash
# Default PostgreSQL port
ss -tlnp | grep 5432
```

**3. Check firewall (if remote):**

```bash
# Allow PostgreSQL port
sudo ufw allow 5432/tcp
```

**4. Check `pg_hba.conf` allows connections:**

For Docker, this is usually handled by the image.

---

## Missing Migrations

### Symptoms

- Error: `relation "cameras" does not exist`
- Error: `relation "events" does not exist`
- Tables missing from database

### Diagnosis

```bash
# List existing tables
psql -h localhost -U security -d security -c "\dt"

# Check alembic version
psql -h localhost -U security -d security -c "SELECT * FROM alembic_version;"
```

### Solutions

**1. Run migrations:**

```bash
# Using alembic directly
cd backend
alembic upgrade head

# Or in container
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

**2. Create database if needed:**

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres

# Create database and user
CREATE USER security WITH PASSWORD 'your_password';
CREATE DATABASE security OWNER security;
GRANT ALL PRIVILEGES ON DATABASE security TO security;
\q
```

---

## Connection Pool Exhausted

### Symptoms

- Error: `too many connections`
- Error: `connection pool exhausted`
- Requests hang then timeout

### Diagnosis

```bash
# Check active connections
psql -h localhost -U security -d security -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'security';"

# Check max connections
psql -h localhost -U security -d security -c "SHOW max_connections;"
```

### Solutions

**1. Increase PostgreSQL connections:**

```bash
# In postgresql.conf or via ALTER SYSTEM
ALTER SYSTEM SET max_connections = 200;
# Restart PostgreSQL
```

**2. Check for connection leaks:**

Look for:

- Unclosed database sessions in code
- Long-running transactions
- Tests not cleaning up connections

**3. Adjust connection pool:**

The backend uses SQLAlchemy async pool. Default settings are usually sufficient.

---

## Slow Queries

### Symptoms

- API responses slow
- Database CPU high
- Timeout errors on complex queries

### Diagnosis

```bash
# Enable query logging (temporary)
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000;  # Log queries >1s
SELECT pg_reload_conf();

# Check slow queries
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Solutions

**1. Check indexes exist:**

```bash
# List indexes
psql -h localhost -U security -d security -c "\di"
```

Required indexes should include:

- `events.started_at`
- `events.camera_id`
- `detections.camera_id`
- `detections.detected_at`

**2. Analyze tables:**

```bash
psql -h localhost -U security -d security -c "ANALYZE;"
```

**3. Vacuum old data:**

```bash
psql -h localhost -U security -d security -c "VACUUM ANALYZE;"
```

**4. Run cleanup:**

Old data slows queries. Trigger cleanup:

```bash
curl -X POST http://localhost:8000/api/system/cleanup
```

---

## Disk Space

### Symptoms

- Error: `No space left on device`
- Database operations fail
- Log: `could not extend file`

### Diagnosis

```bash
# Check disk usage
df -h

# Check database size
psql -h localhost -U security -d security -c "SELECT pg_size_pretty(pg_database_size('security'));"

# Check table sizes
psql -h localhost -U security -d security -c "
SELECT
  table_name,
  pg_size_pretty(pg_total_relation_size(quote_ident(table_name)))
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;
"
```

### Solutions

**1. Run cleanup:**

```bash
# Preview what would be deleted
curl -X POST "http://localhost:8000/api/system/cleanup?dry_run=true"

# Actually clean up
curl -X POST http://localhost:8000/api/system/cleanup
```

**2. Vacuum to reclaim space:**

```bash
psql -h localhost -U security -d security -c "VACUUM FULL;"
```

**Warning:** `VACUUM FULL` locks tables. Run during low activity.

**3. Reduce retention:**

```bash
# Default is 30 days
RETENTION_DAYS=14
LOG_RETENTION_DAYS=3
```

**4. Clean PostgreSQL logs:**

```bash
# Find PostgreSQL data directory
docker compose -f docker-compose.prod.yml exec postgres ls -la /var/lib/postgresql/data/log/
```

---

## Authentication Errors

### Symptoms

- Error: `password authentication failed`
- Error: `FATAL: role "security" does not exist`
- Connection rejected

### Solutions

**1. Verify credentials:**

```bash
# Test with psql
PGPASSWORD=your_password psql -h localhost -U security -d security
```

**2. Reset password:**

```bash
psql -h localhost -U postgres -c "ALTER USER security WITH PASSWORD 'new_password';"
```

**3. Create missing role:**

```bash
psql -h localhost -U postgres -c "CREATE USER security WITH PASSWORD 'your_password';"
psql -h localhost -U postgres -c "CREATE DATABASE security OWNER security;"
```

---

## Backup and Recovery

### Create Backup

```bash
# Full backup
pg_dump -h localhost -U security security > backup_$(date +%Y%m%d).sql

# Compressed backup
pg_dump -h localhost -U security security | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore Backup

```bash
# From SQL file
psql -h localhost -U security security < backup_20250115.sql

# From compressed
gunzip -c backup_20250115.sql.gz | psql -h localhost -U security security
```

---

## Next Steps

- [Connection Issues](connection-issues.md) - Network problems
- [Troubleshooting Index](index.md) - Back to symptom index

---

## See Also

- [Database Management](../../operator/database.md) - PostgreSQL setup and maintenance
- [Backup and Recovery](../../operator/backup.md) - Backup procedures
- [Data Model](../../developer/data-model.md) - Database schema reference
- [Environment Variable Reference](../config/env-reference.md) - Database configuration

---

[Back to Operator Hub](../../operator-hub.md)
