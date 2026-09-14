# Flaky Test Detection Implementation Summary

## Overview

Implemented a comprehensive flaky test detection and categorization system for the CI pipeline. The system automatically detects, tracks, analyzes, and reports tests with non-deterministic behavior.

## What Was Implemented

### 1. Dedicated Flaky Test Detection Workflow (NEW)

**File**: `.github/workflows/flaky-test-detection.yml`

- **Schedule**: Runs nightly at 2 AM UTC
- **Manual Trigger**: Supports workflow_dispatch with configurable parameters:
  - `test_runs`: Number of runs per test suite (default: 5)
  - `test_suite`: Which suite to analyze (unit/integration/all)
- **Features**:
  - Runs unit tests 5 times in parallel with pytest-rerunfailures
  - Runs integration tests 5 times (API, WebSocket, Services) in parallel
  - Aggregates results and calculates flakiness scores
  - Analyzes timing variance to detect race conditions
  - Creates/updates GitHub issues for newly detected flaky tests
  - Uploads comprehensive reports with 90-day retention

### 2. CI Workflow Integration (ENHANCED)

**File**: `.github/workflows/ci.yml`

Enhanced existing CI workflow to capture flaky test data on every run:

- **Unit Tests**: Added `FLAKY_TEST_RESULTS_FILE` environment variable to all 4 shards

  - `flaky-test-tracking-unit-shard-1.jsonl` through `flaky-test-tracking-unit-shard-4.jsonl`
  - Files uploaded with test results (7-day retention)

- **Integration Tests**: Added tracking to all 3 integration test jobs
  - API tests: `flaky-test-tracking-integration-api.jsonl`
  - WebSocket tests: `flaky-test-tracking-integration-websocket.jsonl`
  - Services tests: `flaky-test-tracking-integration-services.jsonl`

### 3. Analysis Infrastructure (EXISTING - VERIFIED)

**File**: `scripts/analyze-flaky-tests.py` (already exists)

The analysis script provides:

- Aggregation of test outcomes from multiple runs
- Flakiness score calculation (0.0 to 1.0)
- Pass rate analysis with configurable thresholds
- Rerun penalty calculation
- Quarantine file management
- JSON report generation
- GitHub Actions job summary integration

**Configuration via environment variables**:

```bash
FLAKY_THRESHOLD=0.9   # Tests with <90% pass rate are flaky
MIN_RUNS=3            # Minimum runs to flag as flaky
RERUN_WEIGHT=0.5      # Weight for rerun penalty
```

### 4. Test Infrastructure (EXISTING - VERIFIED)

**File**: `backend/tests/conftest.py`

The conftest.py already includes:

- `FLAKY_TEST_RESULTS_FILE` environment variable support (line 187)
- Test outcome tracking via `pytest_runtest_makereport` hook (lines 360-412)
- Flaky test quarantine system with `@pytest.mark.flaky` (lines 379-411)
- Session finish handler writing JSON Lines format (lines 414-464)
- Automatic conversion of flaky test failures to xfail

### 5. Documentation (NEW)

**File**: `docs/development/flaky-test-detection.md`

Comprehensive documentation covering:

- System architecture and components
- Detection criteria and flakiness scoring
- Usage instructions for manual and automated detection
- Best practices for investigation and prevention
- Quarantine system workflow
- Troubleshooting guide
- Integration with monitoring systems

## Key Features

### Flakiness Detection Criteria

1. **Pass Rate Analysis**

   - Tests with <90% pass rate flagged as flaky
   - Configurable threshold via `FLAKY_THRESHOLD`

2. **Rerun Tracking**

   - Tests requiring reruns to pass indicate flakiness
   - Weighted contribution to flakiness score

3. **Timing Variance**
   - Coefficient of variation >50% indicates instability
   - Helps identify race conditions and resource contention

### Automated Issue Management

When flaky tests are detected:

1. Search for existing "Flaky Test Detection" issues
2. Create new issue or update existing one with comment
3. Include:
   - Summary table of flaky tests
   - Pass rates and flakiness scores
   - Recommended investigation actions
   - Links to full reports and documentation
4. Apply labels: `flaky-tests`, `testing`, `ci`

### Multi-Run Test Execution

The dedicated workflow runs tests multiple times:

- **Unit tests**: 5 parallel runs (matrix strategy)
- **Integration tests**: 5 parallel runs per suite (API, WebSocket, Services)
- Each run uses `--reruns 2` to detect tests that pass inconsistently
- All results aggregated for comprehensive analysis

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   CI/PR Test Execution                      │
│  (Every commit to main or PR)                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ pytest with           │
          │ FLAKY_TEST_RESULTS_FILE│
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ conftest.py tracks    │
          │ outcomes & reruns     │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Write JSONL artifact  │
          │ (7-day retention)     │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Upload with test      │
          │ results               │
          └───────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           Nightly Flaky Test Detection (2 AM UTC)           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Run tests 5x in       │
          │ parallel              │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Collect all tracking  │
          │ data (5 runs × N jobs)│
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ analyze-flaky-tests.py│
          │ aggregates & scores   │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Generate reports:     │
          │ - JSON report         │
          │ - GitHub issue        │
          │ - Job summary         │
          └───────────────────────┘
```

## Usage Examples

### Manual Flaky Test Detection

```bash
# Run via GitHub UI
Actions → Flaky Test Detection → Run workflow

# Run via GitHub CLI
gh workflow run flaky-test-detection.yml \
  --field test_runs=5 \
  --field test_suite=all
```

### Analyze Historical CI Runs

```bash
# Download artifacts from recent CI runs
mkdir test-results
gh run list --workflow=ci.yml --limit=10 --json databaseId --jq '.[].databaseId' | \
  xargs -I {} gh run download {} --dir test-results/run-{}

# Analyze for flaky patterns
python scripts/analyze-flaky-tests.py test-results/ \
  --output flaky-report.json \
  --quarantine-file backend/tests/flaky_tests.txt
```

### Quarantine a Flaky Test

```python
import pytest

@pytest.mark.flaky
def test_sometimes_fails():
    """Test with known flakiness - quarantined until fixed."""
    # Test implementation
    pass
```

## Configuration

### Environment Variables

| Variable                  | Default  | Description                               |
| ------------------------- | -------- | ----------------------------------------- |
| `FLAKY_TEST_RESULTS_FILE` | _(none)_ | Path to write tracking data (JSONL)       |
| `FLAKY_THRESHOLD`         | `0.9`    | Pass rate below which test is flaky (90%) |
| `MIN_RUNS`                | `3`      | Minimum runs required to flag as flaky    |
| `RERUN_WEIGHT`            | `0.5`    | Weight for rerun penalty in scoring       |

### Workflow Parameters

The dedicated workflow accepts manual inputs:

- `test_runs`: Number of test runs (default: 5)
- `test_suite`: Which suite to test (all/unit/integration)

## Benefits

1. **Early Detection**: Catches flaky tests before they impact development
2. **Automatic Reporting**: Creates GitHub issues for visibility
3. **Historical Analysis**: Tracks flakiness trends over time
4. **Zero Developer Overhead**: Runs automatically, no manual intervention
5. **Actionable Insights**: Provides timing variance and rerun analysis
6. **Quarantine System**: Prevents flaky tests from blocking CI

## Metrics Tracked

- **Flakiness Score**: 0.0 (stable) to 1.0 (very flaky)
- **Pass Rate**: Percentage of runs that passed
- **Rerun Count**: Number of retries needed to pass
- **Timing Variance**: Coefficient of variation in test duration
- **Historical Trends**: Tracking over time for degradation detection

## Next Steps (Optional Enhancements)

1. **Metrics Dashboard**: Push metrics to Prometheus/Datadog
2. **Slack Notifications**: Alert team when new flaky tests detected
3. **Linear Integration**: Create Linear tasks for flaky test fixes
4. **Historical Database**: Store long-term flaky test trends
5. **Auto-Quarantine**: Automatically add `@pytest.mark.flaky` to detected tests
6. **Flakiness Budget**: Enforce maximum allowed flakiness per team/module

## Files Modified

### New Files

- `.github/workflows/flaky-test-detection.yml` (17 KB)
- `docs/development/flaky-test-detection.md` (9.3 KB)

### Modified Files

- `.github/workflows/ci.yml`:
  - Added `FLAKY_TEST_RESULTS_FILE` to 7 test jobs (4 unit + 3 integration)
  - Updated artifact uploads to include tracking files

### Existing Files (Verified)

- `scripts/analyze-flaky-tests.py`: Already complete and functional
- `backend/tests/conftest.py`: Already has tracking infrastructure

## Testing

To verify the implementation:

1. **Trigger Manual Run**:

   ```bash
   gh workflow run flaky-test-detection.yml --field test_suite=unit
   ```

2. **Check Artifacts**:

   - Verify `flaky-test-report.json` is generated
   - Check JSONL files are uploaded from each test run

3. **Verify CI Integration**:

   - Create a PR and verify flaky test tracking files are uploaded
   - Check that files have expected format (JSON Lines)

4. **Test Analysis Script**:
   ```bash
   # Create test data
   mkdir test-results
   # Copy sample JSONL files to test-results/
   python scripts/analyze-flaky-tests.py test-results/
   ```

## References

- [Flaky Test Detection Documentation](docs/development/flaky-test-detection.md)
- [Testing Guide](docs/development/testing.md)
- [conftest.py Fixture Documentation](backend/tests/conftest.py#L180-L464)
- [pytest-rerunfailures Plugin](https://github.com/pytest-dev/pytest-rerunfailures)
