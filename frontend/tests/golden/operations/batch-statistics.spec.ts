/**
 * F-135 (inventory 3.8): the Batch Processing Statistics section expands and
 * its active-batches view lists a live batch.
 *
 * The row's action is "expands the section; sees active batches", and the
 * second clause cannot be faked by an empty render: `hasData` is
 * `activeBatchCount > 0 || totalClosedCount > 0` (BatchStatisticsDashboard.tsx:72)
 * and the active-batches view is only mounted inside `{hasData && …}` (:232).
 * With the stack idle the section shows its empty-state card and NO timeline,
 * so a spec that merely opens the section on a virgin stack asserts presence
 * of a surface that was never reachable — the vacuity trap this lane's own
 * r133 guard names. The honest path supplies one active batch.
 *
 * Supply: POST /api/debug/batch/add-detection (debug.py:1728) — the same
 * surgical-supply pattern this lane used for the F-2xx golden batch, and
 * /api/debug/* is documented live on this stack (databases.spec.ts:14). It
 * writes `batch:<camera>:current` atomically (batch_aggregator.py:622), which
 * GET /api/system/pipeline enumerates by scanning `batch:*:current`
 * (system.py:4066) with NO database validation, so a synthetic camera id is
 * a legitimate active batch for a read that never consults Postgres.
 *
 * Why this cannot leak into another spec's counts:
 *  - camera-scoped: the probe camera `fe_r134_probe` matches no fixture, and
 *    every golden event-count truth is camera-scoped
 *    (event-stats.spec.ts:127 `?camera_id=`, timeline-scrubber.spec.ts:394),
 *    so it can never enter another file's numerator;
 *  - it self-cleans: the `backend` container runs the `batch_timeout` worker
 *    (main.py:1010), which closes the batch at the window/idle timeout and
 *    DELETEs every `batch:*` key (batch_aggregator.py:1016-1024) — no HTTP
 *    delete is needed and none exists;
 *  - closing it creates NO event: the close pushes to the analysis queue, and
 *    analyze_batch loads the batch's detection ids from Postgres and raises
 *    `No detections found for batch` for a synthetic id (vlm_analyzer.py:508-
 *    510) before any event is written. The seed warms the (fake) engine via
 *    wake_ai_vlm and broadcasts `detection.new` over WS — both client-side.
 *
 * The DOM is tied to the backend through the batch's own identity: the
 * returned batch_id and the probe camera id must both appear inside
 * `batch-timeline-chart`, so a view that rendered zeros or a stale list fails.
 * `active-batch-count` is asserted as a positive number, not an exact 1,
 * because another lane's batch could coexist; the probe batch's presence in
 * the chart is the exact, differential claim. aria-expanded is not read (see
 * openSection's measured note: it is stale on this page's controlled sections).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  authPost,
  closedByGuard,
  loginAsAdmin,
  openSection,
  panelRecovers,
  pollApi,
  readOpsHarness,
} from './harness';

const harness = readOpsHarness();

const PROBE_CAMERA = 'fe_r134_probe';
// Synthetic detection id, absent from Postgres by construction (well above any
// id a golden fixture stack's detection sequence reaches).
const PROBE_DETECTION_ID = 99_134_001;

interface AddDetectionResp {
  batch_id: string;
  status: string;
  fast_path: boolean;
}
interface PipelineResp {
  batch_aggregator?: {
    active_batches?: number;
    batches?: { batch_id: string; camera_id: string }[];
  };
}

test.describe('golden path: batch statistics section @critical', () => {
  test.setTimeout(60_000);

  test('expanding the section lists a live active batch', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const session = await loginAsAdmin(page, h);

    // Backend state before UI: open with the section EMPTY of our probe, so a
    // pass cannot be an accidental leftover of a prior run.
    const before = await api<PipelineResp>(h, session, '/api/system/pipeline');
    const probeBefore = before.batch_aggregator?.batches?.find((b) => b.camera_id === PROBE_CAMERA);
    expect(probeBefore, 'probe camera must start with no active batch').toBeUndefined();

    // Supply one active batch. No threat_type / smoke_fire_type and
    // fast_path_enabled ships False (ruling 168), so add_detection takes the
    // normal batching path (batch_aggregator.py:618) rather than a fast path.
    const seeded = await authPost<AddDetectionResp>(h, session, '/api/debug/batch/add-detection', {
      camera_id: PROBE_CAMERA,
      detection_id: PROBE_DETECTION_ID,
      object_type: 'person',
      confidence: 0.5,
    });
    expect(seeded.batch_id, 'seed returned no batch id').toBeTruthy();
    expect(seeded.fast_path, 'seed must not fast-path').toBe(false);

    // The app's OWN endpoint now reports it, keyed to the probe camera.
    const pipeline = await pollApi<PipelineResp>(
      h,
      session,
      '/api/system/pipeline',
      (b) => (b.batch_aggregator?.batches ?? []).some((x) => x.batch_id === seeded.batch_id),
      15_000
    );
    expect(
      pipeline.batch_aggregator?.active_batches,
      'seed is an ACTIVE batch'
    ).toBeGreaterThanOrEqual(1);

    await page.goto(`${h.ui}/operations`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('operations-page')).toBeVisible();

    // "expands the section": batch-statistics defaults OPEN
    // (useSystemPageSections.ts:54), so exercise the affordance for real —
    // close it, prove the panel unmounted, then re-expand through openSection.
    const root = page.getByTestId('batch-statistics-section');
    await expect(root).toBeVisible();
    const panelMounted = async () => (await root.locator(':scope > div').count()) > 0;
    await expect.poll(panelMounted, { timeout: 5_000 }).toBe(true);
    await page.getByTestId('batch-statistics-section-toggle').click();
    await expect.poll(panelMounted, { timeout: 5_000 }).toBe(false);
    await openSection(page, 'batch-statistics'); // re-expands; decides from mount, not aria

    // Re-expanding REMOUNTS the dashboard (CollapsibleSection unmounts a closed
    // panel), so this is a fresh useBatchStatistics mount whose first
    // /api/system/pipeline fetch can fail at the redis contention the harness
    // documents for every /operations panel. The dashboard has its own loading
    // (batch-statistics-loading) and error+Retry (batch-statistics-error)
    // branches, so drive the product's own recovery rather than sit on a short
    // budget — the same posture panelRecovers exists for.
    await panelRecovers(
      root,
      page.getByTestId('batch-statistics-error'),
      page.getByTestId('batch-statistics-loading')
    );

    const dashboard = page.getByTestId('batch-statistics-dashboard');
    await expect(dashboard).toBeVisible();

    // The kept active-batches view renders the seeded batch by identity.
    const chart = page.getByTestId('batch-timeline-chart');
    await expect(chart).toBeVisible();
    await expect(chart).toContainText('Active Batches');
    await expect(chart).toContainText(PROBE_CAMERA);
    await expect(chart).toContainText(seeded.batch_id);

    // The summary count tracks a positive active-batch number (not an exact 1:
    // another lane's batch may coexist; identity above is the exact claim).
    await expect(page.getByTestId('active-batch-count')).toContainText(/^[1-9]\d*$/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
