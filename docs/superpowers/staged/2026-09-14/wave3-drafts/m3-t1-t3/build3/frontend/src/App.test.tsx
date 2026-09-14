import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { server } from './mocks/server';
import { FAST_TIMEOUT, STANDARD_TIMEOUT } from './test/setup';

// NEM-5322: App now gates routes through AuthProvider + ProtectedRoute.
// AuthProvider's boot queries (/api/auth/setup-status, then /api/auth/me)
// have NO global msw handlers; under setup.ts's onUnhandledRequest:'bypass'
// they fall through to a real fetch that fails under jsdom, so
// ProtectedRoute sits on its LoadingSpinner forever and no layout/page
// markup ever mounts. Stub the authenticated path (repo idiom from
// components/auth/ProtectedRoute.test.tsx); setup.ts's afterEach
// resetHandlers() clears these between tests.
const mockUser = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  created_at: '2024-01-01T00:00:00Z',
};

// Mock the Layout component
vi.mock('./components/layout/Layout', () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="mock-layout">
      <div data-testid="layout-children">{children}</div>
    </div>
  ),
}));

// Mock the DashboardPage component (lazy loaded)
vi.mock('./components/dashboard/DashboardPage', () => ({
  default: () => <div data-testid="mock-dashboard">Dashboard Page Content</div>,
}));

// Mock ChunkLoadErrorBoundary and AmbientStatusProvider to pass through children
vi.mock('./components/common', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./components/common')>();
  return {
    ...actual,
    ChunkLoadErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    RouteLoadingFallback: () => <div data-testid="route-loading">Loading...</div>,
    // AmbientStatusProvider uses useSystemStatus which requires API mocking
    // so we mock it to just render children
    AmbientStatusProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

describe('App', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/auth/setup-status', () => HttpResponse.json({ setup_required: false })),
      http.get('/api/auth/me', () => HttpResponse.json(mockUser))
    );
  });

  it('renders without crashing', async () => {
    render(<App />);
    // Cold-start test: bears the first real /api/auth/* round-trip through
    // msw before App's singleton queryClient caches the auth boot state
    // (tests below then fit FAST_TIMEOUT). STANDARD_TIMEOUT is the repo's
    // documented choice for renders gated on actual API calls.
    await waitFor(
      () => expect(screen.getByTestId('mock-layout')).toBeInTheDocument(),
      STANDARD_TIMEOUT
    );
  });

  it('renders Layout component', async () => {
    render(<App />);
    await waitFor(
      () => expect(screen.getByTestId('mock-layout')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
  });

  it('renders DashboardPage component inside Layout after loading', async () => {
    render(<App />);
    // Wait for lazy-loaded DashboardPage to appear (fast timeout for mocked components)
    await waitFor(
      () => expect(screen.getByTestId('mock-dashboard')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
    expect(screen.getByText('Dashboard Page Content')).toBeInTheDocument();
  });

  it('DashboardPage is a child of Layout', async () => {
    render(<App />);
    await waitFor(
      () => expect(screen.getByTestId('mock-dashboard')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
    const layoutChildren = screen.getByTestId('layout-children');
    const dashboard = screen.getByTestId('mock-dashboard');
    expect(layoutChildren).toContainElement(dashboard);
  });

  it('has correct component hierarchy', async () => {
    const { container } = render(<App />);
    await waitFor(
      () => expect(screen.getByTestId('mock-dashboard')).toBeInTheDocument(),
      FAST_TIMEOUT
    );
    const layout = screen.getByTestId('mock-layout');
    const dashboard = screen.getByTestId('mock-dashboard');

    expect(container).toContainElement(layout);
    expect(layout).toContainElement(dashboard);
  });

  it('shows loading fallback while lazy components load', () => {
    // Note: Due to mocking, this test verifies the structure is in place
    // The actual loading state is tested in App.lazy.test.tsx
    render(<App />);
    // The RouteLoadingFallback should be rendered by Suspense
    // but since we mock it and DashboardPage resolves immediately,
    // we just verify the structure exists
    expect(screen.getByTestId('mock-layout')).toBeInTheDocument();
  });
});
