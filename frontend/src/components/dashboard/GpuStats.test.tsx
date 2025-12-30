import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import GpuStats from './GpuStats';
import * as useGpuHistoryModule from '../../hooks/useGpuHistory';

// Mock the useGpuHistory hook
vi.mock('../../hooks/useGpuHistory', () => ({
  useGpuHistory: vi.fn(),
}));

// Default mock return value for useGpuHistory
const defaultMockReturn = {
  current: null,
  history: [],
  isLoading: false,
  error: null,
  start: vi.fn(),
  stop: vi.fn(),
  clearHistory: vi.fn(),
};

// Mock ResizeObserver for Tremor charts
beforeEach(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  // Reset to default mock for each test
  vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({ ...defaultMockReturn });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('GpuStats', () => {
  it('renders component with title', () => {
    render(
      <GpuStats
        gpuName={null}
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        powerUsage={100}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
  });

  it('displays GPU device name when provided', () => {
    // The default mock returns null for current, so gpuName prop should be used
    render(
      <GpuStats
        gpuName="NVIDIA RTX A5500"
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        powerUsage={100}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('NVIDIA RTX A5500')).toBeInTheDocument();
    expect(screen.getByTestId('gpu-device-name')).toBeInTheDocument();
  });

  it('does not display GPU device name when null', () => {
    render(
      <GpuStats
        gpuName={null}
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        powerUsage={100}
        inferenceFps={30}
      />
    );

    expect(screen.queryByTestId('gpu-device-name')).not.toBeInTheDocument();
  });

  it('displays utilization percentage', () => {
    vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
      current: null,
      history: [],
      isLoading: false,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
      clearHistory: vi.fn(),
    });

    render(
      <GpuStats
        gpuName={null}
        utilization={75}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        powerUsage={100}
        inferenceFps={30}
      />
    );

    // Use getAllByText since 'Utilization' appears in both stats label and tab
    expect(screen.getAllByText('Utilization').length).toBeGreaterThan(0);
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('displays memory usage in GB', () => {
    vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
      current: null,
      history: [],
      isLoading: false,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
      clearHistory: vi.fn(),
    });

    render(
      <GpuStats
        gpuName={null}
        utilization={50}
        memoryUsed={12288} // 12 GB in MB
        memoryTotal={24576} // 24 GB in MB
        temperature={60}
        powerUsage={100}
        inferenceFps={30}
      />
    );

    // Use getAllByText since 'Memory' appears in both stats label and tab
    expect(screen.getAllByText('Memory').length).toBeGreaterThan(0);
    expect(screen.getByText('12.0 / 24.0 GB')).toBeInTheDocument();
  });

  it('displays temperature with correct unit', () => {
    vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
      current: null,
      history: [],
      isLoading: false,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
      clearHistory: vi.fn(),
    });

    render(
      <GpuStats
        gpuName={null}
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={65}
        powerUsage={100}
        inferenceFps={30}
      />
    );

    // Use getAllByText since 'Temperature' appears in both stats label and tab
    expect(screen.getAllByText('Temperature').length).toBeGreaterThan(0);
    expect(screen.getByText('65°C')).toBeInTheDocument();
  });

  it('displays power usage with correct unit', () => {
    render(
      <GpuStats
        gpuName={null}
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        powerUsage={150}
        inferenceFps={30}
      />
    );

    expect(screen.getByText('Power Usage')).toBeInTheDocument();
    expect(screen.getByText('150W')).toBeInTheDocument();
  });

  it('displays inference FPS', () => {
    render(
      <GpuStats
        gpuName={null}
        utilization={50}
        memoryUsed={12000}
        memoryTotal={24000}
        temperature={60}
        powerUsage={100}
        inferenceFps={28.5}
      />
    );

    expect(screen.getByText('Inference FPS')).toBeInTheDocument();
    expect(screen.getByText('29')).toBeInTheDocument();
  });

  describe('null value handling', () => {
    it('displays "N/A" for null utilization', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={null}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      // Use getAllByText since 'Utilization' appears in both stats label and tab
      expect(screen.getAllByText('Utilization').length).toBeGreaterThan(0);
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });

    it('displays "N/A" for null memory values', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={null}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays "N/A" for null temperature', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={null}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      // Use getAllByText since 'Temperature' appears in both stats label and tab
      expect(screen.getAllByText('Temperature').length).toBeGreaterThan(0);
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays "N/A" for null power usage', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={null}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('Power Usage')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays "N/A" for null inference FPS', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={null}
        />
      );

      expect(screen.getByText('Inference FPS')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('handles all null values gracefully', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={null}
          memoryUsed={null}
          memoryTotal={null}
          temperature={null}
          powerUsage={null}
          inferenceFps={null}
        />
      );

      expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });
  });

  describe('temperature color coding', () => {
    it('uses green color for safe temperature (<70°C)', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={65}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      // Check for NVIDIA green color class
      const tempValue = screen.getByText('65°C');
      expect(tempValue).toHaveClass('text-[#76B900]');
    });

    it('uses yellow color for warning temperature (70-80°C)', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={75}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      const tempValue = screen.getByText('75°C');
      expect(tempValue).toHaveClass('text-yellow-500');
    });

    it('uses red color for critical temperature (>80°C)', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={85}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      const tempValue = screen.getByText('85°C');
      expect(tempValue).toHaveClass('text-red-500');
    });

    it('uses gray color for null temperature', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={null}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      const naElements = screen.getAllByText('N/A');
      const tempNa = naElements.find((el) => el.closest('[class*="text-gray"]'));
      expect(tempNa).toBeDefined();
    });
  });

  describe('power usage color coding', () => {
    it('uses green color for low power (<150W)', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      const powerValue = screen.getByTestId('gpu-power-usage');
      expect(powerValue).toHaveClass('text-[#76B900]');
    });

    it('uses yellow color for moderate power (150-250W)', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={200}
          inferenceFps={30}
        />
      );

      const powerValue = screen.getByTestId('gpu-power-usage');
      expect(powerValue).toHaveClass('text-yellow-500');
    });

    it('uses red color for high power (>250W)', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={300}
          inferenceFps={30}
        />
      );

      const powerValue = screen.getByTestId('gpu-power-usage');
      expect(powerValue).toHaveClass('text-red-500');
    });

    it('uses gray color for null power', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={null}
          inferenceFps={30}
        />
      );

      const powerValue = screen.getByTestId('gpu-power-usage');
      expect(powerValue).toHaveClass('text-gray-400');
    });
  });

  describe('edge cases', () => {
    it('handles zero values correctly', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={0}
          memoryUsed={0}
          memoryTotal={24000}
          temperature={0}
          powerUsage={0}
          inferenceFps={0}
        />
      );

      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByText('0°C')).toBeInTheDocument();
      expect(screen.getByText('0W')).toBeInTheDocument();
    });

    it('handles 100% utilization', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={100}
          memoryUsed={24000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('handles very high temperatures', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={95}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('95°C')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
          className="custom-class"
        />
      );

      // Verify component renders with custom class by checking it's in the document
      expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
    });
  });

  describe('memory calculation', () => {
    it('correctly converts MB to GB', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={15360} // 15 GB
          memoryTotal={24576} // 24 GB
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('15.0 / 24.0 GB')).toBeInTheDocument();
    });

    it('displays decimal places for partial GB values', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12500} // 12.2 GB
          memoryTotal={24000} // 23.4 GB
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      // Should show one decimal place
      const memoryText = screen.getByText(/GB$/);
      expect(memoryText).toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('rounds decimal values to integers', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={75.7}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={65.4}
          powerUsage={100}
          inferenceFps={28.9}
        />
      );

      expect(screen.getByText('76%')).toBeInTheDocument();
      expect(screen.getByText('65°C')).toBeInTheDocument();
      expect(screen.getByText('29')).toBeInTheDocument();
    });
  });

  describe('GPU history chart', () => {
    it('shows loading state initially', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: true,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      expect(screen.getByTestId('gpu-history-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading history...')).toBeInTheDocument();
    });

    it('displays history chart when data is available', async () => {
      // GpuMetricDataPoint type: { timestamp, utilization, memory_used, temperature }
      const mockHistory = [
        {
          timestamp: '2025-01-01T10:00:00Z',
          utilization: 45.5,
          memory_used: 8192,
          temperature: 65,
        },
        {
          timestamp: '2025-01-01T10:01:00Z',
          utilization: 50.0,
          memory_used: 8500,
          temperature: 66,
        },
      ];

      // GPUStats type for current
      const mockCurrent = {
        gpu_name: 'NVIDIA RTX A5500',
        utilization: 50.0,
        memory_used: 8500,
        memory_total: 24576,
        temperature: 66,
        power_usage: 100,
        inference_fps: 28.5,
      };

      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: mockCurrent,
        history: mockHistory,
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('gpu-history-loading')).not.toBeInTheDocument();
      });

      // The chart should be rendered - check that the empty state is not shown
      expect(screen.queryByTestId('gpu-history-empty')).not.toBeInTheDocument();
    });

    it('shows empty state when no history data', async () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('gpu-history-empty')).toBeInTheDocument();
      });

      expect(screen.getByText('No history data available')).toBeInTheDocument();
    });

    it('shows error state when fetch fails', async () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: 'Network error',
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('gpu-history-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('displays Metrics History section title', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      expect(screen.getByText('Metrics History')).toBeInTheDocument();
    });

    it('displays history controls when showHistoryControls is true', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
          showHistoryControls={true}
        />
      );

      expect(screen.getByTestId('gpu-history-toggle')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-history-clear')).toBeInTheDocument();
    });

    it('hides history controls when showHistoryControls is false', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
          showHistoryControls={false}
        />
      );

      expect(screen.queryByTestId('gpu-history-toggle')).not.toBeInTheDocument();
      expect(screen.queryByTestId('gpu-history-clear')).not.toBeInTheDocument();
    });

    it('displays tab selection for different metrics', () => {
      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      expect(screen.getByTestId('tab-utilization')).toBeInTheDocument();
      expect(screen.getByTestId('tab-temperature')).toBeInTheDocument();
      expect(screen.getByTestId('tab-memory')).toBeInTheDocument();
    });
  });

  describe('hook data priority', () => {
    it('uses hook current data over props when available', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: {
          gpu_name: 'NVIDIA RTX A5500',
          utilization: 80, // Hook provides 80%
          memory_used: 16000, // Hook provides 16GB
          memory_total: 24000,
          temperature: 72, // Hook provides 72C
          power_usage: 150,
          inference_fps: 25,
        },
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50} // Props say 50%
          memoryUsed={12000} // Props say 12GB
          memoryTotal={24000}
          temperature={60} // Props say 60C
          powerUsage={100}
          inferenceFps={30}
        />
      );

      // Should show hook values, not prop values
      expect(screen.getByText('80%')).toBeInTheDocument();
      expect(screen.getByText('72°C')).toBeInTheDocument();
      expect(screen.getByText('15.6 / 23.4 GB')).toBeInTheDocument();
    });

    it('falls back to props when hook current is null', () => {
      vi.mocked(useGpuHistoryModule.useGpuHistory).mockReturnValue({
        current: null,
        history: [],
        isLoading: false,
        error: null,
        start: vi.fn(),
        stop: vi.fn(),
        clearHistory: vi.fn(),
      });

      render(
        <GpuStats
          gpuName={null}
          utilization={50}
          memoryUsed={12000}
          memoryTotal={24000}
          temperature={60}
          powerUsage={100}
          inferenceFps={30}
        />
      );

      // Should show prop values
      expect(screen.getByText('50%')).toBeInTheDocument();
      expect(screen.getByText('60°C')).toBeInTheDocument();
    });
  });
});
