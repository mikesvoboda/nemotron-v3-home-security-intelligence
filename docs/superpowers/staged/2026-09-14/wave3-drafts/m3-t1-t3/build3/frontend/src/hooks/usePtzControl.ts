/**
 * usePtzControl Hook (NEM-4885)
 *
 * Hook for PTZ camera control operations.
 * Uses TanStack Query mutations for PTZ commands.
 *
 * @example
 * ```tsx
 * const { executeCommand, stopMovement } = usePtzControl(cameraId);
 *
 * // Pan right
 * executeCommand.mutate({ command: 'pan', value: 1.0 });
 *
 * // Stop all movement
 * stopMovement.mutate();
 * ```
 */

import { useMutation } from '@tanstack/react-query';

import { executePtzCommand } from '../services/ptzApi';
import { PTZ_DIRECTION_MAP } from '../types/ptz';

import type { PTZCommandRequest, PTZDirection } from '../types/ptz';

export type UsePtzControlReturn = ReturnType<typeof usePtzControl>;

export function usePtzControl(cameraId: string) {
  const executeCommand = useMutation({
    mutationFn: (command: PTZCommandRequest) => executePtzCommand(cameraId, command),
  });

  const stopMovement = useMutation({
    mutationFn: () => executePtzCommand(cameraId, { command: 'stop', value: 0 }),
  });

  const moveDirection = useMutation({
    mutationFn: (direction: PTZDirection) => {
      const command = PTZ_DIRECTION_MAP[direction];
      return executePtzCommand(cameraId, command);
    },
  });

  return {
    executeCommand,
    stopMovement,
    moveDirection,
    isMoving: executeCommand.isPending || moveDirection.isPending,
  };
}
