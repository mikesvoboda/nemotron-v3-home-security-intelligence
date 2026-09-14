/**
 * Tests for PerformanceDashboard component
 *
 * Tests the main dashboard component including:
 * - Rendering with various data states
 * - Time range selector functionality
 * - Connection status display
 * - All metric cards (GPU, AI Models, Database, Redis, Host, Containers)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import PerformanceDashboard from './PerformanceDashboard';
import {
  usePerformanceMetrics,
  type PerformanceUpdate,
  type TimeRange,
} from '../../hooks/usePerformanceMetrics';

// Mock the usePerformanceMetrics hook
vi.mock('../../hooks/usePerformanceMetrics', () => ({
  usePerformanceMetrics: vi.fn(),
}));

// Sample test data
const mockPerformanceUpdate: PerformanceUpdate = {
  timestamp: '2024-01-15T12:00:00Z',
  gpu: {
    name: 'NVIDIA RTX A5500',
    utilization: 45,
    vram_used_gb: 8.5,
    vram_total_gb: 24,
    temperature: 65,
    power_watts: 150,
  },
  ai_models: {
    rtdetr: {
      status: 'healthy',
      vram_gb: 0.17,
      model: 'rtdetr_r50vd_coco_o365',
      device: 'cuda:0',
    },
  },
  nemotron: {
    status: 'healthy',
    slots_active: 1,
    slots_total: 2,
    context_size: 4096,
  },
  inference: null,
  databases: {
    postgresql: {
      status: 'healthy',
      connections_active: 5,
      connections_max: 100,
      cache_hit_ratio: 99.2,
      transactions_per_min: 250,
    },
    redis: {
      status: 'healthy',
      connected_clients: 3,
      memory_mb: 128.5,
      hit_ratio: 85.5,
      blocked_clients: 0,
    },
  },
  host: {
    cpu_percent: 35,
    ram_used_gb: 16.5,
    ram_total_gb: 64,
    disk_used_gb: 250,
    disk_total_gb: 1000,
  },
  containers: [
    { name: 'backend', status: 'running', health: 'healthy' },
    { name: 'frontend', status: 'running', health: 'healthy' },
    { name: 'postgres', status: 'running', health: 'healthy' },
    { name: 'redis', status: 'running', health: 'healthy' },
    { name: 'ai-yolo26', status: 'running', health: 'healthy' },
    { name: 'ai-llm', status: 'running', health: 'starting' },
  ],
  alerts: [],
};

// Default mock implementation
const createMockHook = (
  overrides: Partial<{
    current: PerformanceUpdate | null;
    isConnected: boolean;
    timeRange: TimeRange;
    setTimeRange: (range: TimeRange) => void;
  }> = {}
) => ({
  current: mockPerformanceUpdate,
  history: { '5m': [], '15m': [], '60m': [] },
  alerts: [],
  isConnected: true,
  timeRange: '5m' as TimeRange,
  setTimeRange: vi.fn(),
  ...overrides,
});

describe('PerformanceDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (usePerformanceMetrics as Mock).mockReturnValue(createMockHook());
  });

  describe('basic rendering', () => {
    it('renders the main container with correct testid', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('performance-dashboard')).toBeInTheDocument();
    });

    it('renders the page title', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByText('System Performance')).toBeInTheDocument();
    });

    it('renders the subtitle', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByText('Real-time metrics updated every 5 seconds')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<PerformanceDashboard className="custom-class" />);
      expect(screen.getByTestId('performance-dashboard')).toHaveClass('custom-class');
    });
  });

  describe('connection status', () => {
    it('displays connected status when WebSocket is connected', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('connection-status')).toHaveTextContent('Connected');
    });

    it('displays disconnected status when WebSocket is not connected', () => {
      (usePerformanceMetrics as Mock).mockReturnValue(createMockHook({ isConnected: false }));
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('connection-status')).toHaveTextContent('Disconnected');
    });
  });

  describe('time range selector', () => {
    it('renders time range selector', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('time-range-selector')).toBeInTheDocument();
    });

    it('displays all time range options', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByText('5m')).toBeInTheDocument();
      expect(screen.getByText('15m')).toBeInTheDocument();
      expect(screen.getByText('60m')).toBeInTheDocument();
    });

    it('calls setTimeRange when a different range is selected', () => {
      const setTimeRange = vi.fn();
      (usePerformanceMetrics as Mock).mockReturnValue(createMockHook({ setTimeRange }));
      render(<PerformanceDashboard />);

      fireEvent.click(screen.getByText('15m'));
      expect(setTimeRange).toHaveBeenCalledWith('15m');
    });

    it('highlights the selected time range', () => {
      (usePerformanceMetrics as Mock).mockReturnValue(createMockHook({ timeRange: '15m' }));
      render(<PerformanceDashboard />);

      const button15m = screen.getByText('15m');
      expect(button15m).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('GPU card', () => {
    it('renders GPU card', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('gpu-card')).toBeInTheDocument();
    });

    it('displays GPU name', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByText('NVIDIA RTX A5500')).toBeInTheDocument();
    });

    it('displays GPU utilization', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('gpu-utilization')).toHaveTextContent('45%');
    });

    it('displays GPU VRAM usage', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('gpu-vram')).toHaveTextContent('8.5/24.0 GB');
    });

    it('displays GPU temperature', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('gpu-temperature')).toHaveTextContent('65C');
    });

    it('displays GPU power consumption', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('gpu-power')).toHaveTextContent('150W');
    });

    it('shows no data message when GPU data is null', () => {
      const updateWithoutGpu = { ...mockPerformanceUpdate, gpu: null };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithoutGpu })
      );
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('gpu-card')).toHaveTextContent('No GPU data available');
    });
  });

  describe('AI Models card', () => {
    it('renders AI Models card', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('ai-models-card')).toBeInTheDocument();
    });

    it('displays RT-DETRv2 model', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('ai-model-rtdetr')).toBeInTheDocument();
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('displays RT-DETRv2 status', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('ai-model-rtdetr-status')).toHaveTextContent('Healthy');
    });

    it('displays Nemotron model', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('ai-model-nemotron')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });

    it('displays Nemotron status', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('ai-model-nemotron-status')).toHaveTextContent('Healthy');
    });

    it('displays Nemotron slots info', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByText(/Slots: 1\/2/)).toBeInTheDocument();
    });

    it('displays Nemotron context size', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByText('4,096 tokens')).toBeInTheDocument();
    });

    it('shows no data message when no AI models are available', () => {
      const updateWithoutAi = {
        ...mockPerformanceUpdate,
        ai_models: {},
        nemotron: null,
      };
      (usePerformanceMetrics as Mock).mockReturnValue(createMockHook({ current: updateWithoutAi }));
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('ai-models-card')).toHaveTextContent('No AI model data available');
    });
  });

  describe('Database card', () => {
    it('renders Database card', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('database-card')).toBeInTheDocument();
    });

    it('displays PostgreSQL status', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('db-status')).toHaveTextContent('Healthy');
    });

    it('displays database connections', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('db-connections')).toHaveTextContent('5/100');
    });

    it('displays cache hit ratio', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('db-cache-hit')).toHaveTextContent('99.2%');
    });

    it('displays transactions per minute', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('db-transactions')).toHaveTextContent('250/min');
    });

    it('shows no data message when database data is unavailable', () => {
      const updateWithoutDb = { ...mockPerformanceUpdate, databases: {} };
      (usePerformanceMetrics as Mock).mockReturnValue(createMockHook({ current: updateWithoutDb }));
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('database-card')).toHaveTextContent('No database data available');
    });
  });

  describe('Redis card', () => {
    it('renders Redis card', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('redis-card')).toBeInTheDocument();
    });

    it('displays Redis status', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('redis-status')).toHaveTextContent('Healthy');
    });

    it('displays Redis memory usage', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('redis-memory')).toHaveTextContent('128.50 MB');
    });

    it('displays Redis hit ratio', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('redis-hit-ratio')).toHaveTextContent('85.5%');
    });

    it('displays Redis connected clients', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('redis-clients')).toHaveTextContent('3');
    });

    it('shows no data message when Redis data is unavailable', () => {
      const updateWithoutRedis = {
        ...mockPerformanceUpdate,
        databases: { postgresql: mockPerformanceUpdate.databases.postgresql },
      };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithoutRedis })
      );
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('redis-card')).toHaveTextContent('No Redis data available');
    });
  });

  describe('Host card', () => {
    it('renders Host card', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('host-card')).toBeInTheDocument();
    });

    it('displays CPU usage', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('host-cpu')).toHaveTextContent('35%');
    });

    it('displays RAM usage', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('host-ram')).toHaveTextContent('16.5/64.0 GB');
    });

    it('displays disk usage', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('host-disk')).toHaveTextContent('250.0/1000.0 GB');
    });

    it('shows no data message when host data is null', () => {
      const updateWithoutHost = { ...mockPerformanceUpdate, host: null };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithoutHost })
      );
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('host-card')).toHaveTextContent('No host data available');
    });
  });

  describe('Containers card', () => {
    it('renders Containers card', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('containers-card')).toBeInTheDocument();
    });

    it('displays container summary', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('containers-summary')).toHaveTextContent('5/6 Healthy');
    });

    it('displays all containers', () => {
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('container-backend')).toBeInTheDocument();
      expect(screen.getByTestId('container-frontend')).toBeInTheDocument();
      expect(screen.getByTestId('container-postgres')).toBeInTheDocument();
      expect(screen.getByTestId('container-redis')).toBeInTheDocument();
      expect(screen.getByTestId('container-ai-yolo26')).toBeInTheDocument();
      expect(screen.getByTestId('container-ai-llm')).toBeInTheDocument();
    });

    it('shows no data message when containers array is empty', () => {
      const updateWithoutContainers = { ...mockPerformanceUpdate, containers: [] };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithoutContainers })
      );
      render(<PerformanceDashboard />);
      expect(screen.getByTestId('containers-card')).toHaveTextContent(
        'No container data available'
      );
    });
  });

  describe('empty state', () => {
    it('handles null current data gracefully', () => {
      (usePerformanceMetrics as Mock).mockReturnValue(createMockHook({ current: null }));
      render(<PerformanceDashboard />);

      // Should still render all cards with empty states
      expect(screen.getByTestId('gpu-card')).toBeInTheDocument();
      expect(screen.getByTestId('ai-models-card')).toBeInTheDocument();
      expect(screen.getByTestId('database-card')).toBeInTheDocument();
      expect(screen.getByTestId('redis-card')).toBeInTheDocument();
      expect(screen.getByTestId('host-card')).toBeInTheDocument();
      expect(screen.getByTestId('containers-card')).toBeInTheDocument();
    });
  });

  describe('status colors', () => {
    it('displays red badge for unhealthy status', () => {
      const updateWithUnhealthy = {
        ...mockPerformanceUpdate,
        databases: {
          ...mockPerformanceUpdate.databases,
          postgresql: {
            ...mockPerformanceUpdate.databases.postgresql,
            status: 'unhealthy',
          },
        },
      };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithUnhealthy })
      );
      render(<PerformanceDashboard />);
      const badge = screen.getByTestId('db-status');
      expect(badge).toHaveTextContent('Unhealthy');
    });

    it('displays yellow badge for degraded status', () => {
      const updateWithDegraded = {
        ...mockPerformanceUpdate,
        ai_models: {
          rtdetr: {
            ...mockPerformanceUpdate.ai_models.rtdetr,
            status: 'degraded',
          },
        },
      };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithDegraded })
      );
      render(<PerformanceDashboard />);
      const badge = screen.getByTestId('ai-model-rtdetr-status');
      expect(badge).toHaveTextContent('Degraded');
    });
  });

  describe('GPU temperature colors', () => {
    it('displays green temperature color for normal temperature', () => {
      render(<PerformanceDashboard />);
      const tempElement = screen.getByTestId('gpu-temperature');
      expect(tempElement).toHaveClass('text-green-400');
    });

    it('displays yellow temperature color for high temperature', () => {
      const updateWithHighTemp = {
        ...mockPerformanceUpdate,
        gpu: { ...mockPerformanceUpdate.gpu!, temperature: 75 },
      };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithHighTemp })
      );
      render(<PerformanceDashboard />);
      const tempElement = screen.getByTestId('gpu-temperature');
      expect(tempElement).toHaveClass('text-yellow-400');
    });

    it('displays red temperature color for critical temperature', () => {
      const updateWithCriticalTemp = {
        ...mockPerformanceUpdate,
        gpu: { ...mockPerformanceUpdate.gpu!, temperature: 90 },
      };
      (usePerformanceMetrics as Mock).mockReturnValue(
        createMockHook({ current: updateWithCriticalTemp })
      );
      render(<PerformanceDashboard />);
      const tempElement = screen.getByTestId('gpu-temperature');
      expect(tempElement).toHaveClass('text-red-400');
    });
  });
});
