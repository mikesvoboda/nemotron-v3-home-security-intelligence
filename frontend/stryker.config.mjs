/**
 * Stryker Mutation Testing Configuration
 *
 * This configuration runs mutation testing on a subset of frontend utilities
 * to verify test effectiveness. Start with pure logic modules that have
 * well-defined inputs/outputs and comprehensive tests.
 *
 * Target modules:
 * - src/utils/risk.ts: Risk score to level conversion (mirrors backend severity.py)
 * - src/utils/time.ts: Time formatting utilities
 * - src/utils/confidence.ts: Confidence score utilities
 *
 * Usage:
 *   npm run test:mutation
 *
 * For detailed documentation, see docs/MUTATION_TESTING.md
 */

/** @type {import('@stryker-mutator/api').PartialStrykerOptions} */
export default {
  // Target files to mutate (start small with well-tested utility modules)
  mutate: [
    'src/utils/risk.ts',
    'src/utils/time.ts',
    'src/utils/confidence.ts',
  ],

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
