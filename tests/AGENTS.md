# Root Tests Directory - Agent Guide

## Purpose

This directory contains tests for root-level scripts, specifically the interactive setup script (`setup.py`) and its supporting library (`setup_lib/`). These tests verify the configuration generation and system setup functionality.

**Note:** The main test suites are located in:

- `backend/tests/` - Backend unit and integration tests (pytest)
- `frontend/tests/e2e/` - Frontend E2E tests (Playwright)
- `frontend/src/**/*.test.ts` - Frontend component tests (Vitest)

## Directory Contents

```
tests/
  AGENTS.md            # This file
  test_setup.py        # Tests for setup.py script
  test_setup_core.py   # Tests for setup_lib.core module
  load/                # K6 load testing scripts
    AGENTS.md          # Load testing guide
    config.js          # K6 test configuration
    all.js             # Combined load test suite
    cameras.js         # Camera API load tests
    events.js          # Events API load tests
    mutations.js       # GraphQL mutation load tests
    redis.js           # Redis performance tests
    websocket.js       # WebSocket load tests
    websocket-scale.js # WebSocket scalability tests
    README.md          # Load testing documentation
  smoke/               # Smoke test suite for deployment verification
    conftest.py        # Pytest fixtures for smoke tests
    __init__.py        # Package marker
    test_deployment_health.py  # Deployment health checks
    test_monitoring_smoke.py   # Monitoring stack smoke tests
    test_websocket_smoke.py    # WebSocket connectivity smoke tests
    README.md          # Smoke testing documentation
```

## Key Files

### test_setup.py

**Purpose:** Tests for the main interactive setup script.

**Tests Cover:**

- `check_port_available()` - Port availability detection
- `find_available_port()` - Finding next available port
- `generate_password()` - Secure password generation
- `generate_env_content()` - Environment file content generation
- `generate_docker_override_content()` - Docker override file generation
- `write_config_files()` - File writing functionality
- `run_quick_mode()` - Quick setup mode
- `run_guided_mode()` - Guided setup mode
- `configure_firewall()` - Firewall configuration suggestions
- `prompt_with_default()` - User input handling

**Running Tests:**

```bash
# Run setup tests
uv run pytest tests/test_setup.py -v

# Run with coverage
uv run pytest tests/test_setup.py --cov=setup --cov-report=term-missing
```

### test_setup_core.py

**Purpose:** Tests for the setup library core module (`setup_lib/core.py`).

**Test Classes:**

- `TestCheckPortAvailable` - Port availability checks
- `TestFindAvailablePort` - Available port discovery
- `TestGeneratePassword` - Password generation
- `TestWeakPassword` - Weak password detection

**Running Tests:**

```bash
# Run setup_lib tests
uv run pytest tests/test_setup_core.py -v
```

## Test Organization

### Main Test Suites (Other Locations)

| Location                     | Type        | Framework  | Count   |
| ---------------------------- | ----------- | ---------- | ------- |
| `backend/tests/unit/`        | Unit tests  | pytest     | ~2957   |
| `backend/tests/integration/` | Integration | pytest     | ~626    |
| `frontend/tests/e2e/`        | E2E tests   | Playwright | ~233    |
| `frontend/src/**/*.test.ts`  | Component   | Vitest     | Various |

### This Directory

| File                 | Type       | Framework | Focus      |
| -------------------- | ---------- | --------- | ---------- |
| `test_setup.py`      | Unit tests | pytest    | setup.py   |
| `test_setup_core.py` | Unit tests | pytest    | setup_lib/ |

## Running All Tests

```bash
# Run all root-level tests
uv run pytest tests/ -v

# Run all backend tests
uv run pytest backend/tests/ -n auto --dist=worksteal

# Run all frontend tests
cd frontend && npm test

# Run E2E tests
cd frontend && npx playwright test

# Full validation script
./scripts/validate.sh
```

## Related Documentation

- **backend/tests/AGENTS.md:** Backend test infrastructure
- **frontend/tests/e2e/:** E2E test documentation
- **docs/development/testing.md:** Comprehensive testing guide
- **CLAUDE.md:** TDD requirements and testing policy
