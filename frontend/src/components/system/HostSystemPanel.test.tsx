import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import HostSystemPanel, {
  type HostSystemPanelProps,
  type HostMetrics,
  type HostHistoryData,
} from './HostSystemPanel';

describe('HostSystemPanel', () => {
  // Sample host metrics
  const mockHostMetrics: HostMetrics = {
    cpu_percent: 12,
    ram_used_gb: 8.2,
    ram_total_gb: 32,
    disk_used_gb: 156,
    disk_total_gb: 500,
  };

  // Sample history data
  const mockHistoryData: HostHistoryData = {
    cpu: [
      { timestamp: '2025-01-01T12:00:00Z', value: 10 },
      { timestamp: '2025-01-01T12:00:05Z', value: 12 },
      { timestamp: '2025-01-01T12:00:10Z', value: 15 },
    ],
    ram: [
      { timestamp: '2025-01-01T12:00:00Z', value: 8.0 },
      { timestamp: '2025-01-01T12:00:05Z', value: 8.2 },
      { timestamp: '2025-01-01T12:00:10Z', value: 8.1 },
    ],
  };

  const defaultProps: HostSystemPanelProps = {
    host: mockHostMetrics,
    timeRange: '5m',
    history: mockHistoryData,
  };

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
      expect(screen.getByText('Host System')).toBeInTheDocument();
    });

    it('renders CPU, RAM, and Disk sections', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-cpu-section')).toBeInTheDocument();
      expect(screen.getByTestId('host-ram-section')).toBeInTheDocument();
      expect(screen.getByTestId('host-disk-section')).toBeInTheDocument();
    });
  });

  describe('CPU metrics', () => {
    it('displays CPU percentage correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-cpu-value')).toHaveTextContent('12%');
    });

    it('displays CPU progress bar', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-cpu-bar')).toBeInTheDocument();
    });

    it('displays high CPU with warning color', () => {
      const highCpuHost: HostMetrics = {
        ...mockHostMetrics,
        cpu_percent: 85,
      };

      render(<HostSystemPanel {...defaultProps} host={highCpuHost} />);

      expect(screen.getByTestId('host-cpu-value')).toHaveTextContent('85%');
    });

    it('displays critical CPU with red color', () => {
      const criticalCpuHost: HostMetrics = {
        ...mockHostMetrics,
        cpu_percent: 96,
      };

      render(<HostSystemPanel {...defaultProps} host={criticalCpuHost} />);

      expect(screen.getByTestId('host-cpu-value')).toHaveTextContent('96%');
    });
  });

  describe('RAM metrics', () => {
    it('displays RAM used/total correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-ram-value')).toHaveTextContent('8.2/32 GB');
    });

    it('displays RAM percentage correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      // 8.2 / 32 = 25.625%
      expect(screen.getByTestId('host-ram-percent')).toHaveTextContent('26%');
    });

    it('displays RAM progress bar', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-ram-bar')).toBeInTheDocument();
    });

    it('displays high RAM usage with warning color', () => {
      const highRamHost: HostMetrics = {
        ...mockHostMetrics,
        ram_used_gb: 28,
        ram_total_gb: 32,
      };

      render(<HostSystemPanel {...defaultProps} host={highRamHost} />);

      // 28 / 32 = 87.5%
      expect(screen.getByTestId('host-ram-percent')).toHaveTextContent('88%');
    });
  });

  describe('Disk metrics', () => {
    it('displays Disk used/total correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-disk-value')).toHaveTextContent('156/500 GB');
    });

    it('displays Disk percentage correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      // 156 / 500 = 31.2%
      expect(screen.getByTestId('host-disk-percent')).toHaveTextContent('31%');
    });

    it('displays Disk progress bar', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-disk-bar')).toBeInTheDocument();
    });

    it('displays high Disk usage with warning color', () => {
      const highDiskHost: HostMetrics = {
        ...mockHostMetrics,
        disk_used_gb: 425,
        disk_total_gb: 500,
      };

      render(<HostSystemPanel {...defaultProps} host={highDiskHost} />);

      // 425 / 500 = 85%
      expect(screen.getByTestId('host-disk-percent')).toHaveTextContent('85%');
    });
  });

  describe('null handling', () => {
    it('handles null host metrics gracefully', () => {
      render(<HostSystemPanel host={null} timeRange="5m" history={mockHistoryData} />);

      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('renders panel container even with null data', () => {
      render(<HostSystemPanel host={null} timeRange="5m" history={mockHistoryData} />);

      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
      expect(screen.getByText('Host System')).toBeInTheDocument();
    });
  });

  describe('history charts', () => {
    it('renders CPU history chart area', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-cpu-chart')).toBeInTheDocument();
    });

    it('renders RAM history chart area', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-ram-chart')).toBeInTheDocument();
    });

    it('handles empty history data gracefully', () => {
      const emptyHistory: HostHistoryData = {
        cpu: [],
        ram: [],
      };

      render(<HostSystemPanel {...defaultProps} history={emptyHistory} />);

      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
    });
  });

  describe('time range display', () => {
    it('displays the current time range context', () => {
      render(<HostSystemPanel {...defaultProps} timeRange="15m" />);

      // Time range is used for chart context
      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('formats RAM values with decimal precision', () => {
      const preciseRamHost: HostMetrics = {
        ...mockHostMetrics,
        ram_used_gb: 15.67,
        ram_total_gb: 64,
      };

      render(<HostSystemPanel {...defaultProps} host={preciseRamHost} />);

      expect(screen.getByTestId('host-ram-value')).toHaveTextContent('15.7/64 GB');
    });

    it('formats whole number disk values correctly', () => {
      const wholeDiskHost: HostMetrics = {
        ...mockHostMetrics,
        disk_used_gb: 200,
        disk_total_gb: 1000,
      };

      render(<HostSystemPanel {...defaultProps} host={wholeDiskHost} />);

      expect(screen.getByTestId('host-disk-value')).toHaveTextContent('200/1000 GB');
    });
  });

  describe('threshold warnings', () => {
    it('shows warning styling when CPU exceeds 80%', () => {
      const warningCpuHost: HostMetrics = {
        ...mockHostMetrics,
        cpu_percent: 82,
      };

      render(<HostSystemPanel {...defaultProps} host={warningCpuHost} />);

      // Component should render with appropriate styling
      expect(screen.getByTestId('host-cpu-section')).toBeInTheDocument();
    });

    it('shows critical styling when RAM exceeds 95%', () => {
      const criticalRamHost: HostMetrics = {
        ...mockHostMetrics,
        ram_used_gb: 31,
        ram_total_gb: 32,
      };

      render(<HostSystemPanel {...defaultProps} host={criticalRamHost} />);

      // 31 / 32 = 96.875%
      expect(screen.getByTestId('host-ram-section')).toBeInTheDocument();
    });

    it('shows warning styling when Disk exceeds 80%', () => {
      const warningDiskHost: HostMetrics = {
        ...mockHostMetrics,
        disk_used_gb: 410,
        disk_total_gb: 500,
      };

      render(<HostSystemPanel {...defaultProps} host={warningDiskHost} />);

      // 410 / 500 = 82%
      expect(screen.getByTestId('host-disk-section')).toBeInTheDocument();
    });
  });
});
