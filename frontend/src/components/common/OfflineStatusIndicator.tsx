/**
 * OfflineStatusIndicator component
 *
 * A connected component that combines useNetworkStatus and useCachedEvents hooks
 * with the OfflineIndicator component.
 *
 * @module OfflineStatusIndicator
 * @see NEM-3675 - PWA Offline Caching
 */

import React, { useCallback } from 'react';

import OfflineIndicator, { type OfflineIndicatorProps } from './OfflineIndicator';
import { useCachedEvents } from '../../hooks/useCachedEvents';
import { useNetworkStatus } from '../../hooks/useNetworkStatus';

export interface OfflineStatusIndicatorProps
  extends Omit<OfflineIndicatorProps, 'isOffline' | 'cachedEventsCount' | 'lastOnlineAt'> {
  reloadOnRetry?: boolean;
}

export default function OfflineStatusIndicator({
  reloadOnRetry = false,
  onRetry,
  ...rest
}: OfflineStatusIndicatorProps): React.ReactElement {
  const { isOffline, lastOnlineAt } = useNetworkStatus();
  const { cachedCount } = useCachedEvents();

  const handleRetry = useCallback(() => {
    if (onRetry) {
      onRetry();
    }
    if (reloadOnRetry) {
      window.location.reload();
    }
  }, [onRetry, reloadOnRetry]);

  return (
    <OfflineIndicator
      isOffline={isOffline}
      cachedEventsCount={cachedCount}
      lastOnlineAt={lastOnlineAt}
      onRetry={reloadOnRetry || onRetry ? handleRetry : undefined}
      {...rest}
    />
  );
}
