# Interface Guide

> Understanding visual feedback, loading indicators, and notifications in the dashboard.

This guide explains the visual patterns used throughout the Home Security Intelligence dashboard to communicate status, progress, and results of your actions.

---

## Toast Notifications

Toast notifications are brief messages that appear in the corner of the screen to inform you about the result of an action or important system events.

### Toast Types

| Type        | Appearance                        | Meaning                            |
| ----------- | --------------------------------- | ---------------------------------- |
| **Success** | Green left border, checkmark icon | Your action completed successfully |
| **Error**   | Red left border, X icon           | Something went wrong               |
| **Warning** | Amber left border, warning icon   | Proceed with caution               |
| **Info**    | Blue left border, info icon       | General information                |
| **Loading** | Spinning icon                     | Operation in progress              |

### Toast Behavior

- **Auto-dismiss**: Toasts automatically disappear after a few seconds
  - Success, warning, info: 4 seconds
  - Error: 8 seconds (longer to ensure you see the issue)
- **Manual dismiss**: Hover over a toast to reveal a close button
- **Stacking**: Multiple toasts stack vertically (up to 4 visible)
- **Position**: Toasts appear in the bottom-right corner of the screen

### Common Toast Messages

| Message                    | Meaning                                                  |
| -------------------------- | -------------------------------------------------------- |
| "Settings saved"           | Configuration changes were saved successfully            |
| "Event marked as reviewed" | Event was acknowledged and moved to reviewed state       |
| "Failed to load data"      | There was a problem fetching information from the server |
| "Connection restored"      | WebSocket reconnected after a brief interruption         |
| "Camera offline"           | A camera stopped sending images                          |

### Action Buttons

Some toasts include action buttons:

- **Undo**: Revert the action you just performed
- **View**: Navigate to see more details
- **Retry**: Attempt the operation again after a failure

---

## Loading Indicators

The dashboard shows loading states to let you know when content is being fetched.

### Page Loading

When navigating to a new page:

1. A smooth fade transition occurs
2. If the page takes longer to load, a spinner with "Loading..." appears
3. Once loaded, content fades in smoothly

### Skeleton Placeholders

While content loads, you'll see gray animated placeholders that match the shape of the expected content:

| Component    | Placeholder Appearance                             |
| ------------ | -------------------------------------------------- |
| Event cards  | Gray rectangles matching card layout               |
| Camera feeds | Gray 16:9 thumbnails with status badge placeholder |
| Statistics   | Icon and text placeholders                         |
| Tables       | Row-shaped placeholders                            |
| Charts       | Bar/line-shaped placeholders                       |

**Why skeletons?** These placeholders reduce perceived loading time by showing you where content will appear, making the interface feel faster.

### Spinner Indicators

A spinning circle indicates:

- Initial page load
- Background data refresh
- Form submission in progress
- Long-running operations

---

## Page Transitions

When navigating between pages, content transitions smoothly to help you understand the interface hierarchy:

| Transition   | Description                                                |
| ------------ | ---------------------------------------------------------- |
| **Slide up** | Main navigation (default) - content slides up and fades in |
| **Fade**     | Subtle transitions for related content                     |
| **Scale**    | Modal dialogs opening/closing                              |

### Reduced Motion

If you have "Reduce motion" enabled in your operating system settings, transitions will be instant rather than animated to respect your preference.

---

## Status Indicators

### Connection Status

The application maintains real-time connections:

| Indicator  | Status                          |
| ---------- | ------------------------------- |
| Green dot  | Connected and receiving updates |
| Yellow dot | Connecting or reconnecting      |
| Red dot    | Disconnected                    |

### Camera Status

| Status             | Meaning                             |
| ------------------ | ----------------------------------- |
| **Online** (green) | Camera is active and sending images |
| **Offline** (red)  | Camera hasn't sent images recently  |
| **Unknown** (gray) | Status cannot be determined         |

### Event Risk Levels

Events are color-coded by risk:

| Color  | Risk Level | Score Range |
| ------ | ---------- | ----------- |
| Green  | Low        | 0-29        |
| Yellow | Medium     | 30-59       |
| Orange | High       | 60-84       |
| Red    | Critical   | 85-100      |

---

## Interactive Feedback

### Buttons

- **Hover**: Buttons lighten slightly when you hover over them
- **Active**: Brief darkening when clicked
- **Disabled**: Grayed out and non-interactive
- **Loading**: Shows spinner and prevents double-clicks

### Form Fields

- **Focus**: Blue border when selected
- **Error**: Red border with error message below
- **Success**: Green checkmark for validated input

### Cards and Items

- **Hover**: Subtle elevation or highlight
- **Selected**: Green border or background
- **Expandable**: Chevron icon rotates when opened

---

## Modal Dialogs

Modal dialogs appear centered on screen with a dark backdrop:

- **Opening**: Smoothly scales up from the center
- **Closing**: Fades and scales down
- **Backdrop click**: Most modals close when clicking outside
- **Escape key**: Press Escape to close (when enabled)

### Modal Actions

- **Primary action** (green button): Main action to complete
- **Cancel** (gray button): Close without changes
- **Destructive action** (red button): Irreversible actions like delete

---

## Accessibility Features

The interface is designed to be accessible:

| Feature                   | Description                                       |
| ------------------------- | ------------------------------------------------- |
| **Screen reader support** | Toasts and status changes are announced           |
| **Keyboard navigation**   | All interactive elements are keyboard-accessible  |
| **Focus indicators**      | Clear visual indication of focused elements       |
| **Reduced motion**        | Respects system preference for reduced animations |
| **High contrast**         | Increased contrast mode support                   |

---

## Tips

1. **Pay attention to toast colors** - They quickly indicate success (green) vs error (red)
2. **Skeletons mean loading** - Gray animated placeholders show content is being fetched
3. **Check the connection indicator** - If you see issues, check the connection status
4. **Use keyboard shortcuts** - Many actions have keyboard shortcuts (see [Keyboard Shortcuts](keyboard-shortcuts.md))
5. **Enable notifications** - Allow browser notifications for critical alerts

---

## Troubleshooting Visual Issues

| Issue                 | Solution                                        |
| --------------------- | ----------------------------------------------- |
| Toasts not appearing  | Check if browser notifications are blocked      |
| Animations stuttering | Try enabling "Reduce motion" in system settings |
| Content stuck loading | Refresh the page or check connection status     |
| Colors look wrong     | Check browser's dark mode settings              |

---

## Related Documentation

- [Dashboard](dashboard.md) - Main dashboard features
- [Keyboard Shortcuts](keyboard-shortcuts.md) - Keyboard navigation
- [Understanding Alerts](understanding-alerts.md) - Alert types and meanings
- [Getting Started](../getting-started/quick-start.md) - First-time setup
