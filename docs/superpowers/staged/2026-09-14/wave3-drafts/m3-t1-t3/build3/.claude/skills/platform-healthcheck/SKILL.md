---
name: platform-healthcheck
description: Comprehensive platform health verification for nemotron-v3 home security system. USE WHEN checking platform health, after infrastructure changes, debugging service issues, or verifying deployment state.
---

# Platform Health Check

**Use this skill to verify the complete health of the nemotron-v3 platform.** Don't mark health checks complete until ALL services are healthy.

## Quick Health Check

Run these commands in sequence. **ALL must pass** before declaring the platform healthy:

```bash
# 1. Docker Compose services - ALL should be "Up" and "healthy"
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

# 2. Prometheus targets - ALL should show health: "up"
curl -s localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets[] | "\(.labels.job): \(.health)"' | sort

# 3. API health endpoint
curl -s localhost:8000/api/health | jq

# 4. Redis connectivity
docker compose -f docker-compose.prod.yml exec -T redis redis-cli ping

# 5. PostgreSQL connectivity
docker compose -f docker-compose.prod.yml exec -T postgres pg_isready
```

## Healthy State Definition

The platform is **HEALTHY** when ALL of the following are true:

| Component      | Healthy State                                 |
| -------------- | --------------------------------------------- |
| Docker Compose | All services: `Up`, `healthy` or `running`    |
| Prometheus     | All targets: `health: "up"`                   |
| API            | `/api/health` returns `{"status": "healthy"}` |
| Redis          | `PONG` response                               |
| PostgreSQL     | `accepting connections`                       |
| GPU Services   | YOLO26, Nemotron responding (if deployed)     |

## Troubleshooting Workflow

If any check fails, follow this sequence:

### 1. Service Not Running

```bash
# Check logs for the failing service
docker compose -f docker-compose.prod.yml logs --tail=100 <service-name>

# Restart the specific service
docker compose -f docker-compose.prod.yml restart <service-name>

# Re-verify
docker compose -f docker-compose.prod.yml ps
```

### 2. Prometheus Target Down

```bash
# Check which targets are down
curl -s localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up") | {job: .labels.job, lastError: .lastError}'

# Common fixes:
# - Service not exposing metrics: check if /metrics endpoint exists
# - Wrong port in prometheus.yml: verify port matches service
# - Network issue: check if prometheus can reach the service
```

### 3. API Health Failing

```bash
# Check API logs
docker compose -f docker-compose.prod.yml logs --tail=100 backend

# Check if API container is running
docker compose -f docker-compose.prod.yml ps backend

# Check API dependencies (Redis, Postgres)
docker compose -f docker-compose.prod.yml exec backend python -c "from backend.core.database import engine; print('DB OK')"
```

### 4. Database Issues

```bash
# Check PostgreSQL logs
docker compose -f docker-compose.prod.yml logs --tail=50 postgres

# Check Redis logs
docker compose -f docker-compose.prod.yml logs --tail=50 redis

# Verify connections from backend
docker compose -f docker-compose.prod.yml exec backend python -c "
import redis
r = redis.Redis(host='redis', port=6379)
print('Redis:', r.ping())
"
```

## Post-Fix Verification

After ANY fix, **always re-run the full health check**:

```bash
# Full verification loop - run ALL checks again
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
curl -s localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets[] | "\(.labels.job): \(.health)"' | sort
curl -s localhost:8000/api/health | jq
```

## Completion Criteria

**DO NOT mark the health check complete until:**

- [ ] `docker compose ps` shows ALL services as `Up`/`healthy`
- [ ] ALL Prometheus targets show `health: "up"`
- [ ] API health endpoint returns success
- [ ] No ERROR level logs in recent output
- [ ] Any issues found have been FIXED and RE-VERIFIED

**If you cannot achieve healthy state**, document:

1. Which specific checks are failing
2. Error messages from logs
3. What you tried
4. Recommended next steps

Never leave the platform in a "confused" or partially-fixed state.

---

## Default Prompt Template

When starting any infrastructure task, use this prompt pattern to ensure complete verification:

```
Fix the issue, then verify the entire stack is healthy. Don't stop until
`docker compose ps` shows all services Up and healthy, and all Prometheus
targets are up. List any remaining issues.
```

This ensures:

- Fix is not considered "done" at application
- Full verification loop runs automatically
- Any cascading issues are caught
- Final state is documented
