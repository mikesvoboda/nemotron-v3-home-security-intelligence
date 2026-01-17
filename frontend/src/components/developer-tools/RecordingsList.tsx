/**
 * RecordingsList - Display recorded API requests in a filterable table
 *
 * Shows a list of recorded requests with method, path, status, duration,
 * and action buttons (View, Replay, Delete).
 *
 * Implements NEM-2721: Request Recording and Replay panel
 */

import { clsx } from 'clsx';
import { Eye, Play, Trash2, FileX } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { RecordingResponse } from '../../services/api';

export interface RecordingsListProps {
  /** List of recordings to display */
  recordings: RecordingResponse[];
  /** Callback when View button is clicked */
  onView: (recordingId: string) => void;
  /** Callback when Replay button is clicked */
  onReplay: (recordingId: string) => void;
  /** Callback when Delete button is clicked */
  onDelete: (recordingId: string) => void;
  /** Whether a replay operation is in progress */
  isReplaying: boolean;
  /** Whether a delete operation is in progress */
  isDeleting: boolean;
  /** Additional CSS classes */
  className?: string;
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
 * Format timestamp for display
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Format duration in milliseconds
 */
function formatDuration(durationMs: number): string {
  return `${durationMs.toFixed(2)} ms`;
}

/**
 * RecordingsList displays a table of recorded API requests with filtering and actions.
 */
export default function RecordingsList({
  recordings,
  onView,
  onReplay,
  onDelete,
  isReplaying,
  isDeleting,
  className = '',
}: RecordingsListProps) {
  // Filter state
  const [methodFilter, setMethodFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [pathSearch, setPathSearch] = useState<string>('');

  // Filter recordings
  const filteredRecordings = useMemo(() => {
    return recordings.filter((recording) => {
      // Method filter
      if (methodFilter !== 'all' && recording.method.toUpperCase() !== methodFilter) {
        return false;
      }

      // Status filter
      if (statusFilter !== 'all') {
        const status = recording.status_code;
        if (statusFilter === '2xx' && (status < 200 || status >= 300)) return false;
        if (statusFilter === '4xx' && (status < 400 || status >= 500)) return false;
        if (statusFilter === '5xx' && status < 500) return false;
      }

      // Path search
      if (pathSearch && !recording.path.toLowerCase().includes(pathSearch.toLowerCase())) {
        return false;
      }

      return true;
    });
  }, [recordings, methodFilter, statusFilter, pathSearch]);

  // Get unique methods for filter dropdown
  const uniqueMethods = useMemo(() => {
    return [...new Set(recordings.map((r) => r.method.toUpperCase()))].sort();
  }, [recordings]);

  // Empty state
  if (recordings.length === 0) {
    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1F1F1F] p-8', className)}>
        <div className="flex flex-col items-center justify-center text-center">
          <div className="mb-4 rounded-full bg-gray-800 p-4">
            <FileX className="h-8 w-8 text-gray-400" />
          </div>
          <h3 className="mb-2 text-lg font-medium text-gray-300">No recordings yet</h3>
          <p className="max-w-md text-sm text-gray-500">
            Recordings appear when debug mode is enabled and requests are captured. Enable request
            recording in the debug settings to start capturing API requests.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-4', className)}>
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Method filter */}
        <div className="flex items-center gap-2">
          <label htmlFor="method-filter" className="text-sm text-gray-400">
            Method:
          </label>
          <select
            id="method-filter"
            aria-label="Filter by method"
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
            className="rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          >
            <option value="all">All</option>
            {uniqueMethods.map((method) => (
              <option key={method} value={method}>
                {method}
              </option>
            ))}
          </select>
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-2">
          <label htmlFor="status-filter" className="text-sm text-gray-400">
            Status:
          </label>
          <select
            id="status-filter"
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          >
            <option value="all">All</option>
            <option value="2xx">2xx Success</option>
            <option value="4xx">4xx Client Error</option>
            <option value="5xx">5xx Server Error</option>
          </select>
        </div>

        {/* Path search */}
        <div className="flex items-center gap-2">
          <label htmlFor="path-search" className="text-sm text-gray-400">
            Path:
          </label>
          <input
            id="path-search"
            type="text"
            placeholder="Search path..."
            value={pathSearch}
            onChange={(e) => setPathSearch(e.target.value)}
            className="w-48 rounded-md border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          />
        </div>

        {/* Results count */}
        <div className="ml-auto text-sm text-gray-400">
          {filteredRecordings.length} of {recordings.length} recordings
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1F1F1F]">
        {filteredRecordings.length === 0 ? (
          <div className="flex items-center justify-center p-8">
            <p className="text-gray-400">No recordings match the current filters</p>
          </div>
        ) : (
          <table className="w-full" role="table">
            <thead className="border-b border-gray-800 bg-[#1A1A1A]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Method
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Path
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Duration
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {filteredRecordings.map((recording, index) => (
                <tr
                  key={recording.recording_id}
                  className={clsx(
                    'transition-colors hover:bg-[#76B900]/5',
                    index % 2 === 0 ? 'bg-transparent' : 'bg-gray-800/20'
                  )}
                >
                  {/* Method */}
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                        getMethodBadgeClasses(recording.method)
                      )}
                    >
                      {recording.method}
                    </span>
                  </td>

                  {/* Path */}
                  <td className="px-4 py-3">
                    <span className="font-mono text-sm text-gray-300" title={recording.path}>
                      {recording.path}
                    </span>
                    {recording.body_truncated && (
                      <span className="ml-2 text-xs text-yellow-500" title="Request body was truncated">
                        (truncated)
                      </span>
                    )}
                  </td>

                  {/* Status */}
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                        getStatusCodeClasses(recording.status_code)
                      )}
                    >
                      {recording.status_code}
                    </span>
                  </td>

                  {/* Duration */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-300">
                    {formatDuration(recording.duration_ms)}
                  </td>

                  {/* Timestamp */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-400">
                    {formatTimestamp(recording.timestamp)}
                  </td>

                  {/* Actions */}
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => onView(recording.recording_id)}
                        aria-label={`View recording ${recording.recording_id}`}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                        title="View details"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => onReplay(recording.recording_id)}
                        disabled={isReplaying || isDeleting}
                        aria-label={`Replay recording ${recording.recording_id}`}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-[#76B900]/10 hover:text-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
                        title="Replay request"
                      >
                        <Play className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => onDelete(recording.recording_id)}
                        disabled={isReplaying || isDeleting}
                        aria-label={`Delete recording ${recording.recording_id}`}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                        title="Delete recording"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
