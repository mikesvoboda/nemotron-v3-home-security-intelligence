/**
 * E2E Test Utilities - Central Export
 *
 * Re-exports all utility modules for convenient importing in test specs.
 */

export {
  checkAccessibility,
  checkAccessibilityWithDetails,
  assertNoA11yViolations,
  getViolationsByImpact,
  hasNoCriticalA11yViolations,
  filterViolationsByImpact,
  type A11yCheckOptions,
  type FormattedViolation,
} from './accessibility';
