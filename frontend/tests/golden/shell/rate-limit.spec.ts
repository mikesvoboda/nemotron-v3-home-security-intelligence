/**
 * FE-1 golden path (F2.3, then [r132] ruling 132): the rate-limit RETRYING PILL.
 *
 * ROW (F-022) as it now reads after ruling 132's split — "the retrying pill is
 * kept; the countdown overlay and its invented defaults retire":
 *   - KEPT: RetryingIndicator (data-testid="retrying-indicator", text
 *     "Retrying request..."), which renders only when the store says
 *     isLimited AND react-query has work in flight.
 *   - RETIRED (this PR deletes them): common/RateLimitIndicator.tsx (the
 *     "Rate Limited / Retry in M:SS" overlay + the <=50% quota bar + the
 *     "API quota running low" toast), useRateLimitCountdown, and
 *     updateRateLimitStoreFromError with DEFAULT_RATE_LIMIT_RETRY_SECONDS —
 *     the fabricated limit=100 / remaining=0 / reset=now+60 window that
 *     QueryCache/MutationCache onError used to write on ANY ApiError 429.
 *
 * WHAT THE STORE CAN NOW BE FED BY, post-deletion — exactly one writer:
 * api.ts handleResponse -> extractRateLimitInfo -> update(). And that writer
 * is gated on ALL THREE X-RateLimit-{Limit,Remaining,Reset} headers
 * (api.ts:1060-1061 returns null otherwise; handleResponse:1203-1206 checks
 * the null before calling update()). Consequences, each pinned below:
 *   1. The frontend nginx throttle (`limit_req zone=api burst=20 nodelay`,
 *      limit_req_status 429 — docker-entrypoint.sh:166-169) emits NO
 *      X-RateLimit-* at all, so the throttle that used to light the overlay
 *      through the invented defaults now feeds NOTHING. That is the point of
 *      the retirement, and test 2 is its leg.
 *   2. The FastAPI tier's 429 DOES carry the full header set
 *      (backend/api/middleware/rate_limit.py:531-534) and one shipped control
 *      does ride fetchApi on a tiered route: /operations mounts
 *      WebSocketHealthPanel OPEN BY DEFAULT (useSystemPageSections.ts:74, a
 *      defaults-map entry, not a user toggle), which fetches in a mount effect
 *      (WebSocketHealthPanel.tsx:190 -> :170 -> api.ts:2165) at
 *      GET /api/system/health/websocket — a tiered route
 *      (system.py:1626, RateLimitTier.DEFAULT). So a header-complete 429 IS
 *      producible from the UI; what it is NOT is aimable. The golden UI sits
 *      behind the same nginx $binary_remote_addr bucket as everything else
 *      (@10r/s, BURST MATH below), so the traffic that lights the panel's own
 *      error branch arrives nginx-shed and header-less first, and the panel
 *      fetches on mount — once, before any click can aim it — while the DEFAULT
 *      tier's own per-minute budget is far above what one page's mount fetches
 *      spend. The other fetchApi-wired tier controls are dead or gated outright:
 *      useBulkDetectionMutations has ZERO importers; PromptPlayground's
 *      testPrompt (the one AI_INFERENCE-tier control) renders only when
 *      stats.audited_events > 0 (components/ai/AIAuditPage.tsx:195, gate :349)
 *      and these stacks seed 0; EventTimeline's bulk path loops per-id
 *      UN-tiered PATCHes; ExportButton uses raw fetch. Test 3 pins the header
 *      math and the raw-fetch bypass live.
 *
 * WHY F-022 IS STILL half-built AND NOT flipped: the pill's POSITIVE leg (lit
 * while limited) needs isLimited=true, and per 1 + 2 no shipped control on this
 * tier can be MADE to set it on demand — the panel above can 429, but not at a
 * moment a spec chooses. So the pill is exercised in the component tier only
 * (RetryingIndicator.test.tsx, 12 cases) — which rulings 114/128 do not accept
 * as a publishable flip. What this file CAN publish is the NEGATIVE leg: real
 * throttled 429s riding fetchApi, and the retired surface provably absent. A
 * reachability change that would make the positive leg golden is a backend/UI
 * change outside frontend/ (ruling 87), filed as an owner question on the PR
 * rather than graded into existence here.
 *
 * HISTORY, so the deletions below read as intent and not as drift: this file
 * previously carried a shed leg asserting "Rate Limited / Retry in 1:0X", the
 * aria tick 0:53 -> 0:50, and the 0-of-100 toast. Owner ruling 125 quarantined
 * that leg as test.fixme (expiry 2026-10-14T00:00Z) after CI head 68a6856dc
 * measured "countdown frozen at 0:59 / 0:59" across 2.3 s on three attempts
 * (junit, run 38146684985) — every fresh 429 re-seeded reset=now+60, so a
 * sample taken mid-drip could legitimately show the label jump back up. This
 * PR does not re-enable that leg; it DELETES it, along with the code it
 * asserted, and its replacement asserts the opposite surface. The flood's
 * bucket calibration is inherited from it verbatim (see BURST/DRIP_MS below).
 *
 * THE BUCKET MATH the flood respects (nginx ngx_http_limit_req @10r/s: each
 * request costs 100 ms of excess, burst=20 nodelay): a 60-request burst parks
 * stored excess AT the ceiling (rejections add nothing back — probes 9/10
 * measured a single burst draining in ~2 s, too short to click inside); a drip
 * every 80 ms (12.5 r/s > the 10 r/s refill) pins excess >= burst for the
 * drip's whole span, making a click inside it a deterministic 429. Measured
 * 2026-10-11 probes 10/12 on the live stack: POST 429 (Server: nginx, no
 * X-RateLimit-*, no Retry-After).
 *
 * INSTRUMENT CHOICES, each measured against a failed alternative:
 * - Flood rides context.request (Node-side): the probes' ONE in-main-page
 *   fetch storm (929 fetches) crushed the renderer until no click could run
 *   (probe7), and a drip inside a NON-active page would hit Chromium's
 *   hidden-page timer throttling (~1/s) and clump instead of pinning.
 *   context.request hits the same nginx $binary_remote_addr bucket for free.
 * - Clicks go through el.click() inside page.evaluate after an
 *   enabled-button waitForFunction: with the bucket dirty the panel's query
 *   churn made Playwright actionability retries drift past the drip boundary
 *   (probe10/11 measured 3 s timeouts on an enabled+visible button, probe12's
 *   DOM dump proved dis:false vis:true); the trusted click on the SAME button
 *   React listens to lands the shed every run.
 * - The level button is the control because a MUTATION never retries 429
 *   (utils shouldRetryMutation covers timeouts only) so the shed POST is
 *   FINAL and rides handleResponse — queries, by contrast, DO retry 429
 *   (RETRYABLE_HTTP_STATUS_CODES, utils/error-handling.ts:588) and their ~1 s
 *   backoff usually lands after the bucket drains.
 * - Shed honesty: run to run, either click (or the panel's own refetch wave)
 *   can be the request the error feed sees (probe11 measured a 429 POST list
 *   of [200] while a query final error still lit the old store). So the spec
 *   asserts the posts list contains at least one 429 and otherwise asserts
 *   ONLY store-visible outcomes.
 *
 * SIDE EFFECTS owned by this file: the clicked control is the Operations
 * page's Log Level panel (SystemMonitoringPage.tsx:751 -> POST
 * /api/debug/log-level via useSetLogLevelMutation). A shed POST cannot change
 * the level; an unsent one can, so the level is restored before the spec
 * ends, over h.api DIRECT (the backend's published port — no nginx throttle
 * there, same leg harness.adminSession/api ride; WARNING is the stack
 * default, so the restore is idempotent even if the read failed). The flood
 * (~105 /api requests) is the golden project's one deliberate throttle
 * consumer — serial golden worker (playwright.config.ts:287-288),
 * BOOT_QUIET_MS drain before every navigation AND before the reload; test 3
 * warms the bucket and then paces its PATCH loop at 120 ms (~8.3 r/s < 10 r/s)
 * so nginx never sheds inside the tier measurement.
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
const DRIPS = 45; // ~3.5 s of pinned window; both clicks land inside it

/**
 * Copy that ONLY the retired overlay produced. Deliberately narrow: it must
 * NOT match 'Rate limit exceeded. Please try again later.'
 * (utils/error-handling.ts:349-352, ErrorCode.RATE_LIMIT_EXCEEDED) — that
 * toast is the error mapper's own copy and ruling 132 does not retire it, so
 * a shed mutation error surfacing it is CORRECT behaviour, not a failure.
 * A match here means a countdown/quota surface came back.
 */
const RETIRED_SURFACE = /rate limited|retry in \d|requests? remaining|quota running low/i;

/**
 * Whole-document scan for the retired surface: visible text AND any aria-label,
 * so a re-introduction under a NEW testid is still caught. A toHaveCount(0) on
 * the deleted data-testid alone would be vacuous-by-construction (nothing in
 * src/ emits it any more) — it stays below only as a reintroduction tripwire,
 * and this scan is the assertion that actually has reach.
 */
async function retiredSurface(page: import('@playwright/test').Page): Promise<string> {
  return page.evaluate(() => {
    const text = document.body.innerText ?? '';
    const labelled = [...document.querySelectorAll('[aria-label]')]
      .map((n) => (n as HTMLElement).getAttribute('aria-label') ?? '')
      .join('\n');
    return `${text}\n${labelled}`;
  });
}

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

/**
 * rAF trace of pill presence over `windowMs`. The pill was ~650 ms wide when
 * the store could light it (probe12's trace) — too narrow to await with a
 * locator — so presence is SAMPLED per frame and only transitions recorded.
 */
function pillTrace(page: import('@playwright/test').Page, windowMs: number) {
  return page
    .evaluate(
      ([ms]) =>
        new Promise<Array<{ k: string; atMs: number }>>((res) => {
          const t0 = performance.now();
          const out: Array<{ k: string; atMs: number }> = [];
          let last = '';
          const tick = () => {
            const k = document.querySelector('[data-testid="retrying-indicator"]') ? 'P' : '-';
            if (k !== last) {
              out.push({ k, atMs: Math.round(performance.now() - t0) });
              last = k;
            }
            if (performance.now() - t0 < ms) requestAnimationFrame(tick);
            else res(out);
          };
          requestAnimationFrame(tick);
        }),
      [windowMs]
    )
    .catch((e) => {
      // Navigation would destroy the context; the leg never navigates inside
      // the window — fail LOUD rather than lose the evidence.
      throw new Error(`pill tracer died: ${String(e).slice(0, 120)}`);
    });
}

test.describe('golden path: rate-limit pill @critical', () => {
  test('F-022 (calm): a healthy stack renders no pill and no rate-limit surface', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(90_000);
    await openOperations(page, h);
    // The pill's own gate (isLimited AND in-flight) renders NULL on a quiet
    // store — the lit case needs this baseline, and the retired overlay must
    // be absent from the whole document, not just from its old testid.
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);
    expect(await retiredSurface(page)).not.toMatch(RETIRED_SURFACE);
    // Tripwire, not proof: nothing in src/ emits this testid any more, so a
    // pass here is only meaningful if the id comes back under new code.
    await expect(page.getByTestId('rate-limit-indicator')).toHaveCount(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-022 (post-retirement): a real fetchApi-routed 429 lights NOTHING — the overlay is gone and a header-less shed cannot feed the store', async ({
    context,
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(120_000); // flood + clicks + reload + restore; measured ~30 s pre-retirement

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

    const trace = pillTrace(page, 10_000);

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

    // THE WITNESS LEG — the throttle really fired, and this time it rode
    // fetchApi (a mutation, which never retries a 429, so the denial is FINAL
    // and reaches handleResponse). Pre-retirement this exact status was what
    // updateRateLimitStoreFromError turned into limit=100/remaining=0/reset+60.
    await expect
      .poll(() => posts.includes(429), {
        timeout: 5_000,
        message: `no POST was shed (statuses ${JSON.stringify(posts)}; burst codes ${burstCodes.join(',')})`,
      })
      .toBe(true);

    // THE NEGATIVE LEG — and it must stay negative for the whole flood tail.
    await Promise.all(drips);
    const frames = await trace;
    expect(
      frames.some((f) => f.k === 'P'),
      `the pill lit without a header-fed store: ${JSON.stringify(frames)}`
    ).toBe(false);
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);
    expect(await retiredSurface(page)).not.toMatch(RETIRED_SURFACE);
    // Tripwire for the retired testid (see the calm leg for why this is not
    // the load-bearing assertion).
    await expect(page.getByTestId('rate-limit-indicator')).toHaveCount(0);

    // Reload: the store is per-document JS state (NOT the persisted query
    // cache), so nothing here can survive navigation — and the shed never
    // bounced the app to /setup. Drain first (a reload IS a boot wave).
    await Promise.allSettled(drips);
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);
    expect(await retiredSurface(page)).not.toMatch(RETIRED_SURFACE);
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

  test('F-022 (bypass): the FastAPI tier 429 is real and header-complete, yet nothing mounts — the tier is reached only by raw fetch, which never feeds the store', async ({
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
    // window — and NO accepted response carries any of them, which is why the
    // retired overlay's "<=50% quota" progress band never had a producer.
    const d = tierDenied[0];
    expect(d.limit).toBe('12');
    expect(d.remaining).toBe('0');
    expect(d.retry).toBe('60');
    expect(Number(d.reset)).toBeGreaterThan(Math.floor(Date.now() / 1000) + 30);
    expect(accepted.every((r) => r.limit === null)).toBe(true);

    // And nothing mounted the whole time: these 429s never rode fetchApi, so
    // the one surviving store feed never saw them. Post-retirement this leg
    // carries a SECOND truth — even a tier denial that DID ride fetchApi could
    // now only set isLimited (pill), because the surface that displayed the
    // reset window no longer exists.
    await expect(page.getByTestId('retrying-indicator')).toHaveCount(0);
    expect(await retiredSurface(page)).not.toMatch(RETIRED_SURFACE);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
