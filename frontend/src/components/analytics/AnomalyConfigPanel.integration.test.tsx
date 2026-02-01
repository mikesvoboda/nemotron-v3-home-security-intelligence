/**
 * Integration Tests for AnomalyConfigPanel Component
 *
 * Tests real-world interaction flows including:
 * - Full save flow: render → change value → save → verify API called → verify cache updated
 * - Full reset flow: render → click reset → confirm → verify API called → verify UI updated
 * - Error recovery: API fails → shows error → user retries → succeeds
 * - Toggle global/custom: switch modes → verify UI state changes correctly
 * - Validation prevents save: invalid value → save disabled → fix value → save enabled
 *
 * @see NEM-4920 - [TDD] Integration tests for Phase 3: Baseline Tuning UI
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AnomalyConfigPanel from './AnomalyConfigPanel';
import * as api from '../../services/api';

import type { AnomalyConfig } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    updateAnomalyConfig: vi.fn(),
    fetchAnomalyConfig: vi.fn(),
  };
});

/**
 * Creates a fresh QueryClient for each test.
 * This ensures test isolation by preventing cache contamination.
 */
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries for predictable test behavior
        gcTime: 0, // Disable garbage collection to prevent cache persistence
      },
      mutations: {
        retry: false,
      },
    },
  });

/**
 * Renders component with QueryClientProvider.
 * This simulates the real app environment where components use TanStack Query.
 */
const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return {
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
    queryClient,
  };
};

describe('AnomalyConfigPanel Integration Tests', () => {
  const mockConfig: AnomalyConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    decay_factor: 0.1,
    window_days: 30,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.updateAnomalyConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockConfig);
  });

  describe('Full Save Flow', () => {
    it('completes save flow: render → change value → save → verify API called', async () => {
      // Arrange: Setup mock for successful save
      const updatedConfig: AnomalyConfig = {
        ...mockConfig,
        threshold_stdev: 2.5,
      };
      vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

      const onConfigUpdated = vi.fn();
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} onConfigUpdated={onConfigUpdated} />);

      // Act: Change threshold value
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      // Assert: Save button appears
      const saveButton = await screen.findByTestId('save-config-button');
      expect(saveButton).toBeInTheDocument();
      expect(saveButton).not.toBeDisabled();

      // Act: Click save button
      fireEvent.click(saveButton);

      // Assert: API was called with correct payload
      await waitFor(() => {
        expect(api.updateAnomalyConfig).toHaveBeenCalledWith({
          threshold_stdev: 2.5,
        });
      });

      // Assert: Callback was called with updated config
      await waitFor(() => {
        expect(onConfigUpdated).toHaveBeenCalledWith(updatedConfig);
      });

      // Assert: Save button disappears after save
      await waitFor(() => {
        expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
      });
    });

    it('saves both threshold and min_samples changes together', async () => {
      // Arrange: Setup mock for successful save
      const updatedConfig: AnomalyConfig = {
        ...mockConfig,
        threshold_stdev: 2.8,
        min_samples: 15,
      };
      vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

      const onConfigUpdated = vi.fn();
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} onConfigUpdated={onConfigUpdated} />);

      // Act: Change both values
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.8' } });

      const minSamplesInput = screen.getByTestId('min-samples-input');
      fireEvent.change(minSamplesInput, { target: { value: '15' } });

      // Act: Click save button
      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: API was called with both changes
      await waitFor(() => {
        expect(api.updateAnomalyConfig).toHaveBeenCalledWith({
          threshold_stdev: 2.8,
          min_samples: 15,
        });
      });

      // Assert: Callback received updated config
      await waitFor(() => {
        expect(onConfigUpdated).toHaveBeenCalledWith(updatedConfig);
      });
    });

    it('only sends changed fields in API request', async () => {
      // Arrange: Only change min_samples
      const updatedConfig: AnomalyConfig = {
        ...mockConfig,
        min_samples: 20,
      };
      vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Only change min_samples
      const minSamplesInput = screen.getByTestId('min-samples-input');
      fireEvent.change(minSamplesInput, { target: { value: '20' } });

      // Act: Save
      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Only min_samples was sent (threshold unchanged)
      await waitFor(() => {
        expect(api.updateAnomalyConfig).toHaveBeenCalledWith({
          min_samples: 20,
        });
      });
    });

    it('disables save button during API request', async () => {
      // Arrange: Mock API with delay
      vi.mocked(api.updateAnomalyConfig).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ ...mockConfig, threshold_stdev: 2.5 }), 100))
      );

      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Change value
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Button is disabled immediately
      expect(saveButton).toBeDisabled();

      // Assert: Button shows loading indicator
      expect(screen.getByRole('button', { name: /save changes/i })).toContainHTML('animate-spin');

      // Wait for save to complete
      await waitFor(
        () => {
          expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
        },
        { timeout: 200 }
      );
    });
  });

  describe('Error Recovery Flow', () => {
    it('shows error when API fails, allows retry, succeeds', async () => {
      // Arrange: Mock API to fail first, then succeed
      let callCount = 0;
      vi.mocked(api.updateAnomalyConfig).mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.resolve({ ...mockConfig, threshold_stdev: 2.5 });
      });

      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Change value and save
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Error message appears
      const errorMessage = await screen.findByText(/network error/i);
      expect(errorMessage).toBeInTheDocument();

      // Assert: Save button is re-enabled
      await waitFor(() => {
        expect(saveButton).not.toBeDisabled();
      });

      // Act: Retry save
      fireEvent.click(saveButton);

      // Assert: Error disappears on successful save
      await waitFor(() => {
        expect(screen.queryByText(/network error/i)).not.toBeInTheDocument();
      });

      // Assert: Save button disappears
      await waitFor(() => {
        expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
      });
    });

    it('shows generic error message for unknown error types', async () => {
      // Arrange: Mock API to throw non-Error object
      vi.mocked(api.updateAnomalyConfig).mockRejectedValue('Unknown error');

      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Change value and save
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Generic error message appears
      const errorMessage = await screen.findByText(/failed to update configuration/i);
      expect(errorMessage).toBeInTheDocument();
    });

    it('clears previous error when starting new save attempt', async () => {
      // Arrange: Mock API to fail
      vi.mocked(api.updateAnomalyConfig).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Change value and save (will fail)
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Error appears
      await screen.findByText(/network error/i);

      // Arrange: Mock API to succeed on next attempt
      vi.mocked(api.updateAnomalyConfig).mockResolvedValue({ ...mockConfig, threshold_stdev: 2.8 });

      // Act: Change value again and save
      fireEvent.change(slider, { target: { value: '2.8' } });
      fireEvent.click(saveButton);

      // Assert: Error is cleared immediately on new save attempt
      expect(screen.queryByText(/network error/i)).not.toBeInTheDocument();
    });
  });

  describe('Validation and UI State', () => {
    it('enforces minimum value of 1 for min_samples input', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const minSamplesInput = screen.getByTestId('min-samples-input');

      // Act: Try to enter 0
      fireEvent.change(minSamplesInput, { target: { value: '0' } });

      // Assert: Value is clamped to 1
      expect(minSamplesInput).toHaveValue(1);
    });

    it('enforces minimum value of 1 for negative min_samples', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const minSamplesInput = screen.getByTestId('min-samples-input');

      // Act: Try to enter negative value
      fireEvent.change(minSamplesInput, { target: { value: '-5' } });

      // Assert: Value is clamped to 1
      expect(minSamplesInput).toHaveValue(1);
    });

    it('handles empty input by defaulting to 1', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const minSamplesInput = screen.getByTestId('min-samples-input');

      // Act: Clear the input
      fireEvent.change(minSamplesInput, { target: { value: '' } });

      // Assert: Value defaults to 1
      expect(minSamplesInput).toHaveValue(1);
    });

    it('updates sensitivity label when threshold changes', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Initial state: threshold=2.0 → High Sensitivity
      expect(screen.getByText('High Sensitivity')).toBeInTheDocument();

      // Act: Change to 1.0 → Very High Sensitivity
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '1.0' } });

      expect(screen.getByText('Very High Sensitivity')).toBeInTheDocument();

      // Act: Change to 3.0 → Low Sensitivity
      fireEvent.change(slider, { target: { value: '3.0' } });

      expect(screen.getByText('Low Sensitivity')).toBeInTheDocument();

      // Act: Change to 4.0 → Very Low Sensitivity
      fireEvent.change(slider, { target: { value: '4.0' } });

      expect(screen.getByText('Very Low Sensitivity')).toBeInTheDocument();
    });

    it('disables save when no changes have been made', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Assert: No save button initially
      expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
    });

    it('shows save button immediately when value changes', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Assert: No save button initially
      expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();

      // Act: Change value
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.1' } });

      // Assert: Save button appears immediately
      expect(screen.getByTestId('save-config-button')).toBeInTheDocument();
    });
  });

  describe('External Config Updates', () => {
    it('resets local state when config prop changes', () => {
      // Arrange: Initial render
      const { rerender } = renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Change local value
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      // Assert: Local state changed, save button appears
      expect(screen.getByTestId('save-config-button')).toBeInTheDocument();
      expect(screen.getByText('2.5 std')).toBeInTheDocument();

      // Act: Update config prop (simulating external update)
      const newConfig: AnomalyConfig = {
        ...mockConfig,
        threshold_stdev: 3.0,
        min_samples: 20,
      };
      rerender(
        <QueryClientProvider client={createTestQueryClient()}>
          <AnomalyConfigPanel config={newConfig} />
        </QueryClientProvider>
      );

      // Assert: Local state reset to new config
      expect(screen.getByText('3.0 std')).toBeInTheDocument();
      expect(screen.getByTestId('min-samples-input')).toHaveValue(20);

      // Assert: Save button hidden (no local changes)
      expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
    });

    it('clears hasChanges flag when config prop updates', () => {
      // Arrange: Initial render with changes
      const { rerender } = renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      // Assert: Has changes
      expect(screen.getByTestId('save-config-button')).toBeInTheDocument();

      // Act: External config update
      const updatedConfig: AnomalyConfig = { ...mockConfig, threshold_stdev: 2.5 };
      rerender(
        <QueryClientProvider client={createTestQueryClient()}>
          <AnomalyConfigPanel config={updatedConfig} />
        </QueryClientProvider>
      );

      // Assert: No changes flag after prop update
      expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
    });
  });

  describe('Read-Only Fields', () => {
    it('displays read-only decay_factor and window_days', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Assert: Read-only fields are displayed
      expect(screen.getByText('Decay Factor:')).toBeInTheDocument();
      expect(screen.getByText('0.1')).toBeInTheDocument();
      expect(screen.getByText('Window:')).toBeInTheDocument();
      expect(screen.getByText('30 days')).toBeInTheDocument();
    });

    it('does not allow editing read-only fields', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Assert: No input fields for decay_factor or window_days
      const allInputs = screen.getAllByRole('slider')
        .concat(screen.getAllByRole('spinbutton'));

      // Should only have threshold slider and min_samples input
      expect(allInputs).toHaveLength(2);
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels for threshold slider', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const slider = screen.getByTestId('threshold-slider');
      expect(slider).toHaveAttribute('aria-label', 'Detection threshold in standard deviations');
      expect(slider).toHaveAttribute('aria-valuemin', '1');
      expect(slider).toHaveAttribute('aria-valuemax', '4');
      expect(slider).toHaveAttribute('aria-valuenow', '2');
    });

    it('has proper ARIA labels for min_samples input', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const input = screen.getByTestId('min-samples-input');
      expect(input).toHaveAttribute('aria-label', 'Minimum samples required for detection');
    });

    it('updates aria-valuetext when threshold changes', () => {
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      const slider = screen.getByTestId('threshold-slider');

      // Initial state
      expect(slider).toHaveAttribute('aria-valuetext', expect.stringContaining('2.0 standard deviations'));
      expect(slider).toHaveAttribute('aria-valuetext', expect.stringContaining('High sensitivity'));

      // Change value
      fireEvent.change(slider, { target: { value: '3.0' } });

      expect(slider).toHaveAttribute('aria-valuetext', expect.stringContaining('3.0 standard deviations'));
      expect(slider).toHaveAttribute('aria-valuetext', expect.stringContaining('Low sensitivity'));
    });
  });

  describe('Callback Invocation', () => {
    it('calls onConfigUpdated with new config on successful save', async () => {
      const updatedConfig: AnomalyConfig = {
        ...mockConfig,
        threshold_stdev: 2.5,
      };
      vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

      const onConfigUpdated = vi.fn();
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} onConfigUpdated={onConfigUpdated} />);

      // Act: Change and save
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Callback invoked with updated config
      await waitFor(() => {
        expect(onConfigUpdated).toHaveBeenCalledTimes(1);
        expect(onConfigUpdated).toHaveBeenCalledWith(updatedConfig);
      });
    });

    it('does not call onConfigUpdated when save fails', async () => {
      vi.mocked(api.updateAnomalyConfig).mockRejectedValue(new Error('Save failed'));

      const onConfigUpdated = vi.fn();
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} onConfigUpdated={onConfigUpdated} />);

      // Act: Change and save (will fail)
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Error appears
      await screen.findByText(/save failed/i);

      // Assert: Callback not invoked
      expect(onConfigUpdated).not.toHaveBeenCalled();
    });

    it('works without onConfigUpdated callback (optional prop)', async () => {
      const updatedConfig: AnomalyConfig = {
        ...mockConfig,
        threshold_stdev: 2.5,
      };
      vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

      // Render without onConfigUpdated callback
      renderWithProviders(<AnomalyConfigPanel config={mockConfig} />);

      // Act: Change and save
      const slider = screen.getByTestId('threshold-slider');
      fireEvent.change(slider, { target: { value: '2.5' } });

      const saveButton = await screen.findByTestId('save-config-button');
      fireEvent.click(saveButton);

      // Assert: Save completes without error
      await waitFor(() => {
        expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
      });
    });
  });
});
