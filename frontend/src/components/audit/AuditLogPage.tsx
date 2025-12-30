import { useCallback, useEffect, useState } from 'react';

import AuditDetailModal from './AuditDetailModal';
import AuditFilters, { type AuditFilterParams } from './AuditFilters';
import AuditStatsCards from './AuditStatsCards';
import AuditTable, { type AuditEntry } from './AuditTable';
import {
  fetchAuditLogs,
  fetchAuditStats,
  type AuditLogsQueryParams,
  type AuditLogStats,
} from '../../services/api';

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

  // Load logs whenever query parameters change
  useEffect(() => {
    const loadLogs = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchAuditLogs(queryParams);
        // Cast logs to match AuditEntry type
        setLogs(response.logs as AuditEntry[]);
        setTotalCount(response.count);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load audit logs');
      } finally {
        setLoading(false);
      }
    };
    void loadLogs();
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

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white">Audit Log</h1>
        <p className="mt-2 text-gray-400">
          Review security-sensitive operations and system activity across all resources
        </p>
      </div>

      {/* Statistics Cards */}
      <div className="mb-6">
        <AuditStatsCards stats={stats} loading={statsLoading} />
      </div>

      {/* Filter Panel */}
      <div className="mb-6">
        <AuditFilters
          onFilterChange={handleFilterChange}
          availableActions={stats?.by_action ? Object.keys(stats.by_action) : []}
          availableResourceTypes={stats?.by_resource_type ? Object.keys(stats.by_resource_type) : []}
          availableActors={stats?.recent_actors || []}
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
