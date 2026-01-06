import { Activity, CheckCircle, Clock, FileText, XCircle } from 'lucide-react';

import type { AuditLogStats } from '../../services/api';

export type StatsFilterType = 'total' | 'today' | 'success' | 'failure';

export interface AuditStatsCardsProps {
  stats: AuditLogStats | null;
  loading?: boolean;
  className?: string;
  /** Currently active filter from stats card click */
  activeFilter?: StatsFilterType | null;
  /** Currently active action filter from badge click */
  activeActionFilter?: string | null;
  /** Callback when a stats card is clicked */
  onFilterClick?: (filterType: StatsFilterType) => void;
  /** Callback when an action badge is clicked */
  onActionClick?: (action: string) => void;
}

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  loading?: boolean;
  colorClass?: string;
  onClick?: () => void;
  isActive?: boolean;
}

function StatCard({
  title,
  value,
  icon,
  loading = false,
  colorClass = 'text-[#76B900]',
  onClick,
  isActive = false,
}: StatCardProps) {
  const baseClasses = 'rounded-lg border bg-[#1F1F1F] p-4 transition-all duration-200';
  const interactiveClasses = onClick
    ? 'cursor-pointer hover:bg-[#2A2A2A] hover:border-gray-700'
    : '';
  const activeClasses = isActive
    ? 'ring-2 ring-[#76B900] border-[#76B900]'
    : 'border-gray-800';

  const handleKeyDown = onClick
    ? (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }
    : undefined;

  /*
   * StatCard conditionally becomes interactive when onClick is provided.
   * When onClick is undefined, it's a display-only card with no interactions.
   * eslint rule doesn't recognize this conditional pattern.
   */
  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      className={`${baseClasses} ${interactiveClasses} ${activeClasses}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={handleKeyDown}
      aria-pressed={onClick ? isActive : undefined}
      aria-label={onClick ? `Filter by ${title}` : undefined}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          {loading ? (
            <div className="mt-1 h-8 w-20 animate-pulse rounded bg-gray-700" />
          ) : (
            <p className={`mt-1 text-2xl font-bold ${colorClass}`}>{value}</p>
          )}
        </div>
        <div className={`rounded-lg bg-gray-800 p-3 ${colorClass}`}>{icon}</div>
      </div>
    </div>
  );
}

/**
 * AuditStatsCards component displays key statistics about audit logs
 * - Total logs (click to clear all filters)
 * - Logs today (click to filter to today's date)
 * - Success count (click to filter by status=success)
 * - Failure count (click to filter by status=failure)
 * - Action badges (click to filter by specific action)
 */
export default function AuditStatsCards({
  stats,
  loading = false,
  className = '',
  activeFilter = null,
  activeActionFilter = null,
  onFilterClick,
  onActionClick,
}: AuditStatsCardsProps) {
  const successCount = stats?.by_status?.success ?? 0;
  const failureCount = stats?.by_status?.failure ?? 0;

  return (
    <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 ${className}`}>
      <StatCard
        title="Total Audit Entries"
        value={stats?.total_logs ?? 0}
        icon={<FileText className="h-6 w-6" />}
        loading={loading}
        onClick={onFilterClick ? () => onFilterClick('total') : undefined}
        isActive={activeFilter === 'total'}
      />
      <StatCard
        title="Entries Today"
        value={stats?.logs_today ?? 0}
        icon={<Clock className="h-6 w-6" />}
        loading={loading}
        colorClass="text-blue-400"
        onClick={onFilterClick ? () => onFilterClick('today') : undefined}
        isActive={activeFilter === 'today'}
      />
      <StatCard
        title="Successful Operations"
        value={successCount}
        icon={<CheckCircle className="h-6 w-6" />}
        loading={loading}
        colorClass="text-green-400"
        onClick={onFilterClick ? () => onFilterClick('success') : undefined}
        isActive={activeFilter === 'success'}
      />
      <StatCard
        title="Failed Operations"
        value={failureCount}
        icon={<XCircle className="h-6 w-6" />}
        loading={loading}
        colorClass={failureCount > 0 ? 'text-red-400' : 'text-gray-400'}
        onClick={onFilterClick ? () => onFilterClick('failure') : undefined}
        isActive={activeFilter === 'failure'}
      />

      {/* Action breakdown (secondary row) */}
      {stats?.by_action && Object.keys(stats.by_action).length > 0 && (
        <div className="col-span-full rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="h-5 w-5 text-[#76B900]" />
            <h3 className="text-sm font-medium text-gray-300">Actions by Type</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.by_action)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 10)
              .map(([action, count]) => {
                const isActive = activeActionFilter === action;
                const baseClasses =
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-all duration-200';
                const interactiveClasses = onActionClick
                  ? 'cursor-pointer hover:bg-gray-700 hover:border-gray-600'
                  : '';
                const activeClasses = isActive
                  ? 'ring-2 ring-[#76B900] border-[#76B900] bg-[#76B900]/10'
                  : 'border-gray-700 bg-gray-800';

                return (
                  <button
                    key={action}
                    type="button"
                    className={`${baseClasses} ${interactiveClasses} ${activeClasses}`}
                    onClick={onActionClick ? () => onActionClick(action) : undefined}
                    aria-pressed={isActive}
                  >
                    <span className="text-gray-300">
                      {action
                        .split('_')
                        .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                        .join(' ')}
                    </span>
                    <span className="font-semibold text-[#76B900]">{count}</span>
                  </button>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
