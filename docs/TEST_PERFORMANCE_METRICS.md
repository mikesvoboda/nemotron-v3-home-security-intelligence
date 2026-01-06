# Test Performance Metrics

This document tracks test performance baselines and CI parallelization configuration for the project.

**Last updated:** 2026-01-05
**Related issue:** [NEM-1375](https://linear.app/nemotron-v3-home-security/issue/NEM-1375)

## Test Suite Overview

| Suite                         | Test Count | Parallelization                           | CI Configuration                                   |
| ----------------------------- | ---------- | ----------------------------------------- | -------------------------------------------------- |
| Backend Unit                  | 8,229      | pytest-xdist (`-n auto --dist=worksteal`) | 1 job, parallel workers                            |
| Backend Integration           | 1,556      | Serial (`-n0`) - 4 domain shards          | 4 parallel jobs (API, WebSocket, Services, Models) |
| Frontend Vitest               | ~2,000+    | Thread pool                               | 8 shards                                           |
| Frontend E2E (Chromium)       | ~500+      | Playwright workers                        | 4 shards                                           |
| Frontend E2E (Firefox/WebKit) | ~500+      | Playwright workers                        | 1 job each (non-blocking)                          |

## CI Parallelization Strategy

### Backend Tests

#### Unit Tests

- **Configuration:** Single job with `pytest-xdist`
- **Flags:** `-n auto --dist=worksteal`
- **Rationale:** Worksteal scheduling optimizes for uneven test durations
- **Expected runtime:** ~60-90 seconds

#### Integration Tests (4 Domain Shards)

Domain-based sharding to maximize parallelism while avoiding database contention:

| Shard | Job Name                      | Test Domains     | Filter Pattern                                          |
| ----- | ----------------------------- | ---------------- | ------------------------------------------------------- |
| 1     | `integration-tests-api`       | API routes       | `test_*_api or test_api_*`                              |
| 2     | `integration-tests-websocket` | WebSocket/PubSub | `test_websocket or test_*_broadcaster or test_*_pubsub` |
| 3     | `integration-tests-services`  | Business logic   | `test_*_integration or test_batch* or test_detector*`   |
| 4     | `integration-tests-models`    | Database models  | `test_models or test_database or test_baseline*`        |

- **Configuration:** Serial execution within each shard (`-n0`)
- **Rationale:** Avoids database deadlocks from concurrent schema creation
- **Expected runtime per shard:** ~60-90 seconds (runs in parallel)
- **Total wall-clock time:** ~2-3 minutes (down from ~6-8 minutes serial)

### Frontend Tests

#### Vitest (Component/Hook Tests)

- **Configuration:** 8-shard matrix strategy
- **CI command:** `npx vitest run --shard=${{ matrix.shard }}/8`
- **Timeout:** 3 minutes per shard
- **Coverage:** Collected per-shard, merged in `frontend-coverage-merge` job
- **Expected runtime per shard:** ~30-60 seconds

#### Playwright E2E Tests

- **Primary (Chromium):** 4 shards with `--shard=1/4` through `--shard=4/4`
- **Secondary (Firefox/WebKit):** 1 job each, non-blocking (`continue-on-error: true`)
- **Workers:** 4 parallel workers in CI
- **Retries:** 2 retries on CI for flaky test handling
- **Expected runtime per shard:** ~2-4 minutes

## Performance Thresholds

The `scripts/audit-test-durations.py` script enforces these thresholds:

| Test Category     | Max Duration | Warning at (80%) |
| ----------------- | ------------ | ---------------- |
| Unit tests        | 1.0s         | 0.8s             |
| Integration tests | 5.0s         | 4.0s             |
| E2E tests         | 5.0s         | 4.0s             |
| Known slow tests  | 60.0s        | 48.0s            |
| Benchmarks        | Excluded     | N/A              |

### Known Slow Test Patterns

Tests matching these patterns use the extended 60s threshold:

- Pipeline worker manager tests (real stop timeouts)
- Health monitor subprocess tests
- System broadcaster reconnection tests
- Property-based tests with text generation
- TLS certificate generation (RSA key gen)
- E2E error state tests (API retry exhaustion)
- Accessibility tests (axe-core analysis)
- ReID service retry/backoff tests

See `scripts/audit-test-durations.py` for the full pattern list.

## Baseline Metrics (2026-01-05)

### Test Counts (Minimum Thresholds)

These baselines prevent accidental test deletion:

| Suite               | Minimum Count | Current Count |
| ------------------- | ------------- | ------------- |
| Backend Unit        | 2,900         | 8,229         |
| Backend Integration | 600           | 1,556         |
| Frontend Test Files | 50            | 135           |
| Frontend E2E Specs  | 15            | 26            |

### Expected CI Duration

| Stage                     | Expected Duration | Notes                 |
| ------------------------- | ----------------- | --------------------- |
| Lint + Typecheck          | ~1-2 min          | Runs in parallel      |
| Backend Unit Tests        | ~1-2 min          | pytest-xdist parallel |
| Backend Integration Tests | ~2-3 min          | 4 shards in parallel  |
| Frontend Vitest           | ~1-2 min          | 8 shards in parallel  |
| Frontend E2E (Chromium)   | ~3-5 min          | 4 shards in parallel  |
| **Total CI time**         | **~8-12 min**     | All jobs parallelized |

### Improvement from Parallelization

| Configuration               | Estimated Time | Improvement          |
| --------------------------- | -------------- | -------------------- |
| Serial (no parallelization) | ~25-35 min     | Baseline             |
| Current parallelized        | ~8-12 min      | **60-70% reduction** |

## Caching Strategy

### GitHub Actions Cache

| Cache               | Key Pattern                                                           | Purpose            |
| ------------------- | --------------------------------------------------------------------- | ------------------ |
| uv dependencies     | `uv-${{ runner.os }}-${{ hashFiles('uv.lock') }}`                     | Python packages    |
| npm dependencies    | `npm-${{ runner.os }}-${{ hashFiles('package-lock.json') }}`          | Node packages      |
| Playwright browsers | `playwright-*-${{ runner.os }}-${{ hashFiles('package-lock.json') }}` | Browser binaries   |
| Docker layers       | `gha,scope=backend` / `gha,scope=frontend`                            | Image build layers |

## Test Performance Audit Job

The `test-performance-audit` CI job:

1. Downloads JUnit XML results from all test jobs
2. Parses test durations from XML files
3. Flags tests exceeding thresholds
4. Reports warnings for tests approaching limits
5. Excludes benchmark tests from analysis

### Running Locally

```bash
# After running tests with JUnit output
uv run python scripts/audit-test-durations.py test-results/

# Environment variable overrides
UNIT_TEST_THRESHOLD=2.0 \
INTEGRATION_TEST_THRESHOLD=10.0 \
uv run python scripts/audit-test-durations.py test-results/
```

## Monitoring and Maintenance

### Weekly Checks

1. Review CI run times in GitHub Actions
2. Check for new slow tests in audit reports
3. Verify test count thresholds remain accurate
4. Update slow test patterns if needed

### When to Update Baselines

Update this document when:

- Test count baselines change significantly (add tests)
- New slow test patterns are identified
- CI configuration changes (shards, parallelization)
- Performance improvements are made

### Alerting

The CI workflow includes:

- `test-count-verification` job - fails if test counts drop below thresholds
- `test-performance-audit` job - warns on slow tests, fails if threshold exceeded

## References

- CI workflow: `.github/workflows/ci.yml`
- Test duration audit: `scripts/audit-test-durations.py`
- Vitest config: `frontend/vite.config.ts`
- Playwright config: `frontend/playwright.config.ts`
- pytest config: `pyproject.toml`
