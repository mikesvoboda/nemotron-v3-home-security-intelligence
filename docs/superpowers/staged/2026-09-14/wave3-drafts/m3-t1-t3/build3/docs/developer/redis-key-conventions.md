# Redis Key Naming Conventions

> Standardized Redis key patterns for consistency, debugging, and multi-instance deployments.

**Time to read:** ~8 min
**Prerequisites:** Understanding of Redis data structures, familiarity with the backend codebase

---

## Overview

This document defines the Redis key naming conventions used throughout the Home Security Intelligence backend. Following these conventions ensures:

- **Consistency** - All developers use the same patterns
- **Debuggability** - Keys are self-documenting and easy to inspect
- **Multi-instance support** - Global prefix enables blue-green deployments (NEM-1621)
- **Collision avoidance** - Clear namespacing prevents key conflicts

---

## Global Prefix

All Redis keys SHOULD use the configurable global prefix from `REDIS_KEY_PREFIX` setting (default: `hsi`).

```python
from backend.core.config import get_settings

prefix = get_settings().redis_key_prefix  # Default: "hsi"
```

The prefix can be overridden via environment variable for blue-green deployments:

```bash
REDIS_KEY_PREFIX=hsi-blue   # Blue deployment
REDIS_KEY_PREFIX=hsi-green  # Green deployment
```

---

## Key Format Convention

### Standard Format

```
{prefix}:{domain}:{resource}:{identifier}[:{subkey}]
```

| Component    | Description                               | Example            |
| ------------ | ----------------------------------------- | ------------------ |
| `prefix`     | Global app prefix from settings           | `hsi`              |
| `domain`     | Functional area (cache, queue, job, etc.) | `cache`, `queue`   |
| `resource`   | Resource type within the domain           | `cameras`, `batch` |
| `identifier` | Unique ID for the resource instance       | `front_door`, UUID |
| `subkey`     | Optional additional key component         | `status`, `list`   |

### Examples

```
hsi:cache:cameras:list              # All cameras cache
hsi:cache:cameras:front_door        # Single camera cache
hsi:queue:detection_queue           # Detection processing queue
hsi:queue:dlq:detection_queue       # Dead-letter queue
hsi:job:abc123:status               # Job status
```

---

## Key Patterns by Domain

### Cache Keys (`cache:`)

Managed by `CacheService` and `CacheKeys` class in `backend/services/cache_service.py`.

| Pattern                                             | Purpose           | TTL   | Example                                           |
| --------------------------------------------------- | ----------------- | ----- | ------------------------------------------------- |
| `{prefix}:cache:cameras:list`                       | All cameras list  | 5 min | `hsi:cache:cameras:list`                          |
| `{prefix}:cache:cameras:list:{status}`              | Cameras by status | 5 min | `hsi:cache:cameras:list:online`                   |
| `{prefix}:cache:cameras:{id}`                       | Single camera     | 5 min | `hsi:cache:cameras:front_door`                    |
| `{prefix}:cache:event_stats:{start}:{end}:{camera}` | Event statistics  | 5 min | `hsi:cache:event_stats:2024-01-01:2024-01-31:all` |
| `{prefix}:cache:system:status`                      | System status     | 1 min | `hsi:cache:system:status`                         |

**Usage:**

```python
from backend.services.cache_service import CacheKeys

key = CacheKeys.cameras_list()  # Returns "hsi:cache:cameras:list"
key = CacheKeys.camera("front_door")  # Returns "hsi:cache:cameras:front_door"
```

### Queue Keys (`queue:`)

Processing queues for the detection pipeline. Use `get_prefixed_queue_name()` from constants.

| Pattern                                    | Purpose               | TTL  | Example                                  |
| ------------------------------------------ | --------------------- | ---- | ---------------------------------------- |
| `{prefix}:queue:{queue_name}`              | Main processing queue | None | `hsi:queue:detection_queue`              |
| `{prefix}:queue:dlq:{queue_name}`          | Dead-letter queue     | None | `hsi:queue:dlq:detection_queue`          |
| `{prefix}:queue:dlq:overflow:{queue_name}` | Overflow DLQ          | None | `hsi:queue:dlq:overflow:detection_queue` |

**Usage:**

```python
from backend.core.constants import (
    DETECTION_QUEUE,
    get_prefixed_queue_name,
)

queue_key = get_prefixed_queue_name(DETECTION_QUEUE)
# Returns "hsi:queue:detection_queue"
```

### Batch Keys (`batch:`)

Used by `BatchAggregator` for detection batching. **Note:** These keys currently use unprefixed format for backward compatibility.

| Pattern                                | Purpose                         | TTL    | Example                            |
| -------------------------------------- | ------------------------------- | ------ | ---------------------------------- |
| `batch:{camera_id}:current`            | Current batch ID for camera     | 1 hour | `batch:front_door:current`         |
| `batch:{batch_id}:camera_id`           | Batch's camera ID               | 1 hour | `batch:abc123:camera_id`           |
| `batch:{batch_id}:detections`          | Detection IDs list (Redis LIST) | 1 hour | `batch:abc123:detections`          |
| `batch:{batch_id}:started_at`          | Batch start timestamp           | 1 hour | `batch:abc123:started_at`          |
| `batch:{batch_id}:last_activity`       | Last activity timestamp         | 1 hour | `batch:abc123:last_activity`       |
| `batch:{batch_id}:pipeline_start_time` | Pipeline latency tracking       | 1 hour | `batch:abc123:pipeline_start_time` |
| `batch:{batch_id}:closing`             | Batch closing flag              | 5 min  | `batch:abc123:closing`             |

**Location:** `backend/services/batch_aggregator.py`

### Deduplication Keys (`dedupe:`)

Used by `DedupeService` for file deduplication. **Note:** Uses unprefixed format.

| Pattern                | Purpose          | TTL   | Example                  |
| ---------------------- | ---------------- | ----- | ------------------------ |
| `dedupe:{sha256_hash}` | File hash marker | 5 min | `dedupe:a1b2c3d4e5f6...` |

**Location:** `backend/services/dedupe.py`

**Constant:** `DEDUPE_KEY_PREFIX = "dedupe:"`

### Job Keys (`job:`)

Used by `JobStatusService` and `JobTracker` for background job tracking.

| Pattern                | Purpose                       | TTL                | Example              |
| ---------------------- | ----------------------------- | ------------------ | -------------------- |
| `job:{job_id}:status`  | Job metadata JSON             | 1 hour (completed) | `job:abc123:status`  |
| `job:{job_id}:control` | Job control channel (pub/sub) | None               | `job:abc123:control` |
| `job:status:list`      | Sorted set of job IDs         | None               | `job:status:list`    |
| `jobs:active`          | Sorted set of active jobs     | None               | `jobs:active`        |
| `jobs:completed`       | Sorted set of completed jobs  | 1 hour             | `jobs:completed`     |

**Location:** `backend/services/job_status.py`, `backend/services/job_tracker.py`

### Orchestrator Keys (`orchestrator:`)

Used by `ServiceRegistry` for container service state persistence.

| Pattern                             | Purpose            | TTL  | Example                                |
| ----------------------------------- | ------------------ | ---- | -------------------------------------- |
| `orchestrator:service:{name}:state` | Service state JSON | None | `orchestrator:service:ai-yolo26:state` |

**Location:** `backend/services/managed_service.py`, `backend/services/orchestrator/registry.py`

### Entity Embeddings (`entity_embeddings:`)

Used by `ReIdentificationService` for person/vehicle re-identification.

| Pattern                    | Purpose               | TTL      | Example                        |
| -------------------------- | --------------------- | -------- | ------------------------------ |
| `entity_embeddings:{date}` | Daily embeddings JSON | 48 hours | `entity_embeddings:2024-01-15` |

**Location:** `backend/services/reid_service.py`

### Camera Status Keys (`camera:`)

Used by `CameraService` for status debouncing.

| Pattern                              | Purpose           | TTL    | Example                             |
| ------------------------------------ | ----------------- | ------ | ----------------------------------- |
| `camera:status:debounce:{camera_id}` | Debounce tracking | 30 sec | `camera:status:debounce:front_door` |

**Location:** `backend/services/camera_service.py`

### Telemetry Keys (`telemetry:`)

Used by system routes for latency tracking.

| Pattern                     | Purpose                 | TTL   | Example                       |
| --------------------------- | ----------------------- | ----- | ----------------------------- |
| `telemetry:latency:{stage}` | Pipeline stage latency  | 5 min | `telemetry:latency:detection` |
| `model_zoo:latency:{model}` | Model inference latency | 5 min | `model_zoo:latency:yolo26`    |

**Location:** `backend/api/routes/system.py`

### Cost Tracking Keys (`hsi:cost_tracking:`)

Used by `CostTracker` for usage tracking. Uses prefixed format.

| Pattern                          | Purpose          | TTL  | Example                              |
| -------------------------------- | ---------------- | ---- | ------------------------------------ |
| `hsi:cost_tracking:daily:{date}` | Daily usage hash | None | `hsi:cost_tracking:daily:2024-01-15` |

**Location:** `backend/services/cost_tracker.py`

### Idempotency Keys (`batch_event:`)

Used by `NemotronAnalyzer` for event idempotency.

| Pattern                  | Purpose            | TTL    | Example              |
| ------------------------ | ------------------ | ------ | -------------------- |
| `batch_event:{batch_id}` | Event ID for batch | 1 hour | `batch_event:abc123` |

**Location:** `backend/services/nemotron_analyzer.py`

### Pipeline Error Keys (`pipeline:`)

Used for storing recent pipeline errors.

| Pattern           | Purpose            | TTL      | Example           |
| ----------------- | ------------------ | -------- | ----------------- |
| `pipeline:errors` | Recent errors list | 24 hours | `pipeline:errors` |

**Location:** `backend/core/constants.py`

---

## Pub/Sub Channels

WebSocket event broadcasting uses these channels:

| Channel                | Purpose              | Example              |
| ---------------------- | -------------------- | -------------------- |
| `security_events`      | Main event broadcast | Security events      |
| `job:{job_id}:control` | Job control messages | Cancel/abort signals |

---

## Best Practices

### 1. Always Use Constants

Define key prefixes as constants to prevent typos:

```python
# Good
from backend.services.dedupe import DEDUPE_KEY_PREFIX
key = f"{DEDUPE_KEY_PREFIX}{file_hash}"

# Bad - prone to typos
key = f"dedup:{file_hash}"  # typo: "dedup" vs "dedupe"
```

### 2. Use Helper Functions

Use provided helper functions for prefixed keys:

```python
# Good - uses global prefix
from backend.core.constants import get_prefixed_queue_name
queue = get_prefixed_queue_name(DETECTION_QUEUE)

# Good - CacheKeys handles prefixing
from backend.services.cache_service import CacheKeys
key = CacheKeys.cameras_list()
```

### 3. Always Set TTL for Temporary Data

Prevent memory leaks by always setting TTL:

```python
# Good - TTL prevents orphaned keys
await redis.set(key, value, expire=3600)

# Bad - key never expires
await redis.set(key, value)
```

### 4. Document New Key Patterns

When adding new Redis keys, update this document and add constants.

### 5. Use Consistent Separators

Always use colon (`:`) as the key separator:

```python
# Good
key = f"batch:{batch_id}:camera_id"

# Bad - inconsistent separators
key = f"batch-{batch_id}_camera_id"
```

---

## Migration Notes

### Current State

Some key patterns do not yet use the global prefix for backward compatibility:

- `batch:*` - Batch aggregator
- `dedupe:*` - Deduplication
- `job:*` - Job tracking
- `orchestrator:*` - Service orchestration
- `entity_embeddings:*` - Re-ID service
- `camera:*` - Camera debouncing
- `telemetry:*` - Telemetry

### Future Work

Consider migrating these to use the global prefix (`hsi:`) for full multi-instance isolation. This would require a migration strategy to handle existing keys during deployment.

---

## Debugging Tips

### List All Keys

```bash
# List all keys (use sparingly in production)
redis-cli -a "$REDIS_PASSWORD" keys '*'

# List keys by pattern
redis-cli -a "$REDIS_PASSWORD" keys 'batch:*'
redis-cli -a "$REDIS_PASSWORD" keys 'hsi:cache:*'
```

### Check Key Type

```bash
redis-cli -a "$REDIS_PASSWORD" type "batch:abc123:detections"
# Returns: list
```

### Inspect Key Content

```bash
# String/JSON values
redis-cli -a "$REDIS_PASSWORD" get "job:abc123:status"

# Lists
redis-cli -a "$REDIS_PASSWORD" lrange "batch:abc123:detections" 0 -1

# Sorted sets
redis-cli -a "$REDIS_PASSWORD" zrange "jobs:active" 0 -1
```

### Check TTL

```bash
redis-cli -a "$REDIS_PASSWORD" ttl "dedupe:abc123"
# Returns: remaining seconds, -1 (no TTL), or -2 (key doesn't exist)
```

---

## Related Documentation

- [Redis Setup](../operator/redis.md) - Server configuration and authentication
- [Cache Service](backend-patterns.md) - Cache-aside pattern implementation
- [Batch Aggregation](batching-logic.md) - Detection batching details

---

[Back to Developer Hub](README.md)
