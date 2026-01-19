import { AlertCircle, AlertTriangle, Activity } from 'lucide-react';
import { useMemo } from 'react';

import type { LogEntry } from './LogsTable';

export interface LogStatsSummaryProps {
  logs: LogEntry[];
  className?: string;
}

/**
 * LogStatsSummary displays a compact summary of log statistics for the last hour.
 * Shows counts of errors, warnings, and total logs with corresponding icons.
 *
 * @param logs - Array of log entries to analyze
 * @param className - Optional additional CSS classes
 */
export default function LogStatsSummary({ logs, className = '' }: LogStatsSummaryProps) {
  // Calculate stats for logs in the last hour
  const stats = useMemo(() => {
    const oneHourAgo = Date.now() - 60 * 60 * 1000;

    const logsInLastHour = logs.filter((log) => {
      const logTime = new Date(log.timestamp).getTime();
      return logTime >= oneHourAgo;
    });

    const errors = logsInLastHour.filter(
      (log) => log.level === 'ERROR' || log.level === 'CRITICAL'
    ).length;
    const warnings = logsInLastHour.filter((log) => log.level === 'WARNING').length;
    const total = logsInLastHour.length;

    return { errors, warnings, total };
  }, [logs]);

  return (
    <div
      className={`flex items-center gap-6 rounded-lg border border-gray-800 bg-[#1F1F1F] px-4 py-2 ${className}`}
    >
      <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Last hour</span>

      {/* Errors */}
      <div className="flex items-center gap-2">
        <AlertCircle className="h-4 w-4 text-red-500" />
        <span className="text-sm font-semibold text-red-500">{stats.errors}</span>
        <span className="text-xs text-gray-400">Errors</span>
      </div>

      {/* Warnings */}
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-yellow-500" />
        <span className="text-sm font-semibold text-yellow-500">{stats.warnings}</span>
        <span className="text-xs text-gray-400">Warnings</span>
      </div>

      {/* Total */}
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-gray-400" />
        <span className="text-sm font-semibold text-gray-300">{stats.total}</span>
        <span className="text-xs text-gray-400">Total</span>
      </div>
    </div>
  );
}
