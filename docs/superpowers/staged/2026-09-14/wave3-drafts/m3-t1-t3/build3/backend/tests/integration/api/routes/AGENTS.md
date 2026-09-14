# Integration Tests - API Routes

## Purpose

The `backend/tests/integration/api/routes/` directory contains route-specific integration tests that verify cache invalidation and data consistency across API operations.

## Directory Structure

```
backend/tests/integration/api/routes/
├── AGENTS.md                              # This file
└── test_camera_cache_invalidation.py      # Camera cache invalidation tests (19KB)
```

## Test Files (1 total)

### `test_camera_cache_invalidation.py`

Tests for camera cache invalidation and consistency:

| Test Class                        | Coverage                              |
| --------------------------------- | ------------------------------------- |
| `TestCameraCacheInvalidation`     | Cache invalidation on CRUD operations |
| `TestCameraListCacheInvalidation` | List endpoint cache behavior          |
| `TestCacheConcurrency`            | Concurrent update cache consistency   |

**Key Tests:**

- Cache populated on GET request
- Cache invalidated on PUT/PATCH updates
- Cache invalidated on DELETE
- List cache updated when cameras added/removed
- Concurrent updates maintain cache consistency

## Running Tests

```bash
# All route integration tests
uv run pytest backend/tests/integration/api/routes/ -v

# With coverage
uv run pytest backend/tests/integration/api/routes/ -v --cov=backend.api.routes
```

## Related Documentation

- `/backend/tests/integration/api/AGENTS.md` - API integration tests overview
- `/backend/api/routes/cameras.py` - Camera route implementation
- `/backend/services/cache_service.py` - Cache service implementation
