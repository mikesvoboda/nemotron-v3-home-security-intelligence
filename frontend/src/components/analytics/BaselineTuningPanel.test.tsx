/**
 * Tests for BaselineTuningPanel component
 *
 * TDD: Tests written first to define the expected behavior (Red phase).
 * Tests baseline sensitivity tuning UI that allows users to:
 * - Adjust sensitivity (threshold_stdev: 0.5-5.0, default 2.0)
 * - Set min_samples (default 10, min 1)
 * - Reset baseline data for a camera
 * - Toggle between global and per-camera settings
 *
 * @see NEM-4919 - Phase 3: Baseline Tuning UI
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import BaselineTuningPanel from './BaselineTuningPanel';
import * as gpuConfigApi from '../../services/baselineConfigApi';

// Mock the API module
vi.mock('../../services/baselineConfigApi', () => ({
  fetchBaselineConfig: vi.fn(),
  updateBaselineConfig: vi.fn(),
  resetCameraBaseline: vi.fn(),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
};

describe('BaselineTuningPanel', () => {
  const mockCameraId = 'front_door';

  const mockConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    override_global_config: false,
    global_config: {
      threshold_stdev: 2.0,
      min_samples: 10,
      decay_factor: 0.1,
      window_days: 30,
    },
  };

  const mockCustomConfig = {
    threshold_stdev: 3.5,
    min_samples: 20,
    override_global_config: true,
    global_config: {
      threshold_stdev: 2.0,
      min_samples: 10,
      decay_factor: 0.1,
      window_days: 30,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockConfig);
  });

  describe('rendering', () => {
    it('renders sensitivity slider with current value', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
        expect(screen.getByDisplayValue('2.0')).toBeInTheDocument();
      });
    });

    it('renders min_samples input with current value', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/minimum samples/i)).toBeInTheDocument();
        expect(screen.getByDisplayValue('10')).toBeInTheDocument();
      });
    });

    it('shows "Using Global Settings" when override_global_config = false', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText(/using global settings/i)).toBeInTheDocument();
      });
    });

    it('shows "Custom Override" when override_global_config = true', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText(/custom override/i)).toBeInTheDocument();
      });
    });

    it('disables inputs when using global settings', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
        const minSamplesInput = screen.getByLabelText(/minimum samples/i);

        expect(sensitivitySlider).toBeDisabled();
        expect(minSamplesInput).toBeDisabled();
      });
    });

    it('enables inputs when using custom settings', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
        const minSamplesInput = screen.getByLabelText(/minimum samples/i);

        expect(sensitivitySlider).not.toBeDisabled();
        expect(minSamplesInput).not.toBeDisabled();
      });
    });
  });

  describe('unsaved changes indicator', () => {
    it('shows "Unsaved Changes" indicator when form is dirty', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
      });

      const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
      fireEvent.change(sensitivitySlider, { target: { value: '4.0' } });

      await waitFor(() => {
        expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
      });
    });

    it('save button disabled when no changes', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: /save/i });
        expect(saveButton).toBeDisabled();
      });
    });

    it('save button enabled when changes made', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
      });

      const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
      fireEvent.change(sensitivitySlider, { target: { value: '3.0' } });

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: /save/i });
        expect(saveButton).not.toBeDisabled();
      });
    });
  });

  describe('reset functionality', () => {
    it('reset button shows confirmation modal', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reset baseline/i })).toBeInTheDocument();
      });

      const resetButton = screen.getByRole('button', { name: /reset baseline/i });
      await userEvent.click(resetButton);

      await waitFor(() => {
        expect(screen.getByText(/confirm reset/i)).toBeInTheDocument();
      });
    });
  });

  describe('validation', () => {
    it('validates threshold_stdev range (0.5-5.0)', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
      });

      const sensitivitySlider = screen.getByLabelText(/sensitivity/i);

      // Test below minimum
      fireEvent.change(sensitivitySlider, { target: { value: '0.3' } });
      await waitFor(() => {
        expect(screen.getByText(/must be at least 0.5/i)).toBeInTheDocument();
      });

      // Test above maximum
      fireEvent.change(sensitivitySlider, { target: { value: '6.0' } });
      await waitFor(() => {
        expect(screen.getByText(/must be at most 5.0/i)).toBeInTheDocument();
      });
    });

    it('validates min_samples minimum (1)', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/minimum samples/i)).toBeInTheDocument();
      });

      const minSamplesInput = screen.getByLabelText(/minimum samples/i);
      fireEvent.change(minSamplesInput, { target: { value: '0' } });

      await waitFor(() => {
        expect(screen.getByText(/must be at least 1/i)).toBeInTheDocument();
      });
    });

    it('shows validation errors inline', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
      });

      const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
      fireEvent.change(sensitivitySlider, { target: { value: '0.3' } });

      await waitFor(() => {
        const errorMessage = screen.getByText(/must be at least 0.5/i);
        expect(errorMessage).toHaveClass('error'); // Assuming error class for styling
      });
    });
  });

  describe('save functionality', () => {
    it('shows success toast after save', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);
      vi.mocked(gpuConfigApi.updateBaselineConfig).mockResolvedValue({
        ...mockCustomConfig,
        threshold_stdev: 4.0,
      });

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
      });

      const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
      fireEvent.change(sensitivitySlider, { target: { value: '4.0' } });

      const saveButton = screen.getByRole('button', { name: /save/i });
      await userEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/settings saved/i)).toBeInTheDocument();
      });
    });

    it('shows error toast on API failure', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockResolvedValue(mockCustomConfig);
      vi.mocked(gpuConfigApi.updateBaselineConfig).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/sensitivity/i)).toBeInTheDocument();
      });

      const sensitivitySlider = screen.getByLabelText(/sensitivity/i);
      fireEvent.change(sensitivitySlider, { target: { value: '4.0' } });

      const saveButton = screen.getByRole('button', { name: /save/i });
      await userEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to save/i)).toBeInTheDocument();
      });
    });
  });

  describe('reset baseline functionality', () => {
    it('shows success message after reset', async () => {
      vi.mocked(gpuConfigApi.resetCameraBaseline).mockResolvedValue({
        activity_baselines_deleted: 168,
        class_baselines_deleted: 42,
      });

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reset baseline/i })).toBeInTheDocument();
      });

      const resetButton = screen.getByRole('button', { name: /reset baseline/i });
      await userEvent.click(resetButton);

      // Confirm in modal
      await waitFor(() => {
        expect(screen.getByText(/confirm reset/i)).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText(/baseline reset successfully/i)).toBeInTheDocument();
        expect(screen.getByText(/168.*activity baselines deleted/i)).toBeInTheDocument();
        expect(screen.getByText(/42.*class baselines deleted/i)).toBeInTheDocument();
      });
    });

    it('shows error message on reset failure', async () => {
      vi.mocked(gpuConfigApi.resetCameraBaseline).mockRejectedValue(new Error('Server error'));

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reset baseline/i })).toBeInTheDocument();
      });

      const resetButton = screen.getByRole('button', { name: /reset baseline/i });
      await userEvent.click(resetButton);

      // Confirm in modal
      await waitFor(() => {
        expect(screen.getByText(/confirm reset/i)).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to reset baseline/i)).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('renders loading state initially', () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockImplementation(() => new Promise(() => {}));

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('displays error message when API fails', async () => {
      vi.mocked(gpuConfigApi.fetchBaselineConfig).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(
        () => {
          expect(screen.getByText(/error loading baseline config/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('testid attributes', () => {
    it('has testid for main container', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('baseline-tuning-panel')).toBeInTheDocument();
      });
    });

    it('has testid for sensitivity slider', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('sensitivity-slider')).toBeInTheDocument();
      });
    });

    it('has testid for min samples input', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('min-samples-input')).toBeInTheDocument();
      });
    });

    it('has testid for reset button', async () => {
      renderWithProviders(<BaselineTuningPanel cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('reset-baseline-button')).toBeInTheDocument();
      });
    });
  });
});
