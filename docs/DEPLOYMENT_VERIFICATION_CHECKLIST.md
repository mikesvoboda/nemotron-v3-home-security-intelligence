# Deployment Verification Checklist

This checklist ensures that deployments to staging or production are complete, verified, and ready for use.

## Pre-Deployment Verification (Before deploy workflow runs)

- [ ] Code review approved and merged to `main`
- [ ] All CI checks passed (tests, linting, security scanning)
- [ ] Commit is tagged with version (e.g., `v1.2.3`)
- [ ] Release notes prepared
- [ ] Database migrations reviewed (if applicable)
- [ ] Environment variables are documented
- [ ] Dependencies are up to date
- [ ] No breaking changes to API contracts

## Build Verification (During CI/CD deployment)

- [ ] Docker images build successfully
- [ ] Image scan passes (no critical vulnerabilities)
- [ ] Images are tagged correctly
  - [ ] Latest tag points to main branch
  - [ ] Commit SHA tag is created
  - [ ] Version tag is created (if applicable)
- [ ] Images are pushed to registry (GHCR)
- [ ] SBOM (Software Bill of Materials) generated
- [ ] Container images are signed with cosign
- [ ] SLSA provenance attestation created
- [ ] Build logs are clean (no warnings)

## Post-Build Smoke Tests (CI/CD automation)

Run after container images are pushed:

```bash
pytest tests/smoke/ -m critical -v
```

- [ ] Backend readiness endpoint responds (200)
- [ ] Backend health endpoint responds (200)
- [ ] Frontend serves HTML (200)
- [ ] API endpoints respond:
  - [ ] `/api/system/stats` returns 200
  - [ ] `/api/cameras` returns 200
  - [ ] `/api/events` returns 200
  - [ ] `/api/detections` returns 200
- [ ] Error handling works:
  - [ ] Invalid endpoints return 404
  - [ ] Invalid methods return 405
- [ ] Responses are valid JSON
- [ ] All critical tests pass in CI log

## Staging Deployment Steps

### 1. Prepare Staging Environment

```bash
# Pull latest images
docker pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
docker pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# Create/update .env.staging (from template)
cp .env.example .env.staging

# Set credentials in .env.staging
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export GF_ADMIN_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)
```

### 2. Start Staging Services

```bash
docker compose -f docker-compose.staging.yml up -d --wait

# Verify all services are healthy
docker compose -f docker-compose.staging.yml ps
```

### 3. Verify Service Startup

- [ ] All containers are running (status: "Up")
- [ ] No container restarts (restart count should be 0)
- [ ] Logs show no errors:

```bash
docker compose -f docker-compose.staging.yml logs --tail=50 backend frontend
```

### 4. Run Smoke Tests

```bash
BACKEND_URL=http://staging.example.com:8000 \
FRONTEND_URL=http://staging.example.com:5173 \
pytest tests/smoke/ -m critical -v

# Or for local staging:
pytest tests/smoke/ -m critical -v
```

- [ ] All critical smoke tests pass
- [ ] No test timeouts
- [ ] Backend is healthy
- [ ] Frontend is accessible

### 5. Database Verification

```bash
# Check database is running
docker compose -f docker-compose.staging.yml exec postgres pg_isready -U security

# Verify database schema
docker compose -f docker-compose.staging.yml exec postgres psql -U security -d security -c "\dt"

# Check recent migrations applied
docker compose -f docker-compose.staging.yml logs backend | grep -i migration
```

- [ ] Database is accessible
- [ ] Schema is up to date
- [ ] Migrations completed without errors

### 6. Redis Verification

```bash
# Check Redis is running
docker compose -f docker-compose.staging.yml exec redis redis-cli PING

# Check cache connectivity
docker compose -f docker-compose.staging.yml exec backend redis-cli -h redis PING
```

- [ ] Redis responds to PING
- [ ] Memory usage is reasonable
- [ ] Connection pooling works

### 7. API Endpoint Verification

```bash
# Test key endpoints
curl http://localhost:8000/api/system/health
curl http://localhost:8000/api/cameras
curl http://localhost:8000/api/events?limit=5
curl http://localhost:8000/api/detections?limit=5
```

- [ ] Health endpoint shows "healthy" or "degraded"
- [ ] Cameras endpoint returns valid JSON
- [ ] Events endpoint returns valid JSON
- [ ] Detections endpoint returns valid JSON
- [ ] All responses contain expected fields

### 8. Frontend Verification

```bash
# Check frontend is serving
curl -I http://localhost:5173/

# Check for common HTML markers
curl http://localhost:5173/ | grep -E "(<!DOCTYPE|<html|<body)"
```

- [ ] Frontend returns 200 OK
- [ ] Response includes HTML
- [ ] No redirect loops
- [ ] Static assets are loading (check browser console)

### 9. WebSocket Verification

```bash
# Test WebSocket endpoint availability (should fail gracefully)
curl -i http://localhost:8000/ws/events \
  -H "Upgrade: websocket" \
  -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13"
```

- [ ] WebSocket endpoint exists (not 404)
- [ ] Responds to upgrade request
- [ ] No 500 errors

Or run WebSocket smoke tests:

```bash
pytest tests/smoke/test_websocket_smoke.py -v
```

- [ ] All WebSocket tests pass (or skip if not available)
- [ ] No connection errors in logs

### 10. Monitoring Stack Verification (if enabled)

```bash
# Check Prometheus
curl http://localhost:9090/-/healthy

# Check Grafana
curl http://localhost:3002/api/health

# Check Jaeger
curl http://localhost:16686/api/health

# Check AlertManager
curl http://localhost:9093/-/healthy
```

Run monitoring smoke tests:

```bash
pytest tests/smoke/test_monitoring_smoke.py -v
```

- [ ] Prometheus is healthy and scraping targets
- [ ] Grafana dashboards are available
- [ ] Jaeger is collecting traces
- [ ] AlertManager is configured
- [ ] All datasources are connected

### 11. Performance Baseline (Optional)

```bash
# Load test staging with synthetic traffic
artillery quick --count 10 --num 100 http://localhost:5173/

# Check response times in Prometheus
curl 'http://localhost:9090/api/v1/query?query=http_request_duration_seconds'
```

- [ ] Response times are acceptable
- [ ] No 5xx errors under load
- [ ] CPU usage is reasonable

### 12. Security Verification

```bash
# Check for security headers
curl -I http://localhost:5173/ | grep -i "security\|x-frame\|csp"

# Check HTTPS (if applicable)
curl -v https://staging.example.com:5173/

# Check database has password
docker compose -f docker-compose.staging.yml exec postgres psql -U security -d security -c "SELECT version();"
```

- [ ] Security headers are present (if applicable)
- [ ] HTTPS is enabled (if applicable)
- [ ] Database requires authentication
- [ ] No sensitive data in logs

## Pre-Production Deployment

### 1. Production Image Pull

```bash
# Verify image exists and is signed
docker pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:v1.2.3
docker pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:v1.2.3

# Verify image signature
cosign verify ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:v1.2.3
```

- [ ] Images are signed
- [ ] SBOM is available
- [ ] No critical vulnerabilities

### 2. Backup Production State

```bash
# Backup database
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U security security > backup-prod-$(date +%Y%m%d-%H%M%S).sql

# Backup Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli BGSAVE
docker compose -f docker-compose.prod.yml exec redis redis-cli SAVE
```

- [ ] Database backup created
- [ ] Redis RDB file saved
- [ ] Backup file verified (not empty)
- [ ] Backup stored in safe location

### 3. Production Deployment

```bash
# Update image tags in docker-compose.prod.yml to point to v1.2.3
# or use IMAGE_TAG environment variable
IMAGE_TAG=v1.2.3 docker compose -f docker-compose.prod.yml up -d

# Wait for services to stabilize
sleep 30

# Verify deployment
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec backend python -c \
  "import httpx; print(httpx.get('http://localhost:8000/api/system/health/ready').json())"
```

- [ ] All services started successfully
- [ ] No error messages in logs
- [ ] Health checks passing

### 4. Post-Deployment Validation

Run same smoke tests against production:

```bash
BACKEND_URL=http://production.example.com:8000 \
FRONTEND_URL=http://production.example.com \
pytest tests/smoke/ -m critical -v
```

- [ ] All critical smoke tests pass
- [ ] No degradation in response times
- [ ] Error rate is near zero

### 5. User Acceptance Testing

- [ ] Users can log in (if applicable)
- [ ] Camera feeds are loading
- [ ] Event history is accessible
- [ ] Real-time updates are working (WebSocket or polling)
- [ ] No obvious bugs or errors
- [ ] Performance is acceptable

### 6. Monitor for Issues

```bash
# Watch logs for errors
docker compose -f docker-compose.prod.yml logs -f backend

# Check metrics in Prometheus/Grafana
# Look for:
# - Error rate
# - Response latency
# - Resource usage
# - Database connections
# - Cache hit rate

# Check application alerts
# AlertManager should be quiet (no alerts triggered)
```

- [ ] No critical errors in application logs
- [ ] Metrics are normal
- [ ] No alerts triggered
- [ ] Database connections stable
- [ ] CPU/Memory usage normal

## Rollback Procedure (If issues detected)

### Immediate Actions

```bash
# If deployment is causing critical issues:
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d  # Starts with previous version

# Or switch back to previous image tag:
# Update docker-compose.prod.yml to previous version
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Database Rollback (if needed)

```bash
# Restore from backup
docker compose -f docker-compose.prod.yml down
docker cp backup-prod-TIMESTAMP.sql postgres:/tmp/
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for postgres to start
sleep 10

# Restore database
docker compose -f docker-compose.prod.yml exec postgres psql -U security < /tmp/backup-prod-TIMESTAMP.sql

# Start remaining services
docker compose -f docker-compose.prod.yml up -d
```

Rollback checklist:

- [ ] Rollback decision made and communicated
- [ ] Previous version image pulled
- [ ] Services stopped gracefully
- [ ] Database rolled back (if applicable)
- [ ] Services restarted with previous version
- [ ] Smoke tests pass with previous version
- [ ] Issue post-mortem scheduled

## Deployment Status Summary

Create a summary after deployment:

```
Deployment Date: [date]
Version: [version tag]
Environment: [staging/production]

Pre-deployment:
- [x] Code review approved
- [x] Tests passed
- [x] Security scan passed

Deployment:
- [x] Images built
- [x] Images pushed
- [x] Smoke tests passed

Post-deployment:
- [x] Services healthy
- [x] Health checks passing
- [x] No errors in logs
- [x] Monitoring stack healthy

Status: SUCCESSFUL / FAILED (if failed)
Duration: [deployment time]
Notes: [any relevant notes]

Signed by: [name]
Date: [date]
```

## Related Documentation

- [Deployment Troubleshooting Guide](DEPLOYMENT_TROUBLESHOOTING.md)
- [Docker Deployment Guide](DOCKER_DEPLOYMENT.md)
- [Health Check Strategy](HEALTH_CHECK_STRATEGY.md)
- [Smoke Test README](../tests/smoke/README.md)
- [Staging Environment Config](../docker-compose.staging.yml)

## Quick Reference

### Critical Commands

```bash
# Start staging
docker compose -f docker-compose.staging.yml up -d

# Run smoke tests
pytest tests/smoke/ -m critical -v

# Check health
curl http://localhost:8000/api/system/health

# View logs
docker compose -f docker-compose.staging.yml logs -f backend

# Stop services
docker compose -f docker-compose.staging.yml down
```

### Monitoring Dashboards

- Grafana: `http://localhost:3002`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- AlertManager: `http://localhost:9093`

### Getting Help

If deployment verification fails:

1. Check logs: `docker compose logs backend`
2. Run smoke tests: `pytest tests/smoke/ -v`
3. Check health endpoint: `curl http://localhost:8000/api/system/health`
4. Review [troubleshooting guide](DEPLOYMENT_TROUBLESHOOTING.md)
