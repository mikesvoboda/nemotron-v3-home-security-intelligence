# Frontend Test Setup Directory

## Purpose

Global test configuration and setup for Vitest test runner.

## Key Files

### `setup.ts`

Test environment configuration loaded before all tests.

## Configuration

### Imports

- `@testing-library/jest-dom/vitest`: DOM matchers for Vitest (e.g., `toBeInTheDocument`, `toHaveClass`)
- `@testing-library/react`: React testing utilities (`cleanup`)
- `vitest`: Test framework (`afterEach`)

### Global Setup

#### Automatic Cleanup

```typescript
afterEach(() => {
  cleanup();
});
```

Ensures all rendered components are unmounted and cleaned up after each test. Prevents memory leaks and test pollution.

## Usage

This file is automatically loaded by Vitest via `vitest.config.ts` (or similar). No manual import required in test files.

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

## Notes

- This setup applies globally to all tests
- No need to import matchers in individual test files
- `cleanup()` runs automatically after each test
- Works seamlessly with React Testing Library
- Compatible with TypeScript
