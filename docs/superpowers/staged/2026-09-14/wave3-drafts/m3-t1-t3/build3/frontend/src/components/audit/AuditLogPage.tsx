import { X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import AuditDetailModal from './AuditDetailModal';
import AuditFilters, { type AuditFilterParams } from './AuditFilters';
import AuditStatsCards, { type StatsFilterType } from './AuditStatsCards';
import AuditTableInfinite, { type AuditEntry } from './AuditTableInfinite';
import { useAuditLogsInfiniteQuery, useInfiniteScroll, type AuditLogFilters } from '../../hooks';
import { fetchAuditStats, type AuditLogStats } from '../../services/api';

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
 * - Shows AuditTableInfinite with infinite scroll pagination
 * - Opens AuditDetailModal when clicking on a row
 * - Fetches data from /api/audit and /api/audit/stats endpoints
 * - Uses NVIDIA dark theme styling (bg-[#1A1A1A], green accents #76B900)
 */
export default function AuditLogPage({ className = '' }: AuditLogPageProps) {
  // State for stats
  const [stats, setStats] = useState<AuditLogStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // State for filters
  const [filters, setFilters] = useState<AuditLogFilters>({});

  // State for detail modal
  const [selectedLog, setSelectedLog] = useState<AuditEntry | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // State for stats card filter selection (for visual feedback)
  const [activeStatsFilter, setActiveStatsFilter] = useState<StatsFilterType | null>(null);
  const [activeActionFilter, setActiveActionFilter] = useState<string | null>(null);
  const [activeActorFilter, setActiveActorFilter] = useState<string | null>(null);

  // Controlled filters for AuditFilters component
  const [controlledFilters, setControlledFilters] = useState<AuditFilterParams>({});

  // Use infinite query hook for audit logs
  const {
    logs,
    totalCount,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
    isError,
  } = useAuditLogsInfiniteQuery({
    filters,
    limit: 50,
  });

  // Use infinite scroll hook for automatic loading
  const { sentinelRef, isLoadingMore } = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    hasMore: hasNextPage,
    isLoading: isFetchingNextPage,
  });

  // Cast logs to match AuditEntry type
  const auditLogs = useMemo(() => logs as AuditEntry[], [logs]);

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

  // Handle filter changes from AuditFilters component
  const handleFilterChange = useCallback((filterParams: AuditFilterParams) => {
    setFilters({
      action: filterParams.action,
      resource_type: filterParams.resourceType,
      actor: filterParams.actor,
      status: filterParams.status,
      start_date: filterParams.startDate,
      end_date: filterParams.endDate,
    });
  }, []);

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
  const handleStatsFilterClick = useCallback(
    (filterType: StatsFilterType) => {
      // Toggle behavior: click active filter to clear it
      if (activeStatsFilter === filterType) {
        // Clear the filter
        setActiveStatsFilter(null);
        setActiveActionFilter(null);
        setActiveActorFilter(null);
        setControlledFilters({});
        return;
      }

      // Clear any other filters when clicking a stats card
      setActiveActionFilter(null);
      setActiveActorFilter(null);
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
    },
    [activeStatsFilter]
  );

  // Handle action badge click (from stats cards or table)
  const handleActionClick = useCallback(
    (action: string) => {
      // Toggle behavior: click active filter to clear it
      if (activeActionFilter === action) {
        setActiveActionFilter(null);
        setActiveActorFilter(null);
        setControlledFilters({});
        setActiveStatsFilter(null);
        return;
      }

      // Clear any other filters when clicking an action badge
      setActiveStatsFilter(null);
      setActiveActorFilter(null);
      setActiveActionFilter(action);
      setControlledFilters({ action });
    },
    [activeActionFilter]
  );

  // Handle actor click from table
  const handleActorClick = useCallback(
    (actor: string) => {
      // Toggle behavior: click active filter to clear it
      if (activeActorFilter === actor) {
        setActiveActorFilter(null);
        setActiveActionFilter(null);
        setControlledFilters({});
        setActiveStatsFilter(null);
        return;
      }

      // Clear any other filters when clicking an actor
      setActiveStatsFilter(null);
      setActiveActionFilter(null);
      setActiveActorFilter(actor);
      setControlledFilters({ actor });
    },
    [activeActorFilter]
  );

  // Clear a specific filter chip
  const handleClearFilter = useCallback((filterType: 'action' | 'actor') => {
    if (filterType === 'action') {
      setActiveActionFilter(null);
    } else if (filterType === 'actor') {
      setActiveActorFilter(null);
    }
    setActiveStatsFilter(null);
    setControlledFilters({});
  }, []);

  // Handle load more button click
  const handleLoadMore = useCallback(() => {
    if (!isFetchingNextPage && hasNextPage) {
      fetchNextPage();
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

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
              The audit log automatically records system operations for security and compliance
              purposes. Actions that create audit entries include:
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
          availableResourceTypes={
            stats?.by_resource_type ? Object.keys(stats.by_resource_type) : []
          }
          availableActors={stats?.recent_actors || []}
          controlledFilters={controlledFilters}
        />
      </div>

      {/* Active Filter Chips */}
      {(activeActionFilter || activeActorFilter) && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-400">Active filters:</span>
          {activeActionFilter && (
            <button
              onClick={() => handleClearFilter('action')}
              className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-sm font-medium text-blue-400 transition-colors hover:bg-blue-500/20"
              aria-label={`Clear action filter: ${activeActionFilter
                .split('_')
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                .join(' ')}`}
            >
              Action:{' '}
              {activeActionFilter
                .split('_')
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                .join(' ')}
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          {activeActorFilter && (
            <button
              onClick={() => handleClearFilter('actor')}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#76B900]/30 bg-[#76B900]/10 px-3 py-1 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
              aria-label={`Clear actor filter: ${activeActorFilter}`}
            >
              Actor: {activeActorFilter}
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Audit Table with Infinite Scroll */}
      <AuditTableInfinite
        logs={auditLogs}
        totalCount={totalCount}
        loading={isLoading}
        loadingMore={isFetchingNextPage || isLoadingMore}
        error={isError ? error?.message || 'Failed to load audit logs' : null}
        hasMore={hasNextPage}
        onRowClick={handleRowClick}
        onLoadMore={handleLoadMore}
        onActorClick={handleActorClick}
        onActionClick={handleActionClick}
        activeActorFilter={activeActorFilter}
        activeActionFilter={activeActionFilter}
        loadMoreRef={{ current: null }}
      />

      {/* Infinite scroll sentinel - triggers loading when visible */}
      {hasNextPage && !isLoading && !isError && auditLogs.length > 0 && (
        <div
          ref={sentinelRef}
          className="h-4"
          data-testid="infinite-scroll-sentinel"
          aria-hidden="true"
        />
      )}

      {/* Detail Modal */}
      <AuditDetailModal log={selectedLog} isOpen={isModalOpen} onClose={handleModalClose} />
    </div>
  );
}
