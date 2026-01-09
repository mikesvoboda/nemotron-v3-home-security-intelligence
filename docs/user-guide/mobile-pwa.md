# Mobile and PWA Guide

> Install the security dashboard on your phone or tablet and receive instant security alerts.

**Time to read:** ~10 min
**Prerequisites:** [Getting Started](getting-started.md) or "None"

---

The Nemotron Security Dashboard works as a Progressive Web App (PWA), meaning you can install it on your phone, tablet, or desktop computer and use it like a native app. You can also enable push notifications to receive security alerts even when the browser is closed.

---

## Installing as a PWA

Installing the dashboard as a PWA gives you:

- **Home screen icon** - Launch with one tap, just like a native app
- **Standalone mode** - No browser address bar for a cleaner experience
- **Faster loading** - App assets are cached locally
- **Offline access** - View recent cached events when network is unavailable

### iOS Installation (iPhone/iPad)

1. Open Safari and navigate to your dashboard URL (e.g., `http://your-server:5173`)
2. Tap the **Share** button (square with arrow pointing up)
3. Scroll down and tap **"Add to Home Screen"**
4. Edit the name if desired, then tap **"Add"**
5. The dashboard icon will appear on your Home Screen

> **Note:** iOS requires Safari for PWA installation. Chrome on iOS cannot install PWAs.

### Android Installation

**From Chrome:**

1. Open Chrome and navigate to your dashboard URL
2. Tap the three-dot menu in the top right
3. Tap **"Add to Home screen"** or **"Install app"**
4. Confirm the installation
5. The app icon will appear in your app drawer and home screen

**From Samsung Internet:**

1. Open Samsung Internet and navigate to your dashboard URL
2. Tap the three-line menu
3. Tap **"Add page to"** and select **"Home screen"**

### Desktop Browser Installation

**Chrome, Edge, or Brave:**

1. Navigate to your dashboard URL
2. Look for the install icon in the address bar (plus symbol in a house)
3. Click the icon and select **"Install"**
4. The app will open in its own window without browser controls

**Firefox:**

Firefox does not currently support PWA installation on desktop. Use the web version instead.

---

## Push Notifications

Push notifications alert you to security events even when the app is not open. High-risk and critical events will send immediate notifications to your device.

### How to Enable Notifications

1. Open the dashboard in your browser or PWA
2. Navigate to **Settings** > **Notifications**
3. Click **"Enable Push Notifications"**
4. Your browser will ask for permission - click **"Allow"**

Once enabled, you will receive notifications for:

| Risk Level   | Notification Behavior                           |
| ------------ | ----------------------------------------------- |
| **Low**      | Silent notification (no sound)                  |
| **Medium**   | Standard notification with sound                |
| **High**     | Persistent notification (stays until dismissed) |
| **Critical** | Persistent notification with urgent sound       |

### Notification Content

Each notification includes:

- **Camera name** - Where the event was detected
- **Risk level** - Severity indicator ([HIGH], [MEDIUM], etc.)
- **Summary** - Brief description of what was detected
- **Thumbnail** - Event image (when available)

### Managing Notification Preferences

**To disable notifications:**

1. Open **Settings** in the dashboard
2. Navigate to **Notifications**
3. Toggle off notification permissions

**To manage at the browser level:**

- **Chrome:** Settings > Privacy and Security > Site Settings > Notifications
- **Firefox:** Settings > Privacy & Security > Permissions > Notifications
- **Safari:** Preferences > Websites > Notifications
- **iOS:** Settings > Safari > Notifications
- **Android:** Settings > Apps > Browser > Notifications

### Troubleshooting Notifications

**Not receiving notifications?**

1. Check that notifications are enabled in both the app settings and browser settings
2. Verify your device's Do Not Disturb mode is off
3. Ensure the browser has notification permissions in your OS settings
4. On mobile, ensure battery optimization is not blocking background activity

---

## Mobile-Optimized Features

The dashboard is designed to work seamlessly on mobile devices with touch-friendly interfaces.

### Bottom Navigation

On mobile viewports (under 768px), the dashboard displays a bottom navigation bar for easy thumb access:

| Icon  | Page      |
| ----- | --------- |
| Home  | Dashboard |
| Clock | Timeline  |
| Bell  | Alerts    |
| Gear  | Settings  |

The alerts icon shows a badge when you have unread high-priority events.

### Touch Gestures

The mobile interface supports these touch gestures:

| Gesture                       | Action                          |
| ----------------------------- | ------------------------------- |
| **Swipe left** on event card  | Quick action (dismiss/archive)  |
| **Swipe right** on event card | Quick action (view details)     |
| **Pull down** on any page     | Refresh content                 |
| **Pinch to zoom**             | Zoom on images and video        |
| **Tap and hold**              | Context menu (where applicable) |

### Mobile-Friendly Event Cards

Event cards on mobile show:

- Compact single-line layout for quick scanning
- Touch-friendly action buttons (minimum 44px tap targets)
- Relative timestamps ("5 min ago" instead of full date)
- Duration badges for ongoing events
- Risk badges optimized for mobile display

### Safe Area Support

On devices with notches or home indicators (iPhone X and later, etc.), the interface respects safe area insets:

- Bottom navigation stays above the home indicator
- Content does not get hidden behind notches
- Floating action buttons position correctly

---

## Offline Capabilities

The dashboard continues to work with limited functionality when you lose network connectivity.

### What Works Offline

- **View cached events** - Recently viewed events are stored locally
- **Browse the interface** - Navigation and UI remain responsive
- **View event details** - Previously loaded event data is available

### What Requires Network

- **Live camera feeds** - Requires active connection
- **New event detection** - AI processing happens on the server
- **Real-time updates** - WebSocket requires network
- **Push notifications** - Require network to receive

### Offline Indicator

When network is lost:

1. An offline banner appears at the top of the screen
2. The system status indicator changes to show connectivity issues
3. Cached event count is displayed so you know what's available

When network returns:

1. A "Back Online" notification appears briefly
2. Data automatically syncs with the server
3. Any missed events are loaded

### Cached Event Storage

The app uses IndexedDB to cache events locally:

- Events are cached when viewed
- Cache stores the most recent events you have accessed
- Cached data includes event details, timestamps, and summaries
- Image thumbnails may be cached if previously loaded

---

## Performance Tips

### For Best Mobile Experience

1. **Install as PWA** - Faster loading and more reliable than browser
2. **Enable notifications** - Stay informed of critical events
3. **Use WiFi when available** - Preserves mobile data for notifications
4. **Close unused tabs** - Frees memory for smoother performance

### Battery Optimization

The PWA is designed to be battery-efficient:

- WebSocket connections use heartbeat to minimize power usage
- Notifications are delivered through the system notification service
- Background activity is minimal when app is not in focus
- Polling intervals are optimized to reduce network requests

---

## Troubleshooting

### PWA Installation Issues

| Problem                        | Solution                                                                     |
| ------------------------------ | ---------------------------------------------------------------------------- |
| No "Add to Home Screen" option | Ensure you are using a compatible browser (Safari on iOS, Chrome on Android) |
| App not updating               | Clear the app cache or reinstall                                             |
| PWA shows blank page           | Check network connection and server status                                   |

### Notification Issues

| Problem                      | Solution                                                                  |
| ---------------------------- | ------------------------------------------------------------------------- |
| No permission prompt appears | Browser may have previously blocked - check browser notification settings |
| Notifications not appearing  | Check device Do Not Disturb settings                                      |
| Delayed notifications        | Battery optimization may be delaying delivery                             |

### Mobile Display Issues

| Problem                        | Solution                                                                |
| ------------------------------ | ----------------------------------------------------------------------- |
| Bottom nav overlapping content | Scroll to reveal hidden content, or check for browser toolbar conflicts |
| Text too small                 | Use device accessibility settings to increase text size                 |
| Touch targets too small        | The app uses minimum 44px touch targets, but you can zoom if needed     |

---

## Next Steps

- [Dashboard Overview](dashboard-overview.md) - Learn about the main dashboard interface
- [Understanding Alerts](understanding-alerts.md) - Learn what risk levels mean
- [Settings](settings.md) - Configure notification preferences

---

[Back to User Hub](../user-hub.md)
