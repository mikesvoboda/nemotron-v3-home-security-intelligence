import { clsx } from 'clsx';
import { ChevronLeft, ChevronRight, AlertOctagon, AlertTriangle, Info, Bug, FileText } from 'lucide-react';

import { EmptyState } from '../common';

export interface LogEntry {
  id: number;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  component: string;
  message: string;
  camera_id?: string | null;
  event_id?: number | null;
  request_id?: string | null;
  detection_id?: number | null;
  duration_ms?: number | null;
  extra?: Record<string, unknown> | null;
  source: string;
}

export interface LogsTableProps {
  logs: LogEntry[];
  totalCount: number;
  limit: number;
  offset: number;
  loading?: boolean;
  error?: string | null;
  onRowClick?: (log: LogEntry) => void;
  onPageChange?: (offset: number) => void;
  className?: string;
}

/**
 * Returns the color classes for a log level badge
 * - DEBUG: Gray/muted
 * - INFO: Blue
 * - WARNING: Yellow/amber
 * - ERROR: Red
 * - CRITICAL: Red with emphasis (solid background, bold)
 */
function getLevelBadgeClasses(level: LogEntry['level']): string {
  switch (level) {
    case 'CRITICAL':
      return 'bg-red-600 text-white border-red-600 font-bold';
    case 'ERROR':
      return 'bg-red-500/10 text-red-400 border-red-500/20';
    case 'WARNING':
      return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
    case 'INFO':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    case 'DEBUG':
      return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
    default:
      return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  }
}

/**
 * Returns the icon component for a log level (for accessibility, not color-only)
 */
function LevelIcon({ level }: { level: LogEntry['level'] }) {
  const iconClass = 'h-3.5 w-3.5 flex-shrink-0';
  switch (level) {
    case 'CRITICAL':
      return <AlertOctagon className={`${iconClass} text-white`} aria-hidden="true" />;
    case 'ERROR':
      return <AlertOctagon className={`${iconClass} text-red-400`} aria-hidden="true" />;
    case 'WARNING':
      return <AlertTriangle className={`${iconClass} text-yellow-400`} aria-hidden="true" />;
    case 'INFO':
      return <Info className={`${iconClass} text-blue-400`} aria-hidden="true" />;
    case 'DEBUG':
      return <Bug className={`${iconClass} text-gray-400`} aria-hidden="true" />;
    default:
      return <Info className={`${iconClass} text-gray-400`} aria-hidden="true" />;
  }
}

/**
 * Formats a timestamp for display
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  // Show relative time for recent logs
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  // Otherwise show formatted date
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Truncates a message to fit in the table cell
 */
function truncateMessage(message: string, maxLength: number = 100): string {
  if (message.length <= maxLength) return message;
  return message.substring(0, maxLength) + '...';
}

/**
 * LogsTable component displays a paginated table of log entries
 * - Click row to open detail modal
 * - Level badges with color coding (ERROR=red, WARNING=yellow, INFO=blue, DEBUG=gray)
 * - Matches EventTimeline pagination pattern
 * - Uses NVIDIA dark theme colors (zinc-900 background, green accents)
 */
export default function LogsTable({
  logs,
  totalCount,
  limit,
  offset,
  loading = false,
  error = null,
  onRowClick,
  onPageChange,
  className = '',
}: LogsTableProps) {
  // Calculate pagination info
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(totalCount / limit);
  const hasNextPage = offset + limit < totalCount;
  const hasPreviousPage = offset > 0;

  // Handle pagination
  const handlePreviousPage = () => {
    if (hasPreviousPage && onPageChange) {
      onPageChange(Math.max(0, offset - limit));
    }
  };

  const handleNextPage = () => {
    if (hasNextPage && onPageChange) {
      onPageChange(offset + limit);
    }
  };

  // Handle row click
  const handleRowClick = (log: LogEntry) => {
    if (onRowClick) {
      onRowClick(log);
    }
  };

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Results Summary */}
      <div className="mb-4 flex items-center justify-between text-sm text-gray-400">
        <p>
          Showing {offset + 1}-{Math.min(offset + limit, totalCount)} of {totalCount} logs
        </p>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1F1F1F]">
        {loading ? (
          <div className="flex min-h-[400px] items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
              <p className="text-gray-400">Loading logs...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex min-h-[400px] items-center justify-center border-red-900/50 bg-red-950/20">
            <div className="text-center">
              <p className="mb-2 text-lg font-semibold text-red-500">Error Loading Logs</p>
              <p className="text-sm text-gray-400">{error}</p>
            </div>
          </div>
        ) : logs.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No Logs Found"
            description="No logs match the current filters. Try adjusting your search criteria or selecting a different time range."
            variant="muted"
            testId="logs-empty-state"
          >
            <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 text-left">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-400">
                Logs are generated by:
              </p>
              <ul className="space-y-1.5 text-sm text-gray-400">
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                  Backend API services and routes
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                  AI detection and analysis pipeline
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                  WebSocket events and connections
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                  Frontend component errors
                </li>
              </ul>
            </div>
          </EmptyState>
        ) : (
          <table className="w-full">
            <thead className="border-b border-gray-800 bg-[#1A1A1A]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Level
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Component
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Message
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {logs.map((log) => (
                <tr
                  key={log.id}
                  onClick={() => handleRowClick(log)}
                  className={clsx(
                    'transition-colors',
                    onRowClick && 'cursor-pointer hover:bg-[#76B900]/5'
                  )}
                >
                  {/* Timestamp */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-300">
                    {formatTimestamp(log.timestamp)}
                  </td>

                  {/* Level Badge */}
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
                        getLevelBadgeClasses(log.level)
                      )}
                      role="status"
                      aria-label={`Log level: ${log.level}`}
                    >
                      <LevelIcon level={log.level} />
                      {log.level}
                    </span>
                  </td>

                  {/* Component */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-300">
                    <span className="font-mono text-[#76B900]">{log.component}</span>
                  </td>

                  {/* Message */}
                  <td className="px-4 py-3 text-sm text-gray-300">
                    <span className="line-clamp-2">{truncateMessage(log.message)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination Controls */}
      {!loading && !error && totalCount > 0 && (
        <div className="mt-6 flex items-center justify-between rounded-lg border border-gray-800 bg-[#1F1F1F] px-4 py-3">
          <button
            onClick={handlePreviousPage}
            disabled={!hasPreviousPage}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>

          <div className="text-sm text-gray-400">
            Page {currentPage} of {totalPages}
          </div>

          <button
            onClick={handleNextPage}
            disabled={!hasNextPage}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#76B900]/10 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
            aria-label="Next page"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
