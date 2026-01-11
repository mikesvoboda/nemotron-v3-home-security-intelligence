import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, afterEach } from 'vitest';

import ServiceStatusIndicator from './ServiceStatusIndicator';

import type { ServiceStatus } from '../../hooks/useServiceStatus';

// Helper to create mock service status
function createMockServiceStatus(
  service: 'redis' | 'rtdetr' | 'nemotron',
  status: 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed',
  message?: string
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
    render(
      <ServiceStatusIndicator
        services={{ redis: null, rtdetr: null, nemotron: null }}
        hasUnhealthy={false}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByTestId('service-status-indicator')).toBeInTheDocument();
  });

  it('shows online status when all services are null (initial state)', () => {
    render(
      <ServiceStatusIndicator
        services={{ redis: null, rtdetr: null, nemotron: null }}
        hasUnhealthy={false}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-green-500');
  });

  it('shows online status when all services are healthy', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'healthy'),
          rtdetr: createMockServiceStatus('rtdetr', 'healthy'),
          nemotron: createMockServiceStatus('nemotron', 'healthy'),
        }}
        hasUnhealthy={false}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-green-500');
  });

  it('shows degraded status when any service is restarting', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'healthy'),
          rtdetr: createMockServiceStatus('rtdetr', 'restarting'),
          nemotron: createMockServiceStatus('nemotron', 'healthy'),
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
          rtdetr: createMockServiceStatus('rtdetr', 'unhealthy'),
          nemotron: createMockServiceStatus('nemotron', 'healthy'),
        }}
        hasUnhealthy={true}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Degraded')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-yellow-500');
  });

  it('shows offline status when all services are unhealthy', () => {
    render(
      <ServiceStatusIndicator
        services={{
          redis: createMockServiceStatus('redis', 'unhealthy'),
          rtdetr: createMockServiceStatus('rtdetr', 'failed'),
          nemotron: createMockServiceStatus('nemotron', 'restart_failed'),
        }}
        hasUnhealthy={true}
        isAnyRestarting={false}
      />
    );

    expect(screen.getByText('Offline')).toBeInTheDocument();
    expect(screen.getByTestId('service-status-dot')).toHaveClass('bg-red-500');
  });

  it('has correct aria attributes', () => {
    render(
      <ServiceStatusIndicator
        services={{ redis: null, rtdetr: null, nemotron: null }}
        hasUnhealthy={false}
        isAnyRestarting={false}
      />
    );

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
            rtdetr: createMockServiceStatus('rtdetr', 'healthy'),
            nemotron: createMockServiceStatus('nemotron', 'healthy'),
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
            rtdetr: createMockServiceStatus('rtdetr', 'healthy'),
            nemotron: createMockServiceStatus('nemotron', 'healthy'),
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
            rtdetr: null,
            nemotron: null,
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
            rtdetr: createMockServiceStatus('rtdetr', 'unhealthy'),
            nemotron: createMockServiceStatus('nemotron', 'restarting'),
          }}
          hasUnhealthy={true}
          isAnyRestarting={true}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');
      fireEvent.mouseEnter(indicator);

      // Check service names are displayed
      expect(screen.getByText('Redis')).toBeInTheDocument();
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();

      // Check status indicators
      expect(screen.getByTestId('service-indicator-redis')).toHaveClass('bg-green-500');
      expect(screen.getByTestId('service-indicator-rtdetr')).toHaveClass('bg-red-500');
      expect(screen.getByTestId('service-indicator-nemotron')).toHaveClass('bg-yellow-500');
    });

    it('shows unhealthy warning in dropdown when hasUnhealthy', () => {
      render(
        <ServiceStatusIndicator
          services={{
            redis: createMockServiceStatus('redis', 'healthy'),
            rtdetr: createMockServiceStatus('rtdetr', 'unhealthy'),
            nemotron: createMockServiceStatus('nemotron', 'healthy'),
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
            rtdetr: createMockServiceStatus('rtdetr', 'restarting'),
            nemotron: createMockServiceStatus('nemotron', 'healthy'),
          }}
          hasUnhealthy={false}
          isAnyRestarting={true}
        />
      );

      const indicator = screen.getByTestId('service-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('Services restarting')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      render(
        <ServiceStatusIndicator
          services={{ redis: null, rtdetr: null, nemotron: null }}
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
            rtdetr: null,
            nemotron: null,
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
            rtdetr: createMockServiceStatus('rtdetr', 'failed'),
            nemotron: createMockServiceStatus('nemotron', 'failed'),
          }}
          hasUnhealthy={true}
          isAnyRestarting={false}
        />
      );

      expect(screen.getByTestId('service-status-dot')).not.toHaveClass('animate-pulse');
    });
  });
});
