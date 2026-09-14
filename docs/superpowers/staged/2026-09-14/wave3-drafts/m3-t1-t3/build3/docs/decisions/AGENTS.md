# Decisions Directory - Agent Guide

## Purpose

This directory contains Architecture Decision Records (ADRs) that document significant technical decisions made during the project. ADRs capture the context, options evaluated, and rationale behind important architectural choices.

## Directory Contents

```
decisions/
├── AGENTS.md                                    # This file
├── README.md                                    # Decisions overview and index
├── 2026-01-12-docs-reorganization-design.md     # Documentation reorganization design ADR
└── grafana-integration.md                       # Grafana integration strategy decision
```

## Current Decisions

### 2026-01-12-docs-reorganization-design.md

**Date:** 2026-01-12
**Status:** Decided

**Decision Summary:**

Design specification for reorganizing documentation into a hub-and-spoke architecture with role-based entry points.

### grafana-integration.md

**Date:** 2025-12-27
**Status:** Decided
**Related Beads:** 6fj, c3s

**Decision Summary:**

1. Use native Tremor charts for dashboard metrics visualization (not Grafana embeds)
2. Link to standalone Grafana at `localhost:3002` for detailed metrics exploration

**Context:**

- Project is a local single-user deployment for home security monitoring
- Needed to decide how to display system metrics
- Evaluated embedding Grafana vs using native charts

**Options Evaluated:**

| Option                   | Description                            | Outcome                                                |
| ------------------------ | -------------------------------------- | ------------------------------------------------------ |
| Grafana iframe embed     | Embed Grafana panels in dashboard      | Rejected - auth complexity, CSP/X-Frame-Options issues |
| Grafana public snapshots | Use shareable dashboards               | Rejected - overkill for local use                      |
| Pull Grafana images      | Server-side rendered images            | Rejected - stale data, polling overhead                |
| **Native Tremor charts** | Use Tremor components with backend API | **Selected** - simple, no auth, real-time              |

**Key Rationale:**

- No additional auth complexity for single-user local deployment
- No CSP/iframe issues
- Tremor already in frontend stack
- Backend already exposes metrics endpoints
- Simpler deployment

## ADR Format

All ADRs in this directory follow this structure:

```markdown
# Decision: [Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Decided | Deprecated | Superseded
**Related Beads:** [task IDs]

## Context

[Why this decision needed to be made]

## Decision Summary

[Brief summary of what was decided]

## Options Evaluated

[Table or list of options considered]

## Rationale

[Why the selected option was chosen]

## Implementation Notes

[How to implement the decision]

## Consequences

[Positive, negative, and neutral outcomes]

## References

[Links to relevant documentation]
```

## When to Create an ADR

Create an ADR when:

- Making a significant architectural choice that affects multiple components
- Choosing between multiple viable technical approaches
- Making a decision that future developers will question
- Reverting or changing a previous architectural decision

Do NOT create an ADR for:

- Implementation details that don't affect architecture
- Bug fixes
- Routine feature additions
- Coding style decisions (covered by linters)

## Using ADRs

### For New Developers

1. Read existing ADRs to understand why the system is built this way
2. Refer to ADRs when questioning architectural choices
3. Propose new ADRs for significant changes

### For Existing Developers

1. Create ADRs before implementing major architectural changes
2. Reference ADRs in code comments and PRs
3. Update ADR status when decisions are superseded

## Naming Convention

- Lowercase with hyphens: `decision-name.md`
- No date prefix (date is in the document header)
- Be descriptive: `grafana-integration.md` not `adr-001.md`

## Related Documentation

- **docs/AGENTS.md:** Documentation directory guide
- **docs/plans/:** Design specifications that inform decisions
- **CLAUDE.md:** Claude Code instructions
