# Chaos Testing Directory - Agent Guide

## Purpose

Chaos engineering tests that verify graceful degradation when system components fail: fault injection against the circuit breaker, degradation manager, and pipeline workers, asserting the system stays functional (degraded) during outages.

## Key Files

All tests carry `@pytest.mark.chaos` (marker registered in `backend/tests/conftest.py`); counts are `def test_` measured.

| File                          | Tests | Focus                                                       |
| ----------------------------- | ----- | ----------------------------------------------------------- |
| `test_database_failures.py`   | 16    | PostgreSQL unavailable / slow / intermittent failures       |
| `test_redis_failures.py`      | 15    | Redis unavailable -> fallback queue + in-memory degradation |
| `test_nemotron_failures.py`   | 18    | LLM timeouts / malformed responses -> circuit breaker open  |
| `test_network_conditions.py`  | 15    | Latency, packet loss, DNS failure handling                  |
| `test_worker_chaos.py`        | 20    | Worker crash mid-task, timeout, restart recovery (NEM-2464) |

## Running

```bash
uv run pytest backend/tests/chaos/ -v -m chaos
uv run pytest backend/tests/chaos/test_redis_failures.py -v -m chaos
```

## Patterns and Gotchas

- **There is NO fault-injection framework here anymore.** The old `conftest.py` with `FaultInjector`/`FaultConfig` and six extra test files (ftp, gpu-runtime, pool-exhaustion, timeout-cascade, pubsub, yolo26) were deleted in 978bb04c. Each file injects faults directly with `unittest.mock.AsyncMock` side effects around the real resilience components.
- Components under test: `backend/services/circuit_breaker.py` (CLOSED/OPEN/HALF_OPEN transitions) and `backend/services/degradation_manager.py` (NORMAL/DEGRADED/MINIMAL/OFFLINE modes + fallback queue). Each module has an autouse fixture calling `reset_degradation_manager()` / `reset_circuit_breaker_registry()` - always reset these singletons in new tests.
- **CI never collects this directory**: `.github/workflows/nightly-full-gate.yml` explicitly `--ignore`s it and no PR-gate job collects chaos. Treat it as a locally-run suite (see the R-T7-POISON-CASCADE note in `scripts/validate.sh`: the suite is xdist-unsafe, run it serially with `-n0` if you wire it into a lane).
- Test both failure behavior AND recovery behavior; document expected behavior in the test docstring (the existing files do).

## Related

- `/backend/services/circuit_breaker.py` - circuit breaker implementation
- `/backend/services/degradation_manager.py` - graceful degradation manager
- `/backend/tests/AGENTS.md` - overall test documentation
