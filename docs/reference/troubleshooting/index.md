# Troubleshooting Index

> Symptom-based troubleshooting guide for common issues.

**Time to read:** ~3 min
**Prerequisites:** None

---

## Quick Links by Symptom

### System Won't Start

| Symptom                                         | Likely Cause                       | See                                                           |
| ----------------------------------------------- | ---------------------------------- | ------------------------------------------------------------- |
| "DATABASE_URL environment variable is required" | Missing database configuration     | [Database Issues](database-issues.md#missing-database-url)    |
| "Connection refused" to PostgreSQL              | Database not running or wrong host | [Database Issues](database-issues.md#connection-refused)      |
| "Connection refused" to Redis                   | Redis not running                  | [Connection Issues](connection-issues.md#redis-not-available) |
| Container exits immediately                     | Environment misconfiguration       | [Connection Issues](connection-issues.md#container-crashes)   |

### AI Not Working

| Symptom                               | Likely Cause                  | See                                           |
| ------------------------------------- | ----------------------------- | --------------------------------------------- |
| "RT-DETR service connection refused"  | AI container not running      | [AI Issues](ai-issues.md#service-not-running) |
| "Nemotron service connection refused" | LLM container not running     | [AI Issues](ai-issues.md#service-not-running) |
| CUDA out of memory                    | Insufficient VRAM             | [GPU Issues](gpu-issues.md#out-of-memory)     |
| Slow inference (>1s for detection)    | Running on CPU instead of GPU | [GPU Issues](gpu-issues.md#cpu-fallback)      |
| Health check shows "degraded"         | One AI service down           | [AI Issues](ai-issues.md#degraded-mode)       |

### Events Not Appearing

| Symptom                               | Likely Cause             | See                                                           |
| ------------------------------------- | ------------------------ | ------------------------------------------------------------- |
| Images uploaded but no detections     | File watcher not running | [Connection Issues](connection-issues.md#file-watcher-issues) |
| Detections exist but no events        | Batch aggregator issue   | [AI Issues](ai-issues.md#batch-not-processing)                |
| Events created but risk_score is null | Nemotron service issue   | [AI Issues](ai-issues.md#analysis-failing)                    |
| Dashboard shows stale data            | WebSocket disconnected   | [Connection Issues](connection-issues.md#websocket-issues)    |

### GPU Problems

| Symptom                       | Likely Cause                      | See                                              |
| ----------------------------- | --------------------------------- | ------------------------------------------------ |
| "CUDA not available"          | Driver or container configuration | [GPU Issues](gpu-issues.md#cuda-not-available)   |
| GPU utilization at 0%         | AI services using CPU             | [GPU Issues](gpu-issues.md#cpu-fallback)         |
| "CUDA out of memory"          | Too many models loaded            | [GPU Issues](gpu-issues.md#out-of-memory)        |
| High GPU temperature (>85C)   | Cooling or throttling             | [GPU Issues](gpu-issues.md#thermal-throttling)   |
| nvidia-smi shows no processes | Container GPU access failed       | [GPU Issues](gpu-issues.md#container-gpu-access) |

### Database Problems

| Symptom                   | Likely Cause                     | See                                                      |
| ------------------------- | -------------------------------- | -------------------------------------------------------- |
| "relation does not exist" | Missing migrations               | [Database Issues](database-issues.md#missing-migrations) |
| "too many connections"    | Connection pool exhausted        | [Database Issues](database-issues.md#connection-pool)    |
| Slow queries              | Missing indexes or large dataset | [Database Issues](database-issues.md#slow-queries)       |
| Disk space issues         | Old data not cleaned up          | [Database Issues](database-issues.md#disk-space)         |

### Network/Connection Problems

| Symptom                          | Likely Cause                      | See                                                             |
| -------------------------------- | --------------------------------- | --------------------------------------------------------------- |
| "Connection refused" errors      | Service not running or wrong port | [Connection Issues](connection-issues.md#service-not-reachable) |
| Timeouts during health check     | Network latency or overload       | [Connection Issues](connection-issues.md#timeouts)              |
| WebSocket disconnects frequently | Idle timeout or proxy issues      | [Connection Issues](connection-issues.md#websocket-issues)      |
| CORS errors in browser           | Frontend/backend URL mismatch     | [Connection Issues](connection-issues.md#cors-errors)           |

---

## Diagnostic Commands

### Check Service Health

```bash
# API health check
curl http://localhost:8000/health

# Detailed health with services
curl http://localhost:8000/api/system/health

# Readiness with workers
curl http://localhost:8000/api/system/health/ready
```

### Check AI Services

```bash
# RT-DETRv2
curl http://localhost:8090/health

# Nemotron
curl http://localhost:8091/health
```

### Check Container Status

```bash
# Docker
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend

# Podman
podman-compose -f docker-compose.prod.yml ps
podman-compose -f docker-compose.prod.yml logs backend
```

### Check GPU

```bash
# GPU status
nvidia-smi

# GPU processes
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

### Check Logs

```bash
# Backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# AI service logs
tail -f /tmp/rtdetr-detector.log
tail -f /tmp/nemotron-llm.log
```

---

## Getting Help

If you can't resolve an issue:

1. Check the specific troubleshooting page for your symptom
2. Gather diagnostic information (logs, error messages, `nvidia-smi` output)
3. Search existing [GitHub Issues](https://github.com/yourusername/home-security-intelligence/issues)
4. Open a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Relevant logs and error messages
   - System information (OS, GPU, Docker/Podman version)

---

## Troubleshooting Pages

- [GPU Issues](gpu-issues.md) - CUDA, VRAM, temperature problems
- [Connection Issues](connection-issues.md) - Network, containers, WebSocket
- [AI Issues](ai-issues.md) - RT-DETRv2, Nemotron, pipeline
- [Database Issues](database-issues.md) - PostgreSQL problems
