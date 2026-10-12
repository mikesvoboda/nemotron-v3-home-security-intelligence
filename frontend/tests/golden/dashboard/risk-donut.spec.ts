/**
 * FE-2 golden path (F2.3): F-032 — the risk-distribution donut: today's
 * events split by risk level, and the slice/legend click into the timeline.
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - The row's clause: "sees today's events split by risk level; clicks a slice
 *   to open /timeline?risk_level=…". Backend: GET /api/events/stats ONLY.
 * - The donut (RiskDistributionChart.tsx) is PRESENTATION-ONLY: the parent
 *   (DashboardPage.tsx:175) fetches stats and passes the four counts
 *   (:569-577); the card's center reads totalEvents = critical+high+medium+low
 *   (:112-115) — NOT the endpoint's total_events field, which counts rows in
 *   the DB whose risk fields are NULL and so has no slice; the spec asserts the
 *   SUM against the API's four numbers and says so, rather than asserting a
 *   field the component never reads.
 * - transformDistributionToChartData (:96-107) DROPS zero-count levels: a
 *   level at 0 has no legend button (legend renders the same >0 filter, :282).
 *   A mirror test must assert absence for zeros, not just counts.
 * - The slice/legend click calls onRiskLevelSelect: handleValueChange
 *   (:162-185) for donut wedges, handleLegendClick (:188-203) for legend
 *   buttons — the same contract. DashboardPage's handler NAVIGATES:
 *   /timeline?risk_level=<level> (:340-349). EventTimeline consumes the param
 *   (:307-316) and reflects it in the filters panel's
 *   <select id="risk-filter"> (:1287; panel behind the "Show Filters" button,
 *   label swap :1223, gate :1253, collapsed by default) — that select is how
 *   a click's navigation is proven CONSUMED, not just fired.
 * - The stats call is date-filtered and cache-aside: fetchEventStats({start_date})
 *   (api.ts:2314-2328) with start = new Date(<YYYY-MM-DD>T00:00:00).toISOString()
 *   from the default '7d' range (DashboardPage.tsx:167-175,
 *   useDateRangeState.ts:48). The cache key includes that string
 *   (events.py:593), so the Node-side ground truth REPLAYS THE EXACT URL the
 *   browser sent — captured passively via page.on('response'), which is NOT
 *   one of the guard's INTERCEPTION_METHODS (guard.ts:46) — instead of
 *   recomputing the date here (a Node/browser midnight-ISO divergence would
 *   compare two DIFFERENT queries).
 * - Event creation happens only through the VLM pipeline (ruling 90), so an
 *   empty donut is a REAL stack state, and an empty card has literally no
 *   slice to click. Ordering fact this spec leans on: Playwright sorts by path
 *   and '-' (0x2D) < '/' (0x2F), so ../dashboard-drop.spec.ts (F2.1 — drops a
 *   fixture and asserts its event landed) runs BEFORE this file on the same
 *   stack, which normally makes stats nonzero at this boot; the click leg's
 *   zero-event skip is then the honest data-driven fallback (it names its
 *   reason), not a CI-permanent hiding. If the F2.1 drop ever goes red, this
 *   leg's skip is the visible signal, and the mirror test still passes
 *   honestly in its empty branch.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  api,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readDashboardHarness,
  seedTourDismissed,
  adminSession,
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface EventStats {
  total_events: number;
  events_by_risk_level: { critical: number; high: number; medium: number; low: number };
}

test.describe('golden path: dashboard risk distribution donut @critical', () => {
  test('F-032: the donut mirrors /api/events/stats exactly — legend per nonzero level, center = the four-count sum', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    // Capture the stats responses the APP itself fetches (passive observation;
    // no interception — the guard blocks route/routeFromHAR/routeWebSocket and
    // this uses none of them). Listen before navigating so the boot request is
    // in scope; last-write-wins is safe because the boot's params are fixed.
    let statsUrl: string | null = null;
    page.on('response', (res) => {
      if (/\/api\/events\/stats(\?|$)/.test(res.url())) statsUrl = res.url();
    });

    await seedTourDismissed(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h);
    await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });

    // The app's own stats call happened (its URL, not one we guessed).
    await expect.poll(() => statsUrl, { timeout: 20_000 }).toBeTruthy();

    // Ground truth: replay the app's EXACT URL from Node with a real session.
    const session = await adminSession(h);
    const appPath = new URL(String(statsUrl)).pathname + new URL(String(statsUrl)).search;
    const stats = await api<EventStats>(h, session, appPath);
    const { critical, high, medium, low } = stats.events_by_risk_level;

    // The donut is rendered (empty or not — both are the shipped component).
    const chart = page.getByTestId('risk-distribution-chart');
    const empty = page.getByTestId('risk-distribution-empty');
    const nonzero = critical + high + medium + low > 0;
    if (nonzero) {
      await expect(chart).toBeVisible();
      await expect(empty).toHaveCount(0);
      // Center total = the component's OWN arithmetic over the same four
      // numbers (RiskDistributionChart.tsx:112-115), not total_events.
      await expect(page.getByTestId('total-events')).toHaveText(
        String(critical + high + medium + low)
      );
      // Legend mirrors each level; zero levels have NO button (:282 filter).
      for (const [level, count] of [
        ['critical', critical],
        ['high', high],
        ['medium', medium],
        ['low', low],
      ] as const) {
        const legend = page.getByTestId(`legend-${level}`);
        if (count > 0) {
          await expect(legend, `legend-${level} mirrors ${count}`).toBeVisible();
          await expect(legend).toContainText(String(count));
        } else {
          await expect(legend, `legend-${level} absent at 0`).toHaveCount(0);
        }
      }
    } else {
      // The empty card is ALSO a mirror: stats says zero events, the card says
      // "No events recorded" (RiskDistributionChart.tsx:219-236).
      await expect(empty).toBeVisible();
      await expect(empty).toContainText('No events recorded');
      await expect(chart).toHaveCount(0);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-032: a nonzero slice click opens /timeline?risk_level=… and the timeline consumes it', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    const session = await adminSession(h);
    // The stats shape as the dashboard will ask for it: replay the app's URL
    // after a boot so the params cannot diverge (same trick as test 1).
    let statsUrl: string | null = null;
    page.on('response', (res) => {
      if (/\/api\/events\/stats(\?|$)/.test(res.url())) statsUrl = res.url();
    });
    await seedTourDismissed(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h);
    await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
    await expect.poll(() => statsUrl, { timeout: 20_000 }).toBeTruthy();
    const u = new URL(String(statsUrl));
    const stats = await api<EventStats>(h, session, u.pathname + u.search);

    // DATA-DRIVEN skip (not a behaviour skip): with the stack holding no
    // events the donut renders its empty card and there is literally no slice
    // to click — the row's clause is unexecutable, and pretending otherwise
    // would assert against a mock, which the guard exists to forbid. The
    // mirror test above still runs (honestly, in its empty branch) on such a
    // stack. On CI this normally doesn't fire: ../dashboard-drop.spec.ts sorts
    // first ('-' < '/') and its drop usually lands an event by now.
    const levels = (['critical', 'high', 'medium', 'low'] as const).filter(
      (l) => stats.events_by_risk_level[l] > 0
    );
    test.skip(
      levels.length === 0,
      'stack has zero events: the donut is empty and has no slice to click (drop seeding will give this leg its data)'
    );

    // Click the highest-severity nonzero level's legend button (a DOM slice
    // proxy: the Tremor donut wedges are not test-id-addressable, the legend
    // buttons route through the SAME onRiskLevelSelect handler —
    // handleValueChange :168-186 vs handleLegendClick :188-199, and the row's
    // clause is the NAVIGATION, which both drive identically).
    const level = levels[0];
    await page.getByTestId(`legend-${level}`).click();
    await expect(page).toHaveURL(new RegExp(`/timeline\\?risk_level=${level}`));

    // The timeline CONSUMES the param (EventTimeline.tsx:307-325). Measured at
    // run 38166150838's failure artifact: the app EXPANDS the panel itself when
    // it arrives with URL params — setShowFilters(true) at :324, and the panel
    // starts collapsed (useState(false) at :102). So the deep-link path lands
    // with the toggle already reading "Hide Filters" [expanded] (its aria-label
    // composes that way at :1218-1223), and the panel body is open without any
    // click. My first version waited for "Show Filters" and clicked it — that
    // button never exists on this path, so the click timed out while the
    // behaviour it was meant to reveal had already happened. Assert the
    // auto-expanded state directly; the select's value is the consumption.
    await expect(page.getByRole('button', { name: /Hide Filters/i })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.locator('#risk-filter')).toHaveValue(level);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
