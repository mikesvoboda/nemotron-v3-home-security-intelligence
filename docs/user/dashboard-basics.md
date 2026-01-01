# Dashboard Basics

> Understanding the main security dashboard layout and components.

**Time to read:** ~8 min
**Prerequisites:** None

---

## First Look

When you open the dashboard, you see the main Security Dashboard page. This is your home base for monitoring everything happening around your property. The system automatically watches your cameras, detects movement, and uses AI to assess whether activity might be a security concern.

<!-- SCREENSHOT: Main Dashboard First Look
Location: Main dashboard page (http://localhost:5173/)
Shows: Complete dashboard view with all sections visible - header, sidebar, quick stats, risk gauge, camera grid, and activity feed
Size: 1400x900 pixels (16:9 aspect ratio)
Alt text: The main security dashboard showing the complete interface with navigation sidebar, quick stats cards, risk gauge, camera grid, and live activity feed
-->
<!-- Image placeholder - dashboard screenshot would go here -->

_Caption: The main Security Dashboard - your home base for monitoring your property._

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

<!-- SCREENSHOT: Header Bar with System Health
Location: Top header bar of the dashboard
Shows: The header with NVIDIA logo, "LIVE MONITORING" status indicator with green pulsing dot, and GPU stats badge. Include the tooltip popup showing service status (database, redis, detector, etc.)
Size: 800x200 pixels (4:1 aspect ratio)
Alt text: The dashboard header showing system health status with a green pulsing dot indicating live monitoring, and the tooltip displaying individual service health
-->
<!-- Image placeholder - header health screenshot would go here -->

_Caption: The header bar shows system health at a glance. Hover to see individual service status._

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

<!-- SCREENSHOT: Quick Stats Row
Location: Below the page title on the main dashboard
Shows: Four stat cards in a row: "Active Cameras" (with camera icon and count), "Events Today" (with count), "Current Risk Score" (with risk level badge), and "System Status" (with status dot)
Size: 1200x150 pixels (8:1 aspect ratio)
Alt text: Four quick stat cards showing active cameras count, events today count, current risk score with colored badge, and system status indicator
-->
<!-- Image placeholder - quick stats screenshot would go here -->

_Caption: Quick stats give you key numbers at a glance._

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

<!-- SCREENSHOT: Risk Gauge Close-up
Location: Top-left area of main dashboard content
Shows: The circular risk gauge component displaying a score (e.g., 18), with the colored arc partially filled, "Low" text label below, and the sparkline chart showing recent risk history
Size: 400x400 pixels (1:1 aspect ratio)
Alt text: Circular risk gauge showing current security risk level with score number in center, colored arc indicator, risk level label, and trend sparkline
-->
<!-- Image placeholder - risk gauge screenshot would go here -->

_Caption: The Risk Gauge shows your current security risk level at a glance._

### What the Number Means

The gauge displays a number from **0 to 100**:

| Score Range | Level               | What It Means              |
| ----------- | ------------------- | -------------------------- |
| 0-29        | **Low** (Green)     | Normal activity            |
| 30-59       | **Medium** (Yellow) | Something to be aware of   |
| 60-84       | **High** (Orange)   | Check it out               |
| 85-100      | **Critical** (Red)  | Immediate attention needed |

<!-- SCREENSHOT: Risk Gauge States Comparison
Location: N/A - composite image showing four gauge states
Shows: Four risk gauges side by side showing different states: Low (green, score ~15), Medium (yellow, score ~42), High (orange, score ~68), Critical (red with glow, score ~89)
Size: 800x250 pixels (3.2:1 aspect ratio)
Alt text: Four risk gauge examples showing Low (green), Medium (yellow), High (orange), and Critical (red) risk levels
-->
<!-- Image placeholder - risk gauge states screenshot would go here -->

_Caption: The gauge changes color based on risk level - green for low, yellow for medium, orange for high, and red for critical._

### Reading the Gauge

- **Large number in center** - Current risk score
- **Colored arc** - Fills based on score (more = higher risk)
- **Text label below** - Says "Low", "Medium", "High", or "Critical"
- **Sparkline chart** - Shows how risk changed over recent events

The gauge glows when risk is High or Critical.

---

## Camera Grid

Shows all your security cameras in a visual grid layout.

<!-- SCREENSHOT: Camera Grid View
Location: Middle section of main dashboard
Shows: Camera grid with 3-4 camera cards arranged in a row. Each card should show a thumbnail image, status badge (mix of Online/Offline), camera name, and last seen timestamp. One camera should be selected (green border)
Size: 1000x350 pixels (2.9:1 aspect ratio)
Alt text: Camera grid showing multiple security cameras with thumbnails, status indicators, and one selected camera highlighted with green border
-->
<!-- Image placeholder - camera grid screenshot would go here -->

_Caption: The Camera Grid shows all your cameras at a glance. Click any camera to select it._

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
- [Dashboard Settings](dashboard-settings.md) - Configure the system

---

## See Also

- [Risk Levels Reference](../reference/config/risk-levels.md) - Technical details on risk scoring
- [Glossary](../reference/glossary.md) - Terms and definitions

---

[Back to User Hub](../user-hub.md)
