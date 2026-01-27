/**
 * useRecordingMutations - TanStack Query mutations for request recordings
 *
 * This hook provides mutations for replay, delete, and clear all operations
 * on recorded API requests.
 *
 * Implements NEM-2721: Request Recording and Replay panel
 *
 * @module hooks/useRecordingMutations
 */

import { useMutation } from '@tanstack/react-query';

import { RECORDINGS_QUERY_KEY } from './useRecordingsQuery';
import {
  replayRecording,
  deleteRecording,
  clearAllRecordings,
  type ReplayResponse,
} from '../services/api';

/**
 * Return type for the useRecordingMutations hook
 */
export interface UseRecordingMutationsReturn {
  /** Mutation for replaying a recorded request */
  replayMutation: ReturnType<typeof useMutation<ReplayResponse, Error, string>>;

  /** Mutation for deleting a single recording */
  deleteMutation: ReturnType<typeof useMutation<{ message: string }, Error, string>>;

  /** Mutation for clearing all recordings */
  clearAllMutation: ReturnType<
    typeof useMutation<{ message: string; deleted_count: number }, Error, void>
  >;

  /** Whether a replay is in progress */
  isReplaying: boolean;

  /** Whether a delete is in progress */
  isDeleting: boolean;

  /** Whether a clear all is in progress */
  isClearing: boolean;

  /** Whether any mutation is in progress */
  isAnyMutating: boolean;
}

/**
 * Hook providing mutations for recording operations.
 *
 * Provides three mutations:
 * - `replayMutation`: Replay a recorded request and get the comparison result
 * - `deleteMutation`: Delete a single recording
 * - `clearAllMutation`: Delete all recordings
 *
 * All mutations automatically invalidate the recordings query on success.
 *
 * @returns Mutations and loading states for recording operations
 *
 * @example
 * ```tsx
 * const {
 *   replayMutation,
 *   deleteMutation,
 *   clearAllMutation,
 *   isReplaying,
 * } = useRecordingMutations();
 *
 * // Replay a recording
 * const handleReplay = (recordingId: string) => {
 *   replayMutation.mutate(recordingId, {
 *     onSuccess: (data) => {
 *       console.log('Replay complete:', data);
 *     },
 *   });
 * };
 *
 * // Delete a recording
 * const handleDelete = (recordingId: string) => {
 *   deleteMutation.mutate(recordingId);
 * };
 *
 * // Clear all recordings
 * const handleClearAll = () => {
 *   if (confirm('Delete all recordings?')) {
 *     clearAllMutation.mutate();
 *   }
 * };
 * ```
 */
export function useRecordingMutations(): UseRecordingMutationsReturn {
  // Replay mutation - executes the recorded request and returns comparison
  const replayMutation = useMutation({
    mutationFn: (recordingId: string) => replayRecording(recordingId),
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate recordings query to refresh the list
      void client.invalidateQueries({ queryKey: RECORDINGS_QUERY_KEY });
    },
  });

  // Delete mutation - removes a single recording
  const deleteMutation = useMutation({
    mutationFn: (recordingId: string) => deleteRecording(recordingId),
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate recordings query to refresh the list
      void client.invalidateQueries({ queryKey: RECORDINGS_QUERY_KEY });
    },
  });

  // Clear all mutation - removes all recordings
  const clearAllMutation = useMutation({
    mutationFn: () => clearAllRecordings(),
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate recordings query to refresh the list
      void client.invalidateQueries({ queryKey: RECORDINGS_QUERY_KEY });
    },
  });

  // Derived loading states
  const isReplaying = replayMutation.isPending;
  const isDeleting = deleteMutation.isPending;
  const isClearing = clearAllMutation.isPending;
  const isAnyMutating = isReplaying || isDeleting || isClearing;

  return {
    replayMutation,
    deleteMutation,
    clearAllMutation,
    isReplaying,
    isDeleting,
    isClearing,
    isAnyMutating,
  };
}
