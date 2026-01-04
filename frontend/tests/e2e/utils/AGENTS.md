# E2E Test Utilities Directory

## Purpose

Utility functions and helpers for E2E tests, including accessibility testing with axe-core. These utilities provide consistent patterns for accessibility compliance checking across all E2E test specs.

## Key Files

| File               | Purpose                                   |
| ------------------ | ----------------------------------------- |
| `index.ts`         | Central exports for all utilities         |
| `accessibility.ts` | Accessibility (a11y) testing with axe-core|

## accessibility.ts - Accessibility Testing

Provides helper functions for WCAG 2.1 AA compliance testing using axe-core.

### Exports

| Export                        | Type     | Purpose                                        |
| ----------------------------- | -------- | ---------------------------------------------- |
| `checkAccessibility`          | Function | Run basic accessibility check on page          |
| `checkAccessibilityWithDetails` | Function | Run check and return formatted violations    |
| `assertNoA11yViolations`      | Function | Assert no violations (throws on failure)       |
| `getViolationsByImpact`       | Function | Group violations by impact level               |
| `hasNoCriticalA11yViolations` | Function | Check only for critical violations             |
| `filterViolationsByImpact`    | Function | Filter violations by impact level              |
| `A11yCheckOptions`            | Type     | Configuration options for checks               |
| `FormattedViolation`          | Type     | Formatted violation for error messages         |

### A11yCheckOptions Interface

```typescript
interface A11yCheckOptions {
  /** Tags to check (e.g., 'wcag2a', 'wcag2aa', 'wcag21aa') */
  tags?: string[];
  /** Rules to disable (document reasoning) */
  disableRules?: string[];
  /** CSS selector to limit check scope */
  include?: string;
  /** CSS selectors to exclude from check */
  exclude?: string[];
}
```

### FormattedViolation Interface

```typescript
interface FormattedViolation {
  id: string;
  impact: string;
  description: string;
  help: string;
  helpUrl: string;
  nodes: {
    html: string;
    target: string[];
    failureSummary: string;
  }[];
}
```

### Usage Examples

```typescript
import { checkAccessibility, assertNoA11yViolations } from '../utils';

// Basic accessibility check
test('page is accessible', async ({ page }) => {
  await page.goto('/');
  await assertNoA11yViolations(page);
});

// Check specific region
test('modal is accessible', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="open-modal"]');
  await assertNoA11yViolations(page, {
    include: '[role="dialog"]',
  });
});

// Allow certain violations
test('page with known issues', async ({ page }) => {
  await page.goto('/');
  await assertNoA11yViolations(page, {
    disableRules: ['color-contrast'], // Document why this is disabled
  });
});

// Get detailed violation report
test('check with details', async ({ page }) => {
  await page.goto('/');
  const { violations, summary } = await checkAccessibilityWithDetails(page);
  if (violations.length > 0) {
    console.log(summary);
  }
});

// Check for critical only
test('no critical violations', async ({ page }) => {
  await page.goto('/');
  const hasCritical = await hasNoCriticalA11yViolations(page);
  expect(hasCritical).toBe(true);
});
```

## WCAG 2.1 AA Standards

The utilities default to WCAG 2.1 AA compliance, which includes:

### Perceivable
- Text alternatives for non-text content
- Captions and alternatives for audio/video
- Adaptable content presentation
- Distinguishable content (color contrast 4.5:1)

### Operable
- Keyboard accessible (all functionality)
- Enough time to read and use content
- No content that causes seizures
- Navigable (skip links, focus order, link purpose)

### Understandable
- Readable text content
- Predictable web page operation
- Input assistance (error identification, labels)

### Robust
- Compatible with assistive technologies
- Valid HTML/ARIA usage

## Impact Levels

Violations are categorized by impact:

| Impact   | Description                                 |
| -------- | ------------------------------------------- |
| critical | Users cannot use the functionality at all   |
| serious  | Users have significant difficulty           |
| moderate | Users may have some difficulty              |
| minor    | Users may be inconvenienced                 |

## Dependencies

- `@axe-core/playwright` - Axe accessibility testing integration
- `axe-core` - Core accessibility rules engine

## Integration with Test Specs

The `accessibility.spec.ts` in `specs/` uses these utilities:

```typescript
import { test } from '@playwright/test';
import { assertNoA11yViolations } from '../utils';
import { DashboardPage } from '../pages';

test.describe('Accessibility', () => {
  test('dashboard is WCAG 2.1 AA compliant', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.waitForDashboardLoad();
    await assertNoA11yViolations(page);
  });
});
```

## Notes for AI Agents

- Always use `assertNoA11yViolations` for strict compliance testing
- Use `hasNoCriticalA11yViolations` for less strict checks
- Document any `disableRules` with reasoning in comments
- Use `include` option to scope checks to specific components
- Violations include helpful URLs for remediation guidance
- Impact levels help prioritize fixes
- Tests run against rendered DOM, not source code

## Entry Points

1. **Start here:** `index.ts` - See available exports
2. **Main utility:** `accessibility.ts` - Understand checking patterns
3. **Usage example:** `../specs/accessibility.spec.ts` - See in action
