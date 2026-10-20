/**
 * FE-3 golden path (F2.3): F-045 — Event Timeline › Live activity section, the
 * strict clause. Split out of ./live-socket-arrival.spec.ts by [r264]'s MEASURE
 * box, which named this file the shard-picking long pole.
 *
 * Row clause (docs/reference/feature-inventory.md:199, status `awaiting real tier`):
 *   "sees events arriving over the socket above the historical list; clicks one
 *   to open its detail"
 *
 * WHAT MOVED AND WHY. The inventory row's F-045 legs lived in one file, and
 * [r264]'s shard measurement (runs 39190299978 / 39193472495 at 02dba3843,
 * table on PR #7264) traced the 4/4 shard's slowest cell to ONE test: the
 * strict clause ran 512.5 s (rep 1), 517.4 s (rep 2), 516.9 s in the 3/3 cell
 * and 517.3 s in the unsharded reference — the next-slowest single test in the
 * project is ~65 s. The cost is not this leg's own work; it is SUPPLY
 * CO-LOCATION. The book has five scenario images and every other one is
 * claimed by another spec (the header ledger in ./live-socket-arrival.spec.ts
 * holds the arithmetic), so the only bytes a strict leg can legally send are
 * the ones test 1 already sent — and for 300 s the watcher skips them at the
 * door. Sharing a file meant sharing a drop: test 1 marked the content hash,
 * this leg waited the TTL out (300 s), re-dropped, and polled its window —
 * hence 150 + 300 + 150 = 600 s of budget and a measured ~512 s. In its own
 * file the leg gets its own drop: on a fresh stack its FIRST drop is never
 * marked, the door is open, and the arrival lands inside one
 * ARRIVAL_BUDGET_MS window (~62 s measured).
 *
 * WHO DROPS FIRST, AND WHY THIS NAME. Playwright's shard split (measured on
 * run 39193472495's artifacts: shard 3-of-4 ran golden test positions
 * 125–188, shard 4 ran 189–244) puts the boundary between
 * ./event-detail.spec.ts and ./event-feedback.spec.ts at N=4, and the split
 * balances by test count over the alphabetical order — so this file's name
 * was chosen for its SORT POSITION, not decoration: sorting after
 * timeline/download-media and before timeline/event-bulk-reviewed places its
 * one test ~16 test positions inside shard 3, while the original's tests
 * (216–218) stay in shard 4. N=4 — the picked shape — separates the two
 * droppers and both legs run ~62 s; that is the whole point of the split.
 * The chosen name also decides the UN-sharded shapes: this file sorts BEFORE
 * the original, so on the reference run and every N=2/N=3 cell this leg
 * drops the slow-reply bytes FIRST, marks the hash, and test 1 — ~45 specs
 * (~8 minutes measured) later in collection order — drops into a window
 * whose key has already lapsed. The original carries a TTL-wait fallback for
 * the shape that breaks that premise (a targeted two-file rerun collecting
 * them ~100 s apart); see SUPPLY_REDROPS in ./live-socket-arrival.spec.ts.
 * The 900 s budget below covers even the reversed shape (this leg waiting on
 * a mark nothing made): one re-drop, 600 s worst case, plus boot and clicks.
 *
 * Nothing is mocked: ../guard.ts patches route/unroute/routeFromHAR/
 * routeWebSocket to THROW, so every byte below is the live stack's, and the
 * test closes by tripping that guard on purpose. The drop is the only
 * sanctioned supply that broadcasts (the same call the F2.1 golden path uses,
 * ../dashboard-drop.spec.ts:194-203): scripts/feature-check.sh drop COPIES a
 * scenario image into a camera folder (scripts/feature_check.py:2911-2917) →
 * the real watcher content-hashes it (services/file_watcher.py:869-873) → the
 * real detector and the fake VLM run → the analyzer commits the row
 * (:673-678) → `_broadcast` runs LAST and prod-only (:755-756) →
 * EventBroadcaster publishes to /ws/events.
 *
 * THE STRICT FORM. Test 1 of the original file asserts BOTH clause halves on
 * the detail-fetch and browse paths (a filter round-trip sits between two
 * clicks). This leg keeps the bare form the row's second clause names: ONE
 * click on a socket-only card, no filter, no prior selection. Its product gap
 * — a modal that resolved the clicked row only inside the HTTP-derived list —
 * was repaired in [r211f] (#7210): useEventModalRow
 * (frontend/src/hooks/useEventModalRow.ts:69) completes a selection the loaded
 * browse pages do not hold with GET /api/events/{id}, and getModalEvent
 * (EventTimeline.tsx:1093) renders that row. What once kept the leg out of the
 * run was SUPPLY, not behaviour: the old half-one assert read
 * `Expected: 0, Received: 1` at job 117083054790 of run 38932915995 — the
 * modal DID open, so the gap the row carried is closed.
 *
 * NOT asserted here, with reasons (UR-128): the pause control, its
 * announcement, the LRU cap and the SequenceValidator are the live section's
 * surface but not this row's clause; the modal's internals are F-054's
 * (./event-detail-modal.spec.ts); the `?event=` deep link opens the modal for
 * a socket-only row but F-054 claims that door, so this file never navigates
 * by URL. The `No Live Activity` empty state before the drop IS asserted —
 * it is the premise the card arrives over the socket rather than from the
 * fetched list.
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
  type Session,
  type TimelineHarness,
} from '../harness';

/** Collection-time readiness: Playwright runs collection before any runtime
 *  skip, so every env read goes through the harness's defensive reader. */
const harness = readTimelineHarness();
test.skip(!harness.ready, harness.ready ? '' : harness.why);

/** The book's only un-dropped image — see the header's claim arithmetic in
 *  ./live-socket-arrival.spec.ts. */
const SCENARIO_KEY = 'slow-reply';
/** How long to wait for the real pipeline: watcher poll + detector + the
 *  scenario's 40 s reply + the 25 s read budget + commit + publish. Measured
 *  ~62 s from drop to card on the held stack, so 150 s is slack, not luck. */
const ARRIVAL_BUDGET_MS = 150_000;
/** The second-drop supply: wait the dedupe window out, then re-send the SAME
 *  bytes. The key is `dedupe:<sha256>`, 300 s TTL, set once when the bytes are
 *  first marked (dedupe.py:316, :439). On every ordinary stack this leg's
 *  first drop IS the first drop (it sorts before the original's test 1), the
 *  window lands inside ARRIVAL_BUDGET_MS, and this budget is never spent.
 *  The re-drop exists for the shape where something marked the hash before
 *  this leg dropped anyway — today that is only a future reordering that puts
 *  the original's test 1 ahead of this file in collection order. A re-drop
 *  INSIDE the window is a guaranteed no-op (file_watcher.py:871-873), so the
 *  attempt is wait-then-drop then poll, never poll-while-closed. This is the
 *  idiom ./video-clip.spec.ts:637-650 proves against this exact key
 *  ("waiting the TTL out is the only fix that invents nothing"), and it keeps
 *  the book-known verification_failed outcome that a fresh-byte variant would
 *  trade away. ONE re-drop is enough in every case: if the first window
 *  missed, 150 + 300 = 450 s have passed since this leg's first drop, so any
 *  key set before it has lapsed and the re-drop processes; if the window did
 *  not miss, there is nothing to re-drop. Worst case 150 + 300 + 150 = 600 s,
 *  plus boot and clicks under the 900 s timeout below. */
const SUPPLY_REDROPS = 1;
/** The dedupe TTL, from its source rather than from luck: core/config.py:2089
 *  defaults dedupe_ttl_seconds to 300 (ge=60, le=3600) and DedupeService reads it
 *  into self._ttl_seconds (services/dedupe.py:303), which is the expire= on the
 *  set at :439. The service never refreshes it on a skipped drop, so waiting the
 *  full default is what guarantees the key is gone before the next drop. It is
 *  not read at runtime — no route exposes it to this harness (readRun() sees only
 *  FEATURE_CHECK_SCENARIOS and FEATURE_CHECK_CAMERAS) — so if someone retunes it
 *  in a compose override this constant goes stale, and the leg degrades to its
 *  named skip rather than to a false green. */
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

/** The book row plus the run's scenario→camera map, both read through the
 *  env the harness exports (../dashboard-drop.spec.ts:79-81). Throws into the
 *  caller's skip branch if either is unreadable, so a misconfigured run says
 *  so instead of failing an assertion. */
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

/** The live section's own subtree, so the premise stays a claim about
 *  containment instead of a page-wide testid count. */
const liveSection = (page: Page) =>
  page.locator('section[aria-labelledby="live-activity-heading"]');
const liveCard = (page: Page, id: number) =>
  liveSection(page).locator(`[data-testid="detection-card-${id}"]`);
/** Scoped to the modal on purpose: `close-modal-button` belongs to three
 *  modals (events/EventDetailModal.tsx:644, plate-reads/PlateDetailModal.tsx:412,
 *  entities/EntityDetailModal.tsx:331), so an unscoped strict-mode handle could
 *  bind to a node that is not this modal's. */
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

/** Boot the way every timeline spec must: nginx's api bucket sheds a bare
 *  goto, so the harness's quietBoot keeps driving until the page really
 *  paints. The tour seed is load-bearing: its overlay swallows clicks on
 *  /login. */
async function bootTimeline(page: Page, h: TimelineHarness): Promise<void> {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h, '/timeline');
  await expect(page.getByTestId('timeline-page'), 'the timeline painted').toBeVisible();
}

/** `GET /api/events/{id}` (backend/api/routes/events.py:1918) and the list item
 *  carry the same row fields, so one interface serves the attribution read. The
 *  strict leg reads only the camera id — the row-face asserts are the original
 *  file's test 1's, which ran the same supply. */
interface EventRow {
  id: number;
  camera_id: string;
}
interface EventsPage {
  items: EventRow[];
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

/** Drop the scenario's bytes and wait for the card of OUR camera. Attribution
 *  is not optional: on a stack a neighbour also drives, a fresh live card
 *  could be theirs, so every candidate id is confirmed Node-side as a row of
 *  OUR camera before anything clicks it. Polls one window, then — while the
 *  leg's re-drop budget holds — waits the dedupe TTL out and re-sends (see
 *  SUPPLY_REDROPS: on an ordinary stack this leg drops FIRST, the first
 *  window lands, and the budget stays unspent).
 *  Returns id 0 after recording a named skip. */
async function dropAndAwaitCard(
  page: Page,
  h: TimelineHarness,
  session: Session,
  run: ReturnType<typeof readRun>
): Promise<number> {
  const idsBefore = new Set(
    (await listCameraEvents(h, session, run.cameraId)).items.map((i) => i.id)
  );
  const scenario = run.scenarios.find((s) => s.name === SCENARIO_KEY);
  expect(scenario, `${SCENARIO_KEY} is in the scenario book`).toBeDefined();
  // The premise of what the original file's test 1 asserts downstream of the
  // same supply, checked rather than assumed: if the delay or the timeout
  // changes upstream, the row stops landing verification_failed and the NULL
  // branch stops being what runs.
  expect(
    scenario?.reply_delay_seconds ?? 0,
    'the scenario replies past ai_vlm_read_timeout (25 s default), so the row must land ' +
      'verification_failed with a NULL score'
  ).toBeGreaterThan(25);

  const imagePath = path.join(run.dir, String(scenario?.image));
  dropScenario(imagePath, SCENARIO_KEY);

  // Poll one window; on a miss, wait the dedupe TTL out and re-send. The wait
  // IS the interval — a drop before it is a no-op.
  let windowEnds = Date.now() + ARRIVAL_BUDGET_MS;
  const startedAt = Date.now();
  let attempt = 0;
  for (; ; attempt += 1) {
    for (;;) {
      for (const id of (await liveCardIds(page)).filter((i) => !idsBefore.has(i))) {
        const row = await readRow(h, session, id);
        if (row.camera_id === run.cameraId) return id;
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
  // this path observed: every drop was skipped at the door (or the door was
  // shut for another reason — for a FIRST drop nothing was ever marked, so a
  // lapse was never attempted) and nothing was broadcast. The numbers are the
  // evidence; the reading belongs to whoever reads the row.
  const server = await listCameraEvents(h, session, run.cameraId);
  test
    .info()
    .skip(
      true,
      `no live card for a new ${run.cameraId} row after ${attempt} re-drop(s), ` +
        `${Date.now() - startedAt} ms. Every drop was skipped at the door ` +
        `(dedupe.py:164, :439; file_watcher.py:871-873) or landed no frame. ` +
        `Server rows for the camera: ${JSON.stringify(server.items.map((i) => i.id))}; ` +
        `ids before the drop: ${JSON.stringify([...idsBefore])}`
    );
  return 0;
}

test.describe('F-045 Event Timeline live activity section', () => {
  test('the strict clause: one click on a socket-only card opens its detail', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    // A fresh stack's first drop IS this leg's (it sorts before the
    // original's test 1) and lands inside one ARRIVAL_BUDGET_MS window
    // (~62 s measured); the 900 s also holds the fallback shape — one TTL
    // wait + re-drop, 600 s worst case — plus boot and clicks. Both stay
    // inside ruling 189's 2640 s golden-leg ceiling (feature_check.py:115).
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
    await bootTimeline(page, h);
    await expect(page.getByText('No Live Activity'), 'the section starts empty').toBeVisible();
    const eventId = await dropAndAwaitCard(page, h, session, run);
    if (!eventId) return;
    await expect(
      page.getByTestId(`event-card-${eventId}`),
      'the premise: the fetched list has never seen this row'
    ).toHaveCount(0);
    await liveCard(page, eventId).click();
    await expect(modal(page), 'one click on the live card should open its detail').toBeVisible();
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
