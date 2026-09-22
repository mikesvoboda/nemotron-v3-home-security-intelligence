# API Middleware Unit Tests

## Purpose

Unit tests for the `backend/api/middleware/` components: request/response processing, authentication, rate limiting, idempotency, error handling, and the unified observability middleware that replaced the former timing and request-logging middleware (NEM-5558).

## Directory Structure

```
backend/tests/unit/api/middleware/
├── AGENTS.md                      # This file
├── __init__.py                    # Package initialization
├── test_accept_header.py          # Accept-header negotiation (30KB)
├── test_auth.py                   # API-key auth security logging (15KB)
├── test_baggage_middleware.py     # W3C Baggage propagation (15KB)
├── test_body_limit.py             # Body size limits (15KB)
├── test_content_negotiation.py    # Content negotiation (14KB)
├── test_content_type_validator.py # Content-Type validation (13KB)
├── test_correlation_propagation.py# Correlation ID propagation (23KB)
├── test_deprecation.py            # RFC 8594 deprecation headers (28KB)
├── test_deprecation_logger.py     # Deprecated endpoint logging (17KB)
├── test_error_handler.py          # Error response formatting (31KB)
├── test_etag.py                   # ETag / conditional GET (12KB)
├── test_exception_handler.py      # Exception data minimization (31KB)
├── test_file_validator.py         # Upload magic numbers (25KB)
├── test_gzip.py                   # GZip middleware config (10KB)
├── test_idempotency.py            # Idempotency-Key support (66KB)
├── test_observability.py          # Request-log formatting (3KB)
├── test_prometheus.py             # Prometheus HTTP metrics (23KB)
├── test_pure_asgi_middleware.py   # Pure ASGI pattern (10KB)
├── test_rate_limit.py             # Rate limiting (52KB)
├── test_request_recorder.py       # Request recording (38KB)
└── test_websocket_auth.py         # WebSocket token auth (11KB)
```

## Running Tests

```bash
# All API middleware tests
pytest backend/tests/unit/api/middleware/ -v

# Specific test file
pytest backend/tests/unit/api/middleware/test_observability.py -v

# With coverage
pytest backend/tests/unit/api/middleware/ -v --cov=backend.api.middleware --cov-report=html
```

## Test Files (21 total)

| Test File                         | Target Module               | Covers                                                |
| --------------------------------- | --------------------------- | ----------------------------------------------------- |
| `test_accept_header.py`           | `accept_header.py`          | Accept-header content negotiation (NEM-2086)          |
| `test_auth.py`                    | `auth.py`                   | API-key auth failure security logging                 |
| `test_baggage_middleware.py`      | `baggage.py`                | W3C Baggage extraction and context (NEM-3796)         |
| `test_body_limit.py`              | `body_limit.py`             | Request body size enforcement (NEM-1614)              |
| `test_content_negotiation.py`     | `content_negotiation.py`    | Response content negotiation (NEM-2066)               |
| `test_content_type_validator.py`  | `content_type_validator.py` | Content-Type validation for request bodies (NEM-1617) |
| `test_correlation_propagation.py` | `correlation.py`            | Correlation-ID propagation to AI clients (NEM-1729)   |
| `test_deprecation.py`             | `deprecation.py`            | RFC 8594 Deprecation/Sunset headers                   |
| `test_deprecation_logger.py`      | `deprecation_logger.py`     | Deprecated-endpoint call metrics (NEM-2090)           |
| `test_error_handler.py`           | `error_handler.py`          | Error response formatting and handlers                |
| `test_etag.py`                    | `etag.py`                   | ETag generation and conditional GETs (NEM-3743)       |
| `test_exception_handler.py`       | `exception_handler.py`      | Error response data minimization (NEM-1649)           |
| `test_file_validator.py`          | `file_validator.py`         | Upload magic-number validation (NEM-1618)             |
| `test_gzip.py`                    | GZip wiring in `main.py`    | Compression config and data integrity (NEM-3741)      |
| `test_idempotency.py`             | `idempotency.py`            | Idempotency-Key replay protection (NEM-2018)          |
| `test_observability.py`           | `observability.py`          | Structured request-log formatting (NEM-5558)          |
| `test_prometheus.py`              | `prometheus.py`             | HTTP request duration metrics (NEM-4149)              |
| `test_pure_asgi_middleware.py`    | `security_headers.py`       | Pure-ASGI `__call__` pattern (NEM-3348)               |
| `test_rate_limit.py`              | `rate_limit.py`             | Redis sliding-window tiers, proxy trust               |
| `test_request_recorder.py`        | `request_recorder.py`       | Request recording for replay debugging (NEM-1646)     |
| `test_websocket_auth.py`          | `websocket_auth.py`         | WebSocket token authentication (NEM-1650)             |

## Timing and Logging Coverage (`test_observability.py`)

`RequestTimingMiddleware` and `RequestLoggingMiddleware` were removed under NEM-5558 and their modules and test files deleted. Their remaining unit coverage lives here, re-homed from the former `test_request_logging.py`.

**Test Class:**

| Test Class                 | Coverage                                                    |
| -------------------------- | ----------------------------------------------------------- |
| `TestRequestLogFormatting` | Structured request-log dict used by ObservabilityMiddleware |

**Key Test Coverage:**

- `format_request_log()` output is JSON-serializable for log aggregators
- All aggregation fields present: `method`, `path`, `status_code`, `duration_ms`, `request_id`, `correlation_id`, `trace_id`, `span_id`
- Request path passthrough (masking is handled elsewhere in the pipeline)

**Test Pattern:**

```python
def test_log_output_is_json_parseable(self):
    """Test that log output can be parsed as JSON."""
    from backend.api.middleware.observability import format_request_log

    log_data = format_request_log(
        method="GET", path="/api/test", status_code=200, duration_ms=45.5,
        client_ip="192.168.1.1", request_id="req-123",
    )
    assert isinstance(log_data, dict)
    assert json.loads(json.dumps(log_data))["status_code"] == 200
```

The behavioral side of the merged middleware — `X-Response-Time` header emission, slow-request logging, and chain-order assertions — is exercised at `/backend/tests/integration/test_middleware_chain.py` and `/backend/tests/integration/test_trace_propagation.py`; the `http_request_duration_seconds` histogram itself is covered by `test_prometheus.py`.

## Related Documentation

- `/backend/api/middleware/AGENTS.md` - Middleware implementations
- `/backend/api/middleware/observability.py` - ObservabilityMiddleware implementation
- `/docs/architecture/middleware/README.md` - Registration order in `backend/main.py`
- `/backend/tests/unit/api/AGENTS.md` - API unit tests overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
