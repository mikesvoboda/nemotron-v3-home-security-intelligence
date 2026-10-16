/**
 * F-064 — Event detail › Add face to known persons (docs batch FE-3, `[r196a]`;
 * inventory row 200's action column is the contract: "on a person detection,
 * clicks 'Add Face to Known Persons'; picks or creates a person; enrolls the
 * face." APIs `GET /api/known-persons`, `POST /api/known-persons`,
 * `POST /api/known-persons/{person_id}/enroll-from-detection`).
 *
 * EVERY CLAIM BELOW WAS READ OUT OF THE SHIPPED CODE AT THIS HEAD AND EACH
 * PREDICATE NAMES THE FILE:LINE THAT MAKES IT A JUDGEMENT. UR-128: a leg goes
 * red if the behaviour it mirrors is wrong, and where the row's clause is a
 * WRITE the leg reads the created row back off the server and compares fields —
 * never an exists-only assertion standing in for a write, never an assertion
 * that passes both ways.
 *
 * THE AFFORDANCE AND WHAT GATES IT. EventDetailModal.tsx:833-844 renders
 * `data-testid="enroll-face-button"` with the row's own copy at :843, inside a
 * guard that is `hasPersonDetection && selectedDetectionId` (:833).
 * `hasPersonDetection` is :441-447 (`objectType === 'person' || objectType
 * .includes('person') || objectType === 'face'`), so an event with no person
 * detection must render NOTHING — leg 3 is that clause's negative half, and it
 * is two-sided because the same modal is asserted to have painted its content.
 * The selection the guard reads is the FIRST detection, auto-selected
 * (:252-256).
 *
 * THE MODAL'S SURFACE, AND WHY NO LOCATOR IN THIS FILE ASKS A `role=dialog`
 * WHETHER IT IS VISIBLE. EnrollFaceModal.tsx ships NO data-testids, so every
 * locator is a role or one of the aria-labels the component spells out:
 * Dialog.Title "Enroll Face" (:259-261); radios "Add to existing person" (:323)
 * and "Create new person" (:338); the name input `id="person-name"` (:493)
 * under a visible label "Name" (:447-454); the checkbox aria-label "Is
 * household member" (:471-479); Cancel (:520-525); and a primary button whose
 * LABEL IS the state machine — "Enrolling..." while pending, "Enroll Face"
 * otherwise, `disabled` unless `canEnroll` (:528-537). `canEnroll` (:150-159)
 * returns false when `qualityBlocked` or `isPending`, then
 * `selectedPersonId !== null && !selectedAtMax` in `existing` mode, then
 * `newPersonName.trim().length > 0` in `new` mode — so the disabled/enabled
 * pairs legs 1 and 2 assert are that memo read two ways, not guesses.
 * Now the part that costs a spec its credibility if it is not measured: both
 * this modal and the event detail modal are headless-ui `Dialog as="div"`
 * wrappers (EnrollFaceModal.tsx:232, EventDetailModal.tsx:556) whose EVERY
 * child is `fixed`/`absolute` (:233-249, :558-581), so the wrapper element's
 * own box is 1280x0. Measured on this row's stack: `getBoundingClientRect()`
 * height 0 and `visibility: visible` while the panel renders in full — which is
 * why Playwright's `toBeVisible()` on `getByRole('dialog')` reports
 * "unexpected value hidden" for a modal that is painted and clickable (it is
 * also why every sibling spec asserts on `data-testid="event-detail-modal"`,
 * the Dialog.Panel at :582-584, and never on the role). EnrollFaceModal's
 * Panel carries no testid, so OPEN/CLOSED here is asserted through the
 * Dialog.Title INSIDE the panel (:259-261); the dialog role is used only as a
 * SUBTREE SCOPE, never as a visibility target. `toBeHidden()` on a title is a
 * real absence check, and the negative control in leg 2 (`toBeVisible()` on the
 * button that only exists while the persons list is non-empty, :376) makes a
 * missing subtree indistinguishable from a closed modal impossible.
 *
 * A DERIVED SCORE THE SERVER NEVER SEES. `qualityScore` is not a server field:
 * the host passes `selectedDetection.confidence ?? 0.85`
 * (EventDetailModal.tsx:1384) and EnrollFaceModal.tsx:66 blocks enrollment
 * below 0.7 (`isQualityBlocked` :95-97, first arm of `canEnroll` :151). The
 * book's person-at-door detection carries confidence 0.91
 * (backend/ai_contract/fake/scenario_fixtures/scenarios.json) and the shipped
 * stack stored exactly that (`GET /api/detections?camera_id=person_at_door`
 * → `object_type: person`, `confidence: 0.91`), so the UI does NOT pre-block
 * this detection and the request really is issued. Leg 1 asserts the derived
 * 91% through the widget's own testid (FaceQualityAssessment.tsx:121, :125
 * renders `(score * 100).toFixed(0)` + `%`); that check is two-sided, because a
 * host that stopped passing the confidence would render the 0.85 fallback as
 * 85%.
 *
 * "CREATES A PERSON" IS A WRITE AND IS READ BACK. mode 'new' makes handleEnroll
 * POST /api/known-persons with `{name: newPersonName.trim(),
 * is_household_member}` BEFORE any enroll call (EnrollFaceModal.tsx:179-188),
 * which lands in create_known_person (face_recognition.py:140-170 — 201, with
 * `embedding_count` hardcoded 0 at :166). Neither the route nor the service
 * enforces name uniqueness (no IntegrityError, no existing-name check anywhere
 * in face_recognition.py), so a per-run-salted name is collision-proof AND a
 * judgement in its own right: the list must hold EXACTLY ONE row with that
 * name — two would mean the create mutation ran twice — and the leg then
 * compares `name`, `is_household_member` and `embedding_count` against the
 * server's own row, where `embedding_count = len(p.embeddings)`
 * (face_recognition.py:125). The same leg pins the contract on the wire: POST
 * answers 201 with zero embeddings, `GET /api/known-persons/{id}` reads the
 * same row (:172-206), and DELETE answers 204 and the row is gone (:254-275).
 *
 * "PICKS ... A PERSON" IS PROVED BY THE REQUEST IT CHOOSES, NOT BY THE WIDGET.
 * Leg 2 selects the person leg 1 created out of the Listbox
 * (EnrollFaceModal.tsx:367-384 — Label "Select Person" :372-374, Button
 * aria-label "Select Person" :376-384, option text is `person.name` :435) and
 * then clicks Enroll Face. If the pick had not reached the request body,
 * handleEnroll would return at `if (personId === null) return` (:188) and
 * the user would see NOTHING at all — no toast. So the shipped failure toast
 * appearing after a pick is positive evidence that the picked id was sent, and
 * the controls under it are that no second person row appeared (the write
 * targeted the picked person rather than minting one) and that the picked
 * person's server-side `updated_at` and `embedding_count` are exactly what leg 1
 * left them at (useEnrollFace's onSuccess invalidates `knownPerson(personId)`
 * — useFaceRecognitionApi.ts:508-513 — so if the request had been retargeted or
 * retried, the timestamp this leg reads would have moved).
 *
 * WHY THE PICK LEG BOOTS A SECOND TIME INSTEAD OF REUSING LEG 1'S PAGE. The
 * persons query is `staleTime: STATIC_STALE_TIME` with no refetchOnWindowFocus
 * (useFaceRecognitionApi.ts:390-396) and a page is one browser context per test,
 * so the list a modal renders belongs to its own boot. Leg 1 runs on a stack
 * whose persons table is empty, which is itself the shipped `length === 0`
 * branch (:362-365, asserted there); leg 2 boots fresh so its Listbox is
 * populated from a GET the boot made. One navigation and one click per boot is
 * also the only way to keep the nginx api bucket from shedding an in-test
 * action: see the bucket note at the bottom.
 *
 * "ENROLLS THE FACE" CANNOT EXECUTE ON THE FAKE TIER, AND THESE LEGS ASSERT THE
 * 500 INSTEAD OF PRETENDING OTHERWISE. enroll_from_detection validates the
 * person (:685-692 → 404), the max-embeddings cap (:694-700 → 400) and the
 * detection (:703-711 → 404), and only THEN runs the face leg, inside
 * extract_face_embedding_from_detection (:473-), which asks
 * face_recognizer_loader.get_face_leg_handles() (:466-491) and raises
 * RuntimeError("face extractor unavailable: the pinned face weights are not
 * loaded …") at :517-521 when that answers None. The handler maps the
 * RuntimeError to a 500 whose detail is "Face embedding extraction failed:
 * {e}" (:719-722). The handles are None here because the two pinned weights are
 * not in this image: models.yml:148-173 declares face-detector-scrfd
 * (scrfd_10g_bnkps.onnx) and face-recognizer (w600k_r50.onnx) both at
 * `local_path: model-zoo/face-recognizer` with `download_method: skip` — an
 * operator unpacks the InsightFace buffalo_l zoo at deploy — and `/app/
 * model-zoo` does not exist on a feature-check stack. So the write path from
 * "click Enroll Face" through the shipped error surface IS executable here and
 * is asserted; the vector insert is not, and is reported as a blocked clause
 * with its wire proof (`POST /api/known-persons/1/enroll-from-detection
 * {"detection_id":"1"}` → 500 with exactly that detail).
 *
 * WHY THE 400 QUALITY ARM IS NOT WHAT THIS TIER PRODUCES. The hypothesis was
 * that the fake VLM's person detection yields the 400 "Face quality score (…)
 * is below minimum threshold" arm (face_recognition.py:734-738). It cannot:
 * that check sits AFTER extraction and after the all-None "no face found" arm
 * (:726-730), so it can only fire once the leg has produced a score — and the
 * leg never runs. The two arms are distinguishable in the user's own surface,
 * which is what both legs assert: the catch renders
 * `toast.error(\`Enrollment failed: ${message}\`)` (EnrollFaceModal.tsx:203-207)
 * and `message` is FastAPI's `detail` verbatim, because handleResponse rethrows
 * it as `new Error(errorMessage)` (useFaceRecognitionApi.ts:119-130, detail
 * read at :121-126). A run that asserted the 400 copy on this stack would be
 * asserting a branch the tier cannot reach. Two shipped negatives keep the leg
 * two-sided rather than "an error appeared": the person the modal created is
 * still there with `embedding_count: 0`, so the failed write stored no vector,
 * and the modal STAYS OPEN, because `onClose()` sits at :201 on the success
 * path only and the catch never closes it — the user keeps a retry.
 *
 * DATA SUPPLY, AND THE RESOURCE ARITHMETIC BEHIND THE IMAGE. The batch's own
 * fixture rows carry ZERO detections — POST /api/events/bulk builds `Event(...)`
 * and no Detection row (harness.ts:318-353 documents the route; events.py:1583
 * -1600) — and `hasPersonDetection` needs a `person` Detection, so for THIS row
 * the fake-VLM drop is not a preference, it is the only sanctioned supply that
 * produces the state the clause names. The image is `person-at-door`, chosen by
 * elimination over the book's other four: harness-smoke is claimed by BOTH
 * ./video-clip.spec.ts:131-136 and ../analytics-alerts/harness.ts:16-20,
 * cat-on-porch is F-054's (./event-detail-modal.spec.ts:214), car-in-driveway
 * is DO-1's (./download-media.spec.ts:104), and slow-reply is F-051's
 * (./live-socket-arrival.spec.ts:148) with a 40 s reply delay past this file's
 * patience. person-at-door is F2.1's image (../dashboard-drop.spec.ts:91-98)
 * and that claim has to be reasoned about, not waved at: its
 * `expect(items.length, …).toBe(1)` (../dashboard-drop.spec.ts:222) is a COUNT
 * on this very camera, taken at file position #14 of 99 while this file sits at
 * #91 of the same serial, single-worker project (playwright.config.ts:284-290),
 * so its count is taken before this file can drop anything. What this file must
 * not do is LEAVE a second row there, and the dedupe gate decides what leaving
 * means: the gate is stack-wide on the image's sha256 with a 300 s TTL and
 * nothing on the request path shortens it, so a drop inside the window yields
 * NO row and a drop outside it yields one more row than the camera had. Hence
 * the invariant beforeAll/afterAll hold, stated because run 2 is judged on it:
 * THIS FILE LEAVES THAT CAMERA HOLDING EXACTLY ONE EVENT. If it found zero and
 * its drop produced one, that row stays — deleting it would leave the next run
 * inside the window with no supply at all, the exact failure
 * ./download-media.spec.ts:475-479 names ("a re-run inside the 300 s TTL after a
 * purge is exactly this failure"); if it found one or more and its drop produced
 * a new row, the new row is deleted and the pre-existing one is left alive,
 * untouched. A row this run cannot attribute to itself is never purged, and the
 * tests never depend on who made the row — only on the detection it carries.
 *
 * THE NEGATIVE CONTROL'S SUPPLY IS THE HARNESS'S OWN BUILDER. Leg 3's
 * detection-less event comes from `createDetailFixture` (harness.ts:908-940) on
 * `fe3-detail-probe`: sanctioned supply, already waiting on the 60 s camera-list
 * cache-aside (`waitForCameraInList`) that a `?camera=` deep link needs. That
 * builder purges its own camera's residue before seeding and this file
 * hard-deletes exactly the ids it created afterwards, which is the state that
 * camera is in before file #81 anyway; nothing after #91 reads it
 * (./timeline-scrubber.spec.ts, ./timeline-search.spec.ts,
 * ./video-clip.spec.ts and webhooks/* were grepped — every event read they make
 * is `camera_id=`-scoped to a camera of their own).
 *
 * THE API BUCKET, AND THE ONE PLACE A SHED 500 CAN BE MISREAD AS A PASS.
 * frontend/nginx.conf:24 (zone api, rate=10r/s burst=20 nodelay) sheds boot
 * traffic, and a proxied request that the bucket rejects never reaches gunicorn:
 * the client gets 429 with nginx's HTML body, so the app's
 * `errorBody.detail` read throws and handleResponse falls back to
 * `HTTP 429: Too Many Requests` (useFaceRecognitionApi.ts:120-128) — text that
 * would satisfy an `Enrollment failed:` matcher while proving nothing about the
 * face leg. So the click never fires on a freshly-booted page: leg 1 and leg 2
 * each settle for a full burst refill after their boot (BOOT_QUIET_MS,
 * harness.ts:195, the harness's own refill figure) and then assert the SERVER's
 * cause inside the toast, not just the toast's prefix. If a run ever reports
 * green here with the 429 fallback text, it is a shed, not a pass.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  BOOT_QUIET_MS,
  adminSession,
  api,
  apiWrite,
  closedByGuard,
  createDetailFixture,
  hardDeleteFixtureRows,
  loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedDefaultViewMode,
  seedTourDismissed,
  waitForEventCards,
  type DetailFixture,
  type Session,
  type TimelineHarness,
} from './harness';

/* -------------------------------------------------------------------------- */
/* Collection-time readiness. Playwright runs COLLECTION before any runtime    */
/* skip, so every env read goes through the harness's defensive reader: a      */
/* missing env is a SKIP reason, never a collection crash. That skip is the    */
/* ONLY sanctioned one in this file and it must not fire on a green run.       */
/* -------------------------------------------------------------------------- */
const h = readTimelineHarness();
test.skip(!h.ready, h.ready ? '' : h.why);
const harness = h as TimelineHarness;

/** The book's only fast `person` row that no later golden file claims. */
const SCENARIO = 'person-at-door';
/** The affordance's shipped copy (EventDetailModal.tsx:843). */
const ENROLL_BUTTON_TEXT = 'Add Face to Known Persons';
/** The primary button's shipped label (EnrollFaceModal.tsx:536). */
const PRIMARY_LABEL = 'Enroll Face';
/** face_recognition.py:720 wraps the loader's :519-521 cause in this prefix. */
const WEIGHTS_UNAVAILABLE = 'the pinned face weights are not loaded';
/** Every person this file creates carries this prefix, so afterAll cleans up by
 *  prefix and a re-run starts from its own rows only. */
const PERSON_PREFIX = 'FE3 F-064';
const RUN_SALT = Date.now();
const NEW_PERSON_NAME = `${PERSON_PREFIX} New ${RUN_SALT}`;
const CONTRACT_PERSON_NAME = `${PERSON_PREFIX} Contract ${RUN_SALT}`;

/** Four up from frontend/tests/golden/timeline — the F2.1 spec's recipe is
 *  three up because it sits one level shallower (../dashboard-drop.spec.ts:126). */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

interface BookScenario {
  name: string;
  image: string;
  detections: { class: string; confidence: number }[];
  verdict: { verdict: string; risk_score: number; summary: string };
  reply_delay_seconds?: number;
}

interface KnownPerson {
  id: number;
  name: string;
  is_household_member: boolean;
  notes: string | null;
  embedding_count: number;
  created_at: string;
  updated_at: string;
}

interface KnownPersonPage {
  items: KnownPerson[];
  total: number;
}

interface EventRow {
  id: number;
  camera_id: string;
  summary: string | null;
  risk_score: number | null;
  detection_count: number | null;
  /** Measured on the live API: every event row carries its detection ids. */
  detection_ids: number[] | null;
  verification: { verdict: string } | null;
}

interface EventPage {
  items: EventRow[];
}

interface DetectionRow {
  id: number;
  camera_id: string;
  file_path: string | null;
  object_type: string | null;
  confidence: number | null;
}

interface DetectionPage {
  items: DetectionRow[];
}

/** The drop's camera, read from the stack's own camera map. */
let cameraId = '';
/** The event the legs deep-link: on that camera, the newest row carrying a
 *  detection. Which run created it is irrelevant to every assertion below. */
let eventId = 0;
/** Rows this run can prove it made, and therefore may delete. */
let purgeEventIds: number[] = [];
let detailFixture: DetailFixture | null = null;

function readBook(): { dir: string; scenarios: BookScenario[] } {
  const bookPath = String(process.env.FEATURE_CHECK_SCENARIOS);
  const parsed = JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios: BookScenario[] };
  return { dir: path.dirname(bookPath), scenarios: parsed.scenarios };
}

/** The stack's camera map: feature-check seeds one camera per book row and
 *  folds dashes (scripts/feature_check.py:2093 seed_cameras); the held-stack
 *  generator writes the same mapping to $FEATURE_CHECK_CAMERAS. */
function cameraIdFor(scenario: string): string {
  const mapPath = process.env.FEATURE_CHECK_CAMERAS;
  if (mapPath && existsSync(mapPath)) {
    const map = JSON.parse(readFileSync(mapPath, 'utf8')) as Record<string, string>;
    const fromMap = map[scenario];
    if (typeof fromMap === 'string' && fromMap.length) return fromMap;
  }
  return scenario.replace(/-/g, '_');
}

/** feature-check's own drop contract — the same call
 *  ../dashboard-drop.spec.ts:184-193 and ./live-socket-arrival.spec.ts:209-215
 *  make, so a folder-layout change cannot silently split from the documented
 *  form. */
function dropScenario(imagePath: string, camera: string): void {
  execFileSync(path.join(repoRoot, 'scripts/feature-check.sh'), ['drop', imagePath, camera], {
    cwd: repoRoot,
    env: {
      ...process.env,
      FEATURE_CHECK_CAMERA_ROOT: String(process.env.FEATURE_CHECK_CAMERA_ROOT),
    },
    encoding: 'utf8',
    timeout: 30_000,
  });
}

async function eventsOnCamera(session: Session): Promise<EventRow[]> {
  const body = await api<EventPage>(
    harness,
    session,
    `/api/events?limit=50&camera_id=${encodeURIComponent(cameraId)}`
  );
  return body.items ?? [];
}

async function detectionsOnCamera(session: Session): Promise<DetectionRow[]> {
  const body = await api<DetectionPage>(
    harness,
    session,
    `/api/detections?camera_id=${encodeURIComponent(cameraId)}&limit=100`
  );
  return body.items ?? [];
}

async function knownPersons(session: Session): Promise<KnownPerson[]> {
  const body = await api<KnownPersonPage>(harness, session, '/api/known-persons');
  return body.items ?? [];
}

/** The server's own row for a name this file chose. The cardinality check is
 *  part of the readback: two rows with one name means the modal's create ran
 *  twice (EnrollFaceModal.tsx:181), which is a shipped-behaviour failure. */
async function personByName(session: Session, name: string): Promise<KnownPerson | null> {
  const found = (await knownPersons(session)).filter((p) => p.name === name);
  expect(
    found.length,
    `at most one server row bears the name "${name}" — two means the modal's ` +
      `create mutation ran twice (EnrollFaceModal.tsx:181)`
  ).toBeLessThanOrEqual(1);
  return found[0] ?? null;
}

/** The enroll modal's own subtree — a SCOPE only. See the header: its
 *  role=dialog wrapper has a zero-height box, so visibility is never asked of
 *  it; `enrollTitle` is the visible marker. */
function enrollDialog(page: Page) {
  return page
    .getByRole('dialog')
    .filter({ has: page.getByRole('heading', { name: 'Enroll Face' }) });
}

/** The shipped Dialog.Title inside the panel — the modal's visible marker
 *  (EnrollFaceModal.tsx:259-261), and the only element whose presence proves
 *  the panel painted. */
function enrollTitle(page: Page) {
  return page.getByRole('heading', { name: 'Enroll Face' });
}

/** The enroll button INSIDE the modal. Its label is `isPending ? 'Enrolling...'
 *  : 'Enroll Face'` (:536), so this stops matching during the in-flight state —
 *  which is why no leg waits on it for a completion signal. */
function enrollSubmit(page: Page) {
  return enrollDialog(page).getByRole('button', { name: PRIMARY_LABEL, exact: true });
}

/** The shipped failure toast (EnrollFaceModal.tsx:204). */
function failureToast(page: Page) {
  return page.locator('[data-sonner-toast]').filter({ hasText: 'Enrollment failed:' });
}

/** A detection's stored file as this sandbox sees it. The stack bind-mounts its
 *  camera root at the container path the API reports (compose.json renders
 *  `source: <run>/cameras → target: /cameras`, and scripts/feature_check.py:88
 *  `CAMERA_TARGET = "/cameras"` is the same constant), so the mapped path is a
 *  byte-for-byte view of what the backend's `image_path.exists()` sees.
 *
 *  WHY THE SPEC CARES WHETHER THE BYTES EXIST: it decides WHICH shipped arm
 *  enroll_from_detection takes, and the two are not interchangeable. A
 *  detection whose file is gone short-circuits inside the extractor at
 *  face_recognition.py:513-515 (`return None, None, None`) and the route turns
 *  that into the 400 "No face found…" at :726-731. A detection whose bytes are
 *  live reaches the face leg and raises the RuntimeError at :517-523, which the
 *  route maps to the 500 "Face embedding extraction failed: …" at :719-723. A
 *  picker that took any detection-carrying row could land on either, and a
 *  green run would not say which behaviour it proved — so the picker selects on
 *  liveness and the legs below assert the 500 specifically. */
function detectionBytesLive(d: DetectionRow): boolean {
  const root = process.env.FEATURE_CHECK_CAMERA_ROOT;
  const fp = d.file_path ?? '';
  if (!root || !fp.startsWith('/cameras/')) return false;
  return existsSync(root + fp.slice('/cameras'.length));
}

/** Poll until the camera holds a `person` detection whose stored file is the
 *  book image AND whose bytes are live. Liveness is not a nicety here: this
 *  run's own drop rewrites those bytes even when the dedupe gate swallows the
 *  event (measured: the file reappears with no new row), so waiting for a live
 *  file is what makes the ENROLL arm this spec asserts reproducible. A drop
 *  that neither landed nor restored the file fails loudly, naming the TTL. */
async function waitForPersonDetection(session: Session, timeoutMs: number): Promise<DetectionRow> {
  const suffix = `${SCENARIO}/${SCENARIO}.jpg`;
  const deadline = Date.now() + timeoutMs;
  let seen = 'no detection stored under that path at all';
  while (Date.now() < deadline) {
    const onFile = (await detectionsOnCamera(session)).filter((d) =>
      (d.file_path ?? '').endsWith(suffix)
    );
    const person = onFile.find(
      (d) => (d.object_type ?? '').includes('person') && detectionBytesLive(d)
    );
    if (person) return person;
    if (onFile.length) {
      seen = `the detections under that path carry object_type [${onFile
        .map((d) => d.object_type)
        .join(', ')}] and live bytes [${onFile.map((d) => detectionBytesLive(d)).join(', ')}]`;
    }
    await new Promise((r) => setTimeout(r, 5_000));
  }
  throw new Error(
    `golden fixture: no event on camera ${cameraId} stores a LIVE person detection ending ` +
      `${suffix} within ${timeoutMs}ms — ${seen}. The drop neither landed nor restored the ` +
      'file (a re-run inside the 300 s sha256 TTL after a purge is exactly this failure)'
  );
}

/** Boot into the detail modal of `id` the way a deep link does. Deliberately
 *  ONE navigation per boot and ONE click per boot afterwards: see the bucket
 *  note in the header. */
async function bootIntoDetail(page: Page, id: number, camera: string): Promise<Session> {
  const session = await adminSession(harness);
  await seedTourDismissed(page);
  await seedDefaultViewMode(page);
  await loginAsAdmin(page, harness);
  await quietBoot(page, harness, `/timeline?camera=${encodeURIComponent(camera)}&event=${id}`);
  await expect(page.getByTestId('timeline-page')).toBeVisible();
  await waitForEventCards(page);
  await expect(
    page.getByTestId('event-detail-modal'),
    'the deep link opens the event detail modal (:582-584)'
  ).toBeVisible();
  return session;
}

/** Click the affordance the row names and wait for the modal's own title. The
 *  affordance pair below IS the clause's first verb asserted on the shipped DOM. */
async function openEnrollModal(page: Page): Promise<void> {
  const button = page.getByTestId('enroll-face-button');
  await expect(button, 'the affordance renders on a person detection (:833)').toBeVisible();
  await expect(button, 'and carries the row copy verbatim (:843)').toHaveText(ENROLL_BUTTON_TEXT);
  await button.click();
  await expect(
    enrollTitle(page),
    'the enroll modal painted (asserted on Dialog.Title, :259-261 — see the header)'
  ).toBeVisible();
  await expect(
    enrollDialog(page).getByRole('radio', { name: 'Add to existing person' }),
    'and opens on the existing-person mode (:114)'
  ).toBeChecked();
}

/** Drain one full burst refill before an in-test click: the boot that just
 *  happened consumed tokens, and a bucket-rejected POST never reaches gunicorn
 *  (header: a shed click would still produce an `Enrollment failed:` toast). */
async function refillBurst(page: Page): Promise<void> {
  await page.waitForTimeout(BOOT_QUIET_MS);
}

test.describe('F-064 event detail › add face to known persons', () => {
  test.beforeAll(async () => {
    // Drop + fake-VLM verdict + the detail fixture is real work; inside
    // beforeAll this sets the HOOK's timeout (the shape
    // ./download-media.spec.ts:449-451 uses).
    test.setTimeout(420_000);
    const book = readBook();
    const scenario = book.scenarios.find((s) => s.name === SCENARIO);
    const imagePath = path.join(book.dir, String(scenario?.image ?? ''));
    cameraId = cameraIdFor(SCENARIO);
    if (!existsSync(imagePath)) {
      throw new Error(`scenario book has no image for ${SCENARIO} at ${imagePath}`);
    }

    // THE EMPTY-TABLE PRECONDITION IS WHOLE-TABLE, SO THE DRAIN IS WHOLE-TABLE.
    // Leg 1's clause is "the persons table is empty, and the modal says so" —
    // and the shipped branch tests the length of the ENTIRE list
    // (EnrollFaceModal.tsx:362 `(personsQuery.data?.length ?? 0) === 0`), not
    // the count of this file's rows. Any other row anywhere — a lane-mate's
    // leftover, or one of this file's own whose afterAll DELETE was shed by the
    // api bucket and whose `.catch` swallowed the failure — makes the clause
    // unrenderable. Measured on both sides, not feared: a held-stack run failed
    // leg 1's empty-copy assertion with the dialog's PICKER branch on screen
    // (its aria snapshot: dialog "Enroll Face" -> button "Select Person"), on a
    // browser GET /api/known-persons the nginx access log recorded at 192 B
    // (one row). Read logged numbers as WIRE bytes, not body bytes: the access
    // line is formatted with $body_bytes_sent by the frontend IMAGE's base
    // config (baked at /etc/nginx/nginx.conf — not this repo's file, which
    // nginx includes only as a server block), and this repo's file turns gzip
    // on for application/json (:92-95, no gunzip), so the SAME empty envelope —
    // raw body exactly {"items":[],"total":0}, 22 B — logs 22 B to an
    // `Accept-Encoding: identity` client and 64 B to a gzip browser. Witnessed
    // boots logged the list `200 64` = EMPTY, then the low 190s after the
    // create (192-195: one row's JSON drifts a byte or two with the salted
    // name). Both empty readings sit well below every one-row reading, so the
    // drain's premise holds under either encoding, and the re-read below
    // asserts the drained state as a shipped fact (the route returns
    // total=len(items), backend/api/routes/face_recognition.py:132).
    // Why draining the whole table is legitimate here and a no-op on CI, three
    // checks: (1) the golden project is workers=1/fullyParallel=false and runs
    // cases in file order (playwright.config.ts:289-290), and `identity/` sorts
    // before `timeline/`; (2) the only spec in the corpus that creates persons
    // is identity/persons.spec.ts — identity/household.spec.ts writes
    // /api/household/members, not known-persons, and identity/harness.ts names
    // the endpoint only in prose — and persons.spec.ts deletes its own row in
    // each test's finally and asserts the table EMPTY at its :147, so it leaves
    // nothing; (3) the tier that runs THIS file is the fake one, which seeds no
    // persons at all (scripts/feature_check.py:3039-3041 calls seed_cameras()
    // always and gates the person seed behind `if … seeded`), and the seeded
    // tier runs a DIFFERENT project entirely — scripts/feature_check.py:2345
    // `project_name = "golden-seeded" if self.seeded else "golden"` — so this
    // spec cannot execute there and cannot delete the seeded tier's
    // 'Seeded Known Person'. Nothing under timeline/ or in any later directory
    // reads the table, so the drain desyncs no expectation; it exists to
    // neutralise residue on a manually-held stack, which is what a re-run
    // witness pair has to be reproducible on.
    const session = await adminSession(harness);
    const residue = await knownPersons(session);
    for (const p of residue) {
      await apiWrite<unknown>(harness, session, 'DELETE', `/api/known-persons/${p.id}`);
    }
    const drained = await knownPersons(session);
    expect(
      drained,
      `the persons table must be drained to empty before leg 1 boots — ` +
        `${drained.length} row(s) survived the drain: ${drained.map((p) => p.name).join(', ')}. ` +
        `Leg 1's empty-copy clause is a whole-table property (:362), so residue ` +
        `from ANY writer reddens it, not just this file's`
    ).toHaveLength(0);

    // Sanctioned supply, with the count invariant the header works out: this
    // camera leaves this file holding exactly one event whatever the gate does.
    const before = await eventsOnCamera(session);
    const beforeIds = new Set(before.map((e) => e.id));
    dropScenario(imagePath, SCENARIO);
    await waitForPersonDetection(session, 200_000);

    const after = await eventsOnCamera(session);
    const created = after.filter((e) => !beforeIds.has(e.id));
    purgeEventIds = created.map((e) => e.id);

    // SELECT an event whose detection's bytes are live, not merely "an event
    // with a detection". The route's two failure arms are different shipped
    // behaviour and only one of them is this row's face leg — see
    // detectionBytesLive. `detection_ids` on the event row is the shipped join.
    const livePersons = new Set(
      (await detectionsOnCamera(session))
        .filter((d) => (d.object_type ?? '').includes('person') && detectionBytesLive(d))
        .map((d) => d.id)
    );
    const carrying = after.filter((e) => (e.detection_ids ?? []).some((id) => livePersons.has(id)));
    expect(
      carrying.length,
      `camera ${cameraId} must hold an event whose person detection still has its file on disk — ` +
        `the drop is the only supply that writes Detection rows at all (bulk builds none: ` +
        `bulk_create_events constructs Event rows only, events.py:1553,:1599-1609), and this run's ` +
        `drop rewrites the file even when the dedupe gate swallows the event`
    ).toBeGreaterThan(0);
    eventId = Math.max(...carrying.map((e) => e.id));

    // The negative control's rows: the harness's own detection-less fixture,
    // whose camera is already in the 60 s cached camera list.
    detailFixture = await createDetailFixture(harness, session);
  });

  test.afterAll(async () => {
    if (!h.ready) return;
    const session = await adminSession(harness).catch(() => null);
    if (!session) return;
    // Persons this file created, by the prefix only this file uses.
    const persons = (await knownPersons(session).catch(() => [] as KnownPerson[])).filter((p) =>
      p.name.startsWith(PERSON_PREFIX)
    );
    for (const p of persons) {
      await apiWrite<unknown>(harness, session, 'DELETE', `/api/known-persons/${p.id}`).catch(
        () => undefined
      );
    }
    // A second event on the drop camera, and only one this run can attribute to
    // itself — F2.1's exactly-one count lives upstream of this file.
    if (purgeEventIds.length) {
      await hardDeleteFixtureRows(harness, session, purgeEventIds);
    }
    // And the negative control's fixture, which this run seeded from scratch.
    if (detailFixture) {
      await hardDeleteFixtureRows(harness, session, detailFixture.eventIds);
    }
  });

  test('clicks the affordance, creates a person, and hits the face leg the fake tier cannot run', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);

    const session = await bootIntoDetail(page, eventId, cameraId);
    await openEnrollModal(page);
    const dialog = enrollDialog(page);

    // The shipped empty-persons branch (:362-365). This is a real judgement on
    // this stack's real state (the persons table starts empty; leg 2 boots with
    // one row and asserts the Listbox INSTEAD), and it is load-bearing for leg
    // 2's negative control: if this branch could render when the table is
    // non-empty, leg 2's "the selector exists" would prove nothing.
    await expect(
      dialog.getByText('No known persons available. Create a new person instead.'),
      'with an empty persons table the modal says so instead of rendering a picker (:362-365)'
    ).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: 'Select Person' }),
      'and there is no person selector to pick from (:367-384 is the other branch)'
    ).toHaveCount(0);

    // The derived score: the host passes detection confidence as qualityScore
    // (EventDetailModal.tsx:1384) and the widget renders (score*100)%
    // (FaceQualityAssessment.tsx:121,:125). Two-sided — a host that stopped
    // passing the confidence would render the 0.85 fallback as 85%.
    await expect(
      dialog.getByTestId('quality-overall-score'),
      'the modal reports the detection confidence as the enrollment quality'
    ).toContainText('91%');

    // canEnroll's new-mode arm (:150-159): a trimmed-empty name cannot enroll.
    const modeNew = dialog.getByRole('radio', { name: 'Create new person' });
    await modeNew.click();
    await expect(modeNew, 'mode moved to create-new (:338)').toBeChecked();
    await expect(
      enrollSubmit(page),
      'the primary label is the shipped copy and it is gated (:528-537)'
    ).toBeVisible();
    await expect(enrollSubmit(page), 'an empty name cannot enroll (:158)').toBeDisabled();

    await dialog.locator('#person-name').fill(NEW_PERSON_NAME);
    await dialog.getByRole('checkbox', { name: 'Is household member' }).check();
    await expect(enrollSubmit(page), 'a named person can enroll (:158)').toBeEnabled();
    await refillBurst(page);
    await enrollSubmit(page).click();

    // The shipped error branch: toast.error(`Enrollment failed: ${message}`)
    // (:203-207) carrying FastAPI's detail verbatim
    // (useFaceRecognitionApi.ts:120-128). Asserted on the SERVER's cause, not
    // merely the prefix, because a bucket-shed click would produce the prefix
    // with nginx's "HTTP 429: Too Many Requests" fallback text instead.
    const toast = failureToast(page);
    await expect(toast, 'the write reports the shipped failure copy').toBeVisible({
      timeout: 30_000,
    });
    await expect(
      toast,
      'and names the server cause: the pinned face weights are not loaded ' +
        '(face_recognition.py:517-521 raised; :719-722 maps it to a 500)'
    ).toContainText(WEIGHTS_UNAVAILABLE);

    // READBACK of the row the click created. handleEnroll posts the create
    // FIRST (:181-188), so the person exists even though the enroll failed; the
    // fields below are the server's own, not the response body's.
    const created = await personByName(session, NEW_PERSON_NAME);
    expect(created, 'the modal created the person the row names ("creates a person")').toBeTruthy();
    expect(created?.name, 'with the typed name, trimmed (:182)').toBe(NEW_PERSON_NAME);
    expect(created?.is_household_member, 'the checkbox reached the POST body (:183)').toBe(true);
    expect(created?.embedding_count, 'a failed enroll stored no vector (:125)').toBe(0);

    // The create/read/delete contract on the wire — the same requests the modal
    // asks. create_known_person answers 201 with embedding_count hardcoded 0
    // (face_recognition.py:137-170, :166); GET reads it back (:172-206); DELETE
    // answers 204 (:254-275).
    const posted = await apiWrite<KnownPerson>(harness, session, 'POST', '/api/known-persons', {
      name: CONTRACT_PERSON_NAME,
      is_household_member: false,
      notes: null,
    });
    expect(posted.name, 'POST /api/known-persons answers the row it made').toBe(
      CONTRACT_PERSON_NAME
    );
    expect(posted.embedding_count, 'a fresh person carries zero embeddings (:166)').toBe(0);
    const fetched = await api<KnownPerson>(harness, session, `/api/known-persons/${posted.id}`);
    expect(fetched.id, 'and GET /api/known-persons/{id} reads the same row back').toBe(posted.id);
    expect(fetched.name, 'with the same fields').toBe(CONTRACT_PERSON_NAME);
    await apiWrite<unknown>(harness, session, 'DELETE', `/api/known-persons/${posted.id}`);
    const afterDelete = await knownPersons(session);
    expect(
      afterDelete.some((p) => p.id === posted.id),
      'DELETE /api/known-persons/{id} removed it (:254-275)'
    ).toBe(false);

    // The modal survives the failure so the user keeps a retry (onClose is
    // success-path only, :201), and Cancel is the way out.
    await expect(
      enrollTitle(page),
      'a failed enroll does not close the modal (:201 is the success path only)'
    ).toBeVisible();
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(enrollTitle(page), 'Cancel closes it (:520-525)').toBeHidden();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('picks an existing person, and the pick is what the enroll request targets', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(150_000);

    const session = await adminSession(harness);
    const picked = await personByName(session, NEW_PERSON_NAME);
    expect(
      picked,
      'leg 1 must have left the person it created — afterAll deletes it, not this leg'
    ).toBeTruthy();
    const untouched = { updated_at: picked?.updated_at, embedding_count: picked?.embedding_count };

    // A fresh boot, because leg 1's page booted against an empty persons table
    // and the query is staleTime-pinned (useFaceRecognitionApi.ts:390-396): the
    // list this modal renders comes from the GET its own boot made.
    await bootIntoDetail(page, eventId, cameraId);
    await openEnrollModal(page);
    const dialog = enrollDialog(page);

    // The mirror of leg 1's empty branch: with one row on the server, the
    // selector renders and the empty copy does not.
    await expect(
      dialog.getByRole('button', { name: 'Select Person' }),
      'the Listbox.Button renders once a person exists (:376-384)'
    ).toBeVisible();
    await expect(
      dialog.getByText('No known persons available. Create a new person instead.'),
      'and the empty-table copy is gone (:362-365 is the other branch)'
    ).toHaveCount(0);

    // canEnroll's existing-mode arm (:154-156): nothing selected yet, so the
    // primary is disabled BEFORE the pick and enabled after it.
    await expect(enrollSubmit(page), 'an unselected person cannot enroll (:155)').toBeDisabled();

    await dialog.getByRole('button', { name: 'Select Person' }).click();
    const option = page.getByRole('option').filter({ hasText: NEW_PERSON_NAME });
    await expect(
      option,
      'the person this row created is an option, labelled by its name (:413-437)'
    ).toBeVisible();
    await expect(option, 'and it is selectable, i.e. not at MAX_EMBEDDINGS (:414)').toBeEnabled();
    await option.click();
    await expect(
      dialog.getByRole('button', { name: 'Select Person' }),
      'the selection lands in the button, which renders selectedPerson.name (:379-381)'
    ).toContainText(NEW_PERSON_NAME);
    await expect(enrollSubmit(page), 'a picked person satisfies canEnroll (:155)').toBeEnabled();

    // Clicking with a PICKED person is the clause's second verb, and it is
    // proved by the request it makes: had the pick not reached the body,
    // handleEnroll returns at :188 and NOTHING happens — no toast at all.
    // So the shipped failure toast is positive evidence the picked id was sent.
    const personsBefore = await knownPersons(session);
    await refillBurst(page);
    await enrollSubmit(page).click();
    const toast = failureToast(page);
    await expect(
      toast,
      'the picked person was sent to enroll-from-detection (no pick ⇒ no request ⇒ no toast)'
    ).toBeVisible({ timeout: 30_000 });
    await expect(toast, 'and the server refused it for the weights cause').toContainText(
      WEIGHTS_UNAVAILABLE
    );

    // Controls: the write targeted the picked person instead of minting
    // another, and the targeted row is exactly as leg 1 left it. That last
    // check has teeth because useEnrollFace's onSuccess invalidates
    // knownPerson(personId) (useFaceRecognitionApi.ts:508-513) — a retargeted or
    // retried write would have moved the server's updated_at or the count.
    const personsAfter = await knownPersons(session);
    expect(
      personsAfter.length,
      'picking an existing person must not mint a second one (mode stayed existing)'
    ).toBe(personsBefore.length);
    const stillPicked = await api<KnownPerson>(
      harness,
      session,
      `/api/known-persons/${picked?.id}`
    );
    expect(stillPicked.name, 'the targeted person is still the same row').toBe(NEW_PERSON_NAME);
    expect(stillPicked.embedding_count, 'and gained no embedding on a failed enroll (:203)').toBe(
      untouched.embedding_count
    );
    expect(stillPicked.updated_at, 'and its server timestamp did not move').toBe(
      untouched.updated_at
    );

    await expect(
      enrollTitle(page),
      'the modal stayed open for a retry (:201 is the success path only)'
    ).toBeVisible();
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(enrollTitle(page), 'Cancel closes it').toBeHidden();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('no person detection, no affordance: the gate is hasPersonDetection (EventDetailModal.tsx:833)', async ({
    page,
  }) => {
    test.info().skip(!h.ready, h.ready ? '' : h.why);
    if (!h.ready) return;
    test.setTimeout(120_000);
    const fixture = detailFixture;
    expect(fixture, 'beforeAll seeded the detection-less fixture').toBeTruthy();

    await bootIntoDetail(page, Number(fixture?.eventIds[0]), String(fixture?.cameraId));

    // The clause's negative half. This event is real, its modal is open, and it
    // carries no Detection rows at all — so an absent affordance here is a
    // judgement about :833, not about a page that never rendered. The content
    // assertion below is what makes the count meaningful.
    await expect(
      page.getByTestId('enroll-face-button'),
      'an event with no person detection must not offer enrollment (:833)'
    ).toHaveCount(0);
    await expect(
      page.getByTestId('ai-analysis-section'),
      'the modal itself rendered its content, so the count above is not a dead page'
    ).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
