# Documentation

> The central navigation hub for all Home Security Intelligence documentation.

For a quick overview of the project and getting started instructions, see the [main README](../README.md).

---

## By Audience

### Users

Non-technical guides for operating and understanding the system.

> New here? See [Stability Levels](reference/stability.md) to understand what’s stable vs still evolving.

| Document                                                               | Description                           |
| ---------------------------------------------------------------------- | ------------------------------------- |
| [User Guide: Getting Started](user-guide/getting-started.md)           | First-time setup and basic usage      |
| [User Guide: Using the Dashboard](user-guide/using-the-dashboard.md)   | Understanding the dashboard interface |
| [User Guide: Understanding Alerts](user-guide/understanding-alerts.md) | Risk levels and alert interpretation  |

### Architecture

Technical deep-dives into system design and components.

| Document                                                 | Description                           |
| -------------------------------------------------------- | ------------------------------------- |
| [Architecture: Overview](architecture/overview.md)       | High-level architecture and data flow |
| [Architecture: AI Pipeline](architecture/ai-pipeline.md) | RT-DETRv2 and Nemotron integration    |
| [Architecture: Data Model](architecture/data-model.md)   | PostgreSQL schema and relationships   |
| [Architecture: Decisions](architecture/decisions.md)     | Architectural Decision Records (ADRs) |

### Development

Setup guides, deployment instructions, and contributing guidelines.

| Document                                      | Description                                  |
| --------------------------------------------- | -------------------------------------------- |
| [AI Setup Guide](AI_SETUP.md)                 | Configure RT-DETRv2 and Nemotron AI services |
| [Docker Deployment](DOCKER_DEPLOYMENT.md)     | Deploy with Docker or Podman Compose         |
| [Runtime Configuration](RUNTIME_CONFIG.md)    | Environment variables and service ports      |
| [Self-Hosted Runner](SELF_HOSTED_RUNNER.md)   | GitHub Actions GPU runner setup              |
| [GitHub Copilot Setup](COPILOT_SETUP.md)      | Configure Copilot for development            |
| [GitHub Models](GITHUB_MODELS.md)             | Using GitHub Models API                      |
| [Chrome DevTools MCP](CHROME_DEVTOOLS_MCP.md) | Browser debugging via MCP                    |

### Reference

Design plans, architectural decisions, and future roadmap.

| Document                                                                               | Description                                       |
| -------------------------------------------------------------------------------------- | ------------------------------------------------- |
| [Roadmap](ROADMAP.md)                                                                  | Post-MVP features and future direction            |
| **Plans**                                                                              |                                                   |
| [Dashboard MVP Design](plans/2024-12-21-dashboard-mvp-design.md)                       | Original dashboard design specification           |
| [MVP Implementation Plan](plans/2024-12-22-mvp-implementation-plan.md)                 | Phase-by-phase implementation guide               |
| [Logging System Design](plans/2024-12-24-logging-system-design.md)                     | Structured logging architecture                   |
| [Logging Implementation](plans/2024-12-24-logging-implementation-plan.md)              | Logging system implementation details             |
| [GitHub CI/CD Design](plans/2025-12-26-github-cicd-design.md)                          | CI/CD pipeline architecture                       |
| [GitHub CI/CD Implementation](plans/2025-12-26-github-cicd-implementation.md)          | CI/CD implementation details                      |
| [Service Health Monitoring](plans/2025-12-26-service-health-monitoring-design.md)      | Health check and monitoring design                |
| [README Redesign](plans/2025-12-26-readme-redesign.md)                                 | Documentation refresh plan                        |
| [Documentation Design](plans/2025-12-28-documentation-design.md)                       | This documentation restructure                    |
| [Test Performance Design](plans/2025-12-30-test-performance-optimization-design.md)    | Test time limits and audit design                 |
| [Test Performance Implementation](plans/2025-12-30-test-performance-implementation.md) | Test performance implementation tasks             |
| **Decisions**                                                                          |                                                   |
| [Grafana Integration](decisions/grafana-integration.md)                                | Decision to use native charts over Grafana embeds |
| **Verification**                                                                       |                                                   |
| [Docker Verification Summary](DOCKER_VERIFICATION_SUMMARY.md)                          | Docker deployment test results                    |

---

## Quick Links

- **Getting Started**: [Main README](../README.md#quick-start-60-seconds)
- **API Reference**: `http://localhost:8000/docs` (Swagger UI when running)
- **Issue Tracking**: Use [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) to find available work
- **AGENTS.md Files**: Every directory contains an `AGENTS.md` explaining its purpose

---

## Documentation Structure

```
docs/
  README.md              # This file - navigation hub
  user-guide/            # Non-technical user documentation
  architecture/          # Technical system design
  plans/                 # Design specs and implementation plans
  decisions/             # Architectural decision records (ADRs)
  images/                # Diagrams and screenshots

  # Top-level guides
  AI_SETUP.md            # AI services configuration
  DOCKER_DEPLOYMENT.md   # Container deployment
  RUNTIME_CONFIG.md      # Environment configuration
  ROADMAP.md             # Future features
```

---

## Contributing to Documentation

When adding new documentation:

1. **User-facing guides** go in `user-guide/`
2. **Technical architecture** goes in `architecture/`
3. **Design plans** go in `plans/` with date prefix (e.g., `2025-01-15-feature-design.md`)
4. **Architectural decisions** go in `decisions/`
5. **Update this README** to link to new documents

All documentation should be:

- Written in Markdown
- Clear and concise
- Kept up to date with code changes
