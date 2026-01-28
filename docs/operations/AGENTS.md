# Operations Directory - Agent Guide

## Purpose

This directory contains operational runbooks for managing the Home Security Intelligence system in production environments. Runbooks provide step-by-step procedures for incident response, maintenance tasks, and operational health monitoring.

## Directory Contents

```
docs/operations/
  AGENTS.md              # This file - directory guide
  profiling-runbook.md   # Pyroscope profiling operations procedures
```

## Runbook Overview

| Runbook                                   | Purpose                                     | Audience        |
| ----------------------------------------- | ------------------------------------------- | --------------- |
| [Profiling Runbook](profiling-runbook.md) | Pyroscope incident response and maintenance | Operators, SREs |

## Runbook Structure

Each runbook follows a consistent structure:

1. **Quick Reference** - Common commands and access URLs
2. **Incident Response Procedures** - Step-by-step resolution guides
3. **Maintenance Procedures** - Routine operational tasks
4. **Health Monitoring** - Scripts and checks for proactive monitoring
5. **Performance Baselines** - Expected metrics and alert thresholds
6. **Related Documentation** - Links to guides and reference materials

## Key Patterns

1. **Incident IDs** - Each incident procedure has a unique ID (e.g., `INC-PROF-001`)
2. **Maintenance IDs** - Each maintenance procedure has a unique ID (e.g., `MAINT-PROF-001`)
3. **Copy-paste commands** - All commands are ready to execute
4. **Rollback procedures** - Each change includes rollback steps
5. **Impact statements** - Each procedure documents the impact

## Related Documentation

| Resource                   | Location                                                       |
| -------------------------- | -------------------------------------------------------------- |
| Operator documentation hub | [../operator/README.md](../operator/README.md)                 |
| Monitoring guide           | [../operator/monitoring.md](../operator/monitoring.md)         |
| Troubleshooting guides     | [../reference/troubleshooting/](../reference/troubleshooting/) |
| User guides                | [../guides/](../guides/)                                       |

## Future Runbooks

As the system matures, additional runbooks will be added:

- `database-runbook.md` - PostgreSQL operations
- `redis-runbook.md` - Redis operations
- `ai-services-runbook.md` - AI service management
- `monitoring-runbook.md` - Prometheus/Grafana operations
- `backup-runbook.md` - Backup and recovery procedures
