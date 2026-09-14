# Platform Enhancement Strategy Design

**Date:** 2026-02-01
**Status:** Approved
**Research Source:** 15 parallel research agents analyzing full codebase

## Executive Summary

This design outlines a comprehensive platform enhancement strategy based on exhaustive analysis of:

- 401 API endpoints across 54 route files
- 191 backend services across 15 tiers
- 200+ React components across 43 feature directories
- 32 AI models in Model Zoo
- 7 user personas with distinct needs
- Competitive landscape (Frigate, Blue Iris, Shinobi, UniFi Protect)

**Key Finding:** The backend has 2-3x more functionality than currently exposed to users.

## Strategic Decision

Focus on three priorities:

1. **Surface the Hidden Gold** — Expose existing backend capabilities
2. **AI Differentiation** — Activate underutilized AI models
3. **Ecosystem Integration** — Enable Home Assistant and MQTT connectivity

Competitive feature parity (continuous recording, mobile app) deferred to backlog.

## Epic Structure

```
EPIC 0: Foundation Infrastructure (1-2 weeks)
    │
    ├── MQTT Client Service
    ├── WebSocket Event Expansion (8 new event types)
    ├── Enrichment Viewer Component
    ├── Timeline Visualization Base
    └── Alert Rule Condition Types
    │
    ▼ (blocks)
┌───────────────────┬───────────────────┬───────────────────┐
│     EPIC 1        │     EPIC 2        │     EPIC 3        │
│  Hidden Backend   │ AI Differentiation│   Ecosystem       │
│   (4-5 weeks)     │    (5-6 weeks)    │   (5-6 weeks)     │
└───────────────────┴───────────────────┴───────────────────┘
```

## Phased Parallel Execution

### Foundation (Week 1-2)

- MQTT Client Service
- WebSocket Event Expansion
- Enrichment Viewer Component
- Timeline Visualization Base
- Alert Rule Condition Types

### Phase 1 - Quick Wins (Week 3-4)

| Epic 1                              | Epic 2                  | Epic 3          |
| ----------------------------------- | ----------------------- | --------------- |
| Zone Heatmaps (connect to real API) | Loitering Alerts        | MQTT Publishing |
| Cost Analytics Dashboard            | Pose-Based Alerts       | MQTT Config UI  |
| DLQ Management Actions              | Threat Detection Alerts | MQTT Commands   |
| Threat Detection Surfacing          |                         |                 |

### Phase 2 - Core Features (Week 5-7)

| Epic 1                  | Epic 2              | Epic 3             |
| ----------------------- | ------------------- | ------------------ |
| Tracks Visualization UI | Depth-Based Context | HA MQTT Discovery  |
| Approach Vector Display | Weather Context     | HA Entity Types    |
| Action Events Timeline  | Enhanced Threat UI  | New Webhook Events |

### Phase 3 - Advanced (Week 8-11)

| Epic 1                 | Epic 2               | Epic 3              |
| ---------------------- | -------------------- | ------------------- |
| Re-ID Dashboard        | X-CLIP Activation    | HA Custom Component |
| LLM Reasoning Explorer | Package Detection    | Webhook Presets     |
|                        | Smoke/Fire Detection | Inbound API         |
|                        |                      | Frigate Integration |

## Linear Issues

| Epic               | Issue                                                                   | Status                     |
| ------------------ | ----------------------------------------------------------------------- | -------------------------- |
| Foundation         | [NEM-5019](https://linear.app/nemotron-v3-home-security/issue/NEM-5019) | Todo                       |
| Hidden Backend     | [NEM-5024](https://linear.app/nemotron-v3-home-security/issue/NEM-5024) | Todo (blocked by NEM-5019) |
| AI Differentiation | [NEM-5025](https://linear.app/nemotron-v3-home-security/issue/NEM-5025) | Todo (blocked by NEM-5019) |
| Ecosystem          | [NEM-5032](https://linear.app/nemotron-v3-home-security/issue/NEM-5032) | Todo (blocked by NEM-5019) |
| Competitive Parity | [NEM-4989](https://linear.app/nemotron-v3-home-security/issue/NEM-4989) | Backlog (deferred)         |

## Feature Inventory

### Epic 1: Hidden Backend Exposure

**Phase 1 - Quick Wins:**

- Zone Activity Heatmaps (replace mock data with real API)
- Cost Analytics Dashboard (Prometheus metrics exist)
- DLQ Management Actions (requeue/clear buttons)
- Threat Detection Surfacing (prominent badges)

**Phase 2 - Entity Intelligence:**

- Tracks Visualization UI (API: `/api/tracks`)
- Approach Vector Display (zone_service calculates)
- Action Events Timeline (API: `/api/action-events`)

**Phase 3 - Advanced Viewers:**

- Re-ID Dashboard (API: `/api/entities`, `/api/reid/search`)
- LLM Reasoning Explorer (LLMInteraction table with `<think>` blocks)

### Epic 2: AI Differentiation

**Phase 1 - Alert Integration:**

- Loitering Detection Alerts (dwell time → alert engine)
- Pose-Based Alerts (ViTPose crouching, fallen, climbing)
- Threat Detection Alerts (bypass batching, CRITICAL priority)

**Phase 2 - Context Enhancement:**

- Depth-Based Context (Depth Anything V2 → "5 feet from door")
- Weather Context (SigLIP classifier → risk adjustment)
- Enhanced Threat UI (weapon type, confidence, bounding box)

**Phase 3 - New Capabilities:**

- X-CLIP Action Recognition (lower trigger threshold)
- Package Detection (new YOLO class)
- Smoke/Fire Detection (new model, life safety)

### Epic 3: Ecosystem Integration

**Phase 1 - MQTT Foundation:**

- MQTT Event Publishing (8+ topic types)
- MQTT Configuration UI
- MQTT Command Subscription

**Phase 2 - Home Assistant:**

- HA MQTT Discovery (auto-configure entities)
- HA Entity Types (binary sensors, sensors, triggers)
- HA Custom Component (optional advanced)

**Phase 3 - Webhooks:**

- New Webhook Event Types (8 new types)
- Webhook Presets (IFTTT, Zapier, n8n, Node-RED)
- Inbound Webhook API

**Phase 4 - NVR Partnership:**

- Frigate Integration (bi-directional MQTT events)

## New WebSocket Events

```python
# Zone events
"zone.crossing"          # Line zone crossed
"zone.dwell_started"     # Entity entered zone
"zone.dwell_alert"       # Dwell threshold exceeded
"zone.approach"          # Entity approaching zone

# Entity events
"entity.matched"         # Re-ID match found
"entity.track_updated"   # Track position updated

# AI events
"ai.threat_detected"     # Weapon/threat found
"ai.action_recognized"   # X-CLIP action detected
```

## New Alert Condition Types

```python
"dwell_time"       # Alert when dwell exceeds threshold
"pose_type"        # Alert on specific poses
"action_type"      # Alert on X-CLIP actions
"threat_detected"  # Alert on weapon detection
"smoke_fire"       # Alert on smoke/fire detection
```

## MQTT Topic Structure

```
hsi/events/{camera_id}              # Security events
hsi/alerts/{severity}               # Alert notifications
hsi/detections/{camera_id}/{type}   # Raw detections
hsi/zones/{zone_id}/crossing        # Zone crossings
hsi/zones/{zone_id}/dwell           # Dwell alerts
hsi/entities/{entity_type}          # Entity events
hsi/health/cameras/{camera_id}      # Camera status
hsi/health/system                   # System health

# Commands (subscribe)
hsi/commands/zones/{zone_id}/arm
hsi/commands/zones/{zone_id}/disarm
hsi/commands/cameras/{camera_id}/ptz
hsi/commands/alerts/acknowledge/{alert_id}
```

## Estimated Timeline

| Week | Focus                             |
| ---- | --------------------------------- |
| 1-2  | Foundation Infrastructure         |
| 3-4  | Phase 1 Quick Wins (all epics)    |
| 5-7  | Phase 2 Core Features (all epics) |
| 8-11 | Phase 3 Advanced (all epics)      |

**Total:** ~11 weeks for full implementation

## Success Metrics

- All backend capabilities accessible via UI
- MQTT integration enables Home Assistant automations
- New AI alerts reduce false negatives for threats
- User can see AI reasoning for any event
- Cross-camera entity tracking visible in dashboard

## Risks and Mitigations

| Risk                       | Mitigation                                    |
| -------------------------- | --------------------------------------------- |
| MQTT adds complexity       | Start with publish-only, add commands later   |
| X-CLIP performance         | Keep LOW priority, only load when needed      |
| Smoke/fire false positives | Require 2+ consecutive detections             |
| Re-ID UI complexity        | Start with list view, add visualization later |

## Research Agent Summaries

This design was informed by 15 parallel research agents:

1. **Backend API Endpoints** - 401 endpoints, all fully implemented
2. **Backend Services** - 191 services, many underutilized
3. **AI Pipeline** - 32 models, 10 always-loaded
4. **Frontend Components** - 200+ components, enterprise-grade
5. **Frontend API Integration** - 34 API clients, 200+ hooks
6. **Backend-Frontend Gap Analysis** - 50+ endpoints without UI
7. **Zone Intelligence** - Sophisticated spatial analysis hidden
8. **Person Tracking** - Re-ID complete, UI placeholder only
9. **Alerting & Notifications** - Robust, needs new condition types
10. **Analytics & Reporting** - 100+ metrics tracked, few displayed
11. **Camera Management** - Mature, missing continuous recording
12. **Roadmap Analysis** - Post-MVP, focused on optimization
13. **Integrations** - Webhook-only, MQTT missing
14. **User Personas** - 7 distinct segments identified
15. **Competitive Analysis** - AI advantage, missing table stakes
