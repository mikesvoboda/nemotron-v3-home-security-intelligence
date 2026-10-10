/**
 * F2.1 golden-path guard (20-frontend.md §F2.1).
 *
 * A golden path is an unmocked spec that drives a feature end to end against
 * the stack the feature-check harness (scripts/feature-check.sh, O2.2) brings
 * up. The guard makes "unmocked" mechanical: every page in the `golden`
 * project gets `route`/`unroute`/`routeFromHAR` replaced with a throw, and the
 * page's `context` is replaced with a proxy that throws on the context-level
 * route entry points too, while passing everything else through untouched.
 *
 * Why the guard throws *from* the interception call instead of failing the run
 * afterwards: the Done-when asks for a green `golden` run AND a deliberately
 * mocked spec that "fails the guard". Those are only compatible if the tripwire
 * spec can attempt a mock and assert the throw — proof the guard fires, in a
 * green test. A post-hoc run failure would turn that proof into a permanently
 * red project.
 *
 * A spec can still defeat the guard (walk the prototype, spawn its own
 * browser). That is the same trust a `test.skip` already gets from this repo;
 * the guard's job is to make the accidental and the lazy mock impossible and
 * the deliberate mock loud, not to be a hostile-code sandbox.
 */
import { test as base, type BrowserContext, type Page } from '@playwright/test';

/** Exact message the guard throws. Tests name it; drift here fails them loudly. */
export const GUARD_MESSAGE =
  'golden paths are unmocked: route interception is blocked in the golden project (20-frontend.md F2.1)';

/** The entry points that can install an interception on live traffic. */
const PAGE_ROUTE_METHODS = ['route', 'unroute', 'routeFromHAR'] as const;
const CONTEXT_ROUTE_METHODS = ['route', 'unroute', 'routeFromHAR'] as const;

function guarded(): never {
  throw new Error(GUARD_MESSAGE);
}

/**
 * Shadow `page.route`-family methods by assignment (measured on Playwright
 * 1.63: the Page instance is extensible and the methods live on the
 * prototype, so an own property wins for every ordinary call site), and wrap
 * `page.context()` in a Proxy that blocks the context-level route entry
 * points — `context.route()` intercepts every page of the context, so patching
 * pages alone would leave the widest mocking door open.
 */
function armGuard(page: Page): void {
  for (const method of PAGE_ROUTE_METHODS) {
    (page as unknown as Record<string, unknown>)[method] = guarded;
  }
  const originalContext = page.context.bind(page);
  const guardTrap = () => guarded();
  const guardedContext = new Proxy(originalContext(), {
    get(target, property, receiver) {
      if ((CONTEXT_ROUTE_METHODS as readonly string[]).includes(String(property))) return guardTrap;
      const value = Reflect.get(target, property, receiver);
      if (property === 'newPage') {
        // Pages spawned from the context get armed too, so the proxy can't be
        // used as a side door to an unarmed page.
        return async () => {
          const spawned = await target.newPage();
          armGuard(spawned);
          return spawned;
        };
      }
      return typeof value === 'function' ? value.bind(target) : value;
    },
  }) as BrowserContext;
  page.context = () => guardedContext;
}

/**
 * The golden project's `test`. Same API surface as @playwright/test, plus the
 * armed `page` fixture. Deliberately does NOT inherit the e2e fixtures in
 * tests/e2e/fixtures — those auto-mock, which is what this guard exists to
 * forbid. The tour-disabling localStorage is the real state the app itself
 * writes (the same keys the e2e globalSetup bakes into storageState.json),
 * seeded with addInitScript so golden pages never show the Joyride overlay —
 * a genuine user action replayed, not an API mock.
 */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, use) => {
    armGuard(page);
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
