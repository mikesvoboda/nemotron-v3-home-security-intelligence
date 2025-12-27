import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import ObservabilityPanel, { type GpuMetricDataPoint, type QueueStats } from './ObservabilityPanel';

describe('ObservabilityPanel', () => {
  const defaultProps = {
    gpuUtilization: 50,
    gpuMemoryUsed: 12288,
    gpuMemoryTotal: 24576,
    gpuTemperature: 65,
    healthStatus: 'healthy' as const,
  };

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('System Observability')).toBeInTheDocument();
    });

    it('displays health status indicator', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    it('displays GPU utilization section', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('GPU Utilization Over Time')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('displays GPU memory section', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('GPU Memory')).toBeInTheDocument();
    });

    it('displays temperature section', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('GPU Temperature')).toBeInTheDocument();
      expect(screen.getByText('65')).toBeInTheDocument();
      expect(screen.getByText('Celsius')).toBeInTheDocument();
    });

    it('displays pipeline queue section', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('Pipeline Queue')).toBeInTheDocument();
    });

    it('displays Grafana link section', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText('Detailed Metrics')).toBeInTheDocument();
      expect(screen.getByText('Open Grafana')).toBeInTheDocument();
    });
  });

  describe('health status', () => {
    it('displays healthy status correctly', () => {
      render(<ObservabilityPanel {...defaultProps} healthStatus="healthy" />);
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    it('displays degraded status correctly', () => {
      render(<ObservabilityPanel {...defaultProps} healthStatus="degraded" />);
      expect(screen.getByText('Degraded')).toBeInTheDocument();
    });

    it('displays unhealthy status correctly', () => {
      render(<ObservabilityPanel {...defaultProps} healthStatus="unhealthy" />);
      expect(screen.getByText('Unhealthy')).toBeInTheDocument();
    });

    it('displays unknown status correctly', () => {
      render(<ObservabilityPanel {...defaultProps} healthStatus="unknown" />);
      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });
  });

  describe('GPU metrics', () => {
    it('displays current utilization percentage', () => {
      render(<ObservabilityPanel {...defaultProps} gpuUtilization={75} />);
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('displays N/A for null utilization', () => {
      render(<ObservabilityPanel {...defaultProps} gpuUtilization={null} />);
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays memory values in GB', () => {
      render(
        <ObservabilityPanel
          {...defaultProps}
          gpuMemoryUsed={12288}
          gpuMemoryTotal={24576}
        />
      );
      expect(screen.getByText('12.0 GB')).toBeInTheDocument();
      expect(screen.getByText('24.0 GB')).toBeInTheDocument();
    });

    it('displays N/A for null memory values', () => {
      render(
        <ObservabilityPanel
          {...defaultProps}
          gpuMemoryUsed={null}
          gpuMemoryTotal={null}
        />
      );
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('temperature color coding', () => {
    it('applies green color for safe temperature (<70)', () => {
      render(<ObservabilityPanel {...defaultProps} gpuTemperature={65} />);
      const tempValue = screen.getByText('65');
      expect(tempValue).toHaveClass('text-[#76B900]');
    });

    it('applies yellow color for warning temperature (70-80)', () => {
      render(<ObservabilityPanel {...defaultProps} gpuTemperature={75} />);
      const tempValue = screen.getByText('75');
      expect(tempValue).toHaveClass('text-yellow-500');
    });

    it('applies red color for critical temperature (>80)', () => {
      render(<ObservabilityPanel {...defaultProps} gpuTemperature={85} />);
      const tempValue = screen.getByText('85');
      expect(tempValue).toHaveClass('text-red-500');
    });

    it('applies gray color for null temperature', () => {
      render(<ObservabilityPanel {...defaultProps} gpuTemperature={null} />);
      const naElements = screen.getAllByText('N/A');
      const tempNa = naElements.find((el) => el.closest('[class*="text-gray"]'));
      expect(tempNa).toBeDefined();
    });
  });

  describe('queue statistics', () => {
    it('displays queue stats when provided', () => {
      const queueStats: QueueStats = { pending: 5, processing: 2 };
      render(<ObservabilityPanel {...defaultProps} queueStats={queueStats} />);
      expect(screen.getByText('Pending')).toBeInTheDocument();
      expect(screen.getByText('Processing')).toBeInTheDocument();
    });

    it('displays zero values when queue stats not provided', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      // Should show 0 for both pending and processing
      const zeroElements = screen.getAllByText('0');
      expect(zeroElements.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('GPU history chart', () => {
    it('displays no data message when history is empty', () => {
      render(<ObservabilityPanel {...defaultProps} gpuHistory={[]} />);
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('renders chart when history data is provided', () => {
      const gpuHistory: GpuMetricDataPoint[] = [
        { timestamp: '2024-01-01T10:00:00Z', utilization: 45, memory_used: 10000, temperature: 60 },
        { timestamp: '2024-01-01T10:05:00Z', utilization: 50, memory_used: 11000, temperature: 62 },
        { timestamp: '2024-01-01T10:10:00Z', utilization: 55, memory_used: 12000, temperature: 64 },
      ];
      render(<ObservabilityPanel {...defaultProps} gpuHistory={gpuHistory} />);
      // Chart should be rendered (no "No data available" message)
      expect(screen.queryByText('No data available')).not.toBeInTheDocument();
    });
  });

  describe('Grafana link', () => {
    it('renders default Grafana URL', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      const link = screen.getByRole('link', { name: /open grafana/i });
      expect(link).toHaveAttribute('href', 'http://localhost:3000');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders custom Grafana URL', () => {
      render(
        <ObservabilityPanel {...defaultProps} grafanaUrl="http://custom-grafana:3000" />
      );
      const link = screen.getByRole('link', { name: /open grafana/i });
      expect(link).toHaveAttribute('href', 'http://custom-grafana:3000');
    });

    it('displays URL hint text', () => {
      render(<ObservabilityPanel {...defaultProps} />);
      expect(screen.getByText(/Opens in new tab at/)).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <ObservabilityPanel {...defaultProps} className="custom-test-class" />
      );
      expect(container.firstChild).toHaveClass('custom-test-class');
    });
  });

  describe('edge cases', () => {
    it('handles all null GPU values gracefully', () => {
      render(
        <ObservabilityPanel
          gpuUtilization={null}
          gpuMemoryUsed={null}
          gpuMemoryTotal={null}
          gpuTemperature={null}
          healthStatus="unknown"
        />
      );
      expect(screen.getByText('System Observability')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('handles zero values correctly', () => {
      render(
        <ObservabilityPanel
          gpuUtilization={0}
          gpuMemoryUsed={0}
          gpuMemoryTotal={24576}
          gpuTemperature={0}
          healthStatus="healthy"
        />
      );
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('handles 100% utilization', () => {
      render(<ObservabilityPanel {...defaultProps} gpuUtilization={100} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });
  });
});
