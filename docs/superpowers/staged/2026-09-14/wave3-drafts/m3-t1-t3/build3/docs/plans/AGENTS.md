# Plans Directory - Agent Guide

## Purpose

This directory contains design documents and implementation plans for the Home Security Intelligence project. Plans capture design thinking before implementation and differ from ADRs (Architecture Decision Records) in that they focus on "how to build it" rather than "why we chose this approach."

## Directory Contents

```
plans/
  AGENTS.md                                              # This file
  README.md                                              # Plans overview and index
  2026-01-13-ui-comprehensive-testing-plan.md            # UI testing audit plan
  2026-01-17-backend-frontend-gap-analysis.md            # Backend/frontend gap analysis
  2026-01-17-grafana-ai-audit-panels-design.md           # Grafana AI audit panels design
  2026-01-18-contextual-docs-link-design.md              # Contextual docs link design
  2026-01-18-contextual-docs-link-implementation.md      # Contextual docs link implementation
  2026-01-18-dashboard-summaries-design.md               # Dashboard summaries design
  2026-01-18-docs-drift-detection-design.md              # Docs drift detection design
  2026-01-19-model-zoo-prompt-improvements-design.md     # Model zoo prompt improvements
  2026-01-19-nemotron-prompt-improvements-design.md      # Nemotron prompt improvements
  2026-01-20-distributed-tracing-page-design.md          # Distributed tracing page design
  2026-01-20-loki-pyroscope-alloy-design.md              # Loki, Pyroscope, Alloy design
  2026-01-20-orphaned-infrastructure-integration-design.md # Orphaned infrastructure integration
  2026-01-20-tracing-dashboard-design.md                 # Tracing dashboard design
```

## Plan Types

| Type                      | Purpose                                                  |
| ------------------------- | -------------------------------------------------------- |
| **Design Specifications** | High-level designs from brainstorming sessions           |
| **Implementation Plans**  | Detailed task-by-task breakdowns for agent execution     |
| **Audit Reports**         | Analysis documents identifying gaps or improvement areas |

## Key Plans

### Design Specifications

| Plan                                                       | Description                                         |
| ---------------------------------------------------------- | --------------------------------------------------- |
| `2026-01-17-grafana-ai-audit-panels-design.md`             | Embed Grafana dashboard into AI Performance page    |
| `2026-01-18-contextual-docs-link-design.md`                | Dynamic documentation link based on current page    |
| `2026-01-18-dashboard-summaries-design.md`                 | Dashboard summary components design                 |
| `2026-01-18-docs-drift-detection-design.md`                | CI/CD pipeline for documentation drift detection    |
| `2026-01-19-model-zoo-prompt-improvements-design.md`       | Model Zoo prompt optimization design                |
| `2026-01-19-nemotron-prompt-improvements-design.md`        | Nemotron LLM prompt improvements                    |
| `2026-01-20-distributed-tracing-page-design.md`            | Distributed tracing UI page design                  |
| `2026-01-20-loki-pyroscope-alloy-design.md`                | Observability stack design (Loki, Pyroscope, Alloy) |
| `2026-01-20-orphaned-infrastructure-integration-design.md` | Integration of orphaned infrastructure components   |
| `2026-01-20-tracing-dashboard-design.md`                   | Tracing dashboard design                            |

### Implementation Plans

| Plan                                                | Description                                          |
| --------------------------------------------------- | ---------------------------------------------------- |
| `2026-01-18-contextual-docs-link-implementation.md` | Step-by-step implementation for contextual docs link |

### Audit Reports

| Plan                                          | Description                                      |
| --------------------------------------------- | ------------------------------------------------ |
| `2026-01-13-ui-comprehensive-testing-plan.md` | Browser automation testing plan for all UI pages |
| `2026-01-17-backend-frontend-gap-analysis.md` | Backend endpoints not consumed by frontend       |

## Naming Convention

Plans follow the format: `YYYY-MM-DD-plan-name.md`

## Using Plans for Implementation

For implementation plans, agents should use the `superpowers:executing-plans` skill:

```markdown
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
```

## Creating New Plans

1. Create file with date prefix: `YYYY-MM-DD-plan-name.md`
2. Include sections:
   - Summary/Goal
   - Background/Context
   - Design or Methodology
   - Tasks/Implementation Steps
3. Add agent directive for implementation plans
4. Update `README.md` with new plan entry

## Related Documentation

- **docs/decisions/** - ADRs documenting "why" decisions were made
- **docs/developer/** - Developer documentation index
- **docs/ROADMAP.md** - Post-MVP feature roadmap
- **docs/AGENTS.md** - Documentation root navigation
