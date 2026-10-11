/**
 * Golden path: Sentry error tracking — SDK shipped, loaded, INERT on every
 * shipped build (inventory F-025).
 *
 * Row claim: "nothing visible: errors and replays go to Sentry when a DSN is
 * built in" | no API calls | "(outbound to Sentry SaaS)" | inert because
 * initSentry returns early without VITE_SENTRY_DSN (src/services/sentry.ts:176-178)
 * and nothing in the repo sets it.
 *
 * WHAT A GOLDEN PATH FOR A FEATURE THAT IS SUPPOSED TO DO NOTHING LOOKS LIKE
 *   The row's own contract is a negative: with no DSN baked in at build time,
 *   the Sentry code path must cost the product NOTHING observable — no egress,
 *   no initialized client, no data leaving the origin. So the golden path
 *   proves the negative with real input: genuine uncaught errors and genuine
 *   rejections (the same setTimeout-throw technique F-024 validated), because
 *   "no Sentry requests" is only meaningful once errors demonstrably fired.
 *   The firing proof is the app's OWN ingestion POSTs (`/api/logs/frontend*`,
 *   F-024's row, zero interception) — a body carrying this test's unique marks.
 *   On top of the wire negative, the client-side state is pinned: Sentry v11
 *   materializes its global carrier (`window.__SENTRY__`) lazily, only on the
 *   init path — measured in the shipped bundle:
 *   `function mE(e){const t=e.__SENTRY__=e.__SENTRY__||{};…}` reached from the
 *   client factory — so after a boot and two real errors the carrier being
 *   `undefined` is direct evidence init never ran, not just silence.
 *
 * THE OTHER LEG: WHY INERTNESS IS BY CONSTRUCTION, NOT BY LUCK (bundle leg)
 *   The DSN is a build-time input (`import.meta.env.VITE_SENTRY_DSN`), and no
 *   compose file, Dockerfile or env example in the repo sets it (row's cite).
 *   Test 2 reads what the server ACTUALLY SHIPS: the index's entry bundles
 *   contain the Sentry SDK code (the `__SENTRY__` carrier code is in there —
 *   the module is in the graph via main.tsx's initSentry import) while
 *   containing ZERO DSN-shaped literals, ZERO `sentry.io` hosts, and zero
 *   occurrences of the env-key string itself — Vite folds an unset
 *   `import.meta.env.VITE_*` read away at build, so the gate at sentry.ts:176
 *   is a constant on every shipped build. Even the customConfig escape hatch
 *   cannot re-enable it: the early return at :176-178 happens BEFORE the
 *   `...customConfig` spread at :211, so no runtime caller can pass a DSN in.
 *
 * MEASURED BEFORE WRITING THIS (probe1 on the lane stack, 2026-10-11):
 *   authed boot of / — 81 requests (a boot-churn figure, don't quote as
 *   current), hosts seen: EXACTLY {127.0.0.1:18080}; 0 URLs matching
 *   /sentry/i. One marked uncaught error + one marked rejection fired for
 *   real: pageerror saw both, and four `/api/logs/frontend*` POSTs carried
 *   the marks. window.__SENTRY__ after all of it: ABSENT (exists=false),
 *   window.Sentry: "undefined". The served index listed
 *   ["/assets/index-<hash>.js", "/registerSW.js"]; the main bundle
 *   (~1.11 MB) matched __SENTRY__ 4× and matched sentry.io / VITE_SENTRY_DSN
 *   / a DSN-shaped `https://…@o<digits>…` literal 0× each.
 *
 * MEASURED-ABSENT CLAUSES (ruling 86 — stated, not silently skipped):
 *   1. THE DSN-ON LEG IS UNREACHABLE ON THIS STACK. Proving "errors go to
 *      Sentry when a DSN is built in" would require building the golden image
 *      with a DSN baked in — manufacturing a configuration the product has
 *      never shipped, which is a mock wearing a build flag. The row's own
 *      surface column says "when a DSN is built in"; no shipped build has one.
 *   2. THE ErrorBoundary→captureError GATE LEG IS UNIT-OWNED, AND THE BOUNDARY
 *      HAS NO INTERCEPTION-FREE TRIGGER. ErrorBoundary.test.tsx:578-610 pins
 *      the gated call (isSentryEnabled true → captureError called; false → not
 *      called) with mocks — which is the only honest place left for it,
 *      because F-024 measured that no interception-free way exists to crash
 *      the real boundary (no :param routes, try/catch-guarded storage, clean
 *      boot on corrupted zustand blobs). A golden spec here would have to
 *      manufacture the crash.
 *   3. SESSION REPLAY IS SUBSUMED BY CLAUSE 1. replayIntegration() is only
 *      ever constructed inside the Sentry.init call behind the early return
 *      (sentry.ts:200-212), so replay bytes cannot exist on any shipped build;
 *      there is nothing observable to assert beyond the wire negative below.
 *
 * Throttle discipline: the UI boot goes through quietBoot (harness.ts — the
 * shared nginx /api burst); the bundle leg is Node-side fetch against the UI
 * origin, which serves static assets without touching the API throttle.
 */
import type { Page, Request } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
} from './harness';

const harness = readShellHarness();

/** Unique per RUN: marks must not collide with their own residue on reruns. */
const RUN_MARK = Date.now();
const UNCAUGHT_MARK = `F025_UNCAUGHT_${RUN_MARK}`;
const REJECTION_MARK = `F025_REJECT_${RUN_MARK}`;

/** Requests the app made while errors were REALLY firing, captured passively. */
interface Watched {
  urls: string[];
  logPostBodies: string[];
}

function watchRequests(page: Page): Watched {
  const watched: Watched = { urls: [], logPostBodies: [] };
  page.on('request', (req: Request) => {
    watched.urls.push(req.url());
    if (req.method() === 'POST' && req.url().includes('/api/logs/')) {
      watched.logPostBodies.push(req.postData() ?? '');
    }
  });
  return watched;
}

/** Everything Sentry's wire protocol would have to touch, spelled from the
 *  SDK's own hosts (DSN form https://<key>@<id>.ingest.sentry.io/<project>). */
const SENTRY_URL = /sentry/i;
const DSN_SHAPE = /https?:\/\/[^"'`\s]*@o\d+\.[^\s"'`]*/;

test.describe('golden path: Sentry error tracking shipped-but-inert on the built stack @critical', () => {
  test.setTimeout(120_000);

  test("the wire negative: two REAL errors ride only the app's own backend POSTs — zero requests to any other origin, no Sentry URL, no Sentry client", async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    await seedTourDismissed(page);
    const watched = watchRequests(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h, '/');
    await page.waitForLoadState('load');
    // F-024's validated firing window: 1 s after load so the boot's wave has
    // drained and both global handlers are registered before anything throws.
    await page.waitForTimeout(1_000);

    // Two REAL global events (F-024's validated technique): a throw inside a
    // timer and a rejection dropped inside a timer. These are the exact
    // inputs the row says would go to Sentry if a DSN were built in.
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(String(err)));
    await page.evaluate((m) => {
      setTimeout(() => {
        throw new Error(m);
      }, 0);
    }, UNCAUGHT_MARK);
    await page.waitForTimeout(1_500);
    await page.evaluate((m) => {
      setTimeout(() => {
        void Promise.reject(new Error(m));
      }, 0);
    }, REJECTION_MARK);

    // The firing proof, before the negative can mean anything: the app's own
    // errorReporting single POSTs must carry both marks (unlike the logger
    // batch, the single endpoint POSTs each event immediately, F-024 probe3).
    await expect
      .poll(
        () => ({
          uncaught: watched.logPostBodies.some((b) => b.includes(UNCAUGHT_MARK)),
          rejection: watched.logPostBodies.some((b) => b.includes(REJECTION_MARK)),
        }),
        {
          message: 'both marks must reach /api/logs/frontend — the errors really fired',
          timeout: 15_000,
        }
      )
      .toEqual({ uncaught: true, rejection: true });
    expect(pageErrors.length, 'Playwright saw both real page errors').toBe(2);

    // The negative proper. (a) No URL this page touched mentions Sentry.
    const sentryish = watched.urls.filter((u) => SENTRY_URL.test(u));
    expect(sentryish, `no request may mention Sentry; saw ${sentryish.join(', ')}`).toEqual([]);

    // (b) Nothing left the origin at all — probe1 measured a clean boot at
    // exactly one host, so this is the product contract, not a curated
    // allowlist: the page's own telemetry choices stay on-origin.
    const uiHost = new URL(h.ui).host;
    const foreign = watched.urls.filter((u) => {
      try {
        return new URL(u).host !== uiHost;
      } catch {
        return true; // unparseable = foreign by definition
      }
    });
    expect(foreign, `every observed request stayed on ${uiHost}`).toEqual([]);

    // (c) The client itself never materialized: Sentry v11 creates the
    //    global carrier only on the init path (bundle-witness above), so an
    //    absent carrier after real errors IS the "initSentry returned early"
    //    proof (sentry.ts:176-178) — observed from the page, not from source.
    const sentryClient = await page.evaluate(() => ({
      carrier: typeof (window as unknown as Record<string, unknown>).__SENTRY__,
      global: typeof (window as unknown as Record<string, unknown>).Sentry,
    }));
    expect(sentryClient, 'no Sentry client may exist without a build-time DSN').toEqual({
      carrier: 'undefined',
      global: 'undefined',
    });

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('the shipped artifact: the entry bundles ship the Sentry SDK code with zero DSN material — no key, no sentry.io host, not even the env key (the build folded it)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    // Read exactly what the server serves to a browser — the same index the
    // UI leg rendered, then every entry script it names.
    const indexRes = await fetch(`${h.ui}/`);
    expect(indexRes.status, 'the SPA index must serve for the artifact leg').toBe(200);
    const indexHtml = await indexRes.text();
    const scripts = [...indexHtml.matchAll(/src="(\/[^"]+\.js)"/g)].map((m) => m[1]);
    expect(
      scripts.some((s) => /^\/assets\/index-[\w-]+\.js$/.test(s)),
      `index must name its hashed entry bundle; named ${JSON.stringify(scripts)}`
    ).toBe(true);

    let shipped = indexHtml;
    for (const s of scripts) {
      const res = await fetch(`${h.ui}${s}`);
      expect(res.status, `${s} must serve`).toBe(200);
      shipped += await res.text();
    }

    // The SDK IS in the shipped graph (main.tsx:7 imports initSentry, which
    // statically imports @sentry/react): the global-carrier code is present
    // even though nothing initialized it. Property-key strings survive
    // minification, so this marker is stable across builds.
    const carrierHits = (shipped.match(/__SENTRY__/g) ?? []).length;
    expect(carrierHits, 'the Sentry SDK code must be IN the shipped bundle').toBeGreaterThan(0);

    // …with zero enabling material anywhere in it. All three measured 0 in
    // probe1; together they are the row's "inert in every shipped build":
    expect((shipped.match(DSN_SHAPE) ?? []).length, 'no DSN-shaped literal may ship').toBe(0);
    expect((shipped.match(/sentry\.io/g) ?? []).length, 'no Sentry ingest host may ship').toBe(0);
    expect(
      (shipped.match(/VITE_SENTRY_DSN/g) ?? []).length,
      'the unset env read must be folded away, not left to read real config'
    ).toBe(0);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
