# Deployment Documentation - Agent Guide

## Purpose

This directory contains comprehensive deployment documentation for the Home Security Intelligence system. These guides cover container runtime setup, GPU passthrough configuration, AI service deployment, and self-hosted CI/CD runner setup.

## Directory Contents

```
deployment/
  AGENTS.md              # This file
  README.md              # Main deployment guide (Docker, GPU, AI setup)
  self-hosted-runner.md  # GitHub Actions self-hosted GPU runner setup
```

## Quick Navigation

| Document                | Description                                     | Audience      |
| ----------------------- | ----------------------------------------------- | ------------- |
| `README.md`             | Complete deployment guide with quick start      | Operators     |
| `self-hosted-runner.md` | Self-hosted GitHub Actions runner for GPU CI/CD | DevOps, Admin |

## Key Files

### README.md

**Purpose:** Comprehensive deployment guide for Docker/Podman with GPU-accelerated AI services.

**Topics Covered:**

- Quick start (5-step deployment)
- Prerequisites (hardware, software, network requirements)
- Container runtime setup (Docker Engine, Docker Desktop, Podman)
- GPU passthrough configuration (NVIDIA Container Toolkit)
- Compose files overview (development vs production)
- Deployment options (cross-platform host resolution)
- AI services setup (model downloads, health checks)
- Service dependencies and startup order
- Deployment checklist (pre/post deployment)
- Upgrade procedures
- Rollback procedures
- Troubleshooting common issues

**When to use:** Initial deployment, upgrading versions, troubleshooting deployment issues.

### self-hosted-runner.md

**Purpose:** Setup guide for GitHub Actions self-hosted GPU runner on RTX A5500 hardware.

**Topics Covered:**

- Prerequisites (hardware, software, GitHub requirements)
- Installation steps (GPU verification, NVIDIA toolkit, runner user)
- Configuration (registration token, labels, systemd service)
- Security considerations (fork protection, resource limits, secrets)
- Verification steps
- Troubleshooting (runner offline, GPU unavailable, permission errors)
- Maintenance (runner updates, GPU monitoring, cleanup)
- Quick reference commands

**When to use:** Setting up CI/CD GPU runner, troubleshooting GPU test failures.

## Common Tasks

### Deploy from Scratch

1. Read `README.md` - Prerequisites section
2. Run `./setup.sh` - Generate configuration
3. Run `./ai/download_models.sh` - Download AI models
4. Run `docker compose -f docker-compose.prod.yml up -d`
5. Verify with `curl http://localhost:8000/api/system/health/ready`

### Set Up GPU CI/CD

1. Read `self-hosted-runner.md` - Prerequisites
2. Follow installation steps for runner user and GitHub runner
3. Configure with correct labels: `self-hosted,linux,gpu,rtx-a5500`
4. Install as systemd service
5. Verify runner shows online in GitHub Settings

### Troubleshoot AI Services

1. Check `README.md` - Troubleshooting section
2. Verify GPU access: `nvidia-smi`
3. Test container GPU: `docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi`
4. Check AI health endpoints: `curl http://localhost:8095/health`

## Target Audience

| Audience      | Needs                           | Primary Documents     |
| ------------- | ------------------------------- | --------------------- |
| **Operators** | Deploy and maintain the system  | README.md             |
| **DevOps**    | CI/CD GPU runner setup          | self-hosted-runner.md |
| **Sysadmins** | GPU passthrough, containersetup | README.md             |

## Related Resources

| Resource             | Location                           | Description                     |
| -------------------- | ---------------------------------- | ------------------------------- |
| Operator Hub         | `../AGENTS.md`                     | Parent operator documentation   |
| GPU Setup Details    | `../gpu-setup.md`                  | Detailed GPU configuration      |
| AI Overview          | `../ai-overview.md`                | AI pipeline architecture        |
| Monitoring Guide     | `../monitoring/`                   | Health checks and metrics       |
| Administration Guide | `../admin/`                        | Configuration and secrets       |
| Docker Compose Files | `/docker-compose.*.yml`            | Container orchestration files   |
| AI Model Scripts     | `/ai/download_models.sh`           | Model download automation       |
| GitHub GPU Workflow  | `/.github/workflows/gpu-tests.yml` | CI/CD workflow using GPU runner |

## Key Patterns

1. **Production-first** - Guides focus on production deployment with GPU
2. **Container agnostic** - Instructions for both Docker and Podman
3. **Security emphasis** - Fork protection, resource limits, secrets management
4. **Troubleshooting driven** - Symptom-based solutions for common issues
5. **Checklist format** - Pre/post deployment verification steps
