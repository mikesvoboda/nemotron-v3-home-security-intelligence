# Architecture Decision Records

> Index of significant architectural and design decisions for the Home Security Intelligence project.

Architecture Decision Records (ADRs) capture the context, options evaluated, and rationale behind important technical choices. They serve as documentation for future developers wondering "why was it built this way?"

---

## Current Decisions

| Decision                                                                            | Date       | Status      | Summary                                                               |
| ----------------------------------------------------------------------------------- | ---------- | ----------- | --------------------------------------------------------------------- |
| [Documentation Reorganization](2026-01-12-docs-reorganization-design.md)            | 2026-01-12 | Approved    | Hub-and-spoke documentation architecture with role-based entry points |
| [Grafana Integration](grafana-integration.md)                                       | 2025-12-27 | Decided     | Use native Tremor charts with link to standalone Grafana              |
| [Entity-Detection Referential Integrity](entity-detection-referential-integrity.md) | -          | Placeholder | Database constraints between entities and detections                  |

---

## When to Create an ADR

Create an ADR when:

- Making a significant architectural choice affecting multiple components
- Choosing between multiple viable technical approaches
- Making a decision that future developers will question
- Reverting or changing a previous architectural decision

Do NOT create an ADR for:

- Implementation details that don't affect architecture
- Bug fixes or routine feature additions
- Coding style decisions (covered by linters)

---

## ADR Format

ADRs follow this standard structure:

```markdown
# Decision: [Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Decided | Deprecated | Superseded

## Context

[Why this decision needed to be made]

## Decision Summary

[Brief summary of what was decided]

## Options Evaluated

[Table or list of options considered]

## Rationale

[Why the selected option was chosen]

## Consequences

[Positive, negative, and neutral outcomes]
```

---

## Creating a New ADR

1. Copy the template above
2. Use descriptive filename: `decision-name.md` (not `adr-001.md`)
3. Document the context and options evaluated
4. Get team buy-in before marking as "Decided"
5. Update this README with the new entry

---

## Related Documentation

- [AGENTS.md](AGENTS.md) - Agent guide for this directory
- [Design Plans](../plans/) - Brainstorming and implementation plans
- [Developer Hub](../developer/) - Developer documentation index

---

[Back to Documentation Index](../README.md)
