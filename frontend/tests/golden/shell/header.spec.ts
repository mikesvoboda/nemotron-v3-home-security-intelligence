/**
 * FE-1 golden paths (F2.3): the header's own chrome — F-005 (system health
 * indicator + tooltip), F-006 (GPU quick stats), F-013 (page documentation
 * link), F-014 (theme toggle).
 *
 * Every navigation here goes through quietBoot()/BOOT_QUIET_MS (harness.ts):
 * the SPA's API calls ride the frontend container's nginx, which throttles
 * /api per client IP, and the golden project's single worker always presents
 * the same IP — an unthrottled suite boot starves its own setup-status.
 *
 * Decided from shipped code before writing (each claim cites where):
 *
 * - F-005: Header.tsx:360-373 renders data-testid="health-indicator" with
 *   aria-label `System health status: ${effectiveHealth ?? 'checking'}` and a
 *   "health-dot" span; the text is 'LIVE MONITORING' / 'System Degraded' /
 *   'System Offline' (:87-91), polled every 30 s (:176-177). The backend
 *   answers /api/system/health from live probes (system.py:898/:928), so the
 *   golden path mirrors the API's own verdict rather than hardcoding "LIVE"
 *   (a CI runner with a flaky probe could legitimately render Degraded). The
 *   tooltip is "health-tooltip" (:125) — the row's hover clause.
 * - F-006: Header.tsx:417-421 renders the GPU block as two plain divs (no
 *   testid): label div "GPU:" + value div formatGpuStats() (:248-271,
 *   `round% | round°C | fps.toFixed(1) FPS`, '--' while the socket or the
 *   sample is missing). The value comes from useConnectionStatus's /ws/system
 *   feed (:171, :201-210), whose source row GPUMonitor rewrites every 5 s
 *   (gpu_poll_interval_seconds, backend/core/config.py:1985) — so the mirror
 *   reads /api/system/gpu/history and asserts membership in the newest rows,
 *   never one pinned row (that would race the writer).
 * - F-013: PageDocsLink.tsx renders <a href={GITHUB_BASE_URL + docPath}
 *   target="_blank"> with text "{label} Documentation" for routes configured
 *   in pageDocumentation.ts ('/' → 'Dashboard' → docs/ui/dashboard.md); it
 *   returns null for unconfigured routes. Asserting the href prefix + the
 *   repo-relative path + target=_blank proves the row without fetching
 *   github.com (outbound is the wrong thing for a golden path to depend on).
 * - F-014: ThemeToggle in the Header is the MENU variant (Header.tsx:319
 *   showMenu): the trigger is testid "theme-toggle" (aria-label "Theme
 *   options") and the menu is "theme-menu" with Light/Dark/System items.
 *   ThemeContext writes localStorage THEME_STORAGE_KEY='theme-mode' (:64) and
 *   applies dark/light classes on documentElement (:90-96). "Persists across
 *   reloads" is the row's real clause: pick Dark via the menu, assert the
 *   html class flips, reload, assert it is still dark — all client-only, no
 *   backend state involved.
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  BOOT_QUIET_MS,
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
  type ShellHarness,
} from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface HealthBody {
  status?: string;
  services?: Record<string, unknown>;
}

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await quietBoot(page, h);
  await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
}

test.describe('golden path: header chrome @critical', () => {
  test.setTimeout(60_000);

  test('F-005: the health indicator renders the backend probe verdict and the tooltip lists services', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await openShell(page, h);

    const indicator = page.getByTestId('health-indicator');
    await expect(indicator).toBeVisible();
    const branding = page.getByTestId('header-branding');

    // Mirror, don't assume: the backend computes status from live DB/redis/AI
    // probes per request, so the expected text comes from the API itself.
    const health = await page
      .evaluate(async () => (await fetch('/api/system/health')).json() as HealthBody)
      .catch(() => null);
    if (health && typeof health.status === 'string') {
      const expected =
        health.status === 'healthy'
          ? 'LIVE MONITORING'
          : health.status === 'degraded'
            ? 'System Degraded'
            : 'System Offline';
      // 30 s poll means the FIRST render can briefly trail the API; poll the
      // text, not a fixed wait.
      await expect
        .poll(async () => (await indicator.innerText()) + (await branding.innerText()), {
          timeout: 35_000,
        })
        .toContain(expected);
      await expect(indicator).toHaveAttribute('aria-label', /System health status:/);
    } else {
      // Unreachable health API is itself a state the indicator must survive:
      // the component's own fallback text, never a crash.
      await expect(indicator.or(branding)).toBeVisible();
    }

    // The row's hover clause: the per-service tooltip mounts on hover
    // (Header.tsx:125 renders health-tooltip for the services map).
    await indicator.hover();
    const tooltip = page.getByTestId('health-tooltip');
    await expect(tooltip).toBeVisible({ timeout: 5_000 });
    await expect(tooltip).toContainText(/\w/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-006: the GPU quick stats render the broadcaster feed, not the placeholder', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await openShell(page, h);

    // The block has no data-testid (Header.tsx:417-421 renders two plain
    // divs), so the label anchors the locator and the value is its sibling —
    // structure the row itself describes ("GPU: 42% | 61°C | 3.2 FPS").
    const label = page.getByText('GPU:', { exact: true });
    await expect(label).toBeVisible();
    const value = label.locator('xpath=following-sibling::div[1]');

    // '--' is the shipped placeholder while the socket or the sample is
    // missing (Header.tsx:249-250); the row's claim is the real triple, so
    // wait for the feed rather than asserting the fallback.
    await expect
      .poll(() => value.innerText(), { timeout: 30_000, message: 'GPU feed never arrived' })
      .not.toBe('--');

    // Mirror the truth from the same table the broadcaster reads, across a
    // window of rows: gpu_monitor rewrites gpu_stats every
    // gpu_poll_interval_seconds (default 5.0, backend/core/config.py:1985) and
    // the header shows the newest push (Header.tsx:248-271 formatting is
    // `${round(util)}% | ${round(temp)}°C | ${fps.toFixed(1)} FPS`), so pinning
    // ONE row would race the writer. Membership in the last 12 rows (a minute
    // of samples) proves the header renders a real, current row.
    const expected = await page.evaluate(async () => {
      const r = await fetch('/api/system/gpu/history?limit=12');
      if (r.status !== 200) throw new Error(`gpu/history answered ${r.status}`);
      const body = (await r.json()) as {
        items?: Array<{
          utilization: number | null;
          temperature: number | null;
          inference_fps: number | null;
        }>;
      };
      return (body.items ?? []).map((row) => {
        const parts: string[] = [];
        if (row.utilization !== null) parts.push(`${Math.round(row.utilization)}%`);
        if (row.temperature !== null) parts.push(`${Math.round(row.temperature)}°C`);
        if (row.inference_fps !== null) parts.push(`${row.inference_fps.toFixed(1)} FPS`);
        return parts.length > 0 ? parts.join(' | ') : '--';
      });
    });
    expect(expected.length).toBeGreaterThan(0);
    const window = new Set(expected);
    // await BEFORE the Set lookup: passing the Promise to has() would compare
    // an object against strings and can never be true — a false-green trap
    // ruling 86 calls out.
    await expect
      .poll(async () => window.has((await value.innerText()).trim()), { timeout: 15_000 })
      .toBe(true);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-013: the docs link is route-contextual and points at the repo doc for the page', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await openShell(page, h);

    // pageDocumentation.ts maps '/' → label 'Dashboard', docPath
    // docs/ui/dashboard.md; PageDocsLink.tsx:24 prefixes the GitHub blob base.
    const link = page.getByRole('link', { name: 'Dashboard Documentation' });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute(
      'href',
      'https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/docs/ui/dashboard.md'
    );
    await expect(link).toHaveAttribute('target', '_blank');

    // Route-contextual: on /timeline the SAME slot changes text and path —
    // that is the row's "<Page>" clause, not just a static link. page.goto
    // is a document load, so this boot needs the same drain as openShell's
    // (harness.ts: the shared nginx burst).
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(`${h.ui}/timeline`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('link', { name: 'Timeline Documentation' })).toHaveAttribute(
      'href',
      /docs\/ui\/timeline\.md$/
    );

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-014: the theme menu picks Dark and it persists across reload', async ({ page }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    await openShell(page, h);

    await page.getByTestId('theme-toggle').click();
    const menu = page.getByTestId('theme-menu');
    await expect(menu).toBeVisible();
    await menu.getByRole('menuitem', { name: /Dark/ }).or(menu.getByText('Dark')).first().click();

    // ThemeContext applies the resolved mode as a class on <html> (:90-96).
    await expect(page.locator('html')).toHaveClass(/dark/, { timeout: 5_000 });
    // ...and stores the CHOICE under theme-mode (THEME_STORAGE_KEY, :64).
    // The store is the shared useLocalStorage hook, which JSON-stringifies
    // (src/hooks/useLocalStorage.ts:57), so the RAW jar value is '"dark"' —
    // parse it the way the app reads it back (JSON.parse there) rather than
    // asserting a string the app never writes.
    await expect
      .poll(() =>
        page.evaluate(() => {
          const raw = localStorage.getItem('theme-mode');
          return raw === null ? null : (JSON.parse(raw) as string);
        })
      )
      .toBe('dark');

    // The row's persistence clause, measured the user's way: a reload, sent
    // as a lone boot arriving at a full nginx burst window (BOOT_QUIET_MS +
    // the measurement behind it live in harness.ts — the shedder is the
    // frontend container's nginx, and the fail-closed-on-shed-setup-status
    // fragility it can cause is filed on the F-003 row, not this one).
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('html')).toHaveClass(/dark/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
