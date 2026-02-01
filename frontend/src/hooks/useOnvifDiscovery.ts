/**
 * useOnvifDiscovery Hook (NEM-4754 Phase 3: ONVIF Discovery)
 *
 * Hook for discovering ONVIF cameras on the network.
 * Uses TanStack Query's useMutation for the discovery request.
 *
 * @example
 * ```tsx
 * const { discoverDevices } = useOnvifDiscovery();
 *
 * const handleDiscover = () => {
 *   discoverDevices.mutate({
 *     subnet: '192.168.1.0/24',
 *     timeout: 10,
 *   });
 * };
 *
 * // Access results
 * if (discoverDevices.data) {
 *   console.log(`Found ${discoverDevices.data.count} devices`);
 *   discoverDevices.data.devices.forEach(device => {
 *     console.log(device.manufacturer, device.model, device.ip);
 *   });
 * }
 * ```
 */

import { useMutation } from '@tanstack/react-query';

import type { OnvifDiscoveryRequest, OnvifDiscoveryResponse } from '../types/onvif';

async function discoverOnvifDevices(
  request: OnvifDiscoveryRequest
): Promise<OnvifDiscoveryResponse> {
  const response = await fetch('/api/cameras/onvif/discover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(errorData.detail ?? `HTTP error! status: ${response.status}`);
  }

  return response.json() as Promise<OnvifDiscoveryResponse>;
}

export type UseOnvifDiscoveryReturn = ReturnType<typeof useOnvifDiscovery>;

export function useOnvifDiscovery() {
  return {
    discoverDevices: useMutation({
      mutationFn: discoverOnvifDevices,
    }),
  };
}
