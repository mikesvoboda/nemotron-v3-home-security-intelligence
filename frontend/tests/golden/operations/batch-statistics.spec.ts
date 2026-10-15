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
 * Supply: POST /api/debug/batch/add-detection (debug.py:1728-1742) — the same
 * surgical-supply pattern this lane used for the F-2xx golden batch, and
 * /api/debug/* is documented live on this stack (databases.spec.ts:14). It
 * writes `batch:<camera>:current` atomically (batch_aggregator.py:623-630), which
 * GET /api/system/pipeline enumerates by scanning `batch:*:current`
 * (system.py:4092) with NO database validation, so a synthetic camera id is
 * a legitimate active batch for a read that never consults Postgres.
 *
 * The probe camera is ATTEMPT-scoped, not a fixed name. playwright.config.ts:79
 * sets `retries: 2` on CI, and add_detection REUSES an existing
 * `batch:<camera>:current` rather than minting a new one, so a fixed name would
 * let a failed attempt 1 leave its probe batch alive for the ~90 s window and
 * attempt 2's "must start with no active batch" leg would then fire on this
 * spec's own leftover — a false RED caused by the retry machinery itself.
 * A fresh camera per attempt keeps that leg both meaningful and true by
 * construction; leftovers still self-clean via the worker below. Same posture
 * as access.spec.ts:81 (`GoldenAcc${Date.now()...}${process.pid}`) and
 * frontend-logs.spec.ts:214 (RUN_MARK).
 *
 * Why this cannot leak into another spec's counts — event truths on this
 * suite come in TWO classes and the probe is safe against each differently:
 *  - camera-scoped reads (timeline/event-stats.spec.ts:127 `?camera_id=`,
 *    timeline/timeline-scrubber.spec.ts:394): the probe's `fe_r134_` prefix
 *    matches no fixture camera (the seed's ids are front_door/driveway/
 *    backyard/garage, scripts/sandbox-seed.py:52-57), so it cannot enter
 *    their numerator;
 *  - GLOBAL dashboard mirrors (dashboard/risk-donut.spec.ts:84,
 *    dashboard/stats-row.spec.ts:146 — they passively capture the APP's own
 *    /api/events/stats URL, unscoped): these are NOT protected by camera
 *    scoping. They are protected because the probe creates NO Event rows at
 *    all: analyze_batch raises `No detections found for batch` for a synthetic
 *    id (vlm_analyzer.py:517) before any event is written, so global counts
 *    cannot move.
 *
 * Seed LIFETIME, and why the spec re-adds once before the row asserts:
 * `add_detection` writes `batch:<id>:last_activity` on every call
 * (batch_aggregator.py:641) and REUSES the open batch (the existing-batch path
 * at :583; only the max-size branch mints a new id, and it fires at
 * `batch_max_detections` = 500, :587 and core/config.py:1027 — two adds cannot
 * reach it). So the second add returns the SAME batch_id and resets the idle
 * clock. That matters because one add alone leaves the batch at the mercy of
 * the idle clock — `batch_idle_timeout_seconds` defaults to 30
 * (core/config.py:980-983) and the `batch_timeout` worker checks every 10 s
 * (pipeline_workers.py:1204), so a lone seed can be closed ~30-40 s after it
 * was written, while the recovery leg below (panelRecovers, 60 s budget) can
 * legitimately run that long. The reuse is witnessed from add_detection's OWN
 * response body (again.batch_id === seeded.batch_id), NOT from a count read
 * through the pipeline endpoint — see the key-type risk note below for why
 * the read is not trusted with that claim.
 *
 * Why the poll is IDENTITY-keyed and the row assert is count-free: the
 * pipeline read's `detection_count` WAS entangled with TWO stacked key-type
 * mismatches, both cured ON THIS HEAD by `f9a18d028` (#7156), which reads the
 * LIST with `pipe.lrange` (system.py:4117, in the 4-key pipeline :4114-4120)
 * and unwraps the JSON-quoted scalars (`_coerce_scalar` def :4019, called
 * :4135-4136) before `float()` (:4138). Pre-cure it `pipe.get`s the LIST the
 * aggregator RPUSHes (batch_aggregator.py:638, helper :335-357): WRONGTYPE ⊂
 * RedisError → `except RedisError` (:4130 then, :4162 now) →
 * `batch_aggregator: null` for any live batch. MASKED behind that, the `set`
 * wrapper JSON-quotes the timestamps (core/redis.py:1229), so `float()`
 * raised ValueError and the per-batch `except (ValueError, TypeError,
 * KeyError)` (:4151) SKIPPED the batch — lrange alone looked like progress
 * and returned `{active_batches: 0}`, exactly as `f9a18d028`'s own message
 * records. CI could not have seen either break: the unit fake seeds that key
 * with SET and reads it back through the fake, never the endpoint
 * (backend/tests/unit/services/test_pipeline_worker.py:859, inside
 * `test_batch_metadata_lifecycle`). Both ends are now CI-witnessed — RED at
 * `38664676455` (poll body carries `"batch_aggregator":null`; 70 WRONGTYPE
 * naming `GET batch:<id>:detections` pipeline Command #2; `Error processing
 * batch` 0×, the masking visible) and GREEN at `38725128069` attempt 2 (0× of
 * all three). CI shows the pair but cannot separate the two cures, so that
 * half was measured in a disposable container (this repo's backend/
 * untouched): UNPATCHED → this spec RED + `batch_aggregator:null`; lrange alone → STILL RED,
 * `active_batches: 0` + `could not convert string to float: '"…"'`; both → GREEN with
 * `active_batches: 1`, `detection_count: 2`. Hence identity-keyed poll, count-free row assert, no skip
 * (UR-114), assertions unbent (ruling 161), CI's Feature check as the
 * independent real-Redis witness (harness.ts:17-20 is its only gate;
 * guard.ts has no CI skip, so this spec DOES execute there).
 *
 * It still self-cleans: the `backend` container runs the `batch_timeout`
 * worker (main.py:1011-1015), which closes the batch on EITHER arm — the
 * window arm measures `current_time - started_at` (batch_aggregator.py:790,
 * compared :796), the idle arm measures from the LAST activity (:791, compared
 * :801) — and DELETEs every `batch:*` key (batch_aggregator.py:1018-1026) — no
 * HTTP delete is needed and none exists.
 *
 * The DOM is tied to the backend through the batch's own identity, at ROW
 * level: the returned batch_id and the probe camera id must co-occur in the
 * SAME per-batch row, so a view that rendered zeros, a stale list, or a row
 * that mixed two batches' fields fails. aria-expanded is not read (see
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

// Attempt-scoped (see header): a retry gets a fresh camera so the
// "must start with no active batch" leg can never fire on this spec's own
// leftover batch. 8-char prefix + 6 base36 = 14 chars, above the longest
// seeded camera id (`front_door`, 10 — scripts/sandbox-seed.py:52-57), which
// is the property that keeps this name outside every fixture's orbit.
const PROBE_CAMERA = `fe_r134_${Date.now().toString(36).slice(-6)}`;
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
    batches?: { batch_id: string; camera_id: string; detection_count?: number }[];
  };
}

test.describe('golden path: batch statistics section @critical', () => {
  // 120 s, the same budget worker-management.spec.ts:39 gives a panel that
  // round-trips and polls. 60 s was not enough to be honest: panelRecovers
  // alone allows 60 s, so a /operations boot that lands in the error branch
  // could consume the whole test budget and the batch would close (header)
  // while the row assert still had claims to make.
  test.setTimeout(120_000);

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
    // normal batching path: the fast-path gate at batch_aggregator.py:557 calls
    // _should_use_fast_path (:1186), which returns False whatever the threshold is
    // set to because fast_path_enabled ships False (ruling 168).
    const seeded = await authPost<AddDetectionResp>(h, session, '/api/debug/batch/add-detection', {
      camera_id: PROBE_CAMERA,
      detection_id: PROBE_DETECTION_ID,
      object_type: 'person',
      confidence: 0.5,
    });
    expect(seeded.batch_id, 'seed returned no batch id').toBeTruthy();
    expect(seeded.fast_path, 'seed must not fast-path').toBe(false);

    // Second add on the SAME camera: add_detection reuses the open batch
    // (header), so this returns the SAME batch_id and refreshes
    // batch:<id>:last_activity. That is the seed's keep-alive against the 30 s
    // idle timeout, and it is asserted, not assumed: a reused id with TWO
    // detections can only come from the reuse branch.
    const again = await authPost<AddDetectionResp>(h, session, '/api/debug/batch/add-detection', {
      camera_id: PROBE_CAMERA,
      detection_id: PROBE_DETECTION_ID + 1,
      object_type: 'person',
      confidence: 0.5,
    });
    expect(again.batch_id, 'second add must reuse the open batch').toBe(seeded.batch_id);

    // The app's OWN endpoint now reports it, keyed to the probe camera, with
    // both detections counted on that one batch.
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

    // Keep-alive at the moment of the DOM claim: this third add still reuses
    // the batch (same id — asserted), so it re-arms the 30 s idle clock here
    // rather than at t≈0. Without it, a recovery leg that ran long could read
    // the row after the worker had already closed the batch.
    const kept = await authPost<AddDetectionResp>(h, session, '/api/debug/batch/add-detection', {
      camera_id: PROBE_CAMERA,
      detection_id: PROBE_DETECTION_ID + 2,
      object_type: 'person',
      confidence: 0.5,
    });
    expect(kept.batch_id, 'keep-alive add must reuse the same batch').toBe(seeded.batch_id);

    // The kept active-batches view renders the seeded batch by identity, in
    // ONE ROW. Three chart-wide toContainText checks would also pass if a render
    // bug split a batch's camera and id across two rows, or if the container
    // matched its own empty branch — that branch carries the SAME
    // data-testid (BatchTimelineChart.tsx:49 and :61 are mutually-exclusive
    // returns, so only one is mounted, but the id alone cannot tell them apart).
    // The per-batch row is separately addressable: it uses rounded-md (:77)
    // while the container uses rounded-lg (:61), and it is keyed by batch_id.
    const chart = page.getByTestId('batch-timeline-chart');
    const probeRow = chart.locator('div.rounded-md').filter({ hasText: seeded.batch_id });
    await expect(probeRow, 'exactly one row carries the seeded batch id').toHaveCount(1);
    await expect(probeRow, 'that row also carries the probe camera').toContainText(PROBE_CAMERA);

    // The summary count tracks a positive active-batch number (not an exact 1:
    // another lane's batch may coexist; identity above is the exact claim).
    await expect(page.getByTestId('active-batch-count')).toContainText(/^[1-9]\d*$/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
