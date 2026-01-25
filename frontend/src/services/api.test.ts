import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  ApiError,
  type ProblemDetails,
  isProblemDetails,
  buildWebSocketUrl,
  buildWebSocketUrlInternal,
  buildWebSocketOptions,
  buildWebSocketOptionsInternal,
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
  fetchEventEnrichments,
  createAnalysisStream,
  getMediaUrl,
  getThumbnailUrl,
  getDetectionImageUrl,
  getDetectionFullImageUrl,
  exportEventsCSV,
  searchEvents,
  fetchStorageStats,
  previewCleanup,
  // Retry and deduplication utilities
  shouldRetry,
  getRetryDelay,
  sleep,
  getRequestKey,
  getInFlightRequestCount,
  clearInFlightRequests,
  extractRateLimitInfo,
  // Cursor validation (NEM-2585)
  validateCursorFormat,
  isValidCursor,
  CursorValidationError,
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
  EventVersionConflictError,
  type Detection,
  type DetectionListResponse,
  type EventEnrichmentsResponse,
  type EventEnrichmentsQueryParams,
  type AnalysisStreamParams,
  type ExportQueryParams,
  type EventSearchParams,
  type SearchResponse,
  type SearchResult,
  fetchNotificationConfig,
  testNotification,
  type NotificationConfig,
  type TestNotificationResult,
  fetchAuditLogs,
  fetchAuditStats as fetchAuditLogStats,
  fetchAuditLog,
  type AuditLogsQueryParams,
  // Circuit Breaker and Severity endpoints
  fetchCircuitBreakers,
  resetCircuitBreaker,
  fetchSeverityMetadata,
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
  grafana_url: 'http://localhost:3002',
  debug: false,
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
  version: 1, // Optimistic locking version (NEM-3625)
};

const mockEventListResponse: EventListResponse = {
  items: [mockEvent],
  pagination: {
    total: 1,
    limit: 50,
    offset: null,
    cursor: null,
    next_cursor: null,
    has_more: false,
  },
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
  media_type: 'image',
};

const mockDetectionListResponse: DetectionListResponse = {
  items: [mockDetection],
  pagination: {
    total: 1,
    limit: 50,
    offset: null,
    cursor: null,
    next_cursor: null,
    has_more: false,
  },
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

/**
 * Creates a mock RFC 7807 Problem Details error response.
 * @param problemDetails - The RFC 7807 Problem Details object
 */
function createMockProblemDetailsResponse(problemDetails: ProblemDetails): Response {
  return {
    ok: false,
    status: problemDetails.status,
    statusText: problemDetails.title,
    json: () => Promise.resolve(problemDetails),
    headers: new Headers({ 'Content-Type': 'application/problem+json' }),
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

describe('buildWebSocketOptionsInternal (secure API key handling)', () => {
  describe('without API key', () => {
    it('returns url without protocols when no apiKey is set', () => {
      const options = buildWebSocketOptionsInternal('/ws/events', undefined, undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(options.url).toBe('ws://localhost:5173/ws/events');
      expect(options.protocols).toBeUndefined();
    });

    it('uses wss: protocol for https: pages', () => {
      const options = buildWebSocketOptionsInternal('/ws/events', undefined, undefined, {
        protocol: 'https:',
        host: 'secure.example.com',
      });
      expect(options.url).toBe('wss://secure.example.com/ws/events');
      expect(options.protocols).toBeUndefined();
    });
  });

  describe('with VITE_WS_BASE_URL', () => {
    it('uses configured WS base URL', () => {
      const options = buildWebSocketOptionsInternal('/ws/events', 'ws://backend:8000', undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(options.url).toBe('ws://backend:8000/ws/events');
    });

    it('strips trailing slash from WS base URL', () => {
      const options = buildWebSocketOptionsInternal(
        '/ws/events',
        'wss://api.example.com/',
        undefined,
        {
          protocol: 'http:',
          host: 'localhost:5173',
        }
      );
      expect(options.url).toBe('wss://api.example.com/ws/events');
    });
  });

  describe('with API key (secure protocol-based auth)', () => {
    it('returns protocols array with api-key prefix instead of query param', () => {
      const options = buildWebSocketOptionsInternal('/ws/events', undefined, 'secret-key-123', {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      // URL should NOT contain api_key query param
      expect(options.url).toBe('ws://localhost:5173/ws/events');
      expect(options.url).not.toContain('api_key');
      // Protocols array should contain api-key.{key} format
      expect(options.protocols).toEqual(['api-key.secret-key-123']);
    });

    it('works with both WS base URL and API key', () => {
      const options = buildWebSocketOptionsInternal(
        '/ws/events',
        'wss://api.example.com',
        'secure-token',
        {
          protocol: 'http:',
          host: 'localhost:5173',
        }
      );
      expect(options.url).toBe('wss://api.example.com/ws/events');
      expect(options.url).not.toContain('api_key');
      expect(options.protocols).toEqual(['api-key.secure-token']);
    });

    it('does not set protocols when apiKey is undefined', () => {
      const options = buildWebSocketOptionsInternal('/ws/events', undefined, undefined, {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(options.protocols).toBeUndefined();
    });

    it('does not set protocols when apiKey is empty string', () => {
      const options = buildWebSocketOptionsInternal('/ws/events', undefined, '', {
        protocol: 'http:',
        host: 'localhost:5173',
      });
      expect(options.protocols).toBeUndefined();
    });
  });
});

describe('buildWebSocketOptions', () => {
  it('builds WebSocket options using window.location in browser environment', () => {
    const options = buildWebSocketOptions('/ws/events');
    expect(options.url).toContain('/ws/events');
    expect(options.url).toMatch(/^wss?:\/\//);
  });

  it('returns options with correct url structure', () => {
    const options = buildWebSocketOptions('/ws/system');
    // Should have protocol, host, and endpoint
    expect(options.url).toMatch(/^wss?:\/\/[^/]+\/ws\/system$/);
  });
});

describe('getApiKey', () => {
  it('returns undefined when VITE_API_KEY is not set', () => {
    // In test environment, VITE_API_KEY is not set by default
    const apiKey = getApiKey();
    expect(apiKey).toBeUndefined();
  });
});

describe('isProblemDetails', () => {
  it('returns true for valid RFC 7807 ProblemDetails', () => {
    const problemDetails: ProblemDetails = {
      type: 'about:blank',
      title: 'Not Found',
      status: 404,
      detail: "Camera 'front_door' does not exist",
      instance: '/api/cameras/front_door',
    };
    expect(isProblemDetails(problemDetails)).toBe(true);
  });

  it('returns true for minimal ProblemDetails (required fields only)', () => {
    const minimal = {
      type: 'about:blank',
      title: 'Not Found',
      status: 404,
    };
    expect(isProblemDetails(minimal)).toBe(true);
  });

  it('returns true for ProblemDetails with extension members', () => {
    const extended = {
      type: 'https://example.com/errors/validation',
      title: 'Validation Error',
      status: 422,
      detail: 'Invalid email format',
      instance: '/api/users',
      errors: [{ field: 'email', message: 'Invalid format' }],
    };
    expect(isProblemDetails(extended)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isProblemDetails(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isProblemDetails(undefined)).toBe(false);
  });

  it('returns false for primitive values', () => {
    expect(isProblemDetails('string')).toBe(false);
    expect(isProblemDetails(123)).toBe(false);
    expect(isProblemDetails(true)).toBe(false);
  });

  it('returns false for objects missing type', () => {
    expect(isProblemDetails({ title: 'Error', status: 400 })).toBe(false);
  });

  it('returns false for objects missing title', () => {
    expect(isProblemDetails({ type: 'about:blank', status: 400 })).toBe(false);
  });

  it('returns false for objects missing status', () => {
    expect(isProblemDetails({ type: 'about:blank', title: 'Error' })).toBe(false);
  });

  it('returns false for objects with wrong type for status', () => {
    expect(isProblemDetails({ type: 'about:blank', title: 'Error', status: '400' })).toBe(false);
  });

  it('returns false for legacy error format', () => {
    expect(isProblemDetails({ detail: 'Not found' })).toBe(false);
    expect(isProblemDetails({ error: { code: 'NOT_FOUND', message: 'Not found' } })).toBe(false);
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

  describe('RFC 7807 ProblemDetails support', () => {
    it('creates an error with full ProblemDetails', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        detail: "Camera 'front_door' does not exist",
        instance: '/api/cameras/front_door',
      };
      const error = new ApiError(404, problemDetails.detail!, problemDetails, problemDetails);

      expect(error.problemDetails).toEqual(problemDetails);
      expect(error.type).toBe('about:blank');
      expect(error.title).toBe('Not Found');
      expect(error.detail).toBe("Camera 'front_door' does not exist");
      expect(error.instance).toBe('/api/cameras/front_door');
    });

    it('provides default values when no ProblemDetails', () => {
      const error = new ApiError(500, 'Internal Server Error');

      expect(error.problemDetails).toBeUndefined();
      expect(error.type).toBe('about:blank');
      expect(error.title).toBe('Internal Server Error'); // Falls back to message
      expect(error.detail).toBe('Internal Server Error'); // Falls back to message
      expect(error.instance).toBeUndefined();
    });

    it('handles ProblemDetails with extension members', () => {
      const problemDetails: ProblemDetails = {
        type: 'https://api.example.com/errors/validation',
        title: 'Validation Error',
        status: 422,
        detail: 'Multiple validation errors',
        instance: '/api/users',
        errors: [
          { field: 'email', message: 'Invalid email format' },
          { field: 'name', message: 'Name is required' },
        ],
      };
      const error = new ApiError(422, problemDetails.detail!, problemDetails, problemDetails);

      expect(error.problemDetails).toEqual(problemDetails);
      expect(error.problemDetails?.errors).toBeDefined();
      expect((error.problemDetails as ProblemDetails & { errors: unknown[] }).errors).toHaveLength(
        2
      );
    });

    it('uses title when detail is not provided', () => {
      const problemDetails: ProblemDetails = {
        type: 'about:blank',
        title: 'Bad Request',
        status: 400,
      };
      const error = new ApiError(400, problemDetails.title, problemDetails, problemDetails);

      expect(error.message).toBe('Bad Request');
      expect(error.detail).toBe('Bad Request'); // Falls back to message since no detail
    });
  });
});

describe('RFC 7807 Error Handling Integration', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearInFlightRequests();
  });

  it('extracts full ProblemDetails from 404 response', async () => {
    const problemDetails: ProblemDetails = {
      type: 'about:blank',
      title: 'Not Found',
      status: 404,
      detail: "Camera 'front_door' does not exist",
      instance: '/api/cameras/front_door',
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockProblemDetailsResponse(problemDetails));

    let caughtError: ApiError | null = null;
    try {
      await fetchCamera('front_door');
    } catch (e) {
      caughtError = e as ApiError;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(404);
    expect(caughtError!.message).toBe("Camera 'front_door' does not exist");
    expect(caughtError!.problemDetails).toBeDefined();
    expect(caughtError!.type).toBe('about:blank');
    expect(caughtError!.title).toBe('Not Found');
    expect(caughtError!.detail).toBe("Camera 'front_door' does not exist");
    expect(caughtError!.instance).toBe('/api/cameras/front_door');
  });

  it('extracts ProblemDetails from 400 validation error', async () => {
    const problemDetails: ProblemDetails = {
      type: 'about:blank',
      title: 'Bad Request',
      status: 400,
      detail: 'Invalid camera configuration',
      instance: '/api/cameras',
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockProblemDetailsResponse(problemDetails));

    let caughtError: ApiError | null = null;
    try {
      await createCamera({
        name: 'Test',
        folder_path: '/invalid/path',
        status: 'online',
      });
    } catch (e) {
      caughtError = e as ApiError;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.problemDetails).toBeDefined();
    expect(caughtError!.title).toBe('Bad Request');
    expect(caughtError!.detail).toBe('Invalid camera configuration');
  });

  it('extracts ProblemDetails from 500 server error', async () => {
    vi.useFakeTimers();

    const problemDetails: ProblemDetails = {
      type: 'about:blank',
      title: 'Internal Server Error',
      status: 500,
      detail: 'Database connection failed',
      instance: '/api/cameras',
    };

    vi.mocked(fetch).mockResolvedValue(createMockProblemDetailsResponse(problemDetails));

    let caughtError: ApiError | null = null;
    const promise = fetchCameras().catch((e) => {
      caughtError = e as ApiError;
    });

    await vi.runAllTimersAsync();
    await promise;

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.problemDetails).toBeDefined();
    expect(caughtError!.title).toBe('Internal Server Error');
    expect(caughtError!.detail).toBe('Database connection failed');

    vi.useRealTimers();
  });

  it('uses title when detail is not provided in response', async () => {
    const problemDetails: ProblemDetails = {
      type: 'about:blank',
      title: 'Conflict',
      status: 409,
      instance: '/api/cameras/cam-1',
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockProblemDetailsResponse(problemDetails));

    let caughtError: ApiError | null = null;
    try {
      await deleteCamera('cam-1');
    } catch (e) {
      caughtError = e as ApiError;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.message).toBe('Conflict'); // Uses title when no detail
    expect(caughtError!.problemDetails).toBeDefined();
  });

  it('handles ProblemDetails with extension members', async () => {
    interface ValidationProblemDetails extends ProblemDetails {
      errors: Array<{ field: string; message: string; value?: unknown }>;
    }

    const problemDetails: ValidationProblemDetails = {
      type: 'https://api.example.com/errors/validation',
      title: 'Unprocessable Content',
      status: 422,
      detail: 'Validation failed',
      instance: '/api/cameras',
      errors: [
        { field: 'name', message: 'Name is required' },
        { field: 'folder_path', message: 'Invalid path format', value: '/bad path' },
      ],
    };

    vi.mocked(fetch).mockResolvedValueOnce(
      createMockProblemDetailsResponse(problemDetails as ProblemDetails)
    );

    let caughtError: ApiError | null = null;
    try {
      await createCamera({
        name: '',
        folder_path: '/bad path',
        status: 'online',
      });
    } catch (e) {
      caughtError = e as ApiError;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.problemDetails).toBeDefined();

    // Extension members should be accessible
    const pd = caughtError!.problemDetails as ValidationProblemDetails;
    expect(pd.errors).toBeDefined();
    expect(pd.errors).toHaveLength(2);
    expect(pd.errors[0].field).toBe('name');
  });

  it('maintains backward compatibility with legacy error format', async () => {
    // Legacy format: { detail: "Error message" }
    vi.mocked(fetch).mockResolvedValueOnce(
      createMockErrorResponse(404, 'Not Found', 'Camera not found')
    );

    let caughtError: ApiError | null = null;
    try {
      await fetchCamera('invalid-id');
    } catch (e) {
      caughtError = e as ApiError;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(404);
    expect(caughtError!.message).toBe('Camera not found');
    // Legacy format doesn't have ProblemDetails
    expect(caughtError!.problemDetails).toBeUndefined();
    // But fallback getters should still work
    expect(caughtError!.type).toBe('about:blank');
    expect(caughtError!.title).toBe('Camera not found'); // Falls back to message
  });

  it('handles non-JSON error responses', async () => {
    // Non-5xx errors don't trigger retry, so we use a 4xx error to avoid retry logic
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.reject(new Error('Not JSON')),
      headers: new Headers(),
    } as Response);

    let caughtError: ApiError | null = null;
    try {
      await fetchCamera('cam-1');
    } catch (e) {
      caughtError = e as ApiError;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(400);
    expect(caughtError!.message).toBe('HTTP 400: Bad Request');
    expect(caughtError!.problemDetails).toBeUndefined();
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
        createMockResponse({
          items: mockCameras,
          pagination: {
            total: mockCameras.length,
            limit: 50,
            offset: null,
            cursor: null,
            next_cursor: null,
            has_more: false,
          },
        })
      );

      const result = await fetchCameras();

      expect(fetch).toHaveBeenCalledWith('/api/cameras', {
        headers: {
          'Content-Type': 'application/json',
        },
        signal: expect.any(AbortSignal),
      });
      expect(result).toEqual(mockCameras);
    });

    it('handles empty camera list', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockResponse({
          items: [],
          pagination: {
            total: 0,
            limit: 50,
            offset: null,
            cursor: null,
            next_cursor: null,
            has_more: false,
          },
        })
      );

      const result = await fetchCameras();

      expect(result).toEqual([]);
    });

    it('throws ApiError on 500 error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Database error')
      );

      let caughtError: ApiError | null = null;
      const promise = fetchCameras().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Database error');

      clearInFlightRequests();
      vi.useRealTimers();
    });

    it('throws ApiError on network error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));

      let caughtError: ApiError | null = null;
      const promise = fetchCameras().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(0);
      expect(caughtError!.message).toBe('Network failure');

      clearInFlightRequests();
      vi.useRealTimers();
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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
        items: [
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
        pagination: {
          total: 2,
          limit: 100,
          offset: null,
          has_more: false,
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHistoryResponse));

      const result = await fetchGpuHistory();

      expect(fetch).toHaveBeenCalledWith('/api/system/gpu/history?limit=100', {
        headers: {
          'Content-Type': 'application/json',
        },

        signal: expect.any(AbortSignal),
      });
      expect(result.items).toHaveLength(2);
      expect(result.pagination.total).toBe(2);
      expect(result.items[0].utilization).toBe(45.5);
    });

    it('fetches GPU history with custom limit', async () => {
      const mockHistoryResponse: GPUStatsHistoryResponse = {
        items: [
          {
            recorded_at: '2025-01-01T10:00:00Z',
            utilization: 45.5,
            memory_used: 8192,
            memory_total: 24576,
            temperature: 65,
            inference_fps: 30.2,
          },
        ],
        pagination: {
          total: 1,
          limit: 50,
          offset: null,
          has_more: false,
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHistoryResponse));

      const result = await fetchGpuHistory(50);

      expect(fetch).toHaveBeenCalledWith('/api/system/gpu/history?limit=50', {
        headers: {
          'Content-Type': 'application/json',
        },

        signal: expect.any(AbortSignal),
      });
      expect(result.items).toHaveLength(1);
    });

    it('handles empty GPU history', async () => {
      const emptyHistoryResponse: GPUStatsHistoryResponse = {
        items: [],
        pagination: {
          total: 0,
          limit: 100,
          offset: null,
          has_more: false,
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyHistoryResponse));

      const result = await fetchGpuHistory();

      expect(result.items).toEqual([]);
      expect(result.pagination.total).toBe(0);
    });

    it('handles samples with null values', async () => {
      const mockHistoryResponse: GPUStatsHistoryResponse = {
        items: [
          {
            recorded_at: '2025-01-01T10:00:00Z',
            utilization: null,
            memory_used: null,
            memory_total: null,
            temperature: null,
            inference_fps: null,
          },
        ],
        pagination: {
          total: 1,
          limit: 100,
          offset: null,
          has_more: false,
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockHistoryResponse));

      const result = await fetchGpuHistory();

      expect(result.items[0].utilization).toBeNull();
      expect(result.items[0].memory_used).toBeNull();
    });

    it('throws ApiError on 500 error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'GPU monitoring service unavailable')
      );

      let caughtError: ApiError | null = null;
      const promise = fetchGpuHistory().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('GPU monitoring service unavailable');

      clearInFlightRequests();
      vi.useRealTimers();
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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
      vi.useFakeTimers();
      clearInFlightRequests();

      // Use mockResolvedValue (not Once) because retry logic makes multiple fetch calls
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Redis unavailable')
      );

      let caughtError: ApiError | null = null;
      const promise = fetchTelemetry().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Redis unavailable');

      clearInFlightRequests();
      vi.useRealTimers();
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

        signal: expect.any(AbortSignal),
      });
      expect(result.items).toEqual([mockEvent]);
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
        cursor: 'eyJpZCI6IDEwfQ==',
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
      expect(callUrl).toContain('cursor=eyJpZCI6IDEwfQ%3D%3D');
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

        signal: expect.any(AbortSignal),
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

    it('includes version in update request for optimistic locking (NEM-3625)', async () => {
      const updateData: EventUpdateData = { reviewed: true, version: 3 };
      const updatedEvent = { ...mockEvent, reviewed: true, version: 4 };

      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(updatedEvent));

      const result = await updateEvent(1, updateData);

      expect(fetch).toHaveBeenCalledWith('/api/events/1', {
        method: 'PATCH',
        body: JSON.stringify({ reviewed: true, version: 3 }),
        headers: { 'Content-Type': 'application/json' },
        signal: expect.any(AbortSignal),
      });
      expect(result.version).toBe(4);
    });

    it('throws EventVersionConflictError on 409 Conflict (NEM-3625)', async () => {
      const updateData: EventUpdateData = { reviewed: true, version: 2 };
      // Backend returns detail as an object with message and current_version
      const conflictResponse = {
        detail: {
          message: 'Event was modified by another request. Please refresh and retry.',
          current_version: 5,
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 409,
        statusText: 'Conflict',
        json: () => Promise.resolve(conflictResponse),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      } as Response);

      await expect(updateEvent(1, updateData)).rejects.toThrow(EventVersionConflictError);
    });

    it('EventVersionConflictError contains current version from server (NEM-3625)', async () => {
      const updateData: EventUpdateData = { reviewed: true, version: 2 };
      // Backend returns detail as an object with message and current_version
      const conflictResponse = {
        detail: {
          message: 'Event was modified by another request. Please refresh and retry.',
          current_version: 5,
        },
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 409,
        statusText: 'Conflict',
        json: () => Promise.resolve(conflictResponse),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      } as Response);

      try {
        await updateEvent(1, updateData);
        throw new Error('Expected EventVersionConflictError to be thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(EventVersionConflictError);
        if (error instanceof EventVersionConflictError) {
          expect(error.currentVersion).toBe(5);
          expect(error.eventId).toBe(1);
          expect(error.message).toContain('modified by another request');
        }
      }
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
      vi.useFakeTimers();
      clearInFlightRequests();

      // First call succeeds, subsequent calls fail with retries
      let callCount = 0;
      vi.mocked(fetch).mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve(createMockResponse({ ...mockEvent, reviewed: true }));
        }
        return Promise.reject(new Error('string error'));
      });

      let result: { successful: number[]; failed: { id: number; error: string }[] } | null = null;
      const promise = bulkUpdateEvents([1, 2], { reviewed: true }).then((r) => {
        result = r;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(result!.successful).toContain(1);
      expect(result!.failed[0].error).toBe('string error');

      clearInFlightRequests();
      vi.useRealTimers();
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

        signal: expect.any(AbortSignal),
      });
      expect(result.items).toEqual([mockDetection]);
    });

    it('fetches detections with pagination params', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockDetectionListResponse));

      await fetchEventDetections(1, { limit: 10, cursor: 'eyJpZCI6IDV9' });

      const callUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(callUrl).toContain('limit=10');
      expect(callUrl).toContain('cursor=eyJpZCI6IDV9');
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

  describe('getDetectionFullImageUrl', () => {
    it('constructs full-size detection image URL correctly', () => {
      const url = getDetectionFullImageUrl(123);
      expect(url).toBe('/api/detections/123/image?full=true');
    });

    it('includes full=true query parameter', () => {
      const url = getDetectionFullImageUrl(456);
      expect(url).toContain('?full=true');
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

  // SECURITY: Media endpoints are exempt from API key auth, so no keys should be in URLs
  it('does not include api_key in media URLs (security: exempt endpoints)', () => {
    const mediaUrl = getMediaUrl('cam-1', 'test.jpg');
    const thumbnailUrl = getThumbnailUrl('thumb.jpg');
    const detectionImageUrl = getDetectionImageUrl(123);
    const detectionFullImageUrl = getDetectionFullImageUrl(123);

    expect(mediaUrl).not.toContain('api_key');
    expect(thumbnailUrl).not.toContain('api_key');
    expect(detectionImageUrl).not.toContain('api_key');
    expect(detectionFullImageUrl).not.toContain('api_key');
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

  // SECURITY: Camera snapshot endpoints are exempt from API key auth, so no keys should be in URLs
  it('does not include api_key in snapshot URL (security: exempt endpoint)', () => {
    const url = getCameraSnapshotUrl('cam-123');
    expect(url).not.toContain('api_key');
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
    vi.useFakeTimers();
    clearInFlightRequests();

    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('Not JSON')),
      headers: new Headers({ 'Content-Type': 'text/html' }),
    } as unknown as Response);

    let caughtError: ApiError | null = null;
    const promise = fetchCameras().catch((e) => {
      caughtError = e as ApiError;
    });

    await vi.runAllTimersAsync();
    await promise;

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(500);
    expect(caughtError!.message).toBe('HTTP 500: Internal Server Error');

    clearInFlightRequests();
    vi.useRealTimers();
  });

  it('handles network timeout', async () => {
    vi.useFakeTimers();
    clearInFlightRequests();

    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    let caughtError: ApiError | null = null;
    const promise = fetchHealth().catch((e) => {
      caughtError = e as ApiError;
    });

    await vi.runAllTimersAsync();
    await promise;

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(0);
    expect(caughtError!.message).toBe('Request timeout');

    clearInFlightRequests();
    vi.useRealTimers();
  });

  it('handles fetch rejection with non-Error object', async () => {
    vi.useFakeTimers();
    clearInFlightRequests();

    vi.mocked(fetch).mockRejectedValue('String error');

    let caughtError: ApiError | null = null;
    const promise = fetchHealth().catch((e) => {
      caughtError = e as ApiError;
    });

    await vi.runAllTimersAsync();
    await promise;

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(0);
    expect(caughtError!.message).toBe('Network request failed');

    clearInFlightRequests();
    vi.useRealTimers();
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
    vi.useFakeTimers();
    clearInFlightRequests();

    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'Service temporarily unavailable')
    );

    let caughtError: ApiError | null = null;
    const promise = fetchHealth().catch((e) => {
      caughtError = e as ApiError;
    });

    await vi.runAllTimersAsync();
    await promise;

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(503);
    expect(caughtError!.message).toBe('Service temporarily unavailable');

    clearInFlightRequests();
    vi.useRealTimers();
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

// =============================================================================
// Search Events API Tests
// =============================================================================

const mockSearchResult: SearchResult = {
  id: 1,
  camera_id: 'front_door',
  camera_name: 'Front Door',
  started_at: '2025-12-30T10:30:00Z',
  ended_at: '2025-12-30T10:32:00Z',
  risk_score: 75,
  risk_level: 'high',
  summary: 'Suspicious person detected near entrance',
  reasoning: 'Unknown individual approaching during nighttime hours',
  reviewed: false,
  detection_count: 5,
  detection_ids: [1, 2, 3, 4, 5],
  object_types: 'person, vehicle',
  relevance_score: 0.85,
};

const mockSearchResponse: SearchResponse = {
  results: [mockSearchResult],
  total_count: 1,
  limit: 50,
  offset: 0,
};

describe('searchEvents', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('searches events with query only', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSearchResponse));

    const result = await searchEvents({ q: 'suspicious person' });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/events/search?q=suspicious+person'),
      expect.any(Object)
    );
    expect(result.results).toEqual([mockSearchResult]);
    expect(result.total_count).toBe(1);
  });

  it('searches events with all parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSearchResponse));

    const params: EventSearchParams = {
      q: 'person',
      camera_id: 'front_door',
      start_date: '2025-12-01',
      end_date: '2025-12-31',
      severity: 'high,critical',
      object_type: 'person',
      reviewed: false,
      limit: 25,
      offset: 10,
    };

    await searchEvents(params);

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('q=person');
    expect(calledUrl).toContain('camera_id=front_door');
    expect(calledUrl).toContain('start_date=2025-12-01');
    expect(calledUrl).toContain('end_date=2025-12-31');
    expect(calledUrl).toContain('severity=high%2Ccritical');
    expect(calledUrl).toContain('object_type=person');
    expect(calledUrl).toContain('reviewed=false');
    expect(calledUrl).toContain('limit=25');
    expect(calledUrl).toContain('offset=10');
  });

  it('handles empty search results', async () => {
    const emptyResponse: SearchResponse = {
      results: [],
      total_count: 0,
      limit: 50,
      offset: 0,
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyResponse));

    const result = await searchEvents({ q: 'nonexistent term' });

    expect(result.results).toEqual([]);
    expect(result.total_count).toBe(0);
  });

  it('handles phrase search queries', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSearchResponse));

    await searchEvents({ q: '"suspicious person"' });

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('q=%22suspicious+person%22');
  });

  it('handles boolean search operators', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSearchResponse));

    await searchEvents({ q: 'person OR vehicle' });

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('q=person+OR+vehicle');
  });

  it('returns relevance scores in results', async () => {
    const multipleResults: SearchResponse = {
      results: [
        { ...mockSearchResult, id: 1, relevance_score: 0.95 },
        { ...mockSearchResult, id: 2, relevance_score: 0.75 },
        { ...mockSearchResult, id: 3, relevance_score: 0.55 },
      ],
      total_count: 3,
      limit: 50,
      offset: 0,
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(multipleResults));

    const result = await searchEvents({ q: 'person' });

    expect(result.results[0].relevance_score).toBe(0.95);
    expect(result.results[1].relevance_score).toBe(0.75);
    expect(result.results[2].relevance_score).toBe(0.55);
  });

  it('throws ApiError on server error', async () => {
    vi.useFakeTimers();
    clearInFlightRequests();

    // Use mockResolvedValue (not Once) because retry logic makes multiple fetch calls
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Search service unavailable')
    );

    let caughtError: ApiError | null = null;
    const promise = searchEvents({ q: 'test' }).catch((e) => {
      caughtError = e as ApiError;
    });

    await vi.runAllTimersAsync();
    await promise;

    expect(caughtError).toBeInstanceOf(ApiError);
    expect(caughtError!.status).toBe(500);
    expect(caughtError!.message).toBe('Search service unavailable');

    clearInFlightRequests();
    vi.useRealTimers();
  });

  it('throws ApiError on validation error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      createMockErrorResponse(422, 'Unprocessable Entity', 'Query parameter is required')
    );

    await expect(searchEvents({ q: '' })).rejects.toThrow(ApiError);
  });

  it('excludes undefined optional parameters from URL', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSearchResponse));

    await searchEvents({ q: 'test' });

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('camera_id');
    expect(calledUrl).not.toContain('start_date');
    expect(calledUrl).not.toContain('severity');
    expect(calledUrl).not.toContain('reviewed');
  });

  it('handles special characters in search query', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSearchResponse));

    await searchEvents({ q: 'person & vehicle' });

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('q=person+%26+vehicle');
  });
});

// ============================================================================
// Retry Logic Tests
// ============================================================================

describe('Retry Logic', () => {
  describe('shouldRetry', () => {
    it('returns true for network errors (status 0)', () => {
      expect(shouldRetry(0)).toBe(true);
    });

    it('returns true for 5xx server errors', () => {
      expect(shouldRetry(500)).toBe(true);
      expect(shouldRetry(502)).toBe(true);
      expect(shouldRetry(503)).toBe(true);
      expect(shouldRetry(599)).toBe(true);
    });

    it('returns false for successful responses', () => {
      expect(shouldRetry(200)).toBe(false);
      expect(shouldRetry(201)).toBe(false);
      expect(shouldRetry(204)).toBe(false);
    });

    it('returns false for redirect responses', () => {
      expect(shouldRetry(301)).toBe(false);
      expect(shouldRetry(302)).toBe(false);
      expect(shouldRetry(304)).toBe(false);
    });

    it('returns false for client errors (4xx)', () => {
      expect(shouldRetry(400)).toBe(false);
      expect(shouldRetry(401)).toBe(false);
      expect(shouldRetry(403)).toBe(false);
      expect(shouldRetry(404)).toBe(false);
      expect(shouldRetry(422)).toBe(false);
      expect(shouldRetry(429)).toBe(false);
    });
  });

  describe('getRetryDelay', () => {
    it('returns 1000ms for first retry attempt (0)', () => {
      expect(getRetryDelay(0)).toBe(1000);
    });

    it('returns 2000ms for second retry attempt (1)', () => {
      expect(getRetryDelay(1)).toBe(2000);
    });

    it('returns 4000ms for third retry attempt (2)', () => {
      expect(getRetryDelay(2)).toBe(4000);
    });

    it('follows exponential backoff pattern', () => {
      expect(getRetryDelay(3)).toBe(8000);
      expect(getRetryDelay(4)).toBe(16000);
    });
  });

  describe('sleep', () => {
    it('resolves after specified milliseconds', async () => {
      vi.useFakeTimers();

      const sleepPromise = sleep(100);

      let resolved = false;
      void sleepPromise.then(() => {
        resolved = true;
      });

      // Should not be resolved immediately
      expect(resolved).toBe(false);

      // Advance timers
      await vi.advanceTimersByTimeAsync(100);

      expect(resolved).toBe(true);
      vi.useRealTimers();
    });
  });
});

// ============================================================================
// Request Deduplication Tests
// ============================================================================

describe('Request Deduplication', () => {
  describe('getRequestKey', () => {
    it('returns key for GET requests', () => {
      expect(getRequestKey('GET', '/api/cameras')).toBe('GET:/api/cameras');
      expect(getRequestKey('get', '/api/events')).toBe('GET:/api/events');
    });

    it('returns null for POST requests', () => {
      expect(getRequestKey('POST', '/api/cameras')).toBeNull();
    });

    it('returns null for PATCH requests', () => {
      expect(getRequestKey('PATCH', '/api/cameras/1')).toBeNull();
    });

    it('returns null for PUT requests', () => {
      expect(getRequestKey('PUT', '/api/cameras/1')).toBeNull();
    });

    it('returns null for DELETE requests', () => {
      expect(getRequestKey('DELETE', '/api/cameras/1')).toBeNull();
    });

    it('handles case-insensitive method names', () => {
      expect(getRequestKey('Get', '/api/test')).toBe('GET:/api/test');
      expect(getRequestKey('gET', '/api/test')).toBe('GET:/api/test');
    });
  });

  describe('getInFlightRequestCount', () => {
    beforeEach(() => {
      clearInFlightRequests();
    });

    it('returns 0 when no requests are in flight', () => {
      expect(getInFlightRequestCount()).toBe(0);
    });
  });

  describe('clearInFlightRequests', () => {
    it('clears all tracked requests', () => {
      // Start with clean state
      clearInFlightRequests();
      expect(getInFlightRequestCount()).toBe(0);
    });
  });
});

describe('Request Deduplication Integration', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    clearInFlightRequests();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearInFlightRequests();
  });

  it('deduplicates concurrent GET requests to same URL', async () => {
    let resolveResponse: (value: Response) => void;
    const responsePromise = new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    });

    vi.mocked(fetch).mockReturnValue(responsePromise);

    // Start two concurrent GET requests
    const promise1 = fetchCameras();
    const promise2 = fetchCameras();

    // Fetch should only be called once
    expect(fetch).toHaveBeenCalledTimes(1);

    // Resolve the response
    resolveResponse!(createMockResponse({ cameras: [] }));

    // Both promises should resolve to the same result
    const [result1, result2] = await Promise.all([promise1, promise2]);
    expect(result1).toEqual(result2);
  });

  it('does not deduplicate POST requests', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockResponse({ id: '1', name: 'Camera 1', folder_path: '/cam1', status: 'online' })
    );

    // Start two concurrent POST requests
    const promise1 = createCamera({ name: 'Camera 1', folder_path: '/cam1', status: 'online' });
    const promise2 = createCamera({ name: 'Camera 2', folder_path: '/cam2', status: 'online' });

    await Promise.all([promise1, promise2]);

    // Both POST requests should be made
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('allows sequential GET requests to same URL', async () => {
    vi.mocked(fetch).mockResolvedValue(createMockResponse({ cameras: [] }));

    // First request
    await fetchCameras();

    // Second request (after first completes)
    await fetchCameras();

    // Both requests should be made since they're sequential
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('clears in-flight tracking on error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network error'));

    // Start a request that will fail after retries
    vi.useFakeTimers();
    const promise = fetchCameras().catch(() => {});

    // Advance through all retries
    await vi.advanceTimersByTimeAsync(1000); // First retry delay
    await vi.advanceTimersByTimeAsync(2000); // Second retry delay
    await vi.advanceTimersByTimeAsync(4000); // Third retry delay

    await promise;
    vi.useRealTimers();

    // In-flight requests should be cleared
    expect(getInFlightRequestCount()).toBe(0);
  });
});

// ============================================================================
// Storage API Tests
// ============================================================================

// Note: fetchStorageStats, previewCleanup, StorageStatsResponse are imported at top of file

const mockStorageStatsResponse = {
  disk_used_bytes: 268435456000, // 250 GB
  disk_total_bytes: 536870912000, // 500 GB
  disk_free_bytes: 268435456000, // 250 GB
  disk_usage_percent: 50,
  thumbnails: { file_count: 10000, size_bytes: 21474836480 }, // 20 GB
  images: { file_count: 10000, size_bytes: 107374182400 }, // 100 GB
  clips: { file_count: 500, size_bytes: 107374182400 }, // 100 GB
  events_count: 500,
  detections_count: 5000,
  gpu_stats_count: 10000,
  logs_count: 50000,
  timestamp: '2025-01-01T00:00:00Z',
};

const mockCleanupResponseForStorage = {
  events_deleted: 15,
  detections_deleted: 89,
  gpu_stats_deleted: 2880,
  logs_deleted: 150,
  thumbnails_deleted: 89,
  images_deleted: 0,
  space_reclaimed: 524288000,
  retention_days: 30,
  dry_run: true,
  timestamp: '2025-01-01T00:00:00Z',
};

describe('Storage API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchStorageStats', () => {
    it('fetches storage stats successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStorageStatsResponse));

      const result = await fetchStorageStats();

      expect(fetch).toHaveBeenCalledWith('/api/system/storage', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.disk_total_bytes).toBe(536870912000);
      expect(result.disk_used_bytes).toBe(268435456000);
      expect(result.disk_usage_percent).toBe(50);
    });

    it('returns storage categories correctly', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStorageStatsResponse));

      const result = await fetchStorageStats();

      expect(result.images.file_count).toBe(10000);
      expect(result.images.size_bytes).toBe(107374182400);
    });

    it('throws ApiError on server error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Disk monitoring unavailable')
      );

      let caughtError: ApiError | null = null;
      const promise = fetchStorageStats().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Disk monitoring unavailable');

      clearInFlightRequests();
      vi.useRealTimers();
    });
  });

  describe('previewCleanup', () => {
    it('previews cleanup successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockCleanupResponseForStorage));

      const result = await previewCleanup();

      expect(fetch).toHaveBeenCalledWith('/api/system/cleanup?dry_run=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.events_deleted).toBe(15);
      expect(result.space_reclaimed).toBe(524288000);
      expect(result.dry_run).toBe(true);
    });

    it('throws ApiError on server error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Cleanup service unavailable')
      );

      let caughtError: ApiError | null = null;
      const promise = previewCleanup().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Cleanup service unavailable');

      clearInFlightRequests();
      vi.useRealTimers();
    });
  });
});

// ============================================================================
// Notification API Tests
// ============================================================================

const mockNotificationConfig: NotificationConfig = {
  notification_enabled: true,
  email_configured: true,
  webhook_configured: false,
  push_configured: false,
  available_channels: ['email'],
  smtp_host: 'smtp.example.com',
  smtp_port: 587,
  smtp_from_address: 'alerts@example.com',
  smtp_use_tls: true,
  default_webhook_url: null,
  webhook_timeout_seconds: null,
  default_email_recipients: ['admin@example.com'],
};

const mockTestNotificationResult: TestNotificationResult = {
  channel: 'email',
  success: true,
  error: null,
  message: 'Test notification sent successfully',
};

describe('Notification API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('fetchNotificationConfig', () => {
    it('fetches notification config successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockNotificationConfig));

      const result = await fetchNotificationConfig();

      expect(fetch).toHaveBeenCalledWith('/api/notification/config', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.notification_enabled).toBe(true);
      expect(result.email_configured).toBe(true);
      expect(result.available_channels).toContain('email');
    });

    it('throws ApiError on server error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Config service unavailable')
      );

      let caughtError: ApiError | null = null;
      const promise = fetchNotificationConfig().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Config service unavailable');

      clearInFlightRequests();
      vi.useRealTimers();
    });
  });

  describe('testNotification', () => {
    it('tests email notification successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockTestNotificationResult));

      const result = await testNotification('email', ['test@example.com']);

      expect(fetch).toHaveBeenCalledWith('/api/notification/test', {
        method: 'POST',
        body: JSON.stringify({ channel: 'email', email_recipients: ['test@example.com'] }),
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.success).toBe(true);
      expect(result.channel).toBe('email');
    });

    it('tests webhook notification with custom URL', async () => {
      const webhookResult: TestNotificationResult = {
        channel: 'webhook',
        success: true,
        error: null,
        message: 'Webhook delivered',
      };
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(webhookResult));

      const result = await testNotification('webhook', undefined, 'https://hook.example.com');

      expect(fetch).toHaveBeenCalledWith('/api/notification/test', {
        method: 'POST',
        body: JSON.stringify({ channel: 'webhook', webhook_url: 'https://hook.example.com' }),
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.channel).toBe('webhook');
    });

    it('tests notification without optional parameters', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockTestNotificationResult));

      await testNotification('push');

      expect(fetch).toHaveBeenCalledWith('/api/notification/test', {
        method: 'POST',
        body: JSON.stringify({ channel: 'push' }),
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
    });

    it('handles test failure response', async () => {
      const failedResult: TestNotificationResult = {
        channel: 'email',
        success: false,
        error: 'SMTP connection failed',
        message: 'Failed to send test notification',
      };
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(failedResult));

      const result = await testNotification('email');

      expect(result.success).toBe(false);
      expect(result.error).toBe('SMTP connection failed');
    });
  });
});

// ============================================================================
// Audit Log API Tests
// ============================================================================

describe('Audit Log API', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const mockAuditLogListResponse = {
    items: [
      {
        id: 1,
        timestamp: '2025-01-01T10:00:00Z',
        action: 'create',
        resource_type: 'camera',
        resource_id: 'cam-1',
        actor: 'system',
        status: 'success',
        details: { name: 'Front Door' },
      },
    ],
    pagination: {
      total: 1,
      limit: 100,
      offset: 0,
      has_more: false,
      next_cursor: null,
    },
  };

  const mockAuditLogStats = {
    total_logs: 1000,
    logs_by_action: { create: 300, update: 500, delete: 200 },
    logs_by_status: { success: 950, failure: 50 },
    logs_by_resource_type: { camera: 400, event: 600 },
  };

  describe('fetchAuditLogs', () => {
    it('fetches audit logs without parameters', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditLogListResponse));

      const result = await fetchAuditLogs();

      expect(fetch).toHaveBeenCalledWith('/api/audit', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.items).toHaveLength(1);
    });

    it('fetches audit logs with all query parameters', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditLogListResponse));

      const params: AuditLogsQueryParams = {
        action: 'create',
        resource_type: 'camera',
        resource_id: 'cam-1',
        actor: 'system',
        status: 'success',
        start_date: '2025-01-01',
        end_date: '2025-01-31',
        limit: 50,
        offset: 10,
      };

      await fetchAuditLogs(params);

      const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
      expect(calledUrl).toContain('action=create');
      expect(calledUrl).toContain('resource_type=camera');
      expect(calledUrl).toContain('resource_id=cam-1');
      expect(calledUrl).toContain('actor=system');
      expect(calledUrl).toContain('status=success');
      expect(calledUrl).toContain('start_date=2025-01-01');
      expect(calledUrl).toContain('end_date=2025-01-31');
      expect(calledUrl).toContain('limit=50');
      expect(calledUrl).toContain('offset=10');
    });

    it('throws ApiError on server error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Audit service unavailable')
      );

      let caughtError: ApiError | null = null;
      const promise = fetchAuditLogs().catch((e) => {
        caughtError = e as ApiError;
      });

      await vi.runAllTimersAsync();
      await promise;

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Audit service unavailable');

      clearInFlightRequests();
      vi.useRealTimers();
    });
  });

  describe('fetchAuditStats (audit logs)', () => {
    it('fetches audit log stats successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditLogStats));

      const result = await fetchAuditLogStats();

      expect(fetch).toHaveBeenCalledWith('/api/audit/stats', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.total_logs).toBe(1000);
    });
  });

  describe('fetchAuditLog', () => {
    it('fetches single audit log by ID', async () => {
      const mockSingleLog = mockAuditLogListResponse.items[0];
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSingleLog));

      const result = await fetchAuditLog(1);

      expect(fetch).toHaveBeenCalledWith('/api/audit/1', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.id).toBe(1);
      expect(result.action).toBe('create');
    });

    it('throws ApiError on 404 not found', async () => {
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(404, 'Not Found', 'Audit log not found')
      );

      await expect(fetchAuditLog(999)).rejects.toThrow(ApiError);
      await expect(fetchAuditLog(999)).rejects.toMatchObject({
        status: 404,
        message: 'Audit log not found',
      });
    });
  });

  // ============================================================================
  // Circuit Breaker Endpoints
  // ============================================================================

  describe('fetchCircuitBreakers', () => {
    const mockCircuitBreakersResponse = {
      circuit_breakers: {
        rtdetr_detection: {
          name: 'rtdetr_detection',
          state: 'closed' as const,
          failure_count: 0,
          last_failure_time: null,
          last_success_time: '2025-01-01T12:00:00Z',
          consecutive_successes: 10,
          config: {
            failure_threshold: 5,
            recovery_timeout_seconds: 60,
            half_open_max_calls: 3,
          },
        },
        nemotron_analysis: {
          name: 'nemotron_analysis',
          state: 'open' as const,
          failure_count: 5,
          last_failure_time: '2025-01-01T11:55:00Z',
          last_success_time: '2025-01-01T11:50:00Z',
          consecutive_successes: 0,
          config: {
            failure_threshold: 5,
            recovery_timeout_seconds: 60,
            half_open_max_calls: 3,
          },
        },
      },
      total_count: 2,
      timestamp: '2025-01-01T12:00:00Z',
    };

    it('fetches all circuit breakers successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockCircuitBreakersResponse));

      const result = await fetchCircuitBreakers();

      expect(fetch).toHaveBeenCalledWith('/api/system/circuit-breakers', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.circuit_breakers).toBeDefined();
      expect(result.total_count).toBe(2);
      expect(result.circuit_breakers.rtdetr_detection.state).toBe('closed');
      expect(result.circuit_breakers.nemotron_analysis.state).toBe('open');
    });

    it('throws ApiError on server error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      // Use mockResolvedValue (not Once) to handle all retry attempts
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Failed to fetch circuit breakers')
      );

      // Capture the error - don't re-throw to avoid unhandled rejection warnings
      let caughtError: ApiError | null = null;
      const promise = fetchCircuitBreakers().catch((e) => {
        caughtError = e as ApiError;
      });

      // Advance through all retry delays (1000 + 2000 + 4000 ms) and run all timers
      await vi.runAllTimersAsync();
      await promise;

      // Verify error was thrown and captured
      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Failed to fetch circuit breakers');

      clearInFlightRequests();
      vi.useRealTimers();
    });
  });

  describe('resetCircuitBreaker', () => {
    const mockResetResponse = {
      name: 'nemotron_analysis',
      previous_state: 'open' as const,
      new_state: 'closed' as const,
      message: 'Circuit breaker nemotron_analysis reset from open to closed',
    };

    it('resets a circuit breaker successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockResetResponse));

      const result = await resetCircuitBreaker('nemotron_analysis');

      expect(fetch).toHaveBeenCalledWith('/api/system/circuit-breakers/nemotron_analysis/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.name).toBe('nemotron_analysis');
      expect(result.previous_state).toBe('open');
      expect(result.new_state).toBe('closed');
    });

    it('throws ApiError on 400 invalid name', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(400, 'Bad Request', 'Invalid circuit breaker name')
      );

      await expect(resetCircuitBreaker('invalid_name')).rejects.toThrow(ApiError);
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(400, 'Bad Request', 'Invalid circuit breaker name')
      );
      await expect(resetCircuitBreaker('invalid_name')).rejects.toMatchObject({
        status: 400,
        message: 'Invalid circuit breaker name',
      });
    });

    it('throws ApiError on 404 not found', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Circuit breaker not found')
      );

      await expect(resetCircuitBreaker('nonexistent')).rejects.toThrow(ApiError);
      vi.mocked(fetch).mockResolvedValueOnce(
        createMockErrorResponse(404, 'Not Found', 'Circuit breaker not found')
      );
      await expect(resetCircuitBreaker('nonexistent')).rejects.toMatchObject({
        status: 404,
        message: 'Circuit breaker not found',
      });
    });
  });

  // ============================================================================
  // Severity Metadata Endpoints
  // ============================================================================

  describe('fetchSeverityMetadata', () => {
    const mockSeverityMetadataResponse = {
      definitions: [
        {
          severity: 'low' as const,
          label: 'Low',
          description: 'Routine activity, no concern',
          color: '#22c55e',
          priority: 3,
          min_score: 0,
          max_score: 29,
        },
        {
          severity: 'medium' as const,
          label: 'Medium',
          description: 'Notable activity, worth reviewing',
          color: '#eab308',
          priority: 2,
          min_score: 30,
          max_score: 59,
        },
        {
          severity: 'high' as const,
          label: 'High',
          description: 'Concerning activity, review soon',
          color: '#f97316',
          priority: 1,
          min_score: 60,
          max_score: 84,
        },
        {
          severity: 'critical' as const,
          label: 'Critical',
          description: 'Immediate attention required',
          color: '#ef4444',
          priority: 0,
          min_score: 85,
          max_score: 100,
        },
      ],
      thresholds: {
        low_max: 29,
        medium_max: 59,
        high_max: 84,
      },
    };

    it('fetches severity metadata successfully', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSeverityMetadataResponse));

      const result = await fetchSeverityMetadata();

      expect(fetch).toHaveBeenCalledWith('/api/system/severity', {
        headers: { 'Content-Type': 'application/json' },

        signal: expect.any(AbortSignal),
      });
      expect(result.definitions).toHaveLength(4);
      expect(result.thresholds.low_max).toBe(29);
      expect(result.thresholds.medium_max).toBe(59);
      expect(result.thresholds.high_max).toBe(84);
    });

    it('returns all severity definitions with correct structure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockSeverityMetadataResponse));

      const result = await fetchSeverityMetadata();

      // Verify each severity level is present
      const severities = result.definitions.map((d) => d.severity);
      expect(severities).toContain('low');
      expect(severities).toContain('medium');
      expect(severities).toContain('high');
      expect(severities).toContain('critical');

      // Verify structure of a definition
      const criticalDef = result.definitions.find((d) => d.severity === 'critical');
      expect(criticalDef).toBeDefined();
      expect(criticalDef?.label).toBe('Critical');
      expect(criticalDef?.color).toBe('#ef4444');
      expect(criticalDef?.min_score).toBe(85);
      expect(criticalDef?.max_score).toBe(100);
    });

    it('throws ApiError on server error', async () => {
      vi.useFakeTimers();
      clearInFlightRequests();

      // Use mockResolvedValue (not Once) to handle all retry attempts
      vi.mocked(fetch).mockResolvedValue(
        createMockErrorResponse(500, 'Internal Server Error', 'Failed to fetch severity metadata')
      );

      // Capture the error - don't re-throw to avoid unhandled rejection warnings
      let caughtError: ApiError | null = null;
      const promise = fetchSeverityMetadata().catch((e) => {
        caughtError = e as ApiError;
      });

      // Advance through all retry delays (1000 + 2000 + 4000 ms) and run all timers
      await vi.runAllTimersAsync();
      await promise;

      // Verify error was thrown and captured
      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(500);
      expect(caughtError!.message).toBe('Failed to fetch severity metadata');

      clearInFlightRequests();
      vi.useRealTimers();
    });
  });
});

// ============================================================================
// Rate Limit Header Extraction Tests
// ============================================================================

describe('Rate Limit Header Extraction', () => {
  describe('extractRateLimitInfo', () => {
    it('extracts all rate limit headers when present', () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '95',
        'X-RateLimit-Reset': '1704067200',
      });
      const response = { headers } as Response;
      const result = extractRateLimitInfo(response);
      expect(result).toEqual({ limit: 100, remaining: 95, reset: 1704067200 });
    });

    it('includes retryAfter when Retry-After header is present', () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': '1704067200',
        'Retry-After': '30',
      });
      const response = { headers } as Response;
      const result = extractRateLimitInfo(response);
      expect(result).toEqual({ limit: 100, remaining: 0, reset: 1704067200, retryAfter: 30 });
    });

    it('returns null when X-RateLimit-Limit header is missing', () => {
      const headers = new Headers({
        'X-RateLimit-Remaining': '95',
        'X-RateLimit-Reset': '1704067200',
      });
      const response = { headers } as Response;
      expect(extractRateLimitInfo(response)).toBeNull();
    });

    it('returns null when X-RateLimit-Remaining header is missing', () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Reset': '1704067200',
      });
      const response = { headers } as Response;
      expect(extractRateLimitInfo(response)).toBeNull();
    });

    it('returns null when X-RateLimit-Reset header is missing', () => {
      const headers = new Headers({ 'X-RateLimit-Limit': '100', 'X-RateLimit-Remaining': '95' });
      const response = { headers } as Response;
      expect(extractRateLimitInfo(response)).toBeNull();
    });

    it('returns null when no rate limit headers are present', () => {
      const headers = new Headers({ 'Content-Type': 'application/json' });
      const response = { headers } as Response;
      expect(extractRateLimitInfo(response)).toBeNull();
    });

    it('returns null when rate limit headers have invalid values', () => {
      const headers = new Headers({
        'X-RateLimit-Limit': 'invalid',
        'X-RateLimit-Remaining': '95',
        'X-RateLimit-Reset': '1704067200',
      });
      const response = { headers } as Response;
      expect(extractRateLimitInfo(response)).toBeNull();
    });

    it('excludes retryAfter when Retry-After header has invalid value', () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': '1704067200',
        'Retry-After': 'invalid',
      });
      const response = { headers } as Response;
      const result = extractRateLimitInfo(response);
      expect(result).toEqual({ limit: 100, remaining: 0, reset: 1704067200 });
    });

    it('handles zero values correctly', () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': '0',
      });
      const response = { headers } as Response;
      const result = extractRateLimitInfo(response);
      expect(result).toEqual({ limit: 100, remaining: 0, reset: 0 });
    });
  });

  describe('429 Too Many Requests error handling', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      clearInFlightRequests();
    });

    it('includes retry_after in error data on 429 response', async () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': '1704067200',
        'Retry-After': '60',
      });
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 429,
        statusText: 'Too Many Requests',
        json: () => Promise.resolve({ detail: 'Rate limit exceeded' }),
        headers,
      } as Response);

      let caughtError: ApiError | null = null;
      try {
        await fetchCameras();
      } catch (e) {
        caughtError = e as ApiError;
      }

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(429);
      expect(caughtError!.data).toEqual(expect.objectContaining({ retry_after: 60 }));
    });

    it('handles 429 without Retry-After header', async () => {
      const headers = new Headers({
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': '1704067200',
      });
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 429,
        statusText: 'Too Many Requests',
        json: () => Promise.resolve({ detail: 'Rate limit exceeded' }),
        headers,
      } as Response);

      let caughtError: ApiError | null = null;
      try {
        await fetchCameras();
      } catch (e) {
        caughtError = e as ApiError;
      }

      expect(caughtError).toBeInstanceOf(ApiError);
      expect(caughtError!.status).toBe(429);
      if (typeof caughtError!.data === 'object' && caughtError!.data !== null) {
        expect((caughtError!.data as Record<string, unknown>).retry_after).toBeUndefined();
      }
    });
  });
});

// ============================================================================
// Event Enrichments Tests (NEM-2488)
// ============================================================================

describe('fetchEventEnrichments', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const mockEnrichmentsResponse: EventEnrichmentsResponse = {
    event_id: 123,
    enrichments: [
      {
        detection_id: 1,
        enriched_at: '2025-01-01T10:00:00Z',
        license_plate: {
          detected: true,
          text: 'ABC-1234',
          confidence: 0.95,
        },
        face: {
          detected: false,
          count: 0,
        },
        violence: {
          detected: false,
          score: 0,
        },
      },
      {
        detection_id: 2,
        enriched_at: '2025-01-01T10:01:00Z',
        license_plate: {
          detected: false,
        },
        face: {
          detected: true,
          count: 2,
        },
        violence: {
          detected: false,
          score: 0,
        },
      },
    ],
    count: 2,
    total: 10,
    limit: 50,
    offset: 0,
    has_more: true,
  };

  it('fetches event enrichments without params', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEnrichmentsResponse));

    const result = await fetchEventEnrichments(123);

    expect(fetch).toHaveBeenCalledWith('/api/events/123/enrichments', expect.any(Object));
    expect(result).toEqual(mockEnrichmentsResponse);
  });

  it('fetches event enrichments with pagination params', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEnrichmentsResponse));

    const params: EventEnrichmentsQueryParams = { limit: 10, offset: 20 };
    const result = await fetchEventEnrichments(123, params);

    expect(fetch).toHaveBeenCalledWith(
      '/api/events/123/enrichments?limit=10&offset=20',
      expect.any(Object)
    );
    expect(result).toEqual(mockEnrichmentsResponse);
  });

  it('fetches event enrichments with only limit param', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEnrichmentsResponse));

    const params: EventEnrichmentsQueryParams = { limit: 25 };
    await fetchEventEnrichments(456, params);

    expect(fetch).toHaveBeenCalledWith('/api/events/456/enrichments?limit=25', expect.any(Object));
  });

  it('fetches event enrichments with only offset param', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEnrichmentsResponse));

    const params: EventEnrichmentsQueryParams = { offset: 50 };
    await fetchEventEnrichments(789, params);

    expect(fetch).toHaveBeenCalledWith('/api/events/789/enrichments?offset=50', expect.any(Object));
  });

  it('throws ApiError on 404 for non-existent event', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      createMockErrorResponse(404, 'Not Found', 'Event not found')
    );

    await expect(fetchEventEnrichments(999)).rejects.toThrow(ApiError);
  });
});

// ============================================================================
// Analysis Stream Tests (NEM-2488)
// ============================================================================

describe('createAnalysisStream', () => {
  // Store original EventSource for restoration
  let originalEventSource: typeof EventSource | undefined;
  let MockEventSourceClass: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Save original EventSource if it exists
    originalEventSource = (globalThis as { EventSource?: typeof EventSource }).EventSource;

    // Create a proper mock EventSource class that can be used with `new`
    MockEventSourceClass = vi.fn();
    MockEventSourceClass.mockImplementation(function (
      this: {
        url: string;
        close: ReturnType<typeof vi.fn>;
        onmessage: null;
        onerror: null;
        onopen: null;
        readyState: number;
        CONNECTING: number;
        OPEN: number;
        CLOSED: number;
      },
      url: string
    ) {
      this.url = url;
      this.close = vi.fn();
      this.onmessage = null;
      this.onerror = null;
      this.onopen = null;
      this.readyState = 0;
      this.CONNECTING = 0;
      this.OPEN = 1;
      this.CLOSED = 2;
      return this;
    });

    (globalThis as { EventSource: typeof EventSource }).EventSource =
      MockEventSourceClass as unknown as typeof EventSource;
  });

  afterEach(() => {
    // Restore original EventSource
    if (originalEventSource) {
      (globalThis as { EventSource: typeof EventSource }).EventSource = originalEventSource;
    }
  });

  it('creates EventSource with batch ID only', () => {
    const params: AnalysisStreamParams = { batchId: 'batch-123' };
    const eventSource = createAnalysisStream(params);

    expect(MockEventSourceClass).toHaveBeenCalledWith('/api/events/analyze/batch-123/stream');
    expect(eventSource).toBeDefined();
  });

  it('creates EventSource with camera ID parameter', () => {
    const params: AnalysisStreamParams = {
      batchId: 'batch-456',
      cameraId: 'cam-front',
    };
    createAnalysisStream(params);

    expect(MockEventSourceClass).toHaveBeenCalledWith(
      '/api/events/analyze/batch-456/stream?camera_id=cam-front'
    );
  });

  it('creates EventSource with detection IDs parameter', () => {
    const params: AnalysisStreamParams = {
      batchId: 'batch-789',
      detectionIds: [1, 2, 3],
    };
    createAnalysisStream(params);

    expect(MockEventSourceClass).toHaveBeenCalledWith(
      '/api/events/analyze/batch-789/stream?detection_ids=1%2C2%2C3'
    );
  });

  it('creates EventSource with all parameters', () => {
    const params: AnalysisStreamParams = {
      batchId: 'batch-full',
      cameraId: 'cam-back',
      detectionIds: [10, 20],
    };
    createAnalysisStream(params);

    expect(MockEventSourceClass).toHaveBeenCalledWith(
      '/api/events/analyze/batch-full/stream?camera_id=cam-back&detection_ids=10%2C20'
    );
  });

  it('encodes special characters in batch ID', () => {
    const params: AnalysisStreamParams = {
      batchId: 'batch/with/slashes',
    };
    createAnalysisStream(params);

    expect(MockEventSourceClass).toHaveBeenCalledWith(
      '/api/events/analyze/batch%2Fwith%2Fslashes/stream'
    );
  });

  it('handles empty detection IDs array', () => {
    const params: AnalysisStreamParams = {
      batchId: 'batch-empty',
      detectionIds: [],
    };
    createAnalysisStream(params);

    expect(MockEventSourceClass).toHaveBeenCalledWith('/api/events/analyze/batch-empty/stream');
  });
});

// ============================================================================
// Cursor Validation Tests (NEM-2585)
// ============================================================================

describe('validateCursorFormat', () => {
  describe('valid cursors', () => {
    it('accepts undefined cursor', () => {
      expect(validateCursorFormat(undefined)).toBe(true);
    });

    it('accepts null cursor', () => {
      expect(validateCursorFormat(null)).toBe(true);
    });

    it('accepts empty string cursor', () => {
      expect(validateCursorFormat('')).toBe(true);
    });

    it('accepts alphanumeric cursors', () => {
      expect(validateCursorFormat('abc123XYZ')).toBe(true);
      expect(validateCursorFormat('eyJpZCI6MTIzfQ')).toBe(true);
    });

    it('accepts cursors with underscores (base64url)', () => {
      expect(validateCursorFormat('abc_def_123')).toBe(true);
    });

    it('accepts cursors with hyphens (base64url)', () => {
      expect(validateCursorFormat('abc-def-123')).toBe(true);
    });

    it('accepts cursors with equals padding', () => {
      expect(validateCursorFormat('eyJpZCI6MTIzfQ==')).toBe(true);
      expect(validateCursorFormat('YWJj=')).toBe(true);
    });

    it('accepts realistic base64-encoded JSON cursor', () => {
      // Base64 of {"id":123,"created_at":"2025-01-01T00:00:00Z"}
      const realisticCursor = 'eyJpZCI6MTIzLCJjcmVhdGVkX2F0IjoiMjAyNS0wMS0wMVQwMDowMDowMFoifQ=='; // pragma: allowlist secret
      expect(validateCursorFormat(realisticCursor)).toBe(true);
    });
  });

  describe('invalid cursors', () => {
    it('rejects cursor with HTML/XSS injection', () => {
      expect(() => validateCursorFormat('<script>alert("xss")</script>')).toThrow(
        CursorValidationError
      );
    });

    it('rejects cursor with SQL injection attempt', () => {
      expect(() => validateCursorFormat('SELECT * FROM users')).toThrow(CursorValidationError);
    });

    it('rejects cursor with spaces', () => {
      expect(() => validateCursorFormat('abc def')).toThrow(CursorValidationError);
    });

    it('rejects cursor with special characters', () => {
      const invalidChars = [
        ';',
        '&',
        '?',
        '/',
        '+',
        '!',
        '"',
        "'",
        '<',
        '>',
        '{',
        '}',
        '[',
        ']',
        '|',
        '\\',
        '`',
      ];
      for (const char of invalidChars) {
        expect(() => validateCursorFormat(`abc${char}def`)).toThrow(CursorValidationError);
      }
    });

    it('rejects cursor with newlines', () => {
      expect(() => validateCursorFormat('abc\ndef')).toThrow(CursorValidationError);
    });

    it('rejects cursor with tabs', () => {
      expect(() => validateCursorFormat('abc\tdef')).toThrow(CursorValidationError);
    });

    it('rejects cursor exceeding max length', () => {
      const longCursor = 'a'.repeat(501);
      expect(() => validateCursorFormat(longCursor)).toThrow(CursorValidationError);
      expect(() => validateCursorFormat(longCursor)).toThrow('maximum length');
    });

    it('includes helpful error message for invalid characters', () => {
      expect(() => validateCursorFormat('<invalid>')).toThrow(CursorValidationError);

      let caughtError: CursorValidationError | null = null;
      try {
        validateCursorFormat('<invalid>');
      } catch (error) {
        caughtError = error as CursorValidationError;
      }
      expect(caughtError).toBeInstanceOf(CursorValidationError);
      expect(caughtError?.message).toContain('invalid characters');
      expect(caughtError?.reason).toContain('base64url');
    });

    it('includes truncated cursor in error for long values', () => {
      const longCursor = 'a'.repeat(501);
      expect(() => validateCursorFormat(longCursor)).toThrow(CursorValidationError);

      let caughtError: CursorValidationError | null = null;
      try {
        validateCursorFormat(longCursor);
      } catch (error) {
        caughtError = error as CursorValidationError;
      }
      expect(caughtError).toBeInstanceOf(CursorValidationError);
      // Cursor should be truncated in error message
      expect(caughtError?.cursor.length).toBeLessThan(60);
      expect(caughtError?.cursor).toContain('...');
    });
  });

  describe('edge cases', () => {
    it('accepts cursor at exactly max length', () => {
      const maxCursor = 'a'.repeat(500);
      expect(validateCursorFormat(maxCursor)).toBe(true);
    });

    it('accepts single character cursor', () => {
      expect(validateCursorFormat('a')).toBe(true);
    });

    it('accepts cursor with only equals signs', () => {
      expect(validateCursorFormat('===')).toBe(true);
    });

    it('accepts cursor with mixed case', () => {
      expect(validateCursorFormat('AbCdEfGhIjKlMnOpQrStUvWxYz')).toBe(true);
    });
  });
});

describe('isValidCursor', () => {
  it('returns true for valid cursors', () => {
    expect(isValidCursor(undefined)).toBe(true);
    expect(isValidCursor(null)).toBe(true);
    expect(isValidCursor('')).toBe(true);
    expect(isValidCursor('abc123')).toBe(true);
    expect(isValidCursor('eyJpZCI6MTIzfQ==')).toBe(true);
  });

  it('returns false for invalid cursors without throwing', () => {
    expect(isValidCursor('<script>')).toBe(false);
    expect(isValidCursor('abc def')).toBe(false);
    expect(isValidCursor('a'.repeat(501))).toBe(false);
  });

  it('is useful for conditional logic', () => {
    const cursor = '<invalid>';
    if (!isValidCursor(cursor)) {
      // Handle invalid cursor gracefully
      expect(true).toBe(true);
    }
  });
});

describe('CursorValidationError', () => {
  it('has correct name property', () => {
    const error = new CursorValidationError('bad', 'test reason');
    expect(error.name).toBe('CursorValidationError');
  });

  it('has cursor property', () => {
    const error = new CursorValidationError('bad-cursor', 'test reason');
    expect(error.cursor).toBe('bad-cursor');
  });

  it('has reason property', () => {
    const error = new CursorValidationError('bad', 'specific reason');
    expect(error.reason).toBe('specific reason');
  });

  it('includes reason in message', () => {
    const error = new CursorValidationError('bad', 'specific reason');
    expect(error.message).toContain('specific reason');
  });

  it('extends Error', () => {
    const error = new CursorValidationError('bad', 'test');
    expect(error).toBeInstanceOf(Error);
  });
});

describe('fetchEvents cursor validation', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({
          'content-type': 'application/json',
        }),
        json: vi.fn().mockResolvedValue({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        }),
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('accepts valid cursor parameter', async () => {
    await expect(fetchEvents({ cursor: 'eyJpZCI6MTIzfQ==' })).resolves.toBeDefined();
  });

  it('rejects invalid cursor parameter', async () => {
    await expect(fetchEvents({ cursor: '<script>alert("xss")</script>' })).rejects.toThrow(
      CursorValidationError
    );
  });
});

describe('fetchEventDetections cursor validation', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({
          'content-type': 'application/json',
        }),
        json: vi.fn().mockResolvedValue({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        }),
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('accepts valid cursor parameter', async () => {
    await expect(fetchEventDetections(1, { cursor: 'eyJpZCI6MTIzfQ==' })).resolves.toBeDefined();
  });

  it('rejects invalid cursor parameter', async () => {
    await expect(
      fetchEventDetections(1, { cursor: '<script>alert("xss")</script>' })
    ).rejects.toThrow(CursorValidationError);
  });
});
