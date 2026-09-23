# Python 3.14 Features and Migration Guide

> Comprehensive guide to Python 3.14 features being adopted in the Home Security Intelligence project.

---

## Overview

Python 3.14 (released October 2025) brings significant performance improvements and new features that benefit our AI-powered security monitoring system. This document covers the features we are adopting and how to leverage them.

---

## Key Features Being Adopted

### 1. Free-Threading (PEP 703) - GIL Removal

The most significant change in Python 3.14 is the optional removal of the Global Interpreter Lock (GIL), enabling true parallel execution of Python threads.

#### What It Means

- **Before (GIL enabled):** Only one thread executes Python bytecode at a time, even on multi-core CPUs
- **After (GIL disabled):** Multiple threads can execute Python bytecode simultaneously

#### Performance Impact

| Workload Type      | Expected Improvement              |
| ------------------ | --------------------------------- |
| CPU-bound parallel | Up to N-times speedup (N = cores) |
| I/O-bound          | Minimal change                    |
| Single-threaded    | Slight overhead (~5-10%)          |

#### Enabling Free-Threading

```bash
# Use the free-threaded Python build (3.14t)
python3.14t scripts/benchmark_py314.py

# Check if GIL is disabled at runtime
python3.14t -c "import sys; print(f'GIL enabled: {sys._is_gil_enabled()}')"
```

#### Use Cases in Our Project

1. **AI Model Inference:** Parallel preprocessing of video frames
2. **Database Operations:** Concurrent query execution
3. **WebSocket Broadcasting:** Parallel message distribution
4. **Background Tasks:** True parallel batch processing

#### Code Example

```python
from concurrent.futures import ThreadPoolExecutor
import sys

def check_free_threading() -> bool:
    """Check if running in free-threaded mode."""
    if hasattr(sys, '_is_gil_enabled'):
        return not sys._is_gil_enabled()
    return False

def parallel_inference(frames: list[np.ndarray]) -> list[Detection]:
    """Process frames in parallel with free-threading."""
    if check_free_threading():
        # True parallelism available
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_frame, frames))
    else:
        # Fall back to multiprocessing for CPU-bound work
        with ProcessPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_frame, frames))
    return results
```

---

### 2. UUID7 Support (PEP 778)

Python 3.14 adds native support for UUID version 7, which provides time-ordered UUIDs.

#### Benefits Over UUID4

| Feature              | UUID4  | UUID7                  |
| -------------------- | ------ | ---------------------- |
| Ordering             | Random | Time-ordered           |
| Database indexing    | Poor   | Excellent              |
| Sortability          | No     | Yes (by creation time) |
| Collision resistance | High   | High                   |
| K-sortable           | No     | Yes                    |

#### Performance Characteristics

- **UUID7 generation:** Comparable to UUID4
- **Database INSERT:** 2-10x faster due to sequential writes
- **Index maintenance:** Significantly reduced fragmentation

#### Use Cases in Our Project

1. **Event IDs:** Time-ordered events for efficient querying
2. **Detection IDs:** Sortable detection records
3. **Entity IDs:** Better database performance
4. **Distributed Systems:** Coordinated ID generation

#### Code Example

```python
import uuid

# UUID4 (random)
event_id_v4 = uuid.uuid4()

# UUID7 (time-ordered, Python 3.14+)
event_id_v7 = uuid.uuid7()

# UUID7 embeds timestamp - can extract approximate creation time
# Useful for debugging and auditing
```

#### Migration Strategy

```python
import uuid
import sys

def generate_event_id() -> uuid.UUID:
    """Generate event ID using best available UUID version."""
    if sys.version_info >= (3, 14) and hasattr(uuid, 'uuid7'):
        return uuid.uuid7()
    return uuid.uuid4()
```

---

### 3. Compression Module (Zstd Integration)

Python 3.14 includes a new `compression` module with Zstd support.

#### Benefits

- **Speed:** 3-5x faster than gzip at similar compression ratios
- **Ratio:** Better compression than lz4 at similar speeds
- **Streaming:** Native streaming compression support
- **Standard library:** No external dependencies

#### Use Cases in Our Project

1. **Video frame caching:** Compress cached frames
2. **Log compression:** Efficient log storage
3. **API responses:** Optional response compression
4. **Database backups:** Faster backup/restore

#### Code Example

```python
try:
    import compression.zstd as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

def compress_frame(data: bytes) -> bytes:
    """Compress frame data using best available method."""
    if HAS_ZSTD:
        return zstd.compress(data, level=3)
    import gzip
    return gzip.compress(data)

def decompress_frame(data: bytes) -> bytes:
    """Decompress frame data."""
    if HAS_ZSTD:
        return zstd.decompress(data)
    import gzip
    return gzip.decompress(data)
```

---

### 4. Improved Error Messages

Python 3.14 continues the trend of better error messages with more context and suggestions.

#### Examples

```python
# Python 3.13 and earlier
>>> dct = {"key": "value"}
>>> dct["ket"]
KeyError: 'ket'

# Python 3.14
>>> dct = {"key": "value"}
>>> dct["ket"]
KeyError: 'ket'. Did you mean 'key'?
```

#### Impact

- Faster debugging during development
- More helpful error logs in production
- Better developer experience

---

## Running Benchmarks

We provide a comprehensive benchmark suite to measure Python 3.14 improvements.

### Quick Start

```bash
# Run with default settings
python scripts/benchmark_py314.py

# Run with more iterations for accurate results
python scripts/benchmark_py314.py --iterations 100

# Save results to JSON
python scripts/benchmark_py314.py --output results.json
```

### Comparing Python Versions

```bash
# Run benchmarks on different Python versions
python3.12 scripts/benchmark_py314.py --output results_312.json
python3.13 scripts/benchmark_py314.py --output results_313.json
python3.14 scripts/benchmark_py314.py --output results_314.json
python3.14t scripts/benchmark_py314.py --output results_314t.json

# Compare results
# Look for improvements in:
# - CPU parallel benchmarks (especially with 3.14t)
# - UUID generation
# - General Python operations
```

### Benchmark Output Example

```
==========================================================================================
PYTHON 3.14 BENCHMARK SUITE
==========================================================================================
Python version: 3.14.0 (main, Oct 7 2025, 10:00:00) [GCC 13.2.0]
Implementation: cpython
Free-threading enabled: True

Available Features:
  - free_threading: YES
  - uuid7: YES
  - compression_zstd: YES
  - improved_errors: YES

Running benchmarks with 20 iterations...

>>> CPU Parallel Benchmarks
>>> UUID Benchmarks
>>> Compression Benchmarks
>>> Async Benchmarks
>>> General Performance Benchmarks

==========================================================================================
BENCHMARK RESULTS
==========================================================================================
Name                                     Mean (ms)    Std (ms)   P95 (ms)     Ops/sec
------------------------------------------------------------------------------------------
CPU serial (4 iterations)                245.123      5.432      252.100      4.1
CPU parallel (2 threads)                 128.456      3.210      133.200      7.8
CPU parallel (4 threads)                 65.789       2.100      69.500       15.2
CPU parallel (8 threads)                 35.234       1.500      38.100       28.4
UUID4 generation (1000)                  2.345        0.123      2.567        426.4
UUID7 generation (1000)                  2.456        0.134      2.678        407.2
Zstd compress 100KB                      0.234        0.012      0.256        4273.5
...
==========================================================================================
```

---

## Performance Expectations

### Free-Threading Benchmarks

| Benchmark                | Python 3.13 | Python 3.14 | Python 3.14t | Improvement |
| ------------------------ | ----------- | ----------- | ------------ | ----------- |
| CPU serial (4 iter)      | 250ms       | 245ms       | 250ms        | Baseline    |
| CPU parallel (4 threads) | 245ms       | 240ms       | 65ms         | 3.8x        |
| CPU parallel (8 threads) | 245ms       | 240ms       | 35ms         | 7.0x        |

### UUID Generation

| Operation    | Python 3.13 | Python 3.14 | Notes       |
| ------------ | ----------- | ----------- | ----------- |
| UUID4 (1000) | 2.3ms       | 2.3ms       | No change   |
| UUID7 (1000) | N/A         | 2.4ms       | New feature |

### Compression

| Operation        | gzip (3.13) | Zstd (3.14) | Improvement |
| ---------------- | ----------- | ----------- | ----------- |
| Compress 100KB   | 5.2ms       | 0.23ms      | 22x         |
| Decompress 100KB | 0.8ms       | 0.05ms      | 16x         |

---

## Migration Notes

### Minimum Version Check

```python
import sys

MIN_PYTHON_VERSION = (3, 12)
OPTIMAL_PYTHON_VERSION = (3, 14)

if sys.version_info < MIN_PYTHON_VERSION:
    raise RuntimeError(f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required")

if sys.version_info >= OPTIMAL_PYTHON_VERSION:
    print("Running with Python 3.14 optimizations enabled")
```

### Feature Detection Pattern

```python
import sys
from typing import TYPE_CHECKING

# Feature flags
HAS_FREE_THREADING = hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled()
HAS_UUID7 = hasattr(__import__('uuid'), 'uuid7')

try:
    import compression.zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
```

### Graceful Degradation

All Python 3.14 features should degrade gracefully on older versions:

1. **Free-threading:** Fall back to ProcessPoolExecutor for CPU-bound work
2. **UUID7:** Fall back to UUID4
3. **Zstd:** Fall back to gzip or lz4

---

## Docker Configuration

### Multi-Stage Build with Python 3.14t

```dockerfile
# Build stage with free-threaded Python
FROM python:3.14t-slim AS builder

# Runtime stage
FROM python:3.14t-slim AS runtime

# Verify free-threading is enabled
RUN python -c "import sys; assert not sys._is_gil_enabled(), 'GIL should be disabled'"
```

### Environment Variables

```bash
# Disable GIL explicitly (if using standard 3.14 build)
PYTHON_GIL=0

# Thread stack size (may need adjustment for many threads)
PYTHONTHREADSTACKSIZE=1048576
```

---

## Monitoring and Observability

### Runtime Feature Detection

```python
def get_runtime_info() -> dict:
    """Get runtime information for observability."""
    import sys
    import platform

    return {
        "python_version": sys.version,
        "implementation": sys.implementation.name,
        "gil_enabled": sys._is_gil_enabled() if hasattr(sys, '_is_gil_enabled') else True,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }
```

### Performance Metrics

When using free-threading, monitor:

1. **Thread contention:** Watch for lock contention in shared data structures
2. **Memory usage:** Free-threading may increase memory footprint
3. **CPU utilization:** Should see higher utilization with parallel workloads

---

## Related Documentation

- [Benchmark Script](../../scripts/benchmark_py314.py) - Run performance benchmarks
- [ADR: Python 3.14 Adoption](../decisions/python-314-adoption.md) - Architectural decision record
- [Testing Guide](testing.md) - Test infrastructure documentation

---

## References

- [PEP 703 - Making the Global Interpreter Lock Optional](https://peps.python.org/pep-0703/)
- [PEP 778 - Add UUID version 7](https://peps.python.org/pep-0778/)
- [Python 3.14 Release Notes](https://docs.python.org/3.14/whatsnew/3.14.html)
- [Free-threaded Python Tracking Issue](https://github.com/python/cpython/issues/108219)

---

[Back to Development Documentation](./AGENTS.md)
