/**
 * TypeScript types for Notification Preferences API
 *
 * Mirrors backend schemas from:
 * @see backend/api/schemas/notification_preferences.py
 * @see backend/api/routes/notification_preferences.py
 */

// ============================================================================
// Enums and Constants
// ============================================================================

/**
 * Days of the week for quiet hours scheduling.
 */
export type DayOfWeek =
  | 'monday'
  | 'tuesday'
  | 'wednesday'
  | 'thursday'
  | 'friday'
  | 'saturday'
  | 'sunday';

/**
 * Day of week options with labels for UI display.
 */
export const DAYS_OF_WEEK: ReadonlyArray<{ value: DayOfWeek; label: string; short: string }> = [
  { value: 'monday', label: 'Monday', short: 'Mon' },
  { value: 'tuesday', label: 'Tuesday', short: 'Tue' },
  { value: 'wednesday', label: 'Wednesday', short: 'Wed' },
  { value: 'thursday', label: 'Thursday', short: 'Thu' },
  { value: 'friday', label: 'Friday', short: 'Fri' },
  { value: 'saturday', label: 'Saturday', short: 'Sat' },
  { value: 'sunday', label: 'Sunday', short: 'Sun' },
] as const;

/**
 * Notification sound options.
 */
export type NotificationSound = 'none' | 'default' | 'alert' | 'chime' | 'urgent';

/**
 * Sound options with labels for UI display.
 */
export const NOTIFICATION_SOUNDS: ReadonlyArray<{ value: NotificationSound; label: string }> = [
  { value: 'none', label: 'None (Silent)' },
  { value: 'default', label: 'Default' },
  { value: 'alert', label: 'Alert' },
  { value: 'chime', label: 'Chime' },
  { value: 'urgent', label: 'Urgent' },
] as const;

/**
 * Risk level options.
 */
export type RiskLevel = 'critical' | 'high' | 'medium' | 'low';

/**
 * Risk level options with labels for UI display.
 */
export const RISK_LEVELS: ReadonlyArray<{ value: RiskLevel; label: string; color: string }> = [
  { value: 'critical', label: 'Critical', color: 'red' },
  { value: 'high', label: 'High', color: 'orange' },
  { value: 'medium', label: 'Medium', color: 'yellow' },
  { value: 'low', label: 'Low', color: 'green' },
] as const;

// ============================================================================
// Global Preferences Types
// ============================================================================

/**
 * Global notification preferences response.
 */
export interface NotificationPreferences {
  id: number;
  enabled: boolean;
  sound: NotificationSound;
  risk_filters: RiskLevel[];
}

/**
 * Request to update global notification preferences.
 */
export interface NotificationPreferencesUpdate {
  enabled?: boolean;
  sound?: NotificationSound;
  risk_filters?: RiskLevel[];
}

// ============================================================================
// Camera Notification Settings Types
// ============================================================================

/**
 * Camera notification setting response.
 */
export interface CameraNotificationSetting {
  id: string;
  camera_id: string;
  enabled: boolean;
  risk_threshold: number;
}

/**
 * Request to update camera notification setting.
 */
export interface CameraNotificationSettingUpdate {
  enabled?: boolean;
  risk_threshold?: number;
}

/**
 * Camera notification settings list response.
 */
export interface CameraNotificationSettingsListResponse {
  items: CameraNotificationSetting[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

// ============================================================================
// Quiet Hours Types
// ============================================================================

/**
 * Quiet hours period response.
 */
export interface QuietHoursPeriod {
  id: string;
  label: string;
  start_time: string; // HH:MM:SS format
  end_time: string; // HH:MM:SS format
  days: DayOfWeek[];
}

/**
 * Request to create a quiet hours period.
 */
export interface QuietHoursPeriodCreate {
  label: string;
  start_time: string; // HH:MM:SS format
  end_time: string; // HH:MM:SS format
  days: DayOfWeek[];
}

/**
 * Quiet hours periods list response.
 */
export interface QuietHoursPeriodsListResponse {
  items: QuietHoursPeriod[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

// ============================================================================
// Notification History Types
// ============================================================================

/**
 * Notification channel types for history entries.
 */
export type NotificationChannel = 'email' | 'webhook' | 'push';

/**
 * A single notification delivery history entry.
 * Mirrors backend schema: backend/api/schemas/notification.py:NotificationHistoryEntry
 */
export interface NotificationHistoryEntry {
  /** Unique identifier for this delivery record */
  id: string;
  /** Alert ID that triggered this notification */
  alert_id: string;
  /** Notification channel used (email, webhook, push) */
  channel: NotificationChannel;
  /** Recipient identifier (email address, webhook URL, etc.) */
  recipient: string | null;
  /** Whether the delivery was successful */
  success: boolean;
  /** Error message if delivery failed */
  error: string | null;
  /** Timestamp when notification was delivered (ISO 8601) */
  delivered_at: string | null;
  /** Timestamp when record was created (ISO 8601) */
  created_at: string;
}

/**
 * Response containing paginated notification history.
 * Mirrors backend schema: backend/api/schemas/notification.py:NotificationHistoryResponse
 */
export interface NotificationHistoryResponse {
  /** List of notification history entries */
  entries: NotificationHistoryEntry[];
  /** Total count of entries matching filters */
  count: number;
  /** Maximum number of results returned */
  limit: number;
  /** Number of results skipped */
  offset: number;
}

/**
 * Query parameters for fetching notification history.
 */
export interface NotificationHistoryQueryParams {
  /** Filter by alert ID */
  alert_id?: string;
  /** Filter by notification channel */
  channel?: NotificationChannel;
  /** Filter by success status */
  success?: boolean;
  /** Maximum number of results (1-100, default 50) */
  limit?: number;
  /** Number of results to skip (default 0) */
  offset?: number;
}
