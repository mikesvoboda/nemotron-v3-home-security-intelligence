/**
 * useIntegratedNotifications hook
 *
 * A composite hook that integrates desktop, push, and audio notifications
 * with backend notification preferences. This ensures all notification
 * channels respect the user's saved preferences including:
 * - Global enabled/disabled state
 * - Sound preferences
 * - Risk level filters
 * - Quiet hours (via backend enforcement)
 *
 * @module hooks/useIntegratedNotifications
 */

import { useMemo, useCallback } from 'react';

import { useNotificationPreferences } from './useNotificationPreferences';
import {
  useDesktopNotifications,
  type SecurityAlertNotificationOptions,
} from './useDesktopNotifications';
import { useAudioNotifications } from './useAudioNotifications';
import {
  usePushNotifications,
  type SecurityAlertOptions as PushSecurityAlertOptions,
} from './usePushNotifications';
import { type RiskLevel } from '../utils/risk';

export interface IntegratedNotificationOptions {
  /**
   * Whether to suppress desktop notifications when window has focus
   * @default false
   */
  suppressWhenFocused?: boolean;
  /**
   * Default auto-close timeout for desktop notifications in milliseconds
   * @default 5000
   */
  defaultAutoCloseMs?: number;
  /**
   * Initial volume for audio notifications (0.0 to 1.0)
   * @default 0.5
   */
  initialVolume?: number;
  /**
   * Base path for audio files
   * @default '/sounds'
   */
  soundsPath?: string;
}

export interface SecurityAlertOptions {
  /** Camera name/identifier */
  camera: string;
  /** Risk level of the alert */
  riskLevel: RiskLevel;
  /** Brief summary of the detection */
  summary: string;
  /** Optional event ID for deduplication */
  eventId?: string;
  /** Callback when notification is clicked */
  onClick?: () => void;
}

export interface UseIntegratedNotificationsReturn {
  // Global preferences state
  /** Whether notifications are globally enabled */
  isEnabled: boolean;
  /** Whether preferences are loading */
  isLoading: boolean;
  /** Error from loading preferences */
  error: Error | null;
  /** Current sound preference */
  soundPreference: string;
  /** Current risk level filters */
  riskFilters: string[];

  // Desktop notifications
  /** Desktop notification permission state */
  desktopPermission: NotificationPermission;
  /** Whether desktop notifications are supported */
  desktopSupported: boolean;
  /** Whether desktop notifications have permission */
  desktopHasPermission: boolean;
  /** Request desktop notification permission */
  requestDesktopPermission: () => Promise<NotificationPermission>;

  // Push notifications
  /** Push notification permission state */
  pushPermission: NotificationPermission;
  /** Whether push notifications are supported */
  pushSupported: boolean;
  /** Whether push notifications have permission */
  pushHasPermission: boolean;
  /** Whether we have an active push subscription */
  pushIsSubscribed: boolean;
  /** Request push notification permission */
  requestPushPermission: () => Promise<NotificationPermission>;

  // Audio notifications
  /** Current audio volume */
  audioVolume: number;
  /** Set audio volume */
  setAudioVolume: (volume: number) => void;
  /** Whether audio is ready */
  audioReady: boolean;
  /** Resume audio context after user interaction */
  resumeAudio: () => Promise<void>;

  // Unified actions
  /** Show a security alert through all enabled channels */
  showSecurityAlert: (options: SecurityAlertOptions) => Promise<void>;
  /** Toggle global notifications on/off */
  toggleNotifications: () => void;
  /** Close all active notifications */
  closeAllNotifications: () => void;

  // Preferences mutations
  /** Update notification preferences */
  updatePreferences: (update: {
    enabled?: boolean;
    sound?: string;
    risk_filters?: string[];
  }) => void;
  /** Whether a preference update is pending */
  isUpdating: boolean;
}

/**
 * Hook to manage integrated notifications with backend preferences.
 *
 * This hook combines desktop, push, and audio notifications into a single
 * interface that respects user preferences stored in the backend.
 *
 * @example
 * ```tsx
 * const {
 *   isEnabled,
 *   showSecurityAlert,
 *   toggleNotifications,
 *   requestDesktopPermission,
 *   audioVolume,
 *   setAudioVolume,
 * } = useIntegratedNotifications();
 *
 * // Request permissions on user action
 * const handleEnable = async () => {
 *   await requestDesktopPermission();
 * };
 *
 * // Show alert when event arrives
 * useEffect(() => {
 *   if (newEvent && isEnabled) {
 *     showSecurityAlert({
 *       camera: newEvent.camera_id,
 *       riskLevel: newEvent.risk_level,
 *       summary: newEvent.summary,
 *       onClick: () => navigate(`/events/${newEvent.id}`),
 *     });
 *   }
 * }, [newEvent, isEnabled, showSecurityAlert]);
 * ```
 */
export function useIntegratedNotifications(
  options: IntegratedNotificationOptions = {}
): UseIntegratedNotificationsReturn {
  const {
    suppressWhenFocused = false,
    defaultAutoCloseMs = 5000,
    initialVolume = 0.5,
    soundsPath = '/sounds',
  } = options;

  // Get backend preferences
  const {
    preferences,
    isLoading,
    error,
    updateMutation,
  } = useNotificationPreferences();

  // Extract preference values with defaults
  const isEnabled = preferences?.enabled ?? true;
  const soundPreference = preferences?.sound ?? 'default';
  const riskFilters = useMemo(
    () => preferences?.risk_filters ?? ['critical', 'high', 'medium'],
    [preferences?.risk_filters]
  );

  // Initialize notification hooks with preferences
  const desktop = useDesktopNotifications({
    enabled: isEnabled,
    suppressWhenFocused,
    defaultAutoCloseMs,
    riskFilters,
  });

  const push = usePushNotifications({
    enabled: isEnabled,
    riskFilters,
  });

  const audio = useAudioNotifications({
    enabled: isEnabled,
    initialVolume,
    soundsPath,
    soundPreference,
    riskFilters,
  });

  /**
   * Show a security alert through all enabled channels
   */
  const showSecurityAlert = useCallback(
    async (alertOptions: SecurityAlertOptions): Promise<void> => {
      if (!isEnabled) {
        return;
      }

      const { camera, riskLevel, summary, eventId, onClick } = alertOptions;

      // Check if this risk level is in the filters
      if (riskFilters.length > 0 && !riskFilters.includes(riskLevel)) {
        return;
      }

      // Show desktop notification
      const desktopOptions: SecurityAlertNotificationOptions = {
        camera,
        riskLevel,
        summary,
        eventId,
        onClick,
      };
      desktop.showSecurityAlert(desktopOptions);

      // Show push notification (service worker)
      const pushOptions: PushSecurityAlertOptions = {
        camera,
        riskLevel,
        summary,
        eventId,
      };
      await push.showSecurityAlert(pushOptions);

      // Play audio alert
      await audio.playRiskSound(riskLevel);
    },
    [isEnabled, riskFilters, desktop, push, audio]
  );

  /**
   * Toggle global notifications on/off
   */
  const toggleNotifications = useCallback(() => {
    updateMutation.mutate({ enabled: !isEnabled });
  }, [updateMutation, isEnabled]);

  /**
   * Update notification preferences
   */
  const updatePreferences = useCallback(
    (update: { enabled?: boolean; sound?: string; risk_filters?: string[] }) => {
      updateMutation.mutate(update);
    },
    [updateMutation]
  );

  /**
   * Close all active notifications
   */
  const closeAllNotifications = useCallback(() => {
    desktop.closeAll();
    audio.stopAll();
  }, [desktop, audio]);

  return {
    // Global preferences state
    isEnabled,
    isLoading,
    error,
    soundPreference,
    riskFilters,

    // Desktop notifications
    desktopPermission: desktop.permission,
    desktopSupported: desktop.isSupported,
    desktopHasPermission: desktop.hasPermission,
    requestDesktopPermission: desktop.requestPermission,

    // Push notifications
    pushPermission: push.permission,
    pushSupported: push.isSupported,
    pushHasPermission: push.hasPermission,
    pushIsSubscribed: push.isSubscribed,
    requestPushPermission: push.requestPermission,

    // Audio notifications
    audioVolume: audio.volume,
    setAudioVolume: audio.setVolume,
    audioReady: audio.isReady,
    resumeAudio: audio.resume,

    // Unified actions
    showSecurityAlert,
    toggleNotifications,
    closeAllNotifications,

    // Preferences mutations
    updatePreferences,
    isUpdating: updateMutation.isPending,
  };
}

export default useIntegratedNotifications;
