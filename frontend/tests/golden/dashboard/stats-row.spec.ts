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
 *   (DashboardPage.tsx:485-488), mounted inside the stats-row slot
 *   (renderStatsRow, :563-565). The flags come from the two WS hooks —
 *   useEventStream.ts:227 opens /ws/events and useSystemStatus.ts:126 opens
 *   /ws/system, both via useWebSocket with its shipped defaults (reconnect
 *   true, 15 attempts — useWebSocket.ts:66-70 — and the webSocketManager
 *   schedule, calculateBackoffDelay :210-219: min(1000·2^n, 30 s) × (1+≤25%
 *   jitter)). The only guard-legal way to drop both is Chromium's own network
 *   partition, context.setOffline(true) (real, not interception — the guard
 *   patches route/unroute/routeFromHAR/routeWebSocket, guard.ts:46, and
 *   touches no network emulation).
 *   WHY THIS LEG RELOADS OFFLINE INSTEAD OF PARTITIONING A LIVE PAGE
 *   (ruling 86 applied — the old leg's host dependency is engineered away,
 *   not skipped around): MEASURED FACT from FE-1's shell/ws-status probe
 *   (CI run 38146684985, reproduced there in one run) is that offline
 *   emulation does NOT tear ESTABLISHED loopback WebSockets — an established
 *   socket sat at readyState 1 through the whole offline window while the CI
 *   chips stayed Connected for 60 s across 3 attempts. The old leg waited on
 *   exactly those established sockets, so it could only WITNESS and
 *   runtime-skip on CI (that skip is what held this row at unverified). What
 *   offline emulation DOES kill, deterministically on every host, is FRESH
 *   handshakes: the ws-status probe measured three fresh attempts each
 *   failing at onerror/readyState 3 in ~1 ms with ZERO upgrade requests
 *   reaching the server, while the first post-restore handshake opened in
 *   3 ms. So this leg boots connected ONLINE, warms the boot's answers into
 *   the shipped service worker's api-cache (NetworkFirst on /api/,
 *   vite.config.ts:101-105), then setOffline(true) + a same-URL boot — every
 *   /ws handshake after that boot is NEW and already failed, so the hint is
 *   a schedule question, not a host question, and the leg ASSERTS outright.
 *   The warm set is everything the boot issued (captured passively via
 *   page.on('request') — observation, not interception), not a hand-picked
 *   trio, because on this page THREE cache misses each replace the layout
 *   with a coat: a shed GET /api/auth/setup-status fail-closes to /setup
 *   (ProtectedRoute.tsx:80-82, AuthContext.tsx:137 retry:false), a missing
 *   /api/auth/me lands on /login (AuthContext.tsx:162), and a failing
 *   loadInitialData — Promise.all([fetchCameras, fetchEventStats]) — or
 *   events query error renders "Error Loading Dashboard"
 *   (DashboardPage.tsx:173/:182, :194-196, :447). The stats key embeds
 *   start_date (same reason F-032's mirror replays the app's own URL), so
 *   the capture IS the key list. The offline boot is then asserted to be
 *   REAL and cache-served with offline-cache.spec.ts's instrument (this
 *   dir's own copy): document + every shell asset fromServiceWorker() &&
 *   200 — nothing intercepted, the server really gone.
 *   RECOVERY IS BOUNDED BY THE SHIPPED SCHEDULE, not by patience: while
 *   partitioned this leg holds the offline boot under ~30 s of polls, so the
 *   15-attempt budget (exhaustion 331–414 s away on this schedule) never
 *   fires, and after setOffline(false) each socket's next SCHEDULED attempt
 *   is a fresh handshake that succeeds (probe: 3 ms). Worst case is a socket
 *   sitting in a capped slot when the network returns: ≤ 30 s × 1.25 ≈ 37.5 s
 *   per socket, the two are independent state machines → ONE poll, 90 s.
 */
import type { Response } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  BOOT_QUIET_MS,
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

/** What the shipped worker reports about itself. offline-cache.spec.ts's
 *  instrument — dashboard/ copy, same shape — because the offline boot is
 *  only cache-served if the worker actually CONTROLS this page's scope. */
interface Registration {
  controller: boolean;
  scope: string | null;
  active: string | null;
  waiting: string | null;
  installing: string | null;
}
function registration(page: import('@playwright/test').Page): Promise<Registration> {
  return page.evaluate(async () => {
    const reg = await navigator.serviceWorker.getRegistration();
    return {
      controller: navigator.serviceWorker.controller !== null,
      scope: reg?.scope ?? null,
      active: reg?.active?.state ?? null,
      waiting: reg?.waiting ? reg.waiting.state : 'null',
      installing: reg?.installing ? reg.installing.state : 'null',
    };
  });
}

/** Poll until the worker really controls this page (offline-cache probe:
 *  1.5–2 s). Warm fetches must pass THROUGH the activated worker or api-cache
 *  stays empty and the offline reload boots without its answers. */
async function waitControlled(page: import('@playwright/test').Page, scope: string) {
  await expect
    .poll(() => registration(page), {
      message: 'the shipped service worker must install, activate and take control',
      timeout: 20_000,
    })
    .toEqual({ controller: true, scope, active: 'activated', waiting: 'null', installing: 'null' });
}

/** True once NetworkFirst has written every warmed key into api-cache. The
 *  keys are the FULL captured set (not ws-status's hand-picked trio) because
 *  on this page a missing stats key coats the layout too — see file header. */
function apiCacheHas(page: import('@playwright/test').Page, keys: string[]) {
  return page.evaluate(async (ks: string[]) => {
    const c = await caches.open('api-cache');
    return (await Promise.all(ks.map((k) => c.match(k).then((r) => !!r)))).every(Boolean);
  }, keys);
}

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

  test('F-028: the "(Disconnected)" hint renders when BOTH sockets are down on an offline-reloaded dashboard, and clears when they return', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // Budget from THIS leg's per-phase maxima (each a poll's own timeout or a
    // waitForTimeout in this file): openDashboard 30 s · waitControlled 20 s ·
    // paced warm passes 4 × ~10 keys × (fetch + 150 ms) ≈ 4 × 3 s = 12 s ·
    // api-cache 15 s · negative-control settle 8 s · partition-take 10 s ·
    // reload+load+chunk drain 8 s · offline paint 20 s · hint 15 s · merged
    // recovery 90 s · final drain 2 s  =  ~230 s of ceilings plus two
    // navigations. The legitimate worst path is far under it (polls return as
    // soon as true — the warm loop exits the pass its last key turns 200);
    // 300 s is headroom for a merely-slow leg, inside the Feature-check job's
    // own bound. A leg past test.setTimeout loses its named predicate message
    // (deadlineForMatcher takes the test deadline).
    test.setTimeout(300_000);

    // Capture the boot's /api requests PASSIVELY (page.on('request') is
    // observation, not interception — the guard patches only the route family,
    // guard.ts:46). These exact URLs are the keys the offline reload will
    // re-fetch; warming all of them (not ws-status's hand-picked trio) is what
    // keeps the offline boot off a coat — see file header. Registered BEFORE
    // the boot so the mount-time fetches are in the set.
    const apiGets = new Set<string>();
    page.on('request', (r) => {
      if (
        r.method() === 'GET' &&
        (r.resourceType() === 'fetch' || r.resourceType() === 'xhr') &&
        r.url().startsWith(h.ui) &&
        /\/api\//.test(r.url())
      ) {
        apiGets.add(r.url());
      }
    });

    // --- ONLINE: boot connected, witness the hint is NOT a boot artifact. ---
    await openDashboard(page, h);
    const hint = page.getByText('(Disconnected)');

    // The worker must control the scope before warm fetches reach api-cache.
    await page.waitForLoadState('load');
    await waitControlled(page, `${h.ui}/`);

    // Warm the FULL captured set THROUGH the controlling worker (NetworkFirst
    // writes api-cache only on a request it served). Each fetched with
    // credentials so it matches the app's own key.
    const keys = [...apiGets];
    expect(keys.length, 'the online boot must have issued /api fetches to warm').toBeGreaterThan(0);
    // One warm pass, paced: the shared nginx bucket is rate=10r/s burst=20
    // (harness.ts), and an un-paced loop over ~10 keys can out-run it — a shed
    // 429 is NOT cacheable (cacheableResponse statuses [0,200],
    // vite.config.ts:112), so a shed key would silently never reach api-cache.
    // A shed key is therefore re-fetched, up to a bounded number of passes; a
    // key that can never answer 200 (401/404) still goes red naming its code.
    const codes: Record<string, number> = {};
    for (let pass = 1; pass <= 4; pass++) {
      const missing = keys.filter((k) => codes[k] !== 200);
      if (!missing.length) break;
      Object.assign(
        codes,
        await page.evaluate(async (urls: string[]) => {
          const out: Record<string, number> = {};
          for (const u of urls) {
            out[u] = (await fetch(u, { credentials: 'include' })).status;
            await new Promise((res) => setTimeout(res, 150)); // ~6 r/s
          }
          return out;
        }, missing)
      );
    }
    const notOk = Object.entries(codes).filter(([, code]) => code !== 200);
    expect(
      notOk,
      'every warmed key must answer 200 online (429 = the shared bucket shed even the paced ' +
        'retry passes — stack saturation, see harness.ts; any other code = the key is not the ' +
        'boot answer this leg assumes)'
    ).toEqual([]);
    await expect
      .poll(() => apiCacheHas(page, keys), {
        message: 'NetworkFirst must have written every warmed key to api-cache',
        timeout: 15_000,
      })
      .toBe(true);

    // Negative control: on a settled connected boot the both-down hint is
    // absent. Short settle so a boot where the two sockets connect a beat after
    // dashboard-layout paints doesn't false-fail the leg before it partitions.
    await expect
      .poll(async () => (await hint.count()) === 0, {
        timeout: 8_000,
        message: 'connected dashboard still shows the both-down "(Disconnected)" hint',
      })
      .toBe(true);

    // --- PARTITION + RELOAD: force FRESH handshakes, never wait on old ones. ---
    // This is the whole cure: offline emulation cannot tear an ESTABLISHED
    // loopback socket (the old leg's host dependency, measured run 38146684985)
    // but a handshake STARTED offline fails deterministically (~1 ms probe,
    // zero upgrades reach the server). Reloading re-mounts both hooks, so both
    // sockets are fresh-failed here on EVERY host — no witness, no runtime skip.
    const responses: Response[] = [];
    page.on('response', (r) => responses.push(r));
    await page.context().setOffline(true);
    await expect
      .poll(() => page.evaluate(() => navigator.onLine), {
        message: 'partition must take',
        timeout: 10_000,
      })
      .toBe(false);
    // SAME url, so the session cookie and the warmed scope ride along.
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('load');
    await page.waitForTimeout(1_500); // boot's lazy chunks (offline-cache probe)

    // The reload is REAL and cache-served, not a dev-server artifact: document
    // + every shell asset came from the worker at 200 (offline-cache instrument,
    // this dir's copy). Nothing was intercepted; the server is really gone.
    const shell = responses.filter(
      (r) =>
        r.url().startsWith(h.ui) &&
        (/\/assets\/.*\.(js|css)$/.test(r.url()) || r.request().resourceType() === 'document')
    );
    for (const r of shell) {
      expect(r.fromServiceWorker(), `${r.url()} must come from the worker`).toBe(true);
      expect(r.status(), `${r.url()} must serve 200 from cache`).toBe(200);
    }
    expect(
      shell.some((r) => r.request().resourceType() === 'document'),
      'the offline reload must have served the DOCUMENT from cache'
    ).toBe(true);

    // The warmed set being complete is now TESTED, not assumed: a full dashboard
    // paint offline is exactly the proof no needed /api key missed (a miss would
    // coat the layout — /setup, /login, or the 429 error card; see harness.ts).
    // Named against the coats so a cache miss reads as a cache miss, not as
    // "stack saturation" (that would be a false story: there is no server here).
    await expect
      .poll(
        async () => {
          const painted = await page
            .getByTestId('dashboard-layout')
            .isVisible()
            .catch(() => false);
          if (painted) return 'booted';
          const coat = await page.evaluate(() => {
            const t = document.body.innerText;
            if (/First Time Setup/.test(t)) return 'setup';
            if (/Welcome Back/.test(t)) return 'login';
            if (/Error Loading Dashboard|HTTP 429/.test(t)) return 'err429';
            return null;
          });
          if (coat) throw new Error(`offline boot coated as "${coat}" — warmed set was incomplete`);
          return 'pending';
        },
        { timeout: 20_000, message: 'offline-reloaded dashboard never painted' }
      )
      .toBe('booted');

    // The row's clause: BOTH sockets are down on this freshly-booted offline
    // page, so the hint renders. Every /ws handshake since the reload is new
    // and already failed, so this is a commit-timing question (React mount +
    // two hook state flips), not a host question — 15 s is generous.
    await expect
      .poll(async () => (await hint.count()) > 0, {
        timeout: 15_000,
        intervals: [500],
        message: 'hint never appeared while offline-booted (both sockets failed fresh handshakes)',
      })
      .toBe(true);
    // It sits in the stats-row slot (DashboardPage.tsx:563-565) as shipped text.
    await expect(hint, 'the hint carries the row\'s "(Disconnected)" text').toBeVisible();

    // --- RECOVERY: the shipped schedule, not patience. ---
    // Restoring the network changes nothing until each socket's NEXT SCHEDULED
    // attempt fires — that attempt is a fresh handshake that now succeeds (probe:
    // 3 ms). Worst case is a socket sitting in a capped slot at the flip:
    // ≤ 30 s × 1.25 ≈ 37.5 s (calculateBackoffDelay, webSocketManager.ts:210-219).
    // The two sockets are INDEPENDENT state machines (separate Math.random
    // jitter), so both clauses ride ONE poll bounded above that bound — a
    // sequential short clock is the "found then gone" failure class this cure
    // removes. The 15-attempt budget (exhaustion 331–414 s away) never fires:
    // this leg held the offline boot under ~30 s of polls.
    await page.context().setOffline(false);
    await expect
      .poll(async () => (await hint.count()) === 0, {
        timeout: 90_000,
        intervals: [1_000],
        message:
          'after the restore: the both-down hint never cleared (both sockets did not reconnect)',
      })
      .toBe(true);

    // This leg hammered /api through the worker while partitioned; drain so the
    // next spec inherits a full nginx burst bucket (harness.ts).
    await page.waitForTimeout(BOOT_QUIET_MS);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
