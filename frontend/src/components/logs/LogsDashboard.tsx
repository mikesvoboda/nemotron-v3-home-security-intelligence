import { useCallback, useEffect, useState } from 'react';

import LogDetailModal from './LogDetailModal';
import LogFilters, { type LogFilterParams } from './LogFilters';
import LogsTable, { type LogEntry } from './LogsTable';
import LogStatsCards from './LogStatsCards';
import { fetchCameras, fetchLogs, type Camera, type LogsQueryParams } from '../../services/api';

export interface LogsDashboardProps {
  className?: string;
}

/**
 * LogsDashboard component assembles the complete logging interface
 * - Displays LogStatsCards at the top with real-time statistics
 * - Provides LogFilters for filtering log entries
 * - Shows LogsTable with paginated log entries
 * - Opens LogDetailModal when clicking on a log row
 * - Fetches data from /api/logs and /api/logs/stats endpoints
 * - Uses NVIDIA dark theme styling (bg-[#1A1A1A], green accents #76B900)
 */
export default function LogsDashboard({ className = '' }: LogsDashboardProps) {
  // State for logs data
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for cameras (for filter dropdown)
  const [cameras, setCameras] = useState<Camera[]>([]);

  // State for query parameters
  const [queryParams, setQueryParams] = useState<LogsQueryParams>({
    limit: 50,
    offset: 0,
  });

  // State for detail modal
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Load cameras for filter dropdown
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const data = await fetchCameras();
        setCameras(data);
      } catch (err) {
        console.error('Failed to load cameras:', err);
      }
    };
    void loadCameras();
  }, []);

  // Load logs whenever query parameters change
  useEffect(() => {
    const loadLogs = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchLogs(queryParams);
        setLogs(response.logs);
        setTotalCount(response.count);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load logs');
      } finally {
        setLoading(false);
      }
    };
    void loadLogs();
  }, [queryParams]);

  // Handle filter changes from LogFilters component
  const handleFilterChange = useCallback((filters: LogFilterParams) => {
    setQueryParams((prev) => ({
      ...prev,
      level: filters.level,
      component: filters.component,
      camera_id: filters.camera,
      start_date: filters.startDate,
      end_date: filters.endDate,
      search: filters.search,
      offset: 0, // Reset to first page when filters change
    }));
  }, []);

  // Handle pagination from LogsTable component
  const handlePageChange = (offset: number) => {
    setQueryParams((prev) => ({
      ...prev,
      offset,
    }));
  };

  // Handle row click to open detail modal
  const handleRowClick = (log: LogEntry) => {
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
        <h1 className="text-3xl font-bold text-white">System Logs</h1>
        <p className="mt-2 text-gray-400">
          View and filter all system logs from backend services and frontend components
        </p>
      </div>

      {/* Statistics Cards */}
      <div className="mb-6">
        <LogStatsCards />
      </div>

      {/* Filter Panel */}
      <div className="mb-6">
        <LogFilters onFilterChange={handleFilterChange} cameras={cameras} />
      </div>

      {/* Logs Table with Pagination */}
      <LogsTable
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
      <LogDetailModal log={selectedLog} isOpen={isModalOpen} onClose={handleModalClose} />
    </div>
  );
}
