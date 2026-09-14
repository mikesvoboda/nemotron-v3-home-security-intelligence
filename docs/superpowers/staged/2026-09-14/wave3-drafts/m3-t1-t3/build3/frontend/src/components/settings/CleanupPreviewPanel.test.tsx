import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';

import CleanupPreviewPanel from './CleanupPreviewPanel';

import type { UseCleanupPreviewMutationReturn, UseCleanupMutationReturn } from '../../hooks';
import type { CleanupResponse } from '../../services/api';

// Mock cleanup response data
const mockPreviewResponse: CleanupResponse = {
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

const mockCleanupResponse: CleanupResponse = {
  ...mockPreviewResponse,
  dry_run: false,
};

const emptyPreviewResponse: CleanupResponse = {
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

// Create mock function types
let mockPreview: Mock;
let mockCleanup: Mock;
let mockResetPreview: Mock;
let mockResetCleanup: Mock;

// Mock hook return values
let mockPreviewMutationReturn: UseCleanupPreviewMutationReturn;
let mockCleanupMutationReturn: UseCleanupMutationReturn;

// Mock the hooks
vi.mock('../../hooks', () => ({
  useCleanupPreviewMutation: () => mockPreviewMutationReturn,
  useCleanupMutation: () => mockCleanupMutationReturn,
}));

describe('CleanupPreviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });

    // Reset mock functions
    mockPreview = vi.fn();
    mockCleanup = vi.fn();
    mockResetPreview = vi.fn();
    mockResetCleanup = vi.fn();

    // Default mock returns (idle state)
    mockPreviewMutationReturn = {
      preview: mockPreview,
      previewData: undefined,
      isPending: false,
      error: null,
      reset: mockResetPreview,
      mutation: {} as UseCleanupPreviewMutationReturn['mutation'],
    };

    mockCleanupMutationReturn = {
      cleanup: mockCleanup,
      cleanupData: undefined,
      isPending: false,
      error: null,
      reset: mockResetCleanup,
      mutation: {} as UseCleanupMutationReturn['mutation'],
    };
  });

  afterEach(() => {
    vi.useRealTimers();
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
    it('shows loading state when fetching preview', () => {
      mockPreviewMutationReturn.isPending = true;

      render(<CleanupPreviewPanel />);

      expect(screen.getByRole('button', { name: /Calculating Preview/i })).toBeDisabled();
    });

    it('calls preview mutation when preview button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreview.mockResolvedValue(mockPreviewResponse);

      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      await user.click(previewButton);

      expect(mockPreview).toHaveBeenCalledTimes(1);
      expect(mockResetCleanup).toHaveBeenCalled(); // Clear previous cleanup result
    });

    it('displays preview results when data exists', () => {
      mockPreviewMutationReturn.previewData = mockPreviewResponse;

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Preview Results')).toBeInTheDocument();
      expect(screen.getByText('Retention: 30 days')).toBeInTheDocument();
      expect(screen.getAllByText('15')).toHaveLength(1); // events
      expect(screen.getAllByText('89')).toHaveLength(2); // detections and thumbnails
      expect(screen.getByText('2,880')).toBeInTheDocument(); // GPU stats
      expect(screen.getByText('150')).toBeInTheDocument(); // logs
      expect(screen.getByText('500.00 MB')).toBeInTheDocument(); // space reclaimed
    });

    it('displays message when no data to clean up', () => {
      mockPreviewMutationReturn.previewData = emptyPreviewResponse;

      render(<CleanupPreviewPanel />);

      expect(screen.getByText(/No data to clean up/i)).toBeInTheDocument();
    });

    it('displays error when preview fails', () => {
      mockPreviewMutationReturn.error = new Error('Network error');

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('allows clearing preview', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreviewMutationReturn.previewData = mockPreviewResponse;

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Preview Results')).toBeInTheDocument();

      // Clear preview
      const clearButton = screen.getByRole('button', { name: /Clear Preview/i });
      await user.click(clearButton);

      expect(mockResetPreview).toHaveBeenCalled();
    });
  });

  describe('Cleanup Functionality', () => {
    it('shows confirmation dialog when proceeding with cleanup', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreviewMutationReturn.previewData = mockPreviewResponse;

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Preview Results')).toBeInTheDocument();

      // Click proceed button
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      expect(screen.getByText('Confirm Cleanup')).toBeInTheDocument();
      expect(screen.getByText(/This action cannot be undone/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Yes, Delete Data/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('allows canceling cleanup confirmation', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreviewMutationReturn.previewData = mockPreviewResponse;

      render(<CleanupPreviewPanel />);

      // Click proceed button
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      expect(screen.getByText('Confirm Cleanup')).toBeInTheDocument();

      // Cancel confirmation
      const cancelButton = screen.getByRole('button', { name: /Cancel/i });
      await user.click(cancelButton);

      expect(screen.queryByText('Confirm Cleanup')).not.toBeInTheDocument();
      expect(screen.getByText('Preview Results')).toBeInTheDocument();
    });

    it('calls cleanup mutation when confirmed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreviewMutationReturn.previewData = mockPreviewResponse;
      mockCleanup.mockResolvedValue(mockCleanupResponse);

      render(<CleanupPreviewPanel />);

      // Proceed with cleanup
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Confirm cleanup
      const confirmButton = screen.getByRole('button', { name: /Yes, Delete Data/i });
      await user.click(confirmButton);

      expect(mockCleanup).toHaveBeenCalledTimes(1);
      expect(mockResetPreview).toHaveBeenCalled(); // Preview should be cleared
    });

    it('displays cleanup complete result', () => {
      mockCleanupMutationReturn.cleanupData = mockCleanupResponse;

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Cleanup Complete')).toBeInTheDocument();
      expect(screen.getByText('Retention: 30 days')).toBeInTheDocument();
    });

    it('displays error when cleanup fails', () => {
      mockCleanupMutationReturn.error = new Error('Cleanup failed');

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Cleanup failed')).toBeInTheDocument();
    });

    it('shows cleaning state when cleanup is in progress', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreviewMutationReturn.previewData = mockPreviewResponse;
      mockCleanupMutationReturn.isPending = true;

      render(<CleanupPreviewPanel />);

      // Open confirmation dialog
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Confirm button should show loading state
      expect(screen.getByRole('button', { name: /Deleting/i })).toBeDisabled();
    });

    it('clears cleanup result after 10 seconds', async () => {
      mockCleanupMutationReturn.cleanupData = mockCleanupResponse;

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Cleanup Complete')).toBeInTheDocument();

      // Advance time by 10 seconds
      await vi.advanceTimersByTimeAsync(10000);

      // resetCleanup should have been called
      expect(mockResetCleanup).toHaveBeenCalled();
    });
  });

  describe('Byte Formatting', () => {
    it('does not show space section when space_reclaimed is 0', () => {
      mockPreviewMutationReturn.previewData = {
        ...mockPreviewResponse,
        space_reclaimed: 0,
      };

      render(<CleanupPreviewPanel />);

      expect(screen.queryByText(/Estimated Space to Reclaim/i)).not.toBeInTheDocument();
    });

    it.each([
      [500, '500.00 B'],
      [1024, '1.00 KB'],
      [1048576, '1.00 MB'],
      [1073741824, '1.00 GB'],
      [524288000, '500.00 MB'],
      [2147483648, '2.00 GB'],
    ])('formats %d bytes as %s', (bytes, expected) => {
      mockPreviewMutationReturn.previewData = {
        ...mockPreviewResponse,
        space_reclaimed: bytes,
      };

      render(<CleanupPreviewPanel />);

      expect(screen.getByText(expected)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', () => {
      render(<CleanupPreviewPanel />);

      const previewButton = screen.getByRole('button', { name: /Preview Cleanup/i });
      expect(previewButton).toBeInTheDocument();
    });

    it('disables buttons during loading', () => {
      mockPreviewMutationReturn.isPending = true;

      render(<CleanupPreviewPanel />);

      const loadingButton = screen.getByRole('button', { name: /Calculating Preview/i });
      expect(loadingButton).toBeDisabled();
    });

    it('hides confirmation dialog after cleanup starts', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      mockPreviewMutationReturn.previewData = mockPreviewResponse;
      mockCleanup.mockResolvedValue(mockCleanupResponse);

      render(<CleanupPreviewPanel />);

      // Proceed with cleanup
      const proceedButton = screen.getByRole('button', { name: /Proceed with Cleanup/i });
      await user.click(proceedButton);

      // Verify confirmation is shown
      expect(screen.getByText('Confirm Cleanup')).toBeInTheDocument();

      // Confirm cleanup
      const confirmButton = screen.getByRole('button', { name: /Yes, Delete Data/i });
      await user.click(confirmButton);

      // Confirmation dialog should be hidden (because setShowConfirm(false) is called immediately)
      expect(screen.queryByText('Confirm Cleanup')).not.toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('displays preview error when preview mutation fails', () => {
      mockPreviewMutationReturn.error = new Error('Preview network error');

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Preview network error')).toBeInTheDocument();
    });

    it('displays cleanup error when cleanup mutation fails', () => {
      mockCleanupMutationReturn.error = new Error('Cleanup network error');

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Cleanup network error')).toBeInTheDocument();
    });

    it('prioritizes preview error over cleanup error', () => {
      mockPreviewMutationReturn.error = new Error('Preview error');
      mockCleanupMutationReturn.error = new Error('Cleanup error');

      render(<CleanupPreviewPanel />);

      expect(screen.getByText('Preview error')).toBeInTheDocument();
      expect(screen.queryByText('Cleanup error')).not.toBeInTheDocument();
    });
  });
});
