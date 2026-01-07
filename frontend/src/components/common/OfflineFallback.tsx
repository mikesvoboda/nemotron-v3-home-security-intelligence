/**
 * OfflineFallback component
 *
 * Displays a user-friendly message when the app is offline.
 * Can show cached event counts and provide retry functionality.
 */

import { WifiOff, RefreshCw, Database } from 'lucide-react';
import React, { useEffect, useCallback } from 'react';

export interface OfflineFallbackProps {
  /** Callback when retry button is clicked or when coming back online */
  onRetry?: () => void;
  /** Number of cached events available offline */
  cachedEventsCount?: number;
  /** Last time the app was online */
  lastOnlineAt?: Date | null;
  /** Visual variant */
  variant?: 'full-page' | 'compact';
  /** Whether to automatically retry when coming back online */
  autoRetryOnOnline?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format relative time (e.g., "5 minutes ago")
 */
function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  }
  if (diffHours > 0) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  }
  if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
  }
  return 'just now';
}

/**
 * Offline fallback component for PWA.
 *
 * @example
 * ```tsx
 * const { isOnline, lastOnlineAt } = useNetworkStatus();
 * const { cachedCount } = useCachedEvents();
 *
 * if (!isOnline) {
 *   return (
 *     <OfflineFallback
 *       cachedEventsCount={cachedCount}
 *       lastOnlineAt={lastOnlineAt}
 *       onRetry={() => window.location.reload()}
 *       autoRetryOnOnline
 *     />
 *   );
 * }
 * ```
 */
export default function OfflineFallback({
  onRetry,
  cachedEventsCount = 0,
  lastOnlineAt,
  variant = 'full-page',
  autoRetryOnOnline = true,
  className = '',
}: OfflineFallbackProps): React.ReactElement {
  // Auto-retry when coming back online
  const handleOnline = useCallback(() => {
    if (autoRetryOnOnline && onRetry) {
      onRetry();
    }
  }, [autoRetryOnOnline, onRetry]);

  useEffect(() => {
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [handleOnline]);

  const isFullPage = variant === 'full-page';

  return (
    <div
      data-testid="offline-fallback"
      role="alert"
      className={`
        ${isFullPage ? 'min-h-screen flex items-center justify-center' : ''}
        bg-gray-900 px-4 py-8
        ${className}
      `}
    >
      <div className="max-w-md w-full text-center">
        {/* Offline icon */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-gray-800">
          <WifiOff
            className="h-8 w-8 text-gray-400"
            aria-hidden="true"
          />
        </div>

        {/* Main message */}
        <h2 className="text-xl font-semibold text-white mb-2">
          You&apos;re Offline
        </h2>
        <p className="text-gray-400 mb-6">
          Your network connection is unavailable. Check your WiFi or mobile data settings.
        </p>

        {/* Last online time */}
        {lastOnlineAt && (
          <p className="text-sm text-gray-500 mb-4">
            Last online: {formatRelativeTime(lastOnlineAt)}
          </p>
        )}

        {/* Cached events info */}
        {cachedEventsCount > 0 && (
          <div className="mb-6 p-4 rounded-lg bg-gray-800/50 border border-gray-700">
            <div className="flex items-center justify-center gap-2 text-gray-300">
              <Database className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
              <span>
                <strong className="text-white">{cachedEventsCount}</strong> cached event{cachedEventsCount !== 1 ? 's' : ''} available
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              View recent security events while offline
            </p>
          </div>
        )}

        {/* Retry button */}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="
              inline-flex items-center gap-2
              rounded-lg bg-[#76B900] px-4 py-2
              text-sm font-medium text-black
              hover:bg-[#8BC34A] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900
              transition-colors
            "
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Try Again
          </button>
        )}

        {/* Helpful tips */}
        <div className="mt-8 text-left">
          <h3 className="text-sm font-medium text-gray-300 mb-3">
            Troubleshooting Tips:
          </h3>
          <ul className="text-sm text-gray-500 space-y-2">
            <li className="flex items-start gap-2">
              <span className="text-[#76B900]">1.</span>
              Check your WiFi or mobile data is enabled
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#76B900]">2.</span>
              Move closer to your router if signal is weak
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#76B900]">3.</span>
              Try restarting your router or device
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
