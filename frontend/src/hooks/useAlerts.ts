/**
 * useAlerts - React Query mutation hooks for alert instance management
 *
 * Provides mutations for acknowledging and dismissing alert instances.
 * Works with the alert lifecycle: pending -> delivered -> acknowledged -> dismissed
 *
 * Endpoints:
 * - POST /api/alerts/{alert_id}/acknowledge - Acknowledge an alert
 * - POST /api/alerts/{alert_id}/dismiss - Dismiss an alert
 *
 * @module hooks/useAlerts
 * @see NEM-3647 Alert Instance Management Endpoints
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { acknowledgeAlert, dismissAlert } from '../services/api';
import { queryKeys } from '../services/queryClient';

import type { AlertResponse } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Context for optimistic updates in alert mutations.
 */
export interface AlertMutationContext {
  /** Previous alert data for rollback on error */
  previousAlert?: AlertResponse;
}

/**
 * Options for useAcknowledgeAlert mutation hook.
 */
export interface UseAcknowledgeAlertOptions {
  /**
   * Callback fired when the alert is successfully acknowledged.
   */
  onSuccess?: (data: AlertResponse, alertId: string) => void;
  /**
   * Callback fired when the mutation encounters an error.
   */
  onError?: (error: Error, alertId: string) => void;
  /**
   * Callback fired after mutation completes (success or error).
   */
  onSettled?: (data: AlertResponse | undefined, error: Error | null, alertId: string) => void;
}

/**
 * Return type for useAcknowledgeAlert hook.
 */
export interface UseAcknowledgeAlertReturn {
  /**
   * Acknowledge an alert by ID.
   */
  acknowledgeAlert: (alertId: string) => Promise<AlertResponse>;
  /**
   * Trigger acknowledge mutation (TanStack Query mutate).
   */
  mutate: (alertId: string) => void;
  /**
   * Trigger acknowledge mutation and return a promise (TanStack Query mutateAsync).
   */
  mutateAsync: (alertId: string) => Promise<AlertResponse>;
  /**
   * Whether the mutation is currently in progress.
   */
  isPending: boolean;
  /**
   * Whether the mutation completed successfully.
   */
  isSuccess: boolean;
  /**
   * Whether the mutation encountered an error.
   */
  isError: boolean;
  /**
   * The error object if the mutation failed.
   */
  error: Error | null;
  /**
   * The response data from a successful mutation.
   */
  data: AlertResponse | undefined;
  /**
   * Reset the mutation state.
   */
  reset: () => void;
}

/**
 * Options for useDismissAlert mutation hook.
 */
export interface UseDismissAlertOptions {
  /**
   * Callback fired when the alert is successfully dismissed.
   */
  onSuccess?: (data: AlertResponse, alertId: string) => void;
  /**
   * Callback fired when the mutation encounters an error.
   */
  onError?: (error: Error, alertId: string) => void;
  /**
   * Callback fired after mutation completes (success or error).
   */
  onSettled?: (data: AlertResponse | undefined, error: Error | null, alertId: string) => void;
}

/**
 * Return type for useDismissAlert hook.
 */
export interface UseDismissAlertReturn {
  /**
   * Dismiss an alert by ID.
   */
  dismissAlert: (alertId: string) => Promise<AlertResponse>;
  /**
   * Trigger dismiss mutation (TanStack Query mutate).
   */
  mutate: (alertId: string) => void;
  /**
   * Trigger dismiss mutation and return a promise (TanStack Query mutateAsync).
   */
  mutateAsync: (alertId: string) => Promise<AlertResponse>;
  /**
   * Whether the mutation is currently in progress.
   */
  isPending: boolean;
  /**
   * Whether the mutation completed successfully.
   */
  isSuccess: boolean;
  /**
   * Whether the mutation encountered an error.
   */
  isError: boolean;
  /**
   * The error object if the mutation failed.
   */
  error: Error | null;
  /**
   * The response data from a successful mutation.
   */
  data: AlertResponse | undefined;
  /**
   * Reset the mutation state.
   */
  reset: () => void;
}

/**
 * Combined return type for useAlertMutations hook.
 */
export interface UseAlertMutationsReturn {
  /**
   * Acknowledge mutation result.
   */
  acknowledge: UseAcknowledgeAlertReturn;
  /**
   * Dismiss mutation result.
   */
  dismiss: UseDismissAlertReturn;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Mutation hook for acknowledging an alert.
 *
 * Marks the alert as acknowledged and broadcasts the state change via WebSocket.
 * Only alerts with status PENDING or DELIVERED can be acknowledged.
 *
 * @param options - Optional callbacks for mutation lifecycle
 * @returns Mutation object with acknowledge function and state
 *
 * @example
 * ```tsx
 * function AlertItem({ alertId }: { alertId: string }) {
 *   const { acknowledgeAlert, isPending, isError, error } = useAcknowledgeAlert({
 *     onSuccess: (data) => {
 *       console.log('Alert acknowledged:', data.id, 'Status:', data.status);
 *     },
 *     onError: (err) => {
 *       console.error('Failed to acknowledge:', err.message);
 *     },
 *   });
 *
 *   return (
 *     <button onClick={() => acknowledgeAlert(alertId)} disabled={isPending}>
 *       {isPending ? 'Acknowledging...' : 'Acknowledge'}
 *     </button>
 *   );
 * }
 * ```
 */
export function useAcknowledgeAlert(
  options: UseAcknowledgeAlertOptions = {}
): UseAcknowledgeAlertReturn {
  const { onSuccess, onError, onSettled } = options;
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: acknowledgeAlert,
    onSuccess: (data, alertId) => {
      // Invalidate alerts queries to refresh lists
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all });
      onSuccess?.(data, alertId);
    },
    onError: (error: Error, alertId) => {
      onError?.(error, alertId);
    },
    onSettled: (data, error, alertId) => {
      onSettled?.(data, error, alertId);
    },
  });

  return {
    acknowledgeAlert: mutation.mutateAsync,
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}

/**
 * Mutation hook for dismissing an alert.
 *
 * Marks the alert as dismissed and broadcasts the state change via WebSocket.
 * Only alerts with status PENDING, DELIVERED, or ACKNOWLEDGED can be dismissed.
 *
 * @param options - Optional callbacks for mutation lifecycle
 * @returns Mutation object with dismiss function and state
 *
 * @example
 * ```tsx
 * function AlertItem({ alertId }: { alertId: string }) {
 *   const { dismissAlert, isPending, isError, error } = useDismissAlert({
 *     onSuccess: (data) => {
 *       console.log('Alert dismissed:', data.id, 'Status:', data.status);
 *     },
 *     onError: (err) => {
 *       console.error('Failed to dismiss:', err.message);
 *     },
 *   });
 *
 *   return (
 *     <button onClick={() => dismissAlert(alertId)} disabled={isPending}>
 *       {isPending ? 'Dismissing...' : 'Dismiss'}
 *     </button>
 *   );
 * }
 * ```
 */
export function useDismissAlert(options: UseDismissAlertOptions = {}): UseDismissAlertReturn {
  const { onSuccess, onError, onSettled } = options;
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: dismissAlert,
    onSuccess: (data, alertId) => {
      // Invalidate alerts queries to refresh lists
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all });
      onSuccess?.(data, alertId);
    },
    onError: (error: Error, alertId) => {
      onError?.(error, alertId);
    },
    onSettled: (data, error, alertId) => {
      onSettled?.(data, error, alertId);
    },
  });

  return {
    dismissAlert: mutation.mutateAsync,
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}

/**
 * Combined mutation hooks for alert instance management.
 *
 * Provides both acknowledge and dismiss mutations in a single hook call.
 *
 * @returns Object containing both acknowledge and dismiss mutation results
 *
 * @example
 * ```tsx
 * function AlertActions({ alertId }: { alertId: string }) {
 *   const { acknowledge, dismiss } = useAlertMutations();
 *
 *   const handleAcknowledge = () => {
 *     acknowledge.mutate(alertId);
 *   };
 *
 *   const handleDismiss = () => {
 *     dismiss.mutate(alertId);
 *   };
 *
 *   return (
 *     <div>
 *       <button
 *         onClick={handleAcknowledge}
 *         disabled={acknowledge.isPending}
 *       >
 *         Acknowledge
 *       </button>
 *       <button
 *         onClick={handleDismiss}
 *         disabled={dismiss.isPending}
 *       >
 *         Dismiss
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 */
export function useAlertMutations(): UseAlertMutationsReturn {
  const acknowledge = useAcknowledgeAlert();
  const dismiss = useDismissAlert();

  return {
    acknowledge,
    dismiss,
  };
}

export default useAlertMutations;
