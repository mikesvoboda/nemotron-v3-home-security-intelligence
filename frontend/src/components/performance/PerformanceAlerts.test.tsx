import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, Mock } from 'vitest';

import PerformanceAlerts from './PerformanceAlerts';
import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';

import type { PerformanceAlert } from '../../hooks/usePerformanceMetrics';

// Mock the hook
vi.mock('../../hooks/usePerformanceMetrics');

const mockUsePerformanceMetrics = usePerformanceMetrics as Mock;

function setupMocks(alerts: PerformanceAlert[] = []) {
  mockUsePerformanceMetrics.mockReturnValue({
    current: null,
    history: { '5m': [], '15m': [], '60m': [] },
    alerts,
    isConnected: true,
    timeRange: '5m',
    setTimeRange: vi.fn(),
  });
}

describe('PerformanceAlerts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('empty state', () => {
    it('renders empty state when no alerts exist', () => {
      setupMocks([]);

      render(<PerformanceAlerts />);

      expect(screen.getByTestId('performance-alerts-empty')).toBeInTheDocument();
      expect(screen.getByText('No active alerts')).toBeInTheDocument();
    });

    it('does not render alerts container when empty', () => {
      setupMocks([]);

      render(<PerformanceAlerts />);

      expect(screen.queryByTestId('performance-alerts')).not.toBeInTheDocument();
    });
  });

  describe('rendering alerts', () => {
    it('renders alerts container when alerts exist', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high: 82C',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByTestId('performance-alerts')).toBeInTheDocument();
      expect(screen.queryByTestId('performance-alerts-empty')).not.toBeInTheDocument();
    });

    it('renders title when alerts exist', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'cpu_usage',
          value: 85,
          threshold: 80,
          message: 'CPU usage high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText('Active Alerts')).toBeInTheDocument();
    });

    it('renders multiple alerts', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high: 82C',
        },
        {
          severity: 'critical',
          metric: 'redis_memory',
          value: 600,
          threshold: 500,
          message: 'Redis memory critical: 600 MB',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText('GPU temperature high: 82C')).toBeInTheDocument();
      expect(screen.getByText('Redis memory critical: 600 MB')).toBeInTheDocument();
    });

    it('displays the alert message as callout title', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'rtdetr_latency',
          value: 250,
          threshold: 200,
          message: 'RT-DETRv2 latency P95 high: 250ms (threshold: 200ms)',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(
        screen.getByText('RT-DETRv2 latency P95 high: 250ms (threshold: 200ms)')
      ).toBeInTheDocument();
    });
  });

  describe('alert severity styling', () => {
    it('renders warning alerts with correct test id', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByTestId('alert-warning-gpu_temperature')).toBeInTheDocument();
    });

    it('renders critical alerts with correct test id', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'critical',
          metric: 'redis_memory',
          value: 600,
          threshold: 500,
          message: 'Redis memory critical',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByTestId('alert-critical-redis_memory')).toBeInTheDocument();
    });

    it('renders mixed severity alerts correctly', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'cpu_usage',
          value: 85,
          threshold: 80,
          message: 'CPU usage high',
        },
        {
          severity: 'critical',
          metric: 'disk_space',
          value: 95,
          threshold: 90,
          message: 'Disk space critical',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByTestId('alert-warning-cpu_usage')).toBeInTheDocument();
      expect(screen.getByTestId('alert-critical-disk_space')).toBeInTheDocument();
    });

    it('displays severity badge with uppercase label', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'critical',
          metric: 'test_metric',
          value: 100,
          threshold: 80,
          message: 'Test alert',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    });

    it('displays warning badge for warning alerts', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'test_metric',
          value: 85,
          threshold: 80,
          message: 'Test warning',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText('WARNING')).toBeInTheDocument();
    });
  });

  describe('sorting by severity', () => {
    it('sorts alerts with critical first', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'cpu_usage',
          value: 85,
          threshold: 80,
          message: 'Warning alert first in array',
        },
        {
          severity: 'critical',
          metric: 'disk_space',
          value: 95,
          threshold: 90,
          message: 'Critical alert second in array',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      // Get the callout elements by their testIds
      const criticalCallout = screen.getByTestId('alert-critical-disk_space');
      const warningCallout = screen.getByTestId('alert-warning-cpu_usage');

      // Critical should appear before warning in DOM order
      // Compare using compareDocumentPosition
      const position = criticalCallout.compareDocumentPosition(warningCallout);
      expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('maintains order for alerts of same severity', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'critical',
          metric: 'first_metric',
          value: 95,
          threshold: 90,
          message: 'First critical',
        },
        {
          severity: 'critical',
          metric: 'second_metric',
          value: 98,
          threshold: 90,
          message: 'Second critical',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      const firstCallout = screen.getByTestId('alert-critical-first_metric');
      const secondCallout = screen.getByTestId('alert-critical-second_metric');

      // First should appear before second in DOM order
      const position = firstCallout.compareDocumentPosition(secondCallout);
      expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
  });

  describe('metric display', () => {
    it('displays metric name in title case', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText(/Gpu Temperature:/)).toBeInTheDocument();
    });

    it('displays value vs threshold comparison', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'cpu_usage',
          value: 85,
          threshold: 80,
          message: 'CPU usage high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      // Should show value > threshold format
      expect(screen.getByText(/85/)).toBeInTheDocument();
      expect(screen.getByText(/80/)).toBeInTheDocument();
    });

    it('displays appropriate unit for temperature metrics', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      // Should show temperature unit (degree symbol)
      expect(screen.getByText(/82\u00B0C/)).toBeInTheDocument();
    });

    it('displays appropriate unit for latency metrics', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'rtdetr_latency_ms',
          value: 250,
          threshold: 200,
          message: 'Latency high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText(/250ms/)).toBeInTheDocument();
    });

    it('displays appropriate unit for memory metrics', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'critical',
          metric: 'redis_memory_mb',
          value: 600,
          threshold: 500,
          message: 'Memory high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText(/600MB/)).toBeInTheDocument();
    });

    it('displays appropriate unit for percentage metrics', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'cpu_utilization',
          value: 85,
          threshold: 80,
          message: 'CPU high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText(/85%/)).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className when provided', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'test_metric',
          value: 10,
          threshold: 5,
          message: 'Test alert',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts className="custom-class" />);

      const container = screen.getByTestId('performance-alerts');
      expect(container).toHaveClass('custom-class');
    });

    it('applies custom className to empty state', () => {
      setupMocks([]);

      render(<PerformanceAlerts className="custom-class" />);

      const emptyState = screen.getByTestId('performance-alerts-empty');
      expect(emptyState).toHaveClass('custom-class');
    });
  });

  describe('edge cases', () => {
    it('handles alerts with special characters in messages', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'critical',
          metric: 'db_connections',
          value: 29,
          threshold: 24,
          message: 'PostgreSQL connections: 29/30 (>95% pool)',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByText('PostgreSQL connections: 29/30 (>95% pool)')).toBeInTheDocument();
    });

    it('handles alerts with numeric metric names', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_0_temp',
          value: 76,
          threshold: 75,
          message: 'GPU 0 temperature: 76C',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      expect(screen.getByTestId('alert-warning-gpu_0_temp')).toBeInTheDocument();
    });

    it('handles decimal values correctly', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'vram_gb',
          value: 22.5,
          threshold: 22.0,
          message: 'VRAM high',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      // VRAM should use GB unit
      expect(screen.getByText(/22GB/)).toBeInTheDocument();
    });

    it('handles small decimal values', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'score_threshold',
          value: 0.85,
          threshold: 0.9,
          message: 'Score threshold low',
        },
      ];
      setupMocks(alerts);

      render(<PerformanceAlerts />);

      // Small values (< 1) without percentage keywords should show one decimal
      expect(screen.getByText(/0\.8/)).toBeInTheDocument();
    });
  });

  describe('hook integration', () => {
    it('calls usePerformanceMetrics hook', () => {
      setupMocks([]);

      render(<PerformanceAlerts />);

      expect(mockUsePerformanceMetrics).toHaveBeenCalled();
    });

    it('updates when hook returns new alerts', () => {
      // Initial render with no alerts
      setupMocks([]);
      const { rerender } = render(<PerformanceAlerts />);

      expect(screen.getByText('No active alerts')).toBeInTheDocument();

      // Update mock with alerts
      setupMocks([
        {
          severity: 'warning',
          metric: 'test',
          value: 85,
          threshold: 80,
          message: 'New alert',
        },
      ]);

      rerender(<PerformanceAlerts />);

      expect(screen.getByText('New alert')).toBeInTheDocument();
    });
  });
});
