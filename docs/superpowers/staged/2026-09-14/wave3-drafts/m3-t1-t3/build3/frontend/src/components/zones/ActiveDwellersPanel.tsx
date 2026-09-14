/**
 * ActiveDwellersPanel - Panel showing active dwellers in a zone (NEM-4714)
 *
 * Displays a real-time list of entities currently dwelling in a polygon zone.
 * Features:
 * - Live timer updates showing current dwell duration
 * - WebSocket connection status indicator (Live/Polling)
 * - Object type icons (person/vehicle)
 * - Loading and empty states
 *
 * Part of Phase 2C: Active Dwellers Panel with WebSocket.
 *
 * @module components/zones/ActiveDwellersPanel
 */

import { clsx } from 'clsx';
import { Clock, User, Car, Wifi, WifiOff } from 'lucide-react';
import { memo, useEffect, useState } from 'react';

import type { ActiveDweller } from '../../hooks/useDwellTimeAnalytics';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ActiveDwellersPanel component.
 */
export interface ActiveDwellersPanelProps {
  /** List of active dwellers in the zone */
  dwellers: ActiveDweller[];
  /** Whether data is loading */
  isLoading?: boolean;
  /** WebSocket connection status */
  isConnected?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format dwell time as a live counter display (M:SS format).
 *
 * @param currentSeconds - Current dwell duration in seconds
 * @returns Formatted time string like "5:30"
 */
function formatLiveDwell(currentSeconds: number): string {
  const mins = Math.floor(currentSeconds / 60);
  const secs = currentSeconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Get the appropriate icon component for an object class.
 *
 * @param objectClass - Object class string (person, car, truck, etc.)
 * @returns Lucide icon component
 */
function getObjectIcon(objectClass: string) {
  const vehicleClasses = ['car', 'truck', 'vehicle', 'bus', 'motorcycle'];
  if (vehicleClasses.includes(objectClass.toLowerCase())) {
    return Car;
  }
  return User;
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ActiveDwellersPanel displays real-time active dwellers in a zone.
 *
 * Shows a list of entities currently in the zone with live-updating
 * dwell time counters and connection status indicator.
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <ActiveDwellersPanel
 *   dwellers={dwellersData}
 *   isLoading={false}
 *   isConnected={true}
 * />
 * ```
 */
function ActiveDwellersPanelComponent({
  dwellers,
  isLoading = false,
  isConnected = false,
  className,
}: ActiveDwellersPanelProps) {
  // Live timer update - tick every second to force re-render for live dwell times
  const [, setTick] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-4', className)}
        data-testid="active-dwellers-panel"
      >
        <div className="flex h-32 items-center justify-center" data-testid="loading-state">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-4', className)}
      data-testid="active-dwellers-panel"
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-medium text-white">
          <Clock className="h-4 w-4 text-primary" aria-hidden="true" />
          Active Dwellers
          <span
            className="rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary"
            data-testid="dweller-count"
          >
            {dwellers.length}
          </span>
        </h3>

        {/* Connection status indicator */}
        <div
          className={clsx(
            'flex items-center gap-1 text-xs',
            isConnected ? 'text-green-400' : 'text-gray-500'
          )}
          data-testid="connection-status"
        >
          {isConnected ? (
            <>
              <Wifi className="h-3 w-3" aria-hidden="true" />
              <span>Live</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3" aria-hidden="true" />
              <span>Polling</span>
            </>
          )}
        </div>
      </div>

      {/* Dweller list or empty state */}
      {dwellers.length === 0 ? (
        <p className="py-4 text-center text-sm text-gray-400" data-testid="empty-state">
          No active dwellers in this zone
        </p>
      ) : (
        <div className="space-y-2" data-testid="dweller-list">
          {dwellers.map((dweller) => {
            const Icon = getObjectIcon(dweller.object_class);
            // Calculate live dwell time from entry_time
            const entryDate = new Date(dweller.entry_time);
            const now = new Date();
            const liveSeconds = Math.floor((now.getTime() - entryDate.getTime()) / 1000);

            return (
              <div
                key={dweller.record_id}
                className="flex items-center justify-between rounded-md bg-gray-700/50 px-3 py-2"
                data-testid={`dweller-${dweller.record_id}`}
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-gray-400" aria-hidden="true" />
                  <span className="text-sm capitalize text-gray-200">{dweller.object_class}</span>
                </div>
                <span className="font-mono text-sm text-primary" data-testid="dwell-time">
                  {formatLiveDwell(liveSeconds)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Memoized ActiveDwellersPanel for performance.
 */
export const ActiveDwellersPanel = memo(ActiveDwellersPanelComponent);

export default ActiveDwellersPanel;
