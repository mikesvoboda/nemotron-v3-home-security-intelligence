# Data Directory - Agent Guide

## Purpose

This directory stores runtime data for the Home Security Intelligence application, including image thumbnails and temporary processing files. **Note:** The database has been migrated from SQLite to PostgreSQL and is no longer stored in this directory.

## Directory Contents

```
data/
  AGENTS.md           # This file
  logs/               # Application log files (runtime, currently empty)
```

Note: The `thumbnails/` directory is created at runtime when events are processed. Additional subdirectories may be created as needed.

**MIGRATED TO POSTGRESQL** - This directory no longer stores the database.

The application now uses PostgreSQL instead of SQLite:

- **Database:** PostgreSQL (runs as Docker service or natively)
- **Connection:** Configured via `DATABASE_URL` in `.env` (e.g., `postgresql+asyncpg://user:pass@localhost:5432/home_security`)
- **What it contains:**
  - Camera configurations and metadata
  - Detection events and object bounding boxes
  - Risk analysis results from Nemotron LLM
  - GPU statistics and system metrics
  - WebSocket broadcast state
- **Schema:** Defined by SQLAlchemy models in `backend/models/`
- **Tables:**
  - `cameras` - Camera configuration (id, name, folder_path, status)
  - `events` - Security events with risk scores and reasoning
  - `detections` - Object detection results (bbox, confidence, class)
  - `gpu_stats` - GPU utilization and VRAM usage over time
  - Other system tables (migrations, indexes)
- **Initialization:** Tables automatically created on first backend startup via `backend/core/database.py`
- **Retention:** Events older than 30 days are cleaned up by `backend/services/cleanup_service.py`
- **Backup:** Use PostgreSQL native backup tools (`pg_dump`, `pg_basebackup`)

## Key Files

### thumbnails/

**Purpose:** Store resized thumbnails for faster web UI loading.

**Contents:**

- Thumbnail images for event snapshots
- Generated on-demand by backend services
- Format: JPEG images (typically 200x150px)
- Naming: `{event_id}.jpg` or `{image_hash}.jpg`

### logs/

**Purpose:** Application log files.

**Contents:**

- Backend server logs
- Frontend build logs (if applicable)
- Debug output

## Database Schema

### cameras Table

```sql
CREATE TABLE cameras (
    id VARCHAR PRIMARY KEY,           -- Camera identifier (e.g., "front-door")
    name VARCHAR NOT NULL,            -- Display name (e.g., "Front Door")
    folder_path VARCHAR NOT NULL,     -- Path to camera images
    status VARCHAR NOT NULL,          -- "online", "offline", or "error"
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### events Table

```sql
CREATE TABLE events (
    id VARCHAR PRIMARY KEY,           -- UUID
    camera_id VARCHAR NOT NULL,       -- Foreign key to cameras
    timestamp TIMESTAMP NOT NULL,     -- Event occurrence time
    risk_score INTEGER NOT NULL,      -- 0-100 risk score from Nemotron
    reasoning TEXT NOT NULL,          -- LLM explanation of risk
    image_path VARCHAR,               -- Path to snapshot image
    thumbnail_path VARCHAR,           -- Path to thumbnail
    created_at TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(id)
);
```

### detections Table

```sql
CREATE TABLE detections (
    id VARCHAR PRIMARY KEY,           -- UUID
    event_id VARCHAR NOT NULL,        -- Foreign key to events
    class_name VARCHAR NOT NULL,      -- Object class (person, car, etc.)
    confidence FLOAT NOT NULL,        -- Detection confidence (0-1)
    bbox_x FLOAT,                     -- Bounding box coordinates
    bbox_y FLOAT,
    bbox_width FLOAT,
    bbox_height FLOAT,
    created_at TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id)
);
```

### gpu_stats Table

```sql
CREATE TABLE gpu_stats (
    id VARCHAR PRIMARY KEY,           -- UUID
    timestamp TIMESTAMP NOT NULL,     -- Sample time
    gpu_utilization FLOAT NOT NULL,   -- GPU usage percentage (0-100)
    vram_used INTEGER NOT NULL,       -- VRAM used in MB
    vram_total INTEGER NOT NULL,      -- Total VRAM in MB
    temperature FLOAT,                -- GPU temperature in Celsius
    power_draw FLOAT,                 -- Power draw in Watts
    created_at TIMESTAMP
);
```

## Database Operations

### Seeding Test Data

```bash
# Seed 6 default cameras
./scripts/seed-cameras.py

# Seed without creating folders
./scripts/seed-cameras.py --no-folders

# Clear and re-seed
./scripts/seed-cameras.py --clear --count 6

# List existing cameras
./scripts/seed-cameras.py --list
```

### Manual Database Inspection

```bash
# Connect to PostgreSQL database
psql -h localhost -U username -d home_security

# Common queries
\dt                                              # List all tables
\d cameras                                       # Show table schema
SELECT * FROM cameras;                           # List all cameras
SELECT COUNT(*) FROM events;                     # Count events
SELECT * FROM events ORDER BY timestamp DESC LIMIT 10;
\q                                               # Exit

# Or use a GUI tool like pgAdmin, DBeaver, or DataGrip
```

### Database Reset

```bash
# Stop backend server first
./scripts/dev.sh stop

# Drop and recreate database (PostgreSQL)
psql -h localhost -U username -c "DROP DATABASE IF EXISTS home_security;"
psql -h localhost -U username -c "CREATE DATABASE home_security;"

# Restart backend (will recreate tables)
./scripts/dev.sh start

# Re-seed test data
./scripts/seed-cameras.py
```

## Data Retention

### Automatic Cleanup

- **Default retention:** 30 days
- **Configuration:** RETENTION_DAYS in .env
- **Service:** `backend/services/cleanup_service.py`
- **Schedule:** Runs every 24 hours

**What it removes:**

- Events older than retention period
- Associated detections
- Orphaned thumbnails
- Orphaned image files

```python
# Run cleanup service manually
from backend.services.cleanup_service import CleanupService

cleanup = CleanupService(retention_days=30)
await cleanup.cleanup_old_events()
```

## Directory Structure

```
data/
├── AGENTS.md           # This file
├── logs/               # Application log files (runtime)
└── thumbnails/         # Cached image thumbnails (created at runtime)
    ├── {event_id}.jpg
    └── ...
```

## Git Ignore Rules

The following files are excluded from git:

```gitignore
# Database files (legacy SQLite - no longer used)
data/*.db
data/*.db-journal
data/*.db-shm
data/*.db-wal

# Thumbnails
data/thumbnails/*

# Logs
data/logs/*
```

## Backup and Restore

### Manual Backup

```bash
# PostgreSQL backup
pg_dump -h localhost -U username -F c home_security > backup.dump

# Backup with timestamp
pg_dump -h localhost -U username -F c home_security > backup_$(date +%Y%m%d_%H%M%S).dump

# Compressed backup including thumbnails
tar -czf security_backup_$(date +%Y%m%d).tar.gz data/thumbnails/
```

### Restore from Backup

```bash
# Stop backend
./scripts/dev.sh stop

# Restore PostgreSQL database
pg_restore -h localhost -U username -d home_security -c backup.dump

# Restart backend
./scripts/dev.sh start
```

## Database Migration

When database schema changes:

1. **Alembic migrations** (recommended):

   ```bash
   alembic revision --autogenerate -m "Add new field"
   alembic upgrade head
   ```

2. **Manual migration** (if needed):
   - Schema changes are applied automatically on startup
   - SQLAlchemy creates missing tables/columns
   - For complex changes, backup database first

## Performance Considerations

### Database Size

- **Events:** ~1-2 KB per event
- **Detections:** ~100-200 bytes per detection
- **GPU Stats:** ~100 bytes per sample
- **Estimated growth:** 10-50 MB per month (depends on camera activity)

### Query Optimization

- **Indexes:** Automatically created on primary keys and foreign keys
- **Compound indexes:** Add for frequently queried combinations
- **Query limits:** Use pagination for large result sets
- **Date ranges:** Always filter events by timestamp range

### Database Performance Considerations

- **Concurrent access:** PostgreSQL handles multiple concurrent reads and writes efficiently
- **Connection pooling:** Managed by SQLAlchemy and asyncpg
- **Database size:** PostgreSQL scales to terabytes without performance degradation
- **Query optimization:** Use indexes and EXPLAIN ANALYZE for performance tuning

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres
# or for native: systemctl status postgresql

# Test database connection
psql -h localhost -U username -d home_security -c "SELECT 1;"

# Check active connections
psql -h localhost -U username -d home_security -c "SELECT count(*) FROM pg_stat_activity;"

# Kill stuck connections (if needed)
psql -h localhost -U username -d home_security -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='home_security' AND pid != pg_backend_pid();"
```

### Database Backup and Restore

```bash
# Create backup
pg_dump -h localhost -U username -F c home_security > backup.dump

# Restore from backup
pg_restore -h localhost -U username -d home_security -c backup.dump

# For Docker deployments
docker exec postgres pg_dump -U postgres -F c home_security > backup.dump
docker exec -i postgres pg_restore -U postgres -d home_security -c < backup.dump
```

### Disk Space Issues

```bash
# Check PostgreSQL database size
psql -h localhost -U username -d home_security -c "SELECT pg_size_pretty(pg_database_size('home_security'));"

# Check total data directory size (for thumbnails)
du -sh data/

# Run cleanup manually
curl -X POST http://localhost:8000/api/v1/admin/cleanup

# Reduce retention period in .env
# RETENTION_DAYS=7
```

## Related Documentation

- **Backend models:** `backend/models/AGENTS.md` - SQLAlchemy model definitions
- **Database configuration:** `backend/core/database.py` - Connection and session management
- **Cleanup service:** `backend/services/cleanup_service.py` - Retention policy implementation
- **Environment config:** `.env.example` - Database URL and retention settings
- **Seed script:** `scripts/seed-cameras.py` - Database population tool

## Entry Points for Agents

### Inspecting Database State

1. **List cameras:**

   ```bash
   ./scripts/seed-cameras.py --list
   ```

2. **Check database size:**

   ```bash
   psql -h localhost -U username -d home_security -c "SELECT pg_size_pretty(pg_database_size('home_security'));"
   ```

3. **Query database:**

   ```bash
   psql -h localhost -U username -d home_security
   # Then run SQL queries
   ```

4. **View recent events:**
   ```bash
   psql -h localhost -U username -d home_security -c "SELECT id, camera_id, timestamp, risk_score FROM events ORDER BY timestamp DESC LIMIT 10;"
   ```

### Resetting Database for Testing

1. **Stop backend:**

   ```bash
   ./scripts/dev.sh stop
   ```

2. **Drop and recreate database:**

   ```bash
   psql -h localhost -U username -c "DROP DATABASE IF EXISTS home_security; CREATE DATABASE home_security;"
   ```

3. **Restart backend:**

   ```bash
   ./scripts/dev.sh start
   ```

4. **Seed test data:**
   ```bash
   ./scripts/seed-cameras.py
   ```

### Backing Up Before Major Changes

1. **Create backup:**

   ```bash
   pg_dump -h localhost -U username -F c home_security > backup.dump
   ```

2. **Make changes...**

3. **Restore if needed:**
   ```bash
   ./scripts/dev.sh stop
   pg_restore -h localhost -U username -d home_security -c backup.dump
   ./scripts/dev.sh start
   ```
