/**
 * useNetworkStatus hook
 *
 * Tracks browser network connectivity status with callbacks for online/offline transitions.
 * Useful for PWA offline detection and graceful degradation.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export interface UseNetworkStatusOptions {
  /** Callback when network comes back online */
  onOnline?: () => void;
  /** Callback when network goes offline */
  onOffline?: () => void;
}

export interface UseNetworkStatusReturn {
  /** True if browser is currently online */
  isOnline: boolean;
  /** True if browser is currently offline (convenience inverse of isOnline) */
  isOffline: boolean;
  /** Timestamp of the last time the browser was online */
  lastOnlineAt: Date | null;
  /** True if the browser was previously offline and has since reconnected */
  wasOffline: boolean;
  /** Clear the wasOffline flag (e.g., after showing a reconnection notification) */
  clearWasOffline: () => void;
}

/**
 * Hook to track browser network connectivity status.
 *
 * @example
 * ```tsx
 * const { isOnline, isOffline, wasOffline, clearWasOffline } = useNetworkStatus({
 *   onOnline: () => console.log('Back online!'),
 *   onOffline: () => console.log('Lost connection'),
 * });
 *
 * if (isOffline) {
 *   return <OfflineFallback />;
 * }
 *
 * if (wasOffline) {
 *   return (
 *     <>
 *       <ReconnectedBanner onDismiss={clearWasOffline} />
 *       <MainContent />
 *     </>
 *   );
 * }
 * ```
 */
export function useNetworkStatus(
  options: UseNetworkStatusOptions = {}
): UseNetworkStatusReturn {
  const { onOnline, onOffline } = options;

  // Initialize with current browser status
  const [isOnline, setIsOnline] = useState<boolean>(() => navigator.onLine);
  const [lastOnlineAt, setLastOnlineAt] = useState<Date | null>(() =>
    navigator.onLine ? new Date() : null
  );
  const [wasOffline, setWasOffline] = useState<boolean>(false);

  // Track if we've ever been offline during this hook's lifetime
  const hasBeenOffline = useRef<boolean>(!navigator.onLine);

  // Handler for online event
  const handleOnline = useCallback(() => {
    setIsOnline(true);
    setLastOnlineAt(new Date());

    // If we were offline before, set wasOffline flag
    if (hasBeenOffline.current) {
      setWasOffline(true);
    }

    onOnline?.();
  }, [onOnline]);

  // Handler for offline event
  const handleOffline = useCallback(() => {
    setIsOnline(false);
    hasBeenOffline.current = true;
    onOffline?.();
  }, [onOffline]);

  // Clear the wasOffline flag
  const clearWasOffline = useCallback(() => {
    setWasOffline(false);
  }, []);

  // Set up event listeners
  useEffect(() => {
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [handleOnline, handleOffline]);

  return {
    isOnline,
    isOffline: !isOnline,
    lastOnlineAt,
    wasOffline,
    clearWasOffline,
  };
}
