import { Activity, CheckCircle, Clock, FileText, XCircle } from 'lucide-react';

import type { AuditLogStats } from '../../services/api';

export interface AuditStatsCardsProps {
  stats: AuditLogStats | null;
  loading?: boolean;
  className?: string;
}

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  loading?: boolean;
  colorClass?: string;
}

function StatCard({ title, value, icon, loading = false, colorClass = 'text-[#76B900]' }: StatCardProps) {
  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
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
 * - Total logs
 * - Logs today
 * - Success count
 * - Failure count
 */
export default function AuditStatsCards({
  stats,
  loading = false,
  className = '',
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
      />
      <StatCard
        title="Entries Today"
        value={stats?.logs_today ?? 0}
        icon={<Clock className="h-6 w-6" />}
        loading={loading}
        colorClass="text-blue-400"
      />
      <StatCard
        title="Successful Operations"
        value={successCount}
        icon={<CheckCircle className="h-6 w-6" />}
        loading={loading}
        colorClass="text-green-400"
      />
      <StatCard
        title="Failed Operations"
        value={failureCount}
        icon={<XCircle className="h-6 w-6" />}
        loading={loading}
        colorClass={failureCount > 0 ? 'text-red-400' : 'text-gray-400'}
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
              .map(([action, count]) => (
                <span
                  key={action}
                  className="inline-flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-800 px-3 py-1 text-xs"
                >
                  <span className="text-gray-300">
                    {action
                      .split('_')
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                      .join(' ')}
                  </span>
                  <span className="font-semibold text-[#76B900]">{count}</span>
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
