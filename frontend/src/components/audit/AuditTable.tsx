import { clsx } from 'clsx';
import { CheckCircle, ChevronLeft, ChevronRight, Globe, XCircle } from 'lucide-react';

export interface AuditEntry {
  id: number;
  timestamp: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  actor: string;
  ip_address?: string | null;
  user_agent?: string | null;
  details?: Record<string, unknown> | null;
  status: string;
}

export interface AuditTableProps {
  logs: AuditEntry[];
  totalCount: number;
  limit: number;
  offset: number;
  loading?: boolean;
  error?: string | null;
  onRowClick?: (log: AuditEntry) => void;
  onPageChange?: (offset: number) => void;
  className?: string;
}

/**
 * Returns the color classes for a status badge
 */
function getStatusBadgeClasses(status: string): string {
  switch (status.toLowerCase()) {
    case 'success':
      return 'bg-green-500/10 text-green-400 border-green-500/20';
    case 'failure':
    case 'failed':
    case 'error':
      return 'bg-red-500/10 text-red-400 border-red-500/20';
    default:
      return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
  }
}

/**
 * Returns the icon for a status
 */
function getStatusIcon(status: string) {
  switch (status.toLowerCase()) {
    case 'success':
      return <CheckCircle className="h-3.5 w-3.5" />;
    case 'failure':
    case 'failed':
    case 'error':
      return <XCircle className="h-3.5 w-3.5" />;
    default:
      return null;
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
 * Formats an action name for display
 */
function formatAction(action: string): string {
  return action
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * AuditTable component displays a paginated table of audit log entries
 * - Click row to open detail modal
 * - Status badges with color coding (success=green, failure=red)
 * - Matches LogsTable pagination pattern
 * - Uses NVIDIA dark theme colors (zinc-900 background, green accents)
 */
export default function AuditTable({
  logs,
  totalCount,
  limit,
  offset,
  loading = false,
  error = null,
  onRowClick,
  onPageChange,
  className = '',
}: AuditTableProps) {
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
  const handleRowClick = (log: AuditEntry) => {
    if (onRowClick) {
      onRowClick(log);
    }
  };

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Results Summary */}
      <div className="mb-4 flex items-center justify-between text-sm text-gray-400">
        <p>
          Showing {totalCount > 0 ? offset + 1 : 0}-{Math.min(offset + limit, totalCount)} of{' '}
          {totalCount} audit entries
        </p>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto rounded-lg border border-gray-800 bg-[#1F1F1F]">
        {loading ? (
          <div className="flex min-h-[400px] items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-[#76B900]" />
              <p className="text-gray-400">Loading audit logs...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex min-h-[400px] items-center justify-center border-red-900/50 bg-red-950/20">
            <div className="text-center">
              <p className="mb-2 text-lg font-semibold text-red-500">Error Loading Audit Logs</p>
              <p className="text-sm text-gray-400">{error}</p>
            </div>
          </div>
        ) : logs.length === 0 ? (
          <div className="flex min-h-[400px] items-center justify-center">
            <div className="max-w-md text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gray-800">
                <svg
                  className="h-6 w-6 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <p className="mb-2 text-lg font-semibold text-gray-300">No Audit Entries Found</p>
              <p className="mb-4 text-sm text-gray-500">
                No audit logs match the current filters. Audit entries are automatically created when
                you perform system operations.
              </p>
              <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4 text-left">
                <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-400">
                  Try these actions to generate entries:
                </p>
                <ul className="space-y-2 text-sm text-gray-400">
                  <li className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                    <span>Change system settings in the Settings page</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                    <span>Mark events as reviewed in the Events timeline</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                    <span>Modify camera configurations</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                    <span>Trigger AI re-evaluations on events</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <table className="w-full">
            <thead className="border-b border-gray-800 bg-[#1A1A1A]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Actor
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Action
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Resource
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  IP Address
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                  Status
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

                  {/* Actor */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm">
                    <span className="font-medium text-[#76B900]">{log.actor}</span>
                  </td>

                  {/* Action */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-300">
                    {formatAction(log.action)}
                  </td>

                  {/* Resource */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-300">
                    <span className="font-mono text-xs">
                      {log.resource_type}
                      {log.resource_id && (
                        <span className="text-gray-500">/{log.resource_id}</span>
                      )}
                    </span>
                  </td>

                  {/* IP Address */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm">
                    {log.ip_address ? (
                      <span className="flex items-center gap-1.5 text-gray-400">
                        <Globe className="h-3.5 w-3.5" />
                        <span className="font-mono text-xs">{log.ip_address}</span>
                      </span>
                    ) : (
                      <span className="text-gray-600">-</span>
                    )}
                  </td>

                  {/* Status Badge */}
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
                        getStatusBadgeClasses(log.status)
                      )}
                    >
                      {getStatusIcon(log.status)}
                      {log.status}
                    </span>
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
