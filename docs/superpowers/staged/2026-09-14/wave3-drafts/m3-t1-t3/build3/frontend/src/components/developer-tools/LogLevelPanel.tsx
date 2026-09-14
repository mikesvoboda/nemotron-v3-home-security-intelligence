/**
 * LogLevelPanel - Displays and allows changing the application log level
 *
 * This component shows the current log level and provides buttons to change it.
 * Shows a warning when DEBUG is selected due to performance impact.
 * Notes that changes don't persist on server restart.
 */
import { Callout } from '@tremor/react';
import { AlertTriangle, Loader2, Info, RefreshCw } from 'lucide-react';
import { useCallback } from 'react';

import { useLogLevelQuery } from '../../hooks/useLogLevelQuery';
import { useSetLogLevelMutation, type LogLevel } from '../../hooks/useSetLogLevelMutation';
import { useToast } from '../../hooks/useToast';

// ============================================================================
// Constants
// ============================================================================

const LOG_LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

// ============================================================================
// Types
// ============================================================================

/** Props for LogLevelPanel (currently none, reserved for future use) */
export interface LogLevelPanelProps {
  /** Optional className for additional styling */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export default function LogLevelPanel(_props: LogLevelPanelProps = {}) {
  const { currentLevel, isLoading, error, refetch } = useLogLevelQuery();
  const { setLevel, isPending, error: setError, reset } = useSetLogLevelMutation();
  const { success, error: toastError } = useToast();

  const handleLevelChange = useCallback(
    async (level: LogLevel) => {
      // Don't do anything if clicking current level
      if (level === currentLevel) return;

      try {
        reset(); // Clear any previous error
        await setLevel(level);
        success('Log level changed to ' + level);
        // Refetch to confirm the change
        await refetch();
      } catch {
        toastError('Failed to change log level');
      }
    },
    [currentLevel, setLevel, success, toastError, refetch, reset]
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Log Level Adjuster</h3>
        <div className="flex items-center justify-center py-8" data-testid="log-level-loading">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-400">Loading log level...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
        <h3 className="mb-4 text-lg font-semibold text-white">Log Level Adjuster</h3>
        <div
          className="flex items-center gap-2 rounded bg-red-500/10 px-4 py-3 text-red-400"
          data-testid="log-level-error"
        >
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load log level: {error.message}</span>
          <button
            onClick={() => void refetch()}
            className="ml-auto text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Log Level Adjuster</h3>
        {isPending && (
          <span
            className="flex items-center gap-1 text-sm text-gray-400"
            data-testid="log-level-changing"
          >
            <RefreshCw className="h-4 w-4 animate-spin" />
            Changing...
          </span>
        )}
      </div>

      {/* Current Level Display */}
      <div className="mb-4">
        <span className="text-sm text-gray-400">Current Level: </span>
        <span className="font-mono font-semibold text-[#76B900]">{currentLevel}</span>
      </div>

      {/* Level Buttons */}
      <div className="mb-4 flex flex-wrap gap-2">
        {LOG_LEVELS.map((level) => {
          const isActive = level === currentLevel;
          return (
            <button
              key={level}
              onClick={() => void handleLevelChange(level)}
              disabled={isPending || isActive}
              data-active={isActive ? 'true' : undefined}
              className={[
                'rounded px-4 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-[#76B900] text-black'
                  : 'bg-gray-700 text-gray-200 hover:bg-gray-600 disabled:opacity-50',
              ].join(' ')}
            >
              {level}
            </button>
          );
        })}
      </div>

      {/* Set Error Message */}
      {setError && (
        <div
          className="mb-4 flex items-center gap-2 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400"
          data-testid="log-level-set-error"
        >
          <AlertTriangle className="h-4 w-4" />
          <span>Failed to set log level: {setError.message}</span>
        </div>
      )}

      {/* DEBUG Warning */}
      {currentLevel === 'DEBUG' && (
        <Callout
          title="Performance Warning"
          icon={AlertTriangle}
          color="yellow"
          className="mb-4"
          data-testid="debug-warning"
        >
          <span className="text-sm">
            DEBUG logging is enabled. This may impact performance due to increased log output.
            Consider using INFO or higher for production workloads.
          </span>
        </Callout>
      )}

      {/* Persistence Note */}
      <div className="flex items-start gap-2 rounded border border-gray-700 bg-gray-800/30 px-3 py-2 text-sm text-gray-400">
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <span>
          Log level changes do <strong className="text-gray-300">not persist</strong> on server
          restart. The level will revert to the configured default.
        </span>
      </div>
    </div>
  );
}
