/**
 * Test utilities for frontend testing.
 *
 * This module provides custom render functions, test wrappers, and utilities
 * that make testing React components more convenient and consistent.
 *
 * ## Usage
 *
 * ### Custom Render with Providers
 *
 * Use `renderWithProviders` instead of `render` from Testing Library when
 * your component needs QueryClient or other context providers:
 *
 * ```typescript
 * import { renderWithProviders } from '@/test/utils';
 * import { MyComponent } from './MyComponent';
 *
 * it('renders with providers', () => {
 *   const { getByText } = renderWithProviders(<MyComponent />);
 *   expect(getByText('Hello')).toBeInTheDocument();
 * });
 * ```
 *
 * ### Custom QueryClient Options
 *
 * Override default QueryClient behavior for specific tests:
 *
 * ```typescript
 * renderWithProviders(<MyComponent />, {
 *   queryClientOptions: {
 *     defaultOptions: {
 *       queries: { retry: false, staleTime: 0 }
 *     }
 *   }
 * });
 * ```
 *
 * ### Wrapper Component
 *
 * Use `createWrapper` when testing hooks with `renderHook`:
 *
 * ```typescript
 * import { renderHook } from '@testing-library/react';
 * import { createWrapper } from '@/test/utils';
 *
 * const { result } = renderHook(() => useMyHook(), {
 *   wrapper: createWrapper(),
 * });
 * ```
 *
 * @module test/utils
 */

import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement, ReactNode } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for customizing the test render environment.
 */
export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /**
   * Options to pass to the QueryClient constructor.
   * Useful for disabling retries, adjusting cache time, etc.
   */
  queryClientOptions?: ConstructorParameters<typeof QueryClient>[0];
}

// ============================================================================
// Default QueryClient Configuration
// ============================================================================

/**
 * Default QueryClient configuration optimized for testing.
 *
 * Key differences from production:
 * - No retries (fail fast)
 * - No automatic refetch on window focus/reconnect
 * - Short cache and stale times (reduce test interference)
 * - Errors are thrown immediately (easier to test error states)
 */
export function createTestQueryClient(
  options?: ConstructorParameters<typeof QueryClient>[0]
): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Disable retries to fail fast in tests
        retry: false,
        // Disable automatic refetch behaviors
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        refetchOnMount: false,
        // Short cache times to reduce test interference
        gcTime: 0, // Previously cacheTime in v4
        staleTime: 0,
        // Throw errors immediately instead of silently failing
        throwOnError: true,
      },
      mutations: {
        // Disable retries for mutations
        retry: false,
        // Throw errors immediately
        throwOnError: true,
      },
    },
    ...options,
  });
}

// ============================================================================
// Wrapper Components
// ============================================================================

/**
 * Create a wrapper component with all necessary providers.
 *
 * This is useful when testing hooks with `renderHook` or when you need
 * to reuse the same wrapper configuration across multiple tests.
 *
 * @param queryClientOptions - Options for the QueryClient
 * @returns Wrapper component function
 *
 * @example
 * ```typescript
 * const wrapper = createWrapper();
 * const { result } = renderHook(() => useCamerasQuery(), { wrapper });
 * ```
 */
export function createWrapper(
  queryClientOptions?: ConstructorParameters<typeof QueryClient>[0]
) {
  const queryClient = createTestQueryClient(queryClientOptions);

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Custom Render Function
// ============================================================================

/**
 * Render a component with all necessary test providers.
 *
 * This is a drop-in replacement for `render` from Testing Library that
 * automatically wraps your component with QueryClientProvider and any
 * other providers needed for testing.
 *
 * @param ui - The component to render
 * @param options - Render options including queryClientOptions
 * @returns Render result from Testing Library
 *
 * @example
 * ```typescript
 * const { getByText } = renderWithProviders(<MyComponent />);
 * expect(getByText('Hello')).toBeInTheDocument();
 * ```
 *
 * @example With custom QueryClient
 * ```typescript
 * renderWithProviders(<MyComponent />, {
 *   queryClientOptions: {
 *     defaultOptions: { queries: { retry: 3 } }
 *   }
 * });
 * ```
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: RenderWithProvidersOptions
) {
  const { queryClientOptions, ...renderOptions } = options || {};

  const Wrapper = createWrapper(queryClientOptions);

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

// ============================================================================
// Re-export Testing Library utilities
// ============================================================================

/**
 * Re-export everything from Testing Library for convenience.
 * This allows users to import everything they need from one place:
 *
 * ```typescript
 * import { renderWithProviders, screen, waitFor } from '@/test/utils';
 * ```
 */
export * from '@testing-library/react';

// Override the default render with our custom version
export { renderWithProviders as render };
