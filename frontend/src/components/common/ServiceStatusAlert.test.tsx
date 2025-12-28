import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ServiceStatusAlert, ServiceName, ServiceStatus } from './ServiceStatusAlert';

/**
 * Tests for ServiceStatusAlert component.
 *
 * NOTE: This component is currently DEPRECATED because useServiceStatus hook
 * (which would provide data for this component) is not wired up on the backend.
 * The backend's ServiceHealthMonitor exists but is not initialized in main.py.
 *
 * These tests are retained for when/if the backend is wired up in the future.
 *
 * See bead vq8.11 for context.
 */

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

describe('ServiceStatusAlert (DEPRECATED - backend not wired)', () => {
  describe('visibility', () => {
    it('returns null when all services are null', () => {
      const services = createEmptyServices();
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when all services are healthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'healthy'),
        rtdetr: createServiceStatus('rtdetr', 'healthy'),
        nemotron: createServiceStatus('nemotron', 'healthy'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when some services are null and rest are healthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'healthy'),
        rtdetr: null,
        nemotron: createServiceStatus('nemotron', 'healthy'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders alert when any service is unhealthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'healthy'),
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('status styling', () => {
    it('shows yellow styling for restarting status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'restarting'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-yellow-100', 'text-yellow-800');
    });

    it('shows red styling for unhealthy status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows red styling for restart_failed status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'restart_failed'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows darker red styling for failed status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: null,
        nemotron: createServiceStatus('nemotron', 'failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-200', 'text-red-900');
    });
  });

  describe('status titles', () => {
    it('shows "Service Restarting" title for restarting status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'restarting'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Restarting')).toBeInTheDocument();
    });

    it('shows "Service Unhealthy" title for unhealthy status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Unhealthy')).toBeInTheDocument();
    });

    it('shows "Restart Failed" title for restart_failed status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'restart_failed'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Restart Failed')).toBeInTheDocument();
    });

    it('shows "Service Failed" title for failed status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: null,
        nemotron: createServiceStatus('nemotron', 'failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Failed')).toBeInTheDocument();
    });
  });

  describe('service name formatting', () => {
    it('displays Redis correctly', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Redis')).toBeInTheDocument();
    });

    it('displays RT-DETRv2 correctly', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('displays Nemotron correctly', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: null,
        nemotron: createServiceStatus('nemotron', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });
  });

  describe('message display', () => {
    it('displays service name with message when message is provided', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'restarting', 'Attempting restart (attempt 2/3)'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Redis: Attempting restart (attempt 2/3)')).toBeInTheDocument();
    });

    it('displays service name without message when message is not provided', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Redis')).toBeInTheDocument();
    });
  });

  describe('multiple services', () => {
    it('lists all affected services when multiple are unhealthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText(/Affected:/)).toBeInTheDocument();
      expect(screen.getByText(/Redis/)).toBeInTheDocument();
      expect(screen.getByText(/RT-DETRv2/)).toBeInTheDocument();
    });

    it('shows worst status when services have different statuses', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'restarting'),
        rtdetr: createServiceStatus('rtdetr', 'failed'),
        nemotron: createServiceStatus('nemotron', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      // Failed is worst, should show failed styling and title
      expect(screen.getByText('Service Failed')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveClass('bg-red-200', 'text-red-900');
    });

    it('shows restart_failed over unhealthy', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: createServiceStatus('rtdetr', 'restart_failed'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Restart Failed')).toBeInTheDocument();
    });

    it('shows unhealthy over restarting', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'restarting'),
        rtdetr: createServiceStatus('rtdetr', 'unhealthy'),
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Unhealthy')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveClass('bg-red-100', 'text-red-800');
    });
  });

  describe('icons', () => {
    it('renders spinning RefreshCw icon for restarting status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'restarting'),
        rtdetr: null,
        nemotron: null,
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg.lucide-refresh-cw');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass('animate-spin');
    });

    it('renders AlertTriangle icon for unhealthy status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg.lucide-triangle-alert');
      expect(svg).toBeInTheDocument();
    });

    it('renders XCircle icon for restart_failed status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: createServiceStatus('rtdetr', 'restart_failed'),
        nemotron: null,
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-x');
    });

    it('renders XCircle icon for failed status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: null,
        rtdetr: null,
        nemotron: createServiceStatus('nemotron', 'failed'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-x');
    });
  });

  describe('dismiss button', () => {
    it('renders dismiss button when onDismiss is provided', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} onDismiss={() => {}} />);
      expect(screen.getByLabelText('Dismiss alert')).toBeInTheDocument();
    });

    it('does not render dismiss button when onDismiss is not provided', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.queryByLabelText('Dismiss alert')).not.toBeInTheDocument();
    });

    it('calls onDismiss when dismiss button is clicked', () => {
      const onDismiss = vi.fn();
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} onDismiss={onDismiss} />);

      fireEvent.click(screen.getByLabelText('Dismiss alert'));
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('has yellow focus ring for restarting status', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'restarting'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} onDismiss={() => {}} />);
      const button = screen.getByLabelText('Dismiss alert');
      expect(button).toHaveClass('focus:ring-yellow-500');
    });

    it('has red focus ring for error statuses', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} onDismiss={() => {}} />);
      const button = screen.getByLabelText('Dismiss alert');
      expect(button).toHaveClass('focus:ring-red-500');
    });
  });

  describe('accessibility', () => {
    it('has role="alert"', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('has aria-live="polite"', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'polite');
    });

    it('icons have aria-hidden="true"', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const icons = container.querySelectorAll('svg');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  describe('styling', () => {
    it('has rounded corners', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass('rounded-lg');
    });

    it('has padding', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass('p-4');
    });

    it('has bottom margin', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass('mb-4');
    });

    it('has transition classes for animation', () => {
      const services: Record<ServiceName, ServiceStatus | null> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        rtdetr: null,
        nemotron: null,
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass(
        'transition-all',
        'duration-300',
        'ease-in-out'
      );
    });
  });
});
