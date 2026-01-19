import { clsx } from 'clsx';
import { Radio, Layers } from 'lucide-react';
import { useCallback, useEffect, useState, useRef } from 'react';

import LogDetailModal from './LogDetailModal';
import LogFilters, { type LogFilterParams } from './LogFilters';
import LogsTable, { type LogEntry } from './LogsTable';
import LogStatsCards from './LogStatsCards';
import LogStatsSummary from './LogStatsSummary';
import { fetchCameras, fetchLogs, type Camera, type LogsQueryParams } from '../../services/api';

import type { LogLevel } from '../../services/logger';

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

  // State for level filter from stats cards (synced with LogFilters)
  const [levelFilter, setLevelFilter] = useState<LogLevel | undefined>(undefined);

  // State for tail mode (auto-refresh and scroll to bottom)
  const [tailModeEnabled, setTailModeEnabled] = useState(false);
  const tailIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tableContainerRef = useRef<HTMLDivElement | null>(null);

  // State for log grouping
  const [groupingEnabled, setGroupingEnabled] = useState(false);

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
        // Cast logs to match LogEntry type from LogsTable (level as union type)
        setLogs(response.items as LogEntry[]);
        setTotalCount(response.pagination.total);
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
    // Sync the level filter state when LogFilters changes it (e.g., from dropdown)
    setLevelFilter(filters.level);
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

  // Handle level filter from stats cards
  const handleLevelFilter = useCallback((level: LogLevel | undefined) => {
    setLevelFilter(level);
  }, []);

  // Tail mode: auto-refresh logs every 5 seconds
  useEffect(() => {
    if (tailModeEnabled) {
      const refreshLogs = async () => {
        try {
          const response = await fetchLogs(queryParams);
          setLogs(response.items as LogEntry[]);
          setTotalCount(response.pagination.total);
          // Scroll to bottom when new logs arrive
          if (tableContainerRef.current) {
            tableContainerRef.current.scrollTop = tableContainerRef.current.scrollHeight;
          }
        } catch (err) {
          // Silently handle errors in tail mode to not disrupt the UI
          console.error('Tail mode refresh error:', err);
        }
      };

      tailIntervalRef.current = setInterval(() => {
        void refreshLogs();
      }, 5000);

      return () => {
        if (tailIntervalRef.current) {
          clearInterval(tailIntervalRef.current);
          tailIntervalRef.current = null;
        }
      };
    }
  }, [tailModeEnabled, queryParams]);

  // Toggle tail mode
  const toggleTailMode = useCallback(() => {
    setTailModeEnabled((prev) => !prev);
  }, []);

  // Toggle log grouping
  const toggleGrouping = useCallback(() => {
    setGroupingEnabled((prev) => !prev);
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">System Logs</h1>
            <p className="mt-2 text-gray-400">
              View and filter all system logs from backend services and frontend components
            </p>
          </div>
          {/* Tail mode and grouping toggles */}
          <div className="flex items-center gap-2">
            {/* Grouping toggle */}
            <button
              onClick={toggleGrouping}
              className={clsx(
                'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                groupingEnabled
                  ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                  : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-300'
              )}
              aria-label="Toggle log grouping"
              aria-pressed={groupingEnabled}
            >
              <Layers className="h-4 w-4" />
              Group
            </button>

            {/* Tail mode toggle */}
            <button
              onClick={toggleTailMode}
              className={clsx(
                'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                tailModeEnabled
                  ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
                  : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-300'
              )}
              aria-label="Toggle tail mode"
              aria-pressed={tailModeEnabled}
            >
              <Radio className="h-4 w-4" />
              Tail
              {tailModeEnabled && (
                <span
                  className="h-2 w-2 animate-pulse rounded-full bg-[#76B900]"
                  data-testid="tail-mode-indicator"
                />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="mb-6">
        <LogStatsCards onLevelFilter={handleLevelFilter} activeLevel={levelFilter} />
      </div>

      {/* Log Stats Summary (last hour) */}
      <div className="mb-4">
        <LogStatsSummary logs={logs} />
      </div>

      {/* Filter Panel */}
      <div className="mb-6">
        <LogFilters
          onFilterChange={handleFilterChange}
          cameras={cameras}
          externalLevel={levelFilter}
        />
      </div>

      {/* Logs Table with Pagination */}
      <div ref={tableContainerRef}>
        <LogsTable
          logs={logs}
          totalCount={totalCount}
          limit={queryParams.limit || 50}
          offset={queryParams.offset || 0}
          loading={loading}
          error={error}
          onRowClick={handleRowClick}
          onPageChange={handlePageChange}
          enableGrouping={groupingEnabled}
        />
      </div>

      {/* Detail Modal */}
      <LogDetailModal log={selectedLog} isOpen={isModalOpen} onClose={handleModalClose} />
    </div>
  );
}
