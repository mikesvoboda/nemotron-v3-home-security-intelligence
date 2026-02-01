import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { fetchApi } from './api';
import {
  fetchSupervisorStatus,
  startWorker,
  stopWorker,
  restartWorker,
  resetWorkerRestartCount,
  fetchRestartHistory,
} from './supervisorApi';

// Mock the fetchApi function
vi.mock('./api', () => ({
  fetchApi: vi.fn(),
}));

const mockFetchApi = vi.mocked(fetchApi);

describe('supervisorApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchSupervisorStatus', () => {
    it('calls GET /api/system/supervisor', async () => {
      const mockData = {
        running: true,
        worker_count: 4,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      };

      mockFetchApi.mockResolvedValue(mockData);

      const result = await fetchSupervisorStatus();

      expect(mockFetchApi).toHaveBeenCalledWith('/api/system/supervisor');
      expect(result).toEqual(mockData);
    });

    it('throws error on failure', async () => {
      const errorMessage = 'Network error';
      mockFetchApi.mockRejectedValue(new Error(errorMessage));

      await expect(fetchSupervisorStatus()).rejects.toThrow(errorMessage);
    });

    it('returns all worker statuses', async () => {
      const mockData = {
        running: true,
        worker_count: 3,
        workers: [
          {
            name: 'worker1',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
          {
            name: 'worker2',
            status: 'crashed',
            restart_count: 2,
            max_restarts: 5,
            last_started_at: '2025-01-31T09:00:00Z',
            last_crashed_at: '2025-01-31T10:00:00Z',
            error: 'Connection lost',
          },
          {
            name: 'worker3',
            status: 'failed',
            restart_count: 5,
            max_restarts: 5,
            last_started_at: '2025-01-31T08:00:00Z',
            last_crashed_at: '2025-01-31T10:30:00Z',
            error: 'Max restarts exceeded',
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      };

      mockFetchApi.mockResolvedValue(mockData);

      const result = await fetchSupervisorStatus();

      expect(result.workers).toHaveLength(3);
      expect(result.workers[0].status).toBe('running');
      expect(result.workers[1].status).toBe('crashed');
      expect(result.workers[2].status).toBe('failed');
    });
  });

  describe('startWorker', () => {
    it('calls POST /api/system/supervisor/workers/{name}/start', async () => {
      const mockResponse = {
        success: true,
        message: "Worker 'file_watcher' started successfully",
        worker_name: 'file_watcher',
      };

      mockFetchApi.mockResolvedValue(mockResponse);

      const result = await startWorker('file_watcher');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/workers/file_watcher/start',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('throws error on failure', async () => {
      const errorMessage = 'Worker not found';
      mockFetchApi.mockRejectedValue(new Error(errorMessage));

      await expect(startWorker('unknown_worker')).rejects.toThrow(errorMessage);
    });

    it('encodes worker name in URL', async () => {
      const mockResponse = {
        success: true,
        message: 'Started',
        worker_name: 'worker with spaces',
      };

      mockFetchApi.mockResolvedValue(mockResponse);

      await startWorker('worker with spaces');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/workers/worker with spaces/start',
        { method: 'POST' }
      );
    });
  });

  describe('stopWorker', () => {
    it('calls POST /api/system/supervisor/workers/{name}/stop', async () => {
      const mockResponse = {
        success: true,
        message: "Worker 'detection_worker' stopped successfully",
        worker_name: 'detection_worker',
      };

      mockFetchApi.mockResolvedValue(mockResponse);

      const result = await stopWorker('detection_worker');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/workers/detection_worker/stop',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('throws error on failure', async () => {
      const errorMessage = 'Worker already stopped';
      mockFetchApi.mockRejectedValue(new Error(errorMessage));

      await expect(stopWorker('stopped_worker')).rejects.toThrow(errorMessage);
    });
  });

  describe('restartWorker', () => {
    it('calls POST /api/system/supervisor/workers/{name}/restart', async () => {
      const mockResponse = {
        success: true,
        message: "Worker 'file_watcher' restarted successfully",
        worker_name: 'file_watcher',
      };

      mockFetchApi.mockResolvedValue(mockResponse);

      const result = await restartWorker('file_watcher');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/workers/file_watcher/restart',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('throws error on failure', async () => {
      const errorMessage = 'Worker not running';
      mockFetchApi.mockRejectedValue(new Error(errorMessage));

      await expect(restartWorker('stopped_worker')).rejects.toThrow(errorMessage);
    });
  });

  describe('resetWorkerRestartCount', () => {
    it('calls POST /api/system/supervisor/reset/{name}', async () => {
      const mockResponse = {
        success: true,
        message: "Worker 'detection_worker' restart count reset successfully",
        worker_name: 'detection_worker',
      };

      mockFetchApi.mockResolvedValue(mockResponse);

      const result = await resetWorkerRestartCount('detection_worker');

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/reset/detection_worker',
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('throws error on failure', async () => {
      const errorMessage = 'Cannot reset running worker';
      mockFetchApi.mockRejectedValue(new Error(errorMessage));

      await expect(resetWorkerRestartCount('running_worker')).rejects.toThrow(
        errorMessage
      );
    });
  });

  describe('fetchRestartHistory', () => {
    it('calls GET /api/system/supervisor/restart-history with default params', async () => {
      const mockData = {
        items: [
          {
            worker_name: 'detection_worker',
            timestamp: '2025-01-31T10:30:00Z',
            attempt: 3,
            status: 'success',
            error: null,
          },
        ],
        pagination: {
          total: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      };

      mockFetchApi.mockResolvedValue(mockData);

      const result = await fetchRestartHistory();

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/restart-history'
      );
      expect(result).toEqual(mockData);
    });

    it('calls with limit and offset parameters', async () => {
      const mockData = {
        items: [],
        pagination: {
          total: 100,
          limit: 20,
          offset: 40,
          has_more: true,
        },
      };

      mockFetchApi.mockResolvedValue(mockData);

      await fetchRestartHistory({ limit: 20, offset: 40 });

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/restart-history?limit=20&offset=40'
      );
    });

    it('calls with worker name filter', async () => {
      const mockData = {
        items: [
          {
            worker_name: 'file_watcher',
            timestamp: '2025-01-31T10:00:00Z',
            attempt: 1,
            status: 'success',
            error: null,
          },
        ],
        pagination: {
          total: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      };

      mockFetchApi.mockResolvedValue(mockData);

      await fetchRestartHistory({ workerName: 'file_watcher' });

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/restart-history?workerName=file_watcher'
      );
    });

    it('calls with combined parameters', async () => {
      const mockData = {
        items: [],
        pagination: {
          total: 0,
          limit: 10,
          offset: 5,
          has_more: false,
        },
      };

      mockFetchApi.mockResolvedValue(mockData);

      await fetchRestartHistory({
        workerName: 'detection_worker',
        limit: 10,
        offset: 5,
      });

      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/system/supervisor/restart-history?workerName=detection_worker&limit=10&offset=5'
      );
    });

    it('throws error on failure', async () => {
      const errorMessage = 'Database error';
      mockFetchApi.mockRejectedValue(new Error(errorMessage));

      await expect(fetchRestartHistory()).rejects.toThrow(errorMessage);
    });

    it('returns items sorted by timestamp', async () => {
      const mockData = {
        items: [
          {
            worker_name: 'worker1',
            timestamp: '2025-01-31T10:30:00Z',
            attempt: 2,
            status: 'success',
            error: null,
          },
          {
            worker_name: 'worker2',
            timestamp: '2025-01-31T10:00:00Z',
            attempt: 1,
            status: 'success',
            error: null,
          },
        ],
        pagination: {
          total: 2,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      };

      mockFetchApi.mockResolvedValue(mockData);

      const result = await fetchRestartHistory();

      expect(result.items[0].timestamp).toBe('2025-01-31T10:30:00Z');
      expect(result.items[1].timestamp).toBe('2025-01-31T10:00:00Z');
    });

    it('includes failed restart attempts', async () => {
      const mockData = {
        items: [
          {
            worker_name: 'detection_worker',
            timestamp: '2025-01-31T10:30:00Z',
            attempt: 3,
            status: 'failed',
            error: 'Connection timeout',
          },
        ],
        pagination: {
          total: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      };

      mockFetchApi.mockResolvedValue(mockData);

      const result = await fetchRestartHistory();

      expect(result.items[0].status).toBe('failed');
      expect(result.items[0].error).toBe('Connection timeout');
    });
  });
});
