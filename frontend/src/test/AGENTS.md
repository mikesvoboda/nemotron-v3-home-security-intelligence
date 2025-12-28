# Frontend Test Setup Directory

## Purpose

Global test configuration and setup for Vitest test runner. Configures test environment, browser API mocks, and automatic cleanup. This is the centralized location for test infrastructure that applies to all unit and component tests.

## Key Files

### `setup.ts`

Test environment configuration loaded automatically before all tests via `vite.config.ts` (`setupFiles: './src/test/setup.ts'`).

**Key Responsibilities:**

1. Import `@testing-library/jest-dom/vitest` for DOM matchers
2. Fix HeadlessUI focus issue with jsdom (makes `focus` configurable)
3. Mock `ResizeObserver` for Headless UI Dialog component
4. Mock `IntersectionObserver` for visibility detection components
5. Auto-cleanup rendered components after each test

## Configuration

### Imports

- `@testing-library/jest-dom/vitest`: DOM matchers for Vitest (e.g., `toBeInTheDocument`, `toHaveClass`)
- `@testing-library/react`: React testing utilities (`cleanup`)
- `vitest`: Test framework (`beforeAll`, `afterEach`)

### Global Setup

#### HeadlessUI Focus Fix

```typescript
const originalFocus = HTMLElement.prototype.focus;
Object.defineProperty(HTMLElement.prototype, 'focus', {
  configurable: true,
  enumerable: true,
  writable: true,
  value: originalFocus,
});
```

HeadlessUI tries to set `HTMLElement.prototype.focus` which is getter-only in jsdom. This fix makes it configurable before HeadlessUI loads.

#### Browser API Mocks

Mocks browser APIs not available in jsdom environment:

**ResizeObserver Mock** (added in `beforeAll`):

```typescript
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
```

Required for Headless UI Dialog component which uses ResizeObserver to track viewport changes.

**IntersectionObserver Mock** (added in `beforeAll`):

```typescript
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

Required for Headless UI components that use IntersectionObserver for visibility detection.

#### Automatic Cleanup

```typescript
afterEach(() => {
  cleanup();
});
```

Ensures all rendered components are unmounted and cleaned up after each test. Prevents memory leaks and test pollution.

## Vitest Configuration (vite.config.ts)

This setup file is referenced by the Vitest configuration:

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
  css: true,
  pool: 'forks',
  poolOptions: {
    forks: {
      singleFork: true,
    },
  },
  testTimeout: 10000,
  hookTimeout: 10000,
  coverage: {
    provider: 'v8',
    reporter: ['text', 'json', 'html'],
    thresholds: {
      statements: 95,
      branches: 94,
      functions: 95,
      lines: 95,
    },
  },
}
```

### Configuration Details

| Setting           | Value                    | Purpose                                          |
| ----------------- | ------------------------ | ------------------------------------------------ |
| `globals`         | `true`                   | `describe`, `it`, `expect` available globally    |
| `environment`     | `jsdom`                  | Browser-like DOM environment                     |
| `setupFiles`      | `./src/test/setup.ts`    | This setup file                                  |
| `css`             | `true`                   | Process CSS for style-dependent components       |
| `pool`            | `forks`                  | Use fork pool for memory optimization            |
| `singleFork`      | `true`                   | Prevents heap out of memory errors               |
| `testTimeout`     | `10000`                  | 10 second timeout per test                       |
| `hookTimeout`     | `10000`                  | 10 second timeout for hooks                      |

### Available Matchers

With `@testing-library/jest-dom/vitest` imported, all test files have access to:

- `toBeInTheDocument()`: Element exists in DOM
- `toHaveClass(className)`: Element has CSS class
- `toHaveStyle(styles)`: Element has inline styles
- `toHaveTextContent(text)`: Element contains text
- `toBeVisible()`: Element is visible
- `toBeDisabled()`: Element is disabled
- `toHaveAttribute(attr, value)`: Element has attribute
- `toHaveValue(value)`: Input has value
- `toBeChecked()`: Checkbox/radio is checked
- `toHaveFocus()`: Element has focus
- And many more...

### Example Test Using Setup

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);

    // These matchers are available thanks to setup.ts
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveClass('btn-primary');
  });

  // cleanup() is automatically called after this test
});
```

## Test File Patterns

Tests are discovered by Vitest using these patterns:

- `**/*.test.ts`
- `**/*.test.tsx`
- `**/*.spec.ts`
- `**/*.spec.tsx`

## Running Tests

```bash
# Run tests in watch mode (default)
cd frontend && npm test

# Run tests once (for CI)
npm test -- --run

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- EventCard.test.tsx

# Run tests with UI
npm run test:ui
```

## Coverage Requirements

This project requires **95% coverage** across all metrics:

| Metric       | Threshold |
| ------------ | --------- |
| Statements   | 95%       |
| Branches     | 94%       |
| Functions    | 95%       |
| Lines        | 95%       |

Coverage reports are generated in `./coverage/` directory.

## Testing Library Best Practices

### Query Priority

Use queries in this order (most to least preferred):

1. `getByRole` - Accessible roles (button, heading, etc.)
2. `getByLabelText` - Form inputs with labels
3. `getByPlaceholderText` - Input placeholders
4. `getByText` - Text content
5. `getByDisplayValue` - Current input values
6. `getByAltText` - Image alt text
7. `getByTitle` - Title attribute
8. `getByTestId` - Last resort (data-testid)

### Async Testing

```typescript
import { waitFor, findByText } from '@testing-library/react';

// Use findBy* for async elements
const element = await screen.findByText('Loaded');

// Use waitFor for complex assertions
await waitFor(() => {
  expect(screen.getByText('Updated')).toBeInTheDocument();
});
```

### User Events

```typescript
import userEvent from '@testing-library/user-event';

const user = userEvent.setup();

await user.click(screen.getByRole('button'));
await user.type(screen.getByRole('textbox'), 'Hello');
```

## Related Files

- `/frontend/vite.config.ts` - Vitest configuration
- `/frontend/src/__tests__/` - Configuration tests
- `/frontend/tests/` - Integration and E2E tests

## Notes for AI Agents

- This setup applies globally to all tests
- No need to import matchers in individual test files
- `cleanup()` runs automatically after each test
- Works seamlessly with React Testing Library
- Compatible with TypeScript
- `globals: true` in config means `describe`, `it`, `expect` are available without imports
- CSS is processed (`css: true`) for components that depend on style calculations
- Memory optimization: `pool: 'forks'` with `singleFork: true` prevents heap out of memory
