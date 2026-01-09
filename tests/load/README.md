# k6 Load Testing Suite

Load and performance testing for the Home Security Intelligence API using [k6](https://k6.io/).

## Prerequisites

### Install k6

```bash
# macOS
brew install k6

# Linux (Debian/Ubuntu)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Docker
docker pull grafana/k6
```

### Start the Backend

```bash
# Start the backend services
podman-compose -f docker-compose.prod.yml up -d

# Verify API is ready
curl http://localhost:8000/api/system/health/ready
```

## Quick Start

```bash
# Run all tests with average load
./scripts/load-test.sh

# Run specific test suites
./scripts/load-test.sh events     # Events API only
./scripts/load-test.sh cameras    # Cameras API only
./scripts/load-test.sh websocket  # WebSocket only
./scripts/load-test.sh mutations  # Write operations

# Different load profiles
./scripts/load-test.sh all smoke   # Quick 10-second validation
./scripts/load-test.sh all stress  # Find breaking points
./scripts/load-test.sh all spike   # Test spike handling
./scripts/load-test.sh all soak    # Extended duration test
```

## Load Profiles

| Profile     | VUs     | Duration | Use Case             |
| ----------- | ------- | -------- | -------------------- |
| **smoke**   | 1       | 10s      | CI/CD quick check    |
| **average** | 10      | 2min     | Regular validation   |
| **stress**  | 100     | 5min     | Find breaking points |
| **spike**   | 5→100→5 | 1.5min   | Test auto-scaling    |
| **soak**    | 30      | 10min+   | Find memory leaks    |

## Test Suites

### Events API (`events.js`)

Tests the security events endpoints:

- List events with filters and pagination
- Event statistics
- Full-text search
- Single event retrieval
- Event detections

### Cameras API (`cameras.js`)

Tests the camera management endpoints:

- List cameras with status filter
- Single camera details
- Snapshot image serving
- Activity baselines

### WebSocket (`websocket.js`)

Tests real-time streaming:

- Event stream connections
- System status stream
- Ping/pong latency
- Concurrent connections

### Mutations (`mutations.js`)

Tests write operations:

- Event updates
- Camera creation
- Admin seed endpoints (dev only)
- Frontend log submission

### All (`all.js`)

Combined realistic traffic simulation:

- 35% Events API
- 30% Cameras API
- 15% System API
- 10% WebSocket
- 10% Detections

### WebSocket Scale (`websocket-scale.js`)

Tests WebSocket connection scalability:

- Connection limit testing (1000+ concurrent connections)
- Connection churn and recovery
- Long-lived connection stability
- Scale metrics: success rate, connect time, duration

```bash
# Test with 1000 concurrent connections
./scripts/load-test.sh websocket-scale average

# Custom connection count
k6 run -e MAX_CONNECTIONS=2000 tests/load/websocket-scale.js
```

### Redis Performance (`redis.js`)

Tests Redis-backed operations:

- Cache hit/miss performance
- Cache invalidation patterns
- Pub/sub latency via WebSocket

```bash
# Test Redis performance
./scripts/load-test.sh redis average
```

## Configuration

### Environment Variables

```bash
# API endpoint (default: http://localhost:8000)
export BASE_URL=http://localhost:8000

# WebSocket endpoint (default: ws://localhost:8000)
export WS_URL=ws://localhost:8000

# API key for authenticated endpoints (optional)
export API_KEY=your-api-key

# Admin API key for seed endpoints (optional)
export ADMIN_API_KEY=your-admin-key

# Select load profile
export LOAD_PROFILE=stress
```

### Running with Custom Config

```bash
# Custom base URL
BASE_URL=http://my-server:8000 ./scripts/load-test.sh all

# With API key authentication
API_KEY=secret ./scripts/load-test.sh all stress

# Direct k6 execution
k6 run \
  -e BASE_URL=http://localhost:8000 \
  -e LOAD_PROFILE=stress \
  tests/load/all.js
```

## Thresholds

Tests will fail if these thresholds are not met:

### Response Time

| Metric  | Threshold |
| ------- | --------- |
| p95     | < 500ms   |
| p99     | < 1000ms  |
| average | < 200ms   |

### Error Rate

| Metric             | Threshold |
| ------------------ | --------- |
| HTTP failures      | < 1%      |
| WebSocket failures | < 5%      |

### Endpoint-Specific

| Endpoint        | p95    |
| --------------- | ------ |
| Events List     | 400ms  |
| Events Stats    | 300ms  |
| Events Search   | 500ms  |
| Cameras List    | 300ms  |
| Camera Snapshot | 1000ms |

## Results

Results are saved to `results/`:

```
results/
  k6-all-average-20250105_143022.json     # Detailed metrics
  k6-all-average-20250105_143022.txt      # Summary
```

### Viewing Results

```bash
# View summary
cat results/k6-all-average-*.txt | jq .

# Extract key metrics
jq '.metrics.http_req_duration.values' results/k6-*.json
```

### Grafana Integration

k6 results can be visualized in Grafana:

```bash
# Run with InfluxDB output
k6 run --out influxdb=http://localhost:8086/k6 tests/load/all.js

# Or with Prometheus
k6 run --out experimental-prometheus-rw tests/load/all.js
```

## Examples

### Basic Smoke Test

```bash
# Quick validation before deployment
./scripts/load-test.sh all smoke
```

### Pre-Release Stress Test

```bash
# Full stress test before release
./scripts/load-test.sh all stress
```

### WebSocket Load Test

```bash
# Test real-time streaming under load
./scripts/load-test.sh websocket stress
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Load Test
  run: ./scripts/load-test.sh all smoke
  env:
    BASE_URL: http://localhost:8000
```

## Troubleshooting

### API Not Reachable

```bash
# Check if backend is running
curl http://localhost:8000/api/system/health/ready

# Start backend
podman-compose -f docker-compose.prod.yml up -d
```

### High Error Rate

- Check server logs for errors
- Verify database connectivity
- Check Redis availability
- Monitor GPU utilization for AI endpoints

### Slow Response Times

- Check database query performance
- Monitor Redis cache hit rate
- Review AI service latency
- Check for memory pressure

### WebSocket Connection Failures

- Verify WebSocket URL is correct
- Check for proxy/firewall blocking
- Review connection limits in server config

## Further Reading

- [k6 Documentation](https://k6.io/docs/)
- [k6 Best Practices](https://k6.io/docs/testing-guides/api-load-testing/)
- [Grafana k6 Cloud](https://k6.io/cloud/)
