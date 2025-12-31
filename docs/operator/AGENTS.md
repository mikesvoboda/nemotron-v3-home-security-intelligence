# Operator Documentation

> Spoke documents for the Operator Hub - deployment, configuration, and maintenance guides.

## Purpose

This directory contains focused documentation for operators (sysadmins, DevOps engineers, technically savvy users) who deploy and maintain the Home Security Intelligence system.

## Hub

- **[Operator Hub](../operator-hub.md)** - Central navigation page linking to all operator documentation

## Migration Status

The documentation is being restructured into a hub-and-spoke architecture. Some content currently resides in other locations and will be migrated or consolidated here:

| Topic           | Current Location                   | Status        |
| --------------- | ---------------------------------- | ------------- |
| Requirements    | `getting-started/prerequisites.md` | Link from hub |
| Container Setup | `DOCKER_DEPLOYMENT.md`             | Link from hub |
| GPU Setup       | `AI_SETUP.md`                      | Link from hub |
| Installation    | `getting-started/installation.md`  | Link from hub |
| First Run       | `getting-started/first-run.md`     | Link from hub |
| Configuration   | `admin-guide/configuration.md`     | Link from hub |
| Monitoring      | `admin-guide/monitoring.md`        | Link from hub |
| Retention       | `admin-guide/storage-retention.md` | Link from hub |
| Troubleshooting | `admin-guide/troubleshooting.md`   | Link from hub |
| Upgrading       | `getting-started/upgrading.md`     | Link from hub |

## Future Spokes

As the documentation matures, these focused spoke documents will be created:

- `requirements.md` - System requirements deep dive
- `container-setup.md` - Docker/Podman configuration
- `gpu-setup.md` - NVIDIA Container Toolkit setup
- `deployment-options.md` - Production vs development
- `installation.md` - Step-by-step installation
- `env-vars.md` - Environment variable reference
- `ai-config.md` - AI model configuration
- `cameras.md` - Camera FTP setup
- `database.md` - PostgreSQL configuration
- `monitoring.md` - Health checks and metrics
- `backup.md` - Backup and recovery procedures
- `retention.md` - Data retention policies
- `performance.md` - Performance tuning
- `upgrading.md` - Version upgrades

## Key Patterns

1. **Practical focus** - "How to" rather than "how it works"
2. **Command examples** - Include expected output
3. **Quick reference** - Common tasks and commands
4. **Troubleshooting** - Symptom-based solutions
5. **Read time estimates** - Help operators plan their time
