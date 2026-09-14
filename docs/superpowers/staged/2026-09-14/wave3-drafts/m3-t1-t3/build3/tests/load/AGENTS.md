# Load Testing with k6 - Agent Guide

## Purpose

This directory contains k6 load/performance tests for the security dashboard API. These tests validate that the system can handle expected traffic volumes and identify performance bottlenecks before they impact production.

## Directory Structure

```
tests/load/
  AGENTS.md          # This file - agent guidance
  README.md          # User documentation with examples
  config.js          # Shared configuration, thresholds, and load profiles
  events.js          # Events API load tests
  cameras.js         # Cameras API load tests
  websocket.js       # WebSocket connection tests
  mutations.js       # POST/PATCH/DELETE endpoint tests
  all.js             # Combined realistic traffic simulation
```

## Quick Start

```bash
# Install k6 (if not already installed)
brew install k6  # macOS
# or: sudo apt-get install k6  # Linux

# Run all tests with average load
./scripts/load-test.sh

# Run specific test suite
./scripts/load-test.sh events
./scripts/load-test.sh cameras
./scripts/load-test.sh websocket

# Run with different load profiles
./scripts/load-test.sh all smoke   # Quick validation
./scripts/load-test.sh all stress  # Find breaking points
./scripts/load-test.sh all spike   # Test spike handling
```

## Test Files

### config.js

Shared configuration including:

- Base URLs (configurable via environment)
- Threshold definitions for all metrics
- Load profile stages (smoke, average, stress, spike, soak)
- API endpoint paths
- Helper functions for URL building

### events.js

Tests the Events API (`/api/events/*`):

- `GET /api/events` - List with pagination and filters
- `GET /api/events/stats` - Aggregated statistics
- `GET /api/events/search` - Full-text search
- `GET /api/events/{id}` - Single event details
- `GET /api/events/{id}/detections` - Event detections

### cameras.js

Tests the Cameras API (`/api/cameras/*`):

- `GET /api/cameras` - List with status filter
- `GET /api/cameras/{id}` - Single camera
- `GET /api/cameras/{id}/snapshot` - Image serving
- `GET /api/cameras/{id}/baseline` - Activity baselines

### websocket.js

Tests WebSocket connections:

- `/ws/events` - Security event stream
- `/ws/system` - System status stream
- Connection establishment time
- Ping/pong latency
- Message handling
- Concurrent connection handling

### mutations.js

Tests write operations (development environment):

- `PATCH /api/events/{id}` - Update events
- `POST /api/admin/seed/cameras` - Seed test data
- `POST /api/admin/seed/events` - Seed test events
- `POST /api/cameras` - Create cameras
- `POST /api/logs/frontend` - Log submission

### all.js

Combined traffic simulation with realistic distribution:

- 35% Events API
- 30% Cameras API
- 15% System API
- 10% WebSocket connections
- 10% Detections API

## Load Profiles

| Profile | Purpose                    | VUs     | Duration |
| ------- | -------------------------- | ------- | -------- |
| smoke   | Quick validation           | 1       | 10s      |
| average | Normal production load     | 10      | 2min     |
| stress  | Find breaking points       | 100     | 5min     |
| spike   | Test sudden traffic bursts | 5→100→5 | 1.5min   |
| soak    | Memory leak detection      | 30      | 10min+   |

## Thresholds

### Standard API Thresholds

| Metric              | Threshold    | Description                 |
| ------------------- | ------------ | --------------------------- |
| `http_req_duration` | p95 < 500ms  | 95% of requests under 500ms |
| `http_req_duration` | p99 < 1000ms | 99% of requests under 1s    |
| `http_req_duration` | avg < 200ms  | Average response time       |
| `http_req_failed`   | rate < 1%    | Error rate                  |
| `http_reqs`         | rate > 10/s  | Minimum throughput          |

### WebSocket Thresholds

| Metric                       | Threshold    | Description         |
| ---------------------------- | ------------ | ------------------- |
| `ws_connecting`              | p95 < 200ms  | Connection time     |
| `ws_session_duration`        | avg > 5000ms | Sessions stay open  |
| `ws_sessions{status:failed}` | rate < 5%    | Connection failures |

### Endpoint-Specific Thresholds

| Endpoint        | p95    | Average |
| --------------- | ------ | ------- |
| Events List     | 400ms  | 200ms   |
| Events Stats    | 300ms  | 150ms   |
| Events Search   | 500ms  | 250ms   |
| Camera List     | 300ms  | 150ms   |
| Camera Get      | 200ms  | 100ms   |
| Camera Snapshot | 1000ms | 500ms   |

## Custom Metrics

Each test file defines custom metrics for detailed analysis:

```javascript
// Example from events.js
const eventListDuration = new Trend('event_list_duration', true);
const eventStatsDuration = new Trend('event_stats_duration', true);
const eventSearchDuration = new Trend('event_search_duration', true);
const eventErrorRate = new Rate('event_error_rate');
const eventRequestCount = new Counter('event_request_count');
```

## Environment Variables

| Variable        | Default               | Description                         |
| --------------- | --------------------- | ----------------------------------- |
| `BASE_URL`      | http://localhost:8000 | API base URL                        |
| `WS_URL`        | ws://localhost:8000   | WebSocket URL                       |
| `LOAD_PROFILE`  | average               | Load profile to use                 |
| `API_KEY`       | (empty)               | API key for authenticated endpoints |
| `ADMIN_API_KEY` | (empty)               | Admin API key for seed endpoints    |

## Interpreting Results

### Success Criteria

- All thresholds pass (green checkmarks)
- Error rate < 1%
- p95 response times within limits
- WebSocket connections stable

### Warning Signs

- Increasing response times during test
- Growing error rate over time
- Memory/CPU exhaustion on server
- Connection timeouts

### Common Issues

1. **High p95 but low average**: Occasional slow queries (check database)
2. **Increasing error rate**: Resource exhaustion (scale up)
3. **WebSocket failures**: Connection limits (check server config)
4. **Timeout errors**: Slow AI services (check GPU load)

## Integration with CI/CD

Load tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run Load Tests
  run: |
    ./scripts/load-test.sh all smoke
  env:
    BASE_URL: http://localhost:8000
```

Use `smoke` profile for CI (quick validation), `stress` for release testing.

## Related Documentation

- **scripts/load-test.sh**: Runner script with usage examples
- **tests/load/README.md**: User-facing documentation
- **backend/tests/AGENTS.md**: Backend test infrastructure
- **CLAUDE.md**: Project testing requirements
