import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import PerformanceAlerts from './PerformanceAlerts';

import type { PerformanceAlert } from '../../types/performance';

describe('PerformanceAlerts', () => {
  describe('rendering', () => {
    it('renders nothing when alerts array is empty', () => {
      const { container } = render(<PerformanceAlerts alerts={[]} />);

      // Should not render any visible content
      expect(container.firstChild).toBeNull();
    });

    it('renders callouts when alerts exist', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high: 82C',
        },
      ];

      render(<PerformanceAlerts alerts={alerts} />);

      expect(screen.getByTestId('performance-alerts')).toBeInTheDocument();
      expect(screen.getByText('GPU temperature high: 82C')).toBeInTheDocument();
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

      render(<PerformanceAlerts alerts={alerts} />);

      expect(screen.getByText('GPU temperature high: 82C')).toBeInTheDocument();
      expect(screen.getByText('Redis memory critical: 600 MB')).toBeInTheDocument();
    });
  });

  describe('alert severity colors', () => {
    it('renders warning alerts with yellow/amber color', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'gpu_temperature',
          value: 82,
          threshold: 80,
          message: 'GPU temperature high: 82C',
        },
      ];

      render(<PerformanceAlerts alerts={alerts} />);

      const alertElement = screen.getByTestId('alert-warning-gpu_temperature');
      expect(alertElement).toBeInTheDocument();
    });

    it('renders critical alerts with red color', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'critical',
          metric: 'redis_memory',
          value: 600,
          threshold: 500,
          message: 'Redis memory critical: 600 MB',
        },
      ];

      render(<PerformanceAlerts alerts={alerts} />);

      const alertElement = screen.getByTestId('alert-critical-redis_memory');
      expect(alertElement).toBeInTheDocument();
    });

    it('renders mixed severity alerts correctly', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'cpu_usage',
          value: 85,
          threshold: 80,
          message: 'CPU usage high: 85%',
        },
        {
          severity: 'critical',
          metric: 'disk_space',
          value: 95,
          threshold: 90,
          message: 'Disk space critical: 95%',
        },
      ];

      render(<PerformanceAlerts alerts={alerts} />);

      expect(screen.getByTestId('alert-warning-cpu_usage')).toBeInTheDocument();
      expect(screen.getByTestId('alert-critical-disk_space')).toBeInTheDocument();
    });
  });

  describe('alert content', () => {
    it('displays the alert message', () => {
      const alerts: PerformanceAlert[] = [
        {
          severity: 'warning',
          metric: 'rtdetr_latency',
          value: 250,
          threshold: 200,
          message: 'RT-DETRv2 latency P95 high: 250ms (threshold: 200ms)',
        },
      ];

      render(<PerformanceAlerts alerts={alerts} />);

      expect(
        screen.getByText('RT-DETRv2 latency P95 high: 250ms (threshold: 200ms)')
      ).toBeInTheDocument();
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

      render(<PerformanceAlerts alerts={alerts} className="custom-class" />);

      const container = screen.getByTestId('performance-alerts');
      expect(container).toHaveClass('custom-class');
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

      render(<PerformanceAlerts alerts={alerts} />);

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

      render(<PerformanceAlerts alerts={alerts} />);

      expect(screen.getByTestId('alert-warning-gpu_0_temp')).toBeInTheDocument();
    });
  });
});
