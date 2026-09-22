# Chaos Testing Suite

This directory contains chaos engineering tests that validate system resilience under failure conditions.

## Overview

Chaos tests inject faults into system components to ensure graceful degradation and proper error handling. Each test file mocks a dependency directly (`unittest.mock.AsyncMock` side effects) around the real resilience components, then asserts the system degrades and recovers correctly:

- **Service failures**: Nemotron LLM, database, Redis
- **Network issues**: Latency, DNS failure, timeouts
- **Worker failures**: crash mid-task, timeout, restart recovery

## Test Organization

84 tests total, measured by `uv run pytest backend/tests/chaos/ --collect-only -q` (2026-09-22). All tests carry `@pytest.mark.chaos` (marker registered in `backend/tests/conftest.py`).

| Test File                    | Tests  | Focus Area                                         |
| ---------------------------- | ------ | -------------------------------------------------- |
| `test_database_failures.py`  | 16     | PostgreSQL unavailable / slow / intermittent       |
| `test_redis_failures.py`     | 15     | Redis cache/queue failures, fallback queue         |
| `test_nemotron_failures.py`  | 18     | Nemotron LLM timeouts, connection errors, bad JSON |
| `test_network_conditions.py` | 15     | Network latency and reliability                    |
| `test_worker_chaos.py`       | 20     | Worker crash and queue scenarios (NEM-2464)        |
| **Total**                    | **84** |                                                    |

There is no `conftest.py` in this directory and there was never a `FaultInjector` class here. The old fault-injection framework and six additional test files (yolo26, ftp, gpu-runtime, pool-exhaustion, timeout-cascade, pubsub) were deleted in commit 978bb04c. See `AGENTS.md` in this directory for the same table plus patterns.

## Running Chaos Tests

### Safe Execution

Chaos tests are safe to run in development environments. They use mocking and fault injection to simulate failures without touching real services.

```bash
# Run all chaos tests serially (the suite is xdist-unsafe — see below)
uv run pytest backend/tests/chaos/ -v -m chaos -n0

# Run one file
uv run pytest backend/tests/chaos/test_redis_failures.py -v -m chaos -n0
```

**Run serially.** `pyproject.toml` addopts enable xdist (`-n 8 --dist=worksteal`); this suite is xdist-unsafe by its own conftest-era "deadlock" docs (see the R-T7-POISON-CASCADE note in `scripts/validate.sh`), and a serial full-suite run was still unfinished after 10 minutes when measured on 2026-09-22 — individual files are the practical unit of work.

### Test Markers

All chaos tests carry `@pytest.mark.chaos`, so you can include or exclude them from a wider run:

```bash
# Run only chaos tests
uv run pytest -m chaos backend/tests/ -n0

# Run everything except chaos
uv run pytest -m "not chaos" backend/tests/
```

### Not Run by Default

Chaos tests are **not collected by the standard validation loop or CI**:

- `scripts/validate.sh` passes `--ignore=$PROJECT_ROOT/backend/tests/chaos` on both its unit and integration pytest runs.
- `.github/workflows/nightly-full-gate.yml` passes `--ignore=backend/tests/chaos` on every lane; no PR-gate workflow collects this directory either.

Run them manually before merging changes to the circuit breaker, degradation manager, or pipeline workers.

## What the Tests Exercise

There is no fault-injection framework to import. A test builds its fault inline — either by mocking an HTTP/Redis boundary or by driving the real resilience component with a failing callable:

```python
# Mock a service boundary (from test_nemotron_failures.py)
analyzer = NemotronAnalyzer()


async def timeout(*args, **kwargs):
    raise httpx.TimeoutException("Health check timeout")


with patch("httpx.AsyncClient.get", side_effect=timeout):
    result = await analyzer.health_check()
    assert result is False
```

```python
# Drive the real circuit breaker with a failing operation
config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0)
breaker = CircuitBreaker(name="nemotron_connection_test", config=config)


async def connection_error():
    raise httpx.ConnectError("Nemotron unreachable")


for _ in range(config.failure_threshold):
    try:
        await breaker.call(connection_error)
    except httpx.ConnectError:
        pass

assert breaker.state == CircuitState.OPEN
```

Components under test:

- `backend/services/circuit_breaker.py` — `CircuitBreaker` / `CircuitBreakerConfig` (defaults: `failure_threshold=5`, `recovery_timeout=30.0`)
- `backend/services/degradation_manager.py` — `DegradationManager`, `FallbackQueue`
- `backend/core/redis.py` — `RedisClient` (mocked, with `QueueAddResult`)

Each module has an autouse fixture calling `reset_degradation_manager()` or `reset_circuit_breaker_registry()` — both components are process-wide singletons, so new chaos test files must reset them the same way.

## Expected Behaviors

### Graceful Degradation

When services fail, the system should:

1. **Return degraded responses** instead of crashing
2. **Log errors appropriately** with context
3. **Open circuit breakers** after repeated failures
4. **Fall back to the on-disk FallbackQueue** when Redis or the database is down

### Circuit Breaker States

Tests verify circuit breaker transitions (`CircuitState` in `backend/services/circuit_breaker.py`):

```
CLOSED → OPEN (after failure_threshold failures)
OPEN → HALF_OPEN (after recovery_timeout)
HALF_OPEN → CLOSED (after success_threshold successes)
HALF_OPEN → OPEN (on failure in half-open state)
```

### Degradation Modes

Tests verify degradation manager modes (`DegradationMode` in `backend/services/degradation_manager.py`):

```
NORMAL → DEGRADED (non-critical service down)
DEGRADED → MINIMAL (critical service down)
MINIMAL → OFFLINE (all critical services down)
Recovery transitions back to NORMAL
```

The fallback queue is a `DegradationManager` method pair, not free functions: `manager.should_queue_job(job_type)` decides, `manager.queue_job_for_later(...)` enqueues, and `manager.get_queued_job_count()` reports depth.

## When to Run

Run chaos tests:

- **Before merging** major resilience changes
- **After modifying** circuit breaker or degradation manager
- **When adding** new external service dependencies
- **During incident** response to verify fixes

## Troubleshooting

### Tests Failing with Environment Errors

If you see validation errors about weak passwords, run first-time setup (`python setup.py` at repo root generates `.env`) or point the config loader at a development env file:

```bash
# config.py reads HSI_RUNTIME_ENV_PATH, default "./data/runtime.env"
export HSI_RUNTIME_ENV_PATH=./data/runtime.env
uv run pytest backend/tests/chaos/test_redis_failures.py -v -m chaos -n0
```

### Tests Timing Out

Some chaos tests intentionally inject delays, and `pyproject.toml` sets a global `timeout = 5` (seconds). Raise it for a chaos run:

```bash
uv run pytest backend/tests/chaos/ -v -m chaos -n0 --timeout=60
```

### Flaky Tests

Chaos tests involve timing-sensitive operations. If tests are flaky:

1. **Run with `-n0`** — the suite is not parallel-safe under xdist
2. **Check system load** — high CPU causes timing issues
3. **Review logs** — use `-v --tb=long` for detailed output

## Adding New Chaos Tests

1. Follow the per-file pattern: import the real component, build faults with `AsyncMock`/`patch`, no shared fixture framework to create.
2. Name the file `test_<service>_failures.py` (or a scenario name).
3. Mark every test with `@pytest.mark.chaos` and `@pytest.mark.asyncio` (or set `pytestmark = [pytest.mark.asyncio, pytest.mark.chaos]` at module level, like `test_worker_chaos.py`).
4. Add an autouse fixture resetting the singletons your file touches.
5. Document expected behavior in the test docstring and test both failure AND recovery paths:

```python
@pytest.mark.chaos
@pytest.mark.asyncio
async def test_service_recovery(self) -> None:
    """Recovery closes the circuit breaker and returns mode to NORMAL."""
    # ... simulate recovery
    assert breaker.state == CircuitState.CLOSED
    assert manager.mode == DegradationMode.NORMAL
```

## Related Documentation

- `AGENTS.md` (this directory) - chaos test patterns and CI status
- `/backend/services/circuit_breaker.py` - circuit breaker implementation
- `/backend/services/degradation_manager.py` - graceful degradation manager
- `/backend/core/redis.py` - Redis client with retry logic
- `/backend/tests/AGENTS.md` - overall test documentation

## References

- **Linear Issue**: NEM-3153 - Chaos Testing Suite
- **Related Issues**:
  - NEM-2097 - External service chaos testing
  - NEM-2464 - Worker chaos scenarios
