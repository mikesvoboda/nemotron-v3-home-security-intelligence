# Dashboard Settings

> Configure cameras, processing options, and system preferences.

**Time to read:** ~5 min
**Prerequisites:** [Dashboard Basics](dashboard-basics.md)

---

## Accessing Settings

Click **Settings** in the left sidebar to open the configuration page.

---

## Settings Tabs

The settings page has three tabs:

### Cameras Tab

View and manage your connected cameras:

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
- [Back to User Hub](../user-hub.md)
