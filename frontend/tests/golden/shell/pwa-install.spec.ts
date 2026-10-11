/**
 * Golden path: the PWA install prompt (inventory F-023).
 *
 * Row claim measured here, on the live feature-check stack shape:
 * "after enough visits, sees an Install app prompt; installs or dismisses
 * (remembered)".
 *
 * WHY A SECOND, SELF-LAUNCHED BROWSER — and why it stays interception-free:
 * `beforeinstallprompt` is emitted by Chrome 153 (Playwright 1.63 / chromium
 * build 1243) only in a browser that is (a) NOT off-the-record and (b) NOT
 * headless by Chrome's own flag. Measured 2026-10-11 on this stack — the page
 * is INSTALLABLE in every posture (manifest + /sw.js + 192/512 icons all 200,
 * SW activated, `Page.getInstallabilityErrors` EMPTY headless; only
 * "in-incognito" headed-incognito — only the EVENT varies):
 *   - lane context (headless + incognito): 0 events, 2 runs;
 *   - persistent profile + headless:     0 events, audit [] (2 runs);
 *   - persistent profile + headed/Xvfb:  events fire ~90-130 ms in, banner
 *     paints on visit 2 past the component's 30 s gate;
 *   - persistent profile + headless:false --ozone-platform=headless:
 *     EVENTS FIRE with NO X server (probe7) — the posture of the CI golden
 *     job, a plain `npx playwright test --project=golden` on ubuntu-latest
 *     with no xvfb wrapper. (Playwright's own Xvfb auto-start does NOT cover
 *     launchPersistentContext — measured "Missing X server or $DISPLAY".)
 * So the golden PAGE fixture (Playwright's ephemeral context) can never light
 * this feature; the honest instrument is a throwaway persistent profile over
 * the ozone headless compositor — real served manifest, real activated
 * service worker, real Chromium installability pipeline, zero route/WebSocket
 * interception (this spec never touches page.route in either browser; the
 * guard tripwire is asserted on the lane page, and deliberately NOT on the
 * self-launched page, where an unpatched page.route would INSTALL real
 * interception instead of throwing).
 *
 * WHAT THE UI CAN AND CANNOT PROVE (both asserted, neither faked — ruling 86):
 *   • Appearance leg, fully reachable: InstallPrompt gates on 2 visits AND
 *     >=30 s on the current document (defaults :91-94, checkEngagementCriteria
 *     :182-196) AFTER an event supplies `deferredPrompt` (:287 returns null
 *     without one). The visit ledger is the component's own
 *     `pwa-visit-count`, incremented per mount (:250-252). Reaching it costs
 *     a ~31 s dwell — the feature's own engagement gate, not harness slack.
 *   • "Installs" dead-ends at the platform boundary for ANY automated
 *     instrument: handleInstall (:220-239) calls deferredPrompt.prompt() and
 *     awaits userChoice, but the install dialog is browser UI, not web
 *     content. Measured: after the click the banner stays visible and
 *     `pwa-installed` stays null through 6 s — the promise never resolves
 *     without a human. `markInstalled()` has no reachable writer from the
 *     page (UI-end break per the Statuses section => half-built).
 *   • "Dismisses (remembered)", fully reachable and green here: handleDismiss
 *     (:244-247) stamps `pwa-install-dismissed`; the next document past BOTH
 *     thresholds stays dark while the 7-day cooldown holds (:131-138), and the
 *     banner RETURNS once the stamp is older than the cooldown (that boundary
 *     is crossed by writing the expired shape the shipped check itself
 *     defines, then reloading — a real click dismisses again).
 *   • A third platform fact, measured and asserted: while deferredPrompt
 *     .prompt() is pending, Chrome's native install dialog HOLDS THE PAGE'S
 *     INPUT — a real click on "Not now" on that document reaches no handler,
 *     writes nothing, throws nothing (probes 8/9). The dismissal is therefore
 *     proven twice: synthetic (handler wiring, same document) and real gesture
 *     (next document, no dialog pending).
 *
 * Lane cost: ~140 s serial (three 30 s+ windows are the feature's own gates,
 * not harness slack).
 */
import { chromium } from '@playwright/test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Page } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from '../guard';
import { closedByGuard, readShellHarness, type ShellHarness } from './harness';

const harness = readShellHarness();

/** Counter re-created on EVERY document of the context (a listener injected
 *  via evaluate would die at the first reload and fake a zero). */
const BIP_COUNTER_SCRIPT = () => {
  localStorage.setItem('nemotron-tour-completed', 'true');
  localStorage.setItem('nemotron-tour-skipped', 'true');
  const w = window as unknown as { __bipCount?: number };
  w.__bipCount = 0;
  window.addEventListener('beforeinstallprompt', (e) => {
    w.__bipCount = (w.__bipCount ?? 0) + 1;
    e.preventDefault(); // the component prevents by default too; the probe must, or Chrome owns the event
  });
};

const readBip = (page: Page) =>
  page.evaluate(() => (window as unknown as { __bipCount?: number }).__bipCount ?? -1);

const PWA_JAR_KEYS = ['pwa-visit-count', 'pwa-install-dismissed', 'pwa-installed'] as const;
const readJar = (page: Page) =>
  page.evaluate(
    (keys) => Object.fromEntries(keys.map((k) => [k, localStorage.getItem(k)])),
    [...PWA_JAR_KEYS]
  );

/**
 * The spec-posture browser: persistent (non-off-the-record) profile, headed
 * Chrome over the ozone headless compositor — fires beforeinstallprompt with
 * no DISPLAY, identically here and in CI. Launched from inside the test on
 * purpose: no shared config changes, and the lane's fixture browsers stay
 * exactly as the other specs see them.
 */
async function withInstallableBrowser(
  h: ShellHarness,
  body: (page: Page) => Promise<void>
): Promise<void> {
  const dir = mkdtempSync(join(tmpdir(), 'golden-pwa-'));
  const ctx = await chromium.launchPersistentContext(dir, {
    headless: false,
    args: ['--ozone-platform=headless'],
  });
  try {
    await ctx.addInitScript(BIP_COUNTER_SCRIPT);
    const page = ctx.pages()[0] ?? (await ctx.newPage());
    await page.goto(`${h.ui}/`, { waitUntil: 'commit' });
    await body(page);
  } finally {
    await ctx.close().catch(() => {});
    rmSync(dir, { recursive: true, force: true });
  }
}

test.describe('golden path: pwa install prompt @critical', () => {
  test('the lane browser can never light the prompt: lane-shaped context stays dark past every gate', async ({
    page,
  }) => {
    test.setTimeout(60_000);
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // No dwell is needed for the negative and none is begged for: with the
    // event machinery demonstrably ALIVE in this same Chromium (the profile
    // flags differ — the other test in this file proves events fire when the
    // profile is real), the difference is constant, so one lane-shaped walk
    // past the component's own thresholds is the shipped lane reality.
    await page.addInitScript(BIP_COUNTER_SCRIPT);
    await page.goto(`${h.ui}/`, { waitUntil: 'commit' });
    await page.waitForTimeout(12_000); // covers Chrome's >=10 s engagement heuristic
    await page.reload({ waitUntil: 'commit' }); // visit 2 of the lane context's document ledger
    await page.waitForTimeout(4_000);
    expect(await readBip(page)).toBe(0); // ephemeral profile: Chrome's audit says "in-incognito" headed; headless emits nothing
    expect(await page.locator('[data-testid="install-prompt"]').count()).toBe(0);
    const jar = await readJar(page);
    expect(jar['pwa-visit-count']).toBe('2'); // the component DID mount and count — only the event is missing
    expect(jar['pwa-installed']).toBe(null);
    // The guard tripwire: arming an interception on this page must THROW, i.e.
    // this spec ran live traffic through the lane's own armed machinery.
    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('installable stack: event fires, visit 2 past 30s paints the banner; Install dead-ends at the native dialog; Not now is remembered', async () => {
    test.setTimeout(240_000);
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await withInstallableBrowser(h, async (page) => {
      // --- Visit 1: the EVENT arrives (engine-side), the component withholds
      // the banner — 1 visit is under minVisits=2 (:189). The component is
      // right to wait; the row's "after enough visits" IS this gate.
      await page.waitForTimeout(8_000);
      expect(await readBip(page)).toBeGreaterThanOrEqual(1);
      let jar = await readJar(page);
      expect(jar['pwa-visit-count']).toBe('1');
      expect(jar['pwa-install-dismissed']).toBe(null);
      expect(await page.locator('[data-testid="install-prompt"]').count()).toBe(0);

      // --- Visit 2: dwell past BOTH engagement gates (>=30 s must elapse on
      // THIS document; the per-second re-check interval only exists once an
      // event was deferred, :264-284).
      await page.reload({ waitUntil: 'commit' });
      await expect
        .poll(
          () => page.evaluate(() => !!document.querySelector('[data-testid="install-prompt"]')),
          {
            timeout: 40_000,
            message: 'banner never painted on visit 2 past the engagement window',
          }
        )
        .toBe(true);
      jar = await readJar(page);
      expect(jar['pwa-visit-count']).toBe('2');
      const banner = page.getByTestId('install-prompt');
      await expect(banner.locator('h3')).toHaveText('Install Security Dashboard');
      await expect(banner.locator('p')).toHaveText('Get quick access and offline viewing');
      await expect(page.getByTestId('install-prompt-icon')).toBeVisible();
      // a real dialog with its accessible name chain (aria-labelledby :294-296)
      await expect(page.getByRole('dialog', { name: 'Install Security Dashboard' })).toBeVisible();

      // --- "installs": the leg the WEB cannot finish, asserted as measured
      // fact rather than claimed (ruling 86). The shipped handler calls
      // deferredPrompt.prompt() and awaits userChoice; with no human at the
      // native dialog the choice never resolves — so the component neither
      // marks installed (:231-233) nor runs its cleanup (:236-237). The
      // button is enabled and IS the install path; the dead end is the
      // platform boundary, not a wiring bug.
      await banner.getByRole('button', { name: 'Install', exact: true }).click();
      await page.waitForTimeout(6_000);
      jar = await readJar(page);
      expect(jar['pwa-installed']).toBe(null); // markInstalled has no reachable writer without a resolved accepted choice
      expect(await banner.count()).toBe(1); // prompt() pending => banner stays up
      expect(jar['pwa-install-dismissed']).toBe(null); // Install is NOT a dismissal

      // Chrome's pending native install dialog HOLDS THE PAGE'S INPUT while
      // it waits for the user (a real user must answer the dialog before the
      // page answers anything again; probes 8/9 measured it: a REAL click on
      // "Not now" lands nowhere — no handler, no jar write, no error). The
      // synthetic click below bypasses input delivery to prove the HANDLER
      // wiring: handleDismiss (:244-247) hides the banner and stamps the
      // cooldown. The real-gesture dismissal is proven one document later,
      // where no dialog is pending.
      await expect(async () => {
        await page.evaluate(() => {
          // A compound selector types as Element (no .click), so cast the hit.
          const btn = [...document.querySelectorAll('[data-testid="install-prompt"] button')].find(
            (x) => x.textContent?.trim() === 'Not now'
          ) as HTMLElement | undefined;
          btn?.click();
        });
        await expect(banner).toHaveCount(0, { timeout: 2_000 });
      }).toPass({ timeout: 10_000 });
      jar = await readJar(page);
      expect(Number(jar['pwa-install-dismissed'])).toBeGreaterThan(0);
      const stamp = jar['pwa-install-dismissed'];

      // --- "(remembered)": visit 3 is a FRESH document that clears BOTH
      // engagement gates again (33 s > 30 s, 3 visits >= 2) and the banner
      // still stays dark — isRecentlyDismissed short-circuits the check (:184)
      // for the 7-day cooldown. Without this, every reload would nag.
      await page.reload({ waitUntil: 'commit' });
      await page.waitForTimeout(33_000);
      jar = await readJar(page);
      expect(jar['pwa-visit-count']).toBe('3');
      expect(jar['pwa-install-dismissed']).toBe(stamp); // dismissal survives reloads
      expect(jar['pwa-installed']).toBe(null);
      expect(await page.locator('[data-testid="install-prompt"]').count()).toBe(0);

      // --- The cooldown is a COOLDOWN, not a mute (and the dismissal's own
      // real-gesture leg): write the timestamp the 8-day-old shape the
      // shipped check itself defines as expired (Date.now() - 8d fails
      // isRecentlyDismissed :131-138), reload, clear the engagement gates
      // again — the banner RETURNS, and here, with no native dialog pending
      // on this document, a REAL click on "Not now" hides it and re-stamps.
      await page.evaluate(() => {
        localStorage.setItem('pwa-install-dismissed', String(Date.now() - 8 * 24 * 60 * 60 * 1000));
      });
      await page.reload({ waitUntil: 'commit' });
      await expect
        .poll(
          () => page.evaluate(() => !!document.querySelector('[data-testid="install-prompt"]')),
          {
            timeout: 40_000,
            message: 'banner never returned after the cooldown expired',
          }
        )
        .toBe(true);
      jar = await readJar(page);
      expect(jar['pwa-visit-count']).toBe('4');
      await banner.getByRole('button', { name: 'Not now', exact: true }).click(); // real gesture — no dialog pending here
      await expect(banner).toHaveCount(0, { timeout: 5_000 });
      const restamped = (await readJar(page))['pwa-install-dismissed'];
      expect(Number(restamped)).toBeGreaterThan(0);
      expect(restamped).not.toBe(stamp); // a fresh stamp starts the 7 days again
      // No closedByGuard(page) HERE on purpose: this page belongs to the
      // self-launched unpatched context, where page.route would INSTALL real
      // interception; this spec never calls it on that page in either test.
    });
  });
});
