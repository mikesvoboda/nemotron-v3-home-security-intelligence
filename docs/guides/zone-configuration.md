# Zone Configuration Guide

Complete guide to configuring and using detection zones for focused security monitoring.

## Overview

Detection zones allow you to define specific regions within camera views for targeted AI analysis. Instead of processing the entire frame equally, zones help the AI prioritize activity in designated areas like entry points, driveways, and restricted areas.

![Zone Intelligence](../images/concepts/zone-intelligence.png)

### Benefits of Using Zones

| Benefit                     | Description                                    |
| --------------------------- | ---------------------------------------------- |
| **Reduced false positives** | Ignore motion from roads, sidewalks, trees     |
| **Prioritized alerts**      | Higher-priority notifications for entry points |
| **Organized detections**    | See which zone triggered each detection        |
| **Custom sensitivity**      | Different importance levels per area           |
| **Household integration**   | Link zones to household members                |
| **Activity tracking**       | Monitor dwell time and crossing events         |

---

## Zone Types

Each zone has a type that affects AI behavior and alert prioritization:

| Type          | Color  | Best For                        | Alert Priority |
| ------------- | ------ | ------------------------------- | -------------- |
| `entry_point` | Red    | Doors, gates, garage entries    | Highest        |
| `driveway`    | Orange | Driveways, vehicle access areas | High           |
| `sidewalk`    | Blue   | Sidewalks, walkways             | Medium         |
| `yard`        | Green  | Yards, lawn areas               | Medium         |
| `other`       | Gray   | Miscellaneous areas             | Low            |

> **Note:** These are CameraZone types. PolygonZone (analytics zones) uses a different set of types: monitored, excluded, restricted.

### Zone Types Comparison

The system uses two distinct zone models. **CameraZone** provides semantic labels for risk context (stored in the `camera_zones` table), while **PolygonZone** defines geometric regions for dwell time and crossing analytics (stored in the `analytics_zone` table).

```mermaid
flowchart LR
    subgraph CZ["CameraZone<br/>(camera_zones table)"]
        direction TB
        CZ1[entry_point]
        CZ2[driveway]
        CZ3[sidewalk]
        CZ4[yard]
        CZ5[other]
    end
    subgraph PZ["PolygonZone<br/>(analytics_zone table)"]
        direction TB
        PZ1[monitored]
        PZ2[excluded]
        PZ3[restricted]
    end
    CZ -->|"Semantic labeling<br/>for risk context"| RISK[Risk Scoring]
    PZ -->|"Geometric regions<br/>for dwell/crossing analytics"| ANALYTICS[Zone Analytics]
```

### Zone Type Decision Tree

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart TD
    START["What is the primary<br/>purpose of this area?"]

    START --> ENTRY{"Entry/Exit<br/>to property?"}
    START --> DRIVE{"Vehicle<br/>access?"}
    START --> WALK{"Pedestrian<br/>path?"}
    START --> YARD_Q{"Yard/lawn<br/>area?"}
    START --> OTHER["None of<br/>the above"]

    ENTRY --> EP1[entry_point]
    DRIVE --> DW[driveway]
    WALK --> SW[sidewalk]
    YARD_Q --> YD[yard]
    OTHER --> OTH[other]

    style EP1 fill:#EF4444,color:#fff
    style DW fill:#F97316,color:#fff
    style SW fill:#3B82F6,color:#fff
    style YD fill:#22C55E,color:#fff
    style OTH fill:#6B7280,color:#fff
```

---

## Creating Zones

### Using the Zone Editor

1. Navigate to **Settings > Cameras**
2. Click the map pin icon on the camera card
3. The Zone Editor opens with camera snapshot

### Drawing Rectangle Zones (Recommended)

Best for most use cases:

1. Click the **Rectangle** button in the toolbar
2. Click and hold at one corner
3. Drag to the opposite corner
4. Release to complete
5. Configure zone settings in the form

### Drawing Polygon Zones

For irregular areas:

1. Click the **Polygon** button
2. Click to place each vertex point
3. Continue clicking to add points
4. Double-click to close the shape
5. Configure zone settings

### Zone Form Settings

| Field        | Requirements         | Example            |
| ------------ | -------------------- | ------------------ |
| **Name**     | 1-50 characters      | "Front Door Entry" |
| **Type**     | Select from dropdown | entry_point        |
| **Color**    | Choose from 8 colors | Red (#EF4444)      |
| **Priority** | 0-100 slider         | 90                 |
| **Enabled**  | Toggle on/off        | Enabled            |

### Priority Guidelines

| Priority | Usage                               |
| -------- | ----------------------------------- |
| 0-30     | Informational zones, low importance |
| 31-60    | Standard monitoring, routine areas  |
| 61-85    | Important areas, approach zones     |
| 86-100   | Critical areas, entry points        |

---

## Zone Intelligence Features

### Dwell Time Tracking

The system tracks how long objects remain in zones:

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'secondaryColor': '#A855F7',
    'tertiaryColor': '#009688',
    'background': '#121212',
    'mainBkg': '#1a1a2e',
    'lineColor': '#666666'
  }
}}%%
flowchart LR
    ENTER["Detection<br/>enters zone"]
    TIMER["Timer<br/>starts"]
    LEAVE["Detection<br/>leaves zone"]
    RECORD["Dwell time<br/>recorded"]
    ALERT{"Dwell<br/>threshold?"}
    NORMAL["Normal<br/>activity"]
    EXTENDED["Extended<br/>dwell alert"]
    PROLONGED["Prolonged<br/>dwell alert"]

    ENTER --> TIMER
    TIMER --> LEAVE
    LEAVE --> RECORD
    RECORD --> ALERT
    ALERT -->|"< 2x baseline"| NORMAL
    ALERT -->|"2-5x baseline"| EXTENDED
    ALERT -->|"> 5x baseline"| PROLONGED

    style NORMAL fill:#22C55E,color:#fff
    style EXTENDED fill:#F59E0B,color:#fff
    style PROLONGED fill:#EF4444,color:#fff
```

**Dwell Time Alerts:**

- Normal dwell: No alert
- Extended dwell (2x baseline): Medium alert
- Prolonged dwell (5x baseline): High alert

**Configuration:**

```json
{
  "dwell_threshold_seconds": 30,
  "extended_dwell_multiplier": 2.0,
  "prolonged_dwell_multiplier": 5.0
}
```

### Line Crossing Detection

Detects when objects cross zone boundaries:

| Event          | Description                           |
| -------------- | ------------------------------------- |
| `zone.entered` | Object crossed from outside to inside |
| `zone.exited`  | Object crossed from inside to outside |

**WebSocket Events:**

```json
{
  "type": "zone.entered",
  "data": {
    "zone_id": "uuid",
    "zone_name": "Front Door",
    "zone_type": "entry_point",
    "entity_type": "person",
    "timestamp": "2026-01-26T14:30:00Z"
  }
}
```

### Approach Vector Calculation

The system calculates if objects are approaching zones:

```json
{
  "is_approaching": true,
  "direction_degrees": 45.0,
  "speed_normalized": 0.02,
  "distance_to_zone": 0.15,
  "estimated_arrival_seconds": 7.5
}
```

**Direction Convention:**

- 0 degrees = Moving up (toward top of frame)
- 90 degrees = Moving right
- 180 degrees = Moving down
- 270 degrees = Moving left

---

## Household Integration

### Zone Ownership

Assign zones to household members:

```json
{
  "zone_id": "uuid",
  "owner_id": "member-uuid",
  "allowed_member_ids": ["member-1", "member-2"],
  "allowed_vehicle_ids": ["vehicle-1"]
}
```

**Owner Benefits:**

- Receives all notifications for this zone
- Can customize zone-specific alert settings
- Visual badge shows owner avatar

### Trust Configuration

Configure who triggers alerts in which zones:

| Trust Level       | Behavior                                  |
| ----------------- | ----------------------------------------- |
| **Full Trust**    | No alerts (family members)                |
| **Partial Trust** | Alerts outside schedule (service workers) |
| **Monitor**       | Log only, no notifications                |
| **Unknown**       | Full alerts based on zone type            |

**Trust Matrix Example:**

```
                    | Driveway | Front Door | Backyard | Garage |
--------------------|----------|------------|----------|--------|
Family (full trust) |    OK    |     OK     |    OK    |   OK   |
Service (partial)   |    OK    |     OK     | 9-5 only |  ALERT |
Unknown             |  ALERT   |   ALERT    |  ALERT   | ALERT  |
```

### Schedule-Based Access

Configure time-based trust rules:

```json
{
  "member_ids": ["service-worker-1"],
  "schedule": {
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "start_time": "09:00",
    "end_time": "17:00",
    "timezone": "America/New_York"
  }
}
```

---

## Zone API Reference

### List Zones

```bash
GET /api/cameras/{camera_id}/zones
```

**Query Parameters:**

| Parameter | Type    | Description              |
| --------- | ------- | ------------------------ |
| `enabled` | Boolean | Filter by enabled status |

**Response:** `ZoneListResponse` — `items` plus `pagination`
(`backend/api/schemas/zone.py`):

```json
{
  "items": [
    {
      "id": "uuid",
      "camera_id": "front_door",
      "name": "Front Porch",
      "zone_type": "entry_point",
      "shape": "rectangle",
      "coordinates": [
        [0.1, 0.2],
        [0.9, 0.2],
        [0.9, 0.8],
        [0.1, 0.8]
      ],
      "color": "#EF4444",
      "priority": 90,
      "enabled": true,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ],
  "pagination": { "total": 1, "limit": 50, "offset": 0, "has_more": false }
}
```

### Create Zone

```bash
POST /api/cameras/{camera_id}/zones
Content-Type: application/json

{
  "name": "Front Porch",
  "zone_type": "entry_point",
  "shape": "rectangle",
  "coordinates": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]],
  "color": "#EF4444",
  "priority": 90,
  "enabled": true
}
```

### Update Zone

```bash
PUT /api/cameras/{camera_id}/zones/{zone_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "priority": 95
}
```

### Delete Zone

```bash
DELETE /api/cameras/{camera_id}/zones/{zone_id}
```

### Zone Household Config

```bash
# Get household config for zone
GET /api/zones/{zone_id}/household

# Update household config
PUT /api/zones/{zone_id}/household
{
  "owner_id": "member-uuid",
  "allowed_member_ids": ["member-1", "member-2"]
}
```

---

## Zone Anomalies And Baselines API

Zone anomalies are raised when activity in a zone deviates from the baseline the
`ZoneAnomalyService` maintains for it (`backend/services/zone_anomaly_service.py`,
model `backend/models/zone_anomaly.py`; the baseline rows live in the
`zone_activity_baselines` table).

### List Anomalies For One Zone

```bash
GET /api/zones/{zone_id}/anomalies
```

**Query Parameters:**

| Parameter             | Type    | Default | Description                     |
| --------------------- | ------- | ------- | ------------------------------- |
| `severity`            | string  | -       | Filter by severity (repeatable) |
| `unacknowledged_only` | Boolean | `false` | Only unacknowledged anomalies   |
| `since`               | string  | -       | Lower time bound (ISO 8601)     |
| `until`               | string  | -       | Upper time bound (ISO 8601)     |
| `limit`               | Integer | `50`    | Page size (1-500)               |
| `offset`              | Integer | `0`     | Results to skip                 |

**Response shape** (`ZoneAnomalyListResponse`: `items` + `pagination`, each item
a `ZoneAnomalyResponse` in `backend/api/schemas/zone_anomaly.py`):

```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "zone_id": "456e7890-e89b-12d3-a456-426614174001",
      "camera_id": "front_door",
      "anomaly_type": "unusual_time",
      "severity": "warning",
      "title": "Unusual activity at 03:15",
      "description": "Activity detected in Front Door at 03:15 when typical activity is 0.1.",
      "expected_value": 0.1,
      "actual_value": 1.0,
      "deviation": 3.5,
      "detection_id": 12345,
      "thumbnail_url": "/api/detections/12345/image",
      "acknowledged": false,
      "acknowledged_at": null,
      "acknowledged_by": null,
      "timestamp": "2025-01-24T03:15:00Z"
    }
  ],
  "pagination": { "total": 1, "limit": 50, "offset": 0, "has_more": false }
}
```

### The Other Anomaly Routes

```bash
GET    /api/zones/anomalies                                  # across all zones, same filters
POST   /api/zones/anomalies/{anomaly_id}/acknowledge         # acknowledge one
GET    /api/zones/anomalies/{anomaly_id}/context             # anomaly + investigation context
```

### Camera-Level Baseline

The hourly / day-of-week baseline aggregates are exposed per camera, not per
zone (`backend/api/routes/cameras.py`, prefix `/api/cameras`):

```bash
GET  /api/cameras/{camera_id}/baseline            # summary: hourly + daily patterns, deviation
GET  /api/cameras/{camera_id}/baseline/anomalies  # anomalies for the camera
GET  /api/cameras/{camera_id}/baseline/activity   # activity baseline detail
GET  /api/cameras/{camera_id}/baseline/classes    # per-object-class baseline
GET  /api/cameras/{camera_id}/baseline/config     # baseline configuration
PUT  /api/cameras/{camera_id}/baseline/config     # change configuration
POST /api/cameras/{camera_id}/baseline/reset      # discard and relearn
```

---

## Coordinate System

Zones use **normalized coordinates** (0.0 to 1.0):

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#3B82F6',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#60A5FA',
    'background': '#121212',
    'mainBkg': '#1a1a2e'
  }
}}%%
graph TD
    subgraph Frame["Camera Frame (Normalized)"]
        TL["(0.0, 0.0)<br/>Top Left"]
        TR["(1.0, 0.0)<br/>Top Right"]
        CTR["(0.5, 0.5)<br/>Center"]
        BL["(0.0, 1.0)<br/>Bottom Left"]
        BR["(1.0, 1.0)<br/>Bottom Right"]
    end

    TL --- TR
    TL --- BL
    TR --- BR
    BL --- BR
    TL -.-> CTR
    TR -.-> CTR
    BL -.-> CTR
    BR -.-> CTR

    style TL fill:#3B82F6,color:#fff
    style TR fill:#3B82F6,color:#fff
    style BL fill:#3B82F6,color:#fff
    style BR fill:#3B82F6,color:#fff
    style CTR fill:#A855F7,color:#fff
```

**Why Normalized?**

Zones work regardless of camera resolution. A zone at (0.2, 0.3) to (0.8, 0.7) covers the same relative area whether your camera is 720p or 4K.

**Coordinate Validation:**

- All coordinates must be between 0.0 and 1.0
- Minimum 3 vertices for polygon zones
- Coordinates should form a valid, non-self-intersecting shape

---

## Example Zone Configurations

### Front Door Camera

```json
[
  {
    "name": "Front Door",
    "zone_type": "entry_point",
    "priority": 95,
    "color": "#EF4444",
    "rationale": "Critical - direct entry point"
  },
  {
    "name": "Front Porch",
    "zone_type": "entry_point",
    "priority": 80,
    "color": "#EF4444",
    "rationale": "High priority approach area"
  },
  {
    "name": "Front Walk",
    "zone_type": "monitored",
    "priority": 50,
    "color": "#3B82F6",
    "rationale": "Standard foot traffic monitoring"
  }
]
```

### Driveway Camera

```json
[
  {
    "name": "Garage Door",
    "zone_type": "entry_point",
    "priority": 90,
    "color": "#EF4444",
    "rationale": "Critical access point"
  },
  {
    "name": "Driveway",
    "zone_type": "monitored",
    "priority": 60,
    "color": "#F59E0B",
    "rationale": "Vehicle activity monitoring"
  }
]
```

### Backyard Camera

```json
[
  {
    "name": "Back Door",
    "zone_type": "entry_point",
    "priority": 95,
    "color": "#EF4444",
    "rationale": "Critical entry point"
  },
  {
    "name": "Pool Area",
    "zone_type": "restricted",
    "priority": 90,
    "color": "#EF4444",
    "rationale": "Safety critical - child/pet alert"
  },
  {
    "name": "Fence Line",
    "zone_type": "monitored",
    "priority": 75,
    "color": "#10B981",
    "rationale": "Perimeter breach detection"
  },
  {
    "name": "Patio",
    "zone_type": "other",
    "priority": 40,
    "color": "#3B82F6",
    "rationale": "Known activity area"
  }
]
```

---

## Best Practices

### Do

| Practice                  | Benefit                                 |
| ------------------------- | --------------------------------------- |
| Name zones clearly        | "Front Door Entry" vs "Zone 1"          |
| Focus on entry points     | Doors/gates deserve dedicated zones     |
| Exclude high-motion areas | Roads, tree lines, busy sidewalks       |
| Use multiple small zones  | Better precision than one large zone    |
| Test and iterate          | Review detections, adjust boundaries    |
| Set meaningful priorities | Reserve high values for critical areas  |
| Configure household       | Reduce false positives for known people |

### Don't

| Practice                  | Problem                             |
| ------------------------- | ----------------------------------- |
| Cover entire frame        | Defeats the purpose of zones        |
| Overlap zones excessively | Confuses detection attribution      |
| Set all zones to 100      | No way to prioritize                |
| Delete instead of disable | Lose zone configuration permanently |
| Ignore zone analytics     | Miss optimization opportunities     |

---

## Troubleshooting

### Zone Not Triggering

**Check:**

1. Is the zone enabled? (eye icon is open)
2. Is the zone large enough to cover the area?
3. Is the object actually within zone boundaries?
4. Is the camera online and processing?

**Fix:** Edit zone to expand boundaries or verify enabled state.

### Too Many Alerts from Zone

**Try:**

1. Shrink the zone to focus on critical area
2. Lower the zone priority
3. Check for overlapping zones
4. Add household members to reduce false positives
5. Configure trust rules for expected visitors

### Detections Not Attributed to Zones

**Check:**

1. Zone is enabled
2. Zone covers the detection location
3. Detection confidence meets threshold
4. No higher-priority overlapping zone

### Zone Appears in Wrong Position

**Causes:**

- Camera angle changed after zone creation
- Different resolution between preview and live feed

**Fix:** Delete and re-draw the zone using current camera feed.

---

## Related Documentation

- [Video Analytics Guide](video-analytics.md) - AI pipeline overview
- [Face Recognition Guide](face-recognition.md) - Person identification
- [Detection Zones UI](../ui/zones.md) - User interface guide
