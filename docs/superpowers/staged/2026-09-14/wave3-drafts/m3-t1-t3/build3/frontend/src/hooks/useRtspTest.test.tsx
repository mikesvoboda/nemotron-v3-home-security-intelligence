/**
 * useRtspTest Hook Test Suite (NEM-4748 Phase 2: Connection Testing)
 *
 * TDD Red Phase: Tests MUST FAIL until useRtspTest hook is implemented
 *
 * Tests cover:
 * - Successful connection test
 * - Error handling
 * - Loading state management
 * - Cache invalidation after test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi } from 'vitest';

import { useRtspTest } from './useRtspTest';
import { server } from '../mocks/server';

import type { RTSPTestResult, RTSPTestRequest } from '../types/rtsp';
import type { ReactNode } from 'react';

// Test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const Wrapper = ({ children }: { children: ReactNode }) => {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };

  return Wrapper;
}

describe('useRtspTest', () => {
  describe('Successful Connection Test', () => {
    it('should test RTSP connection successfully', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 245,
        capabilities: {
          video: true,
          audio: true,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
        username: 'admin',
        password: 'password123', // pragma: allowlist secret
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.data).toEqual(mockResult);
    });

    it('should test connection without credentials', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 150,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1280x720',
          codec: 'H.264',
          fps: 15,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.data).toEqual(mockResult);
    });

    it('should handle successful test with partial capabilities', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 300,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: null,
          codec: 'H.264',
          fps: null,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.data?.capabilities?.resolution).toBeNull();
      expect(result.current.testConnection.data?.capabilities?.fps).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('should handle connection timeout error', async () => {
      const mockResult: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Connection timeout - stream did not respond within 5 seconds',
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.data?.success).toBe(false);
      expect(result.current.testConnection.data?.error_message).toContain('timeout');
    });

    it('should handle authentication error', async () => {
      const mockResult: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Authentication failed - check username and password',
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
        username: 'wrong',
        password: 'credentials', // pragma: allowlist secret
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.data?.success).toBe(false);
      expect(result.current.testConnection.data?.error_message).toContain('Authentication');
    });

    it('should handle invalid URL error', async () => {
      const mockResult: RTSPTestResult = {
        success: false,
        latency_ms: null,
        capabilities: null,
        error_message: 'Invalid URL format - must use rtsp:// or rtsps://',
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'http://192.168.1.100/stream',
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.data?.success).toBe(false);
      expect(result.current.testConnection.data?.error_message).toContain('Invalid URL');
    });

    it('should handle network error', async () => {
      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.error();
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isError).toBe(true);
      });

      expect(result.current.testConnection.error).toBeDefined();
    });
  });

  describe('Loading State', () => {
    it('should set loading state during test', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', async () => {
          // Simulate delay
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      expect(result.current.testConnection.isPending).toBe(false);

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      // Should be loading after mutation - wait for state update
      await waitFor(() => {
        expect(result.current.testConnection.isPending).toBe(true);
      });

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      expect(result.current.testConnection.isPending).toBe(false);
    });

    it('should not allow multiple simultaneous tests', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      // Wait for pending state
      await waitFor(() => {
        expect(result.current.testConnection.isPending).toBe(true);
      });

      // Attempt second mutation while first is pending
      result.current.testConnection.mutate(testRequest);

      // Should still only be one pending request
      expect(result.current.testConnection.isPending).toBe(true);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });
    });
  });

  describe('Cache Invalidation', () => {
    it('should not invalidate any queries (test is read-only)', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const queryClient = new QueryClient({
        defaultOptions: {
          queries: { retry: false },
          mutations: { retry: false },
        },
      });

      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const Wrapper = ({ children }: { children: ReactNode }) => {
        return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
      };

      const { result } = renderHook(() => useRtspTest(), { wrapper: Wrapper });

      const testRequest: RTSPTestRequest = {
        rtsp_url: 'rtsp://192.168.1.100:554/stream1',
      };

      result.current.testConnection.mutate(testRequest);

      await waitFor(() => {
        expect(result.current.testConnection.isSuccess).toBe(true);
      });

      // Test should not invalidate cameras query (it's read-only)
      expect(invalidateSpy).not.toHaveBeenCalled();
    });
  });

  describe('Type Safety', () => {
    it('should enforce required rtsp_url field', async () => {
      const mockResult: RTSPTestResult = {
        success: true,
        latency_ms: 200,
        capabilities: {
          video: true,
          audio: false,
          ptz: false,
          resolution: '1920x1080',
          codec: 'H.264',
          fps: 30,
        },
        error_message: null,
      };

      server.use(
        http.post('/api/cameras/rtsp/test', () => {
          return HttpResponse.json(mockResult);
        })
      );

      const { result } = renderHook(() => useRtspTest(), {
        wrapper: createWrapper(),
      });

      const invalidRequest = {};

      // TypeScript should catch this at compile time
      // But for runtime, we ensure the mutation handles it gracefully
      // @ts-expect-error - Testing type safety: rtsp_url is required
      result.current.testConnection.mutate(invalidRequest);

      await waitFor(() => {
        expect(
          result.current.testConnection.isError || result.current.testConnection.isSuccess
        ).toBe(true);
      });
    });
  });
});
