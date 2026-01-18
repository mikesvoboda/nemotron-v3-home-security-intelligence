# Accessibility Implementation Guide

> Developer guide for implementing and maintaining WCAG 2.1 AA compliance.

This document covers the accessibility architecture, implementation patterns, and testing practices used in Home Security Intelligence. The frontend is designed to meet **WCAG 2.1 AA** compliance standards.

---

## WCAG Compliance Overview

### Target Compliance Level

**WCAG 2.1 Level AA** - This is the standard level of accessibility compliance that covers:

- **Perceivable:** Text alternatives, adaptable content, distinguishable content
- **Operable:** Keyboard accessible, enough time, seizures, navigable
- **Understandable:** Readable, predictable, input assistance
- **Robust:** Compatible with assistive technologies

### Key Requirements Met

| WCAG Criterion               | Description                         | Implementation                           |
| ---------------------------- | ----------------------------------- | ---------------------------------------- |
| 1.1.1 Non-text Content       | All images have text alternatives   | `aria-label`, `alt` attributes           |
| 1.3.1 Info and Relationships | Structure conveyed programmatically | Semantic HTML, ARIA roles                |
| 1.4.3 Contrast (Minimum)     | 4.5:1 for text, 3:1 for large text  | WCAG-compliant color palette             |
| 1.4.11 Non-text Contrast     | 3:1 for UI components               | Focus indicators, borders                |
| 2.1.1 Keyboard               | All functionality via keyboard      | `useKeyboardShortcuts`, focus management |
| 2.1.2 No Keyboard Trap       | Focus can be moved away             | Escape key handling, focus trap          |
| 2.4.1 Bypass Blocks          | Skip to main content                | Skip link in Layout                      |
| 2.4.3 Focus Order            | Logical tab order                   | `tabIndex`, DOM order                    |
| 2.4.7 Focus Visible          | Visible focus indicator             | Focus ring styles                        |
| 4.1.2 Name, Role, Value      | ARIA labels for components          | `role`, `aria-*` attributes              |

---

## Architecture

### Key Files

```
frontend/src/
  components/
    layout/
      Layout.tsx              # Skip link, main content landmark
    common/
      ShortcutsHelpModal.tsx  # Keyboard shortcuts help (?)
      CommandPalette.tsx      # Cmd+K navigation
      AnimatedModal.tsx       # Focus trap, Escape handling
  hooks/
    useKeyboardShortcuts.ts   # Global keyboard navigation
    useListNavigation.ts      # j/k list navigation
  config/
    tourSteps.ts              # Product tour configuration
frontend/tests/e2e/specs/
    accessibility.spec.ts     # axe-core WCAG tests
frontend/tailwind.config.js   # WCAG-compliant color palette
```

### Component Responsibilities

| Component                | Accessibility Feature                                           |
| ------------------------ | --------------------------------------------------------------- |
| `Layout.tsx`             | Skip link, main content landmark, keyboard shortcut integration |
| `AnimatedModal.tsx`      | Focus trap, Escape key handling, ARIA modal attributes          |
| `ShortcutsHelpModal.tsx` | Keyboard shortcuts reference                                    |
| `CommandPalette.tsx`     | Keyboard navigation, fuzzy search                               |
| `VideoPlayer.tsx`        | Keyboard controls, ARIA labels for all buttons                  |
| `Lightbox.tsx`           | Keyboard image navigation, focus management                     |

---

## Implementation Patterns

### ARIA Labels

Every interactive element requires an accessible name. Use these patterns:

```tsx
// Button with icon only - use aria-label
<button
  onClick={handleClose}
  aria-label="Close modal"
  className="..."
>
  <X className="h-5 w-5" />
</button>

// Button with visible text - no aria-label needed
<button onClick={handleSave} className="...">
  Save Changes
</button>

// Icon with descriptive purpose
<AlertTriangle
  className="h-4 w-4 text-yellow-500"
  aria-label="Warning: Queue backing up"
/>

// Decorative icon - hide from screen readers
<Settings className="h-5 w-5" aria-hidden="true" />
```

### Keyboard Navigation

The application uses three keyboard navigation systems:

#### 1. Global Shortcuts (`useKeyboardShortcuts`)

```tsx
// In Layout.tsx
useKeyboardShortcuts({
  onOpenCommandPalette: () => setCommandPaletteOpen(true),
  onOpenHelp: () => setShortcutsHelpOpen(true),
  onEscape: () => {
    setCommandPaletteOpen(false);
    setShortcutsHelpOpen(false);
  },
  enabled: !isCommandPaletteOpen && !isShortcutsHelpOpen,
});
```

**Key bindings:**

- `?` - Open keyboard shortcuts help
- `Cmd/Ctrl + K` - Open command palette
- `g + [letter]` - Navigate to page (chord shortcuts)
- `Escape` - Close modal/cancel

#### 2. List Navigation (`useListNavigation`)

```tsx
const { selectedIndex, setSelectedIndex } = useListNavigation({
  itemCount: events.length,
  initialIndex: 0,
  wrap: false,
  onSelect: (index) => openEventDetail(events[index]),
  enabled: true,
});
```

**Key bindings:**

- `j` / `ArrowDown` - Move down
- `k` / `ArrowUp` - Move up
- `Home` - First item
- `End` - Last item
- `Enter` - Select

#### 3. Component-Specific Shortcuts

Some components have their own keyboard handlers:

```tsx
// VideoPlayer.tsx
const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
  switch (e.key) {
    case ' ':
      togglePlay();
      break;
    case 'f':
    case 'F':
      toggleFullscreen();
      break;
    case 'm':
    case 'M':
      toggleMute();
      break;
    case 'ArrowLeft':
      seek(-5);
      break;
    case 'ArrowRight':
      seek(5);
      break;
  }
}, []);
```

### Focus Management

#### Skip Link

The Layout component includes a skip link for keyboard users:

```tsx
// Layout.tsx
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-[#76B900] focus:px-4 focus:py-2 focus:font-medium focus:text-black"
>
  Skip to main content
</a>

// Main content target
<main id="main-content" tabIndex={-1} className="...">
  {children}
</main>
```

#### Focus Trap in Modals

Modals trap focus to prevent tabbing outside:

```tsx
// AnimatedModal.tsx or custom implementation
useEffect(() => {
  if (open) {
    // Store previously focused element
    previousFocusRef.current = document.activeElement as HTMLElement;

    // Focus first focusable element in modal
    const focusable = modalRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    focusable?.focus();
  }

  return () => {
    // Restore focus when modal closes
    previousFocusRef.current?.focus();
  };
}, [open]);
```

#### Focus Indicators

All interactive elements have visible focus indicators:

```tsx
// Tailwind classes for focus states
className =
  'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]';
```

### Screen Reader Support

#### ARIA Roles and States

```tsx
// Dialog/Modal
<div
  role="dialog"
  aria-modal="true"
  aria-label="Add alert rule"
  // or aria-labelledby="modal-title"
>
  <h2 id="modal-title">Add Alert Rule</h2>
  ...
</div>

// Live region for announcements
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {statusMessage}
</div>

// Busy state during loading
<div aria-busy={isLoading}>
  {isLoading ? <Spinner /> : <Content />}
</div>
```

#### Dynamic Content Updates

```tsx
// Announce changes to screen readers
<div aria-live="assertive" aria-atomic="true">
  {criticalAlert && `Critical alert: ${criticalAlert.message}`}
</div>
```

### Color Contrast Ratios

The design system uses WCAG-compliant colors defined in `tailwind.config.js`:

```javascript
// tailwind.config.js - WCAG 2.1 AA compliant colors
colors: {
  // Risk colors - 4.5:1 contrast on 10% opacity backgrounds
  risk: {
    low: '#76B900',      // Green - good contrast on dark
    medium: '#FFB800',   // Amber - good contrast on dark
    high: '#FFCDD2',     // Light coral for 4.5:1 contrast
    critical: '#FFE0E0', // Very light pink for critical badges
  },

  // Text colors - 4.5:1 minimum contrast on gray-700
  text: {
    primary: '#FFFFFF',
    secondary: '#B0B0B0', // 5.17:1 contrast on gray-700
    muted: '#919191',     // 4.81:1 contrast on #222222
  },

  // Gray scale - adjusted for proper contrast
  gray: {
    500: '#9A9A9A', // 4.7:1 contrast on gray-700
    400: '#B0B0B0', // 5.17:1 contrast on gray-700
  },
}
```

**Contrast requirements:**

- Normal text (< 18pt): 4.5:1 minimum
- Large text (>= 18pt or 14pt bold): 3:1 minimum
- UI components and graphical objects: 3:1 minimum

#### Testing Contrast

```bash
# Check contrast in development
# Use browser DevTools > Lighthouse > Accessibility
# Or axe DevTools extension

# Automated E2E test
# frontend/tests/e2e/specs/accessibility.spec.ts
const results = await new AxeBuilder({ page })
  .withRules(['color-contrast'])
  .analyze();
```

---

## Testing Accessibility

### Automated Testing with axe-core

The project uses `@axe-core/playwright` for automated WCAG compliance testing.

#### Running Tests

```bash
# Run accessibility tests
cd frontend && npx playwright test accessibility

# Run with specific browser
cd frontend && npx playwright test accessibility --project=chromium
```

#### Test Configuration

```typescript
// frontend/tests/e2e/specs/accessibility.spec.ts
const WCAG_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa'];

async function runA11yCheck(page) {
  return new AxeBuilder({ page }).withTags(WCAG_AA_TAGS).analyze();
}

test('dashboard page has no accessibility violations', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  const results = await runA11yCheck(page);

  expect(results.violations).toEqual([]);
});
```

#### Tested Pages and Features

| Page/Feature        | Test Coverage                                |
| ------------------- | -------------------------------------------- |
| Dashboard           | Full page scan, risk card focus, camera grid |
| Timeline            | Page scan, filter controls, search input     |
| Settings            | Tab navigation, all tab panels               |
| Alert Rules         | Add/delete modals, table accessibility       |
| Zone Editor         | Canvas navigation, keyboard interaction      |
| Modals              | Focus trap, ARIA attributes, Escape key      |
| Keyboard Navigation | Skip link, main navigation, list navigation  |
| Color Contrast      | Dashboard contrast, all critical UI elements |
| Forms               | Label associations, validation errors        |

### Manual Testing Checklist

Use this checklist before releasing accessibility-impacting changes:

#### Keyboard Navigation

- [ ] Can navigate to all interactive elements using Tab
- [ ] Focus order follows visual layout
- [ ] Focus indicator is clearly visible
- [ ] Can activate all buttons/links with Enter/Space
- [ ] Can close modals with Escape key
- [ ] Skip link works and is visible on focus
- [ ] Keyboard shortcuts work (`?`, `Cmd+K`, `g + letter`)

#### Screen Reader Testing

Test with at least one of:

- VoiceOver (macOS): `Cmd + F5` to enable
- NVDA (Windows): Free download from nvaccess.org
- Orca (Linux): Pre-installed on many distributions

- [ ] Page titles are announced on navigation
- [ ] Interactive elements have accessible names
- [ ] Form fields have associated labels
- [ ] Error messages are announced
- [ ] Modal content is announced when opened
- [ ] Live regions announce dynamic content

#### Visual Testing

- [ ] Content readable at 200% zoom
- [ ] UI usable at 320px viewport width
- [ ] Color is not the only means of conveying information
- [ ] Focus indicators visible in all color modes
- [ ] Animations respect `prefers-reduced-motion`

### Browser-Specific Considerations

#### Firefox Contrast Rendering

Firefox calculates color contrast with slightly different anti-aliasing than Chromium. The test suite includes a filter for Firefox-specific edge cases:

```typescript
// frontend/tests/e2e/specs/accessibility.spec.ts
function filterFirefoxContrastViolations(violations, browserName) {
  if (browserName !== 'firefox') return violations;

  return violations.filter((violation) => {
    if (violation.id !== 'color-contrast') return true;

    // Filter 4.4-4.49 range (within 0.1 of 4.5 threshold)
    const allNodesNearThreshold = violation.nodes.every((node) => {
      const match = node.any[0]?.message?.match(/contrast of (\d+\.\d+)/);
      if (match) {
        const ratio = parseFloat(match[1]);
        return ratio >= 4.4 && ratio < 4.5;
      }
      return false;
    });

    return !allNodesNearThreshold;
  });
}
```

---

## Adding New Accessible Components

When creating new components, follow this checklist:

### 1. Semantic HTML First

```tsx
// Good - semantic HTML
<nav aria-label="Main navigation">
  <ul>
    <li><a href="/dashboard">Dashboard</a></li>
  </ul>
</nav>

// Avoid - div soup
<div className="nav">
  <div className="nav-item" onClick={...}>Dashboard</div>
</div>
```

### 2. ARIA Labels for Custom Components

```tsx
// Custom toggle switch
<button
  role="switch"
  aria-checked={enabled}
  aria-label={`${label}: ${enabled ? 'enabled' : 'disabled'}`}
  onClick={() => setEnabled(!enabled)}
>
  <span className={enabled ? 'on' : 'off'} />
</button>
```

### 3. Focus Management

```tsx
// Trap focus in custom dropdown
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Tab' && isOpen) {
    const focusable = dropdownRef.current?.querySelectorAll<HTMLElement>('button, [href], input');
    const first = focusable?.[0];
    const last = focusable?.[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }
};
```

### 4. Test Coverage

Add accessibility tests for new components:

```typescript
// ComponentName.test.tsx
describe('Accessibility', () => {
  it('has no axe violations', async () => {
    const { container } = render(<MyComponent />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('supports keyboard navigation', () => {
    render(<MyComponent />);
    const button = screen.getByRole('button');
    button.focus();
    expect(button).toHaveFocus();
  });

  it('has accessible name', () => {
    render(<MyComponent />);
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });
});
```

---

## Resources

### WCAG Guidelines

- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [Understanding WCAG 2.1](https://www.w3.org/WAI/WCAG21/Understanding/)
- [WCAG Techniques](https://www.w3.org/WAI/WCAG21/Techniques/)

### Testing Tools

- [axe DevTools](https://www.deque.com/axe/devtools/) - Browser extension
- [Lighthouse](https://developer.chrome.com/docs/lighthouse/) - Built into Chrome DevTools
- [WAVE](https://wave.webaim.org/) - Web accessibility evaluator
- [Colour Contrast Analyzer](https://developer.paciellogroup.com/color-contrast-checker/) - Desktop app

### Screen Readers

- [VoiceOver Guide](https://www.apple.com/accessibility/vision/)
- [NVDA User Guide](https://www.nvaccess.org/documentation/)
- [JAWS Documentation](https://www.freedomscientific.com/products/software/jaws/)

---

## Related Documentation

- [Keyboard Patterns](keyboard-patterns.md) - Developer implementation guide
- [Frontend Patterns](patterns/frontend.md) - Component conventions
- [User Keyboard Shortcuts](../user-guide/keyboard-shortcuts.md) - End-user reference
- [User Accessibility Guide](../user-guide/accessibility.md) - End-user accessibility features

---

_Accessibility is not an afterthought - it is a core requirement. Every PR that affects UI should be tested for accessibility compliance._
