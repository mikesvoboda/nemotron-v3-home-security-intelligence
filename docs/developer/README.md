# Developer Hub

> Entry point for developers and contributors to understand, extend, and contribute to Home Security Intelligence.

---

## Quick Start

| Task                           | Link                                |
| ------------------------------ | ----------------------------------- |
| Set up development environment | [Local Setup](local-setup.md)       |
| Explore the codebase           | [Codebase Tour](codebase-tour.md)   |
| Understand the architecture    | [Architecture](architecture/)       |
| Learn the patterns             | [Patterns & Testing](patterns/)     |
| Contribute code                | [Contributing Guide](contributing/) |

**Interactive API Docs:** Available at `/docs` (Swagger UI) when the backend is running.

---

## Architecture

System design, data flow, and technology decisions.

| Document                                     | Description                                    |
| -------------------------------------------- | ---------------------------------------------- |
| [Architecture Overview](architecture/)       | High-level system design and component diagram |
| [Data Model](data-model.md)                  | PostgreSQL schemas and entity relationships    |
| [AI Pipeline Overview](pipeline-overview.md) | FileWatcher -> RT-DETRv2 -> Nemotron flow      |

**AI Pipeline Deep Dives:**

- [Detection Service](detection-service.md) - RT-DETRv2 API and bounding boxes
- [Batching Logic](batching-logic.md) - Time-windowed batch aggregation
- [Risk Analysis](risk-analysis.md) - Nemotron prompts and scoring
- [Prompt Management](prompt-management.md) - A/B testing and versioning

---

## API Reference

Full REST and WebSocket API documentation.

| Resource       | Link                                         |
| -------------- | -------------------------------------------- |
| API Overview   | [Overview](../api-reference/overview.md)     |
| Cameras API    | [Cameras](../api-reference/cameras.md)       |
| Events API     | [Events](../api-reference/events.md)         |
| Detections API | [Detections](../api-reference/detections.md) |
| WebSocket API  | [WebSocket](../api-reference/websocket.md)   |
| System API     | [System](../api-reference/system.md)         |

**Interactive Docs:** Start the backend and visit `http://localhost:8000/docs` for Swagger UI.

---

## Patterns & Testing

Code patterns, testing strategies, and quality standards.

| Document                                      | Description                              |
| --------------------------------------------- | ---------------------------------------- |
| [Testing Guide](../TESTING_GUIDE.md)          | TDD workflow, fixtures, coverage         |
| [Backend Patterns](backend-patterns.md)       | Repository pattern, Result types, errors |
| [Resilience Patterns](resilience-patterns.md) | Circuit breakers, retry logic            |
| [UX Patterns](ux-patterns.md)                 | Toast notifications, transitions         |
| [Keyboard Patterns](keyboard-patterns.md)     | Shortcuts and command palette            |
| [Accessibility](accessibility.md)             | WCAG compliance and ARIA patterns        |

---

## Contributing

Everything you need to contribute to the project.

| Document                                             | Description                   |
| ---------------------------------------------------- | ----------------------------- |
| [Contributing Guide](contributing/)                  | Full contributor workflow     |
| [Code Quality Tools](../development/code-quality.md) | Linting, formatting, analysis |
| [Pre-commit Hooks](../development/hooks.md)          | Hook configuration and usage  |

### Quick Contribution Workflow

```bash
# 1. Set up environment
uv sync --extra dev

# 2. Find work in Linear
# https://linear.app/nemotron-v3-home-security/team/NEM/active

# 3. Create branch and implement
git checkout -b feature/my-feature

# 4. Run validation before PR
./scripts/validate.sh

# 5. Create PR
gh pr create --title "feat: my feature"
```

---

## Key Resources

### Service Ports

| Service     | Port | Protocol |
| ----------- | ---- | -------- |
| Frontend    | 5173 | HTTP     |
| Backend API | 8000 | HTTP/WS  |
| PostgreSQL  | 5432 | TCP      |
| Redis       | 6379 | TCP      |
| RT-DETRv2   | 8090 | HTTP     |
| Nemotron    | 8091 | HTTP     |

### AGENTS.md Navigation

Every directory contains an `AGENTS.md` file with purpose, key files, and patterns:

```bash
# List all AGENTS.md files
find . -name "AGENTS.md" -type f | head -20
```

| Directory             | Purpose               |
| --------------------- | --------------------- |
| `/AGENTS.md`          | Project overview      |
| `/backend/AGENTS.md`  | Backend architecture  |
| `/frontend/AGENTS.md` | Frontend architecture |
| `/ai/AGENTS.md`       | AI pipeline details   |

---

## Related Documentation

| Hub                                | Audience                        |
| ---------------------------------- | ------------------------------- |
| [User Hub](../user-hub.md)         | End users - dashboard usage     |
| [Operator Hub](../operator-hub.md) | Admins - deployment, monitoring |
| **Developer Hub**                  | You are here                    |

---

[Back to Documentation Index](../README.md)
