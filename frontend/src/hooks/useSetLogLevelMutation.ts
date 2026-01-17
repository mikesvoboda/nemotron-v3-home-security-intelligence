/**
 * useSetLogLevelMutation - TanStack Query mutation hook for setting log level
 *
 * This hook provides a mutation to set the log level via POST /api/debug/log-level
 * and automatically invalidates the log level query on success.
 *
 * Features:
 * - Automatic cache invalidation on success
 * - Type-safe log level parameter
 * - Success/error state tracking
 *
 * @module hooks/useSetLogLevelMutation
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { setLogLevel, type SetLogLevelResponse } from '../services/api';
import { queryKeys } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Valid log level values
 */
export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

/**
 * Return type for the useSetLogLevelMutation hook
 */
export interface UseSetLogLevelMutationReturn {
  /** Function to set the log level */
  setLevel: (level: LogLevel) => Promise<SetLogLevelResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Error object if the mutation failed */
  error: Error | null;
  /** Response data from the last successful mutation */
  data: SetLogLevelResponse | undefined;
  /** Function to reset the mutation state */
  reset: () => void;
  /** Whether the last mutation was successful */
  isSuccess: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook providing mutation for setting the log level.
 *
 * This mutation sets the log level via POST /api/debug/log-level
 * and automatically invalidates the log level query on success.
 *
 * Note: Log level changes do not persist on server restart.
 *
 * @returns Mutation functions and state
 *
 * @example
 * ```tsx
 * const { setLevel, isPending, error, isSuccess } = useSetLogLevelMutation();
 *
 * const handleClick = async (level: LogLevel) => {
 *   try {
 *     await setLevel(level);
 *     toast.success(`Log level set to ${level}`);
 *   } catch (err) {
 *     toast.error('Failed to set log level');
 *   }
 * };
 *
 * return (
 *   <button onClick={() => handleClick('DEBUG')} disabled={isPending}>
 *     Set DEBUG
 *   </button>
 * );
 * ```
 */
export function useSetLogLevelMutation(): UseSetLogLevelMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (level: LogLevel) => setLogLevel(level),
    onSuccess: () => {
      // Invalidate log level query to refetch the new value
      void queryClient.invalidateQueries({ queryKey: queryKeys.debug.logLevel });
    },
  });

  return {
    setLevel: (level: LogLevel) => mutation.mutateAsync(level),
    isPending: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
    isSuccess: mutation.isSuccess,
  };
}

export default useSetLogLevelMutation;
