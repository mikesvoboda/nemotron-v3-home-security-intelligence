/**
 * usePresets Hook (NEM-4885)
 *
 * Hook for PTZ preset management.
 * Uses TanStack Query for fetching presets and navigating to them.
 *
 * @example
 * ```tsx
 * const { presets, gotoPreset, isLoading } = usePresets(cameraId);
 *
 * // Navigate to a preset
 * gotoPreset.mutate('preset_1');
 *
 * // Render preset list
 * presets?.presets.map(preset => (
 *   <button onClick={() => gotoPreset.mutate(preset.token)}>
 *     {preset.name}
 *   </button>
 * ));
 * ```
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getPtzPresets, gotoPtzPreset } from '../services/ptzApi';

export type UsePresetsReturn = ReturnType<typeof usePresets>;

export function usePresets(cameraId: string, enabled = true) {
  const queryClient = useQueryClient();

  const presetsQuery = useQuery({
    queryKey: ['ptzPresets', cameraId],
    queryFn: () => getPtzPresets(cameraId),
    enabled: enabled && !!cameraId,
    staleTime: 30_000, // 30 seconds
  });

  const gotoPreset = useMutation({
    mutationFn: (presetToken: string) => gotoPtzPreset(cameraId, presetToken),
  });

  const refetchPresets = () => {
    void queryClient.invalidateQueries({ queryKey: ['ptzPresets', cameraId] });
  };

  return {
    presets: presetsQuery.data,
    isLoading: presetsQuery.isLoading,
    isError: presetsQuery.isError,
    error: presetsQuery.error,
    gotoPreset,
    refetchPresets,
  };
}
