/**
 * F2.3 DO-3 golden path — the zones surface. Inventory rows
 * docs/reference/feature-inventory.md:462 (F-256) and :464 (F-258).
 * Route: /zones (`path="/zones"` frontend/src/App.tsx:312).
 *
 * What the rows promise, verbatim, and what this file does about it:
 *  F-256  "opens the page; sees a card per zone with type, enabled state and
 *         priority; filters by zone type and time range; clicks Export CSV
 *         (built in the browser); toggles a panel to full screen"
 *  F-258  "sees a grid of household members (or vehicles) against zones with
 *         trust levels; clicks a cell and picks full/partial/monitor/none"
 *
 * Why this file CREATES its rows instead of reading seeded ones: the no-env
 * fake-AI stack seeds only cameras (harness.ts:15-24, verified there), so the
 * passive /zones mount is the EMPTY branch — EmptyState title "No zones
 * configured" (ZonesPage.tsx:651) behind `zones.length === 0` (:639, the third
 * of the page's three early returns, after loading :604 and error :613) — and
 * every card this spec
 * asserts must be created by its API leg and deleted in its finally. The three
 * empty-mount asserts — zones [] (F-256's leg, `pagination.total` 0) and
 * members [] / vehicles [] (F-258's leg, both bare lists: household.py:61 and
 * household.py:218) — are ALSO the proof that no earlier golden spec leaked
 * rows into this stack; run 4 never issued the vehicles GET, so the F-258 leg
 * below is what first measured its 200 and its emptiness. HONEST SCOPE: the
 * proof covers a leaked MEMBER or ZONE, which the teardown re-reads to [], NOT
 * a leaked VEHICLE — that DELETE is trusted on its 204 with no list re-read.
 * The seeding absence is measured, not assumed (harness.ts:15-24, controls).
 *
 * Which camera: the page shows ONE camera's zones — `const firstCameraId =
 * cameras[0]?.id` (ZonesPage.tsx:416) — and the inventory's own F-256 evidence
 * says so ("Only the first camera's zones are shown"). feature_check seeds one
 * camera per scenario folder (seed_cameras, scripts/feature_check.py:1284); their
 * ids are SLUGS (`cat-on-porch` answers `cat_on_porch`), not UUIDs — zones.py:89
 * uuid4 is the ZONE id — and GET /api/cameras has no ORDER BY (list_cameras,
 * backend/api/routes/cameras.py:151; the file's order_by calls :568/:1798 are
 * other routes). So items[0].id shares the client's endpoint and INDEX, which
 * ASSUMES spec-page agreement. Run 8 broke it: see the `const cameraId` bind.
 *
 * Locator ground truth (every cite re-read at the head this file lands in;
 * this repo mixes frameworks per-element, harness.ts:40-64, so each was
 * checked against the element it targets):
 *  - zone card: data-testid={`zone-card-${zone.id}`} ZonesPage.tsx:307,
 *    <h3>{zone.name}</h3> :316, Type row :327-328 (labelled by the zoneType
 *    labels map at :296-302: 'driveway' renders "Driveway"), Status
 *    :331-333 (enabled renders "Active"), Priority :337-339.
 *  - grid container: data-testid="zone-grid" :753, and it maps
 *    filteredZones (:755, filter at :507-512) inside an empty-of-filter
 *    branch ("No zones match the selected filter." :746-748) — so a filter
 *    change is observable as a COUNT change, and it's the same filteredZones
 *    the CSV export reads (handleExport :534-561, mapping filteredZones at
 *    :539), which makes "the export honors the filter" a real end-to-end leg,
 *    not a guess.
 *    WHICH COUNT, precisely — run 4 (hsi-check-20261011213827-91ad72) measured
 *    this the hard way. "zone-grid" is ONE wrapper <div> (:751-754) whose
 *    CHILDREN are the cards, so
 *    expect(getByTestId('zone-grid')).toHaveCount(n) can only ever observe 1
 *    element, at any population. My first draft therefore paired a leg that
 *    passed for the WRONG reason (filter to one type → toHaveCount(1), which
 *    the container satisfies even with zero zones) with one that could only
 *    fail (filter back to all → toHaveCount(2)). Card populations go through
 *    zoneCards() below, never through the container; the container is asserted
 *    only for existence.
 *  - type filter: NATIVE <select> data-testid="zone-type-select" :219-227
 *    (Playwright maps a single <select> to role combobox; selectOption, never
 *    click-then-click — harness.ts:47-51).
 *  - time range: ZonesPage.tsx role="group" (:239) with
 *    aria-label="Time range selection" (:240), the group <div> opening at :237,
 *    buttons with aria-pressed (:248), default state '24h' (:459), options
 *    1h/6h/24h/7d (:109-114). SHIPPED-HONESTY NOTE: the row says "filters by
 *    … time range", but the state lands in hoursLookback (:660) and its only
 *    consumer is the hoursLookback prop passed to <ZoneAnomalyFeed> at :790 —
 *    which sits INSIDE THE OVERVIEW Tab.Panel (:733-797; the analytics panel
 *    opens at :800), wrapped by the alerts PanelWrapper (panelType="alerts"
 *    :785). It does not filter the overview CARDS, and it is not an analytics
 *    prop — my first draft called it "the ANALYTICS tab panel prop", which got
 *    the line right and the label wrong. This spec pins what ships: the
 *    pressed state moves and
 *    the overview grid count does NOT change. Pinning a card-count change
 *    here would be writing the test the row wishes were true.
 *  - export: data-testid="export-button" :270 is common/Button, which spreads
 *    props onto the native <button> (components/common/Button.tsx:146,:168),
 *    so getByTestId resolves to a clickable button. The file is a client-side
 *    Blob: headers ['ID','Name','Type','Enabled','Priority','Color','Created
 *    At'], rows from filteredZones with zone_type raw and enabled as Yes/No,
 *    name `zones-export-${ISO date}.csv` (the assignment is ZonesPage.tsx:555,
 *    inside handleExport :534-561). The repo
 *    precedent for catching it is waitForEvent('download') set BEFORE the
 *    click (frontend/tests/e2e/specs/event-export.spec.ts:482 — the repo root
 *    is not frontend/, so cite the path git ls-tree prints, not the one a
 *    cd'd shell would have used; the line is verified: that file's :482 is
 *    `const downloadPromise = page.waitForEvent('download');`).
 *  - full screen: ZonesPage.tsx each panel is data-testid={`panel-${panelType}`}
 *    :376 with an aria-labelled toggle "Enter full screen"/"Exit full screen"
 *    :385-387. The state is a SINGLE panel (fullScreenPanel !== null, the
 *    state at :460 read at :661) and enabling one UNMOUNTS the others — the
 *    Trust Matrix panel renders only
 *    `fullScreenPanel === null || fullScreenPanel === 'trust'` (:768-769) —
 *    so the observable pin is panel-trust disappearing and returning.
 *  - trust matrix: rendered on the overview tab, which is the default
 *    (ZonesPage.tsx activeTab state 'overview' :462; ZoneTrustMatrix mounted
 *    at :776).
 *    <h3>Zone Trust Matrix</h3> ZoneTrustMatrix.tsx:580; Members/Vehicles
 *    toggle buttons :584-:606 with viewMode default 'members' — the default is
 *    the destructured `initialViewMode = 'members'` at ZoneTrustMatrix.tsx:451,
 *    which :455 only consumes. Cell = <button> aria-label
 *    `${entityName} has ${Label} trust
 *    in ${zoneName}` :172-177 — the whole pin rides on that string; labels
 *    are Full/Partial/Monitor/None — TRUST_LEVEL_CONFIGS :78-:110, NOT :126
 *    (TRUST_LEVELS) — entityName is member.name or vehicle.description (useZoneTrustMatrix
 *    .ts:454,:478). Editor on click: "Select Trust Level" + one button per
 *    level (TrustEditor, ZoneTrustMatrix.tsx:198-239); VEHICLES get only
 *    Partial/None (:199-:202) — shipped limitation, pinned as shipped.
 *  - the trust WRITE: level pick → PUT /api/zones/{id}/household
 *    (upsertZoneHouseholdConfig, useZoneTrustMatrix.ts:231, PUT at :236; handler
 *    upsert_zone_household_config zone_household.py:71, answering 200
 *    (status.HTTP_200_OK at :69) on both branches of the create-or-update
 *    `if existing_config is None` at :141-151). The level→config mapping, read
 *    both directions:
 *      full    → owner_id = memberId          (hook :543-544)
 *      partial → allowed_member_ids          (hook :546-548)
 *      monitor → access_schedules entry      (hook :549-559)
 *      none    → removed from all lists      (hook :560-562)
 *    and computeTrustLevelForMember (useZoneTrustMatrix.ts:320) derives None
 *    when no config exists (:325), so a fresh zone's first cell reads "has None
 *    trust".
 *  - the cell REPAINT after the write is not luck: the mutation invalidates
 *    zoneTrustQueryKeys.config(zoneId) (useZoneTrustMatrix.ts:301-303), the
 *    same key the matrix's configs query reads (:391), so the button's
 *    aria-label changing is an honest assert, not a prayer.
 *  - /api/household/members returns a BARE LIST (response_model=list[...]
 *    household.py:61) and fetchMembers returns the list verbatim — the
 *    return is useHouseholdApi.ts:255, not the :250 signature — AGREE, so the
 *    trust matrix is NOT a second instance of the F-275 envelope-`.length`
 *    break (ruling 118). That falsification was run before writing this and
 *    came back clean; the spec still asserts the bare shape so a future
 *    envelope change breaks LOUDLY instead of silently emptying the matrix.
 *
 * Deliberately NOT here: the health color dot (heuristic getZoneHealth, no
 * row text behind it), the analytics/comparison tabs (different rows, and
 * Tremor territory per harness.ts:44-46), and the matrix's OWN filters: two
 * <select>s (zone type :312, trust level :337) and member/vehicle CHECKBOXES
 * (:372, :407), all in ZoneTrustMatrix.tsx:312-407 — the page-level filter
 * already pins filteredZones; its DELETE route is cleanup, not row surface.
 */
import type { Download, Locator, Page } from '@playwright/test';

import { expect, test } from '../guard';

import {
  adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  type Harness,
} from './harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** Names no other test can collide with. Uniqueness matters because the
 *  empty-state legs assert 0-length lists: a leaked row from any earlier spec
 *  would fail THIS spec for someone else's reason. */
const ZONE_A = 'Golden DO-3 Driveway';
const ZONE_B = 'Golden DO-3 Yard';
const MEMBER = 'Golden DO-3 Member';
const VEHICLE = 'Golden DO-3 Vehicle';

/** The schema demands >=3 points (min_length=3, backend/api/schemas/zone.py:180)
 *  and five geometry checks (_validate_polygon_geometry, :115-:155): 2 values per
 *  point, normalized 0-1, no duplicate neighbours, positive area, no self-cross. */
const COORDS = [
  [0.1, 0.1],
  [0.5, 0.1],
  [0.5, 0.5],
  [0.1, 0.5],
];

function newZone(name: string, zoneType: string, priority: number) {
  return {
    name,
    zone_type: zoneType,
    coordinates: COORDS,
    color: '#3B82F6',
    enabled: true,
    priority,
  };
}

async function signIn(page: Parameters<typeof login>[0], h: Harness) {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

/** Read a caught download's bytes as text. createReadStream() can answer
 *  null (the type says so) — an assert, because a null read here would
 *  otherwise show up as an empty CSV and read like a product defect. */
async function downloadText(download: Download): Promise<string> {
  const stream = await download.createReadStream();
  if (!stream) throw new Error(`download ${download.suggestedFilename()} has no readable stream`);
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk as ArrayBuffer));
  return Buffer.concat(chunks).toString('utf8');
}

/** The ZONE CARDS inside the overview grid — the population a count assert
 *  must target.
 *
 *  getByTestId('zone-grid') is the wrapper <div> at ZonesPage.tsx:751-754, so
 *  it is ONE element whether the grid holds zero zones or fifty; run 4
 *  (hsi-check-20261011213827-91ad72) proved it at the artifact — "locator
 *  resolved to 1 element … unexpected value \"1\"" against an expected count
 *  of 2. Counting CARDS means counting the per-zone divs, and the only stable
 *  per-zone handle is the testid ZonesPage.tsx:307 mints from the
 *  server-minted uuid, which a spec can only know from its own POST — so this
 *  takes the ids the caller created. An empty id list THROWS rather than
 *  returning a locator: the join yields ^zone-card-()$, which matches only the
 *  literal "zone-card-" and no real testid — so it reads as a count of 0. */
function zoneCards(page: Page, ids: string[]): Locator {
  if (ids.length === 0) throw new Error('zoneCards() needs at least one created zone id');
  const escaped = ids.map((id) => id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return page.getByTestId(new RegExp(`^zone-card-(${escaped.join('|')})$`));
}

test.describe('DO-3 zones golden path', () => {
  test('F-256 grid: empty mount, cards with type/status/priority, type filter, browser-built CSV, full screen', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // --- Which camera does the PAGE use? Observed, not assumed. ---
    // The page hardcodes it: `const firstCameraId = cameras[0]?.id`
    // (ZonesPage.tsx:416) with no selector anywhere on /zones, so a spec cannot
    // choose — it can only learn. Taking items[0] from the spec's own GET is
    // what this file used to do, and golden run 8 (hsi-check-20261012001430-
    // 93da95) falsified that: the page read `cat_on_porch` and the spec wrote to
    // another camera, so the cards leg timed out against an honest empty page.
    // The list route has no ORDER BY (list_cameras,
    // backend/api/routes/cameras.py:151), so two unordered scans of one table
    // are free to disagree; spec and page DO share the cache key
    // (CacheKeys.cameras_list_by_status at cameras.py:194), which is
    // why the fix is to READ the page's choice rather than to re-derive it.
    const apiCams = await api.getJson('/api/cameras');
    expect(apiCams.status, 'GET /api/cameras answers 200').toBe(200);
    const seeded = (apiCams.body?.items ?? []).map((c: { id: unknown }) => String(c.id));
    expect(
      seeded.length,
      `the stack seeds cameras, got ${JSON.stringify(apiCams.body)}`
    ).toBeGreaterThan(0);

    // The page's own zones fetch, captured before the navigation that triggers
    // it. The matcher must EXCLUDE the TanStack placeholder cameras — it is the
    // same /api/cameras/{id}/zones shape, and it answers 404 (6 times per run in
    // BOTH the green and the red run, so it discriminates nothing; run 7 and run
    // 8 compose.log both grep -c 6). A predicate that can never fire is worse
    // than a wrong assert, so this one is pinned by apiPath equality, the
    // harness's own rule (harness.ts:198-212).
    const pageZonesCall = page
      .waitForResponse((r) => {
        const m = /^\/api\/cameras\/([^/]+)\/zones$/.exec(apiPath(r.url()));
        return !!m && !m[1].startsWith('placeholder-') && r.status() === 200;
      })
      .catch(() => null);

    await page.goto(`${h.ui}/zones`, { waitUntil: 'domcontentloaded' });
    const firstMount = await pageZonesCall;
    expect(firstMount, 'the page fetches its camera zones on mount').not.toBeNull();
    const cameraId = decodeURIComponent(
      /^\/api\/cameras\/([^/]+)\/zones$/.exec(apiPath(firstMount!.url()))![1]
    );
    // The observation is cross-checked against the spec's own camera list, so a
    // matcher that bound to something other than a seeded camera fails HERE,
    // where the reason is legible, instead of at a card count five seconds later.
    expect(
      seeded,
      `the page's camera ${cameraId} is one the stack seeded (${seeded.join(', ')})`
    ).toContain(cameraId);

    const before = await api.getJson(`/api/cameras/${cameraId}/zones`);
    expect(before.status, 'GET /api/cameras/{id}/zones answers 200').toBe(200);
    expect(before.body?.items, 'the fake-AI stack seeds no zones').toHaveLength(0);
    expect(before.body?.pagination?.total, 'pagination.total agrees with the empty list').toBe(0);

    const createdA = await api.send(
      `/api/cameras/${cameraId}/zones`,
      'POST',
      newZone(ZONE_A, 'driveway', 7)
    );
    expect(createdA.status, 'POST zone A answers 201').toBe(201);
    const zoneA = String(createdA.body?.id);
    expect(zoneA, 'the POST response carries the server-minted id (zones.py:89 uuid4)').not.toBe(
      'undefined'
    );
    const createdB = await api.send(
      `/api/cameras/${cameraId}/zones`,
      'POST',
      newZone(ZONE_B, 'yard', 3)
    );
    expect(createdB.status, 'POST zone B answers 201').toBe(201);
    const zoneB = String(createdB.body?.id);

    // A second observation of the page's derived camera across a re-navigation,
    // then the card leg.
    //
    // WHY THE PREVIOUS VERSION OF THIS BLOCK WAS WRONG TWICE. Run 9 (hsi-check-
    // 20261012013000-1b2d11) failed it with Expected "person_at_door" / Received
    // "cat_on_porch" under a message that said "at remount", and that word was
    // mine, not measured: compose.log puts both camera-zone reads (01:33:09,
    // 01:33:09) and both browser GET /api/cameras reads (09.420 **449 B**, 09.815
    // **462 B**) INSIDE the first page's lifetime -- the next /zones document GET
    // is at 01:33:11. A matcher armed BEFORE a goto captures the next matching
    // response whatever caused it, and the cause here was an in-page refetch. So
    // (1) the label was false. (2) The gate was mis-specified: F-256's `when`
    // column is "opens the page; sees a card per zone with type, enabled state and
    // priority; filters by zone type and time range; clicks Export CSV (built in
    // the browser); toggles a panel to full screen" -- there is no reload step in
    // the row, so a camera-identity-across-time assert is not evidence the row
    // asked for, and red on it is not a row verdict.
    //
    // WHY THE NAVIGATION STAYS. The page learns of a zone the HARNESS created only
    // by re-reading: useZones invalidates on the PAGE's own mutations
    // (frontend/src/hooks/useZones.ts:348, :407, :452) and this spec's POSTs are
    // not those, so a re-navigation is the honest way to reach the populated state
    // the card leg needs.
    //
    // WHY THE OBSERVATION IS A REPORT, NOT A GATE. Three measured reasons.
    // (1) The page's own camera list can re-draw legally across that navigation:
    // list_cameras has no ORDER BY (backend/api/routes/cameras.py:152) and the
    // route is Redis cache-aside (CacheDep :154, key :194), so cameras[0]
    // (frontend/src/pages/ZonesPage.tsx:416) is a legal answer that can differ
    // between two reads of one endpoint. (2) An assert that the page MUST re-read
    // would also fail on a TanStack-Query cache hit, which is a cache detail, not a
    // product promise (DEFAULT_STALE_TIME is 30_000 ms,
    // frontend/src/services/queryClient.ts:42). (3) The state the page re-reads is
    // not exclusive to this test, and run 9 shows the rows are NOT traceable to the
    // only writer this artifact can name: its SECOND read of cat_on_porch carries
    // **327 B**, where every read of that endpoint in this run's nginx log BEFORE
    // that moment carries 129 B (the run's full size set there is 129, 327, 334), so
    // that read was POPULATED -- yet no browser created a zone anywhere in run 9
    // (the only zone writes in that log are PUT /api/zones/{uuid}/household x7 and
    // one DELETE, at 01:33:12 and 01:33:20, and /zones has no create affordance). Note what does NOT explain this, because each of these was a
    // claim in an earlier draft of this comment and each is refuted: golden is
    // ONE WORKER AND SERIAL (frontend/playwright.config.ts:287-288 override the
    // root fullyParallel at :70), so no sibling spec runs during this one -- this
    // test's body is 1.45 s and the GET /api/cameras/deleted I first blamed is 30 s
    // later; the absence of harness writes from nginx proves nothing, because the
    // vhost logged 155 writes in run 9 and ALL 155 carry a Referer, 0 without, i.e.
    // it records browser traffic only and client writes never appear in it; and the
    // GET /api/cameras size step happens in the GREEN run too (hsi-check-
    // 20261011230957-869976: 450 B x8 then 460 B x60), so it discriminates nothing.
    // Asserting page==spec across the navigation would therefore convert rows this
    // batch neither created nor can name into this batch's red.
    const zoneCameraOf = (u: string) => {
      const m = /^\/api\/cameras\/([^/]+)\/zones$/.exec(apiPath(u));
      return m && !m[1].startsWith('placeholder-') ? decodeURIComponent(m[1]) : null;
    };
    // The matcher is armed BEFORE the goto -- a listener cannot catch a response
    // that already flew -- so the timing word in the report is CARRIED IN A
    // FLAG, not assumed from the arm point. That flag is annotation only: the
    // predicate never consults it, so no matching response can be skipped by it
    // (a gate keyed on a flag set after an await can time out on a response that
    // legitimately arrived first, which is not a product failure).
    let navResolved = false;
    const reRead = page
      .waitForResponse((r) => zoneCameraOf(r.url()) !== null && r.status() === 200, {
        timeout: 15_000,
      })
      .catch(() => null);

    try {
      await page.goto(`${h.ui}/zones`, { waitUntil: 'domcontentloaded' });
      navResolved = true;
      await expect(page.getByTestId('zones-page')).toBeVisible();
      // The report. Exactly one warn line from this test either way — the if
      // and the else both print — so absence of a re-read is as visible in
      // golden-playwright.log as its presence. eslint allows
      // console.warn (frontend/eslint.config.mjs:130).
      const reReadCall = await reRead;
      if (reReadCall) {
        console.warn(
          `[F-256] the page re-read zones for camera ` +
            `${zoneCameraOf(reReadCall.url())} ${navResolved ? 'AFTER' : 'BEFORE'} the ` +
            `remount navigation resolved; this spec wrote to ${cameraId}. ` +
            `GET /api/cameras is unordered (cameras.py:152). REPORT ONLY: F-256's ` +
            `when column does not promise a reload, so this gates nothing.`
        );
      } else {
        console.warn(
          `[F-256] no real /api/cameras/{id}/zones response within 15 s of the ` +
            `remount (camera this spec wrote to: ${cameraId}). REPORT ONLY.`
        );
      }

      // 1. Cards: the empty copy is gone, and both cards show the three
      //    fields the row promises.
      //    The message carries the camera and both zone ids so that a red here
      //    says WHICH camera the page disagrees about -- run 8's failure printed
      //    a locator and nothing else, which is why it took two runs to explain.
      await expect(
        page.getByText('No zones configured'),
        `the page still reads "No zones configured" although the harness created ` +
          `zones ${zoneA} and ${zoneB} on camera ${cameraId}`
      ).toHaveCount(0);
      const cardA = page.getByTestId(`zone-card-${zoneA}`);
      const cardB = page.getByTestId(`zone-card-${zoneB}`);
      await expect(cardA).toBeVisible();
      await expect(cardB).toBeVisible();
      await expect(cardA.getByRole('heading', { name: ZONE_A, level: 3 })).toBeVisible();
      // Type renders through the ZonesPage.tsx labels map (:296-303): 'driveway'
      // → "Driveway".
      await expect(cardA.getByText('Driveway', { exact: true })).toBeVisible();
      await expect(cardB.getByText('Yard', { exact: true })).toBeVisible();
      // enabled: true renders "Active" (ZonesPage.tsx:333); priority renders
      // raw (7 at POST).
      await expect(cardA.getByText('Active', { exact: true })).toBeVisible();
      await expect(cardA.getByText('7', { exact: true })).toBeVisible();

      // 2. Type filter: NATIVE select; the grid re-renders from
      //    filteredZones, so counts move with the selection.
      const typeSelect = page.getByTestId('zone-type-select');
      await typeSelect.selectOption('driveway');
      // The container EXISTS (that is its only honest count-free assert) and
      // the CARD POPULATION is 1. Asserting the container's count here — as my
      // first draft did — would pass at any population, so the pair below is
      // existence + cards, never a count on the wrapper.
      await expect(page.getByTestId('zone-grid')).toBeVisible();
      await expect(zoneCards(page, [zoneA, zoneB])).toHaveCount(1);
      await expect(cardA).toBeVisible();
      await expect(cardB).toHaveCount(0);

      // 3. CSV WHILE FILTERED: the export reads filteredZones, so the yard
      //    row is not just absent from the cards — it is absent from the
      //    file. Header array pinned verbatim from ZonesPage.tsx:538.
      //    ROWS ARE COUNTED AMONG MY OWN IDS, not among the whole export. The
      //    first draft counted raw lines of the whole file, which silently
      //    assumes "this camera holds no zone but mine" -- an exclusivity the
      //    shared stack does not provide: golden runs are fullyParallel
      //    (frontend/playwright.config.ts:70) against one backend, and run 9
      //    shows the page re-reading a camera that already answered 327 B of
      //    zones this spec never created. Nothing discriminating is given up: an
      //    export that IGNORED the type filter would still carry zoneB and so
      //    still fails below. Foreign rows are REPORTED, not gated -- same rule
      //    as the re-read above: a neighbour's write is not this batch's verdict.
      const myRows = (csv: string) =>
        csv
          .split('\n')
          .slice(1)
          .filter((l) => l.startsWith(`${zoneA},`) || l.startsWith(`${zoneB},`));

      const filteredPromise = page.waitForEvent('download');
      await page.getByTestId('export-button').click();
      const filteredCsv = await downloadText(await filteredPromise);
      const filteredLines = filteredCsv.split('\n');
      expect(filteredLines[0], 'CSV header, verbatim from handleExport').toBe(
        'ID,Name,Type,Enabled,Priority,Color,Created At'
      );
      const filteredMine = myRows(filteredCsv);
      expect(
        filteredMine,
        `filtered export must carry exactly the driveway zone ${zoneA} of mine`
      ).toHaveLength(1);
      expect(
        filteredMine[0],
        'the row is the WHOLE zone: id,name,type,Yes,priority,color,created'
      ).toBe(`${zoneA},${ZONE_A},driveway,Yes,7,#3B82F6,${createdA.body?.created_at}`);

      // 4. Filter back to all; the unfiltered export then carries BOTH rows.
      //    The count target is the CARDS (both created ids), never the
      //    wrapper div — see zoneCards().
      await typeSelect.selectOption('all');
      await expect(zoneCards(page, [zoneA, zoneB])).toHaveCount(2);
      const allPromise = page.waitForEvent('download');
      await page.getByTestId('export-button').click();
      const allCsv = await downloadText(await allPromise);
      expect(myRows(allCsv), 'unfiltered export carries both of my rows').toHaveLength(2);
      expect(allCsv, 'the yard row rides when unfiltered').toContain(`${zoneB},${ZONE_B},yard`);
      // Visibility into the coupling this leg used to gate on. Report only.
      const foreign = allCsv
        .split('\n')
        .slice(1)
        .filter((l) => l.length > 0 && !l.startsWith(`${zoneA},`) && !l.startsWith(`${zoneB},`));
      if (foreign.length) {
        console.warn(
          `[F-256] camera ${cameraId} carried ${foreign.length} zone row(s) this spec ` +
            `did not create; REPORT ONLY, excluded from the counts above.`
        );
      }

      // 5. Time range: the pressed state moves (aria-pressed, :248) and the
      //    overview grid deliberately does NOT care (hoursLookback feeds only
      //    the analytics panel, :660/:790). Pinned as shipped — see header.
      const range = page.getByRole('group', { name: 'Time range selection' });
      await expect(range.getByRole('button', { name: '24h', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
      await range.getByRole('button', { name: '6h', exact: true }).click();
      await expect(range.getByRole('button', { name: '6h', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
      await expect(range.getByRole('button', { name: '24h', exact: true })).toHaveAttribute(
        'aria-pressed',
        'false'
      );
      // The shipped-honesty pin: the pressed state moved above, and the CARD
      // POPULATION deliberately did not (hoursLookback never reaches the
      // overview grid). Cards, not the container — see zoneCards().
      await expect(zoneCards(page, [zoneA, zoneB])).toHaveCount(2);

      // 6. Full screen: the overview panel's toggle, and the trust panel
      //    UNMOUNTING (single-panel state, :661 + the :768 render guard) and
      //    returning. This is what "toggles a panel to full screen" ships as.
      const overview = page.getByTestId('panel-overview');
      await overview.getByRole('button', { name: 'Enter full screen' }).click();
      await expect(overview.getByRole('button', { name: 'Exit full screen' })).toBeVisible();
      await expect(
        page.getByTestId('panel-trust'),
        'full screen unmounts the other panels'
      ).toHaveCount(0);
      await overview.getByRole('button', { name: 'Exit full screen' }).click();
      await expect(
        page.getByTestId('panel-trust'),
        'exiting remounts the trust panel'
      ).toBeVisible();
    } finally {
      const delA = await api.send(`/api/cameras/${cameraId}/zones/${zoneA}`, 'DELETE');
      const delB = await api.send(`/api/cameras/${cameraId}/zones/${zoneB}`, 'DELETE');
      expect(delA.status, 'DELETE zone A answers 204').toBe(204);
      expect(delB.status, 'DELETE zone B answers 204').toBe(204);
      const after = await api.getJson(`/api/cameras/${cameraId}/zones`);
      expect(
        after.body?.items,
        'the list is back to empty — proven by re-read, not by the 204s'
      ).toHaveLength(0);
    }

    await assertGuardSurvives(page, h);
  });

  test('F-258 trust matrix: None by default, cell editor writes Full/Partial/None, vehicles cap at Partial', async ({
    page,
  }) => {
    const h = harness as Harness;
    const api = await signIn(page, h);

    // --- API leg. Bare lists here, and asserted BARE: household.py:61 ships
    //     list[...], useHouseholdApi.ts:255 returns it verbatim — if either
    //     ever moves to an envelope, these toHaveLength(0) asserts break
    //     loudly instead of the matrix silently losing every column. ---
    const membersBefore = await api.getJson('/api/household/members');
    expect(membersBefore.status, 'GET /api/household/members answers 200').toBe(200);
    expect(Array.isArray(membersBefore.body), 'members is a BARE list').toBe(true);
    expect(membersBefore.body, 'the stack seeds no household members').toHaveLength(0);

    // The vehicles list is asserted for the same two reasons — the row's
    // "vehicles cap at Partial" leg is worthless if a leaked vehicle is
    // already in the grid — and BARE for the same envelope reason
    // (list_vehicles, household.py:218, no early raise: empty stack ⇒ []).
    const vehiclesBefore = await api.getJson('/api/household/vehicles');
    expect(vehiclesBefore.status, 'GET /api/household/vehicles answers 200').toBe(200);
    expect(Array.isArray(vehiclesBefore.body), 'vehicles is a BARE list').toBe(true);
    expect(vehiclesBefore.body, 'the stack seeds no vehicles').toHaveLength(0);

    const member = await api.send('/api/household/members', 'POST', {
      name: MEMBER,
      role: 'resident',
      trusted_level: 'full',
    });
    expect(member.status, 'POST member answers 201').toBe(201);
    const memberId = member.body?.id as number;
    expect(typeof memberId, 'member id is a server integer').toBe('number');

    const vehicle = await api.send('/api/household/vehicles', 'POST', {
      description: VEHICLE,
      vehicle_type: 'car',
    });
    expect(vehicle.status, 'POST vehicle answers 201').toBe(201);
    const vehicleId = vehicle.body?.id as number;

    const cameras = await api.getJson('/api/cameras');
    const cameraId = String(cameras.body?.items?.[0]?.id);
    const zone = await api.send(
      `/api/cameras/${cameraId}/zones`,
      'POST',
      newZone(ZONE_A, 'driveway', 7)
    );
    expect(zone.status, 'POST zone answers 201').toBe(201);
    const zoneId = String(zone.body?.id);

    const noConfig = await api.getJson(`/api/zones/${zoneId}/household`);
    expect(noConfig.status, 'GET /api/zones/{id}/household answers 200').toBe(200);
    // A fresh zone has NO config, and the route says so with 200 + null body
    // (zone_household.py:60-61) — NOT a 404. The matrix's "None" cells are
    // built on exactly this null.
    expect(
      noConfig.body,
      'GET /api/zones/{id}/household answers 200 null for a fresh zone'
    ).toBeNull();

    const cellButton = (entity: string, level: string) =>
      page.getByRole('button', { name: `${entity} has ${level} trust in ${ZONE_A}`, exact: true });
    const configOf = async () =>
      (await api.getJson(`/api/zones/${zoneId}/household`)).body as {
        owner_id: number | null;
        allowed_member_ids: number[];
        allowed_vehicle_ids: number[];
        access_schedules: { member_ids: number[] }[];
      };

    try {
      await page.goto(`${h.ui}/zones`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('zones-page')).toBeVisible();
      const matrix = page.getByTestId('panel-trust');
      await expect(
        matrix.getByRole('heading', { name: 'Zone Trust Matrix', level: 3 })
      ).toBeVisible();

      // 1. Default cell: no config ⇒ "None" (computeTrustLevelForMember's
      //    !config branch). The aria-label IS the grid readout.
      await expect(cellButton(MEMBER, 'None')).toBeVisible();
      // The click fetches the current config (handleCellClick,
      // ZoneTrustMatrix.tsx:486-491);
      // settle it before opening the editor so the write starts from the
      // same null the API leg proved.
      await Promise.all([
        page.waitForResponse(
          (r) => apiPath(r.url()) === `/api/zones/${zoneId}/household` && r.status() === 200
        ),
        cellButton(MEMBER, 'None').click(),
      ]);
      await expect(page.getByText('Select Trust Level')).toBeVisible();

      // 2. FULL ⇒ owner_id. (hook case 'full' :543-544)
      await Promise.all([
        page.waitForResponse(
          (r) =>
            apiPath(r.url()) === `/api/zones/${zoneId}/household` && r.request().method() === 'PUT'
        ),
        page.getByRole('button', { name: 'Full', exact: true }).click(),
      ]).then(async ([put]) => expect(put.status(), 'the trust PUT answers 200').toBe(200));
      await expect(
        cellButton(MEMBER, 'Full'),
        'the cell repaints via the invalidated config key'
      ).toBeVisible();
      let config = await configOf();
      expect(config.owner_id, 'full trust ⇒ owner_id = memberId').toBe(memberId);
      expect(config.allowed_member_ids, 'full does NOT also add to allowed').toEqual([]);

      // 3. PARTIAL ⇒ allowed_member_ids, owner released.
      await cellButton(MEMBER, 'Full').click();
      await expect(page.getByText('Select Trust Level')).toBeVisible();
      await page.getByRole('button', { name: 'Partial', exact: true }).click();
      await expect(cellButton(MEMBER, 'Partial')).toBeVisible();
      config = await configOf();
      expect(config.owner_id, 'partial clears ownership').toBeNull();
      expect(config.allowed_member_ids, 'partial ⇒ allowed_member_ids = [member]').toEqual([
        memberId,
      ]);

      // 4. MONITOR ⇒ an access_schedules entry, allowed cleared. This leg is
      //    what gives leg 5 its teeth: without a populated schedule, "none
      //    clears every schedule" is an assert over an already-empty list.
      await cellButton(MEMBER, 'Partial').click();
      await expect(page.getByText('Select Trust Level')).toBeVisible();
      await page.getByRole('button', { name: 'Monitor', exact: true }).click();
      await expect(cellButton(MEMBER, 'Monitor')).toBeVisible();
      config = await configOf();
      expect(config.allowed_member_ids, 'monitor clears the allowed list').toEqual([]);
      expect(
        config.access_schedules.map((s) => s.member_ids),
        'monitor ⇒ exactly one schedule, carrying this member'
      ).toEqual([[memberId]]);

      // 5. NONE ⇒ removed from every list, INCLUDING the schedule leg 4 wrote.
      await cellButton(MEMBER, 'Monitor').click();
      await expect(page.getByText('Select Trust Level')).toBeVisible();
      await page.getByRole('button', { name: 'None', exact: true }).click();
      await expect(cellButton(MEMBER, 'None')).toBeVisible();
      config = await configOf();
      expect(config.owner_id, 'none clears ownership').toBeNull();
      expect(config.allowed_member_ids, 'none clears allowed').toEqual([]);
      expect(config.access_schedules, 'none clears the schedule monitor wrote').toHaveLength(0);

      // 6. Vehicles view: same grid shape, and the editor OFFERS ONLY
      //    Partial/None (:199-202) — the shipped cap, pinned as shipped.
      await matrix.getByRole('button', { name: 'Vehicles', exact: true }).click();
      await expect(cellButton(VEHICLE, 'None')).toBeVisible();
      await cellButton(VEHICLE, 'None').click();
      await expect(page.getByText('Select Trust Level')).toBeVisible();
      await expect(
        page.getByRole('button', { name: 'Full', exact: true }),
        'vehicle editor offers no Full'
      ).toHaveCount(0);
      await expect(
        page.getByRole('button', { name: 'Monitor', exact: true }),
        'vehicle editor offers no Monitor'
      ).toHaveCount(0);
      await page.getByRole('button', { name: 'Partial', exact: true }).click();
      await expect(cellButton(VEHICLE, 'Partial')).toBeVisible();
      config = await configOf();
      expect(
        config.allowed_vehicle_ids,
        'vehicle partial ⇒ allowed_vehicle_ids = [vehicle]'
      ).toEqual([vehicleId]);
    } finally {
      // Order matters: the config references member+vehicle ids.
      const cfg = await api.send(`/api/zones/${zoneId}/household`, 'DELETE');
      expect(cfg.status, 'DELETE the household config answers 204').toBe(204);
      const dz = await api.send(`/api/cameras/${cameraId}/zones/${zoneId}`, 'DELETE');
      expect(dz.status, 'DELETE the zone answers 204').toBe(204);
      const dv = await api.send(`/api/household/vehicles/${vehicleId}`, 'DELETE');
      expect(dv.status, 'DELETE the vehicle answers 204').toBe(204);
      const dm = await api.send(`/api/household/members/${memberId}`, 'DELETE');
      expect(dm.status, 'DELETE the member answers 204').toBe(204);
      const membersAfter = await api.getJson('/api/household/members');
      expect(membersAfter.body, 'members back to [] — proven by re-read').toHaveLength(0);
      const vehiclesAfter = await api.getJson('/api/household/vehicles');
      expect(vehiclesAfter.body, 'vehicles back to [] — proven by re-read').toHaveLength(0);
      const zonesAfter = await api.getJson(`/api/cameras/${cameraId}/zones`);
      expect(zonesAfter.body?.items, 'zones back to [] — proven by re-read').toHaveLength(0);
    }

    await assertGuardSurvives(page, h);
  });
});
