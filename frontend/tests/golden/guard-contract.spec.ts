/**
 * F2.1 Done-when half 2: "a deliberately mocked spec in it fails the guard"
 * (20-frontend.md §F2.1).
 *
 * This IS the deliberately mocked spec. It tries to mock the API the way every
 * other Playwright spec in this repo does, and asserts the guard rejects each
 * attempt. Done-when half 1 wants the `golden` project green inside O2.2's CI
 * job, so the guard's firing has to be provable by a PASSING test — that is
 * why the guard throws from the interception call itself (see guard.ts) and
 * this spec can hold it to account without reddening the run.
 *
 * The assertions are synchronous (`expect(() => …).toThrow`), not `rejects`,
 * because the guard throws at the call — before any promise exists. A golden
 * spec that forgot to `await` a mock would still fail: that is the point.
 *
 * Out of golden mode (no feature-check stack under us) the suite self-skips:
 * `npx playwright test --project=golden` locally must not run specs against
 * nothing, and CI never invokes the golden project outside the harness.
 */
import { GUARD_MESSAGE, expect, test } from './guard';

const goldenMode = Boolean(process.env.FEATURE_CHECK_UI_URL);
test.skip(
  !goldenMode,
  'golden paths need the feature-check stack (scripts/feature-check.sh --fake)'
);

// Same stack, same guard — just no waiting for a feature, so this stays green
// even while the golden UI is mid-development.
test.describe('golden guard contract @smoke', () => {
  test('page.route() on /api throws the guard', async ({ page }) => {
    expect(() =>
      page.route('**/api/**', (route) => route.fulfill({ status: 200, body: '{}' }))
    ).toThrow(GUARD_MESSAGE);
  });

  test('page.route() on /ws throws the guard', async ({ page }) => {
    expect(() => page.route('**/ws/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
  });

  test('page.routeFromHAR() throws the guard', async ({ page }) => {
    expect(() => page.routeFromHAR('/dev/null')).toThrow(GUARD_MESSAGE);
  });

  test('context.route() throws the guard', async ({ page }) => {
    expect(() =>
      page.context().route('**/api/events', (route) => route.fulfill({ status: 200, body: '[]' }))
    ).toThrow(GUARD_MESSAGE);
  });

  test('page.routeWebSocket() throws the guard', async ({ page }) => {
    // page.route() cannot intercept WebSocket upgrades — routeWebSocket() is
    // the call that CAN mock /ws, so the /ws half of the F2.1 mandate lives
    // and dies here. (Fresh-context review, 2026-10-10: unguarded, this mocked
    // the live event feed with every route-family tripwire still green.)
    expect(() => page.routeWebSocket('**/ws/**', async () => {})).toThrow(GUARD_MESSAGE);
  });

  test('context.routeWebSocket() throws the guard', async ({ page }) => {
    expect(() => page.context().routeWebSocket('**/ws/**', async () => {})).toThrow(GUARD_MESSAGE);
  });

  test('the context fixture itself is armed, not just page.context()', async ({
    page,
    context,
  }) => {
    // House idiom is `test('…', async ({ page, context }) => …)` (see e.g.
    // tests/e2e/specs/ai-audit.spec.ts). Destructuring the context fixture must
    // be as guarded as reaching it through the page.
    expect(context).toBe(page.context());
    expect(() => context.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
    expect(() => context.routeWebSocket('**/ws/**', async () => {})).toThrow(GUARD_MESSAGE);
  });

  test('page.context() cannot smuggle an unarmed page', async ({ page }) => {
    const second = await page.context().newPage();
    expect(() => second.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
  });

  test('the guard does not break ordinary page work', async ({ page }) => {
    // A guard that blocked navigation or reads would fail the real golden path
    // for the wrong reason. The door it closes is interception only.
    await page.goto('about:blank');
    expect(await page.evaluate(() => document.title)).toBe('');
    await page.setContent('<h1 data-testid="still-works">ok</h1>');
    await expect(page.getByTestId('still-works')).toHaveText('ok');
  });
});
