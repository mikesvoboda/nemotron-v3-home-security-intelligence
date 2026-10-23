/**
 * Test utility for rendering components with all required providers.
 *
 * This module provides a custom render function that wraps components with
 * commonly needed providers (Router, Context providers, etc.) to simplify
 * testing and reduce boilerplate.
 *
 * @example
 * // Basic usage
 * import { renderWithProviders, screen } from '../test-utils';
 * const { user } = renderWithProviders(<MyComponent />);
 * await user.click(screen.getByRole('button'));
 *
 * @example
 * // With custom route
 * renderWithProviders(<MyComponent />, { route: '/settings' });
 *
 * @example
 * // With sidebar context
 * renderWithProviders(<MyComponent />, {
 *   sidebarContext: { isMobileMenuOpen: true }
 * });
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, RenderOptions, RenderResult } from '@testing-library/react';
import userEvent, { UserEvent } from '@testing-library/user-event';
import { ReactElement, ReactNode } from 'react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';

import { ThemeProvider } from '../contexts';
import { AnnouncementProvider } from '../contexts/AnnouncementContext';
import { SidebarContext, SidebarContextType } from '../hooks/useSidebarContext';
import { createQueryClient } from '../services/queryClient';

/**
 * Default sidebar context values for testing.
 * Components can override these via the sidebarContext option.
 */
const defaultSidebarContext: SidebarContextType = {
  isMobileMenuOpen: false,
  setMobileMenuOpen: () => {},
  toggleMobileMenu: () => {},
};

/**
 * Options for configuring the test providers wrapper.
 */
export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /**
   * Initial route for MemoryRouter. If not provided, uses '/' by default.
   * Use this when testing components that depend on route params or navigation.
   */
  route?: string;

  /**
   * Whether to use MemoryRouter (true, default) or BrowserRouter (false).
   * MemoryRouter is preferred for tests as it doesn't require browser history API.
   */
  useMemoryRouter?: boolean;

  /**
   * Custom sidebar context values. Merged with defaults.
   * Useful for testing components that use useSidebarContext hook.
   */
  sidebarContext?: Partial<SidebarContextType>;

  /**
   * Whether to wrap with SidebarContext provider.
   * Set to false if testing components that don't need sidebar context.
   * @default true
   */
  withSidebarContext?: boolean;

  /**
   * Whether to wrap with Router provider.
   * Set to false if component already has its own router or doesn't need one.
   * @default true
   */
  withRouter?: boolean;

  /**
   * Whether to wrap with QueryClientProvider.
   * Set to false if testing components that don't use TanStack Query.
   * @default true
   */
  withQueryClient?: boolean;

  /**
   * Custom QueryClient instance. If not provided, a fresh client is created.
   * Useful for testing specific query states or pre-populating cache.
   */
  queryClient?: QueryClient;

  /**
   * Initial entries for MemoryRouter when testing multi-entry history.
   * Overrides `route` when provided.
   */
  initialEntries?: string[];

  /**
   * Whether to wrap with ThemeProvider (dark default).
   * @default false
   */
  withThemeProvider?: boolean;

  /**
   * Whether to wrap with AnnouncementProvider.
   * @default false
   */
  withAnnouncementProvider?: boolean;
}

/**
 * Extended render result that includes userEvent instance.
 */
export interface RenderWithProvidersResult extends RenderResult {
  /**
   * Pre-configured userEvent instance for simulating user interactions.
   * Use this instead of importing userEvent separately.
   */
  user: UserEvent;
}

/**
 * Creates a wrapper component with all the providers based on options.
 */
function createWrapper(
  options: RenderWithProvidersOptions
): React.ComponentType<{ children: ReactNode }> {
  const {
    route = '/',
    initialEntries,
    useMemoryRouter = true,
    sidebarContext,
    withSidebarContext = true,
    withRouter = true,
    withQueryClient = true,
    withThemeProvider = false,
    withAnnouncementProvider = false,
    queryClient,
  } = options;

  // Create a test QueryClient if not provided
  // Uses fresh instance per test to avoid cross-test contamination
  const testQueryClient = queryClient ?? createQueryClient();

  // Merge sidebar context with defaults
  const mergedSidebarContext: SidebarContextType = {
    ...defaultSidebarContext,
    ...sidebarContext,
  };

  const entries = initialEntries ?? [route];

  return function Wrapper({ children }: { children: ReactNode }) {
    let wrapped = <>{children}</>;

    if (withAnnouncementProvider) {
      wrapped = <AnnouncementProvider>{wrapped}</AnnouncementProvider>;
    }

    // Wrap with SidebarContext if needed (and not mocked away by a test)
    if (withSidebarContext && SidebarContext?.Provider) {
      wrapped = (
        <SidebarContext.Provider value={mergedSidebarContext}>{wrapped}</SidebarContext.Provider>
      );
    }

    // Wrap with Router if needed
    if (withRouter) {
      if (useMemoryRouter) {
        wrapped = <MemoryRouter initialEntries={entries}>{wrapped}</MemoryRouter>;
      } else {
        wrapped = <BrowserRouter>{wrapped}</BrowserRouter>;
      }
    }

    if (withThemeProvider) {
      wrapped = <ThemeProvider defaultMode="dark">{wrapped}</ThemeProvider>;
    }

    // Wrap with QueryClientProvider if needed (outermost provider)
    if (withQueryClient) {
      wrapped = <QueryClientProvider client={testQueryClient}>{wrapped}</QueryClientProvider>;
    }

    return wrapped;
  };
}

/**
 * Renders a React component with all common providers for testing.
 *
 * This function wraps @testing-library/react's render with:
 * - Router (MemoryRouter by default for isolated tests)
 * - SidebarContext provider
 * - Pre-configured userEvent for interaction testing
 *
 * @param ui - The React element to render
 * @param options - Configuration options for providers and render
 * @returns Extended render result with user event instance
 *
 * @example
 * // Test a component that uses routing
 * const { user, getByRole } = renderWithProviders(
 *   <SettingsPage />,
 *   { route: '/settings' }
 * );
 *
 * @example
 * // Test mobile menu interaction
 * const mockToggle = vi.fn();
 * renderWithProviders(<Header />, {
 *   sidebarContext: {
 *     isMobileMenuOpen: false,
 *     toggleMobileMenu: mockToggle,
 *   }
 * });
 */

export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {}
): RenderWithProvidersResult {
  const {
    route: _route,
    initialEntries: _initialEntries,
    useMemoryRouter: _useMemoryRouter,
    sidebarContext: _sidebarContext,
    withSidebarContext: _withSidebarContext,
    withRouter: _withRouter,
    withQueryClient: _withQueryClient,
    withThemeProvider: _withThemeProvider,
    withAnnouncementProvider: _withAnnouncementProvider,
    queryClient: _queryClient,
    ...restOptions
  } = options;

  // Create userEvent instance for this test
  const user = userEvent.setup();

  // Create the wrapper component
  const Wrapper = createWrapper(options);

  // Render with the wrapper
  const renderResult = render(ui, {
    wrapper: Wrapper,
    ...restOptions,
  });

  return {
    ...renderResult,
    user,
  };
}

/**
 * Creates a wrapper component for renderHook tests that need QueryClientProvider.
 *
 * @param queryClient - Optional custom QueryClient. If not provided, a fresh client is created.
 * @returns Wrapper component for use with renderHook
 *
 * @example
 * const { result } = renderHook(() => useHealthStatusQuery(), {
 *   wrapper: createQueryWrapper(),
 * });
 */

export function createQueryWrapper(queryClient?: QueryClient) {
  const testQueryClient = queryClient ?? createQueryClient();
  return function QueryWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>;
  };
}

/**
 * Shared navigation test render fixture for navigation, shell, and page components
 * (Sidebar, MobileBottomNav, CommandPalette, ShortcutsHelpModal, Header, Layout,
 * SettingsPage, AnalyticsPage, ProductTour).
 */
export function renderWithNavigation(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {}
): RenderWithProvidersResult {
  return renderWithProviders(ui, {
    withThemeProvider: true,
    withAnnouncementProvider: true,
    ...options,
  });
}

/**
 * Re-export common testing utilities for convenience.
 * This allows tests to import everything from test-utils.
 */

export { screen, within, waitFor, act } from '@testing-library/react';

export { default as userEvent } from '@testing-library/user-event';
export { QueryClient } from '@tanstack/react-query';
