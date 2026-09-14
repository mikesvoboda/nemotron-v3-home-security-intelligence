/**
 * TDD Phase 5: Camera API Motion Sensitivity Tests
 *
 * These tests verify that the Camera API types properly include the motion_sensitivity field.
 * Uses MSW to mock API responses.
 *
 * Test Requirements:
 * - createCamera sends motion_sensitivity field for RTSP cameras
 * - updateCamera sends motion_sensitivity field for RTSP cameras
 * - API response includes motion_sensitivity field
 * - motion_sensitivity is properly serialized in request body
 */

import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';

import { server } from '../../mocks/server';
import { createCamera, updateCamera, fetchCamera, fetchCameras } from '../api';

import type { Camera, CameraCreate, CameraUpdate } from '../api';

// Helper type for captured request body - use unknown to avoid type inference issues
type CapturedBody = Record<string, unknown>;

describe('Camera API - Motion Sensitivity (TDD Phase 5)', () => {
  // Ensure MSW server is running
  beforeAll(() => {
    server.listen({ onUnhandledRequest: 'bypass' });
  });

  afterAll(() => {
    server.close();
  });

  afterEach(() => {
    server.resetHandlers();
  });

  describe('createCamera with motion_sensitivity', () => {
    it('should include motion_sensitivity in request body for RTSP camera', async () => {
      const newCamera: CameraCreate = {
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        motion_sensitivity: 0.75,
      };

      const mockResponse: Camera = {
        id: 'cam-rtsp-1',
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
        motion_sensitivity: 0.75,
      };

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.post('/api/cameras', async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json(mockResponse, { status: 201 });
        })
      );

      const result = await createCamera(newCamera);

      // Verify request body includes motion_sensitivity
      expect(capturedBody).not.toBeNull();
      expect(capturedBody!.motion_sensitivity).toBe(0.75);

      // Verify response includes motion_sensitivity
      expect(result.motion_sensitivity).toBe(0.75);
    });

    it('should send motion_sensitivity: 0.0 when explicitly set to minimum', async () => {
      const newCamera: CameraCreate = {
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        motion_sensitivity: 0.0,
      };

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.post('/api/cameras', async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json(
            {
              ...newCamera,
              id: 'cam-rtsp-1',
              created_at: '2025-01-29T00:00:00Z',
              last_seen_at: null,
            },
            { status: 201 }
          );
        })
      );

      await createCamera(newCamera);

      expect(capturedBody!.motion_sensitivity).toBe(0.0);
    });

    it('should send motion_sensitivity: 1.0 when explicitly set to maximum', async () => {
      const newCamera: CameraCreate = {
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        motion_sensitivity: 1.0,
      };

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.post('/api/cameras', async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json(
            {
              ...newCamera,
              id: 'cam-rtsp-1',
              created_at: '2025-01-29T00:00:00Z',
              last_seen_at: null,
            },
            { status: 201 }
          );
        })
      );

      await createCamera(newCamera);

      expect(capturedBody!.motion_sensitivity).toBe(1.0);
    });

    it('should NOT include motion_sensitivity for FTP camera when not provided', async () => {
      // Test raw API behavior - using type assertion to test sending without motion_sensitivity
      const newCamera = {
        name: 'FTP Camera',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        ingestion_mode: 'ftp',
      } as CameraCreate;

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.post('/api/cameras', async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json(
            {
              ...newCamera,
              id: 'cam-ftp-1',
              created_at: '2025-01-29T00:00:00Z',
              last_seen_at: null,
            },
            { status: 201 }
          );
        })
      );

      await createCamera(newCamera);

      expect(capturedBody!.motion_sensitivity).toBeUndefined();
    });

    it('should handle default motion_sensitivity value (0.5) for RTSP camera', async () => {
      const newCamera: CameraCreate = {
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        motion_sensitivity: 0.5,
      };

      const mockResponse: Camera = {
        id: 'cam-rtsp-1',
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
        motion_sensitivity: 0.5,
      };

      server.use(
        http.post('/api/cameras', () => {
          return HttpResponse.json(mockResponse, { status: 201 });
        })
      );

      const result = await createCamera(newCamera);

      expect(result.motion_sensitivity).toBe(0.5);
    });
  });

  describe('updateCamera with motion_sensitivity', () => {
    it('should include motion_sensitivity in update request', async () => {
      const cameraId = 'cam-rtsp-1';
      const updateData: CameraUpdate = {
        motion_sensitivity: 0.8,
      };

      let capturedBody: CapturedBody | null = null;

      const mockResponse: Camera = {
        id: cameraId,
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
        motion_sensitivity: 0.8,
      };

      server.use(
        http.patch(`/api/cameras/${cameraId}`, async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json(mockResponse);
        })
      );

      const result = await updateCamera(cameraId, updateData);

      // Verify request body includes motion_sensitivity
      expect(capturedBody!.motion_sensitivity).toBe(0.8);

      // Verify response includes updated motion_sensitivity
      expect(result.motion_sensitivity).toBe(0.8);
    });

    it('should allow partial update with motion_sensitivity only', async () => {
      const cameraId = 'cam-rtsp-1';
      const updateData: CameraUpdate = {
        motion_sensitivity: 0.3,
      };

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.patch(`/api/cameras/${cameraId}`, async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json({
            id: cameraId,
            name: 'RTSP Camera',
            folder_path: 'rtsp://192.168.1.100/stream',
            status: 'online',
            ingestion_mode: 'rtsp',
            created_at: '2025-01-29T00:00:00Z',
            last_seen_at: null,
            motion_sensitivity: 0.3,
          });
        })
      );

      await updateCamera(cameraId, updateData);

      expect(capturedBody).not.toBeNull();
      expect(Object.keys(capturedBody!)).toEqual(['motion_sensitivity']);
      expect(capturedBody!.motion_sensitivity).toBe(0.3);
    });

    it('should include motion_sensitivity in update along with other fields', async () => {
      const cameraId = 'cam-rtsp-1';
      const updateData: CameraUpdate = {
        name: 'Updated RTSP Camera',
        status: 'offline',
        motion_sensitivity: 0.9,
      };

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.patch(`/api/cameras/${cameraId}`, async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json({
            id: cameraId,
            name: 'Updated RTSP Camera',
            folder_path: 'rtsp://192.168.1.100/stream',
            status: 'offline',
            ingestion_mode: 'rtsp',
            created_at: '2025-01-29T00:00:00Z',
            last_seen_at: null,
            motion_sensitivity: 0.9,
          });
        })
      );

      const result = await updateCamera(cameraId, updateData);

      expect(capturedBody!.name).toBe('Updated RTSP Camera');
      expect(capturedBody!.status).toBe('offline');
      expect(capturedBody!.motion_sensitivity).toBe(0.9);

      expect(result.motion_sensitivity).toBe(0.9);
    });

    it('should allow update without motion_sensitivity field', async () => {
      const cameraId = 'cam-rtsp-1';
      const updateData: CameraUpdate = {
        name: 'Updated RTSP Camera',
      };

      let capturedBody: CapturedBody | null = null;

      server.use(
        http.patch(`/api/cameras/${cameraId}`, async ({ request }) => {
          capturedBody = (await request.json()) as CapturedBody;
          return HttpResponse.json({
            id: cameraId,
            name: 'Updated RTSP Camera',
            folder_path: 'rtsp://192.168.1.100/stream',
            status: 'online',
            ingestion_mode: 'rtsp',
            created_at: '2025-01-29T00:00:00Z',
            last_seen_at: null,
            motion_sensitivity: 0.5,
          });
        })
      );

      await updateCamera(cameraId, updateData);

      expect(capturedBody!.motion_sensitivity).toBeUndefined();
    });
  });

  describe('fetchCamera response with motion_sensitivity', () => {
    it('should return motion_sensitivity field for RTSP camera', async () => {
      const cameraId = 'cam-rtsp-1';
      const mockResponse: Camera = {
        id: cameraId,
        name: 'RTSP Camera',
        folder_path: 'rtsp://192.168.1.100/stream',
        status: 'online',
        ingestion_mode: 'rtsp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
        motion_sensitivity: 0.65,
      };

      server.use(
        http.get(`/api/cameras/${cameraId}`, () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const result = await fetchCamera(cameraId);

      expect(result.motion_sensitivity).toBe(0.65);
    });

    it('should handle missing motion_sensitivity field for FTP camera', async () => {
      const cameraId = 'cam-ftp-1';
      // Test raw API response behavior - some FTP cameras may not have motion_sensitivity
      const mockResponse = {
        id: cameraId,
        name: 'FTP Camera',
        folder_path: '/export/foscam/front_door',
        status: 'online',
        ingestion_mode: 'ftp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
      } as Camera;

      server.use(
        http.get(`/api/cameras/${cameraId}`, () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const result = await fetchCamera(cameraId);

      expect(result.motion_sensitivity).toBeUndefined();
    });
  });

  describe('fetchCameras response with motion_sensitivity', () => {
    it('should return motion_sensitivity for RTSP cameras in list', async () => {
      const mockResponse = {
        items: [
          {
            id: 'cam-rtsp-1',
            name: 'RTSP Camera 1',
            folder_path: 'rtsp://192.168.1.100/stream',
            status: 'online',
            ingestion_mode: 'rtsp',
            created_at: '2025-01-29T00:00:00Z',
            last_seen_at: null,
            motion_sensitivity: 0.4,
          },
          {
            id: 'cam-ftp-1',
            name: 'FTP Camera',
            folder_path: '/export/foscam/front_door',
            status: 'online',
            ingestion_mode: 'ftp',
            created_at: '2025-01-29T00:00:00Z',
            last_seen_at: null,
          },
          {
            id: 'cam-rtsp-2',
            name: 'RTSP Camera 2',
            folder_path: 'rtsp://192.168.1.101/stream',
            status: 'online',
            ingestion_mode: 'rtsp',
            created_at: '2025-01-29T00:00:00Z',
            last_seen_at: null,
            motion_sensitivity: 0.7,
          },
        ],
        total: 3,
        page: 1,
        size: 10,
        pages: 1,
      };

      server.use(
        http.get('/api/cameras', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const result = await fetchCameras();

      expect(result).toHaveLength(3);
      expect(result[0].motion_sensitivity).toBe(0.4);
      expect(result[1].motion_sensitivity).toBeUndefined();
      expect(result[2].motion_sensitivity).toBe(0.7);
    });
  });

  describe('Motion sensitivity type safety', () => {
    it('should ensure motion_sensitivity is a number type', () => {
      const camera: Camera = {
        id: 'cam-1',
        name: 'Test Camera',
        folder_path: 'rtsp://test',
        status: 'online',
        ingestion_mode: 'rtsp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
        motion_sensitivity: 0.5,
      };

      // TypeScript compile-time check
      const sensitivity: number | undefined = camera.motion_sensitivity;
      expect(typeof sensitivity).toBe('number');
    });

    it('should allow motion_sensitivity to be undefined (legacy API responses)', () => {
      // Test that we can handle API responses from older cameras that may not have motion_sensitivity
      const camera = {
        id: 'cam-1',
        name: 'Test Camera',
        folder_path: '/export/test',
        status: 'online',
        ingestion_mode: 'ftp',
        created_at: '2025-01-29T00:00:00Z',
        last_seen_at: null,
      } as Camera;

      expect(camera.motion_sensitivity).toBeUndefined();
    });
  });
});
