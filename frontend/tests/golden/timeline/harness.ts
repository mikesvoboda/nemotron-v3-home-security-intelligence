/**
 * Shared plumbing for the FE-3 timeline golden paths (F2.3, ruling 87;
 * claim #7049; rows F-043, F-045–F-049, F-052–F-054, F-056–F-057, F-059–F-062,
 * F-064).
 *
 * Fourth sibling of ../shell/harness.ts (FE-1), ../dashboard/harness.ts (FE-2)
 * and the ops batches: the same unmocked contract (`guard.ts` enforces it from
 * the interception call itself, UR-127), the same collection-time rule —
 * Playwright runs COLLECTION before any runtime skip, so every env read is
 * defensive and returns {ready:false} instead of throwing, and each spec
 * self-skips at body top. It does NOT import a sibling's copy: ruling 87 keeps
 * each batch's files inside its own area dir so two lanes' PRs never depend on
 * each other's merge. The duplication is the price of the file rule, same as
 * FE-1 and FE-2 paid it (`../dashboard/harness.ts:1-17` records the same
 * reasoning).
 *
 * What the timeline adds over the dashboard's data-mirror shape: these rows are
 * INTERACTION rows. The dashboard renders what an API answers; the timeline
 * lets the user change state (review a batch, save notes, export, add a face)
 * and then must SHOW that change. So this harness exports the Node-side
 * ground-truth read (`api`, a real response from the same stack) AND
 * `apiWrite`, its real write twin, so a spec can drive a mutation the way the
 * UI's own button does and then compare the DOM against a fresh read of the
 * same row. A pass means the shipped chain works; a red names the endpoint or
 * widget that broke. Nothing here mocks: `guard.ts` throws if a spec tries.
 *
 * The boot/shed machinery below is copied from ../dashboard/harness.ts because
 * the cause is stack-wide, not page-specific: frontend/nginx.conf:24 publishes
 * `zone=api rate=10r/s burst=20 nodelay`, and a golden run drives ONE client IP
 * (the golden project is one worker, serial), so every spec's boot drains the
 * same bucket. A SHED boot does not render the page — it renders a "coat" (see
 * shedCoat), and a spec that judged its first expect() against a coat would
 * read like a feature failure. Measured on the probe stack; FE-2's regression
 * run (CI 38189450762) is the witness quoted there.
 */
import type { Page } from '@playwright/test';

const REQUIRED = [
  'FEATURE_CHECK_UI_URL',
  'FEATURE_CHECK_API_URL',
  'FEATURE_CHECK_ADMIN_USERNAME',
  'FEATURE_CHECK_ADMIN_PASSWORD',
] as const;

export interface TimelineHarness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

export type HarnessState = TimelineHarness | { ready: false; why: string };

/** Defensive by contract: a missing env is a SKIP reason, never a collection crash. */
export function readTimelineHarness(): HarnessState {
  const missing = REQUIRED.filter((name) => !process.env[name]);
  if (missing.length) return { ready: false, why: `missing ${missing.join(', ')}` };
  return {
    ready: true,
    api: String(process.env.FEATURE_CHECK_API_URL),
    ui: String(process.env.FEATURE_CHECK_UI_URL),
    admin: {
      username: String(process.env.FEATURE_CHECK_ADMIN_USERNAME),
      password: String(process.env.FEATURE_CHECK_ADMIN_PASSWORD),
    },
  };
}

export interface Session {
  name: string;
  value: string;
}

/** Real POST /api/auth/login — same field names and cookie handling as F2.1/FE-1/FE-2. */
export async function adminSession(h: TimelineHarness): Promise<Session> {
  const res = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (res.status !== 200) throw new Error(`admin login answered ${res.status}`);
  const pair = res.headers
    .getSetCookie()
    .map((c) => c.split(';')[0])
    .find((c) => c.includes('='));
  if (!pair) throw new Error('admin login set no session cookie');
  const i = pair.indexOf('=');
  return { name: pair.slice(0, i), value: pair.slice(i + 1) };
}

/**
 * Seed a real session cookie onto the UI origin (the cookie is genuine state
 * from a real login — the guard does not cover addCookies; see
 * ../dashboard-drop.spec.ts for the reasoning).
 */
export async function loginAsAdmin(page: Page, h: TimelineHarness): Promise<Session> {
  const session = await adminSession(h);
  const url = new URL(h.ui);
  await page.context().addCookies([
    {
      name: session.name,
      value: session.value,
      domain: url.hostname,
      path: '/',
      httpOnly: true,
      secure: url.protocol === 'https:',
      sameSite: 'Lax',
    },
  ]);
  return session;
}

/** GET with the session attached Node-side (ground-truth reads, never the UI origin). */
export async function api<T>(h: TimelineHarness, session: Session, path: string): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200) {
    throw new Error(`GET ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`);
  }
  return body as T;
}

/**
 * The write twin of `api`. Timeline rows mutate (reviewed, notes, feedback,
 * export, face enrollment), so a spec must be able to ask the SAME question the
 * button asks and read the row back. Deliberately un-opinionated about method
 * and status: the caller names the endpoint and asserts the contract, because a
 * harness that silently accepted a 4xx would hide the very bug these rows test.
 * A non-2xx THROWS with the body, so a spec red reads as "the route answered N"
 * rather than as a locator timeout.
 */
export async function apiWrite<T>(
  h: TimelineHarness,
  session: Session,
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  payload?: unknown
): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    method,
    headers: {
      Cookie: `${session.name}=${session.value}`,
      'Content-Type': 'application/json',
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status < 200 || res.status >= 300) {
    throw new Error(
      `${method} ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`
    );
  }
  return body as T;
}

/**
 * Seed the product tour's own completion/skip state before any navigation, so
 * the tour never runs over the timeline. Measured on the probe stack (FE-1,
 * documented in ../shell/harness.ts): a FRESH context boots ProductTour on
 * every route and its full-screen .react-joyride__overlay intercepts pointer
 * events — on /timeline it would sit over the very filter chips and cards the
 * F-043/F-048 paths click. The seed is the user's own stored state after
 * completing/skipping the tour, written via addInitScript so it exists before
 * the app boots. Whether the tour SHOULD start here is F-021's row, not ours.
 */
export async function seedTourDismissed(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem('nemotron-tour-completed', 'true');
    localStorage.setItem('nemotron-tour-skipped', 'true');
  });
}

/**
 * View mode is localStorage-backed: EventTimeline.tsx:115 reads
 * `useLocalStorage<ViewMode>('timeline-view-mode', 'grid')`. A spec that flips
 * to list view and then reloads inherits that state, which is exactly what the
 * persistence legs WANT; but a spec that never intends it must not inherit it
 * from a sibling that ran earlier in the same context. This clears only that
 * one key so each spec starts on the shipped default (grid).
 */
export async function seedDefaultViewMode(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.removeItem('timeline-view-mode');
  });
}

/**
 * Quiet (drain the shared nginx burst), then navigate. BOOT_QUIET_MS is FE-2's
 * measured constant (a boot lands ~18 /api requests; burst=20 refills at
 * 10 r/s), and the golden project's single worker over a single client IP means
 * the timeline pays the same price the dashboard measured.
 */
export const BOOT_QUIET_MS = 2_000;

/**
 * The ways a SHED boot renders instead of the timeline, read from the app's own
 * pixels. Two are app-wide and shared with FE-2; two are this page's own:
 *   • 'setup'  — a shed GET /api/auth/setup-status (AuthContext.tsx:137,
 *     `retry:false`) leaves setupRequired null WITH an error and the guard
 *     fail-closes to /setup (ProtectedRoute.tsx:79-80): heading "First Time Setup".
 *   • 'login'  — a shed current-user query (AuthContext.tsx:157-162) reads as
 *     unauthenticated → /login, heading "Welcome Back".
 *   • 'err429' — EventTimeline's own error branch replaces the list with
 *     "Error Loading Events" + the thrown message (EventTimeline.tsx:1637),
 *     which is where a shed /api/events lands. This is the coat that must never
 *     be judged as "the timeline shows no events".
 *   • 'empty'  — the shipped no-results branch (EventTimeline.tsx:1643-1648,
 *     EmptyState title "No Events Found"). NOT a shed coat: it is a real render
 *     of a real state, so settleBoot does not treat it as failure. It is
 *     exported separately so a spec can say "the page booted and has no events"
 *     in one read instead of racing a locator.
 */
async function shedCoat(page: Page): Promise<string | null> {
  if (
    await page
      .getByText('First Time Setup')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'setup';
  if (
    await page
      .getByText('Welcome Back')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'login';
  if (
    await page
      .getByText('Error Loading Events')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'err429';
  return null;
}

/** The shipped empty render, checked only when a boot has already failed to paint. */
export async function timelineShowsEmpty(page: Page): Promise<boolean> {
  return page
    .getByText('No Events Found')
    .first()
    .isVisible()
    .catch(() => false);
}

/**
 * After a navigation has been issued, wait for the timeline to PAINT, detecting
 * a shed coat instead of waiting out the full expect timeout. The paint marker
 * is `data-testid="timeline-page"` (EventTimeline.tsx:1093) — the page's own
 * root, present in grid, list and grouped modes alike, so it does not bias which
 * view mode a spec is about to assert.
 */
async function settleBoot(page: Page): Promise<'booted' | string | null> {
  return Promise.race([
    page
      .getByTestId('timeline-page')
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => 'booted' as const),
    (async () => {
      // Poll for a shed coat while the boot settles: whichever appears first
      // wins. Swallow ANY throw (a closed page after the race resolved is the
      // normal case) — this promise floats once timeline-page paints.
      try {
        for (let t = 0; t < 40; t++) {
          const coat = await shedCoat(page);
          if (coat) return coat;
          await page.waitForTimeout(500);
        }
      } catch {
        /* page gone / detached — the race already resolved or the drive ends */
      }
      return null;
    })(),
  ]);
}

/** Re-drive a navigation until the timeline paints (see settleBoot). */
async function driveUntilBooted(
  page: Page,
  label: string,
  navigate: () => Promise<void>
): Promise<void> {
  let lastCoat = 'no-shed-coat(page painted something else)';
  for (let drive = 1; drive <= 4; drive++) {
    await navigate();
    const painted = await settleBoot(page);
    if (painted === 'booted') return;
    lastCoat = painted ?? lastCoat;
    await page.waitForTimeout(4_000); // one burst refill (10 r/s → 20 tokens in 2 s)
  }
  throw new Error(
    `${label}: 4 drives, none painted timeline-page (last shed coat: ${lastCoat}) — ` +
      'the shared nginx api bucket (rate=10r/s burst=20, nginx.conf:24) shed every ' +
      'attempt; this is stack saturation, not a widget failure'
  );
}

/**
 * Quiet (drain the shared nginx burst), then navigate the UI origin and WAIT
 * FOR A BOOTED PAGE. Every golden timeline spec that reads rendered state boots
 * through here, because a coat makes the spec's FIRST expect() fail with a
 * locator error that reads like a FEATURE failure. A shed drive is re-driven
 * after one burst refill; a stack that never boots IS reported, naming the last
 * coat — saturation deserves a red, just not a misleading one.
 *
 * `path` defaults to the timeline; deep-link legs pass `?event=…`/`?camera=…`
 * (the row's own clause) and are judged on the SAME settled path.
 */
export async function quietBoot(page: Page, h: TimelineHarness, path = '/timeline'): Promise<void> {
  await driveUntilBooted(page, 'quietBoot', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
  });
}

/** A reload that settles like quietBoot (SAME url, so localStorage + cookies ride along). */
export async function settledReload(page: Page): Promise<void> {
  await driveUntilBooted(page, 'settledReload', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
  });
}

/* -------------------------------------------------------------------------- */
/* The batch's event fixture — measured, not assumed.                          */
/*                                                                             */
/* FE-3's rows are browse/mutation rows: they need EVENTS to show. The naive   */
/* premise ("events come only from the VLM pipeline, ruling 90, so an          */
/* event-less stack is the honest regime") is wrong in two ways, both measured: */
/*   1. CI's feature-check harness seeds CAMERAS ONLY (feature_check.py:2098   */
/*      → run.seed_cameras(); there is no event-seed step), so a golden stack   */
/*      really does boot with 0 events — an assertion that needs rows would be  */
/*      RED at CI head, not merely here. That is not a regime to skip past.     */
/*   2. The repo ships a sanctioned way to put rows in: ops-a's merged          */
/*      data-ui/trash-restore.spec.ts:91-93 documents it for exactly this case  */
/*      ("A fresh CI golden stack can boot with zero events, so the pool is     */
/*      guaranteed via POST /api/admin/seed/events"), and operations/audit.spec */
/*      .ts:37 seeds cameras the same way. FE-3 uses the narrower tool below.   */
/*                                                                             */
/* Why POST /api/events/bulk rather than the precedent's /api/admin/seed/events: */
/* seed_events picks a RANDOM camera among all (admin.py:513), so it can drop a */
/* row on the drop spec's scenario camera — whose assertion is                  */
/* `expect(items.length).toBe(1)` (dashboard-drop.spec.ts:222) and which counts */
/* events for ITS camera only. bulk names the camera (events.py:1543-1552) and */
/* needs no admin gate, so FE-3 stays surgical: one dedicated camera, all rows   */
/* on it, nothing else's counts touched.                                        */
/* -------------------------------------------------------------------------- */

/** The batch's own camera name; the backend derives the id from it (measured). */
export const FIXTURE_CAMERA_NAME = 'fe3-timeline-probe';

/**
 * Rows FE-3 creates. Deliberately FEWER THAN THE PAGE SIZE (limit 20,
 * EventTimeline.tsx:183): with total ≤ 20 the shipped infinite query never
 * fetches a second page, so an unfiltered DOM↔API mirror is exact. A fixture
 * over 20 would make page 2 load and the unfiltered mirror would then compare
 * 40 cards to 20 rows — a false red. Infinite scroll therefore stays
 * unverified by this batch's F-043 spec and is named in the PR body.
 */
export const FIXTURE_ROWS: ReadonlyArray<{ riskScore: number; riskLevel: string }> = [
  { riskScore: 91, riskLevel: 'critical' },
  { riskScore: 80, riskLevel: 'high' },
  { riskScore: 55, riskLevel: 'medium' },
  { riskScore: 22, riskLevel: 'low' },
  { riskScore: 12, riskLevel: 'low' },
  { riskScore: 8, riskLevel: 'low' },
];

interface CameraRow {
  id: string;
  name: string;
}
interface CameraListBody {
  items?: CameraRow[];
}
interface CameraCreated {
  id: string;
  name: string;
  /** Present on the route's 409, where the existing id travels (`ensureCamera`). */
  detail?: string;
}
interface BulkResult {
  index: number;
  status: string;
  id: number | null;
  error: string | null;
}
interface BulkBody {
  total: number;
  succeeded: number;
  failed: number;
  results: BulkResult[];
}

/**
 * A camera this file just created is INVISIBLE to `GET /api/cameras` for up to a
 * minute, and that is a backend cache contract rather than a UI bug — so FE-3
 * waits it out instead of pretending it isn't there. Measured twice at head
 * `82f79a4f4`, which is what turned CI's `Feature check (fake AI)` red here:
 *
 *  - CI's own artifact: `#camera-filter` reported `""` where the fixture id was
 *    expected, and the run's aria snapshot lists the select's ONLY options as
 *    the five cameras the harness seeds (`person-at-door … harness-smoke`, which
 *    is exactly what the run's own `cameras.json` names). The DOM faithfully
 *    reported the response it got.
 *  - the probe stack, by hand: prime `GET /api/cameras` → `POST /api/cameras`
 *    (201; `GET /api/cameras/{id}` answers 200 for it, `status:"online"`) → poll
 *    the plain list: absent for ~15 s, then present once the key's TTL expired.
 *
 * Why waiting is the only lever this batch has (each fact measured; the fix
 * would live in `backend/`, which ruling 87 keeps out of this PR):
 *  - `list_cameras` is cache-aside on a 60 s entry and a HIT never touches the DB
 *    (`cameras.py:194-217`; `SHORT_TTL = 60` at `cache_service.py:60`).
 *  - The camera invalidation cannot fire: `CacheKeys` bakes the *global* prefix
 *    into the key (`hsi:cache:cameras:list:all`, `cache_service.py:752-762`)
 *    while `invalidate_pattern` prepends only `cache:` to `"cameras:*"` (`:486`,
 *    `:577`), so the SCAN pattern can never match it. Confirmed against Redis in
 *    the probe stack: exactly one key, `cache:hsi:cache:cameras:list:all`. The
 *    same mismatch defeats the product's own escape hatch — `POST
 *    /api/admin/maintenance/clear-cache` answered `{"keys_cleared":0,
 *    "cache_types":[]}` and left that key sitting at `ttl=60`.
 *  - A cache hit does NOT refresh the TTL (`redis_cluster.py:316-333` is a bare
 *    GET), which is what makes a bounded poll converge instead of livelocking:
 *    the entry expires, the next read misses, and the refill comes from the DB,
 *    which already has the row.
 *
 * Cost: one extra GET on a stack that already has the camera (the first poll
 * passes); on a fresh stack, at most one TTL window, once per file. The wait must
 * happen BEFORE the boot because `useCamerasQuery` defaults `refetchInterval` to
 * `false` (`hooks/useCamerasQuery.ts:150`) — a page booted inside the window
 * never corrects itself, which is why the failure surfaced as a locator timeout
 * and not as a recoverable re-render.
 */
const CAMERA_LIST_WAIT_BUDGET_MS = 90_000; // > SHORT_TTL (60 s) + margin
const CAMERA_LIST_POLL_MS = 3_000;

export async function waitForCameraInList(
  h: TimelineHarness,
  session: Session,
  name: string
): Promise<void> {
  const deadline = Date.now() + CAMERA_LIST_WAIT_BUDGET_MS;
  let polls = 0;
  for (;;) {
    polls += 1;
    const list = await api<CameraListBody>(h, session, '/api/cameras');
    if ((list.items ?? []).some((cam) => cam.name === name)) return;
    if (Date.now() >= deadline) {
      throw new Error(
        `fixture: '${name}' never appeared in GET /api/cameras within ` +
          `${CAMERA_LIST_WAIT_BUDGET_MS}ms (${polls} polls). That list is a 60 s ` +
          `cache entry that is not converging — see waitForCameraInList's note: ` +
          `the stack's cache, not the timeline UI.`
      );
    }
    await new Promise((resolve) => setTimeout(resolve, CAMERA_LIST_POLL_MS));
  }
}

/**
 * Find FE-3's own camera by name, creating it when the stack has never seen it.
 *
 * A 409 is a ROUTINE outcome here, not a failure, and must never take the file
 * down: the list read below can be the stale cached answer above, so "not in the
 * list" does not mean "not in the DB". CI's red is exactly that sequence — a
 * retry POSTed the camera its first attempt had already created, died on
 * `Camera with name 'fe3-timeline-probe' already exists (id:
 * fe3_timeline_probe)`, and every remaining test in the file reported as
 * not-run. The id travels inside that 409's own `detail` (measured) and it is
 * the DB's id, so a conflict is parsed rather than thrown and then confirmed
 * against `GET /api/cameras/{id}` — which is NOT cache-aside (`cameras.py:683-
 * 720` reads the DB). A 409 whose detail cannot be parsed still fails loudly,
 * with the route's own body in the message.
 */
async function ensureCamera(
  h: TimelineHarness,
  session: Session,
  name: string,
  folderPath: string
): Promise<string> {
  const list = await api<CameraListBody>(h, session, '/api/cameras');
  const known = (list.items ?? []).find((cam) => cam.name === name);
  if (known) return known.id;

  // Deliberately NOT apiWrite: its documented contract is "a non-2xx THROWS",
  // and that contract is what makes other specs' failures name the endpoint.
  // Here a 409 is an EXPECTED answer, so this one call reads its own status and
  // every other non-2xx still surfaces with the route's body in the message.
  const res = await fetch(`${h.api}/api/cameras`, {
    method: 'POST',
    headers: {
      Cookie: `${session.name}=${session.value}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, folder_path: folderPath }),
  });
  const created = (await res.json().catch(() => null)) as CameraCreated | null;
  if (res.status >= 200 && res.status < 300) {
    const id = created?.id;
    if (!id) throw new Error(`fixture: POST /api/cameras for '${name}' 2xx had no id`);
    return id;
  }
  if (res.status !== 409) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered ${res.status}: ` +
        JSON.stringify(created).slice(0, 200)
    );
  }
  const detail = created?.detail ?? '';
  const found = detail.match(/already exists \(id: ([^)]+)\)/);
  const id = found ? found[1] : null;
  if (!id) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered 409 with an unparseable ` +
        `detail: ${detail.slice(0, 200)}`
    );
  }
  // Confirm the recovered id is real (an uncached read) before the file builds on it.
  await api<{ id: string }>(h, session, `/api/cameras/${encodeURIComponent(id)}`);
  return id;
}

export interface TimelineFixture {
  /** Backend-assigned id of FE-3's own camera (never hardcoded: derived). */
  cameraId: string;
  /** Ids of the rows this call created, in request order. */
  eventIds: number[];
  /** Every row currently on the fixture camera, from the same read a mirror uses. */
  rowsOnCamera: number;
}

/**
 * Give FE-3 a browse regime: one dedicated camera plus FIXTURE_ROWS events on
 * it. Idempotent by design — a re-run against a dirty dev stack finds the
 * existing camera instead of tripping its name-unique 409 (measured:
 * `Camera with name '…' already exists (id: …)`), and each call adds rows with
 * fresh batch ids.
 *
 * Measured contracts this helper depends on (all probed against the lane's
 * probe stack, not read off a doc):
 *  - POST /api/cameras accepts {name, folder_path} alone and does NOT probe the
 *    folder on disk (201 for a path that does not exist), and it derives the id
 *    from the name with dashes folded to underscores — so the id is READ, never
 *    assumed. CI's harness creates its cameras the same way
 *    (feature_check.py:1413-1419) and likewise reads `body["id"]`.
 *  - POST /api/events/bulk answers 207 with per-item results (events.py:1493-
 *    1509). `events.batch_id` is UNIQUE (measured UniqueViolationError), so one
 *    batch_id per row: reusing a single id lands exactly one row and poisons the
 *    session for the rest ("Transaction commit failed").
 *  - The bulk tier is rate-limited (10/min, burst 2, rate_limit.py:617-623) but
 *    the route schema allows 100 events per request (schemas/bulk.py:122-126),
 *    so ONE call per spec file is well inside the budget: 4 successive single-
 *    request calls measured ≥4×OK.
 *  - bulk_create_events does NOT broadcast on /ws/events (no EventBroadcaster
 *    call anywhere in :1526-1608), so a fixture row can never satisfy F-045's
 *    "arriving over the socket" clause. That row needs the fake VLM's drop path
 *    and is NOT unlocked by this fixture.
 *
 * It creates rows only; it never deletes anyone else's, and `clear_existing` is
 * never sent (that flag on the admin seed route wipes every event, admin.py:476-
 * 485). Cleanup lives in `softDeleteFixtureRows`.
 */
export async function createTimelineFixture(
  h: TimelineHarness,
  session: Session
): Promise<TimelineFixture> {
  const cameraId = await ensureCamera(
    h,
    session,
    FIXTURE_CAMERA_NAME,
    '/cameras/fe3_timeline_probe'
  );
  // The UI's camera select is built from GET /api/cameras, whose answer can be a
  // stale cache entry (see waitForCameraInList). The page must not boot before it
  // names this camera, or F-043's deep-link legs assert against a select that
  // legitimately never saw it — which is the CI red this note records.
  await waitForCameraInList(h, session, FIXTURE_CAMERA_NAME);

  // Re-runs on a persistent stack must not accumulate rows on THIS camera, or a
  // row-count mirror would compare the DOM against a number that grew between
  // two legs of one run. Everything already on the fixture camera is FE-3's own
  // residue (the camera is FE-3's own name), so soft-delete it first — the same
  // reversible delete `softDeleteFixtureRows` performs, never a permanent one.
  const stale = await api<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await softDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );

  // Distinct batch_id per row — events.batch_id is UNIQUE (measured). The suffix
  // keeps ids unique across re-runs of the same file on a persistent dev stack.
  const salt = Date.now();
  const events = FIXTURE_ROWS.map((row, i) => ({
    batch_id: `fe3-${salt}-${i}`,
    camera_id: cameraId,
    started_at: new Date(Date.UTC(2026, 9, 13, 4, i * 7)).toISOString(),
    risk_score: row.riskScore,
    risk_level: row.riskLevel,
    summary: `FE-3 fixture row ${i} (${row.riskLevel})`,
  }));
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);

  const onCamera = await api<{ items: unknown[]; pagination: { total: number } }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  return { cameraId, eventIds, rowsOnCamera: onCamera.pagination.total };
}

/**
 * Best-effort tidy-up: soft-delete the rows FE-3 created (measured: DELETE
 * /api/events/{id} answers 204 and the row lands in GET /api/events/deleted —
 * the trash, i.e. exactly where a user's own deletion goes, and reversible via
 * POST /api/events/{id}/restore).
 *
 * Deliberately NOT a permanent delete: `DELETE /api/events/bulk` is a bulk-tier
 * route (events.py:1733-1749) whose budget the fixture already spends, and
 * irreversible cleanup in a shared stack is worse than a recoverable residue.
 * Order matters for honesty: this runs in the file's afterAll, and the golden
 * project is one serial worker, so FE-3 is the LAST file to run (a --list of
 * the golden project places timeline/ 63rd of 63) — no merged spec reads the
 * trash or the camera list after these rows move.
 */
export async function softDeleteFixtureRows(
  h: TimelineHarness,
  session: Session,
  eventIds: number[]
): Promise<void> {
  for (const id of eventIds) {
    // Each row is independent; a 409 (already deleted) is not worth failing an
    // afterAll over, so settle instead of using apiWrite's throwing contract.
    await fetch(`${h.api}/api/events/${id}`, {
      method: 'DELETE',
      headers: { Cookie: `${session.name}=${session.value}` },
    }).catch(() => undefined);
  }
}

/* -------------------------------------------------------------------------- */
/* The stats fixture (F-047) — a SECOND camera, on purpose.                    */
/*                                                                             */
/* F-043 may soft-delete its own rows, and GET /api/events/stats has NO        */
/* deleted_at predicate (events.py:609-623 filters dates + camera only), so    */
/* trash on a shared camera would be counted into F-047's totals. Measured:    */
/* after soft-deleting 1 of 2 rows, GET /api/events said total:1 while a stats */
/* read on a cache key never used before the delete said total_events:2. A     */
/* separate camera is therefore the cheap fix; the mismatch itself is recorded */
/* in the PR body and the inventory row's Notes, not hidden by the fixture.    */
/*                                                                             */
/* Cleanup is a HARD delete here for the same reason: `soft_delete:false` on   */
/* DELETE /api/events/bulk (events.py:1733-1803) removes the row outright, so  */
/* a later run's totals start from this file's own rows only. F-043 keeps the  */
/* reversible soft delete — its mirrors count LIVE rows, which excludes trash.  */
/* -------------------------------------------------------------------------- */

/** FE-3's stats camera: distinct from FIXTURE_CAMERA_NAME for the reason above. */
export const STATS_CAMERA_NAME = 'fe3-stats-probe';

/**
 * Rows for the stats panel: one per risk level, so the panel's four level cards
 * and the chart's bar set are each individually checkable (a fixture with two
 * `low` rows cannot tell a mislabelled card from a mislabelled bar).
 */
export const STATS_FIXTURE_ROWS: ReadonlyArray<{
  riskScore: number;
  riskLevel: 'critical' | 'high' | 'medium' | 'low';
}> = [
  { riskScore: 91, riskLevel: 'critical' },
  { riskScore: 70, riskLevel: 'high' },
  { riskScore: 45, riskLevel: 'medium' },
  { riskScore: 10, riskLevel: 'low' },
];

export interface StatsFixture {
  cameraId: string;
  eventIds: number[];
  /** The UTC calendar day (YYYY-MM-DD) every row was stamped INSIDE. The
   *  date-filter leg must pass THIS back as its range, never `new Date()` —
   *  see the stamp note below for why the runner's clock is the wrong answer. */
  day: string;
}

/**
 * One dedicated camera plus STATS_FIXTURE_ROWS on it. The rows share ONE stamp
 * so no midnight can split them, and the fixture returns that stamp's own UTC
 * day so the date-filter leg reads back the day it wrote rather than asking the
 * runner's clock for "today" (the golden suite's clock is the runner's, and a
 * boot in the first hour of a UTC day made `now - 40..55 min` land on YESTERDAY
 * — run 38488280792 at 00:06:59Z saw all four rows fall out of a
 * start=end=today range: 4 expected, 0 received).
 *
 * The stats panel applies NO default time window (`get_event_stats` filters on
 * `start_date`/`end_date` only when supplied, backend/api/routes/events.py:624)
 * and EventTimeline seeds its filter state empty (EventTimeline.tsx:101), so
 * recency is irrelevant to what renders — only the DAY the rows share matters,
 * and that day is now returned, not guessed.
 *
 * Idempotent the same way createTimelineFixture is, but the purge is a HARD one
 * — see the block header for why soft is not enough for a counts fixture.
 */
export async function createStatsFixture(
  h: TimelineHarness,
  session: Session
): Promise<StatsFixture> {
  const cameraId = await ensureCamera(h, session, STATS_CAMERA_NAME, '/cameras/fe3_stats_probe');
  // Same contract as the browse fixture: F-047's three legs all navigate with
  // ?camera=<id>, and a select that cannot name the camera is a boot the panel
  // never recovers from (refetchInterval is false).
  await waitForCameraInList(h, session, STATS_CAMERA_NAME);

  // Residue from an earlier run would inflate every count this file asserts.
  // Live rows first (cheap, single read), then anything already in the trash on
  // THIS camera — which only this file's own cleanup could have put there, since
  // no other spec names this camera.
  const stale = await api<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await hardDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );
  // Trash on this camera, from the route ops-a's spec uses. NOTE: GET
  // /api/events/deleted takes NO limit/start param (events.py:1411-1413 — its
  // only argument is the db) and reports `pagination.limit: 1000` while ignoring
  // any query string, so this read returns the WHOLE trash and the camera filter
  // below is client-side, not a server narrowing.
  const trashed = await api<{ items: { id: number; camera_id: string }[] }>(
    h,
    session,
    '/api/events/deleted'
  );
  await hardDeleteFixtureRows(
    h,
    session,
    trashed.items.filter((row) => row.camera_id === cameraId).map((row) => row.id)
  );

  const salt = Date.now();
  // ONE shared instant ~6 h ago, not a 40..55 min spread. The spread was the
  // landmine: 40-55 minutes before 00:30Z is 23:50 on the PREVIOUS UTC day, so
  // a run booting in the first hour of a day put the whole fixture outside a
  // "today" range (and a spread that wide could straddle midnight and split the
  // fixture across two days, so no single-day range could ever hold it). 6 h
  // back keeps the instant inside the scrubber's default 24 h window too, which
  // is what the panel's boot render needs.
  const instant = new Date(Date.now() - 6 * 3_600_000);
  const day = instant.toISOString().slice(0, 10);
  const events = STATS_FIXTURE_ROWS.map((row, i) => ({
    batch_id: `fe3s-${salt}-${i}`, // UNIQUE per row (measured UniqueViolationError)
    camera_id: cameraId,
    started_at: instant.toISOString(),
    risk_score: row.riskScore,
    risk_level: row.riskLevel,
    summary: `FE-3 stats fixture row ${i} (${row.riskLevel})`,
  }));
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `stats fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  return { cameraId, eventIds, day };
}

/**
 * Permanent delete via DELETE /api/events/bulk {soft_delete:false} (measured:
 * 207, `succeeded: 2, failed: 0`, and the rows disappear from stats too).
 * Chosen over the per-row soft delete ONLY where a spec asserts COUNTS, because
 * soft-deleted rows keep counting there (see the block header).
 */
export async function hardDeleteFixtureRows(
  h: TimelineHarness,
  session: Session,
  eventIds: number[]
): Promise<void> {
  if (eventIds.length === 0) return;
  // The route caps a request at 100 ids (schemas/bulk.py:182-187).
  for (let i = 0; i < eventIds.length; i += 100) {
    const chunk = eventIds.slice(i, i + 100);
    // Settle, don't throw: cleanup must not turn a green run red. A failure
    // here leaks rows into the NEXT run, where the purge above removes them.
    await fetch(`${h.api}/api/events/bulk`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        Cookie: `${session.name}=${session.value}`,
      },
      body: JSON.stringify({ event_ids: chunk, soft_delete: false }),
    }).catch(() => undefined);
  }
}

/**
 * Wait for the timeline's first event page to LAND, i.e. for the shipped
 * infinite query (EventTimeline.tsx:182 → useEventsQuery → GET /api/events,
 * api.ts:2292) to have resolved into rendered cards. Returns the card count.
 *
 * Returns the count rather than throwing on zero because a leg can still
 * legitimately filter to nothing (a `?verdict=confirmed` deep link on a stack
 * whose rows carry no verification — verifications are written only by the VLM
 * pipeline, ruling 90, and `bulk_create_events` writes none: a created row's
 * `verification` is null, measured). The caller then mirrors 0 against the API's
 * 0 and asserts the shipped empty render, which is a real judgement.
 */
export async function waitForEventCards(page: Page): Promise<number> {
  // The skeleton (EventCardSkeleton) is the in-flight marker; the cards are the
  // landed marker. Race them so an empty answer is not waited out at full timeout.
  const cards = page.getByTestId(/^event-card-\d+$/);
  await Promise.race([
    cards
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 })
      .catch(() => undefined),
    page
      .getByText('No Events Found')
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 })
      .catch(() => undefined),
  ]);
  return cards.count();
}

/* -------------------------------------------------------------------------- */
/* The detail fixture (F-056, F-057) — a THIRD camera, on purpose.             */
/*                                                                             */
/* These two rows mutate the row itself (`reviewed`, `notes`), so they cannot   */
/* share FIXTURE_CAMERA_NAME: F-043's legs mirror DOM card COUNTS against that  */
/* camera's rows, and a row this file marks reviewed is still a row — but a     */
/* later F2.3 spec that filters by `reviewed` would find this camera's rows     */
/* carrying state its own fixture never wrote. A separate camera keeps every    */
/* file's ground truth its own. (Ruling 87 also forbids touching the shared     */
/* harness the OTHER areas use, which is why each area has its own file.)       */
/*                                                                             */
/* FIVE rows, not one, and the last two are the point: `mark-reviewed` renders  */
/* only while `!event.reviewed` (EventDetailModal.tsx:1337, EventListView.tsx:  */
/* 408), so "the event shows reviewed" is a count that must go DOWN BY ONE, not  */
/* to zero. Asserting a disappearance of the whole set would pass on a UI that   */
/* blanked the list, and the untouched rows are the negative control that stops  */
/* that. Each leg owns its OWN row because the golden project is one serial      */
/* worker over a per-file fixture: a PATCH from an earlier test is still on the  */
/* row when a later test starts, so shared rows make a leg's starting state a    */
/* function of test order. The fifth row belongs to the `test.fixme` reopen leg — */
/* it stays note-free today, and when the read-back defect is repaired and the   */
/* fixme lifted that leg must still begin with nothing stored.                   */
/* -------------------------------------------------------------------------- */

/** FE-3's detail camera: distinct from the browse and stats cameras (see above). */
export const DETAIL_CAMERA_NAME = 'fe3-detail-probe';

/**
 * Rows for the detail-modal paths. Five, deliberately: four get exercised and one
 * is never touched, so a leg that marks one reviewed can assert the other rows'
 * affordances SURVIVED. `notes: null` is not settable here — the bulk route never
 * passes `notes` (events.py:1551-1560 builds Event(...) without it) and the column
 * defaults to NULL (models/event.py:78) — which is exactly the starting state
 * F-057 needs, measured: a fresh row reads `notes: None`.
 */
export const DETAIL_ROWS: ReadonlyArray<{ riskScore: number; riskLevel: string }> = [
  { riskScore: 88, riskLevel: 'critical' },
  { riskScore: 72, riskLevel: 'high' },
  { riskScore: 51, riskLevel: 'medium' },
  { riskScore: 18, riskLevel: 'low' },
  { riskScore: 33, riskLevel: 'low' },
];

export interface DetailFixture {
  cameraId: string;
  /** Row ids in request order; the spec names which leg uses which. */
  eventIds: number[];
}

/**
 * One dedicated camera plus DETAIL_ROWS on it, for the two PATCH-backed detail
 * rows. Same idempotence as the other two fixtures — `ensureCamera` absorbs the
 * name-unique 409, and `waitForCameraInList` waits out the 60 s camera-list
 * cache BEFORE any boot, because the modal's camera chip and the filter select
 * are both built from that cached list.
 *
 * Cleanup is the HARD delete: these rows accumulate mutations (`reviewed: true`,
 * a note) across re-runs, and a re-run needs its rows UNreviewed and note-free
 * for the transition to be a transition. A soft delete would leave them in the
 * trash but leave `reviewed: true` on the row a restore brings back.
 */
export async function createDetailFixture(
  h: TimelineHarness,
  session: Session
): Promise<DetailFixture> {
  const cameraId = await ensureCamera(h, session, DETAIL_CAMERA_NAME, '/cameras/fe3_detail_probe');
  await waitForCameraInList(h, session, DETAIL_CAMERA_NAME);

  // Purge this camera's residue from an earlier run, hard, for the reason in the
  // block comment: only the bulk hard delete clears the mutated flags by removing
  // the row outright (events.py:1733-1803, `soft_delete:false`).
  const stale = await api<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await hardDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );

  const salt = Date.now();
  const events = DETAIL_ROWS.map((row, i) => ({
    batch_id: `fe3d-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
    camera_id: cameraId,
    started_at: new Date(Date.UTC(2026, 9, 13, 5, i * 11)).toISOString(),
    risk_score: row.riskScore,
    risk_level: row.riskLevel,
    summary: `FE-3 detail fixture row ${i} (${row.riskLevel})`,
  }));
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `detail fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first ` +
        `error: ${String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)}`
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== DETAIL_ROWS.length) {
    throw new Error(
      `detail fixture: got ${eventIds.length} ids for ${DETAIL_ROWS.length} rows — ` +
        'the legs index these positionally, so a missing id must fail here.'
    );
  }
  // Every row must arrive UNreviewed and note-free, or the "transition" these two
  // rows claim is a no-op against state a previous run left behind. Asserted
  // against the uncached single-read route (`events.py:1870` takes no cache dep).
  for (const id of eventIds) {
    const row = await api<{ reviewed: boolean; notes: string | null }>(
      h,
      session,
      `/api/events/${id}`
    );
    if (row.reviewed || row.notes !== null) {
      throw new Error(
        `detail fixture: row ${id} arrived reviewed=${row.reviewed} notes=${String(
          row.notes
        )} — F-056/F-057 assert a TRANSITION, so the fixture must start clean.`
      );
    }
  }
  return { cameraId, eventIds };
}

/* -------------------------------------------------------------------------- */
/* The SEARCH fixture (F-048) — a FOURTH camera, on purpose.                    */
/*                                                                              */
/* It cannot share FIXTURE_CAMERA_NAME: F-043's legs mirror DOM card counts     */
/* against that camera's rows, and F-048's purge HARD-deletes 25 rows on boot.   */
/* It also cannot reuse the DETAIL camera, whose legs assert "starts unreviewed" */
/* and "starts note-free" — a search fixture that later marks rows reviewed      */
/* would make that file's precondition a function of file order.                */
/*                                                                              */
/* TWENTY-FIVE rows is not a taste number. The search panel's own pagination    */
/* (`SearchResultsPanel.tsx:57` totalPages = ceil(total/limit)) renders its      */
/* Next/Previous buttons ONLY while totalPages > 1, and the page size is the     */
/* component's defaultLimit = 20 (EventTimeline.tsx:163-170). Twenty-five is the */
/* smallest count above 20 whose second page is non-empty, so the paging clause */
/* can be driven at all — and the second page holds exactly 5 rows, which is a   */
/* count a leg asserts rather than a count it hopes for.                        */
/*                                                                              */
/* THE VICTIM ROW'S ROLE CHANGED WITH [r211b]. One extra row is still SOFT-      */
/* deleted after seeding, but its PURPOSE inverted. Before [r211b] the search    */
/* route had no `deleted_at` predicate while browse did, so the victim was a     */
/* guaranteed search HIT that could never be in `filteredEvents` — the defect    */
/* leg clicked it. [r211b] gave search the SAME predicate browse has             */
/* (backend/services/search.py:451; browse's is events.py:421), so now BOTH      */
/* readers hide it: search total drops by the victim, and GET /api/events/{id}   */
/* still 404s. The victim is now the fixture's NEGATIVE control — createSearch-  */
/* Fixture asserts search EXCLUDES it, and the defect leg's closing line reddens */
/* if search ever re-lists it. The defect subject moved to a still-shipped cause:*/
/* search paginates server-side while `filteredEvents` holds only browse's       */
/* loaded page-1 newest-20, so an older live row on search page 2 is offered by  */
/* search and unresolvable by the modal (EventTimeline.tsx:1059-1090).          */
/* -------------------------------------------------------------------------- */

/** FE-3's search camera: distinct from the browse, stats and detail cameras. */
export const SEARCH_CAMERA_NAME = 'fe3-search-probe';

/** Live rows the search legs page through. See the block comment for why 25. */
export const SEARCH_FIXTURE_SIZE = 25;

/**
 * The shared token every fixture row's summary carries. A leg narrows to ONE row
 * with `${SEARCH_QUERY_TOKEN} alpha <i>`, and every locator derives from the
 * fixture rather than hardcoding a name — an accessible-name assertion written
 * against a literal is one summary edit away from silently matching a different
 * widget (the sidebar's "Recent threats indicator" is also a role=button).
 */
export const SEARCH_QUERY_TOKEN = 'fe3f048searchtoken';

/**
 * The victim's summary. It carries SEARCH_QUERY_TOKEN (so the query would match
 * it) but NOT the `alpha <i>` form (so no live-row locator can ever aim at it by
 * accident, and a leg can name it out loud). Declared AFTER the token it
 * interpolates: these are `const`s, so the order is a TDZ error, not a style
 * preference. Since [r211b] the search route hides soft-deleted rows, so this
 * summary no longer appears in search results — the fixture keeps the row to
 * prove THAT (`toBe(false)` in the defect leg), not to be listed.
 */
export const SEARCH_VICTIM_SUMMARY = `${SEARCH_QUERY_TOKEN} deleted-but-still-listed`;

/**
 * Rows actually seeded: the 25 live ones plus the soft-deleted victim. The victim
 * is given the OLDEST `started_at` so that, were it ever to reappear in the
 * result set (a search-route regression that un-hides soft-deleted rows), it
 * would land at the BOTTOM — on page 2 — under the live rows, leaving page 1
 * identical to the browse list's page 1. That is what keeps the modal's positive
 * control honest: a page-1 click opens the modal because the row really is in the
 * cached list, not by luck. The defect the leg measures now sits on page 2 of the
 * LIVE rows (`alpha 0`, the oldest live row): search shows it, the browse cache
 * does not, and the modal renders nothing over it ([r211f], ruling 221).
 */
export const SEARCH_SEED_ROWS = SEARCH_FIXTURE_SIZE + 1;

export interface SearchFixture {
  cameraId: string;
  /** The 25 live rows, in seed order. `alpha <i>` in the summary is this index. */
  eventIds: number[];
  /** The soft-deleted row: hidden by search, absent from browse, 404 by id. */
  victimId: number;
  /** What the SEARCH route calls the total for this token — the victim excluded. */
  searchTotal: number;
  /** What the BROWSE route calls the total — the victim excluded. */
  browseTotal: number;
  /** Rows the server calls `high`, so the severity leg asserts a measured number. */
  highTotal: number;
}

/**
 * One camera, SEARCH_FIXTURE_SIZE live rows, and one soft-deleted row.
 *
 * `risk_score` alternates 91/45 so `risk_level` alternates high/medium — that is
 * what makes the severity filter leg an ASSERTION (13 of 25 high) instead of a
 * restatement of the fixture. `started_at` is spread one minute apart over 3 h
 * ending now, because search's tie-break is `started_at DESC` (search.py:465, moved
 * from :432 when [r211b] inserted the predicate above it) and
 * identical timestamps would make page contents arbitrary.
 *
 * The purge is HARD (`soft_delete:false`) and it asks the SEARCH route as well as
 * the browse list for this camera's ids. Before [r211b] the two disagreed by
 * design: a run that died between the soft-delete and `afterAll` left an orphan
 * invisible to `GET /api/events` but PRESENT in search, so a browse-only purge
 * would leave it and the next run would seed 26 rows and read "of 26" where it
 * asserts "of 25". [r211b] made search hide soft-deleted rows
 * (`backend/services/search.py:451`), so that orphan is now invisible to BOTH
 * readers: the search-route read can no longer recover it, but neither can it
 * corrupt the counts — it is excluded from `total_count` and from `items`, so a
 * lingering orphan is inert. An orphan a run left BEFORE its soft-delete is fully
 * live and both readers still list and purge it.
 */
export async function createSearchFixture(
  h: TimelineHarness,
  session: Session
): Promise<SearchFixture> {
  const cameraId = await ensureCamera(h, session, SEARCH_CAMERA_NAME, '/cameras/fe3_search_probe');
  // The camera <select> and the camera chip are built from the cached list, so a
  // just-created camera must age out of that 60 s entry before any boot.
  await waitForCameraInList(h, session, SEARCH_CAMERA_NAME);

  const salt = Date.now();
  const purge = async (path: string) => {
    // Best-effort on purpose: an unexpected extra row must not turn the fixture
    // red before it has tried to remove it. The count assertions below are the
    // place that mismatch becomes visible, with the number in the message.
    const stale = await api<{ items?: { id: number }[]; results?: { id: number }[] }>(
      h,
      session,
      path
    ).catch(() => null);
    const ids = (stale?.items ?? stale?.results ?? []).map((row) => row.id);
    await hardDeleteFixtureRows(h, session, ids);
  };
  await purge(`/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`);
  await purge(
    `/api/events/search?q=${encodeURIComponent(SEARCH_QUERY_TOKEN)}&limit=100&camera_id=${encodeURIComponent(
      cameraId
    )}`
  );

  // Row 0 is the victim: the OLDEST timestamp in the set (see SEARCH_SEED_ROWS)
  // and a summary no live-row locator aims at. It is deliberately MEDIUM so the
  // live set is exactly HALF-1 high, which makes the severity leg's expectation
  // a number rather than a hope.
  const windowStart = Date.now() - 3 * 3_600_000;
  const events = Array.from({ length: SEARCH_SEED_ROWS }, (_, i) =>
    i === 0
      ? {
          batch_id: `fe3s-${salt}-victim`,
          camera_id: cameraId,
          started_at: new Date(windowStart).toISOString(),
          risk_score: 45,
          risk_level: 'medium',
          summary: SEARCH_VICTIM_SUMMARY,
        }
      : {
          batch_id: `fe3s-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
          camera_id: cameraId,
          started_at: new Date(windowStart + i * 60_000).toISOString(),
          // 72 and 45, NOT 91: `risk_level` is a stored column (event.py:63) but
          // every reader reports `computed_risk_level`, a CASE over risk_score
          // (:393-424, ≤29 low / ≤59 medium / ≤84 high / else critical). A row
          // declared `high` with score 91 therefore REPORTS `critical` while the
          // filter still matches it as `high` — measured — which makes the count
          // this file asserts depend on which of the two you ask. These scores
          // agree with their labels, so the severity leg measures the filter
          // instead of that disagreement. The disagreement itself is F-048's own
          // `test.fixme` leg, where both fields are named on purpose.
          risk_score: i % 2 === 0 ? 72 : 45,
          risk_level: i % 2 === 0 ? 'high' : 'medium',
          summary: `${SEARCH_QUERY_TOKEN} alpha ${i - 1}`,
        }
  );
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `search fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first ` +
        `error: ${String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)}`
    );
  }
  const allIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (allIds.length !== events.length) {
    throw new Error(
      `search fixture: got ${allIds.length} ids for ${events.length} rows — the legs name ` +
        'rows positionally by their `alpha <i>` summary, so a missing id must fail here.'
    );
  }

  // The victim is seeded at index 0 and carries its own summary, so the live rows
  // keep the contiguous `alpha 0 … alpha 24` naming the legs use. `results` comes
  // back in request order (the assumption createDetailFixture already makes), so
  // index 0 IS the victim.
  const victimId = allIds[0];
  await apiWrite<{ succeeded: number }>(h, session, 'DELETE', '/api/events/bulk', {
    event_ids: [victimId],
    soft_delete: true,
  });

  // The fixture's own premises, asserted at creation: if the server ever starts
  // agreeing with itself about the victim, the defect leg's claim stops meaning
  // what it says and this is the place that becomes obvious.
  const searchTruth = await api<{
    total_count: number;
    results: { id: number; risk_level: string }[];
  }>(
    h,
    session,
    `/api/events/search?q=${encodeURIComponent(SEARCH_QUERY_TOKEN)}&limit=100&camera_id=${encodeURIComponent(
      cameraId
    )}`
  );
  const browseTruth = await api<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  const liveIds = browseTruth.items.map((row) => row.id);
  // Plain throws, not `expect`: this file is a harness, and "the stack cannot
  // supply the fixture this file needs" must never be reported as a product
  // failure. Same idiom as createDetailFixture's precondition checks.
  const requireFixture = (premise: boolean, why: string): void => {
    if (!premise) throw new Error(`search fixture: ${why}`);
  };
  requireFixture(
    !searchTruth.results.some((row) => row.id === victimId),
    'search must EXCLUDE the soft-deleted row ([r211b]: the search route filters ' +
      '`Event.deleted_at IS NULL`, backend/services/search.py:451) — the defect leg ' +
      'measures a LIVE page-2 row now, so a search route that listed the victim again ' +
      'would mean this fixture is pinning a different product than the leg claims'
  );
  requireFixture(
    !liveIds.includes(victimId),
    'the browse list must EXCLUDE it, or getModalEvent could find it and the defect ' +
      'leg would be measuring something else'
  );
  requireFixture(
    liveIds.length === SEARCH_FIXTURE_SIZE,
    `the camera must hold exactly ${SEARCH_FIXTURE_SIZE} live rows after seeding, or ` +
      `every "of ${SEARCH_FIXTURE_SIZE}" this file asserts is wrong (got ${liveIds.length})`
  );
  // Report the server's own numbers rather than the fixture's arithmetic: the
  // severity and total assertions then mirror the DOM against the instrument that
  // produced them, which is the difference between a checked count and a guess.
  return {
    cameraId,
    eventIds: allIds.slice(1), // index 0 is the victim, not a live row
    victimId,
    searchTotal: searchTruth.total_count, // excludes the victim → SEARCH_FIXTURE_SIZE
    browseTotal: liveIds.length, // excludes it → SEARCH_FIXTURE_SIZE
    highTotal: searchTruth.results.filter((row) => row.risk_level === 'high').length,
  };
}

/* -------------------------------------------------------------------------- */
/* F-060 FEEDBACK FIXTURE                                                       */
/*                                                                              */
/* Its OWN camera, for the reason the block above states about the search       */
/* camera: this feature WRITES A ROW PER EVENT, and the mutation's success path */
/* invalidates `['feedbackStats']` — a count every other FE-3 file ignores but  */
/* one they would all disturb if feedback rows accumulated on a shared camera.  */
/*                                                                              */
/* THE CASCADE IS THE WHOLE CLEANUP STRATEGY, and it is declared, not assumed:  */
/* `event_feedback.event_id` is `ForeignKey("events.id", ondelete="CASCADE")`   */
/* (backend/models/event_feedback.py:77-78), so the hard purge that             */
/* `hardDeleteFixtureRows` already performs also removes each row's feedback.   */
/* Measured on the probe stack, same run: POST /api/feedback → 201, then        */
/* DELETE /api/events/bulk {soft_delete:false} → 207 succeeded:1, then          */
/* GET /api/feedback/event/<id> → 404 and GET /api/feedback/stats               */
/* → {total_feedback: 0}. There is NO feedback-delete endpoint, and none is     */
/* needed — which matters because a fixture that could not clear its feedback   */
/* would be unrunnable here, not merely untidy: the same UNIQUE(event_id)       */
/* (:78) that makes the second POST a 409 would make the second RUN a 409.     */
/*                                                                              */
/* FOUR ROWS, ONE PER LEG. UNIQUE(event_id) means one feedback per event, so    */
/* legs cannot share a row the way read-only legs can; the fourth is seeded     */
/* WITH feedback by this fixture so the row's "sees the saved feedback when     */
/* reopening" clause can be measured with NO UI action at all — if a leg had to */
/* POST through the UI first, a broken read-back would be indistinguishable     */
/* from a broken write, and this file needs to tell those two apart.            */
/* -------------------------------------------------------------------------- */

/** FE-3's feedback camera: distinct from the browse, stats, detail, search. */
export const FEEDBACK_CAMERA_NAME = 'fe3-feedback-probe';

/** One row per leg: quick path, notes form, derived notes, pre-seeded read-back. */
export const FEEDBACK_FIXTURE_SIZE = 4;

/** Every fixture row carries this, so a purge or a count can name the set. */
export const FEEDBACK_SUMMARY_TOKEN = 'fe3f060feedback';

/**
 * The score every row is seeded with. 45 is `medium` under BOTH implementations
 * of `risk_level` (stored column, and `computed_risk_level`'s ≤59 branch,
 * backend/models/event.py:393-424), which matters here for a reason unrelated to
 * severity: the panel renders `currentRiskScore={event.risk_score ?? undefined}`
 * (EventDetailModal.tsx:543 → :1146) and `handleSubmitWithNotes` PREFIXES the
 * typed notes with `Current score: ${currentRiskScore}. ` (:207-213). A leg that
 * asserts the STORED string therefore needs a score that is unambiguous in the
 * fixture — not one whose label another reader would contradict.
 */
export const FEEDBACK_RISK_SCORE = 45;

/** What the notes-form leg types. Kept out of the token so it is findable. */
export const FEEDBACK_TYPED_NOTES = 'the garden hose looked like a person';

/** What the fixture seeds on the read-back row, before any UI action. */
export const FEEDBACK_SEEDED_NOTES = 'seeded before this run opened the modal';

/** The calibration value seeded on that row, rendered by NO part of the card. */
export const FEEDBACK_SEEDED_THREAT_LEVEL = 'no_threat';

export interface FeedbackFixture {
  cameraId: string;
  /** The four rows in seed order; legs name them by the constants in the spec. */
  eventIds: number[];
  /** Row 3: has a feedback row already, written by the fixture rather than the UI. */
  seededEventId: number;
  /** Notes exactly as the server stored them (read back, not echoed by memory). */
  seededNotes: string;
}

/**
 * One camera, FEEDBACK_FIXTURE_SIZE rows at FEEDBACK_RISK_SCORE, and a feedback
 * row on the LAST one.
 *
 * The purge is hard and runs before seeding (a previous run that died mid-leg
 * leaves a feedback row that would 409 this run's POST), and it relies on the
 * CASCADE documented above — there is no other door.
 *
 * `requireFixture` (plain throws, same idiom as the search fixture) checks the
 * two premises the legs cannot see: that the seeded feedback is REALLY there and
 * that row 0 really has none. Without the second premise the quick leg's
 * "buttons appeared" would be a card that was already there.
 */
export async function createFeedbackFixture(
  h: TimelineHarness,
  session: Session
): Promise<FeedbackFixture> {
  const cameraId = await ensureCamera(
    h,
    session,
    FEEDBACK_CAMERA_NAME,
    '/cameras/fe3_feedback_probe'
  );
  // The camera <select> is built from the 60 s cached list; see the search fixture.
  await waitForCameraInList(h, session, FEEDBACK_CAMERA_NAME);

  const stale = await api<{ items?: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  ).catch(() => null);
  await hardDeleteFixtureRows(
    h,
    session,
    (stale?.items ?? []).map((row) => row.id)
  );

  const salt = Date.now();
  const windowStart = Date.now() - 3 * 3_600_000;
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', {
    events: Array.from({ length: FEEDBACK_FIXTURE_SIZE }, (_, i) => ({
      batch_id: `fe3fb-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
      camera_id: cameraId,
      started_at: new Date(windowStart + i * 60_000).toISOString(),
      risk_score: FEEDBACK_RISK_SCORE,
      risk_level: 'medium',
      summary: `${FEEDBACK_SUMMARY_TOKEN} ${i}`,
    })),
  });
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== FEEDBACK_FIXTURE_SIZE) {
    throw new Error(
      `feedback fixture: got ${eventIds.length} ids for ${FEEDBACK_FIXTURE_SIZE} rows; ` +
        `succeeded ${bulk.succeeded}/${FEEDBACK_FIXTURE_SIZE}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }

  const seededEventId = eventIds[FEEDBACK_FIXTURE_SIZE - 1];
  await apiWrite<{ id: number }>(h, session, 'POST', '/api/feedback', {
    event_id: seededEventId,
    feedback_type: 'false_positive',
    notes: FEEDBACK_SEEDED_NOTES,
    actual_threat_level: FEEDBACK_SEEDED_THREAT_LEVEL,
  });

  const requireFixture = (premise: boolean, why: string): void => {
    if (!premise) throw new Error(`feedback fixture: ${why}`);
  };
  const live = await api<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  requireFixture(
    live.items.length === FEEDBACK_FIXTURE_SIZE,
    `the camera must hold exactly ${FEEDBACK_FIXTURE_SIZE} rows after seeding ` +
      `(got ${live.items.length})`
  );
  // Read the seeded row back through the SAME endpoint the panel calls, so the
  // read-back leg is measuring the panel's data source rather than the POST's
  // own response. Notes come from here, not from the constant, so a server that
  // normalises the string shows up as a leg failure with the real value in it.
  const seeded = await api<{
    notes: string | null;
    feedback_type: string;
    actual_threat_level: string | null;
  }>(h, session, `/api/feedback/event/${seededEventId}`);
  requireFixture(
    seeded.notes === FEEDBACK_SEEDED_NOTES,
    `the seeded feedback must be readable at the endpoint the panel uses ` +
      `(got ${JSON.stringify(seeded.notes)})`
  );
  requireFixture(
    seeded.actual_threat_level === FEEDBACK_SEEDED_THREAT_LEVEL,
    'the calibration field must survive the round trip, or the card-omission ' +
      'leg has nothing to omit'
  );
  return { cameraId, eventIds, seededEventId, seededNotes: seeded.notes ?? '' };
}

/* -------------------------------------------------------------------------- */
/* The AUDIT fixture (F-061 / F-062) — a SIXTH camera.                          */
/*                                                                              */
/* Same isolation rule as the search fixture's block above: these legs read     */
/* counts and states that a foreign row could falsify, and this fixture's purge */
/* HARD-deletes its own rows on boot. It also cannot share the feedback camera, */
/* whose precondition is "row 0 has NO feedback row" — a shared camera would    */
/* make that a function of file order.                                          */
/* -------------------------------------------------------------------------- */

/** FE-3's audit camera: distinct from the browse, stats, detail, search, feedback. */
export const AUDIT_CAMERA_NAME = 'fe3-audit-probe';

/**
 * THE ONE NUMBER THIS FIXTURE EXISTS TO OWN.
 *
 * `POST /api/ai-audit/batch` has NO camera filter — `BatchAuditRequest`
 * (backend/api/schemas/ai_audit.py:524-526) offers only `limit`,
 * `min_risk_score`, `force_reevaluate` — so a spec that wanted to aim a batch
 * at ITS OWN row had no lever… until it counted the other rows. Every other
 * FE-3 fixture row tops out at 91 (the maximum over `FIXTURE_ROWS`,
 * `STATS_FIXTURE_ROWS`, `DETAIL_ROWS` and `FEEDBACK_RISK_SCORE`, derived below as
 * `SIBLING_MAX_RISK_SCORE`; the search fixture's inline scores max at 72), so a
 * fixture row at 99 sits strictly above every one of them and
 * `min_risk_score: 99, limit: 1` selects exactly that row.
 * Measured on the probe stack: the batch answered `total_events: 1` and NO
 * other stack row gained an audit. This constant is the whole targeting
 * mechanism, which is why it is exported and why a leg that changes it breaks
 * the isolation the fixture bought.
 */
export const AUDIT_TARGET_RISK_SCORE = 99;

/** What the fixture row's summary carries, so a purge or a count can name it. */
export const AUDIT_SUMMARY_TOKEN = 'fe3f061audit';

/**
 * The highest risk score any OTHER FE-3 fixture row carries, DERIVED from the
 * sibling fixtures' own exports rather than hard-coded, so a leg's targeting
 * bound cannot go stale when a sibling edits its rows. The search fixture's
 * scores are inline (`:1106`, `i % 2 === 0 ? 72 : 45`) and its max of 72 is below
 * every maximum below, which is why it needs no export to be covered here.
 */
const SIBLING_MAX_RISK_SCORE = Math.max(
  ...FIXTURE_ROWS.map((r) => r.riskScore),
  ...STATS_FIXTURE_ROWS.map((r) => r.riskScore),
  ...DETAIL_ROWS.map((r) => r.riskScore),
  FEEDBACK_RISK_SCORE
);

/**
 * A 404 from `/api/ai-audit/**` that the UI is documented to render verbatim.
 * Kept in the harness because BOTH spec files assert it and they must not drift
 * apart: F-061 shows the server's own string (`auditApi.ts:249` lifts FastAPI's
 * `detail` into `AuditApiError.message`, `EventDetailModal.tsx:327` renders it),
 * F-062 shows the component's OWN sentence for the same status
 * (`EventAuditDetail.tsx:186-187`), and a leg that conflated the two would pass
 * on either UI while asserting neither.
 */
export const AUDIT_NOT_FOUND_DETAIL = (eventId: number): string =>
  `No audit found for event ${eventId}`;

export interface AuditFixture {
  cameraId: string;
  /** The row at AUDIT_TARGET_RISK_SCORE — the only one any leg clicks. */
  targetEventId: number;
  /** A second row, never audited and never clicked: the negative control. */
  controlEventId: number;
}

/**
 * A raw GET that TOLERATES a 404, because `api`'s contract is "non-200 throws"
 * and this fixture's premise is a 404. The distinction is the point: `api` is
 * what a leg uses to demand success; this is what a fixture uses to record an
 * absence. Status AND body come back so the caller can check the shape too —
 * the same event id answers "No audit found for event N" here but
 * "Event with id N not found" for an id no row has, and the legs depend on
 * that pair being different.
 */
export async function readAuditLookup(
  h: TimelineHarness,
  session: Session,
  eventId: number
): Promise<{ status: number; detail?: string; body?: Record<string, unknown> }> {
  const res = await fetch(`${h.api}/api/ai-audit/events/${eventId}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  return {
    status: res.status,
    detail: body?.detail as string | undefined,
    body: body ?? undefined,
  };
}

/**
 * One camera, one row at AUDIT_TARGET_RISK_SCORE and one control row, and a
 * PROVEN ABSENCE of `event_audits` rows for both.
 *
 * The premise check is not decoration. F-061's clause is a DISJUNCTION — "sees
 * 'Re-evaluation triggered successfully', OR 'No audit found for event N' for an
 * event no batch audit has covered" — and the half this fixture sets up is the
 * one that depends on stored state. The tier holds ZERO audit rows in the normal
 * case (measured: `GET /api/ai-audit/stats` answers `total_events: 0`), but a
 * sibling spec can drive `POST /api/ai-audit/batch` (`tests/golden/data-ui/
 * jobs-page.spec.ts:127` does exactly that, with `{limit: 1}`), and the golden
 * project is ONE serial worker over per-file fixtures — so "my row has no audit"
 * is a fact to re-assert per run, never to assume from a past measurement.
 *
 * The purge is HARD and precedes seeding: `event_audits.event_id` is
 * `ForeignKey(..., ondelete="CASCADE")` (backend/models/event_audit.py:27-28),
 * so removing the row removes its audit — and there is no audit-delete endpoint,
 * so the cascade is the only door.
 */
export async function createAuditFixture(
  h: TimelineHarness,
  session: Session
): Promise<AuditFixture> {
  const cameraId = await ensureCamera(h, session, AUDIT_CAMERA_NAME, '/cameras/fe3_audit_probe');
  // The camera <select> and the modal's camera chip are built from the 60 s
  // cached list; see waitForCameraInList.
  await waitForCameraInList(h, session, AUDIT_CAMERA_NAME);

  const stale = await api<{ items?: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  ).catch(() => null);
  await hardDeleteFixtureRows(
    h,
    session,
    (stale?.items ?? []).map((row) => row.id)
  );

  const salt = Date.now();
  // 99 first: AUDIT_TARGET_RISK_SCORE must be the STRICT max of the fixture set,
  // and asserting that is cheaper than trusting the ordering below.
  const rows = [
    { risk_score: AUDIT_TARGET_RISK_SCORE, risk_level: 'critical' },
    { risk_score: 44, risk_level: 'medium' },
  ];
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', {
    events: rows.map((row, i) => ({
      batch_id: `fe3au-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
      camera_id: cameraId,
      started_at: new Date(Date.now() - 3_600_000 * (i + 1)).toISOString(),
      risk_score: row.risk_score,
      risk_level: row.risk_level,
      summary: `${AUDIT_SUMMARY_TOKEN} ${i}`,
    })),
  });
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== rows.length) {
    throw new Error(
      `audit fixture: got ${eventIds.length} ids for ${rows.length} rows; succeeded ` +
        `${bulk.succeeded}/${rows.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const [targetEventId, controlEventId] = eventIds;

  const requireFixture = (premise: boolean, why: string): void => {
    if (!premise) throw new Error(`audit fixture: ${why}`);
  };
  // The bound is checked HERE, at fixture time, rather than in a standalone
  // `test()` asserting a constant: a pure-logic test would (a) still appear in
  // CI's `golden paths:` dict as a "leg" that is not a feature path, and (b) keep
  // passing if a sibling fixture later raised its own rows — this throw fires the
  // moment the isolation stops being true, in the file that depends on it.
  requireFixture(
    AUDIT_TARGET_RISK_SCORE > SIBLING_MAX_RISK_SCORE,
    `the target score ${AUDIT_TARGET_RISK_SCORE} must stay STRICTLY above every ` +
      `other FE-3 fixture score (derived maximum ${SIBLING_MAX_RISK_SCORE}) or ` +
      '`min_risk_score` targeting could select a foreign row'
  );
  // The score is the batch-targeting lever (see AUDIT_TARGET_RISK_SCORE), so a
  // server that clamped or defaulted it silently disarms the isolation.
  const storedTarget = await api<{ risk_score: number | null }>(
    h,
    session,
    `/api/events/${targetEventId}`
  );
  requireFixture(
    storedTarget.risk_score === AUDIT_TARGET_RISK_SCORE,
    `the target row must store risk_score ${AUDIT_TARGET_RISK_SCORE} for ` +
      `min_risk_score targeting to be exclusive (got ${String(storedTarget.risk_score)})`
  );
  for (const id of eventIds) {
    const probe = await readAuditLookup(h, session, id);
    requireFixture(
      probe.status === 404 && probe.detail === AUDIT_NOT_FOUND_DETAIL(id),
      `row ${id} must start with NO audit row, answered 404 with the ` +
        `"no audit" detail (got ${probe.status} ` +
        `${JSON.stringify(probe.detail)?.slice(0, 120)}) — F-061/F-062 assert the ` +
        `not-found branch, so a row that already HAS an audit makes the leg vacuous`
    );
  }
  return { cameraId, targetEventId, controlEventId };
}

/** The tripwire closing every golden spec (F2.1's; OP-1 calls it closedByGuard). */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}
