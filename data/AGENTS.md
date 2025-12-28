# Data Directory - Agent Guide

## Purpose

This directory stores runtime data for the Home Security Intelligence application, including the SQLite database, image thumbnails, and log files.

## Directory Contents

```
data/
  AGENTS.md           # This file
  security.db         # SQLite database (runtime, git-ignored)
  security.db-shm     # SQLite shared memory (runtime)
  security.db-wal     # SQLite write-ahead log (runtime)
  thumbnails/         # Cached image thumbnails (runtime)
  logs/               # Application log files (runtime)
```

## Key Files

### security.db

**Purpose:** Primary data store for all application data.

**Contents:**

- Camera configurations and metadata
- Detection events and object bounding boxes
- Risk analysis results from Nemotron LLM
- GPU statistics and system metrics
- WebSocket broadcast state

**Location:** `data/security.db` (configurable via DATABASE_URL in .env)

**Size:** Typically 1-5 MB, grows with events

**Initialization:** Automatically created on first backend startup via `backend/core/database.py`

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
    status VARCHAR NOT NULL,          -- "active" or "inactive"
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
# Open database with sqlite3
sqlite3 data/security.db

# Common queries
.tables                           # List all tables
.schema cameras                   # Show table schema
SELECT * FROM cameras;            # List all cameras
SELECT COUNT(*) FROM events;      # Count events
SELECT * FROM events ORDER BY timestamp DESC LIMIT 10;
.quit                             # Exit
```

### Database Reset

```bash
# Stop backend server first
./scripts/dev.sh stop

# Delete database
rm -f data/security.db

# Restart backend (will recreate database)
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

## Git Ignore Rules

The following files are excluded from git:

```gitignore
# Database files
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
# Simple backup
cp data/security.db data/security.db.backup

# Backup with timestamp
cp data/security.db data/security.db.$(date +%Y%m%d_%H%M%S)

# Compressed backup
tar -czf security_backup_$(date +%Y%m%d).tar.gz data/
```

### Restore from Backup

```bash
# Stop backend
./scripts/dev.sh stop

# Restore database
cp data/security.db.backup data/security.db

# Restart backend
./scripts/dev.sh start
```

## Troubleshooting

### Database Locked Errors

```bash
# Check for stale connections
lsof data/security.db

# Remove lock files
rm -f data/security.db-journal data/security.db-shm data/security.db-wal
```

### Corrupted Database

```bash
# Check integrity
sqlite3 data/security.db "PRAGMA integrity_check;"

# Attempt repair
sqlite3 data/security.db ".recover" > recovered.sql
sqlite3 data/security_new.db < recovered.sql

# Or restore from backup
cp data/security.db.backup data/security.db
```

### Disk Space Issues

```bash
# Check database size
du -h data/security.db

# Check total data directory size
du -sh data/

# Run cleanup manually
curl -X POST http://localhost:8000/api/v1/admin/cleanup

# Reduce retention period in .env
# RETENTION_DAYS=7
```

## Performance Considerations

### Database Size

- **Events:** ~1-2 KB per event
- **Detections:** ~100-200 bytes per detection
- **GPU Stats:** ~100 bytes per sample
- **Estimated growth:** 10-50 MB per month

### Query Optimization

- Indexes on primary keys and foreign keys
- Use pagination for large result sets
- Always filter events by timestamp range

### SQLite Limitations

- **Concurrent writes:** Limited (use Redis for high-throughput)
- **Database size:** Practical limit ~10 GB
- **Connection pooling:** Handled by SQLAlchemy

## Related Documentation

- `backend/models/AGENTS.md` - SQLAlchemy model definitions
- `backend/core/database.py` - Connection and session management
- `backend/services/cleanup_service.py` - Retention policy
- `.env.example` - Database URL and retention settings
- `scripts/seed-cameras.py` - Database population tool
