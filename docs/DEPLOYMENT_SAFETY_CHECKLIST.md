# Deployment Safety Checklist

This checklist ensures safe and reliable deployments of the Home Security Intelligence system. Complete all items before deploying to production.

## Pre-Deployment Validation

### Environment and Configuration

- [ ] **Secrets Generated**

  ```bash
  # Verify .env file exists and has secure values
  [ -f .env ] && echo "✓ .env exists" || echo "✗ Missing .env"
  grep -q "POSTGRES_PASSWORD" .env && echo "✓ DB password set" || echo "✗ Missing DB password"
  grep -qE "password|changeme|example" .env && echo "✗ Insecure password detected" || echo "✓ Passwords look secure"
  ```

- [ ] **Required Variables Set**

  ```bash
  # Check critical environment variables
  grep -qE "DATABASE_URL=postgresql" .env || echo "✗ Missing DATABASE_URL"
  grep -qE "REDIS_URL=redis://" .env || echo "✗ Missing REDIS_URL"
  grep -qE "FOSCAM_BASE_PATH=" .env || echo "✗ Missing FOSCAM_BASE_PATH"
  grep -qE "RTDETR_URL=" .env || echo "✗ Missing RTDETR_URL"
  grep -qE "NEMOTRON_URL=" .env || echo "✗ Missing NEMOTRON_URL"
  ```

- [ ] **AI Service URLs Correct for Deployment Mode**

  ```bash
  # Production (containerized): should use container names
  grep "RTDETR_URL=http://ai-detector:8090" .env
  grep "NEMOTRON_URL=http://ai-llm:8091" .env

  # OR Development (host-run): should use host gateway
  grep "RTDETR_URL=http://host.docker.internal:8090" .env
  grep "NEMOTRON_URL=http://host.docker.internal:8091" .env
  ```

  See `docs/operator/deployment-modes.md` for guidance.

- [ ] **File Paths Exist and Accessible**

  ```bash
  # Camera upload directory
  [ -d "$FOSCAM_BASE_PATH" ] && ls -ld "$FOSCAM_BASE_PATH" || echo "✗ Camera path not found"

  # AI models directory
  [ -d "$AI_MODELS_PATH" ] && ls -ld "$AI_MODELS_PATH" || echo "✗ AI models path not found"

  # Verify model files
  ls -lh "$AI_MODELS_PATH/nemotron/nemotron-3-nano-30b-a3b-q4km/"*.gguf
  ```

- [ ] **Monitoring Credentials Set (if using)**
  ```bash
  # If using Grafana
  grep -q "GF_ADMIN_PASSWORD" .env && echo "✓ Grafana password set" || echo "✗ Missing Grafana password"
  ```

### System Resources

- [ ] **Disk Space Available**

  ```bash
  df -h /
  df -h "$FOSCAM_BASE_PATH"
  df -h "$AI_MODELS_PATH"

  # Minimum: 100 GB free for production
  # Recommended: 500 GB free
  ```

- [ ] **GPU Available**

  ```bash
  nvidia-smi || echo "✗ GPU not detected"
  nvidia-smi --query-gpu=memory.total --format=csv,noheader

  # Minimum: 16 GB VRAM
  # Recommended: 24 GB VRAM
  ```

- [ ] **NVIDIA Container Toolkit Installed**

  ```bash
  docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
  # Should show GPU info, not error
  ```

- [ ] **Network Ports Available**
  ```bash
  # Check if ports are free
  for port in 5173 8000 8090 8091 8092 8093 8094 5432 6379; do
    if sudo lsof -i :$port > /dev/null 2>&1; then
      echo "✗ Port $port in use"
    else
      echo "✓ Port $port available"
    fi
  done
  ```

### Docker/Podman

- [ ] **Container Runtime Installed**

  ```bash
  docker --version || podman --version
  docker compose version || podman-compose --version
  ```

- [ ] **Images Available or Build Succeeds**

  ```bash
  # If using GHCR
  docker pull ghcr.io/your-org/home-security-intelligence/backend:latest
  docker pull ghcr.io/your-org/home-security-intelligence/frontend:latest

  # If building locally
  docker compose -f docker-compose.prod.yml build --no-cache
  ```

- [ ] **Compose File Valid**
  ```bash
  docker compose -f docker-compose.prod.yml config
  # Should output valid YAML without errors
  ```

### Network and Firewall

- [ ] **Firewall Rules Allow Traffic**

  ```bash
  # For external access (if needed)
  sudo ufw status
  sudo ufw allow 5173/tcp  # Frontend
  sudo ufw allow 8000/tcp  # Backend API
  ```

- [ ] **DNS/Hosts Configured (if using custom domain)**

  ```bash
  # Test resolution
  nslookup your-domain.com

  # Or check /etc/hosts
  cat /etc/hosts | grep your-domain
  ```

### Backup Strategy

- [ ] **Backup Storage Configured**

  ```bash
  # Ensure backup directory exists
  mkdir -p /var/backups/hsi
  ls -ld /var/backups/hsi
  ```

- [ ] **Backup Script Tested**

  ```bash
  # Test database backup
  docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U security -d security > test-backup.sql
  [ -s test-backup.sql ] && echo "✓ Backup works" || echo "✗ Backup failed"
  rm test-backup.sql
  ```

- [ ] **Automated Backups Scheduled (production only)**
  ```bash
  crontab -l | grep pg_dump
  # Should show daily backup cron job
  ```

---

## Service Dependency Verification

### Startup Order

Services must start in this order with health checks passing:

1. **PostgreSQL** (10-15 seconds)
2. **Redis** (5-10 seconds)
3. **AI Services** (60-180 seconds for model loading)
4. **Backend** (waits for DB + Redis)
5. **Frontend** (waits for Backend)

### Pre-Start Checks

- [ ] **PostgreSQL Ready**

  ```bash
  docker compose -f docker-compose.prod.yml up -d postgres
  sleep 10
  docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security
  # Expected: "accepting connections"
  ```

- [ ] **Redis Ready**

  ```bash
  docker compose -f docker-compose.prod.yml up -d redis
  sleep 5
  docker compose -f docker-compose.prod.yml exec redis redis-cli ping
  # Expected: "PONG"
  ```

- [ ] **AI Services Ready**

  ```bash
  docker compose -f docker-compose.prod.yml up -d ai-detector ai-llm ai-florence ai-clip ai-enrichment
  sleep 120

  # Check health endpoints
  curl http://localhost:8090/health  # RT-DETRv2
  curl http://localhost:8091/health  # Nemotron
  curl http://localhost:8092/health  # Florence (optional)
  curl http://localhost:8093/health  # CLIP (optional)
  curl http://localhost:8094/health  # Enrichment (optional)

  # Expected: {"status": "ok"} or similar
  ```

- [ ] **Backend Ready**

  ```bash
  docker compose -f docker-compose.prod.yml up -d backend
  sleep 30

  curl http://localhost:8000/api/system/health/ready
  # Expected: {"status": "ready", "database": "connected", "redis": "connected", ...}
  ```

- [ ] **Frontend Ready**

  ```bash
  docker compose -f docker-compose.prod.yml up -d frontend
  sleep 15

  curl -s http://localhost:5173 | grep -q "<title>" && echo "✓ Frontend serves HTML" || echo "✗ Frontend not responding"
  ```

---

## Post-Deployment Smoke Tests

### Health Checks

- [ ] **All Services Healthy**

  ```bash
  docker compose -f docker-compose.prod.yml ps
  # All services should show "Up" and "(healthy)"
  ```

- [ ] **Backend Health Endpoint**

  ```bash
  curl http://localhost:8000/api/system/health/ready | jq .
  # Check: status=ready, database=connected, redis=connected, workers running
  ```

- [ ] **AI Service Health**
  ```bash
  curl http://localhost:8000/api/system/health | jq '.services'
  # Check: rtdetr and nemotron show "healthy"
  ```

### Functional Tests

- [ ] **Database Connectivity**

  ```bash
  # Query cameras table
  docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "SELECT COUNT(*) FROM cameras;"
  ```

- [ ] **Redis Connectivity**

  ```bash
  # Test set/get
  docker compose -f docker-compose.prod.yml exec redis redis-cli SET test_key test_value
  docker compose -f docker-compose.prod.yml exec redis redis-cli GET test_key
  # Expected: "test_value"
  ```

- [ ] **AI Pipeline Test**

  ```bash
  # Upload test image
  cp backend/data/test_images/sample.jpg "$FOSCAM_BASE_PATH/test_camera/deployment_test_$(date +%s).jpg"

  # Wait 30 seconds
  sleep 30

  # Check detection was created
  curl http://localhost:8000/api/detections?limit=1 | jq '.[0]'
  # Should show recent detection
  ```

- [ ] **WebSocket Connectivity**

  ```bash
  # Test WebSocket connection
  curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Host: localhost:8000" http://localhost:8000/api/ws
  # Should return 101 Switching Protocols
  ```

- [ ] **Frontend Loads**

  ```bash
  # Open in browser
  xdg-open http://localhost:5173 || open http://localhost:5173

  # Manual checks:
  # - Dashboard loads without errors
  # - WebSocket status shows "Connected"
  # - Camera grid appears
  # - No console errors (F12)
  ```

### Performance Baseline

- [ ] **Response Times Acceptable**

  ```bash
  # Backend health check
  time curl http://localhost:8000/api/system/health/ready
  # Target: < 1 second

  # RT-DETRv2 health check
  time curl http://localhost:8090/health
  # Target: < 2 seconds

  # Nemotron health check
  time curl http://localhost:8091/health
  # Target: < 2 seconds
  ```

- [ ] **Resource Usage Reasonable**

  ```bash
  docker stats --no-stream
  # Check CPU % and memory usage are within limits
  ```

- [ ] **GPU Utilization**
  ```bash
  nvidia-smi
  # Check VRAM usage for AI services (should be loaded into memory)
  # Expected: 8-12 GB VRAM used
  ```

---

## Monitoring Setup

### Prometheus and Grafana (Optional)

If using the monitoring stack:

- [ ] **Start Monitoring Stack**

  ```bash
  docker compose --profile monitoring -f docker-compose.prod.yml up -d prometheus grafana jaeger redis-exporter json-exporter
  ```

- [ ] **Prometheus Reachable**

  ```bash
  curl http://localhost:9090/-/healthy
  # Expected: "Prometheus is Healthy"
  ```

- [ ] **Grafana Reachable**

  ```bash
  curl http://localhost:3002/api/health
  # Expected: {"database": "ok", ...}
  ```

- [ ] **Grafana Dashboard Configured**

  ```bash
  # Access Grafana
  xdg-open http://localhost:3002 || open http://localhost:3002

  # Login with admin credentials from .env
  # Check: Dashboards are provisioned and showing data
  ```

- [ ] **Metrics Endpoint Working**
  ```bash
  curl http://localhost:8000/api/metrics
  # Should return Prometheus-formatted metrics
  ```

### Jaeger Distributed Tracing (Optional)

- [ ] **Jaeger Reachable (if OTEL_ENABLED=true)**

  ```bash
  curl http://localhost:16686
  # Should return Jaeger UI HTML
  ```

- [ ] **Traces Being Collected**

  ```bash
  # Trigger a request
  curl http://localhost:8000/api/cameras

  # Check Jaeger UI
  xdg-open http://localhost:16686 || open http://localhost:16686
  # Search for "nemotron-backend" service, should see traces
  ```

---

## Security Validation

- [ ] **No Default/Weak Passwords**

  ```bash
  # Check for common weak passwords
  grep -iE "password|123456|admin|changeme|example" .env && echo "✗ Weak password detected" || echo "✓ No weak passwords"
  ```

- [ ] **Database Password Strong**

  ```bash
  # Verify password is at least 32 characters
  grep "POSTGRES_PASSWORD" .env | awk -F= '{print length($2)}'
  # Should be >= 32
  ```

- [ ] **API Keys Configured (if enabled)**

  ```bash
  grep "API_KEY_ENABLED=true" .env && {
    grep -q "API_KEYS=" .env && echo "✓ API keys configured" || echo "✗ API keys missing"
  }
  ```

- [ ] **File Permissions Correct**

  ```bash
  # .env should not be world-readable
  ls -l .env
  # Should be -rw------- or -rw-r-----

  # Camera directory should be readable by backend
  ls -ld "$FOSCAM_BASE_PATH"
  ```

- [ ] **HTTPS/TLS Configured (production only)**

  ```bash
  # If TLS_MODE=provided, check certificates exist
  [ -f "$TLS_CERT_PATH" ] && [ -f "$TLS_KEY_PATH" ] && echo "✓ TLS certs found" || echo "✗ TLS certs missing"

  # Verify certificates valid
  openssl x509 -in "$TLS_CERT_PATH" -noout -dates
  ```

- [ ] **CORS Properly Configured**
  ```bash
  # Check CORS origins are restricted
  grep "CORS_ORIGINS" .env
  # Should NOT be ["*"] in production
  ```

---

## Rollback Preparation

- [ ] **Previous Version Documented**

  ```bash
  git log --oneline -5
  # Note the current commit hash for rollback
  ```

- [ ] **Database Backup Created**

  ```bash
  docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U security -d security -F c > backup-pre-deploy-$(date +%Y%m%d-%H%M%S).dump
  [ -s backup-pre-deploy-*.dump ] && echo "✓ Backup created" || echo "✗ Backup failed"
  ```

- [ ] **Configuration Backup Created**

  ```bash
  cp .env .env.backup-$(date +%Y%m%d-%H%M%S)
  [ -f .env.backup-* ] && echo "✓ Config backed up" || echo "✗ Config backup failed"
  ```

- [ ] **Rollback Procedure Reviewed**
  ```bash
  # Ensure team knows rollback steps
  cat docs/DEPLOYMENT_RUNBOOK.md | grep -A 20 "## Rollback Procedures"
  ```

---

## Documentation and Communication

- [ ] **Release Notes Reviewed**

  ```bash
  # Check for breaking changes
  git log --oneline HEAD...$(git describe --tags --abbrev=0)
  ```

- [ ] **Deployment Window Scheduled**

  - Notify users of planned downtime (if applicable)
  - Schedule during low-usage period
  - Allow sufficient time for rollback if needed

- [ ] **Team Notified**

  - Share deployment plan
  - Ensure on-call coverage
  - Provide rollback contact information

- [ ] **Runbooks Accessible**
  ```bash
  ls -lh docs/DEPLOYMENT_RUNBOOK.md
  ls -lh docs/DEPLOYMENT_TROUBLESHOOTING.md
  ls -lh docs/DEPLOYMENT_SAFETY_CHECKLIST.md
  ```

---

## Sign-Off

Before proceeding with deployment, complete this final checklist:

| Category                 | Status | Notes |
| ------------------------ | ------ | ----- |
| Environment Validated    | [ ]    |       |
| Resources Available      | [ ]    |       |
| Services Dependencies OK | [ ]    |       |
| Smoke Tests Passed       | [ ]    |       |
| Monitoring Configured    | [ ]    |       |
| Security Validated       | [ ]    |       |
| Rollback Prepared        | [ ]    |       |
| Team Notified            | [ ]    |       |

**Deployment Approved By:** **\*\*\*\***\_\_\_**\*\*\*\***

**Date:** **\*\*\*\***\_\_\_**\*\*\*\***

**Notes:**

---

## Post-Deployment Monitoring

After deployment, monitor for:

**First 15 minutes:**

- [ ] Check logs for errors: `docker compose -f docker-compose.prod.yml logs -f`
- [ ] Monitor resource usage: `docker stats`
- [ ] Verify health endpoints remain healthy

**First hour:**

- [ ] Check AI pipeline processes images correctly
- [ ] Verify events are created with risk scores
- [ ] Monitor queue depths stay reasonable
- [ ] Check GPU temperature and utilization

**First 24 hours:**

- [ ] Review error logs in database
- [ ] Check disk space hasn't dropped significantly
- [ ] Verify no memory leaks (memory usage stable)
- [ ] Monitor user feedback (if applicable)

**Alerts to watch:**

- Database connection errors
- Redis connection failures
- AI service timeouts
- GPU out of memory errors
- Disk space warnings

---

## Checklist Summary

Use this command to generate a quick summary:

```bash
#!/bin/bash
echo "=== Deployment Readiness Summary ==="
echo ""
echo "Environment:"
[ -f .env ] && echo "✓ .env exists" || echo "✗ Missing .env"
grep -qE "DATABASE_URL|REDIS_URL|RTDETR_URL" .env && echo "✓ Core variables set" || echo "✗ Missing core variables"
echo ""
echo "Resources:"
nvidia-smi > /dev/null 2>&1 && echo "✓ GPU detected" || echo "✗ No GPU"
df -h / | awk 'NR==2 {if ($4 > 100) print "✓ Sufficient disk space ("$4" free)"; else print "✗ Low disk space ("$4" free)"}'
echo ""
echo "Services:"
docker compose -f docker-compose.prod.yml ps postgres 2>/dev/null | grep -q "Up" && echo "✓ PostgreSQL running" || echo "✗ PostgreSQL not running"
docker compose -f docker-compose.prod.yml ps redis 2>/dev/null | grep -q "Up" && echo "✓ Redis running" || echo "✗ Redis not running"
docker compose -f docker-compose.prod.yml ps backend 2>/dev/null | grep -q "Up" && echo "✓ Backend running" || echo "✗ Backend not running"
echo ""
echo "Health:"
curl -s http://localhost:8000/api/system/health/ready > /dev/null && echo "✓ Backend healthy" || echo "✗ Backend unhealthy"
curl -s http://localhost:8090/health > /dev/null && echo "✓ RT-DETRv2 healthy" || echo "✗ RT-DETRv2 unhealthy"
curl -s http://localhost:8091/health > /dev/null && echo "✓ Nemotron healthy" || echo "✗ Nemotron unhealthy"
echo ""
echo "==================================="
```

Save as `check-readiness.sh`, make executable with `chmod +x check-readiness.sh`, and run before deployment.
