/**
 * FE-1 golden path (F2.3, then [r132] ruling 132): the rate-limit RETRYING PILL.
 *
 * ROW (F-022) as it now reads after ruling 132's split — "the retrying pill is
 * kept; the countdown overlay and its invented defaults retire":
 *   - KEPT: RetryingIndicator (data-testid="retrying-indicator", text
 *     "Rate limited, retrying…"), which renders only when the store says
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
 * (RetryingIndicator.test.tsx, 13 cases) — which rulings 114/128 do not accept
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
 * THE BUCKET MATH the flood respects, CORRECTED at this head (nginx
 * ngx_http_limit_req @10r/s, burst=20 nodelay; excess is kept in ms of work):
 * each request adds 1000 and time decays it at 10/ms; a request whose updated
 * excess would exceed 20000 is REJECTED — and a rejection does NOT store the
 * new excess or the new timestamp. Decay therefore keeps accruing from the
 * last ACCEPTED request, so a hard-pushed bucket does not sit frozen above the
 * ceiling: it free-runs as a METRONOME, admitting ~1 request per 1000/rate =
 * 100 ms no matter how hard the flood pushes. A 60-request burst parks it there
 * in milliseconds; a drip every 80 ms (12.5 r/s > the 10 r/s refill) keeps it
 * there for the drip's whole span.
 *
 * That single fact is why this leg was red on CI and why it is green here. The
 * pre-fix instrument waited a blind 900 ms and clicked, i.e. it clicked at a
 * RANDOM PHASE of a 100 ms metronome: shed with probability 1 - delta/100ms,
 * which is a coin flip, not a deterministic 429 as the old comment claimed. Run
 * 38477914966 proved it from nginx's own lines — five shed /api/debug/log-level
 * requests spread over 3.06 s (~1 per 612 ms), each logged at excess ~= 20.5, a
 * hair over the ceiling, and attempt 0 admitted BOTH clicks (POST 200 119, POST
 * 200 122) while shedding the panel's own refetch GETs 14 ms later.
 *
 * WITNESS-FIRST, which is what run 38708268611 (CI, #7156's leg, three
 * attempts) paid for. The fix above shipped as "probe until a request is
 * ACCEPTED and click in the same JS turn", and its own 15/15-shed measurement
 * was TRUE — on a saturated live stack. CI was not saturated: the leg's burst
 * parked excess at ~20.02-20.26 (nginx logged 147 `limiting requests` lines in
 * that band), then the flood's own scheduling left a 969 ms gap before the drip
 * began, which at 10 r/s decayed the pin, and the drip re-pinned only partway —
 * first shed at D31, 2.47 s in, with 41 of 45 drips ADMITTED. The armed click
 * fired 0.42 s into that drip: probe 200, click 13 ms later, POST 200. nginx
 * never once logged the POST as a 429 on any attempt, which is exactly the
 * `statuses [200]` in the failure text. The 15/15 was not wrong; it was
 * measuring a state the runner was not in. An instrument whose premise is about
 * a SHARED, externally-loaded resource has to prove that premise at run time
 * instead of inheriting it from wherever it was last measured.
 *
 * So the aim is now two stages, and only the first is new: (1) keep probing
 * until a probe is SHED — a 429 is the observation that the bucket is pinned
 * NOW; (2) only then take the next ADMITTED probe and click in the same turn.
 * Stage 2's window is the old, sound one — an admit leaves stored excess at or
 * just under the ceiling and the following stretch is closed *while the pin
 * holds* — and stage 1 is what makes "while the pin holds" a witnessed fact
 * rather than a hope. The stretch is ~37-100 ms, not a flat 100: see the
 * E > 19370 bound in armedShedClick (E = 20000 exactly under unlimited
 * demand, which is where the 100 ms metronome figure comes from). Arming
 * on the 429 itself is the near-miss to avoid: rejections store nothing, so a
 * shed reveals only the computed excess at its arrival — 20.02-20.26 in this
 * run, i.e. a 2-26 ms window, not 100 ms. If no shed ever appears the helper
 * returns THAT reason rather than clicking; the leg then goes red with the true
 * diagnosis (flood did not pin the bucket) instead of a downstream "no POST was
 * shed" that reads like a product regression.
 *
 * INSTRUMENT CHOICES, each measured against a failed alternative:
 * - Flood rides context.request (Node-side): the probes' ONE in-main-page
 *   fetch storm (929 fetches) crushed the renderer until no click could run
 *   (probe7), and a drip inside a NON-active page would hit Chromium's
 *   hidden-page timer throttling (~1/s) and clump instead of pinning.
 *   context.request hits the same nginx $binary_remote_addr bucket for free.
 * - The shed itself is produced by armedShedClick, not by a blind wait — see
 *   the BUCKET MATH block. The click stays el.click() inside page.evaluate on
 *   the SAME button React listens to (probe10/11/12: Playwright actionability
 *   retries drifted past the drip boundary on an enabled+visible button), just
 *   with the click aimed at the bucket's tick instead of at the clock.
 * - The level button is the control because a MUTATION never retries 429
 *   (utils shouldRetryMutation covers timeouts only) so the shed POST is
 *   FINAL and rides handleResponse — queries, by contrast, DO retry 429
 *   (RETRYABLE_HTTP_STATUS_CODES, utils/error-handling.ts:588) and their ~1 s
 *   backoff usually lands after the bucket drains.
 * - ONE shed is the experiment, so the leg aims one click, not two. The panel
 *   gates every level button on disabled={isPending || isActive}
 *   (LogLevelPanel.tsx:123) with isActive = level === currentLevel, so a
 *   SUCCESSFUL click makes that button disabled forever: the old second
 *   clickLevel('DEBUG') could only time out, which is exactly where attempts 1
 *   and 2 died (waitForFunction at :245). The armed click auto-picks an
 *   ENABLED level so a rare admitted click still cannot deadlock the leg; the
 *   level is restored at the end either way.
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
 * so nginx never sheds inside the tier measurement. Test 3 leaves the shared
 * BULK-tier window (12/60 s, client-IP keyed — one serial worker) full and
 * then WAITS IT OUT before the file ends (one confirming probe, bucket
 * parked at 1/12): every other bulk consumer in the corpus paces itself
 * around that tier (export-modal's spacing helper), so the file that fills
 * the bucket is the one that empties it. Measured cost ~62 s on shard 1
 * (run 39476467175's witness: download-media's seed 429ed 42.6 s after this
 * file's hammer when the two were newly co-sharded).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
  apiShell as api,
  closedByGuard,
  loginAsAdminShell as loginAsAdmin,
  readShellHarness,
  seedTourDismissed,
  type Session,
  type ShellHarness,
} from '../harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** nginx /api throttle geometry (docker-entrypoint.sh:166-169; nginx.conf zones). */
const BURST = 60; // >> burst=20 -> parks the bucket above the ceiling in ms
const DRIP_MS = 80; // 12.5 req/s > the 10 r/s refill -> the metronome never stops
const DRIPS = 45; // ~3.5 s of pinned window; the armed click lands inside it
/** Arm probes wait this long between tries; < the 100 ms admit tick, so the
 *  leg's own traffic keeps the bucket pinned while the hunt runs — the hunt
 *  needs TWO findings in order: a shed (the pin witness), then an admit
 *  (the moment that opens the window). */
const ARM_PROBE_MS = 60;
const ARM_TRIES = 25; // ~2.5 s of hunting = 25 admit ticks; far above need

/**
 * Copy that ONLY the retired overlay produced. Deliberately narrow: it must
 * NOT match 'Rate limit exceeded. Please try again later.'
 * (utils/error-handling.ts:349-352, ErrorCode.RATE_LIMIT_EXCEEDED) — that
 * toast is the error mapper's own copy and ruling 132 does not retire it, so
 * a shed mutation error surfacing it is CORRECT behaviour, not a failure.
 * A match here means a countdown/quota surface came back.
 *
 * ONE KNOWN HOLE, named rather than hidden: `retry in \d` cannot match
 * 'Retrying in 0:59' — two words where the pattern expects one — and that is
 * the copy components/RetryIndicator.tsx:136 renders (data-testid
 * "retry-indicator", countdown at :138). Ruling 132 does not retire that
 * component and this PR does not touch it; it is imported by NOTHING (grep:
 * its own file plus a comment at hooks/useRetry.ts:112), so it cannot render
 * and the hole is unreachable today. If anything ever mounts it, this scan
 * will NOT see it — that is the moment the pattern needs widening, and it is
 * why the hole is written here instead of left to the next reader.
 *
 * THE PILL EXEMPTION below arrived with ruling 155's rename, so it is stated
 * rather than slipped in: the KEPT pill now reads 'Rate limited, retrying…'
 * (ruling 155 item 1), and a bare `rate limited` would match the one component
 * this package KEEPS — a leg that ever lights the pill could then never go
 * green. The lookahead is the owner's EXACT string, not a shape: a 'rate
 * limited' is skipped only when ', retrying…' follows it immediately, so a
 * reworded surface ('Rate limited — retrying in 0:53', 'Rate limited. Retry in
 * 0:53') still matches, as does every retired copy the overlay produced
 * ('Retry in 0:53' via `retry in \d`, '…requests remaining', 'API quota
 * running low'). THE EXEMPTION'S REAL SCOPE, stated exactly because a prefix
 * test is easy to over-read: a lookahead tests what FOLLOWS 'rate limited', so
 * this skips every string that BEGINS with the pill's ruled copy, not one
 * string. 'Rate limited, retrying… 0:53' — the pill plus a leaked countdown —
 * passes unmarked. That append is the ONLY shape the exemption uniquely costs,
 * and it is NOT why digits are invisible to this scan: `retry in \d` misses
 * 'Retrying in 0:59' with no exemption involved, and a bare `60s`, '12 of 100'
 * or a wall clock match no branch either. The scan is TEXT-SHAPE-BOUNDED, so the
 * 'ONE KNOWN HOLE' above and this exemption are two separate limits and neither
 * is the other's excuse. A digit that reaches the pill itself is caught one
 * tier down, at RetryingIndicator.test.tsx:183 — a non-vacuous net, because that
 * fixture feeds the store limit=100 / remaining=0 / reset=+60. Named
 * rather than widened, because both widenings that would close it measured
 * worse than the hole: appending `$` to the lookahead reddens the KEPT pill
 * whenever its text is not alone on a line, and "alone on a line" is a
 * property of innerText's inline/block shape rather than of the pill's own
 * copy, so it goes false silently the day someone adds a sibling; a bare
 * `\d{1,2}:\d{2}` alternative loses the two retired copies that carry no
 * digits ('…requests remaining', 'API quota running low') and matches page
 * chrome the moment a panel that renders 'Last updated: 2:31:45 AM' (e.g.
 * WebSocketHealthPanel.tsx:321) is mounted on a scanned page. Measured, not
 * argued, over a 12-string probe: the exemption differs from the pre-ruling-155
 * pattern on THREE strings — the pill itself and two strings that begin with
 * it — and loses no retired-copy match (the narrower `(?![^a-z0-9]*retry)` was
 * tried first and REJECTED — it also silenced the reworded-overlay case above).
 */
const RETIRED_SURFACE =
  /rate limited(?!, retrying…)|retry in \d|requests? remaining|quota running low/i;

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

/**
 * Witness the nginx bucket PINNED, then click a level button IN THE SAME JS
 * TURN as the next admitted probe.
 *
 * Two stages, and the first one is load-bearing. Stage 1: keep probing until a
 * probe is SHED (429). A shed is the only observation that says "excess is
 * above the ceiling RIGHT NOW" — see the WITNESS-FIRST block in the header.
 * Stage 2: from then on, the first probe that is ADMITTED (200) opens the
 * window the click hides inside, and stage 1 BOUNDS that window numerically
 * rather than rhetorically. Units: nginx keeps excess in thousandths of a
 * request (logged as excess: 20.260 = 20260), so at 10 r/s one request costs
 * 1000 and decay is 10/ms, and burst=20 puts the ceiling at 20000. A shed at t1
 * reveals a COMPUTED excess over the ceiling, and because a rejection stores
 * nothing, the decayed level D(t) keeps falling from the last ACCEPT — so the
 * shed says D(t1) > 19000. The next admit stores E = D(t2)+1000, and the loop
 * makes successive probe STARTS exactly probeMs = 60 ms apart (the wait is
 * computed from the previous round-trip), so arrivals differ by 60 ms plus the
 * one-way transit delta — ~1 ms each on loopback, call it 63 generously — and
 * E = D(t1) - 10·gap + 1000 > 20000 - 630 = 19370. A click d ms after that
 * admit sheds while E - 10·d + 1000 > 20000, i.e. d < (E-19000)/10 >= ~37 ms,
 * against a d measured at 0.0-0.2 ms — a ~185x margin, every term arithmetic.
 * Under unlimited demand the sample lands on the tick, E -> 20000, and the
 * window is the full 100 ms the metronome figure comes from.
 *
 * Why not arm on the 429 itself, which looks equivalent: a rejection stores
 * nothing (the BUCKET MATH block), so it reveals only the COMPUTED excess X at
 * its arrival, and a click δ ms later sheds only while X - 0.01·δ > 20 (in ms
 * units: X - 10·δ > 20000). Run 38708268611's logged X was 20.02-20.26 — a 2
 * to 26 ms window, too thin to gate on. The admit is the provable moment; the
 * shed only proves the STATE that makes the admit's window real.
 *
 * The probe rides in-page fetch so it shares the bucket AND the event-loop
 * turn we then click in. The target is any ENABLED level button rather than a
 * named one: the panel gates buttons on disabled={isPending||isActive}
 * (LogLevelPanel.tsx:123), so naming a level deadlocks the leg if the click
 * happens to be admitted (the named level becomes active, hence disabled).
 * Returns the aim's anatomy (shedProbes = sheds witnessed before arming) or a
 * named skip reason — a hunt that never saw a 429 reports THAT, instead of
 * clicking into an open bucket and going red downstream.
 */
async function armedShedClick(page: import('@playwright/test').Page): Promise<{
  level: string | null;
  msSinceAdmit: number | null;
  shedProbes: number | null;
  tries: number | null;
  skipped: string | null;
}> {
  return page.evaluate(
    async ({ probeMs, tries }) => {
      const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
      const pick = () =>
        [...document.querySelectorAll('button')].find(
          (b) => LEVELS.includes(b.textContent?.trim() ?? '') && !b.disabled
        );
      const target = pick();
      if (!target)
        return {
          level: null,
          msSinceAdmit: null,
          shedProbes: null,
          tries: null,
          skipped: 'no enabled level button',
        };
      const level = target.textContent?.trim() ?? '';
      let shedProbes = 0;
      for (let a = 0; a < tries; a++) {
        const t0 = performance.now();
        const probe = await fetch(`/api/system/health?ARM=${a}`);
        if (probe.status === 429) shedProbes++; // stage 1: the pin witness
        // Arm only on an admit AFTER a shed was witnessed. A 200 on an unpinned
        // bucket is worthless — that is what run 38708268611's leg clicked into.
        if (probe.status !== 200 || shedProbes === 0) {
          const wait = probeMs - (performance.now() - t0);
          if (wait > 0) await new Promise((r) => setTimeout(r, wait));
          continue;
        }
        const admitAt = performance.now();
        const btn = pick();
        if (!btn || btn.textContent?.trim() !== level)
          return {
            level,
            msSinceAdmit: null,
            shedProbes,
            tries: a,
            skipped: 'target button vanished',
          };
        const clickAt = performance.now();
        btn.click(); // React's own handler -> fetchApi -> POST, same turn
        return {
          level,
          msSinceAdmit: +(clickAt - admitAt).toFixed(1),
          shedProbes,
          tries: a,
          skipped: null,
        };
      }
      return {
        level,
        msSinceAdmit: null,
        shedProbes,
        tries,
        skipped:
          shedProbes === 0
            ? 'bucket never pinned — no probe 429 inside the hunt budget'
            : 'no admitted probe after the pin was witnessed',
      };
    },
    { probeMs: ARM_PROBE_MS, tries: ARM_TRIES }
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
    //
    // SCHEDULING ORDER IS THE FLOOD, not a detail. The 60 GETs are in flight
    // the moment the map runs, so the burst is fired before anything is
    // awaited; the drip timers must be armed in the SAME tick. Awaiting the
    // burst first — which this leg used to do — starts the drip clocks ~1.0 s
    // late (the ~20 admitted /health responses are backend-slow and keep
    // Promise.all waiting), and run 38708268611 measured exactly that: a 969 ms
    // gap that decayed the parked pin before D0, a drip that then had to re-pin
    // from scratch (first shed at D31, 41 of 45 admitted), and an aim that
    // clicked into an open bucket. A gap here is not slack, it is the premise
    // dissolving.
    // burstCodes is written IN PLACE by each settling request, so the failure
    // strings below can read it synchronously — binding it through `await` is
    // precisely the gate that must not come back (a 0 means "still in flight",
    // which is itself the diagnosis when the aim could not arm).
    const burstCodes = new Array<number>(BURST).fill(0);
    const burstPending = Promise.all(
      Array.from({ length: BURST }, (_, i) =>
        context.request
          .get(`${h.ui}/api/system/health?F${i}`)
          .then((r) => r.status())
          .catch(() => -1)
          .then((s) => {
            burstCodes[i] = s;
            return s;
          })
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

    // ONE aim, not two. While the bucket is pinned it is a 100 ms metronome
    // (BUCKET MATH), so timing this click off the clock was a coin flip; the
    // witness-first arm makes the shed deterministic — see armedShedClick. A
    // second click was never observable anyway: a successful first click makes
    // its own button disabled via isActive (LogLevelPanel.tsx:123), which is
    // where CI's attempts 1-2 died (waitForFunction, :245 before this head).
    await page.waitForTimeout(400); // burst still draining INTO the drip: no gap
    const aim = await armedShedClick(page);
    expect(
      aim.skipped,
      `could not arm the shed (${JSON.stringify(aim)}; burst codes ${burstCodes.join(',')})`
    ).toBeNull();

    // THE WITNESS LEG — the throttle really fired, and this time it rode
    // fetchApi (a mutation, which never retries 429 — shouldRetry is
    // `status === 0 || 5xx`, api.ts:901 — so the denial is FINAL and reaches
    // handleResponse). Pre-retirement this exact status was what
    // updateRateLimitStoreFromError turned into limit=100/remaining=0/reset+60.
    //
    // One assertion only, and it carries the diagnosis. expect.poll's message
    // is a plain string built at CALL time (types/test.d.ts:8924 — the same
    // eager-string fact that made run 38477914966 print `statuses [200]`
    // before the POST had returned), and a poll that TIMES OUT throws
    // Playwright's own generic message — so nothing may sit behind a poll
    // whose failure would skip its rich expect. A bounded wait that cannot
    // throw, then one plain matcher: its message is built at FAILURE time.
    const shedDeadline = Date.now() + 5_000;
    while (!posts.includes(429) && Date.now() < shedDeadline) {
      await page.waitForTimeout(100);
    }
    expect(
      posts.includes(429),
      `no POST was shed (statuses ${JSON.stringify(posts)}; aim ${JSON.stringify(aim)}; ` +
        `burst codes ${burstCodes.join(',')})`
    ).toBe(true);

    // THE NEGATIVE LEG — and it must stay negative for the whole flood tail.
    // The burst joins the drain here (never before the aim: awaiting it early
    // is the gap that caused run 38708268611) so no request outlives the test.
    await Promise.all([...drips, burstPending]);
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
    test.setTimeout(240_000); // warm waits + the drain's 62s rounds; pathological path ~205s (measured sum)

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

    // ══ THE PAYBACK LEG ══
    // The hammer loop filled the SHARED BULK-tier window (12/60 s, keyed by
    // client IP — and the golden project is one serial worker, so every later
    // bulk consumer on this shard shares the bucket). This file is the only
    // spec in the corpus that deliberately fills the tier; every other bulk
    // consumer paces around it (export-modal.spec.ts's spacing helper, 5 s
    // between bulk calls). Leaving the window full turned deterministic once
    // the shard manifest co-sharded this file with a consumer that seeds in
    // beforeAll: run 39476467175's shard 1 died when download-media's seed
    // POST 429ed 42.6 s after this file's hammer (the warm gates sit between
    // tests 2 and 3, so the NEXT file's first bulk call had no gate of its
    // own).
    //
    // Why the drain WAITS instead of polling: a denied probe is free (the
    // sliding-window Lua script denies without ZADD), but an accepted probe
    // is NOT — it ZADDs and re-pins the bucket at 12/12 for its own 60 s.
    // Polling into acceptance would exit the loop having re-armed the exact
    // trap it drains, and accepted responses carry no rate headers (asserted
    // above), so the bucket state is unreadable from the page. So: wait out
    // the whole window first — 62 s covers the 60 s window plus the hammer
    // burst's ~1.6 s entry spread — THEN one probe confirms the tier answers
    // (and parks the bucket at 1/12, 11 slots free). A denied confirmation
    // buys one more 62 s round; a second denial fails loud instead of
    // handing the shard a full window.
    await page.waitForTimeout(62_000);
    let drained = await probePatch();
    if (drained.s === 429) {
      await page.waitForTimeout(62_000);
      drained = await probePatch();
    }
    if (drained.s === 429) {
      throw new Error(
        `BULK tier still denying 124 s after the hammer: ${JSON.stringify(drained)} — ` +
          `the seed-side bulk consumers sharing this client-IP bucket would 429 ` +
          `in their beforeAll; refusing to hand the shard a full window`
      );
    }
  });
});
