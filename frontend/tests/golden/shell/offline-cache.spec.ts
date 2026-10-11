/**
 * Golden path: the service worker + offline query cache on the built stack
 * (inventory F-027).
 *
 * Row claim: "nothing visible until offline: static assets and recent /api/*
 * responses (5 min, network-first) are served from cache; query results
 * persist for cold starts".
 *
 * WHY THIS SPEC CAN BE HONEST AT ALL (and what it is NOT faking)
 *   The row's whole surface is an offline partition, and Playwright's
 *   context.setOffline() is the browser's REAL network partition (Chromium
 *   NetworkStateConditions — requests genuinely fail; ws-status.spec.ts:198
 *   already leans on it to prove a real WS disconnect, and that spec still
 *   ends with the interception guard tripped). setOffline is browser-level
 *   partition, NOT one of the guard's INTERCEPTION_METHODS (guard.ts:46 lists
 *   route/unroute/routeFromHAR/routeWebSocket) — so this spec never fakes a
 *   server: it takes a real server away and watches the REAL Workbox runtime
 *   answer from REAL CacheStorage. Zero interception; the guard still throws.
 *
 *   Warm-what-you-assert doctrine: NetworkFirst only caches responses that
 *   actually pass through the activated SW, so the offline leg asserts exactly
 *   the three keys this spec warms through the controlled page — and warming
 *   /api/auth/setup-status is LOAD-BEARING, because ProtectedRoute fails
 *   closed when that call has no answer (setupRequired === null && error →
 *   Navigate to="/setup", src/components/auth/ProtectedRoute.tsx:79): an
 *   offline admin with a cold api-cache lands on "Create your admin account".
 *   The boot's own wave is NOT asserted — it races SW activation and caches
 *   unreliably (probe: api-cache ended up holding exactly the warmed keys).
 *
 * THE FOUR LEGS
 *   T1 ARTIFACT (Node-side, no page): the served /sw.js is the Workbox build
 *      vite.config.ts actually generates — the /api route tokens the row
 *      quotes are in it as compiled ("api-cache", networkTimeoutSeconds:10,
 *      maxEntries:50, maxAgeSeconds:300, NetworkFirst), skipWaiting is on,
 *      and a NavigationRoute serves index.html. The manifest's index.html
 *      entry is pinned to the ACTUAL bytes served: Workbox's revision is the
 *      md5 of file content, so the spec md5s the live index and demands the
 *      manifest agrees — content-addressed proof the precache covers the
 *      shell that ships, and it survives deploys. (The manifest is a JS
 *      literal with unquoted keys — matched by pattern, not JSON.parse.)
 *   T2 CONTROL: after a real login boot, the SW is controlling the scope with
 *      active=activated and waiting/installing null — autoUpdate+skipWaiting
 *      (vite.config.ts:60/:132) means an update can never park a waiting
 *      worker, so that null-ness is a real observable of the shipped config.
 *   T3 OFFLINE ROUND TRIP: warm → poll api-cache → setOffline(true) → reload.
 *      The document and every /assets shell file come back 200 with
 *      fromServiceWorker()=true (probe: 44/44 responses, identical 3×3 runs);
 *      one behavioral snapshot proves the app BOOTS offline (title, path '/'
 *      — no fail-close) and, in the SAME snapshot, an UNWARMED endpoint
 *      throws TypeError: Failed to fetch — the control pair that kills both
 *      "setOffline is CDP decoration" and "NetworkFirst just waited out its
 *      10 s timeout" readings: a cached hit answers instantly while an
 *      uncached miss on the same page dies. Then setOffline(false): recovery.
 *   T4 the same snapshot + reload pair carries the TanStack persistence
 *      record: localStorage 'security-dashboard-cache' (queryPersistence.ts:36,
 *      throttled 1 s at :119) survives the offline reload with the cameras
 *      query still recorded — the row's "query results persist" leg.
 *
 * MEASURED BEFORE WRITING THIS (f027-probe2.mjs on the lane stack, 2026-10-11,
 *   3 fresh contexts, shape-identical): registration claim 1.5–2.0 s,
 *   scope http://127.0.0.1:18080/, active activated, waiting/installing null;
 *   all three warm keys 200; api-cache all-match poll 3–4 ms after warm;
 *   precache 180 entries with the index stored under the REVISIONED key
 *   /index.html?__WB_REVISION__=… — bare caches.match('/index.html') MISSES
 *   (that's why T3 probes stored keys via a keys() scan, never a bare match);
 *   offline reload 53–55 ms, 44/44 shell responses SW-served 200 — of which
 *   exactly 3 (document + entry JS + entry CSS) have landed at the 'load'
 *   event and the rest are the dashboard's lazy chunks ~1.5 s later (first
 *   run of this spec caught that timing); snapshot
 *   identical 3/3: path '/', onLine false, title "Security Dashboard", the
 *   three cached keys 200, the unwarmed /api/events control TypeError; the
 *   persistence record survived with ["cameras","list"]; recovery live fetch
 *   200 online again. Served /sw.js today: 11,929 bytes, and the index's
 *   md5 equals its manifest revision (both db9933ec… at probe time).
 *
 * MEASURED-ABSENT CLAUSES (ruling 86 — stated, not silently skipped):
 *   X1 FULL OFFLINE DOM FIDELITY. The offline-booted dashboard is visibly
 *      thin (bodyLen 731 online-vs-1594): with cameras=[] the GPU tiles and
 *      "System degraded" chrome do not render, and the row's "nothing visible
 *      until offline" cannot be scored on-screen — hydrated-on-screen data
 *      behind an offline partition is structurally unobservable here (the
 *      live queries refetch to empty offline; seeding on-screen rows would
 *      need interception). The cache + record legs carry the claim instead.
 *   X2 THE 5-MINUTE EXPIRY AND THE ONLINE NETWORK-FIRST PREFERENCE are
 *      runtime Timers inside Workbox (maxAgeSeconds:300 cache expiry; online
 *      refresh bypass) — unwaitable in bounded time, and a 10 s-timeout
 *      fallback is ambiguous with a slow network. T1 pins the NUMBERS from
 *      the served artifact (300/10/50); behavior past them is Workbox's own
 *      tested surface, not this app's.
 *   X3 UPDATE/OFFLINE-READY UX MEASURED ABSENT BY CONSTRUCTION: no
 *      onNeedRefresh/onOfflineReady/virtual:pwa-register exists anywhere in
 *      src/ (ruling 86: no affordance to assert), and autoUpdate+skipWaiting
 *      leaves waiting===null always — T2 asserts that null instead.
 *   X4 CROSS-PROFILE COLD START (fresh browser profile replaying a previous
 *      session's cache) is out of reach: Playwright contexts are ephemeral,
 *      so there is no yesterday's profile to open. Same-context offline reload
 *      proves the serving mechanism; the storage half is T4's record survival.
 *   X5 EVERY OFFLINE-AUTHED CLAIM DEPENDS ON WARMING setup-status — see the
 *      doctrine block above; the spec states it rather than discovering it
 *      as a flake.
 *   X6 CACHE EVIDENCE VIA RESPONSE HEADERS is unavailable: nginx sends none.
 *      Proof here is fromServiceWorker() + CacheStorage + the miss-control —
 *      all three instruments agree.
 *
 * Throttle discipline: boots go through quietBoot; the offline phase generates
 * ZERO server traffic (SW answers from cache — probe counted 33–34 page-level
 * /api requests during offline that never reached nginx); the test still ends
 * with a BOOT_QUIET_MS drain so the next spec inherits a full burst bucket.
 */
import { createHash } from 'node:crypto';

import type { Page, Response } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
} from './harness';

const harness = readShellHarness();

/** Exactly what T3 warms through the controlled page and then asserts offline.
 *  setup-status is the fail-close guard (ProtectedRoute.tsx:79); cameras is
 *  the persisted query; me is the recovery probe. */
const WARM = ['/api/auth/setup-status', '/api/cameras', '/api/auth/me'];
/** Never warmed — the offline leg asserts it MISSES api-cache and dies. */
const UNWARMED = '/api/events?page=1&limit=5';

/** The persisted-query localStorage key (queryPersistence.ts:36). */
const PERSIST_KEY = 'security-dashboard-cache';

interface Registration {
  controller: boolean;
  scope: string | null;
  active: string | null;
  waiting: string | null;
  installing: string | null;
}

function registration(page: Page): Promise<Registration> {
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

/** Poll until the SW really controls this page's scope (probe: 1.5–2 s).
 *  Warm fetches must pass THROUGH the activated SW or api-cache stays empty. */
async function waitControlled(page: Page, scope: string): Promise<void> {
  await expect
    .poll(() => registration(page), {
      message: 'the shipped service worker must install, activate and take control',
      timeout: 20_000,
    })
    .toEqual({ controller: true, scope, active: 'activated', waiting: 'null', installing: 'null' });
}

test.describe('golden path: service worker + offline cache on the built stack @critical', () => {
  test.setTimeout(120_000);

  test('the shipped artifact: the served /sw.js carries the row\'s exact cache contract — api-cache network-first 10 s / 50 entries / 300 s, skipWaiting, index.html navigation fallback — and its index precache entry is content-addressed to the bytes actually served', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    const indexRes = await fetch(`${h.ui}/`);
    expect(indexRes.status, 'the SPA index must serve').toBe(200);
    const indexHtml = await indexRes.text();

    const swRes = await fetch(`${h.ui}/sw.js`);
    expect(swRes.status, 'the generated service worker must be served').toBe(200);
    const sw = await swRes.text();

    // The row's numbers, as compiled into the real runtime (measured token
    // spellings): vite.config.ts:102-109's /api NetworkFirst route.
    expect(sw, 'the /api route must be NetworkFirst').toMatch(/NetworkFirst/);
    expect(sw, 'the row\'s api cache name must exist').toContain('cacheName:"api-cache"');
    expect(sw).toContain('networkTimeoutSeconds:10');
    expect(sw).toContain('maxEntries:50');
    expect(sw, 'the row\'s "5 min" is 300 s in the artifact').toContain('maxAgeSeconds:300');
    // autoUpdate + skipWaiting (vite.config.ts:60/:132) and the SPA
    // navigation fallback (plugin default navigateFallback: "index.html").
    expect(sw).toMatch(/self\.skipWaiting\(\)/);
    expect(sw).toContain('createHandlerBoundToURL("index.html")');

    // Content-addressed coverage: Workbox's revision for a revisioned entry
    // is the md5 of its content, so the live index and the manifest must
    // agree byte-for-byte — the precache provably holds what ships TODAY.
    const md5 = createHash('md5').update(indexHtml).digest('hex');
    expect(
      sw,
      'precache must pin the index revision to the md5 of the served index'
    ).toContain(`{url:"index.html",revision:"${md5}"}`);

    // Every script the index actually loads is precached, by exact name —
    // (a route-split build names ~20 lazy chunks assets/index-*.js too, so
    // pattern-matching "an index chunk" would lie; only the exact basename
    // the index references counts).
    const scripts = [...indexHtml.matchAll(/src="(\/[^"]+\.js)"/g)].map((m) => m[1]);
    expect(
      scripts.some((s) => /^\/assets\/index-[\w-]+\.js$/.test(s)),
      `index must name its hashed entry bundle; named ${JSON.stringify(scripts)}`
    ).toBe(true);
    for (const s of scripts) {
      expect(sw, `precache must include ${s} that the index loads`).toContain(
        `{url:"${s.slice(1)}"`
      );
    }
    // The plugin's default injectRegister:"script" — the real registration
    // entry point main.tsx:42's module races against at load.
    const regSwRes = await fetch(`${h.ui}/registerSW.js`);
    expect(regSwRes.status, 'the injected registration script must serve').toBe(200);
    expect(await regSwRes.text(), 'it registers this very sw.js').toContain('/sw.js');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('control: after a real login boot the worker is active AND controlling the app scope — and autoUpdate+skipWaiting means no update can ever park a waiting worker (waiting/installing are observably null)', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    await seedTourDismissed(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h, '/');
    await page.waitForLoadState('load');

    await waitControlled(page, `${h.ui}/`);
    // The registration the page itself reports, a second time, un-timed: the
    // state is settled, not racy (X3's measured-absent waits here).
    const reg = await registration(page);
    expect(reg.controller, 'the page is under SW control').toBe(true);
    expect(reg.waiting, 'autoUpdate leaves no waiting worker').toBe('null');
    expect(reg.installing, '…and no installing one').toBe('null');

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('offline for real: with context.setOffline the RELOADED shell is served entirely by the worker (document + every asset 200, fromServiceWorker), the app BOOTS at / with its three warmed API responses from api-cache while an unwarmed endpoint dies TypeError in the same snapshot, the persisted query record survives the reload — and recovery answers live again', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;

    await seedTourDismissed(page);
    await loginAsAdmin(page, h);
    await quietBoot(page, h, '/');
    await page.waitForLoadState('load');
    await waitControlled(page, `${h.ui}/`);

    // Warm EXACTLY the asserted keys, through the controlled page, online.
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
      .poll(
        () =>
          page.evaluate(async (keys) => {
            const c = await caches.open('api-cache');
            return (await Promise.all(keys.map((k) => c.match(k).then((r) => !!r)))).every(Boolean);
          }, WARM),
        { message: 'NetworkFirst must have written all warmed keys to api-cache', timeout: 15_000 }
      )
      .toBe(true);

    // Precache present, with the measured key semantics: the index is stored
    // under its REVISIONED url — a bare caches.match('/index.html') misses —
    // so the instrument is a keys() scan (never trust the bare match).
    const pre = await page.evaluate(async () => {
      const name = (await caches.keys()).find((n) => n.startsWith('workbox-precache-v2-'));
      if (!name)
        return { name: null as string | null, n: 0, indexKey: null, bare: false, stored: false };
      const c = await caches.open(name);
      const keys = (await c.keys()).map((r) => r.url);
      const indexKey = keys.find((u) => u.includes('/index.html')) ?? null;
      return {
        name,
        n: keys.length,
        indexKey,
        bare: !!(await c.match('/index.html')),
        stored: indexKey ? !!(await c.match(indexKey)) : false,
      } as { name: string | null; n: number; indexKey: string | null; bare: boolean; stored?: boolean };
    });
    expect(pre.name, 'the Workbox precache cache must exist').toMatch(/^workbox-precache-v2-/);
    expect(pre.n, 'the shell precache must hold the built asset set').toBeGreaterThan(100);
    expect(pre.bare, 'measured semantics: bare /index.html MISSES the revisioned key').toBe(false);
    expect(pre.stored, 'the stored revisioned key MATCHES').toBe(true);

    // The persistence record (T4's leg): written by the throttled persister
    // (queryPersistence.ts:36 key, :119 1 s throttle) — poll, never a
    // zero-delay read.
    await expect
      .poll(
        () =>
          page.evaluate(
            (k) =>
              new Promise<string>((resolve) => {
                const t = setInterval(() => {
                  const raw = localStorage.getItem(k);
                  if (raw) {
                    clearInterval(t);
                    resolve(raw);
                  }
                }, 250);
                setTimeout(() => {
                  clearInterval(t);
                  resolve('');
                }, 8000);
              }),
            PERSIST_KEY
          ),
        { message: 'the TanStack persister must write its localStorage record', timeout: 12_000 }
      )
      .toContain('"cameras"');

    // --- the partition (browser-level; ws-status.spec.ts:198 precedent) ---
    const responses: Response[] = [];
    page.on('response', (r) => responses.push(r));
    await page.context().setOffline(true);
    await expect
      .poll(() => page.evaluate(() => navigator.onLine), { message: 'partition must take' })
      .toBe(false);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('load');
    // Drain so the boot's lazy-chunk imports land too. Measured (first run of
    // this very spec + probe): right at 'load' the shell is 3 responses —
    // document + entry JS + entry CSS — and by +1.5 s the dashboard's mount
    // has pulled ~41 more precached chunks (44/44 SW-served, probe 3×3).
    await page.waitForTimeout(1_500);

    // Universal claim over everything the offline reload DID fetch, plus the
    // named members the boot cannot happen without — no fragile threshold:
    const shell = responses.filter(
      (r) =>
        r.url().startsWith(h.ui) &&
        (/\/assets\/.*\.(js|css)$/.test(r.url()) || r.request().resourceType() === 'document')
    );
    for (const r of shell) {
      expect(r.fromServiceWorker(), `${r.url()} must come from the worker`).toBe(true);
      expect(r.status(), `${r.url()} must serve 200 from cache`).toBe(200);
    }
    const shellUrls = shell.map((r) => r.url());
    expect(
      shell.some((r) => r.request().resourceType() === 'document'),
      'the offline reload must have served the DOCUMENT from cache'
    ).toBe(true);
    expect(
      shellUrls.some((u) => /\/assets\/index-[\w-]+\.js$/.test(u)),
      'the entry bundle must have come from cache'
    ).toBe(true);
    expect(
      shellUrls.some((u) => /\/assets\/index-[\w-]+\.css$/.test(u)),
      'the entry stylesheet must have come from cache'
    ).toBe(true);
    // The route-split proof: a chunk the boot imports DYNAMICALLY (lazy route)
    // also came from the offline precache — that's the row's "static assets
    // … served from cache" past the static index tags.
    expect(
      shellUrls.some((u) => /\/assets\/DashboardPage-[\w-]+\.js$/.test(u)),
      `a lazily-imported route chunk must serve offline; shell was ${JSON.stringify(shellUrls)}`
    ).toBe(true);

    // One behavioral snapshot = the boot proof + miss control + record, taken
    // as a single atomic observation (ruling: no locator chains across a
    // flapping partition — ws-status memory).
    const snap = await page.evaluate(
      async (args: { warm: string[]; unwarmed: string; persistKey: string }) => {
        const cached: Record<string, number | string> = {};
        for (const k of args.warm) {
          try {
            cached[k] = (await fetch(k, { credentials: 'include' })).status;
          } catch (e) {
            cached[k] = String(e).slice(0, 40);
          }
        }
        let unwarmed: string;
        try {
          unwarmed = `STATUS:${(await fetch(args.unwarmed, { credentials: 'include' })).status}`;
        } catch (e) {
          unwarmed = String(e).slice(0, 40);
        }
        const raw = localStorage.getItem(args.persistKey);
        return {
          path: location.pathname,
          onLine: navigator.onLine,
          controller: navigator.serviceWorker.controller !== null,
          title: document.title,
          cached,
          unwarmed,
          persistSurvived: !!raw,
          persistQueries: raw
            ? ((JSON.parse(raw).clientState?.queries ?? []) as Array<{ queryKey: unknown }>).map(
                (q) => JSON.stringify(q.queryKey)
              )
            : [],
        };
      },
      { warm: WARM, unwarmed: UNWARMED, persistKey: PERSIST_KEY }
    );
    // The app BOOTED offline: at the app root (NOT fail-closed to /setup —
    // the warmed setup-status answer is what makes this claim legal, X5),
    // under control, with the real title.
    expect(snap.path, 'offline boot must stay at / (cached setup-status)').toBe('/');
    expect(snap.controller).toBe(true);
    expect(snap.title).toBe('Security Dashboard');
    // …answering the warmed keys from cache…
    expect(snap.cached).toEqual({
      '/api/auth/setup-status': 200,
      '/api/cameras': 200,
      '/api/auth/me': 200,
    });
    // …while the UNWARMED control dies in the same instant: the partition is
    // real AND NetworkFirst answered the warmed keys from cache rather than
    // "waiting out" a 10 s timeout (that control would have failed the same
    // way only to retry — it instead fails with no network at all).
    expect(snap.unwarmed, 'unwarmed endpoint must genuinely fail offline').toMatch(
      /^TypeError: Failed to fetch/
    );
    // T4's leg: the persisted query record rode through the reload offline.
    expect(snap.persistSurvived, 'the localStorage record must survive the reload').toBe(true);
    expect(snap.persistQueries, 'the cameras query stays recorded for cold starts').toContain(
      '["cameras","list"]'
    );

    // Recovery: back online, live answers return (poll — refill/settle).
    await page.context().setOffline(false);
    await expect
      .poll(
        () =>
          page.evaluate(async () => {
            try {
              return (await fetch('/api/auth/me', { credentials: 'include' })).status;
            } catch {
              return 0;
            }
          }),
        { message: 'back online, /api/auth/me must answer live again', timeout: 20_000 }
      )
      .toBe(200);
    expect(await page.evaluate(() => navigator.onLine)).toBe(true);
    // Lane citizenship: the offline phase issued ZERO real server traffic;
    // still hand the next spec a full nginx burst bucket.
    await page.waitForTimeout(BOOT_QUIET_MS);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
