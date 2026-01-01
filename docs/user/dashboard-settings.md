# Dashboard Settings

> Configure cameras, processing options, and system preferences.

**Time to read:** ~5 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Accessing Settings

Click **Settings** in the left sidebar to open the configuration page.

<!-- SCREENSHOT: Settings Page Overview
Location: Settings page (click Settings in sidebar)
Shows: Settings page with three tabs (CAMERAS, PROCESSING, AI MODELS), Cameras tab selected (green background), camera list table showing cameras with name, folder path, status indicators, last seen, and action buttons
Size: 1200x700 pixels (12:7 aspect ratio)
Alt text: Settings page with tabbed navigation showing Cameras, Processing, and AI Models tabs, with camera configuration table displayed
-->
<!-- Image placeholder - settings page screenshot would go here -->

_Caption: The Settings page lets you configure cameras, processing options, and view AI status._

---

## Settings Tabs

The settings page has three tabs:

### Cameras Tab

View and manage your connected cameras:

<!-- SCREENSHOT: Cameras Settings Tab
Location: Settings page > Cameras tab
Shows: Camera list table with columns: Name (e.g., "Front Door", "Backyard"), Folder Path, Status badge (Online/green, Offline/gray), Last Seen timestamp, and Action buttons (Edit pencil, Delete trash)
Size: 1000x400 pixels (2.5:1 aspect ratio)
Alt text: Camera settings table showing configured cameras with their names, paths, status indicators, and edit/delete action buttons
-->
<!-- Image placeholder - cameras tab screenshot would go here -->

_Caption: The Cameras tab shows all your connected cameras and their status._

- **Camera List** - All registered cameras with status
- **Camera Status** - Online, offline, or error
- **Last Activity** - When camera last sent an image
- **Configuration** - Camera-specific settings

**Actions:**

- View camera details
- Check connection status
- See recent activity

---

### Processing Tab

Configure how events are processed:

| Setting                   | Description                                    |
| ------------------------- | ---------------------------------------------- |
| **Detection Sensitivity** | How confident AI must be to register detection |
| **Batch Window**          | How long to group related detections (seconds) |
| **Idle Timeout**          | How long to wait before closing a batch        |
| **Retention**             | How long events are kept (default: 30 days)    |

**Note:** Processing settings are typically managed by administrators. Contact whoever set up your system to request changes.

---

### AI Models Tab

View AI model status:

<!-- SCREENSHOT: AI Models Settings Tab
Location: Settings page > AI Models tab
Shows: Two model cards (RT-DETRv2 Object Detection and Nemotron Risk Analysis), each showing status badge (Loaded/green), memory usage, inference speed/FPS. Bottom section showing total GPU memory usage bar
Size: 1000x500 pixels (2:1 aspect ratio)
Alt text: AI Models settings showing RT-DETRv2 and Nemotron model cards with status indicators, memory usage, and performance metrics
-->
<!-- Image placeholder - AI models tab screenshot would go here -->

_Caption: The AI Models tab shows the status of your AI detection and analysis models._

- **RT-DETRv2** - Object detection model status
- **Nemotron** - Risk analysis model status
- **GPU** - Graphics card utilization
- **Health** - Service health indicators

**Status Indicators:**

- Green checkmark: Service healthy
- Yellow warning: Service degraded
- Red X: Service unavailable

---

## Quick Reference

### Status Indicators

| Indicator     | Meaning                      |
| ------------- | ---------------------------- |
| Pulsing dot   | System active and working    |
| Solid dot     | Status indicator (see color) |
| Spinning icon | Loading or refreshing        |

### Keyboard Shortcuts

When viewing event details:

| Key         | Action         |
| ----------- | -------------- |
| Left Arrow  | Previous event |
| Right Arrow | Next event     |
| Escape      | Close popup    |

### Common Actions

| I want to...               | Do this...                             |
| -------------------------- | -------------------------------------- |
| See what just happened     | Look at Live Activity feed             |
| Find old events            | Go to Timeline and use filters         |
| See urgent items only      | Go to Alerts page                      |
| Mark something as reviewed | Click event, then "Mark as Reviewed"   |
| Add notes to an event      | Click event, type in Notes, click Save |

---

## Troubleshooting

### Dashboard not loading?

Try refreshing your browser (F5 or Cmd+R)

### Cameras showing offline?

Check that cameras are powered and connected to your network

### No events appearing?

Make sure cameras have activity to detect. Check if file watcher is running.

### System status showing red?

Contact whoever set up your system for assistance

---

## Getting Help

### Technical Problems

Contact your system administrator - the person who installed and maintains your system.

### Understanding Events

Review the [Understanding Alerts](understanding-alerts.md) guide for information about risk scores and what they mean.

### Emergency Situations

This system does NOT automatically contact emergency services.

- **Active emergency:** Call 911 immediately
- **Suspicious activity:** Contact local police non-emergency line

---

## Next Steps

- [Understanding Alerts](understanding-alerts.md) - Risk levels explained
- [Viewing Events](viewing-events.md) - How to review security events

---

## See Also

- [Dashboard Basics](dashboard-basics.md) - Main dashboard overview
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common problems and solutions
- [Environment Variable Reference](../reference/config/env-reference.md) - Configuration options (for admins)

---

[Back to User Hub](../user-hub.md)
