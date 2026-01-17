/**
 * RecordingReplayPanel - Main panel for request recording and replay functionality
 *
 * Provides a complete UI for viewing, filtering, replaying, and managing recorded
 * API requests. Integrates with the DeveloperToolsPage.
 *
 * Implements NEM-2721: Request Recording and Replay panel
 */

import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { Trash2, RefreshCw, AlertCircle, Loader2 } from 'lucide-react';
import { useState, useCallback } from 'react';

import RecordingDetailModal from './RecordingDetailModal';
import RecordingsList from './RecordingsList';
import ReplayResultsModal from './ReplayResultsModal';
import { useRecordingMutations } from '../../hooks/useRecordingMutations';
import { useRecordingsQuery, RECORDINGS_QUERY_KEY } from '../../hooks/useRecordingsQuery';
import { fetchRecordingDetail, type ReplayResponse } from '../../services/api';

export interface RecordingReplayPanelProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * RecordingReplayPanel provides the main interface for managing and replaying
 * recorded API requests.
 */
export default function RecordingReplayPanel({ className = '' }: RecordingReplayPanelProps) {
  // Query for recordings list
  const {
    recordings,
    totalCount,
    isEmpty,
    isLoading: isLoadingRecordings,
    error: recordingsError,
    refetch: refetchRecordings,
  } = useRecordingsQuery({ refetchInterval: false });

  // Mutations
  const {
    replayMutation,
    deleteMutation,
    clearAllMutation,
    isReplaying,
    isDeleting,
    isClearing,
  } = useRecordingMutations();

  // Modal state
  const [selectedRecordingId, setSelectedRecordingId] = useState<string | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isReplayResultsModalOpen, setIsReplayResultsModalOpen] = useState(false);
  const [replayResult, setReplayResult] = useState<ReplayResponse | null>(null);

  // Query for selected recording detail
  const {
    data: recordingDetail,
    isLoading: isLoadingDetail,
    error: detailError,
  } = useQuery({
    queryKey: [...RECORDINGS_QUERY_KEY, selectedRecordingId, 'detail'],
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    queryFn: () => fetchRecordingDetail(selectedRecordingId!),
    enabled: !!selectedRecordingId && isDetailModalOpen,
  });

  // Handle view recording
  const handleView = useCallback((recordingId: string) => {
    setSelectedRecordingId(recordingId);
    setIsDetailModalOpen(true);
  }, []);

  // Handle close detail modal
  const handleCloseDetailModal = useCallback(() => {
    setIsDetailModalOpen(false);
    setSelectedRecordingId(null);
  }, []);

  // Handle replay recording
  const handleReplay = useCallback((recordingId: string) => {
    replayMutation.mutate(recordingId, {
      onSuccess: (data) => {
        setReplayResult(data);
        setIsReplayResultsModalOpen(true);
      },
    });
  }, [replayMutation]);

  // Handle close replay results modal
  const handleCloseReplayResultsModal = useCallback(() => {
    setIsReplayResultsModalOpen(false);
    setReplayResult(null);
  }, []);

  // Handle delete recording
  const handleDelete = useCallback((recordingId: string) => {
    if (window.confirm(`Delete recording ${recordingId}? This action cannot be undone.`)) {
      deleteMutation.mutate(recordingId);
    }
  }, [deleteMutation]);

  // Handle clear all recordings
  const handleClearAll = useCallback(() => {
    if (window.confirm(`Delete all ${totalCount} recordings? This action cannot be undone.`)) {
      clearAllMutation.mutate();
    }
  }, [clearAllMutation, totalCount]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    void refetchRecordings();
  }, [refetchRecordings]);

  return (
    <div className={clsx('space-y-6', className)} data-testid="recording-replay-panel">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">Request Recordings</h2>
          <p className="mt-1 text-sm text-gray-400">
            View, replay, and manage recorded API requests for debugging
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={isLoadingRecordings}
            className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white transition-colors hover:border-[#76B900] hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="Refresh recordings"
          >
            <RefreshCw className={clsx('h-4 w-4', isLoadingRecordings && 'animate-spin')} />
            Refresh
          </button>

          {/* Clear all button */}
          <button
            onClick={handleClearAll}
            disabled={isEmpty || isClearing || isReplaying || isDeleting}
            className="flex items-center gap-2 rounded-md border border-red-900/50 bg-red-950/20 px-3 py-2 text-sm text-red-400 transition-colors hover:border-red-500 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Clear all recordings"
          >
            {isClearing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            Clear All
          </button>
        </div>
      </div>

      {/* Loading state */}
      {isLoadingRecordings && (
        <div className="flex items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <span className="ml-3 text-gray-400">Loading recordings...</span>
        </div>
      )}

      {/* Error state */}
      {recordingsError && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-400" />
            <div>
              <p className="font-medium text-red-400">Failed to load recordings</p>
              <p className="text-sm text-red-400/80">{recordingsError.message}</p>
            </div>
            <button
              onClick={handleRefresh}
              className="ml-auto rounded-md border border-red-900/50 px-3 py-1 text-sm text-red-400 hover:bg-red-900/20"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Recordings list */}
      {!isLoadingRecordings && !recordingsError && (
        <RecordingsList
          recordings={recordings}
          onView={handleView}
          onReplay={handleReplay}
          onDelete={handleDelete}
          isReplaying={isReplaying}
          isDeleting={isDeleting}
        />
      )}

      {/* Recording count */}
      {!isEmpty && !isLoadingRecordings && !recordingsError && (
        <div className="text-sm text-gray-400">
          Total: {totalCount} recording{totalCount !== 1 ? 's' : ''}
        </div>
      )}

      {/* Recording Detail Modal */}
      <RecordingDetailModal
        isOpen={isDetailModalOpen}
        onClose={handleCloseDetailModal}
        recording={recordingDetail ?? null}
        isLoading={isLoadingDetail}
        error={detailError}
      />

      {/* Replay Results Modal */}
      <ReplayResultsModal
        isOpen={isReplayResultsModalOpen}
        onClose={handleCloseReplayResultsModal}
        result={replayResult}
      />
    </div>
  );
}
