# Dashboard Basics

> Understanding the main security dashboard layout and components.

**Time to read:** ~8 min
**Prerequisites:** None

---

## First Look

When you open the dashboard, you see the main Security Dashboard page. This is your home base for monitoring everything happening around your property. The system automatically watches your cameras, detects movement, and uses AI to assess whether activity might be a security concern.

---

## Dashboard Layout

The dashboard is organized into clear sections:

```
+--------------------------------------------------+
|  HEADER: Logo | Live Status | GPU Stats           |
+--------+---------------------------------------+
| SIDEBAR| MAIN CONTENT                         |
|        |                                      |
| [Dash] | Security Dashboard                   |
| [Time] | +----+ +----+ +----+ +----+          |
| [Ent]  | | Cam | | Evts| | Risk| | Sys |      |
| [Alrt] | +----+ +----+ +----+ +----+          |
| [Logs] |                                      |
| [Syst] | +------------+ +--------------+      |
| [Sett] | | RISK GAUGE | | GPU STATS    |      |
|        | +------------+ +--------------+      |
|        |                                      |
|        | CAMERA GRID                          |
|        | +------+ +------+ +------+           |
|        | | Cam1 | | Cam2 | | Cam3 |           |
|        | +------+ +------+ +------+           |
|        |                                      |
|        | LIVE ACTIVITY FEED                   |
|        | +--------------------------------+   |
|        | | Event 1 | Event 2 | Event 3    |   |
|        | +--------------------------------+   |
+--------+---------------------------------------+
```

---

## Header Bar

At the very top of the screen:

| Element         | Description                            |
| --------------- | -------------------------------------- |
| **Logo**        | Green NVIDIA Security logo on the left |
| **Live Status** | Colored dot showing system health      |
| **GPU Stats**   | Graphics card usage (powers AI)        |

### System Health Indicator

The status dot shows whether the system is working:

| Color         | Label             | Meaning               |
| ------------- | ----------------- | --------------------- |
| Green pulsing | "LIVE MONITORING" | Everything working    |
| Yellow        | "System Degraded" | Some features slow    |
| Red           | "System Offline"  | Contact administrator |

Hover over the status indicator to see individual service health.

---

## Sidebar Navigation

The left sidebar has buttons to different areas:

| Button        | What It Does                         |
| ------------- | ------------------------------------ |
| **Dashboard** | Main overview (you are here)         |
| **Timeline**  | All past events with filters         |
| **Entities**  | Tracked people/objects (coming soon) |
| **Alerts**    | High-priority events only            |
| **Logs**      | Technical logs                       |
| **System**    | Performance monitoring               |
| **Settings**  | Configuration options                |

The current page is highlighted in bright green.

---

## Quick Stats Row

Four cards showing key numbers at a glance:

### Active Cameras

How many cameras are online and working. Camera icon appears next to the count.

### Events Today

Total security events detected since midnight. Helps understand how busy cameras have been.

### Current Risk Score

Risk score from the most recent event with a shield icon. Color changes based on risk level.

### System Status

Overall system health:

- **Online** (green pulsing dot) - Working normally
- **Degraded** (yellow dot) - Some issues
- **Offline** (red dot) - Needs attention
- **Unknown** (gray dot) - Cannot determine status

---

## Risk Gauge

The circular dial showing current security risk level.

### What the Number Means

The gauge displays a number from **0 to 100**:

| Score Range | Level               | What It Means              |
| ----------- | ------------------- | -------------------------- |
| 0-29        | **Low** (Green)     | Normal activity            |
| 30-59       | **Medium** (Yellow) | Something to be aware of   |
| 60-84       | **High** (Orange)   | Check it out               |
| 85-100      | **Critical** (Red)  | Immediate attention needed |

### Reading the Gauge

- **Large number in center** - Current risk score
- **Colored arc** - Fills based on score (more = higher risk)
- **Text label below** - Says "Low", "Medium", "High", or "Critical"
- **Sparkline chart** - Shows how risk changed over recent events

The gauge glows when risk is High or Critical.

---

## Camera Grid

Shows all your security cameras in a visual grid layout.

### Camera Card Contents

Each camera appears as a rectangular card with:

1. **Thumbnail Image** - Recent snapshot (updates periodically)
2. **Status Badge** - Top-right corner showing:
   - **Online** (green dot) - Working and sending images
   - **Recording** (yellow dot) - Actively recording motion
   - **Offline** (gray dot) - Not responding
   - **Error** (red dot) - Has a problem
3. **Camera Name** - Friendly name at bottom
4. **Last Seen Time** - When camera last sent an image

### Interacting with Cameras

- Click a camera card to select it and see more details
- Selected cameras have a bright green border and glow
- No thumbnail? You see a camera icon placeholder

### Layout Responsiveness

Cameras arrange based on screen size:

- Phones: 1 camera per row
- Tablets: 2 cameras per row
- Desktop: Up to 4 cameras per row

---

## GPU Statistics

Shows the graphics card performance powering the AI:

- **Utilization** - How busy the GPU is
- **Temperature** - GPU heat level
- **Memory** - How much VRAM is used

---

## Next Steps

- [Viewing Events](viewing-events.md) - Understanding the activity feed and event details
- [Understanding Alerts](understanding-alerts.md) - What risk levels mean
- [Back to User Hub](../user-hub.md)
