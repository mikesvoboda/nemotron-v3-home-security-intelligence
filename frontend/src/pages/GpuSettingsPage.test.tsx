/**
 * GpuSettingsPage Tests
 *
 * Tests for the GPU Settings page that provides:
 * - GPU device display and VRAM visualization
 * - Assignment strategy selection
 * - Service-to-GPU assignment management
 * - Configuration save and apply functionality
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import GpuSettingsPage from './GpuSettingsPage';
import * as gpuConfigApi from '../services/gpuConfigApi';
import { renderWithProviders } from '../test-utils/renderWithProviders';

import type {
  GpuListResponse,
  GpuConfig,
  GpuStatusResponse,
  GpuConfigUpdateResponse,
  GpuApplyResult,
  ServiceHealthResponse,
} from '../services/gpuConfigApi';

// Mock the GPU config API module
vi.mock('../services/gpuConfigApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/gpuConfigApi')>();
  return {
    ...actual,
    getGpus: vi.fn(),
    getGpuConfig: vi.fn(),
    getGpuStatus: vi.fn(),
    getServiceHealth: vi.fn(),
    updateGpuConfig: vi.fn(),
    applyGpuConfig: vi.fn(),
    detectGpus: vi.fn(),
    previewStrategy: vi.fn(),
  };
});

// ============================================================================
// Test Data
// ============================================================================

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

const mockGpuStatus: GpuStatusResponse = {
  in_progress: false,
  services_pending: [],
  services_completed: ['ai-llm', 'ai-yolo26', 'ai-enrichment'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'running', message: null },
    { service: 'ai-enrichment', status: 'running', message: null },
  ],
};

const mockUpdateResponse: GpuConfigUpdateResponse = {
  success: true,
  warnings: [],
};

const mockApplyResult: GpuApplyResult = {
  success: true,
  warnings: [],
  restarted_services: ['ai-llm', 'ai-yolo26', 'ai-enrichment'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'running', message: null },
    { service: 'ai-enrichment', status: 'running', message: null },
  ],
};

const emptyGpuList: GpuListResponse = {
  gpus: [],
};

const mockServiceHealth: ServiceHealthResponse = {
  services: [
    { name: 'ai-llm', status: 'running', health: 'healthy', gpu_index: 0, restart_status: null },
    { name: 'ai-yolo26', status: 'running', health: 'healthy', gpu_index: 0, restart_status: null },
    {
      name: 'ai-enrichment',
      status: 'running',
      health: 'healthy',
      gpu_index: 1,
      restart_status: null,
    },
  ],
};

// ============================================================================
// Tests
// ============================================================================

describe('GpuSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('should render the page title', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('GPU Settings')).toBeInTheDocument();
      });
    });

    it('should show loading state initially', () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      renderWithProviders(<GpuSettingsPage />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should render GPU device cards when GPUs are detected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-device-card-0')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-device-card-1')).toBeInTheDocument();
      });
    });

    it('should render strategy selector', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-strategy-selector')).toBeInTheDocument();
      });
    });

    it('should render assignment table', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-assignment-table')).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('should show empty state when no GPUs are detected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(emptyGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('No GPUs Detected')).toBeInTheDocument();
      });
    });

    it('should show rescan button in empty state', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(emptyGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Rescan GPUs/i })).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('should show error when fetching GPUs fails', async () => {
      // Reject all retry attempts
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch GPUs')
      );
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      // Wait longer to account for retry delay
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
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

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
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        // GPU 0: 8192 MB used / 24576 MB total = 33.3%
        expect(screen.getByTestId('gpu-usage-indicator-0')).toBeInTheDocument();
        // GPU 1: 4096 MB used / 24576 MB total = 16.7%
        expect(screen.getByTestId('gpu-usage-indicator-1')).toBeInTheDocument();
      });
    });
  });

  describe('strategy selection', () => {
    it('should display all available strategies', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

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
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

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
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

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

  describe('assignment table', () => {
    it('should display all service assignments', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('assignment-row-ai-llm')).toBeInTheDocument();
        expect(screen.getByTestId('assignment-row-ai-yolo26')).toBeInTheDocument();
        expect(screen.getByTestId('assignment-row-ai-enrichment')).toBeInTheDocument();
      });
    });

    it('should show service status badges as unknown when not polling', async () => {
      // Service health is only fetched during apply/polling, so initially shows "Unknown"
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      // Wait for the page to load and show assignment table first
      await waitFor(() => {
        expect(screen.getByTestId('gpu-assignment-table')).toBeInTheDocument();
      });

      // Then check status badges
      await waitFor(() => {
        expect(screen.getByTestId('status-badge-ai-llm')).toHaveTextContent('Unknown');
        expect(screen.getByTestId('status-badge-ai-yolo26')).toHaveTextContent('Unknown');
        expect(screen.getByTestId('status-badge-ai-enrichment')).toHaveTextContent('Unknown');
      });
    });

    it('should enable GPU dropdown when strategy is manual', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        const gpuSelect = screen.getByTestId('gpu-select-ai-llm');
        expect(gpuSelect).not.toBeDisabled();
      });
    });
  });

  describe('save and apply', () => {
    it('should render save and apply buttons', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('save-config-button')).toBeInTheDocument();
        expect(screen.getByTestId('apply-config-button')).toBeInTheDocument();
      });
    });

    it('should disable save button when no changes', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('save-config-button')).toBeDisabled();
      });
    });

    it('should enable save button when changes are made', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      const { user } = renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('strategy-option-balanced')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('strategy-option-balanced'));

      await waitFor(() => {
        expect(screen.getByTestId('save-config-button')).not.toBeDisabled();
      });
    });

    it('should show confirmation dialog when apply is clicked', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);
      (gpuConfigApi.updateGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockUpdateResponse
      );
      (gpuConfigApi.applyGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockApplyResult);

      const { user } = renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('apply-config-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('apply-config-button'));

      await waitFor(() => {
        expect(screen.getByTestId('apply-confirmation-dialog')).toBeInTheDocument();
      });
    });
  });

  describe('preview functionality', () => {
    it('should show preview button', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('preview-strategy-button')).toBeInTheDocument();
      });
    });

    it('should disable preview when manual strategy is selected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        // Manual strategy is selected by default, preview should be disabled
        expect(screen.getByTestId('preview-strategy-button')).toBeDisabled();
      });
    });

    it('should enable preview when non-manual strategy is selected', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockGpuConfig,
        strategy: 'balanced',
      });
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

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
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-settings-page')).toBeInTheDocument();
      });
    });

    it('should have accessible labels for GPU selects', async () => {
      (gpuConfigApi.getGpus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuList);
      (gpuConfigApi.getGpuConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuConfig);
      (gpuConfigApi.getGpuStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStatus);
      (gpuConfigApi.getServiceHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockServiceHealth);

      renderWithProviders(<GpuSettingsPage />);

      await waitFor(() => {
        const gpuSelect = screen.getByTestId('gpu-select-ai-llm');
        expect(gpuSelect).toHaveAttribute('aria-label', 'GPU assignment for ai-llm');
      });
    });
  });
});
