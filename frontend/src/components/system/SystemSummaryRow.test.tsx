import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, Mock, vi } from 'vitest';

import SystemSummaryRow from './SystemSummaryRow';
import { useHealthStatusQuery } from '../../hooks/useHealthStatusQuery';
import { useModelZooStatus } from '../../hooks/useModelZooStatus';
import { usePerformanceMetrics } from '../../hooks/usePerformanceMetrics';

import type { PerformanceUpdate } from '../../hooks/usePerformanceMetrics';

// Mock the hooks
vi.mock('../../hooks/usePerformanceMetrics');
vi.mock('../../hooks/useHealthStatusQuery');
vi.mock('../../hooks/useModelZooStatus');

// Mock scrollIntoView
const mockScrollIntoView = vi.fn();
Element.prototype.scrollIntoView = mockScrollIntoView;

// Default mock data
const defaultPerformanceData: PerformanceUpdate = {
  timestamp: new Date().toISOString(),
  gpu: {
    name: 'NVIDIA RTX A5500',
    utilization: 38,
    vram_used_gb: 2.0,
    vram_total_gb: 24.0,
    temperature: 40,
    power_watts: 120,
  },
  ai_models: {
    rtdetr: {
      status: 'loaded',
      vram_gb: 1.2,
      model: 'RT-DETRv2',
      device: 'cuda:0',
    },
  },
  nemotron: {
    status: 'running',
    slots_active: 1,
    slots_total: 4,
    context_size: 32768,
  },
  inference: {
    rtdetr_latency_ms: { avg: 14, p50: 12, p95: 25, p99: 35 },
    nemotron_latency_ms: { avg: 2100, p50: 1800, p95: 3500, p99: 5000 },
    pipeline_latency_ms: { avg: 2200, p50: 1900, p95: 3700, p99: 5200 },
    throughput: {
      detections_per_minute: 1.2,
      detections_total: 1847,
      analyses_total: 64,
    },
    queues: {
      detection_queue: 0,
      analysis_queue: 0,
    },
  },
  databases: {
    postgres: { status: 'connected', connections_active: 5, connections_max: 20, cache_hit_ratio: 0.99, transactions_per_min: 120 },
    redis: { status: 'connected', connected_clients: 3, memory_mb: 128, hit_ratio: 0.95, blocked_clients: 0 },
  },
  host: {
    cpu_percent: 12,
    ram_used_gb: 8,
    ram_total_gb: 32,
    disk_used_gb: 200,
    disk_total_gb: 1000,
  },
  containers: [
    { name: 'backend', status: 'running', health: 'healthy' },
    { name: 'frontend', status: 'running', health: 'healthy' },
    { name: 'postgres', status: 'running', health: 'healthy' },
    { name: 'redis', status: 'running', health: 'healthy' },
  ],
  alerts: [],
};

type ModelStatus = 'loaded' | 'unloaded' | 'loading' | 'error' | 'disabled';

interface MockModel {
  name: string;
  display_name: string;
  vram_mb: number;
  status: ModelStatus;
  category: string;
  enabled: boolean;
  available: boolean;
}

const defaultModels: MockModel[] = [
  { name: 'rtdetr', display_name: 'RT-DETRv2', vram_mb: 1200, status: 'loaded', category: 'detection', enabled: true, available: true },
  { name: 'nemotron', display_name: 'Nemotron', vram_mb: 8000, status: 'loaded', category: 'llm', enabled: true, available: true },
  { name: 'clip', display_name: 'CLIP ViT-L', vram_mb: 800, status: 'unloaded', category: 'embedding', enabled: true, available: true },
];

const defaultVramStats = {
  budget_mb: 24576,
  used_mb: 9200,
  available_mb: 15376,
  usage_percent: 37.4,
};

const defaultServices = {
  database: { status: 'healthy' as const, message: 'Connected' },
  redis: { status: 'healthy' as const, message: 'Connected' },
  ai: { status: 'healthy' as const, message: 'Models loaded' },
};

function setupMocks(overrides?: {
  performance?: Partial<PerformanceUpdate> | null;
  isConnected?: boolean;
  models?: typeof defaultModels;
  vramStats?: typeof defaultVramStats | null;
  services?: typeof defaultServices;
  overallStatus?: 'healthy' | 'degraded' | 'unhealthy' | null;
}) {
  const mockedUsePerformanceMetrics = usePerformanceMetrics as Mock;
  const mockedUseHealthStatusQuery = useHealthStatusQuery as Mock;
  const mockedUseModelZooStatus = useModelZooStatus as Mock;

  mockedUsePerformanceMetrics.mockReturnValue({
    current: overrides?.performance === null ? null : { ...defaultPerformanceData, ...overrides?.performance },
    history: { '5m': [], '15m': [], '60m': [] },
    alerts: [],
    isConnected: overrides?.isConnected ?? true,
    timeRange: '5m',
    setTimeRange: vi.fn(),
  });

  mockedUseHealthStatusQuery.mockReturnValue({
    data: undefined,
    isLoading: false,
    isRefetching: false,
    error: null,
    isStale: false,
    overallStatus: overrides?.overallStatus ?? 'healthy',
    services: overrides?.services ?? defaultServices,
    refetch: vi.fn().mockResolvedValue({}),
  });

  mockedUseModelZooStatus.mockReturnValue({
    models: overrides?.models ?? defaultModels,
    vramStats: overrides?.vramStats ?? defaultVramStats,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  });
}

describe('SystemSummaryRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScrollIntoView.mockClear();
    setupMocks();
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<SystemSummaryRow />);
      expect(screen.getByTestId('system-summary-row')).toBeInTheDocument();
    });

    it('renders all five indicators', () => {
      render(<SystemSummaryRow />);

      expect(screen.getByTestId('summary-indicator-overall')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-gpu')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-pipeline')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-ai-models')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-infra')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<SystemSummaryRow className="custom-class" />);
      const row = screen.getByTestId('system-summary-row');
      expect(row).toHaveClass('custom-class');
    });

    it('has correct region role and aria-label', () => {
      render(<SystemSummaryRow />);
      const region = screen.getByRole('region', { name: /system health summary/i });
      expect(region).toBeInTheDocument();
    });
  });

  describe('Indicator Labels', () => {
    it('displays correct labels for all indicators', () => {
      render(<SystemSummaryRow />);

      expect(screen.getByText('Overall')).toBeInTheDocument();
      expect(screen.getByText('GPU')).toBeInTheDocument();
      expect(screen.getByText('Pipeline')).toBeInTheDocument();
      expect(screen.getByText('AI Models')).toBeInTheDocument();
      expect(screen.getByText('Infra')).toBeInTheDocument();
    });
  });

  describe('GPU Indicator', () => {
    it('displays GPU metrics correctly', () => {
      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(within(gpuIndicator).getByTestId('indicator-primary-gpu')).toHaveTextContent('38% 40C');
      expect(within(gpuIndicator).getByTestId('indicator-secondary-gpu')).toHaveTextContent('2.0GB/24.0GB');
    });

    it('shows healthy state when GPU is cool and under-utilized', () => {
      render(<SystemSummaryRow />);

      const gpuStatus = screen.getByTestId('indicator-status-gpu');
      expect(gpuStatus.querySelector('svg')).toHaveClass('text-green-500');
    });

    it('shows degraded state when temperature is between 70-80C', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            temperature: 75,
          },
        },
      });

      render(<SystemSummaryRow />);

      const gpuStatus = screen.getByTestId('indicator-status-gpu');
      expect(gpuStatus.querySelector('svg')).toHaveClass('text-yellow-500');
    });

    it('shows critical state when temperature exceeds 80C', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            temperature: 85,
          },
        },
      });

      render(<SystemSummaryRow />);

      const gpuStatus = screen.getByTestId('indicator-status-gpu');
      expect(gpuStatus.querySelector('svg')).toHaveClass('text-red-500');
    });

    it('shows degraded state when utilization exceeds 95%', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            utilization: 98,
          },
        },
      });

      render(<SystemSummaryRow />);

      const gpuStatus = screen.getByTestId('indicator-status-gpu');
      expect(gpuStatus.querySelector('svg')).toHaveClass('text-yellow-500');
    });

    it('shows degraded state when GPU data is unavailable', () => {
      setupMocks({
        performance: {
          gpu: null,
        },
      });

      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(within(gpuIndicator).getByTestId('indicator-primary-gpu')).toHaveTextContent('No data');
    });
  });

  describe('Pipeline Indicator', () => {
    it('displays pipeline metrics correctly', () => {
      render(<SystemSummaryRow />);

      const pipelineIndicator = screen.getByTestId('summary-indicator-pipeline');
      expect(within(pipelineIndicator).getByTestId('indicator-primary-pipeline')).toHaveTextContent('0 queue');
      expect(within(pipelineIndicator).getByTestId('indicator-secondary-pipeline')).toHaveTextContent('1.2/min');
    });

    it('shows healthy state when queue depth is low', () => {
      render(<SystemSummaryRow />);

      const pipelineStatus = screen.getByTestId('indicator-status-pipeline');
      expect(pipelineStatus.querySelector('svg')).toHaveClass('text-green-500');
    });

    it('shows degraded state when queue depth is between 10-50', () => {
      setupMocks({
        performance: {
          inference: {
            ...defaultPerformanceData.inference!,
            queues: {
              detection_queue: 15,
              analysis_queue: 10,
            },
          },
        },
      });

      render(<SystemSummaryRow />);

      const pipelineStatus = screen.getByTestId('indicator-status-pipeline');
      expect(pipelineStatus.querySelector('svg')).toHaveClass('text-yellow-500');
    });

    it('shows critical state when queue depth exceeds 50', () => {
      setupMocks({
        performance: {
          inference: {
            ...defaultPerformanceData.inference!,
            queues: {
              detection_queue: 30,
              analysis_queue: 25,
            },
          },
        },
      });

      render(<SystemSummaryRow />);

      const pipelineStatus = screen.getByTestId('indicator-status-pipeline');
      expect(pipelineStatus.querySelector('svg')).toHaveClass('text-red-500');
    });
  });

  describe('AI Models Indicator', () => {
    it('displays AI models count correctly', () => {
      render(<SystemSummaryRow />);

      const aiIndicator = screen.getByTestId('summary-indicator-ai-models');
      expect(within(aiIndicator).getByTestId('indicator-primary-ai-models')).toHaveTextContent('2/3');
    });

    it('shows inference count', () => {
      render(<SystemSummaryRow />);

      const aiIndicator = screen.getByTestId('summary-indicator-ai-models');
      expect(within(aiIndicator).getByTestId('indicator-secondary-ai-models')).toHaveTextContent('1.9k inf');
    });

    it('shows healthy state when models are loaded', () => {
      render(<SystemSummaryRow />);

      const aiStatus = screen.getByTestId('indicator-status-ai-models');
      expect(aiStatus.querySelector('svg')).toHaveClass('text-green-500');
    });

    it('shows critical state when models have errors', () => {
      setupMocks({
        models: [
          { name: 'rtdetr', display_name: 'RT-DETRv2', vram_mb: 1200, status: 'error' as const, category: 'detection', enabled: true, available: true },
        ],
      });

      render(<SystemSummaryRow />);

      const aiStatus = screen.getByTestId('indicator-status-ai-models');
      expect(aiStatus.querySelector('svg')).toHaveClass('text-red-500');
    });

    it('shows degraded state when no models are loaded', () => {
      setupMocks({
        models: [
          { name: 'rtdetr', display_name: 'RT-DETRv2', vram_mb: 1200, status: 'unloaded' as const, category: 'detection', enabled: true, available: true },
        ],
      });

      render(<SystemSummaryRow />);

      const aiStatus = screen.getByTestId('indicator-status-ai-models');
      expect(aiStatus.querySelector('svg')).toHaveClass('text-yellow-500');
    });
  });

  describe('Infrastructure Indicator', () => {
    it('displays infrastructure count correctly', () => {
      render(<SystemSummaryRow />);

      const infraIndicator = screen.getByTestId('summary-indicator-infra');
      // Should show 4/4 (postgres, redis, containers, host)
      expect(within(infraIndicator).getByTestId('indicator-primary-infra')).toHaveTextContent('4/4');
    });

    it('shows healthy state when all components are healthy', () => {
      render(<SystemSummaryRow />);

      const infraStatus = screen.getByTestId('indicator-status-infra');
      expect(infraStatus.querySelector('svg')).toHaveClass('text-green-500');
    });

    it('shows critical state when database is down', () => {
      setupMocks({
        performance: {
          databases: {
            postgres: { status: 'error', connections_active: 0, connections_max: 20, cache_hit_ratio: 0, transactions_per_min: 0 },
            redis: { status: 'connected', connected_clients: 3, memory_mb: 128, hit_ratio: 0.95, blocked_clients: 0 },
          },
        },
      });

      render(<SystemSummaryRow />);

      const infraStatus = screen.getByTestId('indicator-status-infra');
      expect(infraStatus.querySelector('svg')).toHaveClass('text-red-500');
    });

    it('shows degraded state when host resources are high', () => {
      setupMocks({
        performance: {
          host: {
            cpu_percent: 92,
            ram_used_gb: 28,
            ram_total_gb: 32,
            disk_used_gb: 900,
            disk_total_gb: 1000,
          },
        },
      });

      render(<SystemSummaryRow />);

      const infraStatus = screen.getByTestId('indicator-status-infra');
      expect(infraStatus.querySelector('svg')).toHaveClass('text-yellow-500');
    });
  });

  describe('Overall Indicator', () => {
    it('shows healthy when all components are healthy', () => {
      render(<SystemSummaryRow />);

      const overallStatus = screen.getByTestId('indicator-status-overall');
      expect(overallStatus.querySelector('svg')).toHaveClass('text-green-500');
      expect(screen.getByTestId('indicator-primary-overall')).toHaveTextContent('healthy');
    });

    it('shows degraded when any component is degraded', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            temperature: 75,
          },
        },
      });

      render(<SystemSummaryRow />);

      const overallStatus = screen.getByTestId('indicator-status-overall');
      expect(overallStatus.querySelector('svg')).toHaveClass('text-yellow-500');
      expect(screen.getByTestId('indicator-primary-overall')).toHaveTextContent('degraded');
    });

    it('shows critical when any component is critical', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            temperature: 90,
          },
        },
      });

      render(<SystemSummaryRow />);

      const overallStatus = screen.getByTestId('indicator-status-overall');
      expect(overallStatus.querySelector('svg')).toHaveClass('text-red-500');
      expect(screen.getByTestId('indicator-primary-overall')).toHaveTextContent('critical');
    });

    it('considers health endpoint overall status', () => {
      setupMocks({
        overallStatus: 'unhealthy',
      });

      render(<SystemSummaryRow />);

      const overallStatus = screen.getByTestId('indicator-status-overall');
      expect(overallStatus.querySelector('svg')).toHaveClass('text-red-500');
    });
  });

  describe('Click-to-Scroll Functionality', () => {
    it('scrolls to GPU section when GPU indicator is clicked', () => {
      // Create mock element
      const mockElement = document.createElement('div');
      mockElement.id = 'section-gpu';
      document.body.appendChild(mockElement);

      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      fireEvent.click(gpuIndicator);

      expect(mockScrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });

      document.body.removeChild(mockElement);
    });

    it('scrolls to Pipeline section when Pipeline indicator is clicked', () => {
      const mockElement = document.createElement('div');
      mockElement.id = 'section-pipeline';
      document.body.appendChild(mockElement);

      render(<SystemSummaryRow />);

      const pipelineIndicator = screen.getByTestId('summary-indicator-pipeline');
      fireEvent.click(pipelineIndicator);

      expect(mockScrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });

      document.body.removeChild(mockElement);
    });

    it('calls onIndicatorClick callback when provided', () => {
      const mockCallback = vi.fn();
      render(<SystemSummaryRow onIndicatorClick={mockCallback} />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      fireEvent.click(gpuIndicator);

      expect(mockCallback).toHaveBeenCalledWith('section-gpu');
    });

    it('handles keyboard navigation with Enter key', () => {
      const mockElement = document.createElement('div');
      mockElement.id = 'section-ai-models';
      document.body.appendChild(mockElement);

      render(<SystemSummaryRow />);

      const aiIndicator = screen.getByTestId('summary-indicator-ai-models');
      fireEvent.keyDown(aiIndicator, { key: 'Enter' });

      expect(mockScrollIntoView).toHaveBeenCalled();

      document.body.removeChild(mockElement);
    });

    it('handles keyboard navigation with Space key', () => {
      const mockElement = document.createElement('div');
      mockElement.id = 'section-infra';
      document.body.appendChild(mockElement);

      render(<SystemSummaryRow />);

      const infraIndicator = screen.getByTestId('summary-indicator-infra');
      fireEvent.keyDown(infraIndicator, { key: ' ' });

      expect(mockScrollIntoView).toHaveBeenCalled();

      document.body.removeChild(mockElement);
    });
  });

  describe('Tooltips', () => {
    it('renders tooltip content for GPU indicator', () => {
      render(<SystemSummaryRow />);

      const tooltip = screen.getByTestId('indicator-tooltip-gpu');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveTextContent('Utilization: 38%');
      expect(tooltip).toHaveTextContent('Temperature: 40C');
    });

    it('renders tooltip content for Pipeline indicator', () => {
      render(<SystemSummaryRow />);

      const tooltip = screen.getByTestId('indicator-tooltip-pipeline');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveTextContent('Detection queue: 0');
      expect(tooltip).toHaveTextContent('Analysis queue: 0');
    });

    it('renders tooltip content for AI Models indicator', () => {
      render(<SystemSummaryRow />);

      const tooltip = screen.getByTestId('indicator-tooltip-ai-models');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveTextContent('Loaded models: 2');
      expect(tooltip).toHaveTextContent('RT-DETRv2');
    });

    it('renders tooltip content for Infrastructure indicator', () => {
      render(<SystemSummaryRow />);

      const tooltip = screen.getByTestId('indicator-tooltip-infra');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveTextContent('PostgreSQL: OK');
      expect(tooltip).toHaveTextContent('Redis: OK');
    });

    it('renders tooltip content for Overall indicator', () => {
      render(<SystemSummaryRow />);

      const tooltip = screen.getByTestId('indicator-tooltip-overall');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveTextContent('GPU: healthy');
      expect(tooltip).toHaveTextContent('Pipeline: healthy');
    });
  });

  describe('Accessibility', () => {
    it('all indicators have role="button"', () => {
      render(<SystemSummaryRow />);

      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(5);
    });

    it('all indicators have tabIndex="0"', () => {
      render(<SystemSummaryRow />);

      const indicators = [
        screen.getByTestId('summary-indicator-overall'),
        screen.getByTestId('summary-indicator-gpu'),
        screen.getByTestId('summary-indicator-pipeline'),
        screen.getByTestId('summary-indicator-ai-models'),
        screen.getByTestId('summary-indicator-infra'),
      ];

      indicators.forEach((indicator) => {
        expect(indicator).toHaveAttribute('tabindex', '0');
      });
    });

    it('indicators have descriptive aria-labels', () => {
      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveAttribute('aria-label');
      expect(gpuIndicator.getAttribute('aria-label')).toContain('GPU');
      expect(gpuIndicator.getAttribute('aria-label')).toContain('Click to scroll');
    });

    it('tooltips have role="tooltip"', () => {
      render(<SystemSummaryRow />);

      const tooltips = screen.getAllByRole('tooltip');
      expect(tooltips).toHaveLength(5);
    });
  });

  describe('Responsive Layout', () => {
    it('has responsive grid classes', () => {
      render(<SystemSummaryRow />);

      const row = screen.getByTestId('system-summary-row');
      expect(row).toHaveClass('grid-cols-2');
      expect(row).toHaveClass('sm:grid-cols-3');
      expect(row).toHaveClass('lg:grid-cols-5');
    });

    it('overall indicator spans 2 columns on mobile', () => {
      render(<SystemSummaryRow />);

      // The overall indicator is wrapped in a div with col-span-2
      const overallWrapper = screen.getByTestId('summary-indicator-overall').parentElement;
      expect(overallWrapper).toHaveClass('col-span-2');
      expect(overallWrapper).toHaveClass('sm:col-span-1');
    });
  });

  describe('Styling', () => {
    it('indicators have hover effects', () => {
      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveClass('hover:scale-105');
      expect(gpuIndicator).toHaveClass('hover:shadow-lg');
    });

    it('indicators have focus ring', () => {
      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveClass('focus:outline-none');
      expect(gpuIndicator).toHaveClass('focus:ring-2');
    });

    it('healthy indicators have green styling', () => {
      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveClass('bg-green-500/10');
      expect(gpuIndicator).toHaveClass('border-green-500/30');
    });

    it('degraded indicators have yellow styling', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            temperature: 75,
          },
        },
      });

      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveClass('bg-yellow-500/10');
      expect(gpuIndicator).toHaveClass('border-yellow-500/30');
    });

    it('critical indicators have red styling', () => {
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            temperature: 90,
          },
        },
      });

      render(<SystemSummaryRow />);

      const gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(gpuIndicator).toHaveClass('bg-red-500/10');
      expect(gpuIndicator).toHaveClass('border-red-500/30');
    });
  });

  describe('Edge Cases', () => {
    it('handles null performance data gracefully', () => {
      setupMocks({
        performance: null,
      });

      render(<SystemSummaryRow />);

      // Should still render all indicators
      expect(screen.getByTestId('summary-indicator-overall')).toBeInTheDocument();
      expect(screen.getByTestId('summary-indicator-gpu')).toBeInTheDocument();
    });

    it('handles empty models array', () => {
      setupMocks({
        models: [],
      });

      render(<SystemSummaryRow />);

      const aiIndicator = screen.getByTestId('summary-indicator-ai-models');
      // When totalModels is 0, we show "?" to indicate unknown
      expect(within(aiIndicator).getByTestId('indicator-primary-ai-models')).toHaveTextContent('0/?');
    });

    it('handles disconnected WebSocket', () => {
      setupMocks({
        isConnected: false,
        performance: null,
      });

      render(<SystemSummaryRow />);

      // Pipeline should show degraded state when disconnected
      const pipelineIndicator = screen.getByTestId('summary-indicator-pipeline');
      expect(within(pipelineIndicator).getByTestId('indicator-primary-pipeline')).toHaveTextContent('No data');
    });

    it('handles missing vramStats', () => {
      setupMocks({
        vramStats: null,
      });

      render(<SystemSummaryRow />);

      // Should still render AI models indicator
      expect(screen.getByTestId('summary-indicator-ai-models')).toBeInTheDocument();
    });

    it('handles large numbers with formatting', () => {
      setupMocks({
        performance: {
          inference: {
            ...defaultPerformanceData.inference!,
            throughput: {
              detections_per_minute: 120.5,
              detections_total: 1500000,
              analyses_total: 50000,
            },
          },
        },
      });

      render(<SystemSummaryRow />);

      const aiIndicator = screen.getByTestId('summary-indicator-ai-models');
      // 1.5M + 50k = 1.55M, formatted as 1.6M
      expect(within(aiIndicator).getByTestId('indicator-secondary-ai-models')).toHaveTextContent('1.6M inf');
    });
  });

  describe('Updates', () => {
    it('updates when performance data changes', () => {
      const { rerender } = render(<SystemSummaryRow />);

      // Initial render
      let gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(within(gpuIndicator).getByTestId('indicator-primary-gpu')).toHaveTextContent('38% 40C');

      // Update mock and rerender
      setupMocks({
        performance: {
          gpu: {
            ...defaultPerformanceData.gpu!,
            utilization: 75,
            temperature: 65,
          },
        },
      });

      rerender(<SystemSummaryRow />);

      gpuIndicator = screen.getByTestId('summary-indicator-gpu');
      expect(within(gpuIndicator).getByTestId('indicator-primary-gpu')).toHaveTextContent('75% 65C');
    });
  });
});
