# Test Utilities Directory

## Purpose

Provides reusable test helpers and factories to reduce test boilerplate and ensure consistent testing patterns across the Home Security Intelligence frontend codebase.

## Directory Contents

```
frontend/src/test-utils/
├── AGENTS.md              # This documentation file
├── index.ts               # Central export point for all utilities
├── renderWithProviders.tsx # Custom render with providers
├── factories.ts           # Test data factories
└── test-utils.test.tsx    # Tests for test utilities
```

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

### `index.ts`

Central export point for all utilities. Import everything from here:

```tsx
import { renderWithProviders, screen, createEvent } from '../test-utils';
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

## Conventions

1. **Always import from `test-utils`** - Use the central export for consistency
2. **Use factories for test data** - Avoid hardcoding test data
3. **Override only what matters** - Let factories provide sensible defaults

## Notes for AI Agents

- Import everything from `../test-utils` rather than individual files
- Factories create valid test data matching backend API responses
- `renderWithProviders` handles all React context setup automatically
- Tests for these utilities are in `test-utils.test.tsx`
