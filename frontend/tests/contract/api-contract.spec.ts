/**
 * API Contract Tests
 *
 * Validates frontend-backend API contract consistency:
 * - Request/response shapes match OpenAPI schema
 * - Required fields are present
 * - Data types are correct
 * - WebSocket message formats match specification
 * - Error responses follow contract
 *
 * These tests run on the fully integrated system (backend + frontend)
 * and catch schema mismatches early.
 */

import { test, expect } from '@playwright/test';
import type {
  Camera,
  Event,
  Detection,
  HealthResponse,
  SystemStats,
  GPUStats,
  EventListResponse,
  DetectionListResponse,
} from '../../src/types/generated';
import type { WebSocketMessage } from '../../src/types/websocket';

// Helper to make API calls from within the test
async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`http://localhost:8000${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(
      `API error: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}

test.describe('API Contract Tests', () => {
  test.describe('System Health Endpoints', () => {
    test('GET / returns valid HealthResponse', async () => {
      const data = await fetchApi<HealthResponse>('/');

      expect(data).toHaveProperty('status');
      expect(data.status).toMatch(/^(healthy|degraded|unhealthy)$/);

      // Optional fields
      if ('timestamp' in data) {
        expect(typeof data.timestamp).toBe('string');
      }
    });

    test('GET /api/system/health/ready returns ReadinessResponse', async () => {
      const data = await fetchApi('/api/system/health/ready');

      expect(data).toHaveProperty('status');
      expect(['ready', 'not_ready']).toContain(data.status);
    });

    test('GET /api/system/stats returns valid SystemStats', async () => {
      const data = await fetchApi<SystemStats>('/api/system/stats');

      expect(data).toBeDefined();
      expect(typeof data).toBe('object');

      // Should contain at least some metrics
      // Exact fields depend on implementation
      expect(Object.keys(data).length).toBeGreaterThan(0);
    });

    test('GET /api/system/gpu returns valid GPUStats', async () => {
      const data = await fetchApi<GPUStats>('/api/system/gpu');

      expect(data).toBeDefined();

      // GPU stats have these key fields
      if ('gpu_utilization' in data) {
        expect(typeof data.gpu_utilization).toBe('number');
        expect(data.gpu_utilization).toBeGreaterThanOrEqual(0);
        expect(data.gpu_utilization).toBeLessThanOrEqual(100);
      }

      if ('memory_used' in data) {
        expect(typeof data.memory_used).toBe('number');
      }

      if ('temperature' in data) {
        expect(typeof data.temperature).toBe('number');
      }
    });
  });

  test.describe('Camera Endpoints', () => {
    test('GET /api/cameras returns CameraListResponse with array', async () => {
      const data = await fetchApi<{ items: Camera[] }>('/api/cameras');

      expect(Array.isArray(data.items || data)).toBe(true);

      if (data.items && data.items.length > 0) {
        const camera = data.items[0];

        // Validate camera structure
        expect(camera).toHaveProperty('id');
        expect(camera).toHaveProperty('name');
        expect(typeof camera.id).toBe('string');
        expect(typeof camera.name).toBe('string');
      }
    });
  });

  test.describe('Event Endpoints', () => {
    test('GET /api/events returns EventListResponse with pagination', async () => {
      const data = await fetchApi<EventListResponse>('/api/events?limit=10');

      expect(data).toBeDefined();
      expect(Array.isArray(data.items || data.events)).toBe(true);

      // Pagination metadata optional
      if ('total' in data) {
        expect(typeof data.total).toBe('number');
      }

      if ('skip' in data) {
        expect(typeof data.skip).toBe('number');
      }

      if ('limit' in data) {
        expect(typeof data.limit).toBe('number');
      }
    });

    test('Event objects contain required fields', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=1');
      const events = data.items || data.events || [];

      if (events.length > 0) {
        const event = events[0];

        // Required event fields
        expect(event).toHaveProperty('id');
        expect(event).toHaveProperty('camera_id');
        expect(event).toHaveProperty('risk_score');

        // Type validation
        expect(typeof event.id).toBe('number');
        expect(typeof event.camera_id).toBe('string');
        expect(typeof event.risk_score).toBe('number');

        // Risk score 0-100
        expect(event.risk_score).toBeGreaterThanOrEqual(0);
        expect(event.risk_score).toBeLessThanOrEqual(100);
      }
    });

    test('Event risk_level matches score range', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=10');
      const events = data.items || data.events || [];

      for (const event of events) {
        if ('risk_level' in event && 'risk_score' in event) {
          const { risk_score, risk_level } = event;

          // Validate risk_level matches risk_score
          if (risk_score < 30) {
            expect(['low', 'none']).toContain(risk_level);
          } else if (risk_score < 60) {
            expect(risk_level).toBe('medium');
          } else if (risk_score < 85) {
            expect(risk_level).toBe('high');
          } else {
            expect(risk_level).toBe('critical');
          }
        }
      }
    });
  });

  test.describe('Detection Endpoints', () => {
    test('GET /api/detections returns DetectionListResponse', async () => {
      const data = await fetchApi<{
        items: Detection[];
      }>('/api/detections?limit=10');

      expect(Array.isArray(data.items || data.detections)).toBe(true);

      if ((data.items || data.detections)?.length > 0) {
        const detection = (data.items || data.detections)[0];

        expect(detection).toHaveProperty('id');
        expect(detection).toHaveProperty('camera_id');
        expect(detection).toHaveProperty('object_type');

        // Type validation
        expect(typeof detection.id).toBe('number');
        expect(typeof detection.camera_id).toBe('string');
        expect(typeof detection.object_type).toBe('string');
      }
    });

    test('Detection confidence scores are in valid range', async () => {
      const data = await fetchApi<{
        items: Detection[];
      }>('/api/detections?limit=10');
      const detections = data.items || data.detections || [];

      for (const detection of detections) {
        if ('confidence' in detection) {
          expect(detection.confidence).toBeGreaterThanOrEqual(0);
          expect(detection.confidence).toBeLessThanOrEqual(1);
        }
      }
    });
  });

  test.describe('Error Response Contracts', () => {
    test('404 errors return consistent error format', async () => {
      const response = await fetch(
        'http://localhost:8000/api/cameras/nonexistent'
      );

      expect(response.status).toBe(404);

      const data = await response.json();
      expect(data).toHaveProperty('detail');
    });

    test('Validation errors include field information', async () => {
      // Try to create invalid data
      const response = await fetch('http://localhost:8000/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}), // Missing required fields
      });

      expect(response.status).toBe(422); // Validation error

      const data = await response.json();
      // FastAPI validation error format
      expect(data).toHaveProperty('detail');
    });
  });

  test.describe('Pagination Contract', () => {
    test('Paginated endpoints support limit and skip parameters', async () => {
      // Test limit parameter
      const data1 = await fetchApi<any>('/api/events?limit=5');
      const items1 = data1.items || data1.events || [];
      expect(items1.length).toBeLessThanOrEqual(5);

      // Test skip parameter (if supported)
      const data2 = await fetchApi<any>('/api/events?limit=5&skip=5');
      const items2 = data2.items || data2.events || [];
      expect(items2.length).toBeLessThanOrEqual(5);
    });

    test('Pagination cursor format (if applicable)', async () => {
      const data = await fetchApi<any>('/api/events?limit=1');

      // Check for cursor-based pagination (optional implementation detail)
      if ('next_cursor' in data) {
        expect(typeof data.next_cursor).toMatch(/string|null/);
      }
    });
  });

  test.describe('Data Type Consistency', () => {
    test('Timestamps are ISO 8601 format', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=1');
      const events = data.items || data.events || [];

      const iso8601Regex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/;

      for (const event of events) {
        if ('started_at' in event && event.started_at) {
          expect(String(event.started_at)).toMatch(iso8601Regex);
        }
        if ('ended_at' in event && event.ended_at) {
          expect(String(event.ended_at)).toMatch(iso8601Regex);
        }
      }
    });

    test('Numeric IDs are integers', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=5');
      const events = data.items || data.events || [];

      for (const event of events) {
        expect(Number.isInteger(event.id)).toBe(true);
      }
    });

    test('Boolean fields are true booleans', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=5');
      const events = data.items || data.events || [];

      for (const event of events) {
        if ('reviewed' in event) {
          expect(typeof event.reviewed).toBe('boolean');
        }
      }
    });
  });

  test.describe('Required Fields Contract', () => {
    test('Camera responses always have id and name', async () => {
      const data = await fetchApi<{
        items: Camera[];
      }>('/api/cameras');
      const cameras = data.items || [];

      for (const camera of cameras) {
        expect(camera).toHaveProperty('id');
        expect(camera).toHaveProperty('name');
        expect(camera.id).toBeTruthy();
        expect(camera.name).toBeTruthy();
      }
    });

    test('Event responses always have critical fields', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=5');
      const events = data.items || data.events || [];

      const requiredFields = ['id', 'camera_id', 'risk_score'];

      for (const event of events) {
        for (const field of requiredFields) {
          expect(event).toHaveProperty(field);
          expect((event as any)[field]).not.toBeUndefined();
        }
      }
    });
  });

  test.describe('Enum Value Contracts', () => {
    test('Valid risk_level values only', async () => {
      const data = await fetchApi<{
        items: Event[];
      }>('/api/events?limit=20');
      const events = data.items || data.events || [];

      const validRiskLevels = ['low', 'medium', 'high', 'critical', 'none'];

      for (const event of events) {
        if ('risk_level' in event) {
          expect(validRiskLevels).toContain(event.risk_level);
        }
      }
    });

    test('Valid object_type values in detections', async () => {
      const data = await fetchApi<{
        items: Detection[];
      }>('/api/detections?limit=20');
      const detections = data.items || data.detections || [];

      // Common object types - adjust based on actual model
      const validObjectTypes = [
        'person',
        'dog',
        'cat',
        'car',
        'bicycle',
        'unknown',
      ];

      for (const detection of detections) {
        // Object type should be a non-empty string
        expect(typeof detection.object_type).toBe('string');
        expect(detection.object_type.length).toBeGreaterThan(0);
      }
    });
  });
});

test.describe('WebSocket Contract Tests', () => {
  test('WebSocket connects successfully', async ({ page }) => {
    let connected = false;

    page.on('websocket', (ws) => {
      ws.on('framereceived', (frame) => {
        try {
          const data = JSON.parse(frame.payload as string);
          if (data.type === 'connected') {
            connected = true;
          }
        } catch (e) {
          // Ignore non-JSON frames
        }
      });
    });

    await page.goto('/');
    await page.waitForTimeout(1000);

    expect(connected).toBe(true);
  });

  test('WebSocket messages include required envelope fields', async ({ page }) => {
    const messages: WebSocketMessage[] = [];

    page.on('websocket', (ws) => {
      ws.on('framereceived', (frame) => {
        try {
          const data = JSON.parse(frame.payload as string);
          messages.push(data);
        } catch (e) {
          // Ignore
        }
      });
    });

    await page.goto('/');
    await page.waitForTimeout(2000);

    // Should have received some messages
    expect(messages.length).toBeGreaterThan(0);

    for (const msg of messages.slice(0, 5)) {
      // All messages should have envelope structure
      expect(msg).toHaveProperty('type');
      expect(msg).toHaveProperty('timestamp');
      expect(msg).toHaveProperty('id');
      expect(msg).toHaveProperty('data');

      // Validate timestamp format (ISO 8601)
      expect(msg.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);

      // Validate type is a string
      expect(typeof msg.type).toBe('string');
    }
  });

  test('GPU stats message includes valid metrics', async ({ page }) => {
    let gpuMessage: WebSocketMessage | null = null;

    page.on('websocket', (ws) => {
      ws.on('framereceived', (frame) => {
        try {
          const data = JSON.parse(frame.payload as string);
          if (data.type === 'gpu:stats') {
            gpuMessage = data;
          }
        } catch (e) {
          // Ignore
        }
      });
    });

    await page.goto('/');

    // Wait for GPU stats message
    let waited = 0;
    while (!gpuMessage && waited < 30000) {
      await page.waitForTimeout(100);
      waited += 100;
    }

    if (gpuMessage) {
      const { data } = gpuMessage as any;

      // Validate GPU metrics are in valid ranges
      if ('gpu_utilization' in data) {
        expect(data.gpu_utilization).toBeGreaterThanOrEqual(0);
        expect(data.gpu_utilization).toBeLessThanOrEqual(100);
      }

      if ('memory_percent' in data) {
        expect(data.memory_percent).toBeGreaterThanOrEqual(0);
        expect(data.memory_percent).toBeLessThanOrEqual(100);
      }

      if ('temperature' in data) {
        expect(typeof data.temperature).toBe('number');
        expect(data.temperature).toBeGreaterThan(-100);
        expect(data.temperature).toBeLessThan(200); // Sanity check
      }
    }
  });

  test('Event messages contain required fields', async ({ page }) => {
    const eventMessages: WebSocketMessage[] = [];

    page.on('websocket', (ws) => {
      ws.on('framereceived', (frame) => {
        try {
          const data = JSON.parse(frame.payload as string);
          if (data.type?.startsWith('event:')) {
            eventMessages.push(data);
          }
        } catch (e) {
          // Ignore
        }
      });
    });

    await page.goto('/');
    await page.waitForTimeout(3000);

    for (const msg of eventMessages) {
      const { type, data } = msg as any;

      expect(['event:new', 'event:updated']).toContain(type);
      expect(data).toBeDefined();

      if (type === 'event:new') {
        expect(data).toHaveProperty('id');
        expect(data).toHaveProperty('camera_id');
        expect(data).toHaveProperty('risk_score');
      }
    }
  });
});
