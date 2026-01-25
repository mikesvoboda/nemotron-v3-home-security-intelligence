# Structured Logging

![Log Pipeline Overview](../../images/architecture/observability/technical-log-pipeline.png)

> JSON-formatted logging with automatic context propagation, trace correlation, and secure credential handling.

**Key Files:**

- `backend/core/logging.py:1-1232` - Complete logging implementation
- `backend/core/config.py` - Logging configuration settings
- `backend/api/middleware/request_id.py` - Request ID middleware

## Overview

The logging system produces structured JSON logs with automatic enrichment of contextual information. Every log entry includes timestamp, level, component name, and optional fields like request ID, trace ID, span ID, camera ID, and other domain-specific context.

The system uses Python's standard logging library with custom formatters and filters. The `ContextFilter` (`backend/core/logging.py:467-609`) injects context variables from async context managers into every log record. The `CustomJsonFormatter` (`backend/core/logging.py:612-697`) outputs logs as JSON with consistent field ordering.

Sensitive data is protected through URL redaction, credential pattern matching, and log value sanitization to prevent log injection attacks.

## Architecture

```mermaid
graph TD
    subgraph "Log Generation"
        APP[Application Code] --> |logger.info| LOGGER[Python Logger]
    end

    subgraph "Context Enrichment"
        LOGGER --> CF[ContextFilter<br/>logging.py:467-609]
        CF --> |Add trace_id, span_id| CF
        CF --> |Add request_id| CF
        CF --> |Add camera_id, event_id| CF
    end

    subgraph "Formatting"
        CF --> JSON[CustomJsonFormatter<br/>logging.py:612-697]
        CF --> TRACE[TraceContextFormatter<br/>logging.py:426-454]
    end

    subgraph "Output Handlers"
        JSON --> STDOUT[Console Handler<br/>StreamHandler]
        TRACE --> FILE[File Handler<br/>RotatingFileHandler]
        JSON --> DB[Database Handler<br/>logging.py:700-839]
    end

    subgraph "Aggregation"
        STDOUT --> LOKI[Loki]
        FILE --> DISK[Local Disk]
        DB --> PG[(PostgreSQL)]
    end
```

## Log Format

### JSON Log Structure

Every log entry contains these core fields (`backend/core/logging.py:619-697`):

```json
{
  "timestamp": "2024-01-15T10:30:45.123456+00:00",
  "level": "INFO",
  "component": "backend.services.detection_service",
  "message": "Detection completed",
  "hostname": "backend-pod-abc123",
  "container_id": "a1b2c3d4e5f6",
  "app_version": "1.2.3",
  "environment": "production",
  "request_id": "req-550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "corr-abc123",
  "trace_id": "0123456789abcdef0123456789abcdef",
  "span_id": "0123456789abcdef",
  "camera_id": "front_door",
  "detection_count": 3,
  "duration_ms": 245.7
}
```

### Console/File Format

For human-readable output, the `TraceContextFormatter` (`backend/core/logging.py:426-454`) produces:

```
2024-01-15 10:30:45 | INFO     | backend.services.detection | trace_id=abc123... span_id=def456... | Detection completed
```

The format is defined in constants (`backend/core/logging.py:416-423`):

```python
CONSOLE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "trace_id=%(trace_id)s span_id=%(span_id)s | %(message)s"
)
```

## Context Propagation

### Request Context

The `ContextFilter` automatically injects these fields from async context variables:

| Field            | Source                   | Description                         |
| ---------------- | ------------------------ | ----------------------------------- |
| `request_id`     | `_request_id` ContextVar | Unique ID per HTTP request          |
| `correlation_id` | Middleware               | Cross-service correlation           |
| `trace_id`       | OpenTelemetry            | Distributed trace ID (32 hex chars) |
| `span_id`        | OpenTelemetry            | Current span ID (16 hex chars)      |
| `connection_id`  | WebSocket context        | WebSocket connection ID             |
| `task_id`        | Async task context       | Background task ID                  |
| `job_id`         | Scheduler context        | Scheduled job ID                    |

### Structured Log Context Manager

The `log_context` context manager (`backend/core/logging.py:262-316`) adds fields to all logs within its scope:

```python
# From backend/core/logging.py:262-316
@contextmanager
def log_context(**kwargs: Any) -> Generator[None]:
    """Context manager for enriched logging within a scope."""
    current = _log_context.get() or {}
    merged = {**current, **kwargs}
    token = _log_context.set(merged)
    try:
        yield
    finally:
        _log_context.reset(token)
```

Usage example:

```python
from backend.core.logging import log_context, get_logger

logger = get_logger(__name__)

async def process_detection(camera_id: str, image_path: str):
    with log_context(camera_id=camera_id, operation="detect"):
        logger.info("Starting detection")  # Includes camera_id and operation
        result = await detect_objects(image_path)
        logger.info("Detection complete", extra={"detection_count": len(result)})
```

### Trace Context Integration

![Log Context Enrichment](../../images/architecture/observability/technical-log-context.png)

Trace context is extracted from OpenTelemetry automatically (`backend/core/logging.py:214-259`):

```python
# From backend/core/logging.py:214-259
def get_current_trace_context() -> dict[str, str | None]:
    """Get the current OpenTelemetry trace context for log correlation."""
    result: dict[str, str | None] = {"trace_id": None, "span_id": None}
    try:
        span = _get_otel_current_span()
        if span is None:
            return result
        span_context = span.get_span_context()
        if not span_context or not span_context.is_valid:
            return result
        result["trace_id"] = format(span_context.trace_id, "032x")
        result["span_id"] = format(span_context.span_id, "016x")
    except (ImportError, AttributeError, TypeError):
        pass
    return result
```

## Log Levels

![Log Levels Concept](../../images/architecture/observability/concept-log-levels.png)

| Level      | Value | Usage                                    |
| ---------- | ----- | ---------------------------------------- |
| `DEBUG`    | 10    | Detailed diagnostic information          |
| `INFO`     | 20    | Normal operation confirmations           |
| `WARNING`  | 30    | Unexpected but handled situations        |
| `ERROR`    | 40    | Failures that affect specific operations |
| `CRITICAL` | 50    | System-wide failures                     |

Third-party library noise is suppressed (`backend/core/logging.py:904-906`):

```python
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)
```

## Sensitive Data Protection

### URL Redaction

The `redact_url` function (`backend/core/logging.py:318-377`) masks passwords in URLs:

```python
# From backend/core/logging.py:318-377
def redact_url(url: str) -> str:
    """Redact sensitive information from a URL for safe logging."""
    parsed = urlparse(url)
    if not parsed.password:
        return url
    redacted_netloc = f"{parsed.username}:[REDACTED]@{parsed.hostname}"
    # ... reconstruct URL with redacted password
```

Example:

- Input: `postgresql://user:secret@localhost:5432/db` <!-- pragma: allowlist secret -->
- Output: `postgresql://user:[REDACTED]@localhost:5432/db`

### Sensitive Field Detection

Fields are checked against a known list (`backend/core/logging.py:152-168`):

```python
SENSITIVE_FIELD_NAMES = frozenset({
    "password", "secret", "key", "token", "credential",
    "api_key", "api_keys", "admin_api_key", "rtdetr_api_key",
    "nemotron_api_key", "smtp_password", "database_url", "redis_url",
})
```

### Log Injection Prevention

The `sanitize_log_value` function (`backend/core/logging.py:1041-1081`) prevents CWE-117 log injection:

```python
# From backend/core/logging.py:1041-1081
def sanitize_log_value(value: Any) -> str:
    """Sanitize a value for safe inclusion in log messages."""
    str_value = str(value)
    # Remove newlines (log injection), null bytes (truncation)
    sanitized = str_value.replace("\n", " ").replace("\r", " ").replace("\x00", "")
    # Remove control characters
    sanitized = "".join(char if ord(char) >= 32 or char == "\t" else " " for char in sanitized)
    return sanitized
```

### IP Address Masking

For GDPR compliance, IP addresses are partially masked (`backend/core/logging.py:1002-1038`):

```python
# From backend/core/logging.py:1002-1038
def mask_ip(ip: str) -> str:
    """Mask an IP address for safe logging."""
    if ":" in ip:  # IPv6
        parts = ip.split(":")
        return f"{parts[0]}:xxxx:xxxx:xxxx"
    # IPv4
    parts = ip.split(".")
    return f"{parts[0]}.xxx.xxx.xxx"
```

## Handler Configuration

### Console Handler

Configured in `setup_logging` (`backend/core/logging.py:866-871`):

```python
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(log_level)
console_formatter = TraceContextFormatter(CONSOLE_FORMAT)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)
```

### File Handler (Rotating)

Log files rotate based on size (`backend/core/logging.py:874-891`):

```python
file_handler = RotatingFileHandler(
    filename=str(log_path),
    maxBytes=settings.log_file_max_bytes,
    backupCount=settings.log_file_backup_count,
    encoding="utf-8",
)
```

### Database Handler

The `DatabaseHandler` (`backend/core/logging.py:700-839`) writes to PostgreSQL:

```python
# From backend/core/logging.py:782-800
log_entry = Log(
    timestamp=datetime.now(UTC),
    level=record.levelname,
    component=record.name,
    message=self.format(record),
    camera_id=getattr(record, "camera_id", None),
    event_id=getattr(record, "event_id", None),
    request_id=getattr(record, "request_id", None),
    # ... additional fields
)
session.add(log_entry)
session.commit()
```

## Configuration

| Setting                 | Type   | Default                    | Description                     |
| ----------------------- | ------ | -------------------------- | ------------------------------- |
| `LOG_LEVEL`             | `str`  | `"INFO"`                   | Minimum log level to emit       |
| `LOG_FILE_PATH`         | `str`  | `/var/log/hsi/backend.log` | Log file location               |
| `LOG_FILE_MAX_BYTES`    | `int`  | `10485760` (10MB)          | Max size before rotation        |
| `LOG_FILE_BACKUP_COUNT` | `int`  | `5`                        | Number of rotated files to keep |
| `LOG_DB_ENABLED`        | `bool` | `True`                     | Enable database logging         |
| `LOG_DB_MIN_LEVEL`      | `str`  | `"DEBUG"`                  | Minimum level for database      |

## Instance Identification

For horizontal scaling, each log includes instance information cached at startup (`backend/core/logging.py:70-142`):

| Field          | Function             | Source                                     |
| -------------- | -------------------- | ------------------------------------------ |
| `hostname`     | `get_hostname()`     | K8s pod name or system hostname            |
| `container_id` | `get_container_id()` | First 12 chars of container ID from cgroup |
| `app_version`  | `get_app_version()`  | Version from pyproject.toml                |
| `environment`  | Settings             | deployment environment                     |

## Error Logging Helpers

### log_exception_with_context

Structured exception logging (`backend/core/logging.py:1111-1162`):

```python
# From backend/core/logging.py:1111-1162
def log_exception_with_context(
    logger: logging.Logger,
    exception: Exception,
    message: str,
    *,
    include_traceback: bool = True,
    level: int = logging.ERROR,
    **extra_context: Any,
) -> None:
    """Log an exception with structured context for debugging."""
    extra: dict[str, Any] = {
        "error_type": type(exception).__name__,
        "error_message_sanitized": sanitize_error(exception),
        **extra_context,
    }
    logger.log(level, message, extra=extra, exc_info=include_traceback)
```

### log_error

Simplified error logging (`backend/core/logging.py:1165-1232`):

```python
log_error(
    logger,
    "Image processing timed out",
    error=e,
    extra={"camera_id": "front_door", "timeout_ms": 5000},
)
```

## Testing

Test coverage in `backend/tests/unit/core/test_logging.py`.

| Test                                     | Purpose                             |
| ---------------------------------------- | ----------------------------------- |
| `test_context_filter_adds_request_id`    | Verifies request ID injection       |
| `test_context_filter_adds_trace_context` | Verifies trace ID/span ID injection |
| `test_json_formatter_output`             | Validates JSON structure            |
| `test_url_redaction`                     | Confirms credential masking         |
| `test_sanitize_log_value`                | Validates injection prevention      |
| `test_log_context_manager`               | Verifies context propagation        |

## Related Documents

- [Distributed Tracing](./distributed-tracing.md) - Trace ID generation
- [Prometheus Metrics](./prometheus-metrics.md) - Metrics vs logs
- [Grafana Dashboards](./grafana-dashboards.md) - Log visualization in Grafana
