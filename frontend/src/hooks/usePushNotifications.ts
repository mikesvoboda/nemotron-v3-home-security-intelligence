/**
 * usePushNotifications hook
 *
 * Manages browser push notification permissions and displays notifications.
 * Useful for PWA security alerts when important events are detected.
 */

import { useState, useCallback, useEffect } from 'react';

export interface SecurityAlertOptions {
  /** Camera name/identifier */
  camera: string;
  /** Risk level of the detection */
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  /** Brief summary of what was detected */
  summary: string;
  /** Optional event ID for deduplication */
  eventId?: string;
}

export interface UsePushNotificationsOptions {
  /**
   * Whether push notifications are enabled
   * @default true
   */
  enabled?: boolean;
  /**
   * Risk levels that should trigger push notifications
   * If provided, only alerts with matching risk levels will show
   */
  riskFilters?: string[];
}

export interface UsePushNotificationsReturn {
  /** Current notification permission state */
  permission: NotificationPermission;
  /** Whether notifications are supported in this browser */
  isSupported: boolean;
  /** Whether user has granted notification permission */
  hasPermission: boolean;
  /** Whether user has interacted with the permission prompt (granted or denied) */
  hasInteracted: boolean;
  /** Whether we have an active push subscription */
  isSubscribed: boolean;
  /** Whether push notifications are enabled via preferences */
  isEnabled: boolean;
  /** Enable or disable push notifications */
  setEnabled: (enabled: boolean) => void;
  /** Request notification permission from user */
  requestPermission: () => Promise<NotificationPermission>;
  /** Show a notification (requires permission) */
  showNotification: (title: string, options?: NotificationOptions) => Promise<void>;
  /** Convenience method to show a security alert notification */
  showSecurityAlert: (options: SecurityAlertOptions) => Promise<void>;
}

/**
 * Get the appropriate icon based on risk level
 */
function getRiskIcon(riskLevel: string): string {
  switch (riskLevel) {
    case 'critical':
    case 'high':
      return '/icons/badge-72.png';
    default:
      return '/icons/icon-192.png';
  }
}

/**
 * Get title prefix based on risk level
 */
function getRiskPrefix(riskLevel: string): string {
  switch (riskLevel) {
    case 'critical':
      return '[CRITICAL]';
    case 'high':
      return '[HIGH]';
    case 'medium':
      return '[MEDIUM]';
    default:
      return '[LOW]';
  }
}

/**
 * Hook to manage push notifications for security alerts.
 *
 * @example
 * ```tsx
 * const { permission, requestPermission, showSecurityAlert, hasPermission } = usePushNotifications();
 *
 * // Request permission on button click
 * const handleEnableNotifications = async () => {
 *   await requestPermission();
 * };
 *
 * // Show security alert when event is received
 * useEffect(() => {
 *   if (newEvent && hasPermission) {
 *     showSecurityAlert({
 *       camera: newEvent.camera_id,
 *       riskLevel: newEvent.risk_level,
 *       summary: newEvent.summary,
 *     });
 *   }
 * }, [newEvent, hasPermission, showSecurityAlert]);
 * ```
 */
export function usePushNotifications(
  options: UsePushNotificationsOptions = {}
): UsePushNotificationsReturn {
  const { enabled: initialEnabled = true, riskFilters } = options;

  const [permission, setPermission] = useState<NotificationPermission>(() => {
    if (typeof Notification !== 'undefined') {
      return Notification.permission;
    }
    return 'denied';
  });

  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isEnabled, setIsEnabled] = useState(initialEnabled);

  // Update enabled state when option changes
  useEffect(() => {
    setIsEnabled(initialEnabled);
  }, [initialEnabled]);

  // Check if notifications are supported
  const isSupported = typeof Notification !== 'undefined';

  // Whether user has granted permission
  const hasPermission = permission === 'granted';

  // Whether user has interacted with the prompt
  const hasInteracted = permission !== 'default';

  // Check for existing subscription on mount
  useEffect(() => {
    if (!isSupported) return;

    const checkSubscription = async () => {
      if ('serviceWorker' in navigator) {
        try {
          const registration = await navigator.serviceWorker.ready;
          const subscription = await registration.pushManager.getSubscription();
          setIsSubscribed(subscription !== null);
        } catch {
          // Service worker not available
          setIsSubscribed(false);
        }
      }
    };

    void checkSubscription();
  }, [isSupported]);

  /**
   * Request notification permission from user
   */
  const requestPermission = useCallback(async (): Promise<NotificationPermission> => {
    if (!isSupported) {
      return 'denied';
    }

    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      return result;
    } catch {
      // Some browsers throw on requestPermission
      setPermission('denied');
      return 'denied';
    }
  }, [isSupported]);

  /**
   * Show a notification (requires permission)
   */
  const showNotification = useCallback(
    async (title: string, options?: NotificationOptions): Promise<void> => {
      if (!isSupported || permission !== 'granted' || !isEnabled) {
        return;
      }

      try {
        // Use service worker notification if available for better reliability
        if ('serviceWorker' in navigator) {
          try {
            const registration = await navigator.serviceWorker.ready;
            await registration.showNotification(title, options);
            return;
          } catch {
            // Fall back to regular notification
          }
        }

        // Fall back to regular Notification API
        new Notification(title, options);
      } catch {
        // Notification failed - silently ignore
      }
    },
    [isSupported, permission, isEnabled]
  );

  /**
   * Show a security alert notification
   */
  const showSecurityAlert = useCallback(
    async (alertOpts: SecurityAlertOptions): Promise<void> => {
      const { camera, riskLevel, summary, eventId } = alertOpts;

      // Check if this risk level is in the filters (if filters are specified)
      if (riskFilters && riskFilters.length > 0 && !riskFilters.includes(riskLevel)) {
        return;
      }

      const title = `${getRiskPrefix(riskLevel)} ${camera}`;
      const notificationOptions: NotificationOptions = {
        body: summary,
        icon: getRiskIcon(riskLevel),
        badge: '/icons/badge-72.png',
        tag: eventId ?? `security-${Date.now()}`, // Deduplicate by event ID
        requireInteraction: riskLevel === 'high' || riskLevel === 'critical',
        silent: riskLevel === 'low',
        data: {
          camera,
          riskLevel,
          eventId,
        },
      };

      await showNotification(title, notificationOptions);
    },
    [showNotification, riskFilters]
  );

  /**
   * Enable or disable push notifications
   */
  const setEnabled = useCallback((newEnabled: boolean): void => {
    setIsEnabled(newEnabled);
  }, []);

  return {
    permission,
    isSupported,
    hasPermission,
    hasInteracted,
    isSubscribed,
    isEnabled,
    setEnabled,
    requestPermission,
    showNotification,
    showSecurityAlert,
  };
}
