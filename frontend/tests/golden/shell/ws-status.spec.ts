/**
 * FE-1 golden path (F2.3): F-007 — the WebSocket connection status chip, the
 * per-channel Events/System tooltip, and the disconnect banner with its
 * reconnect counter and recovery.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - Connected leg: Header.tsx:386-393 mounts WebSocketStatus (hidden below
 *   sm:, so the desktop viewport is the row's shape). The trigger is
 *   data-testid="websocket-status" with aria-label
 *   `WebSocket connection status: ${label}` (WebSocketStatus.tsx:314-319);
 *   hovering renders role=tooltip "websocket-tooltip" (:235) with one
 *   ChannelIndicator per channel (:241-242): "channel-events"/"channel-system"
 *   rows carrying the channel name, an sr-only state label (:184), a state-
 *   colored dot (connected → bg-green-500, :26-30/:179), and
 *   "last-message-<channel>" formatted by formatTimeSince (:95-115 — 'No
 *   messages yet' | 'Just now' | 'Ns ago' | 'Nm ago' | 'Nh ago'). /ws/system
 *   pushes every 5 s (the feed F-006 already proved), so the System row's
 *   last-message must move to Just now within seconds; /ws/events may
 *   legitimately sit at 'No messages yet' until a detection broadcasts, so
 *   its clause is the family regex, not a pinned value (mirroring, never
 *   assuming).
 * - Disconnect leg ([r165a]'s cure — WHY it is a RELOAD and what replaced):
 *   context.setOffline(true) is Chromium's real network partition — the e2e
 *   lane's own instrument (tests/e2e/utils/browser-helpers.ts:310-311
 *   simulateOfflineMode). It is NOT route()/routeWebSocket(), so the guard's
 *   no-interception contract holds: nothing is mocked; every visible change
 *   comes from the app's own state machine. What it does NOT do
 *   deterministically is break ESTABLISHED loopback WebSockets, and the two
 *   ways the old wait-for-the-old-socket leg died in CI are both on the
 *   record: run 38146684985 (head 68a6856dc) — the chip still read Connected
 *   60 s after partition, 3/3 attempts (initial + 2 retries; junit + DOM
 *   snapshots); and run 38183338604 (head 81553b100) — there the break DID
 *   surface and the leg then FAILED at 195.6 s against its 180 s budget (the
 *   number is that testcase's time attribute in the run's feature-check
 *   artifact, golden-playwright.xml — failure "no coherent
 *   banner+Reconnecting+Attempt n/30 sample" at the 60 s coherence poll; the
 *   same run also failed rate-limit F-022 (shed), so this leg was not the
 *   run's only red), the banner flapping mid-suite (probe: banner mounted,
 *   unmounted on a transient 'connected', remounted; sequential locators
 *   raced it — role found, text gone). A leg whose assertions depend on
 *   sockets the host may or may not tear is a coin flip either way; owner
 *   ruling 165 made curing it a package.
 *   The cure replaces "wait for the established sockets to die" with "make
 *   the app HANDSHAKE while partitioned", because Chromium's offline
 *   emulation IS deterministic about NEW connections: measured 2026-10-14
 *   (bare RFC6455 server on 127.0.0.1 + this sandbox's installed Playwright
 *   1.63.0/Chromium — the lockfile pins ^1.64.0 and CI installs 1.64.0, so
 *   CI's word on socket behaviour is the Feature check, not this probe;
 *   probe recorded in the PR Evidence. Scope note for why the probe's
 *   browser-level finding transfers: the two WS channels THIS page's status
 *   chrome mounts come from useWebSocketStatus.ts:145's new WebSocket(url),
 *   which is where Chromium's offline emulation bites. The page also mounts
 *   webSocketManager sockets (that constructor is at webSocketManager.ts:503-504;
 *   on `/` they come via Layout.tsx:37 useServiceStatus and DashboardPage's
 *   useEventStream/useSystemStatus/useSummaries) and those fail the same
 *   offline way; what the two constructors do NOT share is the attempt
 *   counter the banner sums, so only the :145 channels drive it): three
 *   fresh handshakes while offline each failed
 *   with onerror/readyState 3 in ~1 ms and the server saw ZERO upgrade
 *   requests, while an established socket sat at readyState 1 for the whole
 *   offline window (both CI symptoms reproduced in one run), and the first
 *   handshake after setOffline(false) opened in 3 ms. So the leg now: boots
 *   connected ONLINE, waits for the shipped service worker to control the
 *   scope and warms the boot's answers into api-cache (offline-cache.spec.ts's
 *   measured doctrine, incl. its load-bearing setup-status warming —
 *   ProtectedRoute fails closed without a cached setup-status), then
 *   setOffline(true) + RELOAD. The reload re-mounts the shell — whose WS
 *   chrome mounts unconditionally (Layout.tsx:110-123 wraps the banner in a
 *   plain div; Header.tsx:387-393 mounts the chip, and hidden sm:block is CSS
 *   only — the golden viewport is Desktop Chrome) — and every channel attempt
 *   is a NEW handshake that fails at once: useWebSocketStatus.ts:176-202
 *   takes onclose → state 'reconnecting' → 1s·2^n backoff
 *   (calculateBackoffDelay, useWebSocketStatus.ts:58-67: 30 s cap, ≤25%
 *   jitter), so the banner's role=alert + "Reconnecting"
 *   (ConnectionStatusBanner.tsx:90-100/:173-204) + "Attempt n/30" + counting
 *   duration all render with NO host dependency. The denominator is 30 —
 *   re-derived at this revision: each hook defaults to 15 attempts
 *   (useWebSocketStatus.ts:80-83, the shipped "~8+ minutes" comment), exposes
 *   it as channelStatus.maxReconnectAttempts (:281), and Layout.tsx:116-119
 *   SUMS the two channels — and the numerator is the same sum of counts
 *   (useConnectionStatus.ts:379). On a fresh offline boot both counts start
 *   at 0, so the banner reads a SMALL n over /30 (an offline RELOAD boots both
 *   channels in phase — per-channel close schedule 0/1/3/7/15/31 s from
 *   min→max jitter — so the summed count reaches ~6 at ≈3–9 s, and only a
 *   full-slot offset pushes it to ~15–19 s; the old draft's /^Attempt \d+\/30$/
 *   family was right and is
 *   kept; what was never right anywhere is pinning n, which is exactly what
 *   the old leg's flapping made unsafe).
 *   The counter can only CLIMB while offline: a reset-to-zero needs onopen,
 *   and offline makes onopen impossible (zero upgrades reach the server,
 *   probe) — the flap that killed the old leg cannot occur mid-leg by
 *   construction. The reload itself is served by the precache and asserted as
 *   such with offline-cache.spec.ts's instrument (document + every shell
 *   asset fromServiceWorker() && 200): the reload is real, the server is
 *   really gone, nothing is intercepted.
 * - Banner facts asserted per coherent sample, now taken from the OFFLINE
 *   RELOADED shell: role=alert, "Reconnecting"
 *   (ConnectionStatusBanner renders null when connected, :173 — the boot-time
 *   negative control and the recovery assertion), "reconnect-counter"
 *   Attempt n/30 (15 + 15, summed — useWebSocketStatus.ts:83/:281 through
 *   Layout.tsx:116-119), "disconnected-duration" counting up (:207-211,
 *   family not pinned — the Ns/Nm/Nh forms formatDuration (:28-39) can
 *   render). One page.evaluate snapshot, never a chain of locators
 *   re-resolved against a moving target.
 * - The row's third clause — retries EXHAUST, then "REST Fallback" appears
 *   and data polls every 5 s (useConnectionStatus.ts:115
 *   FALLBACK_POLLING_INTERVAL, startPolling on onMaxRetriesExhausted) — is
 *   NOT reachable inside golden timeouts: exhausting 15 exponential attempts
 *   per channel takes 331–414 s — recomputed from calculateBackoffDelay's own
 *   arithmetic (1+2+4+8+16+30×10 s at no jitter, ×1.25 at max; the shipped
 *   comment's "~8+ minutes" overstates its own schedule) — against any
 *   sane test budget, and no runtime knob shortens it (the count is a hook
 *   default; editing hook or config is ruling 87 territory and would test a
 *   shape CI never ships). Per ruling 86 this spec does not assert that leg
 *   vacuously: the inventory row carries the deferral with this measurement,
 *   and the real tier (ruling 66) — where the operator can leave a stack down
 *   for minutes — owns it. What IS asserted here is that the fallback has NOT
 *   started during a short partition: polling-indicator /
 *   polling-fallback-indicator / the header's plain "REST Fallback" pill stay
 *   absent (isPollingFallback-gated, WebSocketStatus.tsx:339-343,
 *   ConnectionStatusBanner.tsx:222-226, Header.tsx:397-401), and so does the
 *   row's "Retry button" clause — data-testid="retry-button" renders only in
 *   the 'failed' state (ConnectionStatusBanner.tsx:179/:233-241), which the
 *   same 331–414 s exhaustion gates.
 * - Recovery leg: restoring the network changes nothing by itself — the flip
 *   happens on the hook's next SCHEDULED retry, not at the instant the
 *   network returns (the old leg's probes: a probe sitting at Attempt 5 at
 *   t+30 s detected nothing at setOffline(false); Connected arrived ~25 s
 *   later there, ~48 s in a run whose schedule had reached the 30 s cap). On
 *   the offline-RELOADED boot this is exact: every channel is mid-backoff
 *   (never established), so the first scheduled attempt after the restore is
 *   a fresh handshake that succeeds (probe: 3 ms), and the wait only has to
 *   cover the shipped schedule. Worst case is a leg that sampled late near
 *   the cap: a channel sitting in a 30 s slot when the network returns has
 *   ≤ 30 s × 1.25 jitter ≈ 37.5 s of slot left. The predicate is the
 *   SLOWER of two independent hook instances — Layout.tsx:38's pair drives
 *   the banner, Header.tsx:171's pair drives the chip, separate state
 *   machines with separate jitter — so one poll over one predicate carries
 *   90 s, comfortably above that bound (the earlier draft's "75 s" summed
 *   two channels as if they re-opened in sequence, which the code doesn't
 *   impose: each schedules its own retry). A leg that samples early recovers
 *   in seconds. (The old leg's 90 s was budget for a socket it could never
 *   see die; this one pays the shipped schedule instead.)
 *   stopPolling-on-connected (useConnectionStatus.ts:305-309) and the
 *   banner's null render close the leg — asserted INSIDE the recovery poll,
 *   never as a second sequential predicate with its own short clock.
 */
import type { Response } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** The family of strings formatTimeSince can render (WebSocketStatus.tsx:95-115). */
const TIME_SINCE = /^(No messages yet|Just now|\d+s ago|\d+m ago|\d+h ago)$/;

/** What the offline-reloaded boot must still answer. Exactly the trio
 *  offline-cache.spec.ts T3 warmed and proved — setup-status is the fail-close
 *  guard (ProtectedRoute.tsx:79), cameras the persisted query, me the recovery
 *  probe. Carried here verbatim because the reload boots the app, not just the
 *  document. */
const WARM = ['/api/auth/setup-status', '/api/cameras', '/api/auth/me'];

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

/** What the shipped worker reports about itself (offline-cache.spec.ts:144
 *  shape — same instrument, this dir's own copy). */
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

/** Poll until the SW really controls this page's scope (offline-cache probe:
 *  1.5–2 s). Warm fetches must pass THROUGH the activated SW or api-cache
 *  stays empty and the offline reload boots without its answers. */
async function waitControlled(page: import('@playwright/test').Page, scope: string) {
  await expect
    .poll(() => registration(page), {
      message: 'the shipped service worker must install, activate and take control',
      timeout: 20_000,
    })
    .toEqual({ controller: true, scope, active: 'activated', waiting: 'null', installing: 'null' });
}

/** True once NetworkFirst has written every warmed key into api-cache. */
function apiCacheHas(page: import('@playwright/test').Page, keys: string[]) {
  return page.evaluate(async (ks: string[]) => {
    const c = await caches.open('api-cache');
    return (await Promise.all(ks.map((k) => c.match(k).then((r) => !!r)))).every(Boolean);
  }, keys);
}

/** One coherent DOM sample of everything F-007 renders (see file header). */
function snapshot(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const q = (sel: string) => document.querySelector(sel);
    const banner = q('[data-testid="connection-status-banner"]');
    return {
      chip: q('[data-testid="websocket-status"]')?.getAttribute('aria-label') ?? null,
      bannerRole: banner?.getAttribute('role') ?? null,
      bannerText: banner?.textContent ?? null,
      counter: q('[data-testid="reconnect-counter"]')?.textContent ?? null,
      duration: q('[data-testid="disconnected-duration"]')?.textContent ?? null,
      polling:
        !!q('[data-testid="polling-indicator"]') ||
        !!q('[data-testid="polling-fallback-indicator"]'),
      retryButton: !!q('[data-testid="retry-button"]'),
      restPill: (document.body.innerText ?? '').includes('REST Fallback'),
      branding: !!q('[data-testid="header-branding"]'),
    };
  });
}
type Snap = Awaited<ReturnType<typeof snapshot>>;

/** The family of strings formatDuration can render, as the banner prints it
 *  (parenthesised — ConnectionStatusBanner.tsx:207-211/:28-39). */
const DURATION = /^\((\d+s|\d+m|\d+h)\)$/;

/** Wait until the app's own summary says BOTH channels are up. */
async function expectBothChannelsConnected(page: import('@playwright/test').Page) {
  await expect
    .poll(() => page.getByTestId('websocket-status').getAttribute('aria-label'), {
      timeout: 30_000,
      message: 'precondition: both WS channels never reached Connected',
    })
    .toMatch(/WebSocket connection status: Connected/);
}

test.describe('golden path: WebSocket status and disconnect banner @critical', () => {
  test('F-007: the chip reads Connected and the tooltip shows live per-channel Events/System state', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // openShell ≤ 22 s + both-channels 30 s + the negative-control poll below
    // 30 s (it covers the SECOND hook instance — see comment) + tooltip/feed
    // ~35 s ≈ 117 s of poll ceilings ⇒ 150 s wall.
    test.setTimeout(150_000);
    await openShell(page, h);
    await expectBothChannelsConnected(page);

    // Connected ⇒ the banner is NOT rendered (ConnectionStatusBanner returns
    // null for 'connected', :173) — the negative control the disconnect leg
    // later flips. Polled, not sequential: the chip reports HEADER's hook
    // instance and the banner is gated on LAYOUT's (Layout.tsx:38 vs
    // Header.tsx:171 — two useConnectionStatus() calls, two state machines),
    // so under the 3 s default a boot where Layout's pair is a few seconds
    // behind Header's would read as a false red. The poll still can only
    // succeed when the banner genuinely is un-rendered.
    await expect
      .poll(async () => (await snapshot(page)).bannerText === null, {
        timeout: 30_000,
        message: 'connected shell still renders the disconnect banner',
      })
      .toBe(true);

    // Hover opens the tooltip (WebSocketStatus.tsx:276-281, no delay on enter).
    const chip = page.getByTestId('websocket-status');
    await chip.hover();
    const tooltip = page.getByTestId('websocket-tooltip');
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toHaveAttribute('role', 'tooltip');

    // Per-channel rows, exactly the two the row claims.
    const events = page.getByTestId('channel-events');
    const system = page.getByTestId('channel-system');
    await expect(events).toContainText('Events');
    await expect(system).toContainText('System');

    // State is rendered twice per row: sr-only label and the dot's color
    // class. Both come from the live summary — mirror both.
    await expect(events).toContainText('Connected');
    await expect(system).toContainText('Connected');
    await expect(page.getByTestId('channel-dot-events')).toHaveClass(/bg-green-500/);
    await expect(page.getByTestId('channel-dot-system')).toHaveClass(/bg-green-500/);

    // The live-feed clause: /ws/system pushes every ~5 s (the SystemBroadcaster
    // loop F-006 proved against the gpu_stats row), so System's last-message
    // must move off 'No messages yet' into 'Just now'/'Ns ago' within a couple
    // of ticks. Events may still be 'No messages yet' until a detection
    // broadcasts — the family regex is the honest mirror of formatTimeSince.
    await expect(page.getByTestId('last-message-events')).toHaveText(TIME_SINCE);
    await expect
      .poll(async () => (await page.getByTestId('last-message-system').innerText()).trim(), {
        timeout: 30_000,
        message: 'System channel feed never produced a timestamped message',
      })
      .toMatch(/^(Just now|\d+s ago)$/);
    await expect(page.getByTestId('last-message-events')).toHaveText(TIME_SINCE);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-007: partitioning the network raises the banner with a live attempt counter, and the shell recovers', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // Budget from THIS leg's PER-PHASE MAXIMA (each number is a poll's own
    // timeout or a waitForTimeout in this file, not an estimate): openShell
    // 2 s drain + 20 s branding = 22 s · both-channels-up 30 s · negative
    // control 10 s · waitControlled 20 s · api-cache 15 s · onLine 10 s ·
    // chunk drain 1.5 s · coherent sample 25 s · one backoff increment 45 s
    // · merged recovery poll 90 s · final drain 2 s  =  270.5 s of poll
    // ceilings, plus two navigations (boot + reload). The LEGITIMATE worst
    // path is far under that (a passing leg spends ≈120 s: its polls return
    // as soon as they're true), so 300 s is headroom for a leg that is
    // merely slow, and the sum of ceilings stays inside the Feature check
    // job's own 60-min bound (ci.yml, feature-check).
    // The arithmetic matters because a leg that outlives test.setTimeout
    // loses its named predicate message: deadlineForMatcher takes
    // min(testDeadline − 250, matcherDeadline) and prints "Test timeout of
    // …ms exceeded" instead of the message these polls were written to carry.
    test.setTimeout(300_000);

    // --- ONLINE: boot connected, and witness the negative control first. ---
    await openShell(page, h);
    await expectBothChannelsConnected(page);
    // Bounded, not the 3 s default: the chip is HEADER's hook instance, the
    // banner is gated on LAYOUT's (two useConnectionStatus() calls), so a boot
    // where Layout lags Header by a few seconds must not false-fail the leg
    // before it even partitions. It can only pass once the banner is really
    // un-rendered (ConnectionStatusBanner.tsx:173).
    await expect
      .poll(async () => (await snapshot(page)).bannerText === null, {
        timeout: 10_000,
        message: 'connected shell still renders the disconnect banner',
      })
      .toBe(true);

    // The offline boot needs the worker in charge and the boot's API answers
    // in api-cache; without the warmed setup-status the reload fail-closes to
    // /setup (offline-cache.spec.ts X5).
    await page.waitForLoadState('load');
    await waitControlled(page, `${h.ui}/`);
    const warmed = await page.evaluate(async (keys: string[]) => {
      const out: Record<string, number> = {};
      for (const k of keys) out[k] = (await fetch(k, { credentials: 'include' })).status;
      return out;
    }, WARM);
    expect(warmed, 'every warmed key must answer 200 online').toEqual({
      '/api/auth/setup-status': 200,
      '/api/cameras': 200,
      '/api/auth/me': 200,
    });
    await expect
      .poll(() => apiCacheHas(page, WARM), {
        message: 'NetworkFirst must have written all warmed keys to api-cache',
        timeout: 15_000,
      })
      .toBe(true);

    // --- PARTITION + RELOAD: force FRESH handshakes, never wait on old ones. ---
    const responses: Response[] = [];
    page.on('response', (r) => responses.push(r));
    await page.context().setOffline(true);
    await expect
      .poll(() => page.evaluate(() => navigator.onLine), {
        message: 'partition must take',
        timeout: 10_000,
      })
      .toBe(false);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('load');
    // Drain for the boot's lazy chunks (offline-cache probe: at 'load' the
    // shell is 3 responses; by +1.5 s ~44, all worker-served).
    await page.waitForTimeout(1_500);

    // The reload is REAL and cache-served, not a dev-server artifact: every
    // shell response came from the worker at 200, document and entry bundle
    // included (offline-cache.spec.ts:361-382 instrument).
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
    expect(
      shell.some((r) => /\/assets\/index-[\w-]+\.js$/.test(r.url())),
      'the entry bundle must have come from cache'
    ).toBe(true);

    // The row's clause from ONE coherent sample of the offline-booted shell:
    // banner (role=alert) + "Reconnecting" + counter Attempt n/30 + duration
    // counting up. Every channel handshake since the reload was a NEW one and
    // failed in ~1 ms (probe), so this is a schedule question, not a host
    // question — 25 s covers the staggered first ticks (both channels' attempt
    // 0 lands ≤ 1.25 s after boot; the banner needs the 'reconnecting' commit).
    // n is NOT pinned: it is a sum that depends on which close tick landed
    // last. Sequential locator expects instead would race the flap that killed
    // this leg's second draft (role found, text gone).
    const box: { s?: Snap } = {}; // box, not `let s: Snap | null` — a
    // closure-assigned let leaves TS 6.0.3 narrowing the post-poll use to
    // `never` (TS2339 'counter' on never); a property read stays Snap|
    // undefined and unwraps with a normal guard below.
    await expect
      .poll(
        async () => {
          const s = await snapshot(page);
          box.s = s;
          return (
            s.bannerRole === 'alert' &&
            /Reconnecting/.test(s.bannerText ?? '') &&
            /^Attempt \d+\/30$/.test(s.counter ?? '') &&
            DURATION.test(s.duration ?? '') &&
            s.branding === true
          );
        },
        {
          timeout: 25_000,
          message:
            'offline-reloaded shell never produced a coherent banner+Reconnecting+Attempt n/30 sample',
        }
      )
      .toBe(true);
    const s0 = box.s;
    if (!s0) throw new Error('poll never sampled'); // unreachable; type guard
    const first = Number((s0.counter ?? '0/30').match(/\d+/)?.[0] ?? '0');

    // The counter is LIVE, not static: the machine keeps scheduling attempts
    // and each fresh handshake fails. Offline makes a reset structurally
    // impossible (a reset needs onopen — useWebSocketStatus.ts:162-174 — and
    // offline lets zero upgrades reach the server, probe), so the increment is
    // monotone here. The budget is the WORST slot the schedule can be sitting
    // in when this poll starts: at ~25 s offline the staggered channels are
    // around attempt 4, whose slot is min(1000·2^4, 30000) × (1 + ≤0.25)
    // ≈ 20 s (calculateBackoffDelay, useWebSocketStatus.ts:58-67), so 45 s.
    await expect
      .poll(
        async () => {
          const t = await snapshot(page);
          const n = /^Attempt (\d+)\//.exec(t.counter ?? '');
          // −1, not `first`: a vanished counter must fail (it can never
          // satisfy > first either way) but it must name ITSELF, not read as
          // "the number never climbed".
          return n ? Number(n[1]) : -1;
        },
        {
          timeout: 45_000,
          message: 'reconnect counter never incremented (or vanished) while partitioned',
        }
      )
      .toBeGreaterThan(first);

    // The exhaustion legs must NOT be active (331–414 s away — their absence
    // is the honest half of the deferral, ruling 86): no polling fallback, no
    // REST Fallback pill, no Retry button (that one belongs to 'failed' —
    // ConnectionStatusBanner.tsx:179/:233-241). And the offline boot really
    // booted the app: header chrome is on screen, nothing crashed.
    const mid = await snapshot(page);
    expect(mid.polling).toBe(false);
    expect(mid.restPill).toBe(false);
    expect(mid.retryButton).toBe(false);
    expect(mid.branding).toBe(true);

    // Restore — the machine wakes on its next SCHEDULED retry, not at the
    // instant the network returns (measured; file header). ONE poll over ONE
    // predicate, because the two surfaces wait on two INDEPENDENT state
    // machines: useConnectionStatus() is called at Layout.tsx:38 AND
    // Header.tsx:171, each mounting two useWebSocketStatus hooks with their
    // own Math.random() jitter, so the chip (Header's summary) and the
    // banner's null render (Layout's own connectionState,
    // ConnectionStatusBanner.tsx:173) can each be a capped slot behind the
    // other. Worst case after the restore is 2 × 30 s × 1.25 ≈ 75 s per
    // instance; a separate 15 s budget on the second half does not bound
    // that, so both clauses ride one 90 s poll. Sequential predicates here
    // are the "role found, text gone" failure class this cure exists to
    // remove, re-appearing one level up.
    await page.context().setOffline(false);
    await expect
      .poll(
        async () => {
          const t = await snapshot(page);
          return (
            (t.chip ?? '').includes('WebSocket connection status: Connected') &&
            t.bannerText === null
          );
        },
        {
          timeout: 90_000,
          message:
            'after the restore: never reached chip Connected AND banner un-rendered (both channels, both hook instances)',
        }
      )
      .toBe(true);

    // The leg just hammered /api through the worker while partitioned; drain
    // so the next spec inherits a full nginx burst bucket (harness.ts).
    await page.waitForTimeout(BOOT_QUIET_MS);
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
