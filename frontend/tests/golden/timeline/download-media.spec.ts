/**
 * FE-3 golden path (F2.3): F-059 — Event detail › Download Media on /timeline.
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md:195):
 *   F-059 "clicks Download Media; the first detection's image or video downloads"
 *
 * THE SHIPPED CHAIN, CLAIM BY CLAIM — every claim cites the file:line read at
 * this head, and a leg asserts the behaviour those lines promise:
 *   - How the modal opens at all (both doors here are the app's own): the URL
 *     door — selectedEventForModal starts null (EventTimeline.tsx:147) and the
 *     ?event= effect sets it (EventTimeline.tsx:360-366); and the CARD door —
 *     leg 4 clicks an EventCard instance spread from getEventCardProps, which is
 *     the only way a grid card gets a click handler: getEventCardProps carries
 *     onClick: handleEventCardClick (:934) → setSelectedEventForModal (:900-902).
 *     The card instance leg 4 aims at is the DEFAULT grid's (:2043) — viewMode
 *     and groupBy both ship as 'grid'/'time' (:115, :124), which is the branch
 *     that condition leaves open — with :1974 as the same-shaped card in
 *     the groupBy=camera/risk branch this file never selects.
 *     The card's own click fires it unless the point clicked is inside a button
 *     or link (EventCard.tsx:358-366, wired to the card div at :390; testid
 *     event-card-{id} at :388). A THIRD door, the live-activity rail, has its own
 *     inline onEventClick at :1873 — a DIFFERENT line from the grid card's setter,
 *     and leg 4 does NOT ride it (it clicks a grid CARD, so the setter it reaches
 *     is :902, not :1873). A bare /timeline with neither of leg 1/4's doors opens
 *     NOTHING — this file never claims a modal it did not open through a shipped
 *     door, and names the right shipped line for whichever door a leg rides.
 *   - The button. `onDownloadMedia &&` guards it (EventDetailModal.tsx:1257-1266):
 *     aria-label="Download media" (:1262), label 'Download Media' ↔ 'Downloading...'
 *     while in flight (:1265), disabled={isDownloading} (:1260). It has NO
 *     data-testid — the aria-label is the shipped handle; the two OTHER Download
 *     affordances on /timeline name themselves differently ("Download video
 *     clip", EventCard.tsx:661; "Download clip", EventVideoPlayer.tsx:280), so
 *     the role locator cannot double-match. EventTimeline.tsx:2092 always passes
 *     onDownloadMedia={handleDownloadMedia}, so the button rides EVERY modal.
 *   - The click. The modal's handler sets isDownloading, awaits
 *     onDownloadMedia(event.id), and resets in `finally` (EventDetailModal.tsx:279-291,
 *     reset at :290) — so "the label came back" is an observable of the awaited
 *     chain settling, on the success path AND the rejected one.
 *   - The service. downloadEventMedia (api.ts:3242-3306): fetchEvent (api.ts:2250)
 *     → `event.detection_ids ?? []` (:3247) → EMPTY throws `new ApiError(404,
 *     'Event has no associated media to download')` CLIENT-side (:3249-3251; the
 *     server never answers 404 for a media-less event's GET — this string is the
 *     app's own diagnosis, and ApiError's message is its 2nd ctor arg,
 *     api.ts:619-635). Non-empty: detectionId = detection_ids[0] (:3254 — the
 *     row's "first detection"), then fetchEventDetections(eventId,{limit:1})
 *     (api.ts:2576, called :3257) supplies media_type and `items?.[0]` (:3259).
 *     media_type 'video' → /api/detections/{id}/video (api.ts:3202-3204); else
 *     `/api/detections/{id}/image?full=true` (api.ts:3188-3190, called :3268).
 *     BASE_URL is '' (api.ts:853): the media fetch is SAME-ORIGIN, a real
 *     network request through the UI's nginx — not a mock, not a memory blob.
 *   - The byte source. full=true reads the source file raw and returns
 *     Response(content=image_data, media_type="image/jpeg") with NO
 *     Content-Disposition (detections.py:1457-1467 sends only Cache-Control),
 *     so the client's generated name stands: api.ts:3282-3288's regex override
 *     needs the header; the default is `event_${eventId}_media.jpg` (:3281
 *     image arm; the video arm is `event_${eventId}_media.mp4`). What downloads
 *     therefore has exactly the dropped scenario file's bytes, length and name.
 *   - The delivery. blob → createObjectURL → a.download = filename → click →
 *     remove → revoke (api.ts:3290-3299) = the browser download event
 *     Playwright catches with waitForEvent('download'), armed BEFORE the click
 *     (repo precedent e2e/specs/event-export.spec.ts:482; golden precedent
 *     identity/zones.spec.ts:499-521).
 *   - The report. EventTimeline.tsx:1036-1050: success → toastSuccess('Media
 *     download started') (:1041); failure → toastError(err.message) (:1044),
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
 * THE TWO CLAUSES THE OLD HEAD COULD NOT EXECUTE, AND HOW [r323b] (ruling 323
 * item 6) SUPPLIED BOTH: the tier used to hold each clause as a `test.fixme`
 * (the sibling precedent, event-reevaluate.spec.ts:259/:329 for F-061/F-062) —
 * a skipped leg is a claim of NOT-YET-PROVEN — with a witness leg beside it
 * MEASURING why it could not pass. [r323b] added the two supplies the clauses
 * needed and both legs RUN now; the supply docblocks sit at the videoDrop
 * constant (the clip) and the ordering fixture (the crossed detections), and
 * the reworked witness leg stands beside the video leg as the supply's own
 * proof. The suite's shape is SEVEN running legs; the report says so in the
 * same words this header uses.
 *   - THE ROW'S "OR VIDEO" DISJUNCT, NOW SUPPLIED. The book dir carries
 *     r323b-video-clip.mp4 (5 s H.264/yuv420p, backend/ai_contract/fake/
 *     scenario_fixtures/, COMMITTED — the first CI head shipped it as a
 *     local-only 8 KB file behind .gitignore's *.mp4 rule, so CI's checkout
 *     had no clip and both video legs skipped; .gitignore now negates this
 *     one path), and its drop rides the watcher's video branch end
 *     to end: is_video_file (.mp4, file_watcher.py:93) → the queue worker's
 *     video branch extracts frames (measured EXACTLY 1 frame through the
 *     shipped ffmpeg command — the probe, not the formula, is the authority)
 *     → the fake detector's literal script answers 3 detections for the frame
 *     → every one lands media_type="video" (detector_client.py:1176-1182).
 *     Two compose tmpfs mounts (docker-compose.ci.yml) made the tier able to
 *     run that pipeline AND serve the route: the transcoding cache dir the
 *     request-scoped dependency mkdirs (transcoding_service.py:277-297) and
 *     /app/data/thumbnails, where the frame extractor writes its
 *     {video_stem}_frames/ subdirs (video_processor.py:719-721) that a
 *     read-only rootfs cannot hold. get_or_transcode short-circuits an
 *     already-browser-compatible .mp4 (is_transcoding_needed is
 *     extension-only, transcoding_service.py:353-375), so the streamed bytes
 *     are the dropped file's own. The video leg (leg 2) boots the modal on the
 *     clip's event, clicks Download Media, and mirrors the bytes against a
 *     Node read of /api/detections/{id}/video and the clip file itself. The
 *     route's handler-side 400 guard for a NON-video id
 *     (detections.py:1593-1597, detail :1596 "Detection {id} is not a video
 *     (media_type: ...)") is pinned from the other side by the witness leg —
 *     the scenario drop's IMAGE detection refused with that detail.
 *   - "FIRST" WITH MORE THAN ONE DETECTION, NOW SUPPLIED. The ordering
 *     fixture bulk-creates TWO detections with crossed detected_at values
 *     (POST /api/detections/bulk takes detected_at verbatim,
 *     detections.py:1857-1900; DetectionBulkCreateItem carries no media_type,
 *     so both rows are media_type "image" via the column default,
 *     models/detection.py:57) and one event whose junction rows are written
 *     in the request's list order (POST /api/events/bulk,
 *     events.py:1748-1779). The result: detection_ids[0] is the LATER-detected
 *     row while the DEFAULT ordering (Detection.detected_at asc,
 *     events.py:2656) puts the EARLIER one first — the two candidate "firsts"
 *     genuinely disagree, and the client fetches the URL from
 *     detection_ids[0] (api.ts:3254) while reading media_type from the
 *     default-ordered items[0] (api.ts:3257-3265). The ordering leg asserts
 *     the BYTES: what downloads is detection_ids[0]'s image, NOT the
 *     default-ordered first row's (the fixture's byte mirrors, read through
 *     the same full=true route, are asserted distinct in beforeAll so a
 *     fixture drift cannot make the pin vacuous). The junction order is
 *     OBSERVED, not promised by a schema order_by (models/event.py:181-187),
 *     so the fixture re-reads all three orderings as precondition pins and
 *     fails loudly if the disagreement did not hold.
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

/** The video supply [r323b] added (ruling 323 item 6): the book dir carries a
 *  tiny H.264/yuv420p MP4 (r323b-video-clip.mp4, 5 seconds at 128×96, encoded
 *  by the same ffmpeg the backend image ships — backend/Dockerfile:73), so a
 *  drop of it rides the watcher's video branch end to end: is_video_file
 *  (.mp4, file_watcher.py:93) → is_valid_video (1KB floor, :306/:329-330) → the queue
 *  worker's video branch extracts frames at the shipped 4 s interval
 *  (config.py:1975). The formula (video_processor.py:708) would compute 2
 *  frames for a 5 s clip, but the CI image's ffmpeg command measured EXACTLY 1
 *  frame — the probe is the authority, not the formula. The fake detector's
 *  literal script answers 3 detections for that frame (generators.py:402 — an
 *  ffmpeg-generated frame matches no book digest, so the literal path runs)
 *  and every one lands media_type="video" (detector_client.py:1176-1182 —
 *  video_path is non-None for the whole call). The route that serves it no
 *  longer 500s on CI: docker-compose.ci.yml mounts tmpfs at the transcoding
 *  cache dir the dependency constructor mkdirs AND at /app/data/thumbnails,
 *  where the frame extractor writes {video_stem}_frames/ subdirs
 *  (video_processor.py:719-721) that a read-only rootfs cannot hold; and
 *  get_or_transcode short-circuits an already-browser-compatible .mp4 anyway
 *  (is_transcoding_needed is extension-only, transcoding_service.py:371-375),
 *  so the streamed bytes are the dropped file's own. */
const VIDEO_CLIP_NAME = 'r323b-video-clip.mp4';
const VIDEO_CAMERA_NAME = 'r323b-video-probe';
const VIDEO_CAMERA_FOLDER = '/cameras/r323b_video_probe';

interface VideoHarness {
  ready: true;
  /** Absolute host path of the book-dir clip — the byte mirror's local side. */
  clipPath: string;
  /** Absolute container path the drop helper reports (its print) — asserted
   *  against the detection's file_path basename, not reused verbatim. */
  clipTail: string;
}

function readVideoHarness(): VideoHarness | { ready: false; why: string } {
  const bookPath = process.env.FEATURE_CHECK_SCENARIOS;
  if (!bookPath) return { ready: false, why: 'missing FEATURE_CHECK_SCENARIOS' };
  const clipPath = path.join(path.dirname(bookPath), VIDEO_CLIP_NAME);
  if (!existsSync(clipPath)) return { ready: false, why: `no video clip at ${clipPath}` };
  return { ready: true, clipPath, clipTail: VIDEO_CLIP_NAME };
}

const videoDrop = readVideoHarness();

/** The drop helper runs ON THE HOST (feature_check.py's `drop` subcommand
 *  requires FEATURE_CHECK_CAMERA_ROOT — :4499-4511): this env var is the host
 *  run_dir the helper copies into, so the video arm and the ordering arm both
 *  gate on it rather than ever defaulting. A '/cameras' fallback here would be
 *  a path inside the container — useless to a host-side exec. */
const cameraRootEnv = process.env.FEATURE_CHECK_CAMERA_ROOT;

/** The second-image supply the ordering leg rides: TWO book scenario images
 *  dropped on the probe camera put two byte-distinct files under the watched
 *  folder, and the ordering fixture bulk-creates detections whose file_path
 *  point at THOSE stored files (deterministic container paths — the drop
 *  helper copies to `{root}/{camera}/{name}`, feature_check.py:4252-4265), so
 *  the full=true reads the legs mirror are real bytes of two different
 *  images. The drops' own events are a side effect this file purges; only the
 *  FILES matter to the supply. */
const ORDER_IMAGE_A = 'cat-on-porch.jpg';
const ORDER_IMAGE_B = 'person-at-door.jpg';

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
  /** Populated ONLY by the created_at ordering branch (schemas/detections.py:228; the route's junction query events.py:2602-2608). The default
   *  branch leaves it null, which is what makes the knob's effect observable
   *  even at one detection — leg 5's live-knob pair rides exactly this. */
  association_created_at?: string | null;
}

interface CameraRow {
  id: string;
  name: string;
}

/** The bulk routes' verdict shape — re-declared because harness.ts's own
 *  BulkResult/BulkBody (:1549-1560) are module-private. `error` is None on a
 *  success item and a string on a failure (detections.py:1889-1896 /
 *  events.py:2030-2037), hence `string | null`. */
interface BulkResultShape {
  succeeded: number;
  results: { status: string; id: number | null; error?: string | null }[];
}

const eventRow = (session: Session, id: number) =>
  api<EventRow>(harness, session, `/api/events/${id}`);
const detectionItems = (session: Session, id: number, query = '?limit=10') =>
  api<{ items: DetectionItem[] }>(harness, session, `/api/events/${id}/detections${query}`);

/** A route read with no status gate and no body parsing — the shape the byte
 *  mirror and the negative-status probes need (the harness's `api()` THROWS on
 *  non-200, harness.ts:114-123, so it cannot witness a 400 or a 500). Media
 *  routes are auth-exempt in prose (api.ts:3196-3197 comment); the cookie rides
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
        'the negative leg needs the client-side empty-ids branch (api.ts:3247-3251)'
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
/* --- the [r323b] supplies --- */
let videoProbeCameraId = '';
let videoEventId = 0;
let videoDetection: { id: number; fileBytes: Buffer } | null = null;
/** The ordering fixture: one event whose two detections make the two shipped
 *  orderings disagree. first = the row detection_ids[0] names (junction join
 *  order, the id the download URL rides); second = the row the DEFAULT
 *  detected_at ordering puts first. Both carry their own byte mirror. */
let orderEventId = 0;
let orderFirst: { id: number; sourceBytes: Buffer } | null = null;
let orderSecond: { id: number; sourceBytes: Buffer } | null = null;

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

  // ---- [r323b] video supply: the clip drop, polled to a video detection ----
  // Independent of the scenario drop below (its skips gate only its own legs);
  // it needs the book dir (for the clip bytes) and a watched folder.
  if (videoDrop.ready && cameraRootEnv) {
    test.setTimeout(600_000); // two pipelines (video + images) inside one hook
    // The clip's camera, in ensureCamera's idiom (the id is the name's fold;
    // the 409 arm re-reads and confirms — the same measured shape as above).
    const videoListed = await api<CameraRow[] | { items: CameraRow[] }>(
      harness,
      session,
      '/api/cameras'
    );
    const videoRows = Array.isArray(videoListed) ? videoListed : videoListed.items;
    const knownVideo = videoRows.find((row) => row.name === VIDEO_CAMERA_NAME);
    if (knownVideo) videoProbeCameraId = knownVideo.id;
    else {
      try {
        const created = await apiWrite<{ id: string }>(harness, session, 'POST', '/api/cameras', {
          name: VIDEO_CAMERA_NAME,
          folder_path: VIDEO_CAMERA_FOLDER,
        });
        videoProbeCameraId = created.id;
      } catch (error) {
        if (!String(error).includes('409')) throw error;
        const again = await api<CameraRow[] | { items: CameraRow[] }>(
          harness,
          session,
          '/api/cameras'
        );
        const found = (Array.isArray(again) ? again : again.items).find(
          (row) => row.name === VIDEO_CAMERA_NAME
        );
        if (!found) throw error;
        videoProbeCameraId = found.id;
      }
    }
    // Purge this camera's own rows so the poll below can only match a detection
    // that came from a clip drop. (A re-run inside the watcher's 300 s content
    // TTL after a purge still drops one event short — the same space-runs
    // discipline the scenario drop's error names.)
    const staleVideo = await api<{ items: { id: number }[] }>(
      harness,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(videoProbeCameraId)}`
    );
    await hardDeleteRows(
      session,
      staleVideo.items.map((row) => row.id)
    );

    execFileSync(
      path.join(repoRoot, 'scripts/feature-check.sh'),
      ['drop', videoDrop.clipPath, 'r323b_video_probe'],
      {
        cwd: repoRoot,
        env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: cameraRootEnv },
        encoding: 'utf8',
        timeout: 30_000,
      }
    );

    // Poll for the clip's event like the scenario drop's mirror: the event on
    // this camera whose first detection is a VIDEO whose file_path ends with
    // the clip's name. The watcher's video branch shares one file_path across
    // the frame detections (detector_client.py:1179), so the tail match keys
    // the whole clip; the media_type read is the supply's own claim.
    const videoDeadline = Date.now() + 240_000;
    while (Date.now() < videoDeadline && !videoDetection) {
      const vlist = await api<{ items: EventRow[] }>(
        harness,
        session,
        `/api/events?limit=50&camera_id=${encodeURIComponent(videoProbeCameraId)}`
      );
      for (const vrow of vlist.items) {
        const vdets = await detectionItems(session, vrow.id, '?limit=1');
        const vfirst = vdets.items[0];
        if (!vfirst || vfirst.media_type !== 'video') continue;
        if (!(vfirst.file_path ?? '').endsWith(videoDrop.clipTail)) continue;
        videoEventId = vrow.id;
        videoDetection = { id: vfirst.id, fileBytes: readFileSync(videoDrop.clipPath) };
        break;
      }
      if (videoDetection) break;
      await sleep(5_000);
    }
    if (!videoDetection) {
      throw new Error(
        `golden fixture: no event on camera ${videoProbeCameraId} carries a VIDEO detection ` +
          `whose file_path ends with ${videoDrop.clipTail} inside 240 s — the video pipeline ` +
          '(ffmpeg frame extraction, or the fake detector on the frame) did not run'
      );
    }
  }

  // ---- [r323b] ordering supply: two images + a bulk event whose two
  // orderings disagree ----
  // Needs the probe camera's folder watched (it is — the same tree the scenario
  // drop rides); the drops' EVENTS are side effects the purge handles; what the
  // fixture keeps is the FILES at their deterministic container paths, which
  // the bulk-created detections below point at.
  if (h.ready && cameraRootEnv) {
    // The book dir — where the drop images and the clip live — is the
    // scenarios.json file's directory (FEATURE_CHECK_SCENARIOS points AT the
    // file; feature_check.py:3462). The existsSync filter below covers a
    // missing dir, so no ternary is needed here.
    const bookDir = path.dirname(process.env.FEATURE_CHECK_SCENARIOS ?? '');
    const orderImages = [ORDER_IMAGE_A, ORDER_IMAGE_B]
      .map((name) => path.join(bookDir, name))
      .filter((p) => existsSync(p));
    if (orderImages.length === 2) {
      for (const image of orderImages) {
        execFileSync(
          path.join(repoRoot, 'scripts/feature-check.sh'),
          ['drop', image, 'fe3_media_probe'],
          {
            cwd: repoRoot,
            env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: cameraRootEnv },
            encoding: 'utf8',
            timeout: 30_000,
          }
        );
      }
      // The drops need their FILES on disk only — synchronous copies through
      // the drop helper, visible in-container via the bind mount. The image
      // route the byte mirror below rides reads file_path FROM DISK inside the
      // container, so no pipeline wait is needed for these files to serve; the
      // drops' own events are side effects this file purges via
      // purgeProbeRows. The mirror asserts below carry the proof the files
      // serve: a detection route cannot be exercised until a detection
      // references them, and these bulk detections reference exactly them.
      // The two bulk detections, crossed: FIRST gets the LATER detected_at,
      // SECOND the earlier one — so the DEFAULT ordering (detected_at asc)
      // puts SECOND first while the junction join (detection_ids, ascending
      // id: bulk ids assign in request order) puts FIRST first. That is the
      // fixme's disagreement, made deterministic by the shipped bulk routes
      // (POST /api/detections/bulk takes detected_at verbatim,
      // detections.py:1858; POST /api/events/bulk writes the junction in list
      // order, events.py:1778-1779) — no schema extension, no DDL.
      const tEarly = new Date(Date.now() - 20 * 60_000).toISOString();
      const tLate = new Date(Date.now() - 5 * 60_000).toISOString();
      const orderDets = await apiWrite<BulkResultShape>(
        harness,
        session,
        'POST',
        '/api/detections/bulk',
        {
          detections: [
            {
              camera_id: probeCameraId,
              object_type: 'cat',
              confidence: 0.91,
              detected_at: tLate,
              file_path: `/cameras/fe3_media_probe/${ORDER_IMAGE_A}`,
              bbox_x: 20,
              bbox_y: 20,
              bbox_width: 120,
              bbox_height: 200,
            },
            {
              camera_id: probeCameraId,
              object_type: 'person',
              confidence: 0.93,
              detected_at: tEarly,
              file_path: `/cameras/fe3_media_probe/${ORDER_IMAGE_B}`,
              bbox_x: 40,
              bbox_y: 30,
              bbox_width: 110,
              bbox_height: 220,
            },
          ],
        }
      );
      const orderIds = orderDets.results.map((r) => r.id).filter((id): id is number => id !== null);
      if (orderDets.succeeded !== 2 || orderIds.length !== 2) {
        throw new Error(
          `golden fixture: ordering detections bulk succeeded ${orderDets.succeeded}/2 — ` +
            String(orderDets.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
        );
      }
      const orderBulk = await apiWrite<BulkResultShape>(
        harness,
        session,
        'POST',
        '/api/events/bulk',
        {
          events: [
            {
              batch_id: `fe3f296-${Date.now()}`, // events.batch_id is UNIQUE
              camera_id: probeCameraId,
              started_at: tEarly,
              risk_score: 61,
              risk_level: 'medium',
              summary: 'FE-3 F-296 ordering fixture: two orderings disagree',
              detection_ids: orderIds, // list order = junction insertion order
            },
          ],
        }
      );
      const orderEvent = orderBulk.results[0]?.id;
      if (orderBulk.succeeded !== 1 || orderEvent === null || orderEvent === undefined) {
        throw new Error(
          `golden fixture: ordering event bulk failed — ` +
            String(orderBulk.results[0]?.error).slice(0, 200)
        );
      }
      orderEventId = orderEvent;
      // THE ORDERING PINS — the fixture's own preconditions, read back through
      // the two shipped orderings so the leg below cannot ride a coincidence.
      // (1) The junction row order: GET /api/events/{id} reports detection_ids
      // in junction join order — order is OBSERVED, not promised by a schema
      // order_by (models/event.py:181-187), so pin it: the id the download
      // URL rides must be orderIds[0], the LATER detected_at.
      const orderedRow = await eventRow(session, orderEventId);
      if (orderedRow.detection_ids[0] !== orderIds[0]) {
        throw new Error(
          `golden fixture: junction detection_ids[0]=${orderedRow.detection_ids[0]} is not ` +
            `${orderIds[0]} — insertion order did not hold; the ordering leg's premise is void`
        );
      }
      // (2) The DEFAULT ordering (detected_at asc) puts the EARLIER row first
      // (orderIds[1] = D2/person), the reverse of the junction's pick.
      const defaultOrder = await detectionItems(session, orderEventId, '?limit=2');
      if (defaultOrder.items[0]?.id !== orderIds[1]) {
        throw new Error(
          `golden fixture: default ordering answered items[0]=${defaultOrder.items[0]?.id}, ` +
            `not orderIds[1]=${orderIds[1]} — detected_at asc did not put the earlier row first`
        );
      }
      // (3) The created_at ordering (the knob) puts the JUNCTION's first row
      // first: association-created order = junction insertion order because
      // EventDetection.created_at defaults per-row at flush
      // (models/event_detection.py:37/:79).
      const junctionOrder = await detectionItems(
        session,
        orderEventId,
        '?limit=2&order_detections_by=created_at'
      );
      if (junctionOrder.items[0]?.id !== orderIds[0]) {
        throw new Error(
          `golden fixture: created_at ordering answered items[0]=${junctionOrder.items[0]?.id}, ` +
            `not orderIds[0]=${orderIds[0]} — the junction order this leg rides did not hold`
        );
      }
      // Mirror both sides NOW: the bytes the full=true route serves for each
      // bulk detection, read from the route the app itself fetches.
      const a = await mediaRead(session, `/api/detections/${orderIds[0]}/image?full=true`);
      const b = await mediaRead(session, `/api/detections/${orderIds[1]}/image?full=true`);
      if (a.status !== 200 || b.status !== 200) {
        throw new Error(
          `golden fixture: the ordering detections' image routes answered ` +
            `${a.status}/${b.status} — the drop files are not where the fixture's ` +
            'file_path claims; the byte mirror would mirror nothing real'
        );
      }
      orderFirst = { id: orderIds[0], sourceBytes: Buffer.from(await a.arrayBuffer()) };
      orderSecond = { id: orderIds[1], sourceBytes: Buffer.from(await b.arrayBuffer()) };
      if (orderFirst.sourceBytes.equals(orderSecond.sourceBytes)) {
        throw new Error(
          'golden fixture: the two ordering detections mirror IDENTICAL bytes — ' +
            'the two orderings could not be told apart by what downloads'
        );
      }
    }
  }

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
  // Hard delete, exactly this file's rows: the media-less probe row, THE ONE
  // drop event this file selected (the detection goes with it), and the video
  // camera's rows — the clip's event(s) plus any watcher side events the two
  // ordering-image drops made on fe3_media_probe. Deliberately not a camera
  // sweep on car_in_driveway — a neighbour lane's row there stays
  // (event-reevaluate.spec.ts:141-146 keeps the same discipline).
  const session = await adminSession(harness);
  const mine = [dropEventId, medialessEventId].filter((id) => id);
  await hardDeleteRows(session, mine);
  await purgeProbeRows(session).catch(() => undefined); // belt: probe-camera residue
  // The video camera: every row it carries is this file's (the folder is
  // private to the clip drop). The purge unlinks the detection's file_path —
  // the camera-folder COPY of the clip, not the book original — and a later
  // run re-drops it past the 300 s TTL.
  if (videoProbeCameraId) {
    const staleVideo = await api<{ items: { id: number }[] }>(
      harness,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(videoProbeCameraId)}`
    );
    await hardDeleteRows(
      session,
      staleVideo.items.map((row) => row.id)
    );
  }
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
    'the ?event= door opens the modal (EventTimeline.tsx:360-366)'
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
    // {id}/detections, api.ts:2576, called :3257) BEFORE the click, so a
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
    expect(stored.items[0]?.id, 'items[0] is detection_ids[0] — the first, per api.ts:3254').toBe(
      row.detection_ids[0]
    );

    // Node's read of the exact URL the app will fetch (same-origin to Chromium,
    // ''+path at api.ts:853 + :3188-3190; Node rides the API origin). The
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
    // (detections.py:1457-1467 sends only Cache-Control), so api.ts:3281's
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
    // EventDetailModal.tsx:290's finally, observable only once the awaited
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
   * THE ROW'S "OR VIDEO" DISJUNCT, NOW RUNNING (ruling 323 item 6, F-296).
   * [r323b] supplied what the old fixme measured as missing: the book dir
   * carries r323b-video-clip.mp4, whose drop rides the watcher's video branch
   * end to end (the supply docblock at the videoDrop constant) and lands an
   * event whose first detection is a VIDEO. This leg boots the modal on that
   * event, clicks Download Media, and asserts the mirror: what lands in
   * Chromium's download channel equals, byte for byte, a Node read of
   * /api/detections/{id}/video — which equals the dropped clip's own bytes
   * (get_or_transcode short-circuits an already-browser-compatible .mp4, so
   * the route streams the source file untouched; transcoding_service.py:
   * 534-568 short-circuit, :353-375 extension check). The suggested name is
   * the app's own default `event_${eventId}_media.mp4` (api.ts's video arm of
   * the name builder) — no Content-Disposition ships on this route
   * (detections.py:1658-1687 sends Content-Length/Accept-Ranges/
   * Cache-Control only), so the default stands exactly as the image leg's
   * does. Reddening: serve a re-encoded or wrong-detection's bytes, put the
   * wrong id in the name, or stop the video branch from fetching — each flips
   * an equality, the same way leg 1's do.
   */
  test("F-296 the first detection's VIDEO downloads byte-identical to the server read of the app's own video route", async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    test.info().skip(!videoDrop.ready, videoDrop.ready ? '' : videoDrop.why);
    if (!h.ready || !videoDrop.ready || !videoEventId || !videoDetection) return;
    test.setTimeout(180_000);
    const session = await bootWithModal(page, videoProbeCameraId, videoEventId);

    // Server-side preconditions BEFORE the click, leg 1's shape: the row has
    // media, its first detection IS the video the fixture polled for, and
    // items[0] is detection_ids[0] — the id the client's branch will name.
    const button = downloadButton(page);
    await expect(button, 'the modal footer carries the Download Media button').toBeVisible();
    const row = await eventRow(session, videoEventId);
    expect(row.detection_ids.length, 'the video event has at least one detection').toBeGreaterThan(
      0
    );
    const stored = await detectionItems(session, videoEventId);
    expect(
      stored.items[0]?.media_type,
      'the first detection is the video the supply promised'
    ).toBe('video');
    expect(stored.items[0]?.id, 'items[0] is detection_ids[0] — the id the branch fetches').toBe(
      row.detection_ids[0]
    );
    expect(stored.items[0]?.id, 'items[0] is the detection the fixture polled').toBe(
      videoDetection.id
    );

    // Node's read of the exact URL the app will fetch, BEFORE the click. The
    // video route streams the .mp4 source untouched (get_or_transcode
    // short-circuits it), so the mirror is against the dropped clip itself.
    const serverRead = await mediaRead(session, `/api/detections/${videoDetection.id}/video`);
    expect(serverRead.status, 'the video route answers Node-side').toBe(200);
    const serverBytes = Buffer.from(await serverRead.arrayBuffer());
    expect(sha256(serverBytes), 'the server read is the dropped clip BYTE-FOR-BYTE').toBe(
      sha256(readFileSync(videoDrop.clipPath))
    );
    expect(serverBytes.length, 'the server read is the whole clip, not a truncated stream').toBe(
      readFileSync(videoDrop.clipPath).length
    );

    // THE CLICK, with the toast armed first (leg 1's idiom).
    const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Media download started' });
    const landed = await clickAndCatchDownload(page, button);

    // The NAME: the video arm's default (no Content-Disposition ships on this
    // route — detections.py:1658-1687).
    expect(landed.filename, 'the app suggests its own default video name for THIS row').toBe(
      `event_${videoEventId}_media.mp4`
    );
    expect(landed.bytes.length, 'the download matches the server read in LENGTH').toBe(
      serverBytes.length
    );
    expect(landed.bytes.equals(serverBytes), 'the download is the server read BYTE-FOR-BYTE').toBe(
      true
    );
    expect(
      landed.bytes.equals(readFileSync(videoDrop.clipPath)),
      'what landed is the dropped clip itself'
    ).toBe(true);

    await expect(toast, 'the success toast is the shipped copy').toBeVisible();
    await expect(button, 'the button exits its downloading state').toHaveText('Download Media');
    await expect(button).toBeEnabled();
    console.log(
      `[F-296] video download mirrored (event ${videoEventId}, detection ${videoDetection.id}, ` +
        `${landed.bytes.length} bytes)`
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  /**
   * THE SUPPLY WITNESS, REWORKED WITH THE LEG IT WITNESSED (ruling 323 item
   * 6: "the supply-witness leg at :768 changes with them"). The old witness
   * pinned the tier's ABSENCE of video supply (no video detection + the
   * route's dependency 500); [r323b] supplies the video, so this leg now
   * witnesses the PRESENCE: the video detection this file's fixture polled is
   * real — it carries media_type 'video' and a file_path ending in the
   * clip's name — and the video route it rides serves 200 with the clip's own
   * bytes to a plain read (the server-side half of the download leg's mirror,
   * asserted standalone so the supply's health is visible even when the
   * browser leg's skips gate it out). The 400 guard's OTHER branch — a
   * non-video detection id sent to the video route — is a DIFFERENT clause,
   * still pinned: the ORDERING FIXTURE's person image (orderSecond, a bulk
   * route image detection, media_type 'image' by column default) refused 400
   * "Detection {id} is not a video (media_type: image)"
   * (detections.py:1593-1597), proving the route's media-type guard works
   * from the handler, not just the dependency. Refusing orderSecond keeps
   * this leg's inputs to the [r323b] supplies alone — it needs neither the
   * legacy scenario drop nor any pipeline run, and its own fixture pins
   * already proved the row is an image with a serving image route.
   */
  test("F-296 the video supply is real: the clip drop produced a video detection, its video route serves the clip bytes, and an image detection is refused by the route's own 400 guard", async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    test.info().skip(!videoDrop.ready, videoDrop.ready ? '' : videoDrop.why);
    if (!h.ready || !videoDrop.ready || !videoEventId || !videoDetection || !orderSecond) return;
    test.setTimeout(90_000);
    const session = await adminSession(harness);

    // The supply's own claim, re-read live: the event's first detection is
    // the video, its file_path ends with the clip's name.
    const stored = await detectionItems(session, videoEventId);
    expect(stored.items[0]?.media_type, 'the supply produced a VIDEO detection').toBe('video');
    expect(
      (stored.items[0]?.file_path ?? '').endsWith(videoDrop.clipTail),
      'the video detection rides the dropped clip file'
    ).toBe(true);

    // The route serves the clip's own bytes (200, whole file, no truncation)
    // — the tmpfs at /app/data/thumbnails made frame extraction possible, and
    // the .mp4 short-circuit means the streamed bytes are the source's.
    const served = await mediaRead(session, `/api/detections/${videoDetection.id}/video`);
    expect(served.status, 'the video route answers 200 for the video detection').toBe(200);
    const servedBytes = Buffer.from(await served.arrayBuffer());
    expect(sha256(servedBytes), 'the served bytes are the dropped clip BYTE-FOR-BYTE').toBe(
      sha256(readFileSync(videoDrop.clipPath))
    );

    // The handler's own 400 guard (detections.py:1593-1597): an IMAGE
    // detection id sent to the video route is refused by the HANDLER, naming
    // the media_type — the route is guarded, not just reachable. The refused
    // row is the ordering fixture's person image (orderSecond): media_type
    // 'image' by the bulk route's column default, its image route already
    // proven serving by the fixture's byte mirror.
    const refusal = await mediaRead(session, `/api/detections/${orderSecond.id}/video`);
    const body = (await refusal.json().catch(() => null)) as {
      detail?: string;
    } | null;
    expect(refusal.status, 'an image detection id on the video route is the handler’s 400').toBe(
      400
    );
    expect(body?.detail ?? '', 'the 400 detail names the detection’s image media_type').toContain(
      'is not a video (media_type: image)'
    );

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
      'the button rides EVERY modal — media or not (EventDetailModal.tsx:1257)'
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

    // The failure VERBATIM from the client-side ApiError (api.ts:3250 via
    // EventTimeline.tsx:1044) — not a generic "failed". The server never
    // produced this string; the app diagnosed its own empty detection_ids.
    await expect(
      page.locator('[data-sonner-toast]').filter({
        hasText: 'Event has no associated media to download',
      }),
      'the toast names the shipped no-media sentence'
    ).toBeVisible();
    // isDownloading resets on the REJECTED path too (the same finally,
    // EventDetailModal.tsx:288-291): the button is retryable, not bricked.
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
    // DIFFERENT query branch (events.py:2600-2608 joins the event_detections
    // junction and orders by EventDetection.created_at; the default branch
    // :2651-2656 orders Detection.detected_at) and that branch surfaces the
    // junction column as association_created_at, which the default branch leaves
    // null (schema: schemas/detections.py:228). Measured on this stack: the
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
      'the DEFAULT ordering does not populate the junction timestamp (events.py:2651-2656 branch)'
    ).toBeNull();
    expect(
      createdAt.items[0]?.association_created_at ?? null,
      'the created_at ordering DOES populate the junction timestamp, so the knob routes to its own branch (events.py:2600-2608)'
    ).not.toBeNull();
    // The knob is validated, not free-form: an out-of-set value is refused by the
    // shipped route rather than silently falling back to the default
    // (events.py:2528's VALID_DETECTION_ORDER_BY, the 400 at :2572-2576). A
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

  /* ------------------------------ the ordering leg -------------------------- */
  /* The clause the tier previously had no honest data source for, now supplied
   * by the ordering fixture [r323b] built (the beforeAll's ordering supply
   * block): ONE event whose two detections make the two shipped orderings
   * disagree — bulk-created with crossed detected_at values (the LATER
   * timestamp on the row detection_ids[0] names), so the DEFAULT ordering
   * (Detection.detected_at asc) puts the OTHER row first. The fixture's own
   * precondition pins (read back after the bulk writes) prove the disagreement
   * held on the stack that ran this: junction order = orderIds[0], default
   * items[0] = orderIds[1], created_at items[0] = orderIds[0]. */

  /**
   * THE FIRST-DETECTION SEAM, EXECUTED. The shipped client names the download
   * target as event.detection_ids[0] (api.ts:3254 at this head) and separately
   * reads `items?.[0]` of a default-ordered detection list to pick the
   * media_type (api.ts:3257-3265). With ONE detection those two agree whatever
   * the backend does — the old fixme's measured vacuity. This fixture's event
   * makes them DISAGREE: detection_ids[0] is the LATER-detected image (the cat
   * drop), the default ordering puts the EARLIER one first (the person drop).
   * So `isVideo` is decided from the person row while the URL fetches the cat
   * row — and THIS leg asserts the click downloads the CAT's bytes (the
   * detection_ids[0] row), NOT the person's. Reddening it: a client that
   * switches to items[0].id for the URL, or a server that reorders the
   * junction, or an app that guesses media_type from the URL row — each flips
   * an equality below. The filename carries the EVENT id either way
   * (`event_${eventId}_media.jpg`), so the name alone could not tell the two
   * rows apart — the BYTES are the pin.
   */
  test('F-296 with two detections whose two orderings disagree, Download takes detection_ids[0] — the cat image, not the default-ordered person image', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready || !orderEventId || !orderFirst || !orderSecond) return;
    test.setTimeout(180_000);
    const session = await bootWithModal(page, probeCameraId, orderEventId);

    // Premise, re-read live at leg time: the two orderings still disagree
    // (the fixture's beforeAll pins assert the same reads; a drift between
    // fixture time and leg time — another writer touching the row — must
    // fail HERE, naming the seam, not in the byte compare as a mystery).
    const row = await eventRow(session, orderEventId);
    expect(row.detection_ids.length, 'the ordering event holds two detections').toBe(2);
    const defaultOrder = await detectionItems(session, orderEventId, '?limit=2');
    expect(
      defaultOrder.items[0]?.id,
      'the DEFAULT ordering still puts the EARLIER row (person) first'
    ).toBe(orderSecond.id);
    expect(row.detection_ids[0], 'the junction still names the LATER row (cat) first').toBe(
      orderFirst.id
    );
    // The client's media_type read comes from the default-ordered items[0] —
    // the person row — so the premise that isVideo is decided by a DIFFERENT
    // row than the URL fetches is pinned server-side too.
    expect(
      defaultOrder.items[0]?.media_type,
      'the default-ordered first item is an image (the media_type the client reads)'
    ).toBe('image');

    const button = downloadButton(page);
    await expect(button, 'the modal footer carries the Download Media button').toBeVisible();

    // THE CLICK — the same shipped chain as legs 1/4, on an event where the
    // two candidate "firsts" differ.
    const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Media download started' });
    const landed = await clickAndCatchDownload(page, button);

    // The name carries the EVENT id (both rows would produce the same
    // filename — the name cannot discriminate; the BYTES do).
    expect(landed.filename, 'the app’s default name for THIS event').toBe(
      `event_${orderEventId}_media.jpg`
    );
    // THE PIN: what landed is detection_ids[0]'s image (the cat drop) and is
    // byte-distinct from the default-ordered first row's (the person drop).
    expect(
      landed.bytes.equals(orderFirst.sourceBytes),
      'the download is detection_ids[0]’s image — the junction order won'
    ).toBe(true);
    expect(
      landed.bytes.equals(orderSecond.sourceBytes),
      'the download is NOT the default-ordered first row’s image'
    ).toBe(false);

    await expect(toast, 'the success toast is the shipped copy').toBeVisible();
    await expect(button, 'the button exits its downloading state').toHaveText('Download Media');
    console.log(
      `[F-296] ordering seam mirrored (event ${orderEventId}: ids[${row.detection_ids[0]}] ` +
        `vs items[0]=${defaultOrder.items[0]?.id})`
    );
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
