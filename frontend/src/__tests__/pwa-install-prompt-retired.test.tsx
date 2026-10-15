/**
 * [r133] guard: the in-page PWA install prompt is retired (ruling 133).
 *
 * Two legs, one per package box.
 *
 *  A. DELETE — the component, its barrel and its directory are gone, and the
 *     app paints no install surface even when every engagement gate the
 *     deleted component enforced is armed from the DOM side: a seeded
 *     `pwa-visit-count` (its `DEFAULT_MIN_VISITS = 2` gate), a `Date.now`
 *     shifted past its `DEFAULT_MIN_TIME_ON_SITE = 30000` gate, and a
 *     dispatched `beforeinstallprompt`. This arms the gates through
 *     localStorage/Date/the event — never by importing the doomed module —
 *     so the leg is red while `App.tsx` still mounts `<InstallPrompt />`
 *     (all four conditions then paint the banner, as the now-deleted golden
 *     spec `tests/golden/shell/pwa-install.spec.ts` proved on visit 2) and
 *     green once it cannot. A plain
 *     "no `install-prompt` testid" without the arming would be
 *     vacuous-by-construction after the deletion (the rate-limit spec's
 *     `retiredSurface` comment names that trap); the arming is what makes the
 *     absence mean "nothing can light this", and it keeps the leg meaningful
 *     forever: a reintroduced prompt trips it again.
 *  B. KEEP — `public/manifest.json` and the service-worker registration file
 *     survive. Box 2's subject, pinned by exact path. The registration's own
 *     behaviour stays witnessed where it already was: the unit
 *     `services/serviceWorkerRegistration.test.ts` and the golden
 *     `tests/golden/shell/offline-cache.spec.ts` (F-027), which is why
 *     deleting the prompt's spec orphans nothing.
 *
 * Why exact paths and not the `no-browser-api-key.test.ts` filesystem walk:
 * a walk of `frontend/` selects whatever is on disk, including gitignored
 * local scratch that carries these identifiers (this lane's probe dirs sit
 * under `frontend/`), which would read red on a dev machine and green in CI.
 * An exact path selects nothing — it is the same fact on every machine.
 *
 * Why no mutation kill-loss ledger (`01-mutation-policy.md` §The scored set):
 * the zero-kill-loss protocol binds test-only PRs against a scored module;
 * this PR changes production bytes, so its mutant set changes with the code,
 * and UR-16 settles the battery's future: deleted with its module in
 * Phase 3, which is this act.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { act, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { server } from '../mocks/server';
import { STANDARD_TIMEOUT } from '../test/setup';

// The App-render harness App.test.tsx uses: Layout/Dashboard mocked, the
// auth boot stubbed, so ProtectedRoute mounts the real tree instead of
// parking on its spinner. The deleted component mounted as a direct child of
// AnnouncementProvider, outside the router — at `1f6405610:frontend/src/App.tsx:358`
// (revision-qualified on purpose: a bare `App.tsx:358` pointed at that mount
// until this PR deleted it, and now names `<ReactQueryDevtools />` instead).
// The mount witness below needs the layout, and sharing the proven harness
// beats re-deriving one.
const mockUser = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  created_at: '2024-01-01T00:00:00Z',
};

vi.mock('../components/layout/Layout', () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="mock-layout">
      <div data-testid="layout-children">{children}</div>
    </div>
  ),
}));

vi.mock('../components/dashboard/DashboardPage', () => ({
  default: () => <div data-testid="mock-dashboard">Dashboard Page Content</div>,
}));

vi.mock('../components/common', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../components/common')>();
  return {
    ...actual,
    ChunkLoadErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    RouteLoadingFallback: () => <div data-testid="route-loading">Loading...</div>,
    AmbientStatusProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '..'); // frontend/src/
const FE = path.resolve(SRC, '..'); // frontend/

describe('[r133] the in-page PWA install prompt is retired (ruling 133)', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/auth/setup-status', () => HttpResponse.json({ setup_required: false })),
      http.get('/api/auth/me', () => HttpResponse.json(mockUser))
    );
    // Arm the deleted component's visit gate: it incremented on mount and
    // showed at >= 2, so seeding 2 means its ref cleared the gate after
    // mounting. setup.ts's afterEach clears localStorage before each test.
    localStorage.setItem('pwa-visit-count', '2');
  });

  it('leg A: the component, its barrel and its directory no longer exist', () => {
    // Anti-vacuity: the exact-path reads below run against a real tree.
    expect(fs.existsSync(path.join(SRC, 'App.tsx'))).toBe(true);
    // SAFE for this file's purpose (a guard pinning deleted paths): every
    // path is path.resolve/path.join of a directory baked in at authoring;
    // no input ever enters them. (no-browser-api-key.test.ts carries an
    // eslint-disable for the same shape; this file's project does not trip
    // that rule, so the directive would report as unused.)
    const pwaDir = path.join(SRC, 'components', 'pwa');
    expect(fs.existsSync(path.join(pwaDir, 'InstallPrompt.tsx'))).toBe(false);
    expect(fs.existsSync(path.join(pwaDir, 'index.ts'))).toBe(false);
    // The directory itself goes with it: after the deletion it holds no
    // component, and the barrel had zero exports left (the package body's
    // measured correction). components/AGENTS.md keeps no pwa/ row, so the
    // AGENTS.md validator's dead-reference arm (zero tolerance since W1.3)
    // is what stops a stale pointer surviving this deletion.
    expect(fs.existsSync(pwaDir)).toBe(false);
  });

  it('leg A: no install surface paints with every engagement gate armed', async () => {
    render(<App />);
    // Anti-vacuity for the absence below: the app tree really mounted.
    await waitFor(
      () => expect(screen.getByTestId('mock-layout')).toBeInTheDocument(),
      STANDARD_TIMEOUT
    );

    const nowSpy = vi.spyOn(Date, 'now');
    try {
      // startTimeRef took the real clock during mount (which finished before
      // this line). Shifting by +60 s off the CURRENT real now therefore
      // guarantees `Date.now() - startTimeRef >= 60000 >= 30000` regardless of
      // how long render took — the +30 s a naive shift uses sits UNDER the
      // `>= minTimeOnSite` gate by exactly the render time and paints nothing
      // (measured: the first cut of this guard passed vacuously that way).
      nowSpy.mockReturnValue(Date.now() + 60000);
      await act(async () => {
        const installEvent = new Event('beforeinstallprompt', { cancelable: true });
        Object.assign(installEvent, {
          // Shape the deleted component's BeforeInstallPromptEvent type
          // demanded. Not async: the component never awaits prompt() on this
          // path, and an empty async arrow trips @typescript-eslint/require-await.
          prompt: () => Promise.resolve(),
          userChoice: Promise.resolve({ outcome: 'dismissed', platform: 'web' }),
        });
        window.dispatchEvent(installEvent);
        // Flush the setState the event listener queued, so the banner would
        // have painted before the absence assertions below run.
        await Promise.resolve();
      });
    } finally {
      nowSpy.mockRestore();
    }

    // The deleted banner's exact surface: the two testids and both copy
    // strings the component rendered, copied out of it before deletion.
    expect(screen.queryByTestId('install-prompt')).toBeNull();
    expect(screen.queryByTestId('install-prompt-icon')).toBeNull();
    expect(document.body.textContent).not.toContain('Install Security Dashboard');
    expect(document.body.textContent).not.toContain('Get quick access and offline viewing');
  });

  it('leg B: the install platform the package keeps survives by exact path', () => {
    // Box 2 ("Keep manifest.json, /sw.js and their registration"). /sw.js is
    // a build output (frontend/dist/sw.js), not a checked-in file, so the
    // registrable facts here are the manifest and the registration module;
    // the registration's behaviour stays witnessed by
    // services/serviceWorkerRegistration.test.ts (unit) and
    // tests/golden/shell/offline-cache.spec.ts (golden, F-027).
    expect(fs.existsSync(path.join(FE, 'public', 'manifest.json'))).toBe(true);
    expect(fs.existsSync(path.join(SRC, 'services', 'serviceWorkerRegistration.ts'))).toBe(true);
  });
});
