# Zone Intelligence System Design

**Date:** 2026-01-21
**Status:** Draft
**Linear Issue:** NEM-3178 (expanded), NEM-3181 (reframed)

## Overview

Transform underutilized hooks into a comprehensive zone intelligence system that makes the UI more effective through detection intelligence, household context, and operational awareness.

### Goals

1. **Detection Intelligence** - Make zones smarter about what's happening in them (activity heatmaps, dwell time alerts, crossing events)
2. **Household Context** - Connect zones to people/vehicles (e.g., "notify me when non-family enters driveway")
3. **Operational Dashboard** - Create a zone-centric view showing health, alerts, and activity across all zones

### Entry Points

- **Enhanced Zone Editor** - Existing editor with intelligence panels
- **Zone Intelligence Page** - New `/zones` dashboard across all cameras
- **Camera View Overlay** - Real-time zone intelligence on live camera view

---

## Architecture

### Data Flow

```
Backend APIs ──► React Query Hooks ──► Shared Components ──► Entry Points
                     │
                     ├─ useZones (zone CRUD)
                     ├─ useTimelineData (activity buckets)
                     ├─ useRiskHistoryQuery (risk trends)
                     ├─ useHouseholdApi (people/vehicles)
                     ├─ useNotificationPreferences (per-zone alerts)
                     ├─ usePrometheusAlerts (system health)
                     ├─ useWorkerEvents (pipeline status)
                     ├─ useAuditLogsInfiniteQuery (change history)
                     └─ useExportJobs (analytics export)
```

### Shared Component Library

| Component               | Hooks Used                           | Purpose                   |
| ----------------------- | ------------------------------------ | ------------------------- |
| `ZoneActivityHeatmap`   | useZones, useTimelineData            | Detection density overlay |
| `ZoneTimelineScrubber`  | useTimelineData, useRiskHistoryQuery | Time-based activity       |
| `ZoneStatusCard`        | useZones, useHouseholdApi            | Compact zone widget       |
| `ZoneCrossingFeed`      | useZones (+ new WebSocket)           | Entry/exit event stream   |
| `ZoneHouseholdBadge`    | useHouseholdApi                      | Who's in this zone        |
| `SystemHealthIndicator` | usePrometheusAlerts, useWorkerEvents | Status badge + drill-down |

### New Backend Requirements

- WebSocket events for zone crossings (`zone.entered`, `zone.exited`)
- Aggregation endpoint for zone activity heatmaps
- Pattern anomaly detection service
- Zone-household linkage API
- Trust configuration API
- Detection-to-member matching service

---

## Shared Visualization Components

### 1. ZoneActivityHeatmap

Renders detection density as a color gradient overlay on camera snapshots or zone polygons.

```typescript
interface ZoneActivityHeatmapProps {
  cameraId: string;
  zoneId?: string; // Optional: single zone or all zones
  timeRange: TimeRange; // Last hour, day, week
  metric: 'detections' | 'dwell_time' | 'risk_score';
}
```

- Uses `useTimelineData` for bucketed counts
- SVG gradient overlay on `ZoneCanvas` (reuses existing component)
- Color scale: blue (low) → yellow → red (high)
- Tooltip on hover: "47 detections in last 24h"

### 2. ZoneTimelineScrubber

Horizontal timeline showing zone activity over time with drill-down.

```typescript
interface ZoneTimelineScrubberProps {
  zoneIds: string[]; // One or multiple zones
  onTimeSelect: (range: TimeRange) => void;
  height?: number;
}
```

- Uses `useTimelineData` (bucketed events) + `useRiskHistoryQuery` (risk distribution)
- Stacked bar chart: severity colors per time bucket
- Brush selection to zoom into time ranges
- Integrates with other components (selecting time updates heatmap, feed)

### 3. ZoneStatusCard

Compact widget summarizing zone state - designed for dashboards and lists.

```typescript
interface ZoneStatusCardProps {
  zoneId: string;
  cameraId: string;
  compact?: boolean; // Minimal vs expanded view
}
```

- Uses `useZones`, `useHouseholdApi`, `useTimelineData`
- Shows: zone name, type badge, current occupants, recent activity sparkline
- Status indicator: "Active" (recent detections), "Quiet", "Alert"
- Click to expand or navigate to zone detail

### 4. ZoneCrossingFeed

Real-time stream of zone entry/exit events.

```typescript
interface ZoneCrossingFeedProps {
  zoneIds?: string[]; // Filter to specific zones
  householdFilter?: 'all' | 'known' | 'unknown';
  limit?: number;
}
```

- New WebSocket subscription: `zone.entered`, `zone.exited`
- Uses `useHouseholdApi` to label known people/vehicles
- Each event: timestamp, zone name, entity type, thumbnail, trust level
- "Unknown person entered Driveway" highlighted vs "Dad arrived (Front Door)"

---

## Household Integration Layer

### Data Model Extension

```typescript
// New: Zone-to-Household linkages
interface ZoneHouseholdConfig {
  zoneId: string;
  ownerId?: string; // Household member who "owns" this zone
  allowedMemberIds: string[]; // Who can be here without alerts
  allowedVehicleIds: string[];
  accessSchedule?: {
    // Time-based access rules
    memberIds: string[];
    schedule: CronExpression; // e.g., "service workers 9-5 weekdays"
  }[];
}
```

### Components

#### ZoneOwnershipPanel

Assign zones to household members within the Zone Editor.

- Dropdown to select owner ("Dad's parking spot", "Kids' play area")
- Owner receives all notifications for this zone
- Visual badge on zone showing owner avatar

#### ZoneTrustMatrix

Configure who triggers alerts in which zones.

```
                    | Driveway | Front Door | Backyard | Garage |
--------------------|----------|------------|----------|--------|
Family (full trust) |    ✓     |     ✓      |    ✓     |   ✓    |
Service (partial)   |    ✓     |     ✓      |  9-5 ⏰  |   ✗    |
Visitors (monitor)  |    ✓     |     ✓      |    ✗     |   ✗    |
Unknown             |   ⚠️     |    ⚠️      |   🚨     |  🚨    |
```

- Matrix UI for bulk configuration
- Time-based rules shown with clock icon
- Severity escalation: ✓ (no alert) → ⚠️ (notify) → 🚨 (urgent)

#### ZonePresenceIndicator

Shows who's currently in a zone based on recent detections.

- Uses `useHouseholdApi` for member/vehicle data
- Matches detections to known faces/plates
- Displays avatars of current occupants
- "Unknown" shown with generic silhouette + thumbnail

### Alert Logic (Trust Violation)

```typescript
function shouldAlert(detection: Detection, zone: Zone): AlertLevel {
  const entity = matchToHousehold(detection); // Face/plate recognition

  if (!entity) return 'urgent'; // Unknown person/vehicle

  const trust = getZoneTrust(zone.id, entity.id);
  if (trust === 'full') return 'none';
  if (trust === 'partial' && isWithinSchedule(zone, entity)) return 'none';

  return 'notify'; // Trust violation
}
```

---

## Alerting & Anomaly Detection

### Alert Types

1. **Trust Violation Alerts** - Unexpected person/vehicle in zone
2. **Pattern Anomaly Alerts** - Unusual activity compared to baseline

### Trust Violation Pipeline

```
Detection → Zone Match → Household Match → Trust Check → Alert Decision
                              │
                              ├─ Known + Full Trust → No alert
                              ├─ Known + Partial Trust → Check schedule
                              ├─ Known + Monitor → Log only
                              └─ Unknown → Alert (severity by zone type)
```

Zone type affects severity:

| Zone Type   | Unknown Person | Unknown Vehicle |
| ----------- | -------------- | --------------- |
| entry_point | Critical       | Critical        |
| driveway    | Warning        | Warning         |
| sidewalk    | Info           | Info            |
| yard        | Critical       | Warning         |
| other       | Warning        | Warning         |

### Pattern Anomaly Detection

New backend service analyzes zone activity baselines.

```typescript
interface ZoneActivityBaseline {
  zoneId: string;
  hourlyPattern: number[]; // 24 buckets, avg detections per hour
  dayOfWeekPattern: number[]; // 7 buckets
  typicalDwellTime: number; // seconds
  typicalCrossingRate: number; // crossings per hour
}

interface AnomalyEvent {
  type: 'unusual_time' | 'unusual_frequency' | 'unusual_dwell' | 'unusual_entity';
  zoneId: string;
  deviation: number; // Standard deviations from baseline
  description: string; // "Activity at 3:14am - typically no activity 1-6am"
}
```

**Anomaly Types:**

- **Unusual time**: Detection outside normal activity hours for this zone
- **Unusual frequency**: Spike or drop in activity (3+ std deviations)
- **Unusual dwell**: Someone lingering 2x+ longer than typical
- **Unusual entity**: First-time visitor to high-security zone

### Zone Notification Configuration

Uses `useNotificationPreferences` for per-zone alert routing:

```typescript
interface ZoneNotificationConfig {
  zoneId: string;
  trustViolation: {
    enabled: boolean;
    minSeverity: 'info' | 'warning' | 'critical';
    channels: ('push' | 'email' | 'sms')[];
  };
  anomaly: {
    enabled: boolean;
    minDeviation: number; // Default: 2 std deviations
    channels: ('push' | 'email' | 'sms')[];
  };
}
```

### ZoneAlertFeed Component

```typescript
interface ZoneAlertFeedProps {
  zoneIds?: string[];
  types?: ('trust_violation' | 'anomaly')[];
  onAcknowledge: (alertId: string) => void;
}
```

- Real-time via WebSocket
- Groups related alerts (same person, multiple zones)
- Quick actions: Acknowledge, Add to household, View recording

---

## Entry Points

### 1. Enhanced Zone Editor

Evolves existing `ZoneEditor` component with intelligence panels.

```
┌─────────────────────────────────────────────────────────────┐
│ Zone Editor: Front Door Camera                    [X Close] │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐  ┌────────────────────────────┐ │
│ │                         │  │ Zones          [+ Add]     │ │
│ │   Camera View +         │  │ ┌──────────────────────┐   │ │
│ │   ZoneActivityHeatmap   │  │ │ 🟢 Front Porch       │   │ │
│ │                         │  │ │    Dad's zone · 12/hr│   │ │
│ │   [Draw Rectangle]      │  │ ├──────────────────────┤   │ │
│ │   [Draw Polygon]        │  │ │ 🟡 Walkway           │   │ │
│ │                         │  │ │    Shared · 45/hr    │   │ │
│ └─────────────────────────┘  │ └──────────────────────┘   │ │
│                              ├────────────────────────────┤ │
│ ┌─────────────────────────┐  │ Selected: Front Porch     │ │
│ │ ZoneTimelineScrubber    │  │ ┌────────────────────────┐ │ │
│ │ ▁▂▃▅▇▅▃▂▁▁▁▁▂▃▅▇█▇▅▃▂▁ │  │ │ Owner: Dad           │ │ │
│ │ 12am    12pm    Now     │  │ │ Trust: [Configure...] │ │ │
│ └─────────────────────────┘  │ │ Alerts: On (Critical) │ │ │
│                              │ └────────────────────────┘ │ │
├─────────────────────────────┴────────────────────────────┤ │
│ 🟢 System Healthy              Recent: Unknown at 2:34pm  │ │
└─────────────────────────────────────────────────────────────┘
```

**New tabs/panels:**

- Activity heatmap toggle on canvas
- Timeline scrubber below canvas
- Ownership & trust config in zone properties
- System health indicator in footer

### 2. Zone Intelligence Page

New page: `/zones` - unified dashboard across all cameras.

```
┌─────────────────────────────────────────────────────────────┐
│ Zone Intelligence                    🟢 All Systems Healthy │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ZoneTimelineScrubber (all zones)                        │ │
│ │ ▁▂▃▅▇▅▃▂▁▁▁▁▂▃▅▇█▇▅▃▂▁ Driveway                        │ │
│ │ ▁▁▂▂▃▃▂▂▁▁▁▁▁▂▃▃▅▅▃▂▁▁ Front Door                      │ │
│ │ ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▂▃▂▁▁▁ Backyard                        │ │
│ └─────────────────────────────────────────────────────────┘ │
├──────────────────────────┬──────────────────────────────────┤
│ Zone Status Cards        │ Live Feed                        │
│ ┌──────────┐ ┌─────────┐ │ ┌──────────────────────────────┐ │
│ │ Driveway │ │ Front   │ │ │ ZoneCrossingFeed             │ │
│ │ 🚗 Dad   │ │ Door    │ │ │                              │ │
│ │ 23/hr    │ │ Empty   │ │ │ 2:34p Unknown → Driveway ⚠️  │ │
│ │ ▂▃▅▃▂    │ │ 8/hr    │ │ │ 2:31p Dad ← Front Door      │ │
│ └──────────┘ └─────────┘ │ │ 2:15p Package → Front Porch  │ │
│ ┌──────────┐ ┌─────────┐ │ │ 1:58p Kids → Backyard        │ │
│ │ Backyard │ │ Garage  │ │ │                              │ │
│ │ 👧👦 Kids│ │ 🔒 Empty│ │ └──────────────────────────────┘ │
│ │ 5/hr     │ │ 0/hr    │ │                                  │
│ └──────────┘ └─────────┘ │ [Trust Violations] [Anomalies]   │
└──────────────────────────┴──────────────────────────────────┘
```

**Features:**

- Multi-zone timeline comparison
- Grid of `ZoneStatusCard` components
- Filtered `ZoneCrossingFeed` with household labels
- Click any zone card → opens Enhanced Zone Editor

### 3. Camera View Overlay

Enhances existing live camera view with zone intelligence.

```
┌─────────────────────────────────────────────────────────────┐
│ Front Door Camera                    ● LIVE    🟢 Healthy   │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                                                         │ │
│ │              [Live Video Feed]                          │ │
│ │                                                         │ │
│ │    ┌─────────────────┐                                  │ │
│ │    │ Front Porch     │ ← Zone overlay (semi-transparent)│ │
│ │    │ 👤 Dad present  │                                  │ │
│ │    └─────────────────┘                                  │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ ⚠️ Unknown person entered Walkway 2 min ago    [View Alert] │
└─────────────────────────────────────────────────────────────┘
```

**Overlay features:**

- Zone polygons drawn on video (toggle on/off)
- `ZonePresenceIndicator` badges on active zones
- Inline alert banner for trust violations/anomalies
- Click zone → quick stats popover or jump to editor

---

## Implementation Phases

### Phase 1: Shared Component Foundation

| Component               | Hooks Leveraged                          | New Backend Needed           |
| ----------------------- | ---------------------------------------- | ---------------------------- |
| `ZoneActivityHeatmap`   | `useZones`, `useTimelineData`            | Heatmap aggregation endpoint |
| `ZoneTimelineScrubber`  | `useTimelineData`, `useRiskHistoryQuery` | None (existing APIs)         |
| `ZoneStatusCard`        | `useZones`, `useHouseholdApi`            | None                         |
| `SystemHealthIndicator` | `usePrometheusAlerts`, `useWorkerEvents` | None                         |

**Deliverable:** 4 reusable components, unit tested

### Phase 2: Household Integration

| Component               | Hooks Leveraged               | New Backend Needed           |
| ----------------------- | ----------------------------- | ---------------------------- |
| `ZoneOwnershipPanel`    | `useHouseholdApi`, `useZones` | Zone-household linkage API   |
| `ZoneTrustMatrix`       | `useHouseholdApi`, `useZones` | Trust configuration API      |
| `ZonePresenceIndicator` | `useHouseholdApi`             | Detection-to-member matching |

**Deliverable:** Household-zone linking, trust configuration UI

### Phase 3: Crossing Events & Alerts

| Component          | Hooks Leveraged               | New Backend Needed                       |
| ------------------ | ----------------------------- | ---------------------------------------- |
| `ZoneCrossingFeed` | `useZones`, `useHouseholdApi` | WebSocket: `zone.entered`, `zone.exited` |
| `ZoneAlertFeed`    | `useNotificationPreferences`  | Trust violation event pipeline           |

**Deliverable:** Real-time crossing feed, trust-based alerting

### Phase 4: Anomaly Detection

| Feature              | Hooks Leveraged              | New Backend Needed                    |
| -------------------- | ---------------------------- | ------------------------------------- |
| Baseline calculation | —                            | Scheduled job: compute zone baselines |
| Anomaly detection    | —                            | Service: compare activity to baseline |
| Anomaly alerts       | `useNotificationPreferences` | WebSocket: `zone.anomaly`             |

**Deliverable:** Pattern-based anomaly alerts

### Phase 5: Entry Points

| Entry Point            | Components Used           | Effort                    |
| ---------------------- | ------------------------- | ------------------------- |
| Enhanced Zone Editor   | All Phase 1-3 components  | Medium (extend existing)  |
| Zone Intelligence Page | All components            | Medium (new page)         |
| Camera View Overlay    | Subset (Presence, Alerts) | Low (overlay on existing) |

**Deliverable:** Three integrated entry points

---

## Hook Utilization Summary

| Hook                         | Current Uses | After Implementation           |
| ---------------------------- | ------------ | ------------------------------ |
| `useZones`                   | 1            | 8+ (all zone components)       |
| `useTimelineData`            | 0            | 3 (heatmap, scrubber, cards)   |
| `useRiskHistoryQuery`        | 0            | 2 (scrubber, analytics)        |
| `useHouseholdApi`            | 0            | 5 (ownership, trust, presence) |
| `useNotificationPreferences` | 0            | 3 (zone alerts config)         |
| `usePrometheusAlerts`        | 0            | 1 (health indicator)           |
| `useWorkerEvents`            | 0            | 1 (health indicator)           |
| `useAuditLogsInfiniteQuery`  | 0            | 1 (zone change history)        |
| `useExportJobs`              | 0            | 1 (analytics export)           |
| `useInteractionTracking`     | 0            | Throughout (UX analytics)      |

### Hooks Not Addressed

| Hook                    | Potential Future Use                           |
| ----------------------- | ---------------------------------------------- |
| `useTrashQuery`         | "Recently deleted zones" recovery              |
| `usePromptImportExport` | Separate feature (AI prompt management)        |
| `useServiceMutations`   | Health indicator drill-down (restart services) |

---

## Linear Issue Updates

### NEM-3181: Audit and cleanup 18 underutilized hooks

**Reframed:** Instead of removing hooks, leverage them to enhance the zone intelligence system.

- 10 of 18 hooks will be actively used
- 3 hooks have clear future applications
- Remaining hooks to be evaluated for separate features

### NEM-3178: Implement visual zone editor for detection zones

**Expanded:** Enhanced zone editor is Phase 5 of the larger Zone Intelligence System.

- Original scope (visual polygon editor) already exists
- New scope: Add intelligence panels, household integration, activity visualization

---

## Open Questions

1. **Face/plate recognition**: Does the current AI pipeline support matching detections to household members?
2. **Performance**: How will heatmap aggregation scale with high detection volumes?
3. **Mobile**: Should Zone Intelligence Page be mobile-responsive or desktop-only?
