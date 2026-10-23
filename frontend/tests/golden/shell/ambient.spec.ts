/**
 * FE-1 golden path (F2.3): F-020 — ambient status awareness: the background
 * tint layer and the favicon/title badge, toggled from /settings/ambient.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * TWO MEASURED FINDINGS decide this spec's shape (both cost a run to find):
 *
 * 1) "TOGGLES LIVE" WAS NOT LIVE IN-TAB; [r130f] FIXED IT, and these legs
 *    now assert the FIX (ruling 130). The break: useSettings was
 *    localStorage-backed PER HOOK INSTANCE — a useState initializer that read
 *    the jar once (pre-fix useLocalStorage.ts:38) plus a mount-only sync
 *    (pre-fix :41-43), and functional updates computed from the instance's own
 *    `storedValue` closure (pre-fix :63 `[key, storedValue]`). No shared
 *    store, no context, no 'storage' subscription for settings (the only
 *    storage listener in src was useSavedSearches.ts:144, which serves the
 *    cross-TAB half). So the /settings/ambient panel and
 *    AmbientStatusProvider ran TWO independent useSettings() states sharing
 *    only the jar, and the provider's 5 s WS re-render
 *    (system_broadcaster.py:1100) never re-read the jar: measured 2026-10-11,
 *    the effects never converged without a remount.
 *    The fix is in the hook, not in one component (useLocalStorage.ts now):
 *    the jar is the single source of truth, sibling instances in the SAME
 *    document are announced through a module-level registry
 *    (subscribers :37, subscribe :39, announce :53, called at :158), a
 *    notification re-reads the jar (:103/:118), functional updates read the
 *    CURRENT value through a ref (:133/:149) instead of a captured copy, and
 *    a 'storage' listener (:124) covers other documents. Same-tab siblings
 *    could not be fixed by that listener alone: measured on this app origin,
 *    a write's storage event reaches the OTHER page and NOT the writer
 *    (deltaA [] vs deltaB [key]) — the browser stays silent at the document
 *    that called setItem. Tests 1/2 measure the fix: the same tab applies the
 *    toggle with NO reload, survives >=1 WS re-render cycle without
 *    resurrecting the layer, and the jar still carries it across a reload
 *    (persistence, which was never the broken half).
 *    No component work was needed for the live half: AmbientBackground already
 *    returns bare children when disabled (AmbientBackground.tsx:105-107) and
 *    FaviconBadge already restores title+href on any re-render that sees
 *    enabled=false (:259-264, deps list :273-280 includes it). The mount-time
 *    read was the ONLY stale layer, so fixing the hook is fixing the feature.
 * 2) The row's 'degraded or unhealthy' tint bands are UNREACHABLE from any
 *    browser-side instrument, for a stronger reason than F-016's:
 *    useSystemStatus has NO polling — GET /api/system/health is a MOUNT-ONLY
 *    seed (:58-88) and status changes only on NEW WS system_status messages
 *    (:93-98). setOffline cuts the browser's feed (the value FREEZES at the
 *    last healthy sample) and never touches the backend's own db/redis/ai
 *    probes (server-side, system.py:1325-1333), so it cannot produce even
 *    'unhealthy' here — F-016's offline trick only worked because that hook
 *    RE-POLLS every 15 s. Reaching degraded (some-but-not-all probes down)
 *    or unhealthy (db down) needs an operator to take down real
 *    dependencies: the real tier, ruling 66. This spec therefore pins the
 *    HEALTHY band with cross-instrument truth (backend API verdict vs DOM)
 *    and files the rest on the row.
 *
 * What IS green and pinned (each claim cites where it was decided):
 * - Mount: App.tsx:252-335 wraps every protected route in
 *   AmbientStatusProvider, so dashboard AND /settings/ambient render inside
 *   it; the g-chords (useKeyboardShortcuts.ts:19-29) move between them
 *   (F-018-proven instrument).
 * - Healthy derivation chain, measured end to end: GET /api/system/health
 *   says status 'healthy' => threat 0 (AmbientStatusProvider.tsx:43-56) =>
 *   category 'normal' + clamped level '0' as REAL DOM attributes on
 *   data-testid=ambient-overlay, class opacity-0, EMPTY style
 *   (AmbientBackground.tsx:47-52, 103, 113-127), aria-hidden decoration
 *   (:176). The same endpoint is read Node-side (harness api()) for the
 *   cross-check — two instruments, one fact (F-005 discipline).
 * - Badge ON semantics (healthy => alertCount 0, :95-109): document.title ==
 *   "Security Dashboard" (provider baseTitle :117; FaviconBadge.tsx:216-220)
 *   and link[rel="icon"] href is the CANVAS output (draw favicon.svg into
 *   32x32, toDataURL, :130-131+:176-190) — a data:image/png, not the file
 *   URL. FaviconBadge is grep-verified the ONLY writer in src to
 *   document.title and link[rel="icon"], so both globals are PURE readouts.
 * - Badge OFF semantics (the live restore branch, :259-264, replays the values
 *   saved at mount by :239-256 — declaration order guarantees save before
 *   write): BOTH index.html literals come back, title "Nemotron Security
 *   Dashboard" (:24) and href /favicon.svg (:16). The title is route-independent
 *   because the badge sits ABOVE the router.
 * - Panel: reached by REAL navigation (g s chord -> /settings, then the tab
 *   data-testid settings-tab-ambient; SettingsPage.tsx:199-217 pins
 *   role="tab" over NavLink's link role, and the sidebar has no AMBIENT
 *   entry — grep). Tremor Card spreads leftover props onto its div, so the
 *   panel's data-testid=ambient-status-settings is a real anchor.
 * - THE SWITCH LOCATOR (cost two failed legs): getByRole('switch',
 *   {name}) finds NOTHING because Tremor's Switch spreads unknown props —
 *   the app's aria-label — onto its WRAPPER DIV, while the real
 *   role="switch" button (HeadlessUI's) is named "Switch on/off" by its
 *   sr-only copy (dist Switch.js; DOM-probe confirmed: ariaChecked on the
 *   BUTTON, parentAriaLabel on the DIV, button's own aria-label null). The
 *   instrument is div[aria-label=...] chained to getByRole('switch'), and
 *   aria-checked there reads the COMPONENT's own checked flag.
 * - settings-store.ts re-implements the same settings shape but is DEAD
 *   code (only stores/index.ts re-exports it) — not the app's path; the
 *   jar is 'security-dashboard-settings' (useSettings.ts:88), JSON-
 *   stringified (useLocalStorage.ts:153), parsed here the way the app reads.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
  adminSession,
  apiShell as api,
  closedByGuard,
  openShell as openShellFixture,
  readShellHarness,
  type ShellHarness,
} from '../harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

/** Boot literal (index.html:24) vs the feature's own (provider baseTitle,
 *  AmbientStatusProvider.tsx:117). */
const BOOT_TITLE = 'Nemotron Security Dashboard';
const FEATURE_TITLE = 'Security Dashboard';

/** One full WS re-render cycle (broadcaster interval 5 s,
 *  system_broadcaster.py:1100) plus slack. The provider re-renders INSIDE this
 *  window, so a settings value that merely looked current at mount would
 *  resurrect the layer the toggle removed. This is the same physical window the
 *  pre-fix spec used to prove the effects never converged; only the expected
 *  polarity changed (ruling 130). */
const WS_CYCLE_MS = 8_000;

/** Shared navigation fixture (harness.ts openShell), preserving line offsets. */
async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  // Delegated to openShellFixture in harness.ts (F4.9 consolidation).
  // Kept at 6 lines so feature-inventory.md's :251 and :324 cites hold.
  await openShellFixture(page, h);
}

const overlay = (page: import('@playwright/test').Page) => page.getByTestId('ambient-overlay');
const ambientTab = (page: import('@playwright/test').Page) =>
  page.getByTestId('settings-tab-ambient');
const ambientSwitch = (page: import('@playwright/test').Page) =>
  page.locator('div[aria-label="Enable ambient background effects"]').getByRole('switch');
const faviconSwitch = (page: import('@playwright/test').Page) =>
  page.locator('div[aria-label="Enable favicon badge"]').getByRole('switch');

/** One coherent read of everything F-020 writes into the DOM (file header). */
function snapshot(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const q = (sel: string) => document.querySelector(sel);
    const ov = q('[data-testid="ambient-overlay"]');
    const link = q('link[rel="icon"]') as HTMLLinkElement | null;
    return {
      background: !!q('[data-testid="ambient-background"]'),
      category: ov?.getAttribute('data-threat-category') ?? null,
      level: ov?.getAttribute('data-threat-level') ?? null,
      overlayOpacityClass: ov ? /\bopacity-0\b/.test(ov.className) : null,
      overlayHasGradient: ov ? (ov.getAttribute('style') ?? '').includes('radial-gradient') : null,
      title: document.title,
      iconHref: link?.getAttribute('href') ?? null,
      branding: !!q('[data-testid="header-branding"]'),
    };
  });
}
/** True once the badge's restore branch has the index.html favicon back. The
 *  badge's own output is a data: URL, so the two states cannot be mistaken for
 *  each other (FaviconBadge.tsx:176-190 vs the /favicon.svg literal at
 *  index.html:16). */
const bootFaviconRestored = (page: import('@playwright/test').Page) =>
  page.evaluate(() =>
    (document.querySelector('link[rel="icon"]')?.getAttribute('href') ?? '').includes(
      '/favicon.svg'
    )
  );

const ambientJar = (page: import('@playwright/test').Page, key: 'ambient' | 'favicon') =>
  page.evaluate(
    (k) =>
      (
        JSON.parse(localStorage.getItem('security-dashboard-settings') ?? 'null') as {
          ambientStatus?: Record<string, { enabled?: boolean } | undefined>;
        } | null
      )?.ambientStatus?.[k]?.enabled ?? null,
    key
  );

/** The healthy-feed steady state: normal/0 tint + the feature's own title +
 *  the canvas-rendered favicon. Polled (65 s, the F-007/F-016 ceiling: 15 s
 *  backend health cache + the 5 s WS re-broadcast loop) because a shed boot
 *  read must still converge. */
async function expectHealthyAmbientOn(page: import('@playwright/test').Page) {
  await expect
    .poll(
      async () => {
        const s = await snapshot(page);
        return (
          s.background &&
          s.category === 'normal' &&
          s.level === '0' &&
          s.overlayOpacityClass === true &&
          s.overlayHasGradient === false &&
          s.title === FEATURE_TITLE &&
          (s.iconHref ?? '').startsWith('data:image/png')
        );
      },
      { timeout: 65_000, message: 'healthy ambient state never converged' }
    )
    .toBe(true);
}

async function gotoAmbientTab(page: import('@playwright/test').Page, h: ShellHarness) {
  await page.keyboard.press('g');
  await page.keyboard.press('s');
  await expect(page).toHaveURL(new RegExp(`^${h.ui}/settings(/cameras)?$`));
  await ambientTab(page).click();
  await expect(page).toHaveURL(`${h.ui}/settings/ambient`);
  await expect(page.getByTestId('not-found-page')).toHaveCount(0);
  await expect(page.getByTestId('ambient-status-settings')).toBeVisible();
}

async function drainAndReload(page: import('@playwright/test').Page) {
  await page.waitForTimeout(BOOT_QUIET_MS);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

test.describe('golden path: ambient status tint + favicon badge @critical', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test('F-020: /settings/ambient toggles the tint LIVE — no reload — and the jar carries it across one', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(180_000);
    await openShell(page, h);
    await expectHealthyAmbientOn(page);

    await gotoAmbientTab(page, h);
    await expect(ambientSwitch(page)).toHaveAttribute('aria-checked', 'true');

    // Flip OFF through the REAL control: the panel's own aria and the jar
    // both answer instantly (that half of "toggles" works).
    await ambientSwitch(page).click();
    await expect(ambientSwitch(page)).toHaveAttribute('aria-checked', 'false');
    await expect.poll(() => ambientJar(page, 'ambient')).toBe(false);

    // ...and the provider's overlay FOLLOWS, in the same tab, with no remount
    // — the [r130f] fix (file finding #1). Overlay and wrapper go away because
    // enabled=false returns bare children (AmbientBackground.tsx:105-107).
    await expect(overlay(page)).toHaveCount(0);
    await expect(page.getByTestId('ambient-background')).toHaveCount(0);
    const off = await snapshot(page);
    expect(off.background).toBe(false);
    expect(off.branding).toBe(true); // app still paints fine without the layer

    // Then SURVIVE the provider's own re-render loop (a WS system_status
    // arrives every 5 s). The pre-fix break was a stale mount-time read, so a
    // re-render is exactly the event that would resurrect the layer if any
    // component still held a captured value — this window is the same physical
    // wait the pre-fix spec used to prove they never converged.
    await page.waitForTimeout(WS_CYCLE_MS);
    await expect(overlay(page)).toHaveCount(0);
    expect((await snapshot(page)).background, 'a re-render resurrected the layer').toBe(false);
    test.info().annotations.push({
      type: 'F-020 live-sync measurement',
      description: `ambient jar+panel aria flipped false and the overlay unmounted in the SAME tab within the auto-wait window, then stayed absent across >=1 WS re-render cycle (${WS_CYCLE_MS / 1000}s): the jar is now the single source of truth and same-tab siblings are announced through the module registry (useLocalStorage.ts:37/:53/:158). Pre-fix this leg held the layer mounted for >=16s across >3 cycles.`,
    });

    // The persistence half (never the broken half): the jar carries the flip
    // across a reload, where the mount read starts from DEFAULT_SETTINGS (both
    // flags true — useSettings.ts:89 ambient, :99 favicon) — so if the write
    // had not persisted, the remount would bring the layer back. One reload.
    await drainAndReload(page);
    await expect(page).toHaveURL(`${h.ui}/settings/ambient`);
    await expect(overlay(page)).toHaveCount(0);
    await expect(ambientSwitch(page)).toHaveAttribute('aria-checked', 'false');
    expect((await snapshot(page)).background).toBe(false);

    // And ON again is LIVE too: the same registry path re-mounts the healthy
    // effect without a reload (defaults can't fake this — both flags are
    // already true, so only the jar's false->true write is doing any work).
    await ambientSwitch(page).click();
    await expect(ambientSwitch(page)).toHaveAttribute('aria-checked', 'true');
    await expect.poll(() => ambientJar(page, 'ambient')).toBe(true);
    await expect(overlay(page).first()).toBeAttached();
    await expectHealthyAmbientOn(page);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-020: the badge owns the ONLY title/icon writers — mount applies the feature values; OFF reaches the boot literals LIVE, and the jar carries it across one reload', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(180_000);
    await openShell(page, h);
    await expectHealthyAmbientOn(page);

    // ON, healthy feed: alertCount 0 (AmbientStatusProvider.tsx:100-108) =>
    // bare baseTitle (FaviconBadge.tsx:216-220); the favicon href is the
    // canvas pipeline's data URL (:130-131,:176-190). Route-independent:
    // the badge lives in the provider ABOVE the router (App.tsx:252).
    await expect(page).toHaveTitle(FEATURE_TITLE);
    const onHref = await page.evaluate(
      () => document.querySelector('link[rel="icon"]')?.getAttribute('href') ?? null
    );
    expect(onHref, 'badge ON re-renders the favicon through the canvas').toMatch(
      /^data:image\/png/
    );

    // OFF in the panel: aria+jar flip instantly — and the badge now FOLLOWS in
    // the same tab. The restore branch (FaviconBadge.tsx:259-264) replays the
    // values the mount effect saved at :239-256, so BOTH boot literals come
    // back with no reload: the index.html title string (:24) and href
    // /favicon.svg (:16). FaviconBadge is the only writer of either global
    // (grep-verified), so both reads are pure.
    await gotoAmbientTab(page, h);
    await faviconSwitch(page).click();
    await expect(faviconSwitch(page)).toHaveAttribute('aria-checked', 'false');
    await expect.poll(() => ambientJar(page, 'favicon')).toBe(false);
    await expect(page).toHaveTitle(BOOT_TITLE);
    await expect.poll(() => bootFaviconRestored(page)).toBe(true);

    // ...and they STAY restored across the provider's 5 s re-render loop: a
    // captured mount value would re-apply the feature title on the next
    // system_status. Same physical window as the tint leg.
    await page.waitForTimeout(WS_CYCLE_MS);
    await expect(page).toHaveTitle(BOOT_TITLE);
    expect(await bootFaviconRestored(page)).toBe(true);
    test.info().annotations.push({
      type: 'F-020 badge live-sync measurement',
      description: `favicon jar+aria flipped false and document.title/href returned to the index.html boot literals in the SAME tab, then held across >=1 WS re-render cycle (${WS_CYCLE_MS / 1000}s). Pre-fix this leg held "Security Dashboard" for >=11s — the same per-instance-settings break as the tint leg, fixed in the hook.`,
    });

    // Persistence, one reload: the remount re-runs save-then-write (:239-256
    // before :259-280) from a jar that says enabled=false, so the restore is
    // re-derived from stored state rather than left as DOM residue.
    await drainAndReload(page);
    await expect(page).toHaveURL(`${h.ui}/settings/ambient`);
    await expect(page).toHaveTitle(BOOT_TITLE);
    await expect.poll(() => bootFaviconRestored(page)).toBe(true);

    // Re-ON is LIVE too (defaults are already true, so this can only be the
    // jar write) and the title stays route-independent afterwards, because the
    // badge sits above the router (App.tsx:252).
    await faviconSwitch(page).click();
    await expect(faviconSwitch(page)).toHaveAttribute('aria-checked', 'true');
    await expect.poll(() => ambientJar(page, 'favicon')).toBe(true);
    await expect(page).toHaveTitle(FEATURE_TITLE);
    await expect
      .poll(async () => ((await snapshot(page)).iconHref ?? '').startsWith('data:image/png'))
      .toBe(true);
    await page.keyboard.press('g');
    await page.keyboard.press('d');
    await expect(page).toHaveURL(`${h.ui}/`);
    await expect(page).toHaveTitle(FEATURE_TITLE);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-020 (feed truth): the healthy tint is cross-checked against the backend, and its DOM contract is exact', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    test.setTimeout(180_000);
    await openShell(page, h);
    await expectHealthyAmbientOn(page);
    const dom = await snapshot(page);

    // Feed truth, not assumption: the tint says normal BECAUSE the backend
    // says healthy — two independent instruments reading one fact (F-005
    // discipline). Node-side read: backend state, never the UI origin.
    const session = await adminSession(h);
    const health = await api<{ status: string }>(h, session, '/api/system/health');
    expect(health.status).toBe('healthy');
    expect([dom.category, dom.level]).toEqual(['normal', '0']);

    // The normal-band DOM contract, exactly: decoration is aria-hidden
    // (AmbientBackground.tsx:176), the class carries opacity-0 (:117), and
    // the style is EMPTY for normal (:126-127) — a healthy system paints NO
    // gradient at all. (The degraded/high/critical gradients and the
    // reduced-motion pulse cannot be reached from this tier — useSystemStatus
    // has no polling and the browser cannot take the backend's probes down;
    // see file finding #2, filed on the row for the real tier, ruling 66.)
    await expect(overlay(page).first()).toHaveAttribute('aria-hidden', 'true');
    expect(dom.overlayOpacityClass).toBe(true);
    expect(dom.overlayHasGradient).toBe(false);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
