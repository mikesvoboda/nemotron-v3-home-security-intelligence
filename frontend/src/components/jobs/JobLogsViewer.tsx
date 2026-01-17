/**
 * JobLogsViewer - Component for displaying job logs with real-time WebSocket streaming
 *
 * Features:
 * - Connection indicator showing WebSocket status
 * - Auto-scroll to latest logs
 * - Log level filtering (DEBUG, INFO, WARNING, ERROR)
 * - Clear logs functionality
 * - Responsive design
 *
 * NEM-2711
 */

import { clsx } from 'clsx';
import { ChevronDown, FileText, RefreshCw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import ConnectionIndicator from './ConnectionIndicator';
import { useJobLogsWebSocket } from '../../hooks/useJobLogsWebSocket';

import type { JobLogEntry, JobLogLevel } from '../../hooks/useJobLogsWebSocket';

// ============================================================================
// Types
// ============================================================================

export type LogLevelFilter = 'ALL' | JobLogLevel;

export interface JobLogsViewerProps {
  /** The job ID to stream logs for */
  jobId: string;
  /** Whether WebSocket streaming is enabled */
  enabled: boolean;
  /** Maximum height of the log viewer in pixels */
  maxHeight?: number;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the color classes for log level badge.
 */
function getLevelColorClasses(level: JobLogLevel): string {
  switch (level) {
    case 'DEBUG':
      return 'text-gray-400 bg-gray-400/10';
    case 'INFO':
      return 'text-blue-400 bg-blue-400/10';
    case 'WARNING':
      return 'text-yellow-400 bg-yellow-400/10';
    case 'ERROR':
      return 'text-red-400 bg-red-400/10';
    default:
      return 'text-gray-400 bg-gray-400/10';
  }
}

/**
 * Log level priority for filtering (higher number = higher priority).
 */
const LOG_LEVEL_PRIORITY: Record<JobLogLevel, number> = {
  DEBUG: 0,
  INFO: 1,
  WARNING: 2,
  ERROR: 3,
};

/**
 * Filter logs by minimum level.
 */
function filterLogsByLevel(logs: JobLogEntry[], minLevel: LogLevelFilter): JobLogEntry[] {
  if (minLevel === 'ALL') {
    return logs;
  }
  const minPriority = LOG_LEVEL_PRIORITY[minLevel];
  return logs.filter((log) => LOG_LEVEL_PRIORITY[log.level] >= minPriority);
}

/**
 * Format timestamp for display.
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

// ============================================================================
// Sub-components
// ============================================================================

interface LogEntryRowProps {
  log: JobLogEntry;
}

function LogEntryRow({ log }: LogEntryRowProps) {
  const levelClasses = getLevelColorClasses(log.level);
  const timestamp = formatTimestamp(log.timestamp);

  return (
    <div className="flex items-start gap-3 py-1.5 px-3 hover:bg-gray-800/30 font-mono text-sm">
      {/* Timestamp */}
      <span className="text-gray-500 text-xs whitespace-nowrap">{timestamp}</span>

      {/* Level badge */}
      <span className={clsx('px-1.5 py-0.5 rounded text-xs font-medium whitespace-nowrap', levelClasses)}>
        {log.level}
      </span>

      {/* Message */}
      <span className="text-gray-200 break-words flex-1">{log.message}</span>
    </div>
  );
}

interface LevelFilterDropdownProps {
  value: LogLevelFilter;
  onChange: (value: LogLevelFilter) => void;
}

function LevelFilterDropdown({ value, onChange }: LevelFilterDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const options: { value: LogLevelFilter; label: string }[] = [
    { value: 'ALL', label: 'All Levels' },
    { value: 'DEBUG', label: 'Debug' },
    { value: 'INFO', label: 'Info' },
    { value: 'WARNING', label: 'Warning' },
    { value: 'ERROR', label: 'Error' },
  ];

  const selectedLabel = options.find((opt) => opt.value === value)?.label ?? 'All Levels';

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        className={clsx(
          'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium',
          'bg-gray-800 border border-gray-700 text-gray-300',
          'hover:bg-gray-700 hover:border-gray-600 transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900'
        )}
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Filter by log level"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span>{selectedLabel}</span>
        <ChevronDown className={clsx('h-3.5 w-3.5 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 mt-1 z-50 min-w-[120px] bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1"
          role="listbox"
        >
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={value === option.value}
              className={clsx(
                'w-full text-left px-3 py-1.5 text-xs transition-colors',
                value === option.value
                  ? 'bg-[#76B900]/20 text-[#76B900]'
                  : 'text-gray-300 hover:bg-gray-700'
              )}
              onClick={() => {
                onChange(option.value);
                setIsOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * JobLogsViewer displays job logs with real-time WebSocket streaming.
 *
 * @example
 * ```tsx
 * <JobLogsViewer
 *   jobId="job-123"
 *   enabled={job.status === 'running' || job.status === 'pending'}
 *   maxHeight={400}
 * />
 * ```
 */
export default function JobLogsViewer({
  jobId,
  enabled,
  maxHeight = 300,
  className,
}: JobLogsViewerProps) {
  const { logs, status, reconnectCount, clearLogs } = useJobLogsWebSocket({
    jobId,
    enabled,
  });

  const [levelFilter, setLevelFilter] = useState<LogLevelFilter>('ALL');
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Filter logs by level
  const filteredLogs = useMemo(() => filterLogsByLevel(logs, levelFilter), [logs, levelFilter]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  const handleToggleAutoScroll = useCallback(() => {
    setAutoScroll((prev) => !prev);
  }, []);

  const handleClearLogs = useCallback(() => {
    clearLogs();
  }, [clearLogs]);

  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-800 bg-[#1A1A1A]',
        className
      )}
      data-testid="job-logs-viewer"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-gray-400" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-white">Job Logs</h3>
          </div>

          <ConnectionIndicator
            status={status}
            reconnectCount={reconnectCount}
            showLabel
            size="sm"
          />

          {logs.length > 0 && (
            <span className="text-xs text-gray-500">
              {filteredLogs.length === logs.length
                ? `${logs.length} logs`
                : `${filteredLogs.length} of ${logs.length} logs`}
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <LevelFilterDropdown value={levelFilter} onChange={setLevelFilter} />

          <button
            type="button"
            className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium',
              'bg-gray-800 border border-gray-700',
              'hover:bg-gray-700 hover:border-gray-600 transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900',
              autoScroll ? 'text-[#76B900]' : 'text-gray-400'
            )}
            onClick={handleToggleAutoScroll}
            aria-label="Toggle auto-scroll"
            aria-pressed={autoScroll}
          >
            <RefreshCw className={clsx('h-3.5 w-3.5', autoScroll && 'animate-spin')} />
            <span className="hidden sm:inline">Auto-scroll</span>
          </button>

          <button
            type="button"
            className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium',
              'bg-gray-800 border border-gray-700 text-gray-300',
              'hover:bg-gray-700 hover:border-gray-600 transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900',
              'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-gray-800 disabled:hover:border-gray-700'
            )}
            onClick={handleClearLogs}
            disabled={logs.length === 0}
            aria-label="Clear logs"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Clear</span>
          </button>
        </div>
      </div>

      {/* Log content */}
      <div
        ref={logContainerRef}
        className="overflow-y-auto"
        style={{ maxHeight: `${maxHeight}px` }}
        role="log"
        aria-live="polite"
        aria-label="Job log output"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <FileText className="h-8 w-8 text-gray-600 mb-3" aria-hidden="true" />
            <p className="text-sm text-gray-500">
              {logs.length === 0
                ? 'No logs available yet'
                : `No logs matching filter "${levelFilter}"`}
            </p>
            {enabled && logs.length === 0 && (
              <p className="text-xs text-gray-600 mt-1">Waiting for log entries...</p>
            )}
          </div>
        ) : (
          <div className="py-2">
            {filteredLogs.map((log, index) => (
              <LogEntryRow key={`${log.timestamp}-${index}`} log={log} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
