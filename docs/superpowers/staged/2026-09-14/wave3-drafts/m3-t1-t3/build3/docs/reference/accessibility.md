# Accessibility Features

> Use the dashboard with keyboard navigation, screen readers, and other assistive technologies.

Home Security Intelligence is designed to be accessible to everyone. This guide covers the accessibility features available to help you navigate and use the dashboard effectively.

---

## Keyboard Navigation

The entire dashboard can be operated without a mouse. This benefits users who:

- Cannot use a mouse due to mobility impairments
- Prefer keyboard for speed and efficiency
- Use screen readers or other assistive technologies

### Getting Started with Keyboard

1. **Tab** - Move forward through interactive elements
2. **Shift + Tab** - Move backward through interactive elements
3. **Enter** or **Space** - Activate buttons and links
4. **Escape** - Close modals and cancel actions
5. **Arrow keys** - Navigate within components

### Skip to Main Content

When you first Tab into the page, a "Skip to main content" link appears. Press **Enter** to bypass the navigation and jump directly to the main content area.

This saves time by avoiding tabbing through the entire sidebar navigation on every page.

### Command Palette

The fastest way to navigate is the command palette:

1. Press `Cmd + K` (Mac) or `Ctrl + K` (Windows/Linux)
2. Type what you are looking for (e.g., "timeline", "settings")
3. Use **Arrow Up/Down** to select
4. Press **Enter** to navigate

The command palette searches both page names and related keywords, so typing "stats" will find "Analytics" and typing "home" will find "Dashboard".

### Quick Navigation Shortcuts

Press `g` followed by a letter to jump directly to any page:

| Shortcut | Destination |
| -------- | ----------- |
| `g d`    | Dashboard   |
| `g t`    | Timeline    |
| `g n`    | Analytics   |
| `g a`    | Alerts      |
| `g e`    | Entities    |
| `g o`    | Logs        |
| `g y`    | System      |
| `g s`    | Settings    |

### List Navigation

When viewing event lists, activity feeds, or search results:

| Key           | Action                |
| ------------- | --------------------- |
| `j` or `Down` | Move to next item     |
| `k` or `Up`   | Move to previous item |
| `Home`        | Jump to first item    |
| `End`         | Jump to last item     |
| `Enter`       | Open selected item    |

These Vim-style shortcuts (`j`/`k`) keep your hands on the home row for faster navigation.

### Modal and Dialog Navigation

When a modal or dialog opens:

- Focus automatically moves into the modal
- **Tab** cycles through interactive elements inside the modal
- Press **Escape** to close without saving
- Focus returns to the element that opened the modal when it closes

### Help Shortcut

Press `?` anywhere in the application to open the keyboard shortcuts reference. This shows all available shortcuts organized by category.

---

## Screen Reader Compatibility

The dashboard is compatible with major screen readers:

| Screen Reader | Platform | Status          |
| ------------- | -------- | --------------- |
| VoiceOver     | macOS    | Fully supported |
| NVDA          | Windows  | Fully supported |
| JAWS          | Windows  | Supported       |
| Orca          | Linux    | Supported       |

### What Screen Readers Will Announce

**Page Navigation:**

- Page title changes when you navigate
- Main content regions are identified
- Navigation landmarks are labeled

**Interactive Elements:**

- Button names and purposes
- Link destinations
- Form field labels
- Current state (checked, expanded, selected)

**Dynamic Updates:**

- New security alerts are announced immediately
- Loading states are announced
- Error messages are announced

### Tips for Screen Reader Users

1. **Use landmarks** - Jump between regions using your screen reader's landmark navigation

   - VoiceOver: `VO + U` then select Landmarks
   - NVDA: `D` for next landmark, `Shift + D` for previous

2. **Headings navigation** - Pages use heading levels consistently

   - `H` / `Shift + H` to move between headings

3. **Tables** - Event tables have proper headers

   - Use table navigation commands to move between cells

4. **Forms** - All form fields have associated labels
   - Tab through form fields to hear their labels and current values

---

## Visual Accessibility

### Color Contrast

All text and interactive elements meet WCAG 2.1 AA contrast requirements:

- **Normal text:** 4.5:1 contrast ratio minimum
- **Large text:** 3:1 contrast ratio minimum
- **UI components:** 3:1 contrast ratio minimum

Risk levels use both color AND labels:

- **Low (Green)** - Risk score 0-29, displayed with "Low" label
- **Medium (Yellow)** - Risk score 30-59, displayed with "Medium" label
- **High (Orange)** - Risk score 60-84, displayed with "High" label
- **Critical (Red)** - Risk score 85-100, displayed with "Critical" label

Color is never the only way information is conveyed.

### Focus Indicators

When navigating with keyboard, a visible green focus ring shows which element is currently focused. This makes it easy to track your position on the page.

### Text Sizing

The dashboard responds well to browser zoom:

- Content is readable at 200% zoom
- Layout adjusts at smaller viewport sizes
- Text does not get cut off when enlarged

**To increase text size:**

1. Press `Cmd + +` (Mac) or `Ctrl + +` (Windows/Linux) to zoom in
2. Press `Cmd + -` or `Ctrl + -` to zoom out
3. Press `Cmd + 0` or `Ctrl + 0` to reset

### Reduced Motion

If you have `prefers-reduced-motion` enabled in your operating system, animations are minimized:

- Page transitions are instant
- Loading spinners are simplified
- Attention-grabbing animations are disabled

**To enable reduced motion:**

- **macOS:** System Preferences > Accessibility > Display > Reduce motion
- **Windows:** Settings > Ease of Access > Display > Show animations in Windows
- **Linux:** Varies by desktop environment

---

## Browser Settings for Accessibility

### Recommended Browser Extensions

| Extension    | Purpose                                    |
| ------------ | ------------------------------------------ |
| Dark Reader  | Force dark mode on all websites            |
| Vimium       | Vim-style keyboard navigation for browsers |
| axe DevTools | Test accessibility on any website          |

### Browser Accessibility Settings

**Chrome:**

- Settings > Accessibility > Live Caption, High contrast, etc.
- chrome://flags > Enable experimental accessibility features

**Firefox:**

- Settings > General > Language and Appearance > Fonts and Colors > Override
- about:preferences#accessibility

**Safari:**

- Safari > Preferences > Advanced > Accessibility

---

## Mobile Accessibility

The mobile web app supports:

### Touch Accessibility

- Large touch targets (minimum 44x44 pixels)
- Adequate spacing between interactive elements
- Swipe gestures work with accessibility services enabled

### iOS VoiceOver

- All elements are properly labeled
- Swipe to navigate between elements
- Double-tap to activate

### Android TalkBack

- All elements are properly labeled
- Swipe to navigate between elements
- Double-tap to activate

---

## Getting Help

### If You Encounter Accessibility Issues

If you find something that does not work with your assistive technology:

1. Note which page and feature has the issue
2. Note which assistive technology you are using (e.g., "NVDA on Chrome")
3. Describe what you expected to happen vs. what actually happened
4. Contact your system administrator with these details

### Request Accommodations

If you need specific accessibility accommodations not covered here, contact your system administrator. We continuously improve accessibility based on user feedback.

---

## Accessibility Quick Reference

### Essential Shortcuts

| Action             | Shortcut            |
| ------------------ | ------------------- |
| Show all shortcuts | `?`                 |
| Command palette    | `Cmd/Ctrl + K`      |
| Close modal        | `Escape`            |
| Skip to content    | `Tab` (first press) |
| Next element       | `Tab`               |
| Previous element   | `Shift + Tab`       |
| Activate           | `Enter` or `Space`  |

### Navigation Chords (press g then letter)

```
g d - Dashboard    g a - Alerts
g t - Timeline     g e - Entities
g n - Analytics    g o - Logs
g y - System       g s - Settings
```

### List Navigation

```
j / Down  - Next item
k / Up    - Previous item
Home      - First item
End       - Last item
Enter     - Select
```

---

## Related Documentation

- [Keyboard Shortcuts](keyboard-shortcuts.md) - Complete shortcut reference
- [Getting Started](getting-started.md) - System overview
- [Dashboard](../ui/dashboard.md) - Understanding the interface

---

_If something is not accessible to you, it is not accessible. Please report accessibility issues so we can fix them._
