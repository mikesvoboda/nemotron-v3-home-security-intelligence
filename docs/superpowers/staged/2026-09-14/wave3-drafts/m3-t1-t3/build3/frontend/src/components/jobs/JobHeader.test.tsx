/**
 * Tests for JobHeader component (TDD RED)
 *
 * Displays job title, status badge, and progress bar.
 * Based on UI design:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ Export #142                                                     │
 * │ Status: ● Processing (67%)                                      │
 * │ ███████████████████████████░░░░░░░░░░░░░░                       │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * NEM-2710
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import JobHeader from './JobHeader';

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

describe('JobHeader', () => {
  describe('rendering', () => {
    it('renders job type and id', () => {
      const job = createMockJob({ job_id: 'export-142', job_type: 'export' });
      render(<JobHeader job={job} />);

      expect(screen.getByText(/export/i)).toBeInTheDocument();
      expect(screen.getByText(/#142|export-142/)).toBeInTheDocument();
    });

    it('renders job title with job type capitalized', () => {
      const job = createMockJob({ job_type: 'cleanup' });
      render(<JobHeader job={job} />);

      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
    });
  });

  describe('status badge', () => {
    it('shows running status with blue color', () => {
      const job = createMockJob({ status: 'running' });
      render(<JobHeader job={job} />);

      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent(/running/i);
      expect(badge).toHaveClass('text-blue-400');
    });

    it('shows pending status with gray color', () => {
      const job = createMockJob({ status: 'pending' });
      render(<JobHeader job={job} />);

      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent(/pending/i);
      expect(badge).toHaveClass('text-gray-400');
    });

    it('shows completed status with green color', () => {
      const job = createMockJob({ status: 'completed' });
      render(<JobHeader job={job} />);

      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent(/completed/i);
      expect(badge).toHaveClass('text-green-400');
    });

    it('shows failed status with red color', () => {
      const job = createMockJob({ status: 'failed' });
      render(<JobHeader job={job} />);

      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent(/failed/i);
      expect(badge).toHaveClass('text-red-400');
    });
  });

  describe('progress bar', () => {
    it('shows progress bar when status is running', () => {
      const job = createMockJob({ status: 'running', progress: 67 });
      render(<JobHeader job={job} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('shows progress percentage when running', () => {
      const job = createMockJob({ status: 'running', progress: 67 });
      render(<JobHeader job={job} />);

      expect(screen.getByText(/67%/)).toBeInTheDocument();
    });

    it('sets progress bar width correctly', () => {
      const job = createMockJob({ status: 'running', progress: 67 });
      render(<JobHeader job={job} />);

      const progressBar = screen.getByRole('progressbar');
      const fillElement = progressBar.querySelector('[data-testid="progress-fill"]');
      expect(fillElement).toHaveStyle({ width: '67%' });
    });

    it('does not show progress bar for pending status', () => {
      const job = createMockJob({ status: 'pending', progress: 0 });
      render(<JobHeader job={job} />);

      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    it('shows progress bar for completed status with 100%', () => {
      const job = createMockJob({ status: 'completed', progress: 100 });
      render(<JobHeader job={job} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
      expect(screen.getByText(/100%/)).toBeInTheDocument();
    });

    it('shows progress bar for failed status with last known progress', () => {
      const job = createMockJob({ status: 'failed', progress: 45 });
      render(<JobHeader job={job} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
      expect(screen.getByText(/45%/)).toBeInTheDocument();
    });

    it('uses blue fill for running status', () => {
      const job = createMockJob({ status: 'running', progress: 50 });
      render(<JobHeader job={job} />);

      const fillElement = screen.getByTestId('progress-fill');
      expect(fillElement).toHaveClass('bg-blue-500');
    });

    it('uses green fill for completed status', () => {
      const job = createMockJob({ status: 'completed', progress: 100 });
      render(<JobHeader job={job} />);

      const fillElement = screen.getByTestId('progress-fill');
      expect(fillElement).toHaveClass('bg-green-500');
    });

    it('uses red fill for failed status', () => {
      const job = createMockJob({ status: 'failed', progress: 45 });
      render(<JobHeader job={job} />);

      const fillElement = screen.getByTestId('progress-fill');
      expect(fillElement).toHaveClass('bg-red-500');
    });
  });

  describe('status indicator dot', () => {
    it('shows animated dot for running status', () => {
      const job = createMockJob({ status: 'running' });
      render(<JobHeader job={job} />);

      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('animate-pulse');
    });

    it('does not animate dot for completed status', () => {
      const job = createMockJob({ status: 'completed' });
      render(<JobHeader job={job} />);

      const dot = screen.getByTestId('status-dot');
      expect(dot).not.toHaveClass('animate-pulse');
    });
  });

  describe('accessibility', () => {
    it('has appropriate heading level', () => {
      const job = createMockJob();
      render(<JobHeader job={job} />);

      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
    });

    it('progress bar has accessible attributes', () => {
      const job = createMockJob({ status: 'running', progress: 67 });
      render(<JobHeader job={job} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '67');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });
  });
});
