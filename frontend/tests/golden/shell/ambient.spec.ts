/**
 * FE-1 golden path (F2.3): F-020 — ambient status awareness: the background
 * tint layer and the favicon/title badge, toggled from /settings/ambient.
 *
 * Every navigation goes through quietBoot()/BOOT_QUIET_MS (harness.ts — the
 * frontend nginx /api throttle and why a boot needs a drained burst).
 *
 * TWO MEASURED FINDINGS decide this spec's shape (both live, both cost a run
 * to find; the row is demoted half-built per ruling 86 rather than asserted
 * vacuously):
 *
 * 1) "TOGGLES LIVE" IS NOT LIVE IN-TAB. useSettings is localStorage-backed
 *    PER HOOK INSTANCE (useLocalStorage.ts:38 useState initializer + :41-43
 *    mount-only sync whose readValue deps [key, initialValue] are stable),
 *    there is NO shared store, NO React context, and NO 'storage'-event
 *    subscription for settings (the only storage listener in src is
 *    useSavedSearches.ts:144). The /settings/ambient panel and
 *    AmbientStatusProvider therefore run TWO independent useSettings()
 *    states that share only the jar: flipping the switch updates the panel's
 *    aria + the jar INSTANTLY, while the provider's overlay/badge keep the
 *    value they read at MOUNT until a remount. The provider does re-render
 *    every 5 s (each WS system_status sets state, system_broadcaster.py:1100)
 *    — and that re-render does NOT re-read the jar (useState, not a fresh
 *    readValue). So the fair window for "did anything ever converge?" is
 *    3+ broadcast cycles, and the measured answer (2026-10-11, probe stack)
 *    is NO. Tests 1/2 pin the BREAK as evidence (state flipped + jar flipped
 *    + effects STILL the old value after >=16 s), then pin what is actually
 *    true: the toggle persists in the jar and RELOAD applies it — overlay
 *    absent with ambient off, boot literals restored with the badge off.
 *    When a shared store lands, these legs go RED on purpose and the row
 *    re-adjudicates (same failure-as-evidence discipline as F-017's demoted
 *    slide-out clause).
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
 * - Badge OFF semantics AFTER remount (the restore branch, :259-263, replays
 *   the values saved at mount by :239-256 — declaration order guarantees save
 *   before write): BOTH index.html literals come back, title "Nemotron
 *   Security Dashboard" (:24) and href /favicon.svg (:16). The title is
 *   route-independent because the badge sits ABOVE the router.
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
 *   stringified (useLocalStorage.ts:57), parsed here the way the app reads.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
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

/** Boot literal (index.html:24) vs the feature's own (provider baseTitle,
 *  AmbientStatusProvider.tsx:117). */
const BOOT_TITLE = 'Nemotron Security Dashboard';
const FEATURE_TITLE = 'Security Dashboard';

/** >=3 full WS re-render cycles (broadcaster interval 5 s,
 *  system_broadcaster.py:1100). The stale-until-reload legs wait this long
 *  before declaring the provider frozen, so "no live sync" is a measurement
 *  across re-render opportunities, not a 3 s assert window. */
const FROZEN_WINDOW_MS = 16_000;

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
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
  await expect(page).toHaveURL(`${h.ui}/settings`);
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

  test('F-020: /settings/ambient writes the toggle and the jar instantly, but the tint is STALE until reload (break measured) — reload applies it', async ({
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

    // ...and the provider's overlay does NOT follow, across >=3 full WS
    // re-render cycles (file finding #1): the jar is written, the component
    // state behind the overlay is mount-stale. This is the ROW's "toggles
    // live" clause failing as evidence — flip it to expect-absent when a
    // shared settings store lands, and the row upgrades.
    await page.waitForTimeout(FROZEN_WINDOW_MS);
    const frozen = await snapshot(page);
    expect(frozen.background, 'provider never re-read the settings jar').toBe(true);
    test.info().annotations.push({
      type: 'F-020 live-sync measurement',
      description: `ambient jar flipped false and panel aria flipped, yet ambient-background stayed mounted for >=${FROZEN_WINDOW_MS / 1000}s (>3 WS re-render cycles): useSettings is per-instance localStorage state with no cross-tree sync; RELOAD is what applies it (next legs).`,
    });

    // What IS true: the toggle PERSISTED, and a reload (remount = the
    // provider's mount-time jar read) APPLIES it — overlay and wrapper are
    // GONE (enabled=false returns bare children, AmbientBackground.tsx
    // :105-107) while the app paints fine, on the settings route itself.
    await drainAndReload(page);
    await expect(page).toHaveURL(`${h.ui}/settings/ambient`);
    await expect(overlay(page)).toHaveCount(0);
    await expect(page.getByTestId('ambient-background')).toHaveCount(0);
    await expect(ambientSwitch(page)).toHaveAttribute('aria-checked', 'false');
    const afterReload = await snapshot(page);
    expect(afterReload.background).toBe(false);
    expect(afterReload.branding).toBe(true); // app fine behind the absent layer

    // And ON again endures the same way: flip (panel+jar), reload, the mount
    // read re-mounts the whole healthy effect.
    await ambientSwitch(page).click();
    await expect(ambientSwitch(page)).toHaveAttribute('aria-checked', 'true');
    await expect.poll(() => ambientJar(page, 'ambient')).toBe(true);
    await drainAndReload(page);
    await expect(overlay(page).first()).toBeAttached();
    await expectHealthyAmbientOn(page);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-020: the badge owns the ONLY title/icon writers — mount applies the feature values; OFF reaches the boot literals via the jar + reload (live leg measured)', async ({
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

    // OFF in the panel: aria+jar flip instantly — and just like the tint, the
    // title is mount-stale (same root cause, file finding #1; the shorter
    // 2-cycle window here is enough because test 1 already proved the
    // mechanism across 3+ cycles).
    await gotoAmbientTab(page, h);
    await faviconSwitch(page).click();
    await expect(faviconSwitch(page)).toHaveAttribute('aria-checked', 'false');
    await expect.poll(() => ambientJar(page, 'favicon')).toBe(false);
    await page.waitForTimeout(11_000); // >=2 WS cycles
    await expect(page).toHaveTitle(FEATURE_TITLE); // still the feature's: stale
    test.info().annotations.push({
      type: 'F-020 badge live-sync measurement',
      description:
        'favicon jar+aria flipped false but document.title stayed "Security Dashboard" for >=11s — same per-instance-settings break as the tint leg; restore runs at the provider remount below.',
    });

    // Reload: the remount's mount-effect sequence (save-then-write,
    // :239-256 before :259-280) now reads enabled=false, so the restore
    // branch puts BOTH saved boot literals back — title to the index.html
    // string, href to /favicon.svg. FaviconBadge being the only writer makes
    // this read pure (grep-verified).
    await drainAndReload(page);
    await expect(page).toHaveURL(`${h.ui}/settings/ambient`);
    await expect(page).toHaveTitle(BOOT_TITLE);
    await expect
      .poll(async () => {
        const href = await page.evaluate(
          () => document.querySelector('link[rel="icon"]')?.getAttribute('href') ?? null
        );
        return href !== null && href.includes('/favicon.svg');
      })
      .toBe(true);

    // Re-ON endures the same round trip and is re-applied — state, not
    // residue — and the title is still route-independent on the dashboard.
    await faviconSwitch(page).click();
    await expect(faviconSwitch(page)).toHaveAttribute('aria-checked', 'true');
    await expect.poll(() => ambientJar(page, 'favicon')).toBe(true);
    await drainAndReload(page);
    await expect(page).toHaveTitle(FEATURE_TITLE);
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
