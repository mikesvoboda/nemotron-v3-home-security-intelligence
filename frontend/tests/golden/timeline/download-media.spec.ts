/**
 * FE-3 golden path (F2.3): F-059 — Event detail › Download Media on /timeline.
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md:195):
 *   F-059 "clicks Download Media; the first detection's image or video downloads"
 *
 * THE SHIPPED CHAIN, CLAIM BY CLAIM — every claim cites the file:line read at
 * this head, and a leg asserts the behaviour those lines promise:
 *   - How the modal opens at all (both doors here are the app's own): the URL
 *     door — selectedEventForModal starts null (EventTimeline.tsx:131) and the
 *     ?event= effect sets it (EventTimeline.tsx:329-334); and the CARD door —
 *     leg 4 clicks an EventCard instance spread from getEventCardProps, which is
 *     the only way a grid card gets a click handler: getEventCardProps carries
 *     onClick: handleEventCardClick (:790) → setSelectedEventForModal (:751-753).
 *     The card instance leg 4 aims at is the DEFAULT grid's (:1862) — viewMode
 *     and groupBy both ship as 'grid'/'time' (:115, :124), which is the branch
 *     :1741-1744's condition leaves open — with :1793 as the same-shaped card in
 *     the groupBy=camera/risk branch this file never selects.
 *     The card's own click fires it unless the point clicked is inside a button
 *     or link (EventCard.tsx:358-366, wired to the card div at :390; testid
 *     event-card-{id} at :388). A THIRD door, the live-activity rail, has its own
 *     inline onEventClick at :1104 — a DIFFERENT line from the grid card's setter,
 *     and leg 4 does NOT ride it (it clicks a grid CARD, so the setter it reaches
 *     is :753, not :1104). A bare /timeline with neither of leg 1/4's doors opens
 *     NOTHING — this file never claims a modal it did not open through a shipped
 *     door, and names the right shipped line for whichever door a leg rides.
 *   - The button. `onDownloadMedia &&` guards it (EventDetailModal.tsx:1313-1323):
 *     aria-label="Download media" (:1318), label 'Download Media' ↔ 'Downloading...'
 *     while in flight (:1321), disabled={isDownloading} (:1316). It has NO
 *     data-testid — the aria-label is the shipped handle; the two OTHER Download
 *     affordances on /timeline name themselves differently ("Download video
 *     clip", EventCard.tsx:653; "Download clip", EventVideoPlayer.tsx:280), so
 *     the role locator cannot double-match. EventTimeline.tsx:1912 always passes
 *     onDownloadMedia={handleDownloadMedia}, so the button rides EVERY modal.
 *   - The click. The modal's handler sets isDownloading, awaits
 *     onDownloadMedia(event.id), and resets in `finally` (EventDetailModal.tsx:294-306,
 *     reset at :304) — so "the label came back" is an observable of the awaited
 *     chain settling, on the success path AND the rejected one.
 *   - The service. downloadEventMedia (api.ts:3309-3373): fetchEvent (api.ts:2300)
 *     → `event.detection_ids ?? []` (:3314) → EMPTY throws `new ApiError(404,
 *     'Event has no associated media to download')` CLIENT-side (:3316-3318; the
 *     server never answers 404 for a media-less event's GET — this string is the
 *     app's own diagnosis, and ApiError's message is its 2nd ctor arg,
 *     api.ts:619-635). Non-empty: detectionId = detection_ids[0] (:3321 — the
 *     row's "first detection"), then fetchEventDetections(eventId,{limit:1})
 *     (api.ts:2598, called :3324) supplies media_type and `items?.[0]` (:3326).
 *     media_type 'video' → /api/detections/{id}/video (api.ts:3269-3271); else
 *     `/api/detections/{id}/image?full=true` (api.ts:3255-3257, called :3335).
 *     BASE_URL is '' (api.ts:880): the media fetch is SAME-ORIGIN, a real
 *     network request through the UI's nginx — not a mock, not a memory blob.
 *   - The byte source. full=true reads the source file raw and returns
 *     Response(content=image_data, media_type="image/jpeg") with NO
 *     Content-Disposition (get_detection_image signature detections.py:1211;
 *     branch :1256-1263; body :1111-1133), so the client's generated name
 *     stands: api.ts:3347-3355's regex override needs the header; the default is
 *     `event_${eventId}_media.jpg` (:3348). What downloads therefore has exactly
 *     the dropped scenario file's bytes, length and name.
 *   - The delivery. blob → createObjectURL → a.download = filename → click →
 *     remove → revoke (api.ts:3358-3366) = the browser download event
 *     Playwright catches with waitForEvent('download'), armed BEFORE the click
 *     (repo precedent e2e/specs/event-export.spec.ts:482; golden precedent
 *     identity/zones.spec.ts:499-521).
 *   - The report. EventTimeline.tsx:906-919: success → toastSuccess('Media
 *     download started') (:911); failure → toastError(err.message) (:914),
 *     sonner — `[data-sonner-toast]`, the sibling idiom (event-detail.spec.ts:314).
 *
 * WHY THE MIRROR IS THE LEG (UR-128). The row names a VALUE — the first
 * detection's image downloads — so the legs assert the FILE: what landed in
 * Chromium's download channel must equal, byte for byte, a Node fetch of the
 * very endpoint the app named, which must equal the scenario file the drop put
 * on disk. Reddening it: serve detection #2's image, a re-encoded thumbnail, a
 * wrong id in the name, or zero bytes — every one flips an equality. "The button
 * is enabled" could not go red on any of them. The DOM side of each boot is
 * pinned too (which camera chip, which risk value, which row id the download
 * name carries), so a modal for the wrong row fails the leg, not just the bytes.
 *
 * TWO CLAUSES OF THIS ROW THIS TIER CANNOT EXECUTE, AND HOW THEY SIT ON THE
 * RECORD: each has a `test.fixme` leg written for the shape it needs — held as
 * skipped, the sibling precedent (event-reevaluate.spec.ts:259/:329 for
 * F-061/F-062, event-detail.spec.ts's read-back leg for F-057) — so the file's
 * GREEN count claims only what it executed, and a skipped leg reads as
 * not-yet-proven instead of as coverage. Next to each fixme runs a leg that
 * MEASURES why the fixme cannot pass yet, so the pair is evidence plus tripwire,
 * never a guess. The suite's shape is therefore FIVE green legs + TWO fixme, and
 * the report says so in the same words the header uses.
 *   - THE ROW'S "OR VIDEO" DISJUNCT. `detection.media_type === 'video'`
 *     (api.ts:3332) is UNREACHABLE by sanctioned supply: the book ships one IMAGE
 *     per scenario, no video (backend/ai_contract/fake/scenario_fixtures/
 *     scenarios.json — seven scenarios since [F4.4], each detections:[one] or
 *     less of one exception — f4.4-gold-high carries two image detections —
 *     image: *.jpg for all;
 *     asserted against the STORED detection, not the book alone). The branch's
 *     endpoint IS a live route and its shipped refusal is 400 "Detection {id} is
 *     not a video (media_type: image)" (detections.py:1390, guard :1432, f-string
 *     :1435) — but ON THIS STACK the app itself never hears it: the route's
 *     transcoding dependency (detections.py:1395 → dependencies.py:1155 →
 *     TranscodingService.__init__) mkdirs its cache dir under the WORKING DIR
 *     (transcoding_service.py :277-280, :284) and the baked image's root
 *     filesystem is read-only, so __init__ re-raises (:288-297) and FastAPI
 *     answers 500 — the envelope naming "[Errno 30] Read-only file system:
 *     'data/transcoded_cache'" — BEFORE the handler body runs. So the video leg is
 *     a fixme, the supply-witness pins THAT measured 500 (status, envelope code,
 *     cache-dir sentence, and the ABSENCE of the HTTPException detail key, which
 *     names the layer that answered), and the fixme's own docblock says what would
 *     turn it green. The witness is honest about what it does NOT prove: it opens
 *     no page, clicks nothing, exercises no shipped client code, and would stay
 *     green if the video branch were deleted — which is exactly why the clause
 *     needs the fixme and not a passing leg. The branch's IMAGE side is genuinely
 *     pinned by legs 1/4: with `isVideo` inverted or the two URL builders swapped
 *     (api.ts:3332-3335), the click would fetch the video route, hit that 500 at
 *     api.ts:3343-3344 and produce NO download — legs 1 and 4 both die.
 *   - "FIRST" WITH MORE THAN ONE DETECTION. Same book fact — at most one
 *     detection per event via sanctioned supply — and there is no client-called
 *     write that attaches a second detection to an event (the app's detection
 *     reads are GET-only; the detection route's POST/PATCH/DELETE are not shipped
 *     UI affordances), so a ≥2-selection has no honest data source and is NOT
 *     faked by DDL (bulk rows carry ZERO detections: events.py's bulk path builds
 *     no Detection). It is a fixme, with the two measured reasons in its docblock.
 *     What leg 5 pins instead, WITHOUT leaning on a comparison that one row makes
 *     trivial: (a) the ANCHOR — the id the app calls "first", event.detection_ids
 *     [0] (api.ts:3321, from Event.detections/detection_id_list, events.py:189-202)
 *     is the id whose bytes legs 1/4 mirrored and whose id the download name
 *     carried; and (b) that the ordering knob is LIVE rather than ignored, which
 *     IS observable at one detection because the created_at branch joins the
 *     junction table and surfaces association_created_at (events.py:2241-2249,
 *     schema :228-232) where the default branch leaves it null (:2292-2299) — plus
 *     the route 400s a value outside VALID_DETECTION_ORDER_BY (:2170, :2214-2219)
 *     instead of silently defaulting. What leg 5 deliberately does NOT assert is
 *     "the two orderings pick the same row": with one detection that is green for
 *     ANY ORDER BY, including a deleted one, and writing it as a pin on the knob
 *     would be a false claim — the fixme holds that half.
 *
 * THE DROP, AND THE RESOURCE CLAIM BEHIND IT. The book's bytes are a stack-wide
 * SHA256 dedupe with 300 s TTL in Redis, Redis-only in the body (dedupe.py:164,
 * :318-366). person-at-door is F2.1's (dashboard-drop.spec.ts), harness-smoke is
 * smoke()'s (analytics-alerts/harness.ts:17-21), slow-reply is the failure mode
 * (:22-30); cat-on-porch is F-054's ROW (docs/reference/feature-inventory.md:190).
 * The ledger itself records car-in-driveway as the unclaimed byte-set
 * (analytics-alerts/harness.ts:32) — DO-1
 * drops it EARLIER in the golden run order (analytics-alerts sorts before
 * timeline/, and alerts.spec.ts ships NO deletion step — it simply never
 * removes its event), so re-dropping it here is either a fresh event (>300 s
 * later, the measured gap: ~15 specs run serially between) or a dedupe no-op
 * whose event this file can still SELECT — see the fixture. This file's camera filter and afterAll NEVER purge that camera's
 * other rows: afterAll deletes exactly the row this file selected (and its own
 * probe row), the same discipline event-reevaluate.spec.ts:141-146 practices.
 * The drop lands at camera_root/<scenario>/<image.name> (feature_check.py
 * drop(), scripts/feature_check.py:2930-2943) — the harness's own convention,
 * residue and all. ONE deletion does touch that root, and it is the SHIPPED
 * cleanup riding this file's own afterAll, not a hand-delete: the bulk hard
 * delete (soft_delete:false) deletes the event's detection FILES along with the
 * row (event_service.py:249-299 — "immediately delete associated files" — down
 * to file_cleanup_service.py:253's file_path.unlink()), and on this tier the
 * drop's camera-root copy IS that detection's file_path. Measured in run D's
 * teardown: after a green run the folder sits empty, and the next run's
 * re-drop recreates the file. No OTHER row's file is ever touched — the unlink
 * only follows the rows afterAll names, and the probe row has no detections
 * and therefore no files.
 *
 * RE-RUN DETERMINISM, STATED SO RUN 2 IS HONEST. Two greens on ONE stack must
 * survive the TTL. The fixture selects the drop's event by the DEDUPE MIRROR: an
 * event on car_in_driveway whose FIRST detection's stored file_path ends with
 * the book image's name and whose full=true read answers 200. That predicate is
 * true whether the drop created the row (run 1 on a fresh stack) or was swallowed
 * by dedupe while a matching row still exists; when afterAll has deleted the row
 * AND the TTL is unexpired, the drop yields nothing and the fixture FAILS
 * LOUDLY ("neither landed nor deduped") rather than passing on someone else's
 * row — so consecutive local runs are spaced past 300 s (the harness's own CI
 * ordering gives it that spacing anyway; feature_check golden legs are one stack
 * per run). The watcher's on_modified re-schedule (file_watcher.py:539-548)
 * cannot resurrect a purged row's file inside the TTL (same dedupe gate) —
 * measured while writing the selection predicate, not assumed.
 *
 * WHY THIS FILE OWNS ITS FIXTURES. One new file per row, so harness.ts stays
 * untouched; its builders are bound to sibling cameras whose row counts other
 * rows mirror (harness.ts:356, :676, :872). This file declares its OWN probe
 * camera `fe3-media-probe` (the harness's private ensureCamera pattern,
 * harness.ts:481-527, minus the 60 s cached-list wait (waitForCameraInList,
 * harness.ts:440-464): nothing here mirrors the
 * camera CHIP for the probe camera — the ?camera= filter is applied server-side
 * by camera_id and the row is deep-linked by id, so the stale cache cannot move
 * this file's assertions; the chip mirror that DOES run is on car_in_driveway,
 * whose registration predates every golden spec). The bulk-POST is the harness
 * builders' own supply (harness.ts:930-938 — its rows carry ZERO detections,
 * which is exactly the state the client-side 404 branch needs) and the app never
 * calls it; the drop is the sanctioned fake-VLM path. No endpoint is POSTed to
 * "make a test pass" that the app does not itself call (POST /api/cameras is the
 * settings UI's own; the negative leg clicks the shipped button and reports what
 * the shipped client says — no invented server behaviour).
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Download, Page } from '@playwright/test';

import {
  adminSession,
  apiShell as api,
  apiWrite,
  closedByGuard,
  loginAsAdminShell as loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  waitForEventCards,
  type Session,
  type TimelineHarness,
} from '../harness';

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

/* ------------------------- the scenario book + drop ------------------------ */

interface Scenario {
  name: string;
  image: string;
  detections: { class: string; confidence: number }[];
  verdict: { verdict: string; risk_score: number; summary: string };
  reply_delay_seconds?: number;
}

interface DropState {
  ready: true;
  scenario: Scenario;
  /** Absolute path of the book image — ALSO the dedupe mirror: the selected
   *  detection's stored file_path must end with path.basename(this). */
  scenarioImagePath: string;
  cameraRoot: string;
  cameraId: string;
}

type DropHarness = DropState | { ready: false; why: string };

/** The scenario this file claims; see the header's claim arithmetic. */
const CLAIMED_SCENARIO = 'car-in-driveway';

/** Collection-time and defensive like readTimelineHarness(): Playwright runs
 *  COLLECTION before any runtime skip, so a missing file must be a skip reason,
 *  never a `--list` crash outside the harness (the shape dashboard-drop.spec.ts
 *  :61-66 establishes, and dashboard-drop.spec.ts:99-103 shows a semantic
 *  refusal — a book with no usable scenario — arriving as `why`, not a throw). */
function readDropHarness(): DropHarness {
  const bookPath = process.env.FEATURE_CHECK_SCENARIOS;
  const camerasPath = process.env.FEATURE_CHECK_CAMERAS;
  const cameraRoot = process.env.FEATURE_CHECK_CAMERA_ROOT;
  if (!bookPath) return { ready: false, why: 'missing FEATURE_CHECK_SCENARIOS' };
  if (!camerasPath) return { ready: false, why: 'missing FEATURE_CHECK_CAMERAS' };
  if (!cameraRoot) return { ready: false, why: 'missing FEATURE_CHECK_CAMERA_ROOT' };
  if (!existsSync(bookPath)) return { ready: false, why: `no scenario book at ${bookPath}` };
  if (!existsSync(camerasPath)) return { ready: false, why: `no cameras file at ${camerasPath}` };
  let scenarios: Scenario[];
  let cameras: Record<string, string>;
  try {
    scenarios = (JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios: Scenario[] }).scenarios;
    cameras = JSON.parse(readFileSync(camerasPath, 'utf8')) as Record<string, string>;
  } catch (error) {
    return { ready: false, why: `harness JSON unreadable: ${String(error)}` };
  }
  const scenario = scenarios.find((entry) => entry.name === CLAIMED_SCENARIO);
  if (!scenario) return { ready: false, why: `scenario book has no ${CLAIMED_SCENARIO}` };
  if (scenario.reply_delay_seconds) {
    return { ready: false, why: `${CLAIMED_SCENARIO} delays its reply — the book's failure mode` };
  }
  if (scenario.detections.length !== 1) {
    return {
      ready: false,
      why: `${CLAIMED_SCENARIO} declares ${scenario.detections.length} detections; this file's byte mirror pins the first of exactly one, and zero would leave nothing to download`,
    };
  }
  const cameraId = cameras[scenario.name];
  if (!cameraId) return { ready: false, why: `harness seeded no camera named ${scenario.name}` };
  const scenarioImagePath = path.join(path.dirname(bookPath), scenario.image);
  if (!existsSync(scenarioImagePath)) {
    return { ready: false, why: `no scenario image at ${scenarioImagePath}` };
  }
  return { ready: true, scenario, scenarioImagePath, cameraRoot, cameraId };
}

const drop = readDropHarness();

/** scripts/feature-check.sh lives at the repo root: FOUR up from
 *  frontend/tests/golden/timeline (dashboard-drop.spec.ts:126 is three up — this
 *  file is one level deeper, so the literal is '../../../..'). */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

/* ------------------------------ the shapes --------------------------------- */

interface EventRow {
  id: number;
  camera_id: string;
  started_at: string;
  risk_score: number | null;
  summary: string | null;
  detection_count: number;
  detection_ids: number[];
}

interface DetectionItem {
  id: number;
  media_type: string | null;
  file_path: string | null;
  /** Populated ONLY by the created_at ordering branch (schemas/detections.py:
   *  228-232; the route's junction query events.py:2244-2249). The default
   *  branch leaves it null, which is what makes the knob's effect observable
   *  even at one detection — leg 5's live-knob pair rides exactly this. */
  association_created_at?: string | null;
}

interface CameraRow {
  id: string;
  name: string;
}

const eventRow = (session: Session, id: number) =>
  api<EventRow>(harness, session, `/api/events/${id}`);
const detectionItems = (session: Session, id: number, query = '?limit=10') =>
  api<{ items: DetectionItem[] }>(harness, session, `/api/events/${id}/detections${query}`);

/** A route read with no status gate and no body parsing — the shape the byte
 *  mirror and the negative-status probes need (the harness's `api()` THROWS on
 *  non-200, harness.ts:114-123, so it cannot witness a 400 or a 500). Media
 *  routes are auth-exempt in prose (api.ts:3250-3251 comment); the cookie rides
 *  anyway so the read is at worst the app's own identity. */
async function rawGet(session: Session, route: string): Promise<Response> {
  return fetch(`${harness.api}${route}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
}

/** Node's ground-truth read of one of the app's media endpoints. */
const mediaRead = (session: Session, route: string) => rawGet(session, route);

const sha256 = (bytes: Buffer): string => createHash('sha256').update(bytes).digest('hex');
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** The modal's footer control by its shipped aria-label. Substring role matching
 *  cannot hit "Download video clip"/"Download clip" — neither contains "download
 *  media". The accessible name stays "Download media" while the text reads
 *  "Downloading..." (aria-label beats content), so the locator never loses the
 *  button mid-flight. Scoped to the modal so a one-day footer twin elsewhere in
 *  the dialog cannot turn these legs strict-mode red. */
const downloadButton = (page: Page) =>
  page.getByTestId('event-detail-modal').getByRole('button', { name: 'Download media' });

/** The click AS THE APP PERFORMS IT: the download listener armed BEFORE the
 *  click (the precedent the header cites), then the file read through
 *  Playwright's own channel. download.path() resolves null for an
 *  aborted/cancelled download — that is a leg failure, stated, not an empty
 *  buffer that would make a wrong-file red look like an OK one. */
async function clickAndCatchDownload(
  page: Page,
  button: ReturnType<typeof downloadButton>
): Promise<{
  filename: string;
  bytes: Buffer;
}> {
  const waiting = page.waitForEvent('download', { timeout: 60_000 });
  await button.click();
  const download: Download = await waiting;
  const filePath = await download.path();
  expect(filePath, 'the download completed to a file rather than being cancelled').toBeTruthy();
  return { filename: download.suggestedFilename(), bytes: readFileSync(filePath as string) };
}

/* --------------------------- this file's fixtures -------------------------- */
/* The harness's camera contract re-declared locally (its ensureCamera is private
 * and its exported builders are bound to sibling cameras — header explains). */

const CAMERA_NAME = 'fe3-media-probe';
const CAMERA_FOLDER = '/cameras/fe3_media_probe';

/**
 * Idempotence for this file's own probe camera, in the harness's private
 * ensureCamera's shape (harness.ts:481-527: look the camera up by NAME first,
 * treat a 409 as routine rather than fatal, and CONFIRM any recovered id with an
 * uncached single-camera read). Two facts make the 409 arm safe rather than a
 * guess:
 *   - POST /api/cameras 409s on a NAME collision (backend/api/routes/cameras.py:
 *     746-751) and on a folder_path collision (:759-764), and the route's detail
 *     carries the existing row's id — which is what the harness parses;
 *   - the id is never a uuid on this route: it is derived from the NAME,
 *     camera_id = normalize_camera_id(name) (:769), which lowercases and folds
 *     runs of spaces/hyphens into underscores (backend/models/camera.py:29,
 *     :48-49). `fe3-media-probe` therefore has exactly ONE legal id,
 *     `fe3_media_probe`, whichever arm answered.
 * This file still resolves the id from the shipped list route by NAME rather than
 * folding the string locally, so a change to the fold rule cannot leave this
 * fixture aimed at an id the app never issued; and the confirmation read means a
 * 409 that came from folder_path rather than from this file's own camera fails
 * loudly instead of silently mis-targeting.
 */
async function ensureCamera(session: Session): Promise<string> {
  const listed = await api<CameraRow[] | { items: CameraRow[] }>(harness, session, '/api/cameras');
  const rows = Array.isArray(listed) ? listed : listed.items;
  const known = rows.find((row) => row.name === CAMERA_NAME);
  if (known) return known.id;

  try {
    const created = await apiWrite<{ id: string }>(harness, session, 'POST', '/api/cameras', {
      name: CAMERA_NAME,
      folder_path: CAMERA_FOLDER,
    });
    return created.id;
  } catch (error) {
    if (!String(error).includes('409')) throw error;
    // A 409 means the row exists and the earlier list read was the cached
    // answer (list_cameras is cache-aside, cameras.py:194-216). Re-read by name
    // and CONFIRM the id on the uncached single-camera route, as the harness does
    // (harness.ts:524-525 → cameras.py's get_camera, which is not cached).
    const again = await api<CameraRow[] | { items: CameraRow[] }>(harness, session, '/api/cameras');
    const found = (Array.isArray(again) ? again : again.items).find(
      (row) => row.name === CAMERA_NAME
    );
    if (!found) {
      throw new Error(
        `ensureCamera: POST answered 409 but GET /api/cameras lists no camera named ` +
          `${CAMERA_NAME} — the 409 came from folder_path (cameras.py:759-764), not from ` +
          "this file's own camera; refusing to guess an id"
      );
    }
    await api<{ id: string }>(harness, session, `/api/cameras/${encodeURIComponent(found.id)}`);
    return found.id;
  }
}

/** The harness's hard-purge contract re-declared (its export takes its own
 *  harness; this closes over this file's): the bulk route with soft_delete:false
 * (events.py's bulk delete) removes rows OUTRIGHT, which is what clears both
 * this file's probe rows and the drop's event + detection cascade. */
async function hardDeleteRows(session: Session, eventIds: number[]): Promise<void> {
  for (let i = 0; i < eventIds.length; i += 100) {
    await fetch(`${harness.api}/api/events/bulk`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', Cookie: `${session.name}=${session.value}` },
      body: JSON.stringify({ event_ids: eventIds.slice(i, i + 100), soft_delete: false }),
    }).catch(() => undefined); // cleanup must not turn a green run red
  }
}

async function purgeProbeRows(session: Session): Promise<void> {
  if (!probeCameraId) return;
  const stale = await api<{ items: { id: number }[] }>(
    harness,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(probeCameraId)}`
  );
  await hardDeleteRows(
    session,
    stale.items.map((row) => row.id)
  );
}

/** One media-less row on the probe camera: the bulk route is the harness
 *  builders' own supply (harness.ts:930-938) and its rows carry NO detections —
 *  the state the client-side empty-ids branch needs. NOT createDetailFixture:
 *  that camera belongs to F-056/F-057 (harness.ts:847-870). */
async function seedMedialessRow(session: Session): Promise<number> {
  const salt = Date.now();
  const bulk = await apiWrite<{
    succeeded: number;
    results: { status: string; id: number | null; error?: string }[];
  }>(harness, session, 'POST', '/api/events/bulk', {
    events: [
      {
        batch_id: `fe3f059-${salt}`, // events.batch_id is UNIQUE (harness.ts:931)
        camera_id: probeCameraId,
        started_at: new Date(Date.UTC(2026, 9, 13, 4, 20)).toISOString(),
        risk_score: 37,
        risk_level: 'low',
        summary: 'FE-3 F-059 media-less fixture row',
      },
    ],
  });
  const id = bulk.results[0]?.id;
  if (bulk.succeeded !== 1 || id === null || id === undefined) {
    throw new Error(`media-less seed failed: ${JSON.stringify(bulk).slice(0, 200)}`);
  }
  const row = await eventRow(session, id);
  if (row.detection_ids.length !== 0 || row.detection_count !== 0) {
    throw new Error(
      `media-less seed arrived WITH media: detection_ids=${JSON.stringify(row.detection_ids)} — ` +
        'the negative leg needs the client-side empty-ids branch (api.ts:3314-3318)'
    );
  }
  return id;
}

/* ------------------------------- the fixture ------------------------------- */

let probeCameraId = '';
let medialessEventId = 0;
let dropEventId = 0;
let dropDetection: { id: number; mediaType: string; sourceBytes: Buffer };
/** The drop leg's real elapsed time — REPORTED in leg 1, never asserted (no
 *  sleep floors on this tier; ~35 s is what this stack measured). */
let dropElapsedMs = 0;

test.beforeAll(async () => {
  // Drop + fake-VLM verdict + seed is real work; inside beforeAll this sets the
  // HOOK's timeout (event-detail.spec.ts:144-148 states that shape).
  test.setTimeout(420_000);
  const session = await adminSession(harness);

  // The probe camera + its media-less row first: they need no VLM and they
  // make leg 3 executable even on a stack where the drop half is env-skipped.
  probeCameraId = await ensureCamera(session);
  await purgeProbeRows(session); // a re-run starts from its own rows only
  medialessEventId = await seedMedialessRow(session);

  if (!drop.ready) return; // the file-level + per-test skips cover the legs; this
  // keeps the hook from dereferencing a { ready: false } on odd collection paths.

  // 1. The drop, through O2.2's own helper (the documented contract, not a bare
  //    copy) — the sanctioned data supply for anything detection-shaped.
  execFileSync(
    path.join(repoRoot, 'scripts/feature-check.sh'),
    ['drop', drop.scenarioImagePath, drop.scenario.name],
    {
      cwd: repoRoot,
      env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: drop.cameraRoot },
      encoding: 'utf8',
      timeout: 30_000,
    }
  );

  // 2. The drop's event, polled like feature_check.py's smoke() and the sibling
  //    specs — selection is the DEDUPE MIRROR (header): the event on
  //    car_in_driveway whose first detection's stored file_path ends with the
  //    book image's name AND whose full=true read answers 200. That anchors
  //    "this row came from THESE bytes" for the mirror, and it is what a
  //    TTL-swallowed re-drop still satisfies while a matching row exists. This
  //    loop never PURGES the camera — another lane's row on it stays untouched.
  const started = Date.now();
  const deadline = Date.now() + 200_000;
  const tail = path.basename(drop.scenarioImagePath);
  while (Date.now() < deadline) {
    const list = await api<{ items: EventRow[] }>(
      harness,
      session,
      `/api/events?limit=50&camera_id=${encodeURIComponent(drop.cameraId)}`
    );
    for (const row of list.items) {
      const dets = await detectionItems(session, row.id, '?limit=1');
      const first = dets.items[0];
      if (!first || !first.media_type) continue;
      if (!(first.file_path ?? '').endsWith(tail)) continue;
      const full = await mediaRead(session, `/api/detections/${first.id}/image?full=true`);
      if (full.status !== 200) continue; // the endpoint the app rides must answer
      dropEventId = row.id;
      dropDetection = {
        id: first.id,
        mediaType: first.media_type,
        sourceBytes: Buffer.from(await full.arrayBuffer()),
      };
      break;
    }
    if (dropDetection) break;
    await sleep(5_000);
  }
  if (!dropDetection) {
    throw new Error(
      `golden fixture: no event on camera ${drop.cameraId} carries a detection whose ` +
        `file_path ends with ${tail} inside 200 s — the drop neither landed nor deduped` +
        ' (a re-run inside the 300 s TTL after a purge is exactly this failure; space runs)'
    );
  }
  dropElapsedMs = Date.now() - started;

  // 3. Fixture-fact preconditions, asserted where they belong to the fixture
  //    (the shape harness.ts:1529-1541's requireFixture uses).
  const row = await eventRow(session, dropEventId);
  expect(row.detection_count, 'fixture: the selected event has exactly one detection').toBe(1);
  expect(
    row.detection_ids[0],
    'fixture: detection_ids[0] IS the file-backed detection the byte mirror aims at'
  ).toBe(dropDetection.id);
  expect(row.risk_score, 'fixture: the dropped event carries the book score').toBe(
    drop.scenario.verdict.risk_score
  );
  const diskBytes = readFileSync(drop.scenarioImagePath);
  if (!dropDetection.sourceBytes.equals(diskBytes)) {
    throw new Error(
      `golden fixture: full=true bytes (${dropDetection.sourceBytes.length} B) != the book ` +
        `image on disk (${diskBytes.length} B) — the supply drifted between drop and read; ` +
        'the legs below would still mirror a real byte identity, but of a moved target'
    );
  }
});

test.afterAll(async () => {
  // Hard delete, exactly this file's rows: the media-less probe row and THE ONE
  // drop event this file selected (the detection goes with it). Deliberately not
  // a camera sweep on car_in_driveway — a neighbour lane's row there stays
  // (event-reevaluate.spec.ts:141-146 keeps the same discipline).
  const session = await adminSession(harness);
  const mine = [dropEventId, medialessEventId].filter((id) => id);
  await hardDeleteRows(session, mine);
  await purgeProbeRows(session).catch(() => undefined); // belt: probe-camera residue
});

/* --------------------------------- boots ----------------------------------- */
/* quietBoot is the only door: a bare goto rides the nginx api bucket
 * (zone rate=10r/s at frontend/nginx.conf:24; the bucket's
 * `limit_req zone=api burst=20 nodelay` rides the /api location in the
 * generated config, frontend/docker-entrypoint.sh:166-168) and gets shed into setup-boot
 * coats; the harness's driveUntilBooted settles between drives (BOOT_QUIET_MS).
 * The modal then arrives through a SHIPPED door named in the header: the
 * ?event= deep link here; the card click in leg 4. */

async function bootWithModal(page: Page, cameraId: string, eventId: number): Promise<Session> {
  const session = await adminSession(harness);
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(
    page,
    harness,
    `/timeline?camera=${encodeURIComponent(cameraId)}&event=${eventId}`
  );
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await waitForEventCards(page);
  await expect(
    page.getByTestId('event-detail-modal'),
    'the ?event= door opens the modal (EventTimeline.tsx:329-334)'
  ).toBeVisible();
  // The camera filter is part of the door: the row behind it must BE the named
  // camera's (mirrors event-feedback.spec.ts:150's shape + this pin).
  const behind = await eventRow(session, eventId);
  expect(behind.camera_id, 'the row behind the door is on the camera the URL names').toBe(cameraId);
  return session;
}

/* ---------------------------------- legs ----------------------------------- */

test.describe('F-059 download media', () => {
  test('clicking Download Media downloads the first detection image byte-identical to the server read of the app’s own URL', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    test.info().skip(!drop.ready, drop.ready ? '' : drop.why);
    if (!h.ready || !drop.ready) return;
    test.setTimeout(180_000);
    const session = await bootWithModal(page, drop.cameraId, dropEventId);

    // Server-side preconditions that make "no toast? a file!" a judgement:
    // the row has media, and its first detection is an IMAGE on this tier. Read
    // from the SAME endpoint the app calls (fetchEventDetections → /api/events/
    // {id}/detections, api.ts:2598, called :3324) BEFORE the click, so a
    // premise change names the branch instead of timing out. A 'video' answer
    // would mean the header's blocked clause moved — leg 2 pins that wire.
    const button = downloadButton(page);
    await expect(button, 'the modal footer carries the Download Media button').toBeVisible();
    await expect(button, 'the shipped label before any click').toHaveText('Download Media');
    const row = await eventRow(session, dropEventId);
    expect(row.detection_ids.length, 'the event has at least one detection').toBeGreaterThan(0);
    const stored = await detectionItems(session, dropEventId);
    expect(stored.items[0]?.media_type, 'the first detection is an image on this tier').toBe(
      'image'
    );
    expect(stored.items[0]?.id, 'items[0] is detection_ids[0] — the first, per api.ts:3321').toBe(
      row.detection_ids[0]
    );

    // Node's read of the exact URL the app will fetch (same-origin to Chromium,
    // ''+path at api.ts:880 + :3255-3257; Node rides the API origin). The
    // mirror compares ACROSS instruments — Chromium's download channel vs this
    // fetch — each pinned against the dropped file.
    const serverRead = await mediaRead(
      session,
      `/api/detections/${dropDetection.id}/image?full=true`
    );
    expect(serverRead.status, 'the endpoint the app fetches answers Node-side').toBe(200);
    const serverBytes = Buffer.from(await serverRead.arrayBuffer());
    expect(
      sha256(serverBytes),
      'the server read matches the dropped scenario file BYTE-FOR-BYTE'
    ).toBe(sha256(dropDetection.sourceBytes));

    // THE CLICK. Toast listener armed first (sonner, the sibling idiom), then
    // the download event, then the button — both ends of the shipped report.
    const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Media download started' });
    const landed = await clickAndCatchDownload(page, button);

    // The NAME the app chose: no Content-Disposition ships on this route
    // (detections.py:1111-1133 sends only Cache-Control), so api.ts:3348's
    // default stands — a wrong FILE also fails the name, and vice versa.
    expect(landed.filename, 'the app suggests its own default media name for THIS row').toBe(
      `event_${dropEventId}_media.jpg`
    );
    expect(landed.bytes.length, 'the download matches the server read in LENGTH').toBe(
      serverBytes.length
    );
    expect(landed.bytes.length, 'the length is the dropped scenario file’s length').toBe(
      dropDetection.sourceBytes.length
    );
    expect(landed.bytes.equals(serverBytes), 'the download is the server read BYTE-FOR-BYTE').toBe(
      true
    );
    expect(landed.bytes.equals(dropDetection.sourceBytes), 'what landed is the dropped file').toBe(
      true
    );

    // The success report and the isDownloading reset — the label returning is
    // EventDetailModal.tsx:304's finally, observable only once the awaited
    // chain settled.
    await expect(toast, 'the success toast is the shipped copy').toBeVisible();
    await expect(button, 'the button exits its downloading state').toHaveText('Download Media');
    await expect(button).toBeEnabled();
    console.log(
      `[F-059] drop→detection landed in ${Math.round(dropElapsedMs / 1000)} s ` +
        `(event ${dropEventId}, detection ${dropDetection.id}, ${landed.bytes.length} bytes)`
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * THE FIXME'S WITNESS, NOT THE ROW'S COVERAGE. This leg proves NO video
   * downloads — the fixme below holds that clause. What this leg executes is the
   * two measured facts that make the clause unreachable on this tier, so the
   * fixme is evidence and not a guess, plus the tripwire that tells whoever
   * changes the supply that a real leg is now owed:
   *   1. No detection this supply produced is a video — the premise of
   *      "unreachable". If a future book ships one, this reddens and the clause
   *      gets its real leg; until then no reader can mistake this for one.
   *   2. GET /api/detections/{id}/video answers on THIS stack with the
   *      transcoding-dependency 500 (header: read-only image root,
   *      transcoding_service.py:277-297) — NOT a 404, which proves the URL the
   *      video branch builds (api.ts:3269-3271) is a real route; and NOT the
   *      handler's own 400 detail (detections.py:1432-1435), whose ABSENCE is
   *      asserted here so the layer that answered is named. If this stack ever
   *      gains a writable working dir, the 500 flips to that 400 and this leg
   *      goes red in a way that points exactly at the flip.
   * WHAT THIS LEG DOES NOT DO, stated so it cannot be misread as a green for the
   * row's "or video": it opens no page and clicks nothing — there is nothing to
   * click that could make a video exist — so it exercises no shipped client code,
   * and deleting downloadEventMedia's video branch (api.ts:3332-3334) would leave
   * every assert below still green. The client's media-type branch is pinned only
   * on its IMAGE side, by legs 1 and 4: with `isVideo` inverted or the two URL
   * builders swapped, the click would fetch the video route, the 500 above would
   * reach api.ts:3343-3344 and no download would land — legs 1 and 4 die. The
   * branch's video side is the fixme's, and this file claims nothing for it.
   */
  test.fixme("F-296 the first detection's VIDEO downloads (the row's second disjunct) — UNPROVEN on this tier", async ({
    page,
  }) => {
    // Written, NOT executed; shows as "skipped" in the feature-check `golden
    // paths:` dict. Why it cannot run is measured by the leg above and stated in
    // this file's header. WHAT MAKES IT GREEN: a scenario book entry whose
    // detection is a video (book + fake-VLM writer: detector_client.py:1281),
    // after which this leg boots the modal, clicks Download Media, and asserts
    // the landed bytes equal a Node read of
    // `/api/detections/${detectionId}/video` and that the suggested name ends
    // `_media.mp4` (api.ts:3348's video arm) — the same mirror shape as leg 1.
    if (!drop.ready) return; // narrows `drop` for the type gate; fixme never runs.
    await bootWithModal(page, drop.cameraId, dropEventId);
    const landed = await clickAndCatchDownload(page, downloadButton(page));
    expect(landed.filename.endsWith('_media.mp4')).toBe(true);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the supply-witness for that fixme: no detection this drop produced is a video, and the clip route the video branch builds is live but answered by its transcoding dependency (500) before the handler 400 guard', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    test.info().skip(!drop.ready, drop.ready ? '' : drop.why);
    if (!h.ready || !drop.ready) return;
    test.setTimeout(90_000);
    const session = await adminSession(harness);
    expect(drop.scenario.detections.length, 'the claimed scenario declares one detection').toBe(1);
    const stored = await detectionItems(session, dropEventId);
    const types = new Set(stored.items.map((d) => d.media_type));
    expect(types, 'no detection this drop produced is a video').not.toContain('video');

    const refusal = await mediaRead(session, `/api/detections/${dropDetection.id}/video`);
    const body = (await refusal.json().catch(() => null)) as {
      detail?: string;
      error?: { code?: string; message?: string };
    } | null;
    expect(
      refusal.status,
      'the clip route answers 500 (its transcoding dependency cannot init on the read-only ' +
        'image root) — NOT 404, so the URL the video branch builds is a real route'
    ).toBe(500);
    expect(body?.error?.code, 'the 500 rides the app’s error envelope').toBe('INTERNAL_ERROR');
    expect(
      body?.error?.message ?? '',
      'the message names the read-only transcoding cache dir — the layer that answered'
    ).toContain("Read-only file system: 'data/transcoded_cache'");
    expect(
      body?.detail,
      'the handler’s 400 detail (detections.py:1435) never ran — the dependency answered first'
    ).toBeUndefined();
    // The page fixture exists to keep the file's guard contract uniform; this
    // leg navigates nothing (stated above), and closedByGuard still proves the
    // patch is armed.
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('an event with no detections downloads nothing and the app reports ITS OWN error sentence, while the server stays silent on the row', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);
    const session = await bootWithModal(page, probeCameraId, medialessEventId);

    const button = downloadButton(page);
    await expect(
      button,
      'the button rides EVERY modal — media or not (EventDetailModal.tsx:1313)'
    ).toBeVisible();
    const row = await eventRow(session, medialessEventId);
    expect(row.detection_ids, 'the row is media-less at the server').toEqual([]);

    // No download may fire. The probe runs the generous window so a WRONG file
    // (an empty one, say) is still caught; the click and the failure report go
    // first so sonner's auto-dismiss cannot race the toast assert.
    const probe = page
      .waitForEvent('download', { timeout: 20_000 })
      .then((d) => d.suggestedFilename())
      .catch(() => null);
    await button.click();

    // The failure VERBATIM from the client-side ApiError (api.ts:3317 via
    // EventTimeline.tsx:914) — not a generic "failed". The server never
    // produced this string; the app diagnosed its own empty detection_ids.
    await expect(
      page.locator('[data-sonner-toast]').filter({
        hasText: 'Event has no associated media to download',
      }),
      'the toast names the shipped no-media sentence'
    ).toBeVisible();
    // isDownloading resets on the REJECTED path too (the same finally,
    // EventDetailModal.tsx:303-305): the button is retryable, not bricked.
    await expect(button, 'the label returns after the failure too').toHaveText('Download Media');
    expect(await probe, 'no download event fired for a media-less event').toBeNull();

    // THE HONEST ASYMMETRY, pinned so nobody "mirrors" this leg against a server
    // 404 that does not exist: the row is a REAL row to GET /api/events/{id},
    // and what the server does answer for absent media is the media route's own
    // 404 — a different string, from a different layer, than the app's.
    expect(
      (await eventRow(session, medialessEventId)).id,
      'the row is real to the events route'
    ).toBe(medialessEventId);
    const phantom = await mediaRead(session, '/api/detections/999999999/image?full=true');
    expect(phantom.status, 'the media route 404s a detection id that does not exist').toBe(404);
    const phantomBody = (await phantom.json().catch(() => null)) as { detail?: string } | null;
    expect(
      phantomBody?.detail ?? '',
      'the server detail is NOT the app’s sentence (the toast above is client-authored)'
    ).not.toBe('Event has no associated media to download');
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the card door: clicking the drop row’s card opens ITS modal (camera + risk mirror the server row) and Download from that modal lands the same bytes', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    test.info().skip(!drop.ready, drop.ready ? '' : drop.why);
    if (!h.ready || !drop.ready) return;
    test.setTimeout(180_000);
    // The row's words are "clicks Download Media" ON /timeline — the door a user
    // actually walks: card click → modal → footer button. The ?event= variant is
    // leg 1's door; F-054 owns "the modal opens" itself; what THIS leg adds is
    // that the download chain works identically whichever shipped door opened
    // the modal, and that the modal which opened provably belongs to the card
    // clicked (chip + risk mirrors, then the id the download name carries).
    const session = await adminSession(harness);
    await seedTourDismissed(page);
    await seedDefaultViewMode(page);
    await loginAsAdmin(page, harness);
    await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(drop.cameraId)}`);
    await expect(page.getByTestId('timeline-page')).toBeVisible();
    await waitForEventCards(page);

    const card = page.getByTestId(`event-card-${dropEventId}`);
    await expect(card, 'the drop row renders a card on the filtered timeline').toBeVisible();
    // (56,56): the 80×80 THUMBNAIL cell's centre — the card's p-4 padding puts
    // the h-20 w-20 thumbnail at x[16..96],y[16..96] (EventCard.tsx:399,406,409),
    // an img/Eye div that is neither button nor link, so the interactive guard at
    // :358-366 does NOT swallow the click. The corner (8,8) is NOT free: the
    // timeline's desktop grid overlays EVERY card with a 32×32 selection button at
    // `absolute left-2 top-2 z-10` (EventTimeline.tsx:1775-1786, h-8 w-8 ⇒ the box
    // spans x[8..40],y[8..40]) — run 2 measured Playwright's actionability log
    // naming `<button aria-label="Select event …"> … intercepts pointer events`
    // against (8,8). 56 is clear below-right of that box and above the action row.
    await card.click({ position: { x: 56, y: 56 } });
    const panel = page.getByTestId('event-detail-modal');
    // The setter this door actually reaches is the GRID card's own
    // handleEventCardClick (EventTimeline.tsx:751-753, spread via :790 into the
    // card instances at :1793/:1862) — NOT the live-activity rail's inline
    // onEventClick at :1104, which is a different door this leg does not walk.
    await expect(
      panel,
      'the card door opened a modal (EventTimeline.tsx:751-753 via getEventCardProps :790)'
    ).toBeVisible();

    // DOM↔Node agreement on WHICH row's modal this is, before the download:
    // camera chip name and risk value, both mirrored from the server row.
    const truth = await eventRow(session, dropEventId);
    const cameras = await api<CameraRow[] | { items: CameraRow[] }>(
      harness,
      session,
      '/api/cameras'
    );
    const list = Array.isArray(cameras) ? cameras : cameras.items;
    const cameraName = list.find((c) => c.id === truth.camera_id)?.name ?? '';
    expect(cameraName, 'the camera list resolves the row’s camera name').toBe(drop.scenario.name);
    await expect(
      panel.getByTestId('detection-camera'),
      'the modal names the camera of the row whose card was clicked'
    ).toHaveText(cameraName);
    await expect(panel.getByTestId('risk-score')).toContainText(String(truth.risk_score));

    const landed = await clickAndCatchDownload(page, downloadButton(page));
    expect(landed.filename, 'the download name carries the clicked row’s id').toBe(
      `event_${dropEventId}_media.jpg`
    );
    const serverRead = await mediaRead(
      session,
      `/api/detections/${dropDetection.id}/image?full=true`
    );
    const serverBytes = Buffer.from(await serverRead.arrayBuffer());
    expect(landed.bytes.length, 'same LENGTH as the Node read').toBe(serverBytes.length);
    expect(landed.bytes.equals(serverBytes), 'byte-identical to the Node read').toBe(true);
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'Media download started' }),
      'the success toast rides the card door too'
    ).toBeVisible();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the first detection is ONE anchor: detection_ids[0] is the row whose bytes legs 1/4 mirrored and whose id the download name carried, and the ordering knob is LIVE (not ignored) on this event', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    test.info().skip(!drop.ready, drop.ready ? '' : drop.why);
    if (!h.ready || !drop.ready) return;
    test.setTimeout(90_000);
    // WHAT THIS LEG CAN AND CANNOT PROVE, stated before its asserts because the
    // count decides it. The event has exactly ONE detection (asserted two lines
    // below), so WHICH row the ordering knob picks is NOT testable here: with one
    // row, `?order_detections_by=created_at` selects that row for any ORDER BY the
    // backend ships, including one that was deleted — an id-vs-id compare across
    // the two orderings would be green on a broken knob and must not be written as
    // if it were a pin (the review measured exactly this vacuity). What IS
    // non-trivially red-able at count 1 is that the knob is LIVE: it routes to a
    // DIFFERENT query branch (events.py:2241-2249 joins the event_detections
    // junction and orders by EventDetection.created_at; the default branch
    // :2292-2299 orders Detection.detected_at) and that branch surfaces the
    // junction column as association_created_at, which the default branch leaves
    // null (schema: schemas/detections.py:228-232). Measured on this stack: the
    // default read answers null for this row, the created_at read answers a
    // timestamp. So a knob that was ignored, or whose junction branch stopped
    // reading the junction, reddens THIS leg — while the ordering CLAIM ("which
    // row is first when there are two") is held by the fixme below.
    const session = await adminSession(harness);
    const row = await eventRow(session, dropEventId);
    expect(row.detection_count, 'the event holds exactly one detection').toBe(1);
    const detectedAt = await detectionItems(session, dropEventId, '?limit=1');
    expect(
      detectedAt.items[0]?.id,
      'items[0] (limit=1, default order) is the id the app names detection_ids[0]'
    ).toBe(row.detection_ids[0]);
    const createdAt = await detectionItems(
      session,
      dropEventId,
      '?limit=1&order_detections_by=created_at'
    );
    expect(createdAt.items[0]?.id, 'the knob read still returns exactly one row').toBe(
      detectedAt.items[0]?.id
    );
    // THE LIVE-KNOB PAIR — the two asserts that carry this leg. Both are
    // observable at one detection, and each is false if the knob stops
    // reaching its own branch.
    expect(
      detectedAt.items[0]?.association_created_at ?? null,
      'the DEFAULT ordering does not populate the junction timestamp (events.py:2292-2299 branch)'
    ).toBeNull();
    expect(
      createdAt.items[0]?.association_created_at ?? null,
      'the created_at ordering DOES populate the junction timestamp, so the knob routes to its own branch (events.py:2241-2249)'
    ).not.toBeNull();
    // The knob is validated, not free-form: an out-of-set value is refused by the
    // shipped route rather than silently falling back to the default
    // (events.py:2170's VALID_DETECTION_ORDER_BY, the 400 at :2214-2219). A
    // fallback-instead-of-400 would let a typo'd client param mean "default"
    // forever; this pins that it does not.
    const bogus = await mediaRead(
      session,
      `/api/events/${dropEventId}/detections?limit=1&order_detections_by=not_a_column`
    );
    expect(bogus.status, 'an ordering outside the shipped set is a 400, not a silent default').toBe(
      400
    );
    // The anchor the row clause actually rests on: the id the app calls "first"
    // is the id whose bytes legs 1 and 4 mirrored and whose id the download name
    // carried. Reddening it: an association order that put a different detection
    // first, or a mirror aimed at another row.
    expect(
      row.detection_ids[0],
      'the anchored first detection is the one the downloads mirrored'
    ).toBe(dropDetection.id);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /* --------------------------------- fixme ---------------------------------- */
  /* The clause this tier has no honest data source for, held on the record as
   * `test.fixme` (the shape event-reevaluate.spec.ts:259/:329 established for
   * F-061/F-062, and what the inventory's F-057 read-back leg does too): a
   * skipped leg is a claim of NOT-YET-PROVEN, where a passing leg would be a
   * false one. It shows as "skipped" in the feature-check `golden paths:` dict,
   * which is the UR-128 witness — so the suite never reads as proving the
   * multi-detection ordering or a video download it has not executed. */

  /**
   * THE UNPROVEN HALF OF "THE FIRST DETECTION". With ONE detection per event,
   * detection_ids[0] and items[0] cannot disagree, so the ordering claim is
   * vacuous — and the review measured that no red is possible for it here. This
   * leg is what the claim needs: an event with TWO detections whose
   * detected_at and event_detections.created_at DISAGREE about which is first.
   *
   * WHY IT CANNOT RUN ON THIS TIER (both halves measured, not assumed):
   *   1. SANCTIONED SUPPLY MAKES ONE DETECTION PER DROP — by scenario, not by
   *      declaration count. The book's five r287-era scenarios each carried
   *      detections:[one] ([F4.4] added f4.4-gold-high with TWO person
   *      detections and f4.4-gold-rejected with one — but a drop still writes
   *      ONE EVENT; the fake VLM writes exactly the detections the matched
   *      scenario declares (detector_client.py:1281 is the Detection writer),
   *      all attached to that single event). The claim here needs one EVENT
   *      whose detected_at disagrees with a junction created_at ACROSS two of
   *      its detections; a multi-detection scenario like f4.4-gold-high writes
   *      both its rows from the same verdict session (created_at within one
   *      transaction), so detected_at-vs-created_at ordering stays coherent —
   *      the mismatch this leg needs has no scenario. Two drops to one camera
   *      folder make TWO EVENTS, not one
   *      event with two detections — the watcher keys events per file.
   *   2. THERE IS NO CLIENT-CALLED WRITE THAT ATTACHES A SECOND DETECTION. The
   *      app's own detection reads are GET-only (api.ts:2598 fetchEventDetections;
   *      api.ts has no POST/PATCH that attaches a detection to an event), and the
   *      detection route's only POST/PATCH/DELETE are not affordances the shipped
   *      UI calls, so exercising them would be inventing server behaviour — the
   *      thing this file's contract forbids. Bulk rows carry ZERO detections
   *      (events.py's bulk path builds no Detection), and direct DDL is out of
   *      bounds for the same reason the header gives for not purging a shared
   *      camera.
   *
   * WHAT MAKES IT GREEN: a supply path the app itself drives that lands two
   * detections on one event with disagreeing timestamps — i.e. either a scenario
   * book entry declaring detections:[two] (backend ships the shape; the fake VLM
   * would then write both), or a sanctioned fixture hook that inserts a second
   * event_detections row. THEN this leg asserts that clicking Download Media
   * fetches the image whose id is detection_ids[0] (api.ts:3321) and NOT
   * items[0] of the default ordering when those two disagree — which is precisely
   * the seam a ≥2 event could break, and the reason this belongs on the record.
   */
  test.fixme('F-296 with two detections whose two orderings disagree, Download takes detection_ids[0]', async ({
    page,
  }) => {
    // Never executed on this tier — see the docblock's two measured reasons.
    // The click itself is legs 1/4's; the NEW assertion is the byte target's
    // identity, and it is written here so the shape exists for whoever lands
    // the supply.
    if (!drop.ready) return; // narrows `drop` for the type gate; fixme never runs.
    await bootWithModal(page, drop.cameraId, dropEventId);
    const landed = await clickAndCatchDownload(page, downloadButton(page));
    expect(landed.filename).toBe(`event_${dropEventId}_media.jpg`);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
