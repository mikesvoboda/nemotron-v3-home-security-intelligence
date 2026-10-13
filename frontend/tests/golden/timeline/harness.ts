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
  const list = await api<CameraListBody>(h, session, '/api/cameras');
  const existing = (list.items ?? []).find((c) => c.name === FIXTURE_CAMERA_NAME);
  const cameraId = existing
    ? existing.id
    : (
        await apiWrite<CameraCreated>(h, session, 'POST', '/api/cameras', {
          name: FIXTURE_CAMERA_NAME,
          folder_path: '/cameras/fe3_timeline_probe',
        })
      ).id;

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
}

/**
 * One dedicated camera plus STATS_FIXTURE_ROWS on it, anchored to NOW rather
 * than to a calendar date: F-047's date-filter leg asserts "today holds them
 * all", which a hardcoded date would break the moment CI runs at another hour
 * (the golden suite's clock is the runner's, not this file's).
 *
 * Idempotent the same way createTimelineFixture is, but the purge is a HARD one
 * — see the block header for why soft is not enough for a counts fixture.
 */
export async function createStatsFixture(
  h: TimelineHarness,
  session: Session
): Promise<StatsFixture> {
  const list = await api<CameraListBody>(h, session, '/api/cameras');
  const existing = (list.items ?? []).find((c) => c.name === STATS_CAMERA_NAME);
  const cameraId = existing
    ? existing.id
    : (
        await apiWrite<CameraCreated>(h, session, 'POST', '/api/cameras', {
          name: STATS_CAMERA_NAME,
          folder_path: '/cameras/fe3_stats_probe',
        })
      ).id;

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
  const now = Date.now();
  const events = STATS_FIXTURE_ROWS.map((row, i) => ({
    batch_id: `fe3s-${salt}-${i}`, // UNIQUE per row (measured UniqueViolationError)
    camera_id: cameraId,
    // 40..55 minutes ago: inside the last hour, inside today, and inside the
    // scrubber's default 24 h window (measured: it spans now-24 h → now).
    started_at: new Date(now - (40 + i * 5) * 60_000).toISOString(),
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
  return { cameraId, eventIds };
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

/** The tripwire closing every golden spec (F2.1's; OP-1 calls it closedByGuard). */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}
