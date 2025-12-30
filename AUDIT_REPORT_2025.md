# Home Security Intelligence - Code Audit Report

**Date:** 2025-12-29
**Branch:** debug
**Scope:** End-to-end correctness, contract alignment, ops/CI, security, test coverage
**Method:** 10 parallel agents auditing after PR #44, PR #30 merges with conflicts

## Executive Summary

This audit identified **30 issues** across configuration drift, API contract mismatches, CI gaps, security vulnerabilities, and testing blind spots. Issues are prioritized as P0 (critical deployment blockers), P1 (functional bugs), and P2 (quality improvements).

**New Critical Findings (Security):**

- **docker-compose.ghcr.yml uses SQLite (P0)** - Incompatible with PostgreSQL-only backend
- **docker-compose.ghcr.yml missing postgres service (P0)** - Backend depends on non-existent service
- **SQL LIKE pattern injection in events API (P0)** - User input not escaped
- **Hardcoded database credentials (P0)** - "security_dev_password" in source
- **FFmpeg filter command injection risk (P0)** - fps parameter not validated
- **Path traversal in ffmpeg concat file (P0)** - Quotes not escaped
- **Python version mismatch (P0)** - Docs say 3.11+, code requires 3.14+

**Previous Critical Findings (Still Open):**

- Frontend/backend risk level threshold mismatch (P0) - existing bead `mb9s.18`
- Docker healthcheck endpoint mismatch (P0) - existing bead `mb9s.1`
- Batch aggregator race condition (P1) - existing bead `mb9s.19`
- Detection IDs filtering uses fragile LIKE patterns (P1) - existing bead `mb9s.20`
- CI doesn't enforce unified validation scripts (P1) - existing bead `mb9s.2`
- Database URL documentation inconsistency (P1) - existing bead `mb9s.3`
- Missing service restart scripts referenced in code (P1) - existing bead `mb9s.4`

---

## P0 - Critical Deployment Blockers

### P0-1: Frontend/Backend Risk Level Threshold Mismatch

**Impact:** Frontend displays incorrect risk levels for events, causing misclassification of security events. Scores 26-29, 51-59, and 76-84 will show wrong levels.

**Evidence:**

- `backend/services/severity.py:105-107` uses configurable thresholds: LOW=0-29, MEDIUM=30-59, HIGH=60-84, CRITICAL=85-100
- `backend/core/config.py:252-269` defines `severity_low_max=29`, `severity_medium_max=59`, `severity_high_max=84`
- `frontend/src/utils/risk.ts:16-19` uses hardcoded thresholds: LOW=0-25, MEDIUM=26-50, HIGH=51-75, CRITICAL=76-100
- `backend/services/nemotron_analyzer.py:548-555` fallback uses hardcoded 25/50/75 thresholds (matches frontend but not severity service)

**Mismatch:**

- Backend severity service: 29/59/84 (configurable)
- Frontend risk.ts: 25/50/75 (hardcoded)
- Backend fallback: 25/50/75 (hardcoded, only used if LLM doesn't provide risk_level)

**Impact Examples:**

- Score 26: Backend = LOW, Frontend = MEDIUM ❌
- Score 30: Backend = MEDIUM, Frontend = MEDIUM ✅
- Score 60: Backend = HIGH, Frontend = HIGH ✅
- Score 76: Backend = HIGH, Frontend = CRITICAL ❌
- Score 85: Backend = CRITICAL, Frontend = CRITICAL ✅

**Suggested Fix:**

1. Make frontend thresholds configurable via API (add `/api/system/config` endpoint that returns severity thresholds)
2. OR standardize on backend thresholds and update frontend to match (29/59/84)
3. Update `nemotron_analyzer.py` fallback to use SeverityService instead of hardcoded values
4. Add integration test verifying frontend and backend use same thresholds

**Tests to Add:**

- Integration test: Verify risk_level from API matches frontend getRiskLevel() for all score ranges
- Unit test: Verify SeverityService thresholds match config defaults
- E2E test: Verify UI displays correct risk badge for various scores

**Owner:** frontend, backend

---

### P0-2: Docker Healthcheck Endpoint Mismatch

**Impact:** Docker healthchecks may fail or check wrong endpoint, causing incorrect container restart behavior.

**Evidence:**

- `docker-compose.yml:65` uses `/api/system/health/live` for backend healthcheck
- `DOCKER_QUICKSTART.md:53` documents `/api/system/health/ready` as the health check endpoint
- `docker-compose.prod.yml:73` also uses `/api/system/health/live`

**Mismatch:**

- Healthcheck uses **liveness** endpoint (`/live`) which only checks if process is running
- Documentation suggests **readiness** endpoint (`/ready`) which checks dependencies
- Readiness is more appropriate for `depends_on` conditions

**Suggested Fix:**

1. Update `docker-compose.yml` and `docker-compose.prod.yml` to use `/api/system/health/ready`
2. Update `DOCKER_QUICKSTART.md` to clarify when to use `/live` vs `/ready`
3. Consider using `/live` for liveness probe and `/ready` for readiness probe if Kubernetes-style separation is desired

**Tests to Add:**

- Integration test verifying docker-compose healthchecks pass
- Test that readiness endpoint returns 503 when dependencies are down

**Owner:** devops

---

## P1 - Functional Bugs & Configuration Drift

### P1-1: CI Doesn't Enforce Unified Validation Scripts

**Impact:** CI may pass while local `validate.sh` fails, causing "works on my machine" issues.

**Evidence:**

- `.github/workflows/ci.yml` runs individual steps (ruff, mypy, pytest) separately
- `scripts/validate.sh` runs unified validation with coverage enforcement
- `scripts/test-runner.sh` runs unified test suite with coverage thresholds
- CI doesn't call these scripts, so drift can occur

**Mismatch:**

- CI coverage threshold: `--cov-fail-under=93` (unit tests only)
- `scripts/validate.sh:239`: `--cov-fail-under=90` (full backend)
- `scripts/test-runner.sh:23`: `COVERAGE_THRESHOLD=95`

**Suggested Fix:**

1. Add CI job that runs `./scripts/validate.sh` to catch script drift
2. Align coverage thresholds across CI and scripts (recommend 95% for consistency)
3. Document that CI runs both individual steps AND unified scripts

**Tests to Add:**

- CI job: `validate-scripts` that runs `./scripts/validate.sh --backend`
- CI job: `test-runner` that runs `./scripts/test-runner.sh`

**Owner:** cicd

---

### P1-2: Database URL Documentation Inconsistency

**Impact:** Users may configure SQLite expecting it to work, but application only supports PostgreSQL.

**Evidence:**

- `README.md:205` shows SQLite example: `sqlite+aiosqlite:///./data/security.db`
- `README.md:351-352` mentions SQLite in troubleshooting
- `backend/core/config.py:434-443` validates database URL must start with `postgresql://` or `postgresql+asyncpg://`
- `DOCKER_QUICKSTART.md:143` shows SQLite default

**Mismatch:**

- Documentation suggests SQLite is supported
- Code explicitly rejects SQLite URLs

**Suggested Fix:**

1. Remove all SQLite references from README.md and DOCKER_QUICKSTART.md
2. Update `.env.example` to show PostgreSQL-only examples
3. Add clear error message in config validator if SQLite URL detected

**Tests to Add:**

- Unit test verifying SQLite URL is rejected with helpful error message

**Owner:** docs

---

### P1-3: Missing Service Restart Scripts Referenced in Code

**Impact:** Service health monitor will fail to restart AI services if they crash.

**Evidence:**

- `backend/main.py:107` references `scripts/start_rtdetr.sh`
- `backend/main.py:115` references `scripts/start_nemotron.sh`
- These scripts don't exist in repository (checked via glob search)

**Mismatch:**

- Code expects restart scripts at `scripts/start_rtdetr.sh` and `scripts/start_nemotron.sh`
- Actual scripts are at `ai/start_detector.sh` and `ai/start_llm.sh` (or unified `scripts/start-ai.sh`)

**Suggested Fix:**

1. Create symlinks or wrapper scripts at expected paths
2. OR update `backend/main.py` to use correct script paths (`ai/start_detector.sh`, `ai/start_llm.sh`)
3. OR use unified `scripts/start-ai.sh` with service-specific flags

**Tests to Add:**

- Integration test verifying service health monitor can restart services
- Test that restart commands exist and are executable

**Owner:** backend

---

### P1-4: Frontend Port Inconsistency Between Dev and Prod

**Impact:** Production deployment may use wrong port, causing frontend to be unreachable.

**Evidence:**

- `README.md:122` documents frontend port `5173` (Vite dev server)
- `docker-compose.prod.yml:114` uses `${FRONTEND_PORT:-8080}` for production
- `DOCKER_QUICKSTART.md:55` shows port `5173` for frontend

**Mismatch:**

- Documentation doesn't clearly distinguish dev (5173) vs prod (8080) ports
- Production uses port 80 inside container, mapped to 8080 on host

**Suggested Fix:**

1. Update README.md to clearly show dev vs prod ports in table
2. Update DOCKER_QUICKSTART.md to mention production uses port 8080
3. Add note that production frontend runs on port 80 inside container (nginx)

**Tests to Add:**

- Docker compose test verifying production frontend is accessible on correct port

**Owner:** docs

---

### P1-5: Redis Event Channel Configuration Drift Risk

**Impact:** If `redis_event_channel` setting changes, broadcaster and analyzer may use different channels.

**Evidence:**

- `backend/core/config.py:34-36` defines `redis_event_channel` with default `"security_events"`
- `backend/services/event_broadcaster.py:57` uses `channel_name or get_settings().redis_event_channel`
- `backend/services/nemotron_analyzer.py:600` uses `get_event_channel()` which reads from settings
- Both services correctly use settings, but no test verifies they use the SAME channel

**Mismatch:**

- No integration test verifies broadcaster and analyzer use same channel
- If settings are overridden inconsistently, services could diverge

**Suggested Fix:**

1. Add integration test verifying broadcaster subscribes to same channel analyzer publishes to
2. Add runtime check in `NemotronAnalyzer._broadcast_event()` that verifies channel matches broadcaster's channel

**Tests to Add:**

- Integration test: `test_event_channel_alignment()` (already exists in `test_websocket.py:950`)
- Runtime assertion in analyzer that channel matches broadcaster

**Owner:** backend

---

## P2 - Quality Improvements & Testing Gaps

### P2-1: E2E Test API Mocking Failures (Multiple TODOs)

**Impact:** E2E tests may be unreliable in CI, causing false failures.

**Evidence:**

- `frontend/tests/e2e/smoke.spec.ts:159,172,191,203,222,236` - TODOs about API mocking failures
- `frontend/tests/e2e/realtime.spec.ts:124,138,154,174` - TODOs about API mocking failures
- `frontend/tests/e2e/navigation.spec.ts:152,203` - TODOs about API mocking failures

**Issue:**

- Multiple E2E tests have TODOs indicating API mocking doesn't work in CI
- Tests may be skipped or flaky

**Suggested Fix:**

1. Investigate why API mocking fails in CI (likely Playwright network interception issue)
2. Fix mocking or use test backend server instead
3. Remove TODOs once fixed

**Tests to Add:**

- Verify E2E tests pass in CI without manual intervention
- Add test backend server for E2E tests if mocking is unreliable

**Owner:** frontend

---

### P2-2: Coverage Threshold Inconsistency

**Impact:** Different coverage thresholds across CI and scripts can cause confusion.

**Evidence:**

- `.github/workflows/ci.yml:122` uses `--cov-fail-under=93` for unit tests
- `.github/workflows/ci.yml:216` uses `--cov-fail-under=0` for integration tests
- `scripts/validate.sh:239` uses `--cov-fail-under=90`
- `scripts/test-runner.sh:23` uses `COVERAGE_THRESHOLD=95`

**Mismatch:**

- Four different thresholds: 0%, 90%, 93%, 95%
- No clear policy on which threshold applies when

**Suggested Fix:**

1. Standardize on 95% coverage threshold for all tests (unit + integration)
2. Document coverage policy in `pyproject.toml` or `.coveragerc`
3. Update CI and scripts to use same threshold

**Tests to Add:**

- Verify coverage thresholds are consistent across all test runners

**Owner:** cicd

---

### P2-3: Docker Healthcheck Only Checks Liveness, Not Readiness

**Impact:** Containers may be marked healthy before dependencies are ready, causing race conditions.

**Evidence:**

- `docker-compose.yml:65` healthcheck uses `/api/system/health/live`
- `backend/api/routes/system.py:745-759` liveness endpoint always returns 200 (no dependency checks)
- `backend/api/routes/system.py:762-874` readiness endpoint checks DB, Redis, AI services, workers

**Issue:**

- Healthcheck uses liveness probe which doesn't verify dependencies
- `depends_on` with `condition: service_healthy` may pass before backend is actually ready

**Suggested Fix:**

- Already addressed in P0-1, but worth noting as separate quality issue
- Consider using readiness for healthcheck if dependencies are critical

**Owner:** devops

---

### P2-4: Missing Integration Test for Full Pipeline E2E

**Impact:** No test verifies the complete flow from file upload to WebSocket event.

**Evidence:**

- `backend/tests/integration/test_pipeline_e2e.py` exists but may not cover full path
- No test verifies: file upload → watcher → detection → batch → LLM → event → WebSocket broadcast

**Suggested Fix:**

1. Add comprehensive E2E test that exercises full pipeline
2. Verify Redis queue names match between producer and consumer
3. Verify WebSocket message format matches frontend expectations

**Tests to Add:**

- `test_full_pipeline_e2e()` that exercises complete flow
- Verify queue names: `detection_queue`, `analysis_queue`
- Verify Redis channel: `security_events`
- Verify WebSocket message format: `{"type": "event", "data": {...}}`

**Owner:** backend

---

### P2-5: Frontend API Types May Drift from Backend Schemas

**Impact:** Frontend may use outdated types, causing runtime errors.

**Evidence:**

- `frontend/src/services/api.ts:5-8` mentions types are generated from OpenAPI spec
- `.github/workflows/ci.yml:257` has `api-types-check` job that runs `./scripts/generate-types.sh --check`
- No enforcement that types are regenerated before commits

**Issue:**

- Types can drift if developer forgets to regenerate after backend changes
- CI checks but doesn't fail the build if types are outdated

**Suggested Fix:**

1. Add pre-commit hook to regenerate types
2. Make `api-types-check` job fail CI if types are outdated
3. Document type generation workflow in CONTRIBUTING.md

**Tests to Add:**

- Verify `generate-types.sh --check` fails if types are outdated
- Pre-commit hook test

**Owner:** frontend

---

### P2-6: No Test for Docker Compose Production Deployment

**Impact:** Production Docker configuration may have issues not caught in dev.

**Evidence:**

- `scripts/test-docker.sh` exists but may only test dev compose
- No CI job that tests `docker-compose.prod.yml`

**Suggested Fix:**

1. Add CI job that tests production Docker compose
2. Verify production healthchecks work
3. Verify production frontend serves on correct port

**Tests to Add:**

- CI job: `docker-compose-prod-test` that builds and tests production compose
- Verify production frontend accessible on port 8080

**Owner:** devops

---

### P2-7: Health Check Timeout Configuration Not Documented

**Impact:** Health checks may timeout unexpectedly if services are slow.

**Evidence:**

- `backend/api/routes/system.py:198` defines `HEALTH_CHECK_TIMEOUT_SECONDS = 5.0`
- `backend/api/routes/system.py:527` defines `AI_HEALTH_CHECK_TIMEOUT_SECONDS = 3.0`
- No documentation of these timeouts
- Docker healthcheck timeout is 5s, but backend timeout is also 5s (may be tight)

**Suggested Fix:**

1. Document health check timeouts in `docs/RUNTIME_CONFIG.md`
2. Consider making timeouts configurable via environment variables
3. Add note about timeout tuning for slow systems

**Tests to Add:**

- Test that health checks respect timeout configuration
- Test that slow services cause timeout as expected

**Owner:** backend

---

### P2-8: Queue Name Hardcoding Risk

**Impact:** If queue names change, multiple files need updates.

**Evidence:**

- Queue names `"detection_queue"` and `"analysis_queue"` are hardcoded in multiple files
- `backend/services/file_watcher.py:224` hardcodes `queue_name="detection_queue"`
- `backend/services/pipeline_workers.py:101,524` hardcode queue names
- No central constant definition

**Suggested Fix:**

1. Define queue name constants in `backend/core/redis.py` or `backend/core/config.py`
2. Import constants everywhere queue names are used
3. Add test verifying all services use same queue names

**Tests to Add:**

- Test that FileWatcher and DetectionQueueWorker use same queue name
- Test that BatchAggregator and AnalysisQueueWorker use same queue name

**Owner:** backend

---

### P2-9: WebSocket Message Format Not Validated

**Impact:** Frontend may receive malformed messages, causing UI errors.

**Evidence:**

- `backend/services/event_broadcaster.py:214` sends JSON without schema validation
- `frontend/src/hooks/useWebSocket.ts:105` parses JSON but doesn't validate structure
- No runtime validation that message matches expected format

**Suggested Fix:**

1. Add Pydantic model for WebSocket event messages
2. Validate message format before sending in `EventBroadcaster`
3. Add TypeScript type guard in frontend WebSocket hook

**Tests to Add:**

- Test that malformed messages are rejected
- Test that valid messages pass validation

**Owner:** backend, frontend

---

### P2-10: Missing Test for Service Health Monitor Restart Logic

**Impact:** Service health monitor may not restart services correctly.

**Evidence:**

- `backend/services/health_monitor.py` exists but may not have comprehensive tests
- `backend/main.py:98-131` initializes service health monitor but no test verifies restart works

**Suggested Fix:**

1. Add integration test for service health monitor
2. Mock service failures and verify restart is triggered
3. Test that restart commands are executed correctly

**Tests to Add:**

- Test service health monitor detects failures
- Test service health monitor triggers restart
- Test restart command execution

**Owner:** backend

---

### P2-11: No Test for Graceful Shutdown Order

**Impact:** Services may shut down in wrong order, causing data loss or errors.

**Evidence:**

- `backend/main.py:145-172` defines shutdown order but no test verifies it
- Shutdown order: health monitor → cleanup → GPU monitor → pipeline → file watcher → broadcaster → system broadcaster → DB → Redis

**Suggested Fix:**

1. Add test that verifies shutdown order
2. Test that pipeline workers stop before file watcher (allows queue draining)
3. Test that broadcasters stop before Redis connection closes

**Tests to Add:**

- Integration test for graceful shutdown
- Verify shutdown order is correct
- Verify no errors during shutdown

**Owner:** backend

---

### P2-12: Frontend Production Build Port Configuration

**Impact:** Production frontend may not be accessible if port configuration is wrong.

**Evidence:**

- `docker-compose.prod.yml:114` uses `${FRONTEND_PORT:-8080}` for host port mapping
- Frontend runs on port 80 inside container (nginx)
- No validation that FRONTEND_PORT is set correctly

**Suggested Fix:**

1. Document FRONTEND_PORT environment variable in `.env.example`
2. Add note in docker-compose.prod.yml about port configuration
3. Verify production build serves on correct port

**Tests to Add:**

- Test that production frontend is accessible on configured port
- Verify nginx configuration serves on port 80

**Owner:** devops

---

## Summary by Category

### Critical Contract Mismatches

- P0-1: Frontend/backend risk level threshold mismatch (29/59/84 vs 25/50/75)

### Configuration & Documentation Drift

- P0-2: Docker healthcheck endpoint mismatch
- P1-2: Database URL documentation inconsistency
- P1-4: Frontend port inconsistency
- P2-7: Health check timeout not documented
- P2-12: Frontend production port configuration

### CI & Testing Gaps

- P1-1: CI doesn't enforce unified validation scripts
- P2-1: E2E test API mocking failures
- P2-2: Coverage threshold inconsistency
- P2-4: Missing integration test for full pipeline E2E
- P2-5: Frontend API types may drift
- P2-6: No test for Docker Compose production deployment
- P2-10: Missing test for service health monitor restart logic
- P2-11: No test for graceful shutdown order

### Code Quality & Architecture

- P1-3: Missing service restart scripts
- P1-5: Batch aggregator race condition risk
- P1-6: Detection IDs filtering uses fragile LIKE patterns
- P1-7: Redis event channel configuration drift risk
- P2-8: Queue overflow handling not used consistently
- P2-3: Docker healthcheck only checks liveness
- P2-8: Queue name hardcoding risk
- P2-9: WebSocket message format not validated

---

## Recommended Action Plan

1. **Immediate (P0):** Fix Docker healthcheck endpoint mismatch
2. **Week 1 (P1):** Fix CI validation, database docs, service restart scripts, port docs
3. **Week 2 (P2):** Address testing gaps, standardize coverage, add integration tests
4. **Ongoing:** Monitor for new drift, add pre-commit hooks, improve documentation

---

## Acceptance Criteria for Remediation

Each issue should have:

1. ✅ Code fix implemented
2. ✅ Tests added/updated
3. ✅ Documentation updated
4. ✅ CI/CD updated if applicable
5. ✅ Verification that fix resolves the issue
