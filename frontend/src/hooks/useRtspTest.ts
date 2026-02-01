/**
 * useRtspTest Hook (NEM-4748 Phase 2: Connection Testing)
 *
 * Hook for testing RTSP camera connections before adding them.
 * Uses TanStack Query's useMutation for the test request.
 */

import { useMutation } from '@tanstack/react-query';

import type { RTSPTestRequest, RTSPTestResult } from '../types/rtsp';

/**
 * Calls the backend RTSP test endpoint.
 */
async function testRtspConnection(request: RTSPTestRequest): Promise<RTSPTestResult> {
  const response = await fetch('/api/cameras/rtsp/test', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json() as Promise<RTSPTestResult>;
}

/**
 * Return type for useRtspTest hook.
 */
export interface UseRtspTestReturn {
  testConnection: ReturnType<typeof useMutation<RTSPTestResult, Error, RTSPTestRequest>>;
}

/**
 * Hook for testing RTSP camera connections.
 *
 * Provides a mutation for testing RTSP URLs without creating a camera.
 * The test is read-only and does not invalidate any queries.
 *
 * @example
 * ```tsx
 * const { testConnection } = useRtspTest();
 *
 * const handleTest = () => {
 *   testConnection.mutate({
 *     rtsp_url: 'rtsp://192.168.1.100:554/stream1',
 *     username: 'admin',
 *     password: '****', // pragma: allowlist secret
 *   });
 * };
 * ```
 */
export function useRtspTest(): UseRtspTestReturn {
  const testConnection = useMutation({
    mutationFn: testRtspConnection,
    // This is a read-only test - we don't want to invalidate any queries
    // since testing a connection doesn't change any camera data
  });

  return { testConnection };
}
