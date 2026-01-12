# User Documentation Hub - Agent Guide

## Purpose

This directory is the **end-user documentation hub** for the Home Security Intelligence dashboard. It provides a curated entry point for non-technical users who want to understand and operate the security system.

> **Relationship with docs/user-guide/**
>
> This directory (`docs/user/`) serves as the **navigation hub** with `README.md` providing structured pathways through user documentation. The detailed user guides live in `docs/user-guide/` which contains comprehensive documentation for each feature.

## Directory Contents

| File        | Purpose                                           |
| ----------- | ------------------------------------------------- |
| `AGENTS.md` | This file - AI navigation for user docs hub       |
| `README.md` | Main user guide hub with learning paths and links |
| `images/`   | Screenshots and visual assets for user guides     |

## Key File

### README.md

**Purpose:** Primary entry point for end users seeking documentation.

**Target Audience:** Homeowners, family members, and non-technical users.

**Sections:**

| Section                  | Description                                  |
| ------------------------ | -------------------------------------------- |
| Getting Started          | 4-step learning path for new users           |
| Dashboard Features       | Core dashboard, events, customization guides |
| Alerts and Notifications | Risk levels and notification configuration   |
| Mobile and Accessibility | PWA, keyboard shortcuts, accessibility       |
| Advanced Features        | AI enrichment, audit dashboard, monitoring   |
| Quick Help               | Common troubleshooting and emergency info    |

**Learning Paths:**

1. **New User Path:** Getting Started -> Product Tour -> Dashboard Overview -> Understanding Alerts
2. **Daily User Path:** Understanding Alerts -> Viewing Events -> Alerts and Notifications
3. **Power User Path:** Dashboard Customization -> Event Investigation -> System Monitoring

## Related Resources

| Resource                                             | Description                              |
| ---------------------------------------------------- | ---------------------------------------- |
| [docs/user-guide/](../user-guide/)                   | Detailed user documentation (26+ guides) |
| [docs/user-guide/AGENTS.md](../user-guide/AGENTS.md) | Agent guide for detailed user docs       |
| [docs/operator/](../operator/)                       | System administration guides             |
| [docs/developer/](../developer/)                     | Developer documentation                  |

## Entry Points for Agents

### Updating User Documentation

1. For new features: Update `README.md` navigation and add detailed guide to `docs/user-guide/`
2. For UI changes: Update screenshots in `images/` and corresponding guide descriptions
3. Maintain non-technical language throughout

### Finding User Documentation

- **Hub navigation:** Start with `README.md` in this directory
- **Detailed guides:** See `docs/user-guide/` for comprehensive feature documentation
- **Writing guidelines:** See `docs/user-guide/AGENTS.md` for tone and style conventions

### Cross-References

The README.md links to guides in `docs/user-guide/` using relative paths:

```markdown
[Getting Started](getting-started.md) -> docs/user-guide/getting-started.md
[Dashboard Overview](dashboard-overview.md) -> docs/user-guide/dashboard-overview.md
[Understanding Alerts](understanding-alerts.md) -> docs/user-guide/understanding-alerts.md
```
