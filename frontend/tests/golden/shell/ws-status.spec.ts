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
 * - Disconnect leg: context.setOffline(true) is Chromium's real network
 *   partition — the e2e lane's own instrument (tests/e2e/utils/browser-helpers
 *   .ts:311 simulateOfflineMode). It is NOT route()/routeWebSocket(), so the
 *   guard's no-interception contract holds: nothing is mocked; the visible
 *   changes all come from the app's own state machine. But Chromium's offline
 *   emulation against ESTABLISHED loopback WebSockets is NOT deterministic in
 *   TIMING (both measured 2026-10-11 with DOM-transition probes): one run
 *   surfaced the break ~10 s after setOffline (Reconnecting/banner/Attempt 1/30
 *   at +10.3 s, then the app's own 1s·2^n backoff scheduling attempts at
 *   11.5/13.8/18.3/27.5 s — webSocketManager.ts:210-219 caps at 30 s + ≤25%
 *   jitter; 15 attempts per channel, useWebSocketStatus.ts:79-84, the shipped
 *   comment: "~8+ minutes of retry"); another (mid-suite) surfaced it in ~2 s
 *   and then FLAPPED — the banner mounted, unmounted on a transient
 *   'connected', remounted — and per-locator sequential expects raced the
 *   flap (role found, text gone). The honest instrument is therefore ONE
 *   page.evaluate snapshot whose fields are mutually coherent, polled until a
 *   sample satisfies the conjunction — never a chain of locators re-resolved
 *   against a moving target.
 * - Banner facts asserted per coherent sample: role=alert, "Reconnecting"
 *   (ConnectionStatusBanner renders null when connected, :173 — the boot-time
 *   negative control and the recovery assertion), "reconnect-counter"
 *   Attempt n/30 (15 × 2 channels summed by Layout.tsx:112-121),
 *   "disconnected-duration" counting up (:207-211, family not pinned).
 * - The row's third clause — retries EXHAUST, then "REST Fallback" appears
 *   and data polls every 5 s (useConnectionStatus.ts:115
 *   FALLBACK_POLLING_INTERVAL, startPolling on onMaxRetriesExhausted) — is
 *   NOT reachable inside golden timeouts: exhausting 15 exponential attempts
 *   per channel takes the ~8 minutes the shipped comment states, against any
 *   sane test budget, and no runtime knob shortens it (the count is a hook
 *   default; editing hook or config is ruling 87 territory and would test a
 *   shape CI never ships). Per ruling 86 this spec does not assert that leg
 *   vacuously: the inventory row carries the deferral with this measurement,
 *   and the real tier (ruling 66) — where the operator can leave a stack down
 *   for minutes — owns it. What IS asserted here is that the fallback has NOT
 *   started during a short partition: polling-indicator /
 *   polling-fallback-indicator / the header's plain "REST Fallback" pill stay
 *   absent (isPollingFallback-gated, WebSocketStatus.tsx:339-343,
 *   ConnectionStatusBanner.tsx:222-226, Header.tsx:397-401).
 * - Recovery leg: MEASURED (same probes): restoring the network changes
 *   nothing by itself — the flip happens on the hook's next SCHEDULED retry
 *   (a probe sitting at Attempt 5 at t+30 s detected nothing at the instant
 *   of setOffline(false); Connected arrived ~25 s later there, ~48 s in a
 *   run whose schedule had reached the 30 s cap). Both channels must open,
 *   each on its own jittered schedule, so the recovery poll carries 90 s.
 *   stopPolling-on-connected (useConnectionStatus.ts:305-309) and the
 *   banner's null render close the leg.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
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

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
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
      restPill: (document.body.innerText ?? '').includes('REST Fallback'),
      branding: !!q('[data-testid="header-branding"]'),
    };
  });
}
type Snap = Awaited<ReturnType<typeof snapshot>>;

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
    test.setTimeout(60_000);
    await openShell(page, h);
    await expectBothChannelsConnected(page);

    // Connected ⇒ the banner is NOT rendered (ConnectionStatusBanner returns
    // null for 'connected', :173) — the negative control the disconnect leg
    // later flips.
    await expect(page.getByTestId('connection-status-banner')).toHaveCount(0);

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

  // owner ruling 125 — quarantined until fixed, expires 2026-10-14T00:00Z
  test.fixme('F-007: partitioning the network raises the banner with a live attempt counter, and the shell recovers', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // Budget from the measured timeline (file header): surfacing up to ~10 s,
    // increments on the backoff schedule, restore + the worst jittered slot
    // pair (30 s cap + 25% jitter, twice).
    test.setTimeout(180_000);
    await openShell(page, h);
    await expectBothChannelsConnected(page);

    // Partition for real: Chromium offline, not an interception — the guard
    // contract holds because nothing is intercepted (see file header).
    await page.context().setOffline(true);

    // WITNESS the break before asserting the machine: on the CI feature-check
    // host Chromium's offline emulation NEVER surfaced on the ESTABLISHED
    // loopback sockets — the chip still read Connected 60 s after partition,
    // identical across all 3 attempts (initial + 2 retries; junit + per-attempt DOM snapshots, run
    // 38146684985). Standalone probe stacks surface it (~2 s local). Same
    // disk-warning precedent: where the instrument cannot run, the spec
    // self-skips at RUNTIME carrying the measurement — never a silent pass,
    // and never a red that reads as a product regression.
    let tornAtMs = -1;
    const t0 = Date.now();
    while (Date.now() - t0 < 15_000) {
      const s = await snapshot(page);
      if (s.bannerRole === 'alert' || !/Connected/.test(s.chip ?? 'Connected')) {
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
          'host, measured 2026-10-11: 3/3 attempts — initial + 2 retries — chip still Connected after 60 s); ' +
          'ruling 86: the leg is unexecutable here, not failed'
      );

    // The row's clause from ONE coherent sample: banner (role=alert) +
    // "Reconnecting" + counter naming n/30 + duration counting up. 60 s
    // covers both measured surfacing timings (~2 s and ~10.3 s) and flap
    // cycles. Sequential locator expects instead would race the mid-suite
    // flap that killed this leg's second draft (role found, text gone).
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
            /^\(\d+s\)$/.test(s.duration ?? '')
          );
        },
        { timeout: 60_000, message: 'no coherent banner+Reconnecting+Attempt n/30 sample' }
      )
      .toBe(true);
    const s0 = box.s;
    if (!s0) throw new Error('poll never sampled'); // unreachable; type guard
    const first = Number((s0.counter ?? '0 0').match(/\d+/)?.[0] ?? '0');

    // The counter is LIVE, not static: while partitioned the machine keeps
    // scheduling attempts (probe: 1→5 across 27 s). A transient 'connected'
    // flap zeroes it (onopen resets the count, useWebSocketStatus.ts:170), so
    // a sample without the banner holds position instead of faking progress.
    await expect
      .poll(
        async () => {
          const t = await snapshot(page);
          const n = /^Attempt (\d+)\//.exec(t.counter ?? '');
          return n ? Number(n[1]) : first;
        },
        { timeout: 60_000, message: 'reconnect counter never incremented while partitioned' }
      )
      .toBeGreaterThan(first);

    // The REST-fallback legs must NOT be active (exhaustion is ~8 min away —
    // their absence is the honest half of the deferral), and the SPA
    // survived the partition: chrome still on screen, nothing crashed.
    const mid = await snapshot(page);
    expect(mid.polling).toBe(false);
    expect(mid.restPill).toBe(false);
    expect(mid.branding).toBe(true);

    // Restore — the machine wakes on its next SCHEDULED retry, not at the
    // instant the network returns (measured; file header). 90 s covers the
    // worst jittered pair of 30 s-capped slots, one per channel.
    await page.context().setOffline(false);
    await expect
      .poll(async () => (await snapshot(page)).chip, {
        timeout: 90_000,
        message: 'channels never reconnected after the network returned',
      })
      .toMatch(/WebSocket connection status: Connected/);
    // Both channels up fires the banner's null render AND stopPolling
    // (useConnectionStatus.ts:305-309); polled so a one-commit render lag
    // cannot false-fail the recovery the row claims.
    await expect
      .poll(async () => (await snapshot(page)).bannerText, { timeout: 15_000 })
      .toBeNull();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
