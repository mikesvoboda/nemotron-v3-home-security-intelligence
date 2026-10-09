/**
 * F1.3: the login screen appears only when the backend reports auth required.
 *
 * B1.5 put the flag in the setup-status body
 * (backend/api/routes/auth.py:125-128 at origin/main e9ec74ef:
 * `auth_required=get_settings().expose_lan`, schema field documented "The
 * frontend shows its login screen only when this is true").
 *
 * Today `AuthContext` never reads that flag and `ProtectedRoute.tsx:84`
 * redirects on `!isAuthenticated` alone — so with `EXPOSE_LAN` unset (the
 * flag false) the guard still fetches `/api/auth/me`, still gets its route
 * guard's "Not authenticated" 401, and still bounces to the login page. The
 * package's Done when says that run must show no login at all.
 */
import { IsRestoringProvider, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { useEffect, useState } from 'react';
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
  useLocation,
} from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProtectedRoute from './ProtectedRoute';
import { AuthProvider } from '../../contexts/AuthContext';
import { server } from '../../mocks/server';
import LoginPage from '../../pages/LoginPage';

import type { SetupStatusResponse } from '../../services/authApi';
import type { ReactNode } from 'react';

const mockUser = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  created_at: '2024-01-01T00:00:00Z',
};

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="current-path">{location.pathname}</div>;
}

/** The page under test: one guarded route plus a readout of where we ended up. */
function guardedPage() {
  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <div>Protected Content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
      <LocationDisplay />
    </>
  );
}

/**
 * App shell: the guard's redirect destinations (/login, /setup) exist here,
 * and the test's own routes render as children of the same MemoryRouter.
 */
function createWrapper(initialPath = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/setup" element={<div>Setup Form</div>} />
            </Routes>
            {children}
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  };
}

/** Serve the gate's own setup-status shape: both flags, as routes/auth.py does. */
function stubSetupStatus(body: Record<string, unknown>) {
  server.use(
    http.get('/api/auth/setup-status', () =>
      HttpResponse.json(body as unknown as SetupStatusResponse)
    )
  );
}

function notAuthenticated() {
  return new HttpResponse(JSON.stringify({ detail: 'Not authenticated' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('login gate follows the backend auth_required flag (F1.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('EXPOSE_LAN unset — auth_required false', () => {
    it('renders the protected content with no login and no /api/auth/me round trip', async () => {
      const meHandler = vi.fn();
      stubSetupStatus({ setup_required: false, auth_required: false });
      server.use(
        http.get('/api/auth/me', () => {
          meHandler();
          // What the route guard answers today with no session: 401.
          return notAuthenticated();
        })
      );

      render(guardedPage(), { wrapper: createWrapper() });

      await waitFor(() => expect(screen.getByText('Protected Content')).toBeInTheDocument());
      expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
      expect(screen.getByTestId('current-path')).toHaveTextContent('/');
      // Nothing is being gated, so nothing asks who the user is.
      expect(meHandler).not.toHaveBeenCalled();
    });
  });

  describe('EXPOSE_LAN=true — auth_required true', () => {
    it('routes an unauthenticated visitor to the login screen', async () => {
      stubSetupStatus({ setup_required: false, auth_required: true });
      server.use(http.get('/api/auth/me', () => notAuthenticated()));

      render(guardedPage(), { wrapper: createWrapper() });

      await waitFor(() => expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument());
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('renders the protected content once the session checks out', async () => {
      stubSetupStatus({ setup_required: false, auth_required: true });
      server.use(http.get('/api/auth/me', () => HttpResponse.json(mockUser)));

      render(guardedPage(), { wrapper: createWrapper() });

      await waitFor(() => expect(screen.getByText('Protected Content')).toBeInTheDocument());
    });
  });

  describe('a backend predating the flag', () => {
    it('fails closed: absence of auth_required is treated as required', async () => {
      // Endpoints predate B1.5, so /api/auth/login still works and the login
      // screen is reachable; guessing "open" would expose the UI instead.
      stubSetupStatus({ setup_required: false });
      server.use(http.get('/api/auth/me', () => notAuthenticated()));

      render(guardedPage(), { wrapper: createWrapper() });

      await waitFor(() => expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument());
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  /**
   * Regression (live-stack run, 2026-10-09): the persisted-query restore window
   * must not bounce. The live app mounts under PersistQueryClientProvider, which
   * renders children while the cache hydrates; a query that is restored-but-not
   * yet refetching reports isLoading FALSE (React Query v5: isLoading =
   * isPending && isFetching), so the guard used to evaluate an unanswered
   * setup-status as "answered, no user" and redirect to /login ~143 ms after
   * mount — before the response even existed. Observed with EXPOSE_LAN unset,
   * where the Done when forbids any login screen. The cache entry below is the
   * exact state hydration produces: built (pending, idle), no data.
   */
  describe('setup-status still in flight', () => {
    /**
     * This regression must be asserted on the router's TRANSITION log, not on
     * final rendered state. The bad commit lasts one frame: the guard's first
     * render happens with setup-status unanswered (in the browser, before the
     * mount fetch even starts), <Navigate replace> commits, and once the URL is
     * /login the guarded route no longer matches so nothing brings it back.
     * act() flushes that whole sequence before any assertion can observe the
     * intermediate state — a first draft of this test built a pending cache
     * entry and passed at the pre-fix code precisely because it looked only at
     * where the run ENDED. The router.subscribe log below sees every location
     * the app visited, including the one-frame visit that ended the live run 2
     * on /login with EXPOSE_LAN unset.
     */
    it('never routes through /login while the cache is still restoring', async () => {
      // Faithful reproduction of the live cold start: the app mounts under
      // PersistQueryClientProvider, whose IsRestoringProvider(true) makes
      // useBaseQuery skip subscribing (react-query's _optimisticResults
      // 'isRestoring' path), so setup-status reads as pending/idle — NOT
      // loading — while the restore is in progress. A first draft of this test
      // pre-built a pending cache entry instead, and passed at the pre-fix
      // code: with no subscriber, act() never issued the fetch, so the bad
      // frame ended in exactly the place the fix makes it end.
      stubSetupStatus({ setup_required: false, auth_required: false });
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
      });

      function RestoreGate({ children }: { children: ReactNode }) {
        // Opens when AuthProvider's mount effect has run (the restore resolves),
        // mirroring the provider flipping isRestoring false in a browser paint.
        const [restoring, setRestoring] = useState(true);
        useEffect(() => {
          const t = setTimeout(() => setRestoring(false), 0);
          return () => clearTimeout(t);
        }, []);
        return <IsRestoringProvider value={restoring}>{children}</IsRestoringProvider>;
      }

      const router = createMemoryRouter(
        [
          {
            path: '/',
            element: (
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            ),
          },
          { path: '/login', element: <LoginPage /> },
          { path: '/setup', element: <div>Setup Form</div> },
        ],
        { initialEntries: ['/'] }
      );
      const visited: string[] = [];
      router.subscribe((state) => visited.push(state.location.pathname));

      await act(async () => {
        render(
          <QueryClientProvider client={queryClient}>
            <RestoreGate>
              <AuthProvider>
                <RouterProvider router={router} />
              </AuthProvider>
            </RestoreGate>
          </QueryClientProvider>
        );
        // Let the macrotask queue drain inside act: AuthProvider's mount
        // effect runs, then RestoreGate's timeout flips isRestoring false —
        // the moment react-query subscribes the query and issues the fetch.
        await new Promise((resolve) => setTimeout(resolve, 5));
      });

      await waitFor(() => expect(screen.getByText('Protected Content')).toBeInTheDocument(), {
        timeout: 5000,
      });
      // Not in any frame, intermediate or final: the login route was never the
      // app's location. (router.subscribe fires on LOCATION CHANGES, not on the
      // initial state, so a clean run records nothing at all.)
      expect(visited).not.toContain('/login');
      expect(router.state.location.pathname).toBe('/');
    });
  });

  describe('setup still wins over login', () => {
    it('routes to /setup when setup is required, whatever the auth flag', async () => {
      stubSetupStatus({ setup_required: true, auth_required: true });

      render(guardedPage(), { wrapper: createWrapper() });

      await waitFor(() => expect(screen.getByTestId('current-path')).toHaveTextContent('/setup'));
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });
});
