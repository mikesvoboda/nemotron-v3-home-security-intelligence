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
import { render, RenderOptions, RenderResult } from '@testing-library/react';
import userEvent, { UserEvent } from '@testing-library/user-event';
import { ReactElement, ReactNode } from 'react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';

import { SidebarContext, SidebarContextType } from '../hooks/useSidebarContext';

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
function createWrapper(options: RenderWithProvidersOptions): React.ComponentType<{ children: ReactNode }> {
  const {
    route = '/',
    useMemoryRouter = true,
    sidebarContext,
    withSidebarContext = true,
    withRouter = true,
  } = options;

  // Merge sidebar context with defaults
  const mergedSidebarContext: SidebarContextType = {
    ...defaultSidebarContext,
    ...sidebarContext,
  };

  return function Wrapper({ children }: { children: ReactNode }) {
    let wrapped = <>{children}</>;

    // Wrap with SidebarContext if needed
    if (withSidebarContext) {
      wrapped = (
        <SidebarContext.Provider value={mergedSidebarContext}>
          {wrapped}
        </SidebarContext.Provider>
      );
    }

    // Wrap with Router if needed
    if (withRouter) {
      if (useMemoryRouter) {
        wrapped = (
          <MemoryRouter initialEntries={[route]}>
            {wrapped}
          </MemoryRouter>
        );
      } else {
        wrapped = <BrowserRouter>{wrapped}</BrowserRouter>;
      }
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
  const { route: _route, useMemoryRouter: _useMemoryRouter, sidebarContext: _sidebarContext, withSidebarContext: _withSidebarContext, withRouter: _withRouter, ...restOptions } = options;

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
 * Re-export common testing utilities for convenience.
 * This allows tests to import everything from test-utils.
 */
export { screen, within, waitFor, act } from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
