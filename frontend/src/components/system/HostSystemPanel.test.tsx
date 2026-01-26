import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import HostSystemPanel, {
  type HostSystemPanelProps,
  type HostSystemMetrics,
  type SystemStats,
} from './HostSystemPanel';

describe('HostSystemPanel', () => {
  // Sample host metrics
  const mockMetrics: HostSystemMetrics = {
    cpu_percent: 25.5,
    ram_used_gb: 8.2,
    ram_total_gb: 32,
    disk_used_gb: 156,
    disk_total_gb: 500,
  };

  // Sample system stats
  const mockStats: SystemStats = {
    uptime_seconds: 86400 + 3600 + 120, // 1d 1h 2m
    total_cameras: 4,
    total_events: 1000,
    total_detections: 5000,
  };

  const defaultProps: HostSystemPanelProps = {
    metrics: mockMetrics,
    stats: mockStats,
  };

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
      expect(screen.getByText('Host System')).toBeInTheDocument();
    });

    it('renders custom data-testid', () => {
      render(<HostSystemPanel {...defaultProps} data-testid="custom-panel" />);

      expect(screen.getByTestId('custom-panel')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<HostSystemPanel {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('host-system-panel')).toHaveClass('custom-class');
    });
  });

  describe('CPU metrics', () => {
    it('displays CPU usage correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('cpu-metric')).toBeInTheDocument();
      expect(screen.getByTestId('cpu-value')).toHaveTextContent('25.5%');
      expect(screen.getByTestId('cpu-progress')).toBeInTheDocument();
    });

    it('shows green color for low CPU usage', () => {
      render(<HostSystemPanel {...defaultProps} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-green-400');
    });

    it('shows yellow color for warning CPU usage', () => {
      const warningMetrics = { ...mockMetrics, cpu_percent: 85 };
      render(<HostSystemPanel metrics={warningMetrics} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-yellow-400');
    });

    it('shows red color for critical CPU usage', () => {
      const criticalMetrics = { ...mockMetrics, cpu_percent: 96 };
      render(<HostSystemPanel metrics={criticalMetrics} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-red-400');
    });
  });

  describe('RAM metrics', () => {
    it('displays RAM usage correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('ram-metric')).toBeInTheDocument();
      expect(screen.getByTestId('ram-value')).toHaveTextContent('8.2 GB / 32.0 GB (26%)');
      expect(screen.getByTestId('ram-progress')).toBeInTheDocument();
    });

    it('formats large RAM values in TB', () => {
      const largeRamMetrics = { ...mockMetrics, ram_used_gb: 1200, ram_total_gb: 2000 };
      render(<HostSystemPanel metrics={largeRamMetrics} />);

      expect(screen.getByTestId('ram-value')).toHaveTextContent('1.20 TB / 2.00 TB');
    });

    it('applies warning threshold for RAM (85%)', () => {
      const warningRamMetrics = { ...mockMetrics, ram_used_gb: 28, ram_total_gb: 32 }; // 87.5%
      render(<HostSystemPanel metrics={warningRamMetrics} />);

      // Status badge should reflect warning
      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Warning');
    });
  });

  describe('disk metrics', () => {
    it('displays disk usage correctly', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('disk-metric')).toBeInTheDocument();
      expect(screen.getByTestId('disk-value')).toHaveTextContent('156.0 GB / 500.0 GB (31%)');
      expect(screen.getByTestId('disk-progress')).toBeInTheDocument();
    });

    it('applies warning threshold for disk (80%)', () => {
      const warningDiskMetrics = { ...mockMetrics, disk_used_gb: 420, disk_total_gb: 500 }; // 84%
      render(<HostSystemPanel metrics={warningDiskMetrics} />);

      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Warning');
    });

    it('applies critical threshold for disk (90%)', () => {
      const criticalDiskMetrics = { ...mockMetrics, disk_used_gb: 460, disk_total_gb: 500 }; // 92%
      render(<HostSystemPanel metrics={criticalDiskMetrics} />);

      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Critical');
    });
  });

  describe('uptime display', () => {
    it('displays uptime with days, hours, and minutes', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByTestId('uptime-metric')).toBeInTheDocument();
      expect(screen.getByTestId('uptime-value')).toHaveTextContent('1d 1h 2m');
    });

    it('displays uptime without days when less than a day', () => {
      const shortUptime = { ...mockStats, uptime_seconds: 3660 }; // 1h 1m
      render(<HostSystemPanel metrics={mockMetrics} stats={shortUptime} />);

      expect(screen.getByTestId('uptime-value')).toHaveTextContent('1h 1m');
    });

    it('displays uptime in minutes when less than an hour', () => {
      const veryShortUptime = { ...mockStats, uptime_seconds: 300 }; // 5m
      render(<HostSystemPanel metrics={mockMetrics} stats={veryShortUptime} />);

      expect(screen.getByTestId('uptime-value')).toHaveTextContent('5m');
    });

    it('does not display uptime section when stats is null', () => {
      render(<HostSystemPanel metrics={mockMetrics} stats={null} />);

      expect(screen.queryByTestId('uptime-metric')).not.toBeInTheDocument();
    });

    it('does not display uptime section when stats is undefined', () => {
      render(<HostSystemPanel metrics={mockMetrics} />);

      expect(screen.queryByTestId('uptime-metric')).not.toBeInTheDocument();
    });
  });

  describe('system info display', () => {
    it('displays hostname when provided', () => {
      render(<HostSystemPanel {...defaultProps} hostname="my-server" />);

      expect(screen.getByTestId('host-hostname')).toBeInTheDocument();
      expect(screen.getByTestId('host-hostname')).toHaveTextContent('my-server');
    });

    it('displays OS info when provided', () => {
      render(<HostSystemPanel {...defaultProps} osInfo="Linux 6.1.0" />);

      expect(screen.getByTestId('host-os-info')).toBeInTheDocument();
      expect(screen.getByTestId('host-os-info')).toHaveTextContent('Linux 6.1.0');
    });

    it('displays both hostname and OS info', () => {
      render(<HostSystemPanel {...defaultProps} hostname="prod-server" osInfo="Ubuntu 22.04" />);

      expect(screen.getByTestId('host-hostname')).toHaveTextContent('prod-server');
      expect(screen.getByTestId('host-os-info')).toHaveTextContent('Ubuntu 22.04');
    });

    it('does not display system info section when neither provided', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.queryByTestId('host-hostname')).not.toBeInTheDocument();
      expect(screen.queryByTestId('host-os-info')).not.toBeInTheDocument();
    });
  });

  describe('status badge', () => {
    it('shows Healthy badge when all metrics are normal', () => {
      render(<HostSystemPanel {...defaultProps} />);

      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Healthy');
    });

    it('shows Warning badge when CPU is high', () => {
      const warningMetrics = { ...mockMetrics, cpu_percent: 85 };
      render(<HostSystemPanel metrics={warningMetrics} />);

      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Warning');
    });

    it('shows Critical badge when CPU is critical', () => {
      const criticalMetrics = { ...mockMetrics, cpu_percent: 98 };
      render(<HostSystemPanel metrics={criticalMetrics} />);

      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Critical');
    });

    it('shows Critical badge when RAM is critical (95%+)', () => {
      const criticalRamMetrics = { ...mockMetrics, ram_used_gb: 31, ram_total_gb: 32 }; // 96.9%
      render(<HostSystemPanel metrics={criticalRamMetrics} />);

      const statusBadge = screen.getByTestId('host-status-badge');
      expect(statusBadge).toHaveTextContent('Critical');
    });
  });

  describe('loading state', () => {
    it('displays loading skeleton when isLoading is true', () => {
      render(<HostSystemPanel metrics={null} isLoading={true} />);

      expect(screen.getByTestId('host-system-panel-loading')).toBeInTheDocument();
      expect(screen.getByText('Host System')).toBeInTheDocument();
    });

    it('shows animated pulse elements during loading', () => {
      render(<HostSystemPanel metrics={null} isLoading={true} />);

      const loadingPanel = screen.getByTestId('host-system-panel-loading');
      const pulseElements = loadingPanel.querySelectorAll('.animate-pulse');
      expect(pulseElements.length).toBeGreaterThan(0);
    });
  });

  describe('error state', () => {
    it('displays error message when error is provided', () => {
      render(<HostSystemPanel metrics={null} error="Failed to fetch host metrics" />);

      expect(screen.getByTestId('host-system-panel-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to fetch host metrics')).toBeInTheDocument();
    });

    it('shows error styling', () => {
      render(<HostSystemPanel metrics={null} error="Connection timeout" />);

      expect(screen.getByText('Connection timeout')).toHaveClass('text-red-400');
    });
  });

  describe('null handling', () => {
    it('handles null metrics gracefully', () => {
      render(<HostSystemPanel metrics={null} />);

      expect(screen.getByTestId('host-system-panel')).toBeInTheDocument();
      expect(screen.getByText('No host data available')).toBeInTheDocument();
    });

    it('does not show any metric sections when metrics is null', () => {
      render(<HostSystemPanel metrics={null} />);

      expect(screen.queryByTestId('cpu-metric')).not.toBeInTheDocument();
      expect(screen.queryByTestId('ram-metric')).not.toBeInTheDocument();
      expect(screen.queryByTestId('disk-metric')).not.toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles zero CPU usage', () => {
      const zeroMetrics = { ...mockMetrics, cpu_percent: 0 };
      render(<HostSystemPanel metrics={zeroMetrics} />);

      expect(screen.getByTestId('cpu-value')).toHaveTextContent('0.0%');
    });

    it('handles 100% CPU usage', () => {
      const fullMetrics = { ...mockMetrics, cpu_percent: 100 };
      render(<HostSystemPanel metrics={fullMetrics} />);

      expect(screen.getByTestId('cpu-value')).toHaveTextContent('100.0%');
    });

    it('handles very small RAM values', () => {
      const smallRamMetrics = { ...mockMetrics, ram_used_gb: 0.5, ram_total_gb: 1 };
      render(<HostSystemPanel metrics={smallRamMetrics} />);

      expect(screen.getByTestId('ram-value')).toHaveTextContent('0.5 GB / 1.0 GB');
    });

    it('handles very large uptime (multiple days)', () => {
      const longUptime = { ...mockStats, uptime_seconds: 864000 + 7200 + 180 }; // 10d 2h 3m
      render(<HostSystemPanel metrics={mockMetrics} stats={longUptime} />);

      expect(screen.getByTestId('uptime-value')).toHaveTextContent('10d 2h 3m');
    });

    it('handles zero uptime', () => {
      const zeroUptime = { ...mockStats, uptime_seconds: 0 };
      render(<HostSystemPanel metrics={mockMetrics} stats={zeroUptime} />);

      expect(screen.getByTestId('uptime-value')).toHaveTextContent('0m');
    });
  });

  describe('accessibility', () => {
    it('has appropriate text labels for metrics', () => {
      render(<HostSystemPanel {...defaultProps} />);

      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
      expect(screen.getByText('Memory')).toBeInTheDocument();
      expect(screen.getByText('Disk')).toBeInTheDocument();
      expect(screen.getByText('Uptime')).toBeInTheDocument();
    });

    it('uses semantic structure with Card and Title', () => {
      render(<HostSystemPanel {...defaultProps} />);

      // Title should be present
      expect(screen.getByText('Host System')).toBeInTheDocument();
    });
  });

  describe('threshold boundary conditions', () => {
    it('shows green at exactly 79% CPU', () => {
      const boundaryMetrics = { ...mockMetrics, cpu_percent: 79 };
      render(<HostSystemPanel metrics={boundaryMetrics} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-green-400');
    });

    it('shows yellow at exactly 80% CPU', () => {
      const boundaryMetrics = { ...mockMetrics, cpu_percent: 80 };
      render(<HostSystemPanel metrics={boundaryMetrics} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-yellow-400');
    });

    it('shows yellow at exactly 94% CPU', () => {
      const boundaryMetrics = { ...mockMetrics, cpu_percent: 94 };
      render(<HostSystemPanel metrics={boundaryMetrics} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-yellow-400');
    });

    it('shows red at exactly 95% CPU', () => {
      const boundaryMetrics = { ...mockMetrics, cpu_percent: 95 };
      render(<HostSystemPanel metrics={boundaryMetrics} />);

      const cpuValue = screen.getByTestId('cpu-value');
      expect(cpuValue.className).toContain('text-red-400');
    });
  });
});
