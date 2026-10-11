/**
 * F-160 + F-161 + F-162 (inventory 3.8): Test Data Management — seed cameras,
 * seed events, seed pipeline latency, and the typed-confirmation destructive
 * reset, in one file so the destructive row runs last inside it.
 *
 * Why one file, declared in this order: the golden project is serial
 * (workers: 1), and a database reset must be the LAST mutation these rows make
 * — the seed legs need cameras to exist, and the reset deletes
 * Event/Detection/Camera rows (backend/api/routes/admin.py clear_seeded_data).
 *
 * The measured contracts this encodes (all on the harness stack):
 * - POST /api/admin/seed/cameras caps count at 6 (admin.py:49 `le=6`) while
 *   the panel's select offers 5/10/25/50 and defaults to 10 — the default
 *   click answers 422 VALIDATION_ERROR on EVERY stack, because FastAPI
 *   validates the body before seed_cameras runs (a pre-existing-cameras DB
 *   cannot rescue it). The row says "picks a count", so the golden path
 *   picks 5, which is what a working click is; the option/cap mismatch is
 *   recorded in the inventory row's evidence cell, not hidden. The Pipeline
 *   row has the same shape of break: TestDataPanel maps days →
 *   time_span_hours = days*24 (TestDataPanel.tsx:91) against a le=168 cap,
 *   so options 14/30/90 send 336/720/2160 and 422 (measured); 7 — the
 *   default — is the only legal choice.
 * - Tremor's Select is a HIDDEN native <select> plus a Headless UI Listbox,
 *   and React state follows only the LISTBOX. playwright selectOption() on
 *   the hidden select fires a DOM change the component never listens to
 *   (measured: POST still carried the default after selectOption('5'));
 *   run 3's F-161 "pass" was that no-op hiding an unexercised control. The
 *   specs below drive the listbox the user actually sees.
 * - clear_existing defaults False (admin.py:50): seeding does NOT wipe the
 *   harness cameras; the probe measured cleared=0 beside 5 created.
 * - Full Database Reset needs the literal "RESET DATABASE" typed
 *   (TestDataPanel.tsx:213) and its toast reads "Database reset complete".
 * - Camera ids are slug-derived and STABLE across delete+recreate (measured:
 *   all five harness cameras came back with identical ids), so the restore
 *   leg below leaves dashboard-drop's camera-id polling intact even on retry.
 *
 * Destructive-row discipline: this spec only runs the reset when the harness
 * exported FEATURE_CHECK_CAMERAS — the restore contract is not optional.
 */
import { readFileSync } from 'node:fs';

import type { Locator, Page } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import { api, authPost, closedByGuard, loginAsAdmin, openSection, pollApi, readOpsHarness } from './harness';

const harness = readOpsHarness();
const CAMERAS_FILE = process.env.FEATURE_CHECK_CAMERAS ?? '';

const CAMERA_TARGET = '/cameras'; // the watcher's root inside the backend container

/**
 * Pick an option in a SeedRow's Tremor Select by driving the LISTBOX (header
 * comment: the hidden native select is a no-op path). Options render as bare
 * numbers (SeedRow.tsx maps options to <SelectItem value={String(option)}>
 * {option}</SelectItem>), so the accessible name is the number itself —
 * exact:true so '5' cannot match '50'.
 */
async function pickSeedCount(
  page: Page,
  panel: Locator,
  row: 0 | 1 | 2, // SeedRow order in the panel: Cameras, Events, Pipeline Data
  value: '5' | '50' | '7',
): Promise<void> {
  // Measured probe path (listbox_probe): this button click opens the Headless
  // UI list and the option click drives React state (POST then carried
  // {"count":5} → 201 → toast). Do NOT swap back to selectOption(): it only
  // moves the hidden native select, which the component ignores. Options
  // render into a body-level portal, so the option is a PAGE locator.
  await panel.locator('button[aria-haspopup="listbox"]').nth(row).click();
  await page.getByRole('option', { name: value, exact: true }).click();
}

test.describe('golden path: test data management @critical', () => {
  test.setTimeout(120_000);

  test('seed cameras (F-160): picking a legal count creates cameras and toasts', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'test-data');
    const panel = page.getByTestId('test-data-panel');
    await expect(panel).toBeVisible();

    // Row 0 = Cameras (header: pick 5, the one legal option — the default 10
    // is 422 by validation, not by stack state).
    await pickSeedCount(page, panel, 0, '5');
    await panel.getByRole('button', { name: 'Seed Cameras' }).click();
    // filter(), not nth(): sonner stacks toasts and newest-to-top is a
    // position setting, so DOM order is not a contract. \d+ because
    // seed_cameras skips cameras that already exist and counts only new
    // rows (admin.py:341-366) — a re-run against a DB that already has the
    // five sample cameras honestly toasts "Created 0 cameras". The backend
    // leg below is what pins the contract; the toast pins the flow.
    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /Created \d+ cameras/ }))
      .toBeVisible({ timeout: 15_000 });

    // Backend leg: the five sample cameras really exist now. Their ids are
    // the DASHED literals from _get_sample_cameras (admin.py:169-197, inserted
    // verbatim by seed_cameras) — measured, after a first draft wrongly
    // asserted slugified ids. The slugging (dashes → underscores) happens on
    // the POST /api/cameras path the restore book uses, so the DB holds both
    // shapes at once: "front-door" from the seed and "front_door" from the
    // F-162 restore. Two id namespaces, one table — asserted as measured.
    const cameras = await api<{ items?: { id: string }[] } | { id: string }[]>(
      h,
      session,
      '/api/cameras',
    );
    const ids = (Array.isArray(cameras) ? cameras : cameras.items ?? []).map((c) => c.id);
    for (const seeded of ['front-door', 'backyard', 'garage', 'driveway', 'side-gate']) {
      expect(ids).toContain(seeded);
    }

    // Row 1 = Events. 50 is picked (not the 100 default) so the listbox leg
    // is exercised here too; events seed UNCONDITIONALLY (a fresh Event row
    // per iteration, admin.py:595), so the count stays exact across repeats.
    await pickSeedCount(page, panel, 1, '50');
    await panel.getByRole('button', { name: 'Seed Events' }).click();
    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /Created 50 events/ }))
      .toBeVisible({ timeout: 30_000 });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('seed pipeline latency (F-161): the day-count click toasts and samples land', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'test-data');
    const panel = page.getByTestId('test-data-panel');
    // Row 2 = Pipeline Data. 7 is BOTH the default and the only legal option
    // (header: days*24 vs le=168), so this click exercises the listbox path
    // without changing the value — honest, and it still proves the control
    // drives state, because the request the button makes carries 7 through
    // handleValueChange → SeedRow.selectedValue → onSeed.
    await pickSeedCount(page, panel, 2, '7');
    await panel.getByRole('button', { name: 'Seed Pipeline Data' }).click();
    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /Pipeline latency data seeded/ }))
      .toBeVisible({ timeout: 20_000 });

    // Backend leg: the tracker accepted the same call (it only accumulates —
    // samples append to per-stage deques, admin.py:984 — so this re-POST is
    // safe, and its response names the four seeded stages). Deliberately NOT
    // asserted here: snapshots.length > 0. A 7-day backdate measured ZERO
    // rows inside the history endpoint's 60-minute window (admin.py:961
    // spreads samples across the whole span); window-filling data is
    // latency-history.spec.ts's job, through its 1-hour precondition seed.
    const seeded = await authPost<{
      stages_seeded?: string[];
      samples_per_stage?: number;
    }>(h, session, '/api/admin/seed/pipeline-latency', { time_span_hours: 168 });
    expect(seeded.stages_seeded).toEqual([
      'watch_to_detect',
      'detect_to_batch',
      'batch_to_analyze',
      'total_pipeline',
    ]);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('delete all seeded data (F-162): typed reset clears rows, harness cameras are restored', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    test
      .info()
      .skip(
        !CAMERAS_FILE,
        'destructive row needs FEATURE_CHECK_CAMERAS so it can restore afterwards',
      );
    if (!harness.ready || !CAMERAS_FILE) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    const book = JSON.parse(readFileSync(CAMERAS_FILE, 'utf8')) as Record<string, string>;
    expect(Object.keys(book).length).toBeGreaterThan(0);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await openSection(page, 'test-data');
    const panel = page.getByTestId('test-data-panel');

    await panel.getByRole('button', { name: 'Full Database Reset' }).click();
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    // ConfirmWithTextDialog: Cancel + "Confirm" (the default label); the
    // confirm button carries the real disabled gate (inputValue === literal).
    const confirmButton = dialog.getByRole('button', { name: 'Confirm', exact: true });
    await expect(confirmButton).toBeDisabled();
    await dialog.getByPlaceholder('Type "RESET DATABASE"').fill('RESET DATABASE');
    await expect(confirmButton).toBeEnabled();
    await confirmButton.click();

    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /Database reset complete/ }))
      .toBeVisible({ timeout: 20_000 });

    // Restore leg (the contract that makes this row legal to run): recreate
    // each harness camera exactly as scripts/feature_check.py seed_cameras()
    // does, and prove the ids are the ones dashboard-drop already captured.
    for (const [name, expectedId] of Object.entries(book)) {
      const created = await authPost<{ id: string }>(h, session, '/api/cameras', {
        name,
        folder_path: `${CAMERA_TARGET}/${name}`,
      });
      expect(created.id).toBe(expectedId);
    }
    // Polled, not read-once: the measured stale-read lag right after a clear
    // (GET /api/cameras still showing wiped rows) means one immediate read
    // proves nothing about the commit.
    await pollApi<{ pagination?: { total?: number } }>(
      h,
      session,
      '/api/events?limit=1',
      (b) => (b.pagination?.total ?? 0) === 0,
      15_000,
    );

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
