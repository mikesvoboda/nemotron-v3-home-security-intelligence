# Smoke Tests for Deployment Verification

This directory contains smoke tests designed to verify that a deployed environment is healthy and fully functional after deployment.

## Purpose

Smoke tests are lightweight tests that run after deployment to verify:

- All services are running and responding
- Health check endpoints work correctly
- Service-to-service communication is functional
- WebSocket connectivity is available
- Monitoring stack is operational (if enabled)
- API endpoints return proper responses
- Data flows through critical paths

Smoke tests are NOT:

- End-to-end tests (no UI interaction testing)
- Load tests (no performance measurements)
- Comprehensive unit tests (no deep logic verification)
- Security tests (no penetration testing)

## Test Organization

### `test_deployment_health.py`

Tests core deployment health and API functionality:

- Backend health endpoints
- Frontend HTML serving
- Core API endpoints (cameras, events, detections)
- Service connectivity (database, cache)
- Data flow through critical paths
- Error handling and response format

### `test_websocket_smoke.py`

Tests WebSocket connectivity:

- WebSocket endpoint availability
- WebSocket upgrade protocol support
- WebSocket infrastructure dependencies
- Fallback polling endpoints

### `test_monitoring_smoke.py`

Tests optional monitoring stack:

- Prometheus metrics collection
- Grafana dashboard availability
- Jaeger distributed tracing
- AlertManager configuration

## Running Smoke Tests

### Basic Smoke Test (CI/CD pipeline)

```bash
# Run all critical smoke tests (default URLs)
pytest tests/smoke/ -m critical

# Run all smoke tests
pytest tests/smoke/

# Run with verbose output
pytest tests/smoke/ -v

# Run with specific backend URL
BACKEND_URL=http://staging.example.com:8000 pytest tests/smoke/ -m critical
```

### Against Staging Environment

```bash
# Before deploying to production, run full smoke test suite against staging
BACKEND_URL=http://staging-backend:8000 \
FRONTEND_URL=http://staging-frontend:5173 \
pytest tests/smoke/ -v --tb=short
```

### Against Local Development

```bash
# If services are running locally
pytest tests/smoke/ -m critical

# Or with custom URLs
BACKEND_URL=http://localhost:8000 \
FRONTEND_URL=http://localhost:3000 \
pytest tests/smoke/ -v
```

### Test Categories (Markers)

Run tests by category:

```bash
# Critical path tests (must always pass)
pytest tests/smoke/ -m critical

# Integration tests (service-to-service)
pytest tests/smoke/ -m integration

# WebSocket tests
pytest tests/smoke/ -m websocket

# Monitoring stack tests
pytest tests/smoke/ -m monitoring

# Exclude slow tests
pytest tests/smoke/ -m "not slow"

# Only slow tests
pytest tests/smoke/ -m slow
```

## Configuration

### Environment Variables

Set these environment variables to customize smoke test behavior:

| Variable             | Default                 | Purpose                                     |
| -------------------- | ----------------------- | ------------------------------------------- |
| `BACKEND_URL`        | `http://localhost:8000` | Backend API URL                             |
| `FRONTEND_URL`       | `http://localhost:3000` | Frontend URL                                |
| `ENVIRONMENT`        | `unknown`               | Deployment environment (staging/production) |
| `SMOKE_TEST_TIMEOUT` | `120`                   | Test timeout in seconds                     |
| `DEBUG`              | `false`                 | Enable debug logging                        |

### Example CI/CD Integration

In GitHub Actions or GitLab CI:

```yaml
- name: Run smoke tests against staging
  env:
    BACKEND_URL: ${{ secrets.STAGING_BACKEND_URL }}
    FRONTEND_URL: ${{ secrets.STAGING_FRONTEND_URL }}
  run: |
    pytest tests/smoke/ -m critical -v --tb=short
```

## Expected Test Results

### Passing Smoke Tests

A successful smoke test run should show:

```
test_backend_readiness_endpoint_responds PASSED
test_backend_health_endpoint_responds PASSED
test_frontend_serves_html PASSED
test_system_stats_endpoint PASSED
test_cameras_endpoint PASSED
test_events_endpoint PASSED
test_detections_endpoint PASSED
test_backend_can_reach_database PASSED
test_api_response_has_proper_json PASSED

======================== 9 passed in 2.34s ========================
```

### What If Tests Fail?

If a critical smoke test fails:

1. **Backend unreachable**: Check backend service is running and healthy

   ```bash
   docker compose -f docker-compose.staging.yml ps
   docker compose -f docker-compose.staging.yml logs backend
   ```

2. **Health endpoint returns unhealthy**: Check dependencies

   ```bash
   # Check database
   docker compose -f docker-compose.staging.yml exec backend python -c \
     "import httpx; print(httpx.get('http://localhost:8000/api/system/health').json())"
   ```

3. **API endpoint errors**: Check application logs

   ```bash
   docker compose -f docker-compose.staging.yml logs backend --tail=100
   ```

4. **WebSocket tests fail**: WebSocket failures are non-critical - fallback polling works

   - Verify browser console for WebSocket errors
   - Check server-sent event fallback is working

5. **Monitoring tests fail**: Monitoring is optional
   - These tests are skipped if monitoring is not enabled
   - Check `docker compose ps` to see which services are running

## Integration with CI/CD

### GitHub Actions Example

```yaml
# In .github/workflows/deploy.yml
- name: Run smoke tests
  run: |
    pytest tests/smoke/ -m critical -v \
      --junit-xml=smoke-test-results.xml
  env:
    BACKEND_URL: http://localhost:8000
    FRONTEND_URL: http://localhost:3000

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: smoke-test-results
    path: smoke-test-results.xml
```

### Deployment Checklist

Before marking a deployment as complete:

- [ ] Run smoke tests: `pytest tests/smoke/ -m critical`
- [ ] All critical tests pass
- [ ] WebSocket tests pass (or fallback is working)
- [ ] Monitoring stack is healthy (if monitoring enabled)
- [ ] No deployment errors in application logs
- [ ] Health endpoints report "healthy" or "degraded" (not "unhealthy")

## Adding New Smoke Tests

When adding new smoke tests:

1. **Choose the right file**:

   - Core API tests: `test_deployment_health.py`
   - WebSocket tests: `test_websocket_smoke.py`
   - Monitoring tests: `test_monitoring_smoke.py`

2. **Use appropriate markers**:

   ```python
   @pytest.mark.critical  # Must always pass
   @pytest.mark.integration  # Service-to-service
   @pytest.mark.websocket  # WebSocket specific
   @pytest.mark.monitoring  # Monitoring stack
   @pytest.mark.slow  # Takes >5 seconds
   ```

3. **Write descriptive tests**:

   ```python
   @pytest.mark.critical
   def test_something_important(self, http_client: httpx.Client, backend_url: str):
       """
       Description of what this test verifies.

       Explains: What is being tested and why it matters
       """
       response = http_client.get(f"{backend_url}/api/endpoint")
       assert response.status_code == 200
   ```

4. **Handle optional services gracefully**:
   ```python
   @pytest.mark.monitoring
   def test_optional_feature(self, http_client: httpx.Client):
       try:
           response = http_client.get("http://optional-service/health")
       except httpx.RequestError:
           pytest.skip("Optional service not available")
   ```

## Troubleshooting

### Tests timeout

If tests consistently timeout:

```bash
# Increase timeout
SMOKE_TEST_TIMEOUT=300 pytest tests/smoke/ -v

# Check backend is healthy
curl http://localhost:8000/api/system/health/ready
```

### Connection refused errors

If tests can't connect to backend:

```bash
# Verify services are running
docker compose -f docker-compose.staging.yml ps

# Check backend is listening
netstat -tlnp | grep 8000
# or
ss -tlnp | grep 8000

# Start services if needed
docker compose -f docker-compose.staging.yml up -d
```

### Invalid response format

If tests fail with "not valid JSON":

```bash
# Check raw response
curl -v http://localhost:8000/api/system/health

# Check application logs
docker compose -f docker-compose.staging.yml logs backend --tail=50
```

## Performance

Typical smoke test execution times:

- **Critical tests only**: ~2-5 seconds
- **All tests (with timeouts)**: ~10-30 seconds
- **With slow tests**: ~30-60 seconds

To improve performance:

```bash
# Run only critical tests (fastest)
pytest tests/smoke/ -m critical

# Run without slow tests
pytest tests/smoke/ -m "not slow"

# Run in parallel (if using pytest-xdist)
pytest tests/smoke/ -n auto
```

## References

- [Deployment Verification Checklist](../../docs/DEPLOYMENT_VERIFICATION_CHECKLIST.md)
- [Health Check Strategy](../../docs/HEALTH_CHECK_STRATEGY.md)
- [Staging Environment](../../docker-compose.staging.yml)
