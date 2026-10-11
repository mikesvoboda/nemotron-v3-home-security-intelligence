/**
 * Golden path: Real User Monitoring — Core Web Vitals boot → backend
 * histograms (inventory F-026).
 *
 * Row claim: "nothing visible: LCP/INP/CLS/TTFB/FCP are batched and sent to
 * the backend" | `POST /api/rum` | `ingest_rum_metrics`
 * backend/api/routes/rum.py:64 → observe_rum_* histograms
 * (backend/core/metrics.py:2495-2583) → exposed on /api/metrics.
 *
 * WHY THIS SPEC NEEDS NO INTERCEPTION AND NO MOCKING
 *   The whole chain is passive-observable. initRUM() runs at module load
 *   (src/main.tsx:23, before render) with the shipped defaults —
 *   {endpoint:'/api/rum', enabled:true, batchSize:5, flushIntervalMs:10000,
 *   maxQueueSize:50} (src/services/rum.ts:93-99) — and flush() is a plain
 *   same-origin fetch (rum.ts:210), visible to a `page.on('request')`
 *   listener. Observation is exactly what the golden guard forbids the
 *   opposite of: nothing here stubs a route (closedByGuard at the end proves
 *   the page was never intercepted).
 *
 * THE UNIQUE-PATH TRICK (why the store read is a proof, not a hope)
 *   /api/metrics on this stack is shared and monotonically growing — every
 *   past boot leaves its path label behind (791 hsi_rum_* lines when this was
 *   written, 2026-10-11, and it only ever climbs, so don't quote that figure
 *   as a current read). A `path` label this harness has never served is
 *   therefore an unattributable-by-anyone-else oracle: if
 *   hsi_rum_ttfb_seconds_count{path="/golden-f026-store-<ts>"} exists, THIS
 *   boot put it there. Both tests boot their own never-booted path so the
 *   landed series and the observed POST belong to the same test.
 *   (Unknown paths are fine: the SPA fallback serves index.html and the catch-all
 *   route renders NotFound — the document still boots, the vitals still fire.
 *   Measured: probe boot of /golden-f026-probe-<ts> produced the POST.)
 *
 * WHAT WAS MEASURED BEFORE WRITING THIS (probes on the lane stack, 2026-10-11)
 *   probe1 — headless ephemeral boot of a never-booted path, NO input, 26 s
 *     watch: exactly ONE POST /api/rum, at +10132 ms. That is the flush TIMER,
 *     not the batch: 3 metrics < batchSize 5, so reportMetric never triggers
 *     flush (rum.ts:182); the 20 s tick then no-ops because flush() returns
 *     early on an empty queue (rum.ts:191). Body carried
 *     ["PAGE_LOAD_TIME:good","TTFB:good","FCP:good"], each stamped with the
 *     boot's path, session_id absent (initRUM() is called with no config).
 *   probe2 — same no-input boot, context closed at +12062 ms, /api/metrics
 *     polled 25 s: landed families were EXACTLY probe1's three. Closing a
 *     context does not fake a hide, so neither flushWithBeacon path fires
 *     (visibilitychange:hidden rum.ts:147-151, beforeunload :142-145).
 *   probe3 — the missing ingredient is INPUT. Same boot, two Tab presses at
 *     +1.0 s and +1.3 s (visibilityState stayed "visible"), 22 s watch:
 *     STILL ONE POST, still at ~10.1 s, now carrying FOUR metrics —
 *     PAGE_LOAD_TIME, TTFB, FCP and LCP — and /api/metrics landed exactly
 *     {fcp_seconds, lcp_seconds, page_load_time_seconds, ttfb_seconds} for
 *     that path. web-vitals finalizes LCP on the first input (the live
 *     registry is the witness: hsi_rum_lcp_seconds had 6 series, every one of
 *     them from a path some other spec CLICKS ON — /login, /timeline,
 *     /operations, /settings, /settings/ambient — while a never-interacted
 *     boot produced none). So a bare boot's trio was an instrument gap, not a
 *     product break, and this spec closes the gap with a keypress.
 *     WHICH keypress is load-bearing, learned from a red run: the first
 *     four-metric version pressed Tab once, straight at domcontentloaded, and
 *     LCP was missing on BOTH legs — twice, deterministically (2 failed,
 *     EXIT=1, 2026-10-11). web-vitals mounts from an async dynamic import
 *     (rum.ts:372), so a keydown that beats it is input the library never
 *     sees. probe3's shape is what measures four: after 'load', +1 s, press,
 *     +300 ms, press — and that is what bootUntilFlush does below.
 *     The press is deliberately NON-NAVIGATING: reportMetric stamps
 *     window.location.pathname at call time (rum.ts:169-172), so clicking the
 *     404 page's link would stamp the DESTINATION path and quietly break the
 *     unique-path attribution the store leg depends on. Tab moves focus only.
 *   INP and CLS are therefore the only two asserted nowhere below, and the
 *   measured reason is probe3's own negative: with focus already moved twice,
 *     still visible, 22 s elapsed, neither appeared. INP needs an input that
 *     is followed by an actual presentational change (the catch-all NotFound
 *     page has nothing to paint in response to Tab), and CLS needs a layout
 *     shift this page never makes. Forcing either would be manufacturing an
 *     event rather than observing one — a vacuous expect (ruling 86). Their
 *   backend sides are shipped and cited (metrics.py:2523 INP, :2535 CLS) and
 *   rum.py dispatches both (:90-93).
 *
 * Throttle discipline: UI boots go through quietBoot (harness.ts — the shared
 * nginx /api burst). /api/metrics is read Node-side against the API origin,
 * the same way every other backend-state read in this lane is done, and it
 * sits on the SetupGuard whitelist so it needs no session.
 */
import type { Page, Request, Response } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  closedByGuard,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();

/** Shape of the app's own flush body (src/services/rum.ts:198-207). */
interface RumPayload {
  metrics: {
    name: string;
    value: number;
    rating: string;
    delta: number;
    id: string;
    navigationType?: string;
    path?: string;
  }[];
  session_id?: string;
}

/** Shape of ingest_rum_metrics' response (backend/api/schemas/rum.py:127-141). */
interface RumIngestResponse {
  success: boolean;
  metrics_count: number;
  message: string;
  errors: string[];
}

interface RumPost {
  body: string;
  status: number | null;
  json: RumIngestResponse | null;
}

/** The four metrics this instrument delivers: TTFB/FCP on paint,
 *  PAGE_LOAD_TIME on load, and LCP once something is typed (probe3). INP and
 *  CLS are excluded for the measured reason in the header. */
const EXPECTED_WIRE = ['PAGE_LOAD_TIME', 'TTFB', 'FCP', 'LCP'] as const;

/** Wire name → histogram family name on /api/metrics (metrics.py:2495-2574,
 *  dispatched by name in rum.py:86-99). */
const FAMILY_BY_NAME: Record<string, string> = {
  PAGE_LOAD_TIME: 'page_load_time_seconds',
  TTFB: 'ttfb_seconds',
  FCP: 'fcp_seconds',
  LCP: 'lcp_seconds',
};

/** Fresh per RUN (module scope, evaluated once at collection) so reruns never
 *  collide with their own residue; 26 chars, well inside the
 *  sanitize_metric_label(max_length=64) the backend applies. */
const RUN_MARK = Date.now();
const WIRE_PATH = `/golden-f026-wire-${RUN_MARK}`;
const STORE_PATH = `/golden-f026-store-${RUN_MARK}`;

/** Observe the app's own RUM POSTs on a page, passively. Requests and their
 *  responses are paired by Request identity so each POST keeps its own answer. */
function watchRumPosts(page: Page): RumPost[] {
  const posts: RumPost[] = [];
  const byRequest = new Map<Request, RumPost>();
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().endsWith('/api/rum')) {
      const entry: RumPost = { body: req.postData() ?? '', status: null, json: null };
      posts.push(entry);
      byRequest.set(req, entry);
    }
  });
  page.on('response', (res: Response) => {
    const entry = byRequest.get(res.request());
    if (!entry) return;
    entry.status = res.status();
    void res
      .json()
      .then((parsed: RumIngestResponse) => {
        entry.json = parsed;
      })
      .catch(() => {
        /* non-JSON answer: status is still the assertion target */
      });
  });
  return posts;
}

/** One boot, one non-navigating input, then wait for the flush timer to
 *  deliver the batch. The wait is the shipped 10000 ms flushIntervalMs plus
 *  boot time — never a fixed sleep. */
async function bootUntilFlush(page: Page, h: ShellHarness, path: string): Promise<RumPost[]> {
  const posts = watchRumPosts(page);
  await quietBoot(page, h, path);
  // web-vitals finalizes LCP on the first input, so without a press the boot
  // reports a trio and the row's headline vital never reaches the wire
  // (probe1 vs probe3, header). Two placement rules, both learned the hard
  // way on the first four-metric run (LCP missing, twice):
  //   1. AFTER 'load', not at domcontentloaded — web-vitals arrives via an
  //      async dynamic import (rum.ts:372), so a keydown that beats it is
  //      input the library never sees.
  //   2. Twice, like probe3 — one press measured four metrics with a post-
  //      load cushion; don't stake the row's headline vital on a single one.
  // Tab, never a click that navigates: reportMetric stamps
  // window.location.pathname at call time (rum.ts:169-172), so a click that
  // navigated would re-stamp the metric on the destination path and dissolve
  // this test's unique-path oracle. All of this stays well inside the 10 s
  // timer, so whatever finalizes rides the ONE batch the tests assert on.
  await page.waitForLoadState('load');
  await page.waitForTimeout(1_000);
  await page.keyboard.press('Tab');
  await page.waitForTimeout(300);
  await page.keyboard.press('Tab');
  await expect
    .poll(() => posts.length, {
      message: `no POST /api/rum within the flush window — rum.ts:132 arms flushIntervalMs=10000 at initRUM (src/main.tsx:23)`,
      timeout: 25_000,
    })
    .toBeGreaterThan(0);
  return posts;
}

/** Parse this run's own RUM histogram series out of the Prometheus text
 *  exposition, keyed by family, for ONE path label. */
function seriesForPath(
  metricsText: string,
  path: string
): Map<string, { count: number; sum: number; rating: string }> {
  const found = new Map<string, { count: number; sum: number; rating: string }>();
  for (const line of metricsText.split('\n')) {
    const m = /^hsi_rum_(.+?)_(count|sum)\{([^}]*)\}\s+(\S+)$/.exec(line);
    if (!m) continue;
    const [, family, kind, labelText, valueText] = m;
    const labels: Record<string, string> = {};
    for (const pair of labelText.matchAll(/([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"/g)) {
      labels[pair[1]] = pair[2];
    }
    if (labels.path !== path) continue;
    const slot = found.get(family) ?? { count: 0, sum: 0, rating: labels.rating ?? '' };
    slot.rating = labels.rating ?? slot.rating;
    if (kind === 'count') slot.count = Number(valueText);
    else slot.sum = Number(valueText);
    found.set(family, slot);
  }
  return found;
}

async function metricsText(api: string): Promise<string> {
  const res = await fetch(`${api}/api/metrics`);
  expect(res.status, 'GET /api/metrics must answer for the store leg').toBe(200);
  return res.text();
}

test.describe('golden path: RUM Core Web Vitals boot → backend histograms @critical', () => {
  test.setTimeout(120_000);

  test('the wire leg: a boot batches its Web Vitals into ONE POST /api/rum that the backend ingests with zero errors', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;

    await seedTourDismissed(page);
    const posts = await bootUntilFlush(page, harness, WIRE_PATH);

    // Batching is the row's own word ("are batched and sent"), and it is
    // visible in a single delivery: several metrics rode ONE request body.
    expect(posts.length, 'one flush should carry the queue, not one POST per metric').toBe(1);
    const payload = JSON.parse(posts[0].body) as RumPayload;
    expect(
      payload.session_id,
      'initRUM() is called with no config, so session_id stays absent'
    ).toBeUndefined();

    const names = payload.metrics.map((m) => m.name);
    expect(new Set(names), `measured probe carried exactly ${EXPECTED_WIRE.join('/')}`).toEqual(
      new Set<string>(EXPECTED_WIRE)
    );

    for (const metric of payload.metrics) {
      // Every metric gets the boot path stamped in reportMetric (rum.ts:169-172),
      // which is what makes the store leg attributable at all.
      expect(metric.path, `${metric.name} must be stamped with the boot path`).toBe(WIRE_PATH);
      expect(['good', 'needs-improvement', 'poor'], `${metric.name} rating`).toContain(
        metric.rating
      );
      expect(metric.value, `${metric.name} value must be a real measurement`).toBeGreaterThan(0);
    }

    // The shipped rating math for the one metric this repo computes itself
    // (getPageLoadTimeRating, rum.ts:309-313) — deterministic from the value
    // the app reported, so it pins logic rather than timing.
    const plt = payload.metrics.find((m) => m.name === 'PAGE_LOAD_TIME')!;
    const expectedRating =
      plt.value < 3000 ? 'good' : plt.value < 6000 ? 'needs-improvement' : 'poor';
    expect(plt.rating).toBe(expectedRating);

    // The backend's own answer to that exact request.
    await expect
      .poll(() => posts[0].json, { message: 'ingest response never parsed', timeout: 10_000 })
      .not.toBeNull();
    const ingest = posts[0].json!;
    expect(posts[0].status, 'ingest_rum_metrics is a plain POST handler').toBe(200);
    expect(ingest.errors, 'every name on the wire must be one rum.py dispatches').toEqual([]);
    expect(ingest.metrics_count).toBe(payload.metrics.length);
    expect(ingest.success).toBe(true);
    expect(ingest.message).toContain(`${payload.metrics.length} metric`);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the store leg: each accepted metric lands as an hsi_rum_* series on its own path, and no other family did', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    await seedTourDismissed(page);
    await bootUntilFlush(page, harness, STORE_PATH);

    // The store side, polled rather than slept at: ingest is synchronous
    // inside the request, so the series should already be there — the window
    // is headroom for the scrape-free /api/metrics render, not for a queue.
    let landed = new Map<string, { count: number; sum: number; rating: string }>();
    await expect
      .poll(
        async () => {
          landed = seriesForPath(await metricsText(h.api), STORE_PATH);
          return Object.values(FAMILY_BY_NAME).filter((f) => landed.has(f)).length;
        },
        {
          message: 'the ingested metrics must appear as hsi_rum_*_count{path=…} on /api/metrics',
          timeout: 20_000,
          intervals: [1_000],
        }
      )
      .toBe(Object.values(FAMILY_BY_NAME).length);

    for (const name of EXPECTED_WIRE) {
      const family = FAMILY_BY_NAME[name];
      const slot = landed.get(family)!;
      expect(slot.count, `${family} must have observed at least one sample`).toBeGreaterThanOrEqual(
        1
      );
      // _sum > 0 is the value making it through, not just the label:
      // observe_rum_* divides ms by 1000 before observing (metrics.py:2602).
      expect(slot.sum, `${family} must carry the converted seconds value`).toBeGreaterThan(0);
      expect(['good', 'needs-improvement', 'poor'], `${family} rating label`).toContain(
        slot.rating
      );
    }

    // Nothing phantom: for a path this harness has never served before, the
    // ONLY families that can exist are the ones an ingest for it dispatched.
    // INP and CLS are absent exactly as probe3 measured them to be.
    expect([...landed.keys()].sort(), 'no family beyond the four the boot reports').toEqual(
      Object.values(FAMILY_BY_NAME).sort()
    );

    // The second store side: every ingest also bumps a name/rating counter
    // (metrics.py:2577-2582 — labelled metric_name+rating, deliberately
    // path-free, so it cannot be attributed to one boot and is only checked
    // for a name this test just ingested).
    const counterText = (await metricsText(h.api))
      .split('\n')
      .filter((l) => l.startsWith('hsi_rum_metrics_total') && l.includes('metric_name="TTFB"'));
    expect(
      counterText.length,
      'hsi_rum_metrics_total must carry metric_name="TTFB"'
    ).toBeGreaterThan(0);
    for (const line of counterText) {
      expect(Number(line.split(/\s+/).pop()), 'the counter must be counting').toBeGreaterThan(0);
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
