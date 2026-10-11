/**
 * FE-1 golden path (F2.3): F-022 rate-limit indicator + retrying pill.
 *
 * Row claim: "after a 429, sees a countdown overlay until the limit resets,
 * and a 'retrying' pill while requests are in flight". Both components mount
 * app-wide OUTSIDE <Routes> (App.tsx:346/:348), fed by ONE zustand store with
 * TWO writers:
 *
 *   1. HEADER feed — api.ts handleResponse :1203-1206 calls
 *      extractRateLimitInfo, which needs ALL THREE X-RateLimit-{Limit,
 *      Remaining,Reset} headers. The FastAPI tier emits them ONLY on its 429
 *      (success responses carry NO rate headers at all, measured 2026-10-11
 *      in test 3 below), so the "quota low" (<=50%) progress band is
 *      producible by no shipped path. Failure-as-evidence, row note.
 *   2. ERROR-DEFAULTS feed — QueryCache/MutationCache onError
 *      (queryClient.ts:795-804) -> updateRateLimitStoreFromError (:249-297):
 *      an ApiError with status 429 — the SHAPE the frontend's own nginx
 *      throttle produces (limit_req zone=api burst=20 nodelay,
 *      limit_req_status 429, docker-entrypoint.sh:166-169, text/html body ->
 *      problemDetails undefined) — sets the store to the FABRICATED defaults
 *      limit=100, remaining=0, reset=now+60 (DEFAULT_RATE_LIMIT_RETRY_SECONDS
 *      :64). The countdown the user sees is that invented window, not nginx's
 *      real one — the spec pins "Retry in 1:0X", never a server-true reset.
 *
 * WHY THE nginx SHED IS THE GOLDEN TRIGGER: every fetchApi-wired FastAPI-tier
 * control is dead or gated on a golden stack (all measured this pass):
 * useBulkDetectionMutations has ZERO importers; PromptPlayground's fetchApi
 * testPrompt — the one AI_INFERENCE-tier UI control — renders only when
 * audited_events>0 (AIAuditPage.tsx:193-195/:349; feature-check stacks seed
 * 0 → the tab never mounts); EventTimeline's bulk path loops per-id
 * UN-tiered PATCHes; ExportButton uses raw fetch. Test 3 pins the other half
 * of that honesty: the tier IS real (BULK = 10 rpm + burst 2 → 12 accepts
 * then header-complete 429s at PATCH /api/events/bulk) yet the indicators
 * stay DARK for it — a raw fetch bypasses fetchApi, so the store never sees
 * a tier denial.
 *
 * THE BUCKET MATH the flood respects (nginx ngx_http_limit_req @10r/s: each
 * request costs 100 ms of excess, burst=20 nodelay): a 60-request burst
 * parks stored excess AT the ceiling (rejections add nothing back — probes
 * 9/10 measured a single burst draining in ~2 s, too short to click inside);
 * a drip every 80 ms (12.5 r/s > 10 r/s refill) pins excess >= burst for the
 * drip's whole span, making a click inside it deterministic 429. Measured
 * 2026-10-11 probes 10/12 on the live stack: POST 429 (Server: nginx, no
 * X-RateLimit-*, no Retry-After) -> "Rate Limited / Retry in 1:00", aria
 * ticking 0:53 -> 0:50 across 2.3 s; sonner toast "API quota running low —
 * Only 0 of 100 requests remaining" at +1.7 s (the fabricated defaults at
 * 0% < 20% threshold, duration 6000); reload clears the store (per-document
 * — persistOptions cover query state, not this store) and no shed ever
 * failed closed to /setup.
 *
 * Instrument choices, each measured against a failed alternative:
 * - Flood rides context.request (Node-side): the probes' ONE in-main-page
 *   fetch storm (929 fetches) crushed the renderer until no click could run
 *   (probe7), and a drip inside a NON-active page would hit Chromium's
 *   hidden-page timer throttling (~1/s) and clump instead of pinning.
 *   context.request hits the same nginx $binary_remote_addr bucket for free.
 * - Clicks go through el.click() inside page.evaluate after an enabled-button
 *   waitForFunction: with the bucket dirty the panel's query churn made
 *   Playwright actionability retries drift past the drip boundary (probe10/
 *   11 measured 3 s timeouts on an enabled+visible button, probe12's DOM dump
 *   proved dis:false vis:true); the trusted click on the SAME button React
 *   listens to lands the shed every run.
 * - The pill (isLimited AND isFetching/isMutating, ~650 ms wide in probe12's
 *   trace — too narrow to await with a locator, so it is SAMPLED with an rAF
 *   frame trace) is lit by a sidebar-link click: a client-side navigation
 *   KEEPS the limited store (SPA) while the destination's cold queries fire
 *   -> isFetching > 0 -> pill. Probe12 reached the same frame through a
 *   second shed mutation (PI +1535 ms, -I +2182 ms), but a shed-driven pill
 *   additionally needs an ENABLED level button, and all five are disabled
 *   while ANY level mutation is pending — luck-shaped. The nav pill needs
 *   only in-flight queries, which a shed flood guarantees; it counts traffic,
 *   whatever status that traffic lands on.
 * - Shed honesty: run-to-run, either click (or the panel's own refetch
 *   wave) can be the request the final-error feed sees (probe11 measured a
 *   429 POST list of [200] yet the store still lit from a query final
 *   error). So the spec asserts the posts list contains at least one 429 and
 *   otherwise asserts ONLY store-visible outcomes.
 *
 * SIDE EFFECTS owned by this file: the clicked control is the Operations
 * page's Log Level panel (SystemMonitoringPage.tsx:751 -> POST
 * /api/debug/log-level via useSetLogLevelMutation; mutations never retry 429
 * — utils shouldRetryMutation covers timeouts only — so a shed POST is FINAL
 * and writes the store). A shed POST cannot change the level; an unsent one
 * can, so the level is restored before the spec ends, over h.api DIRECT
 * (the backend's published port — no nginx throttle there, same leg
 * harness.adminSession/api ride; WARNING is the stack default, so the
 * restore is idempotent even if the read failed). The flood (~105 /api
 * requests) is the golden project's one deliberate throttle consumer —
 * serial golden worker (playwright.config.ts:287-288), BOOT_QUIET_MS drain
 * before every navigation AND before the reload; test 3 warms the bucket and
 * then paces its PATCH loop at 120 ms (~8.3 r/s < 10 r/s) so nginx never
 * sheds inside the tier measurement.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
  api,
  closedByGuard,
  loginAsAdmin,
  readShellHarness,
  seedTourDismissed,
  type Session,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** nginx /api throttle geometry (docker-entrypoint.sh:166-169; nginx.conf zones). */
const BURST = 60; // >> burst=20 -> rejections pin stored excess at the ceiling
const DRIP_MS = 80; // 12.5 req/s > the 10 r/s refill -> excess never drains
const DRIPS = 45; // ~3.5 s of pinned window; all three clicks land inside it

/**
 * Authenticate ONLY if the stack demands it (feature-check stacks run
 * auth_required=true after register_admin; probe stacks may run it false —
 * GET /api/auth/setup-status answers anonymously and decides). The session
 * rides h.api direct (free of the nginx bucket, like harness.adminSession);
 * null means the stack is anonymous and no cookie is needed.
 */
async function maybeLogin(
  page: import('@playwright/test').Page,
  h: ShellHarness
): Promise<Session | null> {
  const ss = await page
    .context()
    .request.get(`${h.ui}/api/auth/setup-status`)
    .then((r) => r.json().catch(() => null))
    .catch(() => null);
  return ss?.auth_required === true ? loginAsAdmin(page, h) : null;
}

/**
 * Open the Log Level panel (login if asked, drain, navigate, expand) and REST
 * until the bucket is back to a full burst. The 2.5 s calm is the flood's
 * precondition, not a courtesy: measured run 2026-10-11 09:58Z, a flood fired
 * straight after panel-open found a bucket the boot wave had just drained —
 * 11 of 60 accepted, the accepted (backend-slow) responses kept Promise.all
 * waiting seconds, the drip started after the bucket drained, and the click
 * sailed through with excess ~0 (POSTS [200]). Probes 10/12 (green) calmed
 * ~3 s after the panel resolved, so the flood hit a FULL burst: ~20 fast
 * passes, the rest nginx-instant 429s, Promise.all settling in well under a
 * second with the ceiling pinned.
 */
async function openOperations(
  page: import('@playwright/test').Page,
  h: ShellHarness
): Promise<Session | null> {
  await seedTourDismissed(page); // guard.ts's fixture seeds these too; siblings re-seed
  const session = await maybeLogin(page, h);
  await page.waitForTimeout(BOOT_QUIET_MS); // shared nginx burst, harness.ts
  await page.goto(`${h.ui}/operations`, { waitUntil: 'commit' });
  await page.waitForSelector('[data-testid="log-level-section-toggle"]', {
    timeout: 20_000,
  });
  await page.click('[data-testid="log-level-section-toggle"]'); // default-closed
  await page
    .getByRole('button', { name: 'DEBUG', exact: true })
    .last()
    .waitFor({ timeout: 15_000 }); // panel query resolved
  await page.waitForTimeout(2_500); // CALM: boot + panel-query waves done, burst full
  return session;
}

/** Click a level button by exact label once it is ENABLED (see header). */
async function clickLevel(page: import('@playwright/test').Page, level: string) {
  await page.waitForFunction(
    (name) =>
      [...document.querySelectorAll('button')].some(
        (b) => b.textContent?.trim() === name && !b.disabled
      ),
    level,
    { timeout: 5_000 }
  );
  await page.evaluate(
    (name) =>
      (() => {
        const bs = [...document.querySelectorAll('button')].filter(
          (b) => b.textContent?.trim() === name && !b.disabled
        );
        bs[bs.length - 1]?.click();
      })(),
    level
  );
}

test.describe('golden path: rate-limit indicators @critical', () => {
  test('F-022 (calm): a healthy stack mounts neither indicator', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);
    await openOperations(page, h);
    // Both components render NULL with an empty store (the `if (!current)` /
    // `isLimited &&` returns) — the shed test's "lit" needs this baseline.
    await expect(page.getByTestId('rate-limit-indicator')).toHaveCount(0);
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-022 (shed): an nginx-throttled 429 lights the countdown with the fabricated 100/0/+60 window, ticks, toasts, pairs with the pill across an SPA nav, and reloads clean', async ({
    context,
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000); // flood + tick + reload + restore; measured ~30 s

    // BEFORE anything else: catch every log-level POST, shed or not.
    const posts: number[] = [];
    page.on('response', (r) => {
      if (r.request().method() === 'POST' && r.url().includes('/api/debug/log-level'))
        posts.push(r.status());
    });

    const session = await openOperations(page, h);
    // Best-effort: what level is live? Read over h.api DIRECT (no throttle);
    // restore target, WARNING if unreadable.
    const original = await (
      session
        ? api<{ level?: string }>(h, session, '/api/debug/log-level')
        : context.request
            .get(`${h.api}/api/debug/log-level`)
            .then((r) => r.json().catch(() => null))
    )
      .then((b: { level?: string } | null) => b?.level ?? null)
      .catch(() => null);

    // rAF trace of (pill, indicator) presence — the pill is ~650 ms wide when
    // pill-driven, so it is SAMPLED, not awaited after the fact.
    const trace: Promise<Array<{ k: string; atMs: number }>> = page
      .evaluate(
        () =>
          new Promise<Array<{ k: string; atMs: number }>>((res) => {
            const t0 = performance.now();
            const out: Array<{ k: string; atMs: number }> = [];
            let last = '';
            const tick = () => {
              const p = !!document.querySelector('[data-testid="retrying-indicator"]');
              const i = !!document.querySelector('[data-testid="rate-limit-indicator"]');
              const k = `${p ? 'P' : '-'}${i ? 'I' : '-'}`;
              if (k !== last) {
                out.push({ k, atMs: Math.round(performance.now() - t0) });
                last = k;
              }
              if (performance.now() - t0 < 10_000) requestAnimationFrame(tick);
              else res(out);
            };
            requestAnimationFrame(tick);
          })
      )
      .catch((e) => {
        // Navigation would destroy the context; the test never navigates
        // inside the window — fail LOUD rather than lose the evidence.
        throw new Error(`pill tracer died: ${String(e).slice(0, 120)}`);
      });

    // FLOOD from Node (context.request): same nginx client-IP bucket, zero
    // renderer load, no hidden-page timer throttling (probe7/probe10).
    const burstCodes = await Promise.all(
      Array.from({ length: BURST }, (_, i) =>
        context.request
          .get(`${h.ui}/api/system/health?F${i}`)
          .then((r) => r.status())
          .catch(() => -1)
      )
    );
    const drips: Promise<unknown>[] = [];
    for (let d = 0; d < DRIPS; d++)
      drips.push(
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve(
                context.request
                  .get(`${h.ui}/api/system/health?D${d}`)
                  .then((r) => r.status())
                  .catch(() => -1)
              ),
            d * DRIP_MS
          )
        )
      );

    await page.waitForTimeout(900); // mid-drip: bucket pinned RIGHT NOW
    await clickLevel(page, 'DEBUG');
    await page.waitForTimeout(900); // still mid-drip
    await clickLevel(page, 'INFO');

    await expect
      .poll(() => posts.includes(429), {
        timeout: 5_000,
        message: `no POST was shed (statuses ${JSON.stringify(posts)}; burst codes ${burstCodes.join(',')})`,
      })
      .toBe(true);

    const indicator = page.getByTestId('rate-limit-indicator');
    await expect(indicator).toBeVisible({ timeout: 3_000 });
    await expect(indicator).toHaveText(/Rate Limited/);
    await expect(indicator).toHaveText(/Retry in \d:\d{2}/);
    await expect(indicator).toHaveAttribute('role', 'status');
    await expect(indicator).toHaveAttribute('aria-label', /^Rate limited\. Retry in \d:\d{2}$/);

    // The low-quota toast (<20% branch fired by the FABRICATED 0-of-100
    // defaults; sonner duration 6000 ms — read while still on screen).
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'API quota running low' }).first()
    ).toBeVisible();
    await expect(
      page.locator('[data-sonner-toast]').filter({ hasText: 'Only 0 of 100 requests' }).first()
    ).toBeVisible();

    // The pill (isLimited AND (isFetching || isMutating)): click a sidebar
    // link — a client-side navigation that KEEPS the store (SPA, no reload)
    // while the destination page's cold queries fire -> isFetching > 0 ->
    // RetryingIndicator. This is deliberate over probe12's second-shed route
    // (which also worked, PI at +1535 ms): a shed-driven pill needs a third
    // click inside the pinned drip AND an enabled button (all five are
    // disabled while ANY level mutation is pending), so its window is
    // luck-shaped; the nav pill needs only that react-query has work to do —
    // which the shed flood guarantees in abundance. Shed luck plays no part:
    // the pill counts IN-FLIGHT queries, whatever status they land on.
    // Scoped to the sidebar: MobileBottomNav renders a same-named link that
    // is display-none at desktop widths, and getByRole sees hidden nodes.
    await page.getByTestId('sidebar').getByRole('link', { name: 'Dashboard' }).first().click();

    // Countdown ticks (useRateLimitCountdown's 1000 ms interval,
    // formatCountdown M:SS) — measured probe10: 0:53 -> 0:50 across 2.3 s.
    const a1 = await indicator.getAttribute('aria-label');
    await page.waitForTimeout(2_300);
    const a2 = await indicator.getAttribute('aria-label');
    expect(a1).toMatch(/^Rate limited\. Retry in \d:\d{2}$/);
    expect(a2).toMatch(/^Rate limited\. Retry in \d:\d{2}$/);
    expect(a2, `countdown frozen at ${a1} / ${a2}`).not.toBe(a1);

    const frames = await trace;
    const states = frames.map((f) => f.k);
    expect(states, `no pill frame in ${JSON.stringify(frames)}`).toContain('PI');
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0, { timeout: 8_000 });

    // Reload: the store is per-document JS state (NOT the persisted query
    // cache), so the overlay cannot survive navigation — and the shed never
    // bounced the app to /setup. Drain first (a reload IS a boot wave).
    await Promise.allSettled(drips);
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('rate-limit-indicator')).toHaveCount(0);
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);
    expect(page.url()).not.toContain('/setup');

    // Restore over h.api DIRECT (no nginx throttle on that leg, so the
    // restore itself cannot shed). Idempotent: WARNING is the stack default.
    const restore = async () =>
      context.request
        .post(`${h.api}/api/debug/log-level`, {
          headers: { 'Content-Type': 'application/json' },
          data: JSON.stringify({ level: original ?? 'WARNING' }),
        })
        .then((r) => r.status()); // METHOD — APIResponse has no fetch-style .status property
    let restored = await restore().catch(() => -1);
    if (restored !== 200) {
      await new Promise((r) => setTimeout(r, 1_500));
      restored = await restore().catch(() => -1);
    }
    // context.request shares the context's cookie jar, so when maybeLogin
    // stored a session the restore is authenticated; h.api is the backend's
    // published port (no nginx in front), so it cannot shed. 200 is the
    // measured path (probe stacks answer anonymously; feature-check stacks
    // send the seeded cookie cross-port on the same hostname).
    expect(restored, `log-level restore answered ${restored}`).toBe(200);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-022 (bypass): the FastAPI tier 429 is real and header-complete, yet the indicators stay dark because the store is only fed through fetchApi', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000); // warm waits included

    await seedTourDismissed(page);
    await maybeLogin(page, h);
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(`${h.ui}/timeline`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });

    const probePatch = () =>
      page.evaluate(async () => {
        const r = await fetch('/api/events/bulk', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events: [{ id: 999_999_999, reviewed: true }] }),
        });
        return { s: r.status, hdr: r.headers.get('x-ratelimit-limit') };
      });

    // Warm gate A (nginx): a 429 WITHOUT the tier's header set is the
    // frontend throttle still draining test 2 — wait the bucket out.
    for (let warm = 0; warm < 4; warm++) {
      const p = await probePatch();
      if (p.s !== 429 || p.hdr !== null) break;
      await page.waitForTimeout(3_000);
    }
    // Warm gate B (tier): a 429 WITH X-RateLimit-Limit means the previous
    // 60 s tier window is still full (e.g. a rerun) — wait one window out.
    for (let warm = 0; warm < 2; warm++) {
      const p = await probePatch();
      if (p.s !== 429) break;
      await page.waitForTimeout(61_000); // BULK window = 60 s (rate_limit.py tier)
    }

    // Hammer the BULK tier from the page in ORDER, paced at 120 ms
    // (~8.3 r/s < nginx's 10 r/s, so nginx never sheds inside the loop):
    // BULK = 10 rpm + burst 2 -> the 13th call in the window denies.
    const rows = await page.evaluate(async () => {
      const out: Array<{
        s: number;
        limit: string | null;
        remaining: string | null;
        reset: string | null;
        retry: string | null;
      }> = [];
      for (let i = 0; i < 16; i++) {
        const r = await fetch('/api/events/bulk', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events: [{ id: 999_999_999, reviewed: true }] }),
        });
        out.push({
          s: r.status,
          limit: r.headers.get('x-ratelimit-limit'),
          remaining: r.headers.get('x-ratelimit-remaining'),
          reset: r.headers.get('x-ratelimit-reset'),
          retry: r.headers.get('retry-after'),
        });
        await new Promise((res) => setTimeout(res, 120));
      }
      return out;
    });
    const accepted = rows.filter((r) => r.s === 207);
    const tierDenied = rows.filter((r) => r.s === 429 && r.limit !== null);
    const nginxShed = rows.filter((r) => r.s === 429 && r.limit === null);
    expect(
      accepted.length,
      `no accepted bulk call (${JSON.stringify(rows)}) — tier window was not warm`
    ).toBeGreaterThan(0);
    expect(nginxShed, `nginx throttled the paced loop: ${JSON.stringify(rows)}`).toHaveLength(0);
    expect(tierDenied.length, `no tier denial in ${JSON.stringify(rows)}`).toBeGreaterThan(0);
    // The tier's OWN header set (rate_limit.py :531-534): total_limit =
    // 10 rpm + burst 2 = 12, remaining 0, Retry-After 60, reset inside the
    // window — and NO accepted response carries any of them, which is why
    // the "<=50% quota" progress band has no producer.
    const d = tierDenied[0];
    expect(d.limit).toBe('12');
    expect(d.remaining).toBe('0');
    expect(d.retry).toBe('60');
    expect(Number(d.reset)).toBeGreaterThan(Math.floor(Date.now() / 1000) + 30);
    expect(accepted.every((r) => r.limit === null)).toBe(true);

    // And the mounted indicators stayed DARK the whole time: these 429s
    // never rode fetchApi, so neither store feed fired. The row's honest
    // shape — the countdown surface exists and works (test 2), but as
    // shipped only the frontend's OWN throttle 429 can ever light it.
    await expect(page.getByTestId('rate-limit-indicator')).toHaveCount(0);
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
