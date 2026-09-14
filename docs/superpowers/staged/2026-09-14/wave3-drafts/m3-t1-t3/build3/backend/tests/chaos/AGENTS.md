# Chaos Testing Directory

## Purpose

This directory contains chaos engineering tests that verify graceful degradation when system components fail. These tests inject faults into services to ensure the system remains functional (even if degraded) during outages.

## Directory Structure

```
backend/tests/chaos/
├── __init__.py                        # Module documentation
├── conftest.py                        # Fault injection framework and fixtures
├── test_yolo26_failures.py            # YOLO26 object detection service failures
├── test_redis_failures.py             # Redis cache/queue service failures
├── test_database_failures.py          # PostgreSQL database failures
├── test_nemotron_failures.py          # Nemotron LLM service failures
├── test_network_conditions.py         # Network latency and reliability issues
├── test_ftp_failures.py               # FTP upload and file system failures (18 tests)
├── test_gpu_runtime_failures.py       # GPU runtime and CUDA errors (18 tests)
├── test_database_pool_exhaustion.py   # Database connection pool exhaustion (20 tests)
├── test_timeout_cascade.py            # Cascading timeout scenarios (19 tests)
├── test_pubsub_failures.py            # Redis pub/sub failures (17 tests)
└── AGENTS.md                          # This documentation
```

## Running Chaos Tests

```bash
# Run all chaos tests
uv run pytest backend/tests/chaos/ -v -m chaos

# Run specific service failure tests
uv run pytest backend/tests/chaos/test_yolo26_failures.py -v
uv run pytest backend/tests/chaos/test_redis_failures.py -v
uv run pytest backend/tests/chaos/test_database_failures.py -v
uv run pytest backend/tests/chaos/test_nemotron_failures.py -v
uv run pytest backend/tests/chaos/test_network_conditions.py -v

# Run external service failure tests (NEM-2097)
uv run pytest backend/tests/chaos/test_ftp_failures.py -v
uv run pytest backend/tests/chaos/test_gpu_runtime_failures.py -v
uv run pytest backend/tests/chaos/test_database_pool_exhaustion.py -v
uv run pytest backend/tests/chaos/test_timeout_cascade.py -v
uv run pytest backend/tests/chaos/test_pubsub_failures.py -v

# Run with verbose output for debugging
uv run pytest backend/tests/chaos/ -v --tb=long
```

## Fault Injection Framework

### FaultInjector Class

The `FaultInjector` class provides centralized fault management:

```python
from backend.tests.chaos.conftest import FaultInjector, FaultConfig, FaultType

# Create injector
injector = FaultInjector()

# Inject a fault
injector.inject("yolo26", FaultConfig(
    fault_type=FaultType.TIMEOUT,
    delay_seconds=30.0
))

# Check if fault is active
if injector.is_active("yolo26"):
    # Handle degraded path
    pass

# Check statistics
stats = injector.get_stats("yolo26")
print(f"Faults injected: {stats.faults_injected}")

# Clear all faults
injector.clear()
```

### Fault Types

| Fault Type         | Description                                  |
| ------------------ | -------------------------------------------- |
| `TIMEOUT`          | Service doesn't respond within expected time |
| `CONNECTION_ERROR` | Cannot establish connection to service       |
| `SERVER_ERROR`     | Service returns 5xx HTTP errors              |
| `INTERMITTENT`     | Random failures with configurable rate       |
| `LATENCY`          | Artificial delay added to operations         |
| `UNAVAILABLE`      | Service completely unreachable               |

### Available Fixtures

#### YOLO26 Fixtures

| Fixture                   | Description                       |
| ------------------------- | --------------------------------- |
| `yolo26_timeout`          | YOLO26 hangs then times out       |
| `yolo26_connection_error` | YOLO26 is unreachable             |
| `yolo26_server_error`     | YOLO26 returns HTTP 500           |
| `yolo26_intermittent`     | 50% of YOLO26 calls fail randomly |

#### Redis Fixtures

| Fixture              | Description                  |
| -------------------- | ---------------------------- |
| `redis_unavailable`  | Redis connection refused     |
| `redis_timeout`      | Redis operations timeout     |
| `redis_intermittent` | 30% of Redis operations fail |

#### Database Fixtures

| Fixture                 | Description                   |
| ----------------------- | ----------------------------- |
| `database_unavailable`  | PostgreSQL connection refused |
| `database_slow`         | 2s latency added to queries   |
| `database_intermittent` | 20% of queries fail           |

#### Nemotron Fixtures

| Fixture                       | Description              |
| ----------------------------- | ------------------------ |
| `nemotron_timeout`            | LLM inference times out  |
| `nemotron_unavailable`        | LLM service unreachable  |
| `nemotron_malformed_response` | LLM returns invalid JSON |

#### Network Fixtures

| Fixture        | Description                   |
| -------------- | ----------------------------- |
| `high_latency` | 500ms added to all HTTP calls |
| `packet_loss`  | 10% of requests fail randomly |

#### Compound Fixtures

| Fixture                | Description                     |
| ---------------------- | ------------------------------- |
| `all_ai_services_down` | YOLO26 and Nemotron unavailable |
| `cache_and_ai_down`    | Redis and YOLO26 unavailable    |

## Test Patterns

### Testing Circuit Breaker Behavior

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_circuit_opens_after_failures(fault_injector):
    config = CircuitBreakerConfig(failure_threshold=3)
    breaker = CircuitBreaker(name="test", config=config)

    async def failing_op():
        raise TimeoutError()

    # Trigger failures
    for _ in range(config.failure_threshold):
        try:
            await breaker.call(failing_op)
        except TimeoutError:
            pass

    assert breaker.state == CircuitState.OPEN
```

### Testing Degradation Manager

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_degradation_mode_transitions():
    manager = DegradationManager(failure_threshold=2)

    manager.register_service(
        name="redis",
        health_check=AsyncMock(return_value=True),
        critical=True
    )

    # Simulate failures
    await manager.update_service_health("redis", is_healthy=False)
    await manager.update_service_health("redis", is_healthy=False)

    assert manager.mode == DegradationMode.DEGRADED
```

### Testing Fallback Behavior

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_fallback_queue_on_redis_failure(redis_unavailable):
    manager = DegradationManager(redis_client=mock_redis)

    # Should fall back to memory queue
    success = await manager.queue_job_for_later("detection", {"data": "test"})

    assert success is True
    assert manager.get_queued_job_count() > 0
```

## Expected Behaviors

### Service Failures

| Service    | Fault Type       | Expected Behavior                        |
| ---------- | ---------------- | ---------------------------------------- |
| YOLO26     | Timeout          | Return empty detections, log warning     |
| YOLO26     | 5xx Error        | Circuit breaker opens, fallback to queue |
| Redis      | Connection Error | Fall back to in-memory cache             |
| Redis      | Timeout          | Skip caching, proceed without            |
| PostgreSQL | Connection Error | Return 503, health degraded              |
| PostgreSQL | Slow Queries     | Return cached data if available          |
| Nemotron   | Timeout          | Return default risk score                |

### Network Conditions

| Condition       | Expected Behavior                             |
| --------------- | --------------------------------------------- |
| High Latency    | Operations succeed with longer response times |
| Packet Loss     | Retries handle intermittent failures          |
| DNS Failure     | Treated as connection error                   |
| Pool Exhaustion | Circuit breaker opens                         |

## Integration with Existing Components

### Circuit Breaker (`backend/services/circuit_breaker.py`)

The chaos tests verify circuit breaker state transitions:

- CLOSED -> OPEN (after failure threshold)
- OPEN -> HALF_OPEN (after recovery timeout)
- HALF_OPEN -> CLOSED (after success threshold)
- HALF_OPEN -> OPEN (on failure in half-open)

### Degradation Manager (`backend/services/degradation_manager.py`)

The chaos tests verify degradation modes:

- NORMAL -> DEGRADED (non-critical service down)
- DEGRADED -> MINIMAL (critical service down)
- MINIMAL -> OFFLINE (all critical services down)
- Recovery transitions back to NORMAL

### Fallback Mechanisms

The chaos tests verify fallback behaviors:

- Redis down -> Memory queue
- Memory queue full -> Disk-based queue
- Queue overflow -> DLQ or drop oldest

## CI Integration

Chaos tests are included in the standard test suite but can be run separately:

```yaml
# In CI configuration
chaos-tests:
  runs-on: ubuntu-latest
  steps:
    - run: uv run pytest backend/tests/chaos/ -v -m chaos
```

## External Service Failure Tests (NEM-2097)

### FTP Failures (`test_ftp_failures.py`)

Tests for FTP upload and file system issues (18 tests):

- **Upload Timeout**: FTP upload timeout moves files to DLQ for retry
- **Incomplete Upload**: Partial file writes detected via validation
- **Corrupted Files**: Invalid JPEG/MP4 files handled gracefully
- **Disk Full**: Disk space errors logged and alerted
- **Permission Denied**: Read/write permission errors handled without crash
- **File Deleted**: Files deleted mid-processing don't cause infinite retry
- **Invalid Format**: Unsupported file extensions skipped
- **Oversized Files**: Files exceeding size limit rejected
- **Concurrent Conflicts**: Duplicate file hash prevents reprocessing

**Expected Behavior**: File watcher remains stable, DLQ absorbs failures, no data loss

### GPU Runtime Failures (`test_gpu_runtime_failures.py`)

Tests for GPU and CUDA failures (18 tests):

- **GPU Unavailable**: Driver crash mid-inference falls back to queue
- **VRAM Exhaustion**: CUDA OOM triggers batch size reduction
- **Thermal Throttle**: High GPU temperature triggers inference pause
- **Context Corruption**: CUDA context corruption triggers service restart
- **Model Loading**: Corrupted model files trigger redownload
- **Inference Timeout**: Timeouts retry with exponential backoff
- **No GPU**: Missing GPU falls back to CPU inference
- **Batch Processing**: Partial batch failures process successful items

**Expected Behavior**: Circuit breaker opens after repeated failures, degradation mode activated

### Database Pool Exhaustion (`test_database_pool_exhaustion.py`)

Tests for connection pool exhaustion (20 tests):

- **Pool Exhaustion**: 50 concurrent queries with pool of 5 queue properly
- **Pool Timeout**: Timeout exceeded triggers clear error message
- **Connection Leaks**: Unclosed connections detected and logged
- **Long Queries**: Queries cancelled after statement timeout
- **Pool Recycling**: Stale connections recycled on checkout
- **Max Overflow**: Overflow connections created under pressure
- **Connection Refused**: Connection failures logged and alerted
- **Connection Lost**: Mid-transaction loss triggers rollback
- **Deadlock Detection**: Deadlocks detected and retried
- **Transaction Timeout**: Long transactions timeout and rollback

**Expected Behavior**: System remains responsive, connection leaks prevented, graceful errors

### Timeout Cascade (`test_timeout_cascade.py`)

Tests for cascading timeout scenarios (19 tests):

- **Detection→Enrichment**: Detection timeout creates degraded event
- **DB+Redis Cascade**: Combined timeouts activate circuit breaker
- **API Propagation**: API timeouts send notifications to WebSocket clients
- **Batch Cascade**: Batch timeout doesn't delay next batch
- **Dependent Services**: Timeout in one service delays dependent services
- **Timeout Storm**: Multiple simultaneous timeouts open circuit breaker
- **Degraded Mode**: Cascading timeouts trigger degraded mode
- **Recovery Time**: Slow recovery logged for monitoring

**Expected Behavior**: Timeouts don't cascade indefinitely, degraded events created, system remains stable

### Pub/Sub Failures (`test_pubsub_failures.py`)

Tests for Redis pub/sub failures (17 tests):

- **Disconnect**: Disconnect during broadcast triggers retry and reconnection
- **Message Loss**: Zero subscribers detected and logged
- **Reconnection**: Subscribers reconnect and resubscribe to all channels
- **Subscription Failures**: Invalid channels fail gracefully
- **Publish Fallback**: Failed publish falls back to direct WebSocket
- **Race Conditions**: Concurrent subscriptions handled correctly

**Expected Behavior**: Automatic reconnection, message loss logged, WebSocket connections remain stable

## Test Coverage Summary

| Test Suite               | Tests  | Focus Areas                              |
| ------------------------ | ------ | ---------------------------------------- |
| FTP Failures             | 18     | Upload timeouts, corruption, disk issues |
| GPU Runtime Failures     | 18     | VRAM, thermal, CUDA errors               |
| Database Pool Exhaustion | 20     | Connection pool, leaks, timeouts         |
| Timeout Cascade          | 19     | Cascading failures, degradation          |
| Pub/Sub Failures         | 17     | Redis pub/sub, reconnection              |
| **Total New Tests**      | **92** | **External service chaos scenarios**     |

## Adding New Chaos Tests

1. Create fixture in `conftest.py` if new fault type needed
2. Add test file following naming convention `test_<service>_failures.py`
3. Use `@pytest.mark.chaos` marker for all chaos tests
4. Test both failure behavior AND recovery behavior
5. Verify circuit breaker states are correct
6. Document expected behavior in test docstrings

## Related Documentation

- `/backend/services/circuit_breaker.py` - Circuit breaker implementation
- `/backend/services/degradation_manager.py` - Graceful degradation manager
- `/backend/core/redis.py` - Redis client with retry logic
- `/backend/tests/AGENTS.md` - Overall test documentation
- `NEM-2097` - External service chaos testing implementation
