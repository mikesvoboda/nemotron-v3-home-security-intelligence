# Frontend Testing Documentation

## Overview

This document describes the testing infrastructure and test coverage for the frontend React application.

## Testing Stack

- **Test Runner**: Vitest
- **Testing Library**: React Testing Library (@testing-library/react)
- **User Interactions**: @testing-library/user-event
- **DOM Matchers**: @testing-library/jest-dom
- **Environment**: jsdom

## Installation

Before running tests, install the required dependencies:

```bash
cd frontend
npm install
```

This will install all testing dependencies listed in `package.json`:

- `@testing-library/react`
- `@testing-library/jest-dom`
- `@testing-library/user-event`
- `jsdom`
- `vitest`

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage

# Run a specific test file
npm test -- Layout.test.tsx
```

## Test Files

### Component Tests

1. **`src/App.test.tsx`**

   - Tests root App component
   - Verifies Layout and DashboardPage integration
   - Checks component hierarchy

2. **`src/components/layout/Layout.test.tsx`**

   - Tests Layout wrapper component
   - Verifies Header and Sidebar rendering
   - Tests children content rendering
   - Checks flex layout structure
   - Validates activeNav state management

3. **`src/components/layout/Header.test.tsx`**

   - Tests Header component
   - Verifies NVIDIA branding elements
   - Tests system status indicator
   - Validates GPU stats placeholder
   - Checks styling and accessibility

4. **`src/components/layout/Sidebar.test.tsx`**

   - Tests Sidebar navigation component
   - Verifies all navigation items render
   - Tests active state highlighting
   - Validates click interactions
   - Checks WIP badge rendering
   - Tests hover states and transitions

5. **`src/components/dashboard/DashboardPage.test.tsx`**
   - Tests DashboardPage component
   - Verifies heading rendering
   - Validates styling and structure

## Test Coverage

### Coverage Areas

Each test file covers:

- **Rendering**: Component renders without crashing
- **Content**: Expected text and elements are displayed
- **Interactions**: User clicks and navigation work correctly
- **Props**: Props are passed and handled correctly
- **Styling**: CSS classes are applied correctly
- **Accessibility**: Proper semantic HTML and ARIA attributes

### Layout Component (8 tests)

- Renders without crashing
- Renders Header component
- Renders Sidebar component
- Renders children content
- Passes activeNav state to Sidebar
- Correct layout structure with flex classes
- Main element has overflow-auto class
- Renders multiple children correctly

### Header Component (14 tests)

- Renders without crashing
- Displays NVIDIA SECURITY title
- Displays POWERED BY NEMOTRON subtitle
- Renders Activity icon
- Displays System Online status
- Has pulsing green status dot
- Displays GPU stats placeholder
- Correct header styling classes
- Title styling validation
- Subtitle with NVIDIA green color
- Proper flex layout structure
- GPU stats styling
- GPU value color
- Accessibility attributes

### Sidebar Component (16 tests)

- Renders without crashing
- Renders all navigation items
- Highlights active navigation item
- Does not highlight inactive items
- Calls onNavChange when clicked
- Calls onNavChange with correct id
- Displays WIP badge
- WIP badge styling
- Renders icons for all items
- Correct sidebar styling
- Navigation buttons full width
- Changes active state on selection
- Renders all 5 navigation items
- Transition classes for smooth hover
- Inactive items have hover classes

### DashboardPage Component (7 tests)

- Renders without crashing
- Displays Dashboard heading
- Heading has correct styling
- Container styling
- Heading is h2 element
- Semantic HTML structure
- Text content validation

### App Component (5 tests)

- Renders without crashing
- Renders Layout component
- Renders DashboardPage inside Layout
- DashboardPage is child of Layout
- Correct component hierarchy

## Testing Best Practices

### Following React Testing Library Principles

1. **Query by Accessibility**: Use `getByRole`, `getByLabelText`, etc.
2. **Avoid Implementation Details**: Don't test internal state or methods
3. **Test User Behavior**: Focus on what users see and do
4. **Use `screen`**: Import queries from `screen` for better error messages
5. **User Events**: Use `userEvent` instead of `fireEvent` for realistic interactions

### Example Test Pattern

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyComponent from './MyComponent';

describe('MyComponent', () => {
  it('handles user interaction', async () => {
    const user = userEvent.setup();
    render(<MyComponent />);

    const button = screen.getByRole('button', { name: /click me/i });
    await user.click(button);

    expect(screen.getByText('Clicked!')).toBeInTheDocument();
  });
});
```

## Configuration

### Vite Config (`vite.config.ts`)

```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
  css: true,
}
```

### Test Setup (`src/test/setup.ts`)

- Extends Vitest's expect with jest-dom matchers
- Automatic cleanup after each test
- Global test utilities

## Troubleshooting

### Common Issues

1. **Module not found errors**: Run `npm install` to ensure all dependencies are installed

2. **Tests fail with CSS errors**: The `css: true` option in vite.config.ts should handle this

3. **Mock not working**: Ensure mocks are defined before the component import using `vi.mock()`

4. **Async tests timing out**: Use `await` with userEvent interactions and increase timeout if needed

## Future Enhancements

- Add integration tests for API interactions
- Add E2E tests with Playwright or Cypress
- Set up test coverage thresholds
- Add visual regression tests
- Test WebSocket connections
- Test error boundaries

## References

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
