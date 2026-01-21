# Repositories - Agent Guide

## Purpose

This directory contains the Repository pattern implementation for database access abstraction. The repository layer sits between the API routes/services and the SQLAlchemy ORM models, providing:

- **Consistent data access patterns** - Standard CRUD operations with async support
- **Type-safe operations** - Generic base class with full type hints
- **Testability** - Easy to mock for unit testing
- **Separation of concerns** - Database logic isolated from business logic
- **Query encapsulation** - Complex queries encapsulated in repository methods

## Architecture

```
Routes/Services --> Repositories --> SQLAlchemy ORM --> Database
                         |
                    Base[T] class (generic)
                         |
         +---------------+---------------+
         |               |               |
   CameraRepo      EventRepo      DetectionRepo
```

## Files Overview

```
backend/repositories/
|-- __init__.py               # Module exports
|-- AGENTS.md                 # This documentation
|-- alert_repository.py       # Alert and AlertRule repository
|-- base.py                   # Generic Repository[T] base class
|-- camera_repository.py      # Camera entity repository
|-- detection_repository.py   # Detection entity repository
|-- entity_repository.py      # Entity re-identification repository (NEM-2450, NEM-2494)
|-- event_repository.py       # Event entity repository
|-- summary_repository.py     # Summary entity repository
|-- zone_repository.py        # Zone entity repository
```

## `alert_repository.py` - Alert Repository

Extends base with alert and alert rule-specific methods:

| Method                      | Description                              |
| --------------------------- | ---------------------------------------- |
| `get_by_event_id(event_id)` | Get alerts for a specific event          |
| `get_by_rule_id(rule_id)`   | Get alerts triggered by a specific rule  |
| `get_by_status(status)`     | Get alerts by status (pending/delivered) |
| `get_by_severity(severity)` | Get alerts by severity level             |
| `get_pending(limit)`        | Get pending alerts                       |
| `get_recent(limit)`         | Get most recent alerts                   |
| `acknowledge(id)`           | Mark alert as acknowledged               |
| `dismiss(id)`               | Mark alert as dismissed                  |
| `get_by_dedup_key(key)`     | Find alert by deduplication key          |
| `count_by_status(status)`   | Count alerts by status                   |

**AlertRuleRepository** - Extends base with alert rule methods:

| Method                        | Description                     |
| ----------------------------- | ------------------------------- |
| `get_enabled_rules()`         | Get all enabled alert rules     |
| `get_by_camera_id(camera_id)` | Get rules for a specific camera |
| `get_by_severity(severity)`   | Get rules by minimum severity   |

## `base.py` - Generic Repository Base Class

The base class provides common CRUD operations for all repositories:

```python
from backend.repositories import Repository
from backend.models import Camera

class CameraRepository(Repository[Camera]):
    model_class = Camera
```

**Base Methods:**

| Method           | Description                       |
| ---------------- | --------------------------------- |
| `get_by_id(id)`  | Retrieve entity by primary key    |
| `get_all()`      | Retrieve all entities             |
| `get_many(ids)`  | Retrieve multiple entities by IDs |
| `create(entity)` | Create new entity                 |
| `update(entity)` | Update existing entity            |
| `delete(entity)` | Delete entity                     |
| `exists(id)`     | Check if entity exists            |
| `count()`        | Count total entities              |

## `camera_repository.py` - Camera Repository

Extends base with camera-specific methods:

| Method                     | Description                          |
| -------------------------- | ------------------------------------ |
| `get_by_folder_path(path)` | Find camera by upload folder path    |
| `get_by_name(name)`        | Find camera by display name          |
| `get_online_cameras()`     | Get all cameras with status="online" |
| `update_last_seen(id)`     | Update last_seen_at timestamp        |
| `set_status(id, status)`   | Update camera status                 |

## `event_repository.py` - Event Repository

Extends base with event-specific methods:

| Method                          | Description                       |
| ------------------------------- | --------------------------------- |
| `get_by_camera_id(camera_id)`   | Get events for a specific camera  |
| `get_by_batch_id(batch_id)`     | Get events by batch processing ID |
| `get_unreviewed()`              | Get events not yet reviewed       |
| `get_by_risk_level(level)`      | Filter events by risk level       |
| `get_in_date_range(start, end)` | Get events within date range      |
| `get_recent(limit)`             | Get most recent events            |
| `mark_reviewed(id, notes)`      | Mark event as reviewed with notes |

## `detection_repository.py` - Detection Repository

Extends base with detection-specific methods:

| Method                            | Description                           |
| --------------------------------- | ------------------------------------- |
| `get_by_camera_id(camera_id)`     | Get detections for a specific camera  |
| `get_by_object_type(object_type)` | Filter by detected object type        |
| `get_in_date_range(start, end)`   | Get detections within date range      |
| `get_high_confidence(threshold)`  | Get detections above confidence level |
| `get_for_event(event_id)`         | Get detections linked to an event     |
| `get_recent(limit)`               | Get most recent detections            |

## `summary_repository.py` - Summary Repository

Extends base with summary-specific methods:

| Method                             | Description                          |
| ---------------------------------- | ------------------------------------ |
| `get_latest_by_type(summary_type)` | Get latest summary of specified type |
| `get_latest_all()`                 | Get both latest hourly and daily     |
| `cleanup_old_summaries(days)`      | Delete summaries older than N days   |
| `get_by_time_range(start, end)`    | Get summaries in a time range        |

## `zone_repository.py` - Zone Repository

Extends base with zone-specific methods:

| Method                              | Description                           |
| ----------------------------------- | ------------------------------------- |
| `get_by_camera_id(camera_id)`       | Get all zones for a camera            |
| `get_by_name(camera_id, name)`      | Find zone by camera and name          |
| `get_enabled_zones(camera_id)`      | Get only enabled zones for a camera   |
| `get_by_type(camera_id, zone_type)` | Get zones by type (entry_point, etc.) |

## `entity_repository.py` - Entity Repository (NEM-2450, NEM-2494, NEM-2671)

Extends base with entity-specific methods for re-identification tracking:

| Method                                     | Description                                      |
| ------------------------------------------ | ------------------------------------------------ |
| `get_by_type(entity_type)`                 | Get entities by type (person, vehicle, etc.)     |
| `get_recent(limit)`                        | Get most recently seen entities                  |
| `get_in_date_range(start, end)`            | Get entities seen within date range              |
| `update_last_seen(id, timestamp)`          | Update last_seen_at and increment count          |
| `get_by_primary_detection_id(id)`          | Find entity by primary detection                 |
| `get_type_counts()`                        | Get entity counts grouped by type                |
| `get_total_detection_count()`              | Sum of detection_count across all entities       |
| `list_by_type_paginated(...)`              | Paginated list by entity type                    |
| `search_by_metadata(key, value)`           | Search entities by JSONB metadata field          |
| `get_with_high_detection_count(min_count)` | Get frequently detected entities                 |
| `get_first_seen_in_range(start, end)`      | Get entities first seen in date range            |
| `get_by_embedding_model(model)`            | Get entities with specific embedding model       |
| `list(...)`                                | Filter by type, camera_id, since with pagination |
| `find_by_embedding(...)`                   | Find similar entities by cosine similarity       |
| `increment_detection_count(id)`            | Increment count and update timestamp             |
| `get_or_create_for_detection(...)`         | Match or create entity for detection             |
| `get_detections_for_entity(id)`            | Get detections linked to entity                  |
| `get_camera_counts()`                      | Entity counts grouped by camera                  |
| `get_repeat_visitor_count()`               | Count entities seen more than once               |
| `count()`                                  | Total entity count                               |
| `get_repeat_visitors(...)`                 | Get entities with min detection count            |
| `get_stats(entity_type)`                   | Comprehensive statistics by type                 |
| `list_filtered(...)`                       | List with since/until time range filtering       |
| `update_trust_status(id, status, notes)`   | Update trust classification (NEM-2671)           |
| `list_by_trust_status(status, ...)`        | List entities by trust classification            |

**Embedding Similarity:**

The repository includes application-level cosine similarity for matching entities by embedding vectors stored in JSONB. For high-performance vector search at scale, consider using the pgvector extension.

## Usage Patterns

### In API Routes (Dependency Injection)

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core import get_db
from backend.repositories import CameraRepository

@router.get("/cameras/{camera_id}")
async def get_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = CameraRepository(db)
    camera = await repo.get_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera
```

### In Services (Context Manager)

```python
from backend.core import get_session
from backend.repositories import EventRepository

async def process_events():
    async with get_session() as session:
        repo = EventRepository(session)
        unreviewed = await repo.get_unreviewed()
        for event in unreviewed:
            # Process event
            ...
```

### Transaction Handling

Repositories work within the session's transaction context:

```python
async with get_session() as session:
    camera_repo = CameraRepository(session)
    event_repo = EventRepository(session)

    # Both operations in same transaction
    camera = await camera_repo.get_by_id("front_door")
    events = await event_repo.get_by_camera_id(camera.id)

    # Session auto-commits on context exit
```

## Testing

Repositories have comprehensive unit tests in `/backend/tests/unit/repositories/`:

```bash
# Run repository tests
uv run pytest backend/tests/unit/repositories/ -v

# With coverage
uv run pytest backend/tests/unit/repositories/ --cov=backend.repositories
```

**Test Patterns:**

- Use `isolated_db` fixture for database access
- Use `session` fixture for transaction rollback isolation
- Test both happy path and error cases
- Mock external dependencies (Redis, AI services)

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/core/AGENTS.md` - Core infrastructure (database, sessions)
- `/backend/tests/AGENTS.md` - Test infrastructure documentation
