/**
 * F2.1 golden-path guard (20-frontend.md §F2.1).
 *
 * A golden path is an unmocked spec that drives a feature end to end against
 * the stack the feature-check harness (scripts/feature-check.sh, O2.2) brings
 * up. The guard makes "unmocked" mechanical: every Page and BrowserContext a
 * golden spec can reach gets the interception entry points —
 * route/unroute/routeFromHAR **and routeWebSocket** — replaced with a throw,
 * and pages spawned from an armed context are armed themselves.
 *
 * Why routeWebSocket: page.route() does not intercept WebSocket upgrades in
 * Playwright — routeWebSocket() is the API that mocks /ws. Guarding only the
 * route family would satisfy the letter of "fails any spec calling page.route
 * on /api or /ws" while leaving the one call that CAN fake the live event
 * feed wide open.
 *
 * Why instance patching instead of wrapping: Playwright hands out the SAME
 * BrowserContext object through every acquisition path ({ context } fixture,
 * page.context()), so shadowing the methods as own properties on the instance
 * (probed on Playwright 1.63: instances are extensible and the methods live on
 * the prototype, so own properties win at every ordinary call site) arms all
 * paths at once. A wrapper object would have to be injected at each path and
 * can be missed — the fresh-context review measured exactly that miss with the
 * destructured context fixture.
 *
 * Why the guard throws *from* the interception call instead of failing the run
 * afterwards: the Done-when asks for a green `golden` run AND a deliberately
 * mocked spec that "fails the guard". Those are only compatible if the tripwire
 * spec can attempt a mock and assert the throw — proof the guard fires, in a
 * green test. A post-hoc run failure would turn that proof into a permanently
 * red project.
 *
 * A spec can still defeat the guard (walk the prototype, build its own context
 * from the browser fixture, spawn its own browser). That is the same trust a
 * `test.skip` already gets from this repo; the guard's job is to make the
 * accidental and the lazy mock impossible and the deliberate mock loud, not to
 * be a hostile-code sandbox.
 */
import { test as base, type BrowserContext, type Page } from '@playwright/test';

/** Exact message the guard throws. Tests name it; drift here fails them loudly. */
export const GUARD_MESSAGE =
  'golden paths are unmocked: route interception is blocked in the golden project (20-frontend.md F2.1)';

/** Every entry point that can install an interception on live traffic. */
const INTERCEPTION_METHODS = ['route', 'unroute', 'routeFromHAR', 'routeWebSocket'] as const;

/** Idempotence mark: the page fixture and the patched context.newPage can both reach a page. */
const ARMED = Symbol('goldenGuardArmed');

function guarded(): never {
  throw new Error(GUARD_MESSAGE);
}

function armContext(context: BrowserContext): void {
  const instance = context as BrowserContext & { [ARMED]?: true };
  if (instance[ARMED]) return;
  instance[ARMED] = true;
  for (const method of INTERCEPTION_METHODS) {
    (instance as unknown as Record<string, unknown>)[method] = guarded;
  }
  const realNewPage = context.newPage.bind(context);
  context.newPage = async () => {
    const spawned = await realNewPage();
    armPage(spawned);
    return spawned;
  };
}

function armPage(page: Page): void {
  const instance = page as Page & { [ARMED]?: true };
  if (instance[ARMED]) return;
  instance[ARMED] = true;
  for (const method of INTERCEPTION_METHODS) {
    (instance as unknown as Record<string, unknown>)[method] = guarded;
  }
  const realContext = page.context.bind(page);
  page.context = () => {
    const context = realContext();
    armContext(context); // lazy: the context is armed even if only page.context() is ever called
    return context;
  };
}

/**
 * The golden project's `test`. Same API surface as @playwright/test, plus the
 * armed `page` and `context` fixtures. Deliberately does NOT inherit the e2e
 * fixtures in tests/e2e/fixtures — those auto-mock, which is what this guard
 * exists to forbid. Both fixtures arm the REAL instances (the built-in page
 * fixture is born from the same context this override returns), so a spec
 * cannot dodge the guard by choosing a different fixture. The tour-disabling
 * localStorage is the real state the app itself writes (the same keys the e2e
 * globalSetup bakes into storageState.json), seeded with addInitScript so
 * golden pages never show the Joyride overlay — a genuine user action
 * replayed, not an API mock.
 */
export const test = base.extend<{ page: Page; context: BrowserContext }>({
  context: async ({ context }, use) => {
    armContext(context);
    await use(context);
  },
  page: async ({ page }, use) => {
    armPage(page);
    await page.addInitScript(() => {
      try {
        if (window.location.protocol.startsWith('http')) {
          localStorage.setItem('nemotron-tour-completed', 'true');
          localStorage.setItem('nemotron-tour-skipped', 'true');
        }
      } catch {
        // Opaque origins (about:blank) have no localStorage; nothing to skip there.
      }
    });
    await use(page);
  },
});

export { expect } from '@playwright/test';
