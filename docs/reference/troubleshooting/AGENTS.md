# Troubleshooting Reference Directory - Agent Guide

## Purpose

This directory contains symptom-based troubleshooting guides for the Home Security Intelligence system. These guides help operators and users quickly diagnose and resolve common problems.

## Directory Contents

```
troubleshooting/
  AGENTS.md                # This file
  README.md                # Troubleshooting hub (condensed symptom guide)
  index.md                 # Symptom quick reference table
  ai-issues.md             # AI service troubleshooting
  connection-issues.md     # Network and connectivity problems
  database-issues.md       # PostgreSQL problems
  gpu-issues.md            # GPU and CUDA issues
  triton-rootless-cuda.md  # Triton CUDA init failure in rootless Podman
```

## Key Files

### index.md

**Purpose:** First stop when something goes wrong. Symptom-based quick reference.

**Content:**

- Quick self-check commands before troubleshooting
- Symptom quick reference table with likely causes and quick fixes
- Common problems with detailed diagnosis and solutions:
  - Dashboard shows no events
  - Risk gauge stuck at 0
  - Camera shows offline
  - AI not working
  - WebSocket disconnected
  - High CPU/memory usage
  - Disk space running out
  - Slow AI inference
  - CORS errors in browser
- Emergency procedures (system won't start, database corruption, security breach)
- Information to gather for bug reports

**When to use:** First stop for any problem, symptom lookup, emergency situations.

### ai-issues.md

**Purpose:** Troubleshooting YOLO26, Nemotron, and pipeline problems.

**Topics Covered:**

- Service not running
- Degraded mode (one service up, one down)
- Enrichment issues (Florence-2, CLIP, heavy/light enrichment routers)
- Batch not processing
- Analysis failing (null risk scores)
- Detection quality issues (false positives/negatives)
- Slow inference
- Model loading issues
- Circuit breaker open

**Diagnostic Commands:**

```bash
# Check AI container status
docker compose -f docker-compose.prod.yml ps ai-gateway ai-llm

# Check individual services
curl http://localhost:8090/yolo26/health  # YOLO26 (AI gateway router)
curl http://localhost:8091/health         # Nemotron

# Check pipeline
curl http://localhost:8000/api/system/pipeline | jq
```

**When to use:** AI services failing, no detections, analysis problems.

### connection-issues.md

**Purpose:** Network, container, and connectivity troubleshooting.

**Topics Covered:**

- Service not reachable (ports, container networking)
- Redis not available
- Container crashes
- File watcher issues
- WebSocket connection problems
- CORS errors
- Timeouts

**When to use:** Services can't connect to each other, network errors.

### database-issues.md

**Purpose:** PostgreSQL troubleshooting.

**Topics Covered:**

- Missing DATABASE_URL
- Connection refused
- Authentication failed
- Missing tables (schema comes from the SQLAlchemy models — this project has no Alembic)
- Connection pool exhaustion, slow queries
- Disk space issues
- Backup and recovery

**When to use:** Database errors, migration problems, storage issues.

### gpu-issues.md

**Purpose:** NVIDIA GPU and CUDA troubleshooting.

**Topics Covered:**

- CUDA not available
- GPU not detected
- Running on CPU instead of GPU
- VRAM exhaustion
- Thermal throttling
- Container GPU access (NVIDIA Container Toolkit)
- Driver issues
- Multi-GPU configuration

**When to use:** AI running slow, GPU not being used, CUDA errors.

### README.md

**Purpose:** Troubleshooting hub — condensed per-symptom solutions, log locations, database/Redis/GPU quick fixes, emergency procedures, and a one-shot diagnostics collection script.

**When to use:** When index.md's quick table isn't enough but you don't need a full per-domain guide.

### triton-rootless-cuda.md

**Purpose:** Triton CUDA init failure in rootless Podman (cudaGetDeviceCount err=3).

**Topics Covered:**

- Root cause: CUDA Runtime API vs Driver API
- Rootful Podman workaround
- Rootless CDI spec in user directory
- nvidia-cap device permissions
- Explicit nvidia-cap bind mounts

**When to use:** ai-gateway models UNAVAILABLE while ai-llm works; Triton cudaErrorInitializationError.

## Troubleshooting Approach

All troubleshooting guides follow this pattern:

### Structure

1. **Symptoms** - What you observe
2. **Quick Diagnosis** - Commands to identify the problem
3. **Possible Causes** - Ordered by likelihood
4. **Solutions** - Step-by-step fixes

### Solution Order

Solutions are presented most-likely-first:

1. Quick fixes that resolve most cases
2. Configuration changes
3. Service restarts
4. More complex debugging
5. Last resort options

### Example Pattern

````markdown
## Problem Title

### Symptoms

- What the user observes

### Quick Diagnosis

```bash
# Commands to identify the problem
```
````

### Possible Causes

1. Most common cause
2. Second most common
3. Less common cause

### Solutions

**1. Try this first:**

```bash
# Command
```

**2. If that doesn't work:**

```bash
# Alternative command
```

````

## Diagnostic Command Reference

### System Health

```bash
# Overall health
curl http://localhost:8000/api/system/health | jq

# Detailed readiness
curl http://localhost:8000/api/system/health/ready | jq

# Container status
docker compose -f docker-compose.prod.yml ps
````

### AI Services

```bash
# AI gateway aggregate + per-router health (production topology)
curl http://localhost:8090/health
curl http://localhost:8090/yolo26/health

# Host-run standalone detector (only when running ai/start_detector.sh directly)
curl http://localhost:8095/health

# Nemotron
curl http://localhost:8091/health

# Pipeline status
curl http://localhost:8000/api/system/pipeline | jq
```

### GPU

```bash
# GPU status
nvidia-smi

# GPU processes
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

### Queues

```bash
# Queue depths
curl http://localhost:8000/api/system/telemetry | jq .queues

# Redis directly (queues are Redis Streams by default — USE_REDIS_STREAMS)
redis-cli xlen detections:stream
redis-cli xlen analysis:stream
```

## Target Audiences

| Audience       | Needs                    | Primary Documents          |
| -------------- | ------------------------ | -------------------------- |
| **Operators**  | Quick problem resolution | index.md, all issue guides |
| **Support**    | Systematic diagnosis     | All files                  |
| **Users**      | Basic troubleshooting    | index.md (quick reference) |
| **Developers** | Deep debugging           | Specific issue guides      |

## Related Documentation

- **docs/reference/AGENTS.md:** Reference directory overview
- **docs/operator/ai-troubleshooting.md:** Quick AI fixes
- **docs/operator/gpu-setup.md:** GPU configuration
- **docs/reference/config/env-reference.md:** Configuration options
- **docs/reference/glossary.md:** Terms and definitions
