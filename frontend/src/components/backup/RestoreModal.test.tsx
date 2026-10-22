import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RestoreModal from './RestoreModal';
import * as useBackupHooks from '../../hooks/useBackup';

import type { RestoreJob } from '../../types/backup';

vi.mock('../../hooks/useBackup', async () => {
  const actual = await vi.importActual<typeof useBackupHooks>('../../hooks/useBackup');
  return {
    ...actual,
    useStartRestore: vi.fn(),
    useRestoreJob: vi.fn(),
  };
});

const mockedUseStartRestore = vi.mocked(useBackupHooks.useStartRestore);
const mockedUseRestoreJob = vi.mocked(useBackupHooks.useRestoreJob);

describe('RestoreModal', () => {
  const mockStartRestore = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnRestoreComplete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseStartRestore.mockReturnValue({
      mutation: {} as never,
      startRestore: mockStartRestore,
      isLoading: false,
      error: null,
    });
    mockedUseRestoreJob.mockReturnValue({
      data: undefined,
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it('renders upload state with warning banner and file dropzone when open', () => {
    render(<RestoreModal isOpen={true} onClose={mockOnClose} />);

    expect(screen.getByText('Restore from Backup')).toBeInTheDocument();
    expect(screen.getByTestId('restore-warning')).toHaveTextContent(
      /safety backup is saved first/i
    );
    expect(screen.getByTestId('file-dropzone')).toBeInTheDocument();
  });

  it('shows safety backup link, per-table summary, added rows, cleared links, and skipped tables on completion', async () => {
    const completedJob: RestoreJob = {
      id: 'restore-job-1',
      status: 'completed',
      progress: {
        total_tables: 12,
        completed_tables: 12,
        progress_percent: 100,
        current_step: 'Complete',
      },
      backup_id: 'source-backup-1',
      backup_created_at: '2026-10-22T01:00:00Z',
      created_at: '2026-10-22T01:05:00Z',
      started_at: '2026-10-22T01:05:01Z',
      completed_at: '2026-10-22T01:05:05Z',
      items_restored: {
        cameras: 4,
        household_members: 2,
      },
      safety_backup_id: 'safety-job-1',
      tables: {
        cameras: { updated: 3, inserted: 1, replaced: 0, kept: 1 },
        household_members: { updated: 1, inserted: 1, replaced: 0, kept: 0 },
      },
      added_rows: {
        cameras: ['Side Gate Camera'],
        household_members: ['Alex Guest'],
      },
      cleared_known_person_links: ['Alex Guest'],
      skipped_tables: ['events', 'alerts'],
      same_installation: false,
      error_message: null,
    };

    mockStartRestore.mockResolvedValueOnce({
      job_id: 'restore-job-1',
      status: 'pending',
      message: 'started',
    });
    mockedUseRestoreJob.mockReturnValue({
      data: completedJob,
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    render(
      <RestoreModal isOpen={true} onClose={mockOnClose} onRestoreComplete={mockOnRestoreComplete} />
    );

    const file = new File(['zip-bytes'], 'backup.zip', { type: 'application/zip' });
    const fileInput = screen.getByTestId('file-input');
    await userEvent.upload(fileInput, file);

    await waitFor(() => {
      expect(screen.getByTestId('complete-state')).toBeInTheDocument();
    });

    expect(mockOnRestoreComplete).toHaveBeenCalledTimes(1);

    // Safety backup banner + download/restore links
    expect(screen.getByTestId('safety-backup-banner')).toHaveTextContent('safety-j');
    expect(screen.getByTestId('safety-backup-download-link')).toHaveAttribute(
      'href',
      '/api/backup/safety-job-1/download' // pragma: allowlist secret
    );
    expect(screen.getByTestId('safety-backup-restore-link')).toBeInTheDocument();

    // Per-table summary ("restored 4 cameras, added 1, kept 1 not in this backup")
    expect(screen.getByTestId('restore-table-summary-cameras')).toHaveTextContent(
      'restored 4 cameras, added 1, kept 1 not in this backup'
    );

    // Added rows by name
    expect(screen.getByTestId('restore-added-rows')).toHaveTextContent('Side Gate Camera');
    expect(screen.getByTestId('restore-added-rows')).toHaveTextContent('Alex Guest');

    // Cleared known-person links by name
    expect(screen.getByTestId('restore-cleared-links')).toHaveTextContent('Alex Guest');

    // Skipped legacy tables
    expect(screen.getByTestId('restore-skipped-tables')).toHaveTextContent('events, alerts');
  });

  it('shows failure detail when restore job fails and resets on Try Again', async () => {
    const failedJob: RestoreJob = {
      id: 'restore-job-fail',
      status: 'failed',
      progress: {
        total_tables: 12,
        completed_tables: 3,
        progress_percent: 40,
        current_step: 'Restoring cameras...',
      },
      backup_id: 'bad-backup',
      backup_created_at: '2026-10-22T01:00:00Z',
      created_at: '2026-10-22T01:05:00Z',
      started_at: '2026-10-22T01:05:01Z',
      completed_at: '2026-10-22T01:05:03Z',
      items_restored: null,
      error_message: "Unknown column(s) ['bogus'] in table 'cameras' at record 0",
    };

    mockStartRestore.mockResolvedValueOnce({
      job_id: 'restore-job-fail',
      status: 'pending',
      message: 'started',
    });
    mockedUseRestoreJob.mockReturnValue({
      data: failedJob,
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<RestoreModal isOpen={true} onClose={mockOnClose} />);

    const file = new File(['zip-bytes'], 'bad.zip', { type: 'application/zip' });
    await userEvent.upload(screen.getByTestId('file-input'), file);

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
    });

    expect(screen.getByTestId('restore-error-detail')).toHaveTextContent(
      "Unknown column(s) ['bogus'] in table 'cameras' at record 0"
    );

    await userEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(screen.getByTestId('file-dropzone')).toBeInTheDocument();
  });
});
