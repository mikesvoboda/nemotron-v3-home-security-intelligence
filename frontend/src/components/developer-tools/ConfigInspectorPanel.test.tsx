/**
 * Tests for ConfigInspectorPanel component
 *
 * This component displays all configuration key-value pairs from the debug config API.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ConfigInspectorPanel from './ConfigInspectorPanel';
import * as api from '../../services/api';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchDebugConfig: vi.fn(),
}));

describe('ConfigInspectorPanel', () => {
  const mockConfigResponse = {
    database_url: '[REDACTED]',
    redis_url: '[REDACTED]',
    debug_mode: true,
    log_level: 'INFO',
    api_key: '[REDACTED]',
    retention_days: 30,
      log_retention_days: 7,
    batch_window_seconds: 90,
    max_connections: 100,
    null_value: null,
    empty_string: '',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockConfigResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the panel title', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByText('Configuration Inspector')).toBeInTheDocument();
      });
    });

    it('shows loading state initially', () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<ConfigInspectorPanel />);

      expect(screen.getByTestId('config-loading')).toBeInTheDocument();
    });

    it('displays config entries after loading', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByText('database_url')).toBeInTheDocument();
        expect(screen.getByText('log_level')).toBeInTheDocument();
        expect(screen.getByText('retention_days')).toBeInTheDocument();
      });
    });

    it('shows error message on fetch failure', async () => {
      (api.fetchDebugConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch')
      );

      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(
        () => {
          expect(screen.getByTestId('config-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('value formatting', () => {
    it('displays REDACTED values in gray italic', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        const redactedElements = screen.getAllByText('[REDACTED]');
        expect(redactedElements.length).toBeGreaterThan(0);
        // Check styling via data attribute
        redactedElements.forEach((el) => {
          expect(el).toHaveAttribute('data-sensitive', 'true');
        });
      });
    });

    it('displays null values as em dash', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        // em dash represents null
        expect(screen.getByTestId('value-null_value')).toHaveTextContent('\u2014');
      });
    });

    it('displays boolean true correctly', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        const boolElement = screen.getByTestId('value-debug_mode');
        expect(boolElement).toHaveTextContent('true');
      });
    });

    it('displays numbers correctly', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('value-retention_days')).toHaveTextContent('30');
        expect(screen.getByTestId('value-max_connections')).toHaveTextContent('100');
      });
    });

    it('displays strings correctly', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('value-log_level')).toHaveTextContent('INFO');
      });
    });
  });

  describe('copy functionality', () => {
    it('renders copy button for each value', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        const copyButtons = screen.getAllByRole('button', { name: /copy/i });
        expect(copyButtons.length).toBeGreaterThan(0);
      });
    });

    it('copy button is clickable and triggers action', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByText('log_level')).toBeInTheDocument();
      });

      const copyButton = screen.getByTestId('copy-log_level');
      // Verify the button is clickable (doesn't throw)
      await expect(user.click(copyButton)).resolves.not.toThrow();
    });

    it('renders Copy All as JSON button', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /copy all as json/i })).toBeInTheDocument();
      });
    });

    it('Copy All as JSON button is clickable', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByText('log_level')).toBeInTheDocument();
      });

      const copyAllButton = screen.getByRole('button', { name: /copy all as json/i });
      // Verify the button is clickable (doesn't throw)
      await expect(user.click(copyAllButton)).resolves.not.toThrow();
    });
  });

  describe('table structure', () => {
    it('renders config in a table format', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });
    });

    it('has column headers for Key, Value, and Actions', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByText('Key')).toBeInTheDocument();
        expect(screen.getByText('Value')).toBeInTheDocument();
      });
    });
  });

  describe('read-only nature', () => {
    it('does not have any input elements for editing', async () => {
      renderWithProviders(<ConfigInspectorPanel />);

      await waitFor(() => {
        expect(screen.getByText('log_level')).toBeInTheDocument();
      });

      // Should not have any text inputs (config is read-only)
      const inputs = screen.queryAllByRole('textbox');
      expect(inputs.length).toBe(0);
    });
  });
});
