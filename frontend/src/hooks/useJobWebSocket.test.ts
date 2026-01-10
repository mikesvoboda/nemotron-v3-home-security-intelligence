/**
 * Tests for useJobWebSocket hook
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useJobWebSocket } from './useJobWebSocket';

import type {
  JobProgressMessage,
  JobCompletedMessage,
  JobFailedMessage,
} from '../types/websocket';

const mockOnMessage = vi.fn<(data: unknown) => void>();
const mockWsReturn = {
  isConnected: true,
  lastMessage: null,
  send: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  hasExhaustedRetries: false,
  reconnectCount: 0,
  lastHeartbeat: null,
};

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options: { onMessage?: (data: unknown) => void }) => {
    if (options.onMessage) {
      mockOnMessage.mockImplementation(options.onMessage);
    }
    return mockWsReturn;
  }),
}));

const mockSuccess = vi.fn();
const mockError = vi.fn();

vi.mock('./useToast', () => ({
  useToast: () => ({
    success: mockSuccess,
    error: mockError,
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
    promise: vi.fn(),
  }),
}));

vi.mock('../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../services/queryClient', () => ({
  queryKeys: {
    events: {
      all: ['events'],
    },
  },
}));

describe('useJobWebSocket', () => {
  let queryClient: QueryClient;

  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  const createWrapper = () => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('initialization', () => {
    it('should return initial state', () => {
      const { result } = renderHook(() => useJobWebSocket(), {
        wrapper: createWrapper(),
      });
      expect(result.current.activeJobs).toEqual([]);
      expect(result.current.hasActiveJobs).toBe(false);
      expect(result.current.isConnected).toBe(true);
    });

    it('should not have any running jobs initially', () => {
      const { result } = renderHook(() => useJobWebSocket(), {
        wrapper: createWrapper(),
      });
      expect(result.current.isJobRunning('export')).toBe(false);
    });
  });

  describe('job progress', () => {
    it('should track active jobs on progress message', () => {
      const onJobProgress = vi.fn();
      const { result } = renderHook(() => useJobWebSocket({ onJobProgress }), {
        wrapper: createWrapper(),
      });

      const progressMessage: JobProgressMessage = {
        type: 'job_progress',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          progress: 50,
          status: 'running',
        },
      };

      simulateMessage(progressMessage);

      expect(result.current.activeJobs).toHaveLength(1);
      expect(result.current.activeJobs[0]).toEqual({
        job_id: 'job-123',
        job_type: 'export',
        progress: 50,
        status: 'running',
      });
      expect(onJobProgress).toHaveBeenCalledWith(progressMessage.data);
    });
  });

  describe('job completion', () => {
    it('should remove job from active jobs on completion', () => {
      const onJobCompleted = vi.fn();
      const { result } = renderHook(() => useJobWebSocket({ onJobCompleted }), {
        wrapper: createWrapper(),
      });

      simulateMessage({
        type: 'job_progress',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          progress: 90,
          status: 'running',
        },
      });

      expect(result.current.activeJobs).toHaveLength(1);

      const completedMessage: JobCompletedMessage = {
        type: 'job_completed',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          result: { file_path: '/exports/test.json' },
        },
      };

      simulateMessage(completedMessage);

      expect(result.current.activeJobs).toHaveLength(0);
      expect(onJobCompleted).toHaveBeenCalledWith(completedMessage.data);
    });

    it('should show success toast on completion', () => {
      renderHook(() => useJobWebSocket({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      simulateMessage({
        type: 'job_completed',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          result: null,
        },
      });

      expect(mockSuccess).toHaveBeenCalledWith('Export completed successfully');
    });
  });

  describe('job failure', () => {
    it('should remove job from active jobs on failure', () => {
      const onJobFailed = vi.fn();
      const { result } = renderHook(() => useJobWebSocket({ onJobFailed }), {
        wrapper: createWrapper(),
      });

      simulateMessage({
        type: 'job_progress',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          progress: 50,
          status: 'running',
        },
      });

      const failedMessage: JobFailedMessage = {
        type: 'job_failed',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          error: 'Database connection failed',
        },
      };

      simulateMessage(failedMessage);

      expect(result.current.activeJobs).toHaveLength(0);
      expect(onJobFailed).toHaveBeenCalledWith(failedMessage.data);
    });

    it('should show error toast on failure', () => {
      renderHook(() => useJobWebSocket({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      simulateMessage({
        type: 'job_failed',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          error: 'Connection timeout',
        },
      });

      expect(mockError).toHaveBeenCalledWith('Export failed: Connection timeout');
    });
  });

  describe('helper functions', () => {
    it('isJobRunning should return true for running jobs', () => {
      const { result } = renderHook(() => useJobWebSocket(), {
        wrapper: createWrapper(),
      });

      simulateMessage({
        type: 'job_progress',
        data: {
          job_id: 'job-123',
          job_type: 'export',
          progress: 50,
          status: 'running',
        },
      });

      expect(result.current.isJobRunning('export')).toBe(true);
      expect(result.current.isJobRunning('cleanup')).toBe(false);
    });
  });
});
