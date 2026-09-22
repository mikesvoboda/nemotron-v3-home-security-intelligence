# docs/testing/

## Purpose

Historical marker directory. The testing analysis reports that used to live
here (the 2026-01 integration-coverage snapshot and the TDD "red phase" test
summaries) were point-in-time artifacts of shipped work and now live in
`docs/archive/`.

## Where the living documentation is

- **Coverage state:** `docs/developer/test-coverage.md` (kept current; CI publishes
  the real numbers)
- **Testing guide & TDD workflow:** `docs/developer/testing.md`,
  `docs/developer/testing-workflow.md`
- **Test patterns:** `docs/developer/patterns/AGENTS.md`

## Gotcha

Do not quote the coverage tables inside `docs/archive/INTEGRATION_TEST_COVERAGE_ANALYSIS.md`
— it measures ~2,300 integration tests against today's ~4,300. It exists only as
historical record of the 2026-01 analysis.
