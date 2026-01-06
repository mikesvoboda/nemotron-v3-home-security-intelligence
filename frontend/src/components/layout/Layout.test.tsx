import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, Mock } from 'vitest';

import Layout from './Layout';
import { useServiceStatus } from '../../hooks/useServiceStatus';
import { useSidebarContext } from '../../hooks/useSidebarContext';
import { ServiceName, ServiceStatus } from '../common/ServiceStatusAlert';

// Mock the child components
vi.mock('./Header', () => ({
  default: () => <div data-testid="mock-header">Header</div>,
}));

vi.mock('./Sidebar', () => ({
  default: () => <div data-testid="mock-sidebar">Sidebar</div>,
}));

// Mock the useServiceStatus hook
vi.mock('../../hooks/useServiceStatus', () => ({
  useServiceStatus: vi.fn(),
}));

// Helper to create service status
function createServiceStatus(
  service: ServiceName,
  status: ServiceStatus['status'],
  message?: string
): ServiceStatus {
  return {
    service,
    status,
    message,
    timestamp: '2025-12-26T12:00:00Z',
  };
}

// Helper to create empty services record
function createEmptyServices(): Record<ServiceName, ServiceStatus | null> {
  return {
    redis: null,
    rtdetr: null,
    nemotron: null,
  };
}

// Helper to create healthy services
function createHealthyServices(): Record<ServiceName, ServiceStatus | null> {
  return {
    redis: createServiceStatus('redis', 'healthy'),
    rtdetr: createServiceStatus('rtdetr', 'healthy'),
    nemotron: createServiceStatus('nemotron', 'healthy'),
  };
}

describe('Layout', () => {
  beforeEach(() => {
    // Reset mock to return empty/healthy services by default
    (useServiceStatus as Mock).mockReturnValue({
      services: createEmptyServices(),
      hasUnhealthy: false,
      isAnyRestarting: false,
      getServiceStatus: () => null,
    });
  });

  describe('skip link accessibility', () => {
    it('renders skip link for keyboard navigation', () => {
      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toBeInTheDocument();
      expect(skipLink).toHaveAttribute('href', '#main-content');
      expect(skipLink).toHaveTextContent('Skip to main content');
    });

    it('main content has proper id for skip link target', () => {
      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );
      const mainContent = screen.getByTestId('main-content');
      expect(mainContent).toHaveAttribute('id', 'main-content');
      expect(mainContent).toHaveAttribute('tabIndex', '-1');
    });

    it('skip link is visually hidden by default', () => {
      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );
      const skipLink = screen.getByTestId('skip-link');
      expect(skipLink).toHaveClass('sr-only');
    });
  });

  it('renders without crashing', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    expect(screen.getByTestId('mock-header')).toBeInTheDocument();
  });

  it('renders Header component', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    expect(screen.getByTestId('mock-header')).toBeInTheDocument();
    expect(screen.getByText('Header')).toBeInTheDocument();
  });

  it('renders Sidebar component', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    expect(screen.getByTestId('mock-sidebar')).toBeInTheDocument();
  });

  it('renders children content in main area', () => {
    render(
      <Layout>
        <div data-testid="test-child">Test Child Content</div>
      </Layout>
    );
    expect(screen.getByTestId('test-child')).toBeInTheDocument();
    expect(screen.getByText('Test Child Content')).toBeInTheDocument();
  });

  it('has correct layout structure with flex classes', () => {
    const { container } = render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    const layoutDiv = container.firstChild as HTMLElement;
    expect(layoutDiv).toHaveClass('min-h-screen', 'bg-[#0E0E0E]', 'flex', 'flex-col');
  });

  it('main element has overflow-auto class for scrolling', () => {
    render(
      <Layout>
        <div>Test Content</div>
      </Layout>
    );
    const main = screen.getByRole('main');
    expect(main).toHaveClass('flex-1', 'overflow-auto');
  });

  it('renders multiple children correctly', () => {
    render(
      <Layout>
        <div data-testid="child-1">Child 1</div>
        <div data-testid="child-2">Child 2</div>
        <div data-testid="child-3">Child 3</div>
      </Layout>
    );
    expect(screen.getByTestId('child-1')).toBeInTheDocument();
    expect(screen.getByTestId('child-2')).toBeInTheDocument();
    expect(screen.getByTestId('child-3')).toBeInTheDocument();
  });

  describe('ServiceStatusAlert integration', () => {
    it('does not show alert when all services are null', () => {
      (useServiceStatus as Mock).mockReturnValue({
        services: createEmptyServices(),
        hasUnhealthy: false,
        isAnyRestarting: false,
        getServiceStatus: () => null,
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('does not show alert when all services are healthy', () => {
      (useServiceStatus as Mock).mockReturnValue({
        services: createHealthyServices(),
        hasUnhealthy: false,
        isAnyRestarting: false,
        getServiceStatus: (name: ServiceName) => createHealthyServices()[name],
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('shows alert when a service is unhealthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };

      (useServiceStatus as Mock).mockReturnValue({
        services,
        hasUnhealthy: true,
        isAnyRestarting: false,
        getServiceStatus: (name: ServiceName) => services[name],
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Service Unhealthy')).toBeInTheDocument();
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('shows alert when a service is restarting', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: null,
        nemotron: createServiceStatus('nemotron', 'restarting', 'Attempting restart'),
      };

      (useServiceStatus as Mock).mockReturnValue({
        services,
        hasUnhealthy: false,
        isAnyRestarting: true,
        getServiceStatus: (name: ServiceName) => services[name],
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Service Restarting')).toBeInTheDocument();
    });

    it('shows alert when a service has failed', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'failed'),
        rtdetr: null,
        nemotron: null,
      };

      (useServiceStatus as Mock).mockReturnValue({
        services,
        hasUnhealthy: true,
        isAnyRestarting: false,
        getServiceStatus: (name: ServiceName) => services[name],
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Service Failed')).toBeInTheDocument();
    });

    it('dismisses alert when dismiss button is clicked', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };

      (useServiceStatus as Mock).mockReturnValue({
        services,
        hasUnhealthy: true,
        isAnyRestarting: false,
        getServiceStatus: (name: ServiceName) => services[name],
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      // Alert should be visible
      expect(screen.getByRole('alert')).toBeInTheDocument();

      // Click dismiss button
      fireEvent.click(screen.getByLabelText('Dismiss alert'));

      // Alert should be hidden
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('renders alert before children content', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };

      (useServiceStatus as Mock).mockReturnValue({
        services,
        hasUnhealthy: true,
        isAnyRestarting: false,
        getServiceStatus: (name: ServiceName) => services[name],
      });

      render(
        <Layout>
          <div data-testid="test-child">Test Content</div>
        </Layout>
      );

      const main = screen.getByRole('main');
      const alert = screen.getByRole('alert');
      const child = screen.getByTestId('test-child');

      // Alert should come before children in the DOM
      expect(main.firstChild).toBe(alert);
      expect(main.contains(child)).toBe(true);
    });

    it('shows worst status when multiple services are unhealthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: createServiceStatus('rtdetr', 'failed'),
        nemotron: createServiceStatus('nemotron', 'restarting'),
      };

      (useServiceStatus as Mock).mockReturnValue({
        services,
        hasUnhealthy: true,
        isAnyRestarting: true,
        getServiceStatus: (name: ServiceName) => services[name],
      });

      render(
        <Layout>
          <div>Test Content</div>
        </Layout>
      );

      // Should show 'Service Failed' as it's the worst status
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Service Failed')).toBeInTheDocument();
    });
  });

  describe('mobile sidebar context', () => {
    it('provides sidebar context to children', () => {
      // Test component that consumes the context
      function TestConsumer() {
        const { isMobileMenuOpen, toggleMobileMenu } = useSidebarContext();
        return (
          <div>
            <span data-testid="menu-state">{isMobileMenuOpen ? 'open' : 'closed'}</span>
            <button onClick={toggleMobileMenu} data-testid="toggle-button">
              Toggle
            </button>
          </div>
        );
      }

      render(
        <Layout>
          <TestConsumer />
        </Layout>
      );

      // Initially closed
      expect(screen.getByTestId('menu-state')).toHaveTextContent('closed');

      // Click toggle
      fireEvent.click(screen.getByTestId('toggle-button'));
      expect(screen.getByTestId('menu-state')).toHaveTextContent('open');

      // Click toggle again
      fireEvent.click(screen.getByTestId('toggle-button'));
      expect(screen.getByTestId('menu-state')).toHaveTextContent('closed');
    });

    it('shows mobile overlay when menu is open', () => {
      function TestConsumer() {
        const { toggleMobileMenu } = useSidebarContext();
        return (
          <button onClick={toggleMobileMenu} data-testid="toggle-button">
            Toggle
          </button>
        );
      }

      render(
        <Layout>
          <TestConsumer />
        </Layout>
      );

      // Initially no overlay
      expect(screen.queryByTestId('mobile-overlay')).not.toBeInTheDocument();

      // Open menu
      fireEvent.click(screen.getByTestId('toggle-button'));
      expect(screen.getByTestId('mobile-overlay')).toBeInTheDocument();

      // Click overlay to close
      fireEvent.click(screen.getByTestId('mobile-overlay'));
      expect(screen.queryByTestId('mobile-overlay')).not.toBeInTheDocument();
    });

    it('throws error when useSidebarContext used outside Layout', () => {
      function TestOutsideLayout() {
        useSidebarContext();
        return null;
      }

      // Should throw an error
      expect(() => render(<TestOutsideLayout />)).toThrow(
        'useSidebarContext must be used within Layout'
      );
    });
  });
});
