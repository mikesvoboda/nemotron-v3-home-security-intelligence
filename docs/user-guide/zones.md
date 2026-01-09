---
title: Detection Zones
description: Configure detection zones to focus AI analysis on areas that matter most
source_refs:
  - frontend/src/components/settings/ZoneEditor.tsx
  - backend/api/routes/zones.py
---

# Detection Zones

Detection zones let you define specific areas within each camera view for focused monitoring. Instead of analyzing the entire frame, the AI pays special attention to activity in your designated zones like entry points, driveways, or restricted areas.

---

## Why Use Zones?

Zones help you:

- **Reduce false positives**: Ignore motion from roads, sidewalks, or trees
- **Prioritize areas**: Get higher-priority alerts for entry points
- **Organize detections**: See which zone triggered each detection
- **Customize sensitivity**: Different zones can have different importance levels

### Without Zones vs. With Zones

| Scenario                   | Without Zones          | With Zones                         |
| -------------------------- | ---------------------- | ---------------------------------- |
| Car on street              | Medium alert           | Ignored (not in monitored zone)    |
| Person at front door       | Generic "person" alert | "Person in Entry Point zone" alert |
| Tree branches moving       | Motion detected        | Ignored (not in monitored zone)    |
| Someone in restricted area | Standard detection     | High-priority "Restricted" alert   |

---

## Zone Types

Each zone has a type that helps the AI understand its purpose:

| Type          | Icon | Best For                               |
| ------------- | ---- | -------------------------------------- |
| `entry_point` | Door | Doors, gates, garage entries           |
| `driveway`    | Car  | Driveways, parking areas               |
| `walkway`     | Path | Sidewalks, paths, patios               |
| `restricted`  | Lock | Backyards, private areas, secure zones |
| `perimeter`   | Edge | Property boundaries, fence lines       |
| `other`       | Pin  | Any other area you want to monitor     |

---

## Creating Zones

### Step 1: Navigate to Zone Editor

1. Go to **Settings** in the sidebar
2. Click the **Cameras** tab
3. Find your camera and click the **Zones** button (map icon)

### Step 2: Draw Your Zone

1. Click **Add Zone** button
2. Select the zone type from the dropdown
3. Click and drag on the camera preview to draw a rectangle
4. Adjust corners by dragging the handles

### Step 3: Configure Zone Settings

| Setting  | Description                                 |
| -------- | ------------------------------------------- |
| Name     | Descriptive name (e.g., "Front Porch")      |
| Type     | Zone category (entry point, driveway, etc.) |
| Color    | Visual color for the zone overlay           |
| Priority | 0-100 (higher = more important)             |
| Enabled  | Toggle zone on/off without deleting         |

### Step 4: Save

Click **Save Zone** to apply your changes. The zone takes effect immediately.

---

## Managing Zones

### Editing Zones

1. Click on an existing zone in the list
2. Modify settings or drag zone boundaries
3. Click **Save** to apply changes

### Disabling vs. Deleting

- **Disable**: Turn off temporarily; zone definition preserved
- **Delete**: Permanently remove the zone

Use disable when you want to:

- Test if the zone is causing too many alerts
- Temporarily pause monitoring during known activity
- Compare detection accuracy with and without the zone

### Reordering Priority

Higher priority zones (0-100) take precedence when detections occur in overlapping zones. A detection in multiple zones is associated with the highest-priority zone.

---

## Zone Best Practices

### Do

- **Name zones clearly**: "Front Door Entry" is better than "Zone 1"
- **Focus on entry points**: Doors and gates deserve dedicated zones
- **Exclude high-motion areas**: Roads, sidewalks, and tree lines
- **Use multiple small zones**: Better than one large zone
- **Test and iterate**: Review detections and adjust zone boundaries

### Don't

- **Cover entire frame**: Defeats the purpose of zones
- **Overlap zones excessively**: Can make detection attribution confusing
- **Set all zones to high priority**: Use priority levels meaningfully
- **Forget to save**: Changes require clicking Save

---

## Zone Shapes

### Rectangle (Default)

Best for most use cases:

- Doorways and entry points
- Driveways and parking spots
- Simple rectangular areas

**How to draw:** Click and drag to create a box

### Polygon (Advanced)

For irregular areas:

- Curved driveways
- Property boundaries
- Areas avoiding obstacles

**How to draw:** Click to place points, close shape by clicking first point

---

## Viewing Zone Activity

### In the Timeline

Events show which zone was involved:

```
Front Door Camera
Zone: Front Porch (entry_point)
Risk: Medium (45)
"Person approached front door and waited"
```

### In Event Details

The Event Detail Modal shows:

- Zone name and type
- Detection coordinates within the zone
- Time spent in zone (for tracked objects)

---

## Coordinate System

Zones use **normalized coordinates** (0.0 to 1.0):

| Position     | Coordinates |
| ------------ | ----------- |
| Top-left     | (0.0, 0.0)  |
| Top-right    | (1.0, 0.0)  |
| Bottom-left  | (0.0, 1.0)  |
| Bottom-right | (1.0, 1.0)  |
| Center       | (0.5, 0.5)  |

This means zones work regardless of camera resolution - a zone at (0.2, 0.3) to (0.8, 0.7) covers the same relative area on any camera.

---

## Example Zone Configurations

### Front Door Camera

| Zone Name  | Type        | Priority | Purpose               |
| ---------- | ----------- | -------- | --------------------- |
| Door Entry | entry_point | 90       | Direct door approach  |
| Porch Area | walkway     | 70       | Standing/waiting area |
| Driveway   | driveway    | 50       | Vehicle arrival       |

### Backyard Camera

| Zone Name  | Type        | Priority | Purpose                |
| ---------- | ----------- | -------- | ---------------------- |
| Back Door  | entry_point | 90       | Entry point            |
| Patio      | walkway     | 60       | Seating/gathering area |
| Fence Line | perimeter   | 80       | Property boundary      |
| Pool Area  | restricted  | 95       | Safety-critical zone   |

### Garage Camera

| Zone Name   | Type        | Priority | Purpose            |
| ----------- | ----------- | -------- | ------------------ |
| Side Door   | entry_point | 90       | Pedestrian entry   |
| Garage Door | entry_point | 85       | Vehicle entry      |
| Tool Area   | restricted  | 80       | Valuable equipment |

---

## Troubleshooting

### Zone Not Triggering

**Check:**

- Is the zone enabled?
- Is the zone large enough to cover the area?
- Does the camera resolution support the zone size?
- Is the object actually within zone boundaries?

### Too Many Alerts from Zone

**Try:**

- Shrink the zone to focus on the most critical area
- Lower the zone priority
- Check for overlapping zones
- Consider if this zone type should generate fewer alerts

### Zone Appears in Wrong Position

**Causes:**

- Camera angle changed after zone creation
- Different resolution between preview and live feed

**Fix:** Re-draw the zone using the current camera feed

### Detections Not Attributed to Zones

**Check:**

- Zone is enabled
- Zone covers the detection location
- Detection confidence meets threshold

---

## Related Documentation

- [Getting Started Tour](getting-started-tour.md) - Initial zone setup
- [Alerts & Notifications](alerts-notifications.md) - How zones affect alerting
- [Understanding Alerts](understanding-alerts.md) - Risk scoring with zones
- [Zones API](../api-reference/zones.md) - Technical API reference

---

[Back to User Hub](../user-hub.md)
