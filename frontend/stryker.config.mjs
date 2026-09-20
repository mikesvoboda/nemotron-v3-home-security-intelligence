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
    // WP3.3 note (measured): `related` selection is ON (the stryker-9
    // default) and is exactly this intent — but it only WORKS once the test
    // files exist in the sandbox; the original "No tests were found" death
    // was the ignorePatterns bug below deleting them, and switching
    // related:false to "fix" it only widened discovery to the whole 795-file
    // suite (hitting the R-T7-quarantined EventCard red, which stryker
    // ignores the quarantine for). Root cause first; related stays on.
  },

  // TypeScript type checking
  // WP3.3: tsconfig.stryker.json, not tsconfig.json — the checker followed
  // tsconfig.json's `references` into tsconfig.node.json (program =
  // vite.config.ts), where vite 7's ServerOptions rejects `https: true`, and
  // TypescriptChecker.init died BEFORE mutating anything. The error is in a
  // config file, invisible to build/typecheck (src-only program), and not
  // what mutation testing measures. tsconfig.stryker.json pins the checker
  // to the src+tests program the repo's gates already enforce. See that
  // file's header for the measured evidence.
  checkers: ['typescript'],
  tsconfigFile: 'tsconfig.stryker.json',

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
  // WP3.3 (measured): the DEFAULT 5-minute dry-run budget killed the
  // 3-module run ("Initial test run timed out!" at 5m02s,
  // stryker-full-baseline.log 2026-09-20). The dry run executes EVERY
  // related test once under coverage instrumentation, and the three
  // utils' related union covers most of the suite (time.ts is imported
  // everywhere). This is a one-off harness budget fitted to the repo's
  // suite runtime — it adjudicates no test verdict (the map it builds
  // decides mutants), so it is not a test-timeout cap. MEASURED dry-run
  // wall (stryker-dryonly.log, --dryRunOnly RC=0): 1749 tests in 5m45s —
  // net test time 109s, runner overhead 236s (per-test instrumentation
  // dominates 3:1). The 5m default was marginally short; 20m carries the
  // observed wall with slack for suite growth.
  dryRunTimeoutMinutes: 20,

  // Ignore specific mutations that are hard to kill or equivalent
  ignorers: [],

  // Files to ignore during mutation testing
  // WP3.3 (measured): these patterns excluded files from the SANDBOX.
  // stryker copies the project into .stryker-tmp and runs tests
  // there; ignoring '**/*.test.ts' deleted the very tests the runner needed,
  // so the dry run saw "No tests were found" and stryker exited prematurely.
  // That, layered on the tsconfig-reference checker crash, is why this
  // harness has never produced a number. Test files MUST be copied; they
  // cannot be mutated anyway because `mutate:` above is an explicit allowlist.
  ignorePatterns: [
    'node_modules',
    'dist',
    'coverage',
    'reports',
    '**/*.d.ts',
    // WP3.3 SANDBOX PARITY with the R-T7-VITEST quarantine (vite.config.ts
    // `test.exclude`, 16 files / 62 deterministic failures). WHY copying them
    // is the problem and excluding via `exclude` is not: stryker's `related`
    // mode passes test files to vitest EXPLICITLY, and explicit file args
    // override vitest's `exclude` — the quarantine that `npm test` honors did
    // not apply inside the sandbox, so the dry run died on EventCard's
    // snooze red before any mutant ran. Not-copying is the only lever stryker
    // has (ignorePatterns gates the sandbox copy). Same 16 files, same
    // meaning as the R-T7 list — R-4 applies (into quarantine free; these
    // files are ALREADY quarantined in the repo's own test layer).
    // None of them is in the mutate set or a direct test of it.
    'src/components/settings/NotificationSettings.test.tsx',
    'src/components/events/EventTimeline.test.tsx',
    'src/components/alerts/AlertsPage.test.tsx',
    'src/components/events/EventCard.test.tsx',
    'src/components/entities/ReidHistoryPanel.test.tsx',
    'src/components/system/WorkerManagementPanel.test.tsx',
    'src/__tests__/auth-flow.test.tsx',
    'src/components/pyroscope/PyroscopePage.test.tsx',
    'src/components/dashboard/SummaryCards.integration.test.tsx',
    'src/components/entities/TrustClassificationControls.test.tsx',
    'src/hooks/__tests__/integration/race-conditions.integration.test.ts',
    'src/hooks/__tests__/useHouseholdApi.test.ts',
    'src/hooks/__tests__/useSettingsApi.test.tsx',
    'src/components/events/TimeGroupedEvents.simple.test.tsx',
    'src/components/system/SystemHealthIndicator.test.tsx',
    'src/components/zones/ZoneTimelineScrubber.test.tsx',
  ],

  // Log level
  logLevel: 'info',

  // Clean temporary files after run
  cleanTempDir: true,
};
