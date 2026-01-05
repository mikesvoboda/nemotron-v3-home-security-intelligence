# Frontend Test Setup Directory

## Purpose

Global test configuration and setup for Vitest test runner. Configures test environment, browser API mocks, and automatic cleanup. This setup applies to all unit and component tests.

## Directory Contents

```
frontend/src/test/
├── AGENTS.md   # This documentation file
└── setup.ts    # Global test setup (loaded automatically)
```

## Key Files

### setup.ts

Test environment configuration loaded automatically before all tests via `vite.config.ts`:

```typescript
test: {
  setupFiles: './src/test/setup.ts',
}
```

**Responsibilities:**

1. **Import DOM matchers** - `@testing-library/jest-dom/vitest`
2. **Fix HeadlessUI focus issue** - Makes `HTMLElement.prototype.focus` configurable for jsdom
3. **Mock ResizeObserver** - Required for Headless UI Dialog component
4. **Mock IntersectionObserver** - Required for visibility detection components
5. **Comprehensive cleanup** - Handles multiple sources of test leakage:
   - `cleanup()` - Unmounts rendered React components
   - `vi.clearAllMocks()` - Clears mock function calls and instances
   - `vi.clearAllTimers()` - Clears pending fake timers (setTimeout/setInterval)
   - `vi.useRealTimers()` - Resets to real timers if fake timers were used
   - `vi.unstubAllGlobals()` - Unstubs all global mocks (fetch, WebSocket, etc.)
6. **Final cleanup (afterAll)** - Ensures remaining state is cleaned up after all tests

**Browser API Mocks:**

```typescript
// ResizeObserver mock
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// IntersectionObserver mock
globalThis.IntersectionObserver = class IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
  root = null;
  rootMargin = '';
  thresholds: number[] = [];
};
```

## Vitest Configuration

From `vite.config.ts`:

| Setting       | Value                 | Purpose                                   |
| ------------- | --------------------- | ----------------------------------------- |
| `globals`     | `true`                | `describe`, `it`, `expect` without import |
| `environment` | `jsdom`               | Browser-like DOM environment              |
| `setupFiles`  | `./src/test/setup.ts` | This setup file                           |
| `css`         | `true`                | Process CSS for style-dependent tests     |
| `pool`        | `forks`               | Fork pool for memory optimization         |
| `singleFork`  | `true`                | Prevents heap out of memory errors        |
| `testTimeout` | `10000`               | 10 second timeout per test                |
| `hookTimeout` | `10000`               | 10 second timeout for hooks               |

## Available DOM Matchers

With `@testing-library/jest-dom/vitest` imported:

- `toBeInTheDocument()` - Element exists in DOM
- `toHaveClass(className)` - Element has CSS class
- `toHaveStyle(styles)` - Element has inline styles
- `toHaveTextContent(text)` - Element contains text
- `toBeVisible()` - Element is visible
- `toBeDisabled()` - Element is disabled
- `toHaveAttribute(attr, value)` - Element has attribute
- `toHaveValue(value)` - Input has value
- `toBeChecked()` - Checkbox/radio is checked
- `toHaveFocus()` - Element has focus

## Test Discovery

Vitest discovers tests matching these patterns:

- `**/*.test.ts`
- `**/*.test.tsx`
- `**/*.spec.ts`
- `**/*.spec.tsx`

E2E tests in `tests/e2e/` are excluded.

## Running Tests

```bash
# From frontend/ directory
npm test                    # Watch mode (default)
npm test -- --run           # Single run (CI)
npm run test:coverage       # With coverage report
npm run test:ui             # With Vitest UI
npm test -- EventCard.test.tsx  # Specific file
```

## Coverage Configuration

Coverage reports are generated to `./coverage/`:

| Metric     | Threshold |
| ---------- | --------- |
| Statements | 83%       |
| Branches   | 77%       |
| Functions  | 81%       |
| Lines      | 84%       |

Note: Thresholds adjusted based on current coverage levels. See `vite.config.ts` for authoritative values.

**Excluded from Coverage:**

- `src/test/**` - Test setup files
- `src/main.tsx` - Entry point
- `src/types/generated/**` - Auto-generated types
- `**/*.d.ts` - Type declarations
- `**/*.test.{ts,tsx}` - Test files
- `**/index.ts` - Barrel files
- `**/*.example.tsx` - Example files
- `**/Example.tsx` - Example components
- `*.config.{js,ts,cjs,mjs}` - Config files

## Example Test

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import userEvent from '@testing-library/user-event';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);

    // DOM matchers from setup.ts
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveClass('btn-primary');
  });

  // cleanup() runs automatically after this test
});
```

## Related Files

- `/frontend/vite.config.ts` - Vitest configuration
- `/frontend/src/__tests__/` - Configuration tests
- `/frontend/tests/e2e/` - E2E Playwright tests

## Notes for AI Agents

- This setup applies globally to all unit tests
- No need to import matchers in individual test files
- Comprehensive cleanup runs automatically after each test (React, mocks, timers, globals)
- `globals: true` means `describe`, `it`, `expect` are available without imports
- CSS is processed (`css: true`) for components that depend on styles
- Memory optimization via `pool: 'forks'` with `singleFork: true`
- Fake timers are automatically reset to real timers after each test
- Global stubs (fetch, WebSocket) are automatically cleared between tests
