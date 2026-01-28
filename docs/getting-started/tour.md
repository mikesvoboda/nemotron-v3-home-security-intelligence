# Product Tour and First-Time Setup

> Your guided introduction to Home Security Intelligence - learn the dashboard in minutes.

When you first open the dashboard, an interactive product tour guides you through the main features. This guide explains the tour and helps you get started with your security system.

---

## Interactive Product Tour

The product tour automatically starts the first time you visit the dashboard. It walks you through each main feature with highlighted explanations.

### Starting the Tour

The tour starts automatically for first-time users. If you want to restart it later:

1. Open the **Settings** page (press `g s` or click Settings in the sidebar)
2. The tour can be restarted by clearing your browser's localStorage for the site
3. You can also restart by opening the browser console and running:
   ```javascript
   localStorage.removeItem('nemotron-tour-completed');
   localStorage.removeItem('nemotron-tour-skipped');
   ```
4. Refresh the page - the tour will start again

### Tour Navigation

During the tour, you will see these controls:

| Button        | Action                                    |
| ------------- | ----------------------------------------- |
| **Next**      | Move to the next step                     |
| **Back**      | Return to the previous step               |
| **Skip Tour** | Exit the tour early (marks as skipped)    |
| **Close (X)** | Close the current tooltip (marks as done) |

You can also:

- **Click highlighted elements** - Most tour steps allow you to interact with the highlighted feature
- **Press Escape** - Close the current tooltip
- **Click outside** - Close the overlay

### Tour Steps Explained

The tour consists of 7 steps that introduce you to the dashboard:

#### Step 1: Welcome

**What you see:** A centered welcome message

**What it covers:** Introduction to the Nemotron Security Dashboard and what to expect from the tour.

---

#### Step 2: Risk Gauge

**What you see:** The Risk Gauge in the stats row is highlighted

**What it covers:**

- The Risk Gauge shows your current security risk level (0-100)
- AI analyzes camera detections and calculates this score
- Color coding: Green (safe) to Red (high risk)

**Why it matters:** This is your at-a-glance indicator of overall security status. Check it first when opening the dashboard.

---

#### Step 3: Camera Grid

**What you see:** The camera grid section is highlighted

**What it covers:**

- Real-time status of all connected cameras
- Each camera shows its current state (online/offline)
- Click any camera for detailed view and recent activity

**Why it matters:** Quickly verify all your cameras are working and see their latest captures.

---

#### Step 4: Activity Feed

**What you see:** The live activity feed is highlighted

**What it covers:**

- Recent detection events displayed in real-time
- Each event shows camera source, detected objects, and risk assessment
- Events are sorted by time with newest first

**Why it matters:** See what is happening across all cameras in one place without checking each individually.

---

#### Step 5: Event Timeline

**What you see:** The Timeline navigation link is highlighted

**What it covers:**

- Access to historical events
- Filter by date range, camera, or risk level
- Analyze patterns in your security footage

**Why it matters:** Review past events, investigate incidents, and understand activity patterns over time.

---

#### Step 6: Settings

**What you see:** The Settings navigation link is highlighted

**What it covers:**

- Camera configuration and management
- Notification preferences
- AI detection settings
- Option to restart this tour

**Why it matters:** Customize how the system works for your specific needs.

---

#### Step 7: Tour Complete

**What you see:** A centered completion message

**What it covers:**

- Congratulations on completing the tour
- Prompt to enable browser notifications
- Reminder that notifications provide real-time alerts for suspicious activity

**Next step:** Click "Enable Notifications" when prompted to receive alerts.

---

## First-Time Setup

After completing the tour, follow these steps to configure your system:

### 1. Enable Browser Notifications

Browser notifications alert you to security events even when the dashboard is not visible.

1. When prompted at the end of the tour, click **Enable Notifications**
2. Your browser will ask for permission - click **Allow**
3. You will now receive alerts for high-risk events

> **Note:** Notifications require a secure context (HTTPS) or localhost. If you see a "Secure Context Required" warning, contact your system administrator.

### 2. Verify Camera Connections

Check that all your cameras are connected and working:

1. Look at the **Camera Grid** on the dashboard
2. Each camera should show a green status indicator
3. If any camera shows red or offline, go to **Settings > Cameras** to troubleshoot

### 3. Review Default Settings

The system comes with sensible defaults, but you may want to adjust:

**Settings > Cameras:**

- Verify camera names are descriptive (e.g., "Front Door" instead of "Camera 1")
- Configure detection zones for each camera

**Settings > Processing:**

- **Batch Window:** How long to group detections before analysis (default: 90 seconds)
- **Confidence Threshold:** Minimum confidence for AI detections (default: 0.5)

**Settings > Notifications:**

- Configure email or webhook alerts for different risk levels
- Set quiet hours if you do not want overnight notifications

### 4. Add Detection Zones (Optional)

Detection zones let you focus AI analysis on specific areas of the camera view:

1. Go to **Settings > Cameras**
2. Click the **Zones** button for a camera
3. Draw rectangles around areas you want to monitor closely
4. Name each zone (e.g., "Driveway", "Front Porch")

Zones help reduce false alerts from areas like roads or trees moving in the wind.

---

## Understanding the Dashboard

After setup, here is what each part of the dashboard shows:

### Header Bar

| Element               | Description                                     |
| --------------------- | ----------------------------------------------- |
| **Logo**              | Click to return to dashboard from any page      |
| **Connection Status** | Green dot = live connection; Red = disconnected |
| **Theme Toggle**      | Switch between dark/light mode (if available)   |

### Sidebar Navigation

| Destination | Keyboard Shortcut | Description                       |
| ----------- | ----------------- | --------------------------------- |
| Dashboard   | `g d`             | Main overview with risk gauge     |
| Timeline    | `g t`             | Historical event browser          |
| Analytics   | `g n`             | Charts and statistics             |
| Alerts      | `g a`             | Active alerts requiring attention |
| Entities    | `g e`             | Tracked people and vehicles       |
| Logs        | `g o`             | System logs for troubleshooting   |
| System      | `g y`             | System health monitoring          |
| Settings    | `g s`             | Configuration options             |

### Quick Stats Row

The stats row at the top provides quick metrics:

| Stat          | Description                  | Click Action            |
| ------------- | ---------------------------- | ----------------------- |
| Cameras       | Number of active cameras     | Opens camera settings   |
| Events Today  | Total events detected today  | Opens event timeline    |
| Risk Level    | Current risk score and label | Opens alerts page       |
| System Status | Overall system health        | Opens system monitoring |

---

## Keyboard Shortcuts Reference

Learn these shortcuts to navigate faster. Press `?` anywhere to see the full list.

### Quick Navigation

| Shortcut       | Action                       |
| -------------- | ---------------------------- |
| `Cmd/Ctrl + K` | Open command palette         |
| `?`            | Show keyboard shortcuts help |
| `Escape`       | Close modal or cancel action |

### Page Navigation (press `g` then the second key)

| Chord | Destination |
| ----- | ----------- |
| `g d` | Dashboard   |
| `g t` | Timeline    |
| `g n` | Analytics   |
| `g a` | Alerts      |
| `g e` | Entities    |
| `g o` | Logs        |
| `g y` | System      |
| `g s` | Settings    |

### List Navigation (when viewing event lists)

| Key     | Action              |
| ------- | ------------------- |
| `j`     | Move down / Next    |
| `k`     | Move up / Previous  |
| `Home`  | Jump to first item  |
| `End`   | Jump to last item   |
| `Enter` | Select current item |

---

## Tips for New Users

1. **Check the dashboard daily** - A quick glance at the risk gauge tells you if anything needs attention
2. **Use keyboard shortcuts** - Press `Cmd/Ctrl + K` to quickly jump to any page
3. **Review high-risk events first** - Filter the timeline by "High" or "Critical" risk
4. **Enable notifications** - Do not miss important alerts when you are away from the dashboard
5. **Adjust detection zones** - Reduce false positives by focusing on areas that matter

---

## Troubleshooting First-Time Issues

### Tour Does Not Start

The tour only shows for first-time users. If it was previously completed or skipped:

1. Open browser Developer Tools (F12)
2. Go to Application > Local Storage
3. Delete keys starting with `nemotron-tour`
4. Refresh the page

### Dashboard Shows No Data

If the dashboard is empty:

1. Verify cameras are connected (**Settings > Cameras**)
2. Check system status (**System** page)
3. Wait for camera activity - the AI needs images to analyze

### Notifications Not Working

1. Check browser notification permissions (Settings > Site Permissions)
2. Ensure you are using HTTPS or localhost
3. Verify the "Secure Context Required" warning is not showing

---

## Next Steps

Now that you have completed the tour and initial setup:

- **[Dashboard](../ui/dashboard.md)** - Deep dive into dashboard features
- **[Understanding Alerts](../ui/understanding-alerts.md)** - Learn about risk levels and responses
- **[Event Timeline](../ui/timeline.md)** - Browse and search historical events
- **[Settings](../ui/settings.md)** - Full configuration guide

---

## Related Documentation

- [Keyboard Shortcuts](../ui/keyboard-shortcuts.md) - Complete shortcut reference
- [Mobile and PWA Guide](../ui/mobile-pwa.md) - Use on phone or tablet
- [Quick Start](quick-start.md) - System overview for beginners

---

_The product tour is designed to get you familiar with the dashboard in under 5 minutes. Take your time, and remember you can always press `?` for help._
