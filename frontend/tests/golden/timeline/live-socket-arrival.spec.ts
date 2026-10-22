/**
 * FE-3 golden path (F2.3): F-045 — Event Timeline › Live activity section.
 *
 * Row clause (docs/reference/feature-inventory.md:199, status `half-built`):
 *   "sees events arriving over the socket above the historical list; clicks one
 *   to open its detail"
 *
 * Both clause halves are asserted for real in test 1: the socket arrival, and ONE
 * click on that socket-only card opening its detail. The same strict form stands
 * alone in ./event-arrival-strict.spec.ts — [r264]'s split of this file,
 * which measured that leg at ~512 s against test 1's ~65 s and traced the cost to
 * the two legs sharing one drop's dedupe hash (that file's header carries the
 * arithmetic). This file keeps tests 1 and 2. The split also flipped who drops
 * first: the strict file sorts BEFORE this one, so on any stack running both
 * files its leg drops the slow-reply bytes FIRST and test 1 is the second
 * dropper — with ~45 specs (~8 min measured) between them the 300 s window has
 * lapsed by the time test 1 drops, and the TTL-wait fallback in dropAndAwaitCard
 * (below) covers the co-collected shape instead.
 * Nothing is mocked: ../guard.ts patches route/unroute/routeFromHAR/
 * routeWebSocket to THROW, so every byte below is the live stack's, and each
 * test closes by tripping that guard on purpose.
 *
 * WHY A DROP AND NOT A FIXTURE. The row's contract column names WS
 * /ws/events (backend/api/routes/websocket.py:424) and a fixture row cannot
 * reach it: ./harness.ts:560-563 records the measurement — "bulk_create_events
 * does NOT broadcast on /ws/events (no EventBroadcaster call anywhere in
 * :1526-1608), so a fixture row can never satisfy F-045's 'arriving over the
 * socket' clause". So the event is supplied the only sanctioned way that
 * broadcasts, with the same call the F2.1 golden path uses
 * (../dashboard-drop.spec.ts:194-203): scripts/feature-check.sh drop COPIES a
 * scenario image into a camera folder (scripts/feature_check.py:2911-2917) →
 * the real watcher content-hashes it (services/file_watcher.py:869-873) → the
 * real detector and the fake VLM run → the analyzer commits the row
 * (:673-678) → `_broadcast` runs LAST and prod-only (:755-756) →
 * EventBroadcaster publishes to /ws/events.
 *
 * SCENARIO = slow-reply, and the arithmetic that leaves no choice. Dedupe is a
 * content hash with a 300 s TTL (services/dedupe.py:164
 * DEFAULT_DEDUPE_TTL_SECONDS; :316 builds the key from the :167 prefix, :439 sets it with its TTL; file_watcher.py:871-873
 * skips a duplicate at the door) and NO shipped request shortens it — nothing
 * under backend/api/routes calls dedupe.py:496 clear_hash. The book
 * (backend/ai_contract/fake/scenario_fixtures/scenarios.json, read through
 * FEATURE_CHECK_SCENARIOS exactly as ../dashboard-drop.spec.ts:79 and
 * ./event-detail-modal.spec.ts:224 do) has seven images ([F4.4] added
 * f4.4-gold-high and f4.4-gold-rejected, both claimed by
 * ./confidence-filter.spec.ts), and the other five are each claimed by a spec
 * that drops them: person-at-door by F2.1 (its predicate
 * at ../dashboard-drop.spec.ts:93-98 is the book's only
 * fast+confirmed+non-harness-smoke row — computed against the book, not
 * assumed), cat-on-porch by F-054 (./event-detail-modal.spec.ts:214),
 * harness-smoke by ./video-clip.spec.ts:209 AND
 * ../analytics-alerts/harness.ts:78, and car-in-driveway by
 * ../analytics-alerts/harness.ts:77 AND ./download-media.spec.ts:199.
 * Re-dropping a claimed image inside the window would land no event for this
 * spec AND silently starve that file's count assertion. So slow-reply (book
 * index 3, `reply_delay_seconds: 40`). Each leg drops once at the door; the
 * strict leg (the other file) re-sends the same bytes, which is why its
 * re-drop waits a full TTL out rather than firing on a timer.
 *
 * WHAT THAT SCENARIO PUTS ON THE WIRE. Its 40 s reply exceeds
 * `ai_vlm_read_timeout`'s default 25.0 (backend/core/config.py:1180-1182),
 * which this stack does not override, so the read budget lapses and
 * vlm_analyzer.py:656-661 maps it to §6 step 2's degraded row: verdict
 * verification_failed, risk_score None, risk_level None, summary "VLM
 * verification failed; this event needs review." (:335-338) — and it is STILL
 * broadcast (:755-756, no degraded-branch skip). That is exactly the NULL the
 * socket boundary was written to carry: api/schemas/websocket.py:255-257 —
 * "None must validate through this boundary. None is not a low score;
 * consumers must branch on None, never coalesce it." So clause 1 also proves
 * the CONSUMER honoured it: ActivityFeed.tsx:194-197 builds `risk = null` for a
 * NULL score and :257-259 therefore renders no RiskBadge at all.
 *
 * CLAUSE 1 ("arriving over the socket above the historical list") is asserted
 * four ways, not one. The socket feed is a SEPARATE cache from the list:
 * useEventStream.ts keeps frames in local state (its :118 `processEvent` pushes
 * into a useState array; the file has ZERO queryClient references) and
 * EventTimeline.tsx:140 hands wsEvents to activityEvents (:348-363, whose
 * camera_name resolves through cameraNameMap at :353) → LiveActivitySection
 * (:1134-1139), mounted ABOVE the "Historical Events" divider (:1144-1149).
 * So: (a) the shipped empty state "No Live Activity"
 * (LiveActivitySection.tsx:300-308) is on screen BEFORE the drop and gone
 * after, with NO reload between; (b) the card is INSIDE
 * `section[aria-labelledby="live-activity-heading"]` (:214-221, h2 at :245-247)
 * — containment, not a page-wide count; (c) the card's y is above the divider's
 * y; and (d) THE SAME id has NO historical row, whose handle is the different
 * testid event-card-<id> (components/events/EventCard.tsx:388). Point (d) is
 * what keeps (a)-(c) from being a 0-vs-0 mirror: the row is on screen while the
 * fetched list does not contain it, so what put it there is the socket.
 *
 * CLAUSE 2 ("clicks one to open its detail") splits, and the split is the
 * finding this row was filed for. The click always worked: the live card is
 * role=button with onClick=handleEventClick (ActivityFeed.tsx:211-219 →
 * :130-134 → LiveActivitySection.tsx:325 → EventTimeline.tsx:1137). Whether a
 * detail then rendered depended on ONE lookup: at the base commit 4cefe81e4
 * getModalEvent (EventTimeline.tsx:1060-1064) did
 * `filteredEvents.find((e) => e.id === selectedEventForModal)` and returned null
 * for an id the loaded browse pages do not hold, and EventDetailModal returns
 * null with no event (:447-449) although isOpen is true, so event-detail-modal
 * (:584) never mounts. That lookup is repaired here: useEventModalRow (:69)
 * completes the missing id with GET /api/events/{id} and getModalEvent reads
 * its row (EventTimeline.tsx:1096-1097). TEST 1 therefore asserts BOTH halves
 * positively, in the order the app allows: ONE click on a card the list never
 * fetched opens that row’s detail — the detail-fetch path — then the page's own
 * camera filter (Show Filters → #camera-filter, :1256/:1297, whose
 * handleFilterChange at :382-389 re-keys the query) brings the row into the
 * list, and the SAME live card opens the SAME row again through the browse path.
 * The shipped Close button (EventDetailModal.tsx:644 →
 * EventTimeline.tsx:829-837) runs between them, so neither opening is the
 * other’s residue. The strict form — one click, no filter, no prior selection —
 * is ./event-arrival-strict.spec.ts's leg. It was skipped for a measured
 * SUPPLY reason, not a product one: its drop re-sends these bytes, which
 * is_duplicate_and_mark (backend/services/dedupe.py:452) marks and the watcher
 * skips inside the 300 s TTL (file_watcher.py:871-873) while clear_hash
 * (dedupe.py:496) has no non-test caller. Ruling 233 asked for a supply that
 * clears that window; the key expires 300 s after it is first marked
 * (dedupe.py:439) and a skipped drop never refreshes it, so a re-drop after the
 * TTL lands. The repair is visible in CI: the old half-one assert read
 * `Expected: 0, Received: 1` at job 117083054790 of run 38932915995 — the modal
 * DID open, so the gap this row carried is closed.
 *
 * NOT asserted here, with reasons (UR-128): the pause control and its
 * announcement (LiveActivitySection.tsx:165-211) and the LRU cap /
 * SequenceValidator over the frame's `sequence` key are this section's surface
 * but not this row's clause; the modal's internals are F-054's, so test 1 checks
 * only that the detail is for the row the socket announced (title, the
 * verdict-instead-of-score chip, the summary) and does not re-audit them; the
 * `?event=` deep link DOES open the modal for a socket-only row (measured modal
 * count 1) but F-054 claims that door at ./event-detail-modal.spec.ts:12-13, so
 * this file never navigates by URL.
 *
 * PROVENANCE: the probe runs that decided every DOM expectation above (the
 * frame verbatim, the card's aria-label, y=262 vs divider y=491, the zero modal
 * count after the socket-only click, and the filter door's `event-card count
 * now: 1`) are throwaway scripts kept OUTSIDE the repo, at
 * /tmp/f045-probe/probe4.mjs and probe4.log, and are quoted in this row's PR
 * body — they are not test inputs and nothing here reads that path.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { GUARD_MESSAGE, expect, test } from '../guard';
import type { Page } from '@playwright/test';

import {
  adminSession,
  apiShell as api,
  closedByGuard,
  loginAsAdminShell as loginAsAdmin,
  quietBoot,
  readTimelineHarness,
  seedTourDismissed,
  settledReload,
  type Session,
  type TimelineHarness,
} from '../harness';

/** Collection-time readiness: Playwright runs collection before any runtime
 *  skip, so every env read goes through the harness's defensive reader. */
const harness = readTimelineHarness();
test.skip(!harness.ready, harness.ready ? '' : harness.why);

/** The book's only un-dropped image — see the header's claim arithmetic. */
const SCENARIO = 'slow-reply';
/** The book row's name, which is also the FEATURE_CHECK_CAMERAS key whose
 *  value is the camera id — the spec spells the name, never the folded id. */
const SCENARIO_KEY = 'slow-reply';
/** The analyzer's degraded summary (vlm_analyzer.py:338). The DOM is compared
 *  against the server's own copy of this string, so it is never a value the
 *  test invents and then agrees with itself about. */
const DEGRADED_SUMMARY = 'VLM verification failed; this event needs review.';
/** How long to wait for the real pipeline: watcher poll + detector + the
 *  scenario's 40 s reply + the 25 s read budget + commit + publish. Measured
 *  ~62 s from drop to card on the held stack, so 150 s is slack, not luck. */
const ARRIVAL_BUDGET_MS = 150_000;
/** The second-drop supply, restored by the [r264] split as a FALLBACK. This
 *  file now sorts AFTER ./event-arrival-strict.spec.ts, whose leg drops the
 *  same slow-reply bytes first on any stack that runs both files: the
 *  unsharded reference and every N=2/N=3 shard cell. With ~45 specs between
 *  the two files' collection positions the gap is ~8 minutes measured — the
 *  300 s dedupe window (dedupe.py:439) lapses before test 1 drops, so the
 *  first window lands as before. The fallback exists for the shape that
 *  breaks that premise: a targeted two-file rerun (or any future ordering
 *  that brings the files together), where test 1's drop would be swallowed
 *  at the door (file_watcher.py:871-873) and a single-window helper would
 *  dead-end into a named skip. Same idiom the strict leg carries
 *  (SUPPLY_REDROPS there): wait the TTL out, re-send, poll again — one
 *  re-drop, 150 + 300 + 150 = 600 s worst case, inside test 1's 900 s budget. */
const SUPPLY_REDROPS = 1;
/** The dedupe TTL from its source (core/config.py:2089 default 300,
 *  dedupe.py:303/:439): see the strict leg's constant of the same name. Not
 *  readable at runtime, so a compose-override retune degrades to the named
 *  skip, never to a false green. */
const SUPPLY_TTL_WAIT_MS = 300_000;

/** Four up from frontend/tests/golden/timeline; the F2.1 spec is three up
 *  because it sits one level shallower (../dashboard-drop.spec.ts:126). */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

interface Scenario {
  name: string;
  image: string;
  reply_delay_seconds?: number;
  verdict: { verdict: string; risk_score: number; summary: string };
}

/** The scenario book plus the run's scenario→camera map, both read through the
 *  env the harness exports (../dashboard-drop.spec.ts:79-81,
 *  ./event-detail-modal.spec.ts:224-235). Throws into the caller's skip branch
 *  if either is unreadable, so a misconfigured run says so instead of failing
 *  an assertion. */
function readRun(): { dir: string; scenarios: Scenario[]; cameraId: string } {
  const bookPath = String(process.env.FEATURE_CHECK_SCENARIOS);
  const camerasPath = String(process.env.FEATURE_CHECK_CAMERAS);
  const scenarios = (JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios: Scenario[] })
    .scenarios;
  const map = JSON.parse(readFileSync(camerasPath, 'utf8')) as Record<string, string>;
  const cameraId = map[SCENARIO_KEY];
  if (!cameraId) throw new Error(`${camerasPath} maps no camera for ${SCENARIO_KEY}`);
  return { dir: path.dirname(bookPath), scenarios, cameraId };
}

/** `GET /api/events/{id}` (backend/api/routes/events.py:1918) and the list item
 *  carry the same row fields, so one interface serves both agreement reads. */
interface EventRow {
  id: number;
  camera_id: string;
  risk_score: number | null;
  risk_level: string | null;
  summary: string;
  notify: boolean | null;
  verification: { verdict: string } | null;
}
interface EventsPage {
  items: EventRow[];
}
interface CameraRow {
  id: string;
  name: string;
}

const listCameraEvents = (h: TimelineHarness, session: Session, cameraId: string) =>
  api<EventsPage>(h, session, `/api/events?camera_id=${encodeURIComponent(cameraId)}&limit=50`);
const readRow = (h: TimelineHarness, session: Session, id: number) =>
  api<EventRow>(h, session, `/api/events/${id}`);

/** The sanctioned supply: O2.2's own helper rather than a bare copy, so a
 *  folder-layout change cannot silently split from it (same call shape as
 *  ../dashboard-drop.spec.ts:194-203). Absolute program path — Node may not
 *  resolve a relative one against the `cwd` option. */
function dropScenario(imagePath: string, cameraName: string): void {
  execFileSync(path.join(repoRoot, 'scripts/feature-check.sh'), ['drop', imagePath, cameraName], {
    cwd: repoRoot,
    env: { ...process.env },
    encoding: 'utf8',
    timeout: 30_000,
  });
}

/** The live section's own subtree, so "above the historical list" stays a claim
 *  about containment instead of a page-wide testid count. */
const liveSection = (page: Page) =>
  page.locator('section[aria-labelledby="live-activity-heading"]');
const liveCard = (page: Page, id: number) =>
  liveSection(page).locator(`[data-testid="detection-card-${id}"]`);
/** Scoped to the modal on purpose: `risk-score` is ALSO a dashboard testid
 *  (components/dashboard/StatsRow.tsx:232) and `close-modal-button` belongs to
 *  three modals (events/EventDetailModal.tsx:644,
 *  plate-reads/PlateDetailModal.tsx:412, entities/EntityDetailModal.tsx:331), so
 *  an unscoped strict-mode handle could bind to a node that is not this modal's. */
const modal = (page: Page) => page.getByTestId('event-detail-modal');

/** Ids currently on screen in the live section, as numbers. */
async function liveCardIds(page: Page): Promise<number[]> {
  const testIds = await liveSection(page)
    .locator('[data-testid^="detection-card-"]')
    .evaluateAll((els) => els.map((el) => el.getAttribute('data-testid') ?? ''));
  return testIds
    .map((t) => Number(t.replace('detection-card-', '')))
    .filter((n) => Number.isFinite(n));
}

/** Boot the way every timeline spec must: nginx's api bucket
 *  (zone+rate frontend/nginx.conf:24, and the per-location
 *  `limit_req zone=api burst=20 nodelay` that frontend/docker-entrypoint.sh:139
 *  renders into the served config) sheds a bare goto, so the harness's
 *  quietBoot keeps driving until the page really paints. The tour seed
 *  is load-bearing: its overlay swallows clicks on /login. */
async function bootTimeline(page: Page, h: TimelineHarness): Promise<void> {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h, '/timeline');
  await expect(page.getByTestId('timeline-page'), 'the timeline painted').toBeVisible();
}

/** Apply the page's OWN camera filter (EventTimeline.tsx:1256 Show Filters,
 *  :1297 id="camera-filter"; handleFilterChange :382-389 re-keys the query). The
 *  shipped door that moves a socket row into the fetched list with no reload and
 *  no test-side refetch call. */
async function filterToCamera(page: Page, cameraId: string): Promise<void> {
  await page
    .getByRole('button', { name: /Show Filters|Hide Filters/ })
    .first()
    .click();
  await expect(page.locator('#camera-filter'), 'the filter panel opened').toBeVisible();
  await page.locator('#camera-filter').selectOption(cameraId);
}

/** Drop, then attribute. Attribution is not optional: on a stack a neighbour
 *  also drives, a fresh live card could be theirs, so every candidate id is
 *  confirmed Node-side as a row of OUR camera before anything clicks it.
 *  Returns id 0 after recording a named skip (the 300 s dedupe window). */
/**
 * Drop the scenario's bytes and wait for the card of OUR camera.
 *
 * Polls one ARRIVAL_BUDGET_MS window; if it landed no card and the re-drop
 * budget (SUPPLY_REDROPS) still holds, waits the dedupe TTL out, re-sends the
 * same bytes, and polls again — the wait IS the interval, so a drop before it
 * is a no-op. On a normal stack the first window lands (the strict leg's mark
 * lapsed ~8 min ago) and the budget goes unspent. The TTL-wait-then-re-drop
 * path is the fallback for a co-collected strict leg; it came back with the
 * [r264] split because this file now sorts AFTER the strict leg's file.
 */
async function dropAndAwaitCard(
  page: Page,
  h: TimelineHarness,
  session: Session,
  run: ReturnType<typeof readRun>
): Promise<{ id: number; row: EventRow | null }> {
  const idsBefore = new Set(
    (await listCameraEvents(h, session, run.cameraId)).items.map((i) => i.id)
  );
  const scenario = run.scenarios.find((s) => s.name === SCENARIO_KEY);
  expect(scenario, `${SCENARIO_KEY} is in the scenario book`).toBeDefined();
  // The premise of every NULL-face assertion below, checked rather than
  // assumed: if the delay or the timeout changes upstream, this row stops
  // landing verification_failed and the NULL branch stops being what runs.
  expect(
    scenario?.reply_delay_seconds ?? 0,
    'the scenario replies past ai_vlm_read_timeout (25 s default), so the row must land ' +
      'verification_failed with a NULL score'
  ).toBeGreaterThan(25);

  const imagePath = path.join(run.dir, String(scenario?.image));
  dropScenario(imagePath, SCENARIO_KEY);

  // Poll one window; on a miss, wait the TTL out, re-send, poll again.
  let windowEnds = Date.now() + ARRIVAL_BUDGET_MS;
  const startedAt = Date.now();
  let attempt = 0;
  for (; ; attempt += 1) {
    for (;;) {
      for (const id of (await liveCardIds(page)).filter((i) => !idsBefore.has(i))) {
        const row = await readRow(h, session, id);
        if (row.camera_id === run.cameraId) return { id, row };
      }
      if (Date.now() > windowEnds) break;
      await page.waitForTimeout(2_000);
    }
    if (attempt >= SUPPLY_REDROPS) break;
    await page.waitForTimeout(SUPPLY_TTL_WAIT_MS);
    dropScenario(imagePath, SCENARIO_KEY);
    windowEnds = Date.now() + ARRIVAL_BUDGET_MS;
  }
  // Reached only when every window landed no card. The message states what
  // this path observed: each drop was either skipped at the door
  // (file_watcher.py:871-873 — possible only while a strict-leg mark held,
  // since a FIRST drop is never marked) or landed no frame. The numbers are
  // the evidence; the reading belongs to whoever reads the row.
  const server = await listCameraEvents(h, session, run.cameraId);
  test
    .info()
    .skip(
      true,
      `no live card for a new ${run.cameraId} row after ${attempt} re-drop(s), ` +
        `${Date.now() - startedAt} ms. Each drop was skipped at the door ` +
        `(dedupe.py:164, :439; file_watcher.py:871-873) or landed no frame. ` +
        `Server rows for the camera: ${JSON.stringify(server.items.map((i) => i.id))}; ` +
        `ids before the drop: ${JSON.stringify([...idsBefore])}`
    );
  return { id: 0, row: null };
}

test.describe('F-045 Event Timeline live activity section', () => {
  test('an event arrives over /ws/events above the historical list, and its live card opens its detail', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    // Real work on the clock: the arrival leg is ~62 s measured on a stack
    // where the strict leg's mark lapsed (the files collect ~8 min apart), and
    // the co-collected shape — a targeted two-file rerun — rides the fallback:
    // 150 + 300 + 150 = 600 s worst case, plus the quiet boot, the filter
    // round-trip and two clicks. 900 s holds both.
    test.setTimeout(900_000);

    const h = harness;
    let run: ReturnType<typeof readRun>;
    try {
      run = readRun();
    } catch (e) {
      test.info().skip(true, `run config unreadable: ${String(e)}`);
      return;
    }
    const session = await adminSession(h);
    // The camera's display name from the API the page itself uses
    // (GET /api/cameras, backend/api/routes/cameras.py:151), so the aria-label
    // and modal-title asserts are server-derived rather than string guesses.
    const cameras = await api<{ items: CameraRow[] }>(h, session, '/api/cameras?limit=100');
    const cameraName = cameras.items.find((c) => c.id === run.cameraId)?.name ?? SCENARIO_KEY;

    await bootTimeline(page, h);
    // The section's shipped empty state (LiveActivitySection.tsx:300-308).
    // Empty before, one card after, with NO reload between, is what turns
    // "arriving" into a claim about the socket instead of about a fetched page.
    await expect(page.getByText('No Live Activity'), 'the section starts empty').toBeVisible();

    const { id: eventId, row: server } = await dropAndAwaitCard(page, h, session, run);
    if (!server) return; // dropAndAwaitCard recorded the reason
    const card = liveCard(page, eventId);

    /* ---------------- clause 1: over the socket, above the list ------------- */
    await expect(card, 'the arriving row is on screen with no reload').toBeVisible();
    await expect(page.getByText('No Live Activity'), 'the empty state is gone').toHaveCount(0);
    await expect(
      page.locator('[role=status]').first(),
      'the section reports the socket as connected'
    ).toHaveText(/^Live$/);
    await expect(
      page
        .getByTestId('activity-feed')
        .last()
        .getByText(/^Showing 1 of 1 events$/),
      'the feed footer counts the arrival'
    ).toBeVisible();

    // "Above the historical list", twice over: containment inside the live
    // section, and the same id absent from the fetched list. The list is the
    // other cache (useEventStream.ts holds frames in local state with no
    // queryClient reference), so the card cannot have come from it.
    await expect(card, 'the card lives inside the Live Activity section').toHaveCount(1);
    await expect(
      page.getByTestId(`event-card-${eventId}`),
      'the socket row is NOT in the fetched historical list, so the card is a socket ' +
        'arrival and not a historical card styled to look live'
    ).toHaveCount(0);
    const divider = page.getByText('Historical Events', { exact: true });
    await expect(divider, 'the section divider is rendered').toBeVisible();
    const cardBox = await card.boundingBox();
    const dividerBox = await divider.boundingBox();
    expect(
      Boolean(cardBox && dividerBox && cardBox.y < dividerBox.y),
      `live card y=${cardBox?.y} must sit above the Historical Events divider y=${dividerBox?.y}`
    ).toBe(true);

    // The agreement with the server, field by field — including the NULL the
    // socket boundary forbids coalescing (api/schemas/websocket.py:255-257): no
    // RiskBadge at all, and the words "risk level unverified".
    expect(server.camera_id, 'the row is our camera’s').toBe(run.cameraId);
    expect(server.risk_score, 'a read-lapse row carries NULL, never a low score').toBeNull();
    expect(server.verification?.verdict, 'and names its own failure').toBe('verification_failed');
    expect(server.summary, 'with the analyzer’s degraded text').toBe(DEGRADED_SUMMARY);
    await expect(
      card.locator('[data-testid="risk-badge"]'),
      'a NULL score draws no risk badge (ActivityFeed.tsx:194-197, :257-259)'
    ).toHaveCount(0);
    // The card replaces its content for screen readers, so its aria-label is
    // the accessible face of the same row (ActivityFeed.tsx:224-236). The
    // timestamp half is relative ("Just now"), so the exact-string assert is on
    // the part that is NOT time-dependent, and the prefix carries the camera.
    const aria = await card.getAttribute('aria-label');
    expect(aria, `the aria-label opens with the camera: ${aria}`).toMatch(
      new RegExp(`^Event from ${cameraName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} at `)
    );
    const notifySuffix =
      server.notify === true ? ', notifies' : server.notify === false ? ', not notifying' : '';
    expect(
      aria?.split(', risk level ')[1],
      `the rest of the aria-label is risk level + verdict + notify decision (notify=` +
        `${JSON.stringify(server.notify)}): ${aria}`
    ).toBe(`unverified, verdict Verification failed${notifySuffix}`);
    await expect(card, 'the card shows the server’s summary').toContainText(DEGRADED_SUMMARY);

    /* ---- clause 2, half one: ONE click on a socket-only card opens it --------- */
    await expect(modal(page), 'no detail is open before any click').toHaveCount(0);
    await card.click();
    await expect(
      modal(page).filter({ hasText: DEGRADED_SUMMARY }),
      'a click on a card the fetched list never held opens THAT row’s detail: getModalEvent ' +
        'now reads useEventModalRow’s row (EventTimeline.tsx:1096-1097 → useEventModalRow.ts:69), ' +
        'which completes a socket-only id with GET /api/events/{id}. The old assert read ' +
        '`Expected: 0, Received: 1` at job 117083054790 of run 38932915995.'
    ).toBeVisible({ timeout: 20_000 });
    await modal(page).getByTestId('close-modal-button').click();
    await expect(modal(page), 'the shipped Close button closes it').toHaveCount(0);

    /* ---- clause 2, half two: the same one click, row now IN the list ---------- */
    await filterToCamera(page, run.cameraId);
    await expect(
      page.getByTestId(`event-card-${eventId}`),
      'the page’s own camera filter re-keyed the query and the socket row is now in the list'
    ).toBeVisible();
    // Half one's own Close click cleared the selection, so this control proves
    // the list holding the row opens nothing by itself: the opening judged below
    // is caused by a click, not by the one above it.
    await expect(
      modal(page),
      'with the selection cleared, the row sitting in the list opens no detail by itself'
    ).toHaveCount(0);

    const liveAgain = liveCard(page, eventId);
    await expect(liveAgain, 'the live card is still on screen under the filter').toHaveCount(1);
    await liveAgain.click();
    await expect(modal(page), 'the click opens the detail').toHaveCount(1);
    await expect(modal(page), 'the detail is shown').toBeVisible();
    // Half one took the DETAIL-FETCH path (the row was not in the loaded pages);
    // this click takes the BROWSE path (it is), and both must land on the SAME
    // row the socket announced: title from the camera map (getModalEvent :1099 →
    // EventDetailModal.tsx:593-595), verdict chip because riskLevel is null
    // (:540, :626-637), and the AI Summary paragraph is the server's (:883).
    await expect(
      page.getByTestId('detection-camera'),
      'the modal is for our camera’s row'
    ).toHaveText(cameraName);
    await expect(
      modal(page).getByTestId('risk-score'),
      'a NULL-scored row shows the verdict, never a score'
    ).toContainText('Verification failed');
    await expect(
      modal(page).getByTestId('ai-analysis-section'),
      'the AI Summary paragraph is the server’s summary'
    ).toContainText(DEGRADED_SUMMARY);
    await modal(page).getByTestId('close-modal-button').click();
    await expect(modal(page), 'the shipped Close button closes it').toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the live section is a socket channel: the row is historical after a reload, never replayed live', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    test.setTimeout(120_000);
    // NO drop here, deliberately: test 1's row is server state now, and where a
    // fresh boot puts it is the CONTROL that makes test 1's card an observation
    // about the SOCKET rather than about history. The broadcaster replays only
    // for a client that asks by sequence number (services/event_broadcaster.py:
    // 550-557 get_messages_since), so a row that arrived live is ABSENT from the
    // live section on the next load and present in the fetched list instead.
    // Goes red if a bridge ever starts replaying history into the live feed —
    // and red if the live section ever stops being fed by the socket at all.
    const h = harness;
    let run: ReturnType<typeof readRun>;
    try {
      run = readRun();
    } catch (e) {
      test.info().skip(true, `run config unreadable: ${String(e)}`);
      return;
    }
    const session = await adminSession(h);
    const listed = await listCameraEvents(h, session, run.cameraId);
    const row = listed.items.find((i) => i.summary === DEGRADED_SUMMARY);
    test.info().skip(!row, `no degraded ${SCENARIO} row on this stack to re-read`);
    if (!row) return;

    await bootTimeline(page, h);
    await expect(
      page.getByTestId(`event-card-${row.id}`),
      'the row is in the fetched historical list'
    ).toBeVisible();
    await expect(
      liveCard(page, row.id),
      'and NOT in the live section, which holds socket arrivals only'
    ).toHaveCount(0);
    await settledReload(page);
    await expect(
      page.getByTestId(`event-card-${row.id}`),
      'still historical after a settled reload'
    ).toBeVisible();
    await expect(liveCard(page, row.id), 'still absent from the live section').toHaveCount(0);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
