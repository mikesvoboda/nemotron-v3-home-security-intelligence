/**
 * FE-2 golden path (F2.3): F-042 — the Configure widgets modal: toggles,
 * reorder, and the persisted layout.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - The row's clause: "opens Configure; toggles and reorders widgets (stats,
 *   AI row, camera grid, activity feed, GPU, telemetry, queues); the layout
 *   persists across reloads", backend "— (browser storage only)". The whole
 *   chain is client-side: DashboardLayout.tsx:297 mounts
 *   data-testid="configure-dashboard-button"; the modal (DashboardConfigModal
 *   .tsx:154-234) exposes widget-row-<id> / widget-toggle-<id> /
 *   widget-move-up-<id> / widget-move-down-<id> / save-button / cancel-button
 *   / reset-defaults-button, all inside data-testid="widget-list".
 * - The toggles are HeadlessUI Switch (DashboardConfigModal.tsx:1, :268): a
 *   real role="switch" BUTTON whose aria-checked is the source of truth — not
 *   the Tremor pattern that lands its name on a wrapper div. The data-testid
 *   passes through to the button itself.
 * - Persistence is zustand persist at key 'dashboard-config-v2', version 2
 *   (dashboard-config-store.ts:104-107, persist wrap :271); the DEFAULTS ship
 *   gpu-stats / pipeline-telemetry / pipeline-queues visible:false (:118-159)
 *   — the row's "off by default" (F-039/F-040) is this list, and the FIRST
 *   test below asserts it before flipping anything. Save calls
 *   onConfigChange (modal :147-150); Cancel reverts local edit state without
 *   touching the store (:152-155), so a Cancelled toggle must NOT reach the
 *   jar — asserted by byte-comparing the jar before-vs-after Cancel.
 * - DOM landmarks for what the layout renders (read at shipped code):
 *   stats-row → aria-label="Dashboard statistics" (StatsRow.tsx:169);
 *   camera-grid → data-testid="camera-grid" (CameraGrid.tsx:584, renders the
 *   container even when the camera list is empty, :552); activity-feed →
 *   data-testid="activity-feed" (ActivityFeed.tsx:139); pipeline-queues →
 *   data-testid="pipeline-queues" (PipelineQueues.tsx:112); gpu-stats has no
 *   root testid (Tremor Card) so its marker is gpu-device-name (:265);
 *   pipeline-telemetry → data-testid="pipeline-telemetry" (:317). The three
 *   system widgets land inside data-testid="system-widgets-area"
 *   (DashboardLayout.tsx:337-342) in store order; a move-up there is
 *   observable as document order between gpu-device-name and pipeline-queues.
 * - Playwright gives each test a FRESH context, so "the layout persists
 *   across reloads" is exercised the way a user's reload works: same
 *   context/jar, page.reload(). Cross-context defaults ride the fresh jar.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readDashboardHarness,
  seedTourDismissed,
  type DashboardHarness,
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

const STORAGE_KEY = 'dashboard-config-v2';

async function openDashboard(page: import('@playwright/test').Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
}

interface PersistedWidget {
  id: string;
  visible: boolean;
}
interface PersistedConfig {
  widgets: PersistedWidget[];
  version: number;
}

/** The browser's own copy of the layout jar — read in-page, never mocked. */
async function readJar(page: import('@playwright/test').Page): Promise<string | null> {
  return page.evaluate((k) => localStorage.getItem(k), STORAGE_KEY);
}
function widgetsOf(raw: string | null): PersistedWidget[] {
  expect(raw, `jar ${STORAGE_KEY} should exist`).not.toBeNull();
  const parsed = JSON.parse(raw as string) as { state?: PersistedConfig };
  expect(parsed.state?.version, 'persisted CONFIG_VERSION').toBe(2);
  return parsed.state?.widgets ?? [];
}

async function toggleInModal(
  page: import('@playwright/test').Page,
  widgetId: string,
  want: boolean
) {
  const sw = page.getByTestId(`widget-toggle-${widgetId}`);
  await expect(sw).toHaveAttribute('role', 'switch');
  if (((await sw.getAttribute('aria-checked')) === 'true') !== want) await sw.click();
  await expect(sw).toHaveAttribute('aria-checked', String(want));
}

test.describe('golden path: dashboard Configure widgets modal @critical', () => {
  test('F-042: off-by-default widgets ship hidden, the modal enables+reorders+saves them, and the layout survives reload', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    await openDashboard(page, h);

    // Default state, before any write: the three system widgets are absent
    // from the DOM (store DEFAULT_WIDGETS visible:false, store :118-159).
    await expect(page.getByTestId('pipeline-queues')).toHaveCount(0);
    await expect(page.getByTestId('pipeline-telemetry')).toHaveCount(0);
    await expect(page.getByTestId('gpu-device-name')).toHaveCount(0);
    // …while the four default-on widgets are present (the row's named set
    // minus the AI row, which F-038 owns and data-gates separately).
    await expect(page.getByRole('region', { name: 'Dashboard statistics' })).toBeVisible();
    await expect(page.getByTestId('camera-grid')).toBeVisible();
    await expect(page.getByTestId('activity-feed')).toBeVisible();

    // Open Configure (the row's first clause).
    await page.getByTestId('configure-dashboard-button').click();
    const modal = page.getByTestId('widget-list');
    await expect(modal).toBeVisible();
    // All seven named widgets get a row in the modal (the row enumerates
    // exactly: stats, AI row, camera grid, activity feed, GPU, telemetry,
    // queues).
    for (const id of [
      'stats-row',
      'ai-summary-row',
      'camera-grid',
      'activity-feed',
      'gpu-stats',
      'pipeline-telemetry',
      'pipeline-queues',
    ]) {
      await expect(page.getByTestId(`widget-row-${id}`)).toBeVisible();
    }
    // Reorder bounds, list-head form: stats-row is FIRST in defaults
    // (store :118-159) so its move-up ships disabled (WidgetConfigRow
    // disabled={isFirst}, modal :298-300).
    await expect(page.getByTestId('widget-move-up-stats-row')).toBeDisabled();

    const jarBefore = await readJar(page); // whatever the app has already persisted
    await toggleInModal(page, 'pipeline-queues', true);
    await toggleInModal(page, 'gpu-stats', true);

    // Reorder inside the modal: queues ABOVE gpu-stats (both start in
    // defaults order gpu-stats before pipeline-queues). Move-up once swaps
    // adjacent rows (handleMoveUp → moveWidgetUp, modal :112-115).
    const queuesRow = page.getByTestId('widget-row-pipeline-queues');
    const gpuRow = page.getByTestId('widget-row-gpu-stats');
    const rowOrder = async () =>
      page.evaluate(() => {
        const q = document.querySelector('[data-testid="widget-row-pipeline-queues"]')!;
        const g = document.querySelector('[data-testid="widget-row-gpu-stats"]')!;
        return q.compareDocumentPosition(g) & Node.DOCUMENT_POSITION_FOLLOWING
          ? 'queues-first'
          : 'gpu-first';
      });
    // Poll the ORDER, click outside the poller: if an unexpected position
    // ever shows up, more clicks can't converge it to the expectation — the
    // poll fails with the observed order instead of hiding behind them.
    await expect
      .poll(async () => {
        await page.getByTestId('widget-move-up-pipeline-queues').click();
        return rowOrder();
      })
      .toBe('queues-first');
    // The list-head bound moved with the row (same disabled={isFirst} prop
    // stats-row's check pinned before the swap): now-queues-first is inert.
    await expect(page.getByTestId('widget-move-up-pipeline-queues')).toBeDisabled();

    // SAVE.
    await page.getByTestId('save-button').click();
    await expect(modal).toHaveCount(0);

    // The saved layout is on the page: both widgets render, queues BEFORE
    // gpu-stats (document order inside system-widgets-area, layout :337-348).
    await expect(page.getByTestId('pipeline-queues')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('gpu-device-name')).toBeVisible({ timeout: 15_000 });
    const domOrder = await page.evaluate(() => {
      const q = document.querySelector('[data-testid="pipeline-queues"]')!;
      const g = document.querySelector('[data-testid="gpu-device-name"]')!;
      return q.compareDocumentPosition(g) & Node.DOCUMENT_POSITION_FOLLOWING
        ? 'queues-first'
        : 'gpu-first';
    });
    expect(domOrder).toBe('queues-first');

    // The jar carries it: version 2, the two flips, the swap — read from the
    // browser's own storage, not the app's memory.
    const jar = widgetsOf(await readJar(page));
    expect(jar.find((w) => w.id === 'gpu-stats')?.visible).toBe(true);
    expect(jar.find((w) => w.id === 'pipeline-queues')?.visible).toBe(true);
    expect(jar.findIndex((w) => w.id === 'pipeline-queues')).toBeLessThan(
      jar.findIndex((w) => w.id === 'gpu-stats')
    );
    const savedRaw = await readJar(page);
    expect(savedRaw).not.toEqual(jarBefore); // save really wrote

    // THE ROW'S CLAUSE: reload — same context, same jar — layout persists.
    await quietBoot(page, h);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('pipeline-queues')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('gpu-device-name')).toBeVisible({ timeout: 15_000 });
    // …and the jar is byte-identical across the reload (nothing rewrote it).
    expect(await readJar(page)).toEqual(savedRaw);
    // Order still queues-first after reload — the persisted array order is
    // what the layout maps, not a coincidence of this session's clicks.
    const reloadedOrder = await page.evaluate(() => {
      const q = document.querySelector('[data-testid="pipeline-queues"]')!;
      const g = document.querySelector('[data-testid="gpu-device-name"]')!;
      return q.compareDocumentPosition(g) & Node.DOCUMENT_POSITION_FOLLOWING
        ? 'queues-first'
        : 'gpu-first';
    });
    expect(reloadedOrder).toBe('queues-first');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-042: Cancel submits nothing — the jar is byte-identical and a reopen shows the saved state', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    await openDashboard(page, h);

    // Force a known baseline in the jar with one honest save (telemetry ON),
    // so "byte-identical after Cancel" compares a real saved config rather
    // than a missing key.
    await page.getByTestId('configure-dashboard-button').click();
    await toggleInModal(page, 'pipeline-telemetry', true);
    await page.getByTestId('save-button').click();
    await expect(page.getByTestId('pipeline-telemetry')).toBeVisible({ timeout: 15_000 });
    const saved = await readJar(page);

    // Reopen, toggle telemetry back OFF (the switch flips), then CANCEL.
    await page.getByTestId('configure-dashboard-button').click();
    await expect(page.getByTestId('widget-list')).toBeVisible();
    await toggleInModal(page, 'pipeline-telemetry', false);
    await page.getByTestId('cancel-button').click();
    await expect(page.getByTestId('widget-list')).toHaveCount(0);

    // Nothing reached the jar (byte compare) and nothing reached the page:
    // telemetry stays visible because the SAVED config still has it on.
    expect(await readJar(page)).toEqual(saved);
    await expect(page.getByTestId('pipeline-telemetry')).toBeVisible();

    // Reopen: the modal re-seeds from the saved config (modal useEffect
    // :108-112) — telemetry back to checked, the cancelled edit gone.
    await page.getByTestId('configure-dashboard-button').click();
    await expect(page.getByTestId('widget-toggle-pipeline-telemetry')).toHaveAttribute(
      'aria-checked',
      'true'
    );
    await page.getByTestId('config-modal-close').click();
    await expect(page.getByTestId('widget-list')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-042: Reset defaults un-writes everything and reload lands on the shipped layout', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    await openDashboard(page, h);

    // Save a changed layout first (queues ON), then reset.
    await page.getByTestId('configure-dashboard-button').click();
    await toggleInModal(page, 'pipeline-queues', true);
    await page.getByTestId('save-button').click();
    await expect(page.getByTestId('pipeline-queues')).toBeVisible({ timeout: 15_000 });

    await page.getByTestId('configure-dashboard-button').click();
    await page.getByTestId('reset-defaults-button').click();
    // reset() writes DEFAULT_CONFIG_STATE through the store (modal :127-136),
    // so the jar is now the shipped defaults: the three system widgets off.
    await page.getByTestId('save-button').click();
    const jar = widgetsOf(await readJar(page));
    for (const id of ['gpu-stats', 'pipeline-telemetry', 'pipeline-queues']) {
      expect(jar.find((w) => w.id === id)?.visible, `${id} after reset`).toBe(false);
    }
    await expect(page.getByTestId('pipeline-queues')).toHaveCount(0);

    // Reload lands on the shipped layout too.
    await quietBoot(page, h);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('pipeline-queues')).toHaveCount(0);
    await expect(page.getByTestId('camera-grid')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
