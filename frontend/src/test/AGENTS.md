# Frontend Test Setup Directory

## Purpose

Global test configuration and setup for Vitest test runner. Configures test environment, browser API mocks, and automatic cleanup. This is the centralized location for test infrastructure that applies to all unit and component tests.

## Key Files

### `setup.ts`

Test environment configuration loaded automatically before all tests via `vite.config.ts` (`setupFiles: './src/test/setup.ts'`).

## Configuration

### Imports

- `@testing-library/jest-dom/vitest`: DOM matchers for Vitest (e.g., `toBeInTheDocument`, `toHaveClass`)
- `@testing-library/react`: React testing utilities (`cleanup`)
- `vitest`: Test framework (`beforeAll`, `afterEach`)

### Global Setup

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

## Usage

This file is automatically loaded by Vitest via `vite.config.ts`. No manual import required in test files.

The configuration in `vite.config.ts` includes:

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
  css: true,
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

### Available Matchers

With `@testing-library/jest-dom/vitest` imported, all test files have access to:

- `toBeInTheDocument()`: Element exists in DOM
- `toHaveClass(className)`: Element has CSS class
- `toHaveStyle(styles)`: Element has inline styles
- `toHaveTextContent(text)`: Element contains text
- `toBeVisible()`: Element is visible
- `toBeDisabled()`: Element is disabled
- `toHaveAttribute(attr, value)`: Element has attribute
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
npm test

# Run tests once (for CI)
npm test -- --run

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- EventCard.test.tsx

# Run tests with UI
npm run test:ui
```

## Notes

- This setup applies globally to all tests
- No need to import matchers in individual test files
- `cleanup()` runs automatically after each test
- Works seamlessly with React Testing Library
- Compatible with TypeScript
- `globals: true` in config means `describe`, `it`, `expect` are available without imports
- CSS is processed (`css: true`) for components that depend on style calculations
