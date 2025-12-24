# Data Directory - Agent Guide

## Purpose

This directory stores runtime data for the Home Security Intelligence application, including the SQLite database, image thumbnails, and temporary processing files.

## Key Files and Directories

### Database

**security.db** (SQLite database, typically 1-5 MB)

- **Purpose:** Primary data store for all application data
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
- **Initialization:** Automatically created on first backend startup via `backend/core/database.py`
- **Location:** `data/security.db` (configurable via DATABASE_URL in .env)
- **Retention:** Events older than 30 days are cleaned up by `backend/services/cleanup_service.py`
- **Backup:** Recommend periodic backups for production use

### Thumbnails

**thumbnails/** (subdirectory for cached image thumbnails)

- **Purpose:** Store resized thumbnails for faster web UI loading
- **What it contains:**
  - Thumbnail images for event snapshots
  - Generated on-demand by backend services
  - Cached for performance
- **Format:** JPEG images (typically 200x150px or similar)
- **Naming convention:** `{event_id}.jpg` or `{image_hash}.jpg`
- **Cleanup:** Orphaned thumbnails are removed by cleanup service
- **Disk usage:** Grows with event volume, cleaned up with old events

### Temporary Files (Not Committed)

These files may appear during runtime but are not committed to git:

- **processing/** - Temporary storage for in-flight image processing
- **.tmp/** - Temporary files during batch processing
- **cache/** - Redis-backed cache files (if using disk cache)

## Database Schema Overview

### Cameras Table

```sql
CREATE TABLE cameras (
    id VARCHAR PRIMARY KEY,           -- Camera identifier (e.g., "front-door")
    name VARCHAR NOT NULL,            -- Display name (e.g., "Front Door")
    folder_path VARCHAR NOT NULL,     -- Path to camera images
    status VARCHAR NOT NULL,          -- "active" or "inactive"
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Events Table

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

### Detections Table

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

### GPU Stats Table

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

### Initialization

The database is automatically initialized when the backend starts:

```python
# backend/core/database.py
async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### Seeding Test Data

Use the seed-cameras.py script to populate test cameras:

```bash
# Seed 6 cameras (default)
./scripts/seed-cameras.py

# Seed specific number without creating folders
./scripts/seed-cameras.py --count 3 --no-folders

# List existing cameras
./scripts/seed-cameras.py --list

# Clear and re-seed
./scripts/seed-cameras.py --clear --count 6
```

### Manual Database Inspection

```bash
# Open database with sqlite3
sqlite3 data/security.db

# Common queries
sqlite> .tables                           # List all tables
sqlite> .schema cameras                   # Show table schema
sqlite> SELECT * FROM cameras;            # List all cameras
sqlite> SELECT COUNT(*) FROM events;      # Count events
sqlite> SELECT * FROM events ORDER BY timestamp DESC LIMIT 10;
sqlite> .quit                             # Exit
```

### Database Reset

To start fresh (development only):

```bash
# Stop backend server first
# Delete database
rm -f data/security.db

# Restart backend (will recreate database)
cd backend && uvicorn main:app --reload

# Re-seed test data
./scripts/seed-cameras.py
```

## Data Retention

### Automatic Cleanup

The cleanup service runs periodically to remove old data:

- **Default retention:** 30 days
- **Configuration:** RETENTION_DAYS in .env
- **Service:** `backend/services/cleanup_service.py`
- **Schedule:** Runs every 24 hours (configurable)
- **What it removes:**
  - Events older than retention period
  - Associated detections
  - Orphaned thumbnails
  - Orphaned image files

### Manual Cleanup

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
├── security.db         # SQLite database (runtime)
├── thumbnails/         # Cached image thumbnails (runtime)
│   ├── {event_id}.jpg
│   └── ...
└── .gitignore          # Excludes runtime files from git
```

## Git Ignore Rules

The following files are excluded from git (in `.gitignore`):

```gitignore
# Database files
data/*.db
data/*.db-journal
data/*.db-shm
data/*.db-wal

# Thumbnails
data/thumbnails/*

# Temporary files
data/.tmp/
data/processing/
data/cache/
```

## Backup and Restore

### Manual Backup

```bash
# Backup database
cp data/security.db data/security.db.backup

# Backup with timestamp
cp data/security.db data/security.db.$(date +%Y%m%d_%H%M%S)

# Backup with compression
tar -czf security_backup_$(date +%Y%m%d).tar.gz data/
```

### Automated Backup (Production)

For production deployments, set up automated backups:

```bash
# Example cron job (daily at 2 AM)
0 2 * * * tar -czf /backups/security_$(date +\%Y\%m\%d).tar.gz /path/to/data/

# Keep last 7 days of backups
0 3 * * * find /backups/ -name "security_*.tar.gz" -mtime +7 -delete
```

### Restore from Backup

```bash
# Stop backend server
./scripts/dev.sh stop

# Restore database
cp data/security.db.backup data/security.db

# Or restore from compressed backup
tar -xzf security_backup_20231224.tar.gz

# Restart backend
./scripts/dev.sh start
```

## Database Migration

When database schema changes:

1. **Alembic migrations** (future feature):

   ```bash
   alembic revision --autogenerate -m "Add new field"
   alembic upgrade head
   ```

2. **Manual migration** (current approach):
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

### SQLite Limitations

- **Concurrent writes:** Limited (use Redis for high-throughput writes)
- **Database size:** Practical limit ~10 GB (consider PostgreSQL for larger deployments)
- **Connection pooling:** Handled by SQLAlchemy

## Troubleshooting

### Database Locked Errors

```bash
# Check for stale connections
lsof data/security.db

# Kill processes holding the database
kill -9 <pid>

# Remove lock files
rm -f data/security.db-journal data/security.db-shm data/security.db-wal
```

### Corrupted Database

```bash
# Check database integrity
sqlite3 data/security.db "PRAGMA integrity_check;"

# Attempt to repair
sqlite3 data/security.db ".recover" > recovered.sql
sqlite3 data/security_new.db < recovered.sql

# Restore from backup if repair fails
cp data/security.db.backup data/security.db
```

### Disk Space Issues

```bash
# Check database size
du -h data/security.db

# Check total data directory size
du -sh data/

# Run cleanup service manually
curl -X POST http://localhost:8000/api/v1/admin/cleanup

# Reduce retention period
# Edit .env: RETENTION_DAYS=7
```

## Security Considerations

### File Permissions

```bash
# Ensure proper ownership
chown -R $USER:$USER data/

# Secure database file
chmod 600 data/security.db

# Secure directory
chmod 755 data/
```

### Sensitive Data

- **No passwords stored:** Application is single-user, no authentication
- **Camera paths:** May contain sensitive location information
- **Event images:** May contain personal identifiable information
- **Backup encryption:** Consider encrypting backups for sensitive deployments

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
   du -h data/security.db
   ls -lh data/security.db
   ```

3. **Query database:**

   ```bash
   sqlite3 data/security.db
   # Then run SQL queries
   ```

4. **View recent events:**
   ```bash
   sqlite3 data/security.db "SELECT id, camera_id, timestamp, risk_score FROM events ORDER BY timestamp DESC LIMIT 10;"
   ```

### Resetting Database for Testing

1. **Stop backend:**

   ```bash
   ./scripts/dev.sh stop
   ```

2. **Delete database:**

   ```bash
   rm -f data/security.db
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
   cp data/security.db data/security.db.backup
   ```

2. **Make changes...**

3. **Restore if needed:**
   ```bash
   ./scripts/dev.sh stop
   cp data/security.db.backup data/security.db
   ./scripts/dev.sh start
   ```
