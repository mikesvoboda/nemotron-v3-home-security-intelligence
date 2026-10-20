/**
 * GpuSettingsPage Tests (F-176, F-178, F-182).
 *
 * R2a row 36 retired F-177 (Rescan GPUs), F-179 (Assignment table & Save),
 * F-180 (Service-health column), F-181 (Apply), and F-183 (Import & Rollback).
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import GpuSettingsPage from './GpuSettingsPage';
import * as gpuConfigApi from '../services/gpuConfigApi';
import { renderWithProviders } from '../test-utils/renderWithProviders';

import type {
  GpuListResponse,
  GpuConfig,
  StrategyPreviewResponse,
} from '../services/gpuConfigApi';

vi.mock('../services/gpuConfigApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/gpuConfigApi')>();
  return {
    ...actual,
    getGpus: vi.fn(),
    getGpuConfig: vi.fn(),
    previewStrategy: vi.fn(),
  };
});

const mockGpuList: GpuListResponse = {
  gpus: [
    {
      index: 0,
      name: 'NVIDIA RTX A5000',
      vram_total_mb: 24576,
      vram_used_mb: 8192,
      compute_capability: '8.6',
    },
    {
      index: 1,
      name: 'NVIDIA RTX A5000',
      vram_total_mb: 24576,
      vram_used_mb: 4096,
      compute_capability: '8.6',
    },
  ],
};

const mockGpuConfig: GpuConfig = {
  strategy: 'manual',
  assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-yolo26', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-enrichment', gpu_index: 1, vram_budget_override: null },
  ],
  updated_at: '2026-01-23T10:30:00Z',
};

const emptyGpuList: GpuListResponse = {
  gpus: [],
};

const mockBalancedPreview: StrategyPreviewResponse = {
  strategy: 'balanced',
  proposed_assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-yolo26', gpu_index: 1, vram_budget_override: null },
    { service: 'ai-enrichment', gpu_index: 0, vram_budget_override: null },
  ],
  warnings: [],
};

describe('GpuSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('should render the page title and only kept controls', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('GPU Settings')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /apply/i })).not.toBeInTheDocument();
    });

    it('should show loading state initially', () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      renderWithProviders(<GpuSettingsPage />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should render GPU device cards when GPUs are detected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-device-card-0')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-device-card-1')).toBeInTheDocument();
      });
    });

    it('should render strategy selector', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-strategy-selector')).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('should show empty state with Refresh button when no GPUs are detected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(emptyGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('No GPUs Detected')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('should show error when fetching GPUs fails', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch GPUs')
      );
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(
        () => {
          expect(screen.getByText(/Failed to load GPU configuration/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('GPU device cards', () => {
    it('should display GPU name and index', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('NVIDIA RTX A5000')).toHaveLength(2);
        expect(screen.getByText('GPU 0')).toBeInTheDocument();
        expect(screen.getByText('GPU 1')).toBeInTheDocument();
      });
    });

    it('should display VRAM usage', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-usage-indicator-0')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-usage-indicator-1')).toBeInTheDocument();
      });
    });
  });

  describe('strategy selection', () => {
    it('should display all available strategies', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('strategy-option-manual')).toBeInTheDocument();
        expect(screen.getByTestId('strategy-option-vram_based')).toBeInTheDocument();
        expect(screen.getByTestId('strategy-option-latency_optimized')).toBeInTheDocument();
        expect(screen.getByTestId('strategy-option-isolation_first')).toBeInTheDocument();
        expect(screen.getByTestId('strategy-option-balanced')).toBeInTheDocument();
      });
    });

    it('should select the current strategy', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        const manualOption = screen.getByTestId('strategy-option-manual');
        const radioInput = manualOption.querySelector('input[type="radio"]');
        expect(radioInput).toBeChecked();
      });
    });

    it('should allow changing strategy', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      const { user } = renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('strategy-option-balanced')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('strategy-option-balanced'));

      await waitFor(() => {
        const balancedOption = screen.getByTestId('strategy-option-balanced');
        const radioInput = balancedOption.querySelector('input[type="radio"]');
        expect(radioInput).toBeChecked();
      });
    });
  });

  describe('preview functionality', () => {
    it('should show preview button', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('preview-strategy-button')).toBeInTheDocument();
      });
    });

    it('should disable preview when manual strategy is selected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('preview-strategy-button')).toBeDisabled();
      });
    });

    it('should enable preview when non-manual strategy is selected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockGpuConfig,
        strategy: 'balanced',
      });

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('preview-strategy-button')).not.toBeDisabled();
      });
    });
  });

  describe('accessibility', () => {
    it('should have data-testid for page', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-settings-page')).toBeInTheDocument();
      });
    });
  });

  describe('batch operations (NEM-4943)', () => {
    it('should render batch actions component', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-batch-actions')).toBeInTheDocument();
      });
    });

    it('should render all batch action buttons', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('assign-all-button')).toBeInTheDocument();
        expect(screen.getByTestId('reset-defaults-button')).toBeInTheDocument();
        expect(screen.getByTestId('auto-balance-button')).toBeInTheDocument();
      });
    });

    it('should apply balanced strategy when Auto-Balance is clicked', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.previewStrategy as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockBalancedPreview
      );

      const { user } = renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('auto-balance-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('auto-balance-button'));

      await waitFor(() => {
        expect(gpuConfigApi.previewStrategy).toHaveBeenCalled();
        const calls = (gpuConfigApi.previewStrategy as ReturnType<typeof vi.fn>).mock.calls;
        expect(calls.length).toBeGreaterThan(0);
        expect(calls[0][0]).toBe('balanced');
      });
    });
  });
});
