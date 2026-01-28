# User Documentation Hub - Agent Guide

## Purpose

This directory is the **end-user documentation hub** for the Home Security Intelligence dashboard. It provides a curated entry point for non-technical users who want to understand and operate the security system on a day-to-day basis.

> **Documentation Organization**
>
> This directory (`docs/user/`) serves as the **navigation hub** with `README.md` providing structured pathways through user documentation. User documentation has been organized across several directories:
>
> - `docs/getting-started/` - Installation, first run, quick start, and product tour guides
> - `docs/ui/` - UI-specific documentation and usability guides
> - `docs/reference/` - Reference documentation including accessibility
>
> **Relationship with docs/getting-started/:**
>
> - `docs/getting-started/` covers **installation and initial setup** (one-time tasks)
> - `docs/user/` covers **ongoing usage** (day-to-day operations)
> - Both link to shared end-user content in `docs/ui/` to avoid duplication
> - The quick-start and tour guides in getting-started are also referenced from the user hub

## Directory Contents

```
user/
  AGENTS.md   # This file - AI navigation for user docs hub
  README.md   # Main user guide hub with learning paths and links
```

| File        | Purpose                                           |
| ----------- | ------------------------------------------------- |
| `AGENTS.md` | This file - AI navigation for user docs hub       |
| `README.md` | Main user guide hub with learning paths and links |

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

| Resource                                     | Description                                            | Audience         |
| -------------------------------------------- | ------------------------------------------------------ | ---------------- |
| [docs/getting-started/](../getting-started/) | Installation, first run, quick start, and product tour | All users        |
| [docs/ui/](../ui/)                           | UI documentation and usability guides                  | End users        |
| [docs/reference/](../reference/)             | Reference docs including accessibility                 | All users        |
| [docs/operator/](../operator/)               | System administration and deployment                   | Operators/admins |
| [docs/developer/](../developer/)             | Contributing, testing, and architecture                | Developers       |

### Content Ownership

To avoid duplication, content is organized as follows:

| Content Type                | Canonical Location      | Reason                                  |
| --------------------------- | ----------------------- | --------------------------------------- |
| Installation/prerequisites  | `docs/getting-started/` | One-time setup tasks                    |
| Quick start/product tour    | `docs/getting-started/` | First-time user onboarding              |
| Dashboard/UI feature guides | `docs/ui/`              | Detailed feature documentation          |
| Navigation hub for users    | `docs/user/README.md`   | Entry point linking to all user content |
| Reference material          | `docs/reference/`       | Standalone reference docs               |

## Entry Points for Agents

### Updating User Documentation

1. For new features: Update `README.md` navigation and add guide to appropriate location:
   - Getting started content -> `docs/getting-started/`
   - UI/dashboard guides -> `docs/ui/`
   - Reference docs -> `docs/reference/`
2. For UI changes: Update screenshots in `docs/images/` and corresponding guide descriptions
3. Maintain non-technical language throughout

### Finding User Documentation

- **Hub navigation:** Start with `README.md` in this directory
- **Getting started:** See `docs/getting-started/` for quick start and tour guides
- **UI guides:** See `docs/ui/` for comprehensive UI feature documentation
- **Reference:** See `docs/reference/` for accessibility and other reference docs

### Cross-References

The README.md links to guides using relative paths:

```markdown
[Quick Start](../getting-started/quick-start.md) -> docs/getting-started/quick-start.md
[Dashboard](../ui/dashboard.md) -> docs/ui/dashboard.md
[Understanding Alerts](../ui/understanding-alerts.md) -> docs/ui/understanding-alerts.md
```
