/**
 * Tests for LogLevelPanel component
 *
 * This component displays the current log level and allows changing it.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LogLevelPanel from './LogLevelPanel';
import * as api from '../../services/api';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchLogLevel: vi.fn(),
    setLogLevel: vi.fn(),
  };
});

describe('LogLevelPanel', () => {
  const mockLogLevelResponse = {
    level: 'INFO',
  };

  const mockSetLogLevelResponse = {
    level: 'DEBUG',
    previous_level: 'INFO',
    message: 'Log level changed from INFO to DEBUG',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue(mockLogLevelResponse);
    (api.setLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue(mockSetLogLevelResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the panel title', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByText('Log Level Adjuster')).toBeInTheDocument();
      });
    });

    it('shows loading state initially', () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<LogLevelPanel />);

      expect(screen.getByTestId('log-level-loading')).toBeInTheDocument();
    });

    it('displays current log level after loading', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByText(/current level/i)).toBeInTheDocument();
        // Use getAllByText since INFO appears in both "Current Level: INFO" and the button
        const infoElements = screen.getAllByText('INFO');
        expect(infoElements.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows error message on fetch failure', async () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch')
      );

      renderWithProviders(<LogLevelPanel />);

      await waitFor(
        () => {
          expect(screen.getByTestId('log-level-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('log level buttons', () => {
    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

    it('renders buttons for all log levels', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        levels.forEach((level) => {
          expect(screen.getByRole('button', { name: level })).toBeInTheDocument();
        });
      });
    });

    it('highlights the current log level button', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        const infoButton = screen.getByRole('button', { name: 'INFO' });
        expect(infoButton).toHaveAttribute('data-active', 'true');
      });
    });

    it('does not highlight non-current level buttons', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        const debugButton = screen.getByRole('button', { name: 'DEBUG' });
        expect(debugButton).not.toHaveAttribute('data-active', 'true');
      });
    });
  });

  describe('changing log level', () => {
    it('calls setLogLevel when clicking a different level button', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
      });

      const debugButton = screen.getByRole('button', { name: 'DEBUG' });
      await user.click(debugButton);

      expect(api.setLogLevel).toHaveBeenCalledWith('DEBUG');
    });

    it('does not call setLogLevel when clicking current level', async () => {
      const user = userEvent.setup();
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'INFO' })).toBeInTheDocument();
      });

      const infoButton = screen.getByRole('button', { name: 'INFO' });
      await user.click(infoButton);

      expect(api.setLogLevel).not.toHaveBeenCalled();
    });

    it('shows loading state while changing level', async () => {
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- mock returns Promise
        (): Promise<typeof mockSetLogLevelResponse> =>
          new Promise<typeof mockSetLogLevelResponse>((resolve) => {
            setTimeout(() => {
              resolve(mockSetLogLevelResponse);
            }, 100);
          })
      );

      const user = userEvent.setup();
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
      });

      const debugButton = screen.getByRole('button', { name: 'DEBUG' });
      await user.click(debugButton);

      await waitFor(() => {
        expect(screen.getByTestId('log-level-changing')).toBeInTheDocument();
      });
    });
  });

  describe('DEBUG warning', () => {
    it('shows warning alert when DEBUG is selected', async () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue({ level: 'DEBUG' });

      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('debug-warning')).toBeInTheDocument();
      });
    });

    it('warning mentions performance impact', async () => {
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue({ level: 'DEBUG' });

      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        const warning = screen.getByTestId('debug-warning');
        expect(warning).toHaveTextContent(/performance/i);
      });
    });

    it('does not show warning when INFO is selected', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.queryByTestId('debug-warning')).not.toBeInTheDocument();
      });
    });

    it('shows warning when changing to DEBUG', async () => {
      const user = userEvent.setup();

      // Make the mutation resolve with DEBUG level
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockResolvedValue({
        level: 'DEBUG',
        previous_level: 'INFO',
        message: 'Log level changed',
      });

      // Also need to update the fetch to return DEBUG after mutation
      let currentLevel = 'INFO';
      (api.fetchLogLevel as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        (): Promise<{ level: string }> => {
          return Promise.resolve({ level: currentLevel });
        }
      );
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        (level: string): Promise<{ level: string; previous_level: string; message: string }> => {
          currentLevel = level;
          return Promise.resolve({
            level,
            previous_level: 'INFO',
            message: 'Log level changed',
          });
        }
      );

      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
      });

      const debugButton = screen.getByRole('button', { name: 'DEBUG' });
      await user.click(debugButton);

      await waitFor(() => {
        expect(screen.getByTestId('debug-warning')).toBeInTheDocument();
      });
    });
  });

  describe('persistence note', () => {
    it('shows note that changes do not persist on restart', async () => {
      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByText(/not persist/i)).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('shows error when setLogLevel fails', async () => {
      const user = userEvent.setup();
      (api.setLogLevel as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to set log level')
      );

      renderWithProviders(<LogLevelPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'DEBUG' })).toBeInTheDocument();
      });

      const debugButton = screen.getByRole('button', { name: 'DEBUG' });
      await user.click(debugButton);

      await waitFor(
        () => {
          expect(screen.getByTestId('log-level-set-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });
});
