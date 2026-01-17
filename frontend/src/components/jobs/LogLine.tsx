import { memo } from 'react';

import type { JobLogEntryResponse } from '../../types/generated';

/**
 * Props for the LogLine component.
 */
export interface LogLineProps {
  /** The log entry to display */
  log: JobLogEntryResponse;
}

/**
 * Returns the CSS class for log level text color.
 *
 * @param level - Log level string (DEBUG, INFO, WARN, ERROR)
 * @returns Tailwind CSS class for the log level color
 */
function getLevelColorClass(level: string): string {
  switch (level.toUpperCase()) {
    case 'DEBUG':
      return 'text-gray-500';
    case 'INFO':
      return 'text-white';
    case 'WARN':
      return 'text-yellow-400';
    case 'ERROR':
      return 'text-red-400';
    default:
      return 'text-gray-400';
  }
}

/**
 * Formats a timestamp string to show the time portion.
 *
 * @param timestamp - ISO 8601 timestamp string
 * @returns Formatted time string (HH:MM:SS)
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      return timestamp;
    }
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return timestamp;
  }
}

/**
 * Displays a single log line with timestamp, level, and message.
 *
 * Log levels are color-coded for quick visual scanning:
 * - DEBUG: Gray
 * - INFO: White
 * - WARN: Yellow
 * - ERROR: Red
 *
 * @param props - Component props
 * @returns A single log line component
 *
 * @example
 * <LogLine log={{
 *   timestamp: '2024-01-15T10:30:00Z',
 *   level: 'INFO',
 *   message: 'Starting export job',
 *   attempt_number: 1,
 *   context: null,
 * }} />
 */
const LogLine = memo(function LogLine({ log }: LogLineProps) {
  const { timestamp, level, message, attempt_number, context } = log;
  const levelColorClass = getLevelColorClass(level);
  const formattedTime = formatTimestamp(timestamp);

  return (
    <li
      className="flex items-start gap-3 py-0.5 font-mono text-sm leading-relaxed hover:bg-white/5"
    >
      {/* Timestamp */}
      <span
        data-testid="log-timestamp"
        className="shrink-0 text-gray-500"
        title={timestamp}
      >
        {formattedTime}
      </span>

      {/* Level badge */}
      <span
        className={`shrink-0 w-12 font-semibold ${levelColorClass}`}
      >
        {level}
      </span>

      {/* Message and context */}
      <span className="flex-1 text-gray-300">
        {message}

        {/* Show attempt number for retries */}
        {attempt_number > 1 && (
          <span className="ml-2 text-xs text-gray-500">
            (attempt {attempt_number})
          </span>
        )}

        {/* Context indicator */}
        {context && (
          <span
            data-testid="log-context"
            className="ml-2 text-xs text-blue-400 cursor-help"
            title={JSON.stringify(context, null, 2)}
          >
            [+context]
          </span>
        )}
      </span>
    </li>
  );
});

export default LogLine;
