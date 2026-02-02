/**
 * RecentThreatsIndicator - Compact header widget showing recent threat detections
 *
 * This component displays a badge with the count of recent threats and provides
 * a dropdown list with details about each threat. It integrates with WebSocket
 * for real-time updates.
 *
 * @module components/dashboard/RecentThreatsIndicator
 */

import { clsx } from 'clsx';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { forwardRef, useCallback, useEffect, useId, useRef, useState } from 'react';

import type { RecentThreat, RecentThreatsIndicatorProps } from '@/types/threat';

import { useRecentThreats } from '@/hooks/useRecentThreats';

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_VISIBLE = 5;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a timestamp to relative time (e.g., "5 min ago", "1 hour ago")
 */
function formatTimeAgo(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      return timestamp;
    }

    const now = Date.now();
    const diffMs = now - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffSeconds < 60) {
      return 'Just now';
    }
    if (diffMinutes === 1) {
      return '1 min ago';
    }
    if (diffMinutes < 60) {
      return `${diffMinutes} min ago`;
    }
    if (diffHours === 1) {
      return '1 hour ago';
    }
    return `${diffHours} hours ago`;
  } catch {
    return timestamp;
  }
}

/**
 * Format weapon type for display (capitalize first letter)
 */
function formatWeaponType(weaponType: string | undefined): string {
  if (!weaponType) {
    return 'Unknown';
  }
  return weaponType.charAt(0).toUpperCase() + weaponType.slice(1).toLowerCase();
}

// ============================================================================
// Component
// ============================================================================

/**
 * RecentThreatsIndicator displays a compact widget with recent threat count
 * and a dropdown list of threats with real-time WebSocket updates.
 */
export default function RecentThreatsIndicator({
  onThreatClick,
  maxVisible = DEFAULT_MAX_VISIBLE,
  className,
}: RecentThreatsIndicatorProps) {
  // Generate unique IDs for accessibility
  const dropdownId = useId();
  const dropdownIdWithPrefix = `threats-dropdown-${dropdownId}`;

  // Component state
  const [isOpen, setIsOpen] = useState(false);
  const [wasNewThreatOnOpen, setWasNewThreatOnOpen] = useState(false);

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  // Hook for recent threats with WebSocket
  const hookResult = useRecentThreats({
    maxAgeHours: 24,
    onNewThreat: () => {
      // Callback is handled by the hook's hasNewThreat flag
    },
  });

  const { threats, count, isConnected, hasNewThreat, clearNewThreatFlag } = hookResult;

  // Check for loading state (initial load with no threats and connected)
  const isLoading = 'isLoading' in hookResult && (hookResult as { isLoading?: boolean }).isLoading;

  // Determine visible threats
  const visibleThreats = threats.slice(0, maxVisible);
  const hasMoreThreats = threats.length > maxVisible;

  // Toggle dropdown
  const toggleDropdown = useCallback(() => {
    setIsOpen((prev) => {
      const newValue = !prev;
      if (newValue) {
        // Opening dropdown
        setWasNewThreatOnOpen(hasNewThreat);
        clearNewThreatFlag();
      }
      return newValue;
    });
  }, [hasNewThreat, clearNewThreatFlag]);

  // Handle threat item click
  const handleThreatClick = useCallback(
    (eventId: string) => {
      onThreatClick?.(eventId);
      setIsOpen(false);
    },
    [onThreatClick]
  );

  // Handle keyboard activation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleDropdown();
      }
    },
    [toggleDropdown]
  );

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Handle Escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  // Note: Focus is managed by Tab key navigation, not auto-focus
  // This allows users to Tab into the dropdown from the indicator

  // Render loading state
  if (isLoading) {
    return (
      <div className={clsx('relative', className)}>
        <div data-testid="threats-loading" className="flex items-center gap-2 px-3 py-2">
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={clsx('relative', className)}>
      {/* Indicator Button */}
      <div
        data-testid="threats-indicator"
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        aria-controls={dropdownIdWithPrefix}
        aria-label={`Recent threats indicator: ${count} ${count === 1 ? 'threat' : 'threats'}`}
        onClick={toggleDropdown}
        onKeyDown={handleKeyDown}
        className={clsx(
          'flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 transition-colors',
          'hover:bg-gray-800',
          count > 0 ? 'text-red-600' : 'text-gray-400',
          hasNewThreat && 'animate-pulse'
        )}
      >
        {/* Icon */}
        <ShieldAlert className="h-5 w-5" />

        {/* Count Badge */}
        {count > 0 ? (
          <>
            <span data-testid="threats-count-badge" className="font-semibold">
              {count}
            </span>
            <span>{count === 1 ? '1 threat' : `${count} threats`}</span>
          </>
        ) : (
          <span>No threats</span>
        )}

        {/* Connection Indicator */}
        <span
          data-testid="connection-indicator"
          title={isConnected ? 'Connected' : 'Disconnected'}
          className={clsx(
            'ml-1 h-2 w-2 rounded-full',
            isConnected ? 'bg-green-500' : 'bg-red-500'
          )}
        />
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div
          id={dropdownIdWithPrefix}
          data-testid="threats-dropdown"
          role="menu"
          className={clsx(
            'absolute right-0 top-full z-50 mt-2 w-80 rounded-lg border border-gray-700 bg-gray-900 shadow-xl',
            'max-h-96 overflow-y-auto'
          )}
        >
          {threats.length === 0 ? (
            /* Empty State */
            <div className="px-4 py-6 text-center text-gray-400">
              <ShieldAlert className="mx-auto mb-2 h-8 w-8 text-gray-600" />
              <p>No recent threats</p>
              <p className="mt-1 text-sm text-gray-500">Last 24 hours</p>
            </div>
          ) : (
            /* Threat List */
            <div className="divide-y divide-gray-800">
              {visibleThreats.map((threat, index) => (
                <ThreatItem
                  key={threat.id}
                  ref={index === 0 ? firstItemRef : undefined}
                  threat={threat}
                  isNew={index === 0 && wasNewThreatOnOpen}
                  onClick={handleThreatClick}
                />
              ))}
            </div>
          )}

          {/* View All Link */}
          {hasMoreThreats && (
            <div className="border-t border-gray-800 px-4 py-3">
              <button
                className="w-full text-center text-sm text-blue-400 hover:text-blue-300"
                onClick={() => setIsOpen(false)}
              >
                View all {count} threats
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Subcomponent: ThreatItem
// ============================================================================

interface ThreatItemProps {
  threat: RecentThreat;
  isNew: boolean;
  onClick: (eventId: string) => void;
}

const ThreatItem = forwardRef<HTMLButtonElement, ThreatItemProps>(
  function ThreatItem({ threat, isNew, onClick }, ref) {
    return (
      <button
        ref={ref}
        data-testid={`threat-item-${threat.id}`}
        role="menuitem"
        tabIndex={0}
        onClick={() => onClick(threat.eventId)}
        className={clsx(
          'flex w-full items-start gap-3 px-4 py-3 text-left transition-colors',
          'hover:bg-gray-800 focus:bg-gray-800 focus:outline-none',
          isNew && 'bg-red-50'
        )}
      >
        {/* Threat Icon */}
        <div className="mt-0.5 flex-shrink-0">
          <ShieldAlert className="h-5 w-5 text-red-500" />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Weapon Type */}
          <p className="font-medium text-white">
            {formatWeaponType(threat.weaponType)}
          </p>

          {/* Camera Name */}
          <p className="text-sm text-gray-400">{threat.cameraName || 'Unknown camera'}</p>

          {/* Time */}
          <p className="mt-1 text-xs text-gray-500">{formatTimeAgo(threat.timestamp)}</p>
        </div>
      </button>
    );
  }
);
