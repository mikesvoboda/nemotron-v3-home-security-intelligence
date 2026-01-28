# Cache Invalidation Reason Constants

> Standardized reasons for cache invalidation operations in the backend.

**Time to read:** ~3 min
**Source file:** `backend/core/constants.py`

---

## Overview

The `CacheInvalidationReason` enum provides standardized constants for cache invalidation operations. Using these constants instead of magic strings ensures consistency across the codebase and prevents typos.

## Usage

```python
from backend.core.constants import CacheInvalidationReason

# In production code
await cache.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED)
await cache.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_DELETED)

# In tests
mock_cache.invalidate_events.assert_called_once_with(
    reason=CacheInvalidationReason.EVENT_UPDATED
)
```

---

## Reason Categories

### Event Lifecycle Operations

| Constant         | Value            | Description                                              |
| ---------------- | ---------------- | -------------------------------------------------------- |
| `EVENT_CREATED`  | `event_created`  | Cache invalidation when a new event is created           |
| `EVENT_UPDATED`  | `event_updated`  | Cache invalidation when an event is modified             |
| `EVENT_DELETED`  | `event_deleted`  | Cache invalidation when an event is deleted              |
| `EVENT_RESTORED` | `event_restored` | Cache invalidation when a soft-deleted event is restored |

### Camera Lifecycle Operations

| Constant          | Value             | Description                                               |
| ----------------- | ----------------- | --------------------------------------------------------- |
| `CAMERA_CREATED`  | `camera_created`  | Cache invalidation when a new camera is added             |
| `CAMERA_UPDATED`  | `camera_updated`  | Cache invalidation when camera settings are modified      |
| `CAMERA_DELETED`  | `camera_deleted`  | Cache invalidation when a camera is removed               |
| `CAMERA_RESTORED` | `camera_restored` | Cache invalidation when a soft-deleted camera is restored |

### Detection Lifecycle Operations

| Constant            | Value               | Description                                                        |
| ------------------- | ------------------- | ------------------------------------------------------------------ |
| `DETECTION_CREATED` | `detection_created` | Cache invalidation when a new detection is recorded                |
| `DETECTION_UPDATED` | `detection_updated` | Cache invalidation when a detection is modified                    |
| `DETECTION_DELETED` | `detection_deleted` | Cache invalidation when a detection is removed                     |
| `DETECTION_CHANGED` | `detection_changed` | Cache invalidation for generic detection changes (bulk operations) |

### Alert Rule Lifecycle Operations

| Constant             | Value                | Description                                         |
| -------------------- | -------------------- | --------------------------------------------------- |
| `ALERT_RULE_CREATED` | `alert_rule_created` | Cache invalidation when a new alert rule is created |
| `ALERT_RULE_UPDATED` | `alert_rule_updated` | Cache invalidation when an alert rule is modified   |
| `ALERT_RULE_DELETED` | `alert_rule_deleted` | Cache invalidation when an alert rule is removed    |

### Alert State Changes

| Constant             | Value                | Description                                      |
| -------------------- | -------------------- | ------------------------------------------------ |
| `ALERT_CREATED`      | `alert_created`      | Cache invalidation when a new alert is triggered |
| `ALERT_ACKNOWLEDGED` | `alert_acknowledged` | Cache invalidation when an alert is acknowledged |

### System Operations

| Constant            | Value               | Description                                                           |
| ------------------- | ------------------- | --------------------------------------------------------------------- |
| `STATUS_CHANGED`    | `status_changed`    | Cache invalidation when system status changes                         |
| `GRACEFUL_SHUTDOWN` | `graceful_shutdown` | Cache invalidation during graceful service shutdown                   |
| `MANUAL`            | `manual`            | Cache invalidation triggered manually (e.g., admin action, debugging) |

### Test-Specific Reasons

| Constant          | Value             | Description                                        |
| ----------------- | ----------------- | -------------------------------------------------- |
| `CONCURRENT_TEST` | `concurrent_test` | Cache invalidation during concurrent cache testing |
| `TEST`            | `test`            | Generic test-related cache invalidation            |

---

## String Representation

The enum inherits from `str`, so it can be used directly in string contexts:

```python
reason = CacheInvalidationReason.EVENT_CREATED
print(reason)  # Output: event_created
print(str(reason))  # Output: event_created
```

---

## Best Practices

1. **Always use enum constants** - Never use raw strings like `"event_created"`
2. **Import from constants** - `from backend.core.constants import CacheInvalidationReason`
3. **Use in tests** - Assert exact enum values for precise test validation
4. **Log with reason** - Include the reason in cache invalidation logs for debugging

---

## Related Documentation

- [Environment Reference](env-reference.md) - Environment variables
- [Redis Data Structures](../../architecture/data-model/redis-data-structures.md) - Redis caching patterns
- [Resilience Patterns](../../architecture/resilience-patterns/README.md) - Cache strategies

---

[Back to Configuration Reference](./)
