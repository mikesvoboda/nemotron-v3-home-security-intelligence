# Load Tests Directory

## Purpose

Performance and load tests for new features to verify they meet latency, memory, and throughput requirements under realistic workloads. These tests complement the benchmarks directory by focusing on feature-specific performance targets.

Implements NEM-3340: Load Testing for New Features (Phase 7.4).

## Directory Structure

```
backend/tests/load/
├── AGENTS.md              # This file
├── __init__.py            # Package initialization
└── test_performance.py    # Feature performance load tests
```

## Running Tests

```bash
# All load tests
pytest backend/tests/load/ -v

# With benchmark plugin (if available)
pytest backend/tests/load/ --benchmark-only

# Skip slow tests for quick validation
pytest backend/tests/load/ -v -m "not slow"

# Run specific test class
pytest backend/tests/load/test_performance.py::TestHouseholdMatchingPerformance -v

# Run with verbose output for debugging
pytest backend/tests/load/test_performance.py -v -s
```

## Test Files

### `test_performance.py`

Load tests for new feature performance validation:

| Test Class                         | Target        | Description                       |
| ---------------------------------- | ------------- | --------------------------------- |
| `TestHouseholdMatchingPerformance` | <50ms p99     | Household matching latency tests  |
| `TestFrameBufferMemory`            | <500MB/camera | Frame buffer memory limit tests   |
| `TestXCLIPConcurrency`             | No blocking   | X-CLIP concurrent inference tests |
| `TestPipelineThroughput`           | 30fps         | Overall pipeline throughput tests |
| `TestMemoryStress`                 | No OOM        | Memory stress and leak tests      |

## Performance Targets

### Household Matching

| Metric                    | Target | Test Coverage                               |
| ------------------------- | ------ | ------------------------------------------- |
| p99 latency (10 members)  | <50ms  | `test_household_matching_latency_small_db`  |
| p99 latency (100 members) | <50ms  | `test_household_matching_latency_medium_db` |
| p99 latency (500 members) | <50ms  | `test_household_matching_latency_large_db`  |
| cosine_similarity avg     | <100us | `test_cosine_similarity_performance`        |

### Frame Buffer Memory

| Metric                      | Target        | Test Coverage                               |
| --------------------------- | ------------- | ------------------------------------------- |
| Single camera (1800 frames) | <500MB        | `test_frame_buffer_memory_single_camera`    |
| Multi-camera (4x900 frames) | <500MB/camera | `test_frame_buffer_memory_multiple_cameras` |
| Frame add latency           | <10ms avg     | `test_frame_buffer_add_throughput`          |

### X-CLIP Concurrency

| Metric                 | Target      | Test Coverage                    |
| ---------------------- | ----------- | -------------------------------- |
| 10 concurrent requests | 0 errors    | `test_concurrent_xclip_requests` |
| Request isolation      | Independent | `test_xclip_request_isolation`   |
| Throughput             | >10 req/s   | `test_xclip_throughput`          |

## Test Markers

| Marker                 | Description                                |
| ---------------------- | ------------------------------------------ |
| `@pytest.mark.slow`    | Long-running tests (>1s), auto-timeout 30s |
| `@pytest.mark.asyncio` | Async tests                                |

## Fixtures

### Test Data Generators

| Function                               | Purpose                             |
| -------------------------------------- | ----------------------------------- |
| `generate_test_embedding(dim, seed)`   | Create normalized embedding vectors |
| `generate_frame_data(size_bytes)`      | Create frame data of specified size |
| `create_mock_pil_image(width, height)` | Create mock PIL Image for X-CLIP    |

### Service Fixtures

| Fixture                 | Scope    | Description                          |
| ----------------------- | -------- | ------------------------------------ |
| `household_matcher`     | function | HouseholdMatcher instance            |
| `mock_session`          | function | Mock AsyncSession for DB operations  |
| `frame_buffer`          | function | FrameBuffer with 1800 frame capacity |
| `mock_xclip_model_dict` | function | Mocked X-CLIP model and processor    |

## Test Patterns

### Latency Measurement

```python
latencies = []
for _ in range(100):
    start = time.perf_counter()
    await operation()
    latency_ms = (time.perf_counter() - start) * 1000
    latencies.append(latency_ms)

# Calculate p99
latencies.sort()
p99 = latencies[int(len(latencies) * 0.99) - 1]
assert p99 < target_ms
```

### Memory Estimation

```python
# Frame buffer memory estimation
frame_count = buffer.frame_count(camera_id)
frame_size = 100_000  # ~100KB per frame
estimated_memory = frame_count * frame_size
assert estimated_memory < 500 * 1024 * 1024  # 500MB
```

### Concurrent Load Testing

```python
async def make_request(request_id):
    # Perform operation
    return result

tasks = [make_request(i) for i in range(num_concurrent)]
results = await asyncio.gather(*tasks, return_exceptions=True)

errors = [r for r in results if isinstance(r, Exception)]
assert len(errors) == 0
```

## Adding New Load Tests

### Template for Latency Tests

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_new_feature_latency(self):
    """Verify new feature completes within Xms p99."""
    latencies = []

    for _ in range(100):
        start = time.perf_counter()
        await new_feature_operation()
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

    latencies.sort()
    p99 = latencies[98]  # 99th percentile

    assert p99 < TARGET_MS, f"p99 {p99:.2f}ms exceeds {TARGET_MS}ms"
```

### Template for Memory Tests

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_new_feature_memory(self):
    """Verify new feature stays within memory bounds."""
    # Perform memory-intensive operations
    for i in range(LARGE_COUNT):
        await add_data(generate_data(SIZE))

    # Estimate or measure memory
    estimated_memory = calculate_memory_usage()

    assert estimated_memory < MAX_MEMORY_BYTES
```

### Template for Concurrency Tests

```python
@pytest.mark.asyncio
async def test_new_feature_concurrency(self):
    """Verify new feature handles concurrent requests."""
    async def make_request(request_id):
        return await feature_operation()

    tasks = [make_request(i) for i in range(NUM_CONCURRENT)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0
```

## CI/CD Integration

Load tests are designed to be run in CI but are marked as `slow` to allow
skipping during quick validation runs:

```bash
# Full load test suite (CI)
pytest backend/tests/load/ -v --timeout=60

# Quick smoke test (local development)
pytest backend/tests/load/ -v -m "not slow"
```

## Troubleshooting

### Tests timing out

- Increase timeout with `--timeout=N`
- Check if mocked services are properly configured
- Verify test isn't waiting on real network/DB resources

### Memory tests failing

- Check frame size assumptions match actual data
- Verify buffer eviction is working correctly
- Use memray for detailed memory profiling

### Latency variance

- Run on idle system for consistent results
- Increase iteration count for stable p99
- Consider CPU throttling in CI environments

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/benchmarks/AGENTS.md` - Performance benchmarks
- `/backend/services/household_matcher.py` - Household matching service
- `/backend/services/frame_buffer.py` - Frame buffer service
- `/backend/services/xclip_loader.py` - X-CLIP model loader
