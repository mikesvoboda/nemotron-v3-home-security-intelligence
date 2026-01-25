/**
 * Tests for useObjectDistributionQuery hook
 *
 * Tests cover:
 * - Successful data fetching
 * - Loading state
 * - Error handling
 * - Query key generation
 * - Derived values (objectTypes, totalDetections)
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useObjectDistributionQuery, objectDistributionQueryKeys } from './useObjectDistributionQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API
vi.mock('../services/api', () => ({
  fetchObjectDistribution: vi.fn(),
}));

describe('useObjectDistributionQuery', () => {
  const mockParams = {
    start_date: '2026-01-10',
    end_date: '2026-01-17',
  };

  const mockResponse = {
    object_types: [
      { object_type: 'person', count: 150, percentage: 50.0 },
      { object_type: 'car', count: 90, percentage: 30.0 },
      { object_type: 'dog', count: 60, percentage: 20.0 },
    ],
    total_detections: 300,
    start_date: '2026-01-10',
    end_date: '2026-01-17',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('query key factory', () => {
    it('generates correct base key', () => {
      expect(objectDistributionQueryKeys.all).toEqual(['analytics', 'object-distribution']);
    });

    it('generates correct key with params', () => {
      const key = objectDistributionQueryKeys.byDateRange(mockParams);
      expect(key).toEqual(['analytics', 'object-distribution', mockParams]);
    });
  });

  describe('successful fetching', () => {
    beforeEach(() => {
      vi.mocked(api.fetchObjectDistribution).mockResolvedValue(mockResponse);
    });

    it('fetches and returns object distribution data', async () => {
      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockResponse);
      expect(result.current.objectTypes).toEqual(mockResponse.object_types);
      expect(result.current.totalDetections).toBe(300);
      expect(result.current.error).toBeNull();
    });

    it('calls API with correct parameters', async () => {
      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchObjectDistribution).toHaveBeenCalledWith(mockParams);
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      vi.mocked(api.fetchObjectDistribution).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
    });

    it('shows loading state initially', () => {
      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.objectTypes).toEqual([]);
      expect(result.current.totalDetections).toBe(0);
    });
  });

  describe('error handling', () => {
    const mockError = new Error('Network error');

    beforeEach(() => {
      vi.mocked(api.fetchObjectDistribution).mockRejectedValue(mockError);
    });

    it('handles errors correctly', async () => {
      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      // Wait for the query to finish (after retries)
      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error).toBeTruthy();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.objectTypes).toEqual([]);
      expect(result.current.totalDetections).toBe(0);
    });
  });

  describe('options', () => {
    beforeEach(() => {
      vi.mocked(api.fetchObjectDistribution).mockResolvedValue(mockResponse);
    });

    it('respects enabled option', () => {
      const { result } = renderHook(
        () => useObjectDistributionQuery(mockParams, { enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      // Should not be loading when disabled
      expect(result.current.isLoading).toBe(false);
      expect(api.fetchObjectDistribution).not.toHaveBeenCalled();
    });

    it('enables query when enabled is true', async () => {
      const { result } = renderHook(
        () => useObjectDistributionQuery(mockParams, { enabled: true }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchObjectDistribution).toHaveBeenCalled();
    });
  });

  describe('derived values', () => {
    it('provides empty defaults when data is undefined', () => {
      vi.mocked(api.fetchObjectDistribution).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.objectTypes).toEqual([]);
      expect(result.current.totalDetections).toBe(0);
    });

    it('derives objectTypes from response', async () => {
      vi.mocked(api.fetchObjectDistribution).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.objectTypes).toHaveLength(3);
      expect(result.current.objectTypes[0].object_type).toBe('person');
      expect(result.current.objectTypes[1].object_type).toBe('car');
      expect(result.current.objectTypes[2].object_type).toBe('dog');
    });

    it('derives totalDetections from response', async () => {
      vi.mocked(api.fetchObjectDistribution).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useObjectDistributionQuery(mockParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalDetections).toBe(300);
    });
  });
});
