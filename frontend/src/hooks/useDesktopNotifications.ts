/**
 * useDesktopNotifications hook
 *
 * Manages browser desktop notifications with permission handling,
 * auto-close functionality, and focus-based suppression.
 */

import { useState, useCallback, useEffect, useRef } from 'react';

import { type RiskLevel } from '../utils/risk';

export interface DesktopNotificationOptions {
  /**
   * The notification title
   */
  title: string;
  /**
   * The notification body text
   */
  body?: string;
  /**
   * Icon URL for the notification
   */
  icon?: string;
  /**
   * Badge icon URL (for mobile)
   */
  badge?: string;
  /**
   * Notification tag for deduplication
   */
  tag?: string;
  /**
   * Whether the notification should remain visible until user interacts
   */
  requireInteraction?: boolean;
  /**
   * Whether to show the notification silently (no sound/vibration)
   */
  silent?: boolean;
  /**
   * Auto-close timeout in milliseconds
   * @default 5000
   */
  autoCloseMs?: number;
  /**
   * Callback when notification is clicked
   */
  onClick?: () => void;
  /**
   * Callback when notification is closed
   */
  onClose?: () => void;
}

export interface SecurityAlertNotificationOptions {
  /**
   * Camera name/identifier
   */
  camera: string;
  /**
   * Risk level of the alert
   */
  riskLevel: RiskLevel;
  /**
   * Brief summary of the detection
   */
  summary: string;
  /**
   * Optional event ID for deduplication
   */
  eventId?: string;
  /**
   * Callback when notification is clicked
   */
  onClick?: () => void;
}

export interface UseDesktopNotificationsOptions {
  /**
   * Whether notifications are enabled
   * @default true
   */
  enabled?: boolean;
  /**
   * Default auto-close timeout in milliseconds
   * @default 5000
   */
  defaultAutoCloseMs?: number;
  /**
   * Whether to suppress notifications when window has focus
   * @default false
   */
  suppressWhenFocused?: boolean;
}

export interface UseDesktopNotificationsReturn {
  /**
   * Current permission state
   */
  permission: NotificationPermission;
  /**
   * Whether notifications are supported in this browser
   */
  isSupported: boolean;
  /**
   * Whether user has granted notification permission
   */
  hasPermission: boolean;
  /**
   * Whether user has denied notification permission
   */
  isDenied: boolean;
  /**
   * Whether notifications are currently enabled
   */
  isEnabled: boolean;
  /**
   * Enable or disable notifications
   */
  setEnabled: (enabled: boolean) => void;
  /**
   * Request notification permission from user
   */
  requestPermission: () => Promise<NotificationPermission>;
  /**
   * Show a desktop notification
   */
  showNotification: (options: DesktopNotificationOptions) => Notification | null;
  /**
   * Show a security alert notification with standardized formatting
   */
  showSecurityAlert: (options: SecurityAlertNotificationOptions) => Notification | null;
  /**
   * Close all active notifications
   */
  closeAll: () => void;
}

/**
 * Get risk level prefix for notification title
 */
function getRiskPrefix(riskLevel: RiskLevel): string {
  const prefixes: Record<RiskLevel, string> = {
    low: '[LOW]',
    medium: '[MEDIUM]',
    high: '[HIGH]',
    critical: '[CRITICAL]',
  };
  return prefixes[riskLevel];
}

/**
 * Get appropriate icon for risk level
 */
function getRiskIcon(riskLevel: RiskLevel): string {
  // Use alert icon for high/critical, standard icon otherwise
  if (riskLevel === 'high' || riskLevel === 'critical') {
    return '/icons/badge-72.png';
  }
  return '/icons/icon-192.png';
}

/**
 * Hook to manage desktop notifications.
 *
 * @example
 * ```tsx
 * const {
 *   permission,
 *   hasPermission,
 *   requestPermission,
 *   showSecurityAlert,
 *   isEnabled,
 *   setEnabled
 * } = useDesktopNotifications();
 *
 * // Request permission
 * const handleEnable = async () => {
 *   await requestPermission();
 * };
 *
 * // Show notification for new event
 * useEffect(() => {
 *   if (newEvent && hasPermission && isEnabled) {
 *     showSecurityAlert({
 *       camera: newEvent.camera_id,
 *       riskLevel: newEvent.riskLevel,
 *       summary: newEvent.summary,
 *     });
 *   }
 * }, [newEvent, hasPermission, isEnabled, showSecurityAlert]);
 * ```
 */
export function useDesktopNotifications(
  options: UseDesktopNotificationsOptions = {}
): UseDesktopNotificationsReturn {
  const {
    enabled: initialEnabled = true,
    defaultAutoCloseMs = 5000,
    suppressWhenFocused = false,
  } = options;

  const [permission, setPermission] = useState<NotificationPermission>(() => {
    if (typeof window === 'undefined' || typeof Notification === 'undefined') {
      return 'denied';
    }
    return Notification.permission;
  });
  const [isEnabled, setIsEnabled] = useState(initialEnabled);
  const [isFocused, setIsFocused] = useState(() => {
    if (typeof document === 'undefined') return true;
    return document.hasFocus();
  });

  // Track active notifications for cleanup
  const activeNotificationsRef = useRef<Set<Notification>>(new Set());
  // Track auto-close timers
  const timersRef = useRef<Map<Notification, ReturnType<typeof setTimeout>>>(new Map());

  // Check if notifications are supported
  const isSupported = typeof window !== 'undefined' && typeof Notification !== 'undefined';
  const hasPermission = permission === 'granted';
  const isDenied = permission === 'denied';

  // Track window focus state
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleFocus = () => setIsFocused(true);
    const handleBlur = () => setIsFocused(false);

    window.addEventListener('focus', handleFocus);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('blur', handleBlur);
    };
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    // Capture refs for cleanup
    const timers = timersRef.current;
    const activeNotifications = activeNotificationsRef.current;

    return () => {
      // Clear all timers
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
      // Close all notifications
      activeNotifications.forEach((notification) => {
        try {
          notification.close();
        } catch {
          // Ignore errors
        }
      });
      activeNotifications.clear();
    };
  }, []);

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
   * Show a desktop notification
   */
  const showNotification = useCallback(
    (notificationOptions: DesktopNotificationOptions): Notification | null => {
      // Check prerequisites
      if (!isSupported || !hasPermission || !isEnabled) {
        return null;
      }

      // Suppress if window has focus and option is enabled
      if (suppressWhenFocused && isFocused) {
        return null;
      }

      const {
        title,
        body,
        icon,
        badge,
        tag,
        requireInteraction,
        silent,
        autoCloseMs = defaultAutoCloseMs,
        onClick,
        onClose,
      } = notificationOptions;

      try {
        const notification = new Notification(title, {
          body,
          icon,
          badge,
          tag,
          requireInteraction,
          silent,
        });

        // Track active notification
        activeNotificationsRef.current.add(notification);

        // Handle click
        if (onClick) {
          notification.onclick = () => {
            onClick();
            // Focus window and close notification
            window.focus();
            notification.close();
          };
        }

        // Handle close
        notification.onclose = () => {
          activeNotificationsRef.current.delete(notification);
          const timer = timersRef.current.get(notification);
          if (timer) {
            clearTimeout(timer);
            timersRef.current.delete(notification);
          }
          onClose?.();
        };

        // Auto-close after timeout (unless requireInteraction)
        if (!requireInteraction && autoCloseMs > 0) {
          const timer = setTimeout(() => {
            notification.close();
          }, autoCloseMs);
          timersRef.current.set(notification, timer);
        }

        return notification;
      } catch (error) {
        console.warn('Failed to show notification:', error);
        return null;
      }
    },
    [isSupported, hasPermission, isEnabled, suppressWhenFocused, isFocused, defaultAutoCloseMs]
  );

  /**
   * Show a security alert notification with standardized formatting
   */
  const showSecurityAlert = useCallback(
    (alertOptions: SecurityAlertNotificationOptions): Notification | null => {
      const { camera, riskLevel, summary, eventId, onClick } = alertOptions;

      const title = `${getRiskPrefix(riskLevel)} ${camera}`;
      const icon = getRiskIcon(riskLevel);

      // Critical/high alerts require interaction and are not silent
      const requireInteraction = riskLevel === 'high' || riskLevel === 'critical';
      const silent = riskLevel === 'low';

      return showNotification({
        title,
        body: summary,
        icon,
        badge: '/icons/badge-72.png',
        tag: eventId ?? `security-${Date.now()}`,
        requireInteraction,
        silent,
        onClick,
      });
    },
    [showNotification]
  );

  /**
   * Close all active notifications
   */
  const closeAll = useCallback(() => {
    activeNotificationsRef.current.forEach((notification) => {
      try {
        notification.close();
      } catch {
        // Ignore errors
      }
    });
    activeNotificationsRef.current.clear();

    // Clear all timers
    timersRef.current.forEach((timer) => clearTimeout(timer));
    timersRef.current.clear();
  }, []);

  /**
   * Set enabled state
   */
  const setEnabled = useCallback((newEnabled: boolean) => {
    setIsEnabled(newEnabled);
    if (!newEnabled) {
      // Close all notifications when disabled
      activeNotificationsRef.current.forEach((notification) => {
        try {
          notification.close();
        } catch {
          // Ignore errors
        }
      });
      activeNotificationsRef.current.clear();
    }
  }, []);

  return {
    permission,
    isSupported,
    hasPermission,
    isDenied,
    isEnabled,
    setEnabled,
    requestPermission,
    showNotification,
    showSecurityAlert,
    closeAll,
  };
}

export default useDesktopNotifications;
