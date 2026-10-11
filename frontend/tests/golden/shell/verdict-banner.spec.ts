/**
 * FE-1 golden path (F2.3): F-016 — the verdict-engine status banner (F1.2).
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - Available leg: Layout.tsx:128-135 mounts VerdictEngineStatusBanner only
 *   once the hook is `loaded`, and the component returns null for
 *   'available' (VerdictEngineStatusBanner.tsx:128-130). The hook seeds
 *   'unknown' but the loaded gate keeps a healthy boot from painting a false
 *   warning (Layout.tsx:125-127 comment). So on a healthy stack the banner is
 *   absent AND the endpoint it reads (fetchReadiness → GET
 *   /api/system/health/ready, api.ts:2129-2131) says verdict_engine.state
 *   'available' — app absence and backend verdict must agree, both read here.
 * - Degraded/unknown leg (the real one this spec drives): the hook re-reads
 *   readiness on a 15 s poll (useVerdictEngineStatus.ts:74 DEFAULT_POLL_
 *   INTERVAL_MS; the backend caches the probe for the same 15 s, so the poll
 *   is cheap by design). Partitioning the browser with context.setOffline —
 *   the e2e lane's own instrument (tests/e2e/utils/browser-helpers.ts:311),
 *   NOT route()/routeWebSocket(), so the guard's no-interception contract
 *   holds — makes that poll's fetch fail; fetchWithRetry spends its 3
 *   retries (MAX_RETRIES 3, delays 1 s/2 s/4 s, api.ts:893-912) and throws,
 *   and the hook's catch takes the HONEST branch (:182-198): state 'unknown',
 *   reason 'readiness probe unavailable', and since DROPPED on purpose — a
 *   failed read cannot prove WHEN the engine went down, so a stale
 *   transition time must not masquerade as downtime (the comment says
 *   exactly that). The banner then renders (VerdictEngineStatusBanner.tsx:
 *   :131-176): role=status + aria-live=polite + yellow classes (STYLING,
 *   :51-58), text 'Verdict engine state unknown', the fixed fallback line
 *   about verification_failed, and data-testid verdict-engine-reason with the
 *   hook's string — while verdict-engine-since is NOT rendered (elapsed empty
 *   ⇒ :143-148 skips the span). That absence is asserted deliberately: it IS
 *   the honesty rule, visible in DOM.
 * - Recovery: the next scheduled 15 s poll succeeds once the network returns
 *   (the poll is the convergence mechanism, hook :13-16 comment — the WS
 *   event is fire-and-forget and only fires on transitions), state flips back
 *   to 'available', the component returns null again.
 * - The row's 'unavailable' (red, role=alert, real since) leg is NOT
 *   reachable on the golden tier without stopping the ai-vlm container: the
 *   ONLY writer of the backend tracker is get_readiness's own probe (backend/
 *   api/routes/system.py:1549 → verdict_engine_status.py _derive_state :95-
 *   :124: unavailable needs the probe's details['ai-vlm'] to carry an error
 *   string), and the fake VLM's fault knob is a REQUEST HEADER on
 *   /v1/chat/completions (x-fake-fault, backend/ai_contract/fake/app.py:77,
 *   :290-314) while its /health answers 200 unconditionally (:174-177) — no
 *   HTTP-level call can make the readiness probe see a dead engine. Per
 *   ruling 86 this spec does not assert that leg vacuously: the inventory
 *   row carries the deferral with this finding, and the container-stop fault
 *   belongs to the real tier (ruling 66), where the operator can actually
 *   take the engine down and watch since-when tick.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  adminSession,
  api,
  closedByGuard,
  quietBoot,
  loginAsAdmin,
  readShellHarness,
  seedTourDismissed,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

interface Readiness {
  verdict_engine: { state: string; since: string | null; reason: string | null };
}

/** One coherent DOM sample of everything F-016 renders (see file header). */
function snapshot(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const q = (sel: string) => document.querySelector(sel);
    const banner = q('[data-testid="verdict-engine-banner"]');
    return {
      bannerRole: banner?.getAttribute('role') ?? null,
      ariaLive: banner?.getAttribute('aria-live') ?? null,
      bannerText: banner?.textContent ?? null,
      sinceSpan: q('[data-testid="verdict-engine-since"]')?.textContent ?? null,
      reasonSpan: q('[data-testid="verdict-engine-reason"]')?.textContent ?? null,
      classes: banner?.getAttribute('class') ?? null,
      branding: !!q('[data-testid="header-branding"]'),
    };
  });
}
type Snap = Awaited<ReturnType<typeof snapshot>>;

test.describe('golden path: verdict-engine status banner @critical', () => {
  test('F-016: healthy engine paints no banner; a network failure paints the honest unknown one', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // Offline leg budgets the 15 s poll boundary + retry storm (~7 s); the
    // recovery leg budgets one more poll cycle. Sizing rationale in header.
    test.setTimeout(150_000);

    // The engine's own verdict, straight from the endpoint the hook reads.
    const session = await adminSession(h);
    const ready = await api<Readiness>(h, session, '/api/system/health/ready');
    expect(ready.verdict_engine.state).toBe('available');

    await openShell(page, h);

    // Available + loaded ⇒ null render (VerdictEngineStatusBanner.tsx:129).
    // The loaded gate means an early 'unknown' seed must NOT paint either
    // (Layout.tsx:125-127) — count 0 is both claims at once.
    await expect(page.getByTestId('verdict-engine-banner')).toHaveCount(0);

    // Partition: the readiness POLL now fails; the hook's honest branch
    // mounts the yellow polite banner. 45 s = worst poll boundary (15 s) +
    // retry storm (1+2+4 s) + margin for Chromium's surfacing latency
    // (setoffline-loopback memory: fetches fail fast, but the FIRST tick
    // lands on the poll boundary, not at setOffline time).
    await page.context().setOffline(true);
    let s: Snap | null = null;
    await expect
      .poll(
        async () => {
          s = await snapshot(page);
          return (
            s.bannerRole === 'status' &&
            s.ariaLive === 'polite' &&
            /Verdict engine state unknown/.test(s.bannerText ?? '') &&
            /New events need review/.test(s.bannerText ?? '') &&
            s.reasonSpan === 'readiness probe unavailable' &&
            s.sinceSpan === null && // the honesty rule: since is DROPPED (:189-192)
            /bg-yellow-900\/30/.test(s.classes ?? '') &&
            s.branding === true
          );
        },
        { timeout: 45_000, message: 'no coherent honest-unknown banner sample' }
      )
      .toBe(true);
    if (!s) throw new Error('poll never sampled'); // unreachable; type guard

    // "Persistent" per the row: it does not auto-dismiss. Hold ~3 s (well
    // under any plausible animation, across two poll-free moments) — same
    // coherent-snapshot instrument.
    await page.waitForTimeout(3_000);
    const held = await snapshot(page);
    expect(held.bannerRole).toBe('status');
    expect(held.reasonSpan).toBe('readiness probe unavailable');

    // Restore: the 15 s poll is the convergence mechanism (the WS transition
    // cannot fix a missed state — hook header). Next success ⇒ null render.
    await page.context().setOffline(false);
    await expect
      .poll(async () => (await snapshot(page)).bannerRole, {
        timeout: 40_000,
        message: 'banner never cleared after the network returned',
      })
      .toBeNull();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
