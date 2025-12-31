# Admin Guide Directory - Agent Guide

## Purpose

This directory contains system administrator documentation for the Home Security Intelligence system. These guides are for operators and administrators who need to configure, monitor, and maintain the system.

## Directory Contents

```
admin-guide/
  AGENTS.md              # This file
  configuration.md       # System configuration guide
  monitoring.md          # Monitoring and observability
  security.md            # Security hardening guide
  storage-retention.md   # Data storage and retention policies
  troubleshooting.md     # Admin troubleshooting guide
```

## Key Files

### configuration.md

**Purpose:** Comprehensive guide to system configuration.

**Topics Covered:**

- Environment variables and .env file
- Service configuration (backend, frontend, AI services)
- Database configuration (PostgreSQL)
- Redis configuration
- Container orchestration settings

**When to use:** Initial setup, changing system configuration, debugging configuration issues.

### monitoring.md

**Purpose:** Guide to monitoring and observability.

**Topics Covered:**

- Health check endpoints
- Metrics collection
- Log aggregation
- Alert configuration
- Performance dashboards

**When to use:** Setting up monitoring, investigating system health issues.

### security.md

**Purpose:** Security hardening guide.

**Topics Covered:**

- Network security configuration
- Authentication and authorization
- Secrets management
- Container security
- Security best practices

**When to use:** Hardening the system, security audits, compliance.

### storage-retention.md

**Purpose:** Data storage and retention policies.

**Topics Covered:**

- Database storage management
- Media file storage (images, thumbnails)
- Log retention
- Cleanup service configuration
- Backup strategies

**When to use:** Managing disk space, configuring retention policies.

### troubleshooting.md

**Purpose:** Admin troubleshooting guide.

**Topics Covered:**

- Common issues and solutions
- Diagnostic commands
- Log analysis
- Service recovery procedures
- Performance troubleshooting

**When to use:** Diagnosing and resolving system issues.

## Target Audience

| Audience              | Needs                                  | Primary Documents  |
| --------------------- | -------------------------------------- | ------------------ |
| **System Admins**     | Configuration, monitoring, maintenance | All files          |
| **DevOps Engineers**  | Deployment, scaling, automation        | configuration.md   |
| **Security Officers** | Hardening, compliance, auditing        | security.md        |
| **Support Staff**     | Troubleshooting, issue resolution      | troubleshooting.md |

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/architecture/:** Technical architecture details
- **docs/getting-started/:** Installation and setup guides
- **RUNTIME_CONFIG.md:** Environment variable reference
