/**
 * FE-3 golden paths (F2.3): F-053 (event detail › Video clip — generate, play, download).
 *
 * Row clause (verbatim from docs/reference/feature-inventory.md:189):
 *   F-053 "Event Timeline / Event detail › Video clip (generate, play, download)
 *          `/timeline` — clicks Generate Clip on a card or opens the modal's
 *          Video Clip tab; plays or downloads the MP4"
 *   The action column — the contract — is a DISJUNCTION ("or"): the two named
 *   doors are (a) click Generate Clip on a card and (b) open the modal's Video
 *   Clip tab. This file drives BOTH, and the MP4 half is recorded as blocked.
 *
 * THE ROW STAYS `unverified`, AND THE REASON IS A MEASURED BACKEND DEFECT, NOT A
 * QUIET LEG. Read the block below before touching this file: the whole
 * play/download half of the clause is unreachable on the fake tier because the
 * CLIP GENERATOR CANNOT BE CONSTRUCTED AT ALL under the stack's read-only rootfs,
 * and the failure lands BEFORE any of the route's own branches. Every leg here
 * passes today and every leg names the mutation that reddens it (UR-128).
 *
 * WHY generate-to-completion / play / download CANNOT EXECUTE — PROVEN ON THE
 * WIRE ON THIS ROW'S HELD STACK (`make-stack.py up f053 4`, UI :19480 / API
 * :19400), measured four times against three DIFFERENT events, and reproduced
 * through the UI's own nginx so it is the path the browser takes:
 *
 *   1. POST /api/events/{id}/clip/generate → 500
 *      {"error":{"code":"INTERNAL_ERROR","message":"[Errno 30] Read-only file
 *               system: 'data/clips'","timestamp":"2026-10-15T17:51:23.555611+00:00"}}
 *      re-measured 17:55:04 (event 1, a real dropped detection), 18:12:19
 *      (event 2, a detection-less bulk row), 18:31:08 (event 4, a second dropped
 *      detection) — byte-identical. Status line through the UI's nginx:
 *      `HTTP/1.1 500 Internal Server Error` (leg 2 asserts both, from the wire).
 *   2. The backend's own traceback names the CONSTRUCTION, not the ffmpeg call:
 *      `backend/api/dependencies.py:890 get_clip_generator_dep` →
 *      `backend/services/clip_generator.py:642 get_clip_generator` → `:180 __init__`
 *      → `:188 _ensure_clips_directory` → `mkdir(parents=True, exist_ok=True)` at
 *      `:191` → OSError. It is a route `Depends` (generate_event_clip,
 *      backend/api/routes/events.py:2517), so the 500 happens on the way INTO the
 *      handler: the route's own 400 at events.py:2567 ("Cannot generate clip:
 *      event has no detections"), its 400 at :2577, its 201 at :2608-2615 and its
 *      404 are ALL UNREACHABLE on this tier — including for an id that does not
 *      exist: POST /api/events/987654321/clip/generate answers the SAME 500
 *      read-only body, not 404 (measured 18:24:11), because the provider answers
 *      before get_event_or_404 does. So the row's question "what does generate
 *      answer when the event cannot yield a clip?" has a shipped answer
 *      (events.py:2566-2571, 400 + that sentence) and an OPERATING answer on this
 *      tier (500 + read-only), and the two differ: a header that asserted the 400
 *      would be a fiction, so leg 2 asserts the 500 it can prove and this block
 *      records the 400 the code declares.
 *   3. IT IS NOT A "GENERATE ONLY" DEFECT — the media route takes the SAME
 *      dependency, so nothing on the clip path can serve a byte:
 *        GET /api/media/clips/1_clip.mp4            → 500, identical error body
 *        GET /api/media/clips/does_not_exist_clip.mp4 → 500, identical error body
 *        GET /api/media/clips/..%2F..%2Fetc%2Fpasswd   → 500, identical error body
 *      (all direct to :19400 AND through the UI's nginx at :19480). `serve_clip`
 *      (backend/api/routes/media.py:465) declares `Depends(get_clip_generator_dep)`
 *      (`backend/api/dependencies.py:890`), so `_validate_and_resolve_path`
 *      (media.py:42) never runs — the traversal probe not answering media.py's own
 *      400/403 is the proof that play and download are blocked at the same root
 *      cause, and that NO golden trick (a hand-placed file, a forged clip_path)
 *      could reach an MP4: the endpoint that serves it is dead before it reads the
 *      disk.
 *   4. THE TIER BOUNDARY, AND WHY THIS FILE CANNOT ROUTE AROUND IT. The backend
 *      container is `read_only: true` (docker-compose.ci.yml:103) with tmpfs only
 *      on /tmp, /home/appuser/.cache and /cameras. `/app/data` becomes a WRITABLE
 *      tmpfs only on `--seeded` runs: scripts/feature_check.py:500 `if seeded:` →
 *      `:506` appends `/app/data:size=20m,mode=1777,uid=1000,gid=1000`, and CI's
 *      non-seeded golden job (.github/workflows/ci.yml:3712) is the tier this
 *      project runs on — `golden` explicitly ignores `*.seeded.spec.ts`
 *      (frontend/playwright.config.ts:285). Two rules follow, both mine to obey:
 *        • I may not move this row into the seeded regime to make it green (the
 *          brief names exactly ONE new file and forbids touching scripts/, which
 *          owns the seeded stack; the three seeded golden specs that exist are
 *          ops-a's rows in their own PRs: frontend/tests/golden/operations/
 *          {debug-mode-toggle,circuit-breaker-reset,recording-replay}.seeded.spec.ts).
 *        • I may not point `clips_directory` somewhere writable:
 *          core/config.py:2687 defaults it to `data/clips` and NOTHING in this
 *          stack's rendered compose sets it (checked against
 *          /tmp/fe3-stacks/f053/compose.json) — the brief's "never invent an env
 *          var the harness does not already read" is exactly this case.
 *      THE FINDING, FOR THE ROW'S NOTES AND THE PR BODY: on a read-only-rootfs
 *      deployment (which is what docker-compose.ci.yml ships),
 *      `POST /api/events/{id}/clip/generate` and every
 *      `GET /api/media/clips/{filename}` are 500-ALWAYS, because
 *      ClipGenerator's constructor creates its output directory inside a
 *      non-writable path. Fix shape: construct lazily (or honour an existing
 *      writable mount), and the row's MP4 clauses become testable.
 *
 * WHAT THIS FILE ASSERTS, AND THE MUTATION THAT REDDENS EACH LEG.
 * - LEG 1, the modal's Video Clip tab (the row's second named door,
 *   EventDetailModal.tsx:689 → :697-698): the tab mounts EventVideoPlayer and the
 *   DOM mirrors GET /api/events/{id}/clip read Node-side through the very path the
 *   component uses (`fetchEventClipInfo`, api.ts:6289) — including the metadata
 *   the tab HIDES, which is the clause "plays or downloads the MP4" in negative
 *   form: a `<video>` or a download control on a row the server calls unavailable
 *   would be a player pointing at nothing. Reddening it: make get_event_clip
 *   report clip_available:true (or any non-null metadata) on a clip-less row
 *   (events.py:2454-2462); render `<video>`/Download in the unavailable branch
 *   (EventVideoPlayer.tsx:233, :277); remove the generate affordance (:210-228).
 *   Its negative control is the DROP ROW: an event that really did produce a
 *   detection image on disk is equally unavailable, because the only writer of
 *   events.clip_path is the success path this tier cannot reach (events.py:2598,
 *   inside :2589's completed branch). That is what stops leg 1 from reading
 *   "every event on this stack is unavailable, so my mirror proves nothing".
 * - LEG 2, the card's Generate Clip button (the row's FIRST named door,
 *   EventCard.tsx:615-645): the shipped chain is driven by a real CLICK and its
 *   refusal is asserted on BOTH ends — the toast carries the transport's own
 *   sentence and the same status/statusText are read from Node in the same leg,
 *   from the same UI origin. Reddening it: fix the read-only rootfs and the toast
 *   flips to the success copy (EventTimeline.tsx:245), which fails this leg — it
 *   is a witness to the CURRENT shipped answer and is built to flip when the
 *   defect above is repaired. The 75 s settle is not padding: 5xx is retried
 *   (api.ts:904) with getRetryDelay = 1000·2^attempt (api.ts:897, :913) and
 *   MAX_RETRIES = 3 (api.ts:896), so ONE click costs 4 POSTs and 1+2+4 = 7 s of
 *   backoff before anything is rendered.
 * - LEG 3, the card's affordance PAIR: Generate is rendered whenever the handler is
 *   wired (EventCard.tsx:615) but Download only from the in-memory clip map
 *   (:648 `{clipUrl && onDownloadClip && …}`), mirrored per row against the Node
 *   read of every row on this file's camera, with the card count mirrored against
 *   the list route's own total, and 'Regenerate video clip' (:624) asserted absent
 *   camera-wide because nothing can fill that map here
 *   (EventTimeline.tsx:237-244). Reddening it: render Download unconditionally, or
 *   pre-fill the map for a row the server calls unavailable.
 *
 * DATA SUPPLY, AND THE RESOURCE CLAIM BEHIND IT. Sanctioned sources only (the
 * brief): POST /api/events/bulk on a camera this file names — the documented
 * supply, harness.ts:330-353 — and the fake-VLM drop, `scripts/feature-check.sh
 * drop <image> <camera>`, the same call dashboard-drop.spec.ts:194-201 and
 * timeline/event-detail-modal.spec.ts:372-381 make. The scenario is
 * `harness-smoke`, and the reason is arithmetic, not taste: person-at-door's bytes
 * are F2.1's (dashboard-drop.spec.ts:93-98 picks the first fast CONFIRMED scenario
 * that is not harness-smoke, which is person-at-door), car-in-driveway is DO-1's
 * (download-media.spec.ts:179 claims it outright), cat-on-porch is F-054's
 * (timeline/event-detail-modal.spec.ts:214), slow-reply is the book's failure mode
 * (analytics-alerts/harness.ts:22-30). That leaves harness-smoke — the one set
 * whose event EXISTS on every stack regardless of who dropped it. The gate is
 * stack-wide: key `dedupe:<sha256>`, TTL 300 s (dedupe.py:10-13, :164, set at
 * :439), written at PROCESSING time (is_duplicate_and_mark, :452) — so re-dropping
 * another file's bytes inside the window silently suppresses THAT file's
 * assertion, and dropping a set nobody dropped inside the window yields NOTHING.
 *
 * WHY A SECOND EVENT ON THAT CAMERA IS SAFE, AND WHOSE ROW IT IS. The golden
 * project is ONE worker, serial, in file order (playwright.config.ts:286-290) and
 * this file is #92 of 97 collected specs, so the drop lands AFTER everything that
 * counts that camera's rows: analytics-alerts/alerts.spec.ts:220
 * (`toHaveCount(1)` on the one `high` alert) is #2 of 97 and its :14-19 reliance
 * on smoke()'s event is the same file; cameras-baseline's `data_points`/`entries`
 * reads are #58 and cameras-zones' snapshot is #61. All three run first, and the
 * only five files after this one are webhooks/*, which read no event route at all
 * (grepped). So an EXTRA `high` row here cannot reach a count anyone else took.
 *
 * OWNERSHIP IS PROVED, NOT ASSUMED, BECAUSE THE TWO TIERS DIFFER. On CI the gate
 * is still shut when golden starts (analytics-alerts/harness.ts:17-21 measures
 * smoke()'s drop 37 s before golden launches, against the 300 s TTL), so the copy
 * is a no-op and the row the negative control reads belongs to the harness —
 * READ-ONLY here, never purged, because alerts.spec.ts's page is built on it. On a
 * stack that never smoked (every local run, including this file's two witness runs)
 * the copy lands its own event: measured on this row's held stack, copy at
 * 19:03:05 → the row appeared at 19:03:40 with detection_count 1, and the Redis key
 * appeared only with it. beforeAll therefore SNAPSHOTS the camera first and takes
 * only rows that appear AFTER the snapshot as its own (afterAll purges exactly
 * those, plus its bulk rows); a row it cannot attribute is read and left alive.
 * The narrow third case — gate shut on bytes whose row a previous run of THIS file
 * purged — is repaired by re-issuing the same sanctioned drop after the TTL, never
 * by inventing a row through a route the app does not call.
 *
 * WHY THIS FILE OWNS ITS FIXTURE. The file rule is one new file, so no helper may
 * be added to harness.ts — the builders below are that harness's own contracts
 * re-declared locally (its camera helper is module-private: `ensureCamera`,
 * harness.ts:481-527; the exported fixtures are bound to sibling cameras whose row
 * counts other rows mirror, harness.ts:851, :659-668). This file's camera is
 * `fe3-clip-probe`, so every count it mirrors is a count it created. Cleanup is
 * the HARD delete for the reason F-047 chose it (harness.ts:659-668): a re-run must
 * start from its own rows only, and trash is somebody else's ground truth.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  api,
  apiWrite,
  closedByGuard,
  hardDeleteFixtureRows,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  waitForEventCards,
  type Session,
  type TimelineHarness,
} from './harness';

/* -------------------------------------------------------------------------- */
/* Collection-time readiness. Playwright runs COLLECTION before any runtime    */
/* skip, so every env read is defensive: a missing env is a SKIP reason, never */
/* a `--list` crash outside the harness (harness.ts:7-13 states the rule).     */
/* -------------------------------------------------------------------------- */

const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

/** The drop's camera/scenario: see the header's resource arithmetic. */
const DROP_SCENARIO = 'harness-smoke';

/** This file's own camera (see the header: why it may not be a sibling's). */
const CLIP_CAMERA_NAME = 'fe3-clip-probe';

/** FOUR up from frontend/tests/golden/timeline (the precedent at
 *  timeline/event-detail-modal.spec.ts:299 is the same depth). */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

/** What GET /api/events/{id}/clip answers (api.ts:6247 `ClipInfoResponse`). */
interface ClipInfo {
  event_id: number;
  clip_available: boolean;
  clip_url: string | null;
  duration_seconds: number | null;
  generated_at: string | null;
  file_size_bytes: number | null;
}

interface DetectionItem {
  id: number;
  file_path: string | null;
  media_type: string | null;
}

interface EventPage {
  items: { id: number }[];
  pagination: { total: number; has_more: boolean };
}

/** The ONE Node-side read every leg mirrors against — the same route the component
 *  calls (api.ts:6289), read from Node so the comparison is DOM↔server and not
 *  DOM↔DOM. */
const clipTruth = (session: Session, id: number) =>
  api<ClipInfo>(harness, session, `/api/events/${id}/clip`);

const detectionItems = (session: Session, id: number) =>
  api<{ items: DetectionItem[] }>(harness, session, `/api/events/${id}/detections?limit=20`);

/** apiWrite's contract is to THROW on non-2xx — right for a mutation a leg
 *  expects to succeed, wrong for a leg whose SUBJECT is a refusal. So this one
 *  call reads its own status and carries the body in its return value.
 *
 *  `base` defaults to the UI origin on purpose: that is the nginx the browser's
 *  own request goes through (nginx.conf:24's api bucket), and the shipped error
 *  sentence is built from THIS response's status + statusText (api.ts:1212), so
 *  the leg's comparison is same-origin, same-instrument. */
async function generateRaw(
  session: Session,
  id: number,
  base: 'api' | 'ui' = 'ui'
): Promise<{ status: number; statusText: string; body: unknown }> {
  const res = await fetch(`${harness[base]}/api/events/${id}/clip/generate`, {
    method: 'POST',
    headers: { Cookie: `${session.name}=${session.value}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ force: false }),
  });
  return {
    status: res.status,
    statusText: res.statusText,
    body: await res.json().catch(() => null),
  };
}

/* -------------------------------------------------------------------------- */
/* The book row, read as authored — the assertions judge the BOOK, not a number */
/* I typed. Same reason timeline/event-detail-modal.spec.ts:225-245 gives.      */
/* -------------------------------------------------------------------------- */

interface Scenario {
  name: string;
  image: string;
  detections: { class: string; confidence: number }[];
  verdict: { verdict: string; risk_score: number };
  reply_delay_seconds: number;
}

function readBook(): {
  scenario: Scenario;
  imagePath: string;
  cameraId: string;
  cameraRoot: string;
} {
  const bookPath = String(process.env.FEATURE_CHECK_SCENARIOS ?? '');
  const camerasPath = String(process.env.FEATURE_CHECK_CAMERAS ?? '');
  const cameraRoot = String(process.env.FEATURE_CHECK_CAMERA_ROOT ?? '');
  if (!bookPath || !camerasPath || !cameraRoot) {
    throw new Error('drop supply needs FEATURE_CHECK_SCENARIOS / _CAMERAS / _CAMERA_ROOT');
  }
  const scenarios = (JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios: Scenario[] })
    .scenarios;
  const scenario = scenarios.find((s) => s.name === DROP_SCENARIO);
  if (!scenario) throw new Error(`scenario book has no '${DROP_SCENARIO}' row`);
  if (scenario.reply_delay_seconds) {
    throw new Error(`${DROP_SCENARIO} delays its reply — it would never land an event`);
  }
  const cameraId = (JSON.parse(readFileSync(camerasPath, 'utf8')) as Record<string, string>)[
    scenario.name
  ];
  if (!cameraId) throw new Error(`the harness seeded no camera named ${scenario.name}`);
  const imagePath = path.join(path.dirname(bookPath), scenario.image);
  if (!existsSync(imagePath)) throw new Error(`no scenario image at ${imagePath}`);
  return { scenario, imagePath, cameraId, cameraRoot };
}

/* -------------------------------------------------------------------------- */
/* This file's fixture: its own camera plus rows it owns outright.             */
/* -------------------------------------------------------------------------- */

interface CameraCreated {
  id: string;
  detail?: string;
}

/** A 409 is ROUTINE (the list read can be the 60 s cache entry, so "absent from
 *  the list" ≠ "absent from the DB"); the id travels inside the 409's own
 *  `detail` and is confirmed against the UNCACHED single-camera read
 *  (cameras.py:683-720) before anything builds on it. Same contract as
 *  harness.ensureCamera (harness.ts:481-527), which is not exported. */
async function ensureClipCamera(
  session: Session,
  name: string,
  folderPath: string
): Promise<string> {
  const res = await fetch(`${harness.api}/api/cameras`, {
    method: 'POST',
    headers: {
      Cookie: `${session.name}=${session.value}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, folder_path: folderPath }),
  });
  const body = (await res.json().catch(() => null)) as CameraCreated | null;
  if (res.status >= 200 && res.status < 300) {
    if (!body?.id) throw new Error(`fixture: POST /api/cameras for '${name}' 2xx had no id`);
    return body.id;
  }
  if (res.status !== 409) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered ${res.status}: ` +
        JSON.stringify(body).slice(0, 200)
    );
  }
  const found = String(body?.detail ?? '').match(/already exists \(id: ([^)]+)\)/);
  if (!found) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered 409 with an unparseable detail: ` +
        `${String(body?.detail).slice(0, 200)}`
    );
  }
  await api<{ id: string }>(harness, session, `/api/cameras/${encodeURIComponent(found[1])}`);
  return found[1];
}

/** The camera select is built from the 60 s cache-aside list, and a hit never
 *  refreshes the TTL nor refetches (useCamerasQuery defaults refetchInterval to
 *  false), so a page booted inside the window never corrects itself: the wait is
 *  unconditional and happens BEFORE any boot (harness.ts:400-441). */
async function waitForClipCameraInList(session: Session, name: string): Promise<void> {
  const deadline = Date.now() + 90_000; // > SHORT_TTL (60 s) + margin
  let polls = 0;
  for (;;) {
    polls += 1;
    const list = await api<{ items?: { name: string }[] }>(harness, session, '/api/cameras');
    if ((list.items ?? []).some((cam) => cam.name === name)) return;
    if (Date.now() >= deadline) {
      throw new Error(
        `fixture: '${name}' never appeared in GET /api/cameras within 90s (${polls} polls) — ` +
          "that list's 60 s cache entry is not converging (harness.ts:400-441)"
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 3_000));
  }
}

interface DropRow {
  id: number;
  /** False when the drop's bytes hit the watcher's dedupe gate and the row the
   *  negative control reads belongs to whoever landed it first. Then this file
   *  READS it and never purges it — another row's clause may be mirroring it. */
  ownedByThisFile: boolean;
  /** Every row that appeared AFTER the pre-drop snapshot. Any of them can only be
   *  this file's, so all of them are this file's to delete. */
  freshIds: number[];
}

interface ClipFixture {
  cameraId: string;
  /** Row 0: leg 1's tab subject. */
  tabRowId: number;
  /** Row 1: leg 2's card subject (clicked). */
  cardRowId: number;
  /** Row 2: leg 3's card subject (never clicked). */
  pairRowId: number;
  /** Every id this fixture created. */
  eventIds: number[];
}

async function createClipFixture(session: Session): Promise<ClipFixture> {
  const cameraId = await ensureClipCamera(session, CLIP_CAMERA_NAME, '/cameras/fe3_clip_probe');
  await waitForClipCameraInList(session, CLIP_CAMERA_NAME);

  // This camera is this file's own, so everything on it is this file's residue.
  // HARD delete (harness.ts:795's exported cleanup, same route) so a re-run's
  // counts are its own rows only.
  const stale = await api<EventPage>(
    harness,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await hardDeleteFixtureRows(
    harness,
    session,
    stale.items.map((row) => row.id)
  );

  const salt = Date.now();
  const events = [0, 1, 2].map((i) => ({
    // One batch_id per row: events.batch_id is UNIQUE (harness.ts:553).
    batch_id: `fe3clip-${salt}-${i}`,
    camera_id: cameraId,
    started_at: new Date(Date.UTC(2026, 9, 13, 6, i * 9)).toISOString(),
    risk_score: 37,
    risk_level: 'low',
    summary: `FE-3 clip fixture row ${i}`,
  }));
  const bulk = await apiWrite<{
    succeeded: number;
    results: { status: string; id: number | null; error: string | null }[];
  }>(harness, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `clip fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== 3) {
    throw new Error(
      `clip fixture: wanted 3 ids, got ${eventIds.length} — the legs index them positionally.`
    );
  }

  // PRECONDITION ASSERTED, NOT ASSUMED. A bulk row carries no event↔detection
  // link (the bulk builder's Event(...) at events.py:1599-1608 sets no
  // detection_ids), so generate's own shipped gate —
  // `get_detection_ids_from_event` (events.py:189) → empty → 400 (events.py:2566-
  // 2571) — is the code's answer for these rows. That is what makes leg 1's
  // subject "an event that CANNOT yield a clip" by shipped definition, and why
  // the tier's 500 (header step 2) is the operating answer instead.
  for (const id of eventIds) {
    const dets = await detectionItems(session, id);
    if (dets.items.length !== 0) {
      throw new Error(
        `clip fixture: row ${id} arrived with ${dets.items.length} detections — ` +
          'leg 1 needs a row the shipped gate refuses'
      );
    }
    const info = await clipTruth(session, id);
    if (info.clip_available || info.clip_url !== null) {
      throw new Error(
        `clip fixture: row ${id} arrived clip_available=${info.clip_available} ` +
          `clip_url=${String(info.clip_url)} — every leg here starts from no clip`
      );
    }
  }
  return {
    cameraId,
    tabRowId: eventIds[0],
    cardRowId: eventIds[1],
    pairRowId: eventIds[2],
    eventIds,
  };
}

/* -------------------------------------------------------------------------- */
/* The clip panel, read as shipped. All four states live inside the SAME       */
/* container (EventVideoPlayer.tsx:161) by deliberate design (the file's own   */
/* :35-36 note: stable DOM across transitions), so a leg must name the STATE.  */
/* -------------------------------------------------------------------------- */

const player = (page: Page) => page.getByTestId('event-video-player-container');
const unavailable = (page: Page) => page.getByTestId('clip-unavailable');

/** Boot straight into the modal through the shipped `?event=` door, then open the
 *  tab the clause names. Every navigation goes through quietBoot: the nginx api
 *  bucket (frontend/nginx.conf:24, rate=10r/s burst=20) sheds boot traffic and a
 *  SHED boot renders a coat, not the page (harness.ts:198-241). */
async function openClipTab(page: Page, cameraId: string, eventId: number): Promise<Session> {
  const session = await adminSession(harness);
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(
    page,
    harness,
    `/timeline?camera=${encodeURIComponent(cameraId)}&event=${eventId}`
  );
  await expect(page.getByTestId('timeline-page'), 'the page root paints').toBeVisible();
  await waitForEventCards(page);
  await expect(
    page.getByTestId('event-detail-modal'),
    'the deep link opens the modal'
  ).toBeVisible();
  await page.getByTestId('video-clip-tab').click();
  await expect(
    player(page),
    'the Video Clip tab mounts EventVideoPlayer (EventDetailModal.tsx:697-698)'
  ).toBeVisible();
  return session;
}

/** Boot the grid for one camera and nothing else. */
async function bootTimeline(page: Page, path: string): Promise<void> {
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(page, harness, path);
  await expect(page.getByTestId('timeline-page'), 'the page root paints').toBeVisible();
}

let fx: ClipFixture;
let dropRow: DropRow;
let book: ReturnType<typeof readBook>;

/** Every row currently on the drop camera. A SET, because the only question ever
 *  asked of it is "did a row NEW since my snapshot appear?" — which is the one
 *  attribution a re-dropped byte-set cannot get from its own shape. */
async function rowsOn(session: Session, cameraId: string): Promise<Set<number>> {
  const list = await api<EventPage>(
    harness,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  return new Set(list.items.map((row) => row.id));
}

/** The sanctioned supply call, verbatim as the two precedents make it
 *  (timeline/event-detail-modal.spec.ts:372-381, dashboard-drop.spec.ts:194-201). */
function dropImage(): void {
  execFileSync(
    path.join(repoRoot, 'scripts/feature-check.sh'),
    ['drop', book.imagePath, DROP_SCENARIO],
    {
      cwd: repoRoot,
      env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: book.cameraRoot },
      encoding: 'utf8',
      timeout: 30_000,
    }
  );
}

/** Wait for rows that did not exist in `before`. Measured on this row's held
 *  stack: copy → the event with detection_count 1 appeared at t+35 s (copy at
 *  19:03:05, visible 19:03:40), and the Redis gate `dedupe:<sha256>` is written
 *  only at processing time, so "no new row" is the watcher saying it already has
 *  these bytes. Returns EVERY new id: the watcher can land a second event on a
 *  re-copy (its on_modified leg, file_watcher.py:539), and a row that appeared
 *  after my snapshot cannot belong to anyone else, so all of them get purged. */
async function waitForNewRows(
  session: Session,
  cameraId: string,
  before: Set<number>,
  budgetMs: number
): Promise<number[]> {
  const deadline = Date.now() + budgetMs;
  for (;;) {
    const fresh = [...(await rowsOn(session, cameraId))].filter((id) => !before.has(id));
    if (fresh.length > 0) return fresh.sort((a, b) => a - b);
    if (Date.now() >= deadline) return [];
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
}

/** The DEDUPE MIRROR (the predicate download-media.spec.ts:107-119 reasons about
 *  for its own camera): a row whose first detection's stored path is the book's
 *  image. True of a row my drop created AND of the row that made it a no-op, so
 *  the negative control exists on both tiers; it says nothing about who owns it,
 *  which is why ownership travels by snapshot-diff instead. */
async function rowFromBookImage(
  session: Session,
  candidateIds: number[],
  imageName: string
): Promise<number | undefined> {
  for (const id of candidateIds.sort((a, b) => b - a)) {
    const dets = await detectionItems(session, id);
    if (dets.items[0]?.file_path?.endsWith(imageName)) return id;
  }
  return undefined;
}

test.beforeAll(async () => {
  // The drop, the fake VLM's reply, the camera list's 60 s cache entry, and (in
  // the one case that needs it) the 300 s dedupe TTL are all real waits; inside a
  // hook, test.setTimeout sets the HOOK's timeout. The bound is the arithmetic
  // below: ≤120 s of fixture + ≤70 s for the first drop + 5 × 130 s of TTL wait
  // ≈ 840 s worst case, so the hook gets 900 s and the failure still reads as
  // THIS file's error, never as a Playwright timeout.
  test.setTimeout(900_000);
  const session = await adminSession(harness);
  book = readBook();
  fx = await createClipFixture(session);

  // Snapshot BEFORE the copy: a re-copy of bytes Redis already holds is a NO-OP
  // (feature_check.py:2911-2916 "It deduplicates by content for 300 s, so
  // dropping the same bytes twice inside five minutes yields one event"), so the
  // row the negative control needs may not be a row this file made — and a row
  // this file did not make is NOT this file's to delete.
  const before = await rowsOn(session, book.cameraId);
  dropImage();
  const fresh = await waitForNewRows(session, book.cameraId, before, 70_000);
  if (fresh.length > 0) {
    dropRow = { id: fresh[0], ownedByThisFile: true, freshIds: fresh };
  } else {
    // My bytes were already processed. Whoever landed them first owns that row —
    // on CI that is the harness's own smoke() event, which
    // analytics-alerts/alerts.spec.ts:14-19 builds its whole one-alert page on,
    // so this file reads it and never purges it.
    const borrowed = await rowFromBookImage(
      session,
      [...before],
      path.basename(book.scenario.image)
    );
    if (borrowed !== undefined) {
      dropRow = { id: borrowed, ownedByThisFile: false, freshIds: [] };
    } else {
      // The narrow, honest case: the gate is still closed on bytes whose row is
      // already gone — which only happens when a PREVIOUS RUN of this file
      // created the row and its afterAll purged it. Waiting the TTL out is the
      // only fix that invents nothing, so re-issue the same sanctioned drop until
      // a NEW row lands (the watcher's on_modified leg re-processes once the key
      // expires; download-media.spec.ts:117-119 states the same bound).
      let rescued: number[] = [];
      for (let attempt = 0; attempt < 5 && rescued.length === 0; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 60_000));
        dropImage();
        rescued = await waitForNewRows(session, book.cameraId, before, 70_000);
      }
      if (rescued.length === 0) {
        throw new Error(
          `golden fixture: ${DROP_SCENARIO} landed no new row on camera ${book.cameraId} in ` +
            '≈650 s of TTL waits (5 × 130 s) and no pre-existing row carries the book image — ' +
            'the negative control needs ' +
            'a row that HAS a detection image on disk, and this file will not delete or judge a ' +
            'row it cannot prove it created'
        );
      }
      dropRow = { id: rescued[0], ownedByThisFile: true, freshIds: rescued };
    }
  }

  // The control row's own shape, asserted so leg 1's negative control is judging
  // a row that really is clip-capable by the shipped definition (≥1 detection
  // whose file_path exists). The EXACT book count is asserted only of a row this
  // file created: a row inherited through the gate is another spec's pipeline
  // output and this file may not judge it.
  const dets = await detectionItems(session, dropRow.id);
  const want = book.scenario.detections.length;
  if (dropRow.ownedByThisFile ? dets.items.length !== want : dets.items.length < 1) {
    throw new Error(
      `golden fixture: drop row ${dropRow.id} (owned by this file: ` +
        `${dropRow.ownedByThisFile}) has ${dets.items.length} detections; the book declares ` +
        `${want} for ${book.scenario.name}`
    );
  }
  if (!dets.items[0].file_path || dets.items[0].media_type !== 'image') {
    throw new Error(
      `golden fixture: detection ${dets.items[0].id} is ` +
        `${String(dets.items[0].media_type)}/${String(dets.items[0].file_path)} — ` +
        'generate consumes image paths (events.py:2575 → clip_generator.py:424)'
    );
  }
  if (!existsSync(path.join(book.cameraRoot, DROP_SCENARIO, book.scenario.image))) {
    throw new Error(
      `golden fixture: the dropped image is not in ${book.cameraRoot}/${DROP_SCENARIO}`
    );
  }
});

test.afterAll(async () => {
  const session = await adminSession(harness);
  // Hard delete (harness.ts:795, DELETE /api/events/bulk {soft_delete:false}) so
  // a re-run's counts are its own rows only, and so the drop leaves nothing for
  // the next file. Deleted = rows this file created, which after the snapshot
  // diff is decidable rather than hoped: this file's bulk rows, plus every row
  // that appeared AFTER the pre-drop snapshot. A row borrowed through the dedupe
  // gate is NOT in that set, because it is another file's ground truth. A failure
  // here must not turn a green run red: the stack is on its way out.
  const owned = fx.eventIds.concat(dropRow?.freshIds ?? []);
  try {
    await hardDeleteFixtureRows(harness, session, owned);
  } catch {
    /* a purge that fails on a dying stack cannot make a green run red */
  }
});

/* --------------------------------- legs ----------------------------------- */

test.describe('F-053 video clip (generate, play, download)', () => {
  test('the modal Video Clip tab mirrors GET /api/events/{id}/clip and shows no player', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);

    const id = fx.tabRowId;
    const session = await openClipTab(page, fx.cameraId, id);

    // Server truth, read from Node through the route the component calls. This
    // row CANNOT yield a clip by shipped definition (no detection link, asserted
    // in the fixture), so get_event_clip takes its first branch (events.py:2454)
    // and answers every metadata field null (events.py:2455-2462).
    const truth = await clipTruth(session, id);
    expect(truth.event_id, 'the read is about this row').toBe(id);
    expect(truth.clip_available, 'a row with clip_path NULL is unavailable').toBe(false);
    expect(truth.clip_url, 'no clip_path ⇒ no clip_url ⇒ no <video> src').toBeNull();
    expect(truth.duration_seconds, 'no file ⇒ no duration').toBeNull();
    expect(truth.generated_at, 'no file ⇒ no mtime').toBeNull();
    expect(truth.file_size_bytes, 'no file ⇒ no size').toBeNull();

    // DOM ↔ Node. The two sentences are the component's own (:198, :199-201), and
    // the state is the branch getViewState() takes for this payload (:144-149).
    await expect(unavailable(page), 'the tab renders the unavailable state').toBeVisible();
    await expect(
      unavailable(page).getByText('No video clip available'),
      'the unavailable headline'
    ).toBeVisible();
    await expect(
      unavailable(page).getByText('Generate a clip from detection images for this event'),
      'the unavailable sub-line names the source the generator consumes'
    ).toBeVisible();

    // The affordance, with BOTH of its shipped names: the tab's button carries
    // data-testid (:215) and aria-label "Generate video clip" (:214) — the same
    // accessible name the card uses for the same action (EventCard.tsx:625). A
    // `.first()`-style presence check would pass on any button, which is the
    // vacuity these two handles exist to avoid.
    const generateButton = page.getByTestId('generate-clip-button');
    await expect(generateButton).toBeVisible();
    await expect(generateButton).toHaveAccessibleName('Generate video clip');
    await expect(generateButton).toHaveText(/Generate Clip/);

    // The states this row must NOT be in — "plays or downloads the MP4" in
    // negative form. A player or a download control here would be the UI pointing
    // at an MP4 the server just said does not exist.
    await expect(page.getByTestId('clip-available'), 'no available state').toHaveCount(0);
    await expect(page.getByTestId('video-player'), 'no <video> element').toHaveCount(0);
    await expect(page.getByTestId('download-clip-button'), 'no download control').toHaveCount(0);
    await expect(page.getByTestId('clip-loading'), 'the info read has settled').toHaveCount(0);
    await expect(page.getByTestId('clip-error'), 'the info read did not fail').toHaveCount(0);

    // NEGATIVE CONTROL (header). An event whose detection image EXISTS ON DISK is
    // just as unavailable, because the only writer of events.clip_path is the
    // success branch this tier cannot reach (events.py:2598, inside the completed
    // branch opened at :2596). So leg 1's mirror is a fact about clip_path, and it
    // cannot pass by "everything on this stack is unavailable".
    const dropTruth = await clipTruth(session, dropRow.id);
    expect(
      dropTruth.clip_available,
      `the dropped row ${dropRow.id} (which HAS a detection image) is also unavailable ` +
        'until generate completes — clip_available:false is not a fixture artifact'
    ).toBe(false);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('clicking Generate Clip on a card surfaces the server refusal verbatim, which Node reads identically', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    // Not padding: 5xx is retried (api.ts:904) with 1000·2^attempt backoff
    // (:897, :913) up to MAX_RETRIES=3 (:896), so ONE click spends 4 POSTs and
    // 1+2+4 = 7 s of backoff before the UI can render anything.
    test.setTimeout(180_000);

    const id = fx.cardRowId;
    const session = await adminSession(harness);

    // THE WIRE PROOF, ASSERTED NOT QUOTED. Both ends of the refusal in one leg,
    // read from the SAME origin the browser's click uses: the status + statusText
    // (which is where the shipped sentence comes from) and the error body. If a
    // backend fix makes the clip generator constructible, THESE expects go red
    // first and the toast below with them — this file cannot keep claiming a 500
    // it no longer measures.
    const wire = await generateRaw(session, id);
    expect(
      `HTTP/1.1 ${wire.status} ${wire.statusText}`,
      'the UI origin answers 500 for generate on this tier'
    ).toBe('HTTP/1.1 500 Internal Server Error');
    expect(
      (wire.body as { error?: { message?: string } })?.error?.message,
      'the refusal is ClipGenerator.__init__ mkdir on a read-only rootfs'
    ).toMatch(/Read-only file system: 'data\/clips'/);
    // The shipped sentence, DERIVED from that response rather than typed here:
    // api.ts:1212 builds `HTTP ${status}: ${statusText}` because the body is
    // `{"error":{…}}`, which is neither RFC 7807 (isProblemDetails wants string
    // type + string title + numeric status, api.ts:598-610) nor legacy `{detail}`
    // (api.ts:1131). So the two branches that could have carried the route's own
    // words both miss this body, and the transport's words are what ships.
    const refusal = `HTTP ${wire.status}: ${wire.statusText}`;
    expect(refusal).toBe('HTTP 500: Internal Server Error');
    const toast = page.locator('[data-sonner-toast]').filter({ hasText: refusal });

    // The row the page will show, with its truth read BEFORE the click.
    const truthBefore = await clipTruth(session, id);
    expect(truthBefore.clip_available).toBe(false);

    // THE GRID, NOT THE DEEP LINK. Measured on this row's held stack: with
    // `?event=` the modal's headlessui portal is already mounted over the grid and
    // its notes <textarea> "intercepts pointer events" on the card's button, so a
    // `?event=` boot can only ever drive the MODAL's tab — which is leg 1's door.
    // This leg's named door is the CARD (the row's first clause), so it boots the
    // camera's grid bare, where the same button is hittable.
    await bootTimeline(page, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    await waitForEventCards(page);

    // THE ROW'S FIRST NAMED DOOR: Generate Clip ON THE CARD (EventCard.tsx:615).
    const card = page.getByTestId(`event-card-${id}`);
    await expect(card, 'the fixture row renders its card').toBeVisible();
    const cardGenerate = card.getByRole('button', { name: 'Generate video clip' });
    await expect(cardGenerate, 'the card carries the clip action the clause names').toBeVisible();

    await cardGenerate.click();

    // EventTimeline.handleGenerateClip (:227) has no success branch available: the
    // POST throws, so :250-251's catch toasts the transport's message verbatim
    // (useToast.error → sonner, hooks/useToast.ts:155).
    await expect(
      toast,
      `the card's generate click surfaces the server's refusal (read-only rootfs) as the ` +
        `transport's own sentence, not a generic one`
    ).toBeVisible({ timeout: 75_000 });
    await expect(toast).toContainText(refusal);

    // A refused generation stores nothing and unlocks nothing: the card gains no
    // Download (EventCard.tsx:648 needs the in-memory URL) and the row is still
    // unavailable on the server — so the DOM mirror is the Node read of the same
    // row after the same click.
    await expect(
      card.getByRole('button', { name: 'Download video clip' }),
      'a refused generation does not add a Download affordance'
    ).toHaveCount(0);
    const truthAfter = await clipTruth(session, id);
    expect(truthAfter.clip_available, 'a refused generation stores no clip').toBe(false);
    expect(truthAfter.clip_url).toBeNull();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('a card with no clip offers Generate and no Download, mirrored per row against the server', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);

    const session = await adminSession(harness);
    // Per-row ground truth for the WHOLE camera, so the mirror is a computed set
    // and not a hope. This camera holds exactly the rows this file created.
    const rows = await api<EventPage>(
      harness,
      session,
      `/api/events?limit=100&camera_id=${encodeURIComponent(fx.cameraId)}`
    );
    expect(rows.pagination.total, 'this file owns its camera, so its counts are its own').toBe(
      rows.items.length
    );
    expect(
      rows.pagination.has_more,
      'the fixture fits inside one page, so the mirror is exact'
    ).toBe(false);
    const unavailableIds: number[] = [];
    for (const row of rows.items) {
      const info = await clipTruth(session, row.id);
      expect(
        info.clip_available,
        `row ${row.id} has completed no generation, so the server calls it unavailable`
      ).toBe(false);
      unavailableIds.push(row.id);
    }

    await bootTimeline(page, `/timeline?camera=${encodeURIComponent(fx.cameraId)}`);
    const cardCount = await waitForEventCards(page);
    expect(cardCount, 'DOM cards ↔ GET /api/events total for this camera').toBe(
      rows.pagination.total
    );

    // Every unavailable row: Generate present, Download absent. That the set is
    // iterated (not `.first()`) is what makes it 3 rows and not 1.
    for (const id of unavailableIds) {
      const card = page.getByTestId(`event-card-${id}`);
      await expect(card, `row ${id} renders a card`).toBeVisible();
      await expect(
        card.getByRole('button', { name: 'Generate video clip' }),
        `row ${id}: Generate renders whenever the handler is wired (EventCard.tsx:615)`
      ).toBeVisible();
      await expect(
        card.getByRole('button', { name: 'Download video clip' }),
        `row ${id}: Download is rendered only from the in-memory clip map (:648) — this row ` +
          'has no clip to download'
      ).toHaveCount(0);
    }

    // The card's Regenerate/Download names belong to a state nothing on this tier
    // can reach: the map is filled only by a completed generation
    // (EventTimeline.tsx:237-244), so 'Regenerate video clip' (EventCard.tsx:624)
    // must be absent across the camera. Reddening: pre-fill clipUrls for a row the
    // server calls unavailable.
    await expect(
      page.getByRole('button', { name: 'Regenerate video clip' }),
      'no card claims a clip the server says does not exist'
    ).toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
