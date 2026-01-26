/**
 * Tests for useScheduledReports hooks
 *
 * @see NEM-3667 - Scheduled Reports Frontend UI
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useScheduledReportsQuery,
  useScheduledReportQuery,
  useCreateScheduledReportMutation,
  useUpdateScheduledReportMutation,
  useDeleteScheduledReportMutation,
  useTriggerScheduledReportMutation,
  SCHEDULED_REPORT_QUERY_KEYS,
} from './useScheduledReports';
import * as scheduledReportsApi from '../services/scheduledReportsApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type {
  ScheduledReport,
  ScheduledReportListResponse,
  ScheduledReportRunResponse,
} from '../types/scheduledReport';

// Mock the API module
vi.mock('../services/scheduledReportsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/scheduledReportsApi')>();
  return {
    ...actual,
    listScheduledReports: vi.fn(),
    getScheduledReport: vi.fn(),
    createScheduledReport: vi.fn(),
    updateScheduledReport: vi.fn(),
    deleteScheduledReport: vi.fn(),
    triggerScheduledReport: vi.fn(),
  };
});

// Test data
const mockReport: ScheduledReport = {
  id: 1,
  name: 'Weekly Security Summary',
  frequency: 'weekly',
  day_of_week: 1,
  day_of_month: null,
  hour: 8,
  minute: 0,
  timezone: 'America/New_York',
  format: 'pdf',
  enabled: true,
  email_recipients: ['admin@example.com'],
  include_charts: true,
  include_event_details: true,
  last_run_at: '2025-01-20T08:00:00Z',
  next_run_at: '2025-01-27T08:00:00Z',
  created_at: '2025-01-01T12:00:00Z',
  updated_at: '2025-01-15T09:30:00Z',
};

const mockListResponse: ScheduledReportListResponse = {
  items: [mockReport],
  total: 1,
};

const mockRunResponse: ScheduledReportRunResponse = {
  report_id: 1,
  status: 'running',
  message: 'Report generation started',
  started_at: '2025-01-25T10:30:00Z',
};

describe('useScheduledReports hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('SCHEDULED_REPORT_QUERY_KEYS', () => {
    it('should have correct query key structure', () => {
      expect(SCHEDULED_REPORT_QUERY_KEYS.all).toEqual(['scheduled-reports']);
      expect(SCHEDULED_REPORT_QUERY_KEYS.list).toEqual(['scheduled-reports', 'list']);
      expect(SCHEDULED_REPORT_QUERY_KEYS.detail(1)).toEqual(['scheduled-reports', 'detail', 1]);
    });
  });

  describe('useScheduledReportsQuery', () => {
    it('should fetch scheduled reports list', async () => {
      vi.mocked(scheduledReportsApi.listScheduledReports).mockResolvedValue(mockListResponse);

      const { result } = renderHook(() => useScheduledReportsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.reports).toEqual([mockReport]);
      expect(result.current.total).toBe(1);
      expect(result.current.error).toBeNull();
    });

    it('should handle fetch error', async () => {
      const error = new Error('Failed to fetch');
      vi.mocked(scheduledReportsApi.listScheduledReports).mockRejectedValue(error);

      const { result } = renderHook(() => useScheduledReportsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 3000 }
      );

      expect(result.current.error?.message).toBe('Failed to fetch');
      expect(result.current.reports).toEqual([]);
    });

    it('should not fetch when disabled', () => {
      const { result } = renderHook(() => useScheduledReportsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(scheduledReportsApi.listScheduledReports).not.toHaveBeenCalled();
    });
  });

  describe('useScheduledReportQuery', () => {
    it('should fetch a single scheduled report', async () => {
      vi.mocked(scheduledReportsApi.getScheduledReport).mockResolvedValue(mockReport);

      const { result } = renderHook(() => useScheduledReportQuery(1), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockReport);
      expect(scheduledReportsApi.getScheduledReport).toHaveBeenCalledWith(1);
    });

    it('should not fetch with invalid ID', () => {
      const { result } = renderHook(() => useScheduledReportQuery(0), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(scheduledReportsApi.getScheduledReport).not.toHaveBeenCalled();
    });
  });

  describe('useCreateScheduledReportMutation', () => {
    it('should create a scheduled report', async () => {
      vi.mocked(scheduledReportsApi.createScheduledReport).mockResolvedValue(mockReport);

      const { result } = renderHook(() => useCreateScheduledReportMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(false);

      await act(async () => {
        const created = await result.current.createReport({
          name: 'Weekly Security Summary',
          frequency: 'weekly',
          day_of_week: 1,
          hour: 8,
          minute: 0,
        });
        expect(created).toEqual(mockReport);
      });

      expect(scheduledReportsApi.createScheduledReport).toHaveBeenCalled();
    });

    it('should handle create error', async () => {
      const error = new Error('Create failed');
      vi.mocked(scheduledReportsApi.createScheduledReport).mockRejectedValue(error);

      const { result } = renderHook(() => useCreateScheduledReportMutation(), {
        wrapper: createQueryWrapper(),
      });

      await act(async () => {
        await expect(
          result.current.createReport({
            name: 'Test Report',
            frequency: 'daily',
          })
        ).rejects.toThrow('Create failed');
      });
    });
  });

  describe('useUpdateScheduledReportMutation', () => {
    it('should update a scheduled report', async () => {
      const updatedReport = { ...mockReport, name: 'Updated Report' };
      vi.mocked(scheduledReportsApi.updateScheduledReport).mockResolvedValue(updatedReport);

      const { result } = renderHook(() => useUpdateScheduledReportMutation(), {
        wrapper: createQueryWrapper(),
      });

      await act(async () => {
        const updated = await result.current.updateReport(1, { name: 'Updated Report' });
        expect(updated).toEqual(updatedReport);
      });

      expect(scheduledReportsApi.updateScheduledReport).toHaveBeenCalledWith(1, {
        name: 'Updated Report',
      });
    });
  });

  describe('useDeleteScheduledReportMutation', () => {
    it('should delete a scheduled report', async () => {
      vi.mocked(scheduledReportsApi.deleteScheduledReport).mockResolvedValue(undefined);

      const { result } = renderHook(() => useDeleteScheduledReportMutation(), {
        wrapper: createQueryWrapper(),
      });

      await act(async () => {
        await result.current.deleteReport(1);
      });

      expect(scheduledReportsApi.deleteScheduledReport).toHaveBeenCalled();
      // Check that the first argument was 1
      expect(vi.mocked(scheduledReportsApi.deleteScheduledReport).mock.calls[0][0]).toBe(1);
    });
  });

  describe('useTriggerScheduledReportMutation', () => {
    it('should trigger a scheduled report', async () => {
      vi.mocked(scheduledReportsApi.triggerScheduledReport).mockResolvedValue(mockRunResponse);

      const { result } = renderHook(() => useTriggerScheduledReportMutation(), {
        wrapper: createQueryWrapper(),
      });

      await act(async () => {
        const response = await result.current.triggerReport(1);
        expect(response).toEqual(mockRunResponse);
      });

      expect(scheduledReportsApi.triggerScheduledReport).toHaveBeenCalled();
      // Check that the first argument was 1
      expect(vi.mocked(scheduledReportsApi.triggerScheduledReport).mock.calls[0][0]).toBe(1);
    });
  });
});
