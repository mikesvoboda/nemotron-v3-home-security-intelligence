/**
 * FE-1 golden paths (F2.3): the auth gate and the two public pages in front
 * of it — F-001 (login form), F-003 (ProtectedRoute redirect), F-004 (the
 * client-side 404).
 *
 * What is provable on the harness stack, decided from shipped code before
 * writing (each claim cites where):
 *
 * - ProtectedRoute sends an unauthenticated visitor to /login with the
 *   intended destination in location state (`authRequired !== false &&
 *   !isAuthenticated` → `Navigate to="/login" state={{from: location.pathname}}`,
 *   frontend/src/components/auth/ProtectedRoute.tsx:90-93), and to /setup only
 *   when setup is required (:78). The harness registers its first admin during
 *   bring-up (scripts/feature_check.py register_admin), so on this stack
 *   setup_required is false and the /login branch is the live one.
 * - auth_required comes from GET /api/auth/setup-status (`settings.expose_lan`
 *   published as `auth_required`, backend/api/routes/auth.py:113 area). The CI
 *   compose ships no EXPOSE_LAN, so on THIS stack the gate is down
 *   (auth_required false) and an anonymous visitor may legitimately land on a
 *   protected page. The redirect leg is therefore decided by the API's own
 *   answer, not hardcoded: gate up → bounce + return-to-destination after the
 *   form login; gate down → the fail-closed reading of the same code, with a
 *   real login still required to prove /me. Asserting a bounce unconditionally
 *   would assert deployment config, not the feature — and would be RED on the
 *   very stack it runs on.
 * - LoginPage: submit button text is 'Sign In' (:290); a failed login renders
 *   apiError in a role=alert div (:214-217); on success it navigates to
 *   location.state.from ?? '/' (:110) — F-001's "lands on the page they were
 *   bounced from" clause, which is also F-003's other half.
 * - NotFoundPage is client-only: `path="*"` inside the protected tree
 *   (frontend/src/App.tsx), renders data-testid="not-found-page" and a
 *   "Return to Dashboard" button (frontend/src/pages/NotFoundPage.tsx:55).
 */
import { GUARD_MESSAGE, expect, test } from '../guard';
import {
  closedByGuard,
  loginAsAdmin,
  quietBoot,
  readShellHarness,
  seedTourDismissed,
} from './harness';

const harness = readShellHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

interface SetupStatus {
  setup_required: boolean;
  auth_required?: boolean;
}

test.describe('golden path: auth gate, login form, 404 @critical', () => {
  test.setTimeout(60_000);

  test('F-001: a wrong credential errors on the form; the right one navigates and /api/auth/me answers', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // The product tour's overlay covers /login too on a fresh context; see harness.
    await seedTourDismissed(page);

    // The gate's precondition, mirrored rather than assumed.
    const status = await fetch(`${h.api}/api/auth/setup-status`).then(
      (r) => r.json() as Promise<SetupStatus>
    );
    expect(typeof status.setup_required).toBe('boolean');

    // quietBoot: this boot's setup-status must not be shed by the shared
    // nginx burst (harness.ts); a shed boot fails ProtectedRoute closed.
    await quietBoot(page, h, '/login');

    // Wrong password: the form survives and says so — role=alert from
    // LoginPage's apiError branch; still on /login, not a blank page.
    await page.getByLabel('Username').fill(h.admin.username);
    await page.getByLabel('Password').fill('definitely-not-the-harness-password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
    await expect(page).toHaveURL(/\/login/);

    // The real credential through the SAME form: navigates off /login, and the
    // shell mounts (data-testid="header-branding" is Header.tsx, which renders
    // only inside the protected Layout tree).
    await page.getByLabel('Password').fill(h.admin.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByTestId('header-branding')).toBeVisible({ timeout: 20_000 });
    await expect(page).toHaveURL(new RegExp(`^${h.ui.replace('/', '\\/')}(?!/login)`), {
      timeout: 5_000,
    });

    // The cookie the FORM produced is real backend state: /api/auth/me
    // answers for it (F-001's chain: login → Redis session:<id> → get_me →
    // users), read through the BROWSER's own transport, not page.request.
    // Measured on the probe stack: with the form cookie in the jar
    // (session_id, Secure — the backend default, backend/core/config.py:550),
    // an in-page fetch('/api/auth/me') answers 200 while page.request answers
    // 401 on the same context. Cause: Chromium treats http://127.0.0.1 as a
    // trustworthy origin and sends Secure cookies over plain http loopback;
    // page.request is a Node-side transport that does not grant loopback that
    // exemption and drops the Secure cookie. CI's harness URLs are also
    // http://127.0.0.1:<port>, so page.request would be born red there too —
    // measuring Playwright's cookie partitioning, not the feature. The app's
    // own client is a browser fetch (api.ts BASE_URL '' — relative, same
    // origin), so the honest instrument is the same fetch from the page.
    const meBody = await page
      .evaluate(async () => {
        const r = await fetch('/api/auth/me');
        return { status: r.status, body: await r.text() };
      })
      .then((r) => {
        expect(r.status).toBe(200);
        return r.body;
      });
    expect(meBody).toContain(h.admin.username);

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-003: an unauthenticated visit to a protected route follows the gate the API declares', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // The product tour's overlay covers /login too on a fresh context; see harness.
    await seedTourDismissed(page);

    const status = await fetch(`${h.api}/api/auth/setup-status`).then(
      (r) => r.json() as Promise<SetupStatus>
    );
    await quietBoot(page, h, '/timeline');

    if (status.auth_required !== false) {
      // Gate up: bounced to /login WITH the destination in location state
      // (ProtectedRoute:90-93); logging in from there must RETURN to
      // /timeline (LoginPage:110 navigate(from)). The bounce clause end to end.
      await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
      await page.getByLabel('Username').fill(h.admin.username);
      await page.getByLabel('Password').fill(h.admin.password);
      await page.getByRole('button', { name: 'Sign In' }).click();
      await expect(page).toHaveURL(/\/timeline/, { timeout: 20_000 });
    } else {
      // Gate down on this stack (no EXPOSE_LAN in docker-compose.ci.yml):
      // ProtectedRoute's `authRequired !== false &&` guard short-circuits and
      // the page renders anonymously. What the row still must prove: the gate
      // machinery evaluated without crashing to /setup and without a redirect
      // loop — the URL stays where it was sent. Measured both ways on the
      // probe stack (2026-10-11): this branch green as-is, and the branch
      // above green on the same spec after restarting the backend with
      // EXPOSE_LAN=true — setup-status then answers auth_required:true, the
      // bounce to /login fires and the form login returns to /timeline. The
      // flag cannot be flipped through the app (get_settings is @cache'd,
      // backend/core/config.py:3494, and no route writes expose_lan), so the
      // gate-up leg is deployment-configuration territory: this spec covers
      // whichever way the running stack says it is, and the harness ships it
      // down. If the owner wants a gate-up job in CI, that is a compose
      // decision for a separate PR, not something this spec can arrange.
      await expect(page).toHaveURL(/\/timeline/, { timeout: 15_000 });
    }

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });

  test('F-004: an unmatched route renders the 404 and its button returns to the dashboard', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    // The product tour's overlay covers /login too on a fresh context; see harness.
    await seedTourDismissed(page);

    // The catch-all lives INSIDE the protected tree (App.tsx path="*" under
    // ProtectedRoute), so authenticate first — cookie from a real login, the
    // same way every other golden path here does.
    await loginAsAdmin(page, h);
    await quietBoot(page, h, '/no-such-page');
    await expect(page.getByTestId('not-found-page')).toBeVisible({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Return to Dashboard' }).click();
    await expect(page).toHaveURL(`${h.ui}/`, { timeout: 15_000 });
    await expect(page.getByTestId('header-branding')).toBeVisible();

    expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE);
  });
});
