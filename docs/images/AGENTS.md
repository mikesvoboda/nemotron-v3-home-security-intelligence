# Images Directory - Agent Guide

## Purpose

This directory contains visual assets for documentation, including UI mockups, architecture diagrams, and screenshots.

## Directory Contents

```
images/
├── AGENTS.md              # This file
├── .gitkeep               # Ensures directory is tracked in git
└── dashboard-mockup.svg   # Main dashboard UI mockup
```

## Current Assets

### dashboard-mockup.svg

**Type:** SVG vector graphic
**Dimensions:** 1200 x 700 pixels
**Purpose:** Visual mockup of the main dashboard UI

**Sections Shown:**

| Section         | Location     | Description                                                                             |
| --------------- | ------------ | --------------------------------------------------------------------------------------- |
| Header Bar      | Top          | "Home Security Intelligence" title, system status indicator                             |
| Risk Gauge      | Left column  | Current risk level (0-100), risk breakdown (24h events)                                 |
| GPU Status      | Left column  | Utilization bar, memory usage, temperature, FPS                                         |
| Camera Grid     | Center       | 2x2 grid of camera feeds with status indicators                                         |
| Live Activity   | Right column | Event cards with risk scores and timestamps                                             |
| System Overview | Bottom       | RT-DETRv2 status, Nemotron status, active cameras, events today, inference rate, uptime |

**Color Scheme:**

- Background: `#1a1a2e` (dark blue-gray)
- Card backgrounds: `#0f3460` (darker blue)
- Text: White/gray
- Low risk: `#4ade80` (green)
- Medium risk: `#fbbf24` (amber)
- Accent: `#3b82f6` (blue), `#8b5cf6` (purple)

**Usage:**

- Reference when implementing dashboard components
- Include in README or documentation
- Share with stakeholders for UI approval

## File Types

| Extension | Purpose                             | Tools                    |
| --------- | ----------------------------------- | ------------------------ |
| `.svg`    | Vector graphics (mockups, diagrams) | Inkscape, Figma, browser |
| `.png`    | Screenshots, raster images          | Any image viewer         |
| `.gif`    | Animated demos                      | Browser, image viewer    |

## Adding New Images

### Naming Convention

- Lowercase with hyphens: `feature-name-mockup.svg`
- Include type suffix: `-mockup`, `-diagram`, `-screenshot`
- Be descriptive: `event-detail-modal-mockup.svg`

### Image Guidelines

1. **Vector preferred:** Use SVG for mockups and diagrams when possible
2. **Reasonable size:** Keep file sizes under 1MB for faster loading
3. **Include context:** Show realistic data in mockups
4. **Document purpose:** Add entry to this AGENTS.md when adding images

### SVG Best Practices

- Use semantic groupings with `<g>` elements
- Include descriptive comments for complex sections
- Use consistent coordinate systems
- Keep text as actual text (not paths) for accessibility

## Related Documentation

- **docs/plans/2024-12-21-dashboard-mvp-design.md:** UI mockups (ASCII) and design spec
- **frontend/src/components/:** React component implementations
- **docs/AGENTS.md:** Documentation directory guide
