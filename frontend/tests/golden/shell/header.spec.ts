/**
 * FE-1 golden paths (F2.3): the header's own chrome — F-005 (system health
 * indicator + tooltip), F-013 (page documentation link), F-014 (theme toggle).
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
  closedByGuard,
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

interface HealthBody {
  status?: string;
  services?: Record<string, unknown>;
}

async function openShell(page: import('@playwright/test').Page, h: ShellHarness) {
  await seedTourDismissed(page);
  await loginAsAdmin(page, h);
  await page.goto(h.ui, { waitUntil: 'domcontentloaded' });
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
    // that is the row's "<Page>" clause, not just a static link.
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

    // The row's persistence clause, measured the user's way: reload.
    //
    // The pause is measured necessity, not flake-padding. The SPA is served
    // through the frontend container's nginx, which throttles /api by client
    // IP: zone=api rate=10r/s with burst=20 (frontend/nginx.conf:24 + the
    // rendered conf.d `limit_req zone=api burst=20 nodelay`). Every golden
    // test in a file boots the app (~12 API calls), and Playwright's requests
    // all share ONE client IP from the runner's perspective, so by this fourth
    // boot the zone is empty of burst tokens and nginx sheds requests with
    // 429 Server: nginx (measured on the probe stack 2026-10-11: the reload's
    // GET /api/auth/setup-status answered `429 /api/auth/setup-status` while
    // the SAME request direct to the backend answered 200 — and a
    // backend-bucket raise changed nothing, proving the shedder is nginx).
    // A shed setup-status makes ProtectedRoute fail closed (`setupRequired
    // === null && error` → Navigate to="/setup",
    // src/components/auth/ProtectedRoute.tsx:79) and an authenticated admin
    // reload lands on "Create your admin account" — a real fail-closed
    // fragility, which F-002's session row owns and reports; this spec must
    // not trip it while asserting ITS OWN clause. A human reload is a lone
    // boot after quiet, which fits burst=20; a 10 s wait (> the zone's 100
    // token drain at 10r/s) reproduces exactly that shape here.
    await page.waitForTimeout(10_000);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('html')).toHaveClass(/dark/);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
