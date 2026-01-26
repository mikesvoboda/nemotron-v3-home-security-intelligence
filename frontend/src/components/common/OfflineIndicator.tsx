/**
 * OfflineIndicator component
 *
 * A compact offline status indicator with multiple variants:
 * - banner: Full-width banner at top/bottom of screen
 * - badge: Small floating badge
 * - minimal: Icon-only indicator
 *
 * @module OfflineIndicator
 * @see NEM-3675 - PWA Offline Caching
 */

import React, { useState, useEffect, useCallback } from 'react';

export type OfflineIndicatorPosition =
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'top'
  | 'bottom';

export type OfflineIndicatorVariant = 'banner' | 'badge' | 'minimal';

export interface OfflineIndicatorProps {
  /** Whether the app is currently offline */
  isOffline: boolean;
  /** Number of events cached for sync */
  cachedEventsCount?: number;
  /** When the app was last online */
  lastOnlineAt?: Date | null;
  /** Position of the indicator */
  position?: OfflineIndicatorPosition;
  /** Visual variant */
  variant?: OfflineIndicatorVariant;
  /** Whether the indicator can be dismissed */
  dismissible?: boolean;
  /** Callback when dismissed */
  onDismiss?: () => void;
  /** Callback when retry is clicked */
  onRetry?: () => void;
  /** Additional CSS classes */
  className?: string;
  /** Whether to show the indicator (can be controlled externally) */
  show?: boolean;
}

/**
 * Formats the duration since last online
 * @param lastOnlineAt - The Date when the app was last online
 * @returns Formatted duration string
 */
function formatOfflineDuration(lastOnlineAt: Date | null | undefined): string {
  if (!lastOnlineAt) {
    return 'Unknown duration';
  }

  const now = new Date();
  const diffMs = now.getTime() - lastOnlineAt.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffSeconds < 60) {
    return 'Just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  } else {
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  }
}

/**
 * Gets position classes for the indicator
 */
function getPositionClasses(position: OfflineIndicatorPosition): string {
  const baseClasses = 'fixed z-50';
  const positionMap: Record<OfflineIndicatorPosition, string> = {
    'top-left': 'top-4 left-4',
    'top-right': 'top-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'bottom-right': 'bottom-4 right-4',
    top: 'top-0 left-0 right-0',
    bottom: 'bottom-0 left-0 right-0',
  };
  return `${baseClasses} ${positionMap[position]}`;
}

/**
 * Gets variant classes for the indicator
 */
function getVariantClasses(variant: OfflineIndicatorVariant): string {
  const variantMap: Record<OfflineIndicatorVariant, string> = {
    banner:
      'bg-amber-500 dark:bg-amber-600 text-white px-4 py-3 shadow-lg flex items-center justify-between gap-4',
    badge:
      'bg-amber-500 dark:bg-amber-600 text-white px-3 py-2 rounded-lg shadow-lg flex items-center gap-2',
    minimal:
      'bg-amber-500 dark:bg-amber-600 text-white p-2 rounded-full shadow-lg',
  };
  return variantMap[variant];
}

/**
 * OfflineIndicator - A compact offline status indicator
 *
 * Displays current offline status with optional:
 * - Cached events count
 * - Time since last online
 * - Retry button
 * - Dismiss functionality
 */
export default function OfflineIndicator({
  isOffline,
  cachedEventsCount = 0,
  lastOnlineAt,
  position = 'bottom-left',
  variant = 'banner',
  dismissible = false,
  onDismiss,
  onRetry,
  className = '',
  show,
}: OfflineIndicatorProps): React.ReactElement | null {
  const [dismissed, setDismissed] = useState(false);
  const [offlineDuration, setOfflineDuration] = useState(() =>
    formatOfflineDuration(lastOnlineAt)
  );

  // Update offline duration every minute
  useEffect(() => {
    if (!isOffline || !lastOnlineAt) return;

    const interval = setInterval(() => {
      setOfflineDuration(formatOfflineDuration(lastOnlineAt));
    }, 60000);

    return () => clearInterval(interval);
  }, [isOffline, lastOnlineAt]);

  // Reset dismissed state when coming back online
  useEffect(() => {
    if (!isOffline) {
      setDismissed(false);
    }
  }, [isOffline]);

  const handleDismiss = useCallback(() => {
    setDismissed(true);
    onDismiss?.();
  }, [onDismiss]);

  // Determine visibility
  const shouldShow = show !== undefined ? show : isOffline;
  if (!shouldShow || dismissed) {
    return null;
  }

  const positionClasses = getPositionClasses(position);
  const variantClasses = getVariantClasses(variant);

  // Minimal variant - just an icon
  if (variant === 'minimal') {
    return (
      <div
        className={`${positionClasses} ${variantClasses} ${className}`}
        role="status"
        aria-live="polite"
        aria-label="Offline"
        data-testid="offline-indicator"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3"
          />
        </svg>
      </div>
    );
  }

  // Badge variant - compact with essential info
  if (variant === 'badge') {
    return (
      <div
        className={`${positionClasses} ${variantClasses} ${className}`}
        role="status"
        aria-live="polite"
        data-testid="offline-indicator"
      >
        <svg
          className="w-4 h-4 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3"
          />
        </svg>
        <span className="text-sm font-medium">Offline</span>
        {cachedEventsCount > 0 && (
          <span
            className="bg-white/20 px-1.5 py-0.5 rounded text-xs"
            aria-label={`${cachedEventsCount} cached events`}
          >
            {cachedEventsCount}
          </span>
        )}
        {onRetry && (
          <button
            onClick={onRetry}
            className="ml-1 p-1 hover:bg-white/20 rounded transition-colors"
            aria-label="Retry connection"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
        )}
      </div>
    );
  }

  // Banner variant - full information
  return (
    <div
      className={`${positionClasses} ${variantClasses} ${className}`}
      role="alert"
      aria-live="assertive"
      data-testid="offline-indicator"
    >
      <div className="flex items-center gap-3">
        <svg
          className="w-5 h-5 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3"
          />
        </svg>
        <div className="flex flex-col">
          <span className="font-medium">Offline Mode</span>
          <span className="text-sm text-white/80">
            Last online: {offlineDuration}
            {cachedEventsCount > 0 && ` | ${cachedEventsCount} events cached`}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-3 py-1 bg-white/20 hover:bg-white/30 rounded text-sm font-medium transition-colors"
            aria-label="Retry connection"
          >
            Retry
          </button>
        )}
        {dismissible && (
          <button
            onClick={handleDismiss}
            className="p-1 hover:bg-white/20 rounded transition-colors"
            aria-label="Dismiss offline notification"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
