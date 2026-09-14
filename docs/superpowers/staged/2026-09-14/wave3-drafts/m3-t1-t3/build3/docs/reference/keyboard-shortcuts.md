# Keyboard Shortcuts Reference

> Complete reference for all keyboard shortcuts in Home Security Intelligence.

This document provides a comprehensive reference of all keyboard shortcuts available in the dashboard. For detailed usage instructions and accessibility features, see the [UI Keyboard Shortcuts Guide](../ui/keyboard-shortcuts.md).

---

## Quick Reference Card

```
COMMAND PALETTE           NAVIGATION (g + key)
-----------------         --------------------
Cmd/Ctrl + K  Open        g d  Dashboard
                          g t  Timeline
GLOBAL                    g n  Analytics
------                    g a  Alerts
?       Help modal        g e  Entities
Escape  Close modal       g o  Logs
                          g y  System
LIST NAVIGATION           g s  Settings
---------------
j / Arrow Down  Next
k / Arrow Up    Previous
Home            First
End             Last
Enter           Select

VIDEO PLAYER              LIGHTBOX
------------              --------
Space    Play/Pause       Left   Previous
f        Fullscreen       Right  Next
m        Mute             Escape Close
Left     -5 seconds
Right    +5 seconds
```

---

## Global Shortcuts

These shortcuts work anywhere in the application (except when typing in text fields).

| Shortcut       | Action                       | Context  |
| -------------- | ---------------------------- | -------- |
| `Cmd/Ctrl + K` | Open command palette         | Anywhere |
| `?`            | Show keyboard shortcuts help | Anywhere |
| `Escape`       | Close modal / Cancel action  | Anywhere |

---

## Navigation Shortcuts

### Command Palette

The command palette provides fuzzy search for quick navigation.

| Platform | Shortcut |
| -------- | -------- |
| macOS    | `Cmd+K`  |
| Windows  | `Ctrl+K` |
| Linux    | `Ctrl+K` |

**Available Destinations:**

| Destination    | Search Keywords                         |
| -------------- | --------------------------------------- |
| Dashboard      | home, main, overview                    |
| Timeline       | events, history, time                   |
| Analytics      | charts, graphs, statistics, stats       |
| Alerts         | notifications, warnings                 |
| Entities       | people, objects, detection              |
| Logs           | system, debug, output                   |
| System         | monitoring, health, status, performance |
| AI Performance | model, inference, gpu, nemotron, yolo26 |
| Audit Log      | history, changes, tracking              |
| Settings       | preferences, configuration, options     |

### Chord Commands (g + key)

Press `g` followed by another key within 1 second to navigate directly to a page.

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

---

## List Navigation

When viewing lists (Activity Feed, Event Timeline, Search Results):

| Shortcut     | Action              |
| ------------ | ------------------- |
| `j`          | Move down / Next    |
| `k`          | Move up / Previous  |
| `Arrow Down` | Move down           |
| `Arrow Up`   | Move up             |
| `Home`       | Jump to first item  |
| `End`        | Jump to last item   |
| `Enter`      | Select current item |

---

## Media Controls

### Video Player

| Shortcut      | Action                    |
| ------------- | ------------------------- |
| `Space`       | Play / Pause              |
| `Arrow Left`  | Seek backward (5 seconds) |
| `Arrow Right` | Seek forward (5 seconds)  |
| `f` or `F`    | Toggle fullscreen         |
| `m` or `M`    | Toggle mute               |

### Lightbox (Image Viewer)

| Shortcut      | Action         |
| ------------- | -------------- |
| `Arrow Left`  | Previous image |
| `Arrow Right` | Next image     |
| `Escape`      | Close lightbox |

---

## Modal and Dialog Navigation

| Shortcut | Action      |
| -------- | ----------- |
| `Escape` | Close modal |
| `Tab`    | Next field  |
| `Enter`  | Submit form |

---

## Search Bar

| Shortcut | Action             |
| -------- | ------------------ |
| `Enter`  | Submit search      |
| `Escape` | Clear search query |

---

## Accessibility Notes

- Shortcuts are disabled when typing in input fields
- All features are also accessible via mouse/touch
- Focus indicators show current position when using keyboard
- Skip to main content link appears on first Tab press

---

## Platform Differences

| Action          | macOS     | Windows/Linux |
| --------------- | --------- | ------------- |
| Command palette | `Cmd + K` | `Ctrl + K`    |
| Browser zoom in | `Cmd + +` | `Ctrl + +`    |
| Browser zoom    | `Cmd + -` | `Ctrl + -`    |
| Browser reset   | `Cmd + 0` | `Ctrl + 0`    |

---

## Related Documentation

- [UI Keyboard Shortcuts Guide](../ui/keyboard-shortcuts.md) - Detailed usage guide
- [Accessibility Features](accessibility.md) - Full accessibility documentation
- [Getting Started](../getting-started/README.md) - System overview and setup
- [Dashboard Guide](../ui/dashboard.md) - Understanding the interface

---

[Back to Reference Hub](README.md) | [Accessibility](accessibility.md)
