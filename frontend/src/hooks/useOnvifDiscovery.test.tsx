/**
 * useOnvifDiscovery Hook Test Suite (NEM-4754 Phase 3: ONVIF Discovery)
 *
 * Tests cover:
 * - Successful device discovery
 * - Empty results handling
 * - Error handling
 * - Loading state management
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect } from 'vitest';

import { useOnvifDiscovery } from './useOnvifDiscovery';
import { server } from '../mocks/server';

import type { OnvifDiscoveryResponse, OnvifDiscoveryRequest } from '../types/onvif';
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

describe('useOnvifDiscovery', () => {
  describe('Successful Discovery', () => {
    it('should discover ONVIF devices successfully', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: [
          {
            device_url: 'http://192.168.1.100/onvif/device_service',
            ip: '192.168.1.100',
            port: 80,
            manufacturer: 'Hikvision',
            model: 'DS-2CD2032-I',
            firmware_version: '5.4.5',
            serial_number: 'SN001234567890',
            hardware_id: 'HW-001',
            rtsp_urls: [
              { profile: 'mainStream', url: 'rtsp://192.168.1.100:554/stream1' },
              { profile: 'subStream', url: 'rtsp://192.168.1.100:554/stream2' },
            ],
            capabilities: {
              video: true,
              ptz: true,
              events: true,
            },
          },
          {
            device_url: 'http://192.168.1.101/onvif/device_service',
            ip: '192.168.1.101',
            port: 80,
            manufacturer: 'Dahua',
            model: 'IPC-HDW2431T',
            firmware_version: null,
            serial_number: null,
            hardware_id: null,
            rtsp_urls: [{ profile: 'main', url: 'rtsp://192.168.1.101:554/cam/realmonitor' }],
            capabilities: {
              video: true,
              ptz: false,
              events: false,
            },
          },
        ],
        count: 2,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: '192.168.1.0/24',
        timeout: 10,
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isSuccess).toBe(true);
      });

      expect(result.current.discoverDevices.data).toEqual(mockResponse);
      expect(result.current.discoverDevices.data?.count).toBe(2);
      expect(result.current.discoverDevices.data?.devices[0].manufacturer).toBe('Hikvision');
    });

    it('should handle discovery without timeout parameter', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: [],
        count: 0,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: '10.0.0.0/24',
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isSuccess).toBe(true);
      });

      expect(result.current.discoverDevices.data).toEqual(mockResponse);
    });

    it('should handle discovery with empty results', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: [],
        count: 0,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: '192.168.1.0/24',
        timeout: 5,
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isSuccess).toBe(true);
      });

      expect(result.current.discoverDevices.data?.devices).toEqual([]);
      expect(result.current.discoverDevices.data?.count).toBe(0);
    });
  });

  describe('Error Handling', () => {
    it('should handle discovery failure', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(
            { detail: 'Discovery failed: WSDiscovery library not installed' },
            { status: 500 }
          );
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: '192.168.1.0/24',
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isError).toBe(true);
      });

      expect(result.current.discoverDevices.error?.message).toContain('WSDiscovery');
    });

    it('should handle network error', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.error();
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: '192.168.1.0/24',
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isError).toBe(true);
      });

      expect(result.current.discoverDevices.error).toBeDefined();
    });

    it('should handle invalid subnet validation error', async () => {
      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(
            { detail: 'Invalid subnet format' },
            { status: 422 }
          );
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: 'invalid-subnet',
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isError).toBe(true);
      });

      expect(result.current.discoverDevices.error?.message).toContain('Invalid subnet');
    });
  });

  describe('Loading State', () => {
    it('should set loading state during discovery', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: [],
        count: 0,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', async () => {
          // Simulate network delay
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockResponse);
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      expect(result.current.discoverDevices.isPending).toBe(false);

      const request: OnvifDiscoveryRequest = {
        subnet: '192.168.1.0/24',
      };

      result.current.discoverDevices.mutate(request);

      // Should be loading after mutation
      await waitFor(() => {
        expect(result.current.discoverDevices.isPending).toBe(true);
      });

      await waitFor(() => {
        expect(result.current.discoverDevices.isSuccess).toBe(true);
      });

      expect(result.current.discoverDevices.isPending).toBe(false);
    });
  });

  describe('Reset Functionality', () => {
    it('should allow resetting the mutation state', async () => {
      const mockResponse: OnvifDiscoveryResponse = {
        devices: [
          {
            device_url: 'http://192.168.1.100/onvif/device_service',
            ip: '192.168.1.100',
            port: 80,
            manufacturer: 'Test',
            model: 'Test Model',
            firmware_version: null,
            serial_number: null,
            hardware_id: null,
            rtsp_urls: [],
            capabilities: { video: true, ptz: false, events: false },
          },
        ],
        count: 1,
      };

      server.use(
        http.post('/api/cameras/onvif/discover', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      const { result } = renderHook(() => useOnvifDiscovery(), {
        wrapper: createWrapper(),
      });

      const request: OnvifDiscoveryRequest = {
        subnet: '192.168.1.0/24',
      };

      result.current.discoverDevices.mutate(request);

      await waitFor(() => {
        expect(result.current.discoverDevices.isSuccess).toBe(true);
      });

      expect(result.current.discoverDevices.data?.count).toBe(1);

      // Reset the mutation state
      result.current.discoverDevices.reset();

      // After reset, isIdle should be true and isSuccess should be false
      // Note: TanStack Query v5 may preserve data after reset, so we check status flags
      await waitFor(() => {
        expect(result.current.discoverDevices.isIdle).toBe(true);
      });
      expect(result.current.discoverDevices.isSuccess).toBe(false);
    });
  });
});
