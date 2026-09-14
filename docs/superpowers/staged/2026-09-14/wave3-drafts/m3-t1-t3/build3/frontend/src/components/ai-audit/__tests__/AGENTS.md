# AI Audit Tests Directory

## Purpose

Contains test files for AI audit components, specifically testing the barrel export verification and functionality of prompt-related components re-exported from the ai-audit module.

## Files

| File                            | Purpose                                              | Status |
| ------------------------------- | ---------------------------------------------------- | ------ |
| `PromptPlayground.test.tsx`     | Barrel export verification and integration tests     | Active |
| `PromptVersionHistory.test.tsx` | Tests for PromptVersionHistory component             | Active |

## Key Test Files

### PromptPlayground.test.tsx

**Purpose:** Verifies barrel export and basic functionality of prompt-related components re-exported from the ai-audit module

**Test Suites:**

1. **PromptPlayground - Barrel Export Verification (NEM-1894)**
   - Verifies component is properly exported from ai-audit barrel
   - Tests rendering when open/closed
   - Tests title and description display
   - Tests model accordion loading from API
   - Tests close button functionality

2. **PromptABTest - Barrel Export Verification**
   - Verifies component export from barrel
   - Tests rendering with results
   - Tests delta indicator display

3. **ABTestStats - Barrel Export Verification**
   - Verifies component and calculateStats function exports
   - Tests rendering with results
   - Tests aggregate statistics calculation (totalTests, avgScoreDelta, improvementRate, etc.)

4. **SuggestionDiffView - Barrel Export Verification**
   - Verifies component export
   - Tests rendering with diff content

5. **SuggestionExplanation - Barrel Export Verification**
   - Verifies component export
   - Tests expand/collapse functionality for impact explanation

**Mocked Dependencies:**
- `../../../services/api` - All API functions (fetchAllPrompts, updateModelPrompt, testPrompt, exportPrompts, importPrompts, fetchEvents)

---

### PromptVersionHistory.test.tsx

**Purpose:** Comprehensive tests for PromptVersionHistory component

**Test Suites:**

1. **Loading State**
   - Renders loading skeleton when loading

2. **Error State**
   - Renders error state when query fails
   - Shows retry button in error state

3. **Empty State**
   - Renders empty state when no versions exist

4. **Data Display**
   - Renders version history table with data
   - Displays version numbers correctly (v1, v2, v3)
   - Displays model names correctly
   - Shows active badge for current version
   - Shows restore button only for non-active versions

5. **Model Filter**
   - Renders model filter dropdown

6. **Refresh Button**
   - Renders refresh button
   - Calls refetch when clicked

7. **Restore Functionality**
   - Shows success message after successful restore
   - Shows error message after failed restore
   - Calls refetch after successful restore

8. **Component Structure**
   - Renders with correct test ID
   - Renders header with title

**Mocked Dependencies:**
- `../../../hooks/useAIAuditQueries` - useAIAuditPromptHistoryQuery hook
- `../../../services/promptManagementApi` - restorePromptVersion function

**Test Utilities:**
- Custom QueryClientProvider wrapper for React Query
- Fake timers for consistent timestamp testing

## Patterns

### Barrel Export Testing

The PromptPlayground tests verify that components are properly re-exported from the ai-audit barrel (`../index.ts`), ensuring consumers can import via:

```tsx
import { PromptPlayground, PromptABTest, ABTestStats } from '../ai-audit';
```

### Mock Data Fixtures

Both test files use consistent mock data structures:
- `ABTestResult` with originalResult/modifiedResult
- `PromptVersionInfo` with model, version, created_at, is_active
- `EnrichedSuggestion` with category, priority, impactExplanation

### QueryClient Wrapper

PromptVersionHistory tests use a factory function for creating test wrappers:

```tsx
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function TestWrapper({ children }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
};
```

### Time Control

PromptVersionHistory tests use fake timers (`vi.useFakeTimers()`) with a fixed `BASE_TIME` for consistent timestamp formatting tests.

## Dependencies

- `@testing-library/react` - render, screen, waitFor
- `@testing-library/user-event` - userEvent.setup()
- `@tanstack/react-query` - QueryClient, QueryClientProvider
- `vitest` - describe, expect, it, vi, beforeEach, afterEach

## Entry Points

**Start here:** `PromptPlayground.test.tsx` - Tests barrel exports and component basics
**Also see:** `PromptVersionHistory.test.tsx` - Tests version history functionality

## Related Issues

- NEM-1894 - Create PromptPlayground component for A/B testing
