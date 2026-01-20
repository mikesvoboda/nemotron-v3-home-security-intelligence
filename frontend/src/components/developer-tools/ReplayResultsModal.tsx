/**
 * ReplayResultsModal - Display results of replaying a recorded API request
 *
 * Shows comparison between original and replay results including status codes,
 * durations, and response bodies with difference highlighting.
 *
 * Implements NEM-2721: Request Recording and Replay panel
 */

import { clsx } from 'clsx';
import { X, CheckCircle, AlertTriangle, XCircle, FileX } from 'lucide-react';

import ResponsiveModal from '../common/ResponsiveModal';

import type { ReplayResponse } from '../../services/api';

export interface ReplayResultsModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Replay result to display */
  result: ReplayResponse | null;
}

/**
 * Format JSON for display
 */
function formatJson(data: unknown): string {
  if (data === null || data === undefined) {
    return 'null';
  }
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    // Fallback for non-serializable data
    if (typeof data === 'object') {
      return '[Object]';
    }
    // For primitives, use JSON.stringify to avoid base-to-string issues
    return JSON.stringify(data);
  }
}

/**
 * Get color classes for status code badge
 */
function getStatusCodeClasses(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) {
    return 'bg-green-500/10 text-green-400 border-green-500/20';
  } else if (statusCode >= 400 && statusCode < 500) {
    return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
  } else if (statusCode >= 500) {
    return 'bg-red-500/10 text-red-400 border-red-500/20';
  }
  return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
}

/**
 * Get color classes for HTTP method badge
 */
function getMethodBadgeClasses(method: string): string {
  switch (method.toUpperCase()) {
    case 'GET':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    case 'POST':
      return 'bg-green-500/10 text-green-400 border-green-500/20';
    case 'PUT':
    case 'PATCH':
      return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
    case 'DELETE':
      return 'bg-red-500/10 text-red-400 border-red-500/20';
    default:
      return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  }
}

/**
 * Determine if status codes match
 */
function statusCodesMatch(original: number, replay: number): boolean {
  return original === replay;
}

/**
 * Get comparison result type
 */
function getComparisonType(original: number, replay: number): 'success' | 'warning' | 'error' {
  if (original === replay) return 'success';
  if (replay >= 500) return 'error';
  return 'warning';
}

/**
 * ReplayResultsModal displays the comparison between original and replayed request results.
 */
export default function ReplayResultsModal({
  isOpen,
  onClose,
  result,
}: ReplayResultsModalProps) {
  // No result state
  if (!result) {
    return (
      <ResponsiveModal
        isOpen={isOpen}
        onClose={onClose}
        size="lg"
        variant="slideUp"
        mobileHeight="half"
        title="Replay Results"
        aria-labelledby="replay-results-title"
      >
        <div className="p-6">
          <div className="mb-6 flex items-start justify-between">
            <h2 id="replay-results-title" className="text-lg font-semibold text-white">
              Replay Results
            </h2>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="flex flex-col items-center justify-center py-12">
            <FileX className="h-12 w-12 text-gray-500" />
            <p className="mt-4 text-gray-400">No replay results available</p>
          </div>
        </div>
      </ResponsiveModal>
    );
  }

  const statusMatch = statusCodesMatch(result.original_status_code, result.replay_status_code);
  const comparisonType = getComparisonType(result.original_status_code, result.replay_status_code);

  // Extract metadata
  const metadata = result.replay_metadata as {
    original_timestamp?: string;
    original_path?: string;
    original_method?: string;
    replay_duration_ms?: number;
    replayed_at?: string;
  };

  return (
    <ResponsiveModal
      isOpen={isOpen}
      onClose={onClose}
      size="xl"
      variant="slideUp"
      mobileHeight="full"
      title="Replay Results"
      aria-labelledby="replay-results-title"
    >
      <div className="max-h-[80vh] overflow-y-auto p-6">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h2 id="replay-results-title" className="text-lg font-semibold text-white">
              Replay Results
            </h2>
            <p className="mt-1 text-sm text-gray-400">
              Recording ID: <span className="font-mono">{result.recording_id}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Request info */}
        <div className="mb-6 flex flex-wrap items-center gap-4">
          {metadata.original_method && (
            <span
              className={clsx(
                'inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold',
                getMethodBadgeClasses(metadata.original_method)
              )}
            >
              {metadata.original_method}
            </span>
          )}
          {metadata.original_path && (
            <span className="font-mono text-white">{metadata.original_path}</span>
          )}
        </div>

        {/* Status comparison */}
        <div
          data-testid="status-comparison"
          className={clsx(
            'mb-6 rounded-lg border p-4',
            comparisonType === 'success' && 'border-green-500/20 bg-green-500/5',
            comparisonType === 'warning' && 'border-yellow-500/20 bg-yellow-500/5',
            comparisonType === 'error' && 'border-red-500/20 bg-red-500/5'
          )}
        >
          <div className="flex items-center gap-3">
            {comparisonType === 'success' && (
              <CheckCircle className="h-5 w-5 text-green-400" />
            )}
            {comparisonType === 'warning' && (
              <AlertTriangle className="h-5 w-5 text-yellow-400" />
            )}
            {comparisonType === 'error' && (
              <XCircle className="h-5 w-5 text-red-400" />
            )}
            <div>
              <p
                className={clsx(
                  'font-medium',
                  comparisonType === 'success' && 'text-green-400',
                  comparisonType === 'warning' && 'text-yellow-400',
                  comparisonType === 'error' && 'text-red-400'
                )}
              >
                {statusMatch ? 'Status codes match' : 'Status codes differ'}
              </p>
              <div className="mt-2 flex items-center gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Original: </span>
                  <span
                    className={clsx(
                      'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
                      getStatusCodeClasses(result.original_status_code)
                    )}
                  >
                    {result.original_status_code}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Replay: </span>
                  <span
                    className={clsx(
                      'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold',
                      getStatusCodeClasses(result.replay_status_code)
                    )}
                  >
                    {result.replay_status_code}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Duration */}
        {metadata.replay_duration_ms !== undefined && (
          <div className="mb-6">
            <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-400">
              Replay Duration
            </h3>
            <p className="text-lg font-mono text-white">
              {metadata.replay_duration_ms.toFixed(2)} ms
            </p>
          </div>
        )}

        {/* Replay response */}
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-400">
            Replay Response
          </h3>
          <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1A1A1A] p-4">
            <pre className="font-mono text-sm text-gray-300">
              {formatJson(result.replay_response)}
            </pre>
          </div>
        </div>

        {/* Timestamps */}
        <div className="border-t border-gray-800 pt-4">
          <p className="text-xs text-gray-500">
            {metadata.original_timestamp && (
              <>Original timestamp: {new Date(metadata.original_timestamp).toLocaleString()}</>
            )}
            {metadata.replayed_at && (
              <> | Replayed at: {new Date(metadata.replayed_at).toLocaleString()}</>
            )}
          </p>
        </div>
      </div>
    </ResponsiveModal>
  );
}
