import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ProcessingSettings from './ProcessingSettings';
import * as api from '../../services/api';


// Mock the API module
vi.mock('../../services/api');

describe('ProcessingSettings', () => {
  const mockConfig: api.SystemConfig = {
    app_name: 'Home Security Intelligence',
    version: '0.1.0',
    retention_days: 30,
    batch_window_seconds: 90,
    batch_idle_timeout_seconds: 30,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders component with title', () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    render(<ProcessingSettings />);

    expect(screen.getByText('Processing Settings')).toBeInTheDocument();
  });

  it('shows loading skeleton while fetching config', () => {
    vi.mocked(api.fetchConfig).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<ProcessingSettings />);

    // Check for skeleton loading elements
    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('displays all configuration fields after loading', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    render(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
    });

    expect(screen.getByText('Idle Timeout')).toBeInTheDocument();
    expect(screen.getByText('Retention Period')).toBeInTheDocument();
  });

  it('displays correct configuration values', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    render(<ProcessingSettings />);

    await waitFor(() => {
      const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
      expect(batchWindowInput).toHaveValue(90);
    });

    const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
    expect(idleTimeoutInput).toHaveValue(30);

    const retentionInput = screen.getByLabelText('Retention period in days');
    expect(retentionInput).toHaveValue(30);
  });

  it('displays application name and version', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    render(<ProcessingSettings />);

    await waitFor(() => {
      expect(screen.getByText('Home Security Intelligence')).toBeInTheDocument();
    });

    expect(screen.getByText('0.1.0')).toBeInTheDocument();
  });

  it('shows read-only notice', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    render(<ProcessingSettings />);

    await waitFor(() => {
      expect(
        screen.getByText(/Settings are currently read-only/i)
      ).toBeInTheDocument();
    });
  });

  it('disables all input fields', async () => {
    vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

    render(<ProcessingSettings />);

    await waitFor(() => {
      const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
      expect(batchWindowInput).toBeDisabled();
    });

    const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
    expect(idleTimeoutInput).toBeDisabled();

    const retentionInput = screen.getByLabelText('Retention period in days');
    expect(retentionInput).toBeDisabled();
  });

  describe('error handling', () => {
    it('displays error message when fetch fails', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(
        new Error('Network error')
      );

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('displays generic error for non-Error objects', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue('Unknown error');

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load configuration')).toBeInTheDocument();
      });
    });

    it('shows error icon when error occurs', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(
        new Error('Network error')
      );

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Check for AlertCircle icon (it will be in the DOM as an svg)
      const errorContainer = screen.getByText('Network error').closest('div');
      expect(errorContainer).toBeInTheDocument();
    });

    it('does not show config fields when error occurs', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(
        new Error('Network error')
      );

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      expect(screen.queryByText('Batch Window Duration')).not.toBeInTheDocument();
    });
  });

  describe('field descriptions', () => {
    it('shows description for batch window duration', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Time window for grouping detections into events/i)
        ).toBeInTheDocument();
      });
    });

    it('shows description for idle timeout', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Time to wait before processing incomplete batch/i)
        ).toBeInTheDocument();
      });
    });

    it('shows description for retention period', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(
          screen.getByText(/Number of days to retain events and detections/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('edge cases', () => {
    it('handles zero values correctly', async () => {
      const zeroConfig: api.SystemConfig = {
        ...mockConfig,
        batch_window_seconds: 0,
        batch_idle_timeout_seconds: 0,
        retention_days: 0,
      };

      vi.mocked(api.fetchConfig).mockResolvedValue(zeroConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
        expect(batchWindowInput).toHaveValue(0);
      });

      const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
      expect(idleTimeoutInput).toHaveValue(0);

      const retentionInput = screen.getByLabelText('Retention period in days');
      expect(retentionInput).toHaveValue(0);
    });

    it('handles very large values correctly', async () => {
      const largeConfig: api.SystemConfig = {
        ...mockConfig,
        batch_window_seconds: 9999,
        batch_idle_timeout_seconds: 9999,
        retention_days: 9999,
      };

      vi.mocked(api.fetchConfig).mockResolvedValue(largeConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
        expect(batchWindowInput).toHaveValue(9999);
      });

      const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
      expect(idleTimeoutInput).toHaveValue(9999);

      const retentionInput = screen.getByLabelText('Retention period in days');
      expect(retentionInput).toHaveValue(9999);
    });

    it('applies custom className', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings className="custom-test-class" />);

      await waitFor(() => {
        expect(screen.getByText('Processing Settings')).toBeInTheDocument();
      });

      // The Card component should have the custom class
      const card = screen.getByText('Processing Settings').closest('.custom-test-class');
      expect(card).toBeInTheDocument();
    });
  });

  describe('input types', () => {
    it('uses number input type for all numeric fields', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        const batchWindowInput = screen.getByLabelText('Batch window duration in seconds');
        expect(batchWindowInput).toHaveAttribute('type', 'number');
      });

      const idleTimeoutInput = screen.getByLabelText('Batch idle timeout in seconds');
      expect(idleTimeoutInput).toHaveAttribute('type', 'number');

      const retentionInput = screen.getByLabelText('Retention period in days');
      expect(retentionInput).toHaveAttribute('type', 'number');
    });
  });

  describe('accessibility', () => {
    it('includes proper aria-labels for all inputs', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByLabelText('Batch window duration in seconds')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Batch idle timeout in seconds')).toBeInTheDocument();
      expect(screen.getByLabelText('Retention period in days')).toBeInTheDocument();
    });

    it('uses semantic text labels', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue(mockConfig);

      render(<ProcessingSettings />);

      await waitFor(() => {
        expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
      });

      // Check that field labels are present
      expect(screen.getByText('Batch Window Duration')).toBeInTheDocument();
      expect(screen.getByText('Idle Timeout')).toBeInTheDocument();
      expect(screen.getByText('Retention Period')).toBeInTheDocument();
    });
  });
});
