# Chaos Testing Suite

This directory contains chaos engineering tests that validate system resilience under failure conditions.

## Overview

Chaos tests inject faults into system components to ensure graceful degradation and proper error handling. These tests simulate real-world failure scenarios including:

- **Service failures**: AI services (RT-DETR, Nemotron), database, Redis
- **Network issues**: Latency, packet loss, timeouts
- **Resource exhaustion**: Connection pool exhaustion, VRAM exhaustion, disk full
- **Runtime errors**: GPU failures, file corruption, permission errors

## Test Organization

| Test File                          | Tests    | Focus Area                         |
| ---------------------------------- | -------- | ---------------------------------- |
| `test_rtdetr_failures.py`          | 14       | RT-DETR detection service failures |
| `test_redis_failures.py`           | ~15      | Redis cache/queue failures         |
| `test_database_failures.py`        | 20+      | PostgreSQL database failures       |
| `test_nemotron_failures.py`        | 15+      | Nemotron LLM service failures      |
| `test_network_conditions.py`       | 10+      | Network latency and reliability    |
| `test_ftp_failures.py`             | 18       | FTP upload and file system issues  |
| `test_gpu_runtime_failures.py`     | 18       | GPU and CUDA runtime errors        |
| `test_database_pool_exhaustion.py` | 20       | Connection pool exhaustion         |
| `test_timeout_cascade.py`          | 19       | Cascading timeout scenarios        |
| `test_pubsub_failures.py`          | 17       | Redis pub/sub failures             |
| `test_worker_chaos.py`             | 30+      | Worker crash and queue scenarios   |
| **Total**                          | **189+** | **Comprehensive chaos coverage**   |

## Running Chaos Tests

### Safe Execution

**IMPORTANT**: Chaos tests are safe to run in development environments. They use mocking and fault injection to simulate failures without affecting real services.

```bash
# Run all chaos tests
uv run pytest backend/tests/chaos/ -v -m chaos

# Run specific service failure tests
uv run pytest backend/tests/chaos/test_rtdetr_failures.py -v
uv run pytest backend/tests/chaos/test_redis_failures.py -v
uv run pytest backend/tests/chaos/test_database_failures.py -v

# Run with detailed output
uv run pytest backend/tests/chaos/ -v --tb=long -m chaos
```

### Test Markers

All chaos tests are marked with `@pytest.mark.chaos`. This allows selective execution:

```bash
# Run only chaos tests
pytest -m chaos backend/tests/

# Run integration tests excluding chaos
pytest -m "integration and not chaos" backend/tests/
```

### Skipped by Default

Chaos tests are **NOT skipped by default** in the test suite. They run as part of normal test execution to ensure continuous validation of resilience patterns.

## Fault Injection Framework

### FaultInjector

The `FaultInjector` class in `conftest.py` provides centralized fault management:

```python
from backend.tests.chaos.conftest import FaultInjector, FaultConfig, FaultType

# Create injector
injector = FaultInjector()

# Inject a fault
injector.inject("rtdetr", FaultConfig(
    fault_type=FaultType.TIMEOUT,
    delay_seconds=30.0
))

# Check statistics
stats = injector.get_stats("rtdetr")
print(f"Total calls: {stats.total_calls}")
print(f"Faults injected: {stats.faults_injected}")
```

### Fault Types

| Fault Type         | Description                                  | Example Use Case        |
| ------------------ | -------------------------------------------- | ----------------------- |
| `TIMEOUT`          | Service doesn't respond within expected time | RT-DETR inference hangs |
| `CONNECTION_ERROR` | Cannot establish connection                  | Service unreachable     |
| `SERVER_ERROR`     | Service returns 5xx errors                   | Internal server error   |
| `INTERMITTENT`     | Random failures with configurable rate       | Flaky network           |
| `LATENCY`          | Artificial delay added                       | High network latency    |
| `UNAVAILABLE`      | Service completely down                      | Complete outage         |

### Pre-configured Fixtures

#### RT-DETR Service Faults

```python
@pytest.mark.chaos
async def test_detection_timeout(rtdetr_timeout):
    """Test with RT-DETR timing out (30s delay)."""
    # rtdetr_timeout fixture automatically injects fault
    ...

@pytest.mark.chaos
async def test_detection_unavailable(rtdetr_connection_error):
    """Test with RT-DETR unreachable."""
    ...
```

Available RT-DETR fixtures:

- `rtdetr_timeout` - Service times out after 30s
- `rtdetr_connection_error` - Connection refused
- `rtdetr_server_error` - Returns HTTP 500
- `rtdetr_intermittent` - 50% random failure rate

#### Redis Faults

```python
@pytest.mark.chaos
async def test_cache_failure(redis_unavailable):
    """Test with Redis completely down."""
    ...
```

Available Redis fixtures:

- `redis_unavailable` - Connection refused
- `redis_timeout` - Operations timeout after 10s
- `redis_intermittent` - 30% random failure rate

#### Database Faults

```python
@pytest.mark.chaos
async def test_db_connection_loss(database_unavailable):
    """Test with PostgreSQL down."""
    ...
```

Available database fixtures:

- `database_unavailable` - Connection refused
- `database_slow` - 2s latency on all queries
- `database_intermittent` - 20% random failure rate

#### Nemotron LLM Faults

```python
@pytest.mark.chaos
async def test_analysis_timeout(nemotron_timeout):
    """Test with Nemotron LLM timing out."""
    ...
```

Available Nemotron fixtures:

- `nemotron_timeout` - Inference times out after 120s
- `nemotron_unavailable` - Service unreachable
- `nemotron_malformed_response` - Returns invalid JSON

#### Network Condition Faults

```python
@pytest.mark.chaos
async def test_high_latency_network(high_latency):
    """Test with 500ms network latency."""
    ...
```

Available network fixtures:

- `high_latency` - 500ms delay on all HTTP calls
- `packet_loss` - 10% random connection failures

#### Compound Faults

```python
@pytest.mark.chaos
async def test_complete_ai_outage(all_ai_services_down):
    """Test with both RT-DETR and Nemotron down."""
    ...
```

Available compound fixtures:

- `all_ai_services_down` - RT-DETR + Nemotron unavailable
- `cache_and_ai_down` - Redis + RT-DETR unavailable

## Expected Behaviors

### Graceful Degradation

When services fail, the system should:

1. **Return degraded responses** instead of crashing
2. **Log errors appropriately** with context
3. **Open circuit breakers** after repeated failures
4. **Fall back to caching** when possible
5. **Queue for retry** when appropriate

### Circuit Breaker States

Tests verify circuit breaker transitions:

```
CLOSED → OPEN (after failure_threshold failures)
OPEN → HALF_OPEN (after recovery_timeout)
HALF_OPEN → CLOSED (after success_threshold successes)
HALF_OPEN → OPEN (on failure in half-open state)
```

### Degradation Modes

Tests verify degradation manager modes:

```
NORMAL → DEGRADED (non-critical service down)
DEGRADED → MINIMAL (critical service down)
MINIMAL → OFFLINE (all critical services down)
Recovery transitions back to NORMAL
```

## Test Patterns

### 1. Service Timeout

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_service_timeout_opens_circuit_breaker(self):
    """Service timeouts trigger circuit breaker."""
    config = CircuitBreakerConfig(failure_threshold=3)
    breaker = CircuitBreaker(name="test", config=config)

    async def timeout_operation():
        raise TimeoutError("Service timeout")

    # Trigger failures
    for _ in range(config.failure_threshold):
        try:
            await breaker.call(timeout_operation)
        except TimeoutError:
            pass

    assert breaker.state == CircuitState.OPEN
```

### 2. Degradation Detection

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_degradation_mode_transitions(self):
    """Critical failures trigger degradation mode."""
    manager = DegradationManager(failure_threshold=2)

    manager.register_service(
        name="database",
        health_check=AsyncMock(return_value=True),
        critical=True
    )

    # Simulate failures
    await manager.update_service_health("database", is_healthy=False)
    await manager.update_service_health("database", is_healthy=False)

    assert manager.mode in (DegradationMode.MINIMAL, DegradationMode.OFFLINE)
```

### 3. Fallback Behavior

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_fallback_to_memory_queue(redis_unavailable):
    """Falls back to memory queue when Redis unavailable."""
    # Redis unavailable fixture injects fault

    # System should use fallback mechanism
    result = await queue_job("detection", {"data": "test"})

    assert result is True
    assert get_queued_job_count() > 0
```

## Safety Considerations

### Development Environment Only

Chaos tests are designed for **development and CI environments**. They:

- Use **mocking** to simulate failures (not real service disruption)
- Run in **isolated test databases** with transaction rollback
- **Don't affect** real production services or data

### CI Integration

Chaos tests run automatically in CI pipelines:

```yaml
# GitHub Actions
- name: Run Chaos Tests
  run: uv run pytest backend/tests/chaos/ -v -m chaos
```

### When to Run

Run chaos tests:

- **Before merging** major resilience changes
- **After modifying** circuit breaker or degradation manager
- **When adding** new external service dependencies
- **During incident** response to verify fixes

## Troubleshooting

### Tests Failing with Environment Errors

If you see validation errors about weak passwords:

```bash
# Run ./setup.sh to generate secure development credentials
./setup.sh

# Or set HSI_RUNTIME_ENV_PATH to use development environment
export HSI_RUNTIME_ENV_PATH=development
uv run pytest backend/tests/chaos/ -v
```

### Tests Timing Out

Some chaos tests intentionally inject delays. Increase pytest timeout if needed:

```bash
# Disable timeouts for debugging
uv run pytest backend/tests/chaos/ -v --timeout=0

# Or increase specific timeout
uv run pytest backend/tests/chaos/ -v --timeout=60
```

### Flaky Tests

Some chaos tests involve timing-sensitive operations. If tests are flaky:

1. **Check system load** - High CPU can cause timing issues
2. **Reduce parallelism** - Run with `-n0` for serial execution
3. **Review logs** - Use `-v --tb=long` for detailed output

## Adding New Chaos Tests

1. **Create fixture** in `conftest.py` if new fault type needed:

```python
@pytest.fixture
def new_service_failure(fault_injector: FaultInjector):
    """Simulate new service failure."""
    fault_injector.inject("service", FaultConfig(
        FaultType.TIMEOUT,
        delay_seconds=30.0
    ))

    # Mock the service call
    with patch("module.service_call", side_effect=TimeoutError()):
        yield fault_injector
```

2. **Add test file** following naming convention `test_<service>_failures.py`

3. **Use markers** and docstrings:

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_service_failure_scenario():
    """Test graceful degradation when service fails.

    Expected Behavior:
    - Circuit breaker opens after threshold
    - Fallback mechanism activates
    - Errors logged appropriately
    """
    ...
```

4. **Verify recovery** behavior:

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_service_recovery():
    """Test recovery when service becomes available."""
    # Test failure
    # ... trigger failures

    # Test recovery
    # ... simulate service recovery

    assert breaker.state == CircuitState.CLOSED
    assert manager.mode == DegradationMode.NORMAL
```

## Related Documentation

- `/backend/services/circuit_breaker.py` - Circuit breaker implementation
- `/backend/services/degradation_manager.py` - Graceful degradation manager
- `/backend/core/redis.py` - Redis client with retry logic
- `/backend/tests/AGENTS.md` - Overall test documentation
- `AGENTS.md` - Chaos test directory overview

## References

- **Linear Issue**: NEM-3153 - Chaos Testing Suite
- **Related Issues**:
  - NEM-2097 - External service chaos testing
  - Circuit breaker implementation
  - Degradation manager patterns

## Summary

The chaos testing suite provides **189+ tests** covering comprehensive failure scenarios across all system components. Tests are safe to run in development, use fault injection for controlled failure simulation, and verify graceful degradation patterns including circuit breakers, fallback mechanisms, and error handling.

**All chaos tests can be run safely with:**

```bash
uv run pytest backend/tests/chaos/ -v -m chaos
```
