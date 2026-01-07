# Middleware Unit Tests

## Purpose

Unit tests for core middleware components, specifically the correlation ID middleware that tracks requests across distributed systems and logging contexts.

## Directory Structure

```
backend/tests/unit/middleware/
├── AGENTS.md                 # This file
├── __init__.py               # Package initialization
└── test_correlation_id.py    # Correlation ID middleware tests (7KB)
```

## Running Tests

```bash
# All middleware tests
pytest backend/tests/unit/middleware/ -v

# Specific test file
pytest backend/tests/unit/middleware/test_correlation_id.py -v

# With coverage
pytest backend/tests/unit/middleware/ -v --cov=backend.core.logging --cov-report=html
```

## Test Files (1 total)

### `test_correlation_id.py`

Tests for correlation ID middleware and propagation (NEM-1472):

**Test Class:**

| Test Class                    | Coverage                                  |
| ----------------------------- | ----------------------------------------- |
| `TestCorrelationIdMiddleware` | Correlation ID generation and propagation |

**Key Test Coverage:**

- Correlation ID generation when not provided in request
- Preservation of existing correlation ID from X-Correlation-ID header
- UUID format validation
- Response header inclusion
- Context variable storage for thread-safe access
- Propagation to outgoing HTTP requests
- Async request handling
- Integration with logging system

**Test Patterns:**

```python
@pytest.mark.asyncio
async def test_middleware_generates_correlation_id_when_not_provided(self) -> None:
    """Verify middleware generates a correlation ID when not in headers."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    # Response should have a correlation ID header
    assert "X-Correlation-ID" in response.headers

    # Should be a valid UUID format
    correlation_id = response.headers["X-Correlation-ID"]
    assert len(correlation_id) > 0
    uuid.UUID(correlation_id)  # Raises ValueError if invalid

@pytest.mark.asyncio
async def test_middleware_preserves_existing_correlation_id(self) -> None:
    """Verify middleware preserves correlation ID from request headers."""
    test_correlation_id = "test-correlation-123"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/",
            headers={"X-Correlation-ID": test_correlation_id},
        )

    # Response should echo back the same correlation ID
    assert response.headers["X-Correlation-ID"] == test_correlation_id
```

**Context Variable Tests:**

- `set_request_id()` stores correlation ID in context variable
- Context variable is accessible throughout request lifecycle
- Context variables are isolated between concurrent requests
- Context variables are cleared after request completes

**Integration with Logging:**

The correlation ID middleware integrates with the logging system to:

- Add correlation ID to all log messages
- Enable request tracing across services
- Support distributed tracing systems
- Provide request context in error logs

## Use Cases

### Request Tracing

```
Client Request (X-Correlation-ID: abc-123)
  -> API Gateway (preserves abc-123)
    -> Backend Service (preserves abc-123)
      -> Database Query (logs with abc-123)
      -> External API Call (sends abc-123)
```

### Log Correlation

```
[2024-01-07 10:15:30] [abc-123] INFO: Request received
[2024-01-07 10:15:31] [abc-123] INFO: Database query executed
[2024-01-07 10:15:32] [abc-123] ERROR: External API timeout
[2024-01-07 10:15:33] [abc-123] INFO: Response sent (status: 500)
```

## Related Documentation

- `/backend/core/logging.py` - Logging configuration and correlation ID setup
- `/backend/api/middleware/AGENTS.md` - Middleware implementations
- `/backend/tests/unit/AGENTS.md` - Unit tests overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
