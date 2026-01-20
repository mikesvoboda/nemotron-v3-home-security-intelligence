/**
 * Tests for AlertDrawer component
 *
 * NEM-3123: Phase 3.2 - Prometheus alert UI components
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertDrawer from './AlertDrawer';

import type { PrometheusAlert } from '../../hooks/usePrometheusAlerts';

// ============================================================================
// Test Fixtures
// ============================================================================

const createMockAlert = (overrides: Partial<PrometheusAlert> = {}): PrometheusAlert => ({
  fingerprint: `fp-${Math.random().toString(36).slice(2)}`,
  alertname: 'TestAlert',
  severity: 'warning',
  labels: {
    alertname: 'TestAlert',
    instance: 'localhost:9090',
  },
  annotations: {
    summary: 'Test alert summary',
    description: 'Test alert description',
  },
  startsAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
  receivedAt: new Date().toISOString(),
  ...overrides,
});

const criticalAlert = createMockAlert({
  fingerprint: 'critical-1',
  alertname: 'HighGPUMemory',
  severity: 'critical',
  annotations: {
    summary: 'GPU memory usage critical',
    description: 'GPU memory is above 95%',
  },
});

const warningAlert = createMockAlert({
  fingerprint: 'warning-1',
  alertname: 'HighCPUUsage',
  severity: 'warning',
  annotations: {
    summary: 'CPU usage elevated',
    description: 'CPU usage is above 80%',
  },
});

const infoAlert = createMockAlert({
  fingerprint: 'info-1',
  alertname: 'ServiceRestarted',
  severity: 'info',
  annotations: {
    summary: 'Detection service restarted',
    description: 'The detection service was automatically restarted',
  },
});

const emptyAlertsBySeverity = {
  critical: [],
  warning: [],
  info: [],
};

const mixedAlertsBySeverity = {
  critical: [criticalAlert],
  warning: [warningAlert],
  info: [infoAlert],
};

// ============================================================================
// Tests
// ============================================================================

describe('AlertDrawer', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    alerts: [],
    alertsBySeverity: emptyAlertsBySeverity,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders when open', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.getByTestId('alert-drawer')).toBeInTheDocument();
      expect(screen.getByTestId('alert-drawer-panel')).toBeInTheDocument();
    });

    it('renders title', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.getByTestId('alert-drawer-title')).toHaveTextContent('Active Alerts');
    });

    it('renders close button', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.getByTestId('alert-drawer-close')).toBeInTheDocument();
    });

    it('renders empty state when no alerts', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.getByTestId('alert-drawer-empty')).toBeInTheDocument();
      expect(screen.getByText('No Active Alerts')).toBeInTheDocument();
      expect(screen.getByText('All systems are operating normally.')).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      render(<AlertDrawer {...defaultProps} isOpen={false} />);

      expect(screen.queryByTestId('alert-drawer-panel')).not.toBeInTheDocument();
    });
  });

  describe('alert display', () => {
    it('renders critical alerts section', () => {
      const alerts = [criticalAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, critical: [criticalAlert] }}
        />
      );

      expect(screen.getByTestId('alert-drawer-critical-section')).toBeInTheDocument();
      expect(screen.getByTestId('alert-drawer-severity-header-critical')).toHaveTextContent(
        'CRITICAL'
      );
    });

    it('renders warning alerts section', () => {
      const alerts = [warningAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, warning: [warningAlert] }}
        />
      );

      expect(screen.getByTestId('alert-drawer-warning-section')).toBeInTheDocument();
      expect(screen.getByTestId('alert-drawer-severity-header-warning')).toHaveTextContent(
        'WARNING'
      );
    });

    it('renders info alerts section', () => {
      const alerts = [infoAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, info: [infoAlert] }}
        />
      );

      expect(screen.getByTestId('alert-drawer-info-section')).toBeInTheDocument();
      expect(screen.getByTestId('alert-drawer-severity-header-info')).toHaveTextContent('INFO');
    });

    it('renders all severity sections when mixed alerts', () => {
      const alerts = [criticalAlert, warningAlert, infoAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={mixedAlertsBySeverity}
        />
      );

      expect(screen.getByTestId('alert-drawer-critical-section')).toBeInTheDocument();
      expect(screen.getByTestId('alert-drawer-warning-section')).toBeInTheDocument();
      expect(screen.getByTestId('alert-drawer-info-section')).toBeInTheDocument();
    });

    it('renders alert cards with correct data', () => {
      const alerts = [criticalAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, critical: [criticalAlert] }}
        />
      );

      const card = screen.getByTestId('alert-drawer-card');
      expect(card).toBeInTheDocument();
      expect(screen.getByTestId('alert-card-name')).toHaveTextContent('HighGPUMemory');
      expect(screen.getByTestId('alert-card-summary')).toHaveTextContent('GPU memory usage critical');
      expect(screen.getByTestId('alert-card-description')).toHaveTextContent(
        'GPU memory is above 95%'
      );
    });

    it('renders timestamp', () => {
      const alerts = [criticalAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, critical: [criticalAlert] }}
        />
      );

      // Timestamp should show relative time
      expect(screen.getByTestId('alert-card-timestamp')).toBeInTheDocument();
    });

    it('renders severity count badges', () => {
      const alerts = [criticalAlert, warningAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{
            critical: [criticalAlert],
            warning: [warningAlert],
            info: [],
          }}
        />
      );

      const criticalHeader = screen.getByTestId('alert-drawer-severity-header-critical');
      expect(criticalHeader).toHaveTextContent('1');

      const warningHeader = screen.getByTestId('alert-drawer-severity-header-warning');
      expect(warningHeader).toHaveTextContent('1');
    });
  });

  describe('resolved alerts', () => {
    it('renders resolved alerts section when provided', () => {
      const resolvedAlert = createMockAlert({
        fingerprint: 'resolved-1',
        alertname: 'ResolvedAlert',
        severity: 'warning',
      });

      render(
        <AlertDrawer
          {...defaultProps}
          alerts={[warningAlert]}
          alertsBySeverity={{ ...emptyAlertsBySeverity, warning: [warningAlert] }}
          resolvedAlerts={[resolvedAlert]}
        />
      );

      expect(screen.getByTestId('alert-drawer-resolved-section')).toBeInTheDocument();
      expect(screen.getByText('Recently Resolved')).toBeInTheDocument();
    });

    it('renders resolved badge on resolved alerts', () => {
      const resolvedAlert = createMockAlert({
        fingerprint: 'resolved-1',
        alertname: 'ResolvedAlert',
        severity: 'warning',
      });

      render(
        <AlertDrawer
          {...defaultProps}
          alerts={[warningAlert]}
          alertsBySeverity={{ ...emptyAlertsBySeverity, warning: [warningAlert] }}
          resolvedAlerts={[resolvedAlert]}
        />
      );

      expect(screen.getByTestId('alert-card-resolved-badge')).toHaveTextContent('Resolved');
    });
  });

  describe('interactivity', () => {
    it('calls onClose when close button is clicked', () => {
      const onClose = vi.fn();
      render(<AlertDrawer {...defaultProps} onClose={onClose} />);

      fireEvent.click(screen.getByTestId('alert-drawer-close'));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('renders backdrop for click-outside dismissal', () => {
      render(<AlertDrawer {...defaultProps} />);

      // Verify backdrop is rendered for click-outside behavior
      // Note: Actual click-outside behavior is handled by Headless UI Dialog
      // and tested at the integration level
      expect(screen.getByTestId('alert-drawer-backdrop')).toBeInTheDocument();
    });
  });

  describe('footer', () => {
    it('renders footer with alert count when has alerts', () => {
      const alerts = [criticalAlert, warningAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{
            critical: [criticalAlert],
            warning: [warningAlert],
            info: [],
          }}
        />
      );

      expect(screen.getByText('2 active alerts')).toBeInTheDocument();
    });

    it('renders singular alert text for single alert', () => {
      const alerts = [criticalAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, critical: [criticalAlert] }}
        />
      );

      expect(screen.getByText('1 active alert')).toBeInTheDocument();
    });

    it('does not render footer when no alerts', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.queryByText(/active alert/)).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has dialog role', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('close button has aria-label', () => {
      render(<AlertDrawer {...defaultProps} />);

      expect(screen.getByLabelText('Close alert drawer')).toBeInTheDocument();
    });

    it('alerts have data-alert-fingerprint attribute', () => {
      const alerts = [criticalAlert];
      render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={{ ...emptyAlertsBySeverity, critical: [criticalAlert] }}
        />
      );

      const card = screen.getByTestId('alert-drawer-card');
      expect(card).toHaveAttribute('data-alert-fingerprint', 'critical-1');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<AlertDrawer {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('alert-drawer-panel')).toHaveClass('custom-class');
    });

    it('has NVIDIA dark theme styling', () => {
      render(<AlertDrawer {...defaultProps} />);

      const panel = screen.getByTestId('alert-drawer-panel');
      expect(panel).toHaveClass('bg-nvidia-bg', 'border-nvidia-border');
    });
  });

  describe('snapshots', () => {
    it('renders empty state correctly', () => {
      const { container } = render(<AlertDrawer {...defaultProps} />);
      expect(container).toMatchSnapshot();
    });

    it('renders with alerts correctly', () => {
      const alerts = [criticalAlert, warningAlert, infoAlert];
      const { container } = render(
        <AlertDrawer
          {...defaultProps}
          alerts={alerts}
          alertsBySeverity={mixedAlertsBySeverity}
        />
      );
      expect(container).toMatchSnapshot();
    });

    it('renders with resolved alerts correctly', () => {
      const resolvedAlert = createMockAlert({
        fingerprint: 'resolved-1',
        alertname: 'ResolvedAlert',
        severity: 'warning',
      });

      const { container } = render(
        <AlertDrawer
          {...defaultProps}
          alerts={[warningAlert]}
          alertsBySeverity={{ ...emptyAlertsBySeverity, warning: [warningAlert] }}
          resolvedAlerts={[resolvedAlert]}
        />
      );
      expect(container).toMatchSnapshot();
    });
  });
});
