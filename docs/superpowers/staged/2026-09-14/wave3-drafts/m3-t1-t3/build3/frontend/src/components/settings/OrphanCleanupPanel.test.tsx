import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import OrphanCleanupPanel from './OrphanCleanupPanel';
import { renderWithProviders } from '../../test-utils';

// Mock the useToast hook
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock the useOrphanCleanupMutation hook
const mockMutateAsync = vi.fn();
vi.mock('../../hooks/useAdminMutations', () => ({
  useOrphanCleanupMutation: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}));

// Mock response data
const mockPreviewResponse = {
  scanned_files: 1500,
  orphaned_files: 42,
  deleted_files: 42,
  deleted_bytes: 2500000000,
  deleted_bytes_formatted: '2.5 GB',
  failed_count: 0,
  failed_deletions: [],
  duration_seconds: 1.23,
  dry_run: true,
  skipped_young: 5,
  skipped_size_limit: 2,
};

const mockCleanupResponse = {
  scanned_files: 1500,
  orphaned_files: 42,
  deleted_files: 40,
  deleted_bytes: 2300000000,
  deleted_bytes_formatted: '2.3 GB',
  failed_count: 2,
  failed_deletions: ['/path/to/file1.jpg', '/path/to/file2.jpg'],
  duration_seconds: 2.45,
  dry_run: false,
  skipped_young: 5,
  skipped_size_limit: 2,
};

describe('OrphanCleanupPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMutateAsync.mockResolvedValue(mockPreviewResponse);
  });

  describe('rendering', () => {
    it('renders the panel with correct structure', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      expect(screen.getByTestId('orphan-cleanup-panel')).toBeInTheDocument();
      expect(screen.getByText('Orphan File Cleanup')).toBeInTheDocument();
      expect(
        screen.getByText(/Scan and remove files that are no longer referenced in the database/)
      ).toBeInTheDocument();
    });

    it('renders min age hours slider with default value', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const slider = screen.getByTestId('min-age-hours-slider');
      expect(slider).toBeInTheDocument();
      expect(slider).toHaveValue('24');

      // Check displayed value
      expect(screen.getByTestId('min-age-hours-slider-value')).toHaveTextContent('1 day');
    });

    it('renders max delete GB slider with default value', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const slider = screen.getByTestId('max-delete-gb-slider');
      expect(slider).toBeInTheDocument();
      expect(slider).toHaveValue('10');

      // Check displayed value
      expect(screen.getByTestId('max-delete-gb-slider-value')).toHaveTextContent('10.0 GB');
    });

    it('renders Preview and Clean Up buttons', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      expect(screen.getByTestId('btn-preview-cleanup')).toBeInTheDocument();
      expect(screen.getByTestId('btn-preview-cleanup')).toHaveTextContent('Preview');

      expect(screen.getByTestId('btn-run-cleanup')).toBeInTheDocument();
      expect(screen.getByTestId('btn-run-cleanup')).toHaveTextContent('Clean Up');
    });

    it('applies custom className', () => {
      renderWithProviders(<OrphanCleanupPanel className="custom-class" />);

      const panel = screen.getByTestId('orphan-cleanup-panel');
      expect(panel).toHaveClass('custom-class');
    });
  });

  describe('slider interactions', () => {
    it('updates min age hours when slider changes', async () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const slider = screen.getByTestId('min-age-hours-slider');

      // Change to 48 hours using native event dispatch for range inputs
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(
        slider,
        '48'
      );
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      slider.dispatchEvent(new Event('change', { bubbles: true }));

      await waitFor(() => {
        expect(screen.getByTestId('min-age-hours-slider-value')).toHaveTextContent('2 days');
      });
    });

    it('updates max delete GB when slider changes', async () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const slider = screen.getByTestId('max-delete-gb-slider');

      // Change to 25 GB
      slider.focus();
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(
        slider,
        '25'
      );
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      slider.dispatchEvent(new Event('change', { bubbles: true }));

      await waitFor(() => {
        expect(screen.getByTestId('max-delete-gb-slider-value')).toHaveTextContent('25.0 GB');
      });
    });

    it('displays formatted hours correctly for various values', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const slider = screen.getByTestId('min-age-hours-slider');

      // Test 1 hour
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(
        slider,
        '1'
      );
      slider.dispatchEvent(new Event('change', { bubbles: true }));

      expect(screen.getByTestId('min-age-hours-slider-value')).toHaveTextContent('1 hour');

      // Test 25 hours (1d 1h)
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(
        slider,
        '25'
      );
      slider.dispatchEvent(new Event('change', { bubbles: true }));

      expect(screen.getByTestId('min-age-hours-slider-value')).toHaveTextContent('1d 1h');
    });
  });

  describe('preview functionality', () => {
    it('calls mutateAsync with dry_run=true when Preview clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      const previewButton = screen.getByTestId('btn-preview-cleanup');
      await user.click(previewButton);

      expect(mockMutateAsync).toHaveBeenCalledWith({
        dry_run: true,
        min_age_hours: 24,
        max_delete_gb: 10,
      });
    });

    it('displays preview results after successful preview', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      await user.click(screen.getByTestId('btn-preview-cleanup'));

      await waitFor(() => {
        expect(screen.getByTestId('orphan-cleanup-results')).toBeInTheDocument();
        expect(screen.getByText('Preview Results')).toBeInTheDocument();
        expect(screen.getByTestId('result-scanned-files')).toHaveTextContent('1,500');
        expect(screen.getByTestId('result-orphaned-files')).toHaveTextContent('42');
        expect(screen.getByTestId('result-deleted-files')).toHaveTextContent('42 files');
        expect(screen.getByTestId('result-deleted-bytes')).toHaveTextContent('2.5 GB');
      });
    });

    it('shows "Would Delete" and "Would Free" labels for dry run', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      await user.click(screen.getByTestId('btn-preview-cleanup'));

      await waitFor(() => {
        expect(screen.getByText('Would Delete')).toBeInTheDocument();
        expect(screen.getByText('Would Free')).toBeInTheDocument();
      });
    });
  });

  describe('cleanup functionality', () => {
    it('opens confirmation dialog when Clean Up clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      await user.click(screen.getByTestId('btn-run-cleanup'));

      await waitFor(() => {
        expect(screen.getByText('Confirm Orphan Cleanup')).toBeInTheDocument();
        expect(
          screen.getByText(/This will permanently delete orphaned files older than/)
        ).toBeInTheDocument();
      });
    });

    it('calls mutateAsync with dry_run=false after confirmation', async () => {
      const user = userEvent.setup();
      mockMutateAsync.mockResolvedValue(mockCleanupResponse);
      renderWithProviders(<OrphanCleanupPanel />);

      // Open confirmation dialog
      await user.click(screen.getByTestId('btn-run-cleanup'));

      // Wait for dialog and find confirm button
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Click the confirm button (Delete Files)
      const confirmButton = screen.getByRole('button', { name: /Delete Files/i });
      await user.click(confirmButton);

      expect(mockMutateAsync).toHaveBeenCalledWith({
        dry_run: false,
        min_age_hours: 24,
        max_delete_gb: 10,
      });
    });

    it('closes dialog when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      // Open dialog
      await user.click(screen.getByTestId('btn-run-cleanup'));

      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });

      // Cancel
      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });

      // Should not have called the mutation
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });

    it('displays cleanup results after successful cleanup', async () => {
      const user = userEvent.setup();
      mockMutateAsync.mockResolvedValue(mockCleanupResponse);
      renderWithProviders(<OrphanCleanupPanel />);

      // Open and confirm
      await user.click(screen.getByTestId('btn-run-cleanup'));
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /Delete Files/i }));

      await waitFor(() => {
        expect(screen.getByText('Cleanup Completed with Warnings')).toBeInTheDocument();
        expect(screen.getByTestId('result-deleted-files')).toHaveTextContent('40 files');
        expect(screen.getByText('Deleted')).toBeInTheDocument();
        expect(screen.getByText('Space Freed')).toBeInTheDocument();
      });
    });

    it('displays failed deletions when there are failures', async () => {
      const user = userEvent.setup();
      mockMutateAsync.mockResolvedValue(mockCleanupResponse);
      renderWithProviders(<OrphanCleanupPanel />);

      // Open and confirm
      await user.click(screen.getByTestId('btn-run-cleanup'));
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /Delete Files/i }));

      await waitFor(() => {
        expect(screen.getByText('Failed Deletions: 2')).toBeInTheDocument();
        expect(screen.getByText('/path/to/file1.jpg')).toBeInTheDocument();
        expect(screen.getByText('/path/to/file2.jpg')).toBeInTheDocument();
      });
    });

    it('includes preview info in confirmation dialog after preview', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      // First run preview
      await user.click(screen.getByTestId('btn-preview-cleanup'));
      await waitFor(() => {
        expect(screen.getByTestId('orphan-cleanup-results')).toBeInTheDocument();
      });

      // Then open cleanup dialog
      await user.click(screen.getByTestId('btn-run-cleanup'));

      await waitFor(() => {
        expect(
          screen.getByText(/Preview showed 42 files \(2\.5 GB\) would be deleted/)
        ).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('handles preview error gracefully', async () => {
      const user = userEvent.setup();
      mockMutateAsync.mockRejectedValueOnce(new Error('Network error'));
      renderWithProviders(<OrphanCleanupPanel />);

      await user.click(screen.getByTestId('btn-preview-cleanup'));

      // Should not crash, buttons should still be clickable
      await waitFor(() => {
        expect(screen.getByTestId('btn-preview-cleanup')).not.toBeDisabled();
      });
    });

    it('handles cleanup error gracefully', async () => {
      const user = userEvent.setup();
      mockMutateAsync.mockRejectedValueOnce(new Error('Permission denied'));
      renderWithProviders(<OrphanCleanupPanel />);

      // Open and confirm
      await user.click(screen.getByTestId('btn-run-cleanup'));
      await waitFor(() => {
        expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /Delete Files/i }));

      // Dialog should close even on error
      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('additional stats display', () => {
    it('shows skipped files info in results', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OrphanCleanupPanel />);

      await user.click(screen.getByTestId('btn-preview-cleanup'));

      await waitFor(() => {
        expect(screen.getByText(/Duration:/)).toBeInTheDocument();
        expect(screen.getByText(/1\.23s/)).toBeInTheDocument();
        expect(screen.getByText(/Skipped \(too young\):/)).toBeInTheDocument();
        expect(screen.getByText(/Skipped \(size limit\):/)).toBeInTheDocument();
      });
    });

    it('does not show skipped info when counts are zero', async () => {
      const user = userEvent.setup();
      mockMutateAsync.mockResolvedValue({
        ...mockPreviewResponse,
        skipped_young: 0,
        skipped_size_limit: 0,
      });
      renderWithProviders(<OrphanCleanupPanel />);

      await user.click(screen.getByTestId('btn-preview-cleanup'));

      await waitFor(() => {
        expect(screen.queryByText(/Skipped \(too young\):/)).not.toBeInTheDocument();
        expect(screen.queryByText(/Skipped \(size limit\):/)).not.toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('sliders have proper aria attributes', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const minAgeSlider = screen.getByTestId('min-age-hours-slider');
      expect(minAgeSlider).toHaveAttribute('aria-label', 'Minimum File Age');
      expect(minAgeSlider).toHaveAttribute('aria-valuemin', '1');
      expect(minAgeSlider).toHaveAttribute('aria-valuemax', '720');

      const maxDeleteSlider = screen.getByTestId('max-delete-gb-slider');
      expect(maxDeleteSlider).toHaveAttribute('aria-label', 'Maximum Deletion Size');
      expect(maxDeleteSlider).toHaveAttribute('aria-valuemin', '0.1');
      expect(maxDeleteSlider).toHaveAttribute('aria-valuemax', '100');
    });

    it('buttons are focusable and have descriptive text', () => {
      renderWithProviders(<OrphanCleanupPanel />);

      const previewButton = screen.getByTestId('btn-preview-cleanup');
      const cleanupButton = screen.getByTestId('btn-run-cleanup');

      expect(previewButton).not.toBeDisabled();
      expect(cleanupButton).not.toBeDisabled();
      expect(previewButton).toHaveTextContent('Preview');
      expect(cleanupButton).toHaveTextContent('Clean Up');
    });
  });
});
