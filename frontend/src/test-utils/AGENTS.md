# Test Utilities

This directory contains shared test utilities for the Home Security Intelligence frontend.

## Purpose

Provides reusable test helpers, factories, and accessibility testing utilities to reduce test boilerplate and ensure consistent testing patterns across the codebase.

## Key Files

### `renderWithProviders.tsx`

Custom render function that wraps components with all required providers:

- MemoryRouter for routing
- SidebarContext for layout state
- Pre-configured userEvent instance

```tsx
import { renderWithProviders, screen } from '../test-utils';

const { user } = renderWithProviders(<MyComponent />, {
  route: '/settings',
  sidebarContext: { isMobileMenuOpen: true },
});

await user.click(screen.getByRole('button'));
```

### `factories.ts`

Test data factories for creating mock objects with sensible defaults:

- `createEvent()` / `createEvents()` - Security events
- `createDetection()` / `createDetections()` - AI detections
- `createCamera()` / `createCameras()` - Camera configs
- `createServiceStatus()` - Service health statuses
- `createGpuStats()` - GPU statistics
- `createSystemHealth()` - System health responses
- `createTimestamp()` - Timestamp utilities
- WebSocket message factories

```tsx
const event = createEvent({ risk_score: 85 });
const cameras = createCameras(5);
```

### `a11y.ts`

Accessibility testing utilities using axe-core:

- `checkAccessibility()` - Primary accessibility check
- `getAccessibilityResults()` - Get results without failing
- `formatViolations()` - Format violations for debugging
- Pre-configured helpers for specific patterns:
  - `checkInteractiveAccessibility()` - Buttons, links, inputs
  - `checkFormAccessibility()` - Form fields
  - `checkImageAccessibility()` - Images and media
  - `checkNavigationAccessibility()` - Landmarks and navigation

```tsx
it('is accessible', async () => {
  const { container } = renderWithProviders(<MyComponent />);
  await checkAccessibility(container);
});
```

### `index.ts`

Central export point for all utilities. Import everything from here:

```tsx
import { renderWithProviders, screen, createEvent, checkAccessibility } from '../test-utils';
```

## Usage Patterns

### Basic Component Test

```tsx
import { describe, it, expect } from 'vitest';
import { renderWithProviders, screen, createEvent } from '../../test-utils';
import EventCard from './EventCard';

describe('EventCard', () => {
  it('renders event details', () => {
    const event = createEvent({ camera_name: 'Front Door' });
    renderWithProviders(<EventCard {...event} />);
    expect(screen.getByText('Front Door')).toBeInTheDocument();
  });
});
```

### With User Interaction

```tsx
it('handles click', async () => {
  const onClick = vi.fn();
  const { user } = renderWithProviders(<button onClick={onClick}>Click me</button>);

  await user.click(screen.getByRole('button'));
  expect(onClick).toHaveBeenCalled();
});
```

### Accessibility Testing

```tsx
describe('accessibility', () => {
  it('has no violations', async () => {
    const { container } = renderWithProviders(<MyComponent />);
    await checkAccessibility(container);
  });

  it('passes with custom rules', async () => {
    const { container } = renderWithProviders(<MyComponent />);
    await checkAccessibility(container, {
      rules: { 'color-contrast': { enabled: false } },
    });
  });
});
```

## Conventions

1. **Always import from `test-utils`** - Use the central export for consistency
2. **Use factories for test data** - Avoid hardcoding test data
3. **Add accessibility tests** - All components should have at least basic a11y checks
4. **Document known issues** - If disabling rules, add a comment explaining why
