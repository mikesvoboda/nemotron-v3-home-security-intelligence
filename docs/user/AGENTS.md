# User Documentation Directory - Agent Guide

## Purpose

This directory contains end-user documentation for the Home Security Intelligence dashboard. These guides are written for non-technical users who want to understand and operate the security monitoring system.

> **Note: Two Documentation Structures Exist**
>
> This project has two user documentation directories:
>
> - `docs/user-guide/` = Comprehensive standalone documentation with detailed guides
> - `docs/user/` (this directory) = Hub-and-spoke structure with standardized shorter templates linked from `user-hub.md`
>
> **Choose one approach, not both.** The `user/` docs use a consistent template and integrate with the User Hub (`user-hub.md`), while `user-guide/` docs are more comprehensive and standalone. Pick the structure that best fits your documentation needs.

## Directory Contents

```
user/
  AGENTS.md                  # This file
  ai-audit.md                # AI Audit Dashboard and quality metrics
  ai-enrichment.md           # AI enrichment data in event details
  ai-performance.md          # AI Performance page and clickable risk distribution
  dashboard-basics.md        # Main dashboard layout and components
  dashboard-settings.md      # Settings configuration
  system-monitoring.md       # System Monitoring with pipeline visualization and infrastructure grid
  understanding-alerts.md    # Risk levels and how to respond
  viewing-events.md          # Event timeline, live feed, and details
```

## Key Files

### ai-audit.md

**Purpose:** Understanding the AI Audit Dashboard and quality metrics.

**Read Time:** ~8 minutes

**Prerequisites:** dashboard-basics.md, ai-enrichment.md

**Topics Covered:**

- AI Audit Dashboard overview
- Accessing the dashboard
- Quality score metrics:
  - **Average Quality Score** - AI performance on 1-5 scale
  - **Consistency Rate** - How consistent AI evaluations are
  - **Enrichment Utilization** - Percentage of AI models contributing
  - **Evaluation Coverage** - Percentage of events evaluated
- Prompt improvement recommendations:
  - **Missing Context** - Information needed for better assessments
  - **Unused Data** - Data that was not useful
  - **Model Gaps** - AI models that should have contributed
  - **Format Suggestions** - Prompt structure improvements
  - **Confusing Sections** - Unclear parts of prompts
- Reading recommendation priority and frequency
- Changing the time period (24h to 90 days)
- Triggering batch audits (limit, min risk score, force re-evaluate)
- Refreshing data
- Interpreting results (good performance vs areas for improvement)

**Screenshot Placeholders:** AI Audit Dashboard, quality score cards, recommendations panel, batch audit modal

**When to use:** Monitoring AI quality, reviewing improvement recommendations, triggering re-evaluations.

### ai-enrichment.md

**Purpose:** Understanding the AI enrichment data displayed in Event Details.

### ai-performance.md

**Purpose:** Understanding the AI Performance page, Model Zoo, and interactive features.

**Read Time:** ~15 minutes

**Prerequisites:** dashboard-basics.md

**Topics Covered:**

- AI Performance page overview
- Accessing the page
- Model status cards (RT-DETRv2, Nemotron)
- Latency panel and pipeline health
- Detection class distribution chart
- Risk score distribution chart:
  - **Risk levels** - Low (0-29), Medium (30-59), High (60-84), Critical (85-100)
  - **Clickable bars** - Navigate to Timeline filtered by risk level
  - **Navigation behavior** - URL query parameter filtering
  - **Visual feedback** - Hover tooltips, scale effects, focus rings
  - **Accessibility** - Keyboard navigation, screen reader support
- Summary counts section
- **Model Zoo section (comprehensive):**
  - Summary bar (loaded/unloaded/disabled counts, VRAM usage)
  - Latency chart with model selector dropdown
  - Chart metrics (Avg, P50, P95 latency)
  - Model status cards (name, status, VRAM, last used, category)
  - Status indicators (Loaded, Loading, Unloaded, Disabled, Error)
  - Active vs Disabled models organization
- **Model Zoo categories:**
  - Detection models (License Plate, Face, YOLO World, Damage)
  - Classification models (Violence, Weather, Fashion, Vehicle, Pet)
  - Other models (Segmentation, Pose, Depth, Embedding, OCR, Action)
- **Understanding VRAM:** Budget, loading strategy, automatic management
- **Model Zoo Analytics:** Contribution chart, Model leaderboard
- **Troubleshooting Model Zoo issues:**
  - Error status diagnosis
  - Model not loading issues
  - High latency troubleshooting
  - No data available explanations
- Refresh and auto-update behavior
- Grafana integration

**Screenshot Placeholders:** AI Performance page, risk distribution chart, model status cards, Model Zoo section, latency chart, individual model cards

**When to use:** Monitoring AI performance, investigating events by risk level, understanding system health, troubleshooting Model Zoo models.

**Read Time:** ~8 minutes

**Prerequisites:** viewing-events.md

**Topics Covered:**

- What is AI enrichment (going beyond basic detection)
- Finding enrichment data in Event Detail Modal
- Enrichment data types:
  - **Vehicle Information** - Type, color, damage, commercial status
  - **Person Information** - Clothing, action, carrying, security flags
  - **License Plate Detection** - OCR-extracted plate text
  - **Pet Identification** - Cat/dog classification, breed
  - **Weather Conditions** - Clear, rain, snow, fog
  - **Image Quality Assessment** - Quality score, issues
- Understanding confidence scores (high/medium/low)
- Accordion navigation
- When enrichment data is available
- How enrichment affects risk scores
- Data retention

**Screenshot Placeholders:** AI Enrichment panel, Vehicle/Person/License Plate/Pet sections

**When to use:** Understanding advanced AI analysis for events, interpreting security flags.

### dashboard-basics.md

**Purpose:** Understanding the main security dashboard layout and components.

**Read Time:** ~10 minutes

**Topics Covered:**

- First look at the dashboard
- Dashboard layout overview (ASCII diagram)
- Header bar (logo, live status, GPU stats)
- System health indicator (green/yellow/red)
- Sidebar navigation (Dashboard, Timeline, Entities, Alerts, Logs, System, Settings)
- Quick stats row (Active Cameras, Events Today, Current Risk Score, System Status)
- **Clickable stat cards** - Each card navigates to its detailed view (Settings, Timeline, Alerts, System)
- **Sparkline visualization** - Mini line charts showing risk score trends
- Understanding sparklines (data source, reading patterns, when they appear)
- Risk gauge (0-100 scale, color coding, reading the gauge)
- Camera grid (card contents, status badges, interacting with cameras)
- GPU statistics panel

**Screenshot Placeholders:** Multiple screenshots needed for UI elements

**When to use:** First-time orientation, learning dashboard layout, understanding sparkline trends.

### dashboard-settings.md

**Purpose:** Configure cameras, processing options, and system preferences.

**Read Time:** ~5 minutes

**Topics Covered:**

- Accessing settings (sidebar navigation)
- Settings tabs:
  - **Cameras Tab** - View and manage connected cameras
  - **Processing Tab** - Detection sensitivity, batch window, retention
  - **AI Models Tab** - RT-DETRv2 and Nemotron status, GPU usage
- Quick reference (status indicators, keyboard shortcuts, common actions)
- Basic troubleshooting (dashboard not loading, cameras offline, no events)
- Getting help (technical problems, emergency situations)

**Screenshot Placeholders:** Settings page, camera list, AI models tab

**When to use:** Configuring the system, checking AI status.

### system-monitoring.md

**Purpose:** Understanding the System Monitoring page with pipeline visualization and infrastructure grid.

**Read Time:** ~15 minutes

**Prerequisites:** dashboard-basics.md

**Topics Covered:**

- System Monitoring page overview and layout
- Time range selector (1H, 6H, 24H, 7D)
- Grafana integration banner
- Performance alerts banner
- **System Health Panel:**
  - Statistics grid (Uptime, Cameras, Events, Detections)
  - Service health list with status badges
- **GPU Statistics Panel:**
  - Utilization, memory, temperature, power metrics
  - Historical utilization chart
- **AI Models Panel:**
  - RT-DETRv2 (object detection) status and metrics
  - Nemotron (risk analysis) status and metrics
- **Model Zoo Panel:**
  - Summary bar (loaded/unloaded/disabled, VRAM usage)
  - Model categories and status indicators
- **Pipeline Metrics Panel (new redesign feature):**
  - Understanding the four-stage pipeline flow (Files -> Detect -> Batch -> Analyze)
  - Queue depths row with color-coded badges
  - Latency grid (avg, p95, p99 for each stage)
  - Throughput chart showing processing rates
  - Queue backup warning banner
- **Database Panels:**
  - PostgreSQL metrics (connections, cache hit ratio, transactions)
  - Redis metrics (clients, memory, hit ratio)
- **Background Workers Panel:**
  - Worker status summary and dots
  - Expandable worker details list
- **Containers Panel:**
  - Container status table (name, status, CPU, memory, restarts)
- **Host System Panel:**
  - CPU, Memory, Disk usage progress bars with color thresholds
- **Circuit Breakers Panel:**
  - Circuit states (Closed, Open, Half-Open)
  - Circuit breaker table and reset button
- **Severity Configuration Panel:**
  - Risk level threshold definitions
- Health status color guide
- Common questions and troubleshooting quick reference

**Screenshot Placeholders:** System Monitoring page overview, Pipeline Metrics panel, Infrastructure panels, Circuit Breaker panel

**When to use:** Monitoring system health, understanding pipeline flow, checking infrastructure status, troubleshooting performance issues.

### understanding-alerts.md

**Purpose:** What risk levels mean and how to respond to security events.

**Read Time:** ~8 minutes

**Prerequisites:** dashboard-basics.md

**Topics Covered:**

- Risk scoring overview (factors: what, when, how, where)
- Risk levels with examples:
  - **Low (0-29)** - Green, normal activity
  - **Medium (30-59)** - Yellow, unusual but probably okay
  - **High (60-84)** - Orange, concerning activity
  - **Critical (85-100)** - Red, immediate attention needed
- Alerts page (accessing, filtering, refresh)
- Color guide for quick reference
- Why did I get this alert? (time of day, detection type, behavior, location)
- Common false alarms and causes
- Responding to alerts (by risk level)
- Emergency reminder (system does NOT call 911)

**Screenshot Placeholders:** Risk level color guide, alerts page, alert card examples

**When to use:** Understanding risk scores, responding to alerts appropriately.

### viewing-events.md

**Purpose:** How to view, filter, and interact with security events.

**Read Time:** ~10 minutes

**Prerequisites:** dashboard-basics.md

**Topics Covered:**

- Live Activity Feed (understanding, using, auto-scroll feature)
- Event Timeline page:
  - Filtering (camera, risk level, status, object type, date range)
  - Searching events
  - Results summary
  - Working with events (selecting, exporting)
  - Pagination
- Event Details popup:
  - Header section
  - Detection image with bounding boxes
  - Detection sequence (thumbnails)
  - AI Summary and Reasoning
  - Detected Objects list
  - Notes section
- Navigation within events (keyboard shortcuts)
- Actions (mark reviewed, flag, download, add notes)
- Event lifecycle (camera to review)

**Screenshot Placeholders:** Live activity feed, event timeline, filter controls, event detail modal, detection image

**When to use:** Reviewing security events, investigating incidents.

## Writing Style Guidelines

User documentation follows these conventions:

### Tone

- **Friendly and reassuring** - Security can feel invasive; emphasize protection
- **Non-technical** - Avoid jargon; explain concepts simply
- **Action-oriented** - Tell users what to do, not just what exists

### Structure

- **Short paragraphs** - 2-3 sentences maximum
- **Tables for reference** - Easy scanning of information
- **Numbered steps** - Clear procedural guidance
- **Blockquotes for tips** - Helpful hints stand out

### Visual Elements

- **Screenshot placeholders** - Comment blocks indicating needed screenshots
- **ASCII diagrams** - Simple layout visualizations
- **Color coding references** - Match dashboard color scheme

### Document Template

```markdown
# [Topic Title]

> One-sentence summary.

**Time to read:** ~X min
**Prerequisites:** [Link] or "None"

---

[Content with sections]

---

## Next Steps

- [Related Doc](link.md) - Brief description

---

## See Also

- [Reference Doc](../reference/path.md) - Technical details
- [Glossary](../reference/glossary.md) - Terms

---

[Back to User Hub](../user-hub.md)
```

## Target Audiences

| Audience           | Technical Level | Primary Documents                                                                             |
| ------------------ | --------------- | --------------------------------------------------------------------------------------------- |
| **Homeowners**     | Low             | All files                                                                                     |
| **Family Members** | Low             | dashboard-basics.md                                                                           |
| **Daily Users**    | Low-Medium      | viewing-events.md, understanding-alerts.md                                                    |
| **Power Users**    | Medium          | dashboard-settings.md, ai-audit.md, ai-enrichment.md, ai-performance.md, system-monitoring.md |

## Navigation Path

Recommended reading order for new users:

1. `dashboard-basics.md` - Get oriented with the interface
2. `viewing-events.md` - Learn to review security events
3. `understanding-alerts.md` - Understand risk levels
4. `dashboard-settings.md` - Configure preferences
5. `ai-performance.md` - Monitor AI models and investigate by risk level
6. `system-monitoring.md` - Understand system health and circuit breakers

## Relationship to user-guide/

The `docs/user/` directory contains focused, hub-and-spoke documentation integrated with the User Hub (`user-hub.md`). The `docs/user-guide/` directory contains the original user documentation.

**Key Differences:**

| Aspect              | user/                     | user-guide/             |
| ------------------- | ------------------------- | ----------------------- |
| Navigation          | Hub-and-spoke structure   | Standalone documents    |
| Template            | Standardized with headers | Mixed formats           |
| Cross-references    | Consistent back-links     | Variable                |
| Screenshot approach | Placeholder comments      | Some actual screenshots |

Both directories are maintained for different navigation approaches.

## Related Documentation

- **docs/user-hub.md:** Central user documentation hub
- **docs/user-guide/AGENTS.md:** Original user guide directory
- **docs/reference/config/risk-levels.md:** Technical risk score definitions
- **docs/reference/troubleshooting/index.md:** Problem-solving guides
- **docs/reference/glossary.md:** Terms and definitions
