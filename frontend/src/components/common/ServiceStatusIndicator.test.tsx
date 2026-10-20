import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, afterEach } from 'vitest';

import ServiceStatusIndicator from './ServiceStatusIndicator';

import type { ServiceName, ServiceStatus, ServiceStatusType } from '../../hooks/useServiceStatus';

// Helper to create mock service status
function createMockServiceStatus(
  service: ServiceName,
  status: ServiceStatusType,
  message?: string | null
): ServiceStatus {
  return {
    service,
    status,
    message,
    timestamp: '2026-01-10T10:00:00Z',
  };
}

describe('ServiceStatusIndicator', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<ServiceStatusIndicator services={{}} hasUnhealthy={false} isAnyRestarting={false} />);

    expect(screen.getByTestId('service-status-indicator')).toBeInTheDocument();
  });

  it('shows online status when no service has reported (initial state)', () => {
    render(<ServiceStatusIndicator services={{}} hasUnhealthy={false} isAnyRestarting={false} />);

    expect(screen.getByText('Online')).toBeInTheDocument();
    // Uses emerald instead of green for WCAG 4.5:1 contrast compliance
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-emerald-500');
  });

  it('shows online status when all reported services are healthy or running', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'healthy'),
          yolo26: createMockServiceStatus('yolo26', 'healthy'),
          postgres: createMockServiceStatus('postgres', 'running', null),
        }}
        hasUnhealthy={false}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Online')).toBeInTheDocument();
    // Uses emerald instead of green for WCAG 4.5:1 contrast compliance
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-emerald-500');
  });

  it('shows degraded status when any service is restarting', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'healthy'),
          yolo26: createMockServiceStatus('yolo26', 'restarting'),
          postgres: createMockServiceStatus('postgres', 'running', null),
        }}
        hasUnhealthy={false}
        isAnyRestarting={true}
      />
    );

    expect(screen.getByText('Degraded')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-yellow-500');
  });

  it('shows degraded status when some services are unhealthy', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'healthy'),
          yolo26: createMockServiceStatus('yolo26', 'unhealthy'),
          postgres: createMockServiceStatus('postgres', 'running', null),
        }}
        hasUnhealthy={true}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Degraded')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-yellow-500');
  });

  it('shows offline status when all reported services are unhealthy', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'unhealthy'),
          yolo26: createMockServiceStatus('yolo26', 'failed'),
          postgres: createMockServiceStatus('postgres', 'restart_failed'),
        }}
        hasUnhealthy={true}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Offline')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-red-500');
  });

  it('shows offline status when all reported services include a crashed worker', () => {
    render(
      <ServiceStatusIndicator
        services={{
          'worker:detection-0': createMockServiceStatus('worker:detection-0', 'crashed'),
        }}
        hasUnhealthy={true}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('has correct aria attributes', () => {
    render(<ServiceStatusIndicator services={{}} hasUnhealthy={false} isAnyRestarting={false} />);

    const indicator = screen.getByTestId('service-status-indicator');
    expect(indicator).toHaveAttribute('role', 'button');
    expect(indicator).toHaveAttribute('tabIndex', '0');
    expect(indicator).toHaveAttribute('aria-haspopup', 'true');
    expect(indicator).toHaveAttribute('aria-expanded', 'false');
  });

  describe('Dropdown', () => {
    it('shows dropdown on mouse enter', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
            yolo26: createMockServiceStatus('yolo26', 'healthy'),
          }}
          hasUnhealthy={false}
          isAnyRestarting={false}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');

      // Dropdown should not be visible initially
      expect(screen.queryByTestId('service-status-dropdown')).not.toBeInTheDocument();

      // Hover to show dropdown
      fireEvent.mouseEnter(indicator);

      expect(screen.getByTestId('service-status-dropdown')).toBeInTheDocument();
      expect(screen.getByText('AI Services')).toBeInTheDocument();
    });

    it('shows dropdown on focus', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
            yolo26: createMockServiceStatus('yolo26', 'healthy'),
          }}
          hasUnhealthy={false}
          isAnyRestarting={false}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');

      fireEvent.focus(indicator);

      expect(screen.getByTestId('service-status-dropdown')).toBeInTheDocument();
    });

    it('hides dropdown on mouse leave after delay', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
          }}
          hasUnhealthy={false}
          isAnyRestarting={false}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');

      // Show dropdown
      fireEvent.mouseEnter(indicator);
      expect(screen.getByTestId('service-status-dropdown')).toBeInTheDocument();

      // Mouse leave
      fireEvent.mouseLeave(indicator);

      // Still visible immediately
      expect(screen.getByTestId('service-status-dropdown')).toBeInTheDocument();

      // After delay, should be hidden
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      expect(screen.queryByTestId('service-status-dropdown')).not.toBeInTheDocument();

      vi.useRealTimers();
    });

    it('displays service details in dropdown', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
            yolo26: createMockServiceStatus('yolo26', 'unhealthy'),
            postgres: createMockServiceStatus('postgres', 'restarting'),
          }}
          hasUnhealthy={true}
          isAnyRestarting={true}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');
      fireEvent.mouseEnter(indicator);

      // Check service names are displayed
      expect(screen.getByText('Redis')).toBeInTheDocument();
      expect(screen.getByText('YOLO26')).toBeInTheDocument();
      expect(screen.getByText('PostgreSQL')).toBeInTheDocument();

      // Check status indicators
      // Uses emerald instead of green for WCAG 4.5:1 contrast compliance
      expect(screen.getByTestId('service-indicator-redis')).toHaveClass('bg-emerald-500');
      expect(screen.getByTestId('service-indicator-yolo26')).toHaveClass('bg-red-500');
      expect(screen.getByTestId('service-indicator-postgres')).toHaveClass('bg-yellow-500');
    });

    it('shows unhealthy warning in dropdown when hasUnhealthy', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
            yolo26: createMockServiceStatus('yolo26', 'unhealthy'),
          }}
          hasUnhealthy={true}
          isAnyRestarting={false}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('Some services are unhealthy')).toBeInTheDocument();
    });

    it('shows restarting warning in dropdown when isAnyRestarting', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
            yolo26: createMockServiceStatus('yolo26', 'restarting'),
          }}
          hasUnhealthy={false}
          isAnyRestarting={true}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('Services restarting')).toBeInTheDocument();
    });

    it('renders unmapped container and worker names via the dash-as-space fallback', () => {
      render(
        <ServiceStatusIndicator
          services={{
            'node-exporter': createMockServiceStatus('node-exporter', 'stopped', null),
            'worker:analysis-0': createMockServiceStatus('worker:analysis-0', 'failed'),
          }}
          hasUnhealthy={true}
          isAnyRestarting={false}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('node exporter')).toBeInTheDocument();
      expect(screen.getByText('worker:analysis-0'.replace(/-/g, ' '))).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      render(
        <ServiceStatusIndicator
          services={{}}
          hasUnhealthy={false}
          isAnyRestarting={false}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('service-status-indicator')).toHaveClass('custom-class');
    });

    it('pulses status dot when online', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
          }}
          hasUnhealthy={false}
          isAnyRestarting={false}
        />
      );

      expect(screen.getByTestId('service-status-dot')).toHaveClass('animate-pulse');
    });

    it('does not pulse status dot when offline', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'failed'),
            yolo26: createMockServiceStatus('yolo26', 'failed'),
          }}
          hasUnhealthy={true}
          isAnyRestarting={false}
        />
      );

      expect(screen.getByTestId('service-status-dot')).not.toHaveClass('animate-pulse');
    });
  });
});
