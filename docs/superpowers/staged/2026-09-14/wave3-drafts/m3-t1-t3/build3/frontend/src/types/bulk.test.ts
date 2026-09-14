/**
 * Tests for Bulk Operation Types
 *
 * @module types/bulk.test
 */

import { describe, it, expect } from 'vitest';

import {
  isAllSucceeded,
  hasFailures,
  isPartialSuccess,
  getFailedResults,
  getSuccessfulResults,
  getSuccessfulIds,
  type BulkOperationResponse,
  type BulkItemResult,
} from './bulk';

describe('Bulk Operation Type Guards', () => {
  describe('isAllSucceeded', () => {
    it('returns true when all items succeeded', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 3,
        failed: 0,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 1 },
          { index: 1, status: 'success', id: 2 },
          { index: 2, status: 'success', id: 3 },
        ],
      };

      expect(isAllSucceeded(response)).toBe(true);
    });

    it('returns false when any items failed', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 1,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 1 },
          { index: 1, status: 'failed', error: 'Not found' },
          { index: 2, status: 'success', id: 3 },
        ],
      };

      expect(isAllSucceeded(response)).toBe(false);
    });

    it('returns false when any items were skipped', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 0,
        skipped: 1,
        results: [
          { index: 0, status: 'success', id: 1 },
          { index: 1, status: 'skipped' },
          { index: 2, status: 'success', id: 3 },
        ],
      };

      expect(isAllSucceeded(response)).toBe(false);
    });
  });

  describe('hasFailures', () => {
    it('returns true when there are failures', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 1,
        skipped: 0,
      };

      expect(hasFailures(response)).toBe(true);
    });

    it('returns false when there are no failures', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 3,
        failed: 0,
        skipped: 0,
      };

      expect(hasFailures(response)).toBe(false);
    });
  });

  describe('isPartialSuccess', () => {
    it('returns true when some succeeded and some failed', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 1,
        skipped: 0,
      };

      expect(isPartialSuccess(response)).toBe(true);
    });

    it('returns true when some succeeded and some were skipped', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 0,
        skipped: 1,
      };

      expect(isPartialSuccess(response)).toBe(true);
    });

    it('returns false when all succeeded', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 3,
        failed: 0,
        skipped: 0,
      };

      expect(isPartialSuccess(response)).toBe(false);
    });

    it('returns false when all failed', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 0,
        failed: 3,
        skipped: 0,
      };

      expect(isPartialSuccess(response)).toBe(false);
    });
  });

  describe('getFailedResults', () => {
    it('returns only failed results', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 1,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 1 },
          { index: 1, status: 'failed', error: 'Camera not found' },
          { index: 2, status: 'success', id: 3 },
        ],
      };

      const failed = getFailedResults(response);

      expect(failed).toHaveLength(1);
      expect(failed[0]).toEqual({
        index: 1,
        status: 'failed',
        error: 'Camera not found',
      });
    });

    it('returns empty array when no failures', () => {
      const response: BulkOperationResponse = {
        total: 2,
        succeeded: 2,
        failed: 0,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 1 },
          { index: 1, status: 'success', id: 2 },
        ],
      };

      expect(getFailedResults(response)).toHaveLength(0);
    });

    it('handles undefined results', () => {
      const response: BulkOperationResponse = {
        total: 2,
        succeeded: 2,
        failed: 0,
        skipped: 0,
      };

      expect(getFailedResults(response)).toHaveLength(0);
    });
  });

  describe('getSuccessfulResults', () => {
    it('returns only successful results', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 1,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 1 },
          { index: 1, status: 'failed', error: 'Error' },
          { index: 2, status: 'success', id: 3 },
        ],
      };

      const successful = getSuccessfulResults(response);

      expect(successful).toHaveLength(2);
      expect(successful[0]).toEqual({ index: 0, status: 'success', id: 1 });
      expect(successful[1]).toEqual({ index: 2, status: 'success', id: 3 });
    });

    it('handles empty results', () => {
      const response: BulkOperationResponse = {
        total: 0,
        succeeded: 0,
        failed: 0,
        skipped: 0,
        results: [],
      };

      expect(getSuccessfulResults(response)).toHaveLength(0);
    });
  });

  describe('getSuccessfulIds', () => {
    it('returns IDs from successful results', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 2,
        failed: 1,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 100 },
          { index: 1, status: 'failed', error: 'Error' },
          { index: 2, status: 'success', id: 200 },
        ],
      };

      const ids = getSuccessfulIds(response);

      expect(ids).toEqual([100, 200]);
    });

    it('filters out null/undefined IDs', () => {
      const response: BulkOperationResponse = {
        total: 3,
        succeeded: 3,
        failed: 0,
        skipped: 0,
        results: [
          { index: 0, status: 'success', id: 100 },
          { index: 1, status: 'success', id: null },
          { index: 2, status: 'success', id: 300 },
        ],
      };

      const ids = getSuccessfulIds(response);

      expect(ids).toEqual([100, 300]);
    });

    it('returns empty array when no successful results', () => {
      const response: BulkOperationResponse = {
        total: 2,
        succeeded: 0,
        failed: 2,
        skipped: 0,
        results: [
          { index: 0, status: 'failed', error: 'Error 1' },
          { index: 1, status: 'failed', error: 'Error 2' },
        ],
      };

      expect(getSuccessfulIds(response)).toEqual([]);
    });
  });
});

describe('BulkItemResult Type', () => {
  it('allows success status with id', () => {
    const result: BulkItemResult = {
      index: 0,
      status: 'success',
      id: 123,
    };

    expect(result.status).toBe('success');
    expect(result.id).toBe(123);
  });

  it('allows failed status with error', () => {
    const result: BulkItemResult = {
      index: 1,
      status: 'failed',
      error: 'Validation failed',
    };

    expect(result.status).toBe('failed');
    expect(result.error).toBe('Validation failed');
  });

  it('allows skipped status', () => {
    const result: BulkItemResult = {
      index: 2,
      status: 'skipped',
    };

    expect(result.status).toBe('skipped');
  });
});
