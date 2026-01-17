/**
 * useServiceMutations - React Query mutations for service control operations
 *
 * Provides mutations for the ServicesPanel to control services:
 * - Restart a running service
 * - Start a stopped service
 * - Stop/disable a running service
 * - Enable a disabled service
 *
 * Endpoints:
 * - POST /api/system/services/{name}/restart - Restart a service
 * - POST /api/system/services/{name}/start - Start a stopped service
 * - POST /api/system/services/{name}/disable - Stop/disable a service
 * - POST /api/system/services/{name}/enable - Enable a disabled service
 *
 * @module hooks/useServiceMutations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  restartService as restartServiceApi,
  startService as startServiceApi,
  stopService as stopServiceApi,
  enableService as enableServiceApi,
  type ServiceActionResponse,
} from '../services/api';
import { queryKeys } from '../services/queryClient';

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Mutation hook for restarting a service
 *
 * Restarts a running service. The service will go through a restart cycle
 * and its status will be broadcast via WebSocket when complete.
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useRestartServiceMutation();
 *
 * const handleRestart = () => {
 *   mutate('rtdetr', {
 *     onSuccess: () => toast.success('Service restarting...'),
 *     onError: (error) => toast.error(error.message),
 *   });
 * };
 * ```
 */
export function useRestartServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: restartServiceApi,
    onSuccess: () => {
      // Invalidate health queries to refresh service status
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

/**
 * Mutation hook for starting a stopped service
 *
 * Starts a service that was previously stopped. Will fail if the service
 * is already running or is disabled.
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useStartServiceMutation();
 *
 * const handleStart = () => {
 *   mutate('rtdetr', {
 *     onSuccess: () => toast.success('Service starting...'),
 *     onError: (error) => toast.error(error.message),
 *   });
 * };
 * ```
 */
export function useStartServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: startServiceApi,
    onSuccess: () => {
      // Invalidate health queries to refresh service status
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

/**
 * Mutation hook for stopping/disabling a service
 *
 * Stops a running service and disables auto-restart. This maps to the
 * backend's disable endpoint. Use enableService to re-enable.
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useStopServiceMutation();
 *
 * const handleStop = () => {
 *   mutate('rtdetr', {
 *     onSuccess: () => toast.success('Service stopped'),
 *     onError: (error) => toast.error(error.message),
 *   });
 * };
 * ```
 */
export function useStopServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: stopServiceApi,
    onSuccess: () => {
      // Invalidate health queries to refresh service status
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

/**
 * Mutation hook for enabling a disabled service
 *
 * Re-enables a service that was previously disabled. The service will
 * be started automatically if it's not running.
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useEnableServiceMutation();
 *
 * const handleEnable = () => {
 *   mutate('rtdetr', {
 *     onSuccess: () => toast.success('Service enabled'),
 *     onError: (error) => toast.error(error.message),
 *   });
 * };
 * ```
 */
export function useEnableServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: enableServiceApi,
    onSuccess: () => {
      // Invalidate health queries to refresh service status
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

// ============================================================================
// Combined Hook
// ============================================================================

/**
 * Combined hook returning all service mutations
 *
 * Provides a convenient way to access all service mutation hooks in one call.
 *
 * @example
 * ```tsx
 * const { restartService, startService, stopService, enableService } = useServiceMutations();
 *
 * // Restart a service
 * restartService.mutate('rtdetr');
 *
 * // Start a stopped service
 * startService.mutate('nemotron');
 *
 * // Stop/disable a service
 * stopService.mutate('redis');
 *
 * // Enable a disabled service
 * enableService.mutate('redis');
 * ```
 */
export function useServiceMutations() {
  const restartService = useRestartServiceMutation();
  const startService = useStartServiceMutation();
  const stopService = useStopServiceMutation();
  const enableService = useEnableServiceMutation();

  return {
    restartService,
    startService,
    stopService,
    enableService,
  };
}

// Re-export types for convenience
export type { ServiceActionResponse };
