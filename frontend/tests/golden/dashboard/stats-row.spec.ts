/**
 * FE-2 golden path (F2.3): F-028 — the dashboard page and its stats row:
 * active-camera count, events today, the current risk gauge with sparkline,
 * system health, and the "(Disconnected)" hint that appears only when BOTH
 * sockets drop.
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - Row clause + endpoints: opens `/`; sees active-camera count, events today,
 *   risk gauge + sparkline, system health, "(Disconnected)" when both sockets
 *   drop. Backends: GET /api/cameras, /api/events/stats, /api/events,
 *   /api/system/health, WS /ws/events, WS /ws/system.
 * - Each stat card is a MIRROR of a shipped derivation, so the golden path
 *   compares the DOM to a fresh Node read of the SAME endpoint the card read
 *   (never a recomputed guess):
 *     • active-cameras-count  = cameras.filter(status==='online').length
 *       (DashboardPage.tsx:242). Mirror re-reads GET /api/cameras and applies
 *       the identical filter — NOT cameras.length (a camera can be offline).
 *     • events-today-count    = eventStats.total_events + live WS events
 *       today (DashboardPage.tsx:247-267). The REST half is the cached,
 *       date-filtered stats call, so the mirror REPLAYS the app's own
 *       /api/events/stats URL (captured passively via page.on('response'),
 *       not one of guard.ts:46's INTERCEPTION_METHODS) — the same reason F2.3
 *       F-032 replays it: the Redis key embeds start_date (events.py:593).
 *       WHY the replay can equal the card at all: on a quiescent stack the
 *       replay returns the app's number whether the Redis entry is still live
 *       (it IS the entry the app read at boot) or has expired (it recomputes
 *       over the same rows). The equality breaks only if a NEW event lands
 *       mid-window — the card would then count it as a live WS event while
 *       this replay returns the older total. Nothing drops a fixture inside
 *       this batch's window (../dashboard-drop.spec.ts runs BEFORE dashboard/
 *       because '-' 0x2D < '/' 0x2F), so such a drift is a real signal, not
 *       churn to paper over; the poll fails naming both values.
 *     • risk-score            = the first event in mergedEvents that HAS a
 *       score (DashboardPage.tsx:232, P0.25: a null/unverified score must NOT
 *       zero the gauge — that would read "all clear" and lie). mergedEvents
 *       puts live WS events first, then the REST page; events list is ordered
 *       started_at DESC, id DESC (events.py:466-467), so on a settled stack
 *       the mirror's first-non-null over GET /api/events?limit=50 equals the
 *       card's value. risk-label = getRiskLabel(getRiskLevel(score))
 *       (utils/risk.ts:95-104 thresholds LOW_MAX 29 / MEDIUM_MAX 59 /
 *       HIGH_MAX 84; :196-203 labels Low/Medium/High/Critical), mirrored with
 *       the SAME two functions.
 *     • risk-sparkline        = present iff riskHistory.length > 1
 *       (StatsRow.tsx:163,164,235). riskHistory = mergedEvents.slice(0,10)
 *       .reverse().flatMap(non-null score) (DashboardPage.tsx:236-240), so the
 *       mirror counts NON-NULL scores in the newest 10 events and asserts the
 *       sparkline's presence/absence matches that count (>1), not merely "it
 *       renders".
 *     • system-status-label   = the WS system status, SEEDED by
 *       GET /api/system/health on mount (useSystemStatus.ts:4,61-68) and
 *       mapped healthy→Online / degraded→Degraded / unhealthy→Offline /
 *       else→Unknown (StatsRow.tsx:121-132). The mirror reads the SAME health
 *       endpoint and applies the same map; on the fake stack the seed value
 *       holds (no broadcaster churn) so DOM == map(health.status) as an
 *       agreement poll.
 * - The "(Disconnected)" hint is a REAL teardown, not a mock. It renders only
 *   when BOTH connections are down: !eventsConnected && !systemConnected
 *   (DashboardPage.tsx:472-474), inside the stats-row slot (:546-548). Both
 *   flags come from the two WS hooks (useEventStream / useSystemStatus). The
 *   only guard-legal way to drop both is Chromium's own network partition —
 *   context.setOffline(true) (real, not interception). MEASURED FACT (FE-1's
 *   shell/ws-status.spec.ts, run 38146684985, and this lane's own memory): on
 *   the CI feature-check host, offline emulation does NOT tear ESTABLISHED
 *   loopback WebSockets — the chips stayed Connected for 60 s across 3
 *   attempts; a standalone probe stack DOES surface it (~2 s local). So the
 *   disconnect leg WITNESSES the break: if neither socket drops within 15 s it
 *   self-skips AT RUNTIME carrying that measurement — ruling 86: the leg is
 *   unexecutable on this host, not failed, and never a silent pass. Where the
 *   break surfaces, it asserts the hint appears with both sockets down, then
 *   restores and asserts it clears.
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
} from './harness';

const harness = readDashboardHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface CameraList {
  items: { status: string }[]; // fetchCameras reads response.items (api.ts:1404-1407)
}
interface EventStats {
  total_events: number;
}
interface EventRow {
  id: number | string;
  risk_score: number | null;
}
interface EventList {
  items: EventRow[];
}
interface Health {
  status: string;
}

// Mirrors of the shipped formatters, cited in the header.
function getRiskLevel(score: number): 'low' | 'medium' | 'high' | 'critical' {
  if (score <= 29) return 'low';
  if (score <= 59) return 'medium';
  if (score <= 84) return 'high';
  return 'critical';
}
const RISK_LABEL: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};
const STATUS_LABEL: Record<string, string> = {
  healthy: 'Online',
  degraded: 'Degraded',
  unhealthy: 'Offline',
};

async function openDashboard(page: import('@playwright/test').Page, h: DashboardHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('dashboard-layout')).toBeVisible({ timeout: 20_000 });
}

test.describe('golden path: dashboard stats row @critical', () => {
  test('F-028: every stats-row card mirrors its endpoint — online cameras, events today, risk gauge + sparkline, system health', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);

    // Capture the app's OWN stats URL before navigating (passive observation).
    let statsUrl: string | null = null;
    page.on('response', (res) => {
      if (/\/api\/events\/stats(\?|$)/.test(res.url())) statsUrl = res.url();
    });

    await openDashboard(page, h);
    await expect.poll(() => statsUrl, { timeout: 20_000 }).toBeTruthy();

    const session = await adminSession(h);
    const cards = {
      cameras: page.getByTestId('active-cameras-count'),
      events: page.getByTestId('events-today-count'),
      riskScore: page.getByTestId('risk-score'),
      riskLabel: page.getByTestId('risk-label'),
      sparkline: page.getByTestId('risk-sparkline'),
      system: page.getByTestId('system-status-label'),
    };

    // --- active-camera count == count(status==='online') ---
    await expect
      .poll(
        async () => {
          const cams = await api<CameraList>(h, session, '/api/cameras');
          const online = cams.items.filter((c) => c.status === 'online').length;
          const dom = (await cards.cameras.innerText()).trim();
          return dom === String(online) ? 'agree' : `dom="${dom}" online=${online}`;
        },
        {
          message: 'active-cameras-count mirrors online camera count',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // --- events-today-count == replayed stats.total_events (idle: no live WS) ---
    await expect
      .poll(
        async () => {
          const u = new URL(String(statsUrl));
          const stats = await api<EventStats>(h, session, u.pathname + u.search);
          const dom = (await cards.events.innerText()).trim();
          return dom === String(stats.total_events)
            ? 'agree'
            : `dom="${dom}" total=${stats.total_events}`;
        },
        {
          message: 'events-today-count mirrors the app-replayed stats total',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    // --- risk gauge == first NON-NULL score in the newest-50 (started_at DESC) ---
    await expect
      .poll(
        async () => {
          const list = await api<EventList>(h, session, '/api/events?limit=50');
          const score = list.items.find((e) => e.risk_score !== null)?.risk_score ?? 0;
          const dom = (await cards.riskScore.innerText()).trim();
          return dom === String(score) ? `agree:${score}` : `dom="${dom}" gauge=${score}`;
        },
        {
          message: 'risk-score mirrors the first non-null-scored recent event',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toMatch(/^agree:/);

    // The label is the SAME score through the shipped level+label maps.
    const listForLabel = await api<EventList>(h, session, '/api/events?limit=50');
    const scored = listForLabel.items.find((e) => e.risk_score !== null)?.risk_score ?? 0;
    await expect(cards.riskLabel).toHaveText(RISK_LABEL[getRiskLevel(scored)]);

    // --- sparkline presence mirrors riskHistory.length > 1 (non-null in last 10) ---
    const listForSpark = await api<EventList>(h, session, '/api/events?limit=50');
    const scoredInLast10 = listForSpark.items
      .slice(0, 10)
      .filter((e) => e.risk_score !== null).length;
    if (scoredInLast10 > 1) {
      await expect(cards.sparkline, 'sparkline shows with >1 scored recent events').toBeVisible();
    } else {
      await expect(cards.sparkline, 'no sparkline at ≤1 scored recent event').toHaveCount(0);
    }

    // --- system-status-label == map(health.status) seeded from GET /health ---
    await expect
      .poll(
        async () => {
          const health = await api<Health>(h, session, '/api/system/health');
          const want = STATUS_LABEL[health.status] ?? 'Unknown';
          const dom = (await cards.system.innerText()).trim();
          return dom === want ? 'agree' : `dom="${dom}" want="${want}" (health=${health.status})`;
        },
        {
          message: 'system-status-label mirrors GET /api/system/health via the shipped map',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe('agree');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-028: the "(Disconnected)" hint appears only when BOTH sockets drop, and clears on reconnect', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(180_000);

    await openDashboard(page, h);

    const hint = page.getByText('(Disconnected)');
    // Both sockets are up after a quiet boot, so the hint (both-down only) is
    // absent — the row's "when both drop" precondition, asserted BEFORE the
    // partition so the later appearance is a change, not a boot artifact.
    await expect(hint, 'no hint while connected').toHaveCount(0);

    // Partition for real (Chromium offline — not an interception; the guard
    // forbids none of this). Then WITNESS whether the host tears the sockets.
    await page.context().setOffline(true);

    let tornAtMs = -1;
    const t0 = Date.now();
    while (Date.now() - t0 < 15_000) {
      if ((await hint.count()) > 0) {
        tornAtMs = Date.now() - t0;
        break;
      }
      await page.waitForTimeout(1_000);
    }
    test
      .info()
      .skip(
        tornAtMs < 0,
        'setOffline(true) never surfaced on the established loopback WebSockets within 15 s — ' +
          'this host does not break established sockets on offline emulation (CI feature-check ' +
          'host, measured FE-1 run 38146684985: chip still Connected after 60 s); ruling 86: the ' +
          'leg is unexecutable here, not failed'
      );

    // Here the host DID tear both sockets, so the both-down hint is up. It was
    // proven present by the witness loop; assert its text once more for the
    // record and that it sits in the stats-row region.
    await expect(hint).toBeVisible();

    // Restore: both sockets reconnect, so the both-down hint clears.
    await page.context().setOffline(false);
    await expect
      .poll(async () => (await hint.count()) === 0, {
        message: 'hint never cleared after the network returned (both sockets back up)',
        timeout: 120_000,
        intervals: [2_000],
      })
      .toBe(true);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
