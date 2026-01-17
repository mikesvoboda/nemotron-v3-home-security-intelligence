/**
 * DebugModeToggle - Toggle component for enabling/disabling debug mode
 *
 * This component only renders when the backend has debug mode enabled (DEBUG=true).
 * The toggle state is persisted to localStorage and can be used by child components
 * to show/hide debug information.
 *
 * Features:
 * - Conditional rendering based on backend debug flag
 * - localStorage persistence
 * - Orange highlight when active
 * - Accessible toggle control with keyboard support
 *
 * @module components/system/DebugModeToggle
 */

import { Switch } from '@headlessui/react';
import { clsx } from 'clsx';
import { Wrench } from 'lucide-react';

import { useLocalStorage } from '../../hooks/useLocalStorage';
import { useSystemConfigQuery } from '../../hooks/useSystemConfigQuery';

/**
 * Props for the DebugModeToggle component
 */
export interface DebugModeToggleProps {
  /** Additional CSS classes */
  className?: string;
  /** Callback when debug mode state changes */
  onChange?: (enabled: boolean) => void;
}

/**
 * DebugModeToggle - A toggle switch for enabling debug mode
 *
 * Only renders when the backend has DEBUG=true in its configuration.
 * When enabled, displays an orange highlight to indicate debug mode is active.
 *
 * @example
 * ```tsx
 * // In the System Monitoring page header:
 * <div className="flex items-center gap-4">
 *   <TimeRangeSelector ... />
 *   <DebugModeToggle onChange={(enabled) => console.log('Debug:', enabled)} />
 * </div>
 * ```
 */
export default function DebugModeToggle({
  className,
  onChange,
}: DebugModeToggleProps) {
  const { debugEnabled, isLoading, error, data } = useSystemConfigQuery();
  const [debugMode, setDebugMode] = useLocalStorage('system-debug-mode', false);

  // Don't render if:
  // - Loading
  // - Error fetching config
  // - Backend debug is disabled
  // - Config data is undefined
  if (isLoading || error || !debugEnabled || !data) {
    return null;
  }

  const handleToggle = (checked: boolean) => {
    setDebugMode(checked);
    onChange?.(checked);
  };

  return (
    <div
      data-testid="debug-mode-toggle"
      className={clsx(
        'flex items-center gap-2 rounded-lg border px-3 py-1.5 transition-all',
        debugMode
          ? 'border-orange-500/50 bg-orange-500/10'
          : 'border-gray-700 bg-gray-800/50',
        className
      )}
    >
      <Wrench
        data-testid="debug-mode-icon"
        className={clsx(
          'h-4 w-4',
          debugMode ? 'text-orange-400' : 'text-gray-400'
        )}
      />
      <span
        className={clsx(
          'text-sm font-medium',
          debugMode ? 'text-orange-300' : 'text-gray-300'
        )}
      >
        Debug Mode
      </span>
      <Switch
        checked={debugMode}
        onChange={handleToggle}
        aria-label="Toggle debug mode"
        className={clsx(
          'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-gray-900',
          debugMode ? 'bg-orange-500' : 'bg-gray-600'
        )}
      >
        <span
          className={clsx(
            'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
            debugMode ? 'translate-x-5' : 'translate-x-1'
          )}
        />
      </Switch>
    </div>
  );
}
