import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CleanupPreviewPanel from './CleanupPreviewPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  previewCleanup: vi.fn(),
  triggerCleanup: vi.fn(),
}));

describe('CleanupPreviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders initial state with preview button', () => {
    render(<CleanupPreviewPanel />);

    expect(screen.getByText('Cleanup Preview')).toBeInTheDocument();
    expect(screen.getByText(/Preview what will be deleted/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Preview Cleanup/i })).toBeInTheDocument();
  });

  it('renders with custom className', () => {
    const { container } = render(<CleanupPreviewPanel className="custom-class" />);

    const card = container.querySelector('.custom-class');
    expect(card).toBeInTheDocument();
  });

  describe('Preview Functionality', () => {
    it('shows loading state when fetching preview', async () => {
      const user = userEvent.setup();
      vi.mocked(api.previewCleanup).mockImplementation(
        () => new Promise(() => {}) // Never resolves to keep loading state
      );

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      expect(screen.getByRole('button', { name: /Calculating Preview/i })).toBeDisabled();
    });

    it('displays preview results when data exists', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000, // ~500 MB
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      expect(screen.getByText('Retention: 30 days')).toBeInTheDocument();
      expect(screen.getAllByText('15')).toHaveLength(1); // events
      expect(screen.getAllByText('89')).toHaveLength(2); // detections and thumbnails
      expect(screen.getByText('2,880')).toBeInTheDocument(); // GPU stats
      expect(screen.getByText('150')).toBeInTheDocument(); // logs
      expect(screen.getByText('500.00 MB')).toBeInTheDocument(); // space reclaimed
    });

    it('displays message when no data to clean up', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 0,
        detections_deleted: 0,
        gpu_stats_deleted: 0,
        logs_deleted: 0,
        thumbnails_deleted: 0,
        images_deleted: 0,
        space_reclaimed: 0,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText(/No data to clean up/i)).toBeInTheDocument();
      });
    });

    it('displays error when preview fails', async () => {
      const user = userEvent.setup();
      vi.mocked(api.previewCleanup).mockRejectedValue(new Error('Network error'));

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('allows clearing preview', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Clear preview
      const clearButton = screen.getByRole('button', { name: /Clear Preview/i });
      await user.click(clearButton);

      expect(screen.queryByText('Preview Results')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Preview Cleanup/i })).toBeInTheDocument();
    });
  });

  describe('Cleanup Functionality', () => {
    it('shows confirmation dialog when proceeding with cleanup', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Click proceed button
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      expect(screen.getByText('Confirm Cleanup')).toBeInTheDocument();
      expect(screen.getByText(/This action cannot be undone/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Yes, Delete Data/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('allows canceling cleanup confirmation', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Click proceed button
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Cancel confirmation
      const cancelButton = screen.getByRole('button', { name: /Cancel/i });
      await user.click(cancelButton);

      expect(screen.queryByText('Confirm Cleanup')).not.toBeInTheDocument();
      expect(screen.getByText('Preview Results')).toBeInTheDocument();
    });

    it('performs cleanup when confirmed', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      const mockCleanupResult = {
        ...mockPreview,
        dry_run: false,
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);
      vi.mocked(api.triggerCleanup).mockResolvedValue(mockCleanupResult);

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Proceed with cleanup
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Confirm cleanup
      const confirmButton = screen.getByRole('button', { name: /Yes, Delete Data/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText('Cleanup Complete')).toBeInTheDocument();
      });

      expect(api.triggerCleanup).toHaveBeenCalled();
      expect(screen.queryByText('Preview Results')).not.toBeInTheDocument();
    });

    it('displays error when cleanup fails', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);
      vi.mocked(api.triggerCleanup).mockRejectedValue(new Error('Cleanup failed'));

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Proceed with cleanup
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Confirm cleanup
      const confirmButton = screen.getByRole('button', { name: /Yes, Delete Data/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText('Cleanup failed')).toBeInTheDocument();
      });
    });

    it('calls cleanup API when confirmed', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      const mockCleanupResult = {
        ...mockPreview,
        dry_run: false,
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);
      vi.mocked(api.triggerCleanup).mockResolvedValue(mockCleanupResult);

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Proceed with cleanup
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Confirm cleanup
      const confirmButton = screen.getByRole('button', { name: /Yes, Delete Data/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(api.triggerCleanup).toHaveBeenCalled();
      });
    });
  });

  describe('Byte Formatting', () => {
    it('does not show space section when space_reclaimed is 0', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 1,
        detections_deleted: 1,
        gpu_stats_deleted: 1,
        logs_deleted: 1,
        thumbnails_deleted: 1,
        images_deleted: 0,
        space_reclaimed: 0,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      expect(screen.queryByText(/Estimated Space to Reclaim/i)).not.toBeInTheDocument();
    });

    it.each([
      [500, '500.00 B'],
      [1024, '1.00 KB'],
      [1048576, '1.00 MB'],
      [1073741824, '1.00 GB'],
      [524288000, '500.00 MB'],
      [2147483648, '2.00 GB'],
    ])('formats %d bytes as %s', async (bytes, expected) => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 1,
        detections_deleted: 1,
        gpu_stats_deleted: 1,
        logs_deleted: 1,
        thumbnails_deleted: 1,
        images_deleted: 0,
        space_reclaimed: bytes,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText(expected)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', () => {
      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      expect(previewButton).toBeInTheDocument();
    });

    it('disables buttons during loading', async () => {
      const user = userEvent.setup();
      vi.mocked(api.previewCleanup).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      const loadingButton = screen.getByRole('button', { name: /Calculating Preview/i });
      expect(loadingButton).toBeDisabled();
    });

    it('hides confirmation dialog after cleanup starts', async () => {
      const user = userEvent.setup();
      const mockPreview = {
        events_deleted: 15,
        detections_deleted: 89,
        gpu_stats_deleted: 2880,
        logs_deleted: 150,
        thumbnails_deleted: 89,
        images_deleted: 5,
        space_reclaimed: 524288000,
        retention_days: 30,
        dry_run: true,
        timestamp: '2025-12-27T10:30:00Z',
      };

      const mockCleanupResult = {
        ...mockPreview,
        dry_run: false,
      };

      vi.mocked(api.previewCleanup).mockResolvedValue(mockPreview);
      vi.mocked(api.triggerCleanup).mockResolvedValue(mockCleanupResult);

      render(<CleanupPreviewPanel />);

      // Generate preview
      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      await waitFor(() => {
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
      });

      // Proceed with cleanup
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Verify confirmation is shown
      expect(screen.getByText('Confirm Cleanup')).toBeInTheDocument();

      // Confirm cleanup
      const confirmButton = screen.getByRole('button', { name: /Yes, Delete Data/i });
      await user.click(confirmButton);

      await waitFor(() => {
        // Confirmation dialog should be hidden
        expect(screen.queryByText('Confirm Cleanup')).not.toBeInTheDocument();
      });
    });
  });
});
