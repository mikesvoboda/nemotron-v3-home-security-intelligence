# Keyboard Shortcuts

> Navigate the application quickly using keyboard shortcuts - no mouse required.

This guide covers all keyboard shortcuts available in the Home Security Intelligence dashboard. Using these shortcuts will help you navigate faster and work more efficiently.

---

## Command Palette

The command palette provides quick access to all navigation options in one place. It is the fastest way to jump between pages.

### Opening the Command Palette

| Platform | Shortcut |
| -------- | -------- |
| macOS    | `Cmd+K`  |
| Windows  | `Ctrl+K` |
| Linux    | `Ctrl+K` |

### Using the Command Palette

When the command palette opens:

1. **Type to search** - Start typing to filter available destinations
2. **Navigate results** - Use `Arrow Up` and `Arrow Down` to select
3. **Select destination** - Press `Enter` to navigate to the selected page
4. **Close without action** - Press `Escape` to close

The command palette searches both page names and keywords. For example:

- Type "home" to find Dashboard
- Type "stats" to find Analytics
- Type "health" to find System monitoring

### Available Commands

The command palette (`frontend/src/components/common/CommandPalette.tsx`) builds its navigation list from `frontend/src/config/surfaces.ts` for the current view mode (`Easy` or `Advanced`) and includes a **Switch to Advanced** / **Switch to Easy** action:

| Destination             | Mode     | Path          | Search Keywords                         |
| ----------------------- | -------- | ------------- | --------------------------------------- |
| Dashboard               | Easy     | `/`           | home, main, overview, live              |
| Trends                  | Easy     | `/analytics`  | charts, graphs, statistics, analytics   |
| Timeline                | Easy     | `/timeline`   | events, history, feed, stream, activity |
| Alerts                  | Easy     | `/alerts`     | notifications, warnings, alarms         |
| Household               | Easy     | `/household`  | members, family, residents              |
| Settings                | Easy     | `/settings`   | preferences, configuration, options     |
| Audit log               | Easy     | `/audit`      | security, changes, admin, history       |
| AI Workbench            | Advanced | `/ai-audit`   | evaluation, critique, quality, prompts  |
| GPU & Models            | Advanced | `/ai`         | model, inference, gpu, vlm, latency     |
| Entities                | Advanced | `/entities`   | people, objects, detection, re-id       |
| Operations & Monitoring | Advanced | `/operations` | monitoring, health, status, performance |
| Logs                    | Advanced | `/logs`       | system, debug, output, loki             |

---

## Showing Keyboard Shortcuts Help

Press `?` (question mark) anywhere in the application to open the keyboard shortcuts reference modal. This shows all available shortcuts organized by category.

Press `Escape` to close the help modal.

---

## Global Shortcuts

These shortcuts work anywhere in the application (except when typing in text fields).

| Shortcut       | Action                       |
| -------------- | ---------------------------- |
| `Cmd/Ctrl + K` | Open command palette         |
| `?`            | Show keyboard shortcuts help |
| `Escape`       | Close modal / Cancel action  |

---

## Navigation Shortcuts (Chord Commands)

Navigation uses "chord" shortcuts - press `g` followed by another key within 1 second to navigate.

| Chord | Destination                  | Mode     |
| ----- | ---------------------------- | -------- |
| `g d` | Go to Dashboard (`/`)        | Easy     |
| `g t` | Go to Timeline (`/timeline`) | Easy     |
| `g n` | Go to Trends (`/analytics`)  | Easy     |
| `g a` | Go to Alerts (`/alerts`)     | Easy     |
| `g s` | Go to Settings (`/settings`) | Easy     |
| `g e` | Go to Entities (`/entities`) | Advanced |
| `g y` | Go to System (`/operations`) | Advanced |
| `g o` | Go to Logs (`/logs`)         | Advanced |

All `g` chords work in both Easy and Advanced modes; in the `?` shortcuts help modal, chords that open Advanced pages carry an `Advanced` badge.

**How to use:** Press `g`, release it, then press the second key. Both keys must be pressed within 1 second.

**Example:** To go to the Timeline page:

1. Press and release `g`
2. Within 1 second, press `t`
3. You will be navigated to the Timeline page

---

## List Navigation

When viewing lists (like the Activity Feed or Event Timeline), use these shortcuts to navigate items.

| Shortcut     | Action              |
| ------------ | ------------------- |
| `j`          | Move down / Next    |
| `k`          | Move up / Previous  |
| `Arrow Down` | Move down           |
| `Arrow Up`   | Move up             |
| `Home`       | Jump to first item  |
| `End`        | Jump to last item   |
| `Enter`      | Select current item |

These Vim-style shortcuts (`j`/`k`) allow efficient navigation without moving your hands from the home row.

---

## Modal Shortcuts

When viewing modals or dialogs:

| Shortcut | Action      |
| -------- | ----------- |
| `Escape` | Close modal |

---

## Lightbox (Image Viewer) Shortcuts

When viewing images in the full-screen lightbox:

| Shortcut      | Action         |
| ------------- | -------------- |
| `Arrow Left`  | Previous image |
| `Arrow Right` | Next image     |
| `Escape`      | Close lightbox |

---

## Video Player Shortcuts

When the video player is focused:

| Shortcut      | Action                    |
| ------------- | ------------------------- |
| `Space`       | Play / Pause              |
| `Arrow Left`  | Seek backward (5 seconds) |
| `Arrow Right` | Seek forward (5 seconds)  |
| `f` or `F`    | Toggle fullscreen         |
| `m` or `M`    | Toggle mute               |

---

## Search Bar Shortcuts

When the search bar is focused:

| Shortcut | Action             |
| -------- | ------------------ |
| `Enter`  | Submit search      |
| `Escape` | Clear search query |

---

## Important Notes

### Shortcuts Are Disabled When Typing

Keyboard shortcuts are automatically disabled when you are:

- Typing in an input field
- Typing in a text area
- Using any editable content

This prevents accidental navigation while entering text.

### Platform Differences

- **macOS:** Use `Cmd` for modifier shortcuts
- **Windows/Linux:** Use `Ctrl` for modifier shortcuts

### Accessibility

All keyboard shortcuts are designed to complement mouse/touch navigation, not replace it. If you prefer using a mouse or touchscreen, all features remain accessible through those input methods.

---

## Quick Reference Card

Print this card and keep it near your workstation:

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

## Related Documentation

- [Dashboard](dashboard.md) - Understanding the main interface
- [Event Timeline](timeline.md) - Using list navigation in the timeline
- [Settings](settings.md) - Configuring the application

---

_Keyboard shortcuts make navigation faster, but all features are also accessible via mouse and touch._
