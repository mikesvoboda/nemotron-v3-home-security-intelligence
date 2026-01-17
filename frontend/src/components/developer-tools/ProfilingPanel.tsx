/**
 * ProfilingPanel Component
 *
 * Performance profiling panel for the Developer Tools page.
 * Provides controls for starting/stopping profiling and displays results.
 *
 * Features:
 * - Status display (Idle or Profiling with elapsed time)
 * - Start/Stop profiling buttons
 * - Results table with top functions by CPU time
 * - Download button for .prof file
 * - Loading states during operations
 * - Error handling for failed operations
 */

import { Card, Title, Text, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { Activity, Download, Play, Square, AlertCircle, Loader2 } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { useProfileQuery } from '../../hooks/useProfileQuery';
import {
  useStartProfilingMutation,
  useStopProfilingMutation,
  useDownloadProfileMutation,
} from '../../hooks/useProfilingMutations';
import { useToast } from '../../hooks/useToast';

import type { ProfileResults, ProfileFunctionStats } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

export interface ProfilingPanelProps {
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Loading spinner component
 */
function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-8" data-testid="profiling-panel-loading">
      <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
    </div>
  );
}

/**
 * Error display component
 */
function ErrorDisplay({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-red-900/20 p-3 text-red-400">
      <AlertCircle className="h-5 w-5 flex-shrink-0" />
      <Text className="text-red-400">{message}</Text>
    </div>
  );
}

/**
 * Status indicator component
 */
function StatusIndicator({
  isProfiling,
  elapsedSeconds,
}: {
  isProfiling: boolean;
  elapsedSeconds: number | null;
}) {
  return (
    <div className="flex items-center gap-3" data-testid="profiling-status">
      <div
        className={clsx(
          'h-3 w-3 rounded-full',
          isProfiling ? 'animate-pulse bg-[#76B900]' : 'bg-gray-500'
        )}
      />
      <Text className="font-medium text-gray-200">
        {isProfiling ? (
          <>
            Profiling...{' '}
            <span className="text-[#76B900]">({elapsedSeconds ?? 0}s elapsed)</span>
          </>
        ) : (
          'Idle'
        )}
      </Text>
    </div>
  );
}

/**
 * Results table component
 */
function ResultsTable({ results }: { results: ProfileResults }) {
  return (
    <div className="mt-4">
      <Text className="mb-2 font-medium text-gray-300">Top Functions by CPU Time</Text>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" role="table">
          <thead>
            <tr className="border-b border-gray-700 text-left text-gray-400">
              <th className="pb-2 pr-4">Function</th>
              <th className="pb-2 pr-4 text-right">Calls</th>
              <th className="pb-2 pr-4 text-right">Time (s)</th>
              <th className="pb-2 pr-4">CPU %</th>
            </tr>
          </thead>
          <tbody>
            {results.top_functions.map((fn: ProfileFunctionStats, index: number) => (
              <tr key={index} className="border-b border-gray-800">
                <td className="py-2 pr-4 font-mono text-gray-200">{fn.function_name}</td>
                <td className="py-2 pr-4 text-right text-gray-300">{fn.call_count}</td>
                <td className="py-2 pr-4 text-right text-gray-300">{fn.total_time.toFixed(3)}</td>
                <td className="py-2 pr-4">
                  <div className="flex items-center gap-2">
                    <div className="w-24">
                      <ProgressBar
                        value={fn.percentage}
                        color="green"
                        className="h-2"
                        aria-valuenow={fn.percentage}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      />
                    </div>
                    <span className="text-gray-300">{fn.percentage.toFixed(1)}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Text className="mt-2 text-xs text-gray-500">
        Total profiling time: {results.total_time.toFixed(2)}s
      </Text>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ProfilingPanel - Performance profiling controls and results display
 *
 * Usage:
 * ```tsx
 * <ProfilingPanel />
 * ```
 */
export default function ProfilingPanel({ className }: ProfilingPanelProps) {
  const { success, error: showError } = useToast();

  // Local state for elapsed time counter during profiling
  const [localElapsed, setLocalElapsed] = useState<number>(0);

  // Local state to track if we should poll (set after starting profiling)
  const [shouldPoll, setShouldPoll] = useState<boolean>(false);

  // Query for profile status
  const {
    isLoading,
    isProfiling,
    elapsedSeconds,
    results,
    error: queryError,
    refetch,
  } = useProfileQuery({
    // Poll every second while profiling
    refetchInterval: shouldPoll ? 1000 : false,
  });

  // Sync shouldPoll with isProfiling
  useEffect(() => {
    setShouldPoll(isProfiling);
  }, [isProfiling]);

  // Mutations
  const { start, isPending: isStarting, error: startError } = useStartProfilingMutation();

  const { stop, isPending: isStopping, error: stopError } = useStopProfilingMutation();

  const { download, isPending: isDownloading, error: downloadError } = useDownloadProfileMutation();

  // Update local elapsed counter when profiling
  useEffect(() => {
    if (isProfiling) {
      setLocalElapsed(elapsedSeconds ?? 0);

      const interval = setInterval(() => {
        setLocalElapsed((prev) => prev + 1);
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [isProfiling, elapsedSeconds]);

  // Handle start profiling
  const handleStart = useCallback(async () => {
    try {
      await start();
      setLocalElapsed(0);
      success('Profiling started');
    } catch {
      showError('Failed to start profiling');
    }
  }, [start, success, showError]);

  // Handle stop profiling
  const handleStop = useCallback(async () => {
    try {
      await stop();
      success('Profiling stopped');
      // Refetch to get the latest results
      await refetch();
    } catch {
      showError('Failed to stop profiling');
    }
  }, [stop, success, showError, refetch]);

  // Handle download
  const handleDownload = useCallback(async () => {
    try {
      const blob = await download();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'profile.prof';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      success('Profile downloaded');
    } catch {
      showError('Failed to download profile');
    }
  }, [download, success, showError]);

  // Collect all errors
  const errorMessage =
    queryError?.message || startError?.message || stopError?.message || downloadError?.message;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="profiling-panel"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Activity className="h-5 w-5 text-[#76B900]" />
        Performance Profiling
      </Title>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="space-y-4">
          {/* Status and Controls */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <StatusIndicator
              isProfiling={isProfiling}
              elapsedSeconds={isProfiling ? localElapsed : elapsedSeconds}
            />

            <div className="flex gap-2">
              {!isProfiling ? (
                <button
                  onClick={() => void handleStart()}
                  disabled={isStarting}
                  className={clsx(
                    'flex items-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors',
                    isStarting
                      ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                      : 'bg-[#76B900] text-white hover:bg-[#8ACE00]'
                  )}
                >
                  {isStarting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  {isStarting ? 'Starting...' : 'Start Profiling'}
                </button>
              ) : (
                <button
                  onClick={() => void handleStop()}
                  disabled={isStopping}
                  className={clsx(
                    'flex items-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors',
                    isStopping
                      ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                      : 'bg-red-700 text-white hover:bg-red-800'
                  )}
                >
                  {isStopping ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Square className="h-4 w-4" />
                  )}
                  {isStopping ? 'Stopping...' : 'Stop Profiling'}
                </button>
              )}
            </div>
          </div>

          {/* Error Display */}
          {errorMessage && <ErrorDisplay message={errorMessage} />}

          {/* Results */}
          {results && !isProfiling && (
            <>
              <ResultsTable results={results} />

              {/* Download Button */}
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => void handleDownload()}
                  disabled={isDownloading}
                  className={clsx(
                    'flex items-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors',
                    isDownloading
                      ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                      : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                  )}
                >
                  {isDownloading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Download Profile (.prof)
                </button>
              </div>
            </>
          )}

          {/* Empty state when no results */}
          {!results && !isProfiling && (
            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 text-center">
              <Activity className="mx-auto h-10 w-10 text-gray-500" />
              <Text className="mt-2 text-gray-400">Start profiling to analyze CPU performance</Text>
              <Text className="mt-1 text-xs text-gray-500">
                Profile data will be collected until you stop profiling
              </Text>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
