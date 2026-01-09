# Keyboard Patterns and Implementation Guide

> Developer guide for implementing keyboard shortcuts and command palette features.

This document covers the keyboard navigation system architecture, how to add new shortcuts, and best practices for keyboard accessibility.

---

## Architecture Overview

The keyboard navigation system consists of three main components:

```
frontend/src/
  hooks/
    useKeyboardShortcuts.ts    # Global keyboard shortcuts hook
    useListNavigation.ts       # Vim-style list navigation hook
  components/common/
    CommandPalette.tsx         # Cmd+K command palette component
    ShortcutsHelpModal.tsx     # ? keyboard help modal
  components/layout/
    Layout.tsx                 # Integration point for global shortcuts
```

### Component Responsibilities

| Component              | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `useKeyboardShortcuts` | Global shortcuts, chord navigation, modal triggers |
| `useListNavigation`    | j/k navigation for lists                           |
| `CommandPalette`       | Fuzzy search navigation dialog                     |
| `ShortcutsHelpModal`   | Reference modal showing all shortcuts              |

---

## useKeyboardShortcuts Hook

### Overview

The `useKeyboardShortcuts` hook provides global keyboard navigation with support for:

- Single-key shortcuts (`?` for help)
- Chord shortcuts (`g` + `d` for Dashboard)
- Modifier shortcuts (`Cmd/Ctrl + K` for command palette)

### Usage

```typescript
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';

function MyComponent() {
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isPaletteOpen, setPaletteOpen] = useState(false);

  const { isPendingChord } = useKeyboardShortcuts({
    onOpenHelp: () => setIsHelpOpen(true),
    onOpenCommandPalette: () => setPaletteOpen(true),
    onEscape: () => {
      setIsHelpOpen(false);
      setPaletteOpen(false);
    },
    enabled: !isHelpOpen && !isPaletteOpen, // Disable when modals are open
  });

  // isPendingChord is true when 'g' has been pressed and waiting for second key
  return (
    <div>
      {isPendingChord && <span>Waiting for chord key...</span>}
    </div>
  );
}
```

### Options

```typescript
interface UseKeyboardShortcutsOptions {
  /** Callback when ? is pressed to open help modal */
  onOpenHelp?: () => void;
  /** Callback when Cmd/Ctrl + K is pressed to open command palette */
  onOpenCommandPalette?: () => void;
  /** Callback when Escape is pressed */
  onEscape?: () => void;
  /** Whether shortcuts are enabled (default: true) */
  enabled?: boolean;
}
```

### Return Type

```typescript
interface UseKeyboardShortcutsReturn {
  /** Whether a chord is pending (g has been pressed) */
  isPendingChord: boolean;
}
```

### Adding New Navigation Routes

To add a new navigation chord:

1. Edit `CHORD_ROUTES` in `useKeyboardShortcuts.ts`:

```typescript
const CHORD_ROUTES: Record<string, string> = {
  d: '/', // Dashboard
  t: '/timeline', // Timeline
  a: '/analytics', // Analytics
  l: '/alerts', // Alerts
  e: '/entities', // Entities
  o: '/logs', // Logs (o for lOgs since l is taken)
  s: '/system', // System monitoring
  ',': '/settings', // Settings (Vim-style)
  // Add new routes here:
  z: '/zones', // Example: Zones page
};
```

2. Update `ShortcutsHelpModal.tsx` to document the new shortcut:

```typescript
const SHORTCUT_GROUPS: ShortcutGroup[] = [
  // ...
  {
    title: 'Navigation',
    items: [
      // ... existing items
      { keys: ['g', 'z'], description: 'Go to Zones' },
    ],
  },
];
```

3. Update `CommandPalette.tsx` to include the new destination:

```typescript
const NAVIGATION_ITEMS: NavigationItem[] = [
  // ... existing items
  {
    name: 'Zones',
    path: '/zones',
    shortcut: 'g z',
    icon: MapPin,
    keywords: ['areas', 'regions', 'detection zones'],
  },
];
```

---

## useListNavigation Hook

### Overview

The `useListNavigation` hook provides Vim-style j/k navigation for lists with support for:

- `j`/`Arrow Down` to move down
- `k`/`Arrow Up` to move up
- `Home`/`End` to jump to boundaries
- `Enter` to select

### Usage

```typescript
import { useListNavigation } from '../../hooks/useListNavigation';

function EventList({ events }: { events: Event[] }) {
  const { selectedIndex, setSelectedIndex, resetSelection } = useListNavigation({
    itemCount: events.length,
    initialIndex: 0,
    wrap: false,
    onSelect: (index) => {
      console.log('Selected event:', events[index]);
    },
    enabled: true,
  });

  return (
    <ul>
      {events.map((event, index) => (
        <li
          key={event.id}
          className={index === selectedIndex ? 'bg-primary/20' : ''}
        >
          {event.title}
        </li>
      ))}
    </ul>
  );
}
```

### Options

```typescript
interface UseListNavigationOptions {
  /** Total number of items in the list */
  itemCount: number;
  /** Initial selected index (default: 0) */
  initialIndex?: number;
  /** Whether to wrap around at list boundaries (default: false) */
  wrap?: boolean;
  /** Callback when Enter is pressed on a selected item */
  onSelect?: (index: number) => void;
  /** Whether keyboard navigation is enabled (default: true) */
  enabled?: boolean;
}
```

### Return Type

```typescript
interface UseListNavigationReturn {
  /** Currently selected index (-1 if list is empty) */
  selectedIndex: number;
  /** Set the selected index programmatically */
  setSelectedIndex: (index: number) => void;
  /** Reset selection to initial index */
  resetSelection: () => void;
}
```

---

## CommandPalette Component

### Overview

The `CommandPalette` component provides a searchable command palette using the `cmdk` library. It supports:

- Fuzzy search across page names and keywords
- Keyboard navigation with arrow keys
- Visual display of keyboard shortcuts

### Usage

```typescript
import CommandPalette from '../common/CommandPalette';

function Layout() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <CommandPalette
        open={isOpen}
        onOpenChange={setIsOpen}
      />
    </>
  );
}
```

### Props

```typescript
interface CommandPaletteProps {
  /** Whether the palette is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
}
```

### Adding New Commands

To add new navigation items to the command palette:

```typescript
// In CommandPalette.tsx
const NAVIGATION_ITEMS: NavigationItem[] = [
  // ... existing items
  {
    name: 'New Feature', // Display name
    path: '/new-feature', // Route path
    shortcut: 'g n', // Keyboard shortcut (or '' if none)
    icon: SomeIcon, // Lucide icon component
    keywords: ['related', 'terms'], // Search keywords (optional)
  },
];
```

The `keywords` array enables finding items by alternative terms. For example, typing "stats" will find "Analytics" because it has "statistics" and "stats" as keywords.

---

## ShortcutsHelpModal Component

### Overview

The `ShortcutsHelpModal` displays all available keyboard shortcuts organized by category. It opens when the user presses `?`.

### Adding New Shortcut Groups

```typescript
// In ShortcutsHelpModal.tsx
const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: 'Global',
    items: [
      { keys: ['\u2318/Ctrl', 'K'], description: 'Open command palette' },
      // \u2318 is the Unicode for Command key symbol
    ],
  },
  {
    title: 'Navigation',
    items: [
      { keys: ['g', 'd'], description: 'Go to Dashboard' },
      // Multiple keys show with + between them
    ],
  },
  // Add new groups here
  {
    title: 'Custom Feature',
    items: [{ keys: ['x'], description: 'Do something custom' }],
  },
];
```

---

## Best Practices

### 1. Check for Editable Elements

Always check if the user is typing in an input before processing shortcuts:

```typescript
function isEditableElement(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) {
    return false;
  }

  const tagName = target.tagName.toLowerCase();
  if (tagName === 'input' || tagName === 'textarea') {
    return true;
  }

  if (target.contentEditable === 'true') {
    return true;
  }

  return false;
}

// In your keydown handler
const handleKeyDown = useCallback((event: KeyboardEvent) => {
  if (isEditableElement(event.target)) {
    return; // Don't process shortcuts when typing
  }
  // ... handle shortcut
}, []);
```

### 2. Disable Shortcuts When Modals Are Open

Pass `enabled: false` to disable shortcuts when modals that handle their own keyboard events are open:

```typescript
useKeyboardShortcuts({
  // ...
  enabled: !isModalOpen && !isPaletteOpen && !isHelpOpen,
});
```

### 3. Use Consistent Key Conventions

- **Single letters** for quick actions (`?` for help)
- **Chords** for navigation (`g` + `letter`)
- **Modifiers** for system-level actions (`Cmd/Ctrl + K`)
- **Arrow keys** for directional navigation
- **Escape** for cancel/close

### 4. Document All Shortcuts

When adding a new shortcut:

1. Add to `ShortcutsHelpModal.tsx` for the help modal
2. Add to `CommandPalette.tsx` if it's a navigation shortcut
3. Update `docs/user-guide/keyboard-shortcuts.md` for user documentation

### 5. Handle Platform Differences

Use both `metaKey` (Mac) and `ctrlKey` (Windows/Linux):

```typescript
if (key === 'k' && (metaKey || ctrlKey)) {
  // Works on all platforms
  event.preventDefault();
  onOpenCommandPalette?.();
}
```

### 6. Prevent Default Browser Behavior

Call `event.preventDefault()` to prevent browser shortcuts from interfering:

```typescript
if (key === 'k' && (metaKey || ctrlKey)) {
  event.preventDefault(); // Prevent browser's bookmark/search bar
  // ... handle shortcut
}
```

---

## Component-Specific Keyboard Handlers

Some components implement their own keyboard handlers for context-specific shortcuts:

### VideoPlayer

```typescript
// frontend/src/components/video/VideoPlayer.tsx
const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
  switch (e.key) {
    case ' ': // Space: Play/Pause
    case 'ArrowLeft': // Seek backward
    case 'ArrowRight': // Seek forward
    case 'f': // Toggle fullscreen
    case 'm': // Toggle mute
  }
}, []);
```

### Lightbox

```typescript
// frontend/src/components/common/Lightbox.tsx
const handleKeyDown = (e: KeyboardEvent) => {
  switch (e.key) {
    case 'Escape': // Close lightbox
    case 'ArrowLeft': // Previous image
    case 'ArrowRight': // Next image
  }
};
```

### AnimatedModal

```typescript
// frontend/src/components/common/AnimatedModal.tsx
const handleKeyDown = useCallback(
  (e: KeyboardEvent) => {
    if (e.key === 'Escape' && closeOnEscape) {
      onClose();
    }
  },
  [closeOnEscape, onClose]
);
```

---

## Testing Keyboard Shortcuts

### Unit Testing

```typescript
// Example test for useKeyboardShortcuts
import { renderHook } from '@testing-library/react';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';

test('opens command palette on Cmd+K', () => {
  const onOpenCommandPalette = vi.fn();
  renderHook(() => useKeyboardShortcuts({ onOpenCommandPalette }));

  // Simulate Cmd+K
  fireEvent.keyDown(document, {
    key: 'k',
    metaKey: true,
  });

  expect(onOpenCommandPalette).toHaveBeenCalled();
});
```

### E2E Testing

```typescript
// Example Playwright test
test('command palette opens with keyboard', async ({ page }) => {
  await page.goto('/');

  // Press Cmd+K (Mac) or Ctrl+K (Windows/Linux)
  await page.keyboard.press('Control+k');

  // Verify command palette is visible
  await expect(page.locator('[role="dialog"][aria-label="Command palette"]')).toBeVisible();
});
```

---

## Related Documentation

- [Frontend Hooks](hooks.md) - Overview of all custom hooks
- [Architecture Overview](../architecture/overview.md) - System architecture
- [User Keyboard Shortcuts](../user-guide/keyboard-shortcuts.md) - End-user documentation

---

## File Reference

| File                                                         | Purpose                                |
| ------------------------------------------------------------ | -------------------------------------- |
| `frontend/src/hooks/useKeyboardShortcuts.ts`                 | Global keyboard shortcuts hook         |
| `frontend/src/hooks/useKeyboardShortcuts.test.ts`            | Unit tests for keyboard shortcuts      |
| `frontend/src/hooks/useListNavigation.ts`                    | List navigation hook                   |
| `frontend/src/hooks/useListNavigation.test.ts`               | Unit tests for list navigation         |
| `frontend/src/components/common/CommandPalette.tsx`          | Command palette component              |
| `frontend/src/components/common/CommandPalette.test.tsx`     | Command palette tests                  |
| `frontend/src/components/common/ShortcutsHelpModal.tsx`      | Shortcuts help modal                   |
| `frontend/src/components/common/ShortcutsHelpModal.test.tsx` | Help modal tests                       |
| `frontend/src/components/layout/Layout.tsx`                  | Integration point for global shortcuts |
