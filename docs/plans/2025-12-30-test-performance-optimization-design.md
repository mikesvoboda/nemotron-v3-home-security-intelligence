# Test Performance Optimization Design

## Problem

- Pre-push tests are too slow
- CI total time to merge is too long
- No visibility into which tests are slow
- No automated prevention of slow test creation

## Solution Overview

1. **pytest-timeout**: Enforce time limits per test category
2. **CI Timing Auditor**: Collect and analyze test durations, fail on violations
3. **Pre-commit Pattern Detection**: Catch slow-test anti-patterns before commit
4. **Local Parallelization**: Run tests across multiple CPU cores

---

## 1. pytest-timeout Configuration

### Thresholds

| Test Category     | Timeout    |
| ----------------- | ---------- |
| Unit tests        | 1 second   |
| Integration tests | 5 seconds  |
| Slow-marked tests | 30 seconds |

### Implementation

**pyproject.toml:**

```toml
[tool.pytest.ini_options]
timeout = 1
timeout_method = "thread"
markers = [
    "slow: marks test as slow (30s timeout)",
    "integration: marks test as integration (5s timeout)",
]
```

**backend/tests/conftest.py** - automatic timeout assignment:

```python
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        # Integration tests get 5s
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.timeout(5))
        # Explicitly marked slow tests get 30s
        if item.get_closest_marker("slow"):
            item.add_marker(pytest.mark.timeout(30))
```

**Escape hatch for exceptions:**

```python
@pytest.mark.timeout(10)  # Override for specific test
def test_needs_more_time():
    ...
```

---

## 2. CI Timing Auditor Job

### Workflow Addition

Add to `.github/workflows/ci.yml`:

```yaml
test-performance-audit:
  name: Test Performance Audit
  runs-on: ubuntu-latest
  needs: [unit-tests, integration-tests, frontend-tests]
  if: always()
  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.14"

    - name: Download test artifacts
      uses: actions/download-artifact@v4
      with:
        pattern: test-results-*
        path: test-results/
        merge-multiple: true

    - name: Analyze test durations
      run: python scripts/audit-test-durations.py test-results/
      env:
        UNIT_TEST_THRESHOLD: "1.0"
        INTEGRATION_TEST_THRESHOLD: "5.0"
        WARN_THRESHOLD_PERCENT: "80"
```

### Artifact Upload Changes

Modify test jobs to upload JUnit XML:

```yaml
# In unit-tests job
- name: Run unit tests
  run: |
    pytest backend/tests/unit/ \
      --junit-xml=test-results-unit.xml \
      --durations=20 \
      -v

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-results-unit
    path: test-results-unit.xml
```

### Audit Script

**scripts/audit-test-durations.py:**

- Parses JUnit XML files from all test jobs
- Compares test durations against thresholds
- Reports failures and warnings
- Exits non-zero if any test exceeds threshold

Output format:

```
=== TEST PERFORMANCE AUDIT ===

FAILURES (exceeded threshold):
  test_batch_aggregator_full_cycle: 2.3s (limit: 1.0s) [unit]
  test_websocket_reconnection: 6.1s (limit: 5.0s) [integration]

WARNINGS (>80% of threshold):
  test_detector_client_retry: 0.9s (limit: 1.0s) [unit]

Summary: 2 failures, 1 warning
```

---

## 3. Pre-commit Pattern Detection

### Patterns to Detect

| Pattern             | Why It's Slow | Detection Method    |
| ------------------- | ------------- | ------------------- |
| `time.sleep(`       | Real delays   | Regex + mock check  |
| `asyncio.sleep(`    | Real delays   | Regex + mock check  |
| `requests.get/post` | Real HTTP     | Import + call check |
| `httpx.` calls      | Real HTTP     | Import + call check |
| `subprocess.run`    | Process spawn | Regex + mock check  |
| `urllib.request`    | Real HTTP     | Import + call check |

### Update check-test-timeouts.py

Extend existing script to detect:

1. Sleep calls without corresponding mock
2. HTTP library usage without mocking
3. Subprocess calls without mocking

### Example Violations

```python
# FAIL: Real sleep in test
def test_retry_logic():
    time.sleep(2)  # Should mock time.sleep

# FAIL: Real HTTP call
def test_api_integration():
    response = requests.get("https://api.example.com")

# PASS: Properly mocked
def test_retry_logic(mocker):
    mocker.patch("time.sleep")
    ...
```

---

## 4. Local Test Parallelization

### pytest-xdist Setup

**Installation:**

```bash
pip install pytest-xdist
```

**Add to backend/requirements.txt:**

```
pytest-xdist>=3.5.0
```

**pyproject.toml configuration:**

```toml
[tool.pytest.ini_options]
addopts = "-n auto --dist=loadgroup"
```

### Distribution Strategies

| Strategy    | Behavior                    | Use Case                |
| ----------- | --------------------------- | ----------------------- |
| `load`      | Distribute as workers free  | Default                 |
| `loadscope` | Group by module/class       | Shared fixtures         |
| `loadgroup` | Group by xdist_group marker | Tests with shared state |

### Handling Non-Parallelizable Tests

```python
@pytest.mark.xdist_group("database")
def test_db_migration_up():
    ...

@pytest.mark.xdist_group("database")
def test_db_migration_down():
    ...
```

### Convenience Script

**scripts/test-fast.sh:**

```bash
#!/bin/bash
# Fast parallel test runner with timing report
set -e

TARGET="${1:-backend/tests/unit/}"
WORKERS="${2:-auto}"

echo "Running tests in parallel (workers: $WORKERS)"
pytest -n "$WORKERS" --durations=10 "$TARGET" "${@:3}"
```

### Frontend (Vitest)

Already parallel by default. Can tune with:

```bash
npm test -- --pool=threads --poolOptions.threads.maxThreads=4
```

---

## Implementation Order

1. Add pytest-timeout and pytest-xdist to requirements
2. Update pyproject.toml with timeout and parallel config
3. Update conftest.py with timeout hook
4. Create scripts/audit-test-durations.py
5. Update scripts/check-test-timeouts.py with pattern detection
6. Update CI workflow with artifact uploads and audit job
7. Create scripts/test-fast.sh convenience script
8. Run tests, fix any newly-flagged slow tests

---

## Success Criteria

- [ ] All unit tests complete in <1s (or explicitly marked)
- [ ] All integration tests complete in <5s (or explicitly marked)
- [ ] CI audit job catches slow tests before merge
- [ ] Pre-commit catches common slow-test patterns
- [ ] Local test runs use multiple cores by default
- [ ] Clear documentation for timeout overrides
