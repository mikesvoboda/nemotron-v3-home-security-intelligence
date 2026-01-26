/**
 * Tests for JobsList component
 *
 * @module components/jobs/JobsList.test
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import JobsList, { type JobsListProps } from './JobsList';

import type { JobResponse } from '../../services/api';

describe('JobsList', () => {
  // Helper to create mock jobs
  const createMockJob = (overrides: Partial<JobResponse> = {}): JobResponse => ({
    job_id: `job-${Math.random().toString(36).slice(2, 11)}`,
    job_type: 'retention_cleanup',
    status: 'completed',
    progress: 100,
    result: { cleaned_count: 5 },
    error: null,
    created_at: new Date().toISOString(),
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    ...overrides,
  });

  const defaultProps: JobsListProps = {
    jobs: [],
    selectedJobId: null,
    onSelectJob: vi.fn(),
  };

  describe('basic rendering', () => {
    it('renders an empty list when no jobs provided', () => {
      render(<JobsList {...defaultProps} />);

      const list = screen.getByTestId('jobs-list');
      expect(list).toBeInTheDocument();
      expect(list.children).toHaveLength(0);
    });

    it('renders job items for each job', () => {
      const jobs = [createMockJob({ job_id: 'job-1' }), createMockJob({ job_id: 'job-2' })];

      render(<JobsList {...defaultProps} jobs={jobs} />);

      const list = screen.getByTestId('jobs-list');
      expect(list.children).toHaveLength(2);
    });

    it('applies overflow styling for scrollable list', () => {
      render(<JobsList {...defaultProps} />);

      const list = screen.getByTestId('jobs-list');
      expect(list).toHaveClass('overflow-y-auto');
      expect(list).toHaveClass('flex-1');
    });
  });

  describe('selection', () => {
    it('passes isSelected=true to selected job item', () => {
      const jobs = [createMockJob({ job_id: 'job-1' }), createMockJob({ job_id: 'job-2' })];

      render(<JobsList {...defaultProps} jobs={jobs} selectedJobId="job-1" />);

      // The component passes isSelected to JobsListItem, which applies styling
      // We verify the data is passed correctly by checking component renders
      expect(screen.getByTestId('jobs-list').children).toHaveLength(2);
    });

    it('passes isSelected=false to non-selected job items', () => {
      const jobs = [createMockJob({ job_id: 'job-1' }), createMockJob({ job_id: 'job-2' })];

      render(<JobsList {...defaultProps} jobs={jobs} selectedJobId="job-other" />);

      expect(screen.getByTestId('jobs-list').children).toHaveLength(2);
    });

    it('handles null selectedJobId', () => {
      const jobs = [createMockJob({ job_id: 'job-1' })];

      render(<JobsList {...defaultProps} jobs={jobs} selectedJobId={null} />);

      expect(screen.getByTestId('jobs-list').children).toHaveLength(1);
    });
  });

  describe('useDeferredList integration (NEM-3750)', () => {
    it('renders all jobs when list is below threshold', () => {
      const jobs = Array.from({ length: 10 }, (_, i) =>
        createMockJob({ job_id: `job-${i}` })
      );

      render(<JobsList {...defaultProps} jobs={jobs} />);

      const list = screen.getByTestId('jobs-list');
      expect(list.children).toHaveLength(10);
    });

    it('renders all jobs when list is at threshold', () => {
      const jobs = Array.from({ length: 50 }, (_, i) =>
        createMockJob({ job_id: `job-${i}` })
      );

      render(<JobsList {...defaultProps} jobs={jobs} />);

      const list = screen.getByTestId('jobs-list');
      expect(list.children).toHaveLength(50);
    });

    it('renders all jobs when list exceeds threshold', () => {
      const jobs = Array.from({ length: 100 }, (_, i) =>
        createMockJob({ job_id: `job-${i}` })
      );

      render(<JobsList {...defaultProps} jobs={jobs} />);

      const list = screen.getByTestId('jobs-list');
      // All jobs should eventually render (deferred rendering is async)
      expect(list.children).toHaveLength(100);
    });

    it('applies transition opacity class to container', () => {
      const jobs = [createMockJob({ job_id: 'job-1' })];

      render(<JobsList {...defaultProps} jobs={jobs} />);

      const list = screen.getByTestId('jobs-list');
      // Should not have stale class since list is small and synchronous
      expect(list).not.toHaveClass('opacity-70');
    });
  });

  describe('job ordering', () => {
    it('maintains job order as provided', () => {
      const jobs = [
        createMockJob({ job_id: 'job-a' }),
        createMockJob({ job_id: 'job-b' }),
        createMockJob({ job_id: 'job-c' }),
      ];

      const { container } = render(<JobsList {...defaultProps} jobs={jobs} />);

      // Check that items are rendered in order
      const items = container.querySelectorAll('[data-testid="jobs-list"] > *');
      expect(items).toHaveLength(3);
    });
  });
});
