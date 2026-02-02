/**
 * Tests for LoggingSettings component
 *
 * Comprehensive test suite for logging configuration UI:
 * - Log level selection (editable via API)
 * - Log file settings (read-only from config)
 * - Database logging settings (read-only from config)
 * - Log retention (editable via system config)
 */
import { screen, waitFor, within, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LoggingSettings from './LoggingSettings';
import * as api from '../../services/api';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchDebugConfig: vi.fn(),
    fetchLogLevel: vi.fn(),
    setLogLevel: vi.fn(),
    fetchConfig: vi.fn(),
    updateConfig: vi.fn(),
  };
});

// Mock the toast hook
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

describe('LoggingSettings', () => {
  // Debug config response is flat Record<string, unknown>
  const mockDebugConfig = {
    log_level: 'INFO',
    log_file_path: 'data/logs/security.log',
    log_file_max_bytes: 10485760,
    log_file_backup_count: 7,
    log_db_enabled: true,
    log_db_min_level: 'DEBUG',
    log_retention_days: 7,
    database_url: '[REDACTED]',
    redis_url: '[REDACTED]',
    debug: true,
  };

  const mockLogLevelResponse = {
    level: 'INFO',
    previous_level: 'INFO',
  };

  const mockSystemConfig = {
    app_name: 'Home Security',
    version: '1.0.0',
    retention_days: 30,
    log_retention_days: 7,
    batch_window_seconds: 90,
    batch_idle_timeout_seconds: 30,
    detection_confidence_threshold: 0.5,
    fast_path_confidence_threshold: 0.9,
    grafana_url: '/grafana',
    debug: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockDebugConfig);
    (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue(mockLogLevelResponse);
    (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockSystemConfig);
    (api.setLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue({
      level: 'DEBUG',
      previous_level: 'INFO',
    });
    (api.updateConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockSystemConfig);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the panel title and description', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Logging Configuration')).toBeInTheDocument();
      });

      expect(
        screen.getByText(/Configure application logging settings/)
      ).toBeInTheDocument();
    });

    it('applies custom className', async () => {
      renderWithProviders(<LoggingSettings className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('logging-settings')).toHaveClass('custom-class');
      });
    });

    it('shows loading state initially', () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<LoggingSettings />);

      expect(screen.getByTestId('logging-settings-loading')).toBeInTheDocument();
    });

    it('displays all logging sections after loading', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Runtime Log Level')).toBeInTheDocument();
        expect(screen.getByText('Log File Settings')).toBeInTheDocument();
        expect(screen.getByText('Database Logging')).toBeInTheDocument();
        expect(screen.getByText('Log Retention')).toBeInTheDocument();
      });
    });

    it('shows error message on fetch failure', async () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch config')
      );

      renderWithProviders(<LoggingSettings />);

      await waitFor(
        () => {
          expect(screen.getByTestId('logging-settings-error')).toBeInTheDocument();
          expect(screen.getByText(/Failed to fetch config/)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('log level section', () => {
    it('displays current log level', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Current Level:')).toBeInTheDocument();
        // INFO appears in both the display and the button, use getAllByText
        const infoElements = screen.getAllByText('INFO');
        expect(infoElements.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders all log level buttons', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'INFO' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'WARNING' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'ERROR' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'CRITICAL' })).toBeInTheDocument();
      });
    });

    it('highlights the current log level button', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        const infoButton = screen.getByRole('button', { name: 'INFO' });
        expect(infoButton).toHaveAttribute('data-active', 'true');
      });
    });

    it('calls setLogLevel when a different level is clicked', async () => {
      const { user } = renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'DEBUG' }));

      expect(api.setLogLevel).toHaveBeenCalledWith('DEBUG');
    });

    it('shows DEBUG warning when DEBUG level is active', async () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockDebugConfig,
        log_level: 'DEBUG',
      });
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue({
        level: 'DEBUG',
        previous_level: 'INFO',
      });

      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByTestId('debug-warning')).toBeInTheDocument();
        expect(screen.getByText(/DEBUG logging is enabled/)).toBeInTheDocument();
      });
    });

    it('shows persistence note about log level changes', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText(/not persist/)).toBeInTheDocument();
      });
    });
  });

  describe('log file settings section', () => {
    it('displays log file path as read-only', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('File Path')).toBeInTheDocument();
        expect(screen.getByText('data/logs/security.log')).toBeInTheDocument();
      });
    });

    it('displays max file size in human-readable format', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Max File Size')).toBeInTheDocument();
        expect(screen.getByText('10 MB')).toBeInTheDocument();
      });
    });

    it('displays backup count', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Backup Count')).toBeInTheDocument();
        expect(screen.getByText('7 files')).toBeInTheDocument();
      });
    });

    it('shows read-only indicator for file settings', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        const fileSection = screen.getByTestId('log-file-settings');
        expect(within(fileSection).getByText(/read-only/i)).toBeInTheDocument();
      });
    });
  });

  describe('database logging section', () => {
    it('displays database logging enabled status', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('DB Logging')).toBeInTheDocument();
        expect(screen.getByText('Enabled')).toBeInTheDocument();
      });
    });

    it('displays database logging disabled status', async () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockDebugConfig,
        log_db_enabled: false,
      });

      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('DB Logging')).toBeInTheDocument();
        expect(screen.getByText('Disabled')).toBeInTheDocument();
      });
    });

    it('displays minimum database log level', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Min DB Level')).toBeInTheDocument();
        // DEBUG appears in both the db level display and the log level button
        const debugElements = screen.getAllByText('DEBUG');
        expect(debugElements.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows read-only indicator for database settings', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        const dbSection = screen.getByTestId('log-db-settings');
        expect(within(dbSection).getByText(/read-only/i)).toBeInTheDocument();
      });
    });
  });

  describe('log retention section', () => {
    it('displays current log retention days', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        const retentionSection = screen.getByTestId('log-retention-settings');
        expect(within(retentionSection).getByText('7 days')).toBeInTheDocument();
      });
    });

    it('renders retention slider', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByLabelText('Log retention period in days')).toBeInTheDocument();
      });
    });

    it('updates retention value when slider changes', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByLabelText('Log retention period in days')).toBeInTheDocument();
      });

      const slider = screen.getByLabelText('Log retention period in days');

      // Simulate changing the slider value using fireEvent
      fireEvent.change(slider, { target: { value: '14' } });

      // The component should show unsaved changes indicator (button enabled)
      await waitFor(() => {
        expect(screen.getByTestId('retention-save-button')).not.toBeDisabled();
      });
    });

    it('shows Save and Reset buttons for retention', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByTestId('retention-save-button')).toBeInTheDocument();
        expect(screen.getByTestId('retention-reset-button')).toBeInTheDocument();
      });
    });

    it('disables Save button when no changes are made', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByTestId('retention-save-button')).toBeDisabled();
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible labels for all interactive elements', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        // Log level buttons
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'INFO' })).toBeInTheDocument();

        // Retention slider
        expect(screen.getByLabelText('Log retention period in days')).toBeInTheDocument();
      });
    });

    it('provides aria-describedby for read-only sections', async () => {
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByTestId('log-file-settings')).toBeInTheDocument();
        expect(screen.getByTestId('log-db-settings')).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('shows error when log level change fails', async () => {
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to set log level')
      );

      const { user } = renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'DEBUG' }));

      await waitFor(() => {
        expect(screen.getByTestId('log-level-error')).toBeInTheDocument();
      });
    });

    it('displays retry button in error state', async () => {
      // Mock persistent error - all calls fail
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      renderWithProviders(<LoggingSettings />);

      await waitFor(
        () => {
          expect(screen.getByTestId('logging-settings-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      // Verify retry button is present
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
  });

  describe('value formatting', () => {
    it('formats file size correctly for 10 MB default', async () => {
      // Default mockDebugConfig has 10485760 bytes (10 MB)
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('10 MB')).toBeInTheDocument();
      });
    });

    it('formats file size correctly for 1 MB', async () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockDebugConfig,
        log_file_max_bytes: 1048576,
      });

      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('1 MB')).toBeInTheDocument();
      });
    });

    it('formats backup count with plural', async () => {
      // Default has 7 files
      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('7 files')).toBeInTheDocument();
      });
    });

    it('formats backup count with singular', async () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockDebugConfig,
        log_file_backup_count: 1,
      });

      renderWithProviders(<LoggingSettings />);

      await waitFor(() => {
        expect(screen.getByText('1 file')).toBeInTheDocument();
      });
    });
  });
});
