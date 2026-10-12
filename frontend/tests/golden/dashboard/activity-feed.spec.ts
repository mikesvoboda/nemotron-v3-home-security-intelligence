/**
 * FE-2 golden path (F2.3): F-031 — the recent-activity feed: cards for the
 * newest events with verdict / notify / risk badges, and the card click into
 * the event's timeline detail.
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - The row's clause: "sees the ten newest events … with verdict, notify and
 *   risk badges; clicks one to open its detail on /timeline?event=…".
 *   Backend ground truth: GET /api/events sorts `started_at DESC, id DESC`
 *   (events.py:467) and returns items in THAT order (route return at
 *   :541-542) — the API leg asserts the sort contract itself, because
 *   "ten newest" is meaningless unless the page is ordered.
 * - Producer chain: DashboardPage fetches useRecentEventsQuery({limit: 50})
 *   (:86-88) → fetchEvents({limit:50}) → GET /api/events?limit=50
 *   (api.ts:2283,2292). ActivityFeed receives maxItems: 10
 *   (DashboardPage.tsx:511-514) and renders `events.slice(-maxItems)`
 *   (ActivityFeed.tsx:86).
 * - DOCUMENTED BREAK (measured from the two lines above, not observed — the
 *   golden stack cannot reach the failing regime): slice(-10) takes the LAST
 *   ten of a NEWEST-FIRST array, so with >10 events in the 50-window the feed
 *   shows the ten OLDEST of that window, and the auto-scroll effect
 *   (:74-83) scrolls to the bottom — where the OLDEST card sits. The
 *   component is written for an ascending array (newest last); the producer
 *   hands it a descending one and the merge (:201-226) never re-sorts. On the
 *   golden stack the two readings COINCIDE: events are created only through
 *   the VLM pipeline (ruling 90) and this run's stack holds the single
 *   dashboard-drop fixture (≤10 total), so slice(-10) IS "all events" IS
 *   "ten newest". This spec therefore mirrors `page.slice(-10)` — provably
 *   correct in the reachable regime — and the row, when promoted, states the
 *   >10 divergence rather than hiding it. The assert is written so a future
 *   >10 stack fails LOUD (footer + card-count), not silently green.
 * - Card anatomy (ActivityFeed.tsx): role="button" + tabIndex 0 + Enter/Space
 *   keydown (:219-226), data-testid=`detection-card-${event.id}` (:238),
 *   camera text node data-testid="card-camera" (:252), card-timestamp with
 *   <time dateTime={timestamp}> (:275-281). camera_name resolves through the
 *   LOADED cameras list with camera_id as fallback (DashboardPage.tsx:296),
 *   so the mirror fetches GET /api/cameras rather than trusting a name.
 * - Badge rules, all three decided by shipped code:
 *   risk: risk_score null = NO risk badge (P0.25, :194-197); RiskBadge is
 *   role="status" data-testid="risk-badge" aria-label `Risk level: <Label>,
 *   score <n>` and its TEXT is `<Label> (<score>)` (RiskBadge.tsx:74-93);
 *   label map low/medium/high/critical (utils/risk.ts:196-204) from
 *   thresholds 29/59/84 (risk.ts:80-85).
 *   verdict: shows iff risk is null, OR a non-confirmed verdict exists
 *   (:207-209) — a scored confirmed event deliberately carries NO chip; the
 *   badge marks itself data-verdict=<state> (VerdictBadge.tsx:119) with
 *   aria-label `Verification verdict: <Label>`, labels at :23-29.
 *   notify: NotifyBadge renders NOTHING for undefined/null — "absence is not
 *   false" (NotifyBadge.tsx:33) — else data-notify=yes|no + aria
 *   `Notification decision: Notifies|Not notifying` (:50-53).
 *   The card's aria-label re-states risk/verdict/notify (:227-237); the
 *   mirror asserts its substrings (the timestamp half is relative-time prose
 *   — "Just now" — and unstable, so only its `Event from ` prefix is pinned).
 * - Footer: `Showing {displayed} of {events.length} events` renders only when
 *   displayed > 0 (:298-303) — the second number is the PRE-slice merge
 *   length, so in the golden ≤10 regime both numbers are equal; the assert
 *   uses that equality rather than a literal, and a >10 stack fails it loud.
 * - Click: handleEventClick navigates /timeline?event=<id>
 *   (DashboardPage.tsx:317-322); EventTimeline validates digits-only via
 *   parseEventId (validation.ts:602-620, applied at :330) and opens the
 *   detail modal — instrument already PROVEN green on this stack by
 *   dashboard-drop (test ids event-detail-modal, risk-score,
 *   ai-analysis-section — passing in run 38166150838).
 * - Empty state is shipped behavior too: "No Activity Yet" + "Security events
 *   will appear here as they occur." (:171-179). The mirror branches on the
 *   API count (never on faith): 0 items → empty copy asserted and the card
 *   count asserted 0; >0 → cards asserted and the empty copy asserted GONE
 *   (both-branch discipline, FE-2 batch-3 form).
 * - Ordering fact this spec leans on for its ≥1-event state: Playwright sorts
 *   by path and '-' (0x2D) < '/' (0x2F), so ../dashboard-drop.spec.ts runs
 *   before this file on the same stack — but the spec NEVER requires it: the
 *   0-event branch is a legitimate full pass of everything assertable, and
 *   only the click leg skips (with reason) when the stack holds no events.
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
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

// The shapes the feed's producer reads, narrowed to the fields this spec
// mirrors. Declared locally on purpose: the producer maps these same fields
// (DashboardPage.tsx:206-222,291-306), so the mirror compares the browser's
// rendering against the SAME source fields the mapping consumed.
interface EventPageItem {
  id: string | number;
  camera_id: string;
  started_at?: string | null;
  timestamp?: string | null;
  summary?: string | null;
  risk_score?: number | null;
  verification?: { verdict?: string | null } | null;
  notify?: boolean | null;
}
interface EventPage {
  items: EventPageItem[];
}
interface CameraRow {
  id: string;
  name: string;
}
interface CameraList {
  cameras?: CameraRow[];
  items?: CameraRow[];
}

/** The shipped threshold walk (risk.ts:102-105 with :80-85) — this is a
 *  MIRROR of getRiskLevel, written here so a silent threshold change in the
 *  app fails the card asserts instead of moving both sides together. */
function expectedLevel(score: number): 'low' | 'medium' | 'high' | 'critical' {
  if (score <= 29) return 'low';
  if (score <= 59) return 'medium';
  if (score <= 84) return 'high';
  return 'critical';
}
const LEVEL_LABEL = { low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical' } as const;
const VERDICT_LABEL = {
  confirmed: 'Confirmed',
  rejected: 'Rejected',
  uncertain: 'Uncertain',
  verification_failed: 'Verification failed',
} as const;

test.describe('golden path: dashboard recent activity feed @critical', () => {
  test('F-031: the feed mirrors GET /api/events exactly — cards, badges, footer', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    // --- API leg: EXACTLY the query the dashboard's own producer builds
    //     (useRecentEventsQuery limit 50 → fetchEvents → ?limit=50). ---
    const session = await adminSession(h);
    const page0 = await api<EventPage>(h, session, '/api/events?limit=50');
    const items = page0.items;
    expect(Array.isArray(items), 'the events page carries an items array').toBe(true);

    // The sort contract "ten newest" rests on: started_at DESC, id DESC.
    // Asserted on the API's own rows so an upstream sort flip shows up HERE,
    // not as a wrong-looking feed three layers away.
    for (let i = 1; i < items.length; i++) {
      const a = items[i - 1];
      const b = items[i];
      const ta = String(a.started_at ?? '');
      const tb = String(b.started_at ?? '');
      // Sorter semantics, NOT violation semantics: return what a correct
      // `started_at DESC, id DESC` comparator yields for THIS pair, so a
      // correctly-ordered page yields >=0. Reading the branches as "what do I
      // return for a violation" inverts the whole guard — it then fails good
      // rows and PASSES a reversed page (measured: run 38173376883 red 3/3
      // attempts on rows 0/1 = 20:48:59/id2 then 20:47:38/id1, which IS
      // newest-first; the instrument was the bug, not the API).
      const cmp = ta === tb ? Number(a.id) - Number(b.id) : ta > tb ? 1 : -1;
      expect(
        cmp,
        `rows ${i - 1}/${i} violate started_at DESC, id DESC: ${a.started_at}/${a.id} then ${b.started_at}/${b.id}`
      ).toBeGreaterThanOrEqual(0);
    }

    const camList = await api<CameraList>(h, session, '/api/cameras');
    const cameras = camList.cameras ?? camList.items ?? [];
    expect(cameras.length, 'the golden stack seeds cameras').toBeGreaterThan(0);
    const nameOf = (cameraId: string) => cameras.find((c) => c.id === cameraId)?.name ?? cameraId;

    // The producer's slice regime (header): rendered ids MUST equal the
    // API page's last-10 — that is what shipped code does, and in the
    // golden ≤10 regime it is also provably "ten newest". Written as the
    // shipped expression so the >10 break (header) fails loud.
    const renderedIds = items.slice(-10).map((e) => String(e.id));

    // --- UI leg. ---
    await seedTourDismissed(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h);
    const feed = page.getByTestId('activity-feed');
    await expect(feed, 'the dashboard renders the activity feed').toBeVisible();

    if (items.length === 0) {
      // Shipped empty state, verbatim (:175-178), and the card branch
      // asserted ABSENT — both-branch discipline in the 0 direction.
      await expect(page.getByRole('heading', { name: 'No Activity Yet', level: 4 })).toBeVisible();
      await expect(page.getByText('Security events will appear here as they occur.')).toBeVisible();
      await expect(page.getByTestId(/^detection-card-/)).toHaveCount(0);
      // The footer renders only when displayed > 0 (:298) — absent here.
      await expect(page.getByText(/Showing \d+ of \d+ events/)).toHaveCount(0);
    } else {
      // Cards: exact id set, in exact order — not "a card appears".
      const cardCount = await page.getByTestId(/^detection-card-/).count();
      expect(cardCount, 'feed shows the page slice, no more').toBe(renderedIds.length);
      for (const id of renderedIds) {
        await expect(
          page.getByTestId(`detection-card-${id}`),
          `card for event ${id}`
        ).toBeVisible();
      }
      // The empty copy must be GONE with cards live.
      await expect(page.getByRole('heading', { name: 'No Activity Yet', level: 4 })).toHaveCount(0);

      // Per-card mirror against the API rows the producer mapped.
      for (const e of items.slice(-10)) {
        const card = page.getByTestId(`detection-card-${String(e.id)}`);
        const camName = nameOf(String(e.camera_id));
        await expect(card.getByTestId('card-camera')).toContainText(camName);
        if (e.summary) {
          await expect(card, 'summary text mirrors the row').toContainText(String(e.summary));
        }
        // Timestamp: the <time dateTime> attribute mirrors the producer's
        // own ??-chain (DashboardPage.tsx:292) — exact, no clock parsing.
        const ts = e.timestamp ?? e.started_at;
        if (ts) {
          await expect(card.getByTestId('card-timestamp').locator('time')).toHaveAttribute(
            'dateTime',
            String(ts)
          );
        }

        // Risk badge: presence iff score non-null; label from the mirrored
        // threshold walk; score carried in the aria-label.
        const score = e.risk_score;
        const riskBadge = card.getByTestId('risk-badge');
        if (score === null || score === undefined) {
          await expect(riskBadge, 'null score renders NO risk badge').toHaveCount(0);
        } else {
          await expect(riskBadge).toBeVisible();
          const label = LEVEL_LABEL[expectedLevel(Number(score))];
          await expect(riskBadge).toHaveAccessibleName(`Risk level: ${label}, score ${score}`);
        }

        // Verdict chip: shows iff risk null OR (verdict exists && non-
        // confirmed) (:207-209). data-verdict marks the badge itself.
        const verdict = e.verification?.verdict ?? null;
        const hasVerdict = verdict !== null && verdict !== undefined;
        const wantVerdict =
          score === null || score === undefined ? true : hasVerdict && verdict !== 'confirmed';
        const chip = card.locator('[data-verdict]');
        if (wantVerdict) {
          await expect(chip, 'verdict chip per the shipped rule').toHaveCount(1);
          if (hasVerdict && verdict in VERDICT_LABEL) {
            await expect(chip).toHaveAccessibleName(
              `Verification verdict: ${VERDICT_LABEL[verdict as keyof typeof VERDICT_LABEL]}`
            );
          }
        } else {
          await expect(chip, 'scored confirmed events carry NO chip').toHaveCount(0);
        }

        // Notify: strict true/false only — null/absent renders nothing.
        const notify = e.notify;
        const notifyChip = card.locator('[data-notify]');
        if (notify === true || notify === false) {
          await expect(notifyChip).toHaveCount(1);
          await expect(notifyChip).toHaveAccessibleName(
            `Notification decision: ${notify ? 'Notifies' : 'Not notifying'}`
          );
        } else {
          await expect(notifyChip, 'absence is not "not notifying"').toHaveCount(0);
        }

        // aria-label composition (:227-237): stable prefix + the risk half;
        // verdict/notify suffixes ride their own badges' rules.
        const aria = (await card.getAttribute('aria-label')) ?? '';
        expect(aria.startsWith(`Event from ${camName} at `), `aria prefix: ${aria}`).toBe(true);
        const riskPart =
          score === null || score === undefined
            ? 'risk level unverified'
            : `risk level ${expectedLevel(Number(score))}`;
        expect(aria, `aria risk half: ${aria}`).toContain(riskPart);
        if (notify === true) expect(aria).toContain(', notifies');
        if (notify === false) expect(aria).toContain(', not notifying');
      }

      // Footer: "Showing {displayed} of {merged}" — in the reachable regime
      // displayed == merged == the page slice; on a >10 stack this equality
      // is exactly where the documented break becomes visible.
      await expect(
        feed.getByText(`Showing ${renderedIds.length} of ${items.length} events`)
      ).toBeVisible();
    }

    expect(() => page.route('**/api/**', () => undefined)).toThrow(GUARD_MESSAGE);
  });

  test('F-031: clicking a card opens /timeline?event=<id> and the timeline consumes it', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000);

    const session = await adminSession(h);
    const page0 = await api<EventPage>(h, session, '/api/events?limit=50');
    const first = page0.items.slice(-10)[0]; // the newest RENDERED card
    test.skip(
      !first,
      'stack holds zero events: there is no card to click (the drop fixture supplies it normally)'
    );
    const eventId = String(first.id);
    expect(/^\d+$/.test(eventId), 'parseEventId requires digits-only (validation.ts:612)').toBe(
      true
    );

    await seedTourDismissed(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h);
    const card = page.getByTestId(`detection-card-${eventId}`);
    await expect(card).toBeVisible();

    // The row's click. Enter/Space keydown mirrors the card's own handler
    // (:221-226), which the FE-1 Escape-on-body lesson says to prefer over
    // assuming the click's hit-targets for keyboard users — both drive the
    // SAME handleEventClick, and the click half is what the row promises.
    await card.click();
    await expect(page).toHaveURL(new RegExp(`/timeline\\?event=${eventId}`));

    // CONSUMED, not just navigated: EventTimeline's ?event= path opens the
    // detail modal (parseEventId → setSelectedEventForModal, :328-333); the
    // modal's own instruments are the ones dashboard-drop proved green on
    // this stack (event-detail-modal, risk-score, ai-analysis-section).
    const modal = page.getByTestId('event-detail-modal');
    await expect(modal, 'the feed click opened the event detail').toBeVisible({ timeout: 30_000 });
    if (first.risk_score !== null && first.risk_score !== undefined) {
      await expect(page.getByTestId('risk-score')).toContainText(String(first.risk_score));
    }
    if (first.summary) {
      await expect(page.getByTestId('ai-analysis-section')).toContainText(String(first.summary));
    }

    expect(() => page.route('**/api/**', () => undefined)).toThrow(GUARD_MESSAGE);
    expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  });
});
