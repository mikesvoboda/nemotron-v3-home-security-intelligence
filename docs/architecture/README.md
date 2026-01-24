# Architecture Documentation

> Comprehensive technical documentation for the AI-powered home security monitoring system

## Project Overview

This system is an AI-powered home security monitoring dashboard that processes camera feeds in real-time to detect and analyze security-relevant events. The architecture combines RT-DETRv2 for object detection with Nemotron for intelligent risk assessment, creating a sophisticated pipeline that transforms raw camera images into actionable security insights with LLM-determined risk scores.

The system follows an event-driven architecture with batch processing semantics. Camera images flow through a detection pipeline, are grouped into 90-second time windows, and analyzed by an LLM to produce risk-scored security events. Real-time updates are pushed to a React frontend via WebSockets, enabling immediate user awareness of security situations.

Built for single-user local deployment, the system is fully containerized with GPU passthrough for AI models. It maintains 30 days of event retention and operates without authentication overhead, optimized for home security use cases where simplicity and reliability are paramount.

## Quick Navigation

| Hub                                                    | Description                                  | Key Components                                 |
| ------------------------------------------------------ | -------------------------------------------- | ---------------------------------------------- |
| [System Overview](./system-overview/README.md)         | High-level architecture and design decisions | Architecture diagrams, design rationale        |
| [Detection Pipeline](./detection-pipeline/README.md)   | Image processing and object detection        | RT-DETRv2, file watcher, detection flow        |
| [AI Orchestration](./ai-orchestration/README.md)       | LLM integration and risk assessment          | Nemotron, batch processing, prompt engineering |
| [Real-time System](./realtime-system/README.md)        | WebSocket and live updates                   | Event broadcasting, connection management      |
| [Data Model](./data-model/README.md)                   | Database schema and relationships            | SQLAlchemy models, migrations                  |
| [API Reference](./api-reference/README.md)             | REST endpoint documentation                  | FastAPI routes, request/response schemas       |
| [Resilience Patterns](./resilience-patterns/README.md) | Error handling and recovery                  | Retry logic, circuit breakers, fallbacks       |
| [Observability](./observability/README.md)             | Logging, metrics, and monitoring             | Prometheus, Grafana, structured logging        |
| [Background Services](./background-services/README.md) | Async tasks and workers                      | Retention cleanup, health checks               |
| [Middleware](./middleware/README.md)                   | Request processing pipeline                  | Logging, error handling, CORS                  |
| [Frontend](./frontend/README.md)                       | React UI architecture                        | Components, hooks, state management            |
| [Testing](./testing/README.md)                         | Test infrastructure and patterns             | Unit, integration, E2E testing                 |
| [Security](./security/README.md)                       | Security considerations                      | Input validation, data protection              |
| [Dataflows](./dataflows/README.md)                     | End-to-end data traces                       | Request flows, event sequences                 |

## Audience Guide

### For Developers

Start with [System Overview](./system-overview/README.md) to understand the high-level architecture, then dive into specific hubs based on your task. Use [Dataflows](./dataflows/README.md) to understand how data moves through the system.

### For Integrators

Begin with [API Reference](./api-reference/README.md) for REST endpoints and [Real-time System](./realtime-system/README.md) for WebSocket integration. The [Data Model](./data-model/README.md) documents all entities and relationships.

### For Maintainers

Focus on [Resilience Patterns](./resilience-patterns/README.md) for error handling, [Observability](./observability/README.md) for monitoring, and [Testing](./testing/README.md) for quality assurance patterns.

## How to Use This Documentation

1. **Finding Information**: Use the navigation table above to locate the relevant hub. Each hub contains a README with links to detailed documents.

2. **Code References**: All documentation includes precise code citations in the format `path/to/file.py:line` or `path/to/file.py:start-end`. Use these to locate the exact implementation.

3. **Diagrams**: Architecture diagrams use Mermaid syntax and can be rendered in GitHub, VS Code, or any Mermaid-compatible viewer.

4. **Cross-References**: Documents link to related topics. Follow these links to build a complete understanding of interconnected systems.

## How to Contribute

1. **Follow Standards**: Read [STANDARDS.md](./STANDARDS.md) before writing documentation.

2. **Use Templates**: Start from templates in the [templates/](./templates/) directory.

3. **Validate**: Run `python -m scripts.validate_docs docs/architecture/` before committing.

4. **Keep Current**: Update documentation when modifying code. Outdated docs are worse than no docs.

### Documentation Workflow

```bash
# Create new document from template
cp docs/architecture/templates/document-template.md docs/architecture/{hub}/new-doc.md

# Validate documentation
python -m scripts.validate_docs docs/architecture/

# Preview Mermaid diagrams
# Use VS Code with Mermaid extension or mermaid.live
```

## Related Resources

- [STANDARDS.md](./STANDARDS.md) - Documentation standards and formatting rules
- [Templates](./templates/) - Document templates for new content
- [AGENTS.md](./AGENTS.md) - Codebase navigation guide
- [docs/ROADMAP.md](../ROADMAP.md) - Project roadmap
