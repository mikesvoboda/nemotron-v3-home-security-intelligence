# Frontend Testing Quick Start

## Installation

```bash
cd frontend
npm install
```

This will install all required testing dependencies:
- `@testing-library/react` - React component testing utilities
- `@testing-library/jest-dom` - Custom matchers for DOM testing
- `@testing-library/user-event` - User interaction simulation
- `jsdom` - DOM implementation for Node.js
- `vitest` - Fast unit test framework

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode (auto-rerun on changes)
npm test -- --watch

# Run tests with UI dashboard
npm run test:ui

# Run tests with coverage report
npm run test:coverage

# Run a specific test file
npm test -- Header.test.tsx

# Run tests matching a pattern
npm test -- --grep "renders"
```

## Test Summary

**Total Test Files**: 5
**Total Test Cases**: 49+

### Test Coverage by Component

| Component | Test File | Test Cases |
|-----------|-----------|------------|
| App | `src/App.test.tsx` | 5 |
| Layout | `src/components/layout/Layout.test.tsx` | 8 |
| Header | `src/components/layout/Header.test.tsx` | 14 |
| Sidebar | `src/components/layout/Sidebar.test.tsx` | 15+ |
| DashboardPage | `src/components/dashboard/DashboardPage.test.tsx` | 7 |

## What's Tested

- Component rendering without crashes
- Text content and element display
- User interactions (clicks, navigation)
- Props handling and state management
- CSS classes and styling
- Accessibility attributes
- Component hierarchy and integration

## Configuration Files

- `vite.config.ts` - Vitest configuration
- `src/test/setup.ts` - Test environment setup
- `package.json` - Testing dependencies and scripts

## Next Steps

1. Install dependencies: `npm install`
2. Run tests: `npm test`
3. Review coverage: `npm run test:coverage`
4. Read detailed docs: See `TESTING.md` for comprehensive documentation

## Troubleshooting

If tests fail to run:

1. Ensure all dependencies are installed: `npm install`
2. Clear cache: `rm -rf node_modules && npm install`
3. Check Node.js version: `node --version` (requires Node.js 18+)

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Install dependencies
  run: cd frontend && npm install

- name: Run tests
  run: cd frontend && npm test

- name: Generate coverage
  run: cd frontend && npm run test:coverage
```
