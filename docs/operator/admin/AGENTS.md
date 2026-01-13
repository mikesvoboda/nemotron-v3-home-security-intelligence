# Administration Documentation - Agent Guide

## Purpose

This directory contains administration documentation for operators configuring, securing, and managing the Home Security Intelligence system. Topics include environment variables, secrets management, API key security, and security hardening.

## Directory Contents

```
admin/
  AGENTS.md        # This file
  api-keys.md      # API key security and query parameter risks
  README.md        # Configuration, secrets, and security overview
  security.md      # Metrics endpoint hardening guide
```

## Quick Navigation

| File          | Description                                    | When to Use                               |
| ------------- | ---------------------------------------------- | ----------------------------------------- |
| `README.md`   | Configuration overview, env vars, secrets, TLS | Initial setup, configuring the system     |
| `api-keys.md` | API key security risks with query parameters   | Implementing API authentication           |
| `security.md` | Metrics endpoint production hardening          | Securing Prometheus metrics in production |

## Key Files

### README.md

**Purpose:** Comprehensive administration guide covering all configuration aspects.

**Topics Covered:**

- Configuration loading order and key files
- Environment variables (essential, detection, batch, AI, GPU, camera)
- Docker secrets management and rotation
- Security configuration (API keys, CORS, firewall)
- Database and Redis configuration
- AI service URLs and feature toggles
- TLS/HTTPS configuration
- Rate limiting tiers
- Logging and data retention
- Development vs production example configurations

**When to use:** Setting up the system, configuring environment variables, managing secrets.

### api-keys.md

**Purpose:** Security documentation explaining risks of API keys in URL query parameters.

**Topics Covered:**

- Security risks (logs, browser history, referer headers, caching)
- Where query parameters are currently supported
- Recommended practices for HTTP and WebSocket authentication
- Mitigations implemented in the codebase
- Configuration recommendations for disabling query param auth

**When to use:** Implementing API authentication, understanding security implications.

### security.md

**Purpose:** Production hardening guide for the `/api/metrics` Prometheus endpoint.

**Topics Covered:**

- Current security state and why metrics is unauthenticated
- Information disclosure concerns and attack vectors
- Hardening recommendations (IP allowlisting, authentication, rate limiting)
- Nginx and Traefik configuration examples
- Prometheus scrape configuration
- Deployment scenarios (local, exposed, high-security)
- Audit checklist

**When to use:** Securing metrics endpoint, hardening production deployments.

## Target Audience

| Audience              | Needs                                  | Primary Documents        |
| --------------------- | -------------------------------------- | ------------------------ |
| **System Admins**     | Configuration, secrets, security       | README.md, security.md   |
| **DevOps Engineers**  | Deployment hardening, monitoring setup | security.md, README.md   |
| **Security Auditors** | Security posture review, hardening     | api-keys.md, security.md |

## Related Resources

- **[Operator Hub](../../operator-hub.md)** - Central operator documentation navigation
- **[Operator AGENTS.md](../AGENTS.md)** - Parent directory overview
- **[Deployment Guide](../deployment/)** - Service deployment procedures
- **[Monitoring Guide](../monitoring/)** - Health checks and metrics
- **[Backup and Recovery](../backup.md)** - Database backup procedures
- **[Redis Setup](../redis.md)** - Redis configuration and authentication

## Key Patterns

1. **Security-first** - Always document security implications
2. **Environment-specific** - Distinguish development vs production configurations
3. **Copy-paste ready** - Include working code examples
4. **Checklists** - Provide verification steps for security audits
