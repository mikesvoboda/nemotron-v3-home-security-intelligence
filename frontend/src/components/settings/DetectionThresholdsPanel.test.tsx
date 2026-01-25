import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DetectionThresholdsPanel from './DetectionThresholdsPanel';

import type { SettingsResponse } from '../../hooks/useSettingsApi';

// Create mock functions that we can control
const mockUseSettingsQuery = vi.fn();
const mockUseUpdateSettings = vi.fn();
const mockMutateAsync = vi.fn();
const mockResetMutation = vi.fn();

// Mock the useSettingsApi module
vi.mock('../../hooks/useSettingsApi', () => ({
  useSettingsQuery: () => mockUseSettingsQuery(),
  useUpdateSettings: () => mockUseUpdateSettings(),
}));

describe('DetectionThresholdsPanel', () => {
  const mockSettings: SettingsResponse = {
    detection: {
      confidence_threshold: 0.5,
      fast_path_threshold: 0.8,
    },
    batch: {
      window_seconds: 90,
      idle_timeout_seconds: 30,
    },
    severity: {
      low_max: 29,
      medium_max: 59,
      high_max: 84,
    },
    features: {
      vision_extraction_enabled: true,
      reid_enabled: true,
      scene_change_enabled: true,
      clip_generation_enabled: true,
      image_quality_enabled: true,
      background_eval_enabled: true,
    },
    rate_limiting: {
      enabled: true,
      requests_per_minute: 60,
      burst_size: 10,
    },
    queue: {
      max_size: 1000,
      backpressure_threshold: 0.8,
    },
    retention: {
      days: 30,
      log_days: 7,
    },
  };

  const createQueryClient = () =>
    new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

  const renderWithQueryClient = (ui: React.ReactElement) => {
    const queryClient = createQueryClient();
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementation
    mockUseSettingsQuery.mockReturnValue({
      settings: mockSettings,
      isLoading: false,
      isFetching: false,
      error: null,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    });

    mockUseUpdateSettings.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: mockMutateAsync,
      isPending: false,
      isSuccess: false,
      isError: false,
      error: null,
      data: undefined,
      reset: mockResetMutation,
    });
  });

  it('renders component with title', async () => {
    renderWithQueryClient(<DetectionThresholdsPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Thresholds')).toBeInTheDocument();
    });
  });

  it('renders description text', async () => {
    renderWithQueryClient(<DetectionThresholdsPanel />);

    await waitFor(() => {
      expect(
        screen.getByText('Configure AI detection sensitivity and confidence thresholds')
      ).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while fetching settings', () => {
    mockUseSettingsQuery.mockReturnValue({
      settings: undefined,
      isLoading: true,
      isFetching: true,
      error: null,
      isError: false,
      isSuccess: false,
      refetch: vi.fn(),
    });

    renderWithQueryClient(<DetectionThresholdsPanel />);

    // Check for skeleton loading elements
    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('displays both threshold sliders after loading', async () => {
    renderWithQueryClient(<DetectionThresholdsPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
    });

    expect(screen.getByTestId('fast-path-slider')).toBeInTheDocument();
  });

  it('displays correct threshold values as percentages', async () => {
    renderWithQueryClient(<DetectionThresholdsPanel />);

    // Wait for values to be rendered with correct content
    await waitFor(() => {
      expect(screen.getByTestId('confidence-value')).toHaveTextContent('50%');
      expect(screen.getByTestId('fast-path-value')).toHaveTextContent('80%');
    });
  });

  it('displays error message when fetch fails', async () => {
    mockUseSettingsQuery.mockReturnValue({
      settings: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('Network error'),
      isError: true,
      isSuccess: false,
      refetch: vi.fn(),
    });

    renderWithQueryClient(<DetectionThresholdsPanel />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('applies custom className', async () => {
    renderWithQueryClient(<DetectionThresholdsPanel className="custom-test-class" />);

    await waitFor(() => {
      expect(screen.getByText('Detection Thresholds')).toBeInTheDocument();
    });

    const card = screen.getByTestId('detection-thresholds-card');
    expect(card).toHaveClass('custom-test-class');
  });

  describe('slider interactions', () => {
    it('updates confidence value when slider changes', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.75' } });

      await waitFor(() => {
        expect(screen.getByTestId('confidence-value')).toHaveTextContent('75%');
      });
    });

    it('updates fast path value when slider changes', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('fast-path-slider')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('fast-path-slider');
      fireEvent.change(slider, { target: { value: '0.9' } });

      await waitFor(() => {
        expect(screen.getByTestId('fast-path-value')).toHaveTextContent('90%');
      });
    });
  });

  describe('save functionality', () => {
    it('save button is disabled when no changes', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('save-thresholds-button')).toBeInTheDocument();
      });

      const saveButton = screen.getByTestId('save-thresholds-button');
      expect(saveButton).toBeDisabled();
    });

    it('save button is enabled when thresholds are modified', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      // Change threshold value
      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.6' } });

      const saveButton = screen.getByTestId('save-thresholds-button');
      expect(saveButton).not.toBeDisabled();
    });

    it('calls updateSettings on save', async () => {
      mockMutateAsync.mockResolvedValue(mockSettings);

      const user = userEvent.setup();
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      // Change threshold value
      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.6' } });

      // Click save
      const saveButton = screen.getByTestId('save-thresholds-button');
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockMutateAsync).toHaveBeenCalledWith({
          detection: {
            confidence_threshold: 0.6,
            fast_path_threshold: 0.8,
          },
        });
      });
    });

    it('shows success message after save', async () => {
      mockMutateAsync.mockResolvedValue(mockSettings);

      const user = userEvent.setup();
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      // Change and save
      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.6' } });

      const saveButton = screen.getByTestId('save-thresholds-button');
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Detection thresholds saved successfully!')).toBeInTheDocument();
      });
    });

    it('shows error message on save failure', async () => {
      mockUseUpdateSettings.mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: mockMutateAsync,
        isPending: false,
        isSuccess: false,
        isError: true,
        error: new Error('Save failed'),
        data: undefined,
        reset: mockResetMutation,
      });

      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Save failed')).toBeInTheDocument();
      });
    });

    it('shows saving state while mutation is pending', async () => {
      mockUseUpdateSettings.mockReturnValue({
        mutate: vi.fn(),
        mutateAsync: mockMutateAsync,
        isPending: true,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: mockResetMutation,
      });

      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Saving...')).toBeInTheDocument();
      });

      const saveButton = screen.getByTestId('save-thresholds-button');
      expect(saveButton).toBeDisabled();
    });
  });

  describe('reset functionality', () => {
    it('reset button is disabled when no changes', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('reset-thresholds-button')).toBeInTheDocument();
      });

      const resetButton = screen.getByTestId('reset-thresholds-button');
      expect(resetButton).toBeDisabled();
    });

    it('reset button is enabled when values change', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.6' } });

      const resetButton = screen.getByTestId('reset-thresholds-button');
      expect(resetButton).not.toBeDisabled();
    });

    it('resets values when reset button is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      // Change value
      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.6' } });

      await waitFor(() => {
        expect(screen.getByTestId('confidence-value')).toHaveTextContent('60%');
      });

      // Click reset
      const resetButton = screen.getByTestId('reset-thresholds-button');
      await user.click(resetButton);

      // Value should be reset to original
      await waitFor(() => {
        expect(screen.getByTestId('confidence-value')).toHaveTextContent('50%');
      });
      expect((slider as HTMLInputElement).value).toBe('0.5');
    });

    it('calls resetMutation when reset is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      // Change value
      const slider = screen.getByTestId('confidence-slider');
      fireEvent.change(slider, { target: { value: '0.6' } });

      // Click reset
      const resetButton = screen.getByTestId('reset-thresholds-button');
      await user.click(resetButton);

      expect(mockResetMutation).toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has proper aria-labels on sliders', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(
          screen.getByLabelText('Minimum detection confidence threshold')
        ).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Fast path confidence threshold')).toBeInTheDocument();
    });

    it('sliders have correct type', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        const confidenceSlider = screen.getByTestId('confidence-slider');
        expect(confidenceSlider).toHaveAttribute('type', 'range');
      });

      const fastPathSlider = screen.getByTestId('fast-path-slider');
      expect(fastPathSlider).toHaveAttribute('type', 'range');
    });
  });

  describe('threshold descriptions', () => {
    it('displays description for minimum confidence', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(
          screen.getByText(/Detections below this confidence level will be ignored/i)
        ).toBeInTheDocument();
      });
    });

    it('displays description for fast path threshold', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(
          screen.getByText(/High-confidence detections above this threshold are fast-tracked/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('edge cases', () => {
    it('handles zero values correctly', async () => {
      mockUseSettingsQuery.mockReturnValue({
        settings: {
          ...mockSettings,
          detection: {
            confidence_threshold: 0,
            fast_path_threshold: 0,
          },
        },
        isLoading: false,
        isFetching: false,
        error: null,
        isError: false,
        isSuccess: true,
        refetch: vi.fn(),
      });

      renderWithQueryClient(<DetectionThresholdsPanel />);

      // Wait for values to be rendered with correct content
      await waitFor(() => {
        expect(screen.getByTestId('confidence-value')).toHaveTextContent('0%');
        expect(screen.getByTestId('fast-path-value')).toHaveTextContent('0%');
      });
    });

    it('handles maximum values correctly', async () => {
      mockUseSettingsQuery.mockReturnValue({
        settings: {
          ...mockSettings,
          detection: {
            confidence_threshold: 1,
            fast_path_threshold: 1,
          },
        },
        isLoading: false,
        isFetching: false,
        error: null,
        isError: false,
        isSuccess: true,
        refetch: vi.fn(),
      });

      renderWithQueryClient(<DetectionThresholdsPanel />);

      // Wait for values to be rendered with correct content
      await waitFor(() => {
        expect(screen.getByTestId('confidence-value')).toHaveTextContent('100%');
        expect(screen.getByTestId('fast-path-value')).toHaveTextContent('100%');
      });
    });

    it('handles null settings gracefully', () => {
      mockUseSettingsQuery.mockReturnValue({
        settings: undefined,
        isLoading: false,
        isFetching: false,
        error: null,
        isError: false,
        isSuccess: false,
        refetch: vi.fn(),
      });

      renderWithQueryClient(<DetectionThresholdsPanel />);

      // Should render without crashing
      expect(screen.getByText('Detection Thresholds')).toBeInTheDocument();
      // Sliders should not be present
      expect(screen.queryByTestId('confidence-slider')).not.toBeInTheDocument();
    });
  });

  describe('slider configuration', () => {
    it('sliders have correct min, max, and step values', async () => {
      renderWithQueryClient(<DetectionThresholdsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
      });

      const confidenceSlider = screen.getByTestId('confidence-slider');
      expect(confidenceSlider).toHaveAttribute('min', '0');
      expect(confidenceSlider).toHaveAttribute('max', '1');
      expect(confidenceSlider).toHaveAttribute('step', '0.05');

      const fastPathSlider = screen.getByTestId('fast-path-slider');
      expect(fastPathSlider).toHaveAttribute('min', '0');
      expect(fastPathSlider).toHaveAttribute('max', '1');
      expect(fastPathSlider).toHaveAttribute('step', '0.05');
    });
  });
});
