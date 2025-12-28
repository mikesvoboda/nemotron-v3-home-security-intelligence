import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  ApiError,
  buildWebSocketUrl,
  buildWebSocketUrlInternal,
  getApiKey,
  fetchCameras,
  fetchCamera,
  createCamera,
  updateCamera,
  deleteCamera,
  getCameraSnapshotUrl,
  fetchHealth,
  fetchGPUStats,
  fetchGpuHistory,
  fetchConfig,
  updateConfig,
  fetchStats,
  fetchTelemetry,
  fetchEvents,
  fetchEvent,
  fetchEventStats,
  updateEvent,
  bulkUpdateEvents,
  fetchEventDetections,
  fetchLogStats,
  fetchLogs,
  getMediaUrl,
  getThumbnailUrl,
  getDetectionImageUrl,
  exportEventsCSV,
  type Camera,
  type CameraCreate,
  type CameraUpdate,
  type HealthResponse,
  type GPUStats,
  type GPUStatsHistoryResponse,
  type SystemConfig,
  type SystemConfigUpdate,
  type SystemStats,
  type TelemetryResponse,
  type Event,
  type EventListResponse,
  type EventStatsResponse,
  type EventsQueryParams,
  type EventStatsQueryParams,
  type EventUpdateData,
  type Detection,
  type DetectionListResponse,
  type LogStats,
  type LogsResponse,
  type LogsQueryParams,
  type ExportQueryParams,
} from './api';

// Mock data
const mockCamera: Camera = {
  id: 'cam-1',
  name: 'Front Door',
  folder_path: '/export/foscam/front-door',
  status: 'online',
  created_at: '2025-01-01T00:00:00Z',
  last_seen_at: '2025-01-02T12:00:00Z',
};

const mockCameras: Camera[] = [
  mockCamera,
  {
    id: 'cam-2',
    name: 'Backyard',
    folder_path: '/export/foscam/backyard',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: null,
  },
];

const mockHealth: HealthResponse = {
  status: 'healthy',
  services: {
    database: { status: 'healthy', message: 'Database operational', details: null },
    redis: { status: 'healthy', message: 'Redis connected', details: { version: '7.0.0' } },
    ai: { status: 'healthy', message: 'AI services operational', details: null },
  },
  timestamp: '2025-01-01T00:00:00Z',
};

const mockGPUStats: GPUStats = {
  utilization: 45.5,
  memory_used: 8192,
  memory_total: 24576,
  temperature: 65,
  inference_fps: 30.2,
};

const mockConfig: SystemConfig = {
  app_name: 'Home Security Dashboard',
  version: '0.1.0',
  retention_days: 30,
  batch_window_seconds: 90,
  batch_idle_timeout_seconds: 30,
  detection_confidence_threshold: 0.5,
};

const mockStats: SystemStats = {
  total_cameras: 2,
  total_events: 150,
  total_detections: 500,
  uptime_seconds: 86400,
};

const mockTelemetry: TelemetryResponse = {
  queues: {
    detection_queue: 5,
    analysis_queue: 2,
  },
  latencies: {
    watch: {
      avg_ms: 20,
      p50_ms: 10,
      p95_ms: 50,
      p99_ms: 100,
      min_ms: 5,
      max_ms: 200,
      sample_count: 100,
    },
    detect: {
      avg_ms: 200,
      p50_ms: 100,
      p95_ms: 500,
      p99_ms: 1000,
      min_ms: 50,
      max_ms: 2000,
      sample_count: 100,
    },
  },
  timestamp: '2025-01-01T12:00:00Z',
};

const mockEvent: Event = {
  id: 1,
  camera_id: 'cam-1',
  started_at: '2025-01-01T10:00:00Z',
  ended_at: '2025-01-01T10:05:00Z',
  risk_score: 75,
  risk_level: 'high',
  summary: 'Suspicious activity detected',
  reviewed: false,
  notes: null,
  detection_count: 5,
};

const mockEventListResponse: EventListResponse = {
  events: [mockEvent],
  count: 1,
  limit: 50,
  offset: 0,
};

const mockEventStatsResponse: EventStatsResponse = {
  total_events: 44,
  events_by_risk_level: {
    critical: 2,
    high: 5,
    medium: 12,
    low: 25,
  },
  events_by_camera: [
    {
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      event_count: 30,
    },
    {
      camera_id: 'cam-2',
      camera_name: 'Backyard',
      event_count: 14,
    },
  ],
};

const mockDetection: Detection = {
  id: 1,
  camera_id: 'cam-1',
  file_path: '/path/to/image.jpg',
  file_type: 'image/jpeg',
  detected_at: '2025-01-01T10:00:00Z',
  object_type: 'person',
  confidence: 0.95,
  bbox_x: 100,
  bbox_y: 100,
  bbox_width: 200,
  bbox_height: 300,
  thumbnail_path: '/path/to/thumb.jpg',
};

const mockDetectionListResponse: DetectionListResponse = {
  detections: [mockDetection],
  count: 1,
  limit: 50,
  offset: 0,
};

const mockLogStats: LogStats = {
  total_today: 100,
  errors_today: 5,
  warnings_today: 10,
  by_component: { frontend: 50, backend: 50 },
  by_level: { INFO: 85, WARNING: 10, ERROR: 5 },
  top_component: 'frontend',
};

const mockLogsResponse: LogsResponse = {
  logs: [
    {
      id: 1,
      timestamp: '2025-01-01T10:00:00Z',
      level: 'INFO',
      component: 'frontend',
      message: 'Test log message',
      source: 'frontend',
    },
  ],
  count: 1,
  limit: 50,
  offset: 0,
};

// Helper to create mock fetch response
function createMockResponse<T>(data: T, status = 200, statusText = 'OK'): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(data),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

function createMockErrorResponse(status: number, statusText: string, detail?: string): Response {
  const errorBody = detail ? { detail } : null;
  return {
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve(errorBody),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

describe('buildWebSocketUrlInternal', () => {
  describe('without VITE_WS_BASE_URL', () => {
    it('builds WS URL from window.location.host when wsBaseUrl not set', () => {
      const url = buildWebSocketUrlInternal('/ws/events', undefined, undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).toBe('ws://localhost:5173/ws/events');
    });

    it('uses ws: protocol for http: pages', () => {
      const url = buildWebSocketUrlInternal('/ws/system', undefined, undefined, {
        protocol: 'http:',
        host: 'example.com',
      });
      expect(url).toBe('ws://example.com/ws/system');
    });

    it('uses wss: protocol for https: pages', () => {
      const url = buildWebSocketUrlInternal('/ws/events', undefined, undefined, {
        protocol: 'https:',
        host: 'secure.example.com',
      });
      expect(url).toBe('wss://secure.example.com/ws/events');
    });

    it('falls back to localhost:8000 when no window location', () => {
      const url = buildWebSocketUrlInternal('/ws/events', undefined, undefined, undefined);
      expect(url).toBe('ws://localhost:8000/ws/events');
    });
  });

  describe('with VITE_WS_BASE_URL', () => {
    it('uses configured WS base URL', () => {
      const url = buildWebSocketUrlInternal('/ws/events', 'ws://backend:8000', undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).toBe('ws://backend:8000/ws/events');
    });

    it('strips trailing slash from WS base URL', () => {
      const url = buildWebSocketUrlInternal('/ws/events', 'wss://api.example.com/', undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).toBe('wss://api.example.com/ws/events');
    });

    it('ignores window.location when WS base URL is set', () => {
      const url = buildWebSocketUrlInternal('/ws/system', 'wss://production.api.com', undefined, {
        protocol: 'http:',
        host: 'localhost:3000',
      });
      expect(url).toBe('wss://production.api.com/ws/system');
    });
  });

  describe('with API key', () => {
    it('appends api_key query parameter when apiKey is set', () => {
      const url = buildWebSocketUrlInternal('/ws/events', undefined, 'secret-key-123', {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).toBe('ws://localhost:5173/ws/events?api_key=secret-key-123');
    });

    it('appends api_key to URL with existing query params using &', () => {
      const url = buildWebSocketUrlInternal('/ws/events?filter=active', undefined, 'my-api-key', {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).toBe('ws://localhost:5173/ws/events?filter=active&api_key=my-api-key');
    });

    it('URL-encodes special characters in API key', () => {
      const url = buildWebSocketUrlInternal(
        '/ws/events',
        undefined,
        'key with spaces&special=chars',
        {
          protocol: 'http:',
          host: 'localhost:5173',
        }
      );
      expect(url).toContain('api_key=key%20with%20spaces%26special%3Dchars');
    });

    it('works with both WS base URL and API key', () => {
      const url = buildWebSocketUrlInternal('/ws/events', 'wss://api.example.com', 'secure-token', {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).toBe('wss://api.example.com/ws/events?api_key=secure-token');
    });

    it('does not append api_key when apiKey is undefined', () => {
      const url = buildWebSocketUrlInternal('/ws/events', undefined, undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).not.toContain('api_key');
    });

    it('does not append api_key when apiKey is empty string', () => {
      const url = buildWebSocketUrlInternal('/ws/events', undefined, '', {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(url).not.toContain('api_key');
    });
  });
});

describe('buildWebSocketUrl', () => {
  it('builds WS URL using window.location in browser environment', () => {
    // In jsdom test environment, this should use window.location
    const url = buildWebSocketUrl('/ws/events');
    expect(url).toContain('/ws/events');
    expect(url).toMatch(/^wss?:\/\//);
  });

  it('returns URL with correct structure', () => {
    const url = buildWebSocketUrl('/ws/system');
    // Should have protocol, host, and endpoint
    expect(url).toMatch(/^wss?:\/\/[^/]+\/ws\/system$/);
  });
});

describe('getApiKey', () => {
  it('returns undefined when VITE_API_KEY is not set', () => {
    // In test environment, VITE_API_KEY is not set by default
    const apiKey = getApiKey();
    expect(apiKey).toBeUndefined();
  });
});

describe('ApiError', () => {
  it('creates an error with status and message', () => {
    const error = new ApiError(404, 'Not Found');
    expect(error.name).toBe('ApiError');
    expect(error.status).toBe(404);
    expect(error.message).toBe('Not Found');
    expect(error.data).toBeUndefined();
  });

  it('creates an error with additional data', () => {
    const data = { field: 'value' };
    const error = new ApiError(400, 'Bad Request', data);
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad Request');
    expect(error.data).toEqual(data);
  });
});

describe('Camera API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchCameras', () => {
    it('fetches all cameras successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockResponse({ cameras: mockCameras, count: mockCameras.length })
      );

      const result = await fetchCameras();

      expect(fetch).toHaveBeenCalledWith('/api/cameras', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockCameras);
    });

    it('handles empty camera list', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse({ cameras: [], count: 0 }));

      const result = await fetchCameras();

      expect(result).toEqual([]);
    });

    it('throws ApiError on 500 error', async () => {
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Database error')
      );

      await expect(fetchCameras()).rejects.toThrow(ApiError);

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Database error')
      );
      await expect(fetchCameras()).rejects.toMatchObject({
        status: 500,
        message: 'Database error',
      });
    });

    it('throws ApiError on network error', async () => {
      vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));

      await expect(fetchCameras()).rejects.toThrow(ApiError);

      vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));
      await expect(fetchCameras()).rejects.toMatchObject({
        status: 0,
        message: 'Network failure',
      });
    });
  });

  describe('fetchCamera', () => {
    it('fetches a single camera successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockCamera));

      const result = await fetchCamera('cam-1');

      expect(fetch).toHaveBeenCalledWith('/api/cameras/cam-1', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockCamera);
    });

    it('throws ApiError on 404 not found', async () => {
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(404, 'Not Found', 'Camera not found')
      );

      await expect(fetchCamera('invalid-id')).rejects.toThrow(ApiError);

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(404, 'Not Found', 'Camera not found')
      );
      await expect(fetchCamera('invalid-id')).rejects.toMatchObject({
        status: 404,
        message: 'Camera not found',
      });
    });
  });

  describe('createCamera', () => {
    it('creates a camera successfully', async () => {
      const createData: CameraCreate = {
        name: 'New Camera',
        folder_path: '/export/foscam/new-camera',
        status: 'online',
      };

      vi.mocked(fetch).mockResolvedValueOnce(
        createMockResponse({ ...mockCamera, ...createData }, 201)
      );

      const result = await createCamera(createData);

      expect(fetch).toHaveBeenCalledWith('/api/cameras', {
        method: 'POST',
        body: JSON.stringify(createData),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result.name).toBe(createData.name);
      expect(result.folder_path).toBe(createData.folder_path);
    });

    it('creates a camera with default status', async () => {
      const createData: CameraCreate = {
        name: 'Minimal Camera',
        folder_path: '/export/foscam/minimal',
        status: 'online', // Required field with backend default
      };

      vi.mocked(fetch).mockResolvedValueOnce(
        createMockResponse({ ...mockCamera, ...createData }, 201)
      );

      const result = await createCamera(createData);

      expect(result.name).toBe(createData.name);
    });

    it('throws ApiError on 400 validation error', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(400, 'Bad Request', 'Invalid folder path')
      );

      await expect(
        createCamera({ name: 'Bad', folder_path: 'invalid', status: 'online' })
      ).rejects.toThrow(ApiError);
    });
  });

  describe('updateCamera', () => {
    it('updates a camera successfully', async () => {
      const updateData: CameraUpdate = {
        name: 'Updated Front Door',
        status: 'offline',
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse({ ...mockCamera, ...updateData }));

      const result = await updateCamera('cam-1', updateData);

      expect(fetch).toHaveBeenCalledWith('/api/cameras/cam-1', {
        method: 'PATCH',
        body: JSON.stringify(updateData),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result.name).toBe(updateData.name);
      expect(result.status).toBe(updateData.status);
    });

    it('updates camera with partial data', async () => {
      const updateData: CameraUpdate = { status: 'offline' };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse({ ...mockCamera, ...updateData }));

      const result = await updateCamera('cam-1', updateData);

      expect(result.status).toBe('offline');
      expect(result.name).toBe(mockCamera.name);
    });

    it('throws ApiError on 404 not found', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Camera not found')
      );

      await expect(updateCamera('invalid-id', { name: 'Test' })).rejects.toThrow(ApiError);
    });
  });

  describe('deleteCamera', () => {
    it('deletes a camera successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(null, 204, 'No Content'));

      const result = await deleteCamera('cam-1');

      expect(fetch).toHaveBeenCalledWith('/api/cameras/cam-1', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toBeUndefined();
    });

    it('throws ApiError on 404 not found', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Camera not found')
      );

      await expect(deleteCamera('invalid-id')).rejects.toThrow(ApiError);
    });

    it('throws ApiError on 409 conflict', async () => {
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(409, 'Conflict', 'Cannot delete camera with active events')
      );

      await expect(deleteCamera('cam-1')).rejects.toThrow(ApiError);

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(409, 'Conflict', 'Cannot delete camera with active events')
      );
      await expect(deleteCamera('cam-1')).rejects.toMatchObject({
        status: 409,
        message: 'Cannot delete camera with active events',
      });
    });
  });
});

describe('System API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchHealth', () => {
    it('fetches health status successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHealth));

      const result = await fetchHealth();

      expect(fetch).toHaveBeenCalledWith('/api/system/health', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockHealth);
      expect(result.status).toBe('healthy');
    });

    it('handles degraded health status', async () => {
      const degradedHealth: HealthResponse = {
        ...mockHealth,
        status: 'degraded',
        services: {
          database: { status: 'healthy', message: 'Database operational', details: null },
          redis: { status: 'unhealthy', message: 'Redis connection error', details: null },
          ai: { status: 'healthy', message: null, details: null },
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(degradedHealth));

      const result = await fetchHealth();

      expect(result.status).toBe('degraded');
      expect(result.services.redis.status).toBe('unhealthy');
    });
  });

  describe('fetchGPUStats', () => {
    it('fetches GPU stats successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGPUStats));

      const result = await fetchGPUStats();

      expect(fetch).toHaveBeenCalledWith('/api/system/gpu', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockGPUStats);
      expect(result.utilization).toBe(45.5);
    });

    it('handles null GPU stats when GPU unavailable', async () => {
      const nullStats: GPUStats = {
        utilization: null,
        memory_used: null,
        memory_total: null,
        temperature: null,
        inference_fps: null,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(nullStats));

      const result = await fetchGPUStats();

      expect(result.utilization).toBeNull();
      expect(result.memory_used).toBeNull();
    });
  });

  describe('fetchGpuHistory', () => {
    it('fetches GPU history successfully with default limit', async () => {
      const mockHistoryResponse: GPUStatsHistoryResponse = {
        samples: [
          {
            recorded_at: '2025-01-01T10:00:00Z',
            utilization: 45.5,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.2,
          },
          {
            recorded_at: '2025-01-01T10:01:00Z',
            utilization: 50.0,
            memory_used: 8500,
            memory_total: 24576,
            temperature: 66,
            inference_fps: 28.5,
          },
        ],
        count: 2,
        limit: 100,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHistoryResponse));

      const result = await fetchGpuHistory();

      expect(fetch).toHaveBeenCalledWith('/api/system/gpu/history?limit=100', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result.samples).toHaveLength(2);
      expect(result.count).toBe(2);
      expect(result.samples[0].utilization).toBe(45.5);
    });

    it('fetches GPU history with custom limit', async () => {
      const mockHistoryResponse: GPUStatsHistoryResponse = {
        samples: [
          {
            recorded_at: '2025-01-01T10:00:00Z',
            utilization: 45.5,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.2,
          },
        ],
        count: 1,
        limit: 50,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHistoryResponse));

      const result = await fetchGpuHistory(50);

      expect(fetch).toHaveBeenCalledWith('/api/system/gpu/history?limit=50', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result.samples).toHaveLength(1);
    });

    it('handles empty GPU history', async () => {
      const emptyHistoryResponse: GPUStatsHistoryResponse = {
        samples: [],
        count: 0,
        limit: 100,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyHistoryResponse));

      const result = await fetchGpuHistory();

      expect(result.samples).toEqual([]);
      expect(result.count).toBe(0);
    });

    it('handles samples with null values', async () => {
      const mockHistoryResponse: GPUStatsHistoryResponse = {
        samples: [
          {
            recorded_at: '2025-01-01T10:00:00Z',
            utilization: null,
            memory_used: null,
            memory_total: null,
            temperature: null,
            inference_fps: null,
          },
        ],
        count: 1,
        limit: 100,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHistoryResponse));

      const result = await fetchGpuHistory();

      expect(result.samples[0].utilization).toBeNull();
      expect(result.samples[0].memory_used).toBeNull();
    });

    it('throws ApiError on 500 error', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(500, 'Internal Server Error', 'GPU monitoring service unavailable')
      );

      await expect(fetchGpuHistory()).rejects.toThrow(ApiError);
    });
  });

  describe('fetchConfig', () => {
    it('fetches system config successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockConfig));

      const result = await fetchConfig();

      expect(fetch).toHaveBeenCalledWith('/api/system/config', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockConfig);
      expect(result.retention_days).toBe(30);
    });
  });

  describe('updateConfig', () => {
    it('updates system config successfully', async () => {
      const updateData: SystemConfigUpdate = {
        retention_days: 60,
        batch_window_seconds: 120,
      };

      const updatedConfig: SystemConfig = {
        ...mockConfig,
        retention_days: 60,
        batch_window_seconds: 120,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(updatedConfig));

      const result = await updateConfig(updateData);

      expect(fetch).toHaveBeenCalledWith('/api/system/config', {
        method: 'PATCH',
        body: JSON.stringify(updateData),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result.retention_days).toBe(60);
      expect(result.batch_window_seconds).toBe(120);
    });

    it('updates partial config', async () => {
      const updateData: SystemConfigUpdate = {
        detection_confidence_threshold: 0.7,
      };

      const updatedConfig: SystemConfig = {
        ...mockConfig,
        detection_confidence_threshold: 0.7,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(updatedConfig));

      const result = await updateConfig(updateData);

      expect(result.detection_confidence_threshold).toBe(0.7);
    });
  });

  describe('fetchStats', () => {
    it('fetches system stats successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStats));

      const result = await fetchStats();

      expect(fetch).toHaveBeenCalledWith('/api/system/stats', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockStats);
      expect(result.total_cameras).toBe(2);
      expect(result.total_events).toBe(150);
    });

    it('handles zero stats for new system', async () => {
      const zeroStats: SystemStats = {
        total_cameras: 0,
        total_events: 0,
        total_detections: 0,
        uptime_seconds: 0,
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(zeroStats));

      const result = await fetchStats();

      expect(result.total_cameras).toBe(0);
      expect(result.uptime_seconds).toBe(0);
    });
  });

  describe('fetchTelemetry', () => {
    it('fetches telemetry data successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockTelemetry));

      const result = await fetchTelemetry();

      expect(fetch).toHaveBeenCalledWith('/api/system/telemetry', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockTelemetry);
      expect(result.queues.detection_queue).toBe(5);
      expect(result.queues.analysis_queue).toBe(2);
    });

    it('handles empty queues', async () => {
      const emptyTelemetry: TelemetryResponse = {
        queues: {
          detection_queue: 0,
          analysis_queue: 0,
        },
        latencies: null,
        timestamp: '2025-01-01T12:00:00Z',
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyTelemetry));

      const result = await fetchTelemetry();

      expect(result.queues.detection_queue).toBe(0);
      expect(result.queues.analysis_queue).toBe(0);
      expect(result.latencies).toBeNull();
    });

    it('handles high queue depths indicating backup', async () => {
      const backupTelemetry: TelemetryResponse = {
        queues: {
          detection_queue: 15,
          analysis_queue: 12,
        },
        latencies: {
          watch: {
            avg_ms: 100,
            p50_ms: 80,
            p95_ms: 200,
            p99_ms: 500,
            min_ms: 20,
            max_ms: 800,
            sample_count: 50,
          },
          detect: {
            avg_ms: 800,
            p50_ms: 600,
            p95_ms: 1500,
            p99_ms: 3000,
            min_ms: 200,
            max_ms: 5000,
            sample_count: 50,
          },
        },
        timestamp: '2025-01-01T12:00:00Z',
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(backupTelemetry));

      const result = await fetchTelemetry();

      expect(result.queues.detection_queue).toBe(15);
      expect(result.queues.analysis_queue).toBe(12);
    });

    it('throws ApiError on server error', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(500, 'Internal Server Error', 'Redis unavailable')
      );

      await expect(fetchTelemetry()).rejects.toThrow(ApiError);

      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(500, 'Internal Server Error', 'Redis unavailable')
      );
      await expect(fetchTelemetry()).rejects.toMatchObject({
        status: 500,
        message: 'Redis unavailable',
      });
    });
  });
});

describe('Events API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchEvents', () => {
    it('fetches events without params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventListResponse));

      const result = await fetchEvents();

      expect(fetch).toHaveBeenCalledWith('/api/events', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result.events).toEqual([mockEvent]);
    });

    it('fetches events with all query params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventListResponse));

      const params: EventsQueryParams = {
        camera_id: 'cam-1',
        risk_level: 'high',
        start_date: '2025-01-01',
        end_date: '2025-01-31',
        reviewed: false,
        object_type: 'person',
        limit: 25,
        offset: 10,
      };

      await fetchEvents(params);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/events?'),
        expect.any(Object)
      );
      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('camera_id=cam-1');
      expect(callUrl).toContain('risk_level=high');
      expect(callUrl).toContain('start_date=2025-01-01');
      expect(callUrl).toContain('end_date=2025-01-31');
      expect(callUrl).toContain('reviewed=false');
      expect(callUrl).toContain('object_type=person');
      expect(callUrl).toContain('limit=25');
      expect(callUrl).toContain('offset=10');
    });

    it('fetches events with partial params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventListResponse));

      const params: EventsQueryParams = {
        camera_id: 'cam-1',
        limit: 10,
      };

      await fetchEvents(params);

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('camera_id=cam-1');
      expect(callUrl).toContain('limit=10');
      expect(callUrl).not.toContain('risk_level');
    });
  });

  describe('fetchEvent', () => {
    it('fetches a single event', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEvent));

      const result = await fetchEvent(1);

      expect(fetch).toHaveBeenCalledWith('/api/events/1', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockEvent);
    });

    it('throws ApiError on 404', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Event not found')
      );

      await expect(fetchEvent(999)).rejects.toThrow(ApiError);
    });
  });

  describe('fetchEventStats', () => {
    it('fetches event stats without params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventStatsResponse));

      const result = await fetchEventStats();

      expect(fetch).toHaveBeenCalledWith('/api/events/stats', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockEventStatsResponse);
      expect(result.total_events).toBe(44);
    });

    it('fetches event stats with date params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventStatsResponse));

      const params: EventStatsQueryParams = {
        start_date: '2025-01-01T00:00:00Z',
        end_date: '2025-01-31T23:59:59Z',
      };

      await fetchEventStats(params);

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('/api/events/stats?');
      expect(callUrl).toContain('start_date=2025-01-01T00%3A00%3A00Z');
      expect(callUrl).toContain('end_date=2025-01-31T23%3A59%3A59Z');
    });

    it('fetches event stats with only start_date', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventStatsResponse));

      const params: EventStatsQueryParams = {
        start_date: '2025-01-01T00:00:00Z',
      };

      await fetchEventStats(params);

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('start_date=2025-01-01T00%3A00%3A00Z');
      expect(callUrl).not.toContain('end_date');
    });

    it('returns events by risk level breakdown', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventStatsResponse));

      const result = await fetchEventStats();

      expect(result.events_by_risk_level.critical).toBe(2);
      expect(result.events_by_risk_level.high).toBe(5);
      expect(result.events_by_risk_level.medium).toBe(12);
      expect(result.events_by_risk_level.low).toBe(25);
    });

    it('returns events by camera breakdown', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventStatsResponse));

      const result = await fetchEventStats();

      expect(result.events_by_camera).toHaveLength(2);
      expect(result.events_by_camera[0].camera_id).toBe('cam-1');
      expect(result.events_by_camera[0].camera_name).toBe('Front Door');
      expect(result.events_by_camera[0].event_count).toBe(30);
    });

    it('handles empty stats', async () => {
      const emptyStats: EventStatsResponse = {
        total_events: 0,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        events_by_camera: [],
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyStats));

      const result = await fetchEventStats();

      expect(result.total_events).toBe(0);
      expect(result.events_by_camera).toEqual([]);
    });
  });

  describe('updateEvent', () => {
    it('updates event reviewed status', async () => {
      const updateData: EventUpdateData = { reviewed: true };
      const updatedEvent = { ...mockEvent, reviewed: true };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(updatedEvent));

      const result = await updateEvent(1, updateData);

      expect(fetch).toHaveBeenCalledWith('/api/events/1', {
        method: 'PATCH',
        body: JSON.stringify(updateData),
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result.reviewed).toBe(true);
    });

    it('updates event notes', async () => {
      const updateData: EventUpdateData = { notes: 'Test notes' };
      const updatedEvent = { ...mockEvent, notes: 'Test notes' };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(updatedEvent));

      const result = await updateEvent(1, updateData);

      expect(result.notes).toBe('Test notes');
    });

    it('clears event notes', async () => {
      const updateData: EventUpdateData = { notes: null };
      const updatedEvent = { ...mockEvent, notes: null };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(updatedEvent));

      const result = await updateEvent(1, updateData);

      expect(result.notes).toBeNull();
    });
  });

  describe('bulkUpdateEvents', () => {
    it('updates multiple events successfully', async () => {
      const updatedEvent1 = { ...mockEvent, id: 1, reviewed: true };
      const updatedEvent2 = { ...mockEvent, id: 2, reviewed: true };

      vi.mocked(fetch)
        .mockResolvedValueOnce(createMockResponse(updatedEvent1))
        .mockResolvedValueOnce(createMockResponse(updatedEvent2));

      const result = await bulkUpdateEvents([1, 2], { reviewed: true });

      expect(result.successful).toEqual([1, 2]);
      expect(result.failed).toEqual([]);
    });

    it('handles partial failures', async () => {
      vi.mocked(fetch)
        .mockResolvedValueOnce(createMockResponse({ ...mockEvent, reviewed: true }))
        .mockResolvedValueOnce(createMockErrorResponse(404, 'Not Found', 'Event not found'));

      const result = await bulkUpdateEvents([1, 2], { reviewed: true });

      expect(result.successful).toContain(1);
      expect(result.failed).toHaveLength(1);
      expect(result.failed[0].id).toBe(2);
    });

    it('handles non-Error failures', async () => {
      vi.mocked(fetch)
        .mockResolvedValueOnce(createMockResponse({ ...mockEvent, reviewed: true }))
        .mockRejectedValueOnce('string error');

      const result = await bulkUpdateEvents([1, 2], { reviewed: true });

      expect(result.successful).toContain(1);
      expect(result.failed[0].error).toBe('Network request failed');
    });
  });
});

describe('Detections API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchEventDetections', () => {
    it('fetches detections for an event', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockDetectionListResponse));

      const result = await fetchEventDetections(1);

      expect(fetch).toHaveBeenCalledWith('/api/events/1/detections', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result.detections).toEqual([mockDetection]);
    });

    it('fetches detections with pagination params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockDetectionListResponse));

      await fetchEventDetections(1, { limit: 10, offset: 5 });

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('limit=10');
      expect(callUrl).toContain('offset=5');
    });

    it('fetches detections with only limit', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockDetectionListResponse));

      await fetchEventDetections(1, { limit: 20 });

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('limit=20');
    });
  });

  describe('getDetectionImageUrl', () => {
    it('constructs detection image URL correctly', () => {
      const url = getDetectionImageUrl(123);
      expect(url).toBe('/api/detections/123/image');
    });
  });
});

describe('Logs API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchLogStats', () => {
    it('fetches log stats successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLogStats));

      const result = await fetchLogStats();

      expect(fetch).toHaveBeenCalledWith('/api/logs/stats', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result.total_today).toBe(100);
      expect(result.errors_today).toBe(5);
    });
  });

  describe('fetchLogs', () => {
    it('fetches logs without params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLogsResponse));

      const result = await fetchLogs();

      expect(fetch).toHaveBeenCalledWith('/api/logs', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result.logs).toHaveLength(1);
    });

    it('fetches logs with all query params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLogsResponse));

      const params: LogsQueryParams = {
        level: 'ERROR',
        component: 'frontend',
        camera_id: 'cam-1',
        source: 'backend',
        search: 'error message',
        start_date: '2025-01-01',
        end_date: '2025-01-31',
        limit: 25,
        offset: 10,
      };

      await fetchLogs(params);

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('level=ERROR');
      expect(callUrl).toContain('component=frontend');
      expect(callUrl).toContain('camera_id=cam-1');
      expect(callUrl).toContain('source=backend');
      expect(callUrl).toContain('search=error+message');
      expect(callUrl).toContain('start_date=2025-01-01');
      expect(callUrl).toContain('end_date=2025-01-31');
      expect(callUrl).toContain('limit=25');
      expect(callUrl).toContain('offset=10');
    });

    it('fetches logs with partial params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLogsResponse));

      const params: LogsQueryParams = {
        level: 'WARNING',
        limit: 50,
      };

      await fetchLogs(params);

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('level=WARNING');
      expect(callUrl).toContain('limit=50');
      expect(callUrl).not.toContain('component');
    });
  });
});

describe('Media URLs', () => {
  it('constructs camera media URL correctly', () => {
    const url = getMediaUrl('cam-1', 'image_2025-01-01_12-00-00.jpg');
    expect(url).toBe('/api/media/cameras/cam-1/image_2025-01-01_12-00-00.jpg');
  });

  it('constructs thumbnail URL correctly', () => {
    const url = getThumbnailUrl('thumb_2025-01-01_12-00-00.jpg');
    expect(url).toBe('/api/media/thumbnails/thumb_2025-01-01_12-00-00.jpg');
  });

  it('handles special characters in filenames', () => {
    const url = getMediaUrl('cam-1', 'image with spaces.jpg');
    expect(url).toBe('/api/media/cameras/cam-1/image with spaces.jpg');
  });

  it('handles URL-encoded characters', () => {
    const url = getThumbnailUrl('image%20encoded.jpg');
    expect(url).toBe('/api/media/thumbnails/image%20encoded.jpg');
  });
});

describe('Camera Snapshot URL', () => {
  it('constructs camera snapshot URL correctly', () => {
    const url = getCameraSnapshotUrl('cam-123');
    expect(url).toBe('/api/cameras/cam-123/snapshot');
  });

  it('handles UUIDs correctly', () => {
    const url = getCameraSnapshotUrl('123e4567-e89b-12d3-a456-426614174000');
    expect(url).toBe('/api/cameras/123e4567-e89b-12d3-a456-426614174000/snapshot');
  });

  it('URL-encodes special characters in camera ID', () => {
    const url = getCameraSnapshotUrl('camera with spaces');
    expect(url).toBe('/api/cameras/camera%20with%20spaces/snapshot');
  });

  it('handles camera IDs with special URL characters', () => {
    const url = getCameraSnapshotUrl('camera/path');
    expect(url).toBe('/api/cameras/camera%2Fpath/snapshot');
  });
});

describe('Error Handling', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('handles JSON parse error in response', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.reject(new Error('Invalid JSON')),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as unknown as Response);

    await expect(fetchCameras()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.reject(new Error('Invalid JSON')),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as unknown as Response);
    await expect(fetchCameras()).rejects.toMatchObject({
      status: 200,
      message: 'Failed to parse response JSON',
    });
  });

  it('handles error response with string body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve('Simple error message'),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as unknown as Response);

    await expect(fetchCameras()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve('Simple error message'),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as unknown as Response);
    await expect(fetchCameras()).rejects.toMatchObject({
      status: 400,
      message: 'Simple error message',
    });
  });

  it('handles error response with non-JSON body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('Not JSON')),
      headers: new Headers({ 'Content-Type': 'text/html' }),
    } as unknown as Response);

    await expect(fetchCameras()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('Not JSON')),
      headers: new Headers({ 'Content-Type': 'text/html' }),
    } as unknown as Response);
    await expect(fetchCameras()).rejects.toMatchObject({
      status: 500,
      message: 'HTTP 500: Internal Server Error',
    });
  });

  it('handles network timeout', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    await expect(fetchHealth()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));
    await expect(fetchHealth()).rejects.toMatchObject({
      status: 0,
      message: 'Request timeout',
    });
  });

  it('handles fetch rejection with non-Error object', async () => {
    vi.mocked(fetch).mockRejectedValue('String error');

    await expect(fetchHealth()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockRejectedValue('String error');
    await expect(fetchHealth()).rejects.toMatchObject({
      status: 0,
      message: 'Network request failed',
    });
  });

  it('handles 401 unauthorized', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(401, 'Unauthorized', 'Invalid credentials')
    );

    await expect(fetchCameras()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(401, 'Unauthorized', 'Invalid credentials')
    );
    await expect(fetchCameras()).rejects.toMatchObject({
      status: 401,
      message: 'Invalid credentials',
    });
  });

  it('handles 403 forbidden', async () => {
    vi.mocked(fetch).mockResolvedValue(createMockErrorResponse(403, 'Forbidden', 'Access denied'));

    await expect(fetchCameras()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockResolvedValue(createMockErrorResponse(403, 'Forbidden', 'Access denied'));
    await expect(fetchCameras()).rejects.toMatchObject({
      status: 403,
      message: 'Access denied',
    });
  });

  it('handles 503 service unavailable', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'Service temporarily unavailable')
    );

    await expect(fetchHealth()).rejects.toThrow(ApiError);

    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'Service temporarily unavailable')
    );
    await expect(fetchHealth()).rejects.toMatchObject({
      status: 503,
      message: 'Service temporarily unavailable',
    });
  });
});

// =============================================================================
// Export Endpoints Tests
// =============================================================================

describe('exportEventsCSV', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    // Mock URL.createObjectURL and URL.revokeObjectURL
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:http://test/mock-blob-url'),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const createMockBlobResponse = (csvContent: string, filename?: string): Response => {
    const headers = new Headers({
      'Content-Type': 'text/csv',
    });
    if (filename) {
      headers.set('Content-Disposition', `attachment; filename="${filename}"`);
    }
    return {
      ok: true,
      status: 200,
      statusText: 'OK',
      headers,
      blob: () => Promise.resolve(new Blob([csvContent], { type: 'text/csv' })),
      json: () => Promise.reject(new Error('Not JSON')),
    } as unknown as Response;
  };

  it('triggers download with CSV content', async () => {
    const mockCsv = 'event_id,camera_name,started_at\n1,Front Door,2024-01-01T12:00:00';
    vi.mocked(fetch).mockResolvedValue(
      createMockBlobResponse(mockCsv, 'events_export_20240101_120000.csv')
    );

    // Mock document methods
    const mockLink = {
      href: '',
      download: '',
      click: vi.fn(),
    };
    const createElementSpy = vi
      .spyOn(document, 'createElement')
      .mockReturnValue(mockLink as unknown as HTMLAnchorElement);
    const appendChildSpy = vi
      .spyOn(document.body, 'appendChild')
      .mockImplementation((node) => node);
    const removeChildSpy = vi
      .spyOn(document.body, 'removeChild')
      .mockImplementation((node) => node);

    await exportEventsCSV();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/events/export'),
      expect.any(Object)
    );
    expect(createElementSpy).toHaveBeenCalledWith('a');
    expect(mockLink.download).toBe('events_export_20240101_120000.csv');
    expect(mockLink.click).toHaveBeenCalled();

    createElementSpy.mockRestore();
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
  });

  it('sends filter parameters as query string', async () => {
    const mockCsv = 'event_id,camera_name\n1,Front Door';
    vi.mocked(fetch).mockResolvedValue(createMockBlobResponse(mockCsv));

    const mockLink = {
      href: '',
      download: '',
      click: vi.fn(),
    };
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLAnchorElement);
    vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node);
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node);

    const params: ExportQueryParams = {
      camera_id: 'cam-001',
      risk_level: 'high',
      start_date: '2024-01-01',
      end_date: '2024-01-31',
      reviewed: true,
    };

    await exportEventsCSV(params);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/events/export?'),
      expect.any(Object)
    );
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('camera_id=cam-001');
    expect(calledUrl).toContain('risk_level=high');
    expect(calledUrl).toContain('start_date=2024-01-01');
    expect(calledUrl).toContain('end_date=2024-01-31');
    expect(calledUrl).toContain('reviewed=true');
  });

  it('generates default filename when Content-Disposition is missing', async () => {
    const mockCsv = 'event_id,camera_name\n1,Front Door';
    // Create response without Content-Disposition header
    const response = {
      ok: true,
      status: 200,
      statusText: 'OK',
      headers: new Headers({ 'Content-Type': 'text/csv' }),
      blob: () => Promise.resolve(new Blob([mockCsv], { type: 'text/csv' })),
    } as unknown as Response;
    vi.mocked(fetch).mockResolvedValue(response);

    const mockLink = {
      href: '',
      download: '',
      click: vi.fn(),
    };
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLAnchorElement);
    vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node);
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node);

    await exportEventsCSV();

    // Filename should match pattern events_export_YYYYMMDDTHHMMSS.csv
    expect(mockLink.download).toMatch(/^events_export_\d{8}T\d{6}\.csv$/);
  });

  it('throws ApiError on HTTP error response', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      headers: new Headers(),
      json: () => Promise.resolve({ detail: 'Database error' }),
    } as unknown as Response);

    await expect(exportEventsCSV()).rejects.toThrow(ApiError);
    await expect(exportEventsCSV()).rejects.toMatchObject({
      status: 500,
      message: 'Database error',
    });
  });

  it('handles non-JSON error response', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      headers: new Headers(),
      json: () => Promise.reject(new Error('Not JSON')),
    } as unknown as Response);

    await expect(exportEventsCSV()).rejects.toThrow(ApiError);
    await expect(exportEventsCSV()).rejects.toMatchObject({
      status: 502,
      message: 'HTTP 502: Bad Gateway',
    });
  });

  it('throws ApiError on network failure', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network error'));

    await expect(exportEventsCSV()).rejects.toThrow(ApiError);
    await expect(exportEventsCSV()).rejects.toMatchObject({
      status: 0,
      message: 'Network error',
    });
  });

  it('handles reviewed=false parameter correctly', async () => {
    const mockCsv = 'event_id,camera_name\n1,Front Door';
    vi.mocked(fetch).mockResolvedValue(createMockBlobResponse(mockCsv));

    const mockLink = {
      href: '',
      download: '',
      click: vi.fn(),
    };
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLAnchorElement);
    vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node);
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node);

    await exportEventsCSV({ reviewed: false });

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('reviewed=false');
  });

  it('calls export with no query string when no params provided', async () => {
    const mockCsv = 'event_id,camera_name\n1,Front Door';
    vi.mocked(fetch).mockResolvedValue(createMockBlobResponse(mockCsv));

    const mockLink = {
      href: '',
      download: '',
      click: vi.fn(),
    };
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLAnchorElement);
    vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node);
    vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node);

    await exportEventsCSV();

    // The URL should end with /api/events/export (no query string)
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toMatch(/\/api\/events\/export$/);
  });
});
