# Deployment Documentation Hub

> A consolidated navigation portal for all deployment-related documentation (17 documents, ~6,600 lines total).

**Last updated:** 2026-01-09

---

## Quick Start

**Fastest path to a running system:**

```bash
./setup.sh && docker compose -f docker-compose.prod.yml up -d
```

For the complete step-by-step guide, see [Installation Guide](getting-started/installation.md).

---

## Which Document Do I Need?

```
                    START
                      |
        +-------------+-------------+
        |                           |
  First time deploying?       Existing deployment?
        |                           |
        v                           v
  Pre-Deployment              What's the issue?
  (Safety Checklist)                |
        |                     +-----+-----+
        v                     |           |
  DOCKER_DEPLOYMENT.md    Not working?  Performance?
        |                     |           |
        v                     v           v
  Post-Deployment        Troubleshooting  HEALTH_CHECK_STRATEGY.md
  (Verification)              Guides
```

### Quick Decision Matrix

| I want to...                     | Start here                                                     |
| -------------------------------- | -------------------------------------------------------------- |
| Deploy for the first time        | [Installation Guide](getting-started/installation.md)          |
| Understand deployment options    | [Deployment Modes](operator/deployment-modes.md)               |
| Configure AI services            | [AI Setup Guide](AI_SETUP.md)                                  |
| Fix a deployment issue           | [Deployment Troubleshooting](DEPLOYMENT_TROUBLESHOOTING.md)    |
| Verify deployment is healthy     | [Verification Checklist](DEPLOYMENT_VERIFICATION_CHECKLIST.md) |
| Understand service startup order | [Service Dependencies](SERVICE_DEPENDENCIES.md)                |
| Set up GPU passthrough           | [GPU Setup Guide](operator/gpu-setup.md)                       |
| Manage secrets securely          | [Docker Secrets Guide](DOCKER_SECRETS.md)                      |

---

## Deployment Phases

### Pre-Deployment

Prepare your environment before starting any deployment.

| Document                                                      | Time    | Description                                                           | Audience               |
| ------------------------------------------------------------- | ------- | --------------------------------------------------------------------- | ---------------------- |
| [Deployment Safety Checklist](DEPLOYMENT_SAFETY_CHECKLIST.md) | ~10 min | Pre-flight validation checklist for secrets, environment, and AI URLs | `Operator` `DevOps`    |
| [Prerequisites](getting-started/prerequisites.md)             | ~8 min  | Hardware (GPU, RAM, storage) and software requirements                | `Operator` `Developer` |

### During Deployment

Core deployment procedures and container setup.

| Document                                    | Time    | Description                                                            | Audience            |
| ------------------------------------------- | ------- | ---------------------------------------------------------------------- | ------------------- |
| [Deployment Strategy](DEPLOYMENT.md)        | ~25 min | Progressive delivery, health checks, and automated rollback mechanisms | `DevOps`            |
| [Docker Deployment](DOCKER_DEPLOYMENT.md)   | ~20 min | Container runtime setup with Docker or Podman, service configuration   | `Operator` `DevOps` |
| [Deployment Runbook](DEPLOYMENT_RUNBOOK.md) | ~20 min | Step-by-step procedures for fresh deployments, upgrades, and rollbacks | `Operator`          |

### AI Services Deployment

Configure and deploy the GPU-accelerated AI inference stack.

| Document                                             | Time    | Description                                                                     | Audience               |
| ---------------------------------------------------- | ------- | ------------------------------------------------------------------------------- | ---------------------- |
| [AI Setup Guide](AI_SETUP.md)                        | ~30 min | Comprehensive guide for the full AI stack (RT-DETRv2, Nemotron, Florence, CLIP) | `Operator` `DevOps`    |
| [AI Overview](operator/ai-overview.md)               | ~5 min  | High-level introduction to what the AI services do                              | `Operator` `Developer` |
| [AI Installation](operator/ai-installation.md)       | ~10 min | Install prerequisites and dependencies for AI inference                         | `Operator`             |
| [AI Configuration](operator/ai-configuration.md)     | ~8 min  | Environment variables and startup configuration for AI services                 | `Operator` `DevOps`    |
| [AI GHCR Deployment](operator/ai-ghcr-deployment.md) | ~12 min | Deploy AI services using containers (local builds with GHCR backend/frontend)   | `DevOps`               |
| [GPU Setup Guide](operator/gpu-setup.md)             | ~15 min | NVIDIA driver installation and container GPU passthrough configuration          | `Operator` `DevOps`    |

### Post-Deployment

Validate and verify your deployment is working correctly.

| Document                                                       | Time    | Description                                                             | Audience             |
| -------------------------------------------------------------- | ------- | ----------------------------------------------------------------------- | -------------------- |
| [Verification Checklist](DEPLOYMENT_VERIFICATION_CHECKLIST.md) | ~12 min | Comprehensive checklist to validate deployment health and functionality | `Operator` `DevOps`  |
| [Health Check Strategy](HEALTH_CHECK_STRATEGY.md)              | ~12 min | SLOs, health endpoints, circuit breakers, and recovery procedures       | `DevOps` `Developer` |

### Troubleshooting

Diagnose and fix common deployment issues.

| Document                                                    | Time    | Description                                                         | Audience            |
| ----------------------------------------------------------- | ------- | ------------------------------------------------------------------- | ------------------- |
| [Deployment Troubleshooting](DEPLOYMENT_TROUBLESHOOTING.md) | ~15 min | Solutions for database, Redis, AI, network, GPU, and storage issues | `Operator` `DevOps` |
| [AI Troubleshooting](operator/ai-troubleshooting.md)        | ~10 min | Diagnose and fix common AI service issues (GPU, VRAM, connectivity) | `Operator`          |

---

## Reference

Technical reference documentation for configuration and architecture.

| Document                                        | Time    | Description                                                              | Audience             |
| ----------------------------------------------- | ------- | ------------------------------------------------------------------------ | -------------------- |
| [Docker Secrets](DOCKER_SECRETS.md)             | ~10 min | Secure credential management with Docker secrets                         | `DevOps` `Operator`  |
| [Runtime Configuration](RUNTIME_CONFIG.md)      | ~20 min | Authoritative reference for all environment variables and ports          | `Developer` `DevOps` |
| [Service Dependencies](SERVICE_DEPENDENCIES.md) | ~15 min | Service dependency hierarchy, startup order, and failure impact analysis | `DevOps` `Developer` |

---

## Deployment Modes

The system supports multiple deployment configurations based on your environment and requirements.

| Mode                            | Backend           | AI Services | Best For                                       |
| ------------------------------- | ----------------- | ----------- | ---------------------------------------------- |
| **Production**                  | Container         | Container   | Simplest "it just works" setup                 |
| **All-Host Development**        | Host (uvicorn)    | Host        | Local development without container networking |
| **Backend Container + Host AI** | Container         | Host        | Hot-reload containers with host GPU access     |
| **Remote AI Host**              | Host or Container | Remote      | Dedicated GPU server for AI inference          |

For detailed configuration of each mode, including environment variables and networking setup, see [Deployment Modes](operator/deployment-modes.md).

---

## Document Index by Audience

### For Operators

Primary focus: Running and maintaining the system.

1. [Prerequisites](getting-started/prerequisites.md) - Check system requirements
2. [Installation Guide](getting-started/installation.md) - First-time setup
3. [Deployment Runbook](DEPLOYMENT_RUNBOOK.md) - Standard procedures
4. [Verification Checklist](DEPLOYMENT_VERIFICATION_CHECKLIST.md) - Confirm deployment health
5. [Deployment Troubleshooting](DEPLOYMENT_TROUBLESHOOTING.md) - Fix common issues

### For DevOps Engineers

Primary focus: CI/CD, infrastructure, and automation.

1. [Deployment Strategy](DEPLOYMENT.md) - Progressive delivery and rollback
2. [Docker Deployment](DOCKER_DEPLOYMENT.md) - Container orchestration
3. [GPU Setup Guide](operator/gpu-setup.md) - GPU passthrough configuration
4. [Health Check Strategy](HEALTH_CHECK_STRATEGY.md) - SLOs and circuit breakers
5. [Service Dependencies](SERVICE_DEPENDENCIES.md) - Architecture and startup order

### For Developers

Primary focus: Local development and debugging.

1. [Deployment Modes](operator/deployment-modes.md) - Choose your dev setup
2. [Runtime Configuration](RUNTIME_CONFIG.md) - Environment variables
3. [AI Overview](operator/ai-overview.md) - Understand the AI pipeline
4. [AI Troubleshooting](operator/ai-troubleshooting.md) - Debug AI issues

---

## Reading Time Summary

| Category          | Documents | Total Lines | Est. Reading Time |
| ----------------- | --------- | ----------- | ----------------- |
| Pre-Deployment    | 2         | ~650        | ~18 min           |
| During Deployment | 3         | ~1,900      | ~65 min           |
| AI Services       | 6         | ~2,600      | ~80 min           |
| Post-Deployment   | 2         | ~900        | ~24 min           |
| Troubleshooting   | 2         | ~700        | ~25 min           |
| Reference         | 3         | ~1,900      | ~45 min           |
| **Total**         | **17**    | **~6,600**  | **~4.5 hours**    |

> **Tip:** You do not need to read all documents. Use the decision matrix above to find exactly what you need.

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project overview and development instructions
- [ROADMAP.md](ROADMAP.md) - Post-MVP enhancement plans
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing patterns and requirements
- [docs/operator/](operator/) - Additional operator guides (monitoring, backup, database)
