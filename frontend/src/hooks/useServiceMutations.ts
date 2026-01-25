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
 * Implements optimistic updates for instant UI feedback.
 *
 * @module hooks/useServiceMutations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  restartService as restartServiceApi,
  startService as startServiceApi,
  stopService as stopServiceApi,
  enableService as enableServiceApi,
  type HealthResponse,
} from '../services/api';
import { queryKeys } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Context for optimistic update rollback
 */
interface ServiceOptimisticContext {
  previousHealth: HealthResponse | undefined;
}

/**
 * Helper to update a service status optimistically in the health response.
 */
function updateServiceStatus(
  health: HealthResponse | undefined,
  serviceName: string,
  status: string
): HealthResponse | undefined {
  if (!health?.services) return health;

  return {
    ...health,
    services: Object.fromEntries(
      Object.entries(health.services).map(([name, service]) => [
        name,
        name === serviceName ? { ...service, status, message: `Service ${status}...` } : service,
      ])
    ),
  };
}

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Mutation hook for restarting a service with optimistic update.
 */
export function useRestartServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: restartServiceApi,

    onMutate: async (serviceName: string): Promise<ServiceOptimisticContext> => {
      await queryClient.cancelQueries({ queryKey: queryKeys.system.health });

      const previousHealth = queryClient.getQueryData<HealthResponse>(queryKeys.system.health);

      queryClient.setQueryData<HealthResponse>(queryKeys.system.health, (old) =>
        updateServiceStatus(old, serviceName, 'restarting')
      );

      return { previousHealth };
    },

    onError: (
      _error: Error,
      _serviceName: string,
      context: ServiceOptimisticContext | undefined
    ) => {
      if (context?.previousHealth) {
        queryClient.setQueryData(queryKeys.system.health, context.previousHealth);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

/**
 * Mutation hook for starting a stopped service with optimistic update.
 */
export function useStartServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: startServiceApi,

    onMutate: async (serviceName: string): Promise<ServiceOptimisticContext> => {
      await queryClient.cancelQueries({ queryKey: queryKeys.system.health });

      const previousHealth = queryClient.getQueryData<HealthResponse>(queryKeys.system.health);

      queryClient.setQueryData<HealthResponse>(queryKeys.system.health, (old) =>
        updateServiceStatus(old, serviceName, 'starting')
      );

      return { previousHealth };
    },

    onError: (
      _error: Error,
      _serviceName: string,
      context: ServiceOptimisticContext | undefined
    ) => {
      if (context?.previousHealth) {
        queryClient.setQueryData(queryKeys.system.health, context.previousHealth);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

/**
 * Mutation hook for stopping/disabling a service with optimistic update.
 */
export function useStopServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: stopServiceApi,

    onMutate: async (serviceName: string): Promise<ServiceOptimisticContext> => {
      await queryClient.cancelQueries({ queryKey: queryKeys.system.health });

      const previousHealth = queryClient.getQueryData<HealthResponse>(queryKeys.system.health);

      queryClient.setQueryData<HealthResponse>(queryKeys.system.health, (old) =>
        updateServiceStatus(old, serviceName, 'stopping')
      );

      return { previousHealth };
    },

    onError: (
      _error: Error,
      _serviceName: string,
      context: ServiceOptimisticContext | undefined
    ) => {
      if (context?.previousHealth) {
        queryClient.setQueryData(queryKeys.system.health, context.previousHealth);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

/**
 * Mutation hook for enabling a disabled service with optimistic update.
 */
export function useEnableServiceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: enableServiceApi,

    onMutate: async (serviceName: string): Promise<ServiceOptimisticContext> => {
      await queryClient.cancelQueries({ queryKey: queryKeys.system.health });

      const previousHealth = queryClient.getQueryData<HealthResponse>(queryKeys.system.health);

      queryClient.setQueryData<HealthResponse>(queryKeys.system.health, (old) =>
        updateServiceStatus(old, serviceName, 'starting')
      );

      return { previousHealth };
    },

    onError: (
      _error: Error,
      _serviceName: string,
      context: ServiceOptimisticContext | undefined
    ) => {
      if (context?.previousHealth) {
        queryClient.setQueryData(queryKeys.system.health, context.previousHealth);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.health });
    },
  });
}

// ============================================================================
// Combined Hook
// ============================================================================

/**
 * Combined hook providing all service mutation functions.
 *
 * @example
 * ```tsx
 * const { restartService, startService, stopService, enableService } = useServiceMutations();
 *
 * // Restart a service
 * restartService.mutate('rtdetr');
 *
 * // Check if any mutation is pending
 * const isPending = restartService.isPending || startService.isPending;
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

export default useServiceMutations;
