# Testing Guide: Bun vs Vitest

## TL;DR

**✅ Use these commands:**
```bash
npm test              # Run Vitest tests
bun run test          # Also runs Vitest tests
```

**❌ Do NOT use:**
```bash
bun test              # This uses Bun's native test runner (incompatible!)
```

---

## Why `bun test` Doesn't Work

This project uses **Vitest** as the test runner, not Bun's native test runner. The tests are written with Vitest-specific APIs and configuration that are incompatible with Bun's test runner.

### Incompatibility Issues

When you run `bun test`, you'll encounter these errors:

1. **`TypeError: mock(module, fn) requires a function`**
   - Cause: Tests use `vi.mock()` which is Vitest-specific
   - Bun's native test runner has a different mocking API

2. **`ReferenceError: document is not defined`**
   - Cause: jsdom environment is configured in `vite.config.ts`
   - Bun's test runner doesn't automatically load jsdom

3. **`TypeError: undefined is not an object (evaluating 'document[isPrepared]')`**
   - Cause: @testing-library/user-event requires jsdom setup
   - Bun's test runner doesn't execute Vitest's setupFiles

### Why Tests Use Vitest

| Feature | Vitest | Bun Native | Status |
|---------|--------|------------|--------|
| `vi.mock()` | ✅ | ❌ Different API | Required by tests |
| jsdom environment | ✅ | ❌ Manual setup | Required by tests |
| setupFiles | ✅ | ❌ Different approach | Required by tests |
| @testing-library/jest-dom | ✅ | ❌ Incompatible | Required by tests |
| Vite integration | ✅ | ⚠️ Limited | Used by project |

---

## How to Run Tests

### Unit Tests (Vitest)

```bash
# Watch mode (recommended for development)
npm test
# or
bun run test

# Run once (CI mode)
npm test -- --run
# or
bun run test -- --run

# Run with coverage
npm run test:coverage
# or
bun run test:coverage

# Run specific test file
npm test -- AlertsPage.test.tsx
# or
bun run test -- AlertsPage.test.tsx

# Open Vitest UI
npm run test:ui
# or
bun run test:ui
```

### E2E Tests (Playwright)

```bash
# Run all E2E tests
npm run test:e2e

# Run with browser visible
npm run test:e2e:headed

# Debug mode
npm run test:e2e:debug

# View test report
npm run test:e2e:report
```

---

## Technical Details

### Test Configuration

Tests are configured in `vite.config.ts`:

```typescript
test: {
  globals: true,
  environment: 'jsdom',           // Browser-like environment
  setupFiles: './src/test/setup.ts',  // Test setup and mocks
  // ... more config
}
```

### Test Setup (`src/test/setup.ts`)

The setup file configures:
- jsdom polyfills (ResizeObserver, IntersectionObserver)
- MSW (Mock Service Worker) for API mocking
- Test cleanup between tests
- Custom matchers from @testing-library/jest-dom

### Vitest-Specific APIs Used

Tests throughout the codebase use:
- `vi.mock()` - Mock modules
- `vi.spyOn()` - Spy on functions
- `vi.mocked()` - TypeScript-safe mock access
- `vi.clearAllMocks()` - Reset mocks
- Custom matchers like `toBeInTheDocument()`

---

## Migration Path (If Needed)

If you need to make tests compatible with Bun's native test runner:

1. **Replace Vitest mocks** with Bun's mock API
2. **Configure jsdom** manually for Bun
3. **Replace setupFiles** with Bun's equivalent
4. **Rewrite or adapt** custom matchers
5. **Update configuration** in `bunfig.toml`

**Estimated effort:** High (affects 100+ test files)

**Recommendation:** Continue using Vitest. It's purpose-built for Vite projects and has excellent React Testing Library integration.

---

## Related Documentation

- [TESTING.md](./TESTING.md) - Comprehensive testing documentation
- [bunfig.toml](./bunfig.toml) - Bun configuration with warnings
- [vite.config.ts](./vite.config.ts) - Test configuration
- [src/test/setup.ts](./src/test/setup.ts) - Test setup file

---

## Summary

| Command | What It Does | Compatible? |
|---------|-------------|-------------|
| `bun test` | Runs Bun's native test runner | ❌ No - will fail |
| `bun run test` | Runs Vitest via package.json script | ✅ Yes - use this |
| `npm test` | Runs Vitest via package.json script | ✅ Yes - use this |

**Always use `bun run test` or `npm test`**, never `bun test` directly.
