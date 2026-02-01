/**
 * Unit tests for ModelZooPanel component
 *
 * Tests the main Model Zoo admin panel including per-GPU VRAM bars,
 * model grouping, and load/unload functionality.
 *
 * TDD RED PHASE: These tests will fail until the component is implemented.
 *
 * @see NEM-4788
 * @see docs/plans/2025-01-31-model-zoo-management-design.md
 */

import { screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

import ModelZooPanel from './ModelZooPanel';
import * as useModelZooModule from '../../hooks/useModelZoo';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type {
  ModelListResponse,
  VRAMSummaryResponse,
  ModelStatus,
  GpuVRAMInfo,
} from '../../services/modelZooApi';

// Mock the useModelZoo hooks
vi.mock('../../hooks/useModelZoo', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../hooks/useModelZoo')>();
  return {
    ...actual,
    useModels: vi.fn(),
    useVRAMSummary: vi.fn(),
    useLoadModel: vi.fn(),
    useUnloadModel: vi.fn(),
  };
});

// ============================================================================
// Mock Data
// ============================================================================

const mockGpu0Model1: ModelStatus = {
  name: 'vehicle-segment-classification',
  category: 'classification',
  estimated_vram_mb: 1500,
  enabled: true,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: {
    loaded: true,
    actual_vram_mb: 1400,
    last_used: '2026-01-31T10:30:00Z',
    load_count: 3,
  },
};

const mockGpu0Model2: ModelStatus = {
  name: 'fashion-clip',
  category: 'classification',
  estimated_vram_mb: 800,
  enabled: true,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: {
    loaded: false,
    actual_vram_mb: null,
    last_used: null,
    load_count: 0,
  },
};

const mockGpu1Model1: ModelStatus = {
  name: 'threat-detection-yolov8n',
  category: 'detection',
  estimated_vram_mb: 300,
  enabled: true,
  service: 'ai-enrichment-light',
  gpu_id: 1,
  runtime: {
    loaded: true,
    actual_vram_mb: 287,
    last_used: '2026-01-31T10:30:00Z',
    load_count: 5,
  },
};

const mockGpu1Model2: ModelStatus = {
  name: 'osnet-x0-25',
  category: 'embedding',
  estimated_vram_mb: 200,
  enabled: true,
  service: 'ai-enrichment-light',
  gpu_id: 1,
  runtime: {
    loaded: true,
    actual_vram_mb: 180,
    last_used: '2026-01-31T10:25:00Z',
    load_count: 10,
  },
};

const mockDisabledModel: ModelStatus = {
  name: 'xclip-base',
  category: 'classification',
  estimated_vram_mb: 2000,
  enabled: false,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: null,
};

const mockModelListResponse: ModelListResponse = {
  models: [mockGpu0Model1, mockGpu0Model2, mockGpu1Model1, mockGpu1Model2, mockDisabledModel],
  service_status: {
    'ai-enrichment': 'healthy',
    'ai-enrichment-light': 'healthy',
  },
};

const mockGpuVRAMInfo0: GpuVRAMInfo = {
  gpu_id: 0,
  service: 'ai-enrichment',
  budget_mb: 6800,
  used_mb: 1400,
  available_mb: 5400,
  utilization_percent: 20.6,
  loaded_models: ['vehicle-segment-classification'],
};

const mockGpuVRAMInfo1: GpuVRAMInfo = {
  gpu_id: 1,
  service: 'ai-enrichment-light',
  budget_mb: 1200,
  used_mb: 467,
  available_mb: 733,
  utilization_percent: 38.9,
  loaded_models: ['threat-detection-yolov8n', 'osnet-x0-25'],
};

const mockVRAMSummaryResponse: VRAMSummaryResponse = {
  gpus: [mockGpuVRAMInfo0, mockGpuVRAMInfo1],
  totals: {
    budget_mb: 8000,
    used_mb: 1867,
    available_mb: 6133,
    model_count: 3,
  },
};

// ============================================================================
// Default Hook Returns
// ============================================================================

const defaultUseModelsReturn: {
  data: ModelListResponse | undefined;
  models: ModelStatus[];
  serviceStatus: Record<string, string>;
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: ReturnType<typeof vi.fn>;
} = {
  data: mockModelListResponse,
  models: mockModelListResponse.models,
  serviceStatus: mockModelListResponse.service_status,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
};

const defaultUseVRAMSummaryReturn: {
  data: VRAMSummaryResponse | undefined;
  gpus: GpuVRAMInfo[];
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: ReturnType<typeof vi.fn>;
} = {
  data: mockVRAMSummaryResponse,
  gpus: mockVRAMSummaryResponse.gpus,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
};

const defaultUseLoadModelReturn: {
  mutation: ReturnType<typeof import('@tanstack/react-query').useMutation>;
  loadModel: ReturnType<typeof vi.fn>;
  isLoading: boolean;
  error: Error | null;
} = {
  mutation: {} as ReturnType<typeof import('@tanstack/react-query').useMutation>,
  loadModel: vi.fn(),
  isLoading: false,
  error: null,
};

const defaultUseUnloadModelReturn: {
  mutation: ReturnType<typeof import('@tanstack/react-query').useMutation>;
  unloadModel: ReturnType<typeof vi.fn>;
  isLoading: boolean;
  error: Error | null;
} = {
  mutation: {} as ReturnType<typeof import('@tanstack/react-query').useMutation>,
  unloadModel: vi.fn(),
  isLoading: false,
  error: null,
};

// ============================================================================
// Setup Helper
// ============================================================================

function setupMocks(overrides: {
  useModels?: Partial<typeof defaultUseModelsReturn>;
  useVRAMSummary?: Partial<typeof defaultUseVRAMSummaryReturn>;
  useLoadModel?: Partial<typeof defaultUseLoadModelReturn>;
  useUnloadModel?: Partial<typeof defaultUseUnloadModelReturn>;
} = {}) {
  (useModelZooModule.useModels as Mock).mockReturnValue({
    ...defaultUseModelsReturn,
    ...overrides.useModels,
  });
  (useModelZooModule.useVRAMSummary as Mock).mockReturnValue({
    ...defaultUseVRAMSummaryReturn,
    ...overrides.useVRAMSummary,
  });
  (useModelZooModule.useLoadModel as Mock).mockReturnValue({
    ...defaultUseLoadModelReturn,
    ...overrides.useLoadModel,
  });
  (useModelZooModule.useUnloadModel as Mock).mockReturnValue({
    ...defaultUseUnloadModelReturn,
    ...overrides.useUnloadModel,
  });
}

// ============================================================================
// Tests
// ============================================================================

describe('ModelZooPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  // ============================================================================
  // Loading State Tests
  // ============================================================================

  describe('loading state', () => {
    it('renders loading state while fetching', () => {
      setupMocks({
        useModels: { isLoading: true, models: [], data: undefined },
        useVRAMSummary: { isLoading: true, gpus: [], data: undefined },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('shows loading spinner during initial fetch', () => {
      setupMocks({
        useModels: { isLoading: true, models: [], data: undefined },
        useVRAMSummary: { isLoading: true, gpus: [], data: undefined },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Error State Tests
  // ============================================================================

  describe('error state', () => {
    it('renders error state on fetch failure', () => {
      const error = new Error('Failed to fetch models');
      setupMocks({
        useModels: { error, isLoading: false, models: [], data: undefined },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByText(/error/i)).toBeInTheDocument();
      expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
    });

    it('shows retry button on error', () => {
      const error = new Error('Network error');
      setupMocks({
        useModels: { error, isLoading: false, models: [], data: undefined },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('calls refetch when retry button is clicked', async () => {
      const refetch = vi.fn();
      const error = new Error('Network error');
      setupMocks({
        useModels: { error, isLoading: false, models: [], data: undefined, refetch },
      });

      const { user } = renderWithProviders(<ModelZooPanel />);

      await user.click(screen.getByRole('button', { name: /retry/i }));

      expect(refetch).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // VRAM Bar Tests
  // ============================================================================

  describe('VRAM bars', () => {
    it('shows both GPU VRAM bars', () => {
      renderWithProviders(<ModelZooPanel />);

      // Should show VRAM bars for GPU 0 and GPU 1
      expect(screen.getByTestId('vram-bar-gpu-0')).toBeInTheDocument();
      expect(screen.getByTestId('vram-bar-gpu-1')).toBeInTheDocument();
    });

    it('displays VRAM usage for GPU 0', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu0Section = screen.getByTestId('vram-bar-gpu-0');
      expect(within(gpu0Section).getByText(/1400/)).toBeInTheDocument();
      expect(within(gpu0Section).getByText(/6800/)).toBeInTheDocument();
    });

    it('displays VRAM usage for GPU 1', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu1Section = screen.getByTestId('vram-bar-gpu-1');
      expect(within(gpu1Section).getByText(/467/)).toBeInTheDocument();
      expect(within(gpu1Section).getByText(/1200/)).toBeInTheDocument();
    });

    it('shows utilization percentage', () => {
      renderWithProviders(<ModelZooPanel />);

      // GPU 0 is ~20.6%, GPU 1 is ~38.9%
      expect(screen.getByText(/20\.6/)).toBeInTheDocument();
      expect(screen.getByText(/38\.9/)).toBeInTheDocument();
    });

    it('shows service name on VRAM bar', () => {
      renderWithProviders(<ModelZooPanel />);

      // Service names appear in VRAM bars and GPU sections - verify they exist
      const gpu0Bar = screen.getByTestId('vram-bar-gpu-0');
      const gpu1Bar = screen.getByTestId('vram-bar-gpu-1');

      expect(within(gpu0Bar).getByText('ai-enrichment')).toBeInTheDocument();
      expect(within(gpu1Bar).getByText('ai-enrichment-light')).toBeInTheDocument();
    });

    it('VRAM bar has correct fill based on usage', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu0Bar = screen.getByTestId('vram-bar-gpu-0');
      const fillElement = within(gpu0Bar).getByTestId('vram-fill');

      // Should have width style corresponding to ~20.6%
      const widthStyle = fillElement.style.width;
      expect(widthStyle).toContain('20');
    });
  });

  // ============================================================================
  // Model Grouping Tests
  // ============================================================================

  describe('model grouping', () => {
    it('displays models grouped by GPU', () => {
      renderWithProviders(<ModelZooPanel />);

      // Should have sections for GPU 0 and GPU 1
      expect(screen.getByTestId('gpu-section-0')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-section-1')).toBeInTheDocument();
    });

    it('shows correct models in GPU 0 section', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu0Section = screen.getByTestId('gpu-section-0');

      // GPU 0 models
      expect(within(gpu0Section).getByText('vehicle-segment-classification')).toBeInTheDocument();
      expect(within(gpu0Section).getByText('fashion-clip')).toBeInTheDocument();
    });

    it('shows correct models in GPU 1 section', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu1Section = screen.getByTestId('gpu-section-1');

      // GPU 1 models
      expect(within(gpu1Section).getByText('threat-detection-yolov8n')).toBeInTheDocument();
      expect(within(gpu1Section).getByText('osnet-x0-25')).toBeInTheDocument();
    });

    it('shows GPU section header with service name', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu0Section = screen.getByTestId('gpu-section-0');
      const gpu1Section = screen.getByTestId('gpu-section-1');

      // GPU section headers contain the GPU name with model type
      expect(within(gpu0Section).getByText(/GPU 0.*Heavy Models/i)).toBeInTheDocument();
      expect(within(gpu1Section).getByText(/GPU 1.*Light Models/i)).toBeInTheDocument();
    });

    it('shows model count in each GPU section', () => {
      renderWithProviders(<ModelZooPanel />);

      const gpu0Section = screen.getByTestId('gpu-section-0');
      const gpu1Section = screen.getByTestId('gpu-section-1');

      // GPU 0 has 2 enabled models, GPU 1 has 2 models
      expect(within(gpu0Section).getByText(/2 models/i)).toBeInTheDocument();
      expect(within(gpu1Section).getByText(/2 models/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Disabled Models Section Tests
  // ============================================================================

  describe('disabled models section', () => {
    it('shows disabled models in separate section', () => {
      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByTestId('disabled-models-section')).toBeInTheDocument();
    });

    it('displays disabled model names', async () => {
      const { user } = renderWithProviders(<ModelZooPanel />);

      // Disabled section starts collapsed, so expand it first
      const disabledSection = screen.getByTestId('disabled-models-section');
      const expandButton = within(disabledSection).getByRole('button');
      await user.click(expandButton);

      // Now the model name should be visible
      expect(within(disabledSection).getByText('xclip-base')).toBeInTheDocument();
    });

    it('shows disabled models count', () => {
      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByText(/1 disabled/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Service Health Tests
  // ============================================================================

  describe('service health', () => {
    it('shows healthy status for services', () => {
      renderWithProviders(<ModelZooPanel />);

      // Both services are healthy
      const healthIndicators = screen.getAllByTestId('service-health-indicator');
      healthIndicators.forEach((indicator) => {
        expect(indicator).toHaveClass(/healthy|green/i);
      });
    });

    it('shows unhealthy status when service is down', () => {
      setupMocks({
        useModels: {
          ...defaultUseModelsReturn,
          serviceStatus: {
            'ai-enrichment': 'unhealthy',
            'ai-enrichment-light': 'healthy',
          },
        },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByText(/unhealthy/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Load/Unload Integration Tests
  // ============================================================================

  describe('load/unload operations', () => {
    it('calls loadModel when load button is clicked on model card', async () => {
      const loadModel = vi.fn().mockResolvedValue({ success: true });
      setupMocks({
        useLoadModel: { loadModel, isLoading: false },
      });

      const { user } = renderWithProviders(<ModelZooPanel />);

      // Find unloaded model (fashion-clip) and click load
      const fashionClipCard = screen.getByTestId('model-card-fashion-clip');
      const loadButton = within(fashionClipCard).getByRole('button', { name: /^load$/i });

      await user.click(loadButton);

      expect(loadModel).toHaveBeenCalledWith('fashion-clip');
    });

    it('shows loading state on model card during load', () => {
      // When useLoadModel.isLoading is true, buttons should be disabled
      setupMocks({
        useLoadModel: { isLoading: true },
      });

      renderWithProviders(<ModelZooPanel />);

      // When loading is in progress, the refresh button should be disabled
      // This indicates loading state at the panel level
      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      expect(refreshButton).toBeDisabled();
    });

    it('calls unloadModel when unload is confirmed on model card', async () => {
      const unloadModel = vi.fn();
      setupMocks({
        useUnloadModel: { unloadModel, isLoading: false },
      });

      const { user } = renderWithProviders(<ModelZooPanel />);

      // Find loaded model and click unload
      const threatCard = screen.getByTestId('model-card-threat-detection-yolov8n');
      const unloadButton = within(threatCard).getByRole('button', { name: /^unload$/i });

      await user.click(unloadButton);

      // Confirm in dialog
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /confirm/i }));

      expect(unloadModel).toHaveBeenCalledWith('threat-detection-yolov8n');
    });
  });

  // ============================================================================
  // Empty State Tests
  // ============================================================================

  describe('empty state', () => {
    it('shows empty state when no models', () => {
      setupMocks({
        useModels: { models: [], data: { models: [], service_status: {} } },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByText(/no models/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Summary Statistics Tests
  // ============================================================================

  describe('summary statistics', () => {
    it('shows total models count', () => {
      renderWithProviders(<ModelZooPanel />);

      // 5 total models (4 enabled + 1 disabled)
      expect(screen.getByText(/5 models/i)).toBeInTheDocument();
    });

    it('shows loaded models count', () => {
      renderWithProviders(<ModelZooPanel />);

      // 3 loaded models
      expect(screen.getByText(/3 loaded/i)).toBeInTheDocument();
    });

    it('shows total VRAM usage', () => {
      renderWithProviders(<ModelZooPanel />);

      // Total: 1867/8000 MB
      expect(screen.getByText(/1867/)).toBeInTheDocument();
      expect(screen.getByText(/8000/)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  describe('accessibility', () => {
    it('has main panel with correct role', () => {
      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByRole('region', { name: /model zoo/i })).toBeInTheDocument();
    });

    it('GPU sections are collapsible', async () => {
      const { user } = renderWithProviders(<ModelZooPanel />);

      const gpu0Header = screen.getByRole('button', { name: /GPU 0/i });

      await user.click(gpu0Header);

      // Content should toggle visibility
      await waitFor(() => {
        const gpu0Section = screen.getByTestId('gpu-section-0');
        const models = within(gpu0Section).queryAllByTestId(/model-card/);
        expect(models.length).toBe(0); // Models hidden when collapsed
      });
    });
  });

  // ============================================================================
  // Refresh Tests
  // ============================================================================

  describe('refresh functionality', () => {
    it('has refresh button', () => {
      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('calls refetch when refresh is clicked', async () => {
      const modelsRefetch = vi.fn();
      const vramRefetch = vi.fn();
      setupMocks({
        useModels: { refetch: modelsRefetch },
        useVRAMSummary: { refetch: vramRefetch },
      });

      const { user } = renderWithProviders(<ModelZooPanel />);

      await user.click(screen.getByRole('button', { name: /refresh/i }));

      expect(modelsRefetch).toHaveBeenCalled();
      expect(vramRefetch).toHaveBeenCalled();
    });

    it('shows refreshing indicator during refetch', () => {
      setupMocks({
        useModels: { isRefetching: true },
      });

      renderWithProviders(<ModelZooPanel />);

      expect(screen.getByTestId('refreshing-indicator')).toBeInTheDocument();
    });
  });
});
