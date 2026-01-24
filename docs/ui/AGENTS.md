# UI Documentation - Agent Guide

## Purpose

Page-specific documentation for the Nemotron Home Security dashboard. Each file documents what users see on a specific page, including key components, settings, and troubleshooting.

## Directory Contents

```
ui/
  AGENTS.md              # This file
  README.md              # UI documentation hub
  ai-audit.md            # AI Audit page
  ai-performance.md      # AI Performance page
  alerts.md              # Alerts page
  analytics.md           # Analytics page
  audit-log.md           # Audit Log page
  dashboard.md           # Dashboard page
  entities.md            # Entities page
  interface-guide.md     # Interface usability guide
  jobs.md                # Background Jobs page
  keyboard-shortcuts.md  # Keyboard shortcuts reference
  logs.md                # Application Logs page
  mobile-pwa.md          # Mobile and PWA guide
  operations.md          # System Monitoring page
  settings.md            # Settings page
  timeline.md            # Event Timeline page
  trash.md               # Trash/Deleted Events page
  zones.md               # Detection Zones page
```

## Quick Navigation

| File                | Page                 | Frontend Component                                        |
| ------------------- | -------------------- | --------------------------------------------------------- |
| `dashboard.md`      | Main Dashboard       | `frontend/src/components/dashboard/DashboardPage.tsx`     |
| `timeline.md`       | Event Timeline       | `frontend/src/components/events/EventTimeline.tsx`        |
| `entities.md`       | Entities             | `frontend/src/components/entities/EntitiesPage.tsx`       |
| `alerts.md`         | Alerts               | `frontend/src/components/alerts/AlertsPage.tsx`           |
| `zones.md`          | Detection Zones      | `frontend/src/components/zones/ZoneEditor.tsx`            |
| `audit-log.md`      | Audit Log            | `frontend/src/components/audit/AuditLogPage.tsx`          |
| `analytics.md`      | Analytics            | `frontend/src/components/analytics/AnalyticsPage.tsx`     |
| `jobs.md`           | Background Jobs      | `frontend/src/components/jobs/JobsPage.tsx`               |
| `ai-audit.md`       | AI Audit             | `frontend/src/components/ai/AIAuditPage.tsx`              |
| `ai-performance.md` | AI Performance       | `frontend/src/components/ai/AIPerformancePage.tsx`        |
| `operations.md`     | System Monitoring    | `frontend/src/components/system/SystemMonitoringPage.tsx` |
| `trash.md`          | Trash/Deleted Events | `frontend/src/pages/TrashPage.tsx`                        |
| `logs.md`           | Application Logs     | `frontend/src/components/logs/LogsPage.tsx`               |
| `settings.md`       | Settings             | `frontend/src/components/settings/SettingsPage.tsx`       |

## Usability Guides

| File                    | Purpose                                            |
| ----------------------- | -------------------------------------------------- |
| `interface-guide.md`    | Visual feedback, loading indicators, toasts        |
| `keyboard-shortcuts.md` | Command palette, navigation, accessibility         |
| `mobile-pwa.md`         | Mobile responsive, PWA install, push notifications |

## Document Structure

Each page doc follows this template:

```markdown
# Page Name

What this page is and who it's for.

## What You're Looking At

Plain language overview for end users.

## Key Components

- Component 1: Description
- Component 2: Description

## Settings & Configuration

Configurable options on this page.

## Troubleshooting

Common issues and solutions.

## Technical Deep Dive

Related code and architecture docs:

- Component paths
- API endpoints
- Architecture references
```

## Related Resources

- **User hub**: `../user/README.md`
- **Getting started tour**: `../getting-started/tour.md`
- **Frontend AGENTS.md**: `../../frontend/AGENTS.md`
- **Screenshot guide**: `../images/SCREENSHOT_GUIDE.md`
