# User Documentation Directory - Agent Guide

## Purpose

This directory contains end-user documentation using the hub-and-spoke architecture. These guides are written for non-technical users who want to understand and operate the security dashboard. The central hub is [user-hub.md](../user-hub.md).

## Directory Contents

```
user/
  AGENTS.md              # This file
  ai-audit.md            # AI audit trail viewer guide
  ai-enrichment.md       # AI enrichment features guide
  ai-performance.md      # AI performance monitoring guide
  dashboard-basics.md    # Dashboard layout and components
  dashboard-settings.md  # Settings configuration
  system-monitoring.md   # System monitoring page guide
  understanding-alerts.md # Risk levels and responses
  viewing-events.md      # Event viewing and interaction
```

## Key Files

### dashboard-basics.md

**Purpose:** Introduction to the main dashboard layout and components.

**Topics Covered:**

- Dashboard layout overview
- Risk gauge interpretation
- Camera grid navigation
- Live activity feed
- Quick actions and shortcuts

**When to use:** First-time orientation, understanding UI elements.

### understanding-alerts.md

**Purpose:** Explains risk scoring and how to interpret alerts.

**Topics Covered:**

- Risk score scale (0-100)
- Risk levels (low, medium, high, critical)
- Color coding (green, yellow, orange, red)
- What factors affect risk scores
- When to take action vs ignore
- Examples of different alert types

**When to use:** Understanding why an alert was triggered, learning to prioritize alerts.

### viewing-events.md

**Purpose:** Guide to viewing and interacting with security events.

**Topics Covered:**

- Event timeline navigation
- Event filtering and sorting
- Event detail view
- Image and detection viewing
- Event acknowledgment

**When to use:** Reviewing events, investigating incidents.

### dashboard-settings.md

**Purpose:** Guide to configuring dashboard settings.

**Topics Covered:**

- General settings
- Display preferences
- Notification settings
- User preferences

**When to use:** Customizing the dashboard experience.

### system-monitoring.md

**Purpose:** Comprehensive guide to the System monitoring page.

**Topics Covered:**

- System health overview
- Pipeline visualization
- Service status indicators
- GPU monitoring
- Queue depths and latencies
- Troubleshooting from the UI

**When to use:** Monitoring system health, understanding performance.

### ai-audit.md

**Purpose:** Guide to the AI audit trail viewer.

**Topics Covered:**

- Viewing AI decisions
- Understanding AI reasoning
- Audit log filtering
- Transparency and explainability

**When to use:** Understanding why AI made specific decisions.

### ai-enrichment.md

**Purpose:** Guide to AI enrichment features.

**Topics Covered:**

- What enrichment adds to prompts
- Vision extraction results
- Enrichment statistics
- Configuring enrichment

**When to use:** Understanding how AI context is enhanced.

### ai-performance.md

**Purpose:** Guide to AI performance monitoring.

**Topics Covered:**

- Inference latency metrics
- Model performance
- Throughput statistics
- Performance optimization tips

**When to use:** Monitoring and optimizing AI performance.

## Hub-and-Spoke Architecture

This directory follows a hub-and-spoke pattern:

```
user-hub.md (Hub)
    |
    +-- user/dashboard-basics.md
    +-- user/understanding-alerts.md
    +-- user/viewing-events.md
    +-- user/dashboard-settings.md
    +-- user/system-monitoring.md
    +-- user/ai-audit.md
    +-- user/ai-enrichment.md
    +-- user/ai-performance.md
```

The hub (`user-hub.md`) provides navigation and overview, while spoke documents provide detailed content.

## Document Template

All spoke documents should follow this structure:

```markdown
# [Topic Title]

> One-sentence summary.

**Time to read:** ~X min
**Prerequisites:** [Link] or "None"

---

[Content sections]

---

## Next Steps

- [Related Doc](../user-hub.md)

---

[Back to User Hub](../user-hub.md)
```

## Writing Style Guidelines

### Tone

- **Friendly and reassuring** - Security systems can feel invasive; emphasize protection
- **Non-technical** - Avoid jargon; explain concepts simply
- **Action-oriented** - Tell users what to do, not just what exists

### Structure

- **Short paragraphs** - 2-3 sentences maximum
- **Tables for reference** - Easy scanning of information
- **Numbered steps** - Clear procedural guidance
- **Callouts for tips** - Use blockquotes for helpful hints

## Target Audience

| Audience           | Needs                                  | Primary Documents       |
| ------------------ | -------------------------------------- | ----------------------- |
| **New Users**      | Quick orientation, basic understanding | dashboard-basics.md     |
| **Daily Users**    | Alert interpretation, event review     | understanding-alerts.md |
| **Power Users**    | Advanced features, AI insights         | ai-performance.md       |
| **Family Members** | Simple overview                        | dashboard-basics.md     |

## Comparison with user-guide/

This project has two user documentation directories:

| Directory     | Style                          | Navigation           |
| ------------- | ------------------------------ | -------------------- |
| `user/`       | Hub-and-spoke, standardized    | Via user-hub.md      |
| `user-guide/` | Standalone, comprehensive docs | Direct links between |

Choose one approach consistently. The `user/` directory integrates with the documentation hub system.

## Related Documentation

- **docs/user-hub.md:** Central hub for user documentation
- **docs/user-guide/:** Alternative standalone user documentation
- **docs/AGENTS.md:** Documentation directory overview
- **frontend/src/components/:** React components implementing described UI
