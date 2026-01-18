# Design Documents and Implementation Plans

> Index of brainstorming sessions, design specifications, and implementation plans for the Home Security Intelligence project.

Plans are working documents that capture design thinking before implementation. They differ from ADRs (Architecture Decision Records) in that they focus on "how to build it" rather than "why we chose this approach."

---

## Current Plans

### Design Specifications

| Plan                                                                           | Date       | Description                                                               |
| ------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------- |
| [Grafana AI Audit Panels Design](2026-01-17-grafana-ai-audit-panels-design.md) | 2026-01-17 | Embed Grafana dashboard into AI Performance page with new AI audit panels |
| [Contextual Docs Link Design](2026-01-18-contextual-docs-link-design.md)       | 2026-01-18 | Dynamic documentation link in header based on current page                |
| [Docs Drift Detection Design](2026-01-18-docs-drift-detection-design.md)       | 2026-01-18 | CI/CD pipeline to detect when code changes require documentation updates  |

### Implementation Plans

| Plan                                                                                     | Date       | Description                                                                |
| ---------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------- |
| [Contextual Docs Link Implementation](2026-01-18-contextual-docs-link-implementation.md) | 2026-01-18 | Step-by-step implementation plan for contextual documentation link feature |

### Audit Reports

| Plan                                                                         | Date       | Description                                            |
| ---------------------------------------------------------------------------- | ---------- | ------------------------------------------------------ |
| [UI Comprehensive Testing Plan](2026-01-13-ui-comprehensive-testing-plan.md) | 2026-01-13 | Browser automation testing plan for all 12 UI pages    |
| [Backend-Frontend Gap Analysis](2026-01-17-backend-frontend-gap-analysis.md) | 2026-01-17 | Analysis of backend endpoints not consumed by frontend |

---

## Plan Types

### Design Specifications

High-level designs created during brainstorming sessions. Capture requirements, goals, non-goals, and proposed architecture before implementation begins.

### Implementation Plans

Detailed task-by-task breakdowns for Claude agents to execute. Include code snippets, file paths, and explicit steps for TDD workflows.

### Audit Reports

Analysis documents that identify gaps, issues, or improvement opportunities in the codebase.

---

## Creating a New Plan

1. **Naming convention:** `YYYY-MM-DD-plan-name.md`
2. **Include these sections:**
   - Summary/Goal
   - Background/Context
   - Design or Methodology
   - Tasks/Implementation Steps
3. **For implementation plans:** Add the agent directive at the top:
   ```markdown
   > **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
   ```

---

## Workflow

1. **Brainstorm** - Create a design spec during brainstorming sessions
2. **Review** - Get feedback and approval on the design
3. **Implement** - Convert approved designs into implementation plans
4. **Execute** - Agents implement using `superpowers:executing-plans`
5. **Archive** - Completed plans remain as historical reference

---

## Related Documentation

- [Architecture Decisions](../decisions/) - ADRs documenting "why" decisions
- [Developer Hub](../developer/) - Developer documentation index
- [ROADMAP.md](../ROADMAP.md) - Post-MVP feature roadmap

---

[Back to Documentation Index](../README.md)
