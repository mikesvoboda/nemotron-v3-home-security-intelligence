import { useCallback, useEffect, useState } from 'react';

import AuditDetailModal from './AuditDetailModal';
import AuditFilters, { type AuditFilterParams } from './AuditFilters';
import AuditStatsCards, { type StatsFilterType } from './AuditStatsCards';
import AuditTable, { type AuditEntry } from './AuditTable';
import {
  fetchAuditLogs,
  fetchAuditStats,
  isAbortError,
  type AuditLogsQueryParams,
  type AuditLogStats,
} from '../../services/api';

/**
 * Get today's date in YYYY-MM-DD format for filtering
 */
function getTodayDateString(): string {
  const today = new Date();
  return today.toISOString().split('T')[0];
}

export interface AuditLogPageProps {
  className?: string;
}

/**
 * AuditLogPage component assembles the complete audit log viewer interface
 * - Displays AuditStatsCards at the top with statistics
 * - Provides AuditFilters for filtering audit entries
 * - Shows AuditTable with paginated audit entries
 * - Opens AuditDetailModal when clicking on a row
 * - Fetches data from /api/audit and /api/audit/stats endpoints
 * - Uses NVIDIA dark theme styling (bg-[#1A1A1A], green accents #76B900)
 */
export default function AuditLogPage({ className = '' }: AuditLogPageProps) {
  // State for audit logs data
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for stats
  const [stats, setStats] = useState<AuditLogStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // State for query parameters
  const [queryParams, setQueryParams] = useState<AuditLogsQueryParams>({
    limit: 50,
    offset: 0,
  });

  // State for detail modal
  const [selectedLog, setSelectedLog] = useState<AuditEntry | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // State for stats card filter selection (for visual feedback)
  const [activeStatsFilter, setActiveStatsFilter] = useState<StatsFilterType | null>(null);
  const [activeActionFilter, setActiveActionFilter] = useState<string | null>(null);

  // Controlled filters for AuditFilters component
  const [controlledFilters, setControlledFilters] = useState<AuditFilterParams>({});

  // Load stats on mount
  useEffect(() => {
    const loadStats = async () => {
      setStatsLoading(true);
      try {
        const data = await fetchAuditStats();
        setStats(data);
      } catch (err) {
        console.error('Failed to load audit stats:', err);
      } finally {
        setStatsLoading(false);
      }
    };
    void loadStats();
  }, []);

  // Load logs whenever query parameters change (with AbortController to cancel stale requests)
  useEffect(() => {
    const controller = new AbortController();

    const loadLogs = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchAuditLogs(queryParams, { signal: controller.signal });
        // Cast items to match AuditEntry type
        setLogs(response.items as AuditEntry[]);
        setTotalCount(response.pagination.total);
      } catch (err) {
        // Ignore aborted requests - user changed filters before request completed
        if (isAbortError(err)) return;
        setError(err instanceof Error ? err.message : 'Failed to load audit logs');
      } finally {
        // Only update loading state if request wasn't aborted
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };
    void loadLogs();

    // Cleanup: abort pending request when filters change or component unmounts
    return () => controller.abort();
  }, [queryParams]);

  // Handle filter changes from AuditFilters component
  const handleFilterChange = useCallback((filters: AuditFilterParams) => {
    setQueryParams((prev) => ({
      ...prev,
      action: filters.action,
      resource_type: filters.resourceType,
      actor: filters.actor,
      status: filters.status,
      start_date: filters.startDate,
      end_date: filters.endDate,
      offset: 0, // Reset to first page when filters change
    }));
  }, []);

  // Handle pagination from AuditTable component
  const handlePageChange = (offset: number) => {
    setQueryParams((prev) => ({
      ...prev,
      offset,
    }));
  };

  // Handle row click to open detail modal
  const handleRowClick = (log: AuditEntry) => {
    setSelectedLog(log);
    setIsModalOpen(true);
  };

  // Handle modal close
  const handleModalClose = () => {
    setIsModalOpen(false);
    // Don't clear selectedLog immediately to allow modal to animate out
    setTimeout(() => setSelectedLog(null), 300);
  };

  // Handle stats card filter click
  const handleStatsFilterClick = useCallback((filterType: StatsFilterType) => {
    // Toggle behavior: click active filter to clear it
    if (activeStatsFilter === filterType) {
      // Clear the filter
      setActiveStatsFilter(null);
      setActiveActionFilter(null);
      setControlledFilters({});
      return;
    }

    // Clear any action filter when clicking a stats card
    setActiveActionFilter(null);
    setActiveStatsFilter(filterType);

    // Apply the appropriate filter based on card type
    switch (filterType) {
      case 'total':
        // Clear all filters
        setControlledFilters({});
        break;
      case 'today':
        // Filter to today's date
        setControlledFilters({
          startDate: getTodayDateString(),
          endDate: getTodayDateString(),
        });
        break;
      case 'success':
        // Filter by status=success
        setControlledFilters({ status: 'success' });
        break;
      case 'failure':
        // Filter by status=failure
        setControlledFilters({ status: 'failure' });
        break;
    }
  }, [activeStatsFilter]);

  // Handle action badge click
  const handleActionClick = useCallback((action: string) => {
    // Toggle behavior: click active filter to clear it
    if (activeActionFilter === action) {
      setActiveActionFilter(null);
      setControlledFilters({});
      setActiveStatsFilter(null);
      return;
    }

    // Clear any stats filter when clicking an action badge
    setActiveStatsFilter(null);
    setActiveActionFilter(action);
    setControlledFilters({ action });
  }, [activeActionFilter]);

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white">Audit Log</h1>
        <p className="mt-2 text-gray-400">
          Review security-sensitive operations and system activity across all resources
        </p>
      </div>

      {/* Info Box - What gets logged */}
      <div className="mb-6 rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
        <div className="flex items-start gap-3">
          <svg
            className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <h3 className="font-medium text-blue-300">What gets logged</h3>
            <p className="mt-1 text-sm text-gray-300">
              The audit log automatically records system operations for security and
              compliance purposes. Actions that create audit entries include:
            </p>
            <ul className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-sm text-gray-400 sm:grid-cols-2">
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                Settings changes
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                Event reviews
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                AI re-evaluations
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                Camera configurations
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                Alert rule changes
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                Media exports
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="mb-6">
        <AuditStatsCards
          stats={stats}
          loading={statsLoading}
          activeFilter={activeStatsFilter}
          activeActionFilter={activeActionFilter}
          onFilterClick={handleStatsFilterClick}
          onActionClick={handleActionClick}
        />
      </div>

      {/* Filter Panel */}
      <div className="mb-6">
        <AuditFilters
          onFilterChange={handleFilterChange}
          availableActions={stats?.by_action ? Object.keys(stats.by_action) : []}
          availableResourceTypes={stats?.by_resource_type ? Object.keys(stats.by_resource_type) : []}
          availableActors={stats?.recent_actors || []}
          controlledFilters={controlledFilters}
        />
      </div>

      {/* Audit Table with Pagination */}
      <AuditTable
        logs={logs}
        totalCount={totalCount}
        limit={queryParams.limit || 50}
        offset={queryParams.offset || 0}
        loading={loading}
        error={error}
        onRowClick={handleRowClick}
        onPageChange={handlePageChange}
      />

      {/* Detail Modal */}
      <AuditDetailModal log={selectedLog} isOpen={isModalOpen} onClose={handleModalClose} />
    </div>
  );
}
