# Operator Documentation

> Spoke documents for the Operator Hub - deployment, configuration, and maintenance guides.

## Purpose

This directory contains focused documentation for operators (sysadmins, DevOps engineers, technically savvy users) who deploy and maintain the Home Security Intelligence system.

## Hub

- **[Operator Hub](./)** - Central navigation page linking to all operator documentation

## Available Spokes

| Document                | Description                                      |
| ----------------------- | ------------------------------------------------ |
| `ai-configuration.md`   | AI service environment variables                 |
| `ai-ghcr-deployment.md` | GHCR deployment for AI services                  |
| `ai-installation.md`    | AI prerequisites and model downloads             |
| `ai-overview.md`        | AI pipeline architecture                         |
| `ai-performance.md`     | AI performance tuning                            |
| `ai-services.md`        | AI service management                            |
| `ai-tls.md`             | AI service TLS configuration                     |
| `ai-troubleshooting.md` | AI troubleshooting guide                         |
| `backup.md`             | Backup and recovery procedures                   |
| `database.md`           | PostgreSQL configuration                         |
| `deployment-modes.md`   | Deployment mode decision table and AI networking |
| `gpu-setup.md`          | NVIDIA driver and container toolkit setup        |
| `redis.md`              | Redis configuration and authentication           |

## Directory Contents

```
operator/
  AGENTS.md               # This file
  README.md               # Operator documentation hub
  ai-configuration.md     # AI service environment variables
  ai-ghcr-deployment.md   # GHCR deployment for AI services
  ai-installation.md      # AI prerequisites and model downloads
  ai-overview.md          # AI pipeline architecture
  ai-performance.md       # AI performance tuning
  ai-services.md          # AI service management
  ai-tls.md               # AI service TLS configuration
  ai-troubleshooting.md   # AI troubleshooting guide
  backup.md               # Backup and recovery procedures
  database.md             # PostgreSQL configuration
  deployment-modes.md     # Deployment mode decision table
  dlq-management.md       # Dead letter queue management
  gpu-setup.md            # NVIDIA driver and container toolkit setup
  monitoring.md           # Comprehensive monitoring guide
  prometheus-alerting.md  # Prometheus alerting configuration
  redis.md                # Redis configuration and authentication
  scene-change-detection.md # Scene change detection configuration
  secrets-management.md   # Secrets management guide
  service-control.md      # Service control and lifecycle management
  admin/                  # Administration subdirectory
  deployment/             # Deployment guides subdirectory
  monitoring/             # Monitoring guides subdirectory
```

## Migration Status

The documentation is being restructured into a hub-and-spoke architecture. Some content currently resides in other locations and will be migrated or consolidated here:

| Topic           | Current Location                   | Status        |
| --------------- | ---------------------------------- | ------------- |
| Requirements    | `getting-started/prerequisites.md` | Link from hub |
| Container Setup | `deployment/`                      | Complete      |
| GPU Setup       | `gpu-setup.md`                     | Complete      |
| Installation    | `getting-started/installation.md`  | Link from hub |
| First Run       | `getting-started/first-run.md`     | Link from hub |
| Configuration   | `admin-guide/configuration.md`     | Link from hub |
| Monitoring      | `admin-guide/monitoring.md`        | Link from hub |
| Backup          | `backup.md`                        | Complete      |
| Retention       | `admin-guide/storage-retention.md` | Link from hub |
| Troubleshooting | `admin-guide/troubleshooting.md`   | Link from hub |
| Upgrading       | `getting-started/upgrading.md`     | Link from hub |

## Future Spokes

As the documentation matures, these focused spoke documents will be created:

- `requirements.md` - System requirements deep dive
- `container-setup.md` - Docker/Podman configuration
- `deployment-options.md` - Production vs development
- `installation.md` - Step-by-step installation
- `env-vars.md` - Environment variable reference
- `ai-config.md` - AI model configuration
- `cameras.md` - Camera FTP setup
- `database.md` - PostgreSQL configuration
- `monitoring.md` - Health checks and metrics
- ~~`backup.md` - Backup and recovery procedures~~ (Complete)
- `retention.md` - Data retention policies
- `performance.md` - Performance tuning
- `upgrading.md` - Version upgrades

## Key Patterns

1. **Practical focus** - "How to" rather than "how it works"
2. **Command examples** - Include expected output
3. **Quick reference** - Common tasks and commands
4. **Troubleshooting** - Symptom-based solutions
5. **Read time estimates** - Help operators plan their time
