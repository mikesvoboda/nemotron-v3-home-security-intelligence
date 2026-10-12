/**
 * FE-2 golden path (F2.3): F-029 — the camera grid: one card per camera with a
 * live snapshot and online status, a per-card Refresh that re-pulls the
 * snapshot, and a card click that opens /timeline?camera=…
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - The row's clauses: "sees a card per camera with a live snapshot and online
 *   status; clicks Refresh on a card to re-pull the snapshot; clicks a card to
 *   open /timeline?camera=…". Endpoints: GET /api/cameras (`list_cameras`
 *   cameras.py:152, a cache-aside items+pagination envelope, schemas/camera.py
 *   :396-418), GET /api/cameras/{id}/snapshot (`get_camera_snapshot`
 *   cameras.py:1215), POST …/snapshot/refresh (`refresh_camera_snapshot`
 *   cameras.py:1329).
 * - THE ROW'S "live snapshot" HALF IS TWO-STATE, and a one-sided assert would be
 *   wrong. `thumbnail_url` is ALWAYS synthesized from the id
 *   (DashboardPage.tsx:286 → api.ts:1472-1474) — the API never sends one — and a
 *   seeded camera is `status='online'` by DB default (models/camera.py:110), so
 *   `canLoadThumbnail` (CameraGrid.tsx:255) is true and the card ALWAYS renders
 *   the <img> (:330-345). Whether bytes exist is a property of the watched
 *   folder: the route 404s when it holds no image and no video
 *   (cameras.py:1276-1283), the <img> then fires onError (:340-343), and only
 *   THEN does `camera-placeholder-<id>` appear (:262, :348-376). The honest
 *   invariant is therefore a PAIR, and its discriminator is the CARD'S OWN <img>:
 *       img decoded (complete && naturalWidth>0) ⟺ the card is showing a snapshot
 *       img errored / absent + placeholder       ⟺ the card is showing the placeholder
 *   which is the same signal the shipped component branches on (onLoad/onError,
 *   :339-343). Asserting "img visible" would pass on a folder-empty camera;
 *   asserting "placeholder absent" would fail on a camera that legitimately has
 *   no file. Either resolved state is correct for some camera, so the poll only
 *   requires the card to RESOLVE to exactly one of them; which one is right is
 *   then decided against the endpoint, so a wrong-way pair still fails.
 * - Which cameras have files is NOT knowable from here, so it is DISCOVERED,
 *   never hardcoded. `seed_cameras` registers one camera per scenario folder
 *   (feature_check.py:1284-1298) and `smoke()` drops the smoke image into ONE of
 *   them (:1341-1342) before the golden suite runs (order :1836-1840), while
 *   dashboard-drop.spec.ts and the analytics-alerts batch drop MORE and run
 *   BEFORE dashboard/* alphabetically. The set therefore depends on which specs
 *   ran earlier in the run — a hardcoded camera name would be a guess.
 * - WHY the network observation is only a WITNESS and never the assert. A
 *   per-camera status map captured from page.on('response') is AMBIGUOUS here: the
 *   activity feed renders event thumbnails built from the same synthesized URL
 *   (ActivityFeed.tsx:242 ← DashboardPage.tsx:304), so a second request for the
 *   same path can land after the card's and overwrite a last-write-wins entry.
 *   It answers the one question the img cannot: WHY a card that the endpoint
 *   serves shows a placeholder. That matters because snapshots ride the frontend
 *   nginx `zone=api` throttle (docker-entrypoint.sh:139, rate=10r/s burst=20 — the
 *   same bucket the boot wave drains, which is the measurement behind
 *   BOOT_QUIET_MS in harness.ts) while Node reads hit the backend directly
 *   (feature_check.py:1230, port 8000) unthrottled. A shed 429 is a real
 *   user-visible placeholder, so it is the ONLY permitted disagreement between the
 *   two instruments; anything else fails loud naming both values.
 * - Status is mirrored through TWO shipped maps, not one: the page narrows any
 *   DB value outside online/offline/error to 'unknown' (DashboardPage.tsx:282-285),
 *   then the card renders getStatusLabel (CameraGrid.tsx:92-101) into BOTH the
 *   aria-label (:316) and the badge (:381). Asserting the composed chain catches
 *   a page-level mapping regression (a future 'recording' status renders
 *   "Unknown" — the narrowing says so). The grid also merges WS status overrides
 *   over props (:479, :520-529) and drops them when the `cameras` prop identity
 *   changes (:532-543), so status reads are AGREEMENT POLLS, not one-shots.
 * - What is NOT asserted: the footer's last-seen time is compared for PRESENCE
 *   only, never as a string — it renders through toLocaleTimeString (:423-430),
 *   and my Node process and the browser need not agree on locale or TZ, so a
 *   string compare across them could fail with nothing broken. Presence still
 *   mirrors the API field, located STRUCTURALLY (the card's last descendant div
 *   is the footer, :421) rather than by Tailwind class: a class-name locator is
 *   the invented-attribute failure mode this batch's sibling header forbids.
 * - Refresh is proven by the RESPONSE, not the UI: handleRefreshClick swallows
 *   any failure into console.error (:277-279) and clears its spinner in finally
 *   (:279-281), so a 404 refresh (a folder with no image and no video,
 *   cameras.py:1408-1411) is indistinguishable from a 200 to the user. Only the
 *   observed status tells them apart, so this leg reads a real POST status and
 *   drives a camera discovered to have bytes. When NO camera has bytes the leg
 *   self-skips IN ITS OWN TEST with that reason (ruling 86), so it can never hide
 *   the grid-mirror or click evidence — the F-028 precedent's shape.
 * - The click leg asserts the deep link is CONSUMED, not just navigated (F-032's
 *   form): the timeline seeds filters from ?camera= and auto-opens its panel
 *   (EventTimeline.tsx:307-326), so its own events request then carries
 *   camera_id (api.ts:2274). Per batch 3's measurement the panel is already open
 *   on CI, so this READS #camera-filter (:1262) instead of clicking "Show Filters"
 *   and timing out on a button that path never renders.
 * - Every observation is PASSIVE (page.on('request'/'response')); the guard
 *   blocks route/routeFromHAR/routeWebSocket and this spec uses none of them.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readDashboardHarness,
  seedTourDismissed,
  type DashboardHarness,
  type Session,
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface CameraRow {
  id: string;
  name: string;
  status: string;
  last_seen_at: string | null;
}
interface CameraList {
  items: CameraRow[];
}
type GridStatus = 'online' | 'offline' | 'error' | 'recording' | 'unknown';

/** Mirror of DashboardPage.tsx:282-285 — the page's own narrowing map. */
function pageStatus(db: string): GridStatus {
  return db === 'online' || db === 'offline' || db === 'error' ? (db as GridStatus) : 'unknown';
}

/** Mirror of CameraGrid.tsx:92-101 — the card's label map. */
function statusLabel(status: GridStatus): string {
  const labels: Record<GridStatus, string> = {
    online: 'Online',
    recording: 'Recording',
    offline: 'Offline',
    error: 'Error',
    unknown: 'Unknown',
  };
  return labels[status];
}

/** Mirror of api.ts:1472-1474 (BASE_URL defaults to '' — api.ts:877). */
const snapshotPath = (id: string) => `/api/cameras/${encodeURIComponent(id)}/snapshot`;
const refreshPath = (id: string) => `${snapshotPath(id)}/refresh`;

/** The browser's own GET snapshot statuses, keyed by camera id (passive). */
function observeSnapshots(page: import('@playwright/test').Page) {
  const byId = new Map<string, number>();
  page.on('response', (res) => {
    // GET only: api.ts:1553 issues a HEAD probe for the same URL from other
    // surfaces, and a HEAD must not overwrite what the <img> actually got.
    const m = /\/api\/cameras\/([^/?]+)\/snapshot(?:\?|$)/.exec(res.url());
    if (m && res.request().method() === 'GET') byId.set(decodeURIComponent(m[1]), res.status());
  });
  return byId;
}

/** Real POSTs to the refresh route with their statuses (passive). */
function observeRefreshPosts(page: import('@playwright/test').Page) {
  const posts: { id: string; status: number }[] = [];
  page.on('response', (res) => {
    const m = /\/api\/cameras\/([^/?]+)\/snapshot\/refresh(?:\?|$)/.exec(res.url());
    if (m && res.request().method() === 'POST') {
      posts.push({ id: decodeURIComponent(m[1]), status: res.status() });
    }
  });
  return posts;
}

/** The app's own /api/events requests (passive; query strings read later). */
function observeEventQueries(page: import('@playwright/test').Page) {
  const urls: string[] = [];
  page.on('request', (req) => {
    if (/\/api\/events(\?|$)/.test(req.url())) urls.push(req.url());
  });
  return urls;
}

async function openDashboard(page: import('@playwright/test').Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
}

/** The shipped grid wrapper (CameraGrid.tsx:584) — the NON-empty variant only. */
const grid = (page: import('@playwright/test').Page) => page.getByTestId('camera-grid');
const card = (page: import('@playwright/test').Page, id: string) =>
  page.getByTestId(`camera-card-${id}`);
/** Structural footer locator: the card's LAST descendant div is the name/time
 *  row (:421-431) — nothing nests inside it, so document order puts it last. */
const footer = (page: import('@playwright/test').Page, id: string) =>
  card(page, id).locator('div').last();

interface CardMedia {
  /** absent = no <img> in the card at all (the placeholder branch owns it). */
  img: 'absent' | 'loading' | 'decoded' | 'errored';
  placeholder: boolean;
  src: string | null;
}

/**
 * One NON-WAITING read of the card's media state.
 *
 * This is a page.evaluate on purpose, not locator.evaluate/getAttribute: those
 * AUTO-WAIT for the element, so for every camera whose card has no <img> (the
 * placeholder branch, which is most of them on a fresh run) each poll iteration
 * would block for the full action timeout before hitting a catch — with the five
 * seeded cameras that is minutes inside a 120 s test, i.e. a timeout this
 * instrument caused itself. `count()` does not wait, but evaluate does.
 *
 * The card is matched by comparing getAttribute, the form config-modal.spec.ts
 * already uses, so a backend-generated id never has to be CSS-escaped.
 */
async function readCardMedia(
  page: import('@playwright/test').Page,
  cameraId: string
): Promise<CardMedia> {
  return page.evaluate((id) => {
    const find = (testid: string) =>
      [...document.querySelectorAll('[data-testid]')].find(
        (el) => el.getAttribute('data-testid') === testid
      );
    const cardEl = find(`camera-card-${id}`) ?? null;
    const img = cardEl?.querySelector('img') ?? null;
    const imgState: CardMedia['img'] = !img
      ? 'absent'
      : !img.complete
        ? 'loading'
        : img.naturalWidth > 0
          ? 'decoded'
          : 'errored';
    return {
      img: imgState,
      placeholder: find(`camera-placeholder-${id}`) !== undefined,
      src: img?.getAttribute('src') ?? null,
    };
  }, cameraId);
}

/**
 * Verdict on one read: RESOLVED once the card sits in exactly ONE branch, else a
 * string naming what was seen (a poll that never resolves therefore FAILS with
 * the last observed DOM state instead of timing out blank).
 *
 * The two branches are MUTUALLY exclusive in the shipped markup: the <img> is
 * rendered under `hasThumbnail && !imageError` (:330) and the placeholder under
 * `showPlaceholder = !hasThumbnail || imageError` (:262, :348), and onError
 * UNMOUNTS the img. So `absent + placeholder` is the settled error branch, while
 * `errored` (naturalWidth 0 with the node still mounted) is only the window
 * between the browser's error event and React's re-render — hence a transient,
 * not a verdict. `decoded + placeholder` and `absent + absent` are contradiction
 * states no correct render can reach.
 */
const RESOLVED = 'placeholder-or-snapshot';
function mediaVerdict(m: CardMedia): string {
  if (m.img === 'decoded')
    return m.placeholder ? 'decoded <img> AND placeholder both rendered' : RESOLVED;
  if (m.img === 'loading') return 'img still loading (skeleton state)';
  if (m.img === 'errored') return 'img errored; React has not swapped to the placeholder yet';
  return m.placeholder ? RESOLVED : 'no <img> and no placeholder in the card';
}

/** Node-side status of the same path, without downloading the body. */
async function nodeSnapshotStatus(h: DashboardHarness, session: Session, id: string) {
  const res = await fetch(`${h.api}${snapshotPath(id)}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  await res.body?.cancel();
  return res.status;
}

/** Cameras the snapshot endpoint actually serves bytes for (discovered). */
async function servedCameras(h: DashboardHarness, session: Session, items: CameraRow[]) {
  const served: string[] = [];
  for (const cam of items) {
    if ((await nodeSnapshotStatus(h, session, cam.id)) === 200) served.push(cam.id);
  }
  return served;
}

async function listCameras(h: DashboardHarness, session: Session): Promise<CameraRow[]> {
  const list = await api<CameraList>(h, session, '/api/cameras');
  // The harness registers one camera per scenario folder (feature_check.py
  // :1284-1298), so an empty list is a harness failure — fail loud here rather
  // than let every per-camera loop below pass vacuously.
  expect(list.items.length, 'the harness seeded at least one camera').toBeGreaterThan(0);
  return list.items;
}

test.describe('golden path: dashboard camera grid @critical', () => {
  test('F-029: one card per camera mirrors GET /api/cameras, and each card shows the snapshot or the placeholder that endpoint actually served', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    // Listen BEFORE navigating so the boot's own wave is in scope.
    const snapshots = observeSnapshots(page);
    await openDashboard(page, h);

    // The grid renders the GRID variant, not the empty state
    // (CameraGrid.tsx:545-565 returns camera-grid-empty for an empty list).
    await expect(grid(page)).toBeVisible();
    await expect(page.getByTestId('camera-grid-empty')).toHaveCount(0);

    const session = await adminSession(h);
    const items = await listCameras(h, session);

    // "a card per camera" — polled, because the page fetches its own list and
    // paints a beat after the grid wrapper mounts.
    await expect
      .poll(() => grid(page).locator('[data-testid^="camera-card-"]').count(), {
        message: 'one card per camera in GET /api/cameras',
        timeout: 25_000,
        intervals: [1_000],
      })
      .toBe(items.length);

    // Per camera: the aria-label carries BOTH mirrored fields — the name and the
    // COMPOSED status chain (page narrowing + card label, :316).
    for (const cam of items) {
      const want = `Camera ${cam.name}, status: ${statusLabel(pageStatus(cam.status))}`;
      await expect
        .poll(async () => (await card(page, cam.id).getAttribute('aria-label')) ?? '(absent)', {
          message: `${cam.id}: aria-label mirrors the API name through the shipped status maps`,
          timeout: 15_000,
          intervals: [500],
        })
        .toBe(want);
      // Nothing is selected on a fresh dashboard (:317).
      await expect(card(page, cam.id)).toHaveAttribute('aria-pressed', 'false');
    }

    // THE PAIR, per camera: first require the card to RESOLVE to exactly one of
    // its two branches, then decide WHICH branch is correct against the endpoint.
    // The discriminator is the card's own <img> (`complete` + naturalWidth), the
    // same signal the shipped component branches on (:339-343), so it cannot be
    // confused by another surface — a captured per-camera status map WOULD be
    // ambiguous, because the activity feed renders event thumbnails built from the
    // SAME synthesized URL (ActivityFeed.tsx:242 ← DashboardPage.tsx:304).
    for (const cam of items) {
      // The poll's OWN winning read is what gets judged below: re-reading after
      // the poll resolves could straddle a React swap and compare a state the
      // poll never approved.
      let media = await readCardMedia(page, cam.id);
      await expect
        .poll(async () => mediaVerdict((media = await readCardMedia(page, cam.id))), {
          message: `${cam.id}: the card resolves to exactly one of snapshot / placeholder`,
          timeout: 30_000,
          intervals: [1_000],
        })
        .toBe(RESOLVED);

      const nodeStatus = await nodeSnapshotStatus(h, session, cam.id);
      if (media.img === 'decoded') {
        // A decoded img PROVES the endpoint served bytes, and the folder does not
        // change mid-test, so only two answers are reachable on my own read: 200,
        // or a 429 from the app's own MEDIA tier (120/min per client IP,
        // config.py:2416-2420 — Node and the browser both arrive through the same
        // published port, feature_check.py:1230, so my reads share that bucket).
        // A 429 here is this instrument being throttled: stated, not asserted
        // away. A 404 would mean the file vanished — the chain break this arm
        // exists to catch.
        expect(
          [200, 429],
          `${cam.id}: the card decoded a snapshot but GET ${snapshotPath(cam.id)} answered ${nodeStatus}`
        ).toContain(nodeStatus);
        expect(
          new URL(String(media.src), h.ui).pathname,
          `${cam.id}: the decoded <img> src is not the shipped synthesized URL`
        ).toBe(snapshotPath(cam.id));
      } else if (nodeStatus === 200) {
        // The endpoint has bytes the card did not show. Only the frontend
        // throttle explains a refusal that the direct backend read does not see.
        const browserStatus = snapshots.get(cam.id);
        expect(
          browserStatus,
          `${cam.id}: the endpoint serves it but the card shows the placeholder; the browser was answered ${browserStatus}, and only the frontend throttle (429, docker-entrypoint.sh:139) is permitted here`
        ).toBe(429);
      }
      // else: no bytes on either side — the placeholder IS the correct answer.
    }

    // Footer time: PRESENCE mirrored only (see header). Structural locator.
    for (const cam of items) {
      const hasTime = (await footer(page, cam.id).locator('span').count()) > 1;
      expect(
        hasTime,
        `${cam.id}: footer time shown=${hasTime} but GET /api/cameras says last_seen_at=${JSON.stringify(cam.last_seen_at)}`
      ).toBe(cam.last_seen_at !== null && cam.last_seen_at !== undefined);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-029: a card click opens /timeline?camera=<id> and the timeline CONSUMES it (param sent + filter shown)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    const eventQueries = observeEventQueries(page);
    await openDashboard(page, h);
    await expect(grid(page)).toBeVisible();

    const session = await adminSession(h);
    const items = await listCameras(h, session);
    await expect
      .poll(() => grid(page).locator('[data-testid^="camera-card-"]').count(), {
        message: 'cards painted before the click',
        timeout: 25_000,
        intervals: [1_000],
      })
      .toBe(items.length);

    const target = items[0];
    const eventsBefore = eventQueries.length;
    await card(page, target.id).click();

    // 1. The route the row names, with the id in the query.
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 15_000 }).toBe('/timeline');
    expect(new URL(page.url()).searchParams.get('camera')).toBe(target.id);

    // 2. CONSUMED: the timeline's OWN events request carries it (api.ts:2274
    // appends camera_id from the filter the URL seeded at :307-326).
    await expect
      .poll(
        () =>
          eventQueries
            .slice(eventsBefore)
            .some((u) => new URL(u).searchParams.get('camera_id') === target.id)
            ? 'param sent'
            : `no camera_id=${target.id} among ${eventQueries.length - eventsBefore} new event request(s)`,
        { message: 'the deep-linked camera becomes the timeline query filter', timeout: 25_000 }
      )
      .toBe('param sent');

    // 3. And it lands in the visible control. Read, never clicked-through
    // (batch 3 measured the panel is already open on this path).
    await expect(page.locator('#camera-filter')).toHaveValue(target.id, { timeout: 15_000 });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-029: the shipped Refresh button POSTs snapshot/refresh and does not trigger the card click', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    const posts = observeRefreshPosts(page);
    await openDashboard(page, h);
    await expect(grid(page)).toBeVisible();

    const session = await adminSession(h);
    const items = await listCameras(h, session);
    await expect
      .poll(() => grid(page).locator('[data-testid^="camera-card-"]').count(), {
        message: 'cards painted before the refresh drive',
        timeout: 25_000,
        intervals: [1_000],
      })
      .toBe(items.length);

    // Drive Refresh against a camera the endpoint actually has bytes for: on a
    // folder with no image and no video the route 404s (cameras.py:1408-1411)
    // and the component swallows the error into console.error
    // (CameraGrid.tsx:277-281), so the user-visible outcome is identical either
    // way — refreshing such a folder could not distinguish a working re-pull
    // from a broken one.
    const served = await servedCameras(h, session, items);
    test
      .info()
      .skip(
        served.length === 0,
        'no camera folder in this run holds an image or video, so POST …/snapshot/refresh cannot be ' +
          'driven to a 200 (a 404 is indistinguishable from success in this component — ' +
          'CameraGrid.tsx:277-281). Stated per ruling 86 rather than asserted as success; the row ' +
          'stays unverified until a run where a folder has bytes.'
      );
    if (served.length === 0) return;

    const target = served[0];
    const before = posts.length;
    await page.getByTestId(`camera-refresh-${target}`).click();
    await expect
      .poll(
        () => {
          const hit = posts.slice(before).find((p) => p.id === target);
          return hit ? String(hit.status) : 'no POST observed yet';
        },
        {
          message: `the shipped Refresh button POSTs ${refreshPath(target)}`,
          timeout: 20_000,
          intervals: [500],
        }
      )
      .toBe('200');

    // The button stops propagation (:267): a refresh must never fire the card's
    // own click, which would deep-link to /timeline.
    expect(page.url(), 'Refresh does not trigger the card click').not.toContain('/timeline');
    await expect(card(page, target)).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
