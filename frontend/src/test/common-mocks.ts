/**
 * Shared mock utilities for frontend tests
 *
 * This module provides reusable mock factories to reduce boilerplate
 * and improve test performance by standardizing common mocking patterns.
 *
 * @see setup.ts - Test environment configuration
 */

import { vi, type Mock } from 'vitest';

/**
 * vitest 5 moved `Procedure` (vi.fn's inferred-generic bound) into a chunk
 * file; any export whose inferred type mentions it is unnameable in a .d.ts
 * (TS2883), which is fatal to stryker's declaration-emitting checker. These
 * factories build objects full of vi.fn()s, so their return shapes are
 * spelled out in terms of the public `Mock` type instead of inferred.
 */
export interface RouterMock {
  useNavigate: () => Mock;
  useLocation: () => { pathname: string; search: string; hash: string; state: null };
  useParams: () => Record<string, string>;
  BrowserRouter: (props: { children: unknown }) => unknown;
  Routes: (props: { children: unknown }) => unknown;
  Route: (props: { element: unknown }) => unknown;
  Link: (props: { children: unknown }) => unknown;
  NavLink: (props: { children: unknown }) => unknown;
  Outlet: () => null;
}

export interface WebSocketMockShape {
  connect: Mock;
  disconnect: Mock;
  subscribe: Mock;
  unsubscribe: Mock;
  send: Mock;
  on: Mock;
  off: Mock;
}

/**
 * Common router mock factory
 *
 * Creates a mock of react-router-dom with commonly used hooks.
 * Override individual functions as needed per test.
 *
 * @param mockNavigate - Optional custom navigate function
 * @returns Mock router module
 *
 * @example
 * ```typescript
 * vi.mock('react-router-dom', () => createRouterMock());
 * ```
 */
export const createRouterMock = (mockNavigate: Mock = vi.fn()): RouterMock => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/', search: '', hash: '', state: null }),
  useParams: () => ({}),
  BrowserRouter: ({ children }: { children: unknown }) => children,
  Routes: ({ children }: { children: unknown }) => children,
  Route: ({ element }: { element: unknown }) => element,
  Link: ({ children }: { children: unknown }) => children,
  NavLink: ({ children }: { children: unknown }) => children,
  Outlet: () => null,
});

/**
 * API mock factory
 *
 * Creates a mock API client with common endpoints.
 * Override specific endpoints as needed per test.
 *
 * @param overrides - Partial API overrides
 * @returns Mock API client
 *
 * @example
 * ```typescript
 * const api = createApiMock({
 *   fetchCameras: vi.fn().mockResolvedValue([{ id: 1, name: 'Test Camera' }])
 * });
 * ```
 */
export const createApiMock = (
  overrides: Record<string, unknown> = {}
): Record<string, Mock> & {
  fetchCameras: Mock;
  fetchEvents: Mock;
  fetchAlerts: Mock;
  fetchDetections: Mock;
  fetchEntities: Mock;
  fetchSystemHealth: Mock;
  fetchGpuStats: Mock;
} => ({
  fetchCameras: vi.fn().mockResolvedValue([]),
  fetchEvents: vi.fn().mockResolvedValue([]),
  fetchAlerts: vi.fn().mockResolvedValue([]),
  fetchDetections: vi.fn().mockResolvedValue([]),
  fetchEntities: vi.fn().mockResolvedValue([]),
  fetchSystemHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  fetchGpuStats: vi.fn().mockResolvedValue({ utilization: 0 }),
  ...overrides,
});

/**
 * WebSocket mock factory
 *
 * Creates a mock WebSocket client with common methods.
 * Use this for components that rely on WebSocket connections.
 *
 * @param overrides - Partial WebSocket overrides
 * @returns Mock WebSocket client
 *
 * @example
 * ```typescript
 * const ws = createWebSocketMock({
 *   connect: vi.fn().mockResolvedValue(undefined)
 * });
 * ```
 */
export const createWebSocketMock = (
  overrides: Record<string, unknown> = {}
): Record<string, Mock> & WebSocketMockShape => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
  send: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  ...overrides,
});

/**
 * Query client configuration for testing
 *
 * Use these options when creating a QueryClient in tests
 * to disable retries and caching for faster, more predictable tests.
 */
export const testQueryClientOptions = {
  defaultOptions: {
    queries: {
      retry: false, // Disable retries for faster tests
      staleTime: 0,
      gcTime: 0,
    },
    mutations: {
      retry: false,
    },
  },
};

/**
 * Layout mock component factory
 *
 * Creates a simple pass-through mock for Layout component in App tests.
 * Returns a function that renders children with a testable wrapper.
 *
 * Note: This should be used in vi.mock() declarations, not imported directly.
 *
 * @example
 * ```typescript
 * vi.mock('./components/layout/Layout', () => ({
 *   default: ({ children }) => (
 *     <div data-testid="mock-layout">
 *       <div data-testid="layout-children">{children}</div>
 *     </div>
 *   )
 * }));
 * ```
 */
export const createLayoutMock = () => {
  // This is a helper to document the pattern, actual implementation should be in JSX/TSX files
  throw new Error('createLayoutMock should be implemented inline in test files with JSX');
};

/**
 * Fast timeout option for mocked component rendering
 *
 * Use this as the second argument to waitFor() when testing
 * components that are fully mocked and should resolve quickly.
 *
 * Default waitFor timeout is 1000ms, which is excessive for mocked
 * components that resolve synchronously or near-instantly.
 *
 * @example
 * ```typescript
 * await waitFor(
 *   () => expect(screen.getByTestId('mock-layout')).toBeInTheDocument(),
 *   FAST_TIMEOUT
 * );
 * ```
 */
export const FAST_TIMEOUT = { timeout: 300 };

/**
 * Standard timeout option for real component rendering
 *
 * Use this for components that perform actual async operations
 * (API calls, lazy imports, etc.) and need more time to resolve.
 *
 * @example
 * ```typescript
 * await waitFor(
 *   () => expect(screen.getByText('Data loaded')).toBeInTheDocument(),
 *   STANDARD_TIMEOUT
 * );
 * ```
 */
export const STANDARD_TIMEOUT = { timeout: 1000 };
