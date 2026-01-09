# Documentation

> Central navigation hub for Home Security Intelligence documentation.

For a quick overview of the project and getting started instructions, see the [main README](../README.md).

---

## Quick Start by Role

| Role       | Hub                               | Description                         |
| ---------- | --------------------------------- | ----------------------------------- |
| End Users  | [User Hub](user-hub.md)           | Dashboard usage, alerts, settings   |
| Operators  | [Operator Hub](operator-hub.md)   | Deployment, monitoring, maintenance |
| Developers | [Developer Hub](developer-hub.md) | Contributing, architecture, testing |

---

## Documentation Map

### Getting Started

| Document                                          | Description                            |
| ------------------------------------------------- | -------------------------------------- |
| [Prerequisites](getting-started/prerequisites.md) | System requirements and dependencies   |
| [Installation](getting-started/installation.md)   | Step-by-step installation guide        |
| [First Run](getting-started/first-run.md)         | Initial configuration and verification |
| [Upgrading](getting-started/upgrading.md)         | Version upgrade procedures             |

### Deployment and Operations

| Document                                                    | Description                             |
| ----------------------------------------------------------- | --------------------------------------- |
| [Deployment Overview](DEPLOYMENT.md)                        | Deployment strategies and options       |
| [Docker Deployment](DOCKER_DEPLOYMENT.md)                   | Docker/Podman compose setup             |
| [Deployment Runbook](DEPLOYMENT_RUNBOOK.md)                 | Step-by-step deployment procedures      |
| [Deployment Troubleshooting](DEPLOYMENT_TROUBLESHOOTING.md) | Common deployment issues and fixes      |
| [Runtime Configuration](RUNTIME_CONFIG.md)                  | Environment variables and settings      |
| [Docker Secrets](DOCKER_SECRETS.md)                         | Secure credential management            |
| [Service Dependencies](SERVICE_DEPENDENCIES.md)             | Service startup order and health checks |

### AI Services

| Document                                             | Description                       |
| ---------------------------------------------------- | --------------------------------- |
| [AI Setup Guide](AI_SETUP.md)                        | Configure RT-DETRv2 and Nemotron  |
| [AI Overview](operator/ai-overview.md)               | AI architecture and capabilities  |
| [AI Installation](operator/ai-installation.md)       | AI service prerequisites          |
| [AI Configuration](operator/ai-configuration.md)     | AI environment variables          |
| [AI Services](operator/ai-services.md)               | Starting and stopping AI services |
| [AI GHCR Deployment](operator/ai-ghcr-deployment.md) | Deploy AI from container registry |
| [AI Performance](operator/ai-performance.md)         | Performance tuning                |
| [AI Troubleshooting](operator/ai-troubleshooting.md) | Common AI issues and solutions    |
| [AI TLS](operator/ai-tls.md)                         | Secure AI communications          |
| [Health Check Strategy](HEALTH_CHECK_STRATEGY.md)    | Service health monitoring design  |

### Security

| Document                                                    | Description                            |
| ----------------------------------------------------------- | -------------------------------------- |
| [Security Overview](SECURITY.md)                            | Security architecture and practices    |
| [API Key Security](SECURITY_API_KEYS.md)                    | API key management and best practices  |
| [Secrets Management](operator/secrets-management.md)        | Docker secrets and credential rotation |
| [Admin Security Guide](admin-guide/security.md)             | Administrator security configuration   |
| [Metrics Endpoint Hardening](METRICS_ENDPOINT_HARDENING.md) | Protecting Prometheus endpoints        |

### Architecture

| Document                                          | Description                           |
| ------------------------------------------------- | ------------------------------------- |
| [System Overview](architecture/overview.md)       | High-level architecture and data flow |
| [AI Pipeline](architecture/ai-pipeline.md)        | RT-DETRv2 and Nemotron integration    |
| [Data Model](architecture/data-model.md)          | PostgreSQL schema and relationships   |
| [Real-time Events](architecture/real-time.md)     | WebSocket and Redis pub/sub           |
| [Resilience Patterns](architecture/resilience.md) | Circuit breakers, DLQ, retry logic    |
| [Frontend Hooks](architecture/frontend-hooks.md)  | React hooks architecture              |
| [Decisions](architecture/decisions.md)            | Architectural Decision Records (ADRs) |

### API Reference

| Document                                      | Description                        |
| --------------------------------------------- | ---------------------------------- |
| [API Overview](api-reference/overview.md)     | REST endpoints and conventions     |
| [Cameras API](api-reference/cameras.md)       | Camera management endpoints        |
| [Events API](api-reference/events.md)         | Security event endpoints           |
| [Detections API](api-reference/detections.md) | Object detection endpoints         |
| [System API](api-reference/system.md)         | Health and system endpoints        |
| [WebSocket API](api-reference/websocket.md)   | Real-time event streams            |
| [Analytics API](api-reference/analytics.md)   | Detection trends and statistics    |
| [Alerts API](api-reference/alerts.md)         | Alert configuration and management |
| [DLQ API](api-reference/dlq.md)               | Dead letter queue management       |
| [AI Audit API](api-reference/ai-audit.md)     | AI quality metrics                 |
| [Prompts API](api-reference/prompts.md)       | Prompt management and A/B testing  |
| [Entities API](api-reference/entities.md)     | Entity tracking endpoints          |
| [Zones API](api-reference/zones.md)           | Detection zone configuration       |
| [Logs API](api-reference/logs.md)             | Application log access             |
| [Media API](api-reference/media.md)           | Image and video serving            |
| [WebSocket Contracts](WEBSOCKET_CONTRACTS.md) | WebSocket message schemas          |
| [SLO Definitions](slo-definitions.md)         | Service Level Objectives           |
| [API Coverage](API_COVERAGE.md)               | Frontend API consumption analysis  |

### Testing and Quality

| Document                                                | Description                         |
| ------------------------------------------------------- | ----------------------------------- |
| [Testing Guide](TESTING_GUIDE.md)                       | Comprehensive testing documentation |
| [Test Performance Metrics](TEST_PERFORMANCE_METRICS.md) | Test suite performance baselines    |
| [Mutation Testing](MUTATION_TESTING.md)                 | Mutation testing setup and results  |
| [Frontend Patterns](FRONTEND_PATTERNS.md)               | React component testing patterns    |
| [Development Testing](development/testing.md)           | Unit and integration test guide     |
| [Coverage Guide](development/coverage.md)               | Code coverage requirements          |

### Development Tools

| Document                                                      | Description                          |
| ------------------------------------------------------------- | ------------------------------------ |
| [UV Package Manager](UV_USAGE.md)                             | Python dependency management with uv |
| [Local Setup](developer/local-setup.md)                       | Development environment setup        |
| [Codebase Tour](developer/codebase-tour.md)                   | Directory structure walkthrough      |
| [Code Patterns](development/patterns.md)                      | Async patterns and best practices    |
| [Pre-commit Hooks](development/hooks.md)                      | Code quality enforcement             |
| [Contributing Guide](development/contributing.md)             | PR process and conventions           |
| [Git Worktree Workflow](development/git-worktree-workflow.md) | Parallel development workflow        |
| [Agent Coordination](development/AGENT_COORDINATION.md)       | AI agent development patterns        |

### External Integrations

| Document                                           | Description                       |
| -------------------------------------------------- | --------------------------------- |
| [GitHub Copilot Setup](COPILOT_SETUP.md)           | Configure Copilot for development |
| [Chrome DevTools MCP](CHROME_DEVTOOLS_MCP.md)      | Browser debugging via MCP         |
| [Self-Hosted Runner](SELF_HOSTED_RUNNER.md)        | GitHub Actions GPU runner setup   |
| [Linear Integration](LINEAR-GITHUB-INTEGRATION.md) | Linear issue tracking setup       |
| [GitHub Models](GITHUB_MODELS.md)                  | Using GitHub Models API           |

### Operator Guides

| Document                                                     | Description                     |
| ------------------------------------------------------------ | ------------------------------- |
| [Deployment Modes](operator/deployment-modes.md)             | Production vs development modes |
| [GPU Setup](operator/gpu-setup.md)                           | NVIDIA GPU passthrough          |
| [Database Guide](operator/database.md)                       | PostgreSQL configuration        |
| [Redis Guide](operator/redis.md)                             | Redis setup and authentication  |
| [Backup and Recovery](operator/backup.md)                    | Database backup procedures      |
| [Monitoring](operator/monitoring.md)                         | Observability and metrics       |
| [Prometheus Alerting](operator/prometheus-alerting.md)       | Alert rules and notifications   |
| [Service Control](operator/service-control.md)               | Start/stop/restart services     |
| [DLQ Management](operator/dlq-management.md)                 | Failed job recovery             |
| [Scene Change Detection](operator/scene-change-detection.md) | Camera tampering alerts         |
| [Storage Retention](admin-guide/storage-retention.md)        | Data retention policies         |
| [Admin Configuration](admin-guide/configuration.md)          | Environment configuration       |
| [Admin Monitoring](admin-guide/monitoring.md)                | System monitoring setup         |
| [Admin Troubleshooting](admin-guide/troubleshooting.md)      | Common issues and solutions     |

### User Guides

| Document                                                       | Description                        |
| -------------------------------------------------------------- | ---------------------------------- |
| [Getting Started](user-guide/getting-started.md)               | First-time user setup              |
| [Dashboard Overview](user-guide/dashboard-overview.md)         | Main screen layout                 |
| [Using the Dashboard](user-guide/using-the-dashboard.md)       | Complete feature walkthrough       |
| [Understanding Alerts](user-guide/understanding-alerts.md)     | Risk levels and responses          |
| [Alerts and Notifications](user-guide/alerts-notifications.md) | Notification configuration         |
| [Event Timeline](user-guide/event-timeline.md)                 | Browsing and filtering events      |
| [Event Investigation](user-guide/event-investigation.md)       | Deep-dive event analysis           |
| [Search](user-guide/search.md)                                 | Full-text event search             |
| [Settings](user-guide/settings.md)                             | System configuration               |
| [Detection Zones](user-guide/zones.md)                         | Zone-based detection configuration |
| [Keyboard Shortcuts](user-guide/keyboard-shortcuts.md)         | Command palette and navigation     |
| [Mobile PWA](user-guide/mobile-pwa.md)                         | Mobile app and push notifications  |
| [Accessibility](user-guide/accessibility.md)                   | Screen readers and WCAG compliance |
| [Prompt Playground](user-guide/prompt-playground.md)           | AI prompt testing UI               |
| [Logs Dashboard](user-guide/logs-dashboard.md)                 | Application log viewer             |

### Developer Deep Dives

| Document                                                          | Description                           |
| ----------------------------------------------------------------- | ------------------------------------- |
| [Pipeline Overview](developer/pipeline-overview.md)               | AI pipeline architecture              |
| [Detection Service](developer/detection-service.md)               | RT-DETRv2 integration                 |
| [Batching Logic](developer/batching-logic.md)                     | Detection batch aggregation           |
| [Risk Analysis](developer/risk-analysis.md)                       | Nemotron risk scoring                 |
| [Prompt Management](developer/prompt-management.md)               | Prompt versioning and A/B testing     |
| [Alert System](developer/alerts.md)                               | Alert rules and evaluation            |
| [Data Model](developer/data-model.md)                             | Database schema reference             |
| [Video Processing](developer/video.md)                            | FTP uploads and frame extraction      |
| [Clip Generation](developer/clip-generation.md)                   | Event video clips                     |
| [Entity Tracking](developer/entity-tracking.md)                   | Cross-camera re-identification        |
| [Frontend Hooks](architecture/frontend-hooks.md)                  | React hook patterns                   |
| [Backend Patterns](developer/backend-patterns.md)                 | Repository pattern and error handling |
| [Resilience Patterns](developer/resilience-patterns.md)           | Circuit breakers and retries          |
| [UX Patterns](developer/ux-patterns.md)                           | Toast notifications and transitions   |
| [Keyboard Patterns](developer/keyboard-patterns.md)               | Shortcut implementation               |
| [Accessibility](developer/accessibility.md)                       | ARIA patterns and a11y testing        |
| [Visualization Components](developer/visualization-components.md) | Dashboard widgets and charts          |

### Reference

| Document                                                   | Description                     |
| ---------------------------------------------------------- | ------------------------------- |
| [Glossary](reference/glossary.md)                          | Terminology definitions         |
| [Stability Levels](reference/stability.md)                 | API stability classifications   |
| [Risk Levels](reference/config/risk-levels.md)             | Risk score definitions          |
| [Environment Reference](reference/config/env-reference.md) | Complete env variable list      |
| [Roadmap](ROADMAP.md)                                      | Post-MVP features and direction |

### Troubleshooting

| Document                                                            | Description                      |
| ------------------------------------------------------------------- | -------------------------------- |
| [Troubleshooting Index](reference/troubleshooting/index.md)         | Triage flowchart and quick fixes |
| [AI Issues](reference/troubleshooting/ai-issues.md)                 | AI service troubleshooting       |
| [Database Issues](reference/troubleshooting/database-issues.md)     | PostgreSQL troubleshooting       |
| [Connection Issues](reference/troubleshooting/connection-issues.md) | Network and connectivity         |
| [GPU Issues](reference/troubleshooting/gpu-issues.md)               | NVIDIA GPU troubleshooting       |

### Benchmarks

| Document                                                 | Description                     |
| -------------------------------------------------------- | ------------------------------- |
| [Model Zoo Benchmark](benchmarks/model-zoo-benchmark.md) | AI model performance comparison |

---

## Quick Links

- **API Docs**: `http://localhost:8000/docs` (Swagger UI when running)
- **Issue Tracking**: [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active)
- **AGENTS.md Files**: Every directory has one - start there for navigation

---

## Documentation Structure

```
docs/
  README.md                # This file - navigation hub
  user-hub.md              # End-user documentation hub
  operator-hub.md          # Operator/sysadmin documentation hub
  developer-hub.md         # Developer documentation hub

  # Top-level guides
  AI_SETUP.md              # AI services configuration
  DEPLOYMENT.md            # Deployment overview
  DOCKER_DEPLOYMENT.md     # Container deployment
  RUNTIME_CONFIG.md        # Environment configuration
  SECURITY.md              # Security documentation
  TESTING_GUIDE.md         # Testing documentation
  ROADMAP.md               # Future features

  # Subdirectories
  getting-started/         # Installation and setup
  architecture/            # Technical system design
  api-reference/           # REST and WebSocket APIs
  developer/               # Developer deep dives
  development/             # Contributing and code quality
  operator/                # Deployment and operations
  admin-guide/             # Administrator guides
  user-guide/              # End-user guides
  user/                    # Additional user documentation
  reference/               # Glossary, config, troubleshooting
  plans/                   # Design specs and implementation plans
  decisions/               # Architectural decision records (ADRs)
  benchmarks/              # Performance benchmarks
  images/                  # Diagrams and screenshots
```

---

## Contributing to Documentation

When adding new documentation:

1. **User-facing guides** go in `user-guide/` or `user/`
2. **Operator guides** go in `operator/` or `admin-guide/`
3. **Developer guides** go in `developer/` or `development/`
4. **Technical architecture** goes in `architecture/`
5. **API documentation** goes in `api-reference/`
6. **Design plans** go in `plans/` with date prefix (e.g., `2025-01-15-feature-design.md`)
7. **Architectural decisions** go in `decisions/`
8. **Update this README** to link to new documents
9. **Update the relevant hub** (user-hub.md, operator-hub.md, or developer-hub.md)

All documentation should be:

- Written in Markdown
- Clear and concise
- Kept up to date with code changes
- Cross-linked to related documents
