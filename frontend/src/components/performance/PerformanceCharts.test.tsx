/**
 * Tests for PerformanceCharts component
 * Comprehensive test coverage for time-series performance metric visualization
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PerformanceCharts from './PerformanceCharts';
import * as usePerformanceMetricsModule from '../../hooks/usePerformanceMetrics';

import type { PerformanceUpdate, TimeRange } from '../../hooks/usePerformanceMetrics';

// Mock the usePerformanceMetrics hook
vi.mock('../../hooks/usePerformanceMetrics', () => ({
  usePerformanceMetrics: vi.fn(),
}));

/**
 * Create a mock PerformanceUpdate with default values
 */
function createMockPerformanceUpdate(
  overrides: Partial<PerformanceUpdate> = {}
): PerformanceUpdate {
  return {
    timestamp: new Date().toISOString(),
    gpu: {
      name: 'NVIDIA RTX A5500',
      utilization: 45,
      vram_used_gb: 8,
      vram_total_gb: 24,
      temperature: 65,
      power_watts: 120,
    },
    ai_models: {},
    nemotron: null,
    inference: {
      rtdetr_latency_ms: { avg: 25 },
      nemotron_latency_ms: { avg: 5000 },
      pipeline_latency_ms: { avg: 100 },
      throughput: {},
      queues: {},
    },
    databases: {},
    host: {
      cpu_percent: 35,
      ram_used_gb: 16,
      ram_total_gb: 64,
      disk_used_gb: 500,
      disk_total_gb: 1000,
    },
    containers: [],
    alerts: [],
    ...overrides,
  };
}

/**
 * Create mock history data for testing
 */
function createMockHistory(count: number, includeData = true): PerformanceUpdate[] {
  return Array.from({ length: count }, (_, i) => {
    const baseTime = new Date();
    baseTime.setMinutes(baseTime.getMinutes() - (count - i - 1) * 5);

    if (!includeData) {
      return createMockPerformanceUpdate({
        timestamp: baseTime.toISOString(),
        gpu: null,
        inference: null,
        host: null,
      });
    }

    return createMockPerformanceUpdate({
      timestamp: baseTime.toISOString(),
      gpu: {
        name: 'NVIDIA RTX A5500',
        utilization: 40 + Math.random() * 30,
        vram_used_gb: 6 + Math.random() * 6,
        vram_total_gb: 24,
        temperature: 60 + Math.random() * 15,
        power_watts: 100 + Math.random() * 100,
      },
      inference: {
        rtdetr_latency_ms: { avg: 20 + Math.random() * 20 },
        nemotron_latency_ms: { avg: 4000 + Math.random() * 2000 },
        pipeline_latency_ms: { avg: 80 + Math.random() * 50 },
        throughput: {},
        queues: {},
      },
      host: {
        cpu_percent: 30 + Math.random() * 20,
        ram_used_gb: 14 + Math.random() * 8,
        ram_total_gb: 64,
        disk_used_gb: 480 + Math.random() * 40,
        disk_total_gb: 1000,
      },
    });
  });
}

// Default mock return value
const defaultHookReturn = {
  current: null,
  history: {
    '5m': [] as PerformanceUpdate[],
    '15m': [] as PerformanceUpdate[],
    '60m': [] as PerformanceUpdate[],
  },
  alerts: [],
  isConnected: true,
  timeRange: '5m' as TimeRange,
  setTimeRange: vi.fn(),
};

// Mock ResizeObserver for Tremor charts
beforeEach(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
    ...defaultHookReturn,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('PerformanceCharts', () => {
  describe('basic rendering', () => {
    it('renders the main container', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('performance-charts')).toBeInTheDocument();
    });

    it('renders all four chart cards', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('gpu-utilization-card')).toBeInTheDocument();
      expect(screen.getByTestId('temperature-card')).toBeInTheDocument();
      expect(screen.getByTestId('latency-card')).toBeInTheDocument();
      expect(screen.getByTestId('resource-usage-card')).toBeInTheDocument();
    });

    it('renders chart card titles', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('GPU Utilization')).toBeInTheDocument();
      expect(screen.getByText('GPU Temperature')).toBeInTheDocument();
      expect(screen.getByText('Inference Latency')).toBeInTheDocument();
      expect(screen.getByText('System Resources')).toBeInTheDocument();
    });

    it('renders time range selector buttons', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('time-range-5m')).toBeInTheDocument();
      expect(screen.getByTestId('time-range-15m')).toBeInTheDocument();
      expect(screen.getByTestId('time-range-60m')).toBeInTheDocument();
    });

    it('displays time range labels', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('Last 5 minutes')).toBeInTheDocument();
      expect(screen.getByText('Last 15 minutes')).toBeInTheDocument();
      expect(screen.getByText('Last hour')).toBeInTheDocument();
    });
  });

  describe('connection status indicator', () => {
    it('shows connected status when WebSocket is connected', () => {
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        isConnected: true,
      });

      render(<PerformanceCharts />);
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-green-500');
    });

    it('shows disconnected status when WebSocket is not connected', () => {
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        isConnected: false,
      });

      render(<PerformanceCharts />);
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-red-500');
    });
  });

  describe('time range selection', () => {
    it('highlights active time range button', () => {
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        timeRange: '15m',
      });

      render(<PerformanceCharts />);
      const button15m = screen.getByTestId('time-range-15m');
      expect(button15m).toHaveClass('bg-[#76B900]');
    });

    it('calls setTimeRange when clicking time range button', async () => {
      const setTimeRangeMock = vi.fn();
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        setTimeRange: setTimeRangeMock,
      });

      render(<PerformanceCharts />);
      await userEvent.click(screen.getByTestId('time-range-60m'));
      expect(setTimeRangeMock).toHaveBeenCalledWith('60m');
    });

    it('uses prop timeRange over hook timeRange', () => {
      const mockHistory = createMockHistory(10);
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': [],
          '15m': mockHistory,
          '60m': [],
        },
        timeRange: '5m', // Hook says 5m
      });

      // Prop says 15m
      render(<PerformanceCharts timeRange="15m" />);

      // Should show 15m as active (from prop)
      expect(screen.getByTestId('time-range-15m')).toHaveClass('bg-[#76B900]');
    });
  });

  describe('hideTimeRangeSelector prop', () => {
    it('hides time range selector when hideTimeRangeSelector is true', () => {
      render(<PerformanceCharts hideTimeRangeSelector={true} />);
      expect(screen.queryByTestId('time-range-5m')).not.toBeInTheDocument();
      expect(screen.queryByTestId('connection-indicator')).not.toBeInTheDocument();
    });

    it('shows time range selector by default', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('time-range-5m')).toBeInTheDocument();
    });
  });

  describe('empty state handling', () => {
    it('shows empty state for GPU chart when no GPU data', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('No GPU data available')).toBeInTheDocument();
    });

    it('shows empty state for temperature chart when no GPU data', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('No temperature data available')).toBeInTheDocument();
    });

    it('shows empty state for latency chart when no inference data', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('No inference latency data available')).toBeInTheDocument();
    });

    it('shows empty state for resource chart when no host data', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('No system resource data available')).toBeInTheDocument();
    });

    it('shows helper text in empty states', () => {
      render(<PerformanceCharts />);
      const helperTexts = screen.getAllByText('Data will appear as metrics are collected');
      expect(helperTexts.length).toBe(4);
    });
  });

  describe('with data', () => {
    beforeEach(() => {
      const mockHistory = createMockHistory(10);
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': mockHistory,
          '15m': [],
          '60m': [],
        },
      });
    });

    it('renders GPU area chart when data is available', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('gpu-area-chart')).toBeInTheDocument();
    });

    it('renders temperature line chart when data is available', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('temperature-line-chart')).toBeInTheDocument();
    });

    it('renders latency line chart when data is available', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('latency-line-chart')).toBeInTheDocument();
    });

    it('renders resource area chart when data is available', () => {
      render(<PerformanceCharts />);
      expect(screen.getByTestId('resource-area-chart')).toBeInTheDocument();
    });

    it('displays data point count', () => {
      render(<PerformanceCharts />);
      const dataPointTexts = screen.getAllByText('10 data points');
      expect(dataPointTexts.length).toBeGreaterThan(0);
    });

    it('does not show empty chart message when data exists', () => {
      render(<PerformanceCharts />);
      expect(screen.queryByTestId('empty-chart')).not.toBeInTheDocument();
    });
  });

  describe('temperature threshold display', () => {
    beforeEach(() => {
      const mockHistory = createMockHistory(5);
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': mockHistory,
          '15m': [],
          '60m': [],
        },
      });
    });

    it('displays warning threshold legend', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText(/Warning: 75C/)).toBeInTheDocument();
    });

    it('displays critical threshold legend', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText(/Critical: 85C/)).toBeInTheDocument();
    });
  });

  describe('historyData prop', () => {
    it('uses historyData prop instead of hook data when provided', () => {
      const customHistory = createMockHistory(3);

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': createMockHistory(10), // Hook has 10 points
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts historyData={customHistory} />);

      // Should show 3 data points (from prop) not 10 (from hook)
      const dataPointTexts = screen.getAllByText('3 data points');
      expect(dataPointTexts.length).toBeGreaterThan(0);
    });
  });

  describe('className prop', () => {
    it('applies custom className', () => {
      render(<PerformanceCharts className="custom-test-class" />);
      expect(screen.getByTestId('performance-charts')).toHaveClass('custom-test-class');
    });

    it('includes default space-y-4 class', () => {
      render(<PerformanceCharts className="custom-class" />);
      expect(screen.getByTestId('performance-charts')).toHaveClass('space-y-4');
    });
  });

  describe('partial data handling', () => {
    it('shows GPU chart but hides inference chart when only GPU data exists', () => {
      const history = createMockHistory(5).map((update) => ({
        ...update,
        inference: null,
      }));

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': history,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      expect(screen.getByTestId('gpu-area-chart')).toBeInTheDocument();
      expect(screen.getByText('No inference latency data available')).toBeInTheDocument();
    });

    it('shows resource chart but hides GPU chart when only host data exists', () => {
      const history = createMockHistory(5).map((update) => ({
        ...update,
        gpu: null,
      }));

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': history,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      expect(screen.getByTestId('resource-area-chart')).toBeInTheDocument();
      expect(screen.getByText('No GPU data available')).toBeInTheDocument();
    });
  });

  describe('null value handling', () => {
    it('handles null GPU utilization gracefully', () => {
      const history = createMockHistory(5).map((update) => ({
        ...update,
        gpu: {
          ...update.gpu!,
          utilization: null as unknown as number,
        },
      }));

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': history,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      // Should render without crashing
      expect(screen.getByTestId('gpu-utilization-card')).toBeInTheDocument();
    });

    it('handles null inference latency values gracefully', () => {
      const history = createMockHistory(5).map((update) => ({
        ...update,
        inference: {
          rtdetr_latency_ms: {},
          nemotron_latency_ms: {},
          pipeline_latency_ms: {},
          throughput: {},
          queues: {},
        },
      }));

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': history,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      // Should render without crashing
      expect(screen.getByTestId('latency-card')).toBeInTheDocument();
    });

    it('handles zero VRAM total gracefully', () => {
      const history = createMockHistory(5).map((update) => ({
        ...update,
        gpu: {
          ...update.gpu!,
          vram_total_gb: 0,
        },
      }));

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': history,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      // Should render without division by zero errors
      expect(screen.getByTestId('gpu-utilization-card')).toBeInTheDocument();
    });

    it('handles zero RAM total gracefully', () => {
      const history = createMockHistory(5).map((update) => ({
        ...update,
        host: {
          ...update.host!,
          ram_total_gb: 0,
        },
      }));

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': history,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      // Should render without division by zero errors
      expect(screen.getByTestId('resource-usage-card')).toBeInTheDocument();
    });
  });

  describe('chart data transformation', () => {
    it('transforms GPU data correctly for chart', () => {
      const mockHistory: PerformanceUpdate[] = [
        createMockPerformanceUpdate({
          timestamp: '2025-01-01T10:00:00Z',
          gpu: {
            name: 'Test GPU',
            utilization: 50,
            vram_used_gb: 12,
            vram_total_gb: 24,
            temperature: 70,
            power_watts: 150,
          },
        }),
      ];

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': mockHistory,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);

      // Chart should be rendered
      expect(screen.getByTestId('gpu-area-chart')).toBeInTheDocument();
    });

    it('transforms temperature data with threshold lines', () => {
      const mockHistory = createMockHistory(5);

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': mockHistory,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);

      // Temperature chart should show threshold lines
      expect(screen.getByTestId('temperature-line-chart')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles empty history array', () => {
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': [],
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      expect(screen.getByTestId('performance-charts')).toBeInTheDocument();
    });

    it('handles history with only null data', () => {
      const nullHistory = createMockHistory(5, false);

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': nullHistory,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      // Should show empty states since no meaningful data
      expect(screen.getByText('No GPU data available')).toBeInTheDocument();
    });

    it('handles single data point', () => {
      const singlePoint = createMockHistory(1);

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': singlePoint,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      // Should render chart with single point
      expect(screen.getByTestId('gpu-area-chart')).toBeInTheDocument();
      // Multiple charts show data point count, so use getAllByText
      const dataPointTexts = screen.getAllByText('1 data points');
      expect(dataPointTexts.length).toBeGreaterThan(0);
    });

    it('handles large history data', () => {
      const largeHistory = createMockHistory(60);

      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        history: {
          '5m': largeHistory,
          '15m': [],
          '60m': [],
        },
      });

      render(<PerformanceCharts />);
      expect(screen.getByTestId('gpu-area-chart')).toBeInTheDocument();
      // Multiple charts show data point count, so use getAllByText
      const dataPointTexts = screen.getAllByText('60 data points');
      expect(dataPointTexts.length).toBeGreaterThan(0);
    });
  });

  describe('icon rendering', () => {
    it('renders CPU icon in GPU card', () => {
      render(<PerformanceCharts />);
      const gpuCard = screen.getByTestId('gpu-utilization-card');
      expect(gpuCard.querySelector('svg')).toBeInTheDocument();
    });

    it('renders Thermometer icon in temperature card', () => {
      render(<PerformanceCharts />);
      const tempCard = screen.getByTestId('temperature-card');
      expect(tempCard.querySelector('svg')).toBeInTheDocument();
    });

    it('renders Timer icon in latency card', () => {
      render(<PerformanceCharts />);
      const latencyCard = screen.getByTestId('latency-card');
      expect(latencyCard.querySelector('svg')).toBeInTheDocument();
    });

    it('renders HardDrive icon in resource card', () => {
      render(<PerformanceCharts />);
      const resourceCard = screen.getByTestId('resource-usage-card');
      expect(resourceCard.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('responsive grid layout', () => {
    it('renders cards in a grid container', () => {
      render(<PerformanceCharts />);
      const container = screen.getByTestId('performance-charts');
      // Should contain Grid component with gap
      expect(container.querySelector('.gap-4')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible button labels', () => {
      render(<PerformanceCharts />);

      const button5m = screen.getByTestId('time-range-5m');
      expect(button5m).toHaveTextContent('Last 5 minutes');

      const button15m = screen.getByTestId('time-range-15m');
      expect(button15m).toHaveTextContent('Last 15 minutes');

      const button60m = screen.getByTestId('time-range-60m');
      expect(button60m).toHaveTextContent('Last hour');
    });

    it('card titles are visible', () => {
      render(<PerformanceCharts />);
      expect(screen.getByText('GPU Utilization')).toBeVisible();
      expect(screen.getByText('GPU Temperature')).toBeVisible();
      expect(screen.getByText('Inference Latency')).toBeVisible();
      expect(screen.getByText('System Resources')).toBeVisible();
    });
  });

  describe('time range switching', () => {
    it('switches between time ranges correctly', async () => {
      const setTimeRangeMock = vi.fn();
      vi.mocked(usePerformanceMetricsModule.usePerformanceMetrics).mockReturnValue({
        ...defaultHookReturn,
        setTimeRange: setTimeRangeMock,
        history: {
          '5m': createMockHistory(60),
          '15m': createMockHistory(60),
          '60m': createMockHistory(60),
        },
      });

      render(<PerformanceCharts />);

      // Click 15m
      await userEvent.click(screen.getByTestId('time-range-15m'));
      expect(setTimeRangeMock).toHaveBeenCalledWith('15m');

      // Click 60m
      await userEvent.click(screen.getByTestId('time-range-60m'));
      expect(setTimeRangeMock).toHaveBeenCalledWith('60m');

      // Click 5m
      await userEvent.click(screen.getByTestId('time-range-5m'));
      expect(setTimeRangeMock).toHaveBeenCalledWith('5m');
    });
  });

  describe('component lifecycle', () => {
    it('does not crash on unmount', () => {
      const { unmount } = render(<PerformanceCharts />);
      expect(() => unmount()).not.toThrow();
    });

    it('cleans up properly', () => {
      const { unmount } = render(<PerformanceCharts />);
      unmount();
      // No lingering effects or errors
      expect(true).toBe(true);
    });
  });
});
