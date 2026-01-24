# Backend Core Infrastructure Guide

## Purpose

The `backend/core/` directory contains the foundational infrastructure components for the home security intelligence system:

- **Configuration management** - Environment-based settings with Pydantic validation
- **Database layer** - SQLAlchemy 2.0 async engine with PostgreSQL and session management
- **Redis client** - Async Redis wrapper for queues, pub/sub, and caching with backpressure
- **Logging infrastructure** - Centralized structured logging with console, file, and database handlers
- **Prometheus metrics** - Observability metrics for pipeline monitoring with latency tracking
- **TLS/SSL** - Certificate management and HTTPS configuration
- **MIME type utilities** - Media file type detection and normalization
- **Async utilities** - Non-blocking I/O wrappers for blocking operations
- **Resilience patterns** - Circuit breakers, retry logic, and error handling
- **Validation & sanitization** - Input validation, SSRF protection, and security utilities

These components are designed as singletons and provide dependency injection patterns for FastAPI routes and services.

## Files Overview

```
backend/core/
├── __init__.py                   # Public API exports (comprehensive re-exports)
├── async_context.py              # Async context propagation utilities (NEM-1640)
├── async_utils.py                # Non-blocking I/O wrappers (sleep, subprocess, file I/O)
├── circuit_breaker.py            # Shared circuit breaker for AI service resilience
├── config.py                     # Pydantic Settings configuration
├── config_validation.py          # Configuration validation and startup summary (NEM-2026)
├── constants.py                  # Application-wide constants (queue names, DLQ names)
├── container.py                  # Dependency injection container (NEM-1636)
├── database.py                   # SQLAlchemy async database layer
├── dependencies.py               # FastAPI dependencies using DI container (NEM-1636)
├── docker_client.py              # Async Docker/Podman client wrapper
├── error_context.py              # Structured error context for enhanced logging
├── exceptions.py                 # Custom exception hierarchy
├── json_utils.py                 # LLM JSON response parsing utilities
├── logging.py                    # Centralized logging configuration
├── metrics.py                    # Prometheus metrics definitions
├── mime_types.py                 # MIME type utilities for media files
├── profiling.py                  # cProfile performance profiling utilities (NEM-1644)
├── protocols.py                  # Protocol definitions for service interfaces
├── query_explain.py              # EXPLAIN ANALYZE logging for slow queries
├── redis.py                      # Redis async client with backpressure
├── retry.py                      # Retry decorators with exponential backoff
├── sanitization.py               # Input sanitization (command injection, SSRF)
├── telemetry.py                  # OpenTelemetry distributed tracing (NEM-1629)
├── time_utils.py                 # UTC datetime utilities
├── tls.py                        # TLS/SSL certificate management
├── url_validation.py             # SSRF-safe URL validation for webhooks
├── websocket_circuit_breaker.py  # Circuit breaker for WebSocket connections
├── websocket/                    # WebSocket event types and subscription management
│   ├── __init__.py               # Package exports
│   ├── event_schemas.py          # WebSocket event payload schemas
│   ├── event_types.py            # WebSocket event type enums
│   └── subscription_manager.py   # Channel subscription management
├── middleware/                   # Reserved for core middleware (currently empty)
├── README.md                     # General documentation
└── README_REDIS.md               # Detailed Redis documentation
```

## `__init__.py` - Public Exports

The `__init__.py` file provides a clean public API for the core module:

**Exported from config.py:**

- `Settings` - Pydantic settings class
- `get_settings()` - Get cached settings instance

**Exported from config_validation.py (NEM-2026):**

- `ConfigValidationResult` - Result dataclass containing validation status and items
- `ValidationItem` - Individual validation item with name, status, and message
- `validate_config()` - Validate application settings and return structured result
- `log_config_summary()` - Log formatted validation summary at startup

**Exported from database.py:**

- `Base` - SQLAlchemy declarative base
- `init_db()` - Initialize database engine and create tables
- `close_db()` - Cleanup database connections
- `get_db()` - FastAPI dependency for database sessions
- `get_session()` - Context manager for manual session usage
- `get_engine()` - Access global async engine
- `get_session_factory()` - Access session factory
- `escape_ilike_pattern()` - Escape special characters for ILIKE queries
- `get_pool_status()` - Get connection pool status metrics

**Exported from json_utils.py:**

- `extract_json_from_llm_response()` - Parse JSON from LLM output with error handling
- `extract_json_field()` - Extract specific field from JSON in LLM response

**Exported from redis.py:**

- `RedisClient` - Redis client wrapper class
- `QueueAddResult` - Result enum for queue operations (SUCCESS, REJECTED, SENT_TO_DLQ)
- `init_redis()` - Initialize Redis connection
- `close_redis()` - Cleanup Redis connection
- `get_redis()` - FastAPI dependency for Redis client
- `get_redis_optional()` - FastAPI dependency returning None if unavailable
- `get_redis_client_sync()` - Synchronous Redis client for non-async contexts

**Exported from logging.py:**

- `get_logger()` - Get a configured logger instance
- `get_request_id()` - Get current request ID from context
- `set_request_id()` - Set request ID in context
- `setup_logging()` - Initialize application-wide logging
- `sanitize_error()` - Sanitize error messages for logging
- `redact_url()` - Redact credentials from URLs for safe logging
- `redact_sensitive_value()` - Redact sensitive values in log output
- `log_exception_with_context()` - Log exceptions with structured context
- `SENSITIVE_FIELD_NAMES` - Set of field names to redact

**Exported from metrics.py:**

- `get_metrics_response()` - Generate Prometheus metrics response
- `observe_stage_duration()` - Record pipeline stage duration
- `observe_ai_request_duration()` - Record AI service request duration
- `record_detection_processed()` - Increment detection counter
- `record_event_created()` - Increment event counter
- `record_pipeline_error()` - Increment error counter
- `set_queue_depth()` - Update queue depth gauge

**Exported from mime_types.py:**

- `get_mime_type()` - Get MIME type from file path
- `get_mime_type_with_default()` - Get MIME type with fallback
- `is_image_mime_type()` / `is_video_mime_type()` - Type checking
- `is_supported_mime_type()` - Check if MIME type is supported (image or video)
- `normalize_file_type()` - Normalize extension or MIME type
- `EXTENSION_TO_MIME` - Extension to MIME type mapping dict
- `DEFAULT_IMAGE_MIME` / `DEFAULT_VIDEO_MIME` - Default MIME type constants

**Exported from tls.py:**

- `TLSConfig` / `TLSMode` - Configuration dataclass and mode enum
- `TLSError`, `TLSConfigurationError`, `CertificateNotFoundError`, `CertificateValidationError` - Exception hierarchy
- `create_ssl_context()` - Create SSL context for server
- `generate_self_signed_cert()` / `generate_self_signed_certificate()` - Generate self-signed certificates
- `get_tls_config()` / `is_tls_enabled()` - Configuration helpers
- `validate_certificate()` / `validate_certificate_files()` / `get_cert_info()` - Certificate inspection
- `load_certificate_paths()` - Load cert/key paths from settings

**Exported from query_explain.py:**

- `QueryExplainLogger` - Logger class for EXPLAIN ANALYZE
- `setup_explain_logging()` - Configure slow query logging

**Usage:**

```python
from backend.core import get_settings, init_db, get_redis, get_logger, setup_logging
from backend.core import TLSConfig, TLSMode, create_ssl_context
from backend.core import get_mime_type, is_video_mime_type
from backend.core import extract_json_from_llm_response, escape_ilike_pattern
from backend.core import setup_explain_logging, QueryExplainLogger
```

## `async_utils.py` - Async Utilities

### Purpose

Provides async wrappers for common blocking operations that would otherwise block the event loop:

- `async_sleep()` - Non-blocking replacement for time.sleep
- `async_open_image()` - Non-blocking PIL Image.open
- `async_subprocess_run()` - Non-blocking subprocess.run
- `AsyncTaskGroup` - Structured concurrency with Python 3.11+ TaskGroup
- `bounded_gather()` - asyncio.gather with concurrency limits
- `async_read_bytes()`/`async_read_text()` - Non-blocking file reading
- `async_write_bytes()`/`async_write_text()` - Non-blocking file writing

### Key Functions

**`async_sleep(seconds: float)`** - Non-blocking sleep:

```python
# Instead of: time.sleep(1.0)
await async_sleep(1.0)
```

**`async_open_image(path: Path | str)`** - Non-blocking image loading:

```python
# Instead of: img = Image.open(path)
img = await async_open_image(path)
```

**`async_subprocess_run(args, **kwargs)`\*\* - Non-blocking subprocess:

```python
# Instead of: result = subprocess.run([...])
result = await async_subprocess_run(["ffmpeg", "-i", "video.mp4"])
```

**`AsyncTaskGroup`** - Structured concurrency:

```python
async with AsyncTaskGroup() as tg:
    tg.create_task(operation_a())
    tg.create_task(operation_b())
# Automatically waits for all tasks, cancels on error
```

**`bounded_gather(coros, limit=10)`** - Concurrent execution with limits:

```python
results = await bounded_gather(
    [operation(i) for i in range(100)],
    limit=10,  # Max 10 concurrent operations
)
```

**File I/O:**

```python
# Non-blocking file operations
data = await async_read_bytes(Path("file.bin"))
text = await async_read_text(Path("file.txt"))
await async_write_bytes(Path("output.bin"), data)
await async_write_text(Path("output.txt"), text)
```

### Usage Notes

- All blocking operations run in thread pool via `asyncio.to_thread()`
- Prevents event loop blocking in async web frameworks
- Essential for image processing, file I/O, and subprocess calls

## `circuit_breaker.py` - Circuit Breaker Pattern

### Purpose

Provides a reusable `CircuitBreaker` class for protecting AI service calls. Prevents cascading failures by temporarily stopping requests to failing services.

### States

- **CLOSED** - Normal operation, requests proceed
- **OPEN** - Too many failures, requests blocked for recovery
- **HALF_OPEN** - Testing recovery, limited requests allowed

### Key Class: `CircuitBreaker`

**Initialization:**

```python
from backend.core.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    name="florence",
    failure_threshold=5,
    recovery_timeout=60,
    half_open_max_calls=3
)
```

**Methods:**

- `check_and_raise()` - Raises `CircuitBreakerOpenError` if open
- `record_success()` - Record successful call
- `record_failure()` - Record failed call
- `protected_call(func)` - Wrapper for automatic tracking
- Context manager support for scoped protection

**Usage Patterns:**

```python
# Method 1: Manual check and record
breaker.check_and_raise()  # Raises if open
try:
    result = await make_request()
    breaker.record_success()
except Exception:
    breaker.record_failure()
    raise

# Method 2: Protected call wrapper
result = await breaker.protected_call(make_request)

# Method 3: Context manager
async with breaker:
    result = await make_request()
```

### Integration

- Integrated with Prometheus metrics for monitoring
- Logs state transitions (CLOSED → OPEN → HALF_OPEN)
- Thread-safe with asyncio Lock
- Used by AI service clients (RT-DETR, Nemotron, Florence-2)

## `error_context.py` - Structured Error Context

### Purpose

Provides utilities for capturing rich context around errors for better debugging and monitoring.

### Key Components

**`ErrorContext` dataclass** - Structured error information:

- Exception details (type, message, traceback)
- Request context (request_id, path, method)
- Service context (external service errors)
- Operation details (what was being attempted)
- Timestamp and duration tracking

**`ErrorContextBuilder`** - Fluent builder API:

```python
from backend.core.error_context import ErrorContextBuilder

ctx = (
    ErrorContextBuilder()
    .from_exception(exc)
    .with_operation("detect_objects")
    .with_request(request_id, path, method)
    .with_service("rtdetr", status_code=503)
    .build()
)
```

**Helper Functions:**

- `log_error(exception, **context)` - Log error with full context
- `log_with_context(level, message, **context)` - Structured logging helper

**Usage:**

```python
from backend.core.error_context import log_error, log_with_context

# Log an error with full context
try:
    await risky_operation()
except DatabaseError as e:
    log_error(e, operation="sync_data", request_id=request_id)

# Structured logging
log_with_context("info", "Processing started", camera_id="front_door", event_id=123)
```

### Features

- Exception chain capture for root cause analysis
- Request context extraction from FastAPI
- Service context for external service errors
- Automatic sensitive data redaction
- Integration with custom exception hierarchy

## `exceptions.py` - Custom Exception Hierarchy

### Purpose

Defines custom exceptions used throughout the backend with HTTP status code mapping.

### Exception Hierarchy

**Base Exception:**

- `SecurityIntelligenceError` - Base for all custom exceptions

**Infrastructure Errors:**

- `DatabaseError` (500) - Database operation failures
- `RedisError` (500) - Redis operation failures
- `ConfigurationError` (500) - Configuration problems

**External Service Errors:**

- `ExternalServiceError` (503) - Base for external service failures
- `AIServiceError` (503) - AI service unavailable
- `RTDETRError` (503) - RT-DETR service error
- `NemotronError` (503) - Nemotron service error
- `FlorenceError` (503) - Florence-2 service error

**Processing Errors:**

- `DetectionError` (500) - Detection processing failure
- `EventProcessingError` (500) - Event processing failure
- `MediaProcessingError` (500) - Media file processing failure

**Validation Errors:**

- `ValidationError` (400) - Input validation failure
- `NotFoundError` (404) - Resource not found
- `ConflictError` (409) - Resource conflict

**Circuit Breaker:**

- `CircuitBreakerOpenError` (503) - Circuit breaker is open

**Helper Functions:**

- `get_exception_status_code(exc)` - Get HTTP status code for exception
- `get_exception_error_code(exc)` - Get error code string

**Usage:**

```python
from backend.core.exceptions import AIServiceError, NotFoundError

# Raise with context
raise AIServiceError("RT-DETR unavailable", service="rtdetr")

# Get HTTP status
from backend.core.exceptions import get_exception_status_code
status = get_exception_status_code(exc)  # Returns 503 for AIServiceError
```

## `query_explain.py` - Slow Query Logging

### Purpose

Automatic detection and logging of slow database queries with EXPLAIN ANALYZE output for performance debugging.

### Features

- Configurable threshold for slow query detection (default: 100ms)
- Only runs EXPLAIN on SELECT queries (INSERT/UPDATE/DELETE excluded)
- Structured JSON logging with query text, parameters, timing, and EXPLAIN output
- Can be enabled/disabled via settings
- Graceful error handling to avoid crashing on EXPLAIN failures

### Configuration

Environment variables:

- `SLOW_QUERY_THRESHOLD_MS` - Threshold in milliseconds (default: 100)
- `SLOW_QUERY_EXPLAIN_ENABLED` - Enable/disable EXPLAIN logging (default: true)

### Usage

```python
from backend.core.database import get_engine
from backend.core.query_explain import setup_explain_logging

# During application startup
engine = get_engine()
setup_explain_logging(engine.sync_engine)
```

### Implementation

- Uses SQLAlchemy's event system to intercept queries
- Measures query execution time
- Runs EXPLAIN ANALYZE on slow queries
- Logs with structured metadata (query, params, duration, EXPLAIN output)
- Redacts sensitive parameters (passwords, tokens, API keys)

## `retry.py` - Retry Decorators

### Purpose

Provides reusable retry patterns with exponential backoff and jitter for transient failures.

### Features

- Configurable exponential backoff with jitter
- Retry on specific exception types
- Both async and sync decorators
- Context manager for fine-grained control
- Metrics integration for monitoring retry behavior
- Structured logging of retry attempts

### Decorators

**`@retry_async`** - Decorator for async functions:

```python
from backend.core.retry import retry_async
from backend.core.exceptions import ExternalServiceError

@retry_async(max_retries=3, retry_on=(ExternalServiceError,))
async def call_external_service():
    return await http_client.get(url)
```

**`@retry_sync`** - Decorator for sync functions:

```python
from backend.core.retry import retry_sync

@retry_sync(max_retries=3, retry_on=(ConnectionError,))
def sync_operation():
    return requests.get(url)
```

### Context Manager

**`RetryContext`** - Fine-grained control:

```python
from backend.core.retry import RetryContext

async with RetryContext(max_retries=3) as retry:
    while retry.should_retry():
        try:
            result = await risky_operation()
            break
        except TransientError as e:
            if not retry.can_retry(e):
                raise
            await retry.wait()
```

### Configuration

**Parameters:**

- `max_retries` - Maximum retry attempts (default: 3)
- `base_delay` - Initial delay in seconds (default: 1.0)
- `max_delay` - Maximum delay between retries (default: 60.0)
- `exponential_base` - Backoff multiplier (default: 2)
- `retry_on` - Tuple of exception types to retry
- `jitter` - Whether to add random jitter (default: True)

### Usage Notes

- Exponential backoff: delay = base_delay \* (exponential_base \*\* attempt)
- Jitter prevents thundering herd problem
- Integrates with Prometheus for retry metrics
- Used throughout AI service clients

## `container.py` - Dependency Injection Container (NEM-1636)

### Purpose

Provides a lightweight DI container that replaces global singleton patterns with centralized dependency management. Supports singleton and factory patterns with async initialization.

### Key Classes

| Class                           | Purpose                                  |
| ------------------------------- | ---------------------------------------- |
| `Container`                     | Main DI container with service lifecycle |
| `ServiceRegistration`           | Holds registration info for a service    |
| `ServiceNotFoundError`          | Raised when requested service not found  |
| `ServiceAlreadyRegisteredError` | Raised when registering duplicate name   |
| `CircularDependencyError`       | Raised when circular dependency detected |

### Container Methods

| Method                     | Purpose                                     |
| -------------------------- | ------------------------------------------- |
| `register_singleton`       | Register a singleton service                |
| `register_factory`         | Register a factory (new instance each time) |
| `register_async_singleton` | Register an async singleton service         |
| `get`                      | Get a synchronous service by name           |
| `get_async`                | Get an async service by name                |
| `get_dependency`           | Get FastAPI-compatible dependency factory   |
| `override`                 | Override a service for testing              |
| `clear_override`           | Clear a specific override                   |
| `clear_all_overrides`      | Clear all service overrides                 |
| `shutdown`                 | Gracefully shutdown all services            |

### Key Functions

| Function          | Purpose                          |
| ----------------- | -------------------------------- |
| `get_container`   | Get global container singleton   |
| `reset_container` | Reset container for testing      |
| `wire_services`   | Wire up all application services |

### Services Wired by `wire_services()`

- `redis_client` - RedisClient (async singleton)
- `context_enricher` - ContextEnricher (singleton)
- `enrichment_pipeline` - EnrichmentPipeline (async singleton)
- `nemotron_analyzer` - NemotronAnalyzer (async singleton)
- `detector_client` - DetectorClient (singleton)
- `face_detector_service` - FaceDetectorService (singleton)
- `plate_detector_service` - PlateDetectorService (singleton)
- `ocr_service` - OCRService (singleton)
- `yolo_world_service` - YOLOWorldService (singleton)
- `health_service_registry` - HealthServiceRegistry (singleton, NEM-2611)
- `health_event_emitter` - HealthEventEmitter (singleton, NEM-2611)

### Usage

```python
from backend.core.container import get_container, wire_services

# Get the global container
container = get_container()

# Wire up services at startup
await wire_services(container)

# Get services
detector = container.get("detector_client")
redis = await container.get_async("redis_client")

# FastAPI integration
@app.get("/")
async def endpoint(service: MyService = Depends(container.get_dependency("my_service"))):
    ...

# Testing with overrides
container.override("redis_client", mock_redis)
# ... run tests ...
container.clear_override("redis_client")

# Shutdown all services
await container.shutdown()
```

## `dependencies.py` - FastAPI Dependencies (NEM-1636)

### Purpose

Provides FastAPI-compatible dependency functions that inject services from the DI container into route handlers using `Depends()`.

### Key Functions

| Function                                | Service Type            | Purpose                           |
| --------------------------------------- | ----------------------- | --------------------------------- |
| `get_redis_dependency`                  | RedisClient             | Redis client for caching/queues   |
| `get_context_enricher_dependency`       | ContextEnricher         | Detection context enrichment      |
| `get_enrichment_pipeline_dependency`    | EnrichmentPipeline      | Full enrichment pipeline          |
| `get_nemotron_analyzer_dependency`      | NemotronAnalyzer        | LLM risk analysis                 |
| `get_detector_dependency`               | DetectorClient          | RT-DETR object detection          |
| `get_face_detector_service_dependency`  | FaceDetectorService     | Face detection in person regions  |
| `get_plate_detector_service_dependency` | PlateDetectorService    | License plate detection           |
| `get_ocr_service_dependency`            | OCRService              | Plate text recognition            |
| `get_yolo_world_service_dependency`     | YOLOWorldService        | Open-vocabulary detection         |
| `get_entity_repository`                 | EntityRepository        | Entity CRUD with managed session  |
| `get_entity_clustering_service`         | EntityClusteringService | Entity assignment with clustering |
| `get_hybrid_entity_storage`             | HybridEntityStorage     | Redis + PostgreSQL entity storage |
| `get_reid_service_dependency`           | ReIdentificationService | Re-ID with hybrid storage         |
| `get_pagination_limits`                 | PaginationLimits        | Pagination config from settings   |

### PaginationLimits Class (NEM-2591)

Container for pagination limit configuration:

```python
class PaginationLimits:
    max_limit: int       # Maximum allowed limit for paginated requests
    default_limit: int   # Default limit when not specified in request
```

### Usage

```python
from fastapi import Depends
from backend.core.dependencies import (
    get_redis_dependency,
    get_detector_dependency,
    get_pagination_limits,
    PaginationLimits,
)

@router.get("/detections")
async def get_detections(
    redis: RedisClient = Depends(get_redis_dependency),
    detector: DetectorClient = Depends(get_detector_dependency),
    limits: PaginationLimits = Depends(get_pagination_limits),
    limit: int = Query(default=None),
):
    validated_limit = limits.default_limit if limit is None else limit
    if validated_limit > limits.max_limit:
        raise HTTPException(status_code=400, detail="Limit too large")
    ...
```

## `profiling.py` - Performance Profiling (NEM-1644)

### Purpose

Provides cProfile-based profiling infrastructure for performance analysis and debugging.

### Key Components

| Component                 | Purpose                                |
| ------------------------- | -------------------------------------- |
| `ProfilingManager`        | Manages cProfile state and statistics  |
| `profile_if_enabled`      | Decorator for function profiling       |
| `get_profiling_manager`   | Get global profiling manager singleton |
| `reset_profiling_manager` | Reset manager for testing              |

### ProfilingManager Methods

| Method              | Purpose                                 |
| ------------------- | --------------------------------------- |
| `start()`           | Start profiling session                 |
| `stop()`            | Stop profiling and save results         |
| `get_stats_text()`  | Get human-readable statistics           |
| `is_profiling`      | Property: whether profiling is active   |
| `last_profile_path` | Property: path to last saved .prof file |

### Usage

```python
from backend.core.profiling import (
    profile_if_enabled,
    get_profiling_manager,
)

# Decorator for automatic profiling when PROFILING_ENABLED=true
@profile_if_enabled
async def my_endpoint_handler():
    ...

# Manual profiling control
manager = get_profiling_manager()
manager.start()
# ... do work ...
manager.stop()
print(manager.get_stats_text())
```

### Profile Analysis

Profile files (.prof) can be analyzed with:

- snakeviz: `snakeviz data/profiles/my_function.prof`
- py-spy: `py-spy top --pid <PID>`

### Configuration

| Setting           | Env Variable           | Default         |
| ----------------- | ---------------------- | --------------- |
| Profiling enabled | `PROFILING_ENABLED`    | False           |
| Output directory  | `PROFILING_OUTPUT_DIR` | `data/profiles` |

## `protocols.py` - Service Interface Protocols

### Purpose

Defines Protocol classes for structural subtyping, enabling type-safe interface definitions without requiring explicit inheritance. Services implement these protocols structurally (duck typing with static type checking).

### Protocol Definitions

| Protocol                  | Purpose                                |
| ------------------------- | -------------------------------------- |
| `HealthCheckableProtocol` | Services with `health_check()` method  |
| `AIServiceProtocol`       | AI clients (detector, nemotron, etc.)  |
| `QueueProcessorProtocol`  | Queue-based processors (batch, eval)   |
| `BroadcasterProtocol`     | WebSocket message broadcasters         |
| `ModelLoaderProtocol`     | ML model loaders (CLIP, ViTPose, etc.) |
| `SubscribableProtocol`    | Services supporting pub/sub            |
| `CacheProtocol`           | Cache services (get/set/delete/exists) |
| `MetricsProviderProtocol` | Services exposing metrics              |
| `LifecycleProtocol`       | Services with start/stop lifecycle     |

### Type Aliases

| Alias                    | Combination          |
| ------------------------ | -------------------- | ------------------------ |
| `AIServiceWithLifecycle` | `AIServiceProtocol   | LifecycleProtocol`       |
| `BroadcasterWithMetrics` | `BroadcasterProtocol | MetricsProviderProtocol` |

### Usage

```python
from backend.core.protocols import AIServiceProtocol, HealthCheckableProtocol

# Type hinting with protocols
async def process_with_service(service: AIServiceProtocol) -> dict[str, Any]:
    if await service.health_check():
        return await service.process(input_data)

# Works with any class that has matching methods (structural subtyping)
detector = DetectorClient()  # Implements AIServiceProtocol structurally
await process_with_service(detector)

# Runtime type checking with @runtime_checkable
if isinstance(service, HealthCheckableProtocol):
    is_healthy = await service.health_check()
```

### Protocol Method Signatures

**AIServiceProtocol:**

- `health_check() -> bool` - Check service availability
- `process(input_data: Any) -> Any` - Process input through AI
- `get_metrics() -> dict[str, Any]` - Get monitoring metrics

**QueueProcessorProtocol:**

- `enqueue(item: Any) -> bool` - Add item to queue
- `dequeue() -> Any | None` - Remove next item
- `process_item(item: Any) -> None` - Process single item

**ModelLoaderProtocol:**

- `load() -> None` - Load model into memory
- `unload() -> None` - Free model memory
- `is_loaded() -> bool` - Check if loaded
- `predict(input_data: Any) -> Any` - Run inference

**LifecycleProtocol:**

- `start() -> None` - Start the service
- `stop() -> None` - Stop gracefully
- `is_running() -> bool` - Check running state

## `telemetry.py` - OpenTelemetry Distributed Tracing (NEM-1629)

### Purpose

Provides OpenTelemetry instrumentation for distributed tracing across the home security system, enabling:

- Automatic trace propagation across services
- Log correlation with trace IDs
- Performance monitoring via span timings
- Integration with Jaeger, Tempo, or OTLP backends

### Configuration

| Setting             | Env Variable                  | Default               |
| ------------------- | ----------------------------- | --------------------- |
| Enabled             | `OTEL_ENABLED`                | False                 |
| Service name        | `OTEL_SERVICE_NAME`           | nemotron-backend      |
| OTLP endpoint       | `OTEL_EXPORTER_OTLP_ENDPOINT` | http://localhost:4317 |
| Insecure connection | `OTEL_EXPORTER_OTLP_INSECURE` | True                  |
| Sample rate         | `OTEL_TRACE_SAMPLE_RATE`      | 1.0 (100%)            |

### Key Functions

| Function               | Purpose                            |
| ---------------------- | ---------------------------------- |
| `setup_telemetry`      | Initialize OTEL with FastAPI app   |
| `shutdown_telemetry`   | Shutdown and flush pending traces  |
| `get_tracer`           | Get tracer for custom spans        |
| `get_current_span`     | Get active span from context       |
| `add_span_attributes`  | Add attributes to current span     |
| `record_exception`     | Record exception on current span   |
| `is_telemetry_enabled` | Check if telemetry is initialized  |
| `get_trace_id`         | Get current trace ID (32-char hex) |
| `get_span_id`          | Get current span ID (16-char hex)  |
| `get_trace_context`    | Get dict with trace_id and span_id |

### Context Manager and Decorator (NEM-1503)

**`trace_span` Context Manager:**

```python
from backend.core.telemetry import trace_span

with trace_span("detect_objects", camera_id="front_door") as span:
    results = await detector.detect(image_path)
    span.set_attribute("detection_count", len(results))
```

**`trace_function` Decorator:**

```python
from backend.core.telemetry import trace_function

@trace_function("rtdetr_detection")
async def detect_objects(image_path: str) -> list[Detection]:
    return await client.detect(image_path)

@trace_function(service="nemotron")
async def analyze_batch(batch: Batch) -> AnalysisResult:
    return await analyzer.analyze(batch)
```

### Log Correlation

```python
from backend.core.telemetry import get_trace_id, get_trace_context

# Include trace ID in logs
logger.info("Processing", extra={"trace_id": get_trace_id()})

# Or use get_trace_context for both IDs
logger.info("Operation complete", extra={**get_trace_context(), "result": "success"})
```

### Auto-Instrumentation

`setup_telemetry` automatically instruments:

- FastAPI (HTTP request/response tracing)
- HTTPX (outgoing AI service calls)
- SQLAlchemy (database queries)
- Redis (cache operations)

### No-Op Mode

When OTEL is disabled or not installed, all functions return no-op implementations that have minimal overhead.

## `constants.py` - Application Constants

### Purpose

Provides centralized constants for Redis queue names and DLQ (dead-letter queue) naming.

### Constants

**Queue Names:**

- `DETECTION_QUEUE = "detection_queue"` - Queue for incoming detection jobs
- `ANALYSIS_QUEUE = "analysis_queue"` - Queue for batched detections ready for LLM analysis

**DLQ Names:**

- `DLQ_PREFIX = "dlq:"` - Prefix for all dead-letter queues
- `DLQ_DETECTION_QUEUE = "dlq:detection_queue"` - DLQ for failed detection jobs
- `DLQ_ANALYSIS_QUEUE = "dlq:analysis_queue"` - DLQ for failed LLM analysis jobs
- `DLQ_OVERFLOW_PREFIX = "dlq:overflow:"` - Prefix for overflow DLQ queues

### Helper Functions

- `get_dlq_name(queue_name)` - Get the DLQ name for a given queue
- `get_dlq_overflow_name(queue_name)` - Get the overflow DLQ name for a given queue

**Usage:**

```python
from backend.core.constants import (
    DETECTION_QUEUE,
    ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
    get_dlq_name,
)

# Queue operations (use add_to_queue_safe for proper backpressure handling)
result = await redis.add_to_queue_safe(DETECTION_QUEUE, data)
dlq_name = get_dlq_name("detection_queue")  # Returns "dlq:detection_queue"
```

## `config.py` - Configuration Management

### Purpose

Manages all application configuration using Pydantic Settings with environment variable loading.

### Key Classes

**`OrchestratorSettings`** - Container orchestrator configuration (Docker/Podman):

- `enabled: bool` - Enable container orchestration (default: True)
- `docker_host: str | None` - Docker socket path
- Health monitoring and self-healing for AI containers

**`Settings`** - Main configuration class (Pydantic BaseSettings):

**Database Configuration:**

- `database_url: str` - SQLAlchemy URL (required, no default - must be set)
- Must use the async PostgreSQL driver scheme (postgresql+asyncpg)
- Example: `DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security` <!-- pragma: allowlist secret -->

**Redis Configuration:**

- `redis_url: str` - Redis connection URL (default: `redis://localhost:6379/0`)
- `redis_event_channel: str` - Pub/sub channel for events (default: `security_events`)

**Application Settings:**

- `app_name: str` - Application name (default: "Home Security Intelligence")
- `app_version: str` - Version string (default: "0.1.0")
- `debug: bool` - Debug mode flag (default: False)
- `admin_enabled: bool` - Enable admin endpoints (requires debug=True also)
- `admin_api_key: str | None` - Optional API key for admin endpoints

**API Settings:**

- `api_host: str` - Host to bind to (default: `0.0.0.0`)
- `api_port: int` - Port to listen on (default: 8000)
- `cors_origins: list[str]` - Allowed CORS origins

**File Watching Settings:**

- `foscam_base_path: str` - Base path for camera uploads (default: `/export/foscam`)

**Retention Settings:**

- `retention_days: int` - Days to retain events/detections (default: 30)

**Batch Processing Settings:**

- `batch_window_seconds: int` - Time window for batching detections (default: 90)
- `batch_idle_timeout_seconds: int` - Idle timeout before processing batch (default: 30)

**AI Service Endpoints:**

- `rtdetr_url: str` - RT-DETRv2 detection service URL (default: `http://localhost:8090`)
- `nemotron_url: str` - Nemotron reasoning service URL (default: `http://localhost:8091`)

**AI Service Timeout Settings:**

- `ai_connect_timeout: float` - Connection timeout (default: 10.0s, range: 1-60)
- `ai_health_timeout: float` - Health check timeout (default: 5.0s, range: 1-30)
- `rtdetr_read_timeout: float` - RT-DETR response timeout (default: 60.0s, range: 10-300)
- `nemotron_read_timeout: float` - Nemotron response timeout (default: 120.0s, range: 30-600)

**Detection Settings:**

- `detection_confidence_threshold: float` - Minimum confidence (default: 0.5, range: 0.0-1.0)

**Fast Path Settings:**

- `fast_path_confidence_threshold: float` - High-priority threshold (default: 0.90)
- `fast_path_object_types: list[str]` - Object types for fast path (default: `["person"]`)

**GPU Monitoring Settings:**

- `gpu_poll_interval_seconds: float` - GPU stats polling interval (default: 5.0)
- `gpu_stats_history_minutes: int` - GPU stats history retention (default: 60)

**Queue Backpressure Settings:**

- `queue_max_size: int` - Maximum queue size (default: 10000)
- `queue_overflow_policy: str` - Policy when full: 'drop_oldest', 'reject', 'dlq'
- `queue_backpressure_threshold: float` - Fill ratio for warnings (default: 0.8)

**Rate Limiting Settings:**

- `rate_limit_enabled: bool` - Enable rate limiting (default: True)
- `rate_limit_requests_per_minute: int` - General limit (default: 60)
- `rate_limit_burst: int` - Burst allowance (default: 10)
- `rate_limit_media_requests_per_minute: int` - Media endpoint limit (default: 120)
- `rate_limit_websocket_connections_per_minute: int` - WebSocket limit (default: 10)
- `rate_limit_search_requests_per_minute: int` - Search endpoint limit (default: 30)

**WebSocket Settings:**

- `websocket_idle_timeout_seconds: int` - Idle timeout (default: 300s)
- `websocket_ping_interval_seconds: int` - Ping interval (default: 30s)
- `websocket_max_message_size: int` - Max message size (default: 64KB)

**Severity Threshold Settings:**

- `severity_low_max: int` - Max risk score for LOW severity (default: 29)
- `severity_medium_max: int` - Max risk score for MEDIUM (default: 59)
- `severity_high_max: int` - Max risk score for HIGH (default: 84)

**Authentication Settings:**

- `api_key_enabled: bool` - Enable API key authentication (default: False)
- `api_keys: list[str]` - List of valid API keys

**TLS/HTTPS Settings:**

- `tls_mode: str` - TLS mode: 'disabled', 'self_signed', 'provided'
- `tls_cert_path: str` - Path to certificate file
- `tls_key_path: str` - Path to private key file
- `tls_ca_path: str` - Optional CA certificate for client verification
- `tls_verify_client: bool` - Require client certificates (mTLS)
- `tls_min_version: str` - Minimum TLS version ('TLSv1.2' or 'TLSv1.3')

**Notification Settings:**

- `notification_enabled: bool` - Enable notification delivery (default: True)
- `smtp_host/port/user/password` - SMTP email configuration
- `smtp_from_address: str` - Email sender address
- `smtp_use_tls: bool` - Use TLS for SMTP (default: True)
- `default_webhook_url: str | None` - Default webhook URL for alerts
- `webhook_timeout_seconds: int` - Webhook request timeout (default: 30)
- `default_email_recipients: list[str]` - Default email recipients

**Clip Generation Settings:**

- `clips_directory: str` - Directory for event clips (default: "data/clips")
- `clip_pre_roll_seconds: int` - Pre-event time in clips (default: 5)
- `clip_post_roll_seconds: int` - Post-event time in clips (default: 5)
- `clip_generation_enabled: bool` - Enable clip generation (default: True)

**Video Processing Settings:**

- `video_frame_interval_seconds: float` - Frame extraction interval (default: 2.0)
- `video_thumbnails_dir: str` - Thumbnail directory (default: "data/thumbnails")
- `video_max_frames: int` - Max frames per video (default: 30)

**File Deduplication Settings:**

- `dedupe_ttl_seconds: int` - TTL for dedupe entries (default: 300)

**Logging Settings:**

- `log_level: str` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: WARNING)
- `log_file_path: str` - Path for rotating log file (default: `data/logs/security.log`)
- `log_file_max_bytes: int` - Maximum size of each log file (default: 10MB)
- `log_file_backup_count: int` - Number of backup log files to keep (default: 7)
- `log_db_enabled: bool` - Enable writing logs to PostgreSQL database (default: True)
- `log_db_min_level: str` - Minimum log level to write to database (default: DEBUG)
- `log_retention_days: int` - Number of days to retain logs (default: 7)

**DLQ Settings:**

- `max_requeue_iterations: int` - Max iterations for requeue-all (default: 10000)

### Configuration Loading

Settings are loaded from:

1. Environment variables (case-insensitive)
2. `.env` file in project root
3. Optional `runtime.env` file (controlled by `HSI_RUNTIME_ENV_PATH`)
4. Default values

**Model Config:**

```python
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

### Field Validators

**`validate_database_url`** - Validates database URL format:

- Ensures PostgreSQL URL is properly formatted
- Validates connection string components (user, host, port, database)
- No directory creation needed (PostgreSQL is external service)

**`validate_log_file_path`** - Ensures log directory exists:

- Creates parent directory for log files if it doesn't exist

### Singleton Pattern

```python
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    return Settings(_env_file=(".env", runtime_env_path))
```

## `database.py` - SQLAlchemy Async Layer

### Purpose

Provides async database connectivity using SQLAlchemy 2.0 with:

- Async engine creation and pooling
- Session factory for creating async sessions
- FastAPI dependency injection
- Context manager patterns
- PostgreSQL connection pooling

### Key Components

**`Base`** - Declarative base class for ORM models.

**Global State:**

```python
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
```

### Functions

**`init_db() -> None`** - Initialize database:

1. Gets settings via `get_settings()`
2. Creates async engine with appropriate configuration:
   - PostgreSQL: Uses standard connection pool with asyncpg driver
   - Enables debug logging if `settings.debug=True`
   - Configures connection pool settings (pool size, timeout)
3. Enables foreign key constraints (native PostgreSQL support)
4. Creates async session factory with:
   - `expire_on_commit=False` - Keep objects usable after commit
   - `autocommit=False` - Manual transaction control
   - `autoflush=False` - Explicit flush control
5. Imports all models to register with metadata
6. Creates all tables via `Base.metadata.create_all()`

**`close_db() -> None`** - Cleanup database connections.

**`get_engine() -> AsyncEngine`** - Access global engine.

**`get_session_factory() -> async_sessionmaker[AsyncSession]`** - Access session factory.

**`get_session() -> AsyncGenerator[AsyncSession, None]`** - Context manager for services:

```python
async with get_session() as session:
    result = await session.execute(select(Camera))
    # Auto-commit on success, rollback on exception
```

**`get_db() -> AsyncGenerator[AsyncSession, None]`** - FastAPI dependency:

```python
@router.get("/cameras")
async def list_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera))
    return result.scalars().all()
```

**`get_pool_status() -> dict[str, Any]`** - Get connection pool status metrics:

```python
from backend.core import get_pool_status

status = await get_pool_status()
# Returns: {
#   "pool_size": 20,       # Base connections maintained
#   "overflow": 5,         # Overflow connections in use
#   "checkedin": 15,       # Available connections
#   "checkedout": 10,      # Connections currently in use
#   "total_connections": 25
# }
```

### PostgreSQL Connection Pooling

The database module is configured for PostgreSQL with asyncpg. Pool settings are
fully configurable via environment variables:

| Setting      | Env Variable             | Default | Range    | Description                         |
| ------------ | ------------------------ | ------- | -------- | ----------------------------------- |
| Pool Size    | `DATABASE_POOL_SIZE`     | 20      | 5-100    | Base connections maintained in pool |
| Max Overflow | `DATABASE_POOL_OVERFLOW` | 30      | 0-100    | Additional connections under load   |
| Pool Timeout | `DATABASE_POOL_TIMEOUT`  | 30s     | 5-120    | Seconds to wait for connection      |
| Pool Recycle | `DATABASE_POOL_RECYCLE`  | 1800s   | 300-7200 | Connection recycling interval       |
| Pre-ping     | Always enabled           | -       | -        | Validates connections before use    |

**Example configuration for high-traffic deployments:**

```bash
# .env file
DATABASE_POOL_SIZE=30
DATABASE_POOL_OVERFLOW=50
DATABASE_POOL_TIMEOUT=45
DATABASE_POOL_RECYCLE=1200
```

**Pool status is exposed in the health check endpoint** (`/api/system/health`)
for monitoring and alerting on connection pool exhaustion

## `redis.py` - Redis Async Client

### Purpose

Provides async Redis connectivity with:

- Connection pooling and retry logic
- Queue operations (FIFO lists)
- Pub/Sub messaging
- Cache operations
- JSON serialization/deserialization
- Health monitoring

### Key Class: `RedisClient`

**Initialization:**

```python
client = RedisClient(redis_url="redis://localhost:6379/0")
await client.connect()
```

**Connection pooling:**

- Max 10 connections
- UTF-8 encoding with `decode_responses=True`
- 5-second connection timeout
- Keep-alive enabled
- 30-second health check interval

**Retry logic:**

- 3 connection attempts
- Exponential backoff with jitter
- Configurable base delay (1s) and max delay (30s)

### Queue Operations

**With backpressure handling:**

- `add_to_queue_safe(queue_name, data, max_size, overflow_policy, dlq_name)` - Returns `QueueAddResult`
  - `QueueOverflowPolicy.REJECT` - Returns error, item NOT added
  - `QueueOverflowPolicy.DLQ` - Moves oldest to dead-letter queue
  - `QueueOverflowPolicy.DROP_OLDEST` - Trims with explicit warning
- `get_queue_pressure(queue_name, max_size)` - Returns `QueuePressureMetrics`

**Standard operations:**

- `get_from_queue(queue_name, timeout=0)` - BLPOP (blocking pop)
- `get_queue_length(queue_name)` - LLEN
- `peek_queue(queue_name, start=0, end=100, max_items=1000)` - LRANGE
- `clear_queue(queue_name)` - DELETE

### Pub/Sub Operations

**`publish(channel, message)`** - Publish with JSON serialization
**`subscribe(*channels)`** - Subscribe to channels
**`unsubscribe(*channels)`** - Unsubscribe from channels
**`listen(pubsub)`** - Async generator for messages

### Cache Operations

**`get(key)`** - GET with JSON deserialization
**`set(key, value, expire=None)`** - SET with optional TTL
**`delete(*keys)`** - DEL
**`exists(*keys)`** - EXISTS

### Health Check

**`health_check()`** - Returns status dict with connected state and Redis version.

### Global Singleton Pattern

```python
async def init_redis() -> RedisClient:
    """Initialize Redis for app startup."""

async def close_redis() -> None:
    """Close Redis for app shutdown."""

async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """FastAPI dependency for Redis."""
```

## `logging.py` - Centralized Logging

### Purpose

Provides unified logging infrastructure with multiple outputs:

- Console handler with plain text format for development
- File handler with rotating logs for production grep/tail
- Database handler for admin UI queries and structured log storage

### Key Components

**Context Variables:**

- `_request_id: ContextVar[str | None]` - Thread-safe request ID propagation
- `_log_context: ContextVar[dict]` - Structured log context for enriched logging (NEM-1645)
- `get_request_id()` - Retrieve current request ID
- `set_request_id()` - Set request ID (used by RequestIDMiddleware)
- `get_log_context()` - Retrieve current structured log context
- `log_context(**kwargs)` - Context manager for enriched logging

**Classes:**

**`ContextFilter`** - Adds contextual information to log records:

- Injects `request_id` from request context
- Injects `connection_id` from WebSocket context
- Injects all fields from `log_context` context manager

**`CustomJsonFormatter`** - JSON formatter with ISO timestamp and structured fields.

**`DatabaseHandler`** - Custom handler writing logs to database:

- Uses synchronous database sessions
- Extracts structured metadata (camera_id, event_id, detection_id, duration_ms)
- Falls back gracefully if database is unavailable

### Structured Error Context (NEM-1645)

The `log_context` context manager provides a powerful way to enrich all logs within a scope with consistent context fields. This is especially useful for error handling and debugging.

**Basic Usage:**

```python
from backend.core.logging import get_logger, log_context

logger = get_logger(__name__)

# All logs within this context automatically include camera_id and operation
with log_context(camera_id="front_door", operation="detect"):
    logger.info("Starting detection")  # Includes camera_id and operation
    try:
        result = await detect_objects(image_path)
    except TimeoutError as e:
        logger.error("Detection timed out")  # Also includes camera_id and operation
        raise
```

**Nested Contexts:**

```python
with log_context(camera_id="front_door"):
    with log_context(operation="detect", retry_count=1):
        logger.info("Processing")
        # Includes: camera_id, operation, and retry_count
```

**Error Context Guidelines:**

When logging exceptions, always include:

1. **Relevant IDs** (event_id, camera_id, detection_id)
2. **Operation context** (what was being attempted)
3. **Retry count** if applicable

```python
# Good: Structured error context
with log_context(camera_id=camera.id, operation="detection"):
    try:
        await process_detection(image_path)
    except TimeoutError as e:
        logger.exception(
            "Detection request timed out",
            extra={
                "file_path": image_path,
                "timeout_seconds": 30,
                "retry_count": attempt,
            }
        )

# Bad: Missing context
except Exception as e:
    logger.error(f"Error processing image: {e}")  # No context!
```

**Combining with explicit extra:**

```python
with log_context(camera_id="front_door"):
    logger.info(
        "Detection completed",
        extra={"detection_count": 5, "duration_ms": 250}
    )
    # Includes: camera_id (from context), detection_count, duration_ms (from extra)
```

### Functions

**`setup_logging()`** - Initialize application-wide logging:

1. Gets log level from settings
2. Clears existing handlers on root logger
3. Adds ContextFilter for request ID propagation
4. Creates console handler with plain text format
5. Creates rotating file handler (if path is accessible)
6. Creates database handler (if `log_db_enabled=True`)
7. Reduces noise from third-party libraries (uvicorn, sqlalchemy, watchdog)

**`get_logger(name: str)`** - Get a configured logger:

```python
from backend.core import get_logger

logger = get_logger(__name__)
logger.info("Detection processed", extra={
    "camera_id": "front_door",
    "detection_id": 123,
    "duration_ms": 45
})
```

**`sanitize_error(error, max_length=500)`** - Sanitize error messages:

- Removes credential patterns (password, secret, token, api_key, Bearer)
- Simplifies file paths to just filenames
- Truncates long messages

## `async_context.py` - Async Context Propagation (NEM-1640)

### Purpose

Provides utilities for propagating logging context across async boundaries, ensuring `request_id` and `connection_id` are properly maintained when creating background tasks or handling WebSocket connections.

### Key Components

**Context Variables:**

- `_connection_id: ContextVar[str | None]` - WebSocket connection ID for persistent tracing
- `get_connection_id()` - Retrieve current WebSocket connection ID
- `set_connection_id()` - Set WebSocket connection ID

**Functions:**

- `propagate_log_context()` - Async context manager for task context propagation
- `create_task_with_context()` - Create tasks with preserved logging context
- `copy_context_to_task` - Decorator for context-preserving coroutines
- `logger_with_context()` - Async context manager for adding extra fields

### Context Propagation Patterns

#### Problem: Context Loss in Background Tasks

When using `asyncio.create_task()`, the logging context (request_id, connection_id) is not automatically propagated to the new task:

```python
# BAD: Context is lost in the background task
set_request_id("req-123")

async def background_work():
    # request_id is None here!
    logger.info("Working")  # No request_id in log

task = asyncio.create_task(background_work())  # Context not propagated
```

#### Solution 1: create_task_with_context

Use `create_task_with_context()` instead of `asyncio.create_task()`:

```python
from backend.core.async_context import create_task_with_context

set_request_id("req-123")

async def background_work():
    # request_id is "req-123" here!
    logger.info("Working")  # Includes request_id

# Context is automatically propagated
task = create_task_with_context(background_work())
```

#### Solution 2: propagate_log_context

Use the async context manager for explicit context propagation:

```python
from backend.core.async_context import propagate_log_context

async with propagate_log_context(request_id="req-123"):
    # All logs in this context include request_id
    await some_operation()

# Or to preserve existing context in a background task:
async def background_work():
    async with propagate_log_context():
        logger.info("Working")  # Uses propagated context
```

#### Solution 3: copy_context_to_task Decorator

For functions that are always called as background tasks:

```python
from backend.core.async_context import copy_context_to_task

@copy_context_to_task
async def background_processing():
    # Automatically inherits context from caller
    logger.info("Processing")  # Includes request_id from caller

set_request_id("caller-request")
task = asyncio.create_task(background_processing())
await task
```

### WebSocket Connection Tracking

For WebSocket connections, use `connection_id` for persistent tracing across the entire connection lifecycle:

```python
from backend.core.async_context import set_connection_id, get_connection_id

# In WebSocket handler
async def websocket_handler(websocket):
    connection_id = f"ws-{uuid.uuid4().hex[:8]}"
    set_connection_id(connection_id)

    try:
        # All logs in this handler include connection_id
        logger.info("Client connected")  # Has connection_id

        while True:
            data = await websocket.receive_text()
            logger.debug("Received message")  # Has connection_id
    finally:
        set_connection_id(None)
        logger.info("Client disconnected")
```

### Best Practices

1. **Use `create_task_with_context`** for all background tasks that should maintain logging context
2. **Set `connection_id`** at the start of WebSocket handlers and clear it in `finally`
3. **Use `propagate_log_context`** when you need explicit control over context in async operations
4. **Combine with `log_context`** for rich structured logging:

```python
from backend.core.async_context import create_task_with_context
from backend.core.logging import log_context

with log_context(camera_id="front_door"):
    task = create_task_with_context(process_detection(image_path))
    # Task inherits camera_id from log_context
```

### Integration with ContextFilter

The `ContextFilter` in `logging.py` automatically injects:

- `request_id` from request context
- `connection_id` from async_context module
- All fields from `log_context` context manager

This ensures all log messages include the proper context without manual intervention.

## `metrics.py` - Prometheus Metrics

### Purpose

Defines Prometheus metrics for observability:

### Metrics Defined

**Queue Depth Gauges:**

- `hsi_detection_queue_depth` - Images waiting in detection queue
- `hsi_analysis_queue_depth` - Batches waiting in analysis queue

**Stage Duration Histograms:**

- `hsi_stage_duration_seconds` - Duration by stage (detect, batch, analyze)

**Counters:**

- `hsi_events_created_total` - Total security events created
- `hsi_detections_processed_total` - Total detections processed
- `hsi_pipeline_errors_total` - Pipeline errors by type

**AI Request Duration:**

- `hsi_ai_request_duration_seconds` - AI service request duration by service

### Helper Functions

```python
set_queue_depth("detection", 10)
observe_stage_duration("detect", 0.5)
record_event_created()
record_detection_processed(count=5)
observe_ai_request_duration("rtdetr", 0.25)
record_pipeline_error("connection_error")
get_metrics_response()  # Returns Prometheus exposition format
```

### Pipeline Latency Tracker

`PipelineLatencyTracker` provides in-memory latency tracking with percentile calculations:

```python
from backend.core.metrics import get_pipeline_latency_tracker, record_pipeline_stage_latency

# Record latency
record_pipeline_stage_latency("watch_to_detect", 150.5)

# Get statistics
tracker = get_pipeline_latency_tracker()
stats = tracker.get_stage_stats("watch_to_detect", window_minutes=5)
# Returns: {avg_ms, min_ms, max_ms, p50_ms, p95_ms, p99_ms, sample_count}

summary = tracker.get_pipeline_summary()
# Returns stats for all stages: watch_to_detect, detect_to_batch, batch_to_analyze, total_pipeline
```

## `mime_types.py` - MIME Type Utilities

### Purpose

Provides centralized MIME type handling for media files:

### Key Constants

- `IMAGE_MIME_TYPES` - Mapping for .jpg, .jpeg, .png
- `VIDEO_MIME_TYPES` - Mapping for .mp4, .mkv, .avi, .mov
- `EXTENSION_TO_MIME` - Combined extension-to-MIME mapping
- `MIME_TO_EXTENSION` - Reverse MIME-to-extension mapping

### Functions

```python
from backend.core.mime_types import get_mime_type, is_video_mime_type, normalize_file_type

# Get MIME type from path
mime = get_mime_type("/path/to/video.mp4")  # "video/mp4"

# Check type
is_video_mime_type(mime)  # True

# Normalize mixed formats (extension or MIME)
normalize_file_type(".jpg")  # "image/jpeg"
normalize_file_type("image/png")  # "image/png"
```

## `tls.py` - TLS/SSL Configuration

### Purpose

Provides TLS certificate management for HTTPS:

### TLS Modes

```python
from backend.core.tls import TLSMode, TLSConfig

class TLSMode(str, Enum):
    DISABLED = "disabled"      # HTTP only (default)
    SELF_SIGNED = "self_signed"  # Auto-generate certificates
    PROVIDED = "provided"      # Use existing certificate files
```

### Key Functions

**Certificate Generation:**

```python
from backend.core.tls import generate_self_signed_cert

generate_self_signed_cert(
    cert_path=Path("certs/server.crt"),
    key_path=Path("certs/server.key"),
    hostname="localhost",
    san_ips=["192.168.1.100"],
    san_dns=["localhost", "myserver.local"],
    days_valid=365,
)
```

**SSL Context Creation:**

```python
from backend.core.tls import TLSConfig, TLSMode, create_ssl_context

config = TLSConfig(
    mode=TLSMode.PROVIDED,
    cert_path="/path/to/cert.pem",
    key_path="/path/to/key.pem",
    min_version=ssl.TLSVersion.TLSv1_2,
)
ssl_context = create_ssl_context(config)
```

**Certificate Validation:**

```python
from backend.core.tls import validate_certificate, get_cert_info

info = validate_certificate(Path("/path/to/cert.pem"))
# Returns: {valid, subject, issuer, not_before, not_after, serial_number, days_remaining}

# Or use get_cert_info() for currently configured certificate
cert_info = get_cert_info()
```

### Custom Exceptions

- `TLSError` - Base exception for TLS errors
- `TLSConfigurationError` - Invalid or incomplete configuration
- `CertificateNotFoundError` - Certificate file not found
- `CertificateValidationError` - Certificate parsing/validation failed

## `json_utils.py` - LLM JSON Parsing

### Purpose

Provides robust JSON extraction from potentially malformed LLM outputs, handling common issues like:

- Markdown code blocks (`json ... `)
- `<think>...</think>` reasoning blocks
- Extra text before/after JSON
- Missing commas between object properties
- Trailing commas
- Single quotes instead of double quotes
- Incomplete/truncated JSON

### Functions

**`extract_json_from_llm_response(text)`** - Extract and parse JSON from an LLM response:

````python
from backend.core.json_utils import extract_json_from_llm_response

response = '''<think>analyzing...</think>
```json
{"risk_score": 75, "summary": "Person detected"}
```'''

data = extract_json_from_llm_response(response)
# Returns: {"risk_score": 75, "summary": "Person detected"}
````

**`extract_json_field(text, field_name, default)`** - Extract a specific field from JSON in LLM response:

```python
from backend.core.json_utils import extract_json_field

score = extract_json_field(response, "risk_score", default=0)
```

## `sanitization.py` - Input Sanitization

### Purpose

Provides comprehensive sanitization functions to prevent:

- Command injection in shell scripts (container names)
- Path disclosure in error messages
- Metric label cardinality explosion
- Exception message information leakage
- SSRF attacks via URL validation

### Container Name Sanitization

```python
from backend.core.sanitization import sanitize_container_name

name = sanitize_container_name("my-container")  # Valid
sanitize_container_name("$(rm -rf /)")  # Raises ValueError
```

### Metric Label Sanitization

Prevents cardinality explosion in Prometheus metrics:

```python
from backend.core.sanitization import sanitize_object_class, sanitize_error_type

label = sanitize_object_class("person")  # Returns "person"
label = sanitize_object_class("unknown_class")  # Returns "other"
```

Known allowlists: `KNOWN_OBJECT_CLASSES`, `KNOWN_ERROR_TYPES`, `KNOWN_RISK_LEVELS`, `KNOWN_PIPELINE_STAGES`

### Error Sanitization

```python
from backend.core.sanitization import sanitize_error_for_response

safe_msg = sanitize_error_for_response(exception, context="processing image")
# Removes file paths, credentials, IPs from error message
```

## `time_utils.py` - UTC Time Utilities

### Purpose

Centralized time utility functions for consistent UTC handling across the codebase.

### Functions

```python
from backend.core.time_utils import utc_now, utc_now_naive

# Timezone-aware datetime (for DateTime(timezone=True) columns)
now = utc_now()

# Naive datetime (for DateTime(timezone=False) columns in PostgreSQL)
now_naive = utc_now_naive()
```

## `url_validation.py` - SSRF Protection

### Purpose

Secure URL validation to prevent Server-Side Request Forgery (SSRF) attacks. Provides comprehensive protection against various SSRF attack vectors including private IP access, cloud metadata endpoint access, and DNS rebinding attacks.

### Features

- Only HTTPS allowed in production (HTTP for localhost in dev)
- Private IP ranges blocked (RFC 1918: 10.x, 172.16-31.x, 192.168.x)
- Loopback addresses blocked (127.x.x.x)
- Link-local addresses blocked (169.254.x.x)
- Carrier-Grade NAT blocked (100.64.0.0/10)
- Cloud metadata endpoints blocked (169.254.169.254, AWS ECS, Azure IMDS)
- IPv6 private ranges blocked (::1, fe80::/10, fc00::/7)
- DNS resolution to validate resolved IPs (prevents DNS rebinding)
- Embedded credentials in URLs blocked

### Key Components

**Exception:**

- `SSRFValidationError` - Raised when URL fails SSRF validation (does NOT inherit from ValueError to avoid accidental catching)

**Blocked Network Constants:**

- `BLOCKED_IP_NETWORKS` - List of ipaddress.ip_network objects for all blocked ranges
- `BLOCKED_IPS` - Set of specific IPs to always block (cloud metadata endpoints)
- `BLOCKED_HOSTNAMES` - Set of hostnames to block (e.g., "metadata.google.internal")

**Helper Functions:**

- `is_private_ip(ip_str)` - Check if IP is in private/reserved range
- `is_blocked_ip(ip_str)` - Check if IP is specifically blocked (metadata endpoints)
- `is_blocked_hostname(hostname)` - Check if hostname is in blocked list
- `resolve_hostname(hostname)` - Resolve hostname to IP addresses

### Main Functions

**`validate_webhook_url(url, *, allow_dev_http=False, resolve_dns=True)`**

Primary validation function for webhook URLs:

```python
from backend.core.url_validation import validate_webhook_url, SSRFValidationError

try:
    validated_url = validate_webhook_url("https://example.com/webhook")
except SSRFValidationError as e:
    logger.error(f"Invalid webhook URL: {e}")

# Dev mode allows localhost HTTP
validate_webhook_url("http://localhost:8080/hook", allow_dev_http=True)

# Skip DNS resolution (for configuration-time validation only)
validate_webhook_url("https://example.com/hook", resolve_dns=False)
```

**`validate_webhook_url_for_request(url, *, is_development=False)`**

Stricter validation for use immediately before making HTTP requests. Always resolves DNS to prevent DNS rebinding attacks:

```python
from backend.core.url_validation import validate_webhook_url_for_request

# Use at request time to catch DNS rebinding
validated = validate_webhook_url_for_request(
    "https://webhook.example.com/notify",
    is_development=False
)
```

### Security Considerations

1. **DNS Rebinding Protection:** When `resolve_dns=True`, the hostname is resolved and all resolved IPs are checked against blocked ranges. Use `validate_webhook_url_for_request` at request time.

2. **Embedded Credentials:** URLs with username:password@ are rejected to prevent credential leaks.

3. **Scheme Validation:** Only http:// and https:// are allowed; exotic schemes like file://, gopher://, etc. are blocked.

4. **IPv6 Support:** Both IPv4 and IPv6 private ranges are blocked.

## `websocket_circuit_breaker.py` - WebSocket Resilience

### Purpose

Circuit breaker pattern for WebSocket connections in broadcasters, providing graceful degradation when connections are unreliable.

### States

- `CLOSED` - Normal operation, WebSocket operations proceed
- `OPEN` - Too many failures, operations blocked to allow recovery
- `HALF_OPEN` - Testing recovery, limited operations allowed

### Usage

```python
from backend.core.websocket_circuit_breaker import WebSocketCircuitBreaker

breaker = WebSocketCircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    name="event_broadcaster"
)

if breaker.is_call_permitted():
    try:
        await websocket_operation()
        breaker.record_success()
    except Exception:
        breaker.record_failure()
else:
    # Handle degraded mode
    pass
```

## `docker_client.py` - Docker/Podman Container Management

### Purpose

Provides an async wrapper around docker-py for managing Docker/Podman containers. All blocking docker-py calls are run in a thread pool using `asyncio.to_thread()` to make them non-blocking for async web frameworks.

### Features

- Async wrapper around docker-py for non-blocking container operations
- Support for both Docker and Podman (they use the same API)
- Graceful error handling for DockerException and NotFound errors
- Proper logging for all operations
- Context manager support for automatic cleanup

### Key Class: `DockerClient`

**Initialization:**

```python
from backend.core.docker_client import DockerClient

# Using default Docker socket (from environment or standard location)
client = DockerClient()

# Using custom Docker host
client = DockerClient(docker_host="unix:///var/run/docker.sock")

# Using Podman socket
client = DockerClient(docker_host="unix:///run/user/1000/podman/podman.sock")

# Using TCP connection
client = DockerClient(docker_host="tcp://192.168.1.100:2375")
```

### Methods

**Connection Management:**

- `connect() -> bool` - Test connection to Docker daemon, returns True if successful
- `close()` - Close the Docker client connection

**Container Discovery:**

- `list_containers(all=True) -> list[Container]` - List containers (all or running only)
- `get_container(container_id) -> Container | None` - Get container by ID
- `get_container_by_name(name) -> Container | None` - Get container by name pattern

**Container Lifecycle:**

- `start_container(container_id) -> bool` - Start a stopped container
- `stop_container(container_id, timeout=10) -> bool` - Stop a running container
- `restart_container(container_id, timeout=10) -> bool` - Restart a container

**Container Operations:**

- `exec_run(container_id, cmd, timeout=5) -> int` - Execute command, return exit code
- `get_container_status(container_id) -> str | None` - Get status (running, exited, etc.)

### Usage Examples

**Context Manager (Recommended):**

```python
from backend.core.docker_client import DockerClient

async with DockerClient() as client:
    # List all containers
    containers = await client.list_containers()
    for container in containers:
        print(f"{container.name}: {container.status}")

    # Get specific container status
    status = await client.get_container_status("my-container")
    if status == "running":
        # Execute health check
        exit_code = await client.exec_run("my-container", "curl localhost:8080/health")
        print(f"Health check exit code: {exit_code}")
```

**Manual Connection Management:**

```python
from backend.core.docker_client import DockerClient

client = DockerClient()
connected = await client.connect()

if connected:
    try:
        # Restart a container
        success = await client.restart_container("my-app", timeout=30)
        if success:
            print("Container restarted successfully")
    finally:
        await client.close()
```

**Container Health Monitoring:**

```python
from backend.core.docker_client import DockerClient

async def check_container_health(container_name: str) -> bool:
    """Check if a container is running and healthy."""
    async with DockerClient() as client:
        container = await client.get_container_by_name(container_name)
        if container is None:
            return False

        status = await client.get_container_status(container.id)
        return status == "running"
```

### Error Handling

All methods handle Docker errors gracefully:

- `NotFound` exceptions return None or False (expected case, logged at DEBUG)
- `DockerException` and `APIError` are logged at WARNING/ERROR level and return None/False/[]
- The client never raises exceptions for container operations (fail-safe)

### Podman Compatibility

The client works with Podman since it implements the Docker API:

```python
# For rootless Podman
client = DockerClient(docker_host="unix:///run/user/1000/podman/podman.sock")

# For rootful Podman
client = DockerClient(docker_host="unix:///var/run/podman/podman.sock")
```

## Dependency Injection Patterns

### FastAPI Route Dependencies

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core import get_db, get_redis
from backend.core.redis import RedisClient

router = APIRouter()

@router.get("/example")
async def example_route(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    # Database operations
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()

    # Redis operations
    await redis.publish("updates", {"type": "example"})

    return {"cameras": len(cameras)}
```

### Service Dependencies

Services can use context managers directly:

```python
from backend.core import get_session, init_redis

async def my_background_task():
    # Database
    async with get_session() as session:
        result = await session.execute(select(Event))
        events = result.scalars().all()

    # Redis
    redis = await init_redis()
    await redis.publish("channel", {"events": len(events)})
```

## Testing

Core modules have comprehensive unit tests in `backend/tests/unit/`:

- `test_config.py` - Settings loading and validation
- `test_database.py` - Database initialization, sessions, transactions
- `test_docker_client.py` - Docker/Podman client operations, async behavior
- `test_redis.py` - Redis operations, serialization, error handling
- `test_logging.py` - Logging setup, handlers, context propagation

Run with:

```bash
pytest backend/tests/unit/ -v
```

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/models/AGENTS.md` - Database model documentation
- `/backend/services/AGENTS.md` - Service layer documentation
