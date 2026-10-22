/**
 * [r299] Pin for audit item Q-179 (ruling 299, record 6321779954).
 *
 * Q-179: the E2E global setup wrote the tour-suppression keys under the
 * origin `https://localhost:8444` while the specs run at `http://localhost:8444`
 * (playwright.config.ts `use.baseURL`). Playwright seeds localStorage per
 * origin, so the keys never landed and the Joyride tour overlay opened and
 * blocked clicks in every spec that doesn't use the shared fixtures' init
 * script (tests/e2e/fixtures/index.ts) — the nightly visual specs and local
 * runs. This pin keeps the three faces of that URL from ever diverging again:
 *
 *   1. the base URL the config hands every spec (use.baseURL),
 *   2. the origin the global setup writes into the storage state,
 *   3. the committed seed file itself (tests/e2e/.auth/storage-state.json),
 *      which golden runs and concurrent-operations' isolated contexts read
 *      WITHOUT running global setup first.
 *
 * The third leg is the DECIDE's guard: the seed stays committed, so any hand
 * edit to either the file or the writer reddens here instead of drifting
 * silently (a committed file whose generator writes a different byte sequence
 * is exactly how the https literal survived next to a correct committed
 * origin until Q-179 was audited).
 *
 * Lives under tests/pinning/, not tests/e2e/: vitest excludes tests/e2e/**
 * (vite.config.ts), and Playwright's testDir is ./tests/e2e — this file must
 * be collected by the unit gate and invisible to both Playwright runners.
 */

import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import e2eConfig from '../../playwright.config';
import { E2E_STORAGE_STATE_ORIGIN, resolveE2eBaseUrl } from '../e2e/base-url';
import { buildStorageStateJson, writeTourSuppressionState } from '../e2e/global-setup';

// Not import.meta.url: under vitest's transform the test file's
// import.meta.url is not a file: URL. vitest always runs with cwd at the
// frontend root (npm run test, CI's `cd frontend && npx vitest run`,
// validate.sh), so resolve from there — readFileSync's error names the path
// if that ever stops holding.
const COMMITTED_SEED_PATH = resolve(process.cwd(), 'tests/e2e/.auth/storage-state.json');

describe('[r299] E2E storage-state origin matches the configured base URL', () => {
  it('the config hands specs the base URL this module resolves', () => {
    // One knob, one resolution: use.baseURL must be the module's answer, so
    // a re-hardcoded literal in either place cannot slip past this leg.
    expect(e2eConfig.use?.baseURL).toBe(resolveE2eBaseUrl());
  });

  it('the state the global setup writes carries the origin the specs run at', () => {
    // Drives the REAL production writer (the same call globalSetup makes),
    // pointed at a temp path. Pre-fix, the writer baked the literal
    // `https://localhost:8444` and this assertion failed — that red is the
    // UR-69 witness for Q-179.
    const dir = mkdtempSync(join(tmpdir(), 'r299-pin-'));
    try {
      const written = JSON.parse(
        readFileSync(writeTourSuppressionState(join(dir, 'state.json')), 'utf8')
      ) as {
        origins: { origin: string; localStorage: { name: string }[] }[];
      };
      expect(written.origins).toHaveLength(1);
      expect(written.origins[0].origin).toBe(E2E_STORAGE_STATE_ORIGIN);
      expect(written.origins[0].origin).toBe(new URL(e2eConfig.use?.baseURL ?? '').origin);
      // And the payload is still exactly the two tour-suppression keys.
      const names = written.origins[0].localStorage.map((entry) => entry.name).sort();
      expect(names).toEqual(['nemotron-tour-completed', 'nemotron-tour-skipped']);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it('regenerating the seed is byte-identical to the committed file', () => {
    // The writer must reproduce the committed bytes exactly (trailing
    // newline included) so a non-golden run never dirties the tree — and so
    // the committed file and its generator cannot drift apart again.
    const committed = readFileSync(COMMITTED_SEED_PATH, 'utf8');
    expect(buildStorageStateJson()).toBe(committed);
  });
});
