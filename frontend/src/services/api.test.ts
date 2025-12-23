import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  ApiError,
  fetchCameras,
  fetchCamera,
  createCamera,
  updateCamera,
  deleteCamera,
  fetchHealth,
  fetchGPUStats,
  fetchConfig,
  fetchStats,
  getMediaUrl,
  getThumbnailUrl,
  type Camera,
  type CameraCreate,
  type CameraUpdate,
  type HealthResponse,
  type GPUStats,
  type SystemConfig,
  type SystemStats,
} from './api';

// Mock data
const mockCamera: Camera = {
  id: 'cam-1',
  name: 'Front Door',
  folder_path: '/export/foscam/front-door',
  status: 'active',
  created_at: '2025-01-01T00:00:00Z',
  last_seen_at: '2025-01-02T12:00:00Z',
};

const mockCameras: Camera[] = [
  mockCamera,
  {
    id: 'cam-2',
    name: 'Backyard',
    folder_path: '/export/foscam/backyard',
    status: 'active',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: null,
  },
];

const mockHealth: HealthResponse = {
  status: 'healthy',
  services: {
    database: { status: 'healthy' },
    redis: { status: 'healthy' },
    ai_detector: { status: 'healthy' },
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
};

const mockStats: SystemStats = {
  total_cameras: 2,
  total_events: 150,
  total_detections: 500,
  uptime_seconds: 86400,
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
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockCameras));

      const result = await fetchCameras();

      expect(fetch).toHaveBeenCalledWith('/api/cameras', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockCameras);
    });

    it('handles empty camera list', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse([]));

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
        status: 'active',
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

    it('creates a camera with minimal data', async () => {
      const createData: CameraCreate = {
        name: 'Minimal Camera',
        folder_path: '/export/foscam/minimal',
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

      await expect(createCamera({ name: 'Bad', folder_path: 'invalid' })).rejects.toThrow(ApiError);
    });
  });

  describe('updateCamera', () => {
    it('updates a camera successfully', async () => {
      const updateData: CameraUpdate = {
        name: 'Updated Front Door',
        status: 'inactive',
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
      const updateData: CameraUpdate = { status: 'inactive' };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse({ ...mockCamera, ...updateData }));

      const result = await updateCamera('cam-1', updateData);

      expect(result.status).toBe('inactive');
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
      const degradedHealth = {
        ...mockHealth,
        status: 'degraded',
        services: {
          database: { status: 'healthy' },
          redis: { status: 'unhealthy', message: 'Connection timeout' },
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
