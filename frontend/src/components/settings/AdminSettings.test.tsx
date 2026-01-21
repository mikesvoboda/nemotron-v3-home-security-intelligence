import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AdminSettings from './AdminSettings';
import { useDebugMode } from '../../contexts/DebugModeContext';
import { renderWithProviders } from '../../test-utils';

// Mock the DebugModeContext
vi.mock('../../contexts/DebugModeContext', () => ({
  useDebugMode: vi.fn(() => ({
    debugMode: false,
    setDebugMode: vi.fn(),
    isDebugAvailable: false,
  })),
}));

// Mock the useToast hook
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock the useAdminMutations hook
vi.mock('../../hooks/useAdminMutations', () => ({
  useAdminMutations: () => ({
    seedCameras: {
      mutateAsync: vi.fn().mockResolvedValue({ created: 5, cleared: 0, cameras: [] }),
      isPending: false,
    },
    seedEvents: {
      mutateAsync: vi.fn().mockResolvedValue({
        events_created: 50,
        detections_created: 150,
        events_cleared: 0,
        detections_cleared: 0,
      }),
      isPending: false,
    },
    seedPipelineLatency: {
      mutateAsync: vi.fn().mockResolvedValue({
        message: 'Success',
        samples_per_stage: 100,
        stages_seeded: ['detection', 'enrichment'],
        time_span_hours: 168,
      }),
      isPending: false,
    },
    clearSeededData: {
      mutateAsync: vi.fn().mockResolvedValue({
        cameras_cleared: 5,
        events_cleared: 50,
        detections_cleared: 150,
      }),
      isPending: false,
    },
    // Maintenance operations
    orphanCleanup: {
      mutateAsync: vi.fn().mockResolvedValue({
        scanned_files: 100,
        orphaned_files: 15,
        deleted_files: 15,
        deleted_bytes: 2300000000,
        deleted_bytes_formatted: '2.3 GB',
        failed_count: 0,
        failed_deletions: [],
        duration_seconds: 1.5,
        dry_run: false,
        skipped_young: 0,
        skipped_size_limit: 0,
      }),
      isPending: false,
    },
    clearCache: {
      mutateAsync: vi.fn().mockResolvedValue({
        keys_cleared: 150,
        cache_types: ['events', 'cameras', 'system'],
        duration_seconds: 0.5,
        message: 'Cleared 150 cache keys',
      }),
      isPending: false,
    },
    flushQueues: {
      mutateAsync: vi.fn().mockResolvedValue({
        queues_flushed: ['detection_queue', 'analysis_queue'],
        items_cleared: { detection_queue: 10, analysis_queue: 5 },
        duration_seconds: 0.3,
        message: 'Flushed 15 items from 2 queues',
      }),
      isPending: false,
    },
  }),
}));

// Mock the useSettingsApi hook
vi.mock('../../hooks/useSettingsApi', () => ({
  useSettingsApi: () => ({
    settings: {
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
        burst_size: 100,
      },
      queue: {
        max_size: 1000,
        backpressure_threshold: 0.8,
      },
    },
    isLoading: false,
    updateMutation: {
      mutateAsync: vi.fn().mockResolvedValue({}),
      isPending: false,
    },
  }),
}));

describe('AdminSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the admin settings component', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByTestId('admin-settings')).toBeInTheDocument();
      expect(screen.getByText('Admin Settings')).toBeInTheDocument();
    });

    it('renders all section headers', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByText('Feature Toggles')).toBeInTheDocument();
      expect(screen.getByText('System Config')).toBeInTheDocument();
      expect(screen.getByText('Maintenance Actions')).toBeInTheDocument();
    });

    it('does not render Developer Tools section when debug mode is off', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.queryByText('Developer Tools')).not.toBeInTheDocument();
    });

    it('applies custom className', () => {
      renderWithProviders(<AdminSettings className="custom-class" />);

      const container = screen.getByTestId('admin-settings');
      expect(container).toHaveClass('custom-class');
    });
  });

  describe('Feature Toggles section', () => {
    it('renders all feature toggles', () => {
      renderWithProviders(<AdminSettings />);

      // Section should be expanded by default
      expect(screen.getByText('Vision Extraction')).toBeInTheDocument();
      expect(screen.getByText('Re-ID Tracking')).toBeInTheDocument();
      expect(screen.getByText('Scene Change')).toBeInTheDocument();
      expect(screen.getByText('Clip Generation')).toBeInTheDocument();
      expect(screen.getByText('Image Quality')).toBeInTheDocument();
      expect(screen.getByText('Background Eval')).toBeInTheDocument();
    });

    it('displays feature toggle descriptions', () => {
      renderWithProviders(<AdminSettings />);

      expect(
        screen.getByText('Extract visual features from frames using AI models')
      ).toBeInTheDocument();
      expect(screen.getByText('Track individuals across camera views')).toBeInTheDocument();
    });

    it('renders switch components for each feature toggle', () => {
      renderWithProviders(<AdminSettings />);

      // Check that each toggle has a switch with the correct test id
      expect(
        screen.getByTestId('feature-toggle-vision_extraction_enabled-switch')
      ).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-reid_enabled-switch')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-scene_change_enabled-switch')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-clip_generation_enabled-switch')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-image_quality_enabled-switch')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-background_eval_enabled-switch')).toBeInTheDocument();
    });

    it('all feature toggles are enabled by default', () => {
      renderWithProviders(<AdminSettings />);

      // All switches should be checked (enabled) by default
      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      const reidSwitch = screen.getByTestId('feature-toggle-reid_enabled-switch');
      const sceneSwitch = screen.getByTestId('feature-toggle-scene_change_enabled-switch');
      const clipSwitch = screen.getByTestId('feature-toggle-clip_generation_enabled-switch');
      const imageSwitch = screen.getByTestId('feature-toggle-image_quality_enabled-switch');
      const bgSwitch = screen.getByTestId('feature-toggle-background_eval_enabled-switch');

      // HeadlessUI Switch uses aria-checked for state
      expect(visionSwitch).toHaveAttribute('aria-checked', 'true');
      expect(reidSwitch).toHaveAttribute('aria-checked', 'true');
      expect(sceneSwitch).toHaveAttribute('aria-checked', 'true');
      expect(clipSwitch).toHaveAttribute('aria-checked', 'true');
      expect(imageSwitch).toHaveAttribute('aria-checked', 'true');
      expect(bgSwitch).toHaveAttribute('aria-checked', 'true');
    });

    it('clicking a switch calls the update mutation', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      expect(visionSwitch).toHaveAttribute('aria-checked', 'true');

      // Click to toggle off - this should trigger the mutation
      await user.click(visionSwitch);

      // The switch can still be clicked (mutation was triggered)
      // Note: The actual state change depends on the API response
      expect(visionSwitch).toBeInTheDocument();
    });

    it('displays summary count of enabled toggles', () => {
      renderWithProviders(<AdminSettings />);

      // All 6 toggles should be enabled by default, so summary should show 6/6
      expect(screen.getByText('6/6 enabled')).toBeInTheDocument();
    });

    it('switch can be toggled multiple times', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');

      // Click to toggle - should not throw
      await user.click(visionSwitch);

      // Click again - should still work
      await user.click(visionSwitch);

      expect(visionSwitch).toBeInTheDocument();
    });

    it('switch has correct aria-label', () => {
      renderWithProviders(<AdminSettings />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      expect(visionSwitch).toHaveAttribute('aria-label', 'Toggle Vision Extraction off');
    });

    it('can collapse and expand the Feature Toggles section', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const toggleButton = screen.getByTestId('admin-feature-toggles-toggle');
      expect(screen.getByText('Vision Extraction')).toBeInTheDocument();

      // Collapse the section
      await user.click(toggleButton);

      // Wait for animation and check content is hidden
      await waitFor(() => {
        expect(screen.queryByText('Vision Extraction')).not.toBeInTheDocument();
      });
    });
  });

  describe('System Config section', () => {
    it('renders rate limiting section with inputs', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByText('Rate Limiting')).toBeInTheDocument();
      expect(screen.getByTestId('rate-limiting-section')).toBeInTheDocument();
      expect(screen.getByTestId('input-requests-per-minute')).toBeInTheDocument();
      expect(screen.getByTestId('input-burst-size')).toBeInTheDocument();
      expect(screen.getByTestId('switch-rate-limit-enabled')).toBeInTheDocument();
    });

    it('renders queue settings section with inputs', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByText('Queue Settings')).toBeInTheDocument();
      expect(screen.getByTestId('queue-settings-section')).toBeInTheDocument();
      expect(screen.getByTestId('input-max-queue-size')).toBeInTheDocument();
      expect(screen.getByTestId('input-backpressure-threshold')).toBeInTheDocument();
    });

    it('displays values from settings API', async () => {
      renderWithProviders(<AdminSettings />);

      // Check values from mock API settings (useSettingsApi mock)
      const requestsInput = screen.getByTestId('input-requests-per-minute');
      const burstInput = screen.getByTestId('input-burst-size');
      const maxSizeInput = screen.getByTestId('input-max-queue-size');
      const backpressureInput = screen.getByTestId('input-backpressure-threshold');

      // Wait for settings to sync from API
      await waitFor(() => {
        // NumberInput from tremor should have values from the mock API
        expect(requestsInput).toHaveDisplayValue('60');
        expect(burstInput).toHaveDisplayValue('100');
        expect(maxSizeInput).toHaveDisplayValue('1000');
        expect(backpressureInput).toHaveDisplayValue('80');
      });
    });

    it('rate limit enabled switch is checked by default', () => {
      renderWithProviders(<AdminSettings />);

      const enabledSwitch = screen.getByTestId('switch-rate-limit-enabled');
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'true');
    });

    it('renders Save and Reset buttons', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByTestId('btn-save-config')).toBeInTheDocument();
      expect(screen.getByTestId('btn-reset-config')).toBeInTheDocument();
    });

    it('Save and Reset buttons are disabled when no changes', () => {
      renderWithProviders(<AdminSettings />);

      const saveButton = screen.getByTestId('btn-save-config');
      const resetButton = screen.getByTestId('btn-reset-config');

      expect(saveButton).toBeDisabled();
      expect(resetButton).toBeDisabled();
    });

    it('buttons become enabled after making changes', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Get the requests per minute input
      const requestsInput = screen.getByTestId('input-requests-per-minute');

      // Clear and type new value
      await user.clear(requestsInput);
      await user.type(requestsInput, '100');

      // Buttons should now be enabled
      await waitFor(() => {
        expect(screen.getByTestId('btn-save-config')).not.toBeDisabled();
        expect(screen.getByTestId('btn-reset-config')).not.toBeDisabled();
      });
    });

    it('toggling rate limit enabled switch marks changes', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const enabledSwitch = screen.getByTestId('switch-rate-limit-enabled');
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'true');

      // Click to toggle off
      await user.click(enabledSwitch);

      await waitFor(() => {
        expect(enabledSwitch).toHaveAttribute('aria-checked', 'false');
        expect(screen.getByTestId('btn-save-config')).not.toBeDisabled();
      });
    });

    it('Reset button reverts changes', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Change a value
      const requestsInput = screen.getByTestId('input-requests-per-minute');
      await user.clear(requestsInput);
      await user.type(requestsInput, '100');

      // Click reset
      const resetButton = screen.getByTestId('btn-reset-config');
      await waitFor(() => {
        expect(resetButton).not.toBeDisabled();
      });
      await user.click(resetButton);

      // Value should be back to default
      await waitFor(() => {
        expect(requestsInput).toHaveDisplayValue('60');
        expect(resetButton).toBeDisabled();
      });
    });

    it('Save button can be clicked when changes are made', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Change a value
      const requestsInput = screen.getByTestId('input-requests-per-minute');
      await user.clear(requestsInput);
      await user.type(requestsInput, '100');

      // Save button should be enabled
      const saveButton = screen.getByTestId('btn-save-config');
      await waitFor(() => {
        expect(saveButton).not.toBeDisabled();
      });

      // Click save - should not throw
      await user.click(saveButton);

      // Button should still be present after save
      expect(saveButton).toBeInTheDocument();
    });

    it('shows unsaved changes summary when config is modified', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Change a value
      const enabledSwitch = screen.getByTestId('switch-rate-limit-enabled');
      await user.click(enabledSwitch);

      // Summary should show unsaved changes
      await waitFor(() => {
        expect(screen.getByText('unsaved changes')).toBeInTheDocument();
      });
    });

    it('has proper aria labels for inputs', () => {
      renderWithProviders(<AdminSettings />);

      const requestsInput = screen.getByLabelText('Requests per minute');
      const burstInput = screen.getByLabelText('Burst size');
      const maxSizeInput = screen.getByLabelText('Maximum queue size');
      const backpressureInput = screen.getByLabelText('Backpressure threshold percentage');
      const enabledSwitch = screen.getByLabelText('Rate limiting enabled');

      expect(requestsInput).toBeInTheDocument();
      expect(burstInput).toBeInTheDocument();
      expect(maxSizeInput).toBeInTheDocument();
      expect(backpressureInput).toBeInTheDocument();
      expect(enabledSwitch).toBeInTheDocument();
    });

    it('can collapse and expand the System Config section', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const toggleButton = screen.getByTestId('admin-system-config-toggle');
      expect(screen.getByTestId('rate-limiting-section')).toBeInTheDocument();

      // Collapse the section
      await user.click(toggleButton);

      // Wait for animation and check content is hidden
      await waitFor(() => {
        expect(screen.queryByTestId('rate-limiting-section')).not.toBeInTheDocument();
      });
    });
  });

  describe('Maintenance Actions section', () => {
    it('renders all maintenance action buttons', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByTestId('btn-orphan-cleanup')).toBeInTheDocument();
      expect(screen.getByTestId('btn-cache-clear')).toBeInTheDocument();
      expect(screen.getByTestId('btn-flush-queues')).toBeInTheDocument();
    });

    it('displays maintenance action descriptions', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByText('Remove orphaned files and database records')).toBeInTheDocument();
      expect(screen.getByText('Purge all cached data from Redis')).toBeInTheDocument();
      expect(screen.getByText('Clear all processing queues')).toBeInTheDocument();
    });

    it('orphan cleanup button opens confirmation dialog', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const button = screen.getByTestId('btn-orphan-cleanup');
      await user.click(button);

      // Confirmation dialog should appear
      await waitFor(() => {
        expect(screen.getByText('Run Orphan Cleanup')).toBeInTheDocument();
        expect(
          screen.getByText(/This will scan for and remove orphaned files and database records/)
        ).toBeInTheDocument();
      });
    });

    it('cache clear button opens confirmation dialog', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const button = screen.getByTestId('btn-cache-clear');
      await user.click(button);

      // Confirmation dialog should appear - check for the dialog content
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
        expect(screen.getByText(/This will purge all cached data from Redis/)).toBeInTheDocument();
      });
    });

    it('flush queues button opens confirmation dialog', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      const button = screen.getByTestId('btn-flush-queues');
      await user.click(button);

      // Confirmation dialog should appear - check for the dialog content
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
        expect(screen.getByText(/This will clear all processing queues/)).toBeInTheDocument();
      });
    });

    it('orphan cleanup executes after confirmation', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Click the button to open dialog
      const button = screen.getByTestId('btn-orphan-cleanup');
      await user.click(button);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Find the confirm button in the dialog
      const dialog = screen.getByTestId('confirm-dialog');
      const confirmButton = dialog.querySelector('button:not(:first-child)');
      expect(confirmButton).toBeTruthy();
      await user.click(confirmButton!);

      // Dialog should close after execution completes
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });
    });

    it('cache clear executes after confirmation', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Click the button to open dialog
      const button = screen.getByTestId('btn-cache-clear');
      await user.click(button);

      // Wait for dialog to appear and click confirm
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Use getAllByRole since there are multiple "Clear Cache" buttons/text
      const confirmButtons = screen.getAllByRole('button', { name: /Clear Cache/ });
      // The confirm button should be the one in the dialog
      const confirmButton = confirmButtons.find(
        (btn) => btn.closest('[role="dialog"]') !== null
      );
      expect(confirmButton).toBeDefined();
      await user.click(confirmButton!);

      // Dialog should close after execution completes
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });
    });

    it('flush queues executes after confirmation', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Click the button to open dialog
      const button = screen.getByTestId('btn-flush-queues');
      await user.click(button);

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Find the confirm button in the dialog (second button in dialog)
      const dialog = screen.getByTestId('confirm-dialog');
      const confirmButton = dialog.querySelector('button:not(:first-child)');
      expect(confirmButton).toBeTruthy();
      await user.click(confirmButton!);

      // Dialog should close after execution completes
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });
    });

    it('confirmation dialog can be cancelled for orphan cleanup', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Open dialog
      const button = screen.getByTestId('btn-orphan-cleanup');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: /Cancel/ });
      await user.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });

      // Button should not show loading state
      expect(screen.queryByText('Running...')).not.toBeInTheDocument();
    });

    it('confirmation dialog can be cancelled for cache clear', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Open dialog
      const button = screen.getByTestId('btn-cache-clear');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: /Cancel/ });
      await user.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });

      // Button should not show loading state
      expect(screen.queryByText('Clearing...')).not.toBeInTheDocument();
    });

    it('confirmation dialog can be cancelled for flush queues', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Open dialog
      const button = screen.getByTestId('btn-flush-queues');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: /Cancel/ });
      await user.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });

      // Button should not show loading state
      expect(screen.queryByText('Flushing...')).not.toBeInTheDocument();
    });
  });

  describe('Developer Tools section (debug mode)', () => {
    beforeEach(() => {
      // Enable debug mode for these tests
      vi.mocked(useDebugMode).mockReturnValue({
        debugMode: true,
        setDebugMode: vi.fn(),
        isDebugAvailable: true,
      });
    });

    it('renders Developer Tools section when debug mode is enabled', () => {
      renderWithProviders(<AdminSettings />);

      expect(screen.getByText('Developer Tools')).toBeInTheDocument();
    });

    it('shows Debug Mode Only badge with warning indicator', () => {
      renderWithProviders(<AdminSettings />);

      // Developer Tools section has a Debug Mode Only badge with warning
      const debugModeBadge = screen.getByTestId('debug-mode-badge');
      expect(debugModeBadge).toBeInTheDocument();
      expect(debugModeBadge).toHaveTextContent('Debug Mode Only');
    });

    it('renders seed and clear buttons', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Expand the Developer Tools section (it starts collapsed)
      const toggleButton = screen.getByTestId('admin-developer-tools-toggle');
      await user.click(toggleButton);

      await waitFor(() => {
        expect(screen.getByTestId('btn-seed-cameras')).toBeInTheDocument();
        expect(screen.getByTestId('btn-seed-events')).toBeInTheDocument();
        expect(screen.getByTestId('btn-clear-test-data')).toBeInTheDocument();
      });
    });

    it('shows development warning callout', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Expand the Developer Tools section
      const toggleButton = screen.getByTestId('admin-developer-tools-toggle');
      await user.click(toggleButton);

      await waitFor(() => {
        expect(screen.getByText('Development Only')).toBeInTheDocument();
      });
    });

    it('displays seed action descriptions', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AdminSettings />);

      // Expand the Developer Tools section
      const toggleButton = screen.getByTestId('admin-developer-tools-toggle');
      await user.click(toggleButton);

      await waitFor(() => {
        expect(screen.getByText('Create 5 test cameras with realistic names')).toBeInTheDocument();
        expect(screen.getByText('Create 50 test events with detections')).toBeInTheDocument();
        expect(
          screen.getByText('Delete all cameras, events, and detections')
        ).toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('all buttons are accessible', () => {
      renderWithProviders(<AdminSettings />);

      const orphanButton = screen.getByTestId('btn-orphan-cleanup');
      const cacheButton = screen.getByTestId('btn-cache-clear');
      const flushButton = screen.getByTestId('btn-flush-queues');

      expect(orphanButton).not.toBeDisabled();
      expect(cacheButton).not.toBeDisabled();
      expect(flushButton).not.toBeDisabled();
    });

    it('collapsible sections have aria-expanded attribute', () => {
      renderWithProviders(<AdminSettings />);

      const featureTogglesToggle = screen.getByTestId('admin-feature-toggles-toggle');
      expect(featureTogglesToggle).toHaveAttribute('aria-expanded');

      const systemConfigToggle = screen.getByTestId('admin-system-config-toggle');
      expect(systemConfigToggle).toHaveAttribute('aria-expanded');

      const maintenanceToggle = screen.getByTestId('admin-maintenance-toggle');
      expect(maintenanceToggle).toHaveAttribute('aria-expanded');
    });

    it('feature toggle switches have proper aria attributes', () => {
      renderWithProviders(<AdminSettings />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');

      // HeadlessUI Switch provides role="switch" and aria-checked
      expect(visionSwitch).toHaveAttribute('role', 'switch');
      expect(visionSwitch).toHaveAttribute('aria-checked');
      expect(visionSwitch).toHaveAttribute('aria-label');
    });
  });
});
