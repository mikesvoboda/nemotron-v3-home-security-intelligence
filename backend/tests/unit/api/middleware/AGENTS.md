# API Middleware Unit Tests

## Purpose

Unit tests for API middleware components, specifically the RequestTimingMiddleware that tracks API latency and adds performance headers to responses.

## Directory Structure

```
backend/tests/unit/api/middleware/
├── AGENTS.md                 # This file
├── __init__.py               # Package initialization
└── test_request_timing.py    # Request timing middleware tests (17KB)
```

## Running Tests

```bash
# All API middleware tests
pytest backend/tests/unit/api/middleware/ -v

# Specific test file
pytest backend/tests/unit/api/middleware/test_request_timing.py -v

# With coverage
pytest backend/tests/unit/api/middleware/ -v --cov=backend.api.middleware --cov-report=html
```

## Test Files (1 total)

### `test_request_timing.py`

Tests for RequestTimingMiddleware (NEM-1469):

**Test Class:**

| Test Class                    | Coverage                            |
| ----------------------------- | ----------------------------------- |
| `TestRequestTimingMiddleware` | Request timing tracking and logging |

**Key Test Coverage:**

- X-Response-Time header addition to all responses
- Response time measurement accuracy
- Slow request threshold logging
- Different HTTP methods (GET, POST, PUT, DELETE)
- Async endpoint timing
- Error response timing
- Logging integration
- Configurable slow request threshold

**Test Endpoints:**

- `/test` - Fast endpoint (< 10ms)
- `/slow` - Slow endpoint (100ms delay)
- `/create` - POST endpoint
- `/error` - Error-raising endpoint

**Test Patterns:**

```python
@pytest.fixture
def app_with_timing_middleware(self):
    """Create a test FastAPI app with RequestTimingMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestTimingMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "ok"}

    return app

def test_response_time_header_added(app_with_timing_middleware):
    """Test that X-Response-Time header is added."""
    client = TestClient(app_with_timing_middleware)
    response = client.get("/test")

    assert "X-Response-Time" in response.headers
    response_time = float(response.headers["X-Response-Time"].rstrip("ms"))
    assert response_time > 0
```

**Logging Tests:**

- Slow requests logged at WARNING level
- Fast requests not logged
- Request method and path included in logs
- Response status code included in logs

## Related Documentation

- `/backend/api/middleware/AGENTS.md` - Middleware implementations
- `/backend/api/middleware/request_timing.py` - RequestTimingMiddleware implementation
- `/backend/tests/unit/api/AGENTS.md` - API unit tests overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
