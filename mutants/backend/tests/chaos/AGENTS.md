# Chaos Testing Directory

## Purpose

This directory contains chaos engineering tests that verify graceful degradation when system components fail. These tests inject faults into services to ensure the system remains functional (even if degraded) during outages.

## Directory Structure

```
backend/tests/chaos/
├── __init__.py                  # Module documentation
├── conftest.py                  # Fault injection framework and fixtures
├── test_rtdetr_failures.py      # RT-DETR object detection service failures
├── test_redis_failures.py       # Redis cache/queue service failures
├── test_database_failures.py    # PostgreSQL database failures
├── test_nemotron_failures.py    # Nemotron LLM service failures
├── test_network_conditions.py   # Network latency and reliability issues
└── AGENTS.md                    # This documentation
```

## Running Chaos Tests

```bash
# Run all chaos tests
uv run pytest backend/tests/chaos/ -v -m chaos

# Run specific service failure tests
uv run pytest backend/tests/chaos/test_rtdetr_failures.py -v
uv run pytest backend/tests/chaos/test_redis_failures.py -v
uv run pytest backend/tests/chaos/test_database_failures.py -v
uv run pytest backend/tests/chaos/test_nemotron_failures.py -v
uv run pytest backend/tests/chaos/test_network_conditions.py -v

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
injector.inject("rtdetr", FaultConfig(
    fault_type=FaultType.TIMEOUT,
    delay_seconds=30.0
))

# Check if fault is active
if injector.is_active("rtdetr"):
    # Handle degraded path
    pass

# Check statistics
stats = injector.get_stats("rtdetr")
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

#### RT-DETR Fixtures

| Fixture                   | Description                        |
| ------------------------- | ---------------------------------- |
| `rtdetr_timeout`          | RT-DETR hangs then times out       |
| `rtdetr_connection_error` | RT-DETR is unreachable             |
| `rtdetr_server_error`     | RT-DETR returns HTTP 500           |
| `rtdetr_intermittent`     | 50% of RT-DETR calls fail randomly |

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

| Fixture                | Description                      |
| ---------------------- | -------------------------------- |
| `all_ai_services_down` | RT-DETR and Nemotron unavailable |
| `cache_and_ai_down`    | Redis and RT-DETR unavailable    |

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
| RT-DETR    | Timeout          | Return empty detections, log warning     |
| RT-DETR    | 5xx Error        | Circuit breaker opens, fallback to queue |
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
