/**
 * Stryker Mutation Testing Configuration
 *
 * This configuration runs mutation testing on a subset of frontend utilities
 * to verify test effectiveness. Start with pure logic modules that have
 * well-defined inputs/outputs and comprehensive tests.
 *
 * WP4.3 DECIDE (2026-09-17): the BACKEND set widened to all of
 * backend/services/ + backend/api/routes/ (that is where the PLAN's risk
 * concentration sits: the coverage-omit modules and the low-assertion-density
 * route tree). This frontend set deliberately stays at the three pure
 * utilities until a mutation baseline exists for a wider frontend set --
 * widening without a baseline produces an unfalsifiable number. Thresholds
 * remain informational (break: null) for the same reason the backend score
 * is a tracked trend, not a merge gate.
 *
 * Target modules:
 * - src/utils/risk.ts: Risk score to level conversion (mirrors backend severity.py)
 * - src/utils/time.ts: Time formatting utilities
 * - src/utils/confidence.ts: Confidence score utilities
 *
 * Usage:
 *   npm run test:mutation
 *
 * For detailed documentation, see docs/developer/patterns/mutation-testing.md
 */

/** @type {import('@stryker-mutator/api').PartialStrykerOptions} */
export default {
  // Target files to mutate (start small with well-tested utility modules)
  mutate: ['src/utils/risk.ts', 'src/utils/time.ts', 'src/utils/confidence.ts'],

  // Test runner configuration
  testRunner: 'vitest',
  vitest: {
    configFile: 'vite.config.ts',
    // Run only relevant tests for faster mutation testing
    // This filters tests to only those that import the mutated modules
    dir: 'src',
  },

  // TypeScript type checking
  checkers: ['typescript'],
  tsconfigFile: 'tsconfig.json',

  // Reporter configuration
  reporters: ['progress', 'clear-text', 'html'],
  htmlReporter: {
    fileName: 'reports/mutation/mutation-report.html',
  },

  // Mutation score thresholds
  // Start with informational (no blocking) and increase as test quality improves
  thresholds: {
    high: 80,
    low: 60,
    break: null, // Set to a number (e.g., 50) to fail CI below this score
  },

  // Performance tuning
  concurrency: 4, // Run 4 mutants in parallel
  timeoutMS: 30000, // 30 second timeout per mutant

  // Ignore specific mutations that are hard to kill or equivalent
  ignorers: [],

  // Files to ignore during mutation testing
  ignorePatterns: [
    'node_modules',
    'dist',
    'coverage',
    'reports',
    '**/*.test.ts',
    '**/*.test.tsx',
    '**/*.spec.ts',
    '**/*.d.ts',
  ],

  // Log level
  logLevel: 'info',

  // Clean temporary files after run
  cleanTempDir: true,
};
