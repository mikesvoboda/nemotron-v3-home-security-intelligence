import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ProcessingSettings from './ProcessingSettings';
import * as api from '../../services/api';
import { renderWithProviders } from '../../test-utils';

// Mock the API module
vi.mock('../../services/api');

// Mock the hooks used by child components (StorageDashboard, CleanupPreviewPanel)
vi.mock('../../hooks/useStorageStatsQuery', () => ({
  useStorageStatsQuery: () => ({
    data: null,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useCleanupPreviewMutation: () => ({
    preview: vi.fn(),
    previewData: null,
    isPending: false,
    error: null,
    reset: vi.fn(),
  }),
}));

vi.mock('../../hooks', async () => {
  const actual = await vi.importActual('../../hooks');
  return {
    ...actual,
    useCleanupPreviewMutation: () => ({
      preview: vi.fn(),
      previewData: null,
      isPending: false,
      error: null,
      reset: vi.fn(),
      mutation: {},
    }),
    useCleanupMutation: () => ({
      cleanup: vi.fn(),
      cleanupData: null,
      isPending: false,
      error: null,
      reset: vi.fn(),
      mutation: {},
    }),
    useSeverityThresholdsQuery: () => ({
      data: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }),
  };
});

describe('ProcessingSettings', () => {
  const mockConfig: api.SystemConfig = {
    app_name: 'Home Security Intelligence',
    version: '0.1.0',
    retention_days: 30,
    log_retention_days: 7,
    batch_window_seconds: 90,
    batch_idle_timeout_seconds: 30,
    detection_confidence_threshold: 0.5,
    fast_path_confidence_threshold: 0.9,
    grafana_url: 'http://localhost:3002',
    debug: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // Always mock updateConfig to prevent errors
    vi.mocked(api.updateConfig).mockResolvedValue(mockConfig);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders component with title', () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    expect(screen.getByText('Processing Settings')).toBeInTheDocument();
  });

  it('shows loading skeleton while fetching config', () => {
    vi.mocked(api.fetchConfig).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderWithProviders(<ProcessingSettings />);

    // Check for skeleton loading elements
    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('displays all configuration fields after loading', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    expect(screen.getByText('Idle Timeout')).toBeInTheDocument();
    expect(screen.getByText('Event Retention Period')).toBeInTheDocument();
    expect(screen.getByText('Log Retention Period')).toBeInTheDocument();
    expect(screen.getByText('Detection Confidence Threshold')).toBeInTheDocument();
    expect(screen.getByText('Fast-Path Confidence Threshold')).toBeInTheDocument();
  });

  it('displays correct configuration values', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
      expect(batchWindowInput).toHaveValue('90');
    });

    const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
    expect(idleTimeoutInput).toHaveValue('30');

    const retentionInput = screen.getByLabelText('Retention period in days');
    expect(retentionInput).toHaveValue('30');

    const confidenceInput = screen.getByLabelText('Detection confidence threshold');
    expect(confidenceInput).toHaveValue('0.5');
  });

  it('displays confidence threshold with correct formatting', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('0.50')).toBeInTheDocument();
    });
  });

  it('displays application name and version', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Home Security Intelligence')).toBeInTheDocument();
    });

    expect(screen.getByText('0.1.0')).toBeInTheDocument();
  });

  // TODO: This test is now covered by StorageDashboard's own tests
  // StorageDashboard uses useStorageStatsQuery hook which is mocked at file level
  // Skip to avoid flaky behavior from competing API mocks vs hook mocks
  it.skip('displays storage usage indicator', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    // Mock storage stats for StorageDashboard component
    vi.mocked(api.fetchStorageStats).mockResolvedValue({
      disk_used_bytes: 107374182400,
      disk_total_bytes: 536870912000,
      disk_free_bytes: 429496729600,
      disk_usage_percent: 20.0,
      thumbnails: { file_count: 1500, size_bytes: 75000000 },
      images: { file_count: 10000, size_bytes: 5000000000 },
      clips: { file_count: 50, size_bytes: 500000000 },
      events_count: 156,
      detections_count: 892,
      gpu_stats_count: 2880,
      logs_count: 5000,
      timestamp: '2025-12-30T10:30:00Z',
    });

    renderWithProviders(<ProcessingSettings />);

    // StorageDashboard shows "Disk Usage" instead of "Storage"
    await waitFor(() => {
      expect(screen.getByText('Disk Usage')).toBeInTheDocument();
    });
  });

  it('displays Clear Old Data button', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Clear Old Data')).toBeInTheDocument();
    });
  });

  it('all sliders are enabled and functional', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
      expect(batchWindowInput).not.toBeDisabled();
    });

    const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
    expect(idleTimeoutInput).not.toBeDisabled();

    const retentionInput = screen.getByLabelText('Retention period in days');
    expect(retentionInput).not.toBeDisabled();

    const confidenceInput = screen.getByLabelText('Detection confidence threshold');
    expect(confidenceInput).not.toBeDisabled();
  });

  it('Save button is disabled when no changes', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      const saveButton = screen.getByText('Save Changes').closest('button');
      expect(saveButton).toBeDisabled();
    });
  });

  it('Save button is enabled when values change', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
    fireEvent.input(batchWindowInput, { target: { value: '120' } });

    const saveButton = screen.getByText('Save Changes').closest('button');
    expect(saveButton).not.toBeDisabled();
  });

  it('Reset button restores original values', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
    fireEvent.input(batchWindowInput, { target: { value: '120' } });

    expect(batchWindowInput).toHaveValue('120');

    const resetButton = screen.getByText('Reset');
    fireEvent.click(resetButton);

    expect(batchWindowInput).toHaveValue('90');
  });

  it('saves configuration changes successfully', async () => {
    const updatedConfig = { ...mockConfig, batch_window_seconds: 120 };
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.updateConfig).mockResolvedValue(updatedConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
    fireEvent.input(batchWindowInput, { target: { value: '120' } });

    const saveButton = screen.getByText('Save Changes').closest('button');
    fireEvent.click(saveButton!);

    await waitFor(() => {
      expect(api.updateConfig).toHaveBeenCalledWith({
        batch_window_seconds: 120,
        batch_idle_timeout_seconds: 30,
        retention_days: 30,
        log_retention_days: 7,
        detection_confidence_threshold: 0.5,
        fast_path_confidence_threshold: 0.9,
      });
    });

    await waitFor(() => {
      expect(screen.getByText('Settings saved successfully!')).toBeInTheDocument();
    });
  });

  it('clears success message after 3 seconds', async () => {
    const updatedConfig = { ...mockConfig, batch_window_seconds: 120 };
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.updateConfig).mockResolvedValue(updatedConfig);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
    fireEvent.input(batchWindowInput, { target: { value: '120' } });

    const saveButton = screen.getByText('Save Changes').closest('button');
    fireEvent.click(saveButton!);

    await waitFor(() => {
      expect(screen.getByText('Settings saved successfully!')).toBeInTheDocument();
    });

    // Advance time by 3 seconds to clear the success message
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.queryByText('Settings saved successfully!')).not.toBeInTheDocument();
  });

  it('displays error message when save fails', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.updateConfig).mockRejectedValue(new Error('Network error'));

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
    fireEvent.input(batchWindowInput, { target: { value: '120' } });

    const saveButton = screen.getByText('Save Changes').closest('button');
    fireEvent.click(saveButton!);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('disables buttons while saving', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.updateConfig).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
    fireEvent.input(batchWindowInput, { target: { value: '120' } });

    const saveButton = screen.getByText('Save Changes').closest('button');
    fireEvent.click(saveButton!);

    await waitFor(() => {
      expect(screen.getByText('Saving...')).toBeInTheDocument();
    });

    expect(screen.getByText('Saving...').closest('button')).toBeDisabled();
    expect(screen.getByText('Reset').closest('button')).toBeDisabled();
  });

  it('Clear Old Data button triggers cleanup API', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.triggerCleanup).mockResolvedValue({
      events_deleted: 10,
      detections_deleted: 50,
      gpu_stats_deleted: 100,
      logs_deleted: 25,
      thumbnails_deleted: 50,
      images_deleted: 0,
      space_reclaimed: 1024000,
      retention_days: 30,
      dry_run: false,
      timestamp: '2025-12-27T10:30:00Z',
    });

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Clear Old Data')).toBeInTheDocument();
    });

    const clearButton = screen.getByText('Clear Old Data').closest('button');
    fireEvent.click(clearButton!);

    // Wait for cleanup to complete and results to display
    await waitFor(() => {
      expect(api.triggerCleanup).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText('Cleanup Complete')).toBeInTheDocument();
    });

    // Check that results are displayed
    expect(screen.getByText('Events deleted:')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('Clear Old Data button shows loading state', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    // Create a promise that won't resolve immediately
    let resolveCleanup: (value: api.CleanupResponse) => void;
    const cleanupPromise = new Promise<api.CleanupResponse>((resolve) => {
      resolveCleanup = resolve;
    });
    vi.mocked(api.triggerCleanup).mockReturnValue(cleanupPromise);

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Clear Old Data')).toBeInTheDocument();
    });

    const clearButton = screen.getByText('Clear Old Data').closest('button');
    fireEvent.click(clearButton!);

    // Should show loading state
    await waitFor(() => {
      expect(screen.getByText('Running Cleanup...')).toBeInTheDocument();
    });

    // The button should be disabled during cleanup
    expect(screen.getByText('Running Cleanup...').closest('button')).toBeDisabled();

    // Resolve the cleanup
    resolveCleanup!({
      events_deleted: 0,
      detections_deleted: 0,
      gpu_stats_deleted: 0,
      logs_deleted: 0,
      thumbnails_deleted: 0,
      images_deleted: 0,
      space_reclaimed: 0,
      retention_days: 30,
      dry_run: false,
      timestamp: '2025-12-27T10:30:00Z',
    });

    await waitFor(() => {
      expect(screen.queryByText('Running Cleanup...')).not.toBeInTheDocument();
    });
  });

  it('Clear Old Data button handles errors', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.triggerCleanup).mockRejectedValue(new Error('Cleanup failed'));

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Clear Old Data')).toBeInTheDocument();
    });

    const clearButton = screen.getByText('Clear Old Data').closest('button');
    fireEvent.click(clearButton!);

    await waitFor(() => {
      expect(screen.getByText('Cleanup failed')).toBeInTheDocument();
    });
  });

  it('Clear Old Data button handles non-Error objects', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.triggerCleanup).mockRejectedValue('Unknown error');

    renderWithProviders(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Clear Old Data')).toBeInTheDocument();
    });

    const clearButton = screen.getByText('Clear Old Data').closest('button');
    fireEvent.click(clearButton!);

    await waitFor(() => {
      expect(screen.getByText('Failed to run cleanup')).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('displays error message when fetch fails', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('displays generic error for non-Error objects', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue('Unknown error');

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load configuration')).toBeInTheDocument();
      });
    });

    it('shows error icon when error occurs', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Check for AlertCircle icon (it will be in the DOM as an svg)
      const errorContainer = screen.getByText('Network error').closest('div');
      expect(errorContainer).toBeInTheDocument();
    });

    it('does not show config fields when error occurs', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      expect(screen.queryByText('Batch Window Duration')).not.toBeInTheDocument();
    });
  });

  describe('field descriptions', () => {
    it('shows description for batch window duration', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Time window for grouping detections into events/i)
        ).toBeInTheDocument();
      });
    });

    it('shows description for idle timeout', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Time to wait before processing incomplete batch/i)
        ).toBeInTheDocument();
      });
    });

    it('shows description for retention period', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Number of days to retain events and detections/i)
        ).toBeInTheDocument();
      });
    });

    it('shows description for confidence threshold', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText(/Minimum confidence for object detection/i)).toBeInTheDocument();
      });
    });

    it('shows description for fast-path confidence threshold', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/High-confidence threshold for immediate processing/i)
        ).toBeInTheDocument();
      });
    });

    it('shows description for log retention period', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText(/Number of days to retain application logs/i)).toBeInTheDocument();
      });
    });
  });

  describe('edge cases', () => {
    it('handles zero values correctly', async () => {
      const zeroConfig: api.SystemConfig = {
        ...mockConfig,
        batch_window_seconds: 30, // Min value instead of 0
        batch_idle_timeout_seconds: 10, // Min value instead of 0
        retention_days: 1, // Min value instead of 0
        detection_confidence_threshold: 0,
      };

      vi.mocked(api.fetchConfig).mockResolvedValue(zeroConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        const confidenceInput = screen.getByLabelText('Detection confidence threshold');
        expect(confidenceInput).toHaveValue('0');
      });
    });

    it('handles maximum values correctly', async () => {
      const maxConfig: api.SystemConfig = {
        ...mockConfig,
        batch_window_seconds: 300,
        batch_idle_timeout_seconds: 120,
        retention_days: 90,
        detection_confidence_threshold: 1.0,
      };

      vi.mocked(api.fetchConfig).mockResolvedValue(maxConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
        expect(batchWindowInput).toHaveValue('300');
      });

      const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
      expect(idleTimeoutInput).toHaveValue('120');

      const retentionInput = screen.getByLabelText('Retention period in days');
      expect(retentionInput).toHaveValue('90');

      const confidenceInput = screen.getByLabelText('Detection confidence threshold');
      expect(confidenceInput).toHaveValue('1');
    });

    it('applies custom className', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings className="custom-test-class" />);

      await waitFor(() => {
        expect(screen.getByText('Processing Settings')).toBeInTheDocument();
      });

      // The Card component should have the custom class
      const card = screen.getByText('Processing Settings').closest('.custom-test-class');
      expect(card).toBeInTheDocument();
    });
  });

  describe('input types', () => {
    it('uses range input type for all slider fields', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
        expect(batchWindowInput).toHaveAttribute('type', 'range');
      });

      const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
      expect(idleTimeoutInput).toHaveAttribute('type', 'range');

      const retentionInput = screen.getByLabelText('Retention period in days');
      expect(retentionInput).toHaveAttribute('type', 'range');

      const logRetentionInput = screen.getByLabelText('Log retention period in days');
      expect(logRetentionInput).toHaveAttribute('type', 'range');

      const confidenceInput = screen.getByLabelText('Detection confidence threshold');
      expect(confidenceInput).toHaveAttribute('type', 'range');

      const fastPathInput = screen.getByLabelText('Fast-path confidence threshold');
      expect(fastPathInput).toHaveAttribute('type', 'range');
    });
  });

  describe('accessibility', () => {
    it('includes proper aria-labels for all inputs', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByLabelText('Batch window duration in seconds')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Batch idle timeout in seconds')).toBeInTheDocument();
      expect(screen.getByLabelText('Retention period in days')).toBeInTheDocument();
      expect(screen.getByLabelText('Log retention period in days')).toBeInTheDocument();
      expect(screen.getByLabelText('Detection confidence threshold')).toBeInTheDocument();
      expect(screen.getByLabelText('Fast-path confidence threshold')).toBeInTheDocument();
      // StorageDashboard component handles storage display without an aria-label for percentage
    });

    it('uses semantic text labels', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
      });

      // Check that field labels are present
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
      expect(screen.getByText('Idle Timeout')).toBeInTheDocument();
      expect(screen.getByText('Event Retention Period')).toBeInTheDocument();
      expect(screen.getByText('Log Retention Period')).toBeInTheDocument();
      expect(screen.getByText('Detection Confidence Threshold')).toBeInTheDocument();
      expect(screen.getByText('Fast-Path Confidence Threshold')).toBeInTheDocument();
    });
  });

  describe('slider value changes', () => {
    it('updates batch window value when slider moves', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('90s')).toBeInTheDocument();
      });

      const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
      fireEvent.input(batchWindowInput, { target: { value: '150' } });

      expect(screen.getByText('150s')).toBeInTheDocument();
    });

    it('updates confidence threshold with decimal precision', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('0.50')).toBeInTheDocument();
      });

      const confidenceInput = screen.getByLabelText('Detection confidence threshold');
      fireEvent.input(confidenceInput, { target: { value: '0.75' } });

      expect(screen.getByText('0.75')).toBeInTheDocument();
    });

    it('updates fast-path threshold with decimal precision', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('0.90')).toBeInTheDocument();
      });

      const fastPathInput = screen.getByLabelText('Fast-path confidence threshold');
      fireEvent.input(fastPathInput, { target: { value: '0.85' } });

      expect(screen.getByText('0.85')).toBeInTheDocument();
    });

    it('updates log retention value when slider moves', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      renderWithProviders(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('7 days')).toBeInTheDocument();
      });

      const logRetentionInput = screen.getByLabelText('Log retention period in days');
      fireEvent.input(logRetentionInput, { target: { value: '14' } });

      expect(screen.getByText('14 days')).toBeInTheDocument();
    });
  });

  describe('SeverityThresholds integration', () => {
    it('renders SeverityThresholds component within ProcessingSettings', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);
      // Mock the severity config API
      const mockSeverityConfig: api.SeverityMetadataResponse = {
        definitions: [
          {
            severity: 'low',
            label: 'Low',
            description: 'Routine activity',
            color: '#22c55e',
            priority: 3,
            min_score: 0,
            max_score: 29,
          },
          {
            severity: 'medium',
            label: 'Medium',
            description: 'Elevated attention needed',
            color: '#eab308',
            priority: 2,
            min_score: 30,
            max_score: 59,
          },
          {
            severity: 'high',
            label: 'High',
            description: 'Significant concern',
            color: '#f97316',
            priority: 1,
            min_score: 60,
            max_score: 84,
          },
          {
            severity: 'critical',
            label: 'Critical',
            description: 'Immediate attention required',
            color: '#ef4444',
            priority: 0,
            min_score: 85,
            max_score: 100,
          },
        ],
        thresholds: {
          low_max: 29,
          medium_max: 59,
          high_max: 84,
        },
      };
      vi.mocked(api.fetchSeverityConfig).mockResolvedValue(mockSeverityConfig);

      renderWithProviders(<ProcessingSettings />);

      // SeverityThresholds component should be visible
      await waitFor(() => {
        expect(screen.getByText('Risk Score Thresholds')).toBeInTheDocument();
      });

      // Verify the severity thresholds card is rendered with correct test id
      expect(screen.getByTestId('severity-thresholds-card')).toBeInTheDocument();
    });
  });
});
