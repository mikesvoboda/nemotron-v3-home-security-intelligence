# Benchmarks Directory

## Purpose

Performance and complexity benchmarks for detecting regressions in API response times, algorithmic complexity, and memory usage. Benchmarks ensure critical paths maintain acceptable performance as the codebase evolves.

## Directory Structure

```
backend/tests/benchmarks/
├── AGENTS.md                    # This file
├── __init__.py                  # Package initialization
├── test_api_benchmarks.py       # API response time benchmarks
├── test_bigo.py                 # Big-O complexity tests
├── test_connection_pool.py      # Connection pool performance tests
├── test_memory.py               # Memory profiling tests
├── test_performance.py          # Core performance regression benchmarks
└── test_slow_query_detection.py # Slow query detection tests
```

## Running Tests

```bash
# All benchmarks
pytest backend/tests/benchmarks/ -v

# API response time benchmarks
pytest backend/tests/benchmarks/test_api_benchmarks.py --benchmark-only

# Big-O complexity tests
pytest backend/tests/benchmarks/test_bigo.py -v

# Memory profiling (Linux only)
pytest backend/tests/benchmarks/test_memory.py --memray -v

# Compare against baseline
pytest backend/tests/benchmarks/ --benchmark-compare

# Fail if performance degrades
pytest backend/tests/benchmarks/ --benchmark-compare-fail=mean:20%

# Save baseline
pytest backend/tests/benchmarks/ --benchmark-save=baseline

# Skip slow tests
pytest backend/tests/benchmarks/ -v -m "not slow"
```

## Test Files (6 total)

### `test_api_benchmarks.py`

Response time benchmarks using pytest-benchmark:

| Test                                 | Endpoint                       | Group          |
| ------------------------------------ | ------------------------------ | -------------- |
| `test_health_endpoint_benchmark`     | `GET /`                        | api-health     |
| `test_detailed_health_benchmark`     | `GET /health`                  | api-health     |
| `test_cameras_list_benchmark`        | `GET /api/cameras`             | api-cameras    |
| `test_events_list_benchmark`         | `GET /api/events?limit=50`     | api-events     |
| `test_system_status_benchmark`       | `GET /api/system/status`       | api-system     |
| `test_detections_list_benchmark`     | `GET /api/detections?limit=50` | api-detections |
| `test_concurrent_requests_benchmark` | Multiple endpoints             | api-async      |

**Fixtures:**

- `benchmark_env`: Isolated test environment with temp SQLite database
- `benchmark_db`: Initialized database for benchmarks
- `mock_redis_client`: Mocked Redis operations
- `benchmark_client`: AsyncClient with ASGITransport

### `test_bigo.py`

Algorithmic complexity tests using big-o library:

| Test                                   | Operation             | Expected Complexity |
| -------------------------------------- | --------------------- | ------------------- |
| `test_aggregate_detections_complexity` | Batch aggregation     | O(n) or O(n log n)  |
| `test_filter_detections_complexity`    | Confidence filtering  | O(n)                |
| `test_group_by_timewindow_complexity`  | Time window grouping  | O(n)                |
| `test_process_files_complexity`        | File batch processing | O(n)                |
| `test_path_parsing_complexity`         | Path parsing          | O(n)                |

**Helper Functions:**

- `generate_detections(n)`: Generate n mock detections
- `generate_file_paths(n)`: Generate n mock file paths
- `aggregate_detections_by_camera(detections)`: Reference O(n) aggregation
- `process_file_batch(file_paths)`: Reference O(n) file processing
- `filter_high_confidence(detections, threshold)`: Filter by confidence
- `group_by_timewindow(detections, window_size)`: Group by time

**Unit Tests (always run):**

- `TestComplexityHelperFunctions`: Tests helper functions work correctly

### `test_memory.py`

Memory profiling using pytest-memray (Linux only):

| Test                                 | Endpoint                 | Limit |
| ------------------------------------ | ------------------------ | ----- |
| `test_health_endpoint_memory`        | `GET /`                  | 500MB |
| `test_cameras_endpoint_memory`       | `GET /api/cameras`       | 500MB |
| `test_events_endpoint_memory`        | `GET /api/events`        | 500MB |
| `test_system_status_endpoint_memory` | `GET /api/system/status` | 500MB |

**Fallback Tests:**

- Run when memray not available (non-Linux)
- Basic functionality tests without memory limits

### `test_performance.py`

Core performance regression benchmarks:

| Test                                  | Operation Tested           |
| ------------------------------------- | -------------------------- |
| `test_json_serialization_performance` | JSON serialization speed   |
| `test_database_query_performance`     | Simple SELECT query speed  |
| `test_service_function_call_overhead` | Service function call time |

**Purpose:**

- Detect performance regressions in critical operations
- Measure baseline performance for future comparisons
- Identify slow operations early in development

**Fixtures:**

- `performance_env`: Temporary database environment per test
- `performance_db`: Initialized SQLite database for benchmarks
- Uses SQLite for faster setup/teardown in benchmarks

**Usage:**

```bash
pytest backend/tests/benchmarks/test_performance.py --benchmark-only
pytest backend/tests/benchmarks/test_performance.py --benchmark-compare
pytest backend/tests/benchmarks/test_performance.py --benchmark-compare-fail=mean:20%
```

### `test_connection_pool.py`

Database connection pool performance tests:

| Test                                | Operation Tested                    |
| ----------------------------------- | ----------------------------------- |
| `test_connection_pool_under_load`   | Pool behavior under concurrent load |
| `test_connection_pool_exhaustion`   | Pool exhaustion handling            |
| `test_connection_reuse_performance` | Connection reuse efficiency         |

### `test_slow_query_detection.py`

Slow query detection and logging tests:

| Test                               | Operation Tested                  |
| ---------------------------------- | --------------------------------- |
| `test_slow_query_logging`          | Queries over threshold are logged |
| `test_slow_query_threshold_config` | Configurable threshold behavior   |
| `test_query_timing_accuracy`       | Query timing measurement accuracy |

## Test Markers

| Marker                                | Usage                                  |
| ------------------------------------- | -------------------------------------- |
| `@pytest.mark.slow`                   | Long-running benchmark tests           |
| `@pytest.mark.benchmark(group="...")` | API benchmark grouping                 |
| `@pytest.mark.limit_memory("500 MB")` | Memory limit tests                     |
| `@pytest.mark.skipif(...)`            | Conditional skipping for optional deps |

## Dependencies

### Required

- `pytest>=7.4.0`
- `pytest-asyncio>=0.21.0`
- `pytest-benchmark>=4.0.0`
- `httpx>=0.25.0`

### Optional

- `big-o`: Algorithmic complexity analysis
- `pytest-memray`: Memory profiling (Linux only)
- `memray`: Memory allocation tracking (Linux only)

Install optional:

```bash
pip install big-o pytest-memray memray
```

## Benchmark Results

### pytest-benchmark Output

```
----------------------------- benchmark: 6 tests -----------------------------
Name                           Mean      StdDev    Min       Max       Rounds
test_health_endpoint         1.2345ms   0.1234ms  1.1000ms  1.5000ms  100
test_cameras_list            2.3456ms   0.2345ms  2.0000ms  3.0000ms  100
```

### Big-O Complexity Classes

| Class          | Complexity    |
| -------------- | ------------- |
| `Constant`     | O(1)          |
| `Logarithmic`  | O(log n)      |
| `Linear`       | O(n)          |
| `Linearithmic` | O(n log n)    |
| `Quadratic`    | O(n^2) - FAIL |
| `Cubic`        | O(n^3) - FAIL |
| `Exponential`  | O(2^n) - FAIL |

Tests pass if O(n log n) or better, fail if O(n^2) or worse.

## Adding New Benchmarks

### API Response Time

```python
@pytest.mark.benchmark(group="api-newfeature")
def test_new_endpoint_benchmark(self, benchmark, benchmark_client):
    async def fetch():
        return await benchmark_client.get("/api/new-endpoint")

    result = benchmark(lambda: run_async(fetch()))
    assert result.status_code == 200
```

### Complexity Benchmark

```python
@pytest.mark.skipif(not BIG_O_AVAILABLE, reason="big-o not installed")
def test_new_operation_complexity(self):
    def new_op(n):
        data = generate_data(n)
        return new_operation(data)

    best, _ = big_o(new_op, lambda n: n, n_repeats=5, min_n=100, max_n=10000)

    acceptable = [complexities.Constant, complexities.Logarithmic,
                  complexities.Linear, complexities.Linearithmic]
    assert any(isinstance(best, c) for c in acceptable)
```

### Memory Benchmark

```python
@pytest.mark.skipif(not MEMRAY_AVAILABLE, reason="memray Linux only")
@pytest.mark.limit_memory("500 MB")
def test_new_endpoint_memory(self, memory_test_db, mock_redis):
    with get_test_client(mock_redis) as client:
        for _ in range(100):
            response = client.get("/api/new-endpoint")
            assert response.status_code == 200
```

## CI/CD Integration

```yaml
# .github/workflows/benchmarks.yml
- name: Run benchmarks
  run: pytest backend/tests/benchmarks/ --benchmark-only --benchmark-json=benchmark.json

- name: Compare benchmarks
  run: pytest backend/tests/benchmarks/ --benchmark-compare=baseline --benchmark-compare-fail=mean:20%
```

## Troubleshooting

### pytest-benchmark not measuring

- Use `--benchmark-only` flag
- Include `benchmark` fixture in test parameters

### big-o tests skipped

- Install: `pip install big-o`
- Check import error messages

### memray tests skipped

- Only available on Linux
- Install: `pip install pytest-memray memray`

### Benchmark results vary

- Increase `n_repeats` for stability
- Run on idle system
- Use `--benchmark-warmup`

### Memory tests fail

- Check for memory leaks
- Increase limit if justified
- Profile with memray directly

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/AGENTS.md` - Backend architecture
