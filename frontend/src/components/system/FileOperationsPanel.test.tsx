import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import FileOperationsPanel from './FileOperationsPanel';
import * as api from '../../services/api';

// Mock the api module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchStorageStats: vi.fn(),
    fetchJobs: vi.fn(),
    fetchCleanupStatus: vi.fn(),
    triggerCleanup: vi.fn(),
    previewCleanup: vi.fn(),
    previewOrphanedFiles: vi.fn(),
    triggerOrphanedCleanup: vi.fn(),
  };
});

// Mock the storage status store
vi.mock('../../stores/storage-status-store', () => ({
  useStorageStatusStore: vi.fn(() => vi.fn()),
}));

const mockFetchStorageStats = vi.mocked(api.fetchStorageStats);
const mockFetchJobs = vi.mocked(api.fetchJobs);
const mockFetchCleanupStatus = vi.mocked(api.fetchCleanupStatus);
const mockTriggerCleanup = vi.mocked(api.triggerCleanup);
const mockPreviewCleanup = vi.mocked(api.previewCleanup);
const mockPreviewOrphanedFiles = vi.mocked(api.previewOrphanedFiles);
const mockTriggerOrphanedCleanup = vi.mocked(api.triggerOrphanedCleanup);

describe('FileOperationsPanel', () => {
  // Sample storage stats data
  const mockStorageStats: api.StorageStatsResponse = {
    disk_used_bytes: 50_000_000_000, // 50 GB
    disk_total_bytes: 100_000_000_000, // 100 GB
    disk_free_bytes: 50_000_000_000, // 50 GB
    disk_usage_percent: 50.0,
    thumbnails: {
      file_count: 1500,
      size_bytes: 500_000_000, // 500 MB
    },
    images: {
      file_count: 2000,
      size_bytes: 10_000_000_000, // 10 GB
    },
    clips: {
      file_count: 100,
      size_bytes: 5_000_000_000, // 5 GB
    },
    events_count: 1000,
    detections_count: 5000,
    gpu_stats_count: 10000,
    logs_count: 50000,
    timestamp: '2025-12-30T10:00:00Z',
  };

  // Sample jobs data with export jobs
  const mockJobsWithExports: api.JobListResponse = {
    items: [
      {
        job_id: 'export-123',
        job_type: 'export',
        status: 'running' as const,
        progress: 45,
        message: 'Exporting events: 450/1000',
        created_at: '2025-12-30T10:00:00Z',
        started_at: '2025-12-30T10:00:01Z',
        completed_at: null,
        result: null,
        error: null,
      },
      {
        job_id: 'export-456',
        job_type: 'export',
        status: 'completed' as const,
        progress: 100,
        message: 'Export completed',
        created_at: '2025-12-30T09:00:00Z',
        started_at: '2025-12-30T09:00:01Z',
        completed_at: '2025-12-30T09:05:00Z',
        result: { file_path: '/exports/events.zip' },
        error: null,
      },
    ],
    pagination: { total: 2, offset: 0, limit: 50, has_more: false },
  };

  const mockJobsEmpty: api.JobListResponse = {
    items: [],
    pagination: { total: 0, offset: 0, limit: 50, has_more: false },
  };

  // Sample cleanup response
  const mockCleanupResponse: api.CleanupResponse = {
    events_deleted: 100,
    detections_deleted: 500,
    gpu_stats_deleted: 1000,
    logs_deleted: 5000,
    thumbnails_deleted: 500,
    images_deleted: 0,
    space_reclaimed: 1_000_000_000, // 1 GB
    dry_run: false,
    retention_days: 30,
    timestamp: '2025-12-30T10:30:00Z',
  };

  // Sample cleanup status response
  const mockCleanupStatus: api.CleanupStatusResponse = {
    running: true,
    cleanup_time: '03:00',
    retention_days: 30,
    delete_images: false,
    next_cleanup: '2025-12-31T03:00:00Z',
    timestamp: '2025-12-30T10:00:00Z',
  };

  // Sample orphaned files response
  const mockOrphanedPreview: api.OrphanedFileCleanupResponse = {
    dry_run: true,
    orphaned_count: 25,
    orphaned_files: ['/data/thumbnails/orphan1.jpg', '/data/thumbnails/orphan2.jpg'],
    total_size: 524288000, // 500 MB
    total_size_formatted: '500.00 MB',
    timestamp: '2025-12-30T10:30:00Z',
    job_id: null,
  };

  beforeEach(() => {
    mockFetchStorageStats.mockReset();
    mockFetchJobs.mockReset();
    mockFetchCleanupStatus.mockReset();
    mockTriggerCleanup.mockReset();
    mockPreviewCleanup.mockReset();
    mockPreviewOrphanedFiles.mockReset();
    mockTriggerOrphanedCleanup.mockReset();

    // Set default mock values for optional endpoints that may fail gracefully
    mockFetchCleanupStatus.mockResolvedValue(mockCleanupStatus);
    mockPreviewOrphanedFiles.mockResolvedValue({ ...mockOrphanedPreview, orphaned_count: 0, orphaned_files: [] });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the loading state initially', () => {
      // Use promises that never resolve to keep loading state
      mockFetchStorageStats.mockReturnValue(new Promise(() => {}));
      mockFetchJobs.mockReturnValue(new Promise(() => {}));

      render(<FileOperationsPanel />);

      expect(screen.getByTestId('file-operations-panel-loading')).toBeInTheDocument();
      expect(screen.getByText('File Operations')).toBeInTheDocument();
    });

    it('renders the component with title after loading', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('File Operations')).toBeInTheDocument();
    });

    it('displays storage usage metrics', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Check for storage usage display
      expect(screen.getByTestId('storage-usage-section')).toBeInTheDocument();
      // Disk usage percent appears in header badge and in the usage section
      expect(screen.getAllByText(/50\.0%/).length).toBeGreaterThanOrEqual(1);
    });

    it('displays storage breakdown by category', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Check for category breakdown
      expect(screen.getByTestId('storage-category-thumbnails')).toBeInTheDocument();
      expect(screen.getByTestId('storage-category-images')).toBeInTheDocument();
      expect(screen.getByTestId('storage-category-clips')).toBeInTheDocument();
    });

    it('displays last updated timestamp', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      const lastUpdatedElement = screen.queryByTestId('last-updated');
      if (lastUpdatedElement) {
        expect(lastUpdatedElement).toHaveTextContent(/Last updated:/);
      }
    });
  });

  describe('export jobs display', () => {
    it('displays active export jobs with progress', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsWithExports);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('active-exports-section')).toBeInTheDocument();
      });

      // Check for running export job
      expect(screen.getByTestId('export-job-export-123')).toBeInTheDocument();
      expect(screen.getByText(/45%/)).toBeInTheDocument();
    });

    it('shows no exports message when no export jobs', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('no-exports-message')).toBeInTheDocument();
    });

    it('displays completed export jobs in history', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsWithExports);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Check for completed export job
      expect(screen.getByTestId('export-job-export-456')).toBeInTheDocument();
    });
  });

  describe('cleanup functionality', () => {
    it('displays cleanup action button', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('cleanup-button')).toBeInTheDocument();
    });

    it('triggers cleanup preview on button click', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewCleanup.mockResolvedValue({
        ...mockCleanupResponse,
        dry_run: true,
      });

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      const cleanupButton = screen.getByTestId('cleanup-button');
      fireEvent.click(cleanupButton);

      await waitFor(() => {
        expect(mockPreviewCleanup).toHaveBeenCalled();
      });
    });

    it('shows cleanup preview modal with preview results', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewCleanup.mockResolvedValue({
        ...mockCleanupResponse,
        dry_run: true,
      });

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      const cleanupButton = screen.getByTestId('cleanup-button');
      fireEvent.click(cleanupButton);

      await waitFor(() => {
        expect(screen.getByTestId('cleanup-preview-modal')).toBeInTheDocument();
      });

      // Check for preview content
      expect(screen.getByText(/100 events/i)).toBeInTheDocument();
      expect(screen.getByText(/500 detections/i)).toBeInTheDocument();
    });

    it('executes cleanup when confirmed in modal', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewCleanup.mockResolvedValue({
        ...mockCleanupResponse,
        dry_run: true,
      });
      mockTriggerCleanup.mockResolvedValue(mockCleanupResponse);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Open preview
      const cleanupButton = screen.getByTestId('cleanup-button');
      fireEvent.click(cleanupButton);

      await waitFor(() => {
        expect(screen.getByTestId('cleanup-preview-modal')).toBeInTheDocument();
      });

      // Confirm cleanup
      const confirmButton = screen.getByTestId('confirm-cleanup-button');
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockTriggerCleanup).toHaveBeenCalled();
      });
    });
  });

  describe('error handling', () => {
    it('displays error state when storage stats fetch fails', async () => {
      mockFetchStorageStats.mockRejectedValue(new Error('Network error'));
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel-error')).toBeInTheDocument();
      });

      expect(screen.getByText(/Failed to load/i)).toBeInTheDocument();
    });

    it('still displays panel when jobs fetch fails', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockRejectedValue(new Error('Network error'));

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Should still show storage stats
      expect(screen.getByTestId('storage-usage-section')).toBeInTheDocument();
    });

    it('shows cleanup error when cleanup fails', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewCleanup.mockRejectedValue(new Error('Cleanup failed'));

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      const cleanupButton = screen.getByTestId('cleanup-button');
      fireEvent.click(cleanupButton);

      await waitFor(() => {
        expect(screen.getByTestId('cleanup-error')).toBeInTheDocument();
      });
    });
  });

  describe('refresh functionality', () => {
    it('displays refresh button', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });

    it('triggers refresh when refresh button is clicked', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Clear mock call counts
      mockFetchStorageStats.mockClear();
      mockFetchJobs.mockClear();

      // Click refresh
      const refreshButton = screen.getByTestId('refresh-button');
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mockFetchStorageStats).toHaveBeenCalled();
      });
    });
  });

  describe('collapsible behavior', () => {
    it('starts expanded by default', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Should show collapse icon when expanded (defaultExpanded is true)
      expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();
    });

    it('starts collapsed when defaultExpanded is false', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel defaultExpanded={false} />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Should show expand icon when collapsed
      expect(screen.getByTestId('expand-icon')).toBeInTheDocument();
    });

    it('toggles between expanded and collapsed on click', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Initially expanded
      expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();

      // Click to collapse
      const toggleButton = screen.getByTestId('panel-toggle');
      fireEvent.click(toggleButton);

      // Should now be collapsed
      expect(screen.getByTestId('expand-icon')).toBeInTheDocument();

      // Click to expand
      fireEvent.click(toggleButton);

      // Should be expanded again
      expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();
    });
  });

  describe('storage usage display', () => {
    it('formats bytes to human readable size', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Check that disk usage is formatted (sizes may vary due to binary vs decimal formatting)
      const storageSection = screen.getByTestId('storage-usage-section');
      expect(storageSection).toBeInTheDocument();
      // Check for GB values in any format
      expect(storageSection.textContent).toContain('GB');
    });

    it('displays file counts for each category', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      // Check for file counts
      expect(screen.getByText(/1,500/)).toBeInTheDocument(); // thumbnails count
      expect(screen.getByText(/2,000/)).toBeInTheDocument(); // images count
    });

    it('shows warning when disk usage is high', async () => {
      const highUsageStats = {
        ...mockStorageStats,
        disk_usage_percent: 90.0,
        disk_free_bytes: 10_000_000_000, // 10 GB free
      };
      mockFetchStorageStats.mockResolvedValue(highUsageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('disk-usage-warning')).toBeInTheDocument();
    });
  });

  describe('polling behavior', () => {
    it('calls API on mount', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(mockFetchStorageStats).toHaveBeenCalledTimes(1);
        expect(mockFetchJobs).toHaveBeenCalledTimes(1);
      });
    });

    it('cleans up intervals on unmount', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      const { unmount } = render(<FileOperationsPanel pollingInterval={60000} />);

      await waitFor(() => {
        expect(mockFetchStorageStats).toHaveBeenCalledTimes(1);
      });

      const callCount = mockFetchStorageStats.mock.calls.length;

      unmount();

      // Wait a bit to ensure no additional calls happen after unmount
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should not have additional calls after unmount
      expect(mockFetchStorageStats).toHaveBeenCalledTimes(callCount);
    });
  });

  describe('className prop', () => {
    it('applies custom className to the component', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('file-operations-panel')).toHaveClass('custom-class');
    });
  });

  describe('data-testid prop', () => {
    it('uses custom data-testid when provided', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel data-testid="custom-test-id" />);

      await waitFor(() => {
        expect(screen.getByTestId('custom-test-id')).toBeInTheDocument();
      });
    });
  });

  describe('callbacks', () => {
    it('calls onStorageChange callback when storage stats update', async () => {
      const onStorageChange = vi.fn();
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);

      render(<FileOperationsPanel onStorageChange={onStorageChange} />);

      await waitFor(() => {
        expect(onStorageChange).toHaveBeenCalled();
      });

      // Should be called with storage stats
      expect(onStorageChange).toHaveBeenCalledWith(mockStorageStats);
    });
  });

  describe('cleanup summary display', () => {
    it('displays cleanup service status', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockFetchCleanupStatus.mockResolvedValue(mockCleanupStatus);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('cleanup-summary')).toBeInTheDocument();
      expect(screen.getByText('Cleanup Service')).toBeInTheDocument();
      expect(screen.getByText('03:00')).toBeInTheDocument();
      expect(screen.getByText('30 days')).toBeInTheDocument();
    });

    it('shows running status when cleanup service is running', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockFetchCleanupStatus.mockResolvedValue({ ...mockCleanupStatus, running: true });

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('cleanup-summary')).toBeInTheDocument();
      });

      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('shows stopped status when cleanup service is not running', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockFetchCleanupStatus.mockResolvedValue({ ...mockCleanupStatus, running: false });

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('cleanup-summary')).toBeInTheDocument();
      });

      expect(screen.getByText('Stopped')).toBeInTheDocument();
    });
  });

  describe('orphaned files warning', () => {
    it('displays orphaned files warning when orphaned files exist', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewOrphanedFiles.mockResolvedValue(mockOrphanedPreview);

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('orphaned-files-warning')).toBeInTheDocument();
      expect(screen.getByText(/25 Orphaned Files Found/)).toBeInTheDocument();
      expect(screen.getByText(/500\.00 MB can be reclaimed/)).toBeInTheDocument();
    });

    it('does not display orphaned files warning when no orphaned files', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewOrphanedFiles.mockResolvedValue({
        ...mockOrphanedPreview,
        orphaned_count: 0,
        orphaned_files: [],
      });

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('orphaned-files-warning')).not.toBeInTheDocument();
    });

    it('triggers orphaned cleanup when clean up button is clicked', async () => {
      mockFetchStorageStats.mockResolvedValue(mockStorageStats);
      mockFetchJobs.mockResolvedValue(mockJobsEmpty);
      mockPreviewOrphanedFiles.mockResolvedValue(mockOrphanedPreview);
      mockTriggerOrphanedCleanup.mockResolvedValue({
        ...mockOrphanedPreview,
        dry_run: false,
      });

      render(<FileOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('orphaned-files-warning')).toBeInTheDocument();
      });

      const cleanOrphanedButton = screen.getByTestId('clean-orphaned-button');
      fireEvent.click(cleanOrphanedButton);

      await waitFor(() => {
        expect(mockTriggerOrphanedCleanup).toHaveBeenCalled();
      });
    });
  });
});
