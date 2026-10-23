/**
 * FE-3 golden path (F2.3): F-052 — the event-timeline export modal.
 *
 * Row clause (from docs/reference/feature-inventory.md:206, F-052, ruling 234):
 *   "opens More Options; chooses format, columns, camera, risk and dates;
 *    watches progress; downloads the file"
 *
 * What this file ships against that clause:
 *   covered  — opens (test 1), chooses format/columns/camera/risk (tests 1-2),
 *              chooses dates (test 3, ruling 234), watches progress (test 4),
 *              downloads the file (test 5), failing job behaviour (test 6).
 *   excluded — "cancels": the Cancel route is F-099's clause (ruling 234;
 *              inventory :259 — cancel marks the row FAILED, but the running
 *              background task overwrites that with COMPLETED at
 *              backend/api/routes/exports.py:181-188). No leg touches
 *              DELETE /api/exports/{id}/cancel (route at :428).
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - "opens More Options" is ONE button: EventTimeline.tsx:1243 sets
 *   setShowExportModal(true) on the control whose aria-label is exactly "Open
 *   export modal with more options" (:1245), and <ExportModal> is mounted in
 *   ONE place — the timeline — :1918-1929, with initialFilters built from the
 *   page's own eventFilters (:1921-1926) and onExportComplete={() =>
 *   setShowExportModal(false)} (:1927-1929). That last prop is the load-bearing
 *   line of this whole file: COMPLETION, not the user, closes the modal.
 *   Measured consequence: ExportProgress's Download button NEVER renders inside
 *   the modal — onComplete fires the moment status flips to completed
 *   (ExportProgress.tsx:81-83) and React commits the parent's unmount together
 *   with the completed render. A MutationObserver witness caught the panel at
 *   t=177 ms reading "CSV Export | Cancel | Starting CSV export... | 0%" and
 *   saw no Download button ever (probe log /tmp/probe-f052/probe5.mjs). So test
 *   4 asserts THAT shipped shape — the panel mounts showing live progress, then
 *   the modal is gone — and test 5 covers "downloads the file" through the
 *   app's OTHER mount site of the same shipped client, where the button exists.
 * - "chooses format, columns, camera, risk" is decided from the modal's own
 *   submit body: handleStartExport POSTs {export_type, export_format,
 *   camera_id: cameraId || null, risk_level: riskLevel || null, start_date,
 *   end_date, reviewed, columns} (ExportModal.tsx:136-160, fields :142-149).
 *   The Tremor Selects are Type(:228), Format(:251), Camera placeholder "All
 *   cameras"(:276), Risk placeholder "All levels"(:291), Review placeholder
 *   "All events"(:329), DOM order 0-4; each hides a native <select
 *   title="select-hidden">, so the only real drive is the
 *   button[aria-haspopup="listbox"] + getByRole('option', {exact:true}) path
 *   (plain clicks, no force — measured). Camera options are a pure render of
 *   the cached list endpoint (ExportModal.tsx:76-85 → fetchCameras,
 *   api.ts:1407-1410 GET /api/cameras), so test 1 mirrors option strings
 *   against api('/api/cameras') names. Columns are ExportColumnSelector: the
 *   pill renders `${selectedCount} of ${EXPORT_COLUMNS.length}` (:91; 11
 *   columns, types/export.ts:68-92), "Select None" re-opens at exactly
 *   ['event_id'] (:104-111), each column toggles on its label (:142). The POST
 *   carries the array the buttons built, so test 2 asserts the POST verbatim
 *   AND the artifact's column set from the file's own bytes.
 * - Server-side the export really filters what the selects chose: camera and
 *   risk predicates apply to the same SELECT the count comes from
 *   (backend/services/export_service.py:768-771, count :792) under
 *   deleted_at IS NULL (:766); the row round-trips filter_params (a JSON
 *   STRING in the response, schemas/export.py:275 written from routes/exports.py:
 *   257-265). Test 2's expected row count is read from
 *   GET /api/events?camera_id=&risk_level= — the browse list filters the same
 *   stored column (routes/events.py:286-288) that the export service filters
 *   (:771), and this fixture's scores AGREE with their labels, so the
 *   stored-vs-computed risk disagreement the batch's search fixture documents
 *   (harness.ts:1122-1131) cannot skew the mirror.
 * - THE PROGRESS PANEL IS DB-BACKED, AND THAT IS THE TEST. The job row is set
 *   RUNNING with current_step "Starting {FORMAT} export..." (exports.py:160)
 *   before the service runs, and gets progress_percent=100 / current_step
 *   "Complete" / processed=total=event_count only when the file exists
 *   (:183-188); until then total_items stays NULL, which gates the "N / M
 *   items" line (ExportProgress.tsx:282-284). GET /api/exports/{id} (:399)
 *   serves THAT row (the builder reads the model's columns, exports.py:53-62);
 *   the reporter's intermediate percentages (export_service.py:1022-1136)
 *   reach job_tracker + WebSocket only (job_progress_reporter.py imports no DB
 *   session), so a RUNNING row reads percent=0 / total_items NULL (model
 *   defaults models/export_job.py:116-119) until completion. ExportProgress
 *   polls the row every 1000 ms (:110-114, default :58) and renders
 *   "{FORMAT} Export" (:239), current_step and "{percent}%" (:269-271).
 *   RACE THE TEST MUST RESPECT: the POST answers 202 status 'pending'
 *   (:223-231) and the mount-time fetch (:107) can win the RUNNING commit at
 *   :158-161, so the panel's FIRST frame can legitimately be the PENDING row
 *   — pinning "first paint == first poll" would be flaky BY DESIGN. Test 4
 *   instead freezes the WHOLE sequence (a page-side MutationObserver
 *   snapshots the attached Card's text on every mutation) AND captures every
 *   GET /api/exports/{id} RESPONSE from the browser's own traffic (reading a
 *   response is not interception — the guard covers route/unroute/
 *   routeFromHAR/routeWebSocket only), then PAIRS BY VALUE: the attached frame
 *   whose step line equals the RUNNING response's current_step must exist,
 *   with that format's header and that percent — a hardcoded label, a tracker
 *   read, or a pre-set denominator diverge there. The observer snapshots only
 *   while the card is ATTACHED, which is what makes the header's never-paints
 *   claim above an observable negative: completion's text update and the
 *   parent's unmount are one React batch (onExportComplete is called
 *   SYNCHRONOUSLY at ExportProgress.tsx:81-83 → ExportModal.tsx:162-168), so
 *   no attached frame ever carries "Complete" or a Download button — and both
 *   absences are asserted. The timing window sizes the fixture: a 400-row CSV
 *   job runs 266-330 ms, row RUNNING from 31 ms (probe 10, /tmp/probe-f052/
 *   probe10.mjs) — as fast as the first poll, which then answers 'completed',
 *   onComplete fires and NOTHING paints. The 1200-row pool runs 2020 ms
 *   (probe 9, /tmp/probe-f052/probe9.mjs), straddling the 1000 ms cadence.
 *   Test 4's completion denominator is a LIVE GET /api/events total for that
 *   camera read BEFORE the click, equal to the constant the fixture topped up
 *   to — the pool is never deleted (next bullet), so a foreign row REDDENS
 *   the premise instead of drifting the denominator. And because the POOL
 *   PAGE'S OWN paging floods the shared nginx api bucket (nginx.conf:24, the
 *   file's boot rule) — run 3 measured it: booting the 1200-row camera starved
 *   the Start Export POST until fetchApi's DEFAULT_TIMEOUT_MS (services/api.ts:
 *   707) rejected the await at ExportModal.tsx:152 into the catch at :154, so
 *   setJobId (:153) never ran and the FORM stayed up — while the request the
 *   browser had already sent still ran the job to completion server-side
 *   (visible in /data's Export History) — test 4 boots the LIGHT 4-row camera
 *   and CHOOSES the pool camera through the modal's own select, the same
 *   "drive the select, never lean on the pre-fill" path test 2 proves.
 * - BULK WRITES ARE RATE-LIMITED; THE FIXTURE PACES ITSELF. POST and DELETE
 *   /api/events/bulk share the BULK tier (_bulk_rate_limiter, routes/events.py:
 *   1538): rate_limit_bulk_requests_per_minute=10 + burst=2 → 12 requests per
 *   minute per client IP in a SLIDING window (rate_limit.py:322-327, :466-470;
 *   config.py:2457-2471). The export POST/poll/download routes carry NO limiter
 *   (routes/exports.py has zero RateLimiter deps), so only bulk writes pace.
 *   An unpaced purge+refill burned the budget and the run died in beforeAll on
 *   429 "Maximum 12 requests per minute" (recorded failure) — and because the
 *   window SLIDES, the burst also poisons the NEXT run. Hence: ≥5.5 s between
 *   bulk calls, one wait-the-window retry on 429, and the 1200-row pool is
 *   topped up instead of purged and NEVER deleted at teardown — its rows are
 *   scoped to this file's camera, test 4 pins its count by live read, and
 *   every saved teardown DELETE call is budget the NEXT run's fixture has to
 *   pay for instead. (Run 1's teardown deleted 404 rows — 5 DELETE calls that
 *   bought the NEXT run nothing.) The zero-row premise stays cheap for the
 *   same reason: EMPTY_CAMERA never holds rows to delete.
 * - "downloads the file" goes through the app's client twice over: the
 *   Download button is ExportProgress :318-324 / DataManagementPage.tsx:505-512
 *   → handleDownloadJob (:421) → downloadExportFile (api.ts:3700-3748), which
 *   fetches GET /api/exports/{id}/download, reads the filename with
 *   /filename="?([^";\n]+)"?/ from Content-Disposition (api.ts:3726-3729 — the
 *   header the route writes from basename(output_path), exports.py:516 +
 *   FileResponse) and clicks a blob-URL anchor. The golden project
 *   (playwright.config.ts:283-298) ships no acceptDownloads and Playwright 1.63
 *   defaults it FALSE (a download would abort and the event never fire), so the
 *   file declares test.use({acceptDownloads:true}) and test 5 clicks /data's
 *   real button, then mirrors the SAME endpoint Node-side: byte length, sha256,
 *   suggestedFilename vs the route's own header (the same regex, so the
 *   comparison is client-vs-route, not two hand-rolled parses). /data is
 *   REACHED THROUGH THE SIDEBAR, not deep-linked: timeline/harness.ts's
 *   settleBoot hard-races the timeline-page marker (harness.ts:259-263), so
 *   quietBoot CANNOT boot a non-timeline route (run 3 measured the 4-drive
 *   throw on a page that had rendered /data perfectly), and every quietBoot
 *   precedent for '/data'-like routes lives in the shell lane's DIFFERENT
 *   harness (shell/harness.ts:156, own gate + own rule-87 dir). So test 5
 *   boots the light timeline and clicks the shipped ADMIN group's "Data
 *   Management" NavLink (sidebarNav.ts:135, label 'Data Management') — a
 *   client-side transition App.tsx's already-mounted <ProtectedRoute>
 *   <Layout> answers without remount (App.tsx:247-256 nests Routes under the
 *   layout), which is both the drain-friendly path (no second document wave
 *   into the shared nginx bucket) and the path a user takes. The card is
 *   scoped by id (data-testid={`export-job-${id}`} :294; canDownload =
 *   completed && result?.output_path :283); its Download is in-viewport at the
 *   shipped 1280x720 (measured bbox y≈258), so the /data leg needs no viewport
 *   override.
 * - THE VIEWPORT OVERRIDE IS MEASURED, NOT DECORATIVE. The modal Card is
 *   `mx-4 w-full max-w-lg` inside a `fixed inset-0` overlay (ExportModal.tsx:
 *   196-197) with no scroll container, and at the 720 px the golden project
 *   ships (devices['Desktop Chrome']) "Start Export" (:360-367) lands at
 *   y≈779 — a real click there fails hit-testing ("element is outside of the
 *   viewport", probe 1). No sibling of this batch opens this modal, so nothing
 *   proves 720 works; rather than FORCE a click (skipping the hit-test shipped
 *   users depend on), the file drives at 1280x1400, where Start Export measured
 *   at y≈1119, same Desktop Chrome engine.
 * - A failing job cannot show its error: handleExportError sets the error text
 *   and calls onExportComplete(false) (ExportModal.tsx:169-173) — the SAME prop
 *   that closes on success — so the parent unmounts the modal and
 *   ExportProgress's red error render (:299-305) has no window. The corner the
 *   failure leg drives is Excel over a zero-row camera: the count check hands
 *   off to _create_empty_export (export_service.py:792-797) which has no excel
 *   branch and raises ValueError(:925); the except sets FAILED with that
 *   message and download answers 400 "Export job is not complete (status:
 *   failed)" (exports.py:503-506). Measured all of it, including the modal
 *   being gone with zero error text on screen.
 *
 * NOT asserted here, with reasons (UR-128): the Type select's other values
 *   (alerts/full_backup) and their server branches; the Review select beyond
 *   its default (test 2 pins reviewed:null in the POST body); /data's cancel
 *   affordance and job-table paging (F-099's / F-097's surfaces); the tour
 *   overlay (the guard seeds the shipped dismiss state). Every leg closes with
 *   the batch's guard tripwire.
 */
import { createHash } from 'node:crypto';

import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  apiShell as api,
  apiWrite,
  closedByGuard,
  loginAsAdminShell as loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedTourDismissed,
  settledReload,
  waitForCameraInList,
  type Session,
  type TimelineHarness,
} from '../harness';

/* --------------------------------------------------------------------------- */
/* Collection-time readiness (the batch's rule): COLLECTION runs before any      */
/* runtime skip, so every env read is defensive — readTimelineHarness already    */
/* returns {ready:false, why} instead of throwing — and every body re-checks.    */
/* --------------------------------------------------------------------------- */
const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

/** The modal leg needs the taller viewport — see the header's measured claim. */
test.use({ viewport: { width: 1280, height: 1400 }, acceptDownloads: true });

/** This file's cameras: 4 rows (2 critical) / 1200 rows / genuinely zero rows.
 *  BULK_ROWS is 1200 because the header's measured timings say a 400-row job
 *  can finish as fast as the browser's first poll (no running paint at all);
 *  1200 rows keep the panel's running window ~2 s wide. */
const PROBE_CAMERA = 'fe3-export-modal';
const BULK_CAMERA = 'fe3-export-bulk';
const EMPTY_CAMERA = 'fe3-export-empty';
const BULK_ROWS = 1200;

/** Minimum spacing between two calls to /api/events/bulk (POST or DELETE):
 *  the BULK tier is 12 requests per SLIDING minute per client IP (header
 *  cite), and 60/12 = 5 s per call; 5.5 s leaves the arithmetic margin the
 *  window needs. The bulk limiter never burst-overruns a paced caller, so the
 *  only 429s that can still land are foreign traffic's — handled below. */
const BULK_SPACING_MS = 5_500;

const PROBE_ROWS = [
  { risk_score: 91, risk_level: 'critical' },
  { risk_score: 88, risk_level: 'critical' },
  { risk_score: 45, risk_level: 'medium' },
  { risk_score: 20, risk_level: 'low' },
];

interface Fixture {
  probeCameraId: string;
  probeEventIds: number[];
  bulkCameraId: string;
  emptyCameraId: string;
}

/* The siblings' idiom (event-stats.spec.ts:110): a module-scope `let fx:
 * Fixture` — the test bodies read fx.* without null-fumbling because a
 * collection-time test.skip already covers an unready harness; the ONE place
 * that must survive a FAILED beforeAll is afterAll (run 1 proved a teardown
 * crash on undefined is a second red piled on the first), and it guards at
 * runtime instead. */
let fx: Fixture;

/** GET /api/exports/{id}'s response, exactly as the route builds it
 *  (routes/exports.py:59-91): progress carries FIVE fields and filter_params
 *  is a JSON string, not an object. */
interface ExportJobView {
  status: string;
  export_format: string;
  error_message: string | null;
  filter_params: string | null;
  result: { output_path?: string; output_size_bytes?: number; event_count?: number } | null;
  progress: {
    progress_percent: number;
    current_step: string | null;
    total_items: number | null;
    processed_items: number | null;
  };
}

/** One ATTACHED frame the progress panel ever held (the observer's snapshot
 *  shape — header span + the Card's innerText). */
interface PanelFrame {
  header: string | null;
  cardText: string;
}

const sha256 = (bytes: Buffer): string => createHash('sha256').update(bytes).digest('hex');

/** Raw GET for BYTES and for statuses that must be READ, not thrown on — the
 *  harness's api()/apiWrite() throw on non-200/non-2xx by contract (their
 *  documented job), while tests here assert 400 answers, so those reads bypass
 *  them deliberately and say so. */
async function rawGet(
  path: string,
  session: Session
): Promise<{
  status: number;
  body: Buffer;
  contentType: string | null;
  disposition: string | null;
}> {
  const res = await fetch(`${harness.api}${path}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  return {
    status: res.status,
    body: Buffer.from(await res.arrayBuffer()),
    contentType: res.headers.get('content-type'),
    disposition: res.headers.get('content-disposition'),
  };
}

/** The filename the browser would use, extracted by the SAME regex the shipped
 *  client applies (api.ts:3726), so the client-vs-route comparison below is
 *  one parse against the header, not two hand-rolled ones. */
const dispositionFilename = (header: string | null): string | null =>
  header?.match(/filename="?([^";\n]+)"?/)?.[1] ?? null;

/** Boot any golden route through the harness's drain-then-navigate machinery
 *  (nginx.conf:24 rate=10r/s burst=20 sheds boots; the batch never hand-rolls
 *  a bare goto). settledReload re-drives the CURRENT url the same way. */
async function bootTimeline(page: Page, cameraId: string): Promise<void> {
  await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(cameraId)}`);
}

/** The overlay ExportModal renders (fixed inset-0 + <Title>Export Data</Title>,
 *  ExportModal.tsx:196-200), scoped by its title so an unrelated fixed layer
 *  can never stand in for it (probe 5 measured exactly that false positive). */
const exportOverlay = (page: Page) =>
  page.locator('div.fixed.inset-0').filter({ hasText: 'Export Data' }).first();

/** The modal's five Select triggers in DOM order: 0 Type, 1 Format, 2 Camera,
 *  3 Risk, 4 Review (ExportModal.tsx:228-336; 2-4 render because exportType is
 *  the mounted default 'events', :63 + the exportType==='events' gates). */
const modalSelect = (page: Page, index: number) =>
  exportOverlay(page).locator('button[aria-haspopup="listbox"]').nth(index);

async function openExportModal(page: Page): Promise<void> {
  await page
    .getByRole('button', { name: 'Open export modal with more options', exact: true })
    .click();
  await expect(page.getByText('Export Data', { exact: true })).toBeVisible({ timeout: 10_000 });
}

/* --- paced /api/events/bulk calls (the BULK tier is the file's constraint) --- */

/** The session the fixture hooks run against; set by beforeAll before any bulk
 *  call, because bulkCall needs it and the fixture helpers take no arguments. */
let fixtureSession: Session;

/** One slot machine for the whole file: the BULK window is per CLIENT IP, not
 *  per helper (rate_limit.py:466-470), so POST and DELETE share this clock. */
let lastBulkCallAt = 0;

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function bulkSlot(): Promise<void> {
  const wait = lastBulkCallAt + BULK_SPACING_MS - Date.now();
  if (wait > 0) await sleep(wait);
  lastBulkCallAt = Date.now();
}

/** One bulk call, spaced, with the ONE retry the tier allows a paced caller to
 *  need: a 429 means foreign traffic (or the window's tail from a previous
 *  run) holds the slot, and a 60 s sliding window clears in 60 s + margin.
 *  Raw fetch because apiWrite THROWS on 429 — the status here is the branch. */
async function bulkCall(method: 'POST' | 'DELETE', payload: unknown): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    await bulkSlot();
    const res = await fetch(`${harness.api}/api/events/bulk`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Cookie: `${fixtureSession.name}=${fixtureSession.value}`,
      },
      body: JSON.stringify(payload),
    });
    if (res.status !== 429) return res;
    if (attempt >= 1) {
      throw new Error(
        `/api/events/bulk ${method} answered 429 twice; the BULK tier (12 per sliding minute, ` +
          `header cite) has no slot left for this fixture`
      );
    }
    await sleep(65_000);
  }
}

async function bulkHardDelete(ids: number[]): Promise<void> {
  for (let i = 0; i < ids.length; i += 100) {
    // The route caps a request at 100 ids (api/schemas/bulk.py:182-187).
    const res = await bulkCall('DELETE', { event_ids: ids.slice(i, i + 100), soft_delete: false });
    const text = await res.text();
    if (res.status < 200 || res.status >= 300) {
      throw new Error(
        `fixture: DELETE /api/events/bulk answered ${res.status}: ${text.slice(0, 200)}`
      );
    }
  }
}

async function purgeCamera(session: Session, cameraId: string): Promise<void> {
  const live = await api<{ items: { id: number }[] }>(
    harness,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  if (live.items.length > 0) await bulkHardDelete(live.items.map((row) => row.id));
  // Trash on this camera too: GET /api/events/deleted takes NO params and the
  // camera filter below is client-side (harness.ts:745-759 documents it). A
  // trashed row would not count in an export (export_service.py:766), but it
  // does sit in the way of the "this camera holds zero rows" premise.
  const trashed = await api<{ items: { id: number; camera_id: string }[] }>(
    harness,
    session,
    '/api/events/deleted'
  );
  const mine = trashed.items.filter((row) => row.camera_id === cameraId).map((row) => row.id);
  if (mine.length > 0) await bulkHardDelete(mine);
}

/**
 * This file's own fixture — harness.ts exposes no export fixture and the file
 * rule bars editing it, so the batch's own builder pattern (createFeedback-
 * Fixture, harness.ts:1290-1388) is reproduced here: 409-tolerant camera
 * create (the 60 s cached list can say "absent" while the DB says "exists";
 * the id rides inside the 409 detail and is confirmed against the UNcached
 * GET /api/cameras/{id}, harness.ts:485-527 records why a bare POST cannot be
 * apiWrite), waitForCameraInList for the cached list the modal's select reads,
 * one shared instant ~6 h ago, UNIQUE batch_id per row (events.batch_id is
 * UNIQUE, measured) — plus this file's own pacing discipline for the BULK
 * tier, and a teardown that hard-deletes ONLY the 4 probe rows (the pool's
 * retention is argued in the header; afterAll cites it too).
 */
async function ensureCamera(session: Session, name: string, folderPath: string): Promise<string> {
  const list = await api<{ items: { id: string; name: string }[] }>(
    harness,
    session,
    '/api/cameras'
  );
  const known = (list.items ?? []).find((cam) => cam.name === name);
  if (known) return known.id;
  const res = await fetch(`${harness.api}/api/cameras`, {
    method: 'POST',
    headers: {
      Cookie: `${session.name}=${session.value}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, folder_path: folderPath }),
  });
  const created = (await res.json().catch(() => null)) as { id?: string; detail?: string } | null;
  if (res.status >= 200 && res.status < 300) {
    if (!created?.id) throw new Error(`fixture: POST /api/cameras for '${name}' 2xx had no id`);
    return created.id;
  }
  if (res.status !== 409) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered ${res.status}: ` +
        JSON.stringify(created).slice(0, 200)
    );
  }
  const found = (created?.detail ?? '').match(/already exists \(id: ([^)]+)\)/);
  if (!found) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered 409 with an unparseable detail: ` +
        (created?.detail ?? '').slice(0, 200)
    );
  }
  await api<{ id: string }>(harness, session, `/api/cameras/${encodeURIComponent(found[1])}`);
  return found[1];
}

async function seedRows(
  cameraId: string,
  prefix: string,
  salt: number,
  specs: Array<{ risk_score: number; risk_level: string; summary: string }>
): Promise<number[]> {
  const res = await bulkCall('POST', {
    events: specs.map((row, i) => ({
      batch_id: `${prefix}-${salt}-${i}`,
      camera_id: cameraId,
      started_at: new Date(Date.now() - 6 * 3_600_000).toISOString(),
      ...row,
    })),
  });
  // The route answers 207 MULTI-STATUS (events.py:1544), so the body's
  // `succeeded` count is the truth, not the status code alone.
  const bulk = (await res.json().catch(() => null)) as {
    succeeded?: number;
    results?: { id: number | null }[];
  } | null;
  if (res.status < 200 || res.status >= 300 || !bulk || bulk.succeeded !== specs.length) {
    throw new Error(
      `export fixture: ${cameraId} seed answered ${res.status} ` +
        `succeeded ${bulk?.succeeded ?? '?'}/${specs.length}`
    );
  }
  const ids = (bulk.results ?? []).map((r) => r.id).filter((id): id is number => id !== null);
  if (ids.length !== specs.length) {
    throw new Error(
      `export fixture: ${cameraId} seed returned ${ids.length} ids for ${specs.length} rows`
    );
  }
  return ids;
}

async function createExportFixture(session: Session): Promise<Fixture> {
  const probeCameraId = await ensureCamera(session, PROBE_CAMERA, '/cameras/fe3_export_modal');
  const bulkCameraId = await ensureCamera(session, BULK_CAMERA, '/cameras/fe3_export_bulk');
  const emptyCameraId = await ensureCamera(session, EMPTY_CAMERA, '/cameras/fe3_export_empty');
  // The modal's camera select is built from the 60 s cached list (header), so
  // every camera this file needs as an OPTION waits for the cache to converge.
  await waitForCameraInList(harness, session, PROBE_CAMERA);
  await waitForCameraInList(harness, session, BULK_CAMERA);
  await waitForCameraInList(harness, session, EMPTY_CAMERA);

  // Only the two SMALL cameras get purged — each purge is budget from the 12
  // bulk calls per sliding minute (header cite). BULK_CAMERA's pool is topped
  // up below and never purged or deleted: its rows are scoped to this file's
  // camera, test 4 pins its size by live read, and every deletion here is a
  // deletion the next run's top-up would have to pay for again.
  await purgeCamera(session, probeCameraId);
  await purgeCamera(session, emptyCameraId);

  const salt = Date.now();
  const probeEventIds = await seedRows(
    probeCameraId,
    'fe3f052',
    salt,
    PROBE_ROWS.map((row, i) => ({ ...row, summary: `fe3f052 modal fixture ${i}` }))
  );

  // Top the bulk pool UP to exactly BULK_ROWS (a rerun after a green run finds
  // it already full and seeds nothing — a rerun after a PARTIAL run adds only
  // what went missing, never 1200 on top).
  const live = await api<{ pagination?: { total?: number } }>(
    harness,
    session,
    `/api/events?limit=1&camera_id=${encodeURIComponent(bulkCameraId)}`
  );
  const missing = BULK_ROWS - (live.pagination?.total ?? 0);
  for (let b = 0; b < Math.ceil(missing / 100); b++) {
    const size = Math.min(100, missing - b * 100);
    await seedRows(
      bulkCameraId,
      `fe3f052b${b}`,
      salt,
      Array.from({ length: size }, (_, k) => ({
        risk_score: 45,
        risk_level: 'medium',
        summary: `fe3f052 bulk fixture ${b}-${k}`,
      }))
    );
  }
  return { probeCameraId, probeEventIds, bulkCameraId, emptyCameraId };
}

/** Poll a Node-side read of GET /api/exports/{id} until terminal — here the
 *  route is ground truth, not the thing under test. */
async function waitJob(session: Session, jobId: string, timeoutMs: number): Promise<ExportJobView> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const job = await api<ExportJobView>(harness, session, `/api/exports/${jobId}`);
    if (job.status === 'completed' || job.status === 'failed') return job;
    if (Date.now() >= deadline)
      throw new Error(`job ${jobId} still ${job.status} after ${timeoutMs}ms`);
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

test.beforeAll(async () => {
  // Fixture work runs in the hook; inside beforeAll, test.setTimeout sets the
  // HOOK's timeout. The budget is dominated by the BULK tier's arithmetic, not
  // by the work itself: worst case a first-ever stack seeds 12 chunks of the
  // pool at one call per 5.5 s (~66 s) plus two purges, the camera-cache waits
  // cost up to 90 s each, and a single foreign-traffic 429 adds a 65 s window
  // wait. 480 s covers every path that ends green.
  test.setTimeout(480_000);
  const session = await adminSession(harness);
  fixtureSession = session;
  fx = await createExportFixture(session);
});

test.afterAll(async () => {
  // Run 1's teardown crashed here with "Cannot read properties of undefined
  // (reading 'probeEventIds')" AFTER beforeAll had already failed the file —
  // a cleanup hook must never add a second failure to the first real one.
  if (!fx) return;
  const session = await adminSession(harness);
  fixtureSession = session;
  // Only this file's 4 probe rows go back in the ground. The 1200-row pool
  // stays (header cite): camera-scoped, pinned live by test 4, and its ~12
  // DELETE calls each cost a slot of the NEXT run's bulk budget. The zero-row
  // camera never held rows, so nothing here can disturb that premise either.
  await bulkHardDelete(fx.probeEventIds);
});

test.describe('F-052 export modal: opens and chooses', () => {
  test('the More Options button opens the modal, and its camera select mirrors GET /api/cameras with the page camera pre-filled', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(120_000);
    await seedTourDismissed(page);
    const session = await loginAsAdmin(page, harness);
    await bootTimeline(page, fx.probeCameraId);

    // The row's named control is the ONLY opener; a click that opened nothing
    // dies on the Title expect with the app's own pixels as the witness.
    await openExportModal(page);

    const apiCameras = await api<{ items: { id: string; name: string }[] }>(
      harness,
      session,
      '/api/cameras'
    );
    await modalSelect(page, 2).click();
    const options = (await page.getByRole('option').allInnerTexts()).map((t) => t.trim());
    const names = apiCameras.items.map((cam) => cam.name);
    // The select is exactly "All cameras" + one option per API camera, in the
    // endpoint's own order: a select that dropped a cache-stale camera or
    // invented one goes red here.
    expect(options).toEqual(['All cameras', ...names]);
    expect(names).toContain(PROBE_CAMERA);
    await page.keyboard.press('Escape');

    // Pre-fill is shipped behaviour (initialFilters.camera_id = the page's
    // filter, EventTimeline.tsx:1921-1926 → the Select's value): the trigger
    // reads the camera the user was looking at, not "All cameras".
    await expect(modalSelect(page, 2)).toContainText(PROBE_CAMERA, { timeout: 10_000 });
    // The defaults test 2's body equality relies on: Format starts csv
    // (ExportModal.tsx:64) and Review renders its placeholder "All events"
    // (:329-335), so "chooses" starts from a decided place, not a blank one.
    await expect(modalSelect(page, 1)).toContainText('CSV');
    await expect(modalSelect(page, 4)).toContainText('All events');

    await expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('choosing format JSON, camera, risk Critical and two columns posts exactly what was chosen, and the file holds exactly those rows and columns', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(120_000);
    await seedTourDismissed(page);
    const session = await loginAsAdmin(page, harness);
    await bootTimeline(page, fx.probeCameraId);
    await openExportModal(page);

    await modalSelect(page, 1).click();
    await page.getByRole('option', { name: 'JSON', exact: true }).click();
    // Drive the camera select rather than lean on the pre-fill: the clause's
    // "chooses camera" is the click, and the POST must then carry this id.
    await modalSelect(page, 2).click();
    await page.getByRole('option', { name: PROBE_CAMERA, exact: true }).click();
    await modalSelect(page, 3).click();
    await page.getByRole('option', { name: 'Critical', exact: true }).click();

    // Columns: "Select None" re-opens at exactly ['event_id'] (the selector's
    // own :104-111), the pill recomputes to "1 of 11", and adding Risk Score
    // makes a 2-element array the POST must carry verbatim.
    await exportOverlay(page).getByRole('button', { name: 'Select None', exact: true }).click();
    await expect(exportOverlay(page).getByText('1 of 11')).toBeVisible();
    await exportOverlay(page).getByRole('button', { name: 'Risk Score', exact: true }).click();
    await expect(exportOverlay(page).getByText('2 of 11')).toBeVisible();

    // Ground truth BEFORE the click, from the browse list's endpoint: the same
    // stored-column predicate the export service applies (header cites), so
    // this is the count the artifact MUST match — and it is 2, not 4: the risk
    // filter bit.
    const matching = await api<{ pagination?: { total?: number } }>(
      harness,
      session,
      `/api/events?limit=1&camera_id=${encodeURIComponent(fx.probeCameraId)}&risk_level=critical`
    );
    expect(matching.pagination?.total).toBe(2);

    const posted = page.waitForRequest(
      (req) => req.url().endsWith('/api/exports') && req.method() === 'POST',
      { timeout: 20_000 }
    );
    await page.getByRole('button', { name: 'Start Export', exact: true }).click();
    const req = await posted;
    const body = JSON.parse(req.postData() ?? '{}') as Record<string, unknown>;
    // The clause's "chooses", decided by the shipped submit body
    // (ExportModal.tsx:142-149): every chosen value travels and every
    // un-chosen filter is null — including the date pair test 3 is about and
    // the review select still on its default. FULL-object equality, so an
    // extra field, a dropped one, or a reordered column list reddens this.
    expect(body).toEqual({
      export_type: 'events',
      export_format: 'json',
      camera_id: fx.probeCameraId,
      risk_level: 'critical',
      start_date: null,
      end_date: null,
      reviewed: null,
      columns: ['event_id', 'risk_score'],
    });

    const resp = await req.response();
    if (!resp) throw new Error('Start Export produced no response');
    expect(resp.status()).toBe(202); // routes/exports.py:223-231
    const created = (await resp.json()) as { job_id: string; status: string };
    expect(created.status).toBe('pending');

    // The row the modal would poll round-trips what was chosen — the route
    // stores it as a JSON STRING (schemas/export.py:275 ← exports.py:257-265).
    const job = await waitJob(session, created.job_id, 60_000);
    expect(job.status).toBe('completed');
    expect(JSON.parse(job.filter_params ?? 'null')).toEqual({
      camera_id: fx.probeCameraId,
      risk_level: 'critical',
      start_date: null,
      end_date: null,
      reviewed: null,
      columns: ['event_id', 'risk_score'],
    });
    // The completed half of the progress row (exports.py:183-188): processed
    // == total == the COUNT THE FILTER NAMED, not the camera's 4.
    expect(job.progress.progress_percent).toBe(100);
    expect(job.progress.current_step).toBe('Complete');
    expect(job.progress.total_items).toBe(2);
    expect(job.progress.processed_items).toBe(2);

    // The artifact itself, from the bytes the download route answers: the two
    // CHOSEN columns and exactly the two rows the filters named — the clause's
    // filters proven on the file, not on a widget.
    const file = await rawGet(`/api/exports/${created.job_id}/download`, session);
    expect(file.status).toBe(200);
    expect(file.contentType).toContain('application/json'); // exports.py:526 map
    const rows = JSON.parse(file.body.toString('utf8')) as Record<string, unknown>[];
    expect(rows.map((r) => Object.keys(r).sort()).sort()).toEqual([
      ['event_id', 'risk_score'],
      ['event_id', 'risk_score'],
    ]);
    const liveCritical = await api<{ items: { id: number; risk_score: number }[] }>(
      harness,
      session,
      `/api/events?limit=10&camera_id=${encodeURIComponent(fx.probeCameraId)}&risk_level=critical`
    );
    expect(rows.map((r) => JSON.stringify([r.event_id, r.risk_score])).sort()).toEqual(
      liveCritical.items.map((e) => JSON.stringify([e.id, e.risk_score])).sort()
    );

    await expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

test.describe('F-052 export modal: dates', () => {
  test('typing both modal date inputs attaches the range to the export', async ({ page }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(120_000);
    // Ruling 234 ([r234]): useDateRangeState keeps custom dates and preset in
    // local state when persistToUrl is false (ExportModal.tsx:57-59), so typing
    // both date inputs updates dateRangeApiParams and sends start_date/end_date
    // in POST /api/exports.
    await seedTourDismissed(page);
    await loginAsAdmin(page, harness);
    await bootTimeline(page, fx.probeCameraId);
    await openExportModal(page);

    const day = new Date().toISOString().slice(0, 10);
    await exportOverlay(page).locator('input[type="date"]').first().fill(day);
    await exportOverlay(page).locator('input[type="date"]').last().fill(day);

    const posted = page.waitForRequest(
      (req) => req.url().endsWith('/api/exports') && req.method() === 'POST',
      { timeout: 20_000 }
    );
    await page.getByRole('button', { name: 'Start Export', exact: true }).click();
    const body = JSON.parse((await posted).postData() ?? '{}') as Record<string, unknown>;
    expect(body.start_date).toBe(day);
    expect(body.end_date).toBe(day);

    await expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

test.describe('F-052 export modal: watches progress', () => {
  test('the panel paints the running job row it polls — "{FORMAT} Export", the starting step, 0%, no items line — and completion closes the modal', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(180_000);
    await seedTourDismissed(page);
    const session = await loginAsAdmin(page, harness);
    // Boot LIGHT (this file's 4-row camera): the header records run 3's
    // measurement that the 1200-row POOL PAGE starves the nginx api bucket so
    // hard the Start Export POST dies in fetchApi's 30 s timeout client-side.
    // The pool is still what the export filters — it is CHOSEN through the
    // modal's own camera select below, the path test 2 proves, so the page
    // under the modal never pages 1200 rows.
    await bootTimeline(page, fx.probeCameraId);
    await openExportModal(page);

    // The completion denominator: a LIVE read of the pool camera's row count
    // BEFORE the click, and the premise that the pool is exactly what the
    // fixture topped it to (the header says why teardown never deletes it — a
    // foreign row on this camera reddens THIS premise instead of quietly
    // drifting the denominator).
    const poolRows = await api<{ pagination?: { total?: number } }>(
      harness,
      session,
      `/api/events?limit=1&camera_id=${encodeURIComponent(fx.bulkCameraId)}`
    );
    expect(poolRows.pagination?.total).toBe(BULK_ROWS);

    // Choose the pool camera THROUGH the modal (the pre-filled page camera is
    // the probe camera — the click, not the URL, is what points this job at
    // 1200 rows).
    await modalSelect(page, 2).click();
    await page.getByRole('option', { name: BULK_CAMERA, exact: true }).click();
    await expect(modalSelect(page, 2)).toContainText(BULK_CAMERA, { timeout: 10_000 });

    // Two instruments installed BEFORE the click, because the running window
    // (2020 ms measured at 1200 rows; a 400-row job is FASTER than the first
    // poll and paints nothing — header) could still in principle end between
    // two reads: (a) every GET /api/exports/{id} RESPONSE the browser receives,
    // captured from its own traffic (reading a response body is not
    // interception — the guard covers route/unroute/routeFromHAR/routeWebSocket
    // only); (b) a page-side MutationObserver that snapshots the panel card's
    // text on EVERY DOM-mutation microtask WHILE THE CARD IS ATTACHED. Attached-
    // only is the load-bearing choice: handleExportComplete calls
    // onExportComplete(true) SYNCHRONOUSLY inside fetchStatus (ExportModal.tsx:
    // 162-168 + ExportProgress.tsx:81-83), so the completed commit and the
    // parent's unmount batch into ONE React commit — an isConnected-guarded
    // observer sees the card detach with completed text never once attached,
    // which is what turns "the completed frame never paints" (header claim)
    // into an OBSERVABLE negative instead of an unfalsifiable one. A snapshot
    // taken on a detached node would report the batch's internal text and prove
    // nothing. The panel's FIRST attached frame can legitimately be the PENDING
    // row (POST answers 202 status 'pending' — exports.py:223-231, model default
    // models/export_job.py:99; current_step NULL renders the raw status,
    // ExportProgress.tsx:269) while the RUNNING commit at :158-161 races the
    // mount-time fetch (:107) — so the instruments freeze the WHOLE attached
    // sequence and the running frame is PAIRED with the running JSON by derived
    // value, not by position.
    await page.evaluate(() => {
      const w = window as unknown as Record<string, unknown> as {
        __w?: { header: string | null; cardText: string }[];
        __dl?: boolean;
      };
      w.__w = [];
      w.__dl = false;
      let card: Element | null = null;
      const grab = () => {
        // The header's OTHER never-rendered claim, checked against the live
        // document only: ExportProgress's Download button (:318-324) is inside
        // the same commit that unmounts, so a Download button attached to the
        // document at ANY microtask while this job lived would be caught here.
        const dl = Array.from(document.querySelectorAll('button')).some(
          (b) => /^Download /.test(b.textContent?.trim() ?? '') && b.offsetParent !== null
        );
        if (dl) w.__dl = true;
        if (!card || !card.isConnected) {
          card = null;
          const header = Array.from(document.querySelectorAll('span')).find((s) =>
            /^(CSV|JSON|EXCEL|ZIP) Export$/.test(s.textContent?.trim() ?? '')
          );
          if (!header) return;
          card = header.closest('div[class*="rounded"]');
          if (!card) return;
        }
        const live = card;
        const snap = {
          header: live.querySelector('span[class*="font-medium"]')?.textContent?.trim() ?? null,
          cardText: (live as HTMLElement).innerText,
        };
        const prev = w.__w?.[w.__w.length - 1];
        if (!prev || prev.cardText !== snap.cardText) (w.__w ??= []).push(snap);
      };
      const obs = new MutationObserver(grab);
      obs.observe(document.body, { childList: true, subtree: true, characterData: true });
      grab();
    });
    const polls: ExportJobView[] = [];
    page.on('response', (res) => {
      if (/^GET .+\/api\/exports\/[0-9a-fA-F-]+$/.test(`${res.request().method()} ${res.url()}`)) {
        void res
          .json()
          .then((json) => polls.push(json as ExportJobView))
          .catch(() => undefined);
      }
    });

    const posted = page.waitForRequest(
      (req) => req.url().endsWith('/api/exports') && req.method() === 'POST',
      { timeout: 20_000 }
    );
    const panelMounted = page.getByText('CSV Export', { exact: true }).waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    await page.getByRole('button', { name: 'Start Export', exact: true }).click();
    const req = await posted;
    const resp = await req.response();
    if (!resp) throw new Error('Start Export produced no response');
    const created = (await resp.json()) as { job_id: string };
    // The select click is what made this a POOL export: the POST the shipped
    // submit builds (ExportModal.tsx:142-149) carries the chosen camera id.
    expect((JSON.parse(req.postData() ?? '{}') as Record<string, unknown>).camera_id).toBe(
      fx.bulkCameraId
    );
    await panelMounted;

    // The panel renders ONLY once a job exists (ExportProgress.tsx:187), so
    // every attached frame it ever held is a function of a poll's answer. Let
    // the mutation queue flush, then read both frozen instruments.
    await page.waitForTimeout(300);
    const seen = (await page.evaluate(() => (window as unknown as Record<string, unknown>).__w)) as
      PanelFrame[] | null;
    const sawDownloadButton = await page.evaluate(
      () => (window as unknown as Record<string, unknown>).__dl === true
    );
    if (!seen || seen.length === 0) {
      throw new Error('the observer never saw the progress panel ATTACHED to the document');
    }
    if (polls.length === 0) {
      throw new Error('the panel painted before any GET /api/exports/{id} response');
    }
    // Every distinct frame the panel ever held is either the pending row or a
    // running row — never a completed one, and that is asserted below. Pairing
    // is by DERIVED text: the frame whose step line equals the running JSON's
    // current_step is the frame that response produced.
    const running = polls.find((job) => job.status === 'running');
    if (!running) {
      throw new Error(
        `no poll answered 'running' (${polls.map((job) => job.status).join(',')}): the job ` +
          `finished before the panel could see it and this leg's premise is gone`
      );
    }
    expect(running.progress.current_step).toBe(
      `Starting ${running.export_format.toUpperCase()} export...`
    ); // exports.py:160
    expect(running.progress.total_items).toBeNull(); // exports.py:183-188 sets it at completion only
    expect(running.progress.progress_percent).toBe(0); // model default :118, untouched while running
    const step = running.progress.current_step ?? '';
    const frame = seen.find((f) => f.cardText.includes(step));
    if (!frame) {
      throw new Error(
        `the panel never held the running row's step ${JSON.stringify(step)}; frames: ` +
          JSON.stringify(seen.map((f) => f.cardText.replace(/\n/g, ' | ')))
      );
    }
    // Header text = {format.toUpperCase()} Export (:239); step and percent are
    // rendered FROM THE ROW (:269-271). A DOM fed by anything other than this
    // response — a hardcoded label, the in-memory tracker, a pre-set
    // denominator — diverges here.
    expect(frame.header).toBe(`${running.export_format.toUpperCase()} Export`);
    expect(frame.cardText).toContain(`${running.progress.progress_percent}%`);
    // And the shipped negative: the "N / M items" line is gated on a non-null
    // total_items (:282-284), so no frame ever held an items line.
    for (const f of seen) expect(f.cardText).not.toMatch(/\/\s*\d[\d,]*\s+items/);

    // The two never-render claims of the header, now observable negatives:
    // completion's commit and the parent's unmount are ONE React batch
    // (ExportModal.tsx:162-168 calls onExportComplete synchronously from
    // ExportProgress.tsx:81-83), so NO attached frame ever carried the
    // completed row's text and the Download button (:318-324) never attached.
    const completed = polls.find((job) => job.status === 'completed');
    for (const f of seen) {
      expect(f.cardText).not.toContain('Complete');
      if (completed) expect(f.cardText).not.toContain(`${completed.progress.progress_percent}%`);
    }
    expect(sawDownloadButton).toBe(false);

    // The close the row's clause rides on: completion, via
    // onExportComplete, unmounts the modal (EventTimeline.tsx:1927-1929). The
    // modal vanishing IS the assertion; Node-side, the same row is terminal.
    await expect(exportOverlay(page)).toBeHidden({ timeout: 60_000 });
    const done = await waitJob(session, created.job_id, 60_000);
    expect(done.status).toBe('completed');
    // The completion half of the row (exports.py:183-188: processed=total=
    // event_count) AGREES with the live list read taken before the click —
    // the denominator the panel would have shown had it ever had an items
    // line is the pool, neither a constant nor a guess.
    expect(done.progress.total_items).toBe(poolRows.pagination?.total);
    // The browser's own traffic proves the shipped 1000 ms poll cadence ran
    // (ExportProgress.tsx:110-114) rather than a single lucky read: the running
    // row it rendered and the completed row that closed it are DIFFERENT
    // answers the client received.
    expect(polls.length).toBeGreaterThanOrEqual(2);

    await expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

test.describe('F-052 export modal: downloads the file', () => {
  test("the app's Download button produces exactly the bytes GET /api/exports/{id}/download answers, under the name the route's header names", async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(120_000);
    await seedTourDismissed(page);
    const session = await loginAsAdmin(page, harness);

    // A CSV scoped to this file's 4-row camera, started through the shipped
    // POST (the same one the modal's button fires — apiWrite here only because
    // the job must be terminal BEFORE the app-side click, and a harness-side
    // POST keeps this leg's clock out of the download assertion). The app-side
    // path is then entered through /data, the OTHER mount site of the very
    // button the modal's panel would have shown (header cites: ExportProgress.
    // tsx:318-324 == DataManagementPage.tsx:505-512 — both call handleDown-
    // load → downloadExportFile, api.ts:3700-3748); inside the modal that
    // button provably never renders, so a real click on /data IS the app's own
    // path, not a server-side guess.
    const started = await apiWrite<{ job_id: string }>(harness, session, 'POST', '/api/exports', {
      export_type: 'events',
      export_format: 'csv',
      camera_id: fx.probeCameraId,
      risk_level: null,
      start_date: null,
      end_date: null,
      reviewed: null,
      columns: null,
    });
    const done = await waitJob(session, started.job_id, 60_000);
    expect(done.status).toBe('completed');

    // Ground truth, Node-side, from the SAME endpoint the client fetches.
    const truth = await rawGet(`/api/exports/${started.job_id}/download`, session);
    expect(truth.status).toBe(200);
    expect(truth.contentType).toContain('text/csv'); // exports.py:526 map
    const named = dispositionFilename(truth.disposition);
    expect(named).toMatch(/^events_export_\d{8}_\d{6}\.csv$/); // service naming :848
    expect(truth.body.subarray(0, 9).toString()).toBe('Event ID,');

    // Reach /data the way the header says it must be reached here: boot the
    // LIGHT timeline through the harness (settleBoot's timeline-page race is
    // what owns boot-health on THIS lane's pages; a deep quietBoot(page,'/data')
    // could never settle — run 3 measured the throw on a page that had
    // rendered /data fine), then click the shipped sidebar's ADMIN-group link.
    // The NavLink is CLIENT-SIDE (App.tsx:247-256 nests all routes under the
    // already-mounted ProtectedRoute+Layout), so no document remount and no
    // second wave into the shared nginx bucket — the file's boot rule,
    // satisfied by navigation instead of by a re-drain.
    await bootTimeline(page, fx.probeCameraId);
    // Navigate via the Settings hub in the sidebar -> Data tab in HubTabBar (F4.9).
    await page.getByTestId('sidebar-hub-settings').click();
    await expect(page).toHaveURL(/\/settings\/cameras$/);
    await page.getByTestId('settings-tab-data').click();
    await expect(page).toHaveURL(/\/data$/);
    await expect(page.getByTestId('data-management-page')).toBeVisible({ timeout: 30_000 });
    const card = page.getByTestId(`export-job-${started.job_id}`);
    await expect(card).toBeVisible({ timeout: 30_000 });
    // The shipped gate (:283): a completed job with a result row is exactly
    // when its Download button exists.
    const downloadButton = card.getByRole('button', { name: 'Download', exact: true });
    await expect(downloadButton).toBeVisible({ timeout: 15_000 });

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 30_000 }),
      downloadButton.click(),
    ]);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    const artifact = Buffer.concat(chunks);

    // The artifact the app produced, mirrored against the endpoint read:
    // byte-identical, same digest, and the name the anchor used is the one the
    // route's Content-Disposition names — parsed by the client's own regex.
    // A truncating download, a stale cached file, or a mis-derived name goes
    // red here.
    expect(download.suggestedFilename()).toBe(named);
    expect(artifact.length).toBe(truth.body.length);
    expect(sha256(artifact)).toBe(sha256(truth.body));
    // Content = this camera's four rows under the FULL default column set
    // (columns:null → all 11, export_service.py:210-224): header + 4 rows. The
    // writer is csv.writer with the DEFAULT dialect (:355), whose lineterminator
    // is CRLF — so rows are separated by \r\n and a split on \n alone would strand
    // a trailing \r on every line. Split on the shipped terminator; no trim of a
    // real field, so a genuinely empty/extra row still reddens the count.
    const lines = artifact.toString('utf8').replace(/\r\n$/, '').split(/\r\n/);
    expect(lines[0]).toBe(
      'Event ID,Camera,Started At,Ended At,Risk Score,Risk Level,Summary,Detections,' +
        'Reviewed,Object Types,Reasoning'
    );
    expect(lines.length).toBe(fx.probeEventIds.length + 1);

    await expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});

test.describe('F-052 export modal: a failing job closes the modal, unseen', () => {
  test('a job that fails server-side is FAILED with the service message, its download answers 400 — and the modal is already gone before any error branch could render', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(120_000);
    await seedTourDismissed(page);
    const session = await loginAsAdmin(page, harness);

    await bootTimeline(page, fx.probeCameraId);
    await openExportModal(page);

    // The premise, re-pinned every run: this file's own camera, purged in the
    // hook, holds ZERO rows — that is what walks the service into its empty-
    // branch corner (header cite), so a foreign row would COMPLETE the job and
    // this leg would honestly say so here rather than confuse the reader.
    const emptyRows = await api<{ pagination?: { total?: number } }>(
      harness,
      session,
      `/api/events?limit=1&camera_id=${encodeURIComponent(fx.emptyCameraId)}`
    );
    expect(emptyRows.pagination?.total).toBe(0);

    // Chosen THROUGH the modal, so the user's action is the one under test:
    // Excel + the empty camera.
    await modalSelect(page, 1).click();
    await page.getByRole('option', { name: 'Excel', exact: true }).click();
    await modalSelect(page, 2).click();
    await page.getByRole('option', { name: EMPTY_CAMERA, exact: true }).click();

    const posted = page.waitForRequest(
      (req) => req.url().endsWith('/api/exports') && req.method() === 'POST',
      { timeout: 20_000 }
    );
    await page.getByRole('button', { name: 'Start Export', exact: true }).click();
    const resp = await (await posted).response();
    if (!resp) throw new Error('Start Export produced no response');
    const created = (await resp.json()) as { job_id: string };

    const done = await waitJob(session, created.job_id, 60_000);
    expect(done.status).toBe('failed');
    expect(done.error_message).toBe('Unsupported export format: excel'); // service :925
    expect(done.result).toBeNull(); // exports.py:71 — result exists only when COMPLETED
    // The download route's own answer for a not-complete job (:503-506) —
    // read raw because the contract here IS a 400.
    const dl = await rawGet(`/api/exports/${created.job_id}/download`, session);
    expect(dl.status).toBe(400);
    expect((JSON.parse(dl.body.toString('utf8')) as { detail: string }).detail).toBe(
      'Export job is not complete (status: failed)'
    );

    // And the modal's shipped failure shape (header cite ExportModal.tsx:
    // 169-173 + EventTimeline.tsx:1927-1929): the error branch is unmounted
    // before it can show its text, its Close button, or a Download. UR-128
    // asserts THAT, not the shape the row wishes it had. settledReload then
    // proves the page itself survived the vanished-modal failure.
    await expect(exportOverlay(page)).toBeHidden({ timeout: 30_000 });
    expect(await page.getByText('Unsupported export format: excel').count()).toBe(0);
    await settledReload(page);
    await expect(page.getByTestId('timeline-page')).toBeVisible();

    await expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
