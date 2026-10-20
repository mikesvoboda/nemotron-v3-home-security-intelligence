import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ServiceStatusAlert, ServiceName, ServiceStatus } from './ServiceStatusAlert';

/**
 * Tests for ServiceStatusAlert component.
 *
 * This component displays service health status alerts based on data from
 * the useServiceStatus hook, which receives `service_status` WebSocket messages
 * broadcast through the backend's validating funnel. The fixture names map to
 * the live emitters: `yolo26` (ServiceHealthMonitor), `postgres`/`redis`
 * (ContainerOrchestrator), `worker:detection-0` (WorkerSupervisor).
 */

// Helper to create service status
function createServiceStatus(
  service: ServiceName,
  status: ServiceStatus['status'],
  message?: string | null
): ServiceStatus {
  return {
    service,
    status,
    message,
    timestamp: '2025-12-26T12:00:00Z',
  };
}

// Helper to create empty services record (the hook's map starts empty)
function createEmptyServices(): Partial<Record<ServiceName, ServiceStatus>> {
  return {};
}

describe('ServiceStatusAlert', () => {
  describe('visibility', () => {
    it('returns null when no service has reported', () => {
      const services = createEmptyServices();
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when all reported services are healthy or running', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'running', null),
        yolo26: createServiceStatus('yolo26', 'healthy'),
        postgres: createServiceStatus('postgres', 'running', null),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when some services are unreported and rest are healthy', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'healthy'),
        yolo26: createServiceStatus('yolo26', 'healthy'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders alert when any service is unhealthy', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'healthy'),
        yolo26: createServiceStatus('yolo26', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('status styling', () => {
    it('shows yellow styling for restarting status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        yolo26: createServiceStatus('yolo26', 'restarting'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-yellow-100', 'text-yellow-800');
    });

    it('shows red styling for unhealthy status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows red styling for restart_failed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        yolo26: createServiceStatus('yolo26', 'restart_failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows darker red styling for failed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'worker:detection-0': createServiceStatus('worker:detection-0', 'failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-200', 'text-red-900');
    });

    it('shows red styling for crashed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'worker:analysis-0': createServiceStatus('worker:analysis-0', 'crashed'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows red styling for stopped status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        backend: createServiceStatus('backend', 'stopped', null),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows yellow styling for disabled status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        backend: createServiceStatus('backend', 'disabled', null),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('bg-yellow-100', 'text-yellow-800');
    });

    it('ignores running status (orchestrator healthy state)', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        postgres: createServiceStatus('postgres', 'running', null),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('status titles', () => {
    it('shows "Service Restarting" title for restarting status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'restarting'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Restarting')).toBeInTheDocument();
    });

    it('shows "Service Unhealthy" title for unhealthy status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Unhealthy')).toBeInTheDocument();
    });

    it('shows "Restart Failed" title for restart_failed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        yolo26: createServiceStatus('yolo26', 'restart_failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Restart Failed')).toBeInTheDocument();
    });

    it('shows "Service Failed" title for failed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'worker:detection-0': createServiceStatus('worker:detection-0', 'failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Failed')).toBeInTheDocument();
    });

    it('shows "Service Crashed" title for crashed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'worker:detection-0': createServiceStatus('worker:detection-0', 'crashed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Crashed')).toBeInTheDocument();
    });

    it('shows "Service Stopped" title for stopped status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        backend: createServiceStatus('backend', 'stopped', null),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Stopped')).toBeInTheDocument();
    });

    it('shows "Service Disabled" title for disabled status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        backend: createServiceStatus('backend', 'disabled', null),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Disabled')).toBeInTheDocument();
    });
  });

  describe('service name formatting', () => {
    it('displays Redis correctly', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Redis')).toBeInTheDocument();
    });

    it('displays YOLO26 correctly', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        yolo26: createServiceStatus('yolo26', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('YOLO26')).toBeInTheDocument();
    });

    it('displays container names via the label map', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'ai-gateway': createServiceStatus('ai-gateway', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('AI Gateway')).toBeInTheDocument();
    });

    it('falls back to dash-as-space for unmapped container names', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'node-exporter': createServiceStatus('node-exporter', 'stopped', null),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('node exporter')).toBeInTheDocument();
    });

    it('falls back to dash-as-space for worker names', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'worker:detection-0': createServiceStatus('worker:detection-0', 'failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('worker:detection-0'.replace(/-/g, ' '))).toBeInTheDocument();
    });
  });

  describe('message display', () => {
    it('displays service name with message when message is provided', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'restarting', 'Attempting restart (attempt 2/3)'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Redis: Attempting restart (attempt 2/3)')).toBeInTheDocument();
    });

    it('displays service name without message when message is not provided', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Redis')).toBeInTheDocument();
    });

    it('displays service name alone when message is null (orchestrator/worker wire shape)', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        postgres: createServiceStatus('postgres', 'unhealthy', null),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
    });
  });

  describe('multiple services', () => {
    it('lists all affected services when multiple are unhealthy', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        yolo26: createServiceStatus('yolo26', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText(/Affected:/)).toBeInTheDocument();
      expect(screen.getByText(/Redis/)).toBeInTheDocument();
      expect(screen.getByText(/YOLO26/)).toBeInTheDocument();
    });

    it('shows worst status when services have different statuses', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'restarting'),
        yolo26: createServiceStatus('yolo26', 'failed'),
        postgres: createServiceStatus('postgres', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      // Failed is worst, should show failed styling and title
      expect(screen.getByText('Service Failed')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveClass('bg-red-200', 'text-red-900');
    });

    it('shows restart_failed over unhealthy', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
        yolo26: createServiceStatus('yolo26', 'restart_failed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Restart Failed')).toBeInTheDocument();
    });

    it('shows unhealthy over restarting', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'restarting'),
        yolo26: createServiceStatus('yolo26', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Unhealthy')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('shows crashed over stopped', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        backend: createServiceStatus('backend', 'stopped', null),
        'worker:detection-0': createServiceStatus('worker:detection-0', 'crashed'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByText('Service Crashed')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders spinning RefreshCw icon for restarting status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'restarting'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg.lucide-refresh-cw');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass('animate-spin');
    });

    it('renders AlertTriangle icon for unhealthy status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg.lucide-triangle-alert');
      expect(svg).toBeInTheDocument();
    });

    it('renders XCircle icon for restart_failed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        yolo26: createServiceStatus('yolo26', 'restart_failed'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-x');
    });

    it('renders XCircle icon for failed status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        'worker:detection-0': createServiceStatus('worker:detection-0', 'failed'),
      };
      const { container } = render(<ServiceStatusAlert services={services} />);
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-circle-x');
    });
  });

  describe('dismiss button', () => {
    it('renders dismiss button when onDismiss is provided', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} onDismiss={() => {}} />);
      expect(screen.getByLabelText('Dismiss alert')).toBeInTheDocument();
    });

    it('does not render dismiss button when onDismiss is not provided', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.queryByLabelText('Dismiss alert')).not.toBeInTheDocument();
    });

    it('calls onDismiss when dismiss button is clicked', () => {
      const onDismiss = vi.fn();
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} onDismiss={onDismiss} />);

      fireEvent.click(screen.getByLabelText('Dismiss alert'));
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('has yellow focus ring for restarting status', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'restarting'),
      };
      render(<ServiceStatusAlert services={services} onDismiss={() => {}} />);
      const button = screen.getByLabelText('Dismiss alert');
      expect(button).toHaveClass('focus:ring-yellow-500');
    });

    it('has red focus ring for error statuses', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} onDismiss={() => {}} />);
      const button = screen.getByLabelText('Dismiss alert');
      expect(button).toHaveClass('focus:ring-red-500');
    });
  });

  describe('accessibility', () => {
    it('has role="alert"', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('has aria-live="polite"', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'polite');
    });

    it('icons have aria-hidden="true"', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
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
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass('rounded-lg');
    });

    it('has padding', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass('p-4');
    });

    it('has bottom margin', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
      };
      render(<ServiceStatusAlert services={services} />);
      expect(screen.getByRole('alert')).toHaveClass('mb-4');
    });

    it('has transition classes for animation', () => {
      const services: Partial<Record<ServiceName, ServiceStatus>> = {
        redis: createServiceStatus('redis', 'unhealthy'),
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
