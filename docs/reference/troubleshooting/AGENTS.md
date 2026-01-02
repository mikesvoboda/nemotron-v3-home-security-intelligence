# Troubleshooting Reference Directory - Agent Guide

## Purpose

This directory contains symptom-based troubleshooting guides for the Home Security Intelligence system. These guides help operators and users quickly diagnose and resolve common problems.

## Directory Contents

```
troubleshooting/
  AGENTS.md              # This file
  index.md               # Symptom quick reference table
  ai-issues.md           # AI service troubleshooting
  connection-issues.md   # Network and connectivity problems
  database-issues.md     # PostgreSQL problems
  gpu-issues.md          # GPU and CUDA issues
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

**Purpose:** Troubleshooting RT-DETRv2, Nemotron, and pipeline problems.

**Topics Covered:**

- Service not running
- Degraded mode (one service up, one down)
- Batch not processing
- Analysis failing (null risk scores)
- Detection quality issues (false positives/negatives)
- Slow inference
- Model loading issues
- Circuit breaker open

**Diagnostic Commands:**

```bash
# Check AI service status
./scripts/start-ai.sh status

# Check individual services
curl http://localhost:8090/health  # RT-DETRv2
curl http://localhost:8091/health  # Nemotron

# Check pipeline
curl http://localhost:8000/api/system/pipeline | jq
```

**When to use:** AI services failing, no detections, analysis problems.

### connection-issues.md

**Purpose:** Network, container, and connectivity troubleshooting.

**Topics Covered:**

- Backend connection refused
- Redis connection failed
- Database connection failed
- File watcher issues
- WebSocket connection problems
- CORS errors
- Container networking
- Port conflicts

**When to use:** Services can't connect to each other, network errors.

### database-issues.md

**Purpose:** PostgreSQL troubleshooting.

**Topics Covered:**

- Connection refused
- Authentication failed
- Migration failures
- Disk space issues
- Performance problems
- Backup and recovery
- Data corruption

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
# RT-DETRv2
curl http://localhost:8090/health

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

# Redis directly
redis-cli llen detection_queue
redis-cli llen analysis_queue
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
