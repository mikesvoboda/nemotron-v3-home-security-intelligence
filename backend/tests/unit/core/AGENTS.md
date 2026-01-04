# Unit Tests - Core Components

## Purpose

The `backend/tests/unit/core/` directory contains unit tests for the core infrastructure components in `backend/core/`. These tests validate configuration, database management, Redis operations, logging, middleware, security, and WebSocket functionality.

## Directory Structure

```
backend/tests/unit/core/
├── AGENTS.md                         # This file
├── __init__.py                       # Package initialization
├── test_auth_middleware.py           # Authentication middleware
├── test_config.py                    # Settings and configuration
├── test_database_init_lock.py        # Database initialization locking
├── test_database_pool.py             # Connection pool management
├── test_database.py                  # Database operations
├── test_database_utils.py            # Database utilities
├── test_dockerfile_config.py         # Docker configuration validation
├── test_health_monitor.py            # Health monitoring service
├── test_json_utils.py                # JSON serialization utilities
├── test_logging.py                   # Structured logging
├── test_logging_sanitization.py      # Log sanitization (PII removal)
├── test_metrics.py                   # Metrics collection
├── test_middleware.py                # Request/response middleware
├── test_mime_types.py                # MIME type detection
├── test_query_optimization.py        # Query optimization utilities
├── test_rate_limit.py                # Rate limiting middleware
├── test_redis.py                     # Redis client operations
├── test_redis_retry.py               # Redis retry logic
├── test_sanitization.py              # Input sanitization
├── test_security_headers.py          # Security header middleware
├── test_tls.py                       # TLS/SSL configuration
├── test_url_validation.py            # URL validation utilities
├── test_websocket_circuit_breaker.py # WebSocket circuit breaker
├── test_websocket.py                 # WebSocket core functionality
├── test_websocket_timeout.py         # WebSocket timeout handling
└── test_websocket_validation.py      # WebSocket message validation
```

## Test Files (28 files)

### Configuration and Settings

| File                        | Tests For                                 |
| --------------------------- | ----------------------------------------- |
| `test_config.py`            | Settings loading, env vars, type coercion |
| `test_dockerfile_config.py` | Docker configuration validation           |

### Database

| File                         | Tests For                                |
| ---------------------------- | ---------------------------------------- |
| `test_database.py`           | Initialization, sessions, ILIKE escaping |
| `test_database_init_lock.py` | Database initialization locking          |
| `test_database_pool.py`      | Connection pool management               |
| `test_database_utils.py`     | Database utility functions               |
| `test_query_optimization.py` | Query optimization utilities             |

### Redis

| File                  | Tests For                    |
| --------------------- | ---------------------------- |
| `test_redis.py`       | Redis client operations      |
| `test_redis_retry.py` | Redis retry and reconnection |

### Logging and Monitoring

| File                           | Tests For                     |
| ------------------------------ | ----------------------------- |
| `test_logging.py`              | Structured logging            |
| `test_logging_sanitization.py` | PII removal from logs         |
| `test_metrics.py`              | Prometheus metrics collection |
| `test_health_monitor.py`       | Health check service          |

### Middleware and Security

| File                       | Tests For                          |
| -------------------------- | ---------------------------------- |
| `test_auth_middleware.py`  | Authentication middleware          |
| `test_middleware.py`       | Request/response processing        |
| `test_rate_limit.py`       | Rate limiting middleware           |
| `test_security_headers.py` | Security headers (CSP, HSTS, etc.) |
| `test_tls.py`              | TLS/SSL configuration              |
| `test_sanitization.py`     | Input sanitization                 |
| `test_url_validation.py`   | URL validation and sanitization    |

### Utilities

| File                 | Tests For                    |
| -------------------- | ---------------------------- |
| `test_json_utils.py` | JSON serialization utilities |
| `test_mime_types.py` | MIME type detection          |

### WebSocket

| File                                | Tests For                    |
| ----------------------------------- | ---------------------------- |
| `test_websocket.py`                 | WebSocket core functionality |
| `test_websocket_circuit_breaker.py` | Circuit breaker pattern      |
| `test_websocket_timeout.py`         | Timeout handling             |
| `test_websocket_validation.py`      | Message validation           |

## Running Tests

```bash
# All core unit tests
uv run pytest backend/tests/unit/core/ -v

# Database tests only
uv run pytest backend/tests/unit/core/test_database*.py -v

# Redis tests only
uv run pytest backend/tests/unit/core/test_redis*.py -v

# WebSocket tests only
uv run pytest backend/tests/unit/core/test_websocket*.py -v

# With coverage
uv run pytest backend/tests/unit/core/ -v --cov=backend/core

# Single test
uv run pytest backend/tests/unit/core/test_config.py::TestSettings -v
```

## Fixtures Used

From `backend/tests/conftest.py`:

| Fixture                | Scope              | Description                                  |
| ---------------------- | ------------------ | -------------------------------------------- |
| `reset_settings_cache` | function (autouse) | Clears settings cache before/after each test |
| `isolated_db`          | function           | Full PostgreSQL instance with schema         |
| `session`              | function           | Transaction-isolated session with rollback   |
| `mock_redis`           | function           | Mock Redis client                            |

**Helper Functions:**

- `unique_id(prefix)` - Generates unique IDs for parallel test isolation

## Test Patterns

### State Isolation Pattern

```python
# Save original state
original_engine = db_module._engine
try:
    db_module._engine = None  # Set test condition
    # ... test assertions ...
finally:
    db_module._engine = original_engine  # Restore
```

### Async Mock Pattern

```python
mock_session = AsyncMock()
mock_session.commit = AsyncMock()
mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
```

### Environment Variable Pattern

```python
def test_config_from_env(clean_env):
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://..."
    settings = get_settings()
    assert settings.database_url == "postgresql+asyncpg://..."
```

## Related Documentation

- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/backend/tests/conftest.py` - Shared fixtures and helpers
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/AGENTS.md` - Test infrastructure overview
