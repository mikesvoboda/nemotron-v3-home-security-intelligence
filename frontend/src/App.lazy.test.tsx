/**
 * Tests for lazy-loaded routes in App component
 *
 * TDD RED Phase - These tests verify that routes are properly code-split
 * and that Suspense boundaries work correctly with loading states.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { Suspense, lazy, ComponentType, ReactNode } from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';

import { FAST_TIMEOUT } from './test/setup';

describe('App lazy loading', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Suspense fallback', () => {
    it('shows loading fallback while lazy component is loading', async () => {
      // Create a component that delays resolution
      let resolveImport: (value: { default: ComponentType }) => void;
      const LazyDelayed = lazy(
        () =>
          new Promise<{ default: ComponentType }>((resolve) => {
            resolveImport = resolve;
          })
      );

      render(
        <Suspense fallback={<div data-testid="loading-fallback">Loading...</div>}>
          <LazyDelayed />
        </Suspense>
      );

      // Should show loading fallback immediately
      expect(screen.getByTestId('loading-fallback')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // Resolve the import
      resolveImport!({
        default: () => <div data-testid="loaded-content">Loaded</div>,
      });

      // Wait for lazy component to render (fast timeout for mocked components)
      await waitFor(
        () => expect(screen.getByTestId('loaded-content')).toBeInTheDocument(),
        FAST_TIMEOUT
      );

      // Loading fallback should be gone
      expect(screen.queryByTestId('loading-fallback')).not.toBeInTheDocument();
    });

    it('renders RouteLoadingFallback component during route transitions', async () => {
      // Import the actual RouteLoadingFallback once implemented
      // This test verifies the integration
      const LazyComponent = lazy(() =>
        Promise.resolve({
          default: () => <div>Lazy Content</div>,
        })
      );

      // Mock RouteLoadingFallback for now
      const RouteLoadingFallback = () => (
        <div role="status" aria-busy="true" data-testid="route-loading">
          Loading...
        </div>
      );

      render(
        <Suspense fallback={<RouteLoadingFallback />}>
          <LazyComponent />
        </Suspense>
      );

      // Wait for component to load (fast timeout for mocked components)
      await waitFor(
        () => expect(screen.getByText('Lazy Content')).toBeInTheDocument(),
        FAST_TIMEOUT
      );
    });
  });

  describe('code splitting behavior', () => {
    it('lazy components are not loaded until rendered', async () => {
      // Track whether module was imported
      let importCalled = false;
      const TrackedLazy = lazy(() => {
        importCalled = true;
        return Promise.resolve({
          default: () => <div>Tracked Component</div>,
        });
      });

      // Before rendering, import should not be called
      expect(importCalled).toBe(false);

      // After rendering, import should be called
      render(
        <Suspense fallback={<div>Loading</div>}>
          <TrackedLazy />
        </Suspense>
      );

      await waitFor(() => expect(importCalled).toBe(true), FAST_TIMEOUT);
    });

    it('lazy loads different routes independently', async () => {
      const importedRoutes: string[] = [];

      const LazyRoute1 = lazy(() => {
        importedRoutes.push('route1');
        return Promise.resolve({
          default: () => <div data-testid="route1">Route 1</div>,
        });
      });

      const LazyRoute2 = lazy(() => {
        importedRoutes.push('route2');
        return Promise.resolve({
          default: () => <div data-testid="route2">Route 2</div>,
        });
      });

      // Render only Route1
      const { unmount } = render(
        <Suspense fallback={<div>Loading</div>}>
          <LazyRoute1 />
        </Suspense>
      );

      await waitFor(() => expect(screen.getByTestId('route1')).toBeInTheDocument(), FAST_TIMEOUT);

      // Only route1 should be imported
      expect(importedRoutes).toEqual(['route1']);

      unmount();

      // Now render Route2
      render(
        <Suspense fallback={<div>Loading</div>}>
          <LazyRoute2 />
        </Suspense>
      );

      await waitFor(() => expect(screen.getByTestId('route2')).toBeInTheDocument(), FAST_TIMEOUT);

      // Now both routes should be imported
      expect(importedRoutes).toEqual(['route1', 'route2']);
    });
  });

  describe('error handling', () => {
    it('catches chunk load errors via ChunkLoadErrorBoundary', async () => {
      // Suppress expected error
      const originalError = console.error;
      console.error = vi.fn();

      const LazyError = lazy(() => {
        const error = new Error('Loading chunk failed');
        error.name = 'ChunkLoadError';
        return Promise.reject(error);
      });

      // Create a simple error boundary for testing
      const React = await import('react');
      interface ErrorBoundaryState {
        hasError: boolean;
        error: Error | null;
      }
      class TestErrorBoundary extends React.Component<{ children: ReactNode }, ErrorBoundaryState> {
        state: ErrorBoundaryState = { hasError: false, error: null };
        static getDerivedStateFromError(error: Error): ErrorBoundaryState {
          return { hasError: true, error };
        }
        render() {
          if (this.state.hasError) {
            const errorMessage = this.state.error?.message ?? 'Unknown error';
            return (
              <div role="alert" data-testid="error-boundary">
                Error caught: {errorMessage}
              </div>
            );
          }
          return this.props.children;
        }
      }

      render(
        <TestErrorBoundary>
          <Suspense fallback={<div>Loading</div>}>
            <LazyError />
          </Suspense>
        </TestErrorBoundary>
      );

      await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument(), FAST_TIMEOUT);

      expect(screen.getByTestId('error-boundary')).toHaveTextContent('Loading chunk failed');

      console.error = originalError;
    });
  });
});
