# Root Tests Directory - Agent Guide

## Purpose

Auxiliary test suites that run outside the backend/frontend trees: model benchmarks (pytest), K6 load tests, and deployment smoke tests. The old root `test_setup.py` / `test_setup_core.py` were retired to `archive/` — setup-script coverage now lives in `backend/tests/unit/`.

**Main test suites are elsewhere:**

- `backend/tests/` - Backend unit and integration tests (pytest)
- `frontend/tests/e2e/` - Frontend E2E tests (Playwright)
- `frontend/src/**/*.test.ts` - Frontend component tests (Vitest)

## Directory Contents

| Suite        | Purpose                                                        | How to run                          |
| ------------ | -------------------------------------------------------------- | ----------------------------------- |
| `benchmark/` | AI model benchmark tests (engine comparison, quality, metrics) | `uv run pytest tests/benchmark/ -v` |
| `load/`      | K6 load-test scripts (cameras, events, WebSocket, Redis)       | `k6 run tests/load/<script>.js`     |
| `smoke/`     | Post-deployment smoke tests (health, monitoring, WebSocket)    | `uv run pytest tests/smoke/ -v`     |

Each suite has its own `README.md`; `benchmark/` and `load/` have their own `AGENTS.md` with details.

## Patterns

- **Smoke tests need a running stack** - `tests/smoke/` hits live endpoints (`/api/system/health`, Grafana, WebSocket); run only after `docker compose up`.
- **K6 scripts are config-driven** - endpoints/thresholds come from `load/config.js`; `all.js` is the combined suite.
- **`tests/unit/` is vestigial** - only a gitignored `__pycache__` remains from the retired root setup-script tests; do not add new tests there.

## Related Documentation

- **backend/tests/AGENTS.md:** Backend test infrastructure
- **frontend/tests/e2e/:** E2E test documentation
- **docs/developer/testing.md:** Comprehensive testing guide
- **AGENTS.md:** TDD requirements and testing policy
