import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import App from './App';
import { FAST_TIMEOUT } from './test/setup';

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
  it('renders without crashing', async () => {
    render(<App />);
    // Wait for lazy component to load (fast timeout for mocked components)
    await waitFor(
      () => expect(screen.getByTestId('mock-layout')).toBeInTheDocument(),
      FAST_TIMEOUT
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
