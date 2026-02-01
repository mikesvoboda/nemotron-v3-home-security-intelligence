/**
 * useRtspTest Hook (NEM-4748 Phase 2: Connection Testing)
 *
 * Hook for testing RTSP camera connections before adding them.
 * Uses TanStack Query's useMutation for the test request.
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

import { useMutation } from '@tanstack/react-query';

import type { RTSPTestRequest, RTSPTestResult } from '../types/rtsp';

async function testRtspConnection(request: RTSPTestRequest): Promise<RTSPTestResult> {
  const response = await fetch('/api/cameras/rtsp/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json() as Promise<RTSPTestResult>;
}

export type UseRtspTestReturn = ReturnType<typeof useRtspTest>;

export function useRtspTest() {
  return {
    testConnection: useMutation({
      mutationFn: testRtspConnection,
    }),
  };
}
