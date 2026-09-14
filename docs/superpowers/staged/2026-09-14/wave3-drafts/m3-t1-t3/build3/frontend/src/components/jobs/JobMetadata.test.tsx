/**
 * Tests for JobMetadata component (TDD RED)
 *
 * Displays job metadata information including timestamps and type.
 * Based on UI design:
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Started: 2 minutes ago (10:30:00 AM)                            │
 * │ Type: Export | Target: events.csv | Created by: System          │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * NEM-2710
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import JobMetadata from './JobMetadata';

import type { JobResponse, JobStatusEnum } from '../../services/api';

// Helper to create a mock job
function createMockJob(overrides: Partial<JobResponse> = {}): JobResponse {
  return {
    job_id: 'export-142',
    job_type: 'export',
    status: 'running' as JobStatusEnum,
    progress: 67,
    message: null,
    error: null,
    result: null,
    created_at: '2024-01-15T10:30:00Z',
    started_at: '2024-01-15T10:30:01Z',
    completed_at: null,
    ...overrides,
  };
}

describe('JobMetadata', () => {
  // Fixed time for consistent testing
  const NOW = new Date('2024-01-15T10:32:00Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('started timestamp', () => {
    it('shows started timestamp with relative time', () => {
      const job = createMockJob({ started_at: '2024-01-15T10:30:00Z' });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/started/i)).toBeInTheDocument();
      // Check the Started metadata item specifically
      const startedItem = screen.getByTestId('metadata-item-started');
      expect(startedItem).toHaveTextContent(/2 minutes ago/i);
    });

    it('shows "Not started" when started_at is null', () => {
      const job = createMockJob({ status: 'pending', started_at: null });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/not started/i)).toBeInTheDocument();
    });

    it('shows absolute time in parentheses', () => {
      const job = createMockJob({ started_at: '2024-01-15T10:30:00Z' });
      render(<JobMetadata job={job} />);

      // Check the Started metadata item has time in parentheses
      const startedItem = screen.getByTestId('metadata-item-started');
      // Time should contain hours and minutes (exact format depends on timezone)
      expect(startedItem.textContent).toMatch(/\(\d{2}:\d{2}:\d{2}/);
    });
  });

  describe('job type display', () => {
    it('shows job type', () => {
      const job = createMockJob({ job_type: 'export' });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/type/i)).toBeInTheDocument();
      expect(screen.getByText(/export/i)).toBeInTheDocument();
    });

    it('capitalizes job type', () => {
      const job = createMockJob({ job_type: 'cleanup' });
      render(<JobMetadata job={job} />);

      // Type should be displayed capitalized
      expect(screen.getByTestId('job-type')).toHaveTextContent('Cleanup');
    });
  });

  describe('completed timestamp', () => {
    it('shows completed timestamp when job is completed', () => {
      const job = createMockJob({
        status: 'completed',
        completed_at: '2024-01-15T10:31:00Z',
      });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/completed/i)).toBeInTheDocument();
    });

    it('does not show completed section when not completed', () => {
      const job = createMockJob({ status: 'running', completed_at: null });
      render(<JobMetadata job={job} />);

      // Should not have "Completed:" label
      expect(screen.queryByText(/completed:/i)).not.toBeInTheDocument();
    });

    it('shows duration when job is completed', () => {
      const job = createMockJob({
        status: 'completed',
        started_at: '2024-01-15T10:30:00Z',
        completed_at: '2024-01-15T10:31:00Z',
      });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/duration/i)).toBeInTheDocument();
      // Duration should be shown in the duration metadata item
      const durationItem = screen.getByTestId('metadata-item-duration');
      expect(durationItem).toHaveTextContent('1 minute');
    });
  });

  describe('created timestamp', () => {
    it('shows created timestamp', () => {
      const job = createMockJob({ created_at: '2024-01-15T10:28:00Z' });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/created/i)).toBeInTheDocument();
    });
  });

  describe('error display', () => {
    it('shows error message when job has error', () => {
      const job = createMockJob({
        status: 'failed',
        error: 'Connection timeout',
      });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/connection timeout/i)).toBeInTheDocument();
    });

    it('styles error message with red color', () => {
      const job = createMockJob({
        status: 'failed',
        error: 'Connection timeout',
      });
      render(<JobMetadata job={job} />);

      const errorSection = screen.getByTestId('error-section');
      expect(errorSection).toHaveClass('text-red-400');
    });

    it('does not show error section when no error', () => {
      const job = createMockJob({ status: 'running', error: null });
      render(<JobMetadata job={job} />);

      expect(screen.queryByTestId('error-section')).not.toBeInTheDocument();
    });
  });

  describe('message display', () => {
    it('shows message when job has message', () => {
      const job = createMockJob({
        message: 'Processing 1000 events',
      });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/processing 1000 events/i)).toBeInTheDocument();
    });

    it('does not show message section when no message', () => {
      const job = createMockJob({ message: null });
      render(<JobMetadata job={job} />);

      expect(screen.queryByTestId('message-section')).not.toBeInTheDocument();
    });
  });

  describe('layout', () => {
    it('renders metadata items in a structured layout', () => {
      const job = createMockJob();
      render(<JobMetadata job={job} />);

      const container = screen.getByTestId('job-metadata');
      expect(container).toBeInTheDocument();
    });

    it('separates metadata items appropriately', () => {
      const job = createMockJob();
      render(<JobMetadata job={job} />);

      // Should have multiple metadata items
      const items = screen.getAllByTestId(/metadata-item/);
      expect(items.length).toBeGreaterThan(1);
    });
  });

  describe('relative time formatting', () => {
    it('shows "just now" for very recent times', () => {
      const job = createMockJob({ started_at: '2024-01-15T10:31:55Z' });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/just now|seconds ago/i)).toBeInTheDocument();
    });

    it('shows hours for longer durations', () => {
      const job = createMockJob({ started_at: '2024-01-15T08:30:00Z' });
      render(<JobMetadata job={job} />);

      expect(screen.getByText(/2 hours ago/i)).toBeInTheDocument();
    });
  });
});
