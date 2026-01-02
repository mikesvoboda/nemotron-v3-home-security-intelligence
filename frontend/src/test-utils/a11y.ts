/**
 * Accessibility testing utilities using axe-core.
 *
 * This module provides helpers for running automated accessibility checks
 * on rendered components. It integrates with vitest-axe to provide clear
 * assertion messages when accessibility violations are found.
 *
 * @example
 * import { renderWithProviders, screen, checkAccessibility } from '../test-utils';
 *
 * it('has no accessibility violations', async () => {
 *   renderWithProviders(<MyComponent />);
 *   await checkAccessibility();
 * });
 *
 * @example
 * // Check a specific element
 * it('dialog is accessible', async () => {
 *   renderWithProviders(<MyComponent />);
 *   await checkAccessibility(screen.getByRole('dialog'));
 * });
 *
 * @example
 * // Disable specific rules
 * it('component is accessible (ignoring color contrast)', async () => {
 *   renderWithProviders(<MyComponent />);
 *   await checkAccessibility(document.body, { rules: { 'color-contrast': { enabled: false } } });
 * });
 */
import { expect } from 'vitest';
import { axe, configureAxe } from 'vitest-axe';
// Import extend-expect to setup matchers
import 'vitest-axe/extend-expect';

import type { AxeResults, ImpactValue, Result, RunOptions } from 'axe-core';

// Extend vitest types for toHaveNoViolations matcher
declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/no-explicit-any
  interface Assertion<T = any> {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}

/**
 * Default axe configuration for this project.
 * Customized for the Home Security Intelligence dashboard.
 */
const defaultAxeConfig: RunOptions = {
  rules: {
    // Disable rules that may conflict with dark theme styling
    // These can be re-enabled on a per-test basis if needed
    'color-contrast': { enabled: true },
    // Ensure landmark regions are checked
    region: { enabled: true },
    // Check for valid ARIA attributes
    'aria-valid-attr': { enabled: true },
    'aria-valid-attr-value': { enabled: true },
  },
};

/**
 * Configured axe instance for accessibility testing.
 */
const configuredAxe = configureAxe(defaultAxeConfig);

/**
 * Options for accessibility checks.
 */
export interface AccessibilityCheckOptions extends Partial<RunOptions> {
  /**
   * If true, only violations with 'critical' or 'serious' impact are reported.
   * Use this for focused testing on high-priority issues.
   * @default false
   */
  criticalOnly?: boolean;
}

/**
 * Runs accessibility checks on an element or the entire document.
 *
 * This is the primary accessibility testing function. It uses axe-core
 * to analyze the DOM and report any WCAG violations.
 *
 * @param container - Element to check (defaults to document.body)
 * @param options - Axe configuration options
 * @throws AssertionError if accessibility violations are found
 *
 * @example
 * // Basic usage - check entire page
 * await checkAccessibility();
 *
 * @example
 * // Check specific element
 * const dialog = screen.getByRole('dialog');
 * await checkAccessibility(dialog);
 *
 * @example
 * // With custom options
 * await checkAccessibility(document.body, {
 *   rules: { 'color-contrast': { enabled: false } }
 * });
 */
export async function checkAccessibility(
  container: Element | Document = document.body,
  options: AccessibilityCheckOptions = {}
): Promise<void> {
  const { criticalOnly, ...axeOptions } = options;
  // Cast to Element since axe expects Element but we accept Document for convenience
  const element = container instanceof Document ? container.body : container;

  const results = await configuredAxe(element, axeOptions);

  if (criticalOnly) {
    // Filter to only critical and serious violations
    const criticalViolations = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );

    // Create a modified results object
    const filteredResults = {
      ...results,
      violations: criticalViolations,
    };

    expect(filteredResults).toHaveNoViolations();
  } else {
    expect(results).toHaveNoViolations();
  }
}

/**
 * Gets accessibility results without failing the test.
 * Useful for debugging or generating reports.
 *
 * @param container - Element to check (defaults to document.body)
 * @param options - Axe configuration options
 * @returns Full axe results object
 *
 * @example
 * const results = await getAccessibilityResults();
 * console.log(`Found ${results.violations.length} violations`);
 */
export async function getAccessibilityResults(
  container: Element | Document = document.body,
  options: Partial<RunOptions> = {}
): Promise<AxeResults> {
  const element = container instanceof Document ? container.body : container;
  return configuredAxe(element, options);
}

/**
 * Formats accessibility violations into a readable string.
 * Useful for debugging or logging violation details.
 *
 * @param violations - Array of violations from axe results
 * @returns Formatted string describing violations
 *
 * @example
 * const results = await getAccessibilityResults();
 * if (results.violations.length > 0) {
 *   console.log(formatViolations(results.violations));
 * }
 */
export function formatViolations(violations: Result[]): string {
  if (violations.length === 0) {
    return 'No accessibility violations found.';
  }

  return violations
    .map((violation) => {
      const impactBadge = getImpactBadge(violation.impact);
      const nodes = violation.nodes
        .map((node) => `    - ${node.html}\n      ${node.failureSummary}`)
        .join('\n');

      return `
${impactBadge} ${violation.id}: ${violation.description}
  Help: ${violation.helpUrl}
  Affected elements:
${nodes}`;
    })
    .join('\n');
}

/**
 * Gets a visual badge string for the impact level.
 */
function getImpactBadge(impact?: ImpactValue | null): string {
  switch (impact) {
    case 'critical':
      return '[CRITICAL]';
    case 'serious':
      return '[SERIOUS]';
    case 'moderate':
      return '[MODERATE]';
    case 'minor':
      return '[MINOR]';
    default:
      return '[UNKNOWN]';
  }
}

/**
 * Creates an accessibility test helper that checks specific aspects.
 *
 * @example
 * // Create a helper for testing dialogs
 * const checkDialogAccessibility = createAccessibilityHelper({
 *   rules: {
 *     'aria-dialog-name': { enabled: true },
 *     'focus-trap': { enabled: true },
 *   }
 * });
 *
 * it('dialog is accessible', async () => {
 *   await checkDialogAccessibility(screen.getByRole('dialog'));
 * });
 */
export function createAccessibilityHelper(defaultOptions: AccessibilityCheckOptions = {}) {
  return async (container: Element | Document = document.body, options: AccessibilityCheckOptions = {}) => {
    return checkAccessibility(container, { ...defaultOptions, ...options });
  };
}

/**
 * Pre-configured accessibility check for interactive elements (buttons, links, inputs).
 * Focuses on keyboard accessibility and ARIA labeling.
 */
export const checkInteractiveAccessibility = createAccessibilityHelper({
  rules: {
    'button-name': { enabled: true },
    'link-name': { enabled: true },
    'label': { enabled: true },
    'aria-input-field-name': { enabled: true },
  },
});

/**
 * Pre-configured accessibility check for form elements.
 * Focuses on labels, field associations, and error handling.
 */
export const checkFormAccessibility = createAccessibilityHelper({
  rules: {
    'label': { enabled: true },
    'label-title-only': { enabled: true },
    'autocomplete-valid': { enabled: true },
    'select-name': { enabled: true },
  },
});

/**
 * Pre-configured accessibility check for images and media.
 * Focuses on alt text and media alternatives.
 */
export const checkImageAccessibility = createAccessibilityHelper({
  rules: {
    'image-alt': { enabled: true },
    'image-redundant-alt': { enabled: true },
    'svg-img-alt': { enabled: true },
  },
});

/**
 * Pre-configured accessibility check for navigation and landmarks.
 * Focuses on page structure and navigation patterns.
 */
export const checkNavigationAccessibility = createAccessibilityHelper({
  rules: {
    'region': { enabled: true },
    'landmark-one-main': { enabled: true },
    'bypass': { enabled: true },
    'page-has-heading-one': { enabled: true },
  },
});

/**
 * Re-export axe for manual use.
 */
export { axe };
