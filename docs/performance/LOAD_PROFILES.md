# Performance Testing Load Profiles

This document describes the realistic load profiles used in performance testing for the Home Security Intelligence application.

## Overview

Load profiles simulate real-world usage patterns to validate system performance under various conditions. Profiles are designed based on expected usage for a single-user home security monitoring system.

## Production Usage Patterns

### Typical Home Security System Load

| Metric                            | Expected Value | Notes                        |
| --------------------------------- | -------------- | ---------------------------- |
| **Daily Events**                  | 100-500        | Motion events from cameras   |
| **Peak Events/Hour**              | 20-50          | During high-activity periods |
| **Concurrent Dashboard Sessions** | 1-3            | Single household users       |
| **WebSocket Connections**         | 1-5            | Dashboard + mobile apps      |
| **AI Processing**                 | 10-30/hour     | Images requiring detection   |
| **Camera Snapshots**              | 4-8 cameras    | Simultaneous monitoring      |

### Traffic Distribution

Based on typical usage patterns:

| Endpoint Category  | Traffic Share | Reason                            |
| ------------------ | ------------- | --------------------------------- |
| **Events API**     | 35%           | Primary data source for dashboard |
| **Cameras API**    | 30%           | Status checks, snapshots          |
| **System API**     | 15%           | Health checks, monitoring         |
| **WebSocket**      | 10%           | Real-time event streaming         |
| **Detections API** | 10%           | AI detection results              |

## Load Profiles

### 1. Smoke Test Profile

**Purpose:** Quick validation that the system is functional.

**Use Cases:**

- CI/CD pipeline health checks
- Post-deployment validation
- Pre-release smoke testing

**Configuration:**

```javascript
const smokeTestStages = [
  { duration: '10s', target: 1 }, // 1 virtual user for 10 seconds
];
```

**Expected Behavior:**

- All requests succeed (< 1% error rate)
- Response times < 500ms (p95)
- WebSocket connections establish successfully

### 2. Average Load Profile

**Purpose:** Simulate typical daily load.

**Use Cases:**

- Regular performance validation
- Baseline establishment
- Pre-release testing

**Configuration:**

```javascript
const averageLoadStages = [
  { duration: '30s', target: 10 }, // Ramp up to 10 VUs
  { duration: '1m', target: 10 }, // Hold for 1 minute
  { duration: '30s', target: 0 }, // Ramp down
];
```

**Expected Behavior:**

- All requests succeed (< 1% error rate)
- Response times < 500ms (p95)
- System resources stay within limits
- No slow queries detected

### 3. Stress Test Profile

**Purpose:** Find system limits and breaking points.

**Use Cases:**

- Capacity planning
- Finding bottlenecks
- Pre-release stress validation

**Configuration:**

```javascript
const stressTestStages = [
  { duration: '30s', target: 20 }, // Ramp to 20 VUs
  { duration: '1m', target: 50 }, // Increase to 50 VUs
  { duration: '1m', target: 100 }, // Peak at 100 VUs
  { duration: '2m', target: 100 }, // Hold peak for 2 minutes
  { duration: '30s', target: 0 }, // Ramp down
];
```

**Expected Behavior:**

- Error rate may increase at peak (< 5%)
- Response times may degrade but remain usable
- System recovers after load reduction
- No data corruption or crashes

### 4. Spike Test Profile

**Purpose:** Test sudden traffic spikes and recovery.

**Use Cases:**

- Auto-scaling validation
- Circuit breaker testing
- Resilience testing

**Configuration:**

```javascript
const spikeTestStages = [
  { duration: '10s', target: 5 }, // Normal load
  { duration: '5s', target: 100 }, // Sudden spike to 100 VUs
  { duration: '30s', target: 100 }, // Hold spike
  { duration: '5s', target: 5 }, // Drop to normal
  { duration: '30s', target: 5 }, // Recovery period
  { duration: '10s', target: 0 }, // Ramp down
];
```

**Expected Behavior:**

- System handles sudden traffic increase
- May shed some requests during spike
- Full recovery after spike subsides
- No cascade failures

### 5. Soak Test Profile

**Purpose:** Find memory leaks and degradation over time.

**Use Cases:**

- Pre-release stability testing
- Memory leak detection
- Long-running stability validation

**Configuration:**

```javascript
const soakTestStages = [
  { duration: '1m', target: 30 }, // Ramp to moderate load
  { duration: '10m', target: 30 }, // Hold for 10 minutes
  { duration: '30s', target: 0 }, // Ramp down
];
```

**Expected Behavior:**

- Memory usage remains stable
- Response times don't degrade over time
- No connection leaks
- All resources properly released

## Performance Thresholds

### API Endpoints

| Metric                  | Threshold | Description                   |
| ----------------------- | --------- | ----------------------------- |
| `http_req_duration` p95 | < 500ms   | 95th percentile response time |
| `http_req_duration` p99 | < 1000ms  | 99th percentile response time |
| `http_req_duration` avg | < 200ms   | Average response time         |
| `http_req_failed`       | < 1%      | Error rate                    |
| `http_reqs`             | > 10/s    | Minimum throughput            |

### WebSocket Connections

| Metric                    | Threshold | Description             |
| ------------------------- | --------- | ----------------------- |
| `ws_connecting` p95       | < 200ms   | Connection time         |
| `ws_session_duration` avg | > 5s      | Minimum session length  |
| `ws_sessions` failed rate | < 5%      | Connection failure rate |

### WebSocket Scale Test

| Metric                             | Threshold | Description              |
| ---------------------------------- | --------- | ------------------------ |
| `ws_scale_connection_success`      | >= 95%    | Connection success rate  |
| `ws_scale_connect_time` p95        | < 2000ms  | Connection time at scale |
| `ws_scale_connection_errors`       | < 50      | Max error count          |
| `ws_scale_connection_duration` avg | > 30s     | Connection longevity     |

### Redis/Cache Performance

| Metric                          | Threshold | Description              |
| ------------------------------- | --------- | ------------------------ |
| `redis_cache_hit_duration` p95  | < 50ms    | Cache hit response time  |
| `redis_cache_miss_duration` p95 | < 200ms   | Cache miss response time |
| `redis_pubsub_latency` p95      | < 100ms   | Pub/sub message latency  |
| `redis_cache_error_rate`        | < 1%      | Cache error rate         |

## CI/CD Integration

### PR Gates (Blocking)

The following performance tests block PRs on failure:

| Test                     | Threshold            | Workflow         |
| ------------------------ | -------------------- | ---------------- |
| **Benchmark Tests**      | > 20% regression     | `benchmarks.yml` |
| **Memory Profiling**     | > 500MB per endpoint | `benchmarks.yml` |
| **Slow Query Detection** | > 50ms query time    | `benchmarks.yml` |

### Main Branch Gates (Blocking)

The following tests block merges to main on failure:

| Test              | Threshold      | Workflow         |
| ----------------- | -------------- | ---------------- |
| **k6 Load Tests** | All thresholds | `load-tests.yml` |

### Non-Blocking (Informational)

| Test                | Purpose                     | Schedule  |
| ------------------- | --------------------------- | --------- |
| **Stress Tests**    | Capacity planning           | Weekly    |
| **Soak Tests**      | Memory leak detection       | Weekly    |
| **WebSocket Scale** | Connection limit validation | On demand |

## Running Load Tests

### Locally

```bash
# Smoke test (quick validation)
./scripts/load-test.sh all smoke

# Average load test
./scripts/load-test.sh all average

# Stress test
./scripts/load-test.sh all stress

# Specific test suite
./scripts/load-test.sh events average
./scripts/load-test.sh websocket average
./scripts/load-test.sh redis average
./scripts/load-test.sh websocket-scale average
```

### Via k6 Directly

```bash
# With custom base URL
k6 run -e BASE_URL=http://localhost:8000 -e LOAD_PROFILE=stress tests/load/all.js

# WebSocket scale test with custom max connections
k6 run -e WS_URL=ws://localhost:8000 -e MAX_CONNECTIONS=2000 tests/load/websocket-scale.js
```

### Via CI/CD

```bash
# Manual trigger via GitHub Actions
gh workflow run load-tests.yml -f load_profile=stress -f test_suite=all
```

## Interpreting Results

### Key Metrics to Monitor

1. **Response Time Distribution**

   - p50, p95, p99 values
   - Look for bimodal distributions (cache hits vs misses)

2. **Error Rate Trends**

   - Sudden spikes indicate issues
   - Gradual increase may indicate resource exhaustion

3. **Throughput**

   - Should remain stable under sustained load
   - Dropping throughput indicates bottleneck

4. **Resource Utilization**
   - CPU, memory, connections
   - Correlate with performance degradation

### Common Issues

| Symptom               | Possible Cause             | Investigation                |
| --------------------- | -------------------------- | ---------------------------- |
| High p99 latency      | Database contention        | Check slow query logs        |
| Increasing error rate | Connection pool exhaustion | Check pool metrics           |
| WebSocket failures    | Max connections reached    | Check ulimits                |
| Memory growth         | Leak or unbounded caching  | Run soak test with profiling |

## References

- [k6 Documentation](https://k6.io/docs/)
- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [pytest-memray Documentation](https://pytest-memray.readthedocs.io/)
- Test files: `tests/load/*.js`
- Benchmark files: `backend/tests/benchmarks/*.py`
