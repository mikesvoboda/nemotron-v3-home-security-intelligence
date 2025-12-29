# Benchmarks Directory

## Purpose

This directory contains performance and complexity benchmarks for detecting regressions in API response times, algorithmic complexity, and memory usage. Benchmarks ensure that critical paths maintain acceptable performance as the codebase evolves.

## Test Files Overview

| File                     | Description                  | Library                    |
| ------------------------ | ---------------------------- | -------------------------- |
| `test_api_benchmarks.py` | API response time benchmarks | pytest-benchmark           |
| `test_bigo.py`           | Algorithmic complexity tests | big-o (optional)           |
| `test_memory.py`         | Memory profiling tests       | pytest-memray (Linux only) |

### `test_api_benchmarks.py`

Response time benchmarks for critical API endpoints using pytest-benchmark.

**Fixtures:**

- `benchmark_env`: Sets up isolated test environment with temporary DATABASE_URL, REDIS_URL
- `benchmark_db`: Initializes temporary SQLite database for benchmark tests
- `mock_redis_client`: Mocks Redis operations to isolate benchmark measurements
- `benchmark_client`: AsyncClient with ASGITransport for API testing

**Test Classes:**

#### `TestAPIBenchmarks`

Synchronous benchmark tests using the `run_async` helper for proper measurement:

- `test_health_endpoint_benchmark`: Benchmarks `GET /` health check
- `test_detailed_health_benchmark`: Benchmarks `GET /health` detailed health
- `test_cameras_list_benchmark`: Benchmarks `GET /api/cameras` endpoint
- `test_events_list_benchmark`: Benchmarks `GET /api/events?limit=50`
- `test_system_status_benchmark`: Benchmarks `GET /api/system/status`
- `test_detections_list_benchmark`: Benchmarks `GET /api/detections?limit=50`

#### `TestAPIBenchmarksAsync`

Async-specific benchmarks:

- `test_concurrent_requests_benchmark`: Benchmarks multiple concurrent API requests

**Running:**

```bash
# Run all API benchmarks
pytest backend/tests/benchmarks/test_api_benchmarks.py --benchmark-only

# Compare against previous baseline
pytest backend/tests/benchmarks/test_api_benchmarks.py --benchmark-compare

# Fail if mean time degrades by more than 20%
pytest backend/tests/benchmarks/test_api_benchmarks.py --benchmark-compare-fail=mean:20%

# Save baseline for future comparison
pytest backend/tests/benchmarks/test_api_benchmarks.py --benchmark-save=baseline
```

### `test_bigo.py`

Algorithmic complexity tests using the big-o library to verify operations maintain O(n) or better complexity.

**Helper Functions:**

- `generate_detections(n)`: Generate n mock detection dictionaries
- `generate_file_paths(n)`: Generate n mock file paths
- `aggregate_detections_by_camera(detections)`: Reference O(n) aggregation
- `process_file_batch(file_paths)`: Reference O(n) file processing
- `filter_high_confidence(detections, threshold)`: Filter by confidence
- `group_by_timewindow(detections, window_size)`: Group detections by time

**Test Classes:**

#### `TestBatchAggregatorComplexity`

Tests that batch aggregation operations remain O(n) or O(n log n):

- `test_aggregate_detections_complexity`: Verifies aggregation is not O(n^2)
- `test_filter_detections_complexity`: Verifies filtering is O(n) or better
- `test_group_by_timewindow_complexity`: Verifies time grouping is O(n)

#### `TestFileWatcherComplexity`

Tests that file processing operations remain O(n):

- `test_process_files_complexity`: Verifies file batch processing is O(n)
- `test_path_parsing_complexity`: Verifies path parsing is O(n)

#### `TestComplexityHelperFunctions`

Unit tests for the benchmark helper functions (always run, no big-o dependency):

- `test_generate_detections_returns_correct_count`
- `test_generate_detections_has_required_fields`
- `test_generate_file_paths_returns_correct_count`
- `test_generate_file_paths_are_valid_paths`
- `test_aggregate_detections_by_camera`
- `test_filter_high_confidence`
- `test_process_file_batch`
- `test_group_by_timewindow`

**Running:**

```bash
# Run Big-O tests (requires big-o library)
pytest backend/tests/benchmarks/test_bigo.py -v

# Skip if big-o not installed
pytest backend/tests/benchmarks/test_bigo.py -v --ignore-glob="*bigo*"
```

**Note:** Tests are skipped with `pytest.mark.skipif(not BIG_O_AVAILABLE)` if the `big-o` library is not installed.

### `test_memory.py`

Memory profiling tests using pytest-memray to ensure API endpoints stay within memory limits.

**Fixtures:**

- `memory_test_env`: Sets up isolated test environment
- `memory_test_db`: Initializes temporary database for memory tests
- `mock_redis_for_memory`: Mocks Redis for memory tests
- `get_test_client`: Context manager for synchronous TestClient (required by memray)

**Test Classes:**

#### `TestMemoryProfiling`

Memory limit tests (Linux only, requires memray):

- `test_health_endpoint_memory`: 100 requests under 500MB
- `test_cameras_endpoint_memory`: 100 requests under 500MB
- `test_events_endpoint_memory`: 100 requests under 500MB
- `test_system_status_endpoint_memory`: 100 requests under 500MB

#### `TestMemoryProfilingFallback`

Fallback tests when memray is not available:

- `test_health_endpoint_without_memray`: Basic functionality test
- `test_cameras_endpoint_without_memray`: Basic functionality test

**Running:**

```bash
# Run memory tests (Linux only)
pytest backend/tests/benchmarks/test_memory.py --memray -v

# Run without memray profiling
pytest backend/tests/benchmarks/test_memory.py -v
```

**Note:** Tests are skipped with `pytest.mark.skipif(not MEMRAY_AVAILABLE)` on non-Linux platforms.

## Running All Benchmarks

### All benchmark tests

```bash
pytest backend/tests/benchmarks/ -v
```

### With benchmark measurements

```bash
pytest backend/tests/benchmarks/ --benchmark-only
```

### Slow tests (marked with @pytest.mark.slow)

```bash
pytest backend/tests/benchmarks/ -v -m slow
```

### Skip slow tests

```bash
pytest backend/tests/benchmarks/ -v -m "not slow"
```

## Benchmark Markers

Tests use pytest markers for categorization:

- `@pytest.mark.slow`: Long-running benchmark tests
- `@pytest.mark.benchmark(group="api-health")`: API health endpoint benchmarks
- `@pytest.mark.benchmark(group="api-cameras")`: Camera API benchmarks
- `@pytest.mark.benchmark(group="api-events")`: Events API benchmarks
- `@pytest.mark.benchmark(group="api-system")`: System API benchmarks
- `@pytest.mark.benchmark(group="api-detections")`: Detections API benchmarks
- `@pytest.mark.benchmark(group="api-async")`: Async operation benchmarks
- `@pytest.mark.limit_memory("500 MB")`: Memory limit tests (memray)
- `@pytest.mark.skipif`: Conditional skipping for optional dependencies

## Dependencies

### Required

- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-benchmark>=4.0.0` - Response time benchmarking
- `httpx>=0.25.0` - HTTP client for API testing

### Optional

- `big-o` - Algorithmic complexity analysis (Big-O tests)
- `pytest-memray` - Memory profiling (Linux only, memory tests)
- `memray` - Memory allocation tracking (Linux only)

Install optional dependencies:

```bash
pip install big-o pytest-memray memray
```

## Benchmark Results Interpretation

### API Benchmarks (pytest-benchmark)

Output includes:

- **min**: Fastest execution time
- **max**: Slowest execution time
- **mean**: Average execution time
- **stddev**: Standard deviation
- **rounds**: Number of iterations
- **iterations**: Total function calls

Example output:

```
----------------------------- benchmark: 6 tests -----------------------------
Name                           Mean      StdDev    Min       Max       Rounds
test_health_endpoint         1.2345ms   0.1234ms  1.1000ms  1.5000ms  100
test_cameras_list            2.3456ms   0.2345ms  2.0000ms  3.0000ms  100
```

### Big-O Complexity

The big-o library fits measured times to complexity classes:

- `Constant` - O(1)
- `Logarithmic` - O(log n)
- `Linear` - O(n)
- `Linearithmic` - O(n log n)
- `Quadratic` - O(n^2)
- `Cubic` - O(n^3)
- `Polynomial` - O(n^k)
- `Exponential` - O(2^n)

Tests pass if complexity is O(n log n) or better, fail if O(n^2) or worse.

### Memory Profiling (memray)

Memory tests verify endpoints stay under specified limits during repeated calls. The `@pytest.mark.limit_memory("500 MB")` marker enforces the limit.

## Adding New Benchmarks

### API Response Time Benchmark

```python
@pytest.mark.benchmark(group="api-newfeature")
def test_new_endpoint_benchmark(self, benchmark, benchmark_client: AsyncClient):
    """Benchmark GET /api/new-endpoint."""

    async def fetch_new():
        response = await benchmark_client.get("/api/new-endpoint")
        return response

    result = benchmark(lambda: run_async(fetch_new()))
    assert result.status_code == 200
```

### Complexity Benchmark

```python
@pytest.mark.skipif(not BIG_O_AVAILABLE, reason="big-o library not installed")
def test_new_operation_complexity(self):
    """New operation should be O(n) or better."""

    def new_op(n: int) -> int:
        data = generate_data(n)
        result = new_operation(data)
        return len(result)

    best, _others = big_o(
        new_op,
        lambda n: n,
        n_repeats=5,
        min_n=100,
        max_n=10000,
    )

    acceptable = [
        complexities.Constant,
        complexities.Logarithmic,
        complexities.Linear,
        complexities.Linearithmic,
    ]
    assert any(isinstance(best, c) for c in acceptable)
```

### Memory Benchmark

```python
@pytest.mark.skipif(not MEMRAY_AVAILABLE, reason="memray only available on Linux")
@pytest.mark.limit_memory("500 MB")
def test_new_endpoint_memory(self, memory_test_db, mock_redis_for_memory):
    """Ensure new endpoint stays under 500MB with repeated calls."""
    with get_test_client(mock_redis_for_memory) as client:
        for _ in range(100):
            response = client.get("/api/new-endpoint")
            assert response.status_code == 200
```

## CI/CD Integration

Benchmarks can be integrated into CI/CD pipelines:

```yaml
# .github/workflows/benchmarks.yml
- name: Run benchmarks
  run: |
    pytest backend/tests/benchmarks/ --benchmark-only --benchmark-json=benchmark.json

- name: Compare benchmarks
  run: |
    pytest backend/tests/benchmarks/ --benchmark-compare=baseline --benchmark-compare-fail=mean:20%
```

## Troubleshooting

### pytest-benchmark not measuring

- Ensure `--benchmark-only` flag is used
- Check that `benchmark` fixture is included in test parameters

### big-o tests skipped

- Install the big-o library: `pip install big-o`
- Check import error messages in test output

### memray tests skipped

- Only available on Linux
- Install: `pip install pytest-memray memray`

### Benchmark results vary widely

- Increase `n_repeats` for more stable results
- Run on idle system to reduce interference
- Use `--benchmark-warmup` for JIT compilation

### Memory tests fail

- Check for memory leaks in application code
- Increase memory limit if justified
- Profile with memray directly for detailed analysis

## Best Practices

1. **Baseline Management**: Save baselines after confirmed improvements
2. **Threshold Setting**: Set failure thresholds based on statistical variance
3. **Isolation**: Use temporary databases and mocked external services
4. **Consistency**: Run benchmarks on consistent hardware/environment
5. **Documentation**: Document expected performance characteristics

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/integration/AGENTS.md` - Integration test architecture
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/AGENTS.md` - Backend architecture overview
- `/CLAUDE.md` - Project instructions and testing requirements
