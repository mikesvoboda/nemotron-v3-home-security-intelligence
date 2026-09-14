# Integration Tests - Services

## Purpose

The `backend/tests/integration/services/` directory contains integration tests for service classes that require real database connections and complex multi-component interactions.

## Directory Structure

```
backend/tests/integration/services/
├── AGENTS.md                                  # This file
├── __init__.py                                # Package initialization
├── test_cache_behavior.py                     # Cache service integration tests (18KB)
├── test_calibration_severity_integration.py   # Calibration severity tests (17KB)
└── test_model_loaders.py                      # Model loader integration tests (23KB)
```

## Test Files (3 total)

| File                                       | Service Tested       | Key Coverage                       |
| ------------------------------------------ | -------------------- | ---------------------------------- |
| `test_cache_behavior.py`                   | CacheService         | Cache TTL, invalidation, coherence |
| `test_calibration_severity_integration.py` | CalibrationService   | Severity calibration workflow      |
| `test_model_loaders.py`                    | Model loader classes | Model loading, warmup, health      |

## Running Tests

```bash
# All service integration tests
uv run pytest backend/tests/integration/services/ -v

# Specific test file
uv run pytest backend/tests/integration/services/test_cache_behavior.py -v

# With coverage
uv run pytest backend/tests/integration/services/ -v --cov=backend.services
```

## Test Categories

### Cache Behavior Tests (`test_cache_behavior.py`)

Tests for cache service integration:

| Test Class              | Coverage                         |
| ----------------------- | -------------------------------- |
| `TestCacheTTL`          | Time-to-live expiration behavior |
| `TestCacheInvalidation` | Explicit cache invalidation      |
| `TestCacheCoherence`    | Multi-key consistency            |
| `TestCacheConcurrency`  | Concurrent access patterns       |

### Calibration Severity Tests (`test_calibration_severity_integration.py`)

Tests for user severity calibration:

| Test Class                | Coverage                         |
| ------------------------- | -------------------------------- |
| `TestCalibrationWorkflow` | End-to-end calibration flow      |
| `TestSeverityMapping`     | Risk score to severity mapping   |
| `TestUserPreferences`     | Per-user calibration persistence |

### Model Loader Tests (`test_model_loaders.py`)

Tests for AI model loading:

| Test Class         | Coverage                          |
| ------------------ | --------------------------------- |
| `TestModelLoading` | Model file loading and validation |
| `TestModelWarmup`  | Warm-up inference for cold start  |
| `TestModelHealth`  | Health check integration          |

## Key Test Patterns

### Cache Integration Testing

```python
@pytest.mark.asyncio
async def test_cache_ttl_expiration(cache_service, mock_redis):
    # Set with TTL
    await cache_service.set("key", "value", ttl=1)

    # Immediate read succeeds
    assert await cache_service.get("key") == "value"

    # After TTL expires
    await asyncio.sleep(1.1)
    assert await cache_service.get("key") is None
```

### Multi-Component Integration

```python
@pytest.mark.asyncio
async def test_calibration_affects_severity(session, calibration_service):
    # Create calibration
    await calibration_service.save_calibration(
        user_id="user1",
        sensitivity=0.8  # High sensitivity
    )

    # Verify severity mapping changed
    severity = await calibration_service.map_risk_to_severity(
        risk_score=50,
        user_id="user1"
    )
    assert severity == "high"  # Would be "medium" at default sensitivity
```

## Related Documentation

- `/backend/services/AGENTS.md` - Service implementations
- `/backend/tests/integration/AGENTS.md` - Integration tests overview
- `/backend/tests/unit/services/AGENTS.md` - Unit tests for services
