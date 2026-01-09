# AGENTS.md Navigation Index

This document serves as a comprehensive navigation hub for all 188 AGENTS.md files in the Home Security Intelligence repository. AGENTS.md files provide contextual guidance for AI agents and developers exploring the codebase.

## What are AGENTS.md Files?

AGENTS.md files are navigation guides placed in every significant directory throughout the codebase. Each file documents:

- **Purpose**: What the directory contains and why it exists
- **Key Files**: Important files and their responsibilities
- **Patterns**: Coding conventions, architectural decisions, and best practices
- **Entry Points**: Where to start when exploring the directory

These files enable AI coding assistants and developers to quickly understand unfamiliar parts of the codebase without reading every source file.

## How to Read AGENTS.md Files

Each AGENTS.md follows a consistent structure:

```markdown
# [Directory Name] - Agent Guide

## Purpose

Brief description of the directory's role in the system.

## Directory Structure

Tree view of files and subdirectories.

## Key Files

Table of important files with descriptions.

## Important Patterns

Coding conventions and architectural decisions.

## Entry Points

Where to start for specific goals.

## Related Documentation

Links to related AGENTS.md files.
```

**Reading Tips:**

- Start with the root `/AGENTS.md` for project overview
- Read `/CLAUDE.md` for comprehensive project instructions
- Navigate to specific AGENTS.md files based on what you need to modify
- Each directory's AGENTS.md links to related subdirectories

---

## Project-Level Guides

Essential entry points for understanding the entire project.

| Path                       | Description                                                                                                                                                                 |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`/CLAUDE.md`](/CLAUDE.md) | Comprehensive Claude Code instructions with project overview, phase execution order, TDD approach, testing requirements, and git rules. **Start here for project context.** |
| [`/AGENTS.md`](/AGENTS.md) | Root project navigation: tech stack, directory structure, issue tracking (Linear), development workflow, key design decisions, and data flow                                |
| [`/README.md`](/README.md) | Project overview, quick start guide, and feature highlights                                                                                                                 |

---

## For Developers

Documentation for software engineers building and extending the system.

### Developer Documentation Hub

| Path                                                     | Description                                                                                               |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| [`/docs/developer-hub.md`](/docs/developer-hub.md)       | Central navigation page linking to all developer documentation                                            |
| [`/docs/developer/AGENTS.md`](/docs/developer/AGENTS.md) | Developer docs directory: local setup, codebase tour, hooks, backend patterns, accessibility, UX patterns |

### Architecture Documentation

| Path                                                           | Description                                                                                                    |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| [`/docs/architecture/AGENTS.md`](/docs/architecture/AGENTS.md) | Technical architecture: system overview, AI pipeline, data model, real-time communication, resilience patterns |
| [`/docs/decisions/AGENTS.md`](/docs/decisions/AGENTS.md)       | Architecture Decision Records (ADRs) documenting significant technical choices                                 |

### Backend Development

| Path                                                                                                           | Description                                                                                          |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| [`/backend/AGENTS.md`](/backend/AGENTS.md)                                                                     | Backend architecture: FastAPI application, 22 API routes, 89 services, 19 models, data flow diagrams |
| [`/backend/api/AGENTS.md`](/backend/api/AGENTS.md)                                                             | API layer structure: routes, schemas, middleware, dependencies, exception handlers                   |
| [`/backend/api/routes/AGENTS.md`](/backend/api/routes/AGENTS.md)                                               | REST endpoint documentation: cameras, events, detections, system, WebSocket                          |
| [`/backend/api/schemas/AGENTS.md`](/backend/api/schemas/AGENTS.md)                                             | Pydantic schema definitions: request/response models, validation, error handling                     |
| [`/backend/api/middleware/AGENTS.md`](/backend/api/middleware/AGENTS.md)                                       | HTTP middleware: auth, rate limiting, logging, security headers, body limits                         |
| [`/backend/api/helpers/AGENTS.md`](/backend/api/helpers/AGENTS.md)                                             | Route helper functions: enrichment transformers                                                      |
| [`/backend/core/AGENTS.md`](/backend/core/AGENTS.md)                                                           | Core infrastructure: config, database, Redis, logging, metrics, TLS, circuit breaker                 |
| [`/backend/core/middleware/AGENTS.md`](/backend/core/middleware/AGENTS.md)                                     | Core middleware components                                                                           |
| [`/backend/models/AGENTS.md`](/backend/models/AGENTS.md)                                                       | SQLAlchemy ORM models: Camera, Detection, Event, Zone, Alert, GPUStats                               |
| [`/backend/repositories/AGENTS.md`](/backend/repositories/AGENTS.md)                                           | Data access layer: generic Repository pattern, camera/detection/event repositories                   |
| [`/backend/services/AGENTS.md`](/backend/services/AGENTS.md)                                                   | Business logic: AI pipeline, file watcher, batch aggregation, enrichment, alerts                     |
| [`/backend/services/orchestrator/AGENTS.md`](/backend/services/orchestrator/AGENTS.md)                         | Service orchestration subsystem                                                                      |
| [`/backend/alembic/AGENTS.md`](/backend/alembic/AGENTS.md)                                                     | Database migrations using Alembic                                                                    |
| [`/backend/alembic/versions/AGENTS.md`](/backend/alembic/versions/AGENTS.md)                                   | Migration version files                                                                              |
| [`/backend/scripts/AGENTS.md`](/backend/scripts/AGENTS.md)                                                     | Backend utility scripts: VRAM benchmarking                                                           |
| [`/backend/examples/AGENTS.md`](/backend/examples/AGENTS.md)                                                   | Example scripts: Redis usage patterns                                                                |
| [`/backend/data/AGENTS.md`](/backend/data/AGENTS.md)                                                           | Runtime data directory: sample images, thumbnails                                                    |
| [`/backend/data/cameras/AGENTS.md`](/backend/data/cameras/AGENTS.md)                                           | Camera data directories                                                                              |
| [`/backend/data/cameras/backyard/AGENTS.md`](/backend/data/cameras/backyard/AGENTS.md)                         | Backyard camera data                                                                                 |
| [`/backend/data/cameras/driveway/AGENTS.md`](/backend/data/cameras/driveway/AGENTS.md)                         | Driveway camera data                                                                                 |
| [`/backend/data/cameras/front_door/AGENTS.md`](/backend/data/cameras/front_door/AGENTS.md)                     | Front door camera data                                                                               |
| [`/backend/data/prompts/AGENTS.md`](/backend/data/prompts/AGENTS.md)                                           | AI prompt templates directory                                                                        |
| [`/backend/data/prompts/nemotron/AGENTS.md`](/backend/data/prompts/nemotron/AGENTS.md)                         | Nemotron LLM prompts                                                                                 |
| [`/backend/data/prompts/nemotron/history/AGENTS.md`](/backend/data/prompts/nemotron/history/AGENTS.md)         | Nemotron prompt version history                                                                      |
| [`/backend/data/prompts/florence2/AGENTS.md`](/backend/data/prompts/florence2/AGENTS.md)                       | Florence-2 vision prompts                                                                            |
| [`/backend/data/prompts/florence2/history/AGENTS.md`](/backend/data/prompts/florence2/history/AGENTS.md)       | Florence-2 prompt history                                                                            |
| [`/backend/data/prompts/fashion_clip/AGENTS.md`](/backend/data/prompts/fashion_clip/AGENTS.md)                 | FashionCLIP prompts                                                                                  |
| [`/backend/data/prompts/fashion_clip/history/AGENTS.md`](/backend/data/prompts/fashion_clip/history/AGENTS.md) | FashionCLIP prompt history                                                                           |
| [`/backend/data/prompts/xclip/AGENTS.md`](/backend/data/prompts/xclip/AGENTS.md)                               | X-CLIP video prompts                                                                                 |
| [`/backend/data/prompts/xclip/history/AGENTS.md`](/backend/data/prompts/xclip/history/AGENTS.md)               | X-CLIP prompt history                                                                                |
| [`/backend/data/prompts/yolo_world/AGENTS.md`](/backend/data/prompts/yolo_world/AGENTS.md)                     | YOLO-World detection prompts                                                                         |
| [`/backend/data/prompts/yolo_world/history/AGENTS.md`](/backend/data/prompts/yolo_world/history/AGENTS.md)     | YOLO-World prompt history                                                                            |

### Frontend Development

| Path                                                                                                     | Description                                                                     |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| [`/frontend/AGENTS.md`](/frontend/AGENTS.md)                                                             | Frontend architecture: React + TypeScript + Tailwind, Vite config, testing, PWA |
| [`/frontend/src/AGENTS.md`](/frontend/src/AGENTS.md)                                                     | Source code organization                                                        |
| [`/frontend/src/components/AGENTS.md`](/frontend/src/components/AGENTS.md)                               | React component hierarchy and conventions                                       |
| [`/frontend/src/components/ai/AGENTS.md`](/frontend/src/components/ai/AGENTS.md)                         | AI-related components                                                           |
| [`/frontend/src/components/ai/__tests__/AGENTS.md`](/frontend/src/components/ai/__tests__/AGENTS.md)     | AI component tests                                                              |
| [`/frontend/src/components/ai-audit/AGENTS.md`](/frontend/src/components/ai-audit/AGENTS.md)             | AI audit trail components                                                       |
| [`/frontend/src/components/ai-performance/AGENTS.md`](/frontend/src/components/ai-performance/AGENTS.md) | AI performance monitoring components                                            |
| [`/frontend/src/components/alerts/AGENTS.md`](/frontend/src/components/alerts/AGENTS.md)                 | Alert management components                                                     |
| [`/frontend/src/components/analytics/AGENTS.md`](/frontend/src/components/analytics/AGENTS.md)           | Analytics components                                                            |
| [`/frontend/src/components/audit/AGENTS.md`](/frontend/src/components/audit/AGENTS.md)                   | Audit logging components                                                        |
| [`/frontend/src/components/common/AGENTS.md`](/frontend/src/components/common/AGENTS.md)                 | Shared/common components                                                        |
| [`/frontend/src/components/dashboard/AGENTS.md`](/frontend/src/components/dashboard/AGENTS.md)           | Dashboard components: risk gauge, camera grid, activity feed                    |
| [`/frontend/src/components/detection/AGENTS.md`](/frontend/src/components/detection/AGENTS.md)           | Detection display components                                                    |
| [`/frontend/src/components/entities/AGENTS.md`](/frontend/src/components/entities/AGENTS.md)             | Entity tracking components                                                      |
| [`/frontend/src/components/events/AGENTS.md`](/frontend/src/components/events/AGENTS.md)                 | Event display components                                                        |
| [`/frontend/src/components/layout/AGENTS.md`](/frontend/src/components/layout/AGENTS.md)                 | Layout components: navigation, headers, sidebars                                |
| [`/frontend/src/components/logs/AGENTS.md`](/frontend/src/components/logs/AGENTS.md)                     | Log viewer components                                                           |
| [`/frontend/src/components/search/AGENTS.md`](/frontend/src/components/search/AGENTS.md)                 | Search components                                                               |
| [`/frontend/src/components/settings/AGENTS.md`](/frontend/src/components/settings/AGENTS.md)             | Settings page components                                                        |
| [`/frontend/src/components/status/AGENTS.md`](/frontend/src/components/status/AGENTS.md)                 | Status display components                                                       |
| [`/frontend/src/components/system/AGENTS.md`](/frontend/src/components/system/AGENTS.md)                 | System monitoring components                                                    |
| [`/frontend/src/components/video/AGENTS.md`](/frontend/src/components/video/AGENTS.md)                   | Video player and clip components                                                |
| [`/frontend/src/components/zones/AGENTS.md`](/frontend/src/components/zones/AGENTS.md)                   | Zone management components                                                      |
| [`/frontend/src/hooks/AGENTS.md`](/frontend/src/hooks/AGENTS.md)                                         | Custom React hooks: WebSocket, event streams, data fetching                     |
| [`/frontend/src/services/AGENTS.md`](/frontend/src/services/AGENTS.md)                                   | API client and logging services                                                 |
| [`/frontend/src/stores/AGENTS.md`](/frontend/src/stores/AGENTS.md)                                       | State management stores                                                         |
| [`/frontend/src/contexts/AGENTS.md`](/frontend/src/contexts/AGENTS.md)                                   | React contexts: SystemData, Toast                                               |
| [`/frontend/src/config/AGENTS.md`](/frontend/src/config/AGENTS.md)                                       | Environment configuration and tour steps                                        |
| [`/frontend/src/styles/AGENTS.md`](/frontend/src/styles/AGENTS.md)                                       | CSS and Tailwind styling                                                        |
| [`/frontend/src/types/AGENTS.md`](/frontend/src/types/AGENTS.md)                                         | TypeScript type definitions                                                     |
| [`/frontend/src/types/generated/AGENTS.md`](/frontend/src/types/generated/AGENTS.md)                     | Auto-generated API types from OpenAPI                                           |
| [`/frontend/src/utils/AGENTS.md`](/frontend/src/utils/AGENTS.md)                                         | Utility functions                                                               |
| [`/frontend/src/mocks/AGENTS.md`](/frontend/src/mocks/AGENTS.md)                                         | MSW mock handlers for testing                                                   |
| [`/frontend/src/__mocks__/AGENTS.md`](/frontend/src/__mocks__/AGENTS.md)                                 | Jest/Vitest mock modules                                                        |
| [`/frontend/src/test/AGENTS.md`](/frontend/src/test/AGENTS.md)                                           | Test setup and configuration                                                    |
| [`/frontend/src/__tests__/AGENTS.md`](/frontend/src/__tests__/AGENTS.md)                                 | Global test files and custom matchers                                           |
| [`/frontend/src/test-utils/AGENTS.md`](/frontend/src/test-utils/AGENTS.md)                               | Test utilities: factories, renderWithProviders                                  |
| [`/frontend/public/AGENTS.md`](/frontend/public/AGENTS.md)                                               | Static assets: favicon, icons, manifest                                         |
| [`/frontend/public/images/AGENTS.md`](/frontend/public/images/AGENTS.md)                                 | Public image assets                                                             |
| [`/frontend/dist/AGENTS.md`](/frontend/dist/AGENTS.md)                                                   | Production build output (gitignored)                                            |

### AI Pipeline Development

| Path                                                   | Description                                                           |
| ------------------------------------------------------ | --------------------------------------------------------------------- |
| [`/ai/AGENTS.md`](/ai/AGENTS.md)                       | AI pipeline overview: service ports, VRAM usage, architecture diagram |
| [`/ai/rtdetr/AGENTS.md`](/ai/rtdetr/AGENTS.md)         | RT-DETRv2 object detection server: HuggingFace model, FastAPI server  |
| [`/ai/nemotron/AGENTS.md`](/ai/nemotron/AGENTS.md)     | Nemotron LLM for risk analysis: llama.cpp server, GGUF models         |
| [`/ai/clip/AGENTS.md`](/ai/clip/AGENTS.md)             | CLIP embedding server for entity re-identification                    |
| [`/ai/florence/AGENTS.md`](/ai/florence/AGENTS.md)     | Florence-2 vision-language server for attribute extraction            |
| [`/ai/enrichment/AGENTS.md`](/ai/enrichment/AGENTS.md) | Combined enrichment service: vehicle, pet, clothing, depth, pose      |

### Development Workflow

| Path                                                                                                         | Description                                                                     |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| [`/docs/development/AGENTS.md`](/docs/development/AGENTS.md)                                                 | Development workflow: contributing, code quality, coverage, patterns, setup     |
| [`/scripts/AGENTS.md`](/scripts/AGENTS.md)                                                                   | Development and deployment scripts: setup, validation, testing, database, CI/CD |
| [`/.github/AGENTS.md`](/.github/AGENTS.md)                                                                   | GitHub configuration: CI/CD workflows, security scanning, dependency management |
| [`/.github/workflows/AGENTS.md`](/.github/workflows/AGENTS.md)                                               | GitHub Actions workflows: CI, deploy, security, testing                         |
| [`/.github/codeql/AGENTS.md`](/.github/codeql/AGENTS.md)                                                     | CodeQL security analysis configuration                                          |
| [`/.github/codeql/custom-queries/AGENTS.md`](/.github/codeql/custom-queries/AGENTS.md)                       | Custom CodeQL queries                                                           |
| [`/.github/codeql/custom-queries/javascript/AGENTS.md`](/.github/codeql/custom-queries/javascript/AGENTS.md) | JavaScript/TypeScript CodeQL queries                                            |
| [`/.github/codeql/custom-queries/python/AGENTS.md`](/.github/codeql/custom-queries/python/AGENTS.md)         | Python CodeQL queries                                                           |
| [`/.github/prompts/AGENTS.md`](/.github/prompts/AGENTS.md)                                                   | AI prompt templates for code review                                             |
| [`/setup_lib/AGENTS.md`](/setup_lib/AGENTS.md)                                                               | Python utilities for setup.py                                                   |

### Testing Documentation

| Path                                                                                                               | Description                                                                                 |
| ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| [`/docs/testing/AGENTS.md`](/docs/testing/AGENTS.md)                                                               | Testing guides: TDD workflow, testing patterns, Hypothesis property-based testing           |
| [`/backend/tests/AGENTS.md`](/backend/tests/AGENTS.md)                                                             | Backend test infrastructure: 8,229 unit tests, 1,556 integration tests, fixtures, factories |
| [`/backend/tests/unit/AGENTS.md`](/backend/tests/unit/AGENTS.md)                                                   | Unit test patterns: isolated component testing                                              |
| [`/backend/tests/unit/api/AGENTS.md`](/backend/tests/unit/api/AGENTS.md)                                           | API route unit tests                                                                        |
| [`/backend/tests/unit/api/routes/AGENTS.md`](/backend/tests/unit/api/routes/AGENTS.md)                             | Route-specific unit tests                                                                   |
| [`/backend/tests/unit/api/schemas/AGENTS.md`](/backend/tests/unit/api/schemas/AGENTS.md)                           | Schema validation tests                                                                     |
| [`/backend/tests/unit/api/middleware/AGENTS.md`](/backend/tests/unit/api/middleware/AGENTS.md)                     | Middleware unit tests                                                                       |
| [`/backend/tests/unit/api/helpers/AGENTS.md`](/backend/tests/unit/api/helpers/AGENTS.md)                           | Helper function tests                                                                       |
| [`/backend/tests/unit/core/AGENTS.md`](/backend/tests/unit/core/AGENTS.md)                                         | Core infrastructure tests                                                                   |
| [`/backend/tests/unit/middleware/AGENTS.md`](/backend/tests/unit/middleware/AGENTS.md)                             | Middleware tests                                                                            |
| [`/backend/tests/unit/models/AGENTS.md`](/backend/tests/unit/models/AGENTS.md)                                     | ORM model tests                                                                             |
| [`/backend/tests/unit/routes/AGENTS.md`](/backend/tests/unit/routes/AGENTS.md)                                     | Additional route tests                                                                      |
| [`/backend/tests/unit/scripts/AGENTS.md`](/backend/tests/unit/scripts/AGENTS.md)                                   | Script tests                                                                                |
| [`/backend/tests/unit/services/AGENTS.md`](/backend/tests/unit/services/AGENTS.md)                                 | Service unit tests                                                                          |
| [`/backend/tests/unit/integration/AGENTS.md`](/backend/tests/unit/integration/AGENTS.md)                           | Integration helper tests                                                                    |
| [`/backend/tests/integration/AGENTS.md`](/backend/tests/integration/AGENTS.md)                                     | Integration test architecture: multi-component workflows                                    |
| [`/backend/tests/e2e/AGENTS.md`](/backend/tests/e2e/AGENTS.md)                                                     | End-to-end pipeline tests                                                                   |
| [`/backend/tests/gpu/AGENTS.md`](/backend/tests/gpu/AGENTS.md)                                                     | GPU service integration tests                                                               |
| [`/backend/tests/chaos/AGENTS.md`](/backend/tests/chaos/AGENTS.md)                                                 | Chaos engineering failure tests                                                             |
| [`/backend/tests/contracts/AGENTS.md`](/backend/tests/contracts/AGENTS.md)                                         | API contract tests                                                                          |
| [`/backend/tests/security/AGENTS.md`](/backend/tests/security/AGENTS.md)                                           | Security vulnerability tests                                                                |
| [`/backend/tests/benchmarks/AGENTS.md`](/backend/tests/benchmarks/AGENTS.md)                                       | Performance benchmarks                                                                      |
| [`/backend/tests/fixtures/AGENTS.md`](/backend/tests/fixtures/AGENTS.md)                                           | Test fixtures directory                                                                     |
| [`/backend/tests/fixtures/images/AGENTS.md`](/backend/tests/fixtures/images/AGENTS.md)                             | Test image fixtures                                                                         |
| [`/backend/tests/fixtures/images/pipeline_test/AGENTS.md`](/backend/tests/fixtures/images/pipeline_test/AGENTS.md) | Pipeline test images                                                                        |
| [`/backend/tests/utils/AGENTS.md`](/backend/tests/utils/AGENTS.md)                                                 | Test utilities                                                                              |
| [`/frontend/tests/AGENTS.md`](/frontend/tests/AGENTS.md)                                                           | Frontend test organization                                                                  |
| [`/frontend/tests/e2e/AGENTS.md`](/frontend/tests/e2e/AGENTS.md)                                                   | Playwright E2E tests: multi-browser, visual regression                                      |
| [`/frontend/tests/e2e/fixtures/AGENTS.md`](/frontend/tests/e2e/fixtures/AGENTS.md)                                 | E2E test fixtures                                                                           |
| [`/frontend/tests/e2e/pages/AGENTS.md`](/frontend/tests/e2e/pages/AGENTS.md)                                       | Page object models                                                                          |
| [`/frontend/tests/e2e/specs/AGENTS.md`](/frontend/tests/e2e/specs/AGENTS.md)                                       | E2E test specifications                                                                     |
| [`/frontend/tests/e2e/utils/AGENTS.md`](/frontend/tests/e2e/utils/AGENTS.md)                                       | E2E test utilities                                                                          |
| [`/frontend/tests/e2e/visual/AGENTS.md`](/frontend/tests/e2e/visual/AGENTS.md)                                     | Visual regression tests                                                                     |
| [`/frontend/tests/integration/AGENTS.md`](/frontend/tests/integration/AGENTS.md)                                   | Frontend integration tests                                                                  |
| [`/tests/AGENTS.md`](/tests/AGENTS.md)                                                                             | Root-level setup script tests                                                               |
| [`/tests/load/AGENTS.md`](/tests/load/AGENTS.md)                                                                   | Load testing scripts                                                                        |

---

## For Operators

Documentation for system administrators, DevOps engineers, and operators.

### Operator Documentation Hub

| Path                                                   | Description                                                                           |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| [`/docs/operator-hub.md`](/docs/operator-hub.md)       | Central navigation page linking to all operator documentation                         |
| [`/docs/operator/AGENTS.md`](/docs/operator/AGENTS.md) | Operator docs: AI configuration, GPU setup, backup, database, Redis, deployment modes |

### Getting Started

| Path                                                                 | Description                                              |
| -------------------------------------------------------------------- | -------------------------------------------------------- |
| [`/docs/getting-started/AGENTS.md`](/docs/getting-started/AGENTS.md) | Installation, first run, prerequisites, upgrading guides |

### Administration

| Path                                                         | Description                                                                          |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| [`/docs/admin-guide/AGENTS.md`](/docs/admin-guide/AGENTS.md) | Admin guide: configuration, monitoring, security, storage retention, troubleshooting |

### Monitoring and Observability

| Path                                                                                                               | Description                                                          |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| [`/monitoring/AGENTS.md`](/monitoring/AGENTS.md)                                                                   | Monitoring infrastructure: Prometheus, JSON exporter, alerting rules |
| [`/monitoring/grafana/AGENTS.md`](/monitoring/grafana/AGENTS.md)                                                   | Grafana configuration and dashboards                                 |
| [`/monitoring/grafana/dashboards/AGENTS.md`](/monitoring/grafana/dashboards/AGENTS.md)                             | Dashboard JSON definitions: pipeline, synthetic monitoring           |
| [`/monitoring/grafana/provisioning/AGENTS.md`](/monitoring/grafana/provisioning/AGENTS.md)                         | Auto-provisioning configs                                            |
| [`/monitoring/grafana/provisioning/dashboards/AGENTS.md`](/monitoring/grafana/provisioning/dashboards/AGENTS.md)   | Dashboard provider config                                            |
| [`/monitoring/grafana/provisioning/datasources/AGENTS.md`](/monitoring/grafana/provisioning/datasources/AGENTS.md) | Prometheus datasource config                                         |

---

## Reference Documentation

Technical reference materials, API documentation, and design plans.

### API Reference

| Path                                                                                     | Description                                                   |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| [`/docs/api-reference/AGENTS.md`](/docs/api-reference/AGENTS.md)                         | Complete REST API documentation (canonical location)          |
| [`/docs/reference/AGENTS.md`](/docs/reference/AGENTS.md)                                 | Reference documentation root: glossary, stability definitions |
| [`/docs/reference/api/AGENTS.md`](/docs/reference/api/AGENTS.md)                         | API endpoint reference (alternate format)                     |
| [`/docs/reference/config/AGENTS.md`](/docs/reference/config/AGENTS.md)                   | Configuration reference: environment variables, risk levels   |
| [`/docs/reference/troubleshooting/AGENTS.md`](/docs/reference/troubleshooting/AGENTS.md) | Problem-solving guides: AI, network, database, GPU issues     |

### Design Plans

| Path                                             | Description                                                   |
| ------------------------------------------------ | ------------------------------------------------------------- |
| [`/docs/plans/AGENTS.md`](/docs/plans/AGENTS.md) | Design and implementation plans: date-prefixed specifications |

### Benchmarks

| Path                                                       | Description                                         |
| ---------------------------------------------------------- | --------------------------------------------------- |
| [`/docs/benchmarks/AGENTS.md`](/docs/benchmarks/AGENTS.md) | Performance benchmark results: Model Zoo benchmarks |

### Visual Assets

| Path                                               | Description                                   |
| -------------------------------------------------- | --------------------------------------------- |
| [`/docs/images/AGENTS.md`](/docs/images/AGENTS.md) | Visual assets: mockups, screenshots, diagrams |

### User Documentation

| Path                                                       | Description                                                         |
| ---------------------------------------------------------- | ------------------------------------------------------------------- |
| [`/docs/user-hub.md`](/docs/user-hub.md)                   | User documentation hub (end users)                                  |
| [`/docs/user/AGENTS.md`](/docs/user/AGENTS.md)             | User docs: dashboard basics, AI features, system monitoring         |
| [`/docs/user-guide/AGENTS.md`](/docs/user-guide/AGENTS.md) | User guide (original): getting started, alerts, dashboard, timeline |

### Documentation Root

| Path                                 | Description                                                             |
| ------------------------------------ | ----------------------------------------------------------------------- |
| [`/docs/AGENTS.md`](/docs/AGENTS.md) | Documentation directory overview: 18 subdirectories, 34 root-level docs |

---

## Infrastructure and Configuration

Supporting infrastructure, data directories, and configuration.

### Data Directories

| Path                                                 | Description                                           |
| ---------------------------------------------------- | ----------------------------------------------------- |
| [`/data/AGENTS.md`](/data/AGENTS.md)                 | Runtime data directory: logs, thumbnails (gitignored) |
| [`/custom/AGENTS.md`](/custom/AGENTS.md)             | Custom resources: test clips, configurations          |
| [`/custom/clips/AGENTS.md`](/custom/clips/AGENTS.md) | Video clips for testing                               |

### Legacy and Internal

| Path                                     | Description                                                 |
| ---------------------------------------- | ----------------------------------------------------------- |
| [`/.beads/AGENTS.md`](/.beads/AGENTS.md) | Legacy issue tracking data (deprecated, migrated to Linear) |
| [`/.pids/AGENTS.md`](/.pids/AGENTS.md)   | PID files for dev services                                  |
| [`/vsftpd/AGENTS.md`](/vsftpd/AGENTS.md) | vsftpd FTP server container configuration                   |

### Mutation Testing

| Path                                                                                                     | Description                         |
| -------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| [`/mutants/AGENTS.md`](/mutants/AGENTS.md)                                                               | Mutation testing results (mutmut)   |
| [`/mutants/backend/AGENTS.md`](/mutants/backend/AGENTS.md)                                               | Backend mutation testing            |
| [`/mutants/backend/alembic/AGENTS.md`](/mutants/backend/alembic/AGENTS.md)                               | Alembic mutation results            |
| [`/mutants/backend/alembic/versions/AGENTS.md`](/mutants/backend/alembic/versions/AGENTS.md)             | Migration mutation results          |
| [`/mutants/backend/api/AGENTS.md`](/mutants/backend/api/AGENTS.md)                                       | API mutation results                |
| [`/mutants/backend/api/middleware/AGENTS.md`](/mutants/backend/api/middleware/AGENTS.md)                 | Middleware mutation results         |
| [`/mutants/backend/api/routes/AGENTS.md`](/mutants/backend/api/routes/AGENTS.md)                         | Routes mutation results             |
| [`/mutants/backend/api/schemas/AGENTS.md`](/mutants/backend/api/schemas/AGENTS.md)                       | Schema mutation results             |
| [`/mutants/backend/core/AGENTS.md`](/mutants/backend/core/AGENTS.md)                                     | Core mutation results               |
| [`/mutants/backend/core/middleware/AGENTS.md`](/mutants/backend/core/middleware/AGENTS.md)               | Core middleware mutation results    |
| [`/mutants/backend/data/AGENTS.md`](/mutants/backend/data/AGENTS.md)                                     | Data mutation results               |
| [`/mutants/backend/data/cameras/AGENTS.md`](/mutants/backend/data/cameras/AGENTS.md)                     | Camera data mutation results        |
| [`/mutants/backend/examples/AGENTS.md`](/mutants/backend/examples/AGENTS.md)                             | Examples mutation results           |
| [`/mutants/backend/models/AGENTS.md`](/mutants/backend/models/AGENTS.md)                                 | Model mutation results              |
| [`/mutants/backend/scripts/AGENTS.md`](/mutants/backend/scripts/AGENTS.md)                               | Scripts mutation results            |
| [`/mutants/backend/services/AGENTS.md`](/mutants/backend/services/AGENTS.md)                             | Services mutation results           |
| [`/mutants/backend/tests/AGENTS.md`](/mutants/backend/tests/AGENTS.md)                                   | Tests mutation results              |
| [`/mutants/backend/tests/benchmarks/AGENTS.md`](/mutants/backend/tests/benchmarks/AGENTS.md)             | Benchmark mutation results          |
| [`/mutants/backend/tests/chaos/AGENTS.md`](/mutants/backend/tests/chaos/AGENTS.md)                       | Chaos tests mutation results        |
| [`/mutants/backend/tests/contracts/AGENTS.md`](/mutants/backend/tests/contracts/AGENTS.md)               | Contract tests mutation results     |
| [`/mutants/backend/tests/e2e/AGENTS.md`](/mutants/backend/tests/e2e/AGENTS.md)                           | E2E tests mutation results          |
| [`/mutants/backend/tests/fixtures/AGENTS.md`](/mutants/backend/tests/fixtures/AGENTS.md)                 | Fixtures mutation results           |
| [`/mutants/backend/tests/gpu/AGENTS.md`](/mutants/backend/tests/gpu/AGENTS.md)                           | GPU tests mutation results          |
| [`/mutants/backend/tests/integration/AGENTS.md`](/mutants/backend/tests/integration/AGENTS.md)           | Integration tests mutation results  |
| [`/mutants/backend/tests/unit/AGENTS.md`](/mutants/backend/tests/unit/AGENTS.md)                         | Unit tests mutation results         |
| [`/mutants/backend/tests/unit/api/AGENTS.md`](/mutants/backend/tests/unit/api/AGENTS.md)                 | API unit tests mutation results     |
| [`/mutants/backend/tests/unit/api/routes/AGENTS.md`](/mutants/backend/tests/unit/api/routes/AGENTS.md)   | Routes unit tests mutation results  |
| [`/mutants/backend/tests/unit/api/schemas/AGENTS.md`](/mutants/backend/tests/unit/api/schemas/AGENTS.md) | Schema unit tests mutation results  |
| [`/mutants/backend/tests/unit/core/AGENTS.md`](/mutants/backend/tests/unit/core/AGENTS.md)               | Core unit tests mutation results    |
| [`/mutants/backend/tests/unit/models/AGENTS.md`](/mutants/backend/tests/unit/models/AGENTS.md)           | Model unit tests mutation results   |
| [`/mutants/backend/tests/unit/routes/AGENTS.md`](/mutants/backend/tests/unit/routes/AGENTS.md)           | Routes unit tests mutation results  |
| [`/mutants/backend/tests/unit/scripts/AGENTS.md`](/mutants/backend/tests/unit/scripts/AGENTS.md)         | Script unit tests mutation results  |
| [`/mutants/backend/tests/unit/services/AGENTS.md`](/mutants/backend/tests/unit/services/AGENTS.md)       | Service unit tests mutation results |
| [`/mutants/tests/AGENTS.md`](/mutants/tests/AGENTS.md)                                                   | Root tests mutation results         |
| [`/mutants/tests/load/AGENTS.md`](/mutants/tests/load/AGENTS.md)                                         | Load tests mutation results         |

---

## Quick Reference

### Finding Documentation by Topic

| Topic                 | Primary AGENTS.md                    |
| --------------------- | ------------------------------------ |
| Project overview      | `/AGENTS.md`                         |
| Detailed instructions | `/CLAUDE.md`                         |
| Backend architecture  | `/backend/AGENTS.md`                 |
| Frontend architecture | `/frontend/AGENTS.md`                |
| AI services           | `/ai/AGENTS.md`                      |
| API endpoints         | `/backend/api/routes/AGENTS.md`      |
| Database models       | `/backend/models/AGENTS.md`          |
| React components      | `/frontend/src/components/AGENTS.md` |
| Testing               | `/backend/tests/AGENTS.md`           |
| CI/CD                 | `/.github/workflows/AGENTS.md`       |
| Monitoring            | `/monitoring/AGENTS.md`              |
| Deployment            | `/docs/operator/AGENTS.md`           |
| Scripts               | `/scripts/AGENTS.md`                 |

### Statistics

| Category              | Count |
| --------------------- | ----- |
| Total AGENTS.md files | 188   |
| Backend               | 66    |
| Frontend              | 42    |
| Documentation         | 22    |
| Tests                 | 40    |
| AI Pipeline           | 6     |
| Monitoring            | 6     |
| GitHub/CI             | 6     |

---

## Contributing to AGENTS.md Files

When adding new directories or significantly changing existing ones:

1. Create or update the AGENTS.md file in that directory
2. Follow the standard structure (Purpose, Directory Structure, Key Files, Patterns, Entry Points)
3. Link to parent and child AGENTS.md files
4. Update this index if adding new top-level directories

**Template:**

```markdown
# [Directory Name] - Agent Guide

## Purpose

Brief description of what this directory contains.

## Directory Structure

\`\`\`
directory/
file1.py # Description
subdirectory/ # Description
\`\`\`

## Key Files

| File       | Description  |
| ---------- | ------------ |
| `file1.py` | What it does |

## Important Patterns

- Pattern 1
- Pattern 2

## Entry Points

- For task X, start with `file1.py`
- For task Y, see `subdirectory/AGENTS.md`

## Related Documentation

- Parent: `/parent/AGENTS.md`
- Related: `/related/AGENTS.md`
```
