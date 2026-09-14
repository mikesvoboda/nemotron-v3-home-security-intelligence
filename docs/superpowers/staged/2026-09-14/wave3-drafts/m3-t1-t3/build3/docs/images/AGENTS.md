# Images Directory - Agent Guide

## Purpose

This directory contains visual assets for documentation, including UI mockups, architecture diagrams, screenshots, and SVG diagrams organized by topic.

## Directory Structure

```
images/
  AGENTS.md                    # This file
  SCREENSHOT_GUIDE.md          # Screenshot capture guidelines
  style-guide.md               # SVG diagram style guide
  .gitkeep                     # Ensures directory is tracked in git

  # Root-level Images
  alerts.png                   # Alerts page screenshot
  arch-model-zoo.png           # Model Zoo architecture diagram
  arch-system-overview.png     # System overview architecture diagram
  arch-websocket-flow.png      # WebSocket communication flow diagram
  dashboard-full.png           # Full dashboard screenshot
  dashboard-mockup.svg         # Main dashboard UI mockup (vector)
  dashboard.png                # Dashboard screenshot
  deploy-docker-topology.png   # Docker deployment topology diagram
  erd-data-model.png           # Entity-Relationship data model diagram
  first-run-devmode.png        # First run dev mode screenshot
  flow-ai-pipeline.png         # AI pipeline flow diagram
  flow-batch-aggregator.png    # Batch aggregator flow diagram
  ftp-ingestion-flow.png       # FTP camera ingestion flow
  gpu-compatibility-matrix.png # GPU compatibility matrix
  info-camera-to-event.png     # Camera to event flow infographic
  info-detection-types.png     # Detection types infographic
  info-risk-scoring.png        # Risk scoring infographic
  installation-workflow.png    # Installation workflow diagram
  local-ai-concept.png         # Local AI concept diagram
  quickstart-decision-tree.png # Quickstart decision tree
  service-dependencies-mermaid.png # Service dependencies (Mermaid)
  timeline.png                 # Event timeline page screenshot
  troubleshooting-decision-tree.png # Troubleshooting decision tree

  # Subdirectories
  admin/                       # Admin guide diagrams
  ai-pipeline/                 # AI pipeline SVG diagrams
  architecture/                # Architecture diagrams (PNG and SVG)
  data-model/                  # Data model SVG diagrams
  real-time/                   # Real-time/WebSocket SVG diagrams
  resilience/                  # Resilience pattern SVG diagrams
  user-guide/                  # User guide images
```

## Subdirectory Contents

### admin/

Admin guide diagrams:

- `alert-delivery-pipeline.png` - Alert delivery pipeline
- `authentication-flow.png` - Authentication flow
- `cleanup-sequence.png` - Cleanup sequence diagram
- `configuration-hierarchy.png` - Configuration hierarchy
- `monitoring-stack.png` - Monitoring stack
- `network-isolation.png` - Network isolation
- `retention-policies.png` - Retention policies
- `security-architecture.png` - Security architecture

### ai-pipeline/

AI pipeline SVG diagrams:

- `ai-service-interaction.svg` - AI service interaction diagram
- `batch-lifecycle-state.svg` - Batch lifecycle state machine
- `detection-errors.svg` - Detection error handling
- `detection-event-transform.svg` - Detection to event transformation
- `fast-path-decision.svg` - Fast path decision tree
- `pipeline-sequence.svg` - Pipeline sequence diagram

### architecture/

Architecture diagrams (PNG and SVG):

- `overview-*.svg` - System overview diagrams
- `ai-pipeline-*.png` - AI pipeline diagrams
- `circuit-breaker-*.png` - Circuit breaker diagrams
- `deployment-*.png` - Deployment diagrams
- `database-*.png` - Database diagrams
- `frontend-*.png` - Frontend architecture
- `resilience-*.png` - Resilience patterns
- Many more architecture visualizations

### data-model/

Data model SVG diagrams:

- `cleanup-service-sequence.svg` - Cleanup service sequence
- `data-lifecycle-state.svg` - Data lifecycle states
- `entity-relationship.svg` - Entity-relationship diagram
- `storage-architecture.svg` - Storage architecture

### real-time/

Real-time/WebSocket SVG diagrams:

- `events-channel-sequence.svg` - Events channel sequence
- `redis-pubsub-flow.svg` - Redis pub/sub flow
- `system-channel-sequence.svg` - System channel sequence
- `websocket-architecture.svg` - WebSocket architecture

### resilience/

Resilience pattern SVG diagrams:

- `circuit-breaker-registry.svg` - Circuit breaker registry
- `circuit-breaker-states.svg` - Circuit breaker state machine
- `dlq-architecture.svg` - Dead letter queue architecture
- `frontend-state-machine.svg` - Frontend state machine
- `graceful-degradation.svg` - Graceful degradation flow
- `health-check-flow.svg` - Health check flow
- `recovery-flow.svg` - Recovery flow diagram
- `resilience-overview.svg` - Resilience overview
- `retry-handler-flow.svg` - Retry handler flow
- `websocket-circuit-breaker.svg` - WebSocket circuit breaker
- `websocket-manager.svg` - WebSocket manager

### screenshots/

Application screenshots for documentation:

- `ai-performance.png` - AI Performance page
- `alerts.png` - Alerts page
- `analytics.png` - Analytics page
- `audit-log.png` - Audit Log page
- `dashboard.png` - Dashboard page
- `dashboard-tour.gif` - Dashboard tour animation
- `entities.png` - Entities page
- `jobs.png` - Background Jobs page
- `logs.png` - Logs page
- `operations.png` - System Operations page
- `settings.png` - Settings page
- `system.png` - System page
- `timeline.png` - Event Timeline page
- `trash.png` - Trash page

### user-guide/

User guide images:

- `decision-flowchart.png` - User decision flowchart
- `entity-reid-flow.png` - Entity re-identification flow
- `risk-scale.png` - Risk scale visualization

## Color Scheme

Dashboard uses NVIDIA-themed dark design:

- Background: `#1a1a2e` (dark blue-gray)
- Card backgrounds: `#0f3460` (darker blue)
- Text: White/gray
- Low risk: `#4ade80` (green)
- Medium risk: `#fbbf24` (amber)
- Accent: `#3b82f6` (blue), `#8b5cf6` (purple)
- NVIDIA Green: `#76B900`

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

### Subdirectory Organization

Place images in the appropriate subdirectory:

- `admin/` - Admin guide diagrams
- `ai-pipeline/` - AI pipeline diagrams
- `architecture/` - System architecture diagrams
- `data-model/` - Database/data model diagrams
- `real-time/` - WebSocket/real-time diagrams
- `resilience/` - Circuit breaker, retry, DLQ diagrams
- `user-guide/` - End-user documentation images

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

- **docs/AGENTS.md:** Documentation directory guide
- **frontend/src/components/:** React component implementations
- **docs/images/style-guide.md:** Detailed SVG style guidelines
- **docs/images/SCREENSHOT_GUIDE.md:** Screenshot capture instructions
