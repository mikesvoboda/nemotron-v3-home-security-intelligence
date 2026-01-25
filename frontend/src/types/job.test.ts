/**
 * Tests for Job type utilities
 *
 * @see NEM-3593
 */

import { describe, expect, it } from 'vitest';

import {
  isJobDetailResponse,
  isJobResponse,
  jobResponseToDisplayData,
  jobDetailToDisplayData,
  toJobDisplayData,
  hasRetryInfo,
  canRetry,
  hasErrorTraceback,
  formatRetryInfo,
  getShortErrorMessage,
  getPriorityLabel,
  PRIORITY_LABELS,
} from './job';

import type { JobResponse, JobDetailResponse } from './generated';

describe('Job type utilities', () => {
  // Sample test data
  const mockJobResponse: JobResponse = {
    job_id: 'export-123',
    job_type: 'export',
    status: 'running',
    progress: 45,
    created_at: '2024-01-15T10:30:00Z',
    started_at: '2024-01-15T10:30:01Z',
    completed_at: null,
    message: 'Exporting events...',
    error: null,
    result: null,
  };

  const mockJobDetailResponse: JobDetailResponse = {
    id: 'export-123',
    job_type: 'export',
    status: 'running',
    queue_name: 'high_priority',
    priority: 1,
    progress: {
      percent: 45,
      current_step: 'Processing batch 5 of 10',
      items_processed: 500,
      items_total: 1000,
    },
    timing: {
      created_at: '2024-01-15T10:30:00Z',
      started_at: '2024-01-15T10:30:01Z',
      completed_at: null,
      duration_seconds: 45.5,
      estimated_remaining_seconds: 55,
    },
    retry_info: {
      attempt_number: 2,
      max_attempts: 3,
      next_retry_at: null,
      previous_errors: ['First attempt failed'],
    },
    metadata: {
      input_params: { event_ids: ['evt-1', 'evt-2'] },
      worker_id: 'worker-001',
    },
    error: null,
    result: null,
  };

  describe('isJobDetailResponse', () => {
    it('returns true for JobDetailResponse', () => {
      expect(isJobDetailResponse(mockJobDetailResponse)).toBe(true);
    });

    it('returns false for JobResponse', () => {
      expect(isJobDetailResponse(mockJobResponse)).toBe(false);
    });
  });

  describe('isJobResponse', () => {
    it('returns true for JobResponse', () => {
      expect(isJobResponse(mockJobResponse)).toBe(true);
    });

    it('returns false for JobDetailResponse', () => {
      expect(isJobResponse(mockJobDetailResponse)).toBe(false);
    });
  });

  describe('jobResponseToDisplayData', () => {
    it('converts JobResponse to JobDisplayData', () => {
      const result = jobResponseToDisplayData(mockJobResponse);

      expect(result.id).toBe('export-123');
      expect(result.job_type).toBe('export');
      expect(result.status).toBe('running');
      expect(result.progress_percent).toBe(45);
      expect(result.created_at).toBe('2024-01-15T10:30:00Z');
      expect(result.message).toBe('Exporting events...');
    });
  });

  describe('jobDetailToDisplayData', () => {
    it('converts JobDetailResponse to JobDisplayData', () => {
      const result = jobDetailToDisplayData(mockJobDetailResponse);

      expect(result.id).toBe('export-123');
      expect(result.job_type).toBe('export');
      expect(result.status).toBe('running');
      expect(result.queue_name).toBe('high_priority');
      expect(result.priority).toBe(1);
      expect(result.progress_percent).toBe(45);
      expect(result.current_step).toBe('Processing batch 5 of 10');
      expect(result.attempt_number).toBe(2);
      expect(result.max_attempts).toBe(3);
    });
  });

  describe('toJobDisplayData', () => {
    it('converts JobResponse correctly', () => {
      const result = toJobDisplayData(mockJobResponse);
      expect(result.id).toBe('export-123');
      expect(result.message).toBe('Exporting events...');
    });

    it('converts JobDetailResponse correctly', () => {
      const result = toJobDisplayData(mockJobDetailResponse);
      expect(result.id).toBe('export-123');
      expect(result.current_step).toBe('Processing batch 5 of 10');
    });
  });

  describe('hasRetryInfo', () => {
    it('returns true for JobDetailResponse with max_attempts > 1', () => {
      expect(hasRetryInfo(mockJobDetailResponse)).toBe(true);
    });

    it('returns false for JobResponse', () => {
      expect(hasRetryInfo(mockJobResponse)).toBe(false);
    });

    it('returns false for JobDetailResponse with max_attempts = 1', () => {
      const singleAttemptJob: JobDetailResponse = {
        ...mockJobDetailResponse,
        retry_info: { ...mockJobDetailResponse.retry_info, max_attempts: 1 },
      };
      expect(hasRetryInfo(singleAttemptJob)).toBe(false);
    });
  });

  describe('canRetry', () => {
    it('returns false for JobResponse', () => {
      expect(canRetry(mockJobResponse)).toBe(false);
    });

    it('returns false for running job', () => {
      expect(canRetry(mockJobDetailResponse)).toBe(false);
    });

    it('returns true for failed job with remaining attempts', () => {
      const failedJob: JobDetailResponse = {
        ...mockJobDetailResponse,
        status: 'failed',
        retry_info: { attempt_number: 2, max_attempts: 3, previous_errors: [] },
      };
      expect(canRetry(failedJob)).toBe(true);
    });

    it('returns false for failed job with no remaining attempts', () => {
      const failedJob: JobDetailResponse = {
        ...mockJobDetailResponse,
        status: 'failed',
        retry_info: { attempt_number: 3, max_attempts: 3, previous_errors: [] },
      };
      expect(canRetry(failedJob)).toBe(false);
    });
  });

  describe('hasErrorTraceback', () => {
    it('returns false when no error', () => {
      expect(hasErrorTraceback(mockJobResponse)).toBe(false);
    });

    it('returns false for single-line error', () => {
      const jobWithError = { ...mockJobResponse, error: 'Connection timeout' };
      expect(hasErrorTraceback(jobWithError)).toBe(false);
    });

    it('returns true for multi-line error (traceback)', () => {
      const traceback = `Traceback (most recent call last):
  File "test.py", line 1
Error: Something failed`;
      const jobWithTraceback = { ...mockJobResponse, error: traceback };
      expect(hasErrorTraceback(jobWithTraceback)).toBe(true);
    });
  });

  describe('formatRetryInfo', () => {
    it('formats retry info correctly', () => {
      const retryInfo = { attempt_number: 2, max_attempts: 3, previous_errors: [] };
      expect(formatRetryInfo(retryInfo)).toBe('Attempt 2 of 3');
    });

    it('formats single attempt correctly', () => {
      const retryInfo = { attempt_number: 1, max_attempts: 5, previous_errors: [] };
      expect(formatRetryInfo(retryInfo)).toBe('Attempt 1 of 5');
    });
  });

  describe('getShortErrorMessage', () => {
    it('returns null for null input', () => {
      expect(getShortErrorMessage(null)).toBe(null);
    });

    it('returns null for undefined input', () => {
      expect(getShortErrorMessage(undefined)).toBe(null);
    });

    it('returns first line for multi-line error', () => {
      const error = `Connection timeout
Stack trace here`;
      expect(getShortErrorMessage(error)).toBe('Connection timeout');
    });

    it('truncates long first line', () => {
      const longError =
        'A'.repeat(150) +
        '\nMore details';
      const result = getShortErrorMessage(longError);
      expect(result).toHaveLength(103); // 100 + "..."
      expect(result?.endsWith('...')).toBe(true);
    });

    it('returns short error as-is', () => {
      expect(getShortErrorMessage('Short error')).toBe('Short error');
    });
  });

  describe('getPriorityLabel', () => {
    it('returns correct labels for known priorities', () => {
      expect(getPriorityLabel(0)).toBe('Highest');
      expect(getPriorityLabel(1)).toBe('High');
      expect(getPriorityLabel(2)).toBe('Normal');
      expect(getPriorityLabel(3)).toBe('Low');
      expect(getPriorityLabel(4)).toBe('Lowest');
    });

    it('returns fallback for unknown priority', () => {
      expect(getPriorityLabel(5)).toBe('Priority 5');
      expect(getPriorityLabel(10)).toBe('Priority 10');
    });
  });

  describe('PRIORITY_LABELS', () => {
    it('contains all expected priority levels', () => {
      expect(PRIORITY_LABELS[0]).toBe('Highest');
      expect(PRIORITY_LABELS[1]).toBe('High');
      expect(PRIORITY_LABELS[2]).toBe('Normal');
      expect(PRIORITY_LABELS[3]).toBe('Low');
      expect(PRIORITY_LABELS[4]).toBe('Lowest');
    });
  });
});
