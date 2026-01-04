/**
 * Accessibility Testing Utilities
 *
 * Provides helper functions for accessibility (a11y) testing using axe-core.
 * Configured for WCAG 2.1 AA compliance, which covers:
 * - Perceivable: Text alternatives, adaptable content, distinguishable content
 * - Operable: Keyboard accessible, enough time, seizures, navigable
 * - Understandable: Readable, predictable, input assistance
 * - Robust: Compatible with assistive technologies
 *
 * @see https://www.w3.org/WAI/WCAG21/quickref/
 * @see https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright
 */

import type { Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { AxeResults, Result } from 'axe-core';

/**
 * Configuration options for accessibility checks
 */
export interface A11yCheckOptions {
  /**
   * Specific tags to check (e.g., 'wcag2a', 'wcag2aa', 'wcag21aa')
   * Defaults to WCAG 2.1 AA compliance
   */
  tags?: string[];

  /**
   * Specific rules to disable (use sparingly and document reasoning)
   */
  disableRules?: string[];

  /**
   * CSS selector to limit the check to a specific region
   */
  include?: string;

  /**
   * CSS selectors to exclude from the check
   */
  exclude?: string[];
}

/**
 * Formatted accessibility violation for better error messages
 */
export interface FormattedViolation {
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

/**
 * Formats axe-core violations into readable error messages
 */
function formatViolations(violations: Result[]): FormattedViolation[] {
  return violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact || 'unknown',
    description: violation.description,
    help: violation.help,
    helpUrl: violation.helpUrl,
    nodes: violation.nodes.map((node) => ({
      html: node.html,
      target: node.target as string[],
      failureSummary: node.failureSummary || '',
    })),
  }));
}

/**
 * Generates a human-readable summary of violations
 */
function generateViolationSummary(violations: FormattedViolation[]): string {
  if (violations.length === 0) {
    return 'No accessibility violations found.';
  }

  const lines: string[] = [
    `Found ${violations.length} accessibility violation(s):`,
    '',
  ];

  violations.forEach((violation, index) => {
    lines.push(`${index + 1}. [${violation.impact.toUpperCase()}] ${violation.id}`);
    lines.push(`   Description: ${violation.description}`);
    lines.push(`   Help: ${violation.help}`);
    lines.push(`   More info: ${violation.helpUrl}`);
    lines.push(`   Affected elements (${violation.nodes.length}):`);
    violation.nodes.forEach((node, nodeIndex) => {
      lines.push(`     ${nodeIndex + 1}. ${node.target.join(' > ')}`);
      lines.push(`        HTML: ${node.html.slice(0, 100)}${node.html.length > 100 ? '...' : ''}`);
      if (node.failureSummary) {
        lines.push(`        Fix: ${node.failureSummary}`);
      }
    });
    lines.push('');
  });

  return lines.join('\n');
}

/**
 * Default WCAG 2.1 AA tags for compliance checking
 */
const DEFAULT_WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa'];

/**
 * Known issues that are acceptable in this application.
 * Each rule has documented reasoning for why it's disabled.
 *
 * NOTE: Add rules here only after careful consideration.
 * All exclusions should be reviewed periodically.
 */
const KNOWN_ISSUE_RULES: string[] = [
  // No known issues at this time.
  // When adding rules, document the reasoning:
  // Example:
  // 'color-contrast' - Third-party Tremor components with custom theming
];

/**
 * Performs an accessibility check on the current page state
 *
 * @param page - Playwright Page object
 * @param options - Optional configuration for the check
 * @returns AxeResults containing violations, passes, and other metadata
 *
 * @example
 * ```typescript
 * const results = await checkAccessibility(page);
 * expect(results.violations).toEqual([]);
 * ```
 */
export async function checkAccessibility(
  page: Page,
  options: A11yCheckOptions = {}
): Promise<AxeResults> {
  const {
    tags = DEFAULT_WCAG_TAGS,
    disableRules = KNOWN_ISSUE_RULES,
    include,
    exclude = [],
  } = options;

  let builder = new AxeBuilder({ page }).withTags(tags);

  // Disable known issue rules
  if (disableRules.length > 0) {
    builder = builder.disableRules(disableRules);
  }

  // Limit scope if specified
  if (include) {
    builder = builder.include(include);
  }

  // Exclude specific elements
  if (exclude.length > 0) {
    exclude.forEach((selector) => {
      builder = builder.exclude(selector);
    });
  }

  return builder.analyze();
}

/**
 * Performs an accessibility check and returns formatted violations
 * with detailed, human-readable error messages
 *
 * @param page - Playwright Page object
 * @param options - Optional configuration for the check
 * @returns Object containing violations array and summary string
 *
 * @example
 * ```typescript
 * const { violations, summary } = await checkAccessibilityWithDetails(page);
 * if (violations.length > 0) {
 *   console.log(summary);
 * }
 * expect(violations).toEqual([]);
 * ```
 */
export async function checkAccessibilityWithDetails(
  page: Page,
  options: A11yCheckOptions = {}
): Promise<{ violations: FormattedViolation[]; summary: string; raw: AxeResults }> {
  const results = await checkAccessibility(page, options);
  const violations = formatViolations(results.violations);
  const summary = generateViolationSummary(violations);

  return {
    violations,
    summary,
    raw: results,
  };
}

/**
 * Asserts that a page has no accessibility violations.
 * Provides detailed error output if violations are found.
 *
 * @param page - Playwright Page object
 * @param options - Optional configuration for the check
 * @throws Error with detailed violation information if any found
 *
 * @example
 * ```typescript
 * // In a test
 * await page.goto('/dashboard');
 * await assertNoA11yViolations(page);
 * ```
 */
export async function assertNoA11yViolations(
  page: Page,
  options: A11yCheckOptions = {}
): Promise<void> {
  const { violations, summary } = await checkAccessibilityWithDetails(page, options);

  if (violations.length > 0) {
    throw new Error(`Accessibility violations found:\n\n${summary}`);
  }
}

/**
 * Gets a count of violations grouped by impact level
 *
 * @param results - AxeResults from checkAccessibility
 * @returns Object with counts for each impact level
 */
export function getViolationsByImpact(
  results: AxeResults
): { critical: number; serious: number; moderate: number; minor: number } {
  const counts = { critical: 0, serious: 0, moderate: 0, minor: 0 };

  results.violations.forEach((violation) => {
    const impact = violation.impact as keyof typeof counts;
    if (impact in counts) {
      counts[impact]++;
    }
  });

  return counts;
}

/**
 * Checks if the page has any critical or serious accessibility violations
 * Useful for CI/CD gates where minor issues might be tolerated temporarily
 *
 * @param page - Playwright Page object
 * @param options - Optional configuration for the check
 * @returns true if no critical/serious violations, false otherwise
 */
export async function hasNoCriticalA11yViolations(
  page: Page,
  options: A11yCheckOptions = {}
): Promise<boolean> {
  const results = await checkAccessibility(page, options);
  const { critical, serious } = getViolationsByImpact(results);
  return critical === 0 && serious === 0;
}

/**
 * Filter violations to only include specific impact levels
 *
 * @param results - AxeResults from checkAccessibility
 * @param impactLevels - Array of impact levels to include
 * @returns Filtered array of violations
 */
export function filterViolationsByImpact(
  results: AxeResults,
  impactLevels: ('critical' | 'serious' | 'moderate' | 'minor')[]
): Result[] {
  return results.violations.filter(
    (violation) => violation.impact && impactLevels.includes(violation.impact as 'critical' | 'serious' | 'moderate' | 'minor')
  );
}
