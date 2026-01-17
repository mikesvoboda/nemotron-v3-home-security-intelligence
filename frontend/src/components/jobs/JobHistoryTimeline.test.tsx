/**
 * Tests for JobHistoryTimeline component (NEM-2713)
 *
 * JobHistoryTimeline is a collapsible section that displays the complete
 * state transition history of a job in a vertical timeline format.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import JobHistoryTimeline from './JobHistoryTimeline';
import * as api from '../../services/api';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchJobHistory: vi.fn(),
  };
});

describe('JobHistoryTimeline', () => {
  const mockHistory: api.JobHistoryResponse = {
    job_id: '142',
    job_type: 'export',
    status: 'completed',
    created_at: '2026-01-17T10:30:00Z',
    started_at: '2026-01-17T10:30:05Z',
    completed_at: '2026-01-17T10:32:00Z',
    transitions: [
      {
        from: null,
        to: 'pending',
        at: '2026-01-17T10:30:00Z',
        triggered_by: 'api',
        details: null,
      },
      {
        from: 'pending',
        to: 'running',
        at: '2026-01-17T10:30:05Z',
        triggered_by: 'worker',
        details: { worker_id: 'worker-1' },
      },
      {
        from: 'running',
        to: 'completed',
        at: '2026-01-17T10:32:00Z',
        triggered_by: 'worker',
        details: null,
      },
    ],
    attempts: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the collapsible section with History title', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(screen.getByText(/history/i)).toBeInTheDocument();
      });
    });

    it('renders all transitions when expanded', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" defaultOpen />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(screen.getByText(/pending/i)).toBeInTheDocument();
        expect(screen.getAllByText(/running/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
      });
    });

    it('shows all timeline entries', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" defaultOpen />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        const entries = screen.getAllByTestId('timeline-entry');
        expect(entries).toHaveLength(3);
      });
    });
  });

  describe('collapsible behavior', () => {
    it('starts collapsed by default', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      // Wait for data to load first
      await waitFor(() => {
        expect(api.fetchJobHistory).toHaveBeenCalled();
      });

      // Timeline entries should not be visible when collapsed
      await waitFor(() => {
        expect(screen.queryByTestId('timeline-entry')).not.toBeInTheDocument();
      });
    });

    it('starts expanded when defaultOpen is true', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" defaultOpen />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(screen.getAllByTestId('timeline-entry')).toHaveLength(3);
      });
    });

    it('toggles visibility when header is clicked', async () => {
      const user = userEvent.setup();
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      // Wait for data to load
      await waitFor(() => {
        expect(api.fetchJobHistory).toHaveBeenCalled();
      });

      // Find and click the toggle button
      const toggleButton = screen.getByRole('button', { name: /history/i });
      await user.click(toggleButton);

      // Should now be visible
      await waitFor(() => {
        expect(screen.getAllByTestId('timeline-entry')).toHaveLength(3);
      });
    });
  });

  describe('summary badge', () => {
    it('shows transition count in summary when collapsed', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // Should show something like "3 transitions" or "3 steps"
        expect(screen.getByText(/3/)).toBeInTheDocument();
      });
    });

    it('shows current status in summary', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // Should show the final status somehow
        expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
      });
    });
  });

  describe('loading state', () => {
    it('shows loading indicator while fetching', () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      render(<JobHistoryTimeline jobId="142" defaultOpen />, {
        wrapper: createQueryWrapper(),
      });

      expect(screen.getByTestId('timeline-loading')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no transitions exist', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockHistory,
        transitions: [],
      });

      render(<JobHistoryTimeline jobId="142" defaultOpen />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(screen.getByText(/no history/i)).toBeInTheDocument();
      });
    });
  });

  describe('error state', () => {
    it('shows error message when fetch fails', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch')
      );

      render(<JobHistoryTimeline jobId="142" defaultOpen />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          // Should show the error message
          expect(screen.getByText(/Failed to load job history/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('accessibility', () => {
    it('has accessible toggle button', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        const button = screen.getByRole('button');
        expect(button).toHaveAttribute('aria-expanded');
      });
    });
  });

  describe('data fetching', () => {
    it('fetches history for the correct job ID', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchJobHistory).toHaveBeenCalledWith('142');
      });
    });

    it('refetches when jobId changes', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      const { rerender } = render(<JobHistoryTimeline jobId="142" />, {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchJobHistory).toHaveBeenCalledWith('142');
      });

      rerender(<JobHistoryTimeline jobId="143" />);

      await waitFor(() => {
        expect(api.fetchJobHistory).toHaveBeenCalledWith('143');
      });
    });
  });
});
