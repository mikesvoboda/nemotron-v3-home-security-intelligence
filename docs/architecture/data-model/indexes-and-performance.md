# Indexes and Performance

> GIN indexes, BRIN indexes, query patterns, and performance optimization strategies.

## Overview

The data model uses several PostgreSQL-specific index types to optimize different query patterns:

| Index Type | Best For                            | Size       | Update Cost |
| ---------- | ----------------------------------- | ---------- | ----------- |
| B-tree     | Equality and range queries          | Medium     | Low         |
| GIN        | JSONB containment, full-text search | Large      | High        |
| BRIN       | Time-series data (append-only)      | Very Small | Very Low    |
| Partial    | Filtered queries (WHERE clause)     | Small      | Low         |

---

## GIN Indexes

GIN (Generalized Inverted Index) indexes are used for JSONB queries and full-text search.

### JSONB Containment Queries

**Index:** `ix_detections_enrichment_data_gin`

**Source:** `backend/models/detection.py:122-127`

```sql
CREATE INDEX ix_detections_enrichment_data_gin
ON detections USING gin (enrichment_data jsonb_path_ops);
```

**Purpose:** Enables fast containment queries (`@>`) on the `enrichment_data` JSONB column.

**Query Pattern:**

```sql
-- Find detections with license plate data
SELECT * FROM detections
WHERE enrichment_data @> '{"license_plates": [{}]}';

-- Find detections with specific vehicle color
SELECT * FROM detections
WHERE enrichment_data @> '{"vehicle": {"color": "red"}}';
```

**Performance Characteristics:**

- Uses `jsonb_path_ops` operator class (smaller index, faster containment)
- Cannot support key existence (`?`) or key/value queries
- Best for nested path containment queries

---

### Entity Metadata Index

**Index:** `ix_entities_entity_metadata_gin`

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:593-599`

```sql
CREATE INDEX ix_entities_entity_metadata_gin
ON entities USING gin (entity_metadata jsonb_path_ops);
```

**Purpose:** Fast lookups on entity metadata (clothing color, vehicle make/model).

---

### Full-Text Search Indexes

**Index:** `idx_events_search_vector`

**Source:** `backend/models/event.py:180`

```sql
CREATE INDEX idx_events_search_vector
ON events USING gin (search_vector);
```

**Purpose:** Full-text search across event summaries, reasoning, and object types.

**Query Pattern:**

```sql
-- Search events for "person" and "door"
SELECT * FROM events
WHERE search_vector @@ to_tsquery('english', 'person & door')
ORDER BY started_at DESC;
```

---

**Index:** `idx_logs_search_vector`

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:211`

```sql
CREATE INDEX idx_logs_search_vector
ON logs USING gin (search_vector);
```

**Purpose:** Full-text search across log messages.

---

## BRIN Indexes

BRIN (Block Range Index) indexes are highly efficient for time-series data where rows are naturally ordered by timestamp.

### Why BRIN for Time-Series Data

| Feature       | B-tree                | BRIN              |
| ------------- | --------------------- | ----------------- |
| Index Size    | Large (~10% of table) | Tiny (~0.01%)     |
| Update Cost   | O(log n)              | O(1) amortized    |
| Range Queries | Fast                  | Fast              |
| Point Queries | Fast                  | Slower            |
| Best For      | Random access         | Sequential/append |

### Time-Series BRIN Indexes

**Index:** `ix_detections_detected_at_brin`

**Source:** `backend/models/detection.py:130-134`

```sql
CREATE INDEX ix_detections_detected_at_brin
ON detections USING brin (detected_at);
```

**Purpose:** Efficient range queries on chronologically ordered detections.

**Query Pattern:**

```sql
-- Get detections from the last 24 hours
SELECT * FROM detections
WHERE detected_at > NOW() - INTERVAL '24 hours'
ORDER BY detected_at DESC;
```

---

**Index:** `ix_events_started_at_brin`

**Source:** `backend/models/event.py:225-229`

```sql
CREATE INDEX ix_events_started_at_brin
ON events USING brin (started_at);
```

---

**Index:** `ix_gpu_stats_recorded_at_brin`

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:251-253`

```sql
CREATE INDEX ix_gpu_stats_recorded_at_brin
ON gpu_stats USING brin (recorded_at);
```

---

**Index:** `ix_audit_logs_timestamp_brin`

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:177-178`

```sql
CREATE INDEX ix_audit_logs_timestamp_brin
ON audit_logs USING brin (timestamp);
```

---

**Index:** `ix_logs_timestamp_brin`

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:210`

```sql
CREATE INDEX ix_logs_timestamp_brin
ON logs USING brin (timestamp);
```

---

## Partial Indexes

Partial indexes only index rows that match a WHERE condition, reducing size and improving query speed.

### Unreviewed Events Index

**Index:** `idx_events_unreviewed`

**Source:** `backend/models/event.py:200-204`

```sql
CREATE INDEX idx_events_unreviewed
ON events (id)
WHERE reviewed = false;
```

**Purpose:** Fast count and listing of unreviewed events for the dashboard.

**Query Pattern:**

```sql
-- Count unreviewed events
SELECT COUNT(*) FROM events WHERE reviewed = false;

-- List unreviewed events
SELECT * FROM events
WHERE reviewed = false
ORDER BY started_at DESC
LIMIT 10;
```

---

### Unacknowledged Scene Changes Index

**Index:** `idx_scene_changes_acknowledged_false`

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:985-989`

```sql
CREATE INDEX idx_scene_changes_acknowledged_false
ON scene_changes (acknowledged)
WHERE acknowledged = false;
```

---

## Composite Indexes

Composite indexes cover multiple columns to optimize multi-condition queries.

### Events Composite Indexes

| Index Name                         | Columns                  | Purpose                           |
| ---------------------------------- | ------------------------ | --------------------------------- |
| `idx_events_risk_level_started_at` | `risk_level, started_at` | Filter by risk + time             |
| `idx_events_export_covering`       | 8 columns                | Covering index for export queries |

**Export Covering Index:**

**Source:** `backend/models/event.py:187-197`

```sql
CREATE INDEX idx_events_export_covering ON events (
    started_at,
    id,
    ended_at,
    risk_level,
    risk_score,
    camera_id,
    object_types,
    summary
);
```

**Purpose:** Avoids table lookups for export queries by including all needed columns.

---

### Detections Composite Indexes

| Index Name                              | Columns                    | Purpose               |
| --------------------------------------- | -------------------------- | --------------------- |
| `idx_detections_camera_time`            | `camera_id, detected_at`   | Camera + time filter  |
| `idx_detections_camera_object_type`     | `camera_id, object_type`   | Camera + class filter |
| `ix_detections_object_type_detected_at` | `object_type, detected_at` | Class-based analytics |

**Source:** `backend/models/detection.py:112-119`

---

### Alerts Composite Indexes

| Index Name                        | Columns                           | Purpose              |
| --------------------------------- | --------------------------------- | -------------------- |
| `idx_alerts_dedup_key_created_at` | `dedup_key, created_at`           | Deduplication + time |
| `idx_alerts_event_rule_delivered` | `event_id, rule_id, delivered_at` | Combined lookup      |

**Source:** `backend/alembic/versions/e36700c35af6_initial_schema.py:1117-1121`

---

## Query Patterns and Optimization

### Dashboard Event List

**Query:**

```sql
SELECT e.*, c.name as camera_name
FROM events e
JOIN cameras c ON e.camera_id = c.id
WHERE e.deleted_at IS NULL
ORDER BY e.started_at DESC
LIMIT 20 OFFSET 0;
```

**Indexes Used:**

- `ix_events_started_at_brin` (range scan on started_at)
- Primary key on cameras

**Optimization Notes:**

- BRIN index efficient for recent events due to chronological ordering
- Soft delete filter (deleted_at IS NULL) scans efficiently

---

### Unreviewed Events Count

**Query:**

```sql
SELECT COUNT(*) FROM events WHERE reviewed = false;
```

**Indexes Used:**

- `idx_events_unreviewed` (partial index)

**Optimization Notes:**

- Partial index only contains unreviewed rows
- Count is fast even with millions of total events

---

### Camera Detection Timeline

**Query:**

```sql
SELECT * FROM detections
WHERE camera_id = 'front_door'
  AND detected_at > NOW() - INTERVAL '24 hours'
ORDER BY detected_at DESC;
```

**Indexes Used:**

- `idx_detections_camera_time` (camera_id, detected_at)

**Optimization Notes:**

- Composite index covers both filter conditions
- Eliminates need for sorting (index already ordered)

---

### Full-Text Search on Events

**Query:**

```sql
SELECT * FROM events
WHERE search_vector @@ plainto_tsquery('english', 'person delivery package')
  AND started_at > NOW() - INTERVAL '7 days'
ORDER BY ts_rank(search_vector, plainto_tsquery('english', 'person delivery package')) DESC
LIMIT 20;
```

**Indexes Used:**

- `idx_events_search_vector` (GIN for full-text)
- `ix_events_started_at_brin` (time filter)

**Optimization Notes:**

- GIN index provides efficient full-text matching
- Time filter narrows results before ranking

---

### JSONB Enrichment Query

**Query:**

```sql
SELECT d.*, e.summary, e.risk_score
FROM detections d
JOIN event_detections ed ON d.id = ed.detection_id
JOIN events e ON ed.event_id = e.id
WHERE d.enrichment_data @> '{"license_plates": [{"text": "ABC123"}]}'
ORDER BY d.detected_at DESC
LIMIT 10;
```

**Indexes Used:**

- `ix_detections_enrichment_data_gin` (JSONB containment)
- Junction table indexes

**Optimization Notes:**

- GIN index with jsonb_path_ops enables nested path queries
- JOIN optimization through foreign key indexes

---

## Index Maintenance

### Monitoring Index Usage

```sql
-- Check index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Find unused indexes (candidates for removal)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname = 'public';
```

### Monitoring Index Bloat

```sql
-- Check index bloat (requires pgstattuple extension)
SELECT
    relname,
    pg_size_pretty(pg_relation_size(relid)) as size,
    round(100.0 * pg_relation_size(indexrelid) / pg_relation_size(relid), 2) as index_pct
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_relation_size(relid) DESC
LIMIT 10;
```

### Reindexing

```sql
-- Reindex a specific index (online in PG 12+)
REINDEX INDEX CONCURRENTLY idx_events_search_vector;

-- Reindex entire table
REINDEX TABLE CONCURRENTLY events;
```

---

## Performance Recommendations

### 1. Use Appropriate Index Type

| Data Pattern                      | Recommended Index    |
| --------------------------------- | -------------------- |
| Time-series, append-only          | BRIN                 |
| JSONB nested queries              | GIN (jsonb_path_ops) |
| Full-text search                  | GIN (tsvector)       |
| High-cardinality equality         | B-tree               |
| Low-cardinality filter            | Partial index        |
| Multiple columns queried together | Composite B-tree     |

### 2. Column Order in Composite Indexes

Place columns in order of:

1. Equality conditions first
2. Range conditions second
3. Columns needed for sorting last

```sql
-- Good: camera_id (equality) then detected_at (range/sort)
CREATE INDEX idx_detections_camera_time ON detections (camera_id, detected_at);
```

### 3. Covering Indexes for Read-Heavy Queries

Include frequently selected columns to avoid table lookups:

```sql
-- Covering index for export query
CREATE INDEX idx_events_export_covering ON events (
    started_at, id, ended_at, risk_level, risk_score, camera_id, object_types, summary
);
```

### 4. Partial Indexes for Filtered Queries

Use when queries consistently filter on a specific condition:

```sql
-- Only index unreviewed events
CREATE INDEX idx_events_unreviewed ON events (id) WHERE reviewed = false;
```

### 5. Regular VACUUM and ANALYZE

```sql
-- Update statistics for query planner
ANALYZE events;

-- Reclaim space and update visibility map
VACUUM (VERBOSE) events;

-- Full vacuum (locks table, use sparingly)
VACUUM FULL events;
```
