# User Guide Directory - Agent Guide

## Purpose

This directory contains end-user documentation for the Home Security Intelligence dashboard. These guides are written for non-technical users who want to understand and operate the security system.

> **Consolidated User Documentation**
>
> This directory is the canonical location for all end-user documentation. The previous `docs/user/` directory has been consolidated into this directory.

## Directory Contents

```
user-guide/
  AGENTS.md                   # This file
  accessibility.md            # Accessibility features for users (screen readers, keyboard)
  ai-audit.md                 # AI quality metrics and recommendations
  ai-enrichment.md            # Advanced AI analysis in event details
  ai-performance.md           # AI model performance and Model Zoo
  alerts-notifications.md     # Alerts and notifications guide
  dashboard-basics.md         # Dashboard layout, header, sidebar, quick stats
  dashboard-customization.md  # Dashboard customization and personalization
  dashboard-overview.md       # Dashboard overview
  dashboard-settings.md       # Configuration and quick reference
  event-investigation.md      # Video clips, entity tracking, timeline visualization
  event-timeline.md           # Event timeline guide
  getting-started.md          # Quick start guide for new users
  getting-started-tour.md     # Product tour walkthrough and first-time setup
  interface-guide.md          # Toast notifications, loading states, visual feedback
  keyboard-shortcuts.md       # Command palette and keyboard navigation
  logs-dashboard.md           # Logs dashboard guide
  mobile-pwa.md               # PWA installation, push notifications, mobile features
  prompt-playground.md        # AI prompt testing and playground
  search.md                   # Search functionality guide
  settings.md                 # Settings page guide
  system-monitoring.md        # System health, circuit breakers, troubleshooting
  understanding-alerts.md     # Risk levels and alert interpretation
  using-the-dashboard.md      # Comprehensive dashboard guide
  viewing-events.md           # Activity feed, timeline, event details
  zones.md                    # Detection zones configuration guide
```

## Key Files

### getting-started.md

**Purpose:** Onboarding guide for new users with minimal technical knowledge.

**Target Audience:** Homeowners and family members who will use the dashboard.

**Sections:**

| Section               | Description                                        |
| --------------------- | -------------------------------------------------- |
| What Does This Do?    | Simple explanation of system value proposition     |
| How It Works          | Simplified pipeline diagram (cameras -> AI -> you) |
| Opening the Dashboard | How to access at localhost:5173                    |
| What You'll See       | Overview of dashboard sections                     |
| About Demo Data       | Explains sample data during setup                  |
| Quick Tips            | Getting started advice                             |
| Next Steps            | Links to other guides                              |
| Need Help?            | Basic troubleshooting                              |

**Key Features:**

- Mermaid diagrams simplified for non-technical users
- Tables explaining UI sections
- No technical jargon
- AI image generation prompts for documentation visuals

**When to use:** First-time user onboarding, sharing with family members.

### getting-started-tour.md

**Purpose:** Guide to the interactive product tour and first-time setup steps.

**Target Audience:** New users who want to understand the product tour and complete initial setup.

**Topics Covered:**

- How to start/restart the product tour
- Explanation of each tour step
- First-time configuration checklist
- Detection zone setup
- Notification setup
- Keyboard shortcuts quick reference

**When to use:** First-time onboarding, restarting the tour, initial configuration.

### accessibility.md

**Purpose:** Guide to accessibility features for users who need assistive technologies.

**Target Audience:** Users with disabilities, screen reader users, keyboard-only users.

**Topics Covered:**

- Keyboard navigation (Tab, shortcuts, command palette)
- Screen reader compatibility (VoiceOver, NVDA, JAWS)
- Visual accessibility (contrast, focus indicators, text sizing)
- Mobile accessibility (touch targets, TalkBack, VoiceOver)
- Reduced motion preferences

**When to use:** Understanding accessibility features, configuring assistive technology.

### understanding-alerts.md

**Purpose:** Explains risk scoring and how to interpret alerts.

**Target Audience:** Users who want to understand what alerts mean.

**Topics Covered:**

- Risk score scale (0-100)
- Risk levels (low, medium, high, critical)
- Color coding (green, yellow, orange, red)
- What factors affect risk scores
- When to take action vs ignore
- Examples of different alert types
- False alarm handling

**When to use:** Understanding why an alert was triggered, learning to prioritize alerts.

### using-the-dashboard.md

**Purpose:** Comprehensive guide to all dashboard features.

**Target Audience:** Users who want to fully utilize the dashboard.

**Topics Covered:**

- Main dashboard overview
- Risk gauge interpretation
- Camera grid navigation
- Live activity feed usage
- Timeline page filtering
- Event detail modal features
- Settings page configuration
- Keyboard shortcuts (if any)

**When to use:** Learning dashboard features, troubleshooting UI issues.

### alerts-notifications.md

**Purpose:** Guide to alerts and notification features.

**Topics Covered:**

- Alert types and severity levels
- Notification settings
- Alert acknowledgment and dismissal
- Alert history and filtering

**When to use:** Configuring notifications, managing alerts.

### dashboard-overview.md

**Purpose:** Quick overview of the main dashboard.

**Topics Covered:**

- Dashboard layout and sections
- Key metrics and indicators
- Quick actions

**When to use:** Getting a quick orientation to the dashboard.

### event-investigation.md

**Purpose:** Deep-dive guide for investigating security events using video clips, entity tracking, and timeline features.

**Target Audience:** Users who want to thoroughly investigate security incidents.

**Topics Covered:**

- Event video clips (generation, viewing, downloading)
- Entity re-identification (how matching works, similarity scores)
- Viewing entity history across cameras
- Timeline visualization features
- Detection sequence strips
- AI enrichment data interpretation
- Investigation workflow recommendations

**When to use:** Detailed event investigation, tracking persons/vehicles across cameras, understanding what happened during an incident.

### event-timeline.md

**Purpose:** Guide to using the event timeline page.

**Topics Covered:**

- Timeline navigation
- Filtering events by date, camera, risk level
- Event grouping and sorting
- Exporting event data

**When to use:** Reviewing historical events, investigating incidents.

### logs-dashboard.md

**Purpose:** Guide to the logs dashboard.

**Topics Covered:**

- Log viewing and filtering
- Log levels (debug, info, warning, error)
- Log search and export
- Log retention settings

**When to use:** Troubleshooting issues, reviewing system activity.

### search.md

**Purpose:** Guide to search functionality.

**Topics Covered:**

- Search syntax and operators
- Searching events and detections
- Filtering search results
- Saving search queries

**When to use:** Finding specific events or patterns.

### interface-guide.md

**Purpose:** Guide to understanding visual feedback patterns in the dashboard.

**Target Audience:** All users who want to understand loading states, notifications, and visual feedback.

**Topics Covered:**

- Toast notification types (success, error, warning, info, loading)
- Toast appearance, duration, and dismissal
- Skeleton loading placeholders
- Page transitions and animations
- Status indicators (connection, camera, risk)
- Interactive feedback (buttons, forms, cards)
- Accessibility features (reduced motion, screen reader support)

**When to use:** Understanding what visual indicators mean, troubleshooting interface issues.

### keyboard-shortcuts.md

**Purpose:** Comprehensive guide to keyboard navigation and command palette.

**Target Audience:** Users who prefer keyboard navigation over mouse/touch.

**Topics Covered:**

- Command palette (Cmd/Ctrl + K)
- Navigation chords (g + key combinations)
- List navigation (j/k, arrow keys)
- Modal shortcuts (Escape)
- Video player shortcuts (Space, f, m)
- Lightbox navigation (arrow keys)
- Search bar shortcuts

**When to use:** Learning keyboard shortcuts, improving navigation efficiency.

### settings.md

**Purpose:** Guide to settings configuration.

**Topics Covered:**

- Camera configuration
- Processing settings
- AI model settings
- System preferences

**When to use:** Configuring the system, adjusting preferences.

### zones.md

**Purpose:** Guide to configuring detection zones within camera views.

**Target Audience:** Users who want to focus AI analysis on specific areas.

**Topics Covered:**

- Zone types (entry point, driveway, restricted, etc.)
- Creating and editing zones
- Zone shapes (rectangle, polygon)
- Zone priority and overlapping zones
- Coordinate system explanation
- Example zone configurations by camera type
- Troubleshooting zone issues

**When to use:** Setting up detection zones, reducing false positives, focusing on entry points.

### mobile-pwa.md

**Purpose:** Guide to PWA installation, push notifications, and mobile-optimized features.

**Target Audience:** Users who want to access the dashboard on mobile devices or receive push notifications.

**Topics Covered:**

- Installing as a PWA on iOS, Android, and desktop
- Enabling and managing push notifications
- Mobile-optimized features (bottom navigation, swipe gestures)
- Offline capabilities and cached events
- Troubleshooting installation and notification issues

**When to use:** Setting up the dashboard on mobile devices, enabling push notifications, understanding offline mode.

## Writing Style Guidelines

User guide documentation follows these conventions:

### Tone

- **Friendly and reassuring** - Security systems can feel invasive; emphasize protection, not surveillance
- **Non-technical** - Avoid jargon; explain concepts simply
- **Action-oriented** - Tell users what to do, not just what exists

### Structure

- **Short paragraphs** - 2-3 sentences maximum
- **Tables for reference** - Easy scanning of information
- **Numbered steps** - Clear procedural guidance
- **Callouts for tips** - Use blockquotes for helpful hints

### Visual Elements

- **Mermaid diagrams** - Simplified, user-friendly flowcharts
- **Screenshots** - Reference actual UI when possible
- **Icons** - Consistent iconography for navigation
- **Color coding** - Match dashboard color scheme

## Target Audiences

| Audience           | Needs                                     | Primary Documents       |
| ------------------ | ----------------------------------------- | ----------------------- |
| **New Users**      | Quick orientation, basic understanding    | getting-started.md      |
| **Daily Users**    | Alert interpretation, dashboard usage     | understanding-alerts.md |
| **Power Users**    | Full feature exploration, configuration   | using-the-dashboard.md  |
| **Family Members** | Simple overview without technical details | getting-started.md      |

## Important Patterns

### Progressive Disclosure

Documents are ordered from simple to complex:

1. `getting-started.md` - Minimal, essential information
2. `understanding-alerts.md` - Deeper dive into one concept
3. `using-the-dashboard.md` - Comprehensive reference

### Cross-References

Documents link to each other for navigation:

```markdown
- **[Using the Dashboard](using-the-dashboard.md)** - Detailed guide...
- **[Understanding Alerts](understanding-alerts.md)** - What the risk levels mean...
```

### Visual Generation

Each document includes AI image generation prompts for creating:

- Hero/banner images
- Simplified diagrams
- Instructional illustrations

These prompts can be used with DALL-E, Midjourney, or Stable Diffusion.

## Entry Points for Agents

### Updating User Documentation

1. Maintain non-technical language
2. Update screenshots when UI changes
3. Keep Mermaid diagrams synchronized with actual system behavior
4. Test all navigation links

### Adding New Features

1. Update `using-the-dashboard.md` with new feature documentation
2. Add to Quick Tips in `getting-started.md` if universally useful
3. Update alert documentation if new risk factors are added

### Localizing Documentation

Documents are written in English. For localization:

1. Maintain same file structure with language suffix (e.g., `getting-started.es.md`)
2. Update all navigation links
3. Localize Mermaid diagram labels
4. Regenerate images with localized text prompts

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/architecture/:** Technical architecture (for developers, not users)
- **frontend/src/components/:** React components implementing described UI
- **README.md:** Project overview with setup instructions
