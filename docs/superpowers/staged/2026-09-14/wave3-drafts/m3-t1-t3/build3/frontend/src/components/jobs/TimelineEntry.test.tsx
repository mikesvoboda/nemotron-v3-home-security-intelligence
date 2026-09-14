/**
 * Tests for TimelineEntry component (NEM-2713)
 *
 * TimelineEntry displays a single state transition in the job history timeline.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import TimelineEntry from './TimelineEntry';

describe('TimelineEntry', () => {
  const mockTransition = {
    from: 'pending',
    to: 'running',
    at: '2026-01-17T10:30:05Z',
    triggered_by: 'worker',
    details: { worker_id: 'worker-1' },
  };

  describe('rendering', () => {
    it('renders the transition', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      expect(screen.getByTestId('timeline-entry')).toBeInTheDocument();
    });

    it('displays the timestamp', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      // Should format the timestamp nicely - the time may be localized, so check for seconds part
      expect(screen.getByText(/30:05/)).toBeInTheDocument();
    });

    it('displays the status', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      expect(screen.getByText(/running/i)).toBeInTheDocument();
    });

    it('renders StatusDot component', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      expect(screen.getByTestId('status-dot')).toBeInTheDocument();
    });
  });

  describe('connector line', () => {
    it('renders connector line when not the last entry', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      expect(screen.getByTestId('timeline-connector')).toBeInTheDocument();
    });

    it('does not render connector line when it is the last entry', () => {
      render(<TimelineEntry transition={mockTransition} isLast={true} />);
      expect(screen.queryByTestId('timeline-connector')).not.toBeInTheDocument();
    });
  });

  describe('transition message', () => {
    it('shows "Job created" message for initial transition (from null)', () => {
      const initialTransition = {
        from: null,
        to: 'pending',
        at: '2026-01-17T10:30:00Z',
        triggered_by: 'api',
        details: null,
      };
      render(<TimelineEntry transition={initialTransition} isLast={false} />);
      expect(screen.getByText(/created/i)).toBeInTheDocument();
    });

    it('shows appropriate message for state change', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      // Should show something like "Started Processing" or similar
      expect(screen.getByText(/started processing/i)).toBeInTheDocument();
    });

    it('displays custom message when provided', () => {
      const transitionWithMessage = {
        ...mockTransition,
        details: { message: 'Worker picked up job' },
      };
      render(<TimelineEntry transition={transitionWithMessage} isLast={false} />);
      expect(screen.getByText(/worker picked up job/i)).toBeInTheDocument();
    });
  });

  describe('status labels', () => {
    it('formats pending status correctly', () => {
      const pendingTransition = {
        from: null,
        to: 'pending',
        at: '2026-01-17T10:30:00Z',
        triggered_by: 'api',
        details: null,
      };
      render(<TimelineEntry transition={pendingTransition} isLast={false} />);
      // Status label should show "Pending"
      expect(screen.getAllByText(/pending/i).length).toBeGreaterThan(0);
    });

    it('formats completed status correctly', () => {
      const completedTransition = {
        from: 'running',
        to: 'completed',
        at: '2026-01-17T10:32:00Z',
        triggered_by: 'worker',
        details: null,
      };
      render(<TimelineEntry transition={completedTransition} isLast={true} />);
      // Status label should show "Completed"
      expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
    });

    it('formats failed status correctly', () => {
      const failedTransition = {
        from: 'running',
        to: 'failed',
        at: '2026-01-17T10:32:00Z',
        triggered_by: 'worker',
        details: { error: 'Connection timeout' },
      };
      render(<TimelineEntry transition={failedTransition} isLast={true} />);
      // Status label should show "Failed"
      expect(screen.getAllByText(/failed/i).length).toBeGreaterThan(0);
    });
  });

  describe('error details', () => {
    it('displays error message when present in failed transition', () => {
      const failedTransition = {
        from: 'running',
        to: 'failed',
        at: '2026-01-17T10:32:00Z',
        triggered_by: 'worker',
        details: { error: 'Connection timeout after 3 retries' },
      };
      render(<TimelineEntry transition={failedTransition} isLast={true} />);
      expect(screen.getByText(/connection timeout/i)).toBeInTheDocument();
    });
  });

  describe('triggered_by attribution', () => {
    it('shows triggeredBy when it is api', () => {
      const apiTransition = {
        from: null,
        to: 'pending',
        at: '2026-01-17T10:30:00Z',
        triggered_by: 'api',
        details: null,
      };
      render(<TimelineEntry transition={apiTransition} isLast={false} showTriggeredBy />);
      expect(screen.getByText(/api/i)).toBeInTheDocument();
    });

    it('shows triggeredBy when it is worker', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} showTriggeredBy />);
      expect(screen.getByText(/worker/i)).toBeInTheDocument();
    });

    it('hides triggeredBy by default', () => {
      render(<TimelineEntry transition={mockTransition} isLast={false} />);
      // Should not explicitly show "worker" unless showTriggeredBy is true
      // The status message might contain "worker" so check more specifically
      expect(screen.queryByTestId('triggered-by')).not.toBeInTheDocument();
    });
  });
});
